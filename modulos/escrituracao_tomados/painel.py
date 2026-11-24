"""Tela do módulo Serviços Tomados: aba "Gerar arquivo" (telas/gerar_arquivo.py) e a aba
"Instruções de uso" (INSTRUCOES_DE_USO.md, acrescentada pela Central)."""

from __future__ import annotations

from central.painel_abas import Aba, PainelComAbas
from modulos.escrituracao_tomados.telas.gerar_arquivo import PainelGerarArquivo

ABA_GERAR = "Gerar arquivo"


class PainelEscrituracaoTomados(PainelComAbas):
    def __init__(self, pai, info):
        super().__init__(pai, info, [
            Aba(ABA_GERAR, lambda p: PainelGerarArquivo(p, info), info.descricao, "gerar"),
        ])
