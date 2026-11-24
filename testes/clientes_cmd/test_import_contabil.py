"""Testes do Import Contábil (criados na migração para a Central: o programa original não tinha).

Os valores esperados são os arquivos reais conferidos em exemplos/clientes_cmd/import_contabil/:
- Rel_Geral_08_2026.xlsx e Import_gerado_08_2026.txt: agosto/2026, a partir de relatorio_fonte/;
- mes_anterior/Rel Geral.xlsx e mes_anterior/Import_gerado.txt: julho/2026.
Antes da migração, o código original foi rodado com esses arquivos e reproduziu todos eles.
"""

from __future__ import annotations

import math

import openpyxl
import pytest

from modulos.clientes_cmd.import_contabil.consolidar import converter_valor
from modulos.clientes_cmd.import_contabil.processamento import (
    gerar_arquivo_import,
    gerar_rel_geral,
    nome_import,
    nome_rel_geral,
)
from testes.conftest import diferencas_entre_planilhas, pasta_exemplos

# Linhas que cada relatório de agosto/2026 traz (conferido com o programa original).
LINHAS_AGOSTO = {
    "5270- Contratos Cartão de Credito.xlsx": 4964,
    "5285- Clientes PJ receita.xlsx": 1185,
    "5288- Colaboradores ame receita.xlsx": 7,
    "5288-Colaboradores CMD receita.xlsx": 8,
    "5288-Colaboradores Hospital Exemplo.xlsx": 304,
    "5329-Colaboradores Hospital Exemplo provisão.xlsx": 35,
    "5330-Clientes PJ provisão.xlsx": 155,
    "5944-Contrato PF Boleto - Parcela.xlsx": 6,
}


@pytest.fixture(scope="module")
def exemplos():
    return pasta_exemplos("clientes_cmd", "import_contabil")


@pytest.fixture(scope="module")
def rel_geral_agosto(exemplos, tmp_path_factory):
    """Gera o Rel_Geral de agosto uma vez só e reaproveita nos testes."""
    destino = tmp_path_factory.mktemp("import") / nome_rel_geral(8, 2026)
    return gerar_rel_geral(exemplos / "relatorio_fonte", destino)


# ---------------------------------------------------------------------------
# Passo 1: Rel_Geral
# ---------------------------------------------------------------------------


def test_rel_geral_linhas_por_relatorio(rel_geral_agosto):
    assert rel_geral_agosto.linhas_por_arquivo == LINHAS_AGOSTO
    assert rel_geral_agosto.total == sum(LINHAS_AGOSTO.values()) == 6664


def test_rel_geral_igual_ao_conferido(rel_geral_agosto, exemplos):
    assert diferencas_entre_planilhas(exemplos / "Rel_Geral_08_2026.xlsx", rel_geral_agosto.caminho) == []


def test_rel_geral_tem_uma_aba_consolidado(rel_geral_agosto):
    assert openpyxl.load_workbook(rel_geral_agosto.caminho).sheetnames == ["Consolidado"]


def test_pasta_sem_relatorios(tmp_path):
    with pytest.raises(ValueError, match="Nenhum relatório .xlsx ou .xls"):
        gerar_rel_geral(tmp_path, tmp_path / "saida.xlsx")


def test_arquivo_temporario_do_excel_e_ignorado(exemplos, tmp_path):
    pasta = tmp_path / "relatorios"
    pasta.mkdir()
    origem = exemplos / "relatorio_fonte" / "5944-Contrato PF Boleto - Parcela.xlsx"
    (pasta / origem.name).write_bytes(origem.read_bytes())
    (pasta / "~$planilha aberta.xlsx").write_bytes(b"lixo")

    resultado = gerar_rel_geral(pasta, tmp_path / "saida.xlsx")

    assert resultado.linhas_por_arquivo == {origem.name: 6}


# ---------------------------------------------------------------------------
# Passo 2: arquivo de import
# ---------------------------------------------------------------------------


def test_import_agosto_igual_ao_conferido(rel_geral_agosto, exemplos, tmp_path):
    resultado = gerar_arquivo_import(rel_geral_agosto.caminho, 8, 2026, tmp_path / nome_import(8, 2026))
    assert resultado.total == 6664
    assert resultado.caminho.read_bytes() == (exemplos / "Import_gerado_08_2026.txt").read_bytes()


def test_import_a_partir_do_rel_geral_conferido(exemplos, tmp_path):
    resultado = gerar_arquivo_import(exemplos / "Rel_Geral_08_2026.xlsx", 8, 2026, tmp_path / "import.txt")
    assert resultado.caminho.read_bytes() == (exemplos / "Import_gerado_08_2026.txt").read_bytes()


def test_import_julho_igual_ao_conferido(exemplos, tmp_path):
    mes_anterior = exemplos / "mes_anterior"
    resultado = gerar_arquivo_import(mes_anterior / "Rel Geral.xlsx", 7, 2026, tmp_path / "import.txt")
    assert resultado.caminho.read_bytes() == (mes_anterior / "Import_gerado.txt").read_bytes()


def test_import_formato_das_linhas(rel_geral_agosto, tmp_path):
    caminho = gerar_arquivo_import(rel_geral_agosto.caminho, 8, 2026, tmp_path / "import.txt").caminho
    bruto = caminho.read_bytes()
    linhas = bruto.decode("iso-8859-1").split("\r\n")
    assert linhas[-1] == ""                          # termina com CRLF
    assert b"\n" not in bruto.replace(b"\r\n", b"")  # nenhuma quebra só com LF
    assert len(linhas) - 1 == 2 * 6664               # duas linhas por lançamento
    assert linhas[0].startswith("310826,")           # data fixa no último dia do mês (DDMMAA)


def test_caractere_fora_do_iso_8859_1(exemplos, tmp_path):
    """O sistema contábil só aceita ISO-8859-1: um caractere fora dela gera erro claro."""
    livro = openpyxl.load_workbook(exemplos / "Rel_Geral_08_2026.xlsx")
    aba = livro["Consolidado"]
    titulos = [c.value for c in aba[1]]
    aba.cell(2, titulos.index("Complemento") + 1).value = "Parcela €"
    rel_geral = tmp_path / "Rel_Geral_com_euro.xlsx"
    livro.save(rel_geral)

    with pytest.raises(ValueError, match="ISO-8859-1"):
        gerar_arquivo_import(rel_geral, 8, 2026, tmp_path / "import.txt")
    assert not (tmp_path / "import.txt").exists()


# ---------------------------------------------------------------------------
# Regras menores
# ---------------------------------------------------------------------------


def test_nomes_padrao():
    assert nome_rel_geral(8, 2026) == "Rel_Geral_08_2026.xlsx"
    assert nome_import(8, 2026) == "Import_gerado_08_2026.txt"


@pytest.mark.parametrize(
    "valor, esperado",
    [
        ("2,614.91", 2614.91),
        ("2,614,91", 2614.91),
        ("2.614.91", 2614.91),
        ("2614,91", 2614.91),
        (" 15.5 ", 15.5),
        (1234, 1234.0),
        (99.9, 99.9),
    ],
)
def test_converter_valor(valor, esperado):
    assert converter_valor(valor) == pytest.approx(esperado)


@pytest.mark.parametrize("valor", [None, "", "   ", float("nan")])
def test_converter_valor_vazio(valor):
    assert math.isnan(converter_valor(valor))


def test_progresso_dos_dois_passos(exemplos, tmp_path):
    passos = []
    guardar = lambda texto, fracao: passos.append((texto, fracao))  # noqa: E731

    rel_geral = gerar_rel_geral(exemplos / "relatorio_fonte", tmp_path / "rel.xlsx", progresso=guardar)
    assert passos[0][1] == 0.0 and passos[-1] == ("Concluído.", 1.0)

    passos.clear()
    gerar_arquivo_import(rel_geral.caminho, 8, 2026, tmp_path / "import.txt", progresso=guardar)
    assert passos[0][1] == 0.0 and passos[-1] == ("Concluído.", 1.0)
