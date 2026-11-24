"""Testes do andamento (progresso) do processamento — acréscimo da Central (regra 4.3.3).

O parâmetro progresso só informa os passos: o resultado tem de ser o mesmo com ou sem ele.
"""

from __future__ import annotations

from modulos.subvencoes.modelos import MesReferencia, StatusArquivo
from modulos.subvencoes.processamento import processar
from testes.subvencoes.conftest import arquivos_do_mes


def _processar(pasta_saida, balancete=None, progresso=None):
    arquivos = arquivos_do_mes("2026-08")
    return processar(balancete or arquivos.balancete, arquivos.patrimonio,
                     [arquivos.subvencoes, arquivos.projetos], pasta_saida,
                     MesReferencia(2026, 8), progresso=progresso)


def test_progresso_informa_os_passos_em_ordem(tmp_path):
    passos = []
    _processar(tmp_path, progresso=lambda texto, fracao: passos.append((texto, fracao)))

    textos = [t for t, _ in passos]
    fracoes = [f for _, f in passos]
    assert textos[0] == "Lendo o balancete..."
    assert "Conciliando..." in textos
    assert textos[-1] == "Concluído."
    assert fracoes == sorted(fracoes)
    assert fracoes[0] == 0.0 and fracoes[-1] == 1.0
    assert all(0.0 <= f <= 1.0 for f in fracoes)
    # uma linha de andamento por planilha
    assert sum(t.startswith("Lendo a planilha") for t in textos) == 2


def test_resultado_igual_com_e_sem_progresso(tmp_path):
    sem = _processar(tmp_path / "sem")
    com = _processar(tmp_path / "com", progresso=lambda texto, fracao: None)

    assert [(a.gravidade, a.tipo, a.mensagem) for a in sem.avisos] == \
           [(a.gravidade, a.tipo, a.mensagem) for a in com.avisos]
    assert [p.status for p in sem.planilhas] == [p.status for p in com.planilhas]
    assert sorted(p.name for p in (tmp_path / "sem").iterdir()) == \
           sorted(p.name for p in (tmp_path / "com").iterdir())


def test_progresso_chega_ao_fim_mesmo_com_balancete_ilegivel(tmp_path):
    ruim = tmp_path / "Balancete.xlsx"
    ruim.write_text("não é uma planilha", encoding="utf-8")
    passos = []

    resultado = _processar(tmp_path / "saida", balancete=ruim,
                           progresso=lambda texto, fracao: passos.append((texto, fracao)))

    assert passos[-1] == ("Concluído.", 1.0)
    assert "Conciliando..." not in [t for t, _ in passos]
    assert all(p.status == StatusArquivo.NAO_PROCESSADO for p in resultado.planilhas)
