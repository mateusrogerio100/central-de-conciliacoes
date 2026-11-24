"""Tela do módulo Crédito Estouro: aba "Conciliação" (telas/conciliacao.py) e a aba "Instruções de uso"
(INSTRUCOES_DE_USO.md, acrescentada pela Central)."""

from __future__ import annotations

from central.painel_abas import Aba, PainelComAbas
from modulos.credito_estouro.telas.conciliacao import PainelCreditoEstouro

ABA_CONCILIACAO = "Conciliação"


class PainelModuloCreditoEstouro(PainelComAbas):
    def __init__(self, pai, info):
        super().__init__(pai, info, [
            Aba(ABA_CONCILIACAO, lambda p: PainelCreditoEstouro(p, info), info.descricao, "conciliacao"),
        ])
