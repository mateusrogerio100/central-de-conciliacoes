"""Auxiliares dos testes de Fornecedores do Conciliações AMES (tests/test_fornecedores.py) que os testes de
Honorários usam, COPIADOS sem mudança: um teste de módulo não depende dos testes de outro módulo.
"""

from datetime import date, datetime
from pathlib import Path

from openpyxl import Workbook


def _texto_celula(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    if isinstance(valor, (datetime, date)):
        return f"{valor:%d/%m/%Y}"
    return str(valor)


def texto_tasy(pasta: Path, nome: str, linhas: list[list]) -> Path:
    """Como o Tasy salva: .xls que é texto separado por tabulação, em Windows-1252."""
    caminho = pasta / nome
    caminho.write_bytes("\r\n".join("\t".join(_texto_celula(c) for c in linha) for linha in linhas)
                        .encode("cp1252"))
    return caminho


def planilha(pasta: Path, nome: str, linhas: list[list]) -> Path:
    """O mesmo conteúdo salvo como .xlsx (quem abriu e salvou no Excel)."""
    livro = Workbook()
    aba = livro.active
    for linha in linhas:
        aba.append(linha)
    caminho = pasta / nome
    livro.save(caminho)
    return caminho


def _topo_balancete(unidade, mes):
    return [
        [unidade],
        ["Balancete"],
        [None] * 6 + ["Mês Referência:", None, None, mes],
        [None, "Código", None, "Classificação", None, "Descrição", None, None, "Saldo Anterior", None,
         "Débitos", None, "Créditos", "Saldo Atual"],
        [None, "Passivo"],
    ]


def _conta(codigo, classificacao, descricao, saldo):
    return [None, None, str(codigo), None, classificacao, "      " + descricao, None, None, 0, None, 0, None,
            saldo, saldo]
