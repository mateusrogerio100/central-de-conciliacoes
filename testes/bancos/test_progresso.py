"""Testes do andamento (progresso) da conciliação bancária — acréscimo da Central (regra 4.3.3)."""

from __future__ import annotations

import pytest

from modulos.bancos.processamento import ErroConciliacao, executar
from testes.bancos.conftest import ARQUIVO_BALANCETE, PASTA_EXTRATOS


def test_progresso_informa_os_passos_em_ordem(tmp_path):
    if not ARQUIVO_BALANCETE.is_file() or not PASTA_EXTRATOS.is_dir():
        pytest.skip("exemplos não encontrados")
    passos = []

    execucao = executar(ARQUIVO_BALANCETE, PASTA_EXTRATOS, tmp_path,
                        progresso=lambda texto, fracao: passos.append((texto, fracao)))

    textos = [t for t, _ in passos]
    fracoes = [f for _, f in passos]
    assert textos[0].startswith("Lendo o balancete:")
    assert textos[-1].startswith("\nPlanilha gerada:")
    assert fracoes == sorted(fracoes)
    assert fracoes[0] == 0.0 and fracoes[-1] == 1.0
    assert all(0.0 <= f <= 1.0 for f in fracoes)
    # uma linha de andamento por PDF, numerada "[n/total]"
    total = len(execucao.arquivos)
    linhas_pdf = [t for t in textos if t.startswith("  [")]
    assert len(linhas_pdf) == total
    assert linhas_pdf[0].startswith(f"  [1/{total}]") and linhas_pdf[-1].startswith(f"  [{total}/{total}]")


def test_sem_progresso_funciona_como_antes(tmp_path):
    with pytest.raises(ErroConciliacao, match="balancete não encontrado"):
        executar(tmp_path / "nao_existe.xlsx", tmp_path)


def test_balancete_so_com_cabecalho_para_com_aviso(tmp_path):
    # Caso real (06/11/2026): o Tasy exportou o balancete só com o cabeçalho, sem nenhuma conta
    balancete = tmp_path / "balancete.xls"
    balancete.write_text(
        "Fundação Exemplo\t\t\t\t\t\t\t\t\t\t\t\t\n"
        "Balancete\t\t\t\t\t\t\t\t\t\t\t\t\n"
        "\t\t\t\tMês Referência:\t\t\tout/2026\t\t\t\t\t\n"
        "\tCódigo\tClassificação\tDescrição\t\t\tSaldo Anterior\t\tDébitos\t\tCréditos\tSaldo Atual\t\n"
        "\tImpresso em: 06/11/2026 10:04:49\t\t\t\tPágina: 1\t\t\t\t\t\t\n", encoding="cp1252")
    (tmp_path / "extratos").mkdir()
    with pytest.raises(ErroConciliacao, match="não tem nenhuma conta de caixa e bancos"):
        executar(balancete, tmp_path / "extratos", tmp_path)
