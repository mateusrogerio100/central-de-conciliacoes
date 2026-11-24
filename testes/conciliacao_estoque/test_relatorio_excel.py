"""E5 — Excel da EST-01 e da EST-03 (ESPECIFICACAO_ESTOQUE.md, seções 5 e 7.1 "Excel")."""

from __future__ import annotations

from decimal import Decimal

import openpyxl
import pytest

from modulos.conciliacao_estoque import configuracao
from modulos.conciliacao_estoque.comparacao import comparar
from modulos.conciliacao_estoque.leitor_balancete_estoque import ler_balancete_estoque
from modulos.conciliacao_estoque.leitor_scf import ler_scf
from modulos.conciliacao_estoque.relatorio_excel import (
    ABA_ANALISE,
    ABA_CONCILIACAO,
    gerar_excel,
    nome_do_arquivo,
)
from modulos.conciliacao_estoque.utilitarios import normalizar_texto
from testes.conciliacao_estoque.conftest import arquivo_exemplo, calcular, com_nome_antigo, ler_gabarito_estoque

EST_01, EST_03 = configuracao.ETAPAS
PARTE_DA_ETAPA = {"EST-01": "saldo_anterior", "EST-03": "saldo_atual"}


def _todas_as_formulas_calculam(aba):
    for linha in aba.iter_rows():
        for celula in linha:
            if isinstance(celula.value, str) and celula.value.startswith("="):
                calcular(aba, celula.coordinate)


def _linha_com_texto(aba, coluna: str, texto: str) -> int:
    return next(c.row for c in aba[coluna] if isinstance(c.value, str) and c.value.startswith(texto))


# ---------------------------------------------------------------------------
# Setembro/2026
# ---------------------------------------------------------------------------


@pytest.fixture
def gerar(caminho_balancete, caminho_scf, tmp_path):
    balancete, scf = ler_balancete_estoque(caminho_balancete), ler_scf(caminho_scf)

    def _gerar(etapa):
        resultado = comparar(etapa, balancete, scf)
        caminho = gerar_excel(resultado, tmp_path)
        return resultado, caminho, openpyxl.load_workbook(caminho)

    return _gerar


def test_nome_do_arquivo(gerar):
    assert gerar(EST_01)[1].name == "EST-01 Conciliação saldo anterior estoque 09-2026.xlsx"
    assert gerar(EST_03)[1].name == "EST-03 Conciliação saldo atual estoque 09-2026.xlsx"


@pytest.mark.parametrize("etapa", configuracao.ETAPAS, ids=lambda e: e.id)
def test_aba_analise_igual_ao_gabarito(gerar, etapa):
    _, _, pasta = gerar(etapa)
    aba = pasta[ABA_ANALISE]
    _todas_as_formulas_calculam(aba)
    gerado = {}
    for linha in range(5, 45):
        gerado[aba[f"B{linha}"].value] = (
            str(aba[f"A{linha}"].value or ""), calcular(aba, f"C{linha}"), calcular(aba, f"D{linha}"),
            calcular(aba, f"E{linha}"), str(aba[f"F{linha}"].value or ""),
            normalizar_texto(com_nome_antigo(aba[f"G{linha}"].value or "").replace("—", "-")),
        )
    esperado = {
        (g["descricao_balancete"] or g["descricao_scf"]): (
            g["classificacao"], g["saldo_balancete"], g["saldo_scf"], g["diferenca"], g["codigo"],
            normalizar_texto(g["observacao"].replace("—", "-")),
        )
        for g in ler_gabarito_estoque() if g["parte"] == PARTE_DA_ETAPA[etapa.id]
    }
    assert gerado == esperado
    assert aba["B45"].value == "TOTAL"
    assert aba["C45"].value == "=SUBTOTAL(9,C5:C44)"
    assert aba["F4"].value == "Código" and aba["G4"].value == "Observação"     # Código: pedido de 05/11/2026
    assert aba.auto_filter.ref == "A4:G44"
    assert aba.freeze_panes == "A5"


def test_aba_analise_est03_igual_ao_exemplo_aprovado(gerar):
    exemplo = openpyxl.load_workbook(arquivo_exemplo("Exemplo_Conciliacao_Estoque_09-2026.xlsx"))[ABA_ANALISE]
    gerada = gerar(EST_03)[2][ABA_ANALISE]
    # Mudanças aprovadas depois do exemplo: Classificação no lugar do Código reduzido (coluna A, 06/10/2026);
    # o Código volta na coluna F, entre Diferença e Observação, que vai para a G (05/11/2026); "Mapa do Estoque"
    # no lugar de "SCF" (05/11/2026) é comparado com o nome antigo.
    coluna_gerada = {"A": "A", "B": "B", "C": "C", "D": "D", "E": "E", "F": "G"}
    diferencas = [
        (c.coordinate, c.value, gerada[f"{coluna_gerada[c.column_letter]}{c.row}"].value)
        for linha in exemplo.iter_rows(min_row=1, max_row=45, max_col=6) for c in linha
        if c.value != com_nome_antigo(gerada[f"{coluna_gerada[c.column_letter]}{c.row}"].value)
    ]
    assert {d[0][0] for d in diferencas} == {"A"}
    # o Código da coluna F é o mesmo que o exemplo trazia na coluna A
    assert [gerada[f"F{n}"].value for n in range(5, 45)] == [exemplo[f"A{n}"].value for n in range(5, 45)]
    assert gerada["A4"].value == "Classificação"
    assert gerada["A5"].value == "1.01.04.01.0002"
    assert gerada["A28"].value is None          # local do SCF sem conta


def test_aba_conciliacao_est03(gerar):
    resultado, _, pasta = gerar(EST_03)
    aba = pasta[ABA_CONCILIACAO]
    _todas_as_formulas_calculam(aba)
    assert aba["A1"].value == "EST-03 · Conciliação saldo atual estoque · 09/2026"
    assert "SCF - Movimento Estoque (Contabilidade).xls" in aba["A2"].value

    total = _linha_com_texto(aba, "C", "TOTAL GERAL")
    assert calcular(aba, f"D{total}") == calcular(aba, f"F{total}") == Decimal("6034965.49")
    assert calcular(aba, f"G{total}") == 0
    subtotais = {aba[f"C{c.row}"].value: calcular(aba, f"D{c.row}") for c in aba["C"]
                 if isinstance(c.value, str) and c.value.startswith("Subtotal")}
    assert subtotais == {
        "Subtotal 1.01.04.01": Decimal("4200117.67"),
        "Subtotal 1.01.04.02": Decimal("695993.46"),
        "Subtotal 1.01.04.03": Decimal("1138854.36"),
    }
    contas = [c.row for c in aba["B"] if isinstance(c.value, int)]
    assert len(contas) == 23
    assert all(calcular(aba, f"G{n}") == 0 for n in contas)

    conferencias = _linha_com_texto(aba, "C", "Conferências")
    diferencas = [calcular(aba, f"F{n}") for n in range(conferencias + 1, conferencias + 6)]
    assert diferencas == [0] * 5        # 1.01.04, SCF e os 3 grupos
    locais = _linha_com_texto(aba, "A", "Locais do Mapa do Estoque sem conta")
    assert [aba[f"E{n}"].value for n in range(locais + 1, locais + 18)][0] == "Suprimentos Nutrição - Hosp. Coração (16)"
    assert aba[f"E{locais + 18}"].value is None
    assert aba.freeze_panes == "D5"


def test_aba_conciliacao_est01_mostra_o_enxoval(gerar):
    _, _, pasta = gerar(EST_01)
    aba = pasta[ABA_CONCILIACAO]
    _todas_as_formulas_calculam(aba)
    raiz = _linha_com_texto(aba, "C", "Saldo do grupo 1.01.04 ESTOQUES")
    assert calcular(aba, f"D{raiz}") == Decimal("6558659.62")
    assert calcular(aba, f"F{raiz}") == Decimal("41038.00")
    scf = _linha_com_texto(aba, "C", "Total geral do Mapa do Estoque")
    assert calcular(aba, f"F{scf}") == 0           # contas + locais sem conta (com o Enxoval)
    hospital_exemplo = _linha_com_texto(aba, "C", "Saldo do grupo 1.01.04.01")
    assert calcular(aba, f"F{hospital_exemplo}") == Decimal("41038.00")
    assert aba[f"G{hospital_exemplo}"].value.startswith("Diferença no grupo 1.01.04.01 igual ao saldo")
    assert aba[f"G{hospital_exemplo}"].value.endswith("trazer as contas zeradas, para o programa identificar a conta.")
    enxoval = _linha_com_texto(aba, "E", "Estoque Enxoval Hospitalar (67)")
    assert calcular(aba, f"F{enxoval}") == Decimal("41038.00")
    assert aba[f"I{enxoval}"].value == "Local do Mapa do Estoque sem conta no balancete — COM SALDO"


@pytest.mark.parametrize("etapa", configuracao.ETAPAS, ids=lambda e: e.id)
def test_formatacao(gerar, etapa):
    _, _, pasta = gerar(etapa)
    for nome, coluna_diferenca in ((ABA_CONCILIACAO, "G"), (ABA_ANALISE, "E")):
        aba = pasta[nome]
        assert aba.sheet_view.showGridLines is False
        assert aba["A4"].fill.fgColor.rgb.endswith("0F5C63")
        assert aba["A4"].font.color.rgb.endswith("FFFFFF")
        assert aba["A5"].font.name == "Arial"
        regras = {str(intervalo.sqref): [r.formula for r in intervalo.rules] for intervalo in aba.conditional_formatting}
        assert regras[f"{coluna_diferenca}5:{coluna_diferenca}{'34' if nome == ABA_CONCILIACAO else '44'}"] == [
            [f"ROUND({coluna_diferenca}5,2)<>0"]
        ]
        celula_valor = aba["D6"] if nome == ABA_CONCILIACAO else aba["C5"]
        assert celula_valor.number_format == '#,##0.00;[Red]-#,##0.00;"-"'


def test_sem_mes_nao_gera(gerar, caminho_balancete, caminho_scf, tmp_path):
    resultado = comparar(EST_03, ler_balancete_estoque(caminho_balancete), ler_scf(caminho_scf))
    resultado.mes_referencia = None
    with pytest.raises(ValueError):
        nome_do_arquivo(resultado)
