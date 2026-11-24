"""Tela do módulo Conferência de NF: abas "Conferir lote" (telas/conferencia.py), "Gabarito de
contas" (telas/gabarito.py) e "Instruções de uso" (INSTRUCOES_DE_USO.md, acrescentada pela
Central)."""

from __future__ import annotations

from central.painel_abas import Aba, PainelComAbas
from modulos.conferencia_nf.telas.conferencia import PainelConferencia
from modulos.conferencia_nf.telas.gabarito import PainelGabarito

ABA_CONFERIR = "Conferir lote"
ABA_GABARITO = "Gabarito de contas"
DESCRICAO_GABARITO = ("Ensina ao programa as contas já usadas com cada fornecedor e produto, para "
                      "a conferência avisar quando uma conta foge do habitual ou do Padrão.")


class PainelConferenciaNF(PainelComAbas):
    def __init__(self, pai, info):
        super().__init__(pai, info, [
            Aba(ABA_CONFERIR, lambda p: PainelConferencia(p, info), info.descricao, "conferencia"),
            Aba(ABA_GABARITO, lambda p: PainelGabarito(p, info), DESCRICAO_GABARITO, "gabarito"),
        ])
