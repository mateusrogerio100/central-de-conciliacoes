"""PlanilhaHM 2: leitura da estrutura da Planilha HM (seções, eventos, CCs, LOTE REPASSE, coluna do mês).

Lê a planilha de agosto (entrada de setembro) e o gabarito de setembro, e uma planilha fictícia.
"""

from __future__ import annotations

import hashlib

import pytest

from modulos.planilha_hm.leitor_planilha import ler_planilha, linhas_da_formula
from modulos.planilha_hm.modelos import ErroLeitura
from testes.planilha_hm.conftest import escrever_planilha, gabarito_totais, planilha_real

# o que o gabarito de setembro acrescentou na aba 2026 (seção 8 da especificação): (evento, CC); "-" = linha do evento
CRIADAS_EM_SETEMBRO = [(2721, "180"), (2736, "78"), (3106, "18"), (3118, "584"), (3118, "70"), (3157, "53"),
                       (3171, "-"), (3171, "78"), (3172, "-"), (3172, "72")]


def _chaves(planilha) -> set[tuple[int, str]]:
    return ({(e.numero, "-") for e in planilha.eventos}
            | {(e.numero, c.codigo) for e in planilha.eventos for c in e.ccs})


@pytest.fixture(scope="module")
def agosto():
    return ler_planilha(planilha_real("2026-08"))


@pytest.fixture(scope="module")
def setembro():
    return ler_planilha(planilha_real("2026-09"))


# ---------------------------------------------------------------------------
# Planilhas reais
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mes", ["2026-08", "2026-09"])
def test_estrutura_bate_com_o_gabarito_de_totais(mes, agosto, setembro):
    planilha = agosto if mes == "2026-08" else setembro
    esperado = gabarito_totais(mes)
    *secoes, (linha_geral, nome_geral), (linha_lote, nome_lote) = esperado
    assert [(s.linha_total, s.nome_total) for s in planilha.secoes if s.linha_total] == secoes
    assert (planilha.linha_total_geral, nome_geral) == (linha_geral, "TOTAL GERAL")
    assert (planilha.linha_lote, nome_lote) == (linha_lote, "LOTE REPASSE")
    assert planilha.linha_diferenca == linha_lote + 1
    assert planilha.avisos == []


def test_colunas_e_abas(agosto):
    assert (agosto.ano, agosto.aba_ano, agosto.linha_titulos) == (2026, "2026", 6)
    assert agosto.colunas == {"EVENTO": 1, "nome": 2, "Concateno": 3, "Cód.": 4, "Centros de Custos": 5}
    assert agosto.colunas_meses == {m: 5 + m for m in range(1, 13)}          # JANEIRO = F ... DEZEMBRO = Q
    assert sorted(agosto.seniors) == list(range(1, 13))


def test_secoes_de_agosto_e_setembro(agosto, setembro):
    nomes_agosto = [s.nome for s in agosto.secoes]
    assert len(nomes_agosto) == 19 and nomes_agosto[0] == "HONORÁRIOS MÉDICOS - FIXOS"
    # a seção nova de setembro fica logo antes do TOTAL GERAL (R6)
    assert [s.nome for s in setembro.secoes] == nomes_agosto + ["HM CATARATA - AGLUTINADA PJ"]
    vazia = next(s for s in agosto.secoes if "PROGRAMA MAIS SANTAS CASAS" in s.nome)
    assert vazia.eventos == [] and vazia.linha_total is None


def test_linhas_criadas_em_setembro_sao_as_da_especificacao(agosto, setembro):
    assert sorted(_chaves(setembro) - _chaves(agosto)) == CRIADAS_EM_SETEMBRO
    assert _chaves(agosto) - _chaves(setembro) == set()
    assert setembro.secao_do_evento(3171).nome == "HONORÁRIOS MÉDICOS - FIXOS"
    assert setembro.secao_do_evento(3172).nome == "HM CATARATA - AGLUTINADA PJ"


def test_cc_sem_codigo_logo_abaixo_do_evento(agosto):
    """Linha com o número do evento e o Cód. vazio, logo abaixo da linha do evento: CC sem código."""
    celular = agosto.evento(2848)
    assert [c.codigo for c in celular.ccs][0] == "" and celular.ccs[0].nome == "A Classificar"
    secao = agosto.secao_do_evento(2848)
    assert celular.linha in secao.linhas_no_total and celular.ccs[0].linha not in secao.linhas_no_total


def test_total_da_secao_soma_as_linhas_de_evento(agosto):
    for secao in agosto.secoes:
        if secao.linha_total:
            assert sorted(secao.linhas_no_total) == sorted(secao.linhas_eventos), secao.nome
    assert agosto.linhas_no_total_geral == sorted(s.linha_total for s in agosto.secoes if s.linha_total)


def test_abas_senior_e_ultima_competencia(agosto, setembro):
    assert agosto.ultima_competencia == 8 and setembro.ultima_competencia == 9
    assert agosto.seniors[8].linhas_dados == 266 and agosto.seniors[9].linhas_dados == 0
    assert setembro.seniors[9].linhas_dados == 264
    # na planilha de agosto, a coluna Conf.1 de "Senior 09 2026" para na linha 245 (seção 2.3)
    assert agosto.seniors[9].ultima_formula == {"Concateno": 321, "Conf.": 321, "Conf.1": 245}


def test_lote_repasse(setembro):
    assert setembro.lote_por_mes[9] == pytest.approx(5794120.73)


def test_planilha_nao_muda(tmp_path):
    caminho = planilha_real("2026-08")
    antes = hashlib.md5(caminho.read_bytes()).hexdigest()
    ler_planilha(caminho)
    assert hashlib.md5(caminho.read_bytes()).hexdigest() == antes


# ---------------------------------------------------------------------------
# Planilha fictícia
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("deslocar", [0, 2])
def test_ficticia(tmp_path, deslocar):
    planilha = ler_planilha(escrever_planilha(tmp_path / "hm.xlsx", deslocar=deslocar, senior_com_dados={8: 2}))
    assert planilha.colunas["EVENTO"] == 1 + deslocar
    assert planilha.colunas_meses[1] == 6 + deslocar
    assert [s.nome for s in planilha.secoes] == ["HONORÁRIOS MÉDICOS - FIXOS", "HONORÁRIOS MÉDICOS - VAZIA",
                                                 "HM DESCONTOS"]
    fixos, vazia, descontos = planilha.secoes
    assert [(e.numero, e.linha, [(c.codigo, c.linha) for c in e.ccs]) for e in fixos.eventos] == [
        (1001, 7, [("10", 8), ("20", 9)]), (1002, 10, [("10", 11)])]
    assert (fixos.linha_total, fixos.linhas_no_total) == (12, [7, 10])
    assert vazia.eventos == [] and vazia.linha_total is None
    assert [(c.codigo, c.nome) for c in descontos.eventos[0].ccs] == [("", "A Classificar"), ("30", "Centro Gama")]
    assert planilha.linhas_no_total_geral == [12, descontos.linha_total]
    assert planilha.linha_lote == planilha.linha_total_geral + 3
    assert planilha.linha_diferenca == planilha.linha_lote + 1
    assert planilha.lote_por_mes == {8: 12345.67}
    assert planilha.ultima_competencia == 8
    assert planilha.avisos == []


def test_total_que_esquece_um_evento_avisa(tmp_path):
    planilha = ler_planilha(escrever_planilha(tmp_path / "hm.xlsx", total_errado=True))
    assert len(planilha.avisos) == 1
    assert planilha.avisos[0].erro and "faltam as linhas [7]" in planilha.avisos[0].mensagem


def test_falta_aba_senior_avisa(tmp_path):
    planilha = ler_planilha(escrever_planilha(tmp_path / "hm.xlsx", abas_senior=range(1, 12)))
    assert [a.erro for a in planilha.avisos] == [True] and "Senior 12 2026" in planilha.avisos[0].mensagem


def test_sem_aba_do_ano(tmp_path):
    caminho = escrever_planilha(tmp_path / "hm.xlsx", abas_senior=[])
    with pytest.raises(ErroLeitura, match="não parece ser a Planilha HM"):
        ler_planilha(caminho)


def test_arquivo_que_nao_e_xlsx(tmp_path):
    caminho = tmp_path / "hm.xlsx"
    caminho.write_bytes(b"nada")
    with pytest.raises(ErroLeitura, match="não foi possível abrir"):
        ler_planilha(caminho)


@pytest.mark.parametrize("formula, coluna, esperado", [
    ("=SUM(N95+N93+N91)", "N", [95, 93, 91]),
    ("=SUM(N1489,N1486)", "N", [1489, 1486]),
    ("=N1647+N1649", "N", [1647, 1649]),
    ("=N1654", "N", [1654]),
    ("=SUMIF('Senior 09 2026'!$A:$A,$C7,'Senior 09 2026'!$D:$D)", "N", []),
    ("=SUMIF('Senior 09 2026'!$A:$A,$C7,'Senior 09 2026'!$D:$D)", "C", [7]),
    ("SETEMBRO", "N", []),
    (None, "N", []),
])
def test_linhas_da_formula(formula, coluna, esperado):
    assert linhas_da_formula(formula, coluna) == esperado
