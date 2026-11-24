"""Testes da Conciliação de Clientes CMD (criados na migração para a Central: o programa
original não tinha testes automáticos).

Referência de regressão: exemplos/clientes_cmd/Conciliacao_Clientes_CMD.xlsx, a planilha que o
programa original gera com o balancete e os Títulos a Receber de agosto/2026 (conferido antes da
migração: o código original reproduz esse arquivo célula por célula). A Central tem de gerar
exatamente o mesmo resultado.
"""

from __future__ import annotations

import pandas as pd
import pytest

from modulos.clientes_cmd.processamento import (
    NOME_PADRAO_SAIDA,
    ResumoClientes,
    calcular_resumo,
    processar,
)
from testes.conftest import diferencas_entre_planilhas, pasta_exemplos

ARQUIVO_BALANCETE = "Balancete_clientes_CMD_att.xlsx"
ARQUIVO_FINANCEIRO = "CONCILIAÇÕES_CLIENTES_CMD_TITULOS_RECEBER_AGO-26.xlsx"
ARQUIVO_REFERENCIA = "Conciliacao_Clientes_CMD.xlsx"


@pytest.fixture(scope="module")
def exemplos():
    return pasta_exemplos("clientes_cmd")


@pytest.fixture(scope="module")
def agosto(exemplos, tmp_path_factory):
    """Processa agosto/2026 uma vez só (casar os nomes é o passo demorado)."""
    passos = []
    destino = tmp_path_factory.mktemp("clientes") / NOME_PADRAO_SAIDA
    resultado = processar(exemplos / ARQUIVO_BALANCETE, exemplos / ARQUIVO_FINANCEIRO, destino,
                          progresso=lambda texto, fracao: passos.append((texto, fracao)))
    return resultado, passos


def test_planilha_igual_a_do_programa_original(agosto, exemplos):
    resultado, _ = agosto
    assert diferencas_entre_planilhas(exemplos / ARQUIVO_REFERENCIA, resultado.caminho) == []


def test_resumo_de_agosto(agosto):
    resultado, _ = agosto
    assert resultado.resumo == ResumoClientes(total=1214, ok=1173, divergente=15, sem_contabil=8,
                                              sem_financeiro=18)


def test_resumo_soma_o_total(agosto):
    resumo = agosto[0].resumo
    assert resumo.ok + resumo.divergente + resumo.sem_contabil + resumo.sem_financeiro == resumo.total


def test_progresso(agosto):
    _, passos = agosto
    fracoes = [f for _, f in passos]
    assert passos[0] == ("Lendo o balancete...", 0.0)
    assert passos[-1] == ("Concluído.", 1.0)
    assert fracoes == sorted(fracoes)


def test_nome_padrao():
    assert NOME_PADRAO_SAIDA == "Conciliacao_Clientes_CMD.xlsx"


def test_calcular_resumo_regras():
    tabela = pd.DataFrame(
        [
            ("CASADO", 100.00, 100.00),        # OK
            ("CASADO", 100.00, 100.004),       # OK: diferença arredondada a 2 casas é zero
            ("CASADO", 100.00, 99.00),         # DIVERGENTE
            ("SO_CONTABIL", 50.00, None),      # SEM FINANCEIRO
            ("SO_FINANCEIRO", None, 70.00),    # SEM CONTÁBIL
            ("SO_FINANCEIRO", None, 80.00),    # SEM CONTÁBIL
        ],
        columns=["situacao", "valor_contabil", "valor_financeiro"],
    )
    assert calcular_resumo(tabela) == ResumoClientes(total=6, ok=2, divergente=1, sem_contabil=2,
                                                     sem_financeiro=1)
