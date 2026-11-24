"""Tela do módulo Conciliação Bancária: aba "Conciliação" (telas/conciliacao.py) e a aba
"Instruções de uso" (INSTRUCOES_DE_USO.md, acrescentada pela Central)."""

from __future__ import annotations

from central.painel_abas import Aba, PainelComAbas
from modulos.bancos.telas.conciliacao import PainelBancos

ABA_CONCILIACAO = "Conciliação"


class PainelModuloBancos(PainelComAbas):
    def __init__(self, pai, info):
        super().__init__(pai, info, [
            Aba(ABA_CONCILIACAO, lambda p: PainelBancos(p, info), info.descricao, "conciliacao"),
        ])
