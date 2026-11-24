"""PlanilhaHM 1: leitura do Eventos (R1, R2) e do Movimento (total, conta de cada evento).

Testes obrigatórios 1, 2 e 3 da seção 8 da especificação (arquivos reais de exemplos\\planilha_hm\\) e casos
fictícios para cada regra.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime
from decimal import Decimal

import pytest

from modulos.planilha_hm.leitor_eventos import ler_eventos
from modulos.planilha_hm.leitor_movimento import COMO_NOME, COMO_NUMERO, contas_do_evento, ler_movimento
from modulos.planilha_hm.modelos import ContaContabil, ErroLeitura
from testes.planilha_hm.conftest import (
    TITULOS_MOVIMENTO,
    cabecalho_pagina,
    escrever_eventos,
    escrever_movimento,
    evento,
    exemplos,
    gabarito_senior,
    lancamento,
    medico,
    rodape,
    subtotal,
    total_evento,
    total_relatorio,
)

D = Decimal


def _md5(caminho) -> str:
    return hashlib.md5(caminho.read_bytes()).hexdigest()


def _linhas_senior(eventos) -> Counter:
    return Counter((s.evento, s.codigo, s.nome, s.valor) for s in eventos.subtotais)


def _movimento_real(mes: str):
    return next(exemplos(mes).glob("Movimento*.csv"))


# ---------------------------------------------------------------------------
# Testes obrigatórios com os arquivos reais
# ---------------------------------------------------------------------------

def test_1_eventos_setembro_xls_do_tasy():
    caminho = exemplos("2026-09") / "Eventos 09-2026.XLS"
    antes = _md5(caminho)
    eventos = ler_eventos(caminho)
    assert (eventos.ano, eventos.mes) == (2026, 9)
    assert len(eventos.eventos) == 136
    assert all(e.ok for e in eventos.eventos)                    # R2 sem erro
    assert len(eventos.subtotais) == 264
    assert _linhas_senior(eventos) == gabarito_senior("2026-09")
    assert eventos.total == D("5794120.73") == eventos.total_relatorio
    assert sum((s.valor for s in eventos.subtotais), D(0)) == D("5794120.73")
    assert eventos.avisos == []
    assert _md5(caminho) == antes


def test_1_desconto_vale_o_subtotal_positivo():
    """2446 HM Desconto Amesc, sinal (-): os médicos vêm negativos, mas o subtotal e o total são positivos."""
    eventos = ler_eventos(exemplos("2026-09") / "Eventos 09-2026.XLS")
    desconto = next(e for e in eventos.eventos if e.numero == 2446)
    assert desconto.sinal == "(-)"
    assert desconto.codigo_historico == "112"
    assert desconto.total > 0 and desconto.soma_subtotais == desconto.total


def test_2_eventos_agosto_plan1():
    caminho = exemplos("2026-08") / "Eventos 08-2026.xlsx"
    eventos = ler_eventos(caminho)
    assert (eventos.ano, eventos.mes) == (2026, 8)
    assert all(e.ok for e in eventos.eventos)
    assert len(eventos.subtotais) == 266
    assert _linhas_senior(eventos) == gabarito_senior("2026-08")
    assert eventos.total == D("5737714.53") == eventos.total_relatorio
    assert eventos.avisos == []


@pytest.mark.parametrize("mes, total, lote", [("2026-08", "5737714.53", "72520"), ("2026-09", "5794120.73", "72959")])
def test_3_total_do_movimento(mes, total, lote):
    caminho = _movimento_real(mes)
    antes = _md5(caminho)
    movimento = ler_movimento(caminho)
    assert movimento.total == D(total)
    assert (movimento.ano, movimento.mes) == (2026, int(mes[-2:]))
    assert movimento.lote == lote
    assert movimento.avisos == []
    assert _md5(caminho) == antes


def test_3_conta_dos_eventos_novos_de_setembro():
    movimento = ler_movimento(_movimento_real("2026-09"))
    contas, como = contas_do_evento(movimento, 3171)
    assert [c.classificacao for c in contas] == ["3.01.01.06.03.0002"] and como == COMO_NUMERO
    contas, como = contas_do_evento(movimento, 3172)
    assert [c.classificacao for c in contas] == ["3.01.01.06.28.0005"] and como == COMO_NUMERO


def test_3_movimento_bate_com_o_eventos_nos_dois_meses():
    for mes, eventos in (("2026-08", "Eventos 08-2026.xlsx"), ("2026-09", "Eventos 09-2026.XLS")):
        assert ler_movimento(_movimento_real(mes)).total == ler_eventos(exemplos(mes) / eventos).total


# ---------------------------------------------------------------------------
# Eventos fictícios (formato Plan1)
# ---------------------------------------------------------------------------

def test_subtotais_e_total(tmp_path):
    caminho = escrever_eventos(
        tmp_path / "eventos.xlsx",
        [*evento(1001, "HM Exemplo A"), medico(1, 100), medico(2, 50.5), subtotal(10, "Centro Alfa", 150.5),
         medico(3, 20), subtotal(20, "Centro Beta", 20), total_evento(1001, "HM Exemplo A", 170.5, historico=901)],
        [*evento(1002, "HM Desconto Exemplo", "(-)"), medico(4, -30), subtotal(10, "Centro Alfa", 30),
         total_evento(1002, "HM Desconto Exemplo", 30, historico=0)],
        [total_relatorio(200.5)])
    eventos = ler_eventos(caminho)
    assert [(s.evento, s.codigo, s.nome, s.valor) for s in eventos.subtotais] == [
        (1001, "10", "Centro Alfa", D("150.50")), (1001, "20", "Centro Beta", D("20.00")),
        (1002, "10", "Centro Alfa", D("30.00"))]
    assert [e.codigo_historico for e in eventos.eventos] == ["901", "0"]
    assert eventos.total == eventos.total_relatorio == D("200.50")
    assert eventos.avisos == []


def test_cabecalho_e_rodape_de_pagina_nao_interrompem_o_evento(tmp_path):
    """R1: a virada de página entre os médicos e o subtotal não fecha o bloco."""
    caminho = escrever_eventos(
        tmp_path / "eventos.xlsx",
        [*evento(1001, "HM Exemplo A"), medico(1, 100), rodape(), *cabecalho_pagina(2), medico(2, 50),
         subtotal(10, "Centro Alfa", 150), rodape(), *cabecalho_pagina(3),
         total_evento(1001, "HM Exemplo A", 150)],
        [total_relatorio(150)])
    eventos = ler_eventos(caminho)
    assert eventos.eventos[0].ok
    assert [(s.codigo, s.valor) for s in eventos.subtotais] == [("10", D("150.00"))]
    assert eventos.avisos == []


def test_r2_soma_diferente_do_total_fica_fora(tmp_path):
    caminho = escrever_eventos(
        tmp_path / "eventos.xlsx",
        [*evento(1001, "HM Exemplo A"), medico(1, 100), subtotal(10, "Centro Alfa", 100),
         total_evento(1001, "HM Exemplo A", 120)],
        [*evento(1002, "HM Exemplo B"), medico(2, 40), subtotal(20, "Centro Beta", 40),
         total_evento(1002, "HM Exemplo B", 40)],
        [total_relatorio(160)])
    eventos = ler_eventos(caminho)
    errado = eventos.eventos[0]
    assert not errado.ok and "100,00" in errado.erro and "120,00" in errado.erro
    assert [e.numero for e in eventos.eventos_ok] == [1002]
    assert [s.evento for s in eventos.subtotais] == [1002]          # o evento com erro não vai para a planilha


def test_r2_evento_sem_total_fica_fora(tmp_path):
    caminho = escrever_eventos(
        tmp_path / "eventos.xlsx",
        [*evento(1001, "HM Exemplo A"), medico(1, 100), subtotal(10, "Centro Alfa", 100)],
        [*evento(1002, "HM Exemplo B"), medico(2, 40), subtotal(20, "Centro Beta", 40),
         total_evento(1002, "HM Exemplo B", 40)])
    eventos = ler_eventos(caminho)
    assert "Total Evento" in eventos.eventos[0].erro
    assert eventos.eventos[1].ok
    # sem a linha do total geral: só um aviso de atenção
    assert [(a.erro, "total geral" in a.mensagem) for a in eventos.avisos] == [(False, True)]


def test_total_do_relatorio_diferente_avisa(tmp_path):
    caminho = escrever_eventos(
        tmp_path / "eventos.xlsx",
        [*evento(1001, "HM Exemplo A"), medico(1, 100), subtotal(10, "Centro Alfa", 100),
         total_evento(1001, "HM Exemplo A", 100)],
        [total_relatorio(999)])
    avisos = ler_eventos(caminho).avisos
    assert len(avisos) == 1 and avisos[0].erro and "999,00" in avisos[0].mensagem


def test_competencia_em_texto(tmp_path):
    caminho = escrever_eventos(
        tmp_path / "eventos.xlsx",
        [*evento(1001, "HM Exemplo A"), medico(1, 10), subtotal(10, "Centro Alfa", 10),
         total_evento(1001, "HM Exemplo A", 10)],
        cabecalho=[[None, "Conferência Lançamentos Contábeis"], ["Competência:", "10/2026", "a", "10/2026"]])
    eventos = ler_eventos(caminho)
    assert (eventos.ano, eventos.mes) == (2026, 10)


def test_competencia_de_mais_de_um_mes_e_erro(tmp_path):
    caminho = escrever_eventos(
        tmp_path / "eventos.xlsx",
        [*evento(1001, "HM Exemplo A"), medico(1, 10), subtotal(10, "Centro Alfa", 10),
         total_evento(1001, "HM Exemplo A", 10), total_relatorio(10)],
        cabecalho=[[None, "Conferência Lançamentos Contábeis"],
                   ["Competência:", datetime(2026, 9, 1), "a", datetime(2026, 10, 1)]])
    eventos = ler_eventos(caminho)
    assert eventos.mes == 9
    assert any(a.erro and "mais de um mês" in a.mensagem for a in eventos.avisos)


def test_linha_estranha_aparece_nos_avisos(tmp_path):
    caminho = escrever_eventos(
        tmp_path / "eventos.xlsx",
        [*evento(1001, "HM Exemplo A"), ["texto solto que ninguém espera"], medico(1, 10),
         subtotal(10, "Centro Alfa", 10), total_evento(1001, "HM Exemplo A", 10), total_relatorio(10)])
    avisos = ler_eventos(caminho).avisos
    assert len(avisos) == 1 and "texto solto" in avisos[0].mensagem


def test_arquivo_que_nao_e_o_eventos(tmp_path):
    caminho = escrever_eventos(tmp_path / "outro.xlsx", [["Qualquer coisa", 1, 2]], cabecalho=[])
    with pytest.raises(ErroLeitura, match="não parece ser o relatório Eventos"):
        ler_eventos(caminho)


def test_arquivo_que_nao_e_planilha(tmp_path):
    caminho = tmp_path / "Eventos.XLS"
    caminho.write_bytes(b"isto nao e uma planilha")
    with pytest.raises(ErroLeitura, match=r"\.XLS"):
        ler_eventos(caminho)


def test_arquivo_inexistente(tmp_path):
    with pytest.raises(ErroLeitura, match="não encontrado"):
        ler_eventos(tmp_path / "nao_existe.XLS")


# ---------------------------------------------------------------------------
# Movimento fictício
# ---------------------------------------------------------------------------

def _movimento_ficticio(tmp_path, bom=False):
    return escrever_movimento(
        tmp_path / "movimento.csv",
        lancamento("1.000,00", "HM Exemplo A (Evento 1001)", debito="30001", conta_debito="Honorários Exemplo PJ",
                   classificacao_debito="3.01.01.06.99.0001"),
        lancamento("1.000,00", "HM Exemplo A (Evento 1001)", credito="200001"),
        lancamento("250,50", "Evento 1002 - HM Exemplo B", debito="30002", conta_debito="Plantões Exemplo PJ",
                   classificacao_debito="3.01.01.06.99.0002"),
        lancamento("80,00", "HM Exemplo Sem Numero", debito="30003", conta_debito="Fixos Exemplo PF",
                   classificacao_debito="3.01.01.06.99.0003"),
        lancamento("57,03", "Desconto Exemplo", debito="21001", credito="21002", conta_debito="Medico Exemplo",
                   classificacao_debito="2.01.03.01.0001"),
        bom=bom)


@pytest.mark.parametrize("bom", [False, True])
def test_movimento_total_mes_e_lote(tmp_path, bom):
    movimento = ler_movimento(_movimento_ficticio(tmp_path, bom))
    # só as linhas com débito (inclui a com débito e crédito); a de crédito puro fica fora
    assert movimento.total == D("1000.00") + D("250.50") + D("80.00") + D("57.03")
    assert (movimento.ano, movimento.mes, movimento.lote) == (2026, 9, "70001")
    assert movimento.avisos == []


def test_evento_do_historico(tmp_path):
    movimento = ler_movimento(_movimento_ficticio(tmp_path))
    assert [l.evento for l in movimento.linhas] == [1001, 1001, 1002, None, None]
    assert movimento.linhas[0].codigo_historico == "900"


def test_conta_do_evento_pelo_numero_so_no_debito(tmp_path):
    movimento = ler_movimento(_movimento_ficticio(tmp_path))
    assert contas_do_evento(movimento, 1001) == (
        [ContaContabil("30001", "Honorários Exemplo PJ", "3.01.01.06.99.0001")], COMO_NUMERO)
    assert contas_do_evento(movimento, 1002)[0][0].classificacao == "3.01.01.06.99.0002"


def test_conta_do_evento_pelo_nome(tmp_path):
    """R5, item 2: sem o número no histórico, procura pelo nome do evento."""
    movimento = ler_movimento(_movimento_ficticio(tmp_path))
    contas, como = contas_do_evento(movimento, 1003, "HM Exemplo Sem Número")
    assert [c.classificacao for c in contas] == ["3.01.01.06.99.0003"] and como == COMO_NOME


def test_conta_do_evento_nao_achada(tmp_path):
    movimento = ler_movimento(_movimento_ficticio(tmp_path))
    assert contas_do_evento(movimento, 9999, "HM Inexistente") == ([], "")


def test_movimento_de_dois_meses_e_erro(tmp_path):
    caminho = escrever_movimento(tmp_path / "movimento.csv",
                                 lancamento("10,00", "x", debito="1"), lancamento("10,00", "x", debito="1"),
                                 lancamento("10,00", "x", debito="1", data="01/10/2026"))
    movimento = ler_movimento(caminho)
    assert movimento.mes == 9
    assert [a.erro for a in movimento.avisos] == [True] and "10/2026" in movimento.avisos[0].mensagem


def test_valor_invalido_aparece_nos_avisos(tmp_path):
    caminho = escrever_movimento(tmp_path / "movimento.csv",
                                 lancamento("10,00", "x", debito="1"), lancamento("abc", "x", debito="1"))
    movimento = ler_movimento(caminho)
    assert movimento.total == D("10.00")
    assert len(movimento.avisos) == 1 and "linha 3" in movimento.avisos[0].origem


def test_movimento_sem_os_titulos(tmp_path):
    caminho = escrever_movimento(tmp_path / "outro.csv", ["1", "2"], titulos=["Coluna A", "Coluna B"])
    with pytest.raises(ErroLeitura, match="não parece ser o Movimento"):
        ler_movimento(caminho)


def test_movimento_com_um_historico_so_nao_e_aceito(tmp_path):
    titulos = [t for i, t in enumerate(TITULOS_MOVIMENTO) if not (t == "Histórico" and i == 11)]
    caminho = escrever_movimento(tmp_path / "movimento.csv", ["x"] * len(titulos), titulos=titulos)
    with pytest.raises(ErroLeitura, match="duas colunas"):
        ler_movimento(caminho)
