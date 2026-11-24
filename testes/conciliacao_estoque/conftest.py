"""Configuração dos testes do Estoque: localiza exemplos/conciliacao_estoque/AAAA-MM/.

Os exemplos têm saldos reais e não vão para o git. Se a pasta não existir,
os testes que dependem dela são pulados (os demais continuam rodando).
"""

from __future__ import annotations

import csv
import re
from decimal import Decimal
from pathlib import Path

import pytest

from testes.conftest import pasta_exemplos

MES_EXEMPLO = "2026-09"

# Pedido do usuário (05/11/2026): nos relatórios, "Mapa do Estoque" no lugar de "SCF". Os gabaritos e os
# exemplos aprovados (de setembro) ainda dizem "SCF": para compará-los, o texto gerado volta ao nome antigo.
# Só o nome muda; valores, fórmulas e o resto do texto continuam conferidos.
NOMES_NOVOS = (("Grupo do Mapa do Estoque", "Grupo SCF"), ("Mapa do Estoque", "SCF"))


def com_nome_antigo(valor):
    """Texto gerado com "Mapa do Estoque" → como o gabarito escreve ("SCF"). Outros valores ficam iguais."""
    if not isinstance(valor, str):
        return valor
    for novo, antigo in NOMES_NOVOS:
        valor = valor.replace(novo, antigo)
    return valor


def arquivo_exemplo(nome: str) -> Path:
    """Arquivo de exemplos/conciliacao_estoque/2026-09/; pula o teste se não existir."""
    caminho = pasta_exemplos("conciliacao_estoque", MES_EXEMPLO) / nome
    if not caminho.is_file():
        pytest.skip(f"Arquivo de exemplo {caminho} não encontrado")
    return caminho


def ler_gabarito_estoque() -> list[dict]:
    """gabarito_estoque_2026-09.csv (EST-01 e EST-03): UTF-8, ';', decimal com ponto."""
    caminho = arquivo_exemplo("gabarito_estoque_2026-09.csv")
    with open(caminho, encoding="utf-8-sig", newline="") as arquivo:
        linhas = list(csv.DictReader(arquivo, delimiter=";"))
    for linha in linhas:
        for campo in ("saldo_balancete", "saldo_scf", "diferenca"):
            linha[campo] = Decimal(linha[campo])
    return linhas


@pytest.fixture
def caminho_balancete() -> Path:
    return arquivo_exemplo("Balancete_estoque_completo.xls")


@pytest.fixture
def caminho_scf() -> Path:
    return arquivo_exemplo("SCF - Movimento Estoque (Contabilidade).xls")


@pytest.fixture
def caminho_mapa() -> Path:
    """O mesmo SCF de setembro, com números em outro formato ("0", "660", "59,7")."""
    return arquivo_exemplo("Mapa_movimentacao.xls")


# ---------------------------------------------------------------------------
# Calculadora das fórmulas usadas no relatório (para conferir sem abrir o Excel)
# ---------------------------------------------------------------------------

_INTERVALO = re.compile(r"(?:SUBTOTAL\(9,|SUM\()([A-Z]+)(\d+):([A-Z]+)(\d+)\)")
_OUTRA_ABA = re.compile(r"'([^']+)'!([A-Z]+\d+)")
_CELULA = re.compile(r"\b([A-Z]+\d+)\b")


def calcular(aba, referencia: str) -> Decimal:
    """Valor de uma célula; fórmulas com +, -, parênteses, SUM, SUBTOTAL(9, ...) e 'Outra aba'!C1."""
    valor = aba[referencia].value
    if valor is None:
        return Decimal("0")
    if not isinstance(valor, str):
        return Decimal(repr(valor))
    assert valor.startswith("="), f"{referencia}: texto onde se esperava número ({valor!r})"
    expressao = _OUTRA_ABA.sub(lambda m: f"({calcular(aba.parent[m.group(1)], m.group(2))})", valor[1:])
    expressao = _INTERVALO.sub(lambda m: f"({_somar_intervalo(aba, *m.groups())})", expressao)
    expressao = _CELULA.sub(lambda m: f"({calcular(aba, m.group(1))})", expressao)
    assert re.fullmatch(r"[\d.()+\- ]+", expressao), f"{referencia}: fórmula não reconhecida {valor!r}"
    return eval(re.sub(r"(\d+(?:\.\d+)?)", r"Decimal('\1')", expressao), {"Decimal": Decimal})


def _somar_intervalo(aba, coluna, inicio, coluna_fim, fim) -> Decimal:
    assert coluna == coluna_fim
    return sum((calcular(aba, f"{coluna}{n}") for n in range(int(inicio), int(fim) + 1)), Decimal("0"))
