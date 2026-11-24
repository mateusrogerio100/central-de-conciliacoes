"""Tela do módulo Estoque: aba "Conciliação" (telas/conciliacao.py) e a aba "Instruções de uso"
(INSTRUCOES_DE_USO.md, acrescentada pela Central)."""

from __future__ import annotations

from central.painel_abas import Aba, PainelComAbas
from modulos.conciliacao_estoque.telas.conciliacao import PainelEstoque

ABA_CONCILIACAO = "Conciliação"


class PainelModuloEstoque(PainelComAbas):
    def __init__(self, pai, info, pasta_configuracao=None):
        super().__init__(pai, info, [
            Aba(ABA_CONCILIACAO, lambda p: PainelEstoque(p, info, pasta_configuracao), info.descricao, "conciliacao"),
        ])
