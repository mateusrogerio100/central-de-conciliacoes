"""T3 — conferência = gabarito do protótipo (gabarito_conferencia.csv e gabarito_divergencias.csv).

Os gabaritos foram gerados pelo protótipo com a configuração de 22/10/2026 (config_gabarito_22-10-2026)
e conferidos pelo usuário. Divergência aqui = parar e perguntar, nunca ajustar o gabarito.
"""

from __future__ import annotations

import csv
from decimal import Decimal

import pytest

from modulos.checklist_contratos.conferencia import conferir
from modulos.checklist_contratos.leitor_checklist import ler_checklist
from modulos.checklist_contratos.leitor_configuracao import ler_configuracao
from modulos.checklist_contratos.leitor_movimento import ler_movimentos
from modulos.checklist_contratos.modelos import Situacao
from testes.checklist_contratos.conftest import exemplos

# seção 8 da especificação: OK, conta divergente, não encontrado, manual, ignorado, lançamentos divergentes
ESPERADO = {
    "2026-09": (121, 3, 13, 13, 8, 3),
    "2026-10": (80, 5, 52, 13, 8, 6),
}
_CACHE: dict = {}


def _conferencia(mes: str):
    if mes not in _CACHE:
        pasta = exemplos(mes)
        mm = mes[-2:]
        movimentos = {e: ler_movimentos(pasta / f"Movimentos_NF_{mm}_{e}.csv", e) for e in ("SC", "CMD")}
        checklist = ler_checklist(pasta / "Check list 2026.xlsx", 2026, int(mm))
        configuracao = ler_configuracao(exemplos("config_gabarito_22-10-2026"))
        _CACHE[mes] = checklist, conferir(movimentos, checklist, configuracao)
    return _CACHE[mes]


def _gabarito(mes: str, nome: str) -> list[dict]:
    texto = (exemplos(mes, "gabarito") / nome).read_text(encoding="utf-8-sig")
    return list(csv.DictReader(texto.splitlines(), delimiter=";"))


@pytest.mark.parametrize("mes", sorted(ESPERADO))
def test_t3_contagem_por_situacao(mes):
    _, conferencia = _conferencia(mes)
    contagem = conferencia.contagem()
    divergentes = sum(len(r.divergentes) for r in conferencia.resultados if r.situacao == Situacao.CONTA_DIVERGENTE)
    assert (contagem[Situacao.OK], contagem[Situacao.CONTA_DIVERGENTE], contagem[Situacao.NAO_ENCONTRADO],
            contagem[Situacao.MANUAL], contagem[Situacao.IGNORADO], divergentes) == ESPERADO[mes]
    assert len(conferencia.resultados) == 158                      # R10: uma linha por regra


@pytest.mark.parametrize("mes", sorted(ESPERADO))
def test_t3_cada_linha_igual_ao_gabarito_conferencia(mes):
    checklist, conferencia = _conferencia(mes)
    gabarito = {(g["Aba"], int(g["Linha"])): g for g in _gabarito(mes, "gabarito_conferencia.csv")}
    diferencas = []
    for r in conferencia.resultados:
        g = gabarito.pop((checklist.abas[r.regra.aba].nome, r.linha.numero))
        valor = f"{r.valor:.2f}" if r.valor is not None else ""
        lotes = r.lote_lancamento if r.situacao in (Situacao.OK, Situacao.CONTA_DIVERGENTE) else g["Lote_Lanc"]
        if (r.situacao.value, valor, lotes, "/".join(r.regra.contas)) != \
                (g["Status"], g["Valor_encontrado"], g["Lote_Lanc"], g["Conta_esperada"]):
            diferencas.append((r.regra.aba, r.linha.numero, r.situacao.value, valor, lotes, dict(g)))
    assert diferencas == [] and gabarito == {}


@pytest.mark.parametrize("mes", sorted(ESPERADO))
def test_t3_divergencias_iguais_ao_gabarito(mes):
    checklist, conferencia = _conferencia(mes)
    meu = sorted((checklist.abas[r.regra.aba].nome, r.linha.numero, "/".join(r.regra.contas), l.conta,
                  f"{l.valor:.2f}", l.lote, l.lancamento)
                 for r in conferencia.resultados if r.situacao == Situacao.CONTA_DIVERGENTE
                 for l in r.divergentes)
    gabarito = sorted((g["Aba"], int(g["Linha"]), g["Conta_esperada"], g["Conta_lancada"], g["Valor"], g["Lote"],
                       g["Lancamento"]) for g in _gabarito(mes, "gabarito_divergencias.csv"))
    assert meu == gabarito


def test_t3_setembro_118_de_121_iguais_ao_que_o_usuario_preencheu():
    # os 3 diferentes são pontos da seção 10 (serviço postal, SIP e monitoramento veicular): vale o gabarito
    _, conferencia = _conferencia("2026-09")
    oks = [r for r in conferencia.resultados if r.situacao == Situacao.OK]
    iguais = [r for r in oks if isinstance(r.linha.valor_mes, (int, float))
              and Decimal(str(r.linha.valor_mes)).quantize(Decimal("0.01")) == r.valor]
    assert len(oks) == 121 and len(iguais) == 118
