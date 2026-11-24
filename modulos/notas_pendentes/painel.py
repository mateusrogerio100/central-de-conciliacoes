"""Tela do módulo Notas Pendentes: aba "E-mails" (telas/gerar.py) e a aba "Instruções de uso"
(INSTRUCOES_DE_USO.md, acrescentada pela Central). A aba do envio entra na Etapa Pendentes 3, com a API da TI.
"""

from __future__ import annotations

from central.painel_abas import Aba, PainelComAbas
from modulos.notas_pendentes.telas.gerar import PainelGerar

ABA_GERAR = "E-mails"


class PainelNotasPendentes(PainelComAbas):
    def __init__(self, pai, info):
        super().__init__(pai, info, [
            Aba(ABA_GERAR, lambda p: PainelGerar(p, info), info.descricao, "gerar"),
        ])
