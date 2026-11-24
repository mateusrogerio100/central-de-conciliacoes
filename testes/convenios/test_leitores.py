"""V1 — leitura do razão (3.1), da planilha de receitas (3.2) e das equivalências (3.3)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from modulos.convenios.leitor_equivalencias import ler_equivalencias, pasta_sugerida
from modulos.convenios.leitor_planilha import ler_planilha
from modulos.convenios.leitor_razao import ler_razao
from modulos.convenios.modelos import ErroLeitura
from testes.convenios.conftest import (
    CABECALHO_PAGINA, conta, escrever_planilha, escrever_razao, escrever_razao_texto, exemplos, lancamento,
    total,
)

C1 = ("40075", "4.01.05.01.0001", "Convênio Prefeitura Exemplo")
C2 = ("40064", "4.01.05.01.0003", "Convênios Ambulatorial Exemplo")


# ---------------------------------------------------------------------------
# Razão — arquivo real de set/2026
# ---------------------------------------------------------------------------

def test_v1_razao_real_de_setembro():
    razao = ler_razao(exemplos("2026-09") / "Razao Convenios 092026.xlsx")
    assert (razao.ano, razao.mes) == (2026, 9)
    assert [(c.codigo, len(c.lancamentos), c.total) for c in razao.contas] == [
        ("40075", 46, Decimal("303448.88")), ("40064", 84, Decimal("1892486.44")),
        ("40063", 19, Decimal("426975.59")), ("40419", 40, Decimal("512279.22"))]
    assert razao.total == Decimal("3135190.13")
    assert razao.avisos == []                         # cada conta fecha com a linha "Total"
    # o histórico que quebrou na virada da página não vira lançamento a mais
    assert len(razao.lancamentos) == 189


def test_v1_razao_real_de_agosto_no_xls_de_texto_do_tasy():
    razao = ler_razao(exemplos("2026-09") / "razao_08_2026.xls")
    assert (razao.ano, razao.mes) == (2026, 8)
    assert [(c.codigo, len(c.lancamentos), c.total) for c in razao.contas] == [
        ("40075", 41, Decimal("275595.61")), ("40076", 3, Decimal("1483.79")),
        ("40064", 95, Decimal("1933564.81")), ("40063", 12, Decimal("518088.39")),
        ("40419", 62, Decimal("350471.34")), ("40009", 11, Decimal("-1429.83")),
        ("40011", 4, Decimal("-3227.98"))]
    assert razao.total == Decimal("3074546.13") and razao.avisos == []


# ---------------------------------------------------------------------------
# Razão — casos montados
# ---------------------------------------------------------------------------

def test_v1_debito_diminui_e_saldo_anterior_nao_entra(tmp_path):
    razao = ler_razao(escrever_razao(
        tmp_path / "r.xlsx", conta(*C1), [None, None, "Saldo anterior ", *[None] * 11, 5000],
        lancamento("Faturamento Mês NF 1 Convênio A Set/2026 Protocolo 1", credito=100),
        lancamento("Estorno Convênio A", debito=30), total(*C1, credito=100, debito=30)))
    (c,) = razao.contas
    assert [(l.valor, l.data) for l in c.lancamentos] == [(Decimal("100.00"), date(2026, 9, 30)),
                                                          (Decimal("-30.00"), date(2026, 9, 30))]
    assert c.total == razao.total == Decimal("70.00") and razao.avisos == []


def test_v1_varias_paginas_e_historico_quebrado(tmp_path):
    razao = ler_razao(escrever_razao(
        tmp_path / "r.xlsx", conta(*C1),
        lancamento("Faturamento Mês NF 1 Convênio A Set/2026 Protocolo 1", credito=10),
        [None, "Impresso em: 27/10/2026 16:21:58", None, "Página: 1"],
        *CABECALHO_PAGINA,
        [None, None, "Set/2026  Protocolo 1 "],        # continuação do histórico: não é lançamento
        lancamento("Faturamento Mês NF 2 Convênio B Set/2026 Protocolo 2", credito=20),
        total(*C1, credito=30), conta(*C2),
        lancamento("Referente Convênio C NF. 3 Nota Fiscal Avulsa", credito=5), total(*C2, credito=5)))
    assert [(c.codigo, len(c.lancamentos)) for c in razao.contas] == [("40075", 2), ("40064", 1)]
    assert razao.total == Decimal("35.00") and razao.avisos == []


def test_v1_xls_de_texto_le_igual_ao_xlsx(tmp_path):
    linhas = (conta(*C1), [None, None, "Saldo anterior ", *[None] * 11, 5000],
              lancamento("Faturamento Mês NF 1 Convênio Á Set/2026 Protocolo 1", credito=1234.5),
              [None, "Impresso em: 27/10/2026 16:21:58", None, "Página: 1"], *CABECALHO_PAGINA,
              [None, None, "Set/2026  Protocolo 1 "],
              lancamento("Estorno Convênio Á", debito=30), total(*C1, credito=1234.5, debito=30))
    texto = ler_razao(escrever_razao_texto(tmp_path / "r.xls", *linhas))
    planilha = ler_razao(escrever_razao(tmp_path / "r.xlsx", *linhas))
    assert (texto.ano, texto.mes, texto.avisos) == (2026, 9, [])
    assert [(l.data, l.historico, l.lote, l.valor) for l in texto.lancamentos] == \
           [(l.data, l.historico, l.lote, l.valor) for l in planilha.lancamentos]
    assert texto.total == Decimal("1204.50")


def test_v1_soma_diferente_do_total_e_total_faltando_avisam(tmp_path):
    razao = ler_razao(escrever_razao(
        tmp_path / "r.xlsx", conta(*C1), lancamento("A", credito=10), total(*C1, credito=99),
        conta(*C2), lancamento("B", credito=1)))
    assert [a.erro for a in razao.avisos] == [True, True]
    assert "diferente da linha Total" in razao.avisos[0].mensagem
    assert "não encontrada" in razao.avisos[1].mensagem


def test_v1_periodo_faltando_avisa(tmp_path):
    razao = ler_razao(escrever_razao(tmp_path / "r.xlsx", conta(*C1), lancamento("A", credito=1),
                                     total(*C1, credito=1), cabecalho=[CABECALHO_PAGINA[3]]))
    assert razao.mes is None and razao.avisos[0].erro


def test_v1_arquivo_que_nao_e_razao_e_xls_antigo(tmp_path):
    with pytest.raises(ErroLeitura, match="não parece ser um razão"):
        ler_razao(escrever_razao(tmp_path / "r.xlsx", ["qualquer coisa"], cabecalho=[]))
    antigo = tmp_path / "antigo.xls"
    antigo.write_bytes(b"\xd0\xcf\x11\xe0" + b"0" * 100)
    with pytest.raises(ErroLeitura, match="salve como .xlsx"):
        ler_razao(antigo)
    with pytest.raises(ErroLeitura, match="não encontrado"):
        ler_razao(tmp_path / "nao_existe.xlsx")
    texto_qualquer = tmp_path / "qualquer.xls"
    texto_qualquer.write_text("sem tabulação nenhuma", encoding="utf-8")
    with pytest.raises(ErroLeitura, match="nem o texto exportado pelo Tasy"):
        ler_razao(texto_qualquer)


# ---------------------------------------------------------------------------
# Planilha de receitas
# ---------------------------------------------------------------------------

def test_v1_planilha_real_de_agosto():
    planilha = ler_planilha(exemplos("2026-09") / "RECEITAS DE CONVÊNIOS 082026.xlsx", 2026)
    assert planilha.aba == "Receita de Convênios 2026"
    assert (planilha.linha_titulos, planilha.linha_total, planilha.linha_saldo, planilha.linha_diferenca) == (
        4, 59, 61, 62)
    assert len(planilha.convenios) == 51 and planilha.colunas_mes[9] == 11 and planilha.coluna_acumulado == 15
    assert planilha.preenchidas_no_mes(9) == [] and len(planilha.preenchidas_no_mes(8)) == 23
    assert planilha.avisos == []


def test_v1_planilha_ficticia(tmp_path):
    caminho = escrever_planilha(tmp_path / "p.xlsx", [("Convênio A", {8: 10}), ("Convênio B ", {9: 5}),
                                                      ("convenio a", {})])
    planilha = ler_planilha(caminho, 2026)
    assert [(c.nome, c.linha) for c in planilha.convenios] == [("Convênio A", 5), ("Convênio B", 6),
                                                               ("convenio a", 7)]
    assert [c.nome for c in planilha.preenchidas_no_mes(9)] == ["Convênio B"]
    assert len(planilha.avisos) == 1 and "repete a linha 5" in planilha.avisos[0].mensagem


def test_v1_planilha_sem_a_aba_do_ano(tmp_path):
    caminho = escrever_planilha(tmp_path / "p.xlsx", [("Convênio A", {})], ano=2025, abas_antigas=())
    with pytest.raises(ErroLeitura, match="Receita de Convênios 2026"):
        ler_planilha(caminho, 2026)


# ---------------------------------------------------------------------------
# Equivalências
# ---------------------------------------------------------------------------

def _csv(pasta, *linhas):
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "equivalencias.csv").write_text("\n".join(["Nome_no_razao;Linha_da_planilha;Obs", *linhas]) + "\n",
                                             encoding="utf-8-sig")
    return pasta


def test_v1_equivalencias_da_pasta(tmp_path):
    pasta = _csv(tmp_path / "config", "Prefeitura X - Unidade 1;PM X;", "Prefeitura X - Unidade 2;PM X;somam",
                 ";Linha sem nome;", "")
    equivalencias = ler_equivalencias(pasta)
    assert not equivalencias.de_fabrica
    assert [(e.nome_no_razao, e.linha_da_planilha) for e in equivalencias.itens] == [
        ("Prefeitura X - Unidade 1", "PM X"), ("Prefeitura X - Unidade 2", "PM X")]
    assert len(equivalencias.avisos) == 1 and "pulada" in equivalencias.avisos[0].mensagem


def test_v1_sem_equivalencias_usa_o_modelo_vazio_com_aviso_vermelho(tmp_path):
    for pasta in (None, tmp_path):
        equivalencias = ler_equivalencias(pasta)
        assert equivalencias.de_fabrica and equivalencias.itens == []
        assert equivalencias.avisos[0].erro


def test_v1_equivalencias_coluna_faltando(tmp_path):
    (tmp_path / "equivalencias.csv").write_text("Nome;Linha\nA;B\n", encoding="utf-8")
    with pytest.raises(ErroLeitura, match="Nome_no_razao"):
        ler_equivalencias(tmp_path)


def test_v1_pasta_config_ao_lado_da_planilha(tmp_path):
    planilha = tmp_path / "RECEITAS.xlsx"
    assert pasta_sugerida(planilha) is None
    _csv(tmp_path / "config")
    assert pasta_sugerida(planilha) == tmp_path / "config"


def test_v1_equivalencias_reais_sao_lidas():
    equivalencias = ler_equivalencias(exemplos("config"))
    assert len(equivalencias.itens) >= 10 and equivalencias.avisos == []
