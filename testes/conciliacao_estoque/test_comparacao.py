"""E4 — comparação da EST-01 e da EST-03 contra o gabarito (ESPECIFICACAO_ESTOQUE.md, seções 6, 7.1 e 7.2)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from modulos.conciliacao_estoque import configuracao
from modulos.conciliacao_estoque.comparacao import comparar
from modulos.conciliacao_estoque.leitor_balancete_estoque import ler_balancete_estoque
from modulos.conciliacao_estoque.leitor_scf import ler_scf
from modulos.conciliacao_estoque.modelos import (
    BalanceteEstoque,
    ContaBalancete,
    Gravidade,
    LocalSCF,
    RelatorioSCF,
)
from modulos.conciliacao_estoque.utilitarios import normalizar_texto
from testes.conciliacao_estoque.conftest import ler_gabarito_estoque

EST_01, EST_03 = configuracao.ETAPAS
PARTE_DA_ETAPA = {"EST-01": "saldo_anterior", "EST-03": "saldo_atual"}


@pytest.fixture
def setembro(caminho_balancete, caminho_scf):
    return ler_balancete_estoque(caminho_balancete), ler_scf(caminho_scf)


def _texto_comparavel(texto: str) -> str:
    """O gabarito escreve "local do SCF ... - saldo zero"; o programa, "Local do Mapa do Estoque ... — saldo zero"
    (o nome "Mapa do Estoque" no lugar de "SCF" nos relatórios é pedido do usuário, 05/11/2026)."""
    return normalizar_texto(texto.replace("—", "-").replace("Mapa do Estoque", "SCF"))


def test_etapas_configuradas():
    assert [e.id for e in configuracao.ETAPAS] == ["EST-01", "EST-03"]
    assert (EST_01.titulo, EST_03.titulo) == ("Conciliação saldo anterior estoque", "Conciliação saldo atual estoque")


@pytest.mark.parametrize("etapa", configuracao.ETAPAS, ids=lambda e: e.id)
def test_setembro_igual_ao_gabarito(setembro, etapa):
    resultado = comparar(etapa, *setembro)
    gabarito = [g for g in ler_gabarito_estoque() if g["parte"] == PARTE_DA_ETAPA[etapa.id]]
    gerado = [
        {
            "grupo": l.grupo, "classificacao": l.classificacao,
            "codigo": str(l.codigo) if l.codigo is not None else "",
            "descricao_balancete": l.descricao_balancete, "descricao_scf": l.descricao_scf,
            "local_scf": str(l.local_scf), "saldo_balancete": l.saldo_balancete, "saldo_scf": l.saldo_scf,
            "diferenca": l.diferenca, "como_casou": l.como.value, "observacao": _texto_comparavel(l.observacao),
        }
        for l in resultado.contas + resultado.locais_sem_conta
    ]
    esperado = [{**{k: v for k, v in g.items() if k != "parte"}, "observacao": _texto_comparavel(g["observacao"])}
                for g in gabarito]
    chave = lambda linha: (linha["codigo"] == "", linha["local_scf"])    # noqa: E731
    assert sorted(gerado, key=chave) == sorted(esperado, key=chave)
    assert len(gerado) == 40


def test_setembro_est03_saldo_atual(setembro):
    resultado = comparar(EST_03, *setembro)
    assert resultado.contas_conciliadas == 23 and resultado.contas_com_diferenca == 0
    assert resultado.total_balancete == resultado.total_scf == Decimal("6034965.49")
    assert resultado.saldo_sintetica_raiz == Decimal("6034965.49")
    assert resultado.total_scf_das_linhas == Decimal("6034965.49")
    assert {g.classificacao: g.subtotal for g in resultado.grupos} == {
        "1.01.04.01": Decimal("4200117.67"),
        "1.01.04.02": Decimal("695993.46"),
        "1.01.04.03": Decimal("1138854.36"),
    }
    assert resultado.grupos_conferidos == 3
    assert len(resultado.locais_sem_conta) == 17
    assert all(l.saldo_scf == 0 for l in resultado.locais_sem_conta)
    assert resultado.avisos == []


def test_setembro_est01_saldo_anterior_com_o_enxoval(setembro):
    """Seção 7.2: o Enxoval (67) tinha 41.038,00 de saldo anterior e o balancete não imprimiu a conta."""
    resultado = comparar(EST_01, *setembro)
    assert resultado.contas_conciliadas == 23 and resultado.contas_com_diferenca == 0
    assert resultado.total_balancete == Decimal("6517621.62")
    assert resultado.saldo_sintetica_raiz == Decimal("6558659.62")
    assert resultado.total_scf == resultado.total_scf_das_linhas == Decimal("6558659.62")

    enxoval = next(l for l in resultado.locais_sem_conta if l.local_scf == 67)
    assert enxoval.saldo_scf == Decimal("41038.00")
    assert enxoval.observacao == "Local do Mapa do Estoque sem conta no balancete — COM SALDO"

    grupos = {g.classificacao: g for g in resultado.grupos}
    hospital_exemplo = grupos["1.01.04.01"]
    assert hospital_exemplo.saldo_sintetica == Decimal("4675745.59")
    assert hospital_exemplo.subtotal == Decimal("4634707.59")
    assert hospital_exemplo.diferenca == Decimal("41038.00")
    assert hospital_exemplo.causa_provavel == (
        "Diferença no grupo 1.01.04.01 igual ao saldo de local(is) do Mapa do Estoque sem conta: "
        "provável conta com saldo atual zero que o balancete não imprime"
    )
    assert resultado.grupos_conferidos == 2

    assert [(a.gravidade, a.tipo) for a in resultado.avisos] == [
        (Gravidade.ATENCAO, "local com saldo sem conta"),
        (Gravidade.ATENCAO, "grupo com diferença"),
    ]
    assert "provável conta com saldo atual zero" in resultado.avisos[1].mensagem
    assert "trazer as contas zeradas" in resultado.avisos[1].mensagem


def test_balancete_com_a_conta_zerada_impressa_nao_tem_diferenca():
    """Com o balancete gerado com as contas zeradas, o Enxoval casa e o grupo fecha."""
    balancete, scf = _cenario(
        [_conta(114, "1.01.04", "ESTOQUES", Decimal("130.00")),
         _conta(1141, "1.01.04.01", "ESTOQUE HOSPITAL EXEMPLO", Decimal("130.00")),
         _conta(1, "1.01.04.01.0001", "Almoxarifado (12)", Decimal("100.00")),
         _conta(2, "1.01.04.01.0002", "Estoque Enxoval Hospitalar (67)", Decimal("30.00"))],
        [_local(12, "Almoxarifado (12)", Decimal("100.00")), _local(67, "Enxoval (67)", Decimal("30.00"))],
    )
    resultado = comparar(EST_01, balancete, scf)
    assert resultado.locais_sem_conta == []
    assert resultado.grupos_conferidos == 1
    assert resultado.avisos == []


# ---------------------------------------------------------------------------
# Casos construídos
# ---------------------------------------------------------------------------

Z = Decimal("0.00")


def _conta(codigo, classificacao, descricao, saldo):
    return ContaBalancete(codigo, classificacao, descricao, saldo, Z, saldo, linha=1)


def _local(codigo, descricao, saldo):
    return LocalSCF(codigo, descricao, [saldo] + [Z] * 11 + [saldo], linha=1)


def _cenario(contas, locais, total_scf=None):
    balancete = BalanceteEstoque("bal.xls", contas=contas)
    soma = sum((l.saldo_atual for l in locais), Z)
    scf = RelatorioSCF("scf.xls", locais=locais, total=[total_scf or soma] + [Z] * 11 + [total_scf or soma])
    return balancete, scf


def test_conta_com_diferenca_e_conta_sem_par():
    balancete, scf = _cenario(
        [_conta(114, "1.01.04", "ESTOQUES", Decimal("150.00")),
         _conta(1141, "1.01.04.01", "ESTOQUE HOSPITAL EXEMPLO", Decimal("150.00")),
         _conta(1, "1.01.04.01.0001", "Almoxarifado - SC (12)", Decimal("100.00")),
         _conta(2, "1.01.04.01.0002", "Lavanderia (102)", Decimal("50.00"))],
        [_local(12, "Almoxarifado Central (12)", Decimal("90.00"))],
    )
    resultado = comparar(EST_03, balancete, scf)
    assert [l.diferenca for l in resultado.contas] == [Decimal("10.00"), Decimal("50.00")]
    assert resultado.contas_com_diferenca == 2
    assert resultado.grupos_conferidos == 1
    assert [a.tipo for a in resultado.avisos] == ["conta sem par"]


def test_sem_causa_provavel_quando_a_diferenca_nao_bate_com_os_locais_sem_conta():
    balancete, scf = _cenario(
        [_conta(114, "1.01.04", "ESTOQUES", Decimal("200.00")),
         _conta(1141, "1.01.04.01", "ESTOQUE HOSPITAL EXEMPLO", Decimal("200.00")),
         _conta(1, "1.01.04.01.0001", "Almoxarifado (12)", Decimal("100.00"))],
        [_local(12, "Almoxarifado (12)", Decimal("100.00")), _local(67, "Enxoval (67)", Decimal("30.00"))],
    )
    resultado = comparar(EST_03, balancete, scf)
    assert resultado.grupos[0].diferenca == Decimal("100.00")
    assert resultado.grupos[0].causa_provavel == ""


def test_total_do_scf_diferente_das_linhas_gera_erro():
    balancete, scf = _cenario(
        [_conta(114, "1.01.04", "ESTOQUES", Decimal("100.00")),
         _conta(1141, "1.01.04.01", "ESTOQUE HOSPITAL EXEMPLO", Decimal("100.00")),
         _conta(1, "1.01.04.01.0001", "Almoxarifado (12)", Decimal("100.00"))],
        [_local(12, "Almoxarifado (12)", Decimal("100.00"))],
        total_scf=Decimal("150.00"),
    )
    resultado = comparar(EST_03, balancete, scf)
    assert [(a.gravidade, a.tipo) for a in resultado.avisos] == [(Gravidade.ERRO, "total do Mapa do Estoque")]


def test_mes_diferente_gera_atencao(setembro):
    from modulos.conciliacao_estoque.modelos import MesReferencia

    balancete, scf = setembro
    scf.mes_referencia = MesReferencia(2026, 8)
    resultado = comparar(EST_03, balancete, scf)
    assert [a.tipo for a in resultado.avisos] == ["mês diferente"]
