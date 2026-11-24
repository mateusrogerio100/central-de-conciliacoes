"""Testes da tela de módulo com abas (central/painel_abas.py): cada aba só é montada quando aberta."""

from __future__ import annotations

import customtkinter as ctk

from central.modulo_base import InfoModulo
from central.painel_abas import ABA_INSTRUCOES, Aba, PainelComAbas


class AbaDeTeste(ctk.CTkFrame):
    def __init__(self, pai, nome, montadas):
        super().__init__(pai, fg_color="transparent")
        montadas.append(nome)
        self.escolha = ""


def _painel(raiz_tk, montadas, aba_inicial=None):
    info = InfoModulo(chave="subvencoes", nome="Teste", descricao="Teste.", contexto="Teste", icone="banco",
                      criar_painel=lambda pai: None)
    abas = [Aba(nome, lambda p, n=nome: AbaDeTeste(p, n, montadas), f"Frase {nome}", f"aba_{nome.lower()}")
            for nome in ("RB", "SJ", "AV")]
    return PainelComAbas(raiz_tk, info, abas, aba_inicial=aba_inicial)


def test_so_a_primeira_aba_e_montada_ao_abrir(raiz_tk):
    montadas = []
    painel = _painel(raiz_tk, montadas)
    try:
        assert montadas == ["RB"] and set(painel.paineis) == {"RB"}
        assert painel.instrucoes is None
    finally:
        painel.destroy()


def test_aba_inicial_escolhida_e_a_unica_montada(raiz_tk):
    montadas = []
    painel = _painel(raiz_tk, montadas, aba_inicial="AV")
    try:
        assert montadas == ["AV"] and painel.aba_atual == "AV"
        assert painel.cabecalho.rotulo_descricao.cget("text") == "Frase AV"
    finally:
        painel.destroy()


def test_aba_inicial_desconhecida_vira_a_primeira(raiz_tk):
    montadas = []
    painel = _painel(raiz_tk, montadas, aba_inicial="XX")
    try:
        assert montadas == ["RB"] and painel.aba_atual == "RB"
    finally:
        painel.destroy()


def test_aba_e_montada_uma_vez_e_guarda_o_estado(raiz_tk):
    montadas = []
    painel = _painel(raiz_tk, montadas)
    try:
        painel.abas.selecionar("SJ", avisar=True)
        painel.aba_sj.escolha = "nfe SJ.xls"
        painel.abas.selecionar("RB", avisar=True)
        painel.abas.selecionar("SJ", avisar=True)
        assert montadas == ["RB", "SJ"]
        assert painel.aba_sj.escolha == "nfe SJ.xls"
        assert painel.cabecalho.rotulo_descricao.cget("text") == "Frase SJ"
        assert not painel.paineis["RB"].winfo_manager()
    finally:
        painel.destroy()


def test_atributo_de_aba_ainda_nao_aberta_a_monta(raiz_tk):
    montadas = []
    painel = _painel(raiz_tk, montadas)
    try:
        aba = painel.aba_av                        # montada agora, sem ser mostrada
        assert montadas == ["RB", "AV"] and painel.aba_atual == "RB"
        assert painel.aba_av is aba and not aba.winfo_manager()
    finally:
        painel.destroy()


def test_instrucoes_montadas_so_quando_abertas(raiz_tk):
    painel = _painel(raiz_tk, [])
    try:
        painel.abas.selecionar(ABA_INSTRUCOES, avisar=True)
        assert painel.instrucoes is not None and painel.paineis[ABA_INSTRUCOES] is painel.instrucoes
    finally:
        painel.destroy()


def test_atributo_desconhecido_continua_dando_erro(raiz_tk):
    painel = _painel(raiz_tk, [])
    try:
        try:
            painel.nao_existe
        except AttributeError:
            pass
        else:
            raise AssertionError("deveria dar AttributeError")
    finally:
        painel.destroy()
