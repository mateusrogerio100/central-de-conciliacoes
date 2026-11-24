"""V2 e V3 — nome do convênio no histórico (C1 a C3) e linha da planilha (C4 a C7)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from modulos.convenios.classificacao import (
    COMO_DENTRO, COMO_EQUIVALENCIA, COMO_IGUAL, COMO_NAO_IDENTIFICADO, COMO_NOVA, classificar, nome_do_historico,
)
from modulos.convenios.leitor_equivalencias import ler_equivalencias
from modulos.convenios.leitor_planilha import ler_planilha
from modulos.convenios.leitor_razao import ler_razao
from modulos.convenios.modelos import ContaRazao, Equivalencia, Equivalencias, Lancamento, LinhaConvenio, Planilha, Razao
from testes.convenios.conftest import exemplos


# ---------------------------------------------------------------------------
# V2 — nome no histórico
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("historico, nome", [
    ("Faturamento Mês NF 299141 PM de Cidade Exemplo Set/2026 Protocolo 152516", "PM de Cidade Exemplo"),
    ("Faturamento Mês  NF 1 Pref.Munic.Exemplo-UNIDADE Ago/2026  Protocolo 2 ", "Pref.Munic.Exemplo-UNIDADE"),
    ("Faturamento Mês PM EXEMPLO CONVENIO Set/2026 Protocolo 149938", "PM EXEMPLO CONVENIO"),   # sem NF
    ("Faturamento Mês NF 3 PLANO EXEMPLO 2013 Set/2026 Protocolo 4", "PLANO EXEMPLO 2013"),
    ("Referente Fundação Exemplo NF. 89592 Nota Fiscal Avulsa", "Fundação Exemplo"),
    ("Referente AME- Ambulatório Exemplo - Cidade NF. 89681 Nota Fiscal Avulsa", "AME- Ambulatório Exemplo - Cidade"),
    ("Referente NFSE 89617 Faturamento convênio Plano Exemplo referente aditivo", ""),            # vai para a C3
    ("Estorno de faturamento", ""),
])
def test_v2_nome_do_historico(historico, nome):
    assert nome_do_historico(historico) == nome


# ---------------------------------------------------------------------------
# V3 — linha da planilha (casos montados)
# ---------------------------------------------------------------------------

def _razao(*historicos_valores) -> Razao:
    conta = ContaRazao("40064", "4.01.05.01.0003", "Convênios Exemplo")
    for numero, (historico, valor) in enumerate(historicos_valores, start=10):
        valor = Decimal(valor)
        conta.lancamentos.append(Lancamento("40064", date(2026, 9, 30), historico, "1",
                                            -valor if valor < 0 else Decimal("0.00"),
                                            valor if valor > 0 else Decimal("0.00"), numero))
    return Razao("razao.xlsx", 2026, 9, [conta])


def _planilha(*nomes) -> Planilha:
    convenios = [LinhaConvenio(nome.strip(), 5 + i) for i, nome in enumerate(nomes)]   # como o leitor
    return Planilha("p.xlsx", "Receita de Convênios 2026", 2026, 4, 2, {m: 2 + m for m in range(1, 13)}, 15,
                    convenios, 5 + len(nomes) + 2, None, None)


def _equivalencias(*pares) -> Equivalencias:
    return Equivalencias("equivalencias.csv", False,
                         [Equivalencia(nome, linha, obs, i) for i, (nome, linha, obs) in enumerate(pares, start=2)])


def _fat(nome: str) -> str:
    return f"Faturamento Mês NF 1 {nome} Set/2026 Protocolo 1"


def test_v3_nome_igual_sem_acento_pontuacao_e_de():
    c = classificar(_razao((_fat("PM de Cidade Exemplo"), "10"), (_fat("Clinica Exemplo LTDA"), "5")),
                    _planilha("PM Cidade Exemplo ", "Clínica Exemplo Ltda."), _equivalencias())
    assert [(d.linha, d.como) for d in c.destinos] == [("PM Cidade Exemplo", COMO_IGUAL),
                                                        ("Clínica Exemplo Ltda.", COMO_IGUAL)]
    assert c.avisos == [] and c.linhas_novas == []


def test_v3_equivalencias_somam_na_mesma_linha_e_debito_diminui():
    c = classificar(_razao((_fat("PM EXEMPLO CONVENIO"), "100"), (_fat("Pref.Munic.Exemplo-UNIDADE"), "20"),
                           ("Referente Ambulatório Exemplo - Cidade NF. 5 Nota", "7"),
                           (_fat("PM EXEMPLO CONVENIO"), "-30")),
                    _planilha("Ambulatório Cidade", "PM Exemplo"),
                    _equivalencias(("PM EXEMPLO CONVENIO", "PM Exemplo", ""),
                                   ("Pref.Munic.Exemplo-UNIDADE", "PM Exemplo", ""),
                                   ("Ambulatório Exemplo - Cidade", "Ambulatório Cidade", "")))
    por_linha = {t.nome: (t.valor, len(t.destinos)) for t in c.linhas if t.destinos}
    assert por_linha == {"Ambulatório Cidade": (Decimal("7"), 1), "PM Exemplo": (Decimal("90"), 3)}
    assert {d.como for d in c.destinos} == {COMO_EQUIVALENCIA}
    assert c.total == Decimal("97")


def test_v3_convenio_novo_ganha_linha_com_aviso():
    c = classificar(_razao((_fat("Convênio Novo"), "40"), (_fat("convenio novo"), "2")), _planilha("Outro"),
                    _equivalencias())
    (nova,) = c.linhas_novas
    assert (nova.nome, nova.valor, nova.linha_planilha) == ("Convênio Novo", Decimal("42"), None)
    assert {d.como for d in c.destinos} == {COMO_NOVA}
    assert "Convênio Novo" in c.avisos[0].mensagem and "42,00" in c.avisos[0].mensagem
    assert c.linhas[-1] is nova                                         # as novas vêm depois das da planilha


def test_v3_nao_identificado_pelo_equivalencias():
    c = classificar(_razao((_fat("PLANO EXEMPLO 2013"), "1000"), (_fat("Outro"), "1")),
                    _planilha("Plano Exemplo SC", "Plano Exemplo HC", "Outro"),
                    _equivalencias(("PLANO EXEMPLO 2013", "NÃO IDENTIFICADO", "SC ou HC: aguardando")))
    assert [(d.linha, d.como) for d in c.nao_identificados] == [("", COMO_NAO_IDENTIFICADO)]
    assert c.nao_identificados[0].obs == "SC ou HC: aguardando"
    assert c.total_nao_identificado == Decimal("1000") and c.linhas_novas == []    # não vira linha nova
    assert c.avisos[-1].erro and "1.000,00" in c.avisos[-1].mensagem


def test_v3_historico_fora_do_padrao():
    c = classificar(_razao(("Referente NFSE 1 Faturamento convênio Plano Exemplo referente aditivo", "30"),
                           ("Referente NFSE 2 Faturamento Clínica Exemplo serviço avulso", "5"),
                           ("Lançamento sem nome conhecido", "1")),
                    _planilha("Plano Exemplo", "Clínica Exemplo"),
                    _equivalencias(("convênio Plano Exemplo referente aditivo", "Plano Exemplo", "aditivo")))
    assert [(d.linha, d.como) for d in c.destinos] == [("Plano Exemplo", COMO_EQUIVALENCIA),
                                                        ("Clínica Exemplo", COMO_DENTRO), ("", COMO_NAO_IDENTIFICADO)]
    assert sum("confira" in a.mensagem for a in c.avisos) == 1          # só o achado pelo nome da planilha


def test_v3_equivalencia_para_linha_que_nao_existe_na_planilha():
    c = classificar(_razao((_fat("Nome Antigo"), "3")), _planilha("Outro"),
                    _equivalencias(("Nome Antigo", "Nome Novo da Planilha", "")))
    assert [t.nome for t in c.linhas_novas] == ["Nome Novo da Planilha"]
    assert "não existe na planilha" in c.avisos[0].mensagem


# ---------------------------------------------------------------------------
# V3 — setembro/2026 real (só totais: nenhum nome real no teste)
# ---------------------------------------------------------------------------

def test_v3_setembro_real_tudo_distribuido():
    pasta = exemplos("2026-09")
    razao = ler_razao(pasta / "Razao Convenios 092026.xlsx")
    planilha = ler_planilha(pasta / "RECEITAS DE CONVÊNIOS 082026.xlsx", 2026)
    c = classificar(razao, planilha, ler_equivalencias(exemplos("config")))
    assert c.total == razao.total == Decimal("3135190.13")             # nada some
    assert len(c.destinos) == len(razao.lancamentos) == 189
    assert sum(1 for t in c.linhas if t.destinos and t.linha_planilha) == 20
    assert len(c.linhas_novas) == 1 and c.linhas_novas[0].valor == Decimal("40652.27")
    assert c.total_nao_identificado == Decimal("1140564.00") and len(c.nao_identificados) == 51   # IAMSPE
    assert not any(d.como == COMO_DENTRO for d in c.destinos)
    assert [a.erro for a in c.avisos] == [False, True]                  # convênio novo; não identificado
