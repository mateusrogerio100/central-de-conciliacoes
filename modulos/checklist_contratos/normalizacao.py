"""Normalização de textos (M2) e chave do responsável (P5)."""

from __future__ import annotations

import re
import unicodedata

_RE_SEPARADOR_PESSOAS = re.compile(r"\s+e\s+|\s*[,/;&]\s*")


def normalizar(texto) -> str:
    """M2: sem acento, minúsculo, espaços e quebras de linha repetidos viram um só, sem pontas."""
    if texto is None:
        return ""
    decomposto = unicodedata.normalize("NFD", str(texto))
    sem_acento = "".join(c for c in decomposto if unicodedata.category(c) != "Mn")
    return " ".join(sem_acento.split()).lower()


def pessoas_do_responsavel(responsavel: str) -> list[str]:
    """P5: "Ana/Bruno", "Ana e Bruno", "Ana, Bruno" -> ["ana", "bruno"] (normalizados)."""
    return [p.strip() for p in _RE_SEPARADOR_PESSOAS.split(normalizar(responsavel)) if p.strip()]


def chave_responsavel(responsavel: str) -> str:
    """P5: as pessoas normalizadas juntadas com "/" ("Ana e Bruno" = "Ana/Bruno" = "ana/bruno")."""
    return "/".join(pessoas_do_responsavel(responsavel))
