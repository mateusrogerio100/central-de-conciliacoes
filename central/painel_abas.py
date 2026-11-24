"""Tela de módulo com abas: cabeçalho do módulo, a linha de abas e o conteúdo da aba escolhida.

Todo módulo que usa esta tela ganha, no fim, a aba "Instruções de uso", que mostra o
INSTRUCOES_DE_USO.md da pasta do módulo (central/instrucoes.py). Um módulo novo só precisa
escrever esse arquivo.

Cada aba só é montada na primeira vez em que é aberta (um módulo com várias abas, como a
Conferência ISS com as cinco prefeituras, abre tão rápido quanto um de uma aba só) e depois guarda o
próprio estado (arquivos escolhidos, resultado) ao trocar de uma para a outra. O atributo de uma aba
(ex.: painel.import_contabil) também a monta, se ela ainda não foi aberta.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import customtkinter as ctk

from central import tema
from central.componentes import Abas, CabecalhoModulo
from central.instrucoes import PainelInstrucoes
from central.modulo_base import InfoModulo

ABA_INSTRUCOES = "Instruções de uso"
DESCRICAO_INSTRUCOES = "Como usar este módulo, passo a passo, e o que significa cada resultado."


@dataclass
class Aba:
    nome: str                           # texto da aba
    criar: Callable[[Any], Any]         # recebe o frame pai e devolve o painel da aba
    descricao: str                      # frase do cabeçalho enquanto a aba está aberta
    atributo: str = ""                  # nome do atributo para acessar o painel (ex.: "conciliacao")


class PainelComAbas(ctk.CTkFrame):
    def __init__(self, pai, info: InfoModulo, abas: list[Aba], aba_inicial: str | None = None):
        """aba_inicial: a aba mostrada ao abrir (ex.: a última cidade usada); padrão = a primeira."""
        super().__init__(pai, fg_color="transparent")
        self.info = info
        self.descricoes = {aba.nome: aba.descricao for aba in abas}
        self.descricoes[ABA_INSTRUCOES] = DESCRICAO_INSTRUCOES

        self.cabecalho = CabecalhoModulo(self, info.contexto, info.nome, abas[0].descricao)
        self.cabecalho.pack(fill="x", pady=(0, tema.ESPACO_PEQUENO))
        self.abas = Abas(self, [aba.nome for aba in abas] + [ABA_INSTRUCOES], ao_trocar=self.mostrar_aba)
        self.abas.pack(anchor="w", pady=(0, tema.ESPACO_ENTRE_BLOCOS))

        self._abas = {aba.nome: aba for aba in abas}
        self._aba_do_atributo = {aba.atributo: aba.nome for aba in abas if aba.atributo}
        self.paineis: dict[str, Any] = {}          # só as abas já montadas
        self.instrucoes: PainelInstrucoes | None = None
        self.mostrar_aba(aba_inicial if aba_inicial in self._abas else abas[0].nome)

    def __getattr__(self, nome: str):
        # chamado só para atributos que não existem: o de uma aba ainda não montada a monta agora
        abas = self.__dict__.get("_aba_do_atributo", {})
        if nome in abas:
            return self.painel_da_aba(abas[nome])
        raise AttributeError(nome)

    def painel_da_aba(self, nome: str):
        """O painel da aba, montado agora se ainda não foi (sem mostrá-lo)."""
        if nome not in self.paineis:
            if nome == ABA_INSTRUCOES:
                self.instrucoes = PainelInstrucoes(self, self.info.chave)
                painel = self.instrucoes
            else:
                aba = self._abas[nome]
                painel = aba.criar(self)
                if aba.atributo:
                    setattr(self, aba.atributo, painel)
            self.paineis[nome] = painel
        return self.paineis[nome]

    def mostrar_aba(self, nome: str) -> None:
        self.painel_da_aba(nome)
        self.abas.selecionar(nome)
        for aba, painel in self.paineis.items():
            if aba == nome:
                painel.pack(fill="both", expand=True)
            else:
                painel.pack_forget()
        self.cabecalho.rotulo_descricao.configure(text=self.descricoes[nome])

    @property
    def aba_atual(self) -> str:
        return self.abas.atual

    @property
    def ocupado(self) -> bool:
        """Alguma aba processando (a janela pergunta antes de fechar)."""
        return any(getattr(p, "ocupado", False) for p in self.paineis.values())
