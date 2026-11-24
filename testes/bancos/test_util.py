"""Testes das funções de apoio (valores, contas, texto de PDF)."""

from decimal import Decimal

import pytest

from modulos.bancos.modelos import SaldoExtraido
from modulos.bancos.util import (
    converter_valor,
    extrair_paginas_pdf,
    extrair_paginas_rapido,
    extrair_texto_pdf,
    formatar_valor,
    normalizar_conta,
    numero_do_mes,
    parece_escaneado,
    valor_de_float,
)
from testes.bancos.conftest import PASTA_EXTRATOS, PASTA_MODELOS, caminho_exemplo


# ---------------------------------------------------------------------------
# Valores no formato brasileiro (todos os formatos citados na especificação)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("texto, esperado", [
    ("1.117.461,33", "1117461.33"),     # ponto de milhar
    ("8893,49", "8893.49"),             # sem ponto de milhar (tabela do CDB)
    ("539.300,00 D", "-539300.00"),     # D = negativo
    ("0,00 C", "0.00"),                 # C = positivo
    ("223.374,00 C", "223374.00"),
    ("93,56 C", "93.56"),
    ("4.136,14C", "4136.14"),           # C colado no número
    ("50,00C*", "50.00"),               # asterisco final (Sicoob)
    ("R$ 228,18", "228.18"),            # prefixo R$
    ("R$228,18", "228.18"),
    ("4.927.281,60", "4927281.60"),
    ("0,00", "0.00"),
    ("-1.234,56", "-1234.56"),          # sinal de menos
    ("  310,72  ", "310.72"),           # espaços nas pontas
    ("12,00 d", "-12.00"),              # d minúsculo
])
def test_converter_valor(texto, esperado):
    valor = converter_valor(texto)
    assert isinstance(valor, Decimal)
    assert valor == Decimal(esperado)


def test_zero_devedor_nao_vira_menos_zero():
    assert str(converter_valor("0,00 D")) == "0.00"


@pytest.mark.parametrize("texto", [
    "",
    "abc",
    "1.234",          # sem centavos
    "12,3",           # só uma casa decimal
    "1,234.56",       # formato americano
    "1.23,45",        # ponto de milhar no lugar errado
    "C",
])
def test_converter_valor_invalido_levanta_erro(texto):
    with pytest.raises(ValueError):
        converter_valor(texto)


@pytest.mark.parametrize("valor, esperado", [
    ("1117461.33", "1.117.461,33"),
    ("0", "0,00"),
    ("-539300", "-539.300,00"),
    ("8893.49", "8.893,49"),
])
def test_formatar_valor(valor, esperado):
    assert formatar_valor(Decimal(valor)) == esperado


# ---------------------------------------------------------------------------
# Valores vindos do Excel (float) -> Decimal
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("numero, esperado", [
    (640.44000000000005, "640.44"),
    (2728903.05, "2728903.05"),
    (200.0, "200.00"),
    (0, "0.00"),
    (-539300.0, "-539300.00"),
])
def test_valor_de_float(numero, esperado):
    valor = valor_de_float(numero)
    assert isinstance(valor, Decimal)
    assert str(valor) == esperado


# ---------------------------------------------------------------------------
# Normalização de número de conta
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("texto, esperado", [
    ("000568630703-9", "5686307039"),   # CEF no extrato (zeros à esquerda)
    ("568630703-9", "5686307039"),      # CEF no balancete
    ("2.004.834-3", "20048343"),        # Sicoob no extrato
    ("2004834-3", "20048343"),          # Sicoob no balancete
    ("400759-x", "400759X"),            # dígito X minúsculo
    ("400759-X", "400759X"),
    ("8036-5", "80365"),
    ("1179-7", "11797"),
    ("1144-4", "11444"),
    ("534-7", "5347"),
    ("400500-7", "4005007"),
    ("5749-5", "57495"),
    ("3634-5", "36345"),                # Santander no balancete (curto)
    ("130036345", "130036345"),         # Santander no extrato
    ("13000305-3", "130003053"),
    ("0000", "0"),
])
def test_normalizar_conta(texto, esperado):
    assert normalizar_conta(texto) == esperado


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------

def test_saldo_disponivel_e_total_menos_bloqueado():
    saldo = SaldoExtraido(
        banco="SICOOB", tipo="CC", conta="20048343",
        conta_original="2.004.834-3",
        saldo_total=Decimal("4186.14"), saldo_bloqueado=Decimal("50.00"),
    )
    assert saldo.saldo_disponivel == Decimal("4136.14")


# ---------------------------------------------------------------------------
# Detecção de PDF escaneado
# ---------------------------------------------------------------------------

def test_escaneado_sem_texto():
    assert parece_escaneado(["", "  \n ", ""])


def test_escaneado_sem_paginas():
    assert parece_escaneado([])


def test_nao_escaneado_com_texto():
    assert not parece_escaneado(["Extrato de conta corrente " * 5])


def test_escaneado_com_pouco_texto_por_pagina():
    # 10 páginas com uma palavrinha cada (ex.: só o número da página)
    assert parece_escaneado(["pág. 1"] * 10)


def test_pdf_real_escaneado():
    arquivo = caminho_exemplo("Aplicações ok.pdf")
    assert parece_escaneado(extrair_paginas_pdf(arquivo))


def test_pdf_real_com_texto():
    arquivo = caminho_exemplo("1179 7.pdf")
    paginas = extrair_paginas_pdf(arquivo)
    assert not parece_escaneado(paginas)
    texto = extrair_texto_pdf(arquivo)
    assert "Extrato de conta corrente" in texto


@pytest.mark.parametrize("nome, esperado", [
    ("Agosto", 8), ("AGOSTO", 8), ("março", 3), ("MARCO", 3), ("dezembro", 12), ("agost", None),
])
def test_numero_do_mes(nome, esperado):
    assert numero_do_mes(nome) == esperado


# ---------------------------------------------------------------------------
# Checagem rápida de texto (pypdfium2): só serve para dizer "não tem texto"
# ---------------------------------------------------------------------------

def test_rapido_pdf_real_escaneado():
    assert parece_escaneado(extrair_paginas_rapido(caminho_exemplo("Aplicações ok.pdf")))


def test_rapido_pdf_real_com_texto():
    assert not parece_escaneado(extrair_paginas_rapido(caminho_exemplo("1179 7.pdf")))


def test_rapido_concorda_com_pdfplumber_em_todos_os_exemplos():
    """Nos PDFs de exemplo (agosto e modelos), a checagem
    rápida e a leitura completa chegam à mesma conclusão sobre "tem texto ou não".
    (Setembro/2026, com 96 PDFs sem texto, foi conferido à parte: os mesmos 96 nos dois.)"""
    pastas = [PASTA_EXTRATOS, PASTA_MODELOS]
    arquivos = [a for p in pastas if p.is_dir() for a in sorted(p.rglob("*.pdf"))]
    if not arquivos:
        pytest.skip("pastas de exemplos não encontradas")
    divergentes = [a.name for a in arquivos
                   if parece_escaneado(extrair_paginas_rapido(a))
                   != parece_escaneado(extrair_paginas_pdf(a))]
    assert divergentes == []
