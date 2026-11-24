"""Testes das abas do módulo Clientes CMD (Conciliação de clientes | Import Contábil)."""

from __future__ import annotations

import pytest

from central.componentes import Abas
from modulos.clientes_cmd import MODULO
from modulos.clientes_cmd.painel import ABA_CONCILIACAO, ABA_IMPORT, DESCRICOES


def test_abre_na_conciliacao(criar_painel):
    tela = criar_painel(MODULO)
    assert tela.aba_atual == ABA_CONCILIACAO
    assert tela.conciliacao.winfo_manager() == "pack" and not tela.import_contabil.winfo_manager()
    assert tela.cabecalho.rotulo_titulo.cget("text") == "Clientes CMD"


def test_trocar_de_aba_mantem_o_que_foi_escolhido(criar_painel, tmp_path):
    tela = criar_painel(MODULO)
    tela.conciliacao.cartao_saida.definir_caminhos(tmp_path, avisar=False)

    tela.abas.selecionar(ABA_IMPORT, avisar=True)                 # como um clique na aba
    assert tela.aba_atual == ABA_IMPORT
    assert tela.import_contabil.winfo_manager() == "pack" and not tela.conciliacao.winfo_manager()
    assert tela.cabecalho.rotulo_descricao.cget("text") == DESCRICOES[ABA_IMPORT]
    tela.import_contabil.campo_mes.definir("07/2026")

    tela.abas.selecionar(ABA_CONCILIACAO, avisar=True)
    assert tela.conciliacao.pasta_saida == tmp_path
    assert tela.cabecalho.rotulo_descricao.cget("text") == DESCRICOES[ABA_CONCILIACAO]
    tela.mostrar_aba(ABA_IMPORT)
    assert tela.import_contabil.campo_mes.valor() == "07/2026"


def test_ocupado_se_qualquer_aba_estiver_processando(criar_painel):
    tela = criar_painel(MODULO)
    assert not tela.ocupado
    tela.import_contabil.ocupado = True
    assert tela.ocupado
    tela.import_contabil.ocupado = False


def test_componente_abas(raiz_tk):
    trocas = []
    abas = Abas(raiz_tk, ["A", "B"], ao_trocar=trocas.append)
    assert abas.atual == "A"
    abas.selecionar("B", avisar=True)
    abas.selecionar("B", avisar=True)                            # a mesma aba não avisa de novo
    assert trocas == ["B"]
    with pytest.raises(ValueError):
        abas.selecionar("C")
    abas.destroy()
