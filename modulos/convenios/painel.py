"""Tela do módulo Convênios: aba "Preenchimento" (telas/preenchimento.py) e a aba "Instruções de uso"
(INSTRUCOES_DE_USO.md, acrescentada pela Central)."""

from __future__ import annotations

from central.painel_abas import Aba, PainelComAbas
from modulos.convenios.telas.preenchimento import PainelConvenios

ABA_PREENCHIMENTO = "Preenchimento"


class PainelModuloConvenios(PainelComAbas):
    def __init__(self, pai, info):
        super().__init__(pai, info, [
            Aba(ABA_PREENCHIMENTO, lambda p: PainelConvenios(p, info), info.descricao, "preenchimento"),
        ])
