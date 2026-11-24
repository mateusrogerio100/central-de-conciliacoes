"""Configuração dos testes: localiza a pasta exemplos/subvencoes/ e os arquivos de cada mês.

Os exemplos têm dados reais e não vão para o git. Se a pasta não existir,
os testes que dependem dela são pulados (os demais continuam rodando).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest

from modulos.subvencoes.utilitarios import normalizar_texto
from testes.conftest import PASTA_EXEMPLOS as PASTA_EXEMPLOS_CENTRAL

PASTA_EXEMPLOS = PASTA_EXEMPLOS_CENTRAL / "subvencoes"
MESES_EXEMPLO = ["2026-07", "2026-08"]


@dataclass
class ArquivosDoMes:
    pasta: Path
    balancete: Path
    patrimonio: Path
    subvencoes: Path
    projetos: Path
    gabarito: Path


def _localizar(pasta: Path, trecho: str, extensao: str) -> Path:
    """Acha o arquivo pelo conteúdo do nome (normalizado), para os nomes exatos poderem variar."""
    candidatos = [
        p for p in pasta.iterdir()
        if p.suffix.lower() == extensao and trecho in normalizar_texto(p.name)
        and not p.name.startswith("~$")
    ]
    if len(candidatos) != 1:
        pytest.fail(f"Esperado 1 arquivo com '{trecho}' em {pasta}, encontrado(s): {candidatos}")
    return candidatos[0]


def arquivos_do_mes(mes: str) -> ArquivosDoMes:
    pasta = PASTA_EXEMPLOS / mes
    if not pasta.is_dir():
        pytest.skip(f"Pasta de exemplos {pasta} não encontrada")
    return ArquivosDoMes(
        pasta=pasta,
        balancete=_localizar(pasta, "balancete", ".xlsx"),
        patrimonio=_localizar(pasta, "patrimonio", ".xlsx"),
        subvencoes=_localizar(pasta, "subven", ".xlsx"),
        projetos=_localizar(pasta, "projetos", ".xlsx"),
        gabarito=_localizar(pasta, "gabarito", ".csv"),
    )


def ler_gabarito(caminho: Path) -> list[dict]:
    """Lê o CSV do gabarito (UTF-8, ';', decimal com ponto), com valores em Decimal."""
    with open(caminho, encoding="utf-8-sig", newline="") as arquivo:
        linhas = list(csv.DictReader(arquivo, delimiter=";"))
    for linha in linhas:
        linha["linha"] = int(linha["linha"])
        linha["conta_contabil"] = int(linha["conta_contabil"])
        linha["saldo_patrimonio"] = Decimal(linha["saldo_patrimonio"])
        linha["saldo_contabil"] = Decimal(linha["saldo_contabil"])
    return linhas


@pytest.fixture(params=MESES_EXEMPLO)
def mes_exemplo(request) -> str:
    return request.param


@pytest.fixture
def arquivos(mes_exemplo) -> ArquivosDoMes:
    return arquivos_do_mes(mes_exemplo)
