"""REGISTRO dos leitores de extrato.

Para adicionar um modelo novo: criar o arquivo do leitor nesta pasta
(copiando _modelo_novo.py), importar a classe aqui e acrescentá-la na
lista LEITORES. Nada mais no programa precisa mudar.
"""

from .base import LeitorBase, LeituraError
from .bb_cdb import LeitorBBCDB
from .bb_conta_corrente import LeitorBBContaCorrente
from .bb_fundos import LeitorBBFundos
from .bb_poupanca import LeitorBBPoupanca
from .bb_rende_facil import LeitorBBRendeFacil
from .cef_conta_corrente import LeitorCEFContaCorrente
from .santander_conta_corrente import LeitorSantanderContaCorrente
from .santander_contamax import LeitorSantanderContaMax
from .sicoob_conta_corrente import LeitorSicoobContaCorrente

LEITORES: list[LeitorBase] = [
    LeitorBBContaCorrente(),
    LeitorBBCDB(),
    LeitorBBPoupanca(),
    LeitorBBRendeFacil(),
    LeitorBBFundos(),
    LeitorCEFContaCorrente(),
    LeitorSantanderContaCorrente(),
    LeitorSantanderContaMax(),
    LeitorSicoobContaCorrente(),
]

__all__ = ["LEITORES", "LeitorBase", "LeituraError"]
