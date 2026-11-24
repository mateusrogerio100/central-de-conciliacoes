"""Fornecedores: balancete (865, conta 2111) e títulos a pagar analítico, como saem do Tasy.

Mostra: contas que batem, uma diferença, um cadastro duplicado somado (nome digitado diferente),
"a reclassificar" (nunca pareia) e um fornecedor só no relatório; um título de saldo zero fica fora.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from manual.ficticios import Exemplo
from manual.ficticios.tasy import texto_tasy

UNIDADE = "AME - Cidade Exemplo (Fund. Hospital Exemplo)"
MES = "set/2026"

CONTAS = [                                   # código, descrição, saldo
    (30001, "Alfa Exemplo Distribuidora Ltda", 12450.00),
    (30002, "Beta Exemplo Materiais Hospitalares Ltda", 7320.50),
    (30003, "Gama Exemplo Serviços Médicos", 3800.00),
    (30004, "Delta Exemplo Comércio Varejista Ltda", 5297.90),
    (30005, "Epsilon Exemplo Laboratório Ltda", 1980.00),
    (30006, "Fornecedores a reclassificar", 650.00),
]
TITULOS = [                                  # fornecedor, Nr. Doc., Nr. Título, saldo, CNPJ
    ("Alfa Exemplo Distribuidora Ltda - EPP", "5101", "910001", 8000.00, "00.111.222/0001-33"),
    ("Alfa Exemplo Distribuidora Ltda - EPP", "5102", "910002", 4450.00, "00.111.222/0001-33"),
    ("Beta Exemplo Materiais Hospitalares Ltda", "7201", "910003", 7000.50, "00.222.333/0001-44"),
    ("Gama Exemplo Servicos Medicos Ltda", "", "910004", 3800.00, "00.333.444/0001-55"),
    ("Delta Exemplo Comercio Varejista Ltda", "8301", "910005", 2356.00, "00.444.555/0001-66"),
    ("Delta Exemplo Comervio Varejista Ltda", "8302", "910006", 2941.90, "00.444.555/0001-66"),
    ("Epsilon Exemplo Laboratorio Ltda", "9401", "910007", 1980.00, "00.555.666/0001-77"),
    ("Kappa Exemplo Transportes Ltda", "9502", "910008", 940.00, "00.666.777/0001-88"),
    ("Omega Exemplo Banco SA", "", "910009", 0.00, "00.777.888/0001-99"),
]


def _topo_balancete():
    return [
        [UNIDADE],
        ["Balancete"],
        [None] * 6 + ["Mês Referência:", None, None, MES],
        [None, "Código", None, "Classificação", None, "Descrição", None, None, "Saldo Anterior", None,
         "Débitos", None, "Créditos", "Saldo Atual"],
        [None, "Passivo"],
    ]


def _conta(codigo, classificacao, descricao, saldo):
    return [None, None, str(codigo), None, classificacao, "      " + descricao, None, None, saldo, None, 0, None,
            0, saldo]


def linhas_balancete():
    linhas = _topo_balancete()
    linhas.append(_conta(2111, "2.01.01.01", "FORNECEDORES NO PAÍS", sum(c[2] for c in CONTAS)))
    for posicao, (codigo, descricao, saldo) in enumerate(CONTAS, start=1):
        linhas.append(_conta(codigo, f"2.01.01.01.{posicao:04d}", descricao, saldo))
    linhas.append([None, "Impresso em: 06/10/2026", None, None, None, None, None, "Página: 1", None,
                   None, None, "USUARIO", None, None, "WEXE001"])
    return linhas


CABECALHO_ANALITICO = ["Pessoa Física/Jurídica", "Nr. Doc.", "Nr. Título", "TIpo Título", "Sit.", "Dt. Emissão",
                       "Dt. Vencto. Atu.", "Dt. Vencto. Ori.", "Dt. Liquid.", "Vl. Juros", "Vl. Multa", "Vl. Saldo",
                       "Observação", "Vl classif", "Vl título", "Vl pago", "Cheque", "Estabelecimento", "CNPJ",
                       "Valor NF", "Ordem Compra", "Vl baixa", "Trans fin baixa", "Classificação"]


def linhas_titulos():
    linhas = [CABECALHO_ANALITICO]
    for fornecedor, documento, numero, saldo, cnpj in TITULOS:
        linhas.append([fornecedor, documento, numero, "Nota Fiscal", "A", datetime(2026, 9, 24),
                       datetime(2026, 10, 15), datetime(2026, 10, 15), "", 0, 0, saldo, "", 0, saldo, 0, 0,
                       UNIDADE, cnpj, saldo, 1, 0, "", ""])
    return linhas


def gerar(pasta: Path) -> list[Exemplo]:
    balancete = texto_tasy(pasta / "balancete_2111_set2026.xls", linhas_balancete())
    titulos = texto_tasy(pasta / "titulos_pagar_analitico_set2026.xls", linhas_titulos())
    saida = pasta / "saida"
    saida.mkdir(parents=True, exist_ok=True)
    return [Exemplo("conciliacao_fornecedores", "fornecedores", "Conciliação", "conciliacao",
                    {"cartao_balancete": [balancete], "cartao_titulos": [titulos], "cartao_pasta": [saida]},
                    pasta_saida=saida,
        numeros=("4", "3", "7"))]
