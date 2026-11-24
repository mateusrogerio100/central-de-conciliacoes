"""Como o Tasy grava os relatórios: o ".xls" que é texto separado por tabulação (Windows-1252) e o
mesmo conteúdo salvo como .xlsx (quem abriu e salvou no Excel). Igual aos ajudantes dos testes."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook


def numero_br(valor) -> str:
    """1234.5 -> "1.234,50" (como o Tasy escreve)."""
    return f"{Decimal(str(valor)):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def texto_celula(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, (int, float, Decimal)) and not isinstance(valor, bool):
        return numero_br(valor)
    if isinstance(valor, (datetime, date)):
        return f"{valor:%d/%m/%Y}"
    return str(valor)


def texto_tasy(caminho: Path, linhas: list[list]) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes("\r\n".join("\t".join(texto_celula(c) for c in linha) for linha in linhas).encode("cp1252"))
    return caminho


def topo_balancete(unidade: str, mes: str, grupo: str = "Passivo") -> list[list]:
    """Topo do balancete (865) do Tasy; mes como "set/2026"."""
    return [
        [unidade],
        ["Balancete"],
        [None] * 6 + ["Mês Referência:", None, None, mes],
        [None, "Código", None, "Classificação", None, "Descrição", None, None, "Saldo Anterior", None,
         "Débitos", None, "Créditos", "Saldo Atual"],
        [None, grupo],
    ]


def conta_balancete(codigo, classificacao: str, descricao: str, saldo) -> list:
    return [None, None, str(codigo), None, classificacao, "      " + descricao, None, None, saldo, None, 0, None,
            0, saldo]


def planilha(caminho: Path, linhas: list[list], nome_aba: str | None = None) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    livro = Workbook()
    aba = livro.active
    if nome_aba:
        aba.title = nome_aba
    for linha in linhas:
        aba.append(linha)
    livro.save(caminho)
    return caminho
