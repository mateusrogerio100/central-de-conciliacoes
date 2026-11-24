"""Convênios: o Razão Convênios do mês (como o Tasy exporta), a planilha RECEITAS DE CONVÊNIOS e a pasta config
com o equivalencias.csv.

Mostra: cinco convênios preenchidos (um deles pela equivalência, somando dois nomes do razão), um convênio novo
(linha acrescentada) e a conferência TOTAL RECEITAS × Saldo Contábil fechando em zero.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import openpyxl

from manual.ficticios import Exemplo

CONTA = "40075 - 4.01.05.01.0001  Convênio Prefeitura Exemplo"
TOTAL = "Total - 40075 - 4.01.05.01.0001  Convênio Prefeitura Exemplo"
LANCAMENTOS = [   # (histórico, crédito, débito)
    ("Faturamento Mês NF 1001 PM de Cidade Alfa Set/2026 Protocolo 501", 12500.00, 0),
    ("Faturamento Mês NF 1002 PM CIDADE BETA CONVENIO Set/2026 Protocolo 502", 30200.40, 0),
    ("Faturamento Mês NF 1003 Pref.Munic.Cidade Beta-UNIVERSIDADE Set/2026 Protocolo 503", 1840.00, 0),
    ("Faturamento Mês NF 1004 Plano Exemplo Saúde Set/2026 Protocolo 504", 48760.15, 0),
    ("Estorno Faturamento Mês NF 1004 Plano Exemplo Saúde Set/2026 Protocolo 504", 0, 760.15),
    ("Referente Clínica Exemplo Gama Ltda NF. 2001 Nota Fiscal Avulsa", 3420.00, 0),
    ("Referente Fundação Exemplo Delta NF. 2002 Nota Fiscal Avulsa", 9800.00, 0),
]
CONVENIOS = [  # (nome na planilha, agosto)
    ("Clínica Exemplo Gama Ltda", 3100.00),
    ("Plano Exemplo Saúde", 47250.30),
    ("PM Cidade Alfa", 11980.00),
    ("PM Cidade Beta", 31020.75),
]


def _razao(caminho: Path) -> Path:
    livro = openpyxl.Workbook()
    aba = livro.active
    aba.append([None, "Fundação Exemplo", None, None, None, None, None, None, None, None, "Livro: 0"])
    aba.append(["Razão"])
    aba.append([None, None, None, "Período:", datetime(2026, 9, 1), "até:", None, datetime(2026, 9, 30)])
    aba.append([None, "Data", "Histórico", None, None, None, "Lote", None, None, "Débitos", None, "Créditos", None,
                None, "Saldo"])
    aba.append([None, CONTA])
    for historico, credito, debito in LANCAMENTOS:
        aba.append([None, datetime(2026, 9, 30), historico, None, None, None, 70001, None, None, debito, None,
                    credito])
    aba.append([None, None, TOTAL, None, None, None, None, None, None, sum(d for _, _, d in LANCAMENTOS), None,
                sum(c for _, c, _ in LANCAMENTOS)])
    livro.save(caminho)
    return caminho


def _planilha(caminho: Path) -> Path:
    livro = openpyxl.Workbook()
    aba = livro.active
    aba.title = "Receita de Convênios 2026"
    aba["B2"] = "4.01.05.01 - RECEITA DE CONVÊNIOS"
    aba.append([])
    aba.append([None, "CONVÊNIO", *[datetime(2026, m, 1) for m in range(1, 13)], "Acumulado 2026"])
    for nome, agosto in CONVENIOS:
        linha = aba.max_row + 1
        aba.append([None, nome, *[agosto if m == 8 else None for m in range(1, 13)], f"=SUM(C{linha}:N{linha})"])
    fim = aba.max_row + 1
    aba.append([None, None, *[None] * 12, f"=SUM(C{fim}:N{fim})"])          # linha de folga, como na real
    aba.append([])
    total = aba.max_row + 1
    aba.append([None, "TOTAL RECEITAS", *[f"=SUM({c}5:{c}{fim})" for c in "CDEFGHIJKLMN"], f"=SUM(O5:O{fim})"])
    aba.append([])
    saldo = aba.max_row + 1
    aba.append([None, "Saldo Contábil", *[None] * 7, sum(a for _, a in CONVENIOS)])
    aba.append([None, "Diferença", *[f"={c}{total}-{c}{saldo}" for c in "CDEFGHIJKLMN"]])
    livro.save(caminho)
    return caminho


def gerar(pasta: Path) -> list[Exemplo]:
    pasta.mkdir(parents=True, exist_ok=True)
    razao = _razao(pasta / "Razao Convenios 092026.xlsx")
    planilha = _planilha(pasta / "RECEITAS DE CONVÊNIOS 082026.xlsx")
    config = pasta / "config"
    config.mkdir(exist_ok=True)
    (config / "equivalencias.csv").write_text(
        "Nome_no_razao;Linha_da_planilha;Obs\n"
        "PM CIDADE BETA CONVENIO;PM Cidade Beta;\n"
        "Pref.Munic.Cidade Beta-UNIVERSIDADE;PM Cidade Beta;soma na linha da prefeitura\n", encoding="utf-8-sig")
    saida = pasta / "saida"
    saida.mkdir(exist_ok=True)
    return [Exemplo("convenios", "convenios", "Preenchimento", "preenchimento",
                    {"cartao_razao": [razao], "cartao_planilha": [planilha], "cartao_equivalencias": [config],
                     "cartao_saida": [saida]},
                    pasta_saida=saida, numeros=("5", "1", "0"))]
