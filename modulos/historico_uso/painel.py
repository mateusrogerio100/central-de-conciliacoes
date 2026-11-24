"""Tela do módulo Histórico de uso: aba "Histórico" (telas/historico.py) e a aba "Instruções de uso"
(INSTRUCOES_DE_USO.md, acrescentada pela Central)."""

from __future__ import annotations

from central.painel_abas import Aba, PainelComAbas
from modulos.historico_uso.telas.historico import PainelHistorico

ABA_HISTORICO = "Histórico"


class PainelModuloHistorico(PainelComAbas):
    def __init__(self, pai, info):
        super().__init__(pai, info, [
            Aba(ABA_HISTORICO, lambda p: PainelHistorico(p, info), info.descricao, "historico"),
        ])
