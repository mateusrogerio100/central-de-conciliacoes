"""Testes da aba Import Contábil do módulo Clientes CMD (o programa original não tinha testes de interface)."""

from __future__ import annotations

from datetime import date

import pytest

from modulos.clientes_cmd import MODULO
from modulos.clientes_cmd.import_contabil import processamento
from testes.conftest import esperar, pasta_exemplos


@pytest.fixture
def criar_aba_import(criar_painel):
    """A aba Import Contábil, já selecionada na tela do módulo Clientes CMD."""

    def _criar():
        tela = criar_painel(MODULO)
        tela.mostrar_aba("Import Contábil")
        return tela.import_contabil

    return _criar


def test_mes_padrao_e_o_mes_anterior(criar_aba_import):
    painel = criar_aba_import()
    mes, ano = processamento.mes_anterior()
    assert painel.campo_mes.valor() == f"{mes:02d}/{ano}"


def test_mes_anterior_e_interpretar_mes():
    assert processamento.mes_anterior(date(2026, 1, 15)) == (12, 2025)
    assert processamento.mes_anterior(date(2026, 9, 25)) == (8, 2026)
    assert processamento.interpretar_mes("08/2026") == (8, 2026)
    assert processamento.interpretar_mes(" 8-2026 ") == (8, 2026)
    for invalido in ("13/2026", "08/26", "agosto", "", "08/2026/1"):
        assert processamento.interpretar_mes(invalido) is None


def test_botoes_dependem_do_que_foi_escolhido(criar_aba_import, tmp_path):
    exemplos = pasta_exemplos("clientes_cmd", "import_contabil")
    painel = criar_aba_import()
    assert not painel.botao.habilitado and not painel.botao_import.habilitado

    painel.cartao_relatorios.definir_caminhos(exemplos / "relatorio_fonte")
    assert painel.cartao_relatorios.texto_confirmacao == "8 relatório(s) encontrado(s)"
    assert painel.pasta_saida == exemplos                  # a pasta ACIMA da dos relatórios
    assert painel.botao.habilitado and not painel.botao_import.habilitado

    painel.campo_mes.definir("13/2026")                    # mês inválido desabilita
    assert not painel.botao.habilitado
    painel.campo_mes.definir("08/2026")
    painel.cartao_rel_geral.definir_caminhos(exemplos / "Rel_Geral_08_2026.xlsx")
    assert painel.botao_import.habilitado


def test_nao_grava_rel_geral_na_pasta_dos_relatorios(criar_aba_import, dialogos, tmp_path):
    exemplos = pasta_exemplos("clientes_cmd", "import_contabil")
    painel = criar_aba_import()
    painel.cartao_relatorios.definir_caminhos(exemplos / "relatorio_fonte")
    painel.cartao_saida.definir_caminhos(exemplos / "relatorio_fonte")

    painel.processar()

    assert dialogos.avisos and "diferente da pasta dos relatórios" in dialogos.avisos[0]
    assert not painel.ocupado


def test_dois_passos_pela_tela(criar_aba_import, dialogos, tmp_path):
    exemplos = pasta_exemplos("clientes_cmd", "import_contabil")
    painel = criar_aba_import()
    painel.campo_mes.definir("08/2026")
    painel.cartao_relatorios.definir_caminhos(exemplos / "relatorio_fonte")
    painel.cartao_saida.definir_caminhos(tmp_path)

    painel.processar()                                     # passo 1
    esperar(painel, lambda: not painel.ocupado)
    rel_geral = tmp_path / "Rel_Geral_08_2026.xlsx"
    assert rel_geral.is_file()
    assert painel.cartao_rel_geral.caminho == rel_geral    # o Rel_Geral gerado já fica escolhido
    assert painel.botao_import.habilitado
    assert painel.resultado.selo.cget("text") == "Rel_Geral 08/2026 gerado"

    painel.gerar_import()                                  # passo 2
    esperar(painel, lambda: not painel.ocupado)
    gerado = tmp_path / "Import_gerado_08_2026.txt"
    assert gerado.read_bytes() == (exemplos / "Import_gerado_08_2026.txt").read_bytes()
    assert painel.resultado.selo.cget("text") == "Import 08/2026 gerado"
    assert dialogos.perguntas == []


def test_import_existente_pergunta_antes_de_substituir(criar_aba_import, dialogos, tmp_path):
    exemplos = pasta_exemplos("clientes_cmd", "import_contabil")
    existente = tmp_path / "Import_gerado_08_2026.txt"
    existente.write_bytes(b"antigo")
    dialogos.resposta = False
    painel = criar_aba_import()
    painel.campo_mes.definir("08/2026")
    painel.cartao_rel_geral.definir_caminhos(exemplos / "Rel_Geral_08_2026.xlsx")
    painel.cartao_saida.definir_caminhos(tmp_path)

    painel.gerar_import()

    assert len(dialogos.perguntas) == 1
    assert existente.read_bytes() == b"antigo"
