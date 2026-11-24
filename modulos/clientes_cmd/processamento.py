"""Conciliação de Clientes CMD completa. É o único módulo que a tela (painel) chama.

Ordem (a mesma da janela do programa original): extrair o balancete e os Títulos a Receber
(extracao.py) -> casar os clientes pelo nome (casamento.py) -> gravar a planilha (relatorio.py).

O resumo (OK / DIVERGENTE / SEM CONTÁBIL / SEM FINANCEIRO) e o nome padrão do arquivo vieram
da janela original (_calcular_resumo e "Salvar Como..."), sem mudança de regra: na Central a
tela não tem regra de negócio.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pandas as pd

from .casamento import casar
from .extracao import extrair_balancete, extrair_financeiro
from .relatorio import gerar_relatorio

NOME_PADRAO_SAIDA = "Conciliacao_Clientes_CMD.xlsx"


@dataclass
class ResumoClientes:
    total: int
    ok: int
    divergente: int
    sem_contabil: int       # cliente só no financeiro (situação SO_FINANCEIRO)
    sem_financeiro: int     # cliente só no contábil (situação SO_CONTABIL)


@dataclass
class ResultadoClientes:
    caminho: Path                   # planilha gravada
    resumo: ResumoClientes
    tabela: pd.DataFrame            # uma linha por cliente, casado ou não (saída do casamento)


def calcular_resumo(df_combinado: pd.DataFrame) -> ResumoClientes:
    """Conta os clientes por status, como a coluna Status da planilha calcula."""
    ok = 0
    divergente = 0
    for linha in df_combinado.itertuples(index=False):
        if linha.situacao != "CASADO":
            continue
        if pd.isna(linha.valor_contabil) or pd.isna(linha.valor_financeiro):
            continue
        if round(linha.valor_contabil - linha.valor_financeiro, 2) == 0:
            ok += 1
        else:
            divergente += 1

    return ResumoClientes(
        total=len(df_combinado),
        ok=ok,
        divergente=divergente,
        sem_contabil=int((df_combinado["situacao"] == "SO_FINANCEIRO").sum()),
        sem_financeiro=int((df_combinado["situacao"] == "SO_CONTABIL").sum()),
    )


def processar(balancete, financeiro, caminho_saida,
              progresso: Callable[[str, float | None], None] | None = None) -> ResultadoClientes:
    """Lê os dois relatórios, casa os clientes e grava a planilha em `caminho_saida`.

    `progresso(texto, fracao)`, se informado, recebe cada passo (fracao de 0 a 1).
    Um relatório que não puder ser interpretado levanta ValueError com a explicação.
    """
    if progresso is None:
        progresso = _sem_progresso
    caminho_saida = Path(caminho_saida)

    progresso("Lendo o balancete...", 0.0)
    df_balancete = extrair_balancete(balancete)
    progresso("Lendo os Títulos a Receber...", 0.25)
    df_financeiro = extrair_financeiro(financeiro)
    progresso("Casando os clientes...", 0.5)
    df_combinado = casar(df_balancete, df_financeiro)
    progresso("Gravando a planilha...", 0.85)
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)
    gerar_relatorio(df_combinado, caminho_saida)
    progresso("Concluído.", 1.0)

    return ResultadoClientes(caminho=caminho_saida, resumo=calcular_resumo(df_combinado), tabela=df_combinado)


def _sem_progresso(texto: str, fracao: float | None) -> None:
    """Usado quando ninguém acompanha o andamento (testes)."""
