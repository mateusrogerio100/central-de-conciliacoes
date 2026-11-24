"""Funções auxiliares: texto, dinheiro (Decimal) e mês de referência."""

from __future__ import annotations

import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal

from modulos.conciliacao_estoque import configuracao
from modulos.conciliacao_estoque.modelos import MesReferencia

CENTAVO = Decimal("0.01")
_PADRAO_NUMERO = re.compile(configuracao.PADRAO_NUMERO)
_PADRAO_MES_ABREVIADO = re.compile(r"^([a-z]{3})/(\d{4})$")
_PADRAO_MES_NUMERICO = re.compile(r"^(?:\d{1,2}/)?(\d{1,2})/(\d{4})$")


def normalizar_texto(valor) -> str:
    """Remove acentos, passa para minúsculas, junta espaços repetidos e tira espaços das pontas."""
    if valor is None:
        return ""
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.lower().split())


def texto_igual(valor, procurado: str) -> bool:
    """Compara um texto com um título, ignorando acentos, caixa e ':' final."""
    if not isinstance(valor, str):
        return False
    return normalizar_texto(valor).rstrip(":").strip() == normalizar_texto(procurado).rstrip(":").strip()


def texto_comeca_com(valor, prefixo: str) -> bool:
    if not isinstance(valor, str):
        return False
    return normalizar_texto(valor).startswith(normalizar_texto(prefixo))


def arredondar(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def eh_numero(texto: str) -> bool:
    return isinstance(texto, str) and bool(_PADRAO_NUMERO.match(texto.strip()))


def para_decimal(texto: str) -> Decimal | None:
    """Número no formato brasileiro ("1.234.567,89", "-523,1", "660", "59,7") -> Decimal com 2 casas.

    Devolve None se o texto não for um número nesse formato.
    """
    if not eh_numero(texto):
        return None
    limpo = texto.strip().replace(".", "").replace(",", ".")
    return arredondar(Decimal(limpo))


def formatar_valor(valor: Decimal | None) -> str:
    """Decimal("-41038.00") -> "-41.038,00" (para mensagens)."""
    if valor is None:
        return "-"
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def mes_de_texto(texto: str) -> MesReferencia | None:
    """"set/2026", "09/2026" ou "01/09/2026" -> MesReferencia(2026, 9). None se não reconhecer."""
    limpo = normalizar_texto(texto)
    encontrado = _PADRAO_MES_ABREVIADO.match(limpo)
    if encontrado:
        mes = configuracao.MESES_ABREVIADOS.get(encontrado.group(1))
        return MesReferencia(int(encontrado.group(2)), mes) if mes else None
    encontrado = _PADRAO_MES_NUMERICO.match(limpo)
    if encontrado and 1 <= int(encontrado.group(1)) <= 12:
        return MesReferencia(int(encontrado.group(2)), int(encontrado.group(1)))
    return None
