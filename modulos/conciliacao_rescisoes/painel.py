"""Tela do módulo Rescisões: aba "Conciliação" (telas/conciliacao.py) e a aba "Instruções de uso"
(INSTRUCOES_DE_USO.md, acrescentada pela Central)."""

from __future__ import annotations

from central.painel_abas import Aba, PainelComAbas
from modulos.conciliacao_rescisoes.telas.conciliacao import PainelConciliacaoRescisoes

ABA_CONCILIACAO = "Conciliação"


class PainelModuloRescisoes(PainelComAbas):
    def __init__(self, pai, info):
        super().__init__(pai, info, [
            Aba(ABA_CONCILIACAO, lambda p: PainelConciliacaoRescisoes(p, info), info.descricao, "conciliacao"),
        ])
