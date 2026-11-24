"""Regras da seção 4.3 conferidas em TODOS os módulos de modulos/ (os atuais e os que vierem).

- A lógica não importa a interface: só painel.py (e o que estiver em telas/) pode usar tkinter.
- Um módulo nunca importa outro módulo.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from testes.conftest import RAIZ

PASTA_MODULOS = RAIZ / "modulos"
BIBLIOTECAS_DE_TELA = {"tkinter", "customtkinter"}


def _pastas_de_modulos() -> list[Path]:
    return sorted(p for p in PASTA_MODULOS.iterdir() if (p / "__init__.py").is_file())


def _importacoes(arquivo: Path) -> set[str]:
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    nomes = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            nomes.update(a.name for a in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module and no.level == 0:
            nomes.add(no.module)
    return nomes


def _e_arquivo_de_tela(arquivo: Path, pasta_modulo: Path) -> bool:
    relativo = arquivo.relative_to(pasta_modulo)
    return relativo.name == "painel.py" or relativo.parts[0] == "telas"


@pytest.mark.parametrize("pasta", _pastas_de_modulos(), ids=lambda p: p.name)
def test_logica_nao_importa_interface(pasta):
    problemas = []
    for arquivo in pasta.rglob("*.py"):
        if _e_arquivo_de_tela(arquivo, pasta):
            continue
        for nome in _importacoes(arquivo):
            if nome.split(".")[0] in BIBLIOTECAS_DE_TELA:
                problemas.append(f"{arquivo.relative_to(RAIZ)} importa {nome}")
    assert problemas == []


@pytest.mark.parametrize("pasta", _pastas_de_modulos(), ids=lambda p: p.name)
def test_modulo_nao_importa_outro_modulo(pasta):
    problemas = []
    for arquivo in pasta.rglob("*.py"):
        for nome in _importacoes(arquivo):
            partes = nome.split(".")
            if partes[0] == "modulos" and len(partes) > 1 and partes[1] != pasta.name:
                problemas.append(f"{arquivo.relative_to(RAIZ)} importa {nome}")
    assert problemas == []
