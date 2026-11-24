"""Tela do módulo Planilha HM: aba "Preenchimento" (telas/preenchimento.py) e a aba "Instruções de uso"
(INSTRUCOES_DE_USO.md, acrescentada pela Central)."""

from __future__ import annotations

from central.painel_abas import Aba, PainelComAbas
from modulos.planilha_hm.telas.preenchimento import PainelPlanilhaHM

ABA_PREENCHIMENTO = "Preenchimento"


class PainelModuloPlanilhaHM(PainelComAbas):
    def __init__(self, pai, info):
        super().__init__(pai, info, [
            Aba(ABA_PREENCHIMENTO, lambda p: PainelPlanilhaHM(p, info), info.descricao, "preenchimento"),
        ])
