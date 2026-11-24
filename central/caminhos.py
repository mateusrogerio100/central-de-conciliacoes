"""Onde ficam os arquivos internos do programa (fontes, ícones, ícone da janela).

Rodando pelo Python, a base é a raiz do projeto. Dentro do .exe (PyInstaller), os arquivos
incluídos com --add-data ficam numa pasta temporária (sys._MEIPASS), com os mesmos caminhos
relativos (ex.: --add-data "central\\fontes;central\\fontes").
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parent.parent


def pasta_base() -> Path:
    """Raiz dos arquivos internos: sys._MEIPASS no .exe, a raiz do projeto no Python."""
    return Path(getattr(sys, "_MEIPASS", RAIZ_PROJETO))


def caminho_interno(*partes: str) -> Path:
    """Caminho de um arquivo interno, ex.: caminho_interno("central", "fontes")."""
    return pasta_base().joinpath(*partes)
