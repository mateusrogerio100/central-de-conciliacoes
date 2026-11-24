"""O que a tela mostra depois do processamento (substitui o texto montar_resumo da janela antiga).

Só organiza para exibir o que o processamento já calculou: números, uma linha por aba e as
conferências (GUIA_VISUAL, seção 5: "Soma dos bens = total do relatório" e "Saldo contábil de
cada aba = balancete"). Nenhuma regra de negócio nova.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from modulos.subvencoes.modelos import Gravidade, ResultadoProcessamento, StatusArquivo

MAXIMO_LINHAS_PROBLEMA = 6


@dataclass
class LinhaAba:
    aba: str
    contas: int
    com_diferenca: int


@dataclass
class Conferencia:
    texto: str
    status: str                 # "ok", "atencao" ou "erro"
    valor: str | None = None


@dataclass
class ResumoTela:
    contas_preenchidas: int
    contas_com_diferenca: int
    avisos: int
    erros: int
    atencoes: int
    abas: list[LinhaAba] = field(default_factory=list)
    conferencias: list[Conferencia] = field(default_factory=list)

    @property
    def selo(self) -> tuple[str, str]:
        if self.erros or any(c.status == "erro" for c in self.conferencias):
            return "Concluído com erros", "erro"
        return "Concluído", "ok"

    @property
    def legenda_avisos(self) -> str:
        return f"avisos · {self.erros} erro{'s' if self.erros != 1 else ''}"


def formatar_reais(valor: Decimal) -> str:
    texto = f"{valor:,.2f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


def resumir(resultado: ResultadoProcessamento) -> ResumoTela:
    contagem = resultado.quantidade_por_gravidade()
    geradas = resultado.planilhas_geradas
    resumo = ResumoTela(
        contas_preenchidas=sum(p.linhas_preenchidas for p in geradas),
        contas_com_diferenca=sum(p.linhas_com_diferenca for p in geradas),
        avisos=len(resultado.avisos),
        erros=contagem[Gravidade.ERRO],
        atencoes=contagem[Gravidade.ATENCAO],
    )

    if resultado.conciliacao is not None:
        por_aba: dict[tuple[str, str], LinhaAba] = {}
        for linha in resultado.conciliacao.linhas:
            item = por_aba.setdefault((linha.planilha, linha.aba), LinhaAba(linha.aba, 0, 0))
            item.contas += 1
            if linha.diferenca != 0:
                item.com_diferenca += 1
        resumo.abas = list(por_aba.values())

    resumo.conferencias = _conferencias(resultado)
    return resumo


def _conferencias(resultado: ResultadoProcessamento) -> list[Conferencia]:
    conferencias: list[Conferencia] = []

    patrimonio = resultado.patrimonio
    if patrimonio is not None:
        soma = formatar_reais(patrimonio.soma_itens)
        if patrimonio.total_geral_sistema is None:
            conferencias.append(Conferencia("Relatório de patrimônio sem a linha de total geral", "atencao", soma))
        elif patrimonio.total_geral_confere:
            conferencias.append(Conferencia("Soma dos bens = total do relatório", "ok", soma))
        else:
            diferenca = formatar_reais(patrimonio.soma_itens - patrimonio.total_geral_sistema)
            conferencias.append(Conferencia("Soma dos bens diferente do total do relatório", "atencao", diferenca))

    if resultado.conciliacao is not None and resultado.conciliacao.conferencias_aba:
        abas = resultado.conciliacao.conferencias_aba
        divergentes = [a for a in abas if not a.confere]
        if not divergentes:
            conferencias.append(Conferencia("Saldo contábil de cada aba = balancete", "ok",
                                            f"{len(abas)} aba{'s' if len(abas) != 1 else ''}"))
        for aba in divergentes:
            if aba.sintetica is None:
                conferencias.append(Conferencia(f"Aba {aba.aba}: conta sintética não encontrada no balancete",
                                                "atencao"))
            else:
                diferenca = formatar_reais(aba.soma_saldo_contabil - aba.sintetica.saldo_atual)
                conferencias.append(Conferencia(f"Saldo contábil da aba {aba.aba} ≠ balancete", "atencao", diferenca))

    problemas = [a for a in resultado.arquivos if a.status in (StatusArquivo.FALHOU, StatusArquivo.NAO_PROCESSADO)]
    for arquivo in problemas[:MAXIMO_LINHAS_PROBLEMA]:
        detalhe = f" — {arquivo.detalhe}" if arquivo.detalhe else ""
        conferencias.append(Conferencia(f"{arquivo.tipo} {arquivo.nome}: {arquivo.status.value}{detalhe}", "erro"))
    if len(problemas) > MAXIMO_LINHAS_PROBLEMA:
        conferencias.append(Conferencia(f"... e mais {len(problemas) - MAXIMO_LINHAS_PROBLEMA} arquivo(s) com "
                                        "problema (veja o relatório de avisos)", "erro"))

    if not resultado.caminho_relatorio:
        conferencias.append(Conferencia(f"Relatório de avisos NÃO gravado: {resultado.erro_relatorio}", "erro"))
    return conferencias
