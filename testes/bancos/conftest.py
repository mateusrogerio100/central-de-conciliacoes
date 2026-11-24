"""Caminhos dos exemplos usados nos testes (exemplos/bancos/ da Central).

A pasta exemplos/ não vai para o git (tem dados reais). Se ela não existir,
os testes que dependem dela são pulados em vez de falhar.
"""

from pathlib import Path

import pytest

from testes.conftest import PASTA_EXEMPLOS as PASTA_EXEMPLOS_CENTRAL

PASTA_EXEMPLOS_BANCOS = PASTA_EXEMPLOS_CENTRAL / "bancos"
PASTA_EXEMPLOS = PASTA_EXEMPLOS_BANCOS / "2026-08"
PASTA_EXTRATOS = PASTA_EXEMPLOS / "extratos"
ARQUIVO_BALANCETE = PASTA_EXEMPLOS / "balancete_bancario.xlsx"


def caminho_exemplo(nome_arquivo: str) -> Path:
    """Acha um PDF do gabarito pelo nome, em qualquer subpasta de extratos/.

    Pula o teste se a pasta de exemplos ou o arquivo não existirem.
    """
    if not PASTA_EXTRATOS.is_dir():
        pytest.skip("pasta exemplos/bancos/2026-08/extratos não encontrada")
    encontrados = list(PASTA_EXTRATOS.rglob(nome_arquivo))
    if not encontrados:
        pytest.skip(f"arquivo de exemplo não encontrado: {nome_arquivo}")
    return encontrados[0]


# PDFs dos modelos novos criados pelo /novo-modelo (Etapa 10).
PASTA_MODELOS = PASTA_EXEMPLOS_BANCOS / "modelos"


def caminho_modelo(nome_arquivo: str) -> Path:
    """Acha um PDF de modelo novo pelo nome em exemplos/modelos/ (pula se faltar)."""
    if not PASTA_MODELOS.is_dir():
        pytest.skip("pasta exemplos/bancos/modelos não encontrada")
    encontrados = list(PASTA_MODELOS.rglob(nome_arquivo))
    if not encontrados:
        pytest.skip(f"arquivo de modelo não encontrado: {nome_arquivo}")
    return encontrados[0]
