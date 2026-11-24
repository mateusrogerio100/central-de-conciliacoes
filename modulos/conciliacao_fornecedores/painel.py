"""Tela do módulo Fornecedores: aba "Conciliação" (telas/conciliacao.py) e a aba "Instruções de uso"
(INSTRUCOES_DE_USO.md, acrescentada pela Central)."""

from __future__ import annotations

from central.painel_abas import Aba, PainelComAbas
from modulos.conciliacao_fornecedores.telas.conciliacao import PainelConciliacaoFornecedores

ABA_CONCILIACAO = "Conciliação"


class PainelModuloFornecedores(PainelComAbas):
    def __init__(self, pai, info):
        super().__init__(pai, info, [
            Aba(ABA_CONCILIACAO, lambda p: PainelConciliacaoFornecedores(p, info), info.descricao, "conciliacao"),
        ])
