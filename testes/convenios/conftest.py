"""Apoio dos testes do módulo Convênios.

Os exemplos reais (razão de set/2026, planilha de ago/2026 e o equivalencias.csv preenchido) ficam em
exemplos\\convenios\\, fora do git. Sem a pasta, os testes que dependem dela são pulados. Os demais usam
arquivos fictícios montados aqui (nenhum nome real de convênio).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import openpyxl

from testes.conftest import pasta_exemplos

CABECALHO_PAGINA = [
    [None, "Fundação Exemplo", None, None, None, None, None, None, None, None, "Livro: 0"],
    ["Razão"],
    [None, None, None, "Período:", datetime(2026, 9, 1), "até:", None, datetime(2026, 9, 30)],
    [None, "Data", "Histórico", None, None, None, "Lote", None, None, "Débitos", None, "Créditos", None, None,
     "Saldo"],
]


def exemplos(*subpastas: str) -> Path:
    """exemplos\\convenios\\<subpastas>; pula sem a pasta."""
    return pasta_exemplos("convenios", *subpastas)


def lancamento(historico: str, credito=0, debito=0, data=datetime(2026, 9, 30), lote=70001) -> list:
    return [None, data, historico, None, None, None, lote, None, None, debito, None, credito, None, None, 0]


def conta(codigo: str, classificacao: str, nome: str) -> list:
    return [None, f"{codigo} - {classificacao}  {nome}"]


def total(codigo: str, classificacao: str, nome: str, credito, debito=0) -> list:
    return [None, None, f"Total - {codigo} - {classificacao}  {nome}", None, None, None, None, None, None, debito,
            None, credito]


def escrever_razao(caminho: Path, *linhas: list, cabecalho=CABECALHO_PAGINA) -> Path:
    livro = openpyxl.Workbook()
    aba = livro.active
    for linha in [*cabecalho, *linhas]:
        aba.append(linha)
    livro.save(caminho)
    return caminho


def _texto_da_celula(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, datetime):
        return f"{valor:%d/%m/%Y}"
    if isinstance(valor, int) and valor > 9999:       # lote: "72262", como no Tasy
        return str(valor)
    if isinstance(valor, (int, float)):
        return f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return str(valor)


def escrever_razao_texto(caminho: Path, *linhas: list, cabecalho=CABECALHO_PAGINA) -> Path:
    """O ".xls" do Tasy: texto com tabulação, datas "30/09/2026" e valores "1.234,56", codificação do Windows."""
    texto = "\r\n".join("\t".join(_texto_da_celula(v) for v in linha) for linha in [*cabecalho, *linhas])
    caminho.write_bytes(texto.encode("cp1252"))
    return caminho


def escrever_planilha(caminho: Path, convenios: list[tuple], ano=2026, abas_antigas=(2025,)) -> Path:
    """Planilha de receitas fictícia: convenios = [(nome, {mês: valor}), ...]."""
    livro = openpyxl.Workbook()
    livro.remove(livro.active)
    for a in (*abas_antigas, ano):
        aba = livro.create_sheet(f"Receita de Convênios {a}")
        aba["B2"] = "4.01.05.01 - RECEITA DE CONVÊNIOS"
        aba.append([])
        aba.append([None, "                        CONVÊNIO", *[datetime(a, m, 1) for m in range(1, 13)],
                    f"Acumulado {a}"])
        for nome, valores in convenios:
            linha = aba.max_row + 1
            aba.append([None, nome, *[valores.get(m) for m in range(1, 13)], f"=SUM(C{linha}:N{linha})"])
        aba.append([])
        fim = aba.max_row
        aba.append([None, "TOTAL RECEITAS ", *[f"=SUM({c}5:{c}{fim})" for c in "CDEFGHIJKLMN"]])
        aba.append([])
        aba.append([None, "Saldo Contábil"])
        aba.append([None, "Diferença"])
    livro.save(caminho)
    return caminho
