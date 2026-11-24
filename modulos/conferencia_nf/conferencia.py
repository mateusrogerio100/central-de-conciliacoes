"""Conferência de cada fato contábil com o PDF da nota. Regras F, C e S da especificação.

Para cada fato: tira do complemento os números de nota, as datas (DT) e o fornecedor (F1-F3);
confere partidas x contrapartidas (F5); separa lançamento e estorno que se anulam (F6); casa
com o PDF (C1-C4); confere número, data e valor (S1-S3a) e dá a situação (S5), com uma frase
para cada problema (S6).

Os PDFs casados ficam com `usada = True` (o relatório lista os que sobraram).
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from difflib import SequenceMatcher

from modulos.conferencia_nf import configuracao as cfg
from modulos.conferencia_nf.modelos import (
    Fato, Lancamento, NotaPdf, NotaSemPdf, Resultado, Retencao, Situacao,
)

# ---------------------------------------------------------------------------
# Formatação (também usada pelo relatório)
# ---------------------------------------------------------------------------


def formatar_valor(valor: Decimal) -> str:
    """Decimal('-1234.5') -> '-1.234,50'."""
    texto = f"{abs(valor):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"-{texto}" if valor < 0 else texto


def formatar_data(data: date | None) -> str:
    return data.strftime("%d/%m/%Y") if data else ""


def formatar_documento(documento: str) -> str:
    """'98765432000430' -> '98.765.432/0004-30'; CPF -> '000.000.000-00'; outro: como veio."""
    if len(documento) == 14:
        d = documento
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    if len(documento) == 11:
        d = documento
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    return documento


def nome_unidade(cnpj: str) -> str:
    """S15: 'AME Cidade Alfa (98.765.432/0004-30)'; CNPJ fora da lista: só o número formatado."""
    nome = cfg.UNIDADES_FUNDACAO.get(cnpj)
    return f"{nome} ({formatar_documento(cnpj)})" if nome else formatar_documento(cnpj)


def sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn")


# ---------------------------------------------------------------------------
# Semelhança de nomes (C2)
# ---------------------------------------------------------------------------


def chave_nome(nome: str) -> str:
    """Maiúsculas, sem acento, sem pontuação e sem LTDA/ME/EPP/DE/DA..."""
    limpo = re.sub(r"[^A-Z0-9 ]", " ", sem_acento(nome).upper())
    return " ".join(p for p in limpo.split() if p not in cfg.PALAVRAS_IGNORADAS_NOME)


def semelhanca_nome(a: str, b: str) -> float:
    """O maior entre a semelhança de letras e a proporção de palavras em comum (sobre o nome com
    menos palavras). 0 a 1."""
    ka, kb = chave_nome(a), chave_nome(b)
    if not ka or not kb:
        return 0.0
    letras = SequenceMatcher(None, ka, kb).ratio()
    pa, pb = set(ka.split()), set(kb.split())
    palavras = len(pa & pb) / min(len(pa), len(pb))
    return max(letras, palavras)


def _mesmo_fornecedor(fornecedor: str, nota: NotaPdf) -> bool:
    return semelhanca_nome(fornecedor, nota.emitente_nome) >= cfg.SEMELHANCA_MINIMA_NOME


# ---------------------------------------------------------------------------
# O que vem do fato (F1-F5)
# ---------------------------------------------------------------------------


def numeros_do_fato(fato: Fato) -> list[str]:
    """F1: números de nota distintos citados nos complementos, sem zeros à esquerda."""
    numeros: list[str] = []
    for lancamento in fato.lancamentos:
        for numero in cfg.RE_NUMERO_NF.findall(lancamento.complemento):
            numero = str(int(numero))
            if numero not in numeros:
                numeros.append(numero)
    return numeros


def datas_do_fato(fato: Fato) -> list[date]:
    """F2: datas (DT) distintas citadas nos complementos. Data impossível é ignorada."""
    datas: list[date] = []
    for lancamento in fato.lancamentos:
        for dia, mes, ano in cfg.RE_DATA_DT.findall(lancamento.complemento):
            try:
                data = date(int(ano), int(mes), int(dia))
            except ValueError:
                continue
            if data not in datas:
                datas.append(data)
    return datas


def fornecedor_do_fato(fato: Fato) -> str:
    """F3: texto do complemento antes de "NF."; sem "NF.", antes de "Recibo" ou do número do
    documento; em último caso, o nome da conta do maior crédito."""
    for lancamento in fato.lancamentos:
        achado = cfg.RE_NUMERO_NF.search(lancamento.complemento)
        if achado and lancamento.complemento[:achado.start()].strip():
            return lancamento.complemento[:achado.start()].strip(" -")
    for lancamento in fato.lancamentos:
        achado = cfg.RE_INICIO_DOCUMENTO.search(lancamento.complemento)
        if achado and lancamento.complemento[:achado.start()].strip(" -"):
            return lancamento.complemento[:achado.start()].strip(" -")
    creditos = [l for l in fato.lancamentos if l.conta_credito]
    return max(creditos, key=lambda l: l.valor).nome_conta if creditos else ""


def partidas_fecham(fato: Fato) -> bool:
    """F5: pelo menos um débito e um crédito, e a soma dos débitos igual à dos créditos."""
    tem_debito = any(l.conta_debito for l in fato.lancamentos)
    tem_credito = any(l.conta_credito for l in fato.lancamentos)
    return tem_debito and tem_credito and fato.total_debito == fato.total_credito


def conta_de_resultado(lancamento: Lancamento) -> bool:
    """S11: classificação começando por 3 ou 4 (receita e despesa)."""
    return lancamento.classificacao.startswith(cfg.CLASSES_COM_CENTRO_CUSTO)


def lancamentos_sem_centro_custo(fato: Fato) -> list[Lancamento]:
    """S11: lançamentos em conta de resultado sem centro de custo (só se o arquivo traz o centro
    de custo; o lote antigo não traz)."""
    if not fato.com_centro_custo:
        return []
    return [l for l in fato.lancamentos if conta_de_resultado(l) and not l.centro_custo]


def rateios(fato: Fato) -> dict[tuple[str, str], list[Lancamento]]:
    """S12: (lado, conta) da conta de resultado dividida em mais de um centro de custo -> os
    lançamentos dela, na ordem do lote. Só informativo."""
    por_conta: dict[tuple[str, str], list[Lancamento]] = {}
    for l in fato.lancamentos:
        if conta_de_resultado(l) and l.centro_custo:
            lado = "D" if l.conta_debito else "C"
            por_conta.setdefault((lado, l.conta_debito or l.conta_credito), []).append(l)
    return {conta: ls for conta, ls in por_conta.items()
            if len({l.centro_custo for l in ls}) > 1}


def total_desconto(fato: Fato) -> Decimal:
    """S3a: soma dos créditos em conta de desconto (desconto lançado à parte)."""
    return sum((l.valor for l in fato.lancamentos if l.conta_credito
                and cfg.TEXTO_CONTA_DESCONTO in sem_acento(l.nome_conta).upper()),
               Decimal("0.00"))


def escriturar_na_prefeitura(r: Resultado) -> bool:
    """S9: nota de serviço, a escriturar no site da prefeitura. Só pelo PDF: o fato casou com uma
    DANFSe. Nota sem PDF fica de fora, mesmo que seja de serviço (o lote não diz o tipo)."""
    return r.nota is not None and r.nota.tipo == cfg.TIPO_NFSE


def nao_optante(r: Resultado) -> bool:
    return escriturar_na_prefeitura(r) and \
        sem_acento(r.nota.regime).upper().startswith(cfg.REGIME_TEXTO_NAO_OPTANTE)


def falar_com_fornecedor(r: Resultado) -> bool:
    """S10: nota de serviço de prestador "Não Optante" sem nenhum imposto federal retido (IRRF,
    Previdência e Contribuições Sociais em branco). O ISS não entra na regra. Só informativo:
    não muda a situação do fato. Federal não lido: fica de fora (o relatório pede para conferir)."""
    if not nao_optante(r) or not r.nota.federais_lidos:
        return False
    n = r.nota
    return n.irrf + n.previdencia_retida + n.contribuicoes_retidas == 0


def aviso_pasta_de_outro_dia(notas: list[NotaPdf]) -> str:
    """S17: a frase de alerta quando quase nenhum PDF casou com o lote ("" se está tudo certo).
    Os repetidos não contam (a primeira cópia é que casa)."""
    lidas = [n for n in notas if not n.repetida_de]
    casadas = sum(1 for n in lidas if n.usada)
    if not lidas or casadas >= len(lidas) * cfg.MINIMO_PDFS_CASADOS:
        return ""
    return cfg.AVISO_PASTA_DE_OUTRO_DIA.format(casados=casadas, lidos=len(lidas))


# ---------------------------------------------------------------------------
# Estorno (F6)
# ---------------------------------------------------------------------------


def _ordem_do_fato(numero: str) -> tuple[int, str]:
    return len(numero), numero


def _mesmo_lancamento(fato: Fato) -> tuple:
    """Dois fatos com os mesmos complementos e o mesmo total são o mesmo lançamento."""
    return tuple(sorted({l.complemento for l in fato.lancamentos})), fato.total_debito


def _invertidos(a: Fato, b: Fato) -> bool:
    """As contas debitadas em um são as creditadas no outro (um estorna o outro)."""
    def contas(fato: Fato, lado: str) -> set[str]:
        return {getattr(l, lado) for l in fato.lancamentos if getattr(l, lado)}
    return contas(a, "conta_debito") == contas(b, "conta_credito") \
        and contas(a, "conta_credito") == contas(b, "conta_debito")


def separar_estornos(fatos: list[Fato]) -> tuple[dict[str, str], dict[tuple, list[Fato]]]:
    """F6. Dentro de cada grupo de fatos iguais, na ordem do número do fato, cada fato invertido
    anula o anterior que ainda está de pé.

    Devolve (fato anulado -> fato que o anula, e vice-versa; grupo -> fatos que ficaram de pé).
    """
    iguais: dict[tuple, list[Fato]] = {}
    for fato in fatos:
        iguais.setdefault(_mesmo_lancamento(fato), []).append(fato)
    anulado_por: dict[str, str] = {}
    de_pe: dict[tuple, list[Fato]] = {}
    for chave, grupo in iguais.items():
        pendentes: list[Fato] = []
        for fato in sorted(grupo, key=lambda f: _ordem_do_fato(f.fato)):
            par = next((p for p in reversed(pendentes) if _invertidos(fato, p)), None)
            if par is None:
                pendentes.append(fato)
            else:
                pendentes.remove(par)
                anulado_por[fato.fato], anulado_por[par.fato] = par.fato, fato.fato
        de_pe[chave] = pendentes
    return anulado_por, de_pe


# ---------------------------------------------------------------------------
# Casamento com o PDF (C1-C4)
# ---------------------------------------------------------------------------


def escolher_nota(candidatas: list[NotaPdf], fornecedor: str, valor: Decimal
                  ) -> tuple[NotaPdf | None, bool]:
    """C3: entre os PDFs com o número do fato, o do mesmo fornecedor. Devolve (nota, fornecedor
    confere). Sem fornecedor parecido, só casa se exatamente um candidato tiver o mesmo valor."""
    if not candidatas:
        return None, False
    melhor = max(candidatas, key=lambda n: (semelhanca_nome(fornecedor, n.emitente_nome),
                                            n.valor == valor))
    if _mesmo_fornecedor(fornecedor, melhor):
        return melhor, True
    mesmo_valor = [n for n in candidatas if n.valor == valor]
    if len(mesmo_valor) == 1:
        return mesmo_valor[0], False
    return None, False


# ---------------------------------------------------------------------------
# Conferência
# ---------------------------------------------------------------------------


def conferir(fatos: list[Fato], notas: list[NotaPdf], sem_pdf: list[NotaSemPdf] | None = None,
             cnpj_unidade: str | None = None) -> list[Resultado]:
    """Um Resultado por fato, na ordem do lote. cnpj_unidade: a unidade escolhida na tela (S15);
    None = não confere o destinatário."""
    por_numero: dict[str, list[NotaPdf]] = {}
    for nota in notas:
        if not nota.repetida_de:
            por_numero.setdefault(nota.numero, []).append(nota)
    numeros_sem_pdf = {s.numero for s in sem_pdf or []}
    usado_por: dict[str, str] = {}          # arquivo do PDF -> fato que ficou com ele
    anulado_por, de_pe = separar_estornos(fatos)

    resultados = []
    for fato in fatos:
        r = Resultado(fato, fornecedor_do_fato(fato), numeros_do_fato(fato), datas_do_fato(fato),
                      partidas_ok=partidas_fecham(fato))
        resultados.append(r)

        validos = de_pe[_mesmo_lancamento(fato)]
        if fato.fato in anulado_por:
            r.situacao = Situacao.ESTORNO
            par = sorted((fato.fato, anulado_por[fato.fato]), key=_ordem_do_fato)
            r.observacoes.append(
                f"Os fatos {par[0]} e {par[1]} são o mesmo lançamento com débito e crédito "
                "invertidos (lançamento e estorno): um anula o outro. "
                + (f"O que vale é o fato {', '.join(f.fato for f in validos)}." if validos
                   else "Não sobrou lançamento deste documento no lote."))
            continue
        _observacoes_do_lancamento(r, validos)

        if not r.numeros:
            r.situacao = Situacao.SEM_NUMERO
            tipo = "recibo" if any(cfg.RE_RECIBO.search(l.complemento) for l in fato.lancamentos) \
                else "doação, taxa ou outro documento"
            r.observacoes.append(f"Complemento sem \"NF. número\" ({tipo}): conferir à mão.")
            continue

        candidatas = [n for numero in r.numeros for n in por_numero.get(numero, []) if not n.usada]
        nota, fornecedor_confere = escolher_nota(candidatas, r.fornecedor, fato.total_debito)
        if nota is None:
            r.situacao = Situacao.SEM_PDF
            r.observacoes.append(_motivo_sem_pdf(r, candidatas, por_numero, usado_por,
                                                 numeros_sem_pdf))
            continue

        nota.usada = True
        usado_por[nota.arquivo] = fato.fato
        r.nota = nota
        _conferir_com_a_nota(r, nota, fornecedor_confere)
    for r in resultados:
        if cnpj_unidade:
            _conferir_destinatario(r, cnpj_unidade)
        _conferir_retencoes(r)
        _conferir_centro_custo(r)
        _conferir_centro_custo_cmd(r)
        _conferir_diluicao(r)
        _conferir_reclassificar(r)
    return resultados


def _creditado(fato: Fato, conta: str) -> Decimal:
    """Créditos menos débitos na conta (estorno de retenção dentro do fato abate)."""
    return sum((l.valor if l.conta_credito == conta else -l.valor for l in fato.lancamentos
                if conta in (l.conta_credito, l.conta_debito)), Decimal("0.00"))


def retencoes_da_nota(r: Resultado) -> list[Retencao]:
    """S13: cada imposto retido na DANFSe x o crédito na conta dele no fato. Vazio se o fato não
    casou com uma DANFSe. Imposto zerado na nota e sem crédito no fato não entra na lista."""
    if not escriturar_na_prefeitura(r):
        return []
    n = r.nota
    conta_irrf = cfg.CONTA_IRRF_PF if len(n.emitente_documento) == 11 else cfg.CONTA_IRRF_PJ
    iss_retido = sem_acento(n.retencao_iss).upper().startswith(cfg.RETENCAO_ISS_RETIDO)
    iss = (n.valor_iss if iss_retido else Decimal("0.00")) if n.retencao_iss else None
    impostos = [("IRRF", conta_irrf, n.irrf), ("INSS", cfg.CONTA_INSS, n.previdencia_retida),
                ("PIS/COFINS/CSLL", cfg.CONTA_PIS_COFINS_CSLL, n.contribuicoes_retidas),
                ("ISS", cfg.CONTA_ISS_RETIDO, iss)]
    retencoes = [Retencao(imposto, conta, valor, _creditado(r.fato, conta))
                 for imposto, conta, valor in impostos]
    return [x for x in retencoes if x.nota != 0 or x.lancado != 0]


def _conferir_destinatario(r: Resultado, cnpj_unidade: str):
    """S15 (pedido do usuário, 19/10/2026): o CNPJ do destinatário (DANFE) ou do tomador (DANFSe)
    tem que ser o da unidade escolhida na tela. Diferente: DIVERGENTE (vermelho). Não lido no PDF:
    CONFERIR (amarelo), para olhar no PDF. Só vale para o fato casado com o PDF."""
    if r.nota is None:
        return
    documento = r.nota.destinatario_documento
    papel = "tomador" if r.nota.tipo == cfg.TIPO_NFSE else "destinatário"
    if not documento:
        r.confere_destinatario = "NÃO LIDO"
        r.observacoes.append(f"CNPJ do {papel} não foi lido na nota: conferir no PDF se é "
                             f"{nome_unidade(cnpj_unidade)}.")
        if r.situacao == Situacao.OK:
            r.situacao = Situacao.CONFERIR
    elif documento == cnpj_unidade:
        r.confere_destinatario = "OK"
    else:
        r.confere_destinatario = "ERRADO"
        outra = "" if documento in cfg.UNIDADES_FUNDACAO else ", que não é de nenhuma unidade da " \
            "Fundação"
        r.observacoes.append(f"CNPJ do {papel} errado: a nota veio para "
                             f"{nome_unidade(documento)}{outra}; a unidade conferida é "
                             f"{nome_unidade(cnpj_unidade)}.")
        r.situacao = Situacao.DIVERGENTE


def _percentual(valor: Decimal) -> str:
    """Decimal('1.5') -> '1,5%'; Decimal('4.65') -> '4,65%'."""
    return f"{valor.normalize():f}".replace(".", ",") + "%"


def _calculado(base: Decimal, aliquota: Decimal) -> Decimal:
    return (base * aliquota / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def codigo_contribuicoes(nota: NotaPdf) -> str | None:
    """S16a: o código do tipo de retenção do PIS/COFINS/CSLL ("Código 3" -> "3"); None se a nota
    não traz o código ou ele não é um dos conhecidos."""
    achado = cfg.RE_CODIGO_CONTRIBUICOES.match(nota.descricao_contribuicoes.strip())
    codigo = achado.group(1) if achado else None
    return codigo if codigo in cfg.CODIGOS_CONTRIBUICOES else None


def aliquotas_erradas(r: Resultado) -> list[str]:
    """S16: cada retenção federal da nota de serviço x a alíquota esperada sobre o valor do serviço
    (até TOLERANCIA_ALIQUOTA de diferença). Imposto zerado ou não lido na nota não é conferido
    aqui; o IRRF de prestador pessoa física (CPF) também não (tabela progressiva).
    S16a: o PIS/COFINS/CSLL usa as alíquotas do código da nota (CODIGOS_CONTRIBUICOES)."""
    if not escriturar_na_prefeitura(r) or not r.nota.valor:
        return []
    n = r.nota
    codigo = codigo_contribuicoes(n)
    aliquotas_contribuicoes = cfg.CODIGOS_CONTRIBUICOES[codigo][1] if codigo \
        else (cfg.ALIQUOTA_PIS_COFINS_CSLL,)
    impostos = [("PIS/COFINS/CSLL", n.contribuicoes_retidas, aliquotas_contribuicoes),
                ("INSS", n.previdencia_retida, cfg.ALIQUOTAS_INSS)]
    if len(n.emitente_documento) != 11:
        impostos.insert(0, ("IRRF", n.irrf, (cfg.ALIQUOTA_IRRF,)))
    frases = []
    for imposto, retido, aliquotas in impostos:
        if not retido:
            continue
        calculados = [_calculado(n.valor, a) for a in aliquotas]
        if any(abs(retido - c) <= cfg.TOLERANCIA_ALIQUOTA for c in calculados):
            continue
        esperado = " ou ".join(f"{_percentual(a)} = R$ {formatar_valor(c)}"
                               for a, c in zip(aliquotas, calculados))
        if imposto == "PIS/COFINS/CSLL" and codigo:
            esperado = f"pelo código {codigo} da nota ({cfg.CODIGOS_CONTRIBUICOES[codigo][0]}) " \
                + esperado
        aplicada = (retido / n.valor * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        frases.append(f"Alíquota do {imposto} da nota: R$ {formatar_valor(retido)} = "
                      f"{_percentual(aplicada)} do serviço (R$ {formatar_valor(n.valor)}); "
                      f"esperado {esperado}.")
    return frases


def _conferir_retencoes(r: Resultado):
    """S13 (decisão do usuário, 16/10/2026): retenção que não bate deixa o fato CONFERIR RETENÇÃO
    (roxo). Se o fato já estiver DIVERGENTE, continua vermelho, com a frase da retenção.
    S16 (19/10/2026): alíquota da retenção diferente da esperada, mesmo tratamento."""
    r.retencoes = retencoes_da_nota(r)
    r.aliquotas_erradas = aliquotas_erradas(r)
    r.observacoes.extend(r.aliquotas_erradas)
    erradas = [x for x in r.retencoes if not x.confere]
    if not erradas:
        if r.aliquotas_erradas and r.situacao in (Situacao.OK, Situacao.CONFERIR):
            r.situacao = Situacao.RETENCAO
        return
    for x in erradas:
        if x.nota is None:
            r.observacoes.append(f"Retenção de {x.imposto}: não foi possível ler na nota; lançado "
                                 f"{formatar_valor(x.lancado)} na conta {x.conta}. Conferir no PDF.")
        else:
            r.observacoes.append(f"Retenção de {x.imposto} (conta {x.conta}): nota "
                                 f"{formatar_valor(x.nota)} x lançado {formatar_valor(x.lancado)}.")
    if r.situacao in (Situacao.OK, Situacao.CONFERIR):
        r.situacao = Situacao.RETENCAO

def _conferir_centro_custo(r: Resultado):
    """S11 (decisão do usuário, 16/10/2026): conta de resultado sem centro de custo deixa o fato
    DIVERGENTE, com ou sem PDF (o erro é do lançamento). O estorno continua estorno."""
    if r.situacao == Situacao.ESTORNO:
        return
    r.sem_centro_custo = lancamentos_sem_centro_custo(r.fato)
    if not r.sem_centro_custo:
        return
    r.situacao = Situacao.DIVERGENTE
    r.observacoes.append(
        "Conta de resultado sem centro de custo: "
        + "; ".join(f"sequência {l.sequencia}, {l.classificacao} {l.nome_conta}, "
                    f"R$ {formatar_valor(l.valor)}" for l in r.sem_centro_custo) + ".")


def _conferir_centro_custo_cmd(r: Resultado):
    """S18 (pedido do usuário, 28/10/2026): lançamento com o centro de custo 539 - CMD deve ir para a
    conta do ativo. Aviso na observação; o fato OK vira CONFERIR (situação pior não muda)."""
    if r.situacao == Situacao.ESTORNO:
        return
    r.centro_custo_cmd = [l for l in r.fato.lancamentos if l.centro_custo in cfg.CENTROS_CUSTO_TROCAR_PELO_ATIVO]
    if not r.centro_custo_cmd:
        return
    if r.situacao == Situacao.OK:
        r.situacao, r.motivo_aviso = Situacao.CONFERIR, cfg.MOTIVO_CENTRO_CUSTO_CMD
    r.observacoes.append(
        f"{cfg.MOTIVO_CENTRO_CUSTO_CMD}: "
        + "; ".join(f"sequência {l.sequencia}, {l.classificacao} {l.nome_conta}, "
                    f"R$ {formatar_valor(l.valor)}" for l in r.centro_custo_cmd) + ".")


def contas_para_diluir(fato: Fato) -> dict[tuple[str, str], list[Lancamento]]:
    """S19: (lado, conta) de despesa ou receita com software, uniforme ou enxoval no nome e mais de
    LIMITE_DILUICAO no fato (somando os lançamentos da conta, como no rateio) -> os lançamentos dela."""
    por_conta: dict[tuple[str, str], list[Lancamento]] = {}
    for l in fato.lancamentos:
        nome = sem_acento(l.nome_conta).lower()
        if conta_de_resultado(l) and any(p in nome for p in cfg.PALAVRAS_DILUICAO):
            lado = "D" if l.conta_debito else "C"
            por_conta.setdefault((lado, l.conta_debito or l.conta_credito), []).append(l)
    return {conta: ls for conta, ls in por_conta.items()
            if sum((l.valor for l in ls), Decimal("0.00")) > cfg.LIMITE_DILUICAO}


def _conferir_diluicao(r: Resultado):
    """S19 (pedido do usuário, 28/10/2026): aviso para ver se o custo ou a despesa pode ser diluído.
    O fato OK vira CONFERIR (situação pior não muda); estorno fica de fora."""
    if r.situacao == Situacao.ESTORNO:
        return
    contas = contas_para_diluir(r.fato)
    if not contas:
        return
    r.diluicao = [l for ls in contas.values() for l in ls]
    if r.situacao == Situacao.OK:
        r.situacao, r.motivo_aviso = Situacao.CONFERIR, cfg.MOTIVO_DILUICAO
    r.observacoes.append(
        f"{cfg.MOTIVO_DILUICAO}: "
        + "; ".join(f"{ls[0].classificacao} {ls[0].nome_conta}, R$ "
                    f"{formatar_valor(sum((l.valor for l in ls), Decimal('0.00')))}" for ls in contas.values())
        + ".")


def lancamentos_a_reclassificar(fato: Fato) -> list[Lancamento]:
    """S20: lançamentos do fato na conta "Fornecedores a reclassificar" (pelo nome)."""
    return [l for l in fato.lancamentos
            if cfg.NOME_FORNECEDORES_RECLASSIFICAR in " ".join(sem_acento(l.nome_conta).lower().split())]


def _conferir_reclassificar(r: Resultado):
    """S20 (pedido do usuário, 06/11/2026): conta "Fornecedores a reclassificar". No crédito, conferir se
    precisa trocar para a conta do próprio fornecedor; no débito, conferir se foi provisionada. O fato OK
    vira CONFERIR (situação pior não muda); estorno fica de fora."""
    if r.situacao == Situacao.ESTORNO:
        return
    r.reclassificar = lancamentos_a_reclassificar(r.fato)
    if not r.reclassificar:
        return
    for motivo, lado in ((cfg.MOTIVO_RECLASSIFICAR_CREDITO, "C"), (cfg.MOTIVO_RECLASSIFICAR_DEBITO, "D")):
        ls = [l for l in r.reclassificar if ("D" if l.conta_debito else "C") == lado]
        if not ls:
            continue
        if r.situacao == Situacao.OK:
            r.situacao, r.motivo_aviso = Situacao.CONFERIR, motivo
        r.observacoes.append(
            f"{motivo}: " + "; ".join(f"sequência {l.sequencia}, {l.classificacao} {l.nome_conta}, "
                                      f"R$ {formatar_valor(l.valor)}" for l in ls) + ".")


def _observacoes_do_lancamento(r: Resultado, validos: list[Fato]):
    """Problemas do próprio lançamento, que valem com ou sem PDF."""
    fato = r.fato
    for outro in validos:
        if outro is not fato:
            r.observacoes.append(f"Mesmo lançamento repetido no fato {outro.fato}.")
    if not r.partidas_ok:
        r.observacoes.append(
            f"Partidas e contrapartidas não fecham: débitos {formatar_valor(fato.total_debito)} "
            f"x créditos {formatar_valor(fato.total_credito)} (diferença "
            f"{formatar_valor(fato.total_debito - fato.total_credito)}).")
    if len(r.numeros) > 1:
        r.observacoes.append("Os lançamentos do fato citam números de nota diferentes: "
                             + ", ".join(r.numeros) + ".")
    if len(r.datas) > 1:
        r.observacoes.append("Os lançamentos do fato citam datas (DT) diferentes: "
                             + ", ".join(formatar_data(d) for d in r.datas) + ".")
    sem_numero = [l.sequencia for l in fato.lancamentos
                  if not cfg.RE_NUMERO_NF.search(l.complemento)]
    if r.numeros and sem_numero:
        r.observacoes.append("Lançamento(s) sem o número da nota no complemento: sequência "
                             + ", ".join(sem_numero) + ".")


def _motivo_sem_pdf(r: Resultado, candidatas: list[NotaPdf],
                    por_numero: dict[str, list[NotaPdf]], usado_por: dict[str, str],
                    numeros_sem_pdf: set[str]) -> str:
    """Por que o fato ficou SEM PDF (C3, C4 e S7)."""
    ja_usadas = [n for numero in r.numeros for n in por_numero.get(numero, [])
                 if n.usada and (n.valor == r.fato.total_debito
                                 or _mesmo_fornecedor(r.fornecedor, n))]
    if ja_usadas:
        return ("O PDF desta nota existe, mas já foi usado no fato "
                + ", ".join(usado_por[n.arquivo] for n in ja_usadas)
                + ": a mesma nota aparece em mais de um fato do lote.")
    if candidatas:
        return ("Há PDF com o mesmo número, mas de outro fornecedor e outro valor ("
                + "; ".join(f"{n.emitente_nome}, R$ {formatar_valor(n.valor)}" for n in candidatas)
                + "): não foi considerado.")
    if any(numero in numeros_sem_pdf for numero in r.numeros):
        return (f"Nota listada em {cfg.ARQUIVO_SEM_PDF}: veio sem DANFE (precisa do XML "
                "completo).")
    return "PDF da nota não encontrado na pasta."


def _conferir_com_a_nota(r: Resultado, nota: NotaPdf, fornecedor_confere: bool):
    """S1-S5 para um fato casado com o PDF."""
    fato = r.fato
    r.confere_numero = "OK" if len(r.numeros) == 1 else "DIVERGE"
    if not r.datas:
        r.confere_data = "SEM DT"
        r.observacoes.append("Complemento sem a data de emissão (DT).")
    elif r.datas == [nota.emissao]:
        r.confere_data = "OK"
    else:
        r.confere_data = "DIVERGE"
        r.observacoes.append(
            f"Data de emissão: Tasy {', '.join(formatar_data(d) for d in r.datas)} x nota "
            f"{formatar_data(nota.emissao)}.")

    desconto = total_desconto(fato)
    if nota.valor == fato.total_debito:
        r.confere_valor = "OK"
    elif desconto and nota.valor == fato.total_debito - desconto:
        # S3a: desconto lançado à parte, a crédito; a nota vem pelo valor já com o desconto
        r.confere_valor = f"OK (desconto à parte de {formatar_valor(desconto)})"
    else:
        r.confere_valor = "DIVERGE"
        r.observacoes.append(
            f"Valor: Tasy (total dos débitos) {formatar_valor(fato.total_debito)} x nota "
            f"{formatar_valor(nota.valor)} (diferença "
            f"{formatar_valor(fato.total_debito - nota.valor)}).")

    alertas = False
    if not fornecedor_confere:
        alertas = True
        if r.confere_numero == r.confere_data == "OK":
            r.observacoes.append("Número, data e valor conferem com o PDF, mas o nome do "
                                 f"fornecedor é diferente (na nota: {nota.emitente_nome}).")
        else:
            r.observacoes.append("Casada pelo número e pelo valor, mas o nome do fornecedor é "
                                 f"diferente (na nota: {nota.emitente_nome}): conferir.")
    if nota.situacao and sem_acento(nota.situacao).upper() != cfg.SITUACAO_NOTA_AUTORIZADA:
        alertas = True
        r.observacoes.append(f"Situação da nota no PDF: {nota.situacao}.")
    if nota.diferencas_pdf:
        # X4: XML e PDF da mesma nota dizem coisas diferentes; a conferência usou o XML
        alertas = True
        r.observacoes.append("O XML e o PDF da nota não dizem o mesmo (a conferência usou o XML): "
                             + "; ".join(nota.diferencas_pdf) + ".")

    tudo_ok = r.partidas_ok and r.confere_numero == r.confere_data == "OK" \
        and r.confere_valor.startswith("OK")
    if not tudo_ok:
        r.situacao = Situacao.DIVERGENTE
    elif alertas or r.observacoes:
        r.situacao = Situacao.CONFERIR
    else:
        r.situacao = Situacao.OK
