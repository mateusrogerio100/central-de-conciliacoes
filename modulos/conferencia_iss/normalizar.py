"""
Regras de normalização (seção 3 da especificação).

Deixa documentos, números de nota e valores no mesmo "formato" nas duas fontes
(Tasy e prefeitura), para que a comparação seja justa.
Valores inválidos levantam ValueError: quem lê o arquivo transforma isso em aviso.
"""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation

TIPO_NOTA_PESSOA_FISICA = "Entrada por pessoa física"

_REGEX_NUMERO_AJUSTADO = re.compile(r"^(20\d\d)0+(\d+)$")
_REGEX_DECIMAL = re.compile(r"^-?\d+(\.\d+)?$")


def so_digitos(texto: str | None) -> str:
    """Mantém só os dígitos: "00.111.222/0001-33" → "00111222000133"."""
    if not texto:
        return ""
    return "".join(c for c in texto if c.isdigit())


def normalizar_documento(texto: str | None) -> str:
    """CNPJ/CPF só com dígitos (zeros à esquerda fazem parte do documento)."""
    return so_digitos(texto)


def normalizar_numero(texto: str | None) -> str:
    """Número da nota: só dígitos e sem zeros à esquerda ("000123" → "123")."""
    digitos = so_digitos(texto)
    if not digitos:
        return ""
    return digitos.lstrip("0") or "0"


def numero_ajustado(texto: str | None) -> str | None:
    """
    Número "ano + zeros + número" do Tasy → só o número final.

    "2026000000122" → "122". Devolve None se o número não tem esse formato.
    """
    numero = normalizar_numero(texto)
    encontrado = _REGEX_NUMERO_AJUSTADO.match(numero)
    if not encontrado:
        return None
    final = encontrado.group(2).lstrip("0")
    return final or None


def _para_decimal(texto: str, original: str) -> Decimal:
    if not _REGEX_DECIMAL.match(texto):
        raise ValueError(f"Valor inválido: {original!r}")
    try:
        return Decimal(texto)
    except InvalidOperation as erro:
        raise ValueError(f"Valor inválido: {original!r}") from erro


def _limpar(texto: str | None) -> str:
    """Tira espaços comuns e o &nbsp; (\\xa0) que a prefeitura usa para vazio."""
    if texto is None:
        return ""
    return texto.replace("\xa0", " ").strip()


def valor_tasy(texto: str | None) -> Decimal | None:
    """
    Valor do Tasy: "1234,56" (vírgula decimal, sem milhar) → Decimal("1234.56").

    Vazio → None. Formato inesperado → ValueError.
    """
    limpo = _limpar(texto)
    if not limpo:
        return None
    return _para_decimal(limpo.replace(",", "."), texto)


def valor_prefeitura(texto: str | None) -> Decimal | None:
    """
    Valor da prefeitura: "1.234,56" (ponto de milhar, vírgula decimal) → Decimal("1234.56").

    Vazio ou &nbsp; → None. Formato inesperado → ValueError.
    """
    limpo = _limpar(texto)
    if not limpo:
        return None
    return _para_decimal(limpo.replace(".", "").replace(",", "."), texto)


def eh_pessoa_fisica(tipo_nota: str | None) -> bool:
    """Nota de pessoa física do Tasy (o código do emitente não é CPF)."""
    return _limpar(tipo_nota).casefold() == TIPO_NOTA_PESSOA_FISICA.casefold()


def formatar_documento(documento: str | None) -> str:
    """
    Documento para exibição no relatório:
    14 dígitos → 00.000.000/0000-00; 11 dígitos → 000.000.000-00; outro → como está.
    """
    d = so_digitos(documento)
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    return documento or ""


# Palavras que não identificam o prestador (aparecem no nome de muitos deles)
PALAVRAS_GENERICAS = frozenset({
    "LTDA", "LIMITADA", "ME", "EPP", "EIRELI", "MEI", "SS", "SA", "S", "A", "CIA",
    "DE", "DA", "DO", "DAS", "DOS", "E", "EM", "PARA",
    "SERVICOS", "SERVICO", "MEDICOS", "MEDICO", "MEDICA", "MEDICAS", "MEDICINA",
    "CLINICA", "CLINICAS", "SAUDE", "SOCIEDADE", "SIMPLES", "INDIVIDUAL", "UNIPESSOAL",
})


def palavras_do_nome(nome: str | None) -> set[str]:
    """
    Palavras que identificam o prestador, para comparar nomes escritos de jeitos diferentes.

    Sem acento, em maiúsculas, sem pontuação, sem números soltos e sem as palavras
    genéricas. Letras soltas seguidas viram uma palavra só ("K&W" → "KW", "R T V" → "RTV").
    "VERANO SERVIÇOS MÉDICOS LTDA" → {"VERANO"}.
    """
    texto = unicodedata.normalize("NFKD", nome or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c)).upper()
    palavras: list[str] = []
    letras: list[str] = []
    for parte in re.findall(r"[A-Z0-9]+", texto):
        if len(parte) == 1 and parte.isalpha():
            letras.append(parte)
            continue
        if letras:
            palavras.append("".join(letras))
            letras = []
        palavras.append(parte)
    if letras:
        palavras.append("".join(letras))
    return {p for p in palavras if p not in PALAVRAS_GENERICAS and not p.isdigit()}


def nomes_parecidos(nome_a: str | None, nome_b: str | None) -> bool:
    """Os dois nomes têm pelo menos uma palavra que identifica o prestador em comum."""
    return bool(palavras_do_nome(nome_a) & palavras_do_nome(nome_b))
