"""Comparação de textos (regra C4) e conversão de valores."""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation

from modulos.convenios import configuracao as cfg

_RE_PONTUACAO = re.compile(r"[^a-z0-9]+")


def normalizar(texto) -> str:
    """Sem acento, minúsculo, espaços repetidos viram um só, sem pontas."""
    if texto is None:
        return ""
    sem_acento = "".join(c for c in unicodedata.normalize("NFD", str(texto)) if unicodedata.category(c) != "Mn")
    return " ".join(sem_acento.split()).lower()


def chave_nome(texto) -> str:
    """C4: sem acento, maiúsculas, pontuação e "de/da/do" ("PM de Cidade Teta " = "PM Cidade Teta")."""
    palavras = _RE_PONTUACAO.sub(" ", normalizar(texto)).split()
    return " ".join(p for p in palavras if p not in cfg.PALAVRAS_IGNORADAS)


def texto_igual(valor, procurado: str) -> bool:
    """Compara uma célula com um título, ignorando acento, maiúsculas e ':' no fim."""
    return isinstance(valor, str) and normalizar(valor).rstrip(":").strip() == normalizar(procurado)


def formatar_valor(valor: Decimal) -> str:
    """Decimal('-1234.5') -> '-1.234,50'."""
    texto = f"{abs(valor):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"-{texto}" if valor < 0 else texto


def para_decimal(valor) -> Decimal | None:
    """Número da célula -> Decimal com 2 casas; texto "1.234,56" também; vazio -> None."""
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float, Decimal)):
        return Decimal(repr(valor) if isinstance(valor, float) else str(valor)).quantize(Decimal("0.01"))
    texto = str(valor).strip()
    if not texto:
        return None
    try:
        return Decimal(texto.replace(".", "").replace(",", ".")).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None
