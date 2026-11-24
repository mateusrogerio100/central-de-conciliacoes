"""Import Contábil com os relatórios no .xls como sai do Tasy (texto separado por tabulação, cp1252).

Pedido do usuário (11/11/2026): juntar os relatórios no Rel_Geral sem precisar abrir cada um no Excel e
salvar como .xlsx. O teste principal regrava os relatórios reais de agosto/2026 no formato de texto do
Tasy e confere que o Rel_Geral sai igual ao conferido. Os demais usam dados fictícios.
"""

from __future__ import annotations

import csv
import io

import openpyxl
import pandas as pd
import pytest

from modulos.clientes_cmd.import_contabil.consolidar import celula_do_texto
from modulos.clientes_cmd.import_contabil.processamento import contar_relatorios, gerar_rel_geral
from testes.conftest import diferencas_entre_planilhas, pasta_exemplos

CABECALHO = ["NR_CONTRATO", "Dia lançamento", "Conta debito", "Conta credito", "Vl parcela", "Historico",
             "Complemento", "Centro custo", "Vl parcela"]


def _texto_do_tasy(linhas) -> bytes:
    """Como o Tasy grava: tabulação, aspas de CSV, CRLF, cp1252."""
    saida = io.StringIO(newline="")
    csv.writer(saida, delimiter="\t", quotechar='"', lineterminator="\r\n").writerows(linhas)
    return saida.getvalue().encode("cp1252")


def _para_texto(valor) -> str:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    if isinstance(valor, float):
        return f" {valor:017.2f}".replace(".", ",")        # " 0000000000159,80", como o Tasy
    return str(valor)


@pytest.mark.parametrize("texto, esperado", [
    ("", None),
    ("201749", 201749),
    ("091126", 91126),
    (" 0000000000159,80", 159.8),
    ("1.234,56", 1234.56),
    ("79.90", "79.90"),                     # o Excel em português deixa como texto; converter_valor resolve
    (' " lote mensalidade&1, produto& X"', ' " lote mensalidade&1, produto& X"'),
])
def test_celula_convertida_como_o_excel(texto, esperado):
    assert celula_do_texto(texto) == esperado


def test_relatorio_do_tasy_vira_rel_geral(tmp_path):
    pasta = tmp_path / "relatorios"
    pasta.mkdir()
    # gravado à mão, byte a byte como o Tasy: as aspas do Complemento vêm desse jeito nos arquivos reais
    cabecalho = "\t".join(CABECALHO)
    texto = "\r\n".join([
        cabecalho,
        '100\t091126\t201749\t40499\t79.90\t367\t" "" lote mensalidade&1, nr contrato& 100"""\t1007\t79.90',
        cabecalho,                                                    # cabeçalho repetido a cada página
        '200\t091126\t201746\t40493\t 0000000000159,80\t367\t""""200, Caixa Vendas, aut: 1""\t1007\t'
        ' 0000000000159,80',
    ]) + "\r\n"
    (pasta / "5288-Colaboradores receita (2).xls").write_bytes(texto.encode("cp1252"))
    (pasta / "5329-provisao vazia (2).xls").write_bytes(_texto_do_tasy([CABECALHO, [""] * 9]))

    resultado = gerar_rel_geral(pasta, tmp_path / "Rel_Geral.xlsx")

    assert resultado.linhas_por_arquivo == {"5288-Colaboradores receita (2).xls": 2,
                                            "5329-provisao vazia (2).xls": 0}
    df = pd.read_excel(resultado.caminho, dtype=object)
    assert list(df["Conta debito"]) == [201749, 201746]
    assert list(df["Vl parcela formatado"]) == [79.9, 159.8]
    assert list(df["Complemento"]) == ['" lote mensalidade&1, nr contrato& 100"', '"200, Caixa Vendas, aut: 1"']
    assert contar_relatorios(pasta) == 2


def test_mesmo_relatorio_em_xls_e_xlsx_para_com_aviso(tmp_path):
    pasta = tmp_path / "relatorios"
    pasta.mkdir()
    (pasta / "5944-Boleto.xls").write_bytes(_texto_do_tasy([CABECALHO]))
    pd.DataFrame(columns=CABECALHO).to_excel(pasta / "5944-Boleto.xlsx", index=False)
    with pytest.raises(ValueError, match="entraria duas vezes"):
        gerar_rel_geral(pasta, tmp_path / "Rel_Geral.xlsx")


def test_agosto_em_texto_do_tasy_da_o_mesmo_rel_geral(tmp_path):
    exemplos = pasta_exemplos("clientes_cmd", "import_contabil")
    pasta = tmp_path / "relatorios_xls"
    pasta.mkdir()
    for origem in sorted((exemplos / "relatorio_fonte").glob("*.xlsx")):
        aba = openpyxl.load_workbook(origem, data_only=True).worksheets[0]
        linhas = [[_para_texto(v) for v in linha] for linha in aba.iter_rows(values_only=True)]
        (pasta / (origem.stem + ".xls")).write_bytes(_texto_do_tasy(linhas))

    resultado = gerar_rel_geral(pasta, tmp_path / "Rel_Geral_08_2026.xlsx")

    assert resultado.total == 6664
    assert diferencas_entre_planilhas(exemplos / "Rel_Geral_08_2026.xlsx", resultado.caminho) == []
