"""Conciliação de clientes com os relatórios no .xls como sai do Tasy (texto separado por tabulação, cp1252).

Pedido do usuário (12/11/2026). O teste principal regrava o balancete e os Títulos a Receber reais de
agosto/2026 no formato de texto do Tasy e confere que a planilha sai igual à de referência.
"""

from __future__ import annotations

import csv
import io

import openpyxl
import pytest

from modulos.clientes_cmd.extracao import celula_do_texto, extrair_balancete
from modulos.clientes_cmd.processamento import processar
from testes.conftest import diferencas_entre_planilhas, pasta_exemplos


def _texto_do_tasy(linhas) -> bytes:
    saida = io.StringIO(newline="")
    csv.writer(saida, delimiter="\t", quotechar='"', lineterminator="\r\n").writerows(linhas)
    return saida.getvalue().encode("cp1252")


def _para_texto(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float):
        return f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")   # 1.234,56 como o Tasy
    return str(valor)


def _regravar_como_texto(origem, destino):
    aba = openpyxl.load_workbook(origem, data_only=True).active
    destino.write_bytes(_texto_do_tasy([[_para_texto(v) for v in l] for l in aba.iter_rows(values_only=True)]))
    return destino


@pytest.mark.parametrize("texto, esperado", [
    ("", None),
    ("14296", 14296),
    ("2.419.888,77", 2419888.77),
    ("-279,60", -279.6),
    ("1.01.14.01.0002", "1.01.14.01.0002"),
    ("              Paola", "              Paola"),
])
def test_celula_convertida_como_o_excel(texto, esperado):
    assert celula_do_texto(texto) == esperado


def test_balancete_do_tasy(tmp_path):
    linhas = [
        ["CMD - Exemplo", "", "", "", "", ""],
        ["", "", "", "", "", "", "Mês Referência:", "", "out/2026"],
        ["", "Código", "", "Classificação", "", "Descrição", "", "", "", "Saldo Anterior", "", "Movimento",
         "Saldo Atual", ""],
        ["", "", "1173", "", "1.01.14", "      CLIENTES", "", "", "", "1.000,00", "", "234,56", "1.234,56", ""],
        ["", "", "14296", "", "1.01.14.01.0002", "              Cliente A", "", "", "", "1.000,00", "", "0,00",
         "1.000,00", ""],
        ["", "", "14312", "", "1.01.14.01.0007", "              Cliente B", "", "", "", "0,00", "", "234,56",
         "234,56", ""],
        ["", "Impresso em: 12/11/2026 08:05:54", "", "", "", "", "", "Página: 1"],
    ]
    caminho = tmp_path / "Balancete_clientes.xls"
    caminho.write_bytes(_texto_do_tasy(linhas))
    df = extrair_balancete(caminho)
    assert df.values.tolist() == [[14296, "Cliente A", 1000.0], [14312, "Cliente B", 234.56]]


def test_excel_antigo_de_verdade_tem_mensagem_clara(tmp_path):
    antigo = tmp_path / "antigo.xls"
    antigo.write_bytes(bytes.fromhex("D0CF11E0") + b"\x00" * 100)
    with pytest.raises(ValueError, match="Excel antigo"):
        extrair_balancete(antigo)


def test_agosto_em_texto_do_tasy_da_a_mesma_planilha(tmp_path):
    exemplos = pasta_exemplos("clientes_cmd")
    balancete = _regravar_como_texto(exemplos / "Balancete_clientes_CMD_att.xlsx", tmp_path / "balancete.xls")
    financeiro = _regravar_como_texto(exemplos / "CONCILIAÇÕES_CLIENTES_CMD_TITULOS_RECEBER_AGO-26.xlsx",
                                      tmp_path / "titulos.xls")
    resultado = processar(balancete, financeiro, tmp_path / "Conciliacao_Clientes_CMD.xlsx")
    assert diferencas_entre_planilhas(exemplos / "Conciliacao_Clientes_CMD.xlsx", resultado.caminho) == []
