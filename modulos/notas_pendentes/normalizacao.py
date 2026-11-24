"""Normalização de textos para comparar (copiada do checklist_contratos: um módulo nunca importa outro)."""

from __future__ import annotations

import unicodedata


def normalizar(texto) -> str:
    """Sem acento, minúsculo, espaços e quebras de linha repetidos viram um só, sem pontas."""
    if texto is None:
        return ""
    decomposto = unicodedata.normalize("NFD", str(texto))
    sem_acento = "".join(c for c in decomposto if unicodedata.category(c) != "Mn")
    return " ".join(sem_acento.split()).lower()
