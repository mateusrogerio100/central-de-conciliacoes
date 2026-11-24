"""V4 — maio/2026 refeito a partir do controle de abril e comparado com a planilha da Contabilidade
(ESPECIFICACAO, seções 2.3 e 8). Usa os arquivos reais de exemplos\\credito_estouro\\ (fora do git): os nomes
ficam no casos_reais.json de lá, nunca aqui.
"""

import json
from decimal import Decimal as D
from pathlib import Path

import pytest

from modulos.credito_estouro import conciliador as c
from modulos.credito_estouro.conciliador import conciliar, montar_controle_inicial
from modulos.credito_estouro.controle import LeituraControle
from modulos.credito_estouro.leitor_eventos import ler_eventos
from modulos.credito_estouro.leitor_razao import ler_razao
from modulos.credito_estouro.modelos import (
    TIPO_0256,
    TIPO_ACERTO,
    TIPO_DIFERENCA_0241,
    TIPO_PARCELAMENTO,
    TIPO_PENDENCIA,
    ItemControle,
)

PASTA = Path(__file__).resolve().parents[2] / "exemplos" / "credito_estouro"
pytestmark = pytest.mark.skipif(not (PASTA / "casos_reais.json").exists(), reason="exemplos reais fora do git")


def controle_inicial(mes: str) -> LeituraControle:
    """O controle montado uma vez: 0256 do PDF do mês + parcelamentos e diferenças da planilha à mão."""
    eventos = ler_eventos(next((PASTA / mes).glob("EVENTOS*")))
    casos = json.loads((PASTA / "casos_reais.json").read_text(encoding="utf-8"))[mes]
    outros = [ItemControle(caso["matricula"], caso["nome"], caso["tipo"], eventos.competencia, D(caso["valor"]),
                           D(caso["parcela"]) if caso.get("parcela") else None, caso.get("observacao", ""),
                           caso.get("pagador", ""))
              for caso in casos]
    return LeituraControle(arquivo=f"controle {mes}", competencia=eventos.competencia,
                           itens=montar_controle_inicial(eventos, outros))


def _soma(itens, tipo):
    return sum((i.valor for i in itens if i.tipo == tipo), D("0"))


def test_controles_iniciais_somam_o_saldo_do_razao():
    assert controle_inicial("2026-04").total == D("97075.60")    # planilha de abril
    assert controle_inicial("2026-05").total == D("98853.35")    # planilha de maio


@pytest.fixture(scope="module")
def maio():
    eventos = ler_eventos(next((PASTA / "2026-05").glob("EVENTOS*")))
    razao = ler_razao(PASTA / "2026-05" / "Razão.pdf")
    return conciliar(eventos, razao, controle_inicial("2026-04"))


def test_maio_prova_fecha(maio):
    assert maio.avisos == []
    assert maio.saldo_final_razao == D("98853.35")
    assert maio.diferenca_sem_explicacao == 0
    assert all(conferencia.diferenca == 0 for conferencia in maio.conferencias_folha)


def test_maio_igual_a_planilha_da_contabilidade(maio):
    """Planilha 05-2026.xlsx: 0256 96.906,08 + parcelamentos 373,21 e 340,97 + 0241 não lançado 1.233,09."""
    controle_maio = controle_inicial("2026-05")
    novo = maio.controle_novo
    assert _soma(novo, TIPO_0256) == D("96906.08")
    for tipo in (TIPO_PARCELAMENTO, TIPO_DIFERENCA_0241):
        assert sorted((i.matricula, i.valor) for i in novo if i.tipo == tipo) == sorted(
            (i.matricula, i.valor) for i in controle_maio.itens if i.tipo == tipo)
    assert _soma(novo, TIPO_PARCELAMENTO) == D("714.18")
    assert _soma(novo, TIPO_DIFERENCA_0241) == D("1233.09")
    assert _soma(novo, TIPO_PENDENCIA) == _soma(novo, TIPO_ACERTO) == 0
    assert maio.a_conferir == []


def test_maio_r1_e_r3(maio):
    situacoes = [l.situacao for l in maio.cobrancas]
    assert (situacoes.count(c.COBRADO), situacoes.count(c.BAIXADO), len(situacoes)) == (120, 8, 128)
    assert sorted(l.situacao for l in maio.parcelamentos) == sorted(
        [c.QUITADO_1204, c.QUITADO_RAZAO, c.PARCELA_DESCONTADA, c.PARCELA_DESCONTADA])
