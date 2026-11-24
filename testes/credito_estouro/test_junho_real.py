"""V5 — junho/2026 a partir do controle de maio (ESPECIFICACAO, seção 2.4). Arquivos reais de
exemplos\\credito_estouro\\ (fora do git); nenhum nome aqui.
"""

from decimal import Decimal as D
from pathlib import Path

import pytest

from modulos.credito_estouro import conciliador as c
from modulos.credito_estouro.conciliador import conciliar
from modulos.credito_estouro.leitor_eventos import ler_eventos
from modulos.credito_estouro.leitor_razao import ler_razao
from modulos.credito_estouro.modelos import (
    TIPO_0256,
    TIPO_ACERTO,
    TIPO_DIFERENCA_0241,
    TIPO_PARCELAMENTO,
    TIPO_PENDENCIA,
)
from testes.credito_estouro.test_maio_real import PASTA, controle_inicial

pytestmark = pytest.mark.skipif(not (PASTA / "casos_reais.json").exists(), reason="exemplos reais fora do git")
EVENTOS = "2026-06"


def _junho(razao: str):
    eventos = ler_eventos(next((PASTA / EVENTOS).glob("EVENTOS*")))
    return conciliar(eventos, ler_razao(PASTA / EVENTOS / razao), controle_inicial("2026-05"))


@pytest.fixture(scope="module")
def junho():
    return _junho("razao_06_credito_suplemento.xls")


def test_junho_prova_fecha(junho):
    assert junho.avisos == []
    assert (junho.saldo_anterior_razao, junho.saldo_final_razao) == (D("98853.35"), D("116027.92"))
    assert junho.diferenca_sem_explicacao == 0
    assert junho.a_conferir == []
    assert junho.composicao == {TIPO_0256: D("111708.31"), TIPO_PARCELAMENTO: D("280.05"),
                                TIPO_DIFERENCA_0241: D("-0.30"), TIPO_PENDENCIA: D("4039.86"), TIPO_ACERTO: D("0")}


def test_junho_r1(junho):
    situacoes = [l.situacao for l in junho.cobrancas]
    assert {s: situacoes.count(s) for s in set(situacoes)} == {c.COBRADO: 139, c.COBRADO_DIFERENTE: 1,
                                                               c.PARCELAMENTO_NOVO: 1, c.NAO_COBRADO: 6}
    assert sum((l.diferenca for l in junho.cobrancas if l.situacao == c.NAO_COBRADO), D("0")) == D("4850.36")
    assert [l.diferenca for l in junho.cobrancas if l.situacao == c.COBRADO_DIFERENTE] == [D("-810.50")]


def test_junho_parcelamentos(junho):
    assert sorted((l.situacao.split(" (")[0], l.saldo_novo) for l in junho.parcelamentos) == sorted([
        ("Quitado", D("0")), ("Quitado", D("0")), (c.PARCELAMENTO_NOVO, D("280.05"))])
    novo = [l for l in junho.parcelamentos if l.situacao.startswith(c.PARCELAMENTO_NOVO)][0]
    assert (novo.saldo_anterior, novo.parcela) == (D("420.07"), D("140.02"))


def test_junho_0241(junho):
    situacoes = [l.situacao for l in junho.afastados]
    assert situacoes.count(c.PAGOU_A_MAIS) == 1 and situacoes.count(c.PAGOU_A_MENOS) == 0
    assert situacoes.count(c.NAO_PAGOU) == 0


def test_junho_com_o_razao_em_pdf_fecha_mas_nome_cortado_vai_para_conferir():
    """O PDF do Tasy corta o fim de 4 nomes: a prova fecha igual, mas esses pagamentos não acham o dono."""
    pdf = _junho("razao_06_credito_suplemento.pdf")
    assert pdf.diferenca_sem_explicacao == 0
    assert len(pdf.a_conferir) == 4
