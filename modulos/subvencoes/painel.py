"""Tela do módulo Subvenções e Projetos: aba "Preenchimento" (telas/preenchimento.py) e a aba
"Instruções de uso" (INSTRUCOES_DE_USO.md, acrescentada pela Central)."""

from __future__ import annotations

from central.painel_abas import Aba, PainelComAbas
from modulos.subvencoes.telas.preenchimento import PainelSubvencoes

ABA_PREENCHIMENTO = "Preenchimento"


class PainelModuloSubvencoes(PainelComAbas):
    def __init__(self, pai, info):
        super().__init__(pai, info, [
            Aba(ABA_PREENCHIMENTO, lambda p: PainelSubvencoes(p, info), info.descricao, "preenchimento"),
        ])
