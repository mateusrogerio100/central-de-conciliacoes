"""Testes da estrutura do projeto: arquivos da base e proteção dos dados sensíveis."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from central import VERSAO, tema
from testes.conftest import RAIZ


def test_versao_definida():
    partes = VERSAO.split(".")
    assert len(partes) == 3 and all(p.isdigit() for p in partes)


def test_fontes_ibm_plex_na_pasta_da_central():
    nomes = {p.name for p in tema._pasta_fontes().glob("*.ttf")}
    assert nomes == {
        "IBMPlexSans-Regular.ttf",
        "IBMPlexSans-Bold.ttf",
        "IBMPlexMono-Regular.ttf",
        "IBMPlexMono-Bold.ttf",
    }


def test_icone_do_programa_existe():
    assert (RAIZ / "recursos" / "icone.ico").is_file()


@pytest.mark.parametrize(
    "caminho",
    [
        "exemplos/subvencoes/2026-08/Balancete_att.xlsx",
        "origem/AUTOMACAO_BANCOS/interface.py",
        "saida/qualquer.xlsx",
        "planilha.xlsx",
        "antiga.xls",
        "gabarito_2026-08.csv",
        "extrato.pdf",
        "Import_gerado_08_2026.txt",
        ".venv/Scripts/python.exe",
        "build/x",
        "dist/CentralConciliacoes.exe",
        "CentralConciliacoes.spec",
    ],
)
def test_dados_sensiveis_ficam_fora_do_git(caminho):
    if shutil.which("git") is None:
        pytest.skip("git não encontrado")
    resultado = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", caminho], cwd=RAIZ, capture_output=True
    )
    assert resultado.returncode == 0, f"{caminho} NÃO está protegido pelo .gitignore"


def test_requirements_nao_e_ignorado():
    if shutil.which("git") is None:
        pytest.skip("git não encontrado")
    resultado = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", "requirements.txt"], cwd=RAIZ, capture_output=True
    )
    assert resultado.returncode == 1
