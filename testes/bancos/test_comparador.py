"""Testes do comparador (extratos x balancete)."""

from decimal import Decimal
from pathlib import Path

import pytest

from modulos.bancos.balancete import ler_balancete
from modulos.bancos.comparador import (
    DIFERENCA,
    NAO_ESTA_NO_BALANCETE,
    OK,
    SEM_EXTRATO,
    conciliar,
    contar_por_status,
)
from modulos.bancos.identificador import identificar_pasta
from modulos.bancos.modelos import ContaBalancete, SaldoExtraido
from testes.bancos.conftest import ARQUIVO_BALANCETE, PASTA_EXTRATOS


def conta(codigo, banco, tipo, numero, saldo, descricao=""):
    return ContaBalancete(codigo=codigo, classificacao="1.01.01.02.01.0001",
                          descricao=descricao or f"{banco} {tipo} {numero}",
                          banco=banco, tipo=tipo, conta=numero, saldo_atual=Decimal(saldo))


def saldo(banco, tipo, numero, total, bloqueado="0", arquivo="a.pdf",
          secundaria=False, observacao=""):
    return SaldoExtraido(banco=banco, tipo=tipo, conta=numero, conta_original=numero,
                         saldo_total=Decimal(total), saldo_bloqueado=Decimal(bloqueado),
                         arquivo=Path(arquivo), modelo="Teste",
                         fonte_secundaria=secundaria, observacao=observacao)


def por_conta(linhas):
    return {(l.banco, l.tipo, l.conta): l for l in linhas}


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def test_ok_quando_diferenca_zero():
    [linha] = conciliar([conta("1", "BB", "CC", "80365", "640.44")],
                        [saldo("BB", "CC", "80365", "640.44")])
    assert linha.status == OK
    assert linha.diferenca == Decimal("0.00")


def test_diferenca_e_extrato_menos_balancete():
    [linha] = conciliar([conta("1", "SANTANDER", "APLICACAO", "36345", "310.71")],
                        [saldo("SANTANDER", "APLICACAO", "36345", "310.72")])
    assert linha.status == DIFERENCA
    assert linha.diferenca == Decimal("0.01")


def test_diferenca_negativa():
    [linha] = conciliar([conta("1", "BB", "APLICACAO", "5347", "21160.10")],
                        [saldo("BB", "APLICACAO", "5347", "228.18")])
    assert (linha.status, linha.diferenca) == (DIFERENCA, Decimal("-20931.92"))


def test_sem_extrato():
    [linha] = conciliar([conta("1", "BB", "CC", "80365", "640.44")], [])
    assert linha.status == SEM_EXTRATO
    assert linha.diferenca is None and linha.grupo is None


def test_nao_esta_no_balancete_com_saldo_zero():
    linhas = conciliar([], [saldo("BB", "CC", "11797", "0.00")])
    assert [(l.status, l.observacao) for l in linhas] == [(NAO_ESTA_NO_BALANCETE, "saldo zero")]


def test_nao_esta_no_balancete_com_saldo():
    [linha] = conciliar([], [saldo("BB", "CC", "11797", "15.00")])
    assert (linha.status, linha.observacao) == (NAO_ESTA_NO_BALANCETE, "")
    assert linha.saldo_balancete is None


def test_descricao_nao_reconhecida():
    [linha] = conciliar([conta("1", "", "", "", "5.00", descricao="Conta Estranha")], [])
    assert (linha.status, linha.observacao) == (SEM_EXTRATO, "descrição não reconhecida")


def test_tipo_diferente_nao_casa():
    # Mesma conta 1179-7 no BB: C/C no extrato, Poupança no balancete
    linhas = conciliar([conta("1", "BB", "POUPANCA", "11797", "223374.00")],
                       [saldo("BB", "CC", "11797", "0.00")])
    assert [l.status for l in linhas] == [SEM_EXTRATO, NAO_ESTA_NO_BALANCETE]


def test_ordem_das_linhas():
    linhas = conciliar(
        [conta("2", "BB", "CC", "22222", "1"), conta("1", "BB", "CC", "11111", "1")],
        [saldo("BB", "CC", "99999", "1"), saldo("BB", "CC", "11111", "1")],
    )
    assert [l.conta for l in linhas] == ["22222", "11111", "99999"]


def test_contar_por_status():
    linhas = conciliar(
        [conta("1", "BB", "CC", "11111", "1"), conta("2", "BB", "CC", "22222", "1")],
        [saldo("BB", "CC", "11111", "1"), saldo("BB", "CC", "33333", "0")],
    )
    assert contar_por_status(linhas) == {
        OK: 1, DIFERENCA: 0, SEM_EXTRATO: 1, NAO_ESTA_NO_BALANCETE: 1}


# ---------------------------------------------------------------------------
# Casamento por sufixo
# ---------------------------------------------------------------------------

def test_casamento_por_sufixo():
    [linha] = conciliar([conta("1", "SANTANDER", "APLICACAO", "36369", "138.49")],
                        [saldo("SANTANDER", "APLICACAO", "130036369", "138.49")])
    assert linha.status == OK
    assert "conta casada por sufixo" in linha.observacao
    assert linha.conta == "36369"          # a do balancete


def test_sufixo_funciona_nos_dois_sentidos():
    [linha] = conciliar([conta("1", "SANTANDER", "APLICACAO", "130036369", "1")],
                        [saldo("SANTANDER", "APLICACAO", "36369", "1")])
    assert linha.status == OK


def test_sufixo_curto_demais_nao_casa():
    # "7161" tem só 4 caracteres
    linhas = conciliar([conta("1", "BB", "CC", "7161", "1")],
                       [saldo("BB", "CC", "4007161", "1")])
    assert [l.status for l in linhas] == [SEM_EXTRATO, NAO_ESTA_NO_BALANCETE]


def test_sufixo_com_dois_candidatos_nao_casa():
    linhas = conciliar([conta("1", "SANTANDER", "APLICACAO", "36369", "1")],
                       [saldo("SANTANDER", "APLICACAO", "130036369", "1"),
                        saldo("SANTANDER", "APLICACAO", "990036369", "1")])
    assert linhas[0].status == SEM_EXTRATO
    assert [l.status for l in linhas[1:]] == [NAO_ESTA_NO_BALANCETE] * 2


def test_sufixo_disputado_por_duas_contas_nao_casa():
    linhas = conciliar([conta("1", "SANTANDER", "APLICACAO", "36369", "1"),
                        conta("2", "SANTANDER", "APLICACAO", "036369", "1")],
                       [saldo("SANTANDER", "APLICACAO", "130036369", "1")])
    assert [l.status for l in linhas] == [SEM_EXTRATO, SEM_EXTRATO, NAO_ESTA_NO_BALANCETE]


def test_sufixo_de_outro_banco_nao_casa():
    linhas = conciliar([conta("1", "BB", "APLICACAO", "36369", "1")],
                       [saldo("SANTANDER", "APLICACAO", "130036369", "1")])
    assert linhas[0].status == SEM_EXTRATO


def test_exato_tem_prioridade_sobre_sufixo():
    linhas = conciliar([conta("1", "SANTANDER", "APLICACAO", "36369", "5"),
                        conta("2", "SANTANDER", "APLICACAO", "130036369", "7")],
                       [saldo("SANTANDER", "APLICACAO", "130036369", "7")])
    assert [l.status for l in linhas] == [SEM_EXTRATO, OK]
    assert "sufixo" not in linhas[1].observacao


# ---------------------------------------------------------------------------
# Soma e fonte secundária
# ---------------------------------------------------------------------------

def test_saldos_da_mesma_chave_sao_somados():
    # Caso real: CDB + Rende Fácil da conta 534-7
    [linha] = conciliar([conta("1", "BB", "APLICACAO", "5347", "21160.10")],
                        [saldo("BB", "APLICACAO", "5347", "20931.92", arquivo="534 7 CDB.pdf"),
                         saldo("BB", "APLICACAO", "5347", "228.18", arquivo="534 7 RF.pdf")])
    assert linha.status == OK
    assert linha.grupo.saldo_total == Decimal("21160.10")
    assert linha.arquivos == ["534 7 CDB.pdf", "534 7 RF.pdf"]


def test_bloqueado_somado_e_disponivel():
    [linha] = conciliar([conta("1", "SICOOB", "CC", "20048343", "4186.14")],
                        [saldo("SICOOB", "CC", "20048343", "4186.14", bloqueado="50.00")])
    assert linha.grupo.saldo_bloqueado == Decimal("50.00")
    assert linha.grupo.saldo_disponivel == Decimal("4136.14")


def test_fonte_secundaria_usada_quando_nao_ha_principal():
    [linha] = conciliar([conta("1", "SANTANDER", "APLICACAO", "130036369", "138.49")],
                        [saldo("SANTANDER", "APLICACAO", "130036369", "138.49", secundaria=True)])
    assert linha.status == OK


def test_fonte_secundaria_nao_soma_com_principal():
    [linha] = conciliar(
        [conta("1", "SANTANDER", "APLICACAO", "130036383", "132.59")],
        [saldo("SANTANDER", "APLICACAO", "130036383", "132.59", arquivo="contamax.pdf"),
         saldo("SANTANDER", "APLICACAO", "130036383", "132.59", arquivo="cc.pdf",
               secundaria=True)],
    )
    assert linha.status == OK
    assert linha.grupo.saldo_total == Decimal("132.59")
    assert linha.arquivos == ["contamax.pdf"]
    assert "divergentes" not in linha.observacao


def test_fonte_secundaria_divergente_gera_observacao():
    [linha] = conciliar(
        [conta("1", "SANTANDER", "APLICACAO", "130036383", "132.59")],
        [saldo("SANTANDER", "APLICACAO", "130036383", "132.59", arquivo="contamax.pdf"),
         saldo("SANTANDER", "APLICACAO", "130036383", "100.00", arquivo="cc.pdf",
               secundaria=True)],
    )
    assert linha.status == OK                   # vale o principal
    assert "extratos divergentes: 132,59" in linha.observacao
    assert "100,00" in linha.observacao


def test_observacoes_dos_extratos_aparecem():
    [linha] = conciliar(
        [conta("1", "BB", "APLICACAO", "4005007", "10")],
        [saldo("BB", "APLICACAO", "4005007", "4", arquivo="f.pdf", observacao="Fundo A: 4,00"),
         saldo("BB", "APLICACAO", "4005007", "6", arquivo="c.pdf")],
    )
    assert linha.observacao == "f.pdf: Fundo A: 4,00"


def test_chave_repetida_no_balancete_nao_conta_extrato_duas_vezes():
    linhas = conciliar([conta("1", "BB", "CC", "11111", "5"), conta("2", "BB", "CC", "11111", "5")],
                       [saldo("BB", "CC", "11111", "5")])
    assert [l.status for l in linhas] == [OK, SEM_EXTRATO]
    assert "código 1" in linhas[1].observacao


# ---------------------------------------------------------------------------
# Ponta a ponta com os exemplos (status esperados da seção 11)
# ---------------------------------------------------------------------------

STATUS_ESPERADOS = {
    ("BB", "APLICACAO", "11444"): (OK, "0.00"),
    ("BB", "POUPANCA", "11797"): (OK, "0.00"),
    ("CEF", "CC", "5686307039"): (OK, "0.00"),
    ("SANTANDER", "APLICACAO", "36383"): (OK, "0.00"),       # ContaMax, casada por sufixo
    ("SICOOB", "CC", "20048343"): (OK, "0.00"),              # 4.136,14 + 50,00
    ("BB", "APLICACAO", "5347"): (DIFERENCA, None),
    ("BB", "APLICACAO", "4005007"): (DIFERENCA, None),
    ("BB", "APLICACAO", "4005856"): (DIFERENCA, None),
    ("BB", "CC", "11797"): (NAO_ESTA_NO_BALANCETE, None),
    ("SANTANDER", "CC", "130036345"): (NAO_ESTA_NO_BALANCETE, None),
    ("SANTANDER", "CC", "130036369"): (NAO_ESTA_NO_BALANCETE, None),
}


@pytest.fixture(scope="module")
def conciliacao_exemplo():
    if not ARQUIVO_BALANCETE.is_file() or not PASTA_EXTRATOS.is_dir():
        pytest.skip("exemplos não encontrados")
    balancete = ler_balancete(ARQUIVO_BALANCETE)
    identificacao = identificar_pasta(PASTA_EXTRATOS, balancete.competencia)
    return balancete, conciliar(balancete.contas, identificacao.saldos)


def test_ponta_a_ponta_status_esperados(conciliacao_exemplo):
    _, linhas = conciliacao_exemplo
    obtidos = por_conta(linhas)
    for chave, (status, diferenca) in STATUS_ESPERADOS.items():
        linha = obtidos[chave]
        assert linha.status == status, chave
        if diferenca is not None:
            assert linha.diferenca == Decimal(diferenca), chave
        if status == NAO_ESTA_NO_BALANCETE:
            assert linha.observacao == "saldo zero", chave


def test_ponta_a_ponta_demais_contas_sem_extrato(conciliacao_exemplo):
    balancete, linhas = conciliacao_exemplo
    for linha in linhas:
        chave = (linha.banco, linha.tipo, linha.conta)
        if chave not in STATUS_ESPERADOS:
            assert linha.status == SEM_EXTRATO, chave
    # toda conta do balancete aparece exatamente uma vez
    codigos = [l.conta_balancete.codigo for l in linhas if l.conta_balancete]
    assert sorted(codigos) == sorted(c.codigo for c in balancete.contas)


def test_ponta_a_ponta_sufixo_e_contagem(conciliacao_exemplo):
    balancete, linhas = conciliacao_exemplo
    assert "conta casada por sufixo" in por_conta(linhas)[("SANTANDER", "APLICACAO", "36383")].observacao
    # Sem ContaMax na pasta: o item D do extrato de C/C não é mais usado
    assert por_conta(linhas)[("SANTANDER", "APLICACAO", "36369")].status == SEM_EXTRATO
    assert por_conta(linhas)[("SANTANDER", "APLICACAO", "36345")].status == SEM_EXTRATO
    assert contar_por_status(linhas) == {
        OK: 5, DIFERENCA: 3, NAO_ESTA_NO_BALANCETE: 3,
        SEM_EXTRATO: len(balancete.contas) - 8,
    }
