"""Tela do módulo Imprimir PDFs: aba "Imprimir" (telas/imprimir.py) e a aba "Instruções de uso"
(INSTRUCOES_DE_USO.md, acrescentada pela Central)."""

from __future__ import annotations

from central.painel_abas import Aba, PainelComAbas
from modulos.imprimir_pdfs.telas.imprimir import PainelImprimirPdfs

ABA_IMPRIMIR = "Imprimir"


class PainelModuloImprimirPdfs(PainelComAbas):
    def __init__(self, pai, info):
        super().__init__(pai, info, [
            Aba(ABA_IMPRIMIR, lambda p: PainelImprimirPdfs(p, info), info.descricao, "imprimir"),
        ])
