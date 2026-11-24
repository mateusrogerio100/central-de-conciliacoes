"""Tela do módulo EFD Contribuições: aba "Geração do SPED" (telas/geracao.py) e a aba "Instruções de uso"
(INSTRUCOES_DE_USO.md, acrescentada pela Central)."""

from __future__ import annotations

from central.painel_abas import Aba, PainelComAbas
from modulos.efd_contribuicoes.telas.geracao import PainelGeracaoSped

ABA_GERACAO = "Geração do SPED"


class PainelModuloEfd(PainelComAbas):
    def __init__(self, pai, info):
        super().__init__(pai, info, [
            Aba(ABA_GERACAO, lambda p: PainelGeracaoSped(p, info), info.descricao, "geracao"),
        ])
