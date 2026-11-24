"""Julho/2026 a partir do Excel de junho, com o PDF do 0775 de julho (regra R4, aprovada pelo usuário em 16/11/2026).
Arquivos reais de exemplos/credito_estouro/ (fora do git); nenhum nome aqui.
"""

from decimal import Decimal as D

import pytest

from modulos.credito_estouro import conciliador as c
from modulos.credito_estouro.processamento import processar
from testes.credito_estouro.test_maio_real import PASTA, controle_inicial
from modulos.credito_estouro.controle import gravar_controle

pytestmark = pytest.mark.skipif(not (PASTA / "2026-07").exists(), reason="exemplos reais fora do git")


def _controle_junho(tmp_path):
    maio = controle_inicial("2026-05")
    controle_maio = gravar_controle(tmp_path / "maio.xlsx", maio.competencia, "", D("98853.35"), maio.itens)
    junho = processar(next((PASTA / "2026-06").glob("EVENTOS*")), PASTA / "2026-06" / "razao_06_credito_suplemento.xls",
                      controle_maio, tmp_path)
    return junho.caminho_planilha


def test_julho_com_o_0775(tmp_path):
    pdfs = [next((PASTA / "2026-07").glob("EVENTOS*")), next((PASTA / "2026-07").glob("EVENTO 775*"))]
    julho = processar(pdfs, PASTA / "2026-07" / "razao_07.xls", _controle_junho(tmp_path), tmp_path)
    assert julho.erro == ""
    conciliacao = julho.conciliacao
    devolucao = [x for x in conciliacao.conferencias_folha if "0775" in x.descricao][0]
    assert devolucao.razao == devolucao.folha == D("441.65")
    # o 0256 de junho dela foi cobrado no 0258 de julho e devolvido no 0775: sem pendência de cobrado a mais
    assert [(l.valor, l.situacao) for l in conciliacao.devolucoes] == [(D("441.65"), c.DEVOLUCAO_CONFERIR)]
    # julho tem R$ 0,21 de diferença no "Crédito complemento salário no mês 0726" do razão (para o usuário ver)
    assert conciliacao.diferenca_sem_explicacao == D("-0.21")


def test_julho_sem_o_pdf_do_0775_avisa(tmp_path):
    julho = processar([next((PASTA / "2026-07").glob("EVENTOS*"))], PASTA / "2026-07" / "razao_07.xls",
                      _controle_junho(tmp_path), tmp_path)
    assert any("nenhum PDF escolhido tem o evento 0775" in a.mensagem for a in julho.avisos)
