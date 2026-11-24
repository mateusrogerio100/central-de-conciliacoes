import datetime
from decimal import Decimal

import openpyxl
import pytest

from modulos.subvencoes.modelos import ErroArquivo, MesReferencia
from modulos.subvencoes.utilitarios import (
    abrir_planilha,
    mes_de_texto,
    mes_de_valor,
    nome_com_mes,
    normalizar_texto,
    para_decimal,
    para_float_excel,
    para_inteiro,
    texto_igual,
)


def test_normalizar_texto_remove_acentos_espacos_e_caixa():
    assert normalizar_texto("  Convênio   Federal 937610/2022 ") == "convenio federal 937610/2022"
    assert normalizar_texto("Convenio Federal 773672/2012") == normalizar_texto("Convênio Federal 773672/2012")
    assert normalizar_texto(None) == ""


def test_texto_igual_ignora_dois_pontos_e_acentos():
    assert texto_igual("Mês Referência:", "Mes Referencia")
    assert texto_igual("SALDO ATUAL", "Saldo Atual")
    assert not texto_igual(123, "Saldo Atual")


@pytest.mark.parametrize("valor, esperado", [
    (1278771.55, Decimal("1278771.55")),
    (0.1 + 0.2, Decimal("0.30")),
    (600000, Decimal("600000.00")),
    (-4666.669999999998, Decimal("-4666.67")),
    ("1.234,56", Decimal("1234.56")),
    ("154.70", Decimal("154.70")),
    (Decimal("2.005"), Decimal("2.01")),
    ("abc", None),
    ("", None),
    (None, None),
    (True, None),
])
def test_para_decimal(valor, esperado):
    assert para_decimal(valor) == esperado


def test_para_decimal_sempre_duas_casas():
    assert para_decimal(10).as_tuple().exponent == -2


def test_para_float_excel():
    assert para_float_excel(Decimal("569.57")) == 569.57


@pytest.mark.parametrize("valor, esperado", [
    (24876, 24876), (24876.0, 24876), ("24876", 24876), (24876.5, None), ("Total", None), (None, None),
])
def test_para_inteiro(valor, esperado):
    assert para_inteiro(valor) == esperado


def test_mes_de_valor():
    assert mes_de_valor(datetime.datetime(2026, 8, 1)) == MesReferencia(2026, 8)
    assert mes_de_valor("01/08/2026") == MesReferencia(2026, 8)
    assert mes_de_valor("01/08/26") == MesReferencia(2026, 8)
    assert mes_de_texto("09/2026") == MesReferencia(2026, 9)
    assert mes_de_texto("13/2026") is None
    assert mes_de_valor(12345) is None


def test_mes_referencia_formatos():
    mes = MesReferencia(2026, 9)
    assert str(mes) == "09/2026"
    assert mes.para_nome_arquivo == "09-2026"
    with pytest.raises(ValueError):
        MesReferencia(2026, 13)


@pytest.mark.parametrize("nome, esperado", [
    ("Projetos_08-2026.xlsx", "Projetos_09-2026.xlsx"),
    ("Projetos 08-2026.xlsx", "Projetos 09-2026.xlsx"),
    ("Subvenções_Investimento_08-2026.xlsx", "Subvenções_Investimento_09-2026.xlsx"),
    ("Planilha.xlsx", "Planilha_09-2026.xlsx"),
    ("Copia 01-2025 de 08-2026.xlsx", "Copia 01-2025 de 09-2026.xlsx"),
])
def test_nome_com_mes(nome, esperado):
    assert nome_com_mes(nome, MesReferencia(2026, 9)) == esperado


def test_abrir_planilha_erros_claros(tmp_path):
    with pytest.raises(ErroArquivo, match="não encontrado"):
        abrir_planilha(tmp_path / "nao_existe.xlsx")

    antigo = tmp_path / "antigo.xls"
    antigo.write_bytes(b"x")
    with pytest.raises(ErroArquivo, match=r"\.xls"):
        abrir_planilha(antigo)

    corrompido = tmp_path / "corrompido.xlsx"
    corrompido.write_bytes(b"isto nao e um xlsx")
    with pytest.raises(ErroArquivo, match="não foi possível abrir"):
        abrir_planilha(corrompido)


def test_abrir_planilha_ok(tmp_path):
    caminho = tmp_path / "ok.xlsx"
    openpyxl.Workbook().save(caminho)
    pasta = abrir_planilha(caminho)
    assert pasta.worksheets
