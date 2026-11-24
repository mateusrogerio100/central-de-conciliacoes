"""Abertura dos relatórios do Tasy (balancete e SCF) como uma lista de linhas de texto.

Os ".xls" do Tasy não são Excel: são texto separado por tabulação, em cp1252 (seção 3.1).
O programa reconhece o formato pelo CONTEÚDO do arquivo, não pela extensão:
- texto com tabulação -> lido direto;
- .xlsx (o usuário abriu e salvou no Excel) -> cada célula vira texto, com números no formato
  brasileiro sem separador de milhar ("2090915,58"), para o resto do programa funcionar igual;
- .xls binário de verdade (Excel 97-2003) -> mensagem pedindo para salvar como .xlsx.

Cada linha devolvida é uma lista de textos, com as células vazias mantidas ("").
"""

from __future__ import annotations

import datetime
import io
import zipfile
from decimal import Decimal
from pathlib import Path

import openpyxl

from modulos.conciliacao_estoque import configuracao
from modulos.conciliacao_estoque.modelos import ErroArquivo

_ASSINATURA_XLS_BINARIO = b"\xd0\xcf\x11\xe0"
_ASSINATURA_ZIP = b"PK"


def ler_linhas(caminho) -> list[list[str]]:
    caminho = Path(caminho)
    nome = caminho.name
    if not caminho.is_file():
        raise ErroArquivo(f"{nome}: arquivo não encontrado.")
    try:
        with open(caminho, "rb") as arquivo:
            inicio = arquivo.read(4)
    except PermissionError:
        raise ErroArquivo(f"{nome}: o arquivo está aberto em outro programa (feche o Excel e tente de novo).")

    if inicio.startswith(_ASSINATURA_XLS_BINARIO):
        raise ErroArquivo(
            f"{nome}: é um Excel antigo (.xls 97-2003). Abra no Excel e salve como .xlsx "
            "(Pasta de Trabalho do Excel)."
        )
    if inicio.startswith(_ASSINATURA_ZIP):
        return _ler_xlsx(caminho)
    return _ler_texto(caminho)


def _ler_texto(caminho: Path) -> list[list[str]]:
    try:
        texto = caminho.read_text(encoding=configuracao.CODIFICACAO_TASY, errors="replace")
    except PermissionError:
        raise ErroArquivo(f"{caminho.name}: o arquivo está aberto em outro programa (feche e tente de novo).")
    return [linha.split(configuracao.SEPARADOR_TASY) for linha in texto.splitlines()]


def _ler_xlsx(caminho: Path) -> list[list[str]]:
    try:
        # pelo conteúdo, não pelo caminho: o openpyxl recusa um .xlsx que tenha extensão .xls
        conteudo = io.BytesIO(caminho.read_bytes())
        pasta_trabalho = openpyxl.load_workbook(conteudo, read_only=True, data_only=True)
    except PermissionError:
        raise ErroArquivo(f"{caminho.name}: o arquivo está aberto em outro programa (feche o Excel e tente de novo).")
    except (zipfile.BadZipFile, KeyError, OSError) as erro:
        raise ErroArquivo(f"{caminho.name}: não foi possível abrir como planilha .xlsx ({erro}).")
    try:
        aba = pasta_trabalho.worksheets[0]
        return [[_celula_para_texto(v) for v in linha] for linha in aba.iter_rows(values_only=True)]
    finally:
        pasta_trabalho.close()


def _celula_para_texto(valor) -> str:
    """Conteúdo de uma célula do .xlsx no mesmo formato do texto do Tasy."""
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return str(valor)
    if isinstance(valor, (int, float)):
        # pelo texto (repr), para não carregar a imprecisão do float; "f" evita notação 1E-5
        numero = format(Decimal(repr(valor)), "f")
        if "." in numero:
            numero = numero.rstrip("0").rstrip(".")
        return numero.replace(".", ",")
    if isinstance(valor, datetime.datetime):
        return valor.strftime("%d/%m/%Y")
    if isinstance(valor, datetime.date):
        return valor.strftime("%d/%m/%Y")
    return str(valor)
