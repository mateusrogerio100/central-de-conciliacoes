"""Funções de apoio do módulo Crédito Estouro.

`dinheiro` e `reais` são COPIADAS de modulos\\conciliacao_rescisoes\\fornecedores\\leitores.py (um módulo nunca
importa outro).
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

_CENTAVO = Decimal("0.01")
_REGEX_DATA = re.compile(r"^(\d{2})/(\d{2})/(\d{4})")


def juntar_espacos(texto: object) -> str:
    return re.sub(r"\s+", " ", str(texto)).strip()


def sem_acento(texto: str) -> str:
    """Sem acento e em minúsculas: para comparar títulos e nomes."""
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().casefold()


def dinheiro(valor: object) -> Decimal:
    """Número da planilha ou texto "1.234,56" → Decimal com 2 casas. Outro → ValueError."""
    if isinstance(valor, bool) or valor is None:
        raise ValueError(f"valor inválido: {valor!r}")
    if isinstance(valor, (int, float, Decimal)):
        return Decimal(str(valor)).quantize(_CENTAVO)
    if isinstance(valor, str):
        texto = valor.strip().replace(".", "").replace(",", ".")
        try:
            return Decimal(texto).quantize(_CENTAVO)
        except InvalidOperation as erro:
            raise ValueError(f"valor inválido: {valor!r}") from erro
    raise ValueError(f"valor inválido: {valor!r}")


def reais(numero: Decimal | None) -> str:
    """Decimal → "1.234,56"."""
    if numero is None:
        return "—"
    texto = f"{numero:,.2f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


def data_br(valor: object) -> date | None:
    """Data da planilha ou texto "31/05/2026" (o resto da célula é ignorado) → date; outro → None."""
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        achado = _REGEX_DATA.match(valor.strip())
        if achado:
            dia, mes, ano = (int(p) for p in achado.groups())
            try:
                return date(ano, mes, dia)
            except ValueError:
                return None
    return None


def eh_pdf(bruto: bytes) -> bool:
    return bruto.startswith(b"%PDF-")


def paginas_do_pdf(caminho) -> list[str]:
    """Texto de cada página do PDF (separado para os testes poderem usar texto sintético)."""
    import pdfplumber

    with pdfplumber.open(caminho) as pdf:
        return [pagina.extract_text() or "" for pagina in pdf.pages]
