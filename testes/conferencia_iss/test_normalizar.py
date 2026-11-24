"""Testes das regras de normalização (seção 3 da especificação)."""

from decimal import Decimal

import pytest

from modulos.conferencia_iss.modelos import (
    ItemResultado,
    LinhaPrefeitura,
    NotaTasy,
    situacao_escriturada_varias_vezes,
)
from modulos.conferencia_iss.normalizar import (
    eh_pessoa_fisica,
    formatar_documento,
    normalizar_documento,
    normalizar_numero,
    numero_ajustado,
    valor_prefeitura,
    valor_tasy,
)


# ---------------------------------------------------------------------
# Documento
# ---------------------------------------------------------------------
@pytest.mark.parametrize(
    "entrada, esperado",
    [
        ("00.111.222/0001-33", "00111222000133"),
        ("123.456.789-09", "12345678909"),
        ("55666777000188", "55666777000188"),
        (" 08.123.456/0002-47 ", "08123456000247"),
        ("", ""),
        (None, ""),
    ],
)
def test_normalizar_documento(entrada, esperado):
    assert normalizar_documento(entrada) == esperado


# ---------------------------------------------------------------------
# Número da nota
# ---------------------------------------------------------------------
@pytest.mark.parametrize(
    "entrada, esperado",
    [
        ("000123", "123"),
        ("123", "123"),
        ("8905486", "8905486"),
        (" 41 ", "41"),
        ("NF-00629", "629"),
        ("0", "0"),
        ("000", "0"),
        ("", ""),
        (None, ""),
    ],
)
def test_normalizar_numero(entrada, esperado):
    assert normalizar_numero(entrada) == esperado


@pytest.mark.parametrize(
    "entrada, esperado",
    [
        ("2026000000122", "122"),      # caso do gabarito 8.1
        ("2025000000001", "1"),
        ("20260100", "100"),
        ("2026000000100", "100"),
        ("122", None),                 # número comum
        ("2026", None),                # só o ano
        ("20261", None),               # sem zeros entre ano e número
        ("1999000000122", None),       # não começa com 20
        ("20260000", None),            # só zeros depois do ano
        ("", None),
        (None, None),
    ],
)
def test_numero_ajustado(entrada, esperado):
    assert numero_ajustado(entrada) == esperado


# ---------------------------------------------------------------------
# Valores
# ---------------------------------------------------------------------
@pytest.mark.parametrize(
    "entrada, esperado",
    [
        ("1234,56", Decimal("1234.56")),
        ("6927,15", Decimal("6927.15")),
        ("667", Decimal("667")),
        ("0,01", Decimal("0.01")),
        (" 280,00 ", Decimal("280.00")),
        ("-10,50", Decimal("-10.50")),
    ],
)
def test_valor_tasy(entrada, esperado):
    resultado = valor_tasy(entrada)
    assert isinstance(resultado, Decimal)
    assert resultado == esperado


@pytest.mark.parametrize("entrada", ["", "   ", None])
def test_valor_tasy_vazio(entrada):
    assert valor_tasy(entrada) is None


@pytest.mark.parametrize("entrada", ["abc", "12,34,56", "1.234,56", "R$ 10,00"])
def test_valor_tasy_invalido(entrada):
    with pytest.raises(ValueError):
        valor_tasy(entrada)


@pytest.mark.parametrize(
    "entrada, esperado",
    [
        ("1.234,56", Decimal("1234.56")),
        ("1.495.749,39", Decimal("1495749.39")),
        ("667,00", Decimal("667.00")),
        ("9.699,71", Decimal("9699.71")),
        ("280,00", Decimal("280.00")),
    ],
)
def test_valor_prefeitura(entrada, esperado):
    resultado = valor_prefeitura(entrada)
    assert isinstance(resultado, Decimal)
    assert resultado == esperado


@pytest.mark.parametrize("entrada", ["", "\xa0", " \xa0 ", None])
def test_valor_prefeitura_vazio(entrada):
    """Caso do gabarito 8.1 (nº 8905486): Valor do Doc. vazio (&nbsp;)."""
    assert valor_prefeitura(entrada) is None


@pytest.mark.parametrize("entrada", ["abc", "1,234,56", "R$ 1.000,00"])
def test_valor_prefeitura_invalido(entrada):
    with pytest.raises(ValueError):
        valor_prefeitura(entrada)


def test_mesmo_valor_nas_duas_fontes_e_igual():
    """7.590,00 da prefeitura tem que ser exatamente igual a 7590,00 do Tasy."""
    assert valor_tasy("7590,00") == valor_prefeitura("7.590,00")
    assert valor_tasy("7590,00") - valor_prefeitura("7.123,21") == Decimal("466.79")


# ---------------------------------------------------------------------
# Pessoa física
# ---------------------------------------------------------------------
@pytest.mark.parametrize(
    "entrada, esperado",
    [
        ("Entrada por pessoa física", True),
        (" Entrada por pessoa física ", True),
        ("ENTRADA POR PESSOA FÍSICA", True),
        ("Entrada", False),
        ("", False),
        (None, False),
    ],
)
def test_eh_pessoa_fisica(entrada, esperado):
    assert eh_pessoa_fisica(entrada) is esperado


# ---------------------------------------------------------------------
# Formatação de documento para o relatório
# ---------------------------------------------------------------------
@pytest.mark.parametrize(
    "entrada, esperado",
    [
        ("00111222000133", "00.111.222/0001-33"),
        ("00.111.222/0001-33", "00.111.222/0001-33"),
        ("12345678909", "123.456.789-09"),
        ("12345", "12345"),
        ("", ""),
    ],
)
def test_formatar_documento(entrada, esperado):
    assert formatar_documento(entrada) == esperado


# ---------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------
def _nota(valor="100,00"):
    return NotaTasy(
        arquivo="teste.csv", linha=2, nota_fiscal="1", numero="1", numero_ajustado=None,
        emitente="Fornecedor Teste", codigo_emitente="11222333000181",
        documento="11222333000181", tipo_nota="Entrada", eh_pessoa_fisica=False,
        valor_mercadoria=valor_tasy(valor),
    )


def _linha(valor="100,00"):
    return LinhaPrefeitura(
        linha=1, documento="11222333000181", documento_original="11.222.333/0001-81",
        prestador="Fornecedor Teste", numero_doc="1", numero="1",
        valor_doc=valor_prefeitura(valor),
    )


def test_item_diferenca_zero_confere():
    item = ItemResultado("Conferida", _nota("100,00"), _linha("100,00"))
    assert item.diferenca == Decimal("0")
    assert item.valor_confere is True


def test_item_diferenca_um_centavo_nao_confere():
    item = ItemResultado("Divergência de valor", _nota("100,01"), _linha("100,00"))
    assert item.diferenca == Decimal("0.01")
    assert item.valor_confere is False


def test_item_sem_um_dos_lados_nao_tem_diferenca():
    assert ItemResultado("x", nota_tasy=_nota()).diferenca is None
    assert ItemResultado("x", linha_prefeitura=_linha()).valor_confere is None
    assert ItemResultado("x", _nota(), _linha("")).diferenca is None


def test_nota_tasy_nao_tem_observacao():
    """LGPD: a Observação do Tasy não existe no modelo, então não chega ao relatório."""
    campos = {nome.casefold() for nome in NotaTasy.__dataclass_fields__}
    assert not any("observ" in nome for nome in campos)


def test_situacao_escriturada_varias_vezes():
    assert situacao_escriturada_varias_vezes(2) == "Notas escrituradas 2 vezes na prefeitura"


def test_documentos_casos_reais():
    """Os CNPJs reais que estavam nos testes de normalização do Conciliações AMES (fora do git)."""
    from testes.conferencia_iss.pastas_exemplos import caso_real

    for entrada, esperado in caso_real("normalizar_documento"):
        assert normalizar_documento(entrada) == esperado
    for entrada, esperado in caso_real("formatar_documento"):
        assert formatar_documento(entrada) == esperado
