"""Comparação de textos e conversão de valores."""

from __future__ import annotations

import unicodedata
from decimal import Decimal, InvalidOperation

from modulos.planilha_hm import configuracao as cfg


def normalizar(texto) -> str:
    """Sem acento, minúsculo, espaços repetidos viram um só, sem pontas."""
    if texto is None:
        return ""
    sem_acento = "".join(c for c in unicodedata.normalize("NFD", str(texto)) if unicodedata.category(c) != "Mn")
    return " ".join(sem_acento.split()).lower()


def texto_igual(valor, procurado: str) -> bool:
    """Compara uma célula com um título, ignorando acento, maiúsculas e ':' no fim."""
    return isinstance(valor, str) and normalizar(valor).rstrip(":").strip() == normalizar(procurado).rstrip(":")


def para_decimal(valor) -> Decimal | None:
    """Número da célula -> Decimal com 2 casas; texto "1.234,56" ou "57,03-" também; vazio ou texto -> None."""
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float, Decimal)):
        return Decimal(repr(valor) if isinstance(valor, float) else str(valor)).quantize(Decimal("0.01"))
    texto = str(valor).strip()
    achado = cfg.RE_VALOR_TEXTO.match(texto)
    if achado:
        numero = Decimal(achado.group(2).replace(".", "").replace(",", "."))
        return (-numero if achado.group(1) or achado.group(3) else numero).quantize(Decimal("0.01"))
    try:
        return Decimal(texto.replace(".", "").replace(",", ".")).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def para_inteiro(valor) -> int | None:
    """2446, 2446.0 ou "2446" -> 2446; outro valor -> None."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float) and valor.is_integer():
        return int(valor)
    if isinstance(valor, str) and valor.strip().isdigit():
        return int(valor.strip())
    return None


def formatar_valor(valor: Decimal) -> str:
    """Decimal('-1234.5') -> '-1.234,50'."""
    texto = f"{abs(valor):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"-{texto}" if valor < 0 else texto
