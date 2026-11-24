"""Em que linha da planilha entra cada lançamento do razão. Regras C1 a C7 da especificação.

- C1/C2: o nome do convênio sai do histórico ("Faturamento Mês [NF n] <nome> <Mês>/<ano>" ou
  "Referente <nome> NF. n").
- C4: o nome casa com a linha da planilha comparando sem acento, maiúsculas, pontuação e "de/da/do".
- C5: o que a C4 não resolve vem do equivalencias.csv (Nome_no_razao -> Linha_da_planilha). A linha especial
  "NÃO IDENTIFICADO" manda o valor para "Não identificado", com aviso (ex.: IAMSPE).
- C3: histórico fora dos dois formatos: procura dentro dele um nome do equivalencias.csv (vale como
  equivalência) ou, sem nenhum, um nome da planilha (com aviso para conferir).
- C6: nome que não casa com nada = convênio novo: ganha uma linha (gravada na etapa 3), com aviso.
- C7: tudo o que cai na mesma linha soma, de todas as contas.
Nada some: todo lançamento sai com o destino e o motivo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from modulos.convenios import configuracao as cfg
from modulos.convenios.modelos import ZERO, Aviso, Equivalencias, Lancamento, Planilha, Razao
from modulos.convenios.normalizacao import chave_nome, formatar_valor

# como o lançamento chegou à linha (vai para o relatório)
COMO_IGUAL = "nome igual ao da planilha"
COMO_EQUIVALENCIA = "equivalências"
COMO_DENTRO = "nome achado dentro do histórico: conferir"
COMO_NOVA = "convênio novo: linha acrescentada"
COMO_NAO_IDENTIFICADO = "não identificado"


@dataclass
class Destino:
    """Para onde vai um lançamento."""

    lancamento: Lancamento
    nome_lido: str             # o que saiu do histórico (C1/C2); "" quando não saiu nada
    linha: str                 # nome da linha da planilha (ou da linha nova); "" = não identificado
    como: str
    obs: str = ""


@dataclass
class TotalLinha:
    """C7: o total do mês de uma linha da planilha (ou de uma linha nova)."""

    nome: str
    linha_planilha: int | None             # None = linha nova (C6)
    valor: Decimal = ZERO
    destinos: list[Destino] = field(default_factory=list)

    @property
    def nomes_lidos(self) -> list[str]:
        return list(dict.fromkeys(d.nome_lido or d.lancamento.historico for d in self.destinos))


@dataclass
class Classificacao:
    destinos: list[Destino] = field(default_factory=list)
    linhas: list[TotalLinha] = field(default_factory=list)          # na ordem da planilha; as novas no fim
    avisos: list[Aviso] = field(default_factory=list)

    @property
    def nao_identificados(self) -> list[Destino]:
        return [d for d in self.destinos if not d.linha]

    @property
    def total_nao_identificado(self) -> Decimal:
        return sum((d.lancamento.valor for d in self.nao_identificados), ZERO)

    @property
    def linhas_novas(self) -> list[TotalLinha]:
        return [t for t in self.linhas if t.linha_planilha is None]

    @property
    def total(self) -> Decimal:
        return sum((t.valor for t in self.linhas), ZERO) + self.total_nao_identificado


def nome_do_historico(historico: str) -> str:
    """C1/C2: o nome do convênio no histórico; "" se o histórico não estiver em nenhum dos dois formatos."""
    achado = cfg.RE_FATURAMENTO.match(historico)
    if achado:
        return " ".join(achado.group(1).split())
    achado = cfg.RE_REFERENTE.match(historico)
    if achado and not cfg.RE_NOME_QUE_E_DOCUMENTO.match(achado.group(1)):
        return " ".join(achado.group(1).split())
    return ""


def _contem(texto: str, trecho: str) -> bool:
    """O trecho (já como chave) aparece no texto como palavras inteiras."""
    return bool(trecho) and f" {trecho} " in f" {texto} "


def classificar(razao: Razao, planilha: Planilha, equivalencias: Equivalencias) -> Classificacao:
    resultado = Classificacao()
    nao_identificado = chave_nome(cfg.LINHA_NAO_IDENTIFICADO)
    linhas_planilha: dict[str, tuple[str, int]] = {}
    for c in planilha.convenios:
        linhas_planilha.setdefault(chave_nome(c.nome), (c.nome, c.linha))
    equivalencia = {chave_nome(e.nome_no_razao): e for e in equivalencias.itens}
    totais: dict[str, TotalLinha] = {chave: TotalLinha(nome, numero) for chave, (nome, numero) in linhas_planilha.items()}
    destinos_faltando: set[str] = set()

    def para_linha(nome_linha: str) -> str:
        """A linha da planilha com esse nome; sem ela, uma linha nova (C6)."""
        chave = chave_nome(nome_linha)
        if chave not in totais:
            totais[chave] = TotalLinha(nome_linha, None)
        return totais[chave].nome

    for lancamento in razao.lancamentos:
        nome = nome_do_historico(lancamento.historico)
        chave = chave_nome(nome)
        if nome and chave in equivalencia:
            alvo = equivalencia[chave]
            if chave_nome(alvo.linha_da_planilha) == nao_identificado:
                destino = Destino(lancamento, nome, "", COMO_NAO_IDENTIFICADO, alvo.obs)
            else:
                if chave_nome(alvo.linha_da_planilha) not in linhas_planilha:
                    destinos_faltando.add(alvo.linha_da_planilha)
                destino = Destino(lancamento, nome, para_linha(alvo.linha_da_planilha), COMO_EQUIVALENCIA, alvo.obs)
        elif nome and chave in linhas_planilha:
            destino = Destino(lancamento, nome, linhas_planilha[chave][0], COMO_IGUAL)
        elif nome:
            destino = Destino(lancamento, nome, para_linha(nome), COMO_NOVA)
        else:
            destino = _procurar_dentro(lancamento, equivalencia, linhas_planilha, nao_identificado, para_linha)
        resultado.destinos.append(destino)
        if destino.linha:
            total = totais[chave_nome(destino.linha)]
            total.valor += lancamento.valor
            total.destinos.append(destino)

    resultado.linhas = sorted((t for t in totais.values() if t.destinos or t.linha_planilha),
                              key=lambda t: (t.linha_planilha is None, t.linha_planilha or 0, chave_nome(t.nome)))
    _avisar(resultado, destinos_faltando)
    return resultado


def _procurar_dentro(lancamento, equivalencia, linhas_planilha, nao_identificado, para_linha) -> Destino:
    """C3: histórico fora dos formatos: o nome mais longo do equivalencias.csv que aparece nele; sem nenhum, o
    nome mais longo da planilha (para conferir)."""
    texto = chave_nome(lancamento.historico)
    do_csv = [(chave, e) for chave, e in equivalencia.items() if _contem(texto, chave)]
    if do_csv:
        _, e = max(do_csv, key=lambda c: len(c[0]))
        if chave_nome(e.linha_da_planilha) == nao_identificado:
            return Destino(lancamento, "", "", COMO_NAO_IDENTIFICADO, e.obs)
        return Destino(lancamento, "", para_linha(e.linha_da_planilha), COMO_EQUIVALENCIA, e.obs)
    da_planilha = [(chave, nome) for chave, (nome, _) in linhas_planilha.items() if _contem(texto, chave)]
    if da_planilha:
        _, nome = max(da_planilha, key=lambda c: len(c[0]))
        return Destino(lancamento, "", para_linha(nome), COMO_DENTRO)
    return Destino(lancamento, "", "", COMO_NAO_IDENTIFICADO,
                   "Histórico fora dos formatos \"Faturamento Mês ...\" e \"Referente ... NF.\" e sem nome conhecido.")


def _avisar(resultado: Classificacao, destinos_faltando: set[str]):
    for nome in sorted(destinos_faltando):
        resultado.avisos.append(Aviso(cfg.ARQUIVO_EQUIVALENCIAS, f"A linha \"{nome}\" do equivalencias.csv não existe na "
                                                                 "planilha: vai ser acrescentada."))
    for total in resultado.linhas_novas:
        resultado.avisos.append(Aviso("Convênio novo", f"\"{total.nome}\" não tem linha na planilha: linha acrescentada "
                                                       f"com {formatar_valor(total.valor)} no mês. Confira o nome."))
    for destino in resultado.destinos:
        if destino.como == COMO_DENTRO:
            resultado.avisos.append(Aviso(f"Razão linha {destino.lancamento.linha}",
                                          f"\"{destino.lancamento.historico[:80]}\" foi para \"{destino.linha}\" pelo "
                                          "nome achado dentro do histórico: confira."))
    if resultado.nao_identificados:
        motivos = sorted({d.nome_lido or "histórico fora do padrão" for d in resultado.nao_identificados})
        resultado.avisos.append(Aviso("Não identificado", f"{len(resultado.nao_identificados)} lançamento(s), "
                                                          f"{formatar_valor(resultado.total_nao_identificado)}, sem linha na planilha "
                                                          f"({', '.join(motivos)}): preencha à mão.", erro=True))
