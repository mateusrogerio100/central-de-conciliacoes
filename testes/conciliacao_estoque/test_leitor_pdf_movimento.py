"""E6 — leitura do PDF "Movimento estoque" (ESPECIFICACAO_ESTOQUE.md, seções 3.5 e 7.1)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from modulos.conciliacao_estoque.configuracao_est02 import carregar_configuracao_estoque
from modulos.conciliacao_estoque.leitor_pdf_movimento import ler_pdf_movimento, ler_texto_movimento
from modulos.conciliacao_estoque.modelos import ErroArquivo, Gravidade, MesReferencia
from testes.conciliacao_estoque.conftest import arquivo_exemplo

OPERACOES_SETEMBRO = {1, 2, 4, 11, 12, 13, 14, 15, 16, 17, 51, 87, 91, 92, 101, 112, 117, 120}


@pytest.fixture
def setembro():
    return ler_pdf_movimento(arquivo_exemplo("Movimento_estoque_PDF.pdf"))


def test_setembro_operacoes_e_total_geral(setembro):
    assert setembro.mes_referencia == MesReferencia(2026, 9)
    assert len(setembro.operacoes) == 18
    assert {o.codigo for o in setembro.operacoes} == OPERACOES_SETEMBRO
    assert setembro.total_geral == setembro.soma_operacoes == Decimal("12085173.07")
    assert setembro.avisos == []


def test_setembro_valores(setembro):
    assert setembro.valor(1) == Decimal("2586295.37")       # nome na mesma linha
    assert setembro.valor(16) == Decimal("12826.35")        # nome acima e abaixo da linha "Operação"
    assert setembro.valor(15) == Decimal("12983.54")
    assert setembro.valor(117) == Decimal("0.00")
    assert setembro.valor(2) == Decimal("1505890.74")       # página 2
    assert setembro.valor(999) == Decimal("0.00")           # ausente vale 0
    assert {o.codigo for o in setembro.operacoes if o.pagina == 2} == {91, 120, 12, 2}


def test_setembro_todas_as_operacoes_tem_grupo(setembro, tmp_path):
    config = carregar_configuracao_estoque(pasta=tmp_path)
    assert [o.codigo for o in setembro.operacoes if config.grupo_da_operacao(o.codigo) is None] == []


# ---------------------------------------------------------------------------
# Casos construídos (texto já extraído)
# ---------------------------------------------------------------------------

CABECALHO = "Movimento estoque\nQuebras: Operação\nData de Referência : 01/09/2026\nOperação Quantidade Valor\n"


def _ler(*paginas):
    return ler_texto_movimento([CABECALHO + p for p in paginas], "teste.pdf")


def test_caso_simples_em_duas_paginas_e_total_sem_operacao_ignorado():
    movimento = _ler(
        "Nome longo\nOperação 5\nda operação\nTotal 3 10,00 1.000,50\nImpresso em 05/10/2026 Página 1",
        "Operação 7 Outra\nTotal 1 2,00 99,50\nTotal 4 12,00 1.100,00\nTotal geral: 12,00 1.100,00",
    )
    assert [(o.codigo, o.valor, o.pagina) for o in movimento.operacoes] == [
        (5, Decimal("1000.50"), 1), (7, Decimal("99.50"), 2),
    ]
    assert movimento.avisos == []


def test_soma_diferente_do_total_geral():
    movimento = _ler("Operação 5\nTotal 1 1,00 10,00\nTotal geral: 1,00 11,00")
    assert [a.tipo for a in movimento.avisos] == ["soma diferente do total geral"]


def test_operacao_sem_total():
    movimento = _ler("Operação 5\nOperação 6\nTotal 1 1,00 10,00\nTotal geral: 1,00 10,00")
    assert [a.tipo for a in movimento.avisos] == ["operação sem total"]
    assert [o.codigo for o in movimento.operacoes] == [6]


def test_operacao_repetida():
    movimento = _ler("Operação 5\nTotal 1 1,00 10,00\nOperação 5\nTotal 1 1,00 10,00\nTotal geral: 2,00 20,00")
    tipos = [a.tipo for a in movimento.avisos if a.gravidade == Gravidade.ERRO]
    assert tipos == ["operação repetida", "soma diferente do total geral"]


def test_sem_total_geral():
    movimento = _ler("Operação 5\nTotal 1 1,00 10,00")
    assert [a.tipo for a in movimento.avisos] == ["total geral não encontrado"]


def test_texto_que_nao_e_movimento_estoque():
    with pytest.raises(ErroArquivo, match="Movimento estoque"):
        ler_texto_movimento(["Balancete\nqualquer coisa"], "outro.pdf")


def test_arquivo_que_nao_e_pdf(tmp_path):
    arquivo = tmp_path / "falso.pdf"
    arquivo.write_bytes(b"isto nao e um pdf")
    with pytest.raises(ErroArquivo):
        ler_pdf_movimento(arquivo)


# Relatório tirado por período ("De … Até …") em vez de "Data de Referência" (ajuste de 04/11/2026)

def _ler_com_periodo(linha_periodo):
    cabecalho = f"Movimento estoque\nQuebras: Operação\n{linha_periodo}\nOperação Quantidade Valor\n"
    return ler_texto_movimento([cabecalho + "Operação 5\nTotal 1 1,00 10,00\nTotal geral: 1,00 10,00"], "teste.pdf")


def test_periodo_de_um_mes_inteiro_vale_como_mes_de_referencia():
    movimento = _ler_com_periodo("De : 01/10/2026 00:00 Até : 31/10/2026 23:59")
    assert movimento.mes_referencia == MesReferencia(2026, 10)
    assert movimento.avisos == []


def test_periodo_de_fevereiro_ate_o_dia_28():
    movimento = _ler_com_periodo("De : 01/02/2027 00:00 Até : 28/02/2027 23:59")
    assert movimento.mes_referencia == MesReferencia(2027, 2)


@pytest.mark.parametrize("linha", [
    "De : 05/10/2026 00:00 Até : 31/10/2026 23:59",
    "De : 01/10/2026 00:00 Até : 30/10/2026 23:59",
    "De : 01/10/2026 00:00 Até : 30/11/2026 23:59",
])
def test_periodo_que_nao_e_um_mes_inteiro_avisa_e_fica_sem_mes(linha):
    movimento = _ler_com_periodo(linha)
    assert movimento.mes_referencia is None
    tipos = [a.tipo for a in movimento.avisos]
    assert tipos == ["período não é um mês inteiro", "mês não encontrado"]
    assert all(a.gravidade == Gravidade.ATENCAO for a in movimento.avisos)


def test_pdf_real_de_outubro_tirado_por_periodo():
    from testes.conciliacao_estoque.conftest import pasta_exemplos
    caminho = pasta_exemplos("conciliacao_estoque", "2026-10") / "Movimento_estoque_por_periodo.pdf"
    if not caminho.is_file():
        pytest.skip(f"Arquivo de exemplo {caminho} não encontrado")
    movimento = ler_pdf_movimento(caminho)
    assert movimento.mes_referencia == MesReferencia(2026, 10)
    assert len(movimento.operacoes) == 12
    assert movimento.total_geral == Decimal("115124.71")
    assert movimento.avisos == []
