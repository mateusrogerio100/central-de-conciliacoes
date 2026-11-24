"""
Números de resumo do Resultado, usados pela aba Resumo do Excel e pela tela.

Cada nota do Tasy e cada linha da prefeitura é contada uma vez por situação
(nas escrituradas mais de uma vez, a nota aparece em várias linhas do relatório).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from modulos.conferencia_iss.modelos import (
    SITUACAO_CANCELADA_COM_TASY,
    SITUACAO_CANCELADA_SEM_TASY,
    SITUACAO_CONFERIDA,
    SITUACAO_CONFERIDA_AJUSTADO,
    SITUACAO_CONFERIDA_SEM_CPF,
    SITUACAO_DIVERGENCIA,
    SITUACAO_NOME_DIFERENTE,
    SITUACAO_SOMENTE_PREFEITURA,
    SITUACAO_SOMENTE_TASY,
    Resultado,
)

SITUACOES_CONFERIDAS = (
    SITUACAO_CONFERIDA, SITUACAO_CONFERIDA_AJUSTADO, SITUACAO_CONFERIDA_SEM_CPF,
)
SITUACOES_CANCELADAS = (SITUACAO_CANCELADA_COM_TASY, SITUACAO_CANCELADA_SEM_TASY)
# Situações que só aparecem no resumo quando há alguma nota/linha nelas
SITUACOES_SO_SE_HOUVER = (
    (SITUACAO_CONFERIDA_SEM_CPF, SITUACAO_NOME_DIFERENTE) + SITUACOES_CANCELADAS
)


def eh_escriturada_varias_vezes(situacao: str) -> bool:
    return situacao.startswith("Notas escrituradas ")


def linhas_do_resumo(resultado: Resultado) -> list[tuple[str, int, int, Decimal, Decimal]]:
    """
    Uma linha por situação: (situação, notas do Tasy, linhas da prefeitura,
    total mercadoria Tasy, total Valor do Doc.). Cada nota/linha é contada uma vez.
    """
    ordem = [SITUACAO_CONFERIDA, SITUACAO_CONFERIDA_AJUSTADO, SITUACAO_CONFERIDA_SEM_CPF]
    escrituradas = sorted(
        {i.situacao for i in resultado.itens if eh_escriturada_varias_vezes(i.situacao)},
        key=lambda s: int("".join(c for c in s if c.isdigit()) or 0),
    )
    ordem += escrituradas + [SITUACAO_DIVERGENCIA, SITUACAO_NOME_DIFERENTE,
                             SITUACAO_SOMENTE_TASY, SITUACAO_SOMENTE_PREFEITURA]
    ordem += list(SITUACOES_CANCELADAS)

    linhas = []
    for situacao in ordem:
        notas, linhas_pref = {}, {}
        for item in resultado.itens:
            if item.situacao != situacao:
                continue
            if item.nota_tasy is not None:
                notas[id(item.nota_tasy)] = item.nota_tasy.valor_mercadoria
            if item.linha_prefeitura is not None:
                linhas_pref[id(item.linha_prefeitura)] = item.linha_prefeitura.valor_doc
        if situacao in SITUACOES_SO_SE_HOUVER and not notas and not linhas_pref:
            continue                     # ex.: "sem CPF" só aparece se houver nota PF conferida
        linhas.append((
            situacao,
            len(notas),
            len(linhas_pref),
            sum(notas.values(), Decimal(0)),
            sum((v for v in linhas_pref.values() if v is not None), Decimal(0)),
        ))
    return linhas


def conferencia_nada_sumiu(resultado: Resultado) -> tuple[tuple[int, int], tuple[int, int]]:
    """((notas do Tasy no relatório, total lido), (linhas da prefeitura no relatório, total lido))."""
    notas = {id(i.nota_tasy) for i in resultado.itens if i.nota_tasy is not None}
    linhas = {id(i.linha_prefeitura) for i in resultado.itens if i.linha_prefeitura is not None}
    return (
        (len(notas), len(resultado.notas_tasy)),
        (len(linhas), len(resultado.linhas_prefeitura)),
    )




@dataclass
class NumerosPrincipais:
    """Os três números grandes da tela (seção 7 da especificação)."""

    conferidas: int          # notas do Tasy conferidas (as três situações "Conferida")
    somente_tasy: int        # notas do Tasy sem par na prefeitura
    para_analisar: int       # divergências + escrituradas + somente prefeitura + canceladas c/ Tasy
                             # + nome diferente
    divergencias: int
    escrituradas: int        # notas do Tasy escrituradas mais de uma vez
    somente_prefeitura: int  # linhas da prefeitura sem par no Tasy
    canceladas_com_tasy: int = 0   # notas do Tasy cuja nota está cancelada na prefeitura
    canceladas_sem_tasy: int = 0   # linhas canceladas na prefeitura sem nota no Tasy
    nome_diferente: int = 0        # Cidade Gama: número e valor iguais, nome diferente


def numeros_principais(resultado: Resultado) -> NumerosPrincipais:
    conferidas = somente_tasy = divergencias = escrituradas = somente_prefeitura = 0
    canceladas_com_tasy = canceladas_sem_tasy = nome_diferente = 0
    for situacao, notas, linhas, _, _ in linhas_do_resumo(resultado):
        if situacao in SITUACOES_CONFERIDAS:
            conferidas += notas
        elif situacao == SITUACAO_SOMENTE_TASY:
            somente_tasy += notas
        elif situacao == SITUACAO_DIVERGENCIA:
            divergencias += notas
        elif eh_escriturada_varias_vezes(situacao):
            escrituradas += notas
        elif situacao == SITUACAO_SOMENTE_PREFEITURA:
            somente_prefeitura += linhas
        elif situacao == SITUACAO_CANCELADA_COM_TASY:
            canceladas_com_tasy += notas
        elif situacao == SITUACAO_CANCELADA_SEM_TASY:
            canceladas_sem_tasy += linhas
        elif situacao == SITUACAO_NOME_DIFERENTE:
            nome_diferente += notas
    return NumerosPrincipais(
        conferidas=conferidas,
        somente_tasy=somente_tasy,
        para_analisar=(divergencias + escrituradas + somente_prefeitura + canceladas_com_tasy
                       + nome_diferente),
        divergencias=divergencias,
        escrituradas=escrituradas,
        somente_prefeitura=somente_prefeitura,
        canceladas_com_tasy=canceladas_com_tasy,
        canceladas_sem_tasy=canceladas_sem_tasy,
        nome_diferente=nome_diferente,
    )
