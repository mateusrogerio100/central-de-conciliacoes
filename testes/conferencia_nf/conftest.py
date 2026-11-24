"""Apoio dos testes do módulo Conferência de NF.

Ler os PDFs de um lote leva uns 20 segundos: cada lote é lido uma vez só por execução e cada
teste recebe uma cópia (a conferência marca os PDFs usados, e um teste não pode sujar o outro).
"""

from __future__ import annotations

import copy

from modulos.conferencia_nf import leitor_pdfs
from testes.conftest import pasta_exemplos

_LEITURAS: dict[str, tuple] = {}


def ler_pdfs_do_lote(lote: str):
    """(notas, falhas, frações do progresso) de exemplos\\conferencia_nf\\<lote>, em cópia nova.

    Pula o teste se a pasta não existir.
    """
    pasta = pasta_exemplos("conferencia_nf", lote)
    if lote not in _LEITURAS:
        fracoes = []
        notas, falhas = leitor_pdfs.ler_pasta(pasta, lambda _texto, fracao: fracoes.append(fracao))
        _LEITURAS[lote] = notas, falhas, fracoes
    return copy.deepcopy(_LEITURAS[lote])
