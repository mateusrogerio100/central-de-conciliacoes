"""Números do resumo da Conciliação do Imobilizado – AME's (planilha e tela usam os mesmos)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from modulos.conciliacao_imobilizado.modelos import (
    ORDEM_SITUACOES,
    SITUACAO_CONFERE,
    SITUACAO_DIFERENCA,
    SITUACAO_DIFERENCA_EXPLICADA,
    SITUACAO_DIFERENCA_SEM_EXPLICACAO,
    SITUACOES_PARA_ANALISAR,
    ItemConciliacao,
    ResultadoBens,
)

NOME_BENS_ADQUIRIDOS = "Bens adquiridos (555)"
NOME_BAIXAS = "Baixa de bens (561)"


@dataclass(frozen=True)
class LinhaResumo:
    situacao: str
    contas: int
    saldo_patrimonio: Decimal
    saldo_balancete: Decimal
    diferenca: Decimal


@dataclass(frozen=True)
class NumerosBens:
    contas: int
    conferem: int
    explicadas: int
    para_analisar: int


def linhas_do_resumo(resultado: ResultadoBens) -> list[LinhaResumo]:
    """Uma linha por situação que aparece (na ordem de ORDEM_SITUACOES)."""
    linhas = []
    for situacao in ORDEM_SITUACOES:
        itens = [i for i in resultado.itens if i.situacao == situacao]
        if not itens and situacao != SITUACAO_CONFERE:
            continue
        linhas.append(LinhaResumo(
            situacao=situacao,
            contas=len(itens),
            saldo_patrimonio=sum((i.saldo_patrimonio or Decimal(0) for i in itens), Decimal(0)),
            saldo_balancete=sum((i.saldo_balancete or Decimal(0) for i in itens), Decimal(0)),
            diferenca=sum((i.diferenca or Decimal(0) for i in itens), Decimal(0)),
        ))
    return linhas


def numeros_principais(resultado: ResultadoBens) -> NumerosBens:
    def contar(*situacoes: str) -> int:
        return sum(1 for i in resultado.itens if i.situacao in situacoes)

    return NumerosBens(
        contas=len(resultado.itens),
        conferem=contar(SITUACAO_CONFERE),
        explicadas=contar(SITUACAO_DIFERENCA_EXPLICADA),
        para_analisar=contar(*SITUACOES_PARA_ANALISAR),
    )


def diferencas_pendentes(resultado: ResultadoBens) -> list[ItemConciliacao]:
    """Contas nos dois relatórios com diferença ainda não explicada."""
    return [i for i in resultado.itens
            if i.situacao in (SITUACAO_DIFERENCA, SITUACAO_DIFERENCA_SEM_EXPLICACAO)]


def relatorios_que_ajudariam(resultado: ResultadoBens) -> list[str]:
    """
    Relatórios opcionais não informados que poderiam explicar as diferenças pendentes
    (vazio se não há diferença pendente ou se os dois já foram informados).
    """
    if not diferencas_pendentes(resultado):
        return []
    return [nome for nome, leu in ((NOME_BENS_ADQUIRIDOS, resultado.leu_bens_adquiridos),
                                   (NOME_BAIXAS, resultado.leu_baixas)) if not leu]
