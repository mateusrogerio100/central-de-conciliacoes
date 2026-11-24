"""
Onde ficam os arquivos reais de exemplo da Conferência ISS (exemplos\\conferencia_iss\\, fora do git).

Copiado do Conciliações AMES (tests/pastas_exemplos.py) com a pasta trocada e sem as pastas das
outras aplicações. Os testes que usam estes arquivos são pulados se a pasta não existir.

caso_real() lê os CNPJs e nomes de prestadores citados no gabarito, que ficam em
exemplos\\conferencia_iss\\casos_reais.json (fora do git): nos testes só ficam números e valores.
"""

import json
from pathlib import Path

import pytest

from testes.conftest import PASTA_EXEMPLOS as PASTA_EXEMPLOS_CENTRAL

PASTA_EXEMPLOS = PASTA_EXEMPLOS_CENTRAL / "conferencia_iss"
ARQUIVO_CASOS_REAIS = PASTA_EXEMPLOS / "casos_reais.json"


def _primeira_que_existe(*nomes: str) -> Path:
    for nome in nomes:
        if (PASTA_EXEMPLOS / nome).exists():
            return PASTA_EXEMPLOS / nome
    return PASTA_EXEMPLOS / nomes[0]


# Cidade Beta, competência 09/2026 (gabarito seção 8.1). A pasta já se chamou "2026-09".
PASTA_RB = _primeira_que_existe("2026-09_RB", "2026-09")
# Cidade Epsilon, competência 09/2026
PASTA_SJ = PASTA_EXEMPLOS / "Exemplos_SJ"
# Cidade Gama e Cidade Alfa, competência 09/2026
PASTA_CP = PASTA_EXEMPLOS / "Exemplos_Cidade_Gama"
PASTA_FR = PASTA_EXEMPLOS / "Exemplos_Cidade_Alfa"


def caso_real(*chaves: str):
    """O dado real guardado em casos_reais.json (pula o teste se o arquivo não existir)."""
    if not ARQUIVO_CASOS_REAIS.exists():
        pytest.skip(f"{ARQUIVO_CASOS_REAIS} não encontrado (dados reais ficam fora do git)")
    dado = json.loads(ARQUIVO_CASOS_REAIS.read_text(encoding="utf-8"))
    for chave in chaves:
        dado = dado[chave]
    return dado
