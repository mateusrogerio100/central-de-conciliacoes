"""E3 — casamento das contas do balancete com os locais do SCF (ESPECIFICACAO_ESTOQUE.md, seções 4 e 7.1)."""

from __future__ import annotations

import re
from dataclasses import replace
from decimal import Decimal

import pytest

from modulos.conciliacao_estoque.casamento import (
    OBSERVACAO_NOME_EQUIVALENTE,
    NomePadronizado,
    casar,
    codigo_no_fim,
    nome_padronizado,
)
from modulos.conciliacao_estoque.leitor_balancete_estoque import ler_balancete_estoque
from modulos.conciliacao_estoque.leitor_scf import ler_scf
from modulos.conciliacao_estoque.modelos import ComoCasou, ContaBalancete, LocalSCF
from testes.conciliacao_estoque.conftest import ler_gabarito_estoque

ZERO = Decimal("0.00")


def _conta(codigo: int, descricao: str) -> ContaBalancete:
    return ContaBalancete(codigo, f"1.01.04.01.{codigo:04d}", descricao, ZERO, ZERO, ZERO, linha=codigo)


def _local(codigo: int, descricao: str) -> LocalSCF:
    return LocalSCF(codigo, descricao, [ZERO] * 13, linha=codigo)


def _pares(resultado) -> dict[int, int | None]:
    return {p.conta.codigo: (p.local.codigo if p.local else None) for p in resultado.pares}


# ---------------------------------------------------------------------------
# Nome padronizado (nível 2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("descricao, resto, unidades", [
    ("Central de Kits - SC (23)", "central kits", {"SC"}),
    ("Central de Kits (23)", "central kits", set()),
    ("Farmácia  - HC (13)", "farmacia", {"HC"}),
    ("Farmácia  - Hospital do Coração (13)", "farmacia", {"HC"}),
    ("Farmácia - Hospital Central (14)", "farmacia", {"HCA"}),
    ("Estoque SESMT - EPI - HC e H Central (118)", "sesmt epi", {"HC", "HCA"}),
    ("Estoque Órtese e Prótese Hosp. Coração (24)", "ortese protese", {"HC"}),
    ("Estoque - Gases Medicinais SCF (30)", "gases medicinais", {"SC"}),
    ("CAF(Central Abastecimento Farmacêutico) (49)", "caf central abastecimento farmaceutico", set()),
    ("Estoque Ortopedia/GO (55)", "ortopedia go", set()),
])
def test_nome_padronizado(descricao, resto, unidades):
    assert nome_padronizado(descricao) == NomePadronizado(resto, frozenset(unidades))


def test_codigo_no_fim():
    assert codigo_no_fim("Central de Kits - SC (23)") == 23
    assert codigo_no_fim("CAF (Central Abastecimento Farmacêutico) (49)") == 49
    assert codigo_no_fim("Central de Kits - SC") is None


# ---------------------------------------------------------------------------
# Regras com casos construídos
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("conta, local_certo, local_proibido", [
    ("Farmácia - Hospital do Coração", (13, "Farmácia - Hospital do Coração (13)"),
     (14, "Farmácia - Hospital Central (14)")),
    ("Estoque Kits Cirurgicos HC", (120, "Estoque Kits Cirurgicos HC (120)"),
     (119, "Estoque kits Cirurgicos SC (119)")),
    ("Suprimentos Nutrição - Hosp. Coração", (16, "Suprimentos Nutrição - Hosp. Coração (16)"),
     (15, "Suprimentos Nutrição - Hospital Exemplo (15)")),
])
def test_casamentos_proibidos(conta, local_certo, local_proibido):
    """Seção 4: unidades diferentes nunca casam, nem quando o local certo não existe."""
    certo, proibido = _local(*local_certo), _local(*local_proibido)
    assert _pares(casar([_conta(1, conta)], [proibido, certo])) == {1: local_certo[0]}
    sozinho = casar([_conta(1, conta)], [proibido])
    assert _pares(sozinho) == {1: None}
    assert sozinho.pares[0].sugestao is None      # nem como sugestão (unidade incompatível)


def test_nivel_1_tem_prioridade_e_cada_local_casa_uma_vez():
    contas = [_conta(1, "Nome qualquer (23)"), _conta(2, "Central de Kits")]
    resultado = casar(contas, [_local(23, "Central de Kits (23)")])
    assert _pares(resultado) == {1: 23, 2: None}
    assert resultado.pares[0].como == ComoCasou.CODIGO_LOCAL
    assert resultado.locais_sem_conta == []


def test_nivel_2_com_mais_de_um_candidato_nao_casa():
    contas = [_conta(1, "Central de Kits")]
    locais = [_local(23, "Central de Kits (23)"), _local(24, "Central de Kits - SC (24)")]
    resultado = casar(contas, locais)
    assert _pares(resultado) == {1: None}
    assert [l.codigo for l in resultado.locais_sem_conta] == [23, 24]


def test_numero_que_nao_existe_no_scf_cai_para_o_nivel_2():
    resultado = casar([_conta(1, "Central de Kits - SC (99)")], [_local(23, "Central de Kits (23)")])
    assert resultado.pares[0].como == ComoCasou.NOME_EQUIVALENTE
    assert resultado.pares[0].observacao == OBSERVACAO_NOME_EQUIVALENTE


def test_nivel_3_sugere_o_mais_parecido():
    resultado = casar([_conta(1, "Almoxarifado Hemodialise SC")],
                      [_local(26, "Almoxarifado Hemodiálise Adulto (26)"), _local(30, "Lavanderia (30)")])
    par = resultado.pares[0]
    assert par.local is None and par.como == ComoCasou.SEM_PAR
    assert par.sugestao.codigo == 26
    assert re.fullmatch(r"Sem par no Mapa do Estoque — possível par: Almoxarifado Hemodiálise Adulto \(26\) "
                        r"\(semelhança \d+%\)", par.observacao)


def test_nivel_3_sem_candidato_parecido():
    resultado = casar([_conta(1, "Almoxarifado Central")], [_local(30, "Lavanderia (30)")])
    assert resultado.pares[0].observacao == "Sem par no Mapa do Estoque"
    assert resultado.pares[0].sugestao is None


# ---------------------------------------------------------------------------
# Arquivos reais de setembro/2026
# ---------------------------------------------------------------------------


def test_setembro_23_contas_no_nivel_1(caminho_balancete, caminho_scf):
    balancete, scf = ler_balancete_estoque(caminho_balancete), ler_scf(caminho_scf)
    resultado = casar(balancete.analiticas, scf.locais)
    assert len(resultado.pares) == 23
    assert all(p.como == ComoCasou.CODIGO_LOCAL for p in resultado.pares)
    assert len(resultado.locais_sem_conta) == 17

    esperado = {int(g["codigo"]): int(g["local_scf"]) for g in ler_gabarito_estoque() if g["codigo"]}
    assert _pares(resultado) == esperado
    sem_conta = {int(g["local_scf"]) for g in ler_gabarito_estoque() if not g["codigo"]}
    assert {l.codigo for l in resultado.locais_sem_conta} == sem_conta


def test_setembro_sem_numero_casa_tudo_no_nivel_2(caminho_balancete, caminho_scf):
    """Tirando o (número) das descrições do balancete, os mesmos 23 pares saem no nível 2."""
    balancete, scf = ler_balancete_estoque(caminho_balancete), ler_scf(caminho_scf)
    sem_numero = [replace(c, descricao=re.sub(r"\s*\(\d+\)\s*$", "", c.descricao)) for c in balancete.analiticas]
    assert all(codigo_no_fim(c.descricao) is None for c in sem_numero)
    com_numero = casar(balancete.analiticas, scf.locais)
    resultado = casar(sem_numero, scf.locais)
    nao_casadas = [(p.conta.descricao, p.observacao) for p in resultado.pares if p.como != ComoCasou.NOME_EQUIVALENTE]
    assert nao_casadas == []
    assert _pares(resultado) == _pares(com_numero)
