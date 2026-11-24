"""PlanilhaHM 3: inserir linhas sem o Excel, mantendo as fórmulas (R7).

Teste obrigatório 5 da seção 8: inserir na planilha de agosto as 12 linhas que o gabarito de setembro (feito
pelo Excel) tem a mais; toda fórmula das linhas que já existiam fica igual à do gabarito, sem #REF!.
"""

from __future__ import annotations

import hashlib

import openpyxl
import pytest
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table, TableFormula

from modulos.planilha_hm.insercao_linhas import deslocar_referencias, inserir_linhas
from modulos.planilha_hm.leitor_planilha import ler_planilha, linhas_da_formula
from testes.planilha_hm.conftest import planilha_real

# a planilha real tem uma área de impressão quebrada (#N/A) desde antes; aqui ela é aberta direto pelo openpyxl
pytestmark = pytest.mark.filterwarnings("ignore:Print area cannot be set")


def _estilo(celula):
    f, p, b = celula.font, celula.fill, celula.border
    return (f.name, f.sz, f.b, f.color.rgb if f.color else None, p.patternType,
            p.fgColor.rgb if p.fgColor else None, p.fgColor.theme if p.fgColor else None,
            tuple(getattr(b, lado).style for lado in ("left", "right", "top", "bottom")), celula.number_format)


# ---------------------------------------------------------------------------
# Teste 5: comparação com o gabarito de setembro
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def setembro_com_linhas_inseridas(tmp_path_factory):
    """A planilha de agosto com as linhas novas do gabarito inseridas (vazias), gravada e aberta de novo."""
    agosto, setembro = ler_planilha(planilha_real("2026-08")), ler_planilha(planilha_real("2026-09"))

    def chaves(p):
        return ({(e.numero, "-"): e.linha for e in p.eventos}
                | {(e.numero, c.codigo): c.linha for e in p.eventos for c in e.ccs})

    secoes_novas = [s for s in setembro.secoes if s.nome not in {x.nome for x in agosto.secoes}]
    novas = sorted([chaves(setembro)[k] for k in set(chaves(setembro)) - set(chaves(agosto))]
                   + [s.linha for s in secoes_novas] + [s.linha_total for s in secoes_novas])
    caminho = planilha_real("2026-08")
    antes = hashlib.md5(caminho.read_bytes()).hexdigest()
    livro = openpyxl.load_workbook(caminho)
    for numero in novas:                       # em ordem crescente, cada linha já na numeração final
        inserir_linhas(livro, "2026", numero)
    gravada = tmp_path_factory.mktemp("r7") / "inserida.xlsx"
    livro.save(gravada)
    assert hashlib.md5(caminho.read_bytes()).hexdigest() == antes            # a entrada não muda
    return novas, openpyxl.load_workbook(gravada), setembro


def _mapa(novas: list[int], ultima: int) -> dict[int, int]:
    """Linha de agosto -> linha depois das inserções."""
    mapa, destino = {}, 1
    for linha in range(1, ultima + 1):
        while destino in novas:
            destino += 1
        mapa[linha] = destino
        destino += 1
    return mapa


def test_5_formulas_iguais_as_do_gabarito(setembro_com_linhas_inseridas):
    novas, livro, setembro = setembro_com_linhas_inseridas
    assert novas == [163, 164, 260, 261, 602, 955, 1182, 1368, 1653, 1654, 1655, 1656]
    nossa = livro["2026"]
    original = openpyxl.load_workbook(planilha_real("2026-08"))["2026"]
    gabarito = openpyxl.load_workbook(planilha_real("2026-09"))["2026"]
    mapa = _mapa(novas, original.max_row)
    fixos = next(s for s in setembro.secoes if s.nome == "HONORÁRIOS MÉDICOS - FIXOS")
    evento_novo = setembro.evento(3171).linha
    total_secao_nova = next(s for s in setembro.secoes if s.nome == "HM CATARATA - AGLUTINADA PJ").linha_total
    diferentes = []
    for linha in range(1, original.max_row + 1):
        for coluna in range(1, original.max_column + 1):
            nosso, esperado = nossa.cell(mapa[linha], coluna).value, gabarito.cell(mapa[linha], coluna).value
            if nosso == esperado or (isinstance(nosso, float) and isinstance(esperado, float)
                                     and round(nosso, 6) == round(esperado, 6)):
                continue
            letra = get_column_letter(coluna)
            a_mais = set(linhas_da_formula(esperado, letra)) - set(linhas_da_formula(nosso, letra))
            # o que a R5/R6 acrescenta (PlanilhaHM 4): o evento 3171 no total dos FIXOS e a seção nova no
            # TOTAL GERAL; e o LOTE REPASSE de setembro
            if mapa[linha] in (fixos.linha_total, setembro.linha_total_geral) and a_mais == (
                    {evento_novo} if mapa[linha] == fixos.linha_total else {total_secao_nova}) and set(
                    linhas_da_formula(nosso, letra)) <= set(linhas_da_formula(esperado, letra)):
                continue
            if mapa[linha] == setembro.linha_lote and coluna == setembro.colunas_meses[9] and nosso is None:
                continue
            diferentes.append((mapa[linha], letra, nosso, esperado))
    assert diferentes == []


def test_5_nenhum_ref_e_outras_abas_iguais(setembro_com_linhas_inseridas):
    _, livro, _ = setembro_com_linhas_inseridas
    original = openpyxl.load_workbook(planilha_real("2026-08"))
    for aba in livro.worksheets:
        for linha in aba.iter_rows():
            for celula in linha:
                assert not (isinstance(celula.value, str) and "#REF" in celula.value), (aba.title, celula.coordinate)
    for nome in livro.sheetnames[1:]:          # as abas Senior só apontam para '2026'!C:C: não mudam
        assert _valores(livro[nome]) == _valores(original[nome]), nome


def _valores(aba) -> list[list]:
    """Os valores da aba; número arredondado (gravar e abrir muda a 13ª casa: 412.70000000000005 -> 412.7)."""
    return [[round(c.value, 6) if isinstance(c.value, float) else c.value for c in linha] for linha in aba.iter_rows()]


def test_5_formatacao_e_alturas_descem_junto(setembro_com_linhas_inseridas):
    novas, livro, _ = setembro_com_linhas_inseridas
    nossa = livro["2026"]
    original = openpyxl.load_workbook(planilha_real("2026-08"))["2026"]
    mapa = _mapa(novas, original.max_row)
    for linha in range(1, original.max_row + 1):
        assert nossa.row_dimensions[mapa[linha]].height == original.row_dimensions[linha].height, linha
        for coluna in range(1, original.max_column + 1):
            assert _estilo(nossa.cell(mapa[linha], coluna)) == _estilo(original.cell(linha, coluna)), (linha, coluna)
    assert nossa.freeze_panes == original.freeze_panes == "F7"               # acima das inserções: não muda


def test_5_tabela_do_excel_cresce_como_no_gabarito(setembro_com_linhas_inseridas):
    """A aba 2026 tem uma tabela do Excel (linha 6 até a linha de totais). Se ela não crescer junto, o Excel acusa
    "problema no conteúdo" ao abrir a cópia (visto pelo usuário em 30/10/2026)."""
    _, livro, _ = setembro_com_linhas_inseridas
    gabarito = openpyxl.load_workbook(planilha_real("2026-09"))["2026"]
    [nossa] = livro["2026"].tables.values()
    [esperada] = gabarito.tables.values()
    assert (nossa.ref, nossa.autoFilter.ref) == (esperada.ref, esperada.autoFilter.ref) == ("A6:Q1658", "A6:Q1657")
    assert ([c.totalsRowFormula.attr_text if c.totalsRowFormula else None for c in nossa.tableColumns]
            == [c.totalsRowFormula.attr_text if c.totalsRowFormula else None for c in esperada.tableColumns])


# ---------------------------------------------------------------------------
# Referências numa fórmula
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("formula, antes, esperado", [
    ("=SUM(N95+N93+N91)", 94, "=SUM(N96+N93+N91)"),
    ("=SUM(N1489,N1486)", 1, "=SUM(N1490,N1487)"),
    ("=N1647+N1649", 1648, "=N1647+N1650"),
    ("=SUM(F5:F10)", 8, "=SUM(F5:F11)"),           # o intervalo cresce
    ("=SUM(F5:F10)", 5, "=SUM(F6:F11)"),
    ("=SUM(F5:F10)", 11, "=SUM(F5:F10)"),
    ("=$C$7&D7", 7, "=$C$8&D8"),
    ("=A7&D7", 8, "=A7&D7"),
    ("=SUMIF('Senior 09 2026'!$A:$A,$C7,'Senior 09 2026'!$D:$D)", 5,
     "=SUMIF('Senior 09 2026'!$A:$A,$C8,'Senior 09 2026'!$D:$D)"),
    ("='Senior 09 2026'!A10+A10", 5, "='Senior 09 2026'!A10+A11"),    # outra aba não desce
    ("='2026'!A10+A10", 5, "='2026'!A11+A11"),                          # a própria aba com o nome
    ('=CONCATENATE("A10",A10)', 5, '=CONCATENATE("A10",A11)'),          # texto entre aspas fica
    ("=LOG10(A10)", 5, "=LOG10(A11)"),
    ("=N1657-N1660", 1658, "=N1657-N1661"),
])
def test_deslocar_na_propria_aba(formula, antes, esperado):
    assert deslocar_referencias(formula, "2026", "2026", antes) == esperado


@pytest.mark.parametrize("formula, esperado", [
    ("=VLOOKUP(F2,'2026'!C:C,1,0)", "=VLOOKUP(F2,'2026'!C:C,1,0)"),    # coluna inteira não muda
    ("='2026'!N100+A100", "='2026'!N101+A100"),                         # só a referência à aba 2026 desce
    ("=SUM('2026'!N5:N200)", "=SUM('2026'!N5:N201)"),
])
def test_deslocar_em_outra_aba(formula, esperado):
    assert deslocar_referencias(formula, "2026", "Senior 09 2026", 50) == esperado


def test_deslocar_mais_de_uma_linha():
    assert deslocar_referencias("=SUM(N95+N93)", "2026", "2026", 94, quantidade=3) == "=SUM(N98+N93)"


def test_aba_com_apostrofo_no_nome():
    assert deslocar_referencias("='O''Brien'!A5", "O'Brien", "Outra", 5) == "='O''Brien'!A6"


# ---------------------------------------------------------------------------
# Planilha fictícia: o que desce junto com as linhas
# ---------------------------------------------------------------------------

def test_inserir_linhas_ficticia(tmp_path):
    livro = openpyxl.Workbook()
    aba = livro.active
    aba.title = "2026"
    for linha in range(1, 11):
        aba.cell(linha, 1, f"linha {linha}")
        aba.cell(linha, 2, linha)
    aba["C10"] = "=SUM(B1:B9)"
    aba["B4"].font = Font(bold=True)
    aba["B4"].fill = PatternFill("solid", fgColor="FFFF00")
    aba.row_dimensions[6].height = 30
    aba.row_dimensions[6].hidden = True
    aba.merge_cells("A7:B7")
    aba.merge_cells("D2:D8")                       # atravessa o ponto de inserção: cresce
    aba.freeze_panes = "B6"
    aba.conditional_formatting.add("B5:B9", CellIsRule(operator="greaterThan", formula=["$B$9"],
                                                       fill=PatternFill("solid", fgColor="FF0000")))
    validacao = DataValidation(type="list", formula1="$A$8:$A$9")
    validacao.add("E6:E9")
    aba.add_data_validation(validacao)
    livro.defined_names["faixa"] = DefinedName("faixa", attr_text="'2026'!$B$6:$B$9")
    tabela = Table(displayName="TabelaExemplo", ref="A1:B9", totalsRowCount=1)
    tabela._initialise_columns()
    tabela.tableColumns[1].totalsRowFunction = "custom"
    tabela.tableColumns[1].totalsRowFormula = TableFormula(attr_text="SUM(B2:B8)")
    aba.add_table(tabela)
    outra = livro.create_sheet("Outra")
    outra["A1"] = "='2026'!B8*2"
    outra["A2"] = "=B8"                            # B8 da própria aba "Outra": não muda

    inserir_linhas(livro, "2026", 5, quantidade=2, modelo=4)
    caminho = tmp_path / "inserida.xlsx"
    livro.save(caminho)
    livro = openpyxl.load_workbook(caminho)
    aba, outra = livro["2026"], livro["Outra"]

    assert [aba.cell(l, 1).value for l in range(1, 13)] == [
        "linha 1", "linha 2", "linha 3", "linha 4", None, None, "linha 5", "linha 6", "linha 7", "linha 8",
        "linha 9", "linha 10"]
    assert aba["C12"].value == "=SUM(B1:B11)"
    assert aba["B5"].font.b and aba["B6"].font.b and aba["B5"].value is None      # formatação da linha modelo
    assert aba.row_dimensions[8].height == 30 and aba.row_dimensions[8].hidden
    assert not aba.row_dimensions[6].hidden
    assert sorted(map(str, aba.merged_cells.ranges)) == ["A9:B9", "D2:D10"]
    assert aba.freeze_panes == "B8"
    assert [str(f.sqref) for f in aba.conditional_formatting] == ["B7:B11"]
    assert next(iter(aba.conditional_formatting)).rules[0].formula == ["$B$11"]
    dv = aba.data_validations.dataValidation[0]
    assert str(dv.sqref) == "E8:E11" and dv.formula1 == "$A$10:$A$11"
    assert livro.defined_names["faixa"].attr_text == "'2026'!$B$8:$B$11"
    assert (outra["A1"].value, outra["A2"].value) == ("='2026'!B10*2", "=B8")
    tabela = aba.tables["TabelaExemplo"]
    assert tabela.ref == "A1:B11" and tabela.tableColumns[1].totalsRowFormula.attr_text == "SUM(B2:B10)"
