"""E1 — abertura dos relatórios do Tasy (texto com tabulação, .xlsx, .xls binário) e números."""

from __future__ import annotations

import datetime
from decimal import Decimal

import openpyxl
import pytest

from modulos.conciliacao_estoque.leitor_tasy_texto import ler_linhas
from modulos.conciliacao_estoque.modelos import ErroArquivo, MesReferencia
from modulos.conciliacao_estoque.utilitarios import mes_de_texto, para_decimal


@pytest.mark.parametrize("texto, esperado", [
    ("1.234.567,89", Decimal("1234567.89")),
    ("-523.694,13", Decimal("-523694.13")),
    ("6.558.659,62", Decimal("6558659.62")),
    ("0", Decimal("0.00")),
    ("660", Decimal("660.00")),
    ("59,7", Decimal("59.70")),
    ("0,09", Decimal("0.09")),
    ("2090915,58", Decimal("2090915.58")),
    (" 86,06 ", Decimal("86.06")),
])
def test_numero_no_formato_brasileiro(texto, esperado):
    assert para_decimal(texto) == esperado


@pytest.mark.parametrize("texto", ["", "abc", "1.23,4", "1,234.56", "1.01.04", "(23)", "12,"])
def test_texto_que_nao_e_numero(texto):
    assert para_decimal(texto) is None


@pytest.mark.parametrize("texto, esperado", [
    ("set/2026", MesReferencia(2026, 9)),
    ("SET/2026", MesReferencia(2026, 9)),
    ("01/09/2026", MesReferencia(2026, 9)),
    ("09/2026", MesReferencia(2026, 9)),
    ("xyz/2026", None),
    ("01/13/2026", None),
])
def test_mes_de_texto(texto, esperado):
    assert mes_de_texto(texto) == esperado


def test_texto_com_tabulacao_em_cp1252(tmp_path):
    arquivo = tmp_path / "relatorio.xls"
    arquivo.write_bytes("Farmácia\t\t1.234,56\nCoração\tx\n".encode("cp1252"))
    assert ler_linhas(arquivo) == [["Farmácia", "", "1.234,56"], ["Coração", "x"]]


def test_xlsx_vira_texto_no_mesmo_formato(tmp_path):
    arquivo = tmp_path / "salvo_no_excel.xls"   # extensão não importa: vale o conteúdo
    pasta = openpyxl.Workbook()
    aba = pasta.active
    aba.append(["Almoxarifado (12)", None, 2090915.58, 660, 59.7, -0.09, 0.1 + 0.2])
    aba.append([datetime.datetime(2026, 9, 1), "01/09/2026"])
    pasta.save(arquivo)
    linhas = ler_linhas(arquivo)
    assert linhas[0] == ["Almoxarifado (12)", "", "2090915,58", "660", "59,7", "-0,09", "0,3"]
    assert linhas[1][:2] == ["01/09/2026", "01/09/2026"]
    assert [para_decimal(t) for t in linhas[0][2:7]] == [
        Decimal("2090915.58"), Decimal("660.00"), Decimal("59.70"), Decimal("-0.09"), Decimal("0.30"),
    ]


def test_xls_binario_pede_para_salvar_como_xlsx(tmp_path):
    arquivo = tmp_path / "antigo.xls"
    arquivo.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 100)
    with pytest.raises(ErroArquivo, match="salve como .xlsx"):
        ler_linhas(arquivo)


def test_arquivo_inexistente(tmp_path):
    with pytest.raises(ErroArquivo, match="não encontrado"):
        ler_linhas(tmp_path / "nao_existe.xls")
