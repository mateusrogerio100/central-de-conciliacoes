"""
Casamento dos pagamentos do Razão com as rescisões (ESPECIFICACAO seção 17.2).

Para cada pagamento, os candidatos são as rescisões ainda não baixadas com o mesmo nome, vindas dos PDFs
usados no mês E da lista de pendentes do mês anterior (regra corrigida pelo usuário, out/2026):
- se algum candidato tem o VALOR IGUAL ao pago (± R$ 0,01), fica esse; empatando, o da lista anterior
  (é a rescisão mais antiga). Ex.: a pessoa está na lista de maio com o valor exato pago e no PDF de
  junho com outro valor (novo cálculo, ainda não pago) → baixa a de maio; a de junho vai para a lista nova;
- se nenhum tem o valor igual, vale a prioridade de antes: PDF primeiro, depois a lista anterior
  (e a diferença vai para a aba "Valores diferentes").
Cada rescisão só pode ser baixada uma vez.

1ª volta — nome idêntico (sem acento, maiúsculas, pontuação e "de/da/do/dos/das/e").
2ª volta — nome parecido, para quem sobrou: "Barretto" × "Barreto", sobrenome a mais
   ("... Coelho"), letra no lugar do nome ("Paulo Henrique R Teixeira"). O primeiro nome precisa
   ser o mesmo. Casa com nota ≥ 0,85, ou nota ≥ 0,70 quando o valor é igual.
Um nome idêntico nunca perde para um parecido (a 1ª volta vem antes). Em cada volta, primeiro se
casam os pagamentos que têm candidato de valor igual, depois os outros (assim um pagamento sem valor
igual não "rouba" a rescisão de valor exato de outro pagamento).

Valor pago diferente do valor da rescisão achada: o pagamento aparece na aba "Valores diferentes", para análise.
- pago A MENOR: o que faltou pagar (rescisão − pago) continua na lista nova, no lugar da rescisão, com a origem
  "... – restante (pago R$ X em dd/mm/aaaa)" (pedido do usuário, out/2026: ainda falta pagar);
- pago A MAIOR: a rescisão sai da lista e a diferença vai para a composição da diferença (rodapé).
O que não foi baixado (PDF + pendentes) forma a lista nova de "Rescisões a pagar".

Pagamento não encontrado ganha uma observação (primeira regra que se aplicar, com a mesma
semelhança de nomes):
a) a pessoa está num PDF usado ou na lista anterior, mas a rescisão já foi baixada por outro pagamento;
b) a pessoa está num PDF que NÃO entrou no mês (ex.: complementar do mês seguinte);
c) o nome está no rodapé da lista anterior (composição da diferença, títulos a lançar...);
d) sem rescisão correspondente.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from difflib import SequenceMatcher

from modulos.conciliacao_rescisoes.fornecedores.leitores import reais
from modulos.conciliacao_rescisoes.modelos import (
    ORIGEM_NAO_ENCONTRADO,
    REGRA_JA_BAIXADA,
    REGRA_PDF_FORA_DO_MES,
    REGRA_RODAPE,
    REGRA_SEM_RESCISAO,
    ORIGEM_PDF,
    ORIGEM_PENDENTE,
    Baixa,
    ItemLista,
    Pagamento,
    Pendente,
    RescisaoMes,
)

NOTA_MINIMA = 0.85
NOTA_MINIMA_VALOR_IGUAL = 0.70
NOTA_CONTIDO = 0.95                      # todas as palavras do nome curto (3 ou mais) estão no longo
NOTA_CONTIDO_CURTO = 0.75                # idem, nome curto com só 2 palavras (precisa do valor igual)
PALAVRAS_VAZIAS = frozenset({"de", "da", "do", "dos", "das", "e"})
TOLERANCIA_VALOR = Decimal("0.01")       # "valor igual ao pago"


def palavras_do_nome(nome: str) -> list[str]:
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower()
    return [p for p in re.findall(r"[a-z]+", sem_acento) if p not in PALAVRAS_VAZIAS]


def _palavra_bate(curta: str, longas: list[str]) -> bool:
    for longa in longas:
        if curta == longa or (len(curta) == 1 and longa.startswith(curta)):
            return True
        if len(curta) > 3 and SequenceMatcher(None, curta, longa).ratio() >= 0.85:
            return True
    return False


def nota_nome(nome_a: str, nome_b: str) -> float:
    """Semelhança de dois nomes de pessoa (0 a 1; 1 = idênticos)."""
    a, b = palavras_do_nome(nome_a), palavras_do_nome(nome_b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if SequenceMatcher(None, a[0], b[0]).ratio() < 0.8:
        return 0.0                       # primeiro nome diferente: outra pessoa
    parecido = SequenceMatcher(None, " ".join(a), " ".join(b)).ratio()
    curto, longo = sorted((a, b), key=len)
    contido = 0.0
    if all(_palavra_bate(p, longo) for p in curto):
        contido = NOTA_CONTIDO if len(curto) >= 3 else NOTA_CONTIDO_CURTO
    return round(min(max(parecido, contido), 0.99), 2)


def _aceita(nota: float, valor_igual: bool) -> bool:
    return nota >= NOTA_MINIMA or (valor_igual and nota >= NOTA_MINIMA_VALOR_IGUAL)


def valor_igual(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) <= TOLERANCIA_VALOR


@dataclass
class Conciliacao:
    baixas: list[Baixa] = field(default_factory=list)
    lista_nova: list[ItemLista] = field(default_factory=list)


def conciliar(pagamentos: list[Pagamento], rescisoes: list[RescisaoMes], pendentes: list[Pendente],
              periodo_do_mes: object, rodape: list[tuple[str, Decimal | None]] = (),
              fora_do_mes: list[RescisaoMes] = ()) -> Conciliacao:
    """fora_do_mes: rescisões dos PDFs que não entraram no mês (só para a observação b)."""
    usados = {"pdf": set(), "pendente": set()}
    baixas: dict[int, Baixa] = {}
    de_onde: dict[int, tuple[str, int]] = {}                    # posição do pagamento → (fonte, índice)
    fontes = (("pdf", rescisoes), ("pendente", pendentes))      # ordem = prioridade sem valor igual

    def candidatos(pagamento: Pagamento, so_identico: bool):
        """[(fonte, índice, nota, valor igual)] das rescisões não baixadas com o mesmo nome."""
        achados = []
        for fonte, lista in fontes:
            for indice, candidato in enumerate(lista):
                if indice in usados[fonte]:
                    continue
                nota = nota_nome(pagamento.nome, candidato.nome)
                igual = valor_igual(candidato.valor, pagamento.valor)
                if (so_identico and nota < 1.0) or (not so_identico and not _aceita(nota, igual)):
                    continue
                achados.append((fonte, indice, nota, igual))
        return achados

    def escolher(achados):
        iguais = [a for a in achados if a[3]]
        if iguais:
            # valor igual: a lista anterior primeiro (rescisão mais antiga), depois a maior nota
            return max(iguais, key=lambda a: (a[0] == "pendente", a[2], -a[1]))
        # sem valor igual: PDF primeiro, depois a lista anterior; em cada uma, a maior nota
        for fonte, _ in fontes:
            da_fonte = [a for a in achados if a[0] == fonte]
            if da_fonte:
                return max(da_fonte, key=lambda a: (a[2], -a[1]))
        return None

    def baixar(posicao: int, pagamento: Pagamento, escolhido) -> None:
        fonte, indice, nota, _ = escolhido
        usados[fonte].add(indice)
        de_onde[posicao] = (fonte, indice)
        if fonte == "pdf":
            baixas[posicao] = Baixa(pagamento, ORIGEM_PDF, rescisao=rescisoes[indice], nota=nota)
        else:
            baixas[posicao] = Baixa(pagamento, ORIGEM_PENDENTE, pendente=pendentes[indice], nota=nota)

    for so_identico in (True, False):
        for so_valor_igual in (True, False):
            for posicao, pagamento in enumerate(pagamentos):
                if posicao in baixas:
                    continue
                achados = candidatos(pagamento, so_identico)
                if so_valor_igual:
                    achados = [a for a in achados if a[3]]
                escolhido = escolher(achados)
                if escolhido is not None:
                    baixar(posicao, pagamento, escolhido)

    resultado = Conciliacao()
    resultado.baixas = [baixas.get(posicao) or Baixa(pagamento, ORIGEM_NAO_ENCONTRADO)
                        for posicao, pagamento in enumerate(pagamentos)]
    # pago a menor: a posição da rescisão na sua lista → a baixa (o restante continua na lista nova)
    a_menor = {de_onde[posicao]: baixa for posicao, baixa in baixas.items() if baixa.diferenca > 0}
    lista_nova = []
    for i, p in enumerate(pendentes):
        if i not in usados["pendente"]:
            lista_nova.append(ItemLista(p.periodo, p.nome, p.valor, ORIGEM_PENDENTE))
        elif ("pendente", i) in a_menor:
            baixa = a_menor[("pendente", i)]
            lista_nova.append(ItemLista(p.periodo, p.nome, baixa.diferenca, ORIGEM_PENDENTE, restante_de=baixa))
    for i, r in enumerate(rescisoes):
        if i not in usados["pdf"]:
            lista_nova.append(ItemLista(periodo_do_mes, r.nome, r.valor, ORIGEM_PDF, pdf=r.pdf))
        elif ("pdf", i) in a_menor:
            baixa = a_menor[("pdf", i)]
            lista_nova.append(ItemLista(periodo_do_mes, r.nome, baixa.diferenca, ORIGEM_PDF, pdf=r.pdf,
                                        restante_de=baixa))
    resultado.lista_nova = lista_nova
    observar_nao_encontrados(resultado.baixas, rodape, fora_do_mes)
    return resultado


def _texto_ja_baixada(valor_rescisao: Decimal, origem: str, anterior: Baixa) -> str:
    pago = anterior.pagamento
    data = f"{pago.data:%d/%m}" if pago.data else "data não informada"
    bordero = f", borderô {pago.bordero}" if pago.bordero else ""
    return f"Rescisão de R$ {reais(valor_rescisao)} ({origem}) já baixada pelo pagamento de {data}{bordero}."


def _nome_do_rodape(texto: str) -> str:
    """"FULANO DE TAL - Calculo 1635 mês 06" → "FULANO DE TAL"."""
    return texto.split(" - ")[0]


def observar_nao_encontrados(baixas: list[Baixa], rodape: list[tuple[str, Decimal | None]] = (),
                             fora_do_mes: list[RescisaoMes] = ()) -> None:
    """Preenche regra e observação dos pagamentos não encontrados (não muda nenhum casamento)."""
    achadas = [b for b in baixas if b.origem != ORIGEM_NAO_ENCONTRADO]

    def parece(pagamento: Pagamento, nome: str, valor: Decimal | None) -> float | None:
        nota = nota_nome(pagamento.nome, nome)
        return nota if _aceita(nota, valor is not None and valor_igual(valor, pagamento.valor)) else None

    def ja_baixada(pagamento: Pagamento) -> Baixa | None:
        """O pagamento achado (PDF ou lista anterior) de rescisão com o mesmo nome; maior nota."""
        melhor, nota_melhor = None, None
        for anterior in achadas:
            referencia = anterior.rescisao or anterior.pendente
            nota = parece(pagamento, referencia.nome, referencia.valor)
            if nota is not None and (nota_melhor is None or nota > nota_melhor):
                melhor, nota_melhor = anterior, nota
        return melhor

    for baixa in baixas:
        if baixa.origem != ORIGEM_NAO_ENCONTRADO:
            continue
        pagamento = baixa.pagamento
        anterior = ja_baixada(pagamento)
        if anterior is not None:
            origem = (anterior.rescisao.pdf or "PDF") if anterior.rescisao is not None else "lista anterior"
            baixa.regra, baixa.ja_baixada_por = REGRA_JA_BAIXADA, anterior
            baixa.observacao = _texto_ja_baixada(anterior.valor_referencia, origem, anterior)
            continue
        fora = next((r for r in fora_do_mes if parece(pagamento, r.nome, r.valor) is not None), None)
        if fora is not None:
            data = f"pagamento {fora.data_pagamento:%d/%m}, " if fora.data_pagamento else ""
            baixa.regra = REGRA_PDF_FORA_DO_MES
            formato = "Excel" if (fora.pdf or "").startswith("Excel") else "PDF"
            baixa.observacao = (f"Consta no {formato} {fora.arquivo or fora.pdf} ({data}R$ {reais(fora.valor)}), "
                                "não lançado no razão deste mês.")
            continue
        linha = next((item for item in rodape
                      if _aceita(max(nota_nome(pagamento.nome, _nome_do_rodape(item[0])),
                                     nota_nome(pagamento.nome, item[0])), False)), None)
        if linha is not None:
            texto, valor = linha
            baixa.regra = REGRA_RODAPE
            baixa.observacao = (f"Consta na composição da diferença da lista anterior: '{texto}'"
                                + (f" (R$ {reais(valor)})." if valor is not None else "."))
            continue
        baixa.regra = REGRA_SEM_RESCISAO
        baixa.observacao = "Sem rescisão correspondente."
