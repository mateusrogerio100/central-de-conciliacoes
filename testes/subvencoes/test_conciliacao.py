"""Testes da conciliação (R1–R9).

A conciliação não lê planilhas; as linhas de conta de cada aba vêm do gabarito
(aba, linha, código, convênio). A leitura das planilhas é testada na Etapa 4.
"""

from decimal import Decimal

import pytest

from modulos.subvencoes.conciliacao import (
    SITUACAO_CABECALHO_AUSENTE,
    SITUACAO_NAO_USADA,
    SITUACAO_TOTAL_DIVERGENTE,
    SITUACAO_USADA,
    conciliar,
    situacao_conta_patrimonio,
)
from modulos.subvencoes.leitor_balancete import ler_balancete
from modulos.subvencoes.leitor_patrimonio import ler_patrimonio
from modulos.subvencoes.modelos import (
    AbaPlanilha,
    Balancete,
    ContaBalancete,
    ContaPatrimonio,
    Gravidade,
    ItemPatrimonio,
    LinhaPlanilha,
    PlanilhaLida,
    RelatorioPatrimonio,
)
from modulos.subvencoes.utilitarios import normalizar_texto
from testes.subvencoes.conftest import arquivos_do_mes, ler_gabarito


def planilhas_do_gabarito(arquivos, gabarito) -> list[PlanilhaLida]:
    nomes_arquivo = {"Subvenções_Investimento": arquivos.subvencoes.name, "Projetos": arquivos.projetos.name}
    planilhas: dict[str, PlanilhaLida] = {}
    for linha in gabarito:
        arquivo = nomes_arquivo[linha["planilha"]]
        planilha = planilhas.setdefault(arquivo, PlanilhaLida(arquivo=arquivo))
        aba = next((a for a in planilha.abas if a.nome == linha["aba"]), None)
        if aba is None:
            aba = AbaPlanilha(nome=linha["aba"])
            planilha.abas.append(aba)
        aba.linhas.append(LinhaPlanilha(linha["linha"], linha["conta_contabil"], linha["convenio"]))
    return list(planilhas.values())


@pytest.fixture
def cenario(arquivos):
    gabarito = ler_gabarito(arquivos.gabarito)
    balancete = ler_balancete(arquivos.balancete)
    patrimonio = ler_patrimonio(arquivos.patrimonio)
    resultado = conciliar(balancete, patrimonio, planilhas_do_gabarito(arquivos, gabarito))
    return gabarito, balancete, patrimonio, resultado


# ---------------------------------------------------------------------------
# Exemplos reais x gabarito
# ---------------------------------------------------------------------------


def test_valores_iguais_ao_gabarito(cenario):
    gabarito, _, _, resultado = cenario
    assert len(resultado.linhas) == len(gabarito) == 123
    divergencias = []
    for esperado, obtido in zip(gabarito, resultado.linhas):
        assert (obtido.aba, obtido.linha, obtido.conta_contabil) == \
               (esperado["aba"], esperado["linha"], esperado["conta_contabil"])
        if (obtido.saldo_patrimonio, obtido.saldo_contabil) != \
                (esperado["saldo_patrimonio"], esperado["saldo_contabil"]):
            divergencias.append(
                f"{esperado['aba']} linha {esperado['linha']} conta {esperado['conta_contabil']}: "
                f"esperado SP={esperado['saldo_patrimonio']} SC={esperado['saldo_contabil']}, "
                f"obtido SP={obtido.saldo_patrimonio} SC={obtido.saldo_contabil}"
            )
    assert divergencias == []


def test_quantidade_de_linhas_por_aba(cenario):
    _, _, _, resultado = cenario
    por_aba = {}
    for linha in resultado.linhas:
        por_aba[linha.aba] = por_aba.get(linha.aba, 0) + 1
    assert por_aba == {"Federal Investimento": 71, "Estadual Investimento": 30,
                       "Municipal Investimento": 7, "PROJETOS 1": 15}


def test_r9_bate_nas_quatro_abas(cenario):
    _, _, _, resultado = cenario
    assert len(resultado.conferencias_aba) == 4
    sinteticas = {}
    for conferencia in resultado.conferencias_aba:
        assert conferencia.confere, f"{conferencia.aba}: {conferencia.soma_saldo_contabil}"
        sinteticas[conferencia.aba] = conferencia.sintetica.classificacao
    assert sinteticas == {"Federal Investimento": "2.02.06.01", "Estadual Investimento": "2.02.06.03",
                          "Municipal Investimento": "2.02.06.04", "PROJETOS 1": "2.02.06.09"}


def test_avisos_de_r5(cenario):
    """Avisos R5 x gabarito e arquivos de origem.

    A coluna 'observacao' do gabarito é informativa e nem sempre está preenchida
    (em agosto, 201675, 292989 e 292674 têm Saldo Patrimônio 0 sem observação).
    Por isso: toda observação do gabarito precisa ter o aviso, e todo aviso
    'sem bens' precisa ser de uma conta que de fato não existe no patrimônio.
    """
    gabarito, balancete, patrimonio, resultado = cenario
    por_conta = {str(l["conta_contabil"]): l for l in gabarito}
    obtidos = {(a.tipo, a.conta) for a in resultado.avisos}
    assert all(a.gravidade == Gravidade.ATENCAO for a in resultado.avisos)
    assert {t for t, _ in obtidos} <= {"conta fora do balancete", "conta sem bens no patrimônio"}

    for linha in gabarito:
        conta = str(linha["conta_contabil"])
        if "fora do balancete" in linha["observacao"]:
            assert ("conta fora do balancete", conta) in obtidos
        if "sem bens no patrimonio" in linha["observacao"]:
            assert ("conta sem bens no patrimônio", conta) in obtidos

    nomes_patrimonio = {normalizar_texto(c.nome) for c in patrimonio.contas}
    for tipo, conta in obtidos:
        esperado = por_conta[conta]
        assert esperado["saldo_patrimonio"] == 0
        if tipo == "conta fora do balancete":
            assert int(conta) not in balancete.contas
            assert esperado["saldo_contabil"] == 0
        else:
            assert normalizar_texto(balancete.contas[int(conta)].descricao) not in nomes_patrimonio


def test_sem_conta_nova_nos_exemplos(cenario):
    """R7: todas as analíticas (exceto Doações) têm linha nas planilhas; Doações não geram aviso."""
    _, balancete, _, resultado = cenario
    assert not [a for a in resultado.avisos if a.tipo == "conta nova no balancete"]
    doacoes = [c for c in balancete.analiticas() if c.classificacao.startswith("2.02.06.08")]
    assert doacoes


def test_situacao_das_contas_do_patrimonio(cenario, mes_exemplo):
    _, _, patrimonio, resultado = cenario
    situacoes = {normalizar_texto(c.nome): situacao_conta_patrimonio(c, resultado) for c in patrimonio.contas}
    for nome in ["Bens em Comodato", "Doações Imobilizado a realizar", "Doações Pró Vida"]:
        assert situacoes[normalizar_texto(nome)] == SITUACAO_NAO_USADA   # R8
    assert situacoes[normalizar_texto("Convênio Federal 773671/2012")] == SITUACAO_USADA
    if mes_exemplo == "2026-07":
        assert situacoes[normalizar_texto("Convenio Federal 773672/2012")] == SITUACAO_CABECALHO_AUSENTE
    else:
        assert situacoes[normalizar_texto("Convênio Federal 775214/2012")] == SITUACAO_TOTAL_DIVERGENTE


def test_observacoes_dos_casos_especiais():
    arquivos = arquivos_do_mes("2026-08")
    gabarito = ler_gabarito(arquivos.gabarito)
    resultado = conciliar(ler_balancete(arquivos.balancete), ler_patrimonio(arquivos.patrimonio),
                          planilhas_do_gabarito(arquivos, gabarito))
    linha = next(l for l in resultado.linhas if l.conta_contabil == 25195)
    assert "soma dos bens" in linha.observacao
    assert linha.diferenca == Decimal("0.00")


# ---------------------------------------------------------------------------
# Casos construídos
# ---------------------------------------------------------------------------


def _balancete():
    contas = [
        ContaBalancete(1, "2.02.06.01", "SUBVENÇÃO FEDERAL", Decimal("300.00"), 1),
        ContaBalancete(10, "2.02.06.01.0001", "Convênio Federal 1/2020 ", Decimal("100.00"), 2),
        ContaBalancete(11, "2.02.06.01.0002", "Convenio Federal 2/2020", Decimal("200.00"), 3),
        ContaBalancete(2, "2.02.06.03", "SUBVENÇÃO ESTADUAL", Decimal("50.00"), 4),
        ContaBalancete(20, "2.02.06.03.0001", "Convênio Estadual 1/2020", Decimal("50.00"), 5),
        ContaBalancete(8, "2.02.06.08", "DOAÇÕES", Decimal("7.00"), 6),
        ContaBalancete(80, "2.02.06.08.0001", "Doações Pró Vida", Decimal("7.00"), 7),
    ]
    return Balancete(arquivo="Balancete.xlsx", mes_referencia=None, contas={c.codigo: c for c in contas})


def _patrimonio():
    def conta(nome, *valores):
        itens = [ItemPatrimonio(str(i), "bem", Decimal(v), i) for i, v in enumerate(valores)]
        return ContaPatrimonio(nome=nome, itens=itens)
    return RelatorioPatrimonio(arquivo="patrimonio.xlsx", mes_referencia=None, contas=[
        conta("CONVENIO FEDERAL 1/2020", "60.00", "30.00"),     # nome com caixa/acento diferentes
        conta("Convênio Estadual 1/2020", "45.50"),
        conta("Bens em Comodato", "999.00"),
    ])


def _planilha(*abas):
    return [PlanilhaLida("Subvenções_09-2026.xlsx",
                         [AbaPlanilha(nome, [LinhaPlanilha(5 + i, c, f"conv {c}") for i, c in enumerate(codigos)])
                          for nome, codigos in abas])]


def test_regras_r1_a_r5_e_r8():
    resultado = conciliar(_balancete(), _patrimonio(), _planilha(("Federal", [10, 11, 99]), ("Estadual", [20])))
    valores = {l.conta_contabil: (l.saldo_patrimonio, l.saldo_contabil) for l in resultado.linhas}
    assert valores == {
        10: (Decimal("90.00"), Decimal("100.00")),     # R2 normalizado + R4 soma dos bens
        11: (Decimal("0.00"), Decimal("200.00")),      # R5: sem conta no patrimônio
        99: (Decimal("0.00"), Decimal("0.00")),        # R5: fora do balancete
        20: (Decimal("45.50"), Decimal("50.00")),
    }
    tipos = sorted((a.tipo, a.conta) for a in resultado.avisos)
    assert ("conta fora do balancete", "99") in tipos
    assert ("conta sem bens no patrimônio", "11") in tipos
    fora = next(a for a in resultado.avisos if a.conta == "99")
    assert (fora.arquivo, fora.aba, fora.linha) == ("Subvenções_09-2026.xlsx", "Federal", 7)
    assert resultado.contas_patrimonio_usadas == {"convenio federal 1/2020", "convenio estadual 1/2020"}


def test_r7_conta_nova_e_doacoes_ignoradas():
    resultado = conciliar(_balancete(), _patrimonio(), _planilha(("Federal", [10]), ("Estadual", [20])))
    novas = [a for a in resultado.avisos if a.tipo == "conta nova no balancete"]
    assert [a.conta for a in novas] == ["11"]                      # 80 (Doações) não gera aviso
    assert all(l.conta_contabil != 11 for l in resultado.linhas)   # nenhuma linha criada


def test_r9_confere_e_nao_confere():
    ok = conciliar(_balancete(), _patrimonio(), _planilha(("Federal", [10, 11]), ("Estadual", [20])))
    assert all(c.confere for c in ok.conferencias_aba)
    assert not [a for a in ok.avisos if a.tipo == "conferência da aba não bate"]

    faltando = conciliar(_balancete(), _patrimonio(), _planilha(("Federal", [10]), ("Estadual", [20])))
    federal = next(c for c in faltando.conferencias_aba if c.aba == "Federal")
    assert not federal.confere
    avisos = [a for a in faltando.avisos if a.tipo == "conferência da aba não bate"]
    assert [a.aba for a in avisos] == ["Federal"]
    assert "-200.00" in avisos[0].mensagem


def test_r9_contas_de_mais_de_uma_sintetica():
    resultado = conciliar(_balancete(), _patrimonio(), _planilha(("Mista", [10, 11, 20])))
    avisos = [a for a in resultado.avisos if a.tipo == "conferência da aba não bate"]
    assert len(avisos) == 1 and "mais de uma" in avisos[0].mensagem


def test_r9_aba_so_com_contas_fora_do_balancete():
    resultado = conciliar(_balancete(), _patrimonio(), _planilha(("Federal", [10, 11]), ("Velha", [98, 99])))
    avisos = [a for a in resultado.avisos if a.tipo == "conferência da aba não bate"]
    assert [a.aba for a in avisos] == ["Velha"]


def test_situacoes_do_patrimonio():
    patrimonio = _patrimonio()
    patrimonio.contas.append(ContaPatrimonio("Sem cabeçalho", cabecalho_ausente=True))
    patrimonio.contas.append(ContaPatrimonio(
        "Total errado", itens=[ItemPatrimonio("1", "bem", Decimal("1.00"), 1)],
        total_sistema=Decimal("0.00"), quantidade_sistema=1))
    resultado = conciliar(_balancete(), patrimonio, _planilha(("Federal", [10, 11])))
    situacoes = [situacao_conta_patrimonio(c, resultado) for c in patrimonio.contas]
    assert situacoes == [SITUACAO_USADA, SITUACAO_NAO_USADA, SITUACAO_NAO_USADA,
                         SITUACAO_CABECALHO_AUSENTE, SITUACAO_TOTAL_DIVERGENTE]


def test_conta_repetida_no_patrimonio_soma_os_blocos():
    """Decisão do usuário: nome repetido no patrimônio -> soma dos blocos."""
    patrimonio = _patrimonio()
    patrimonio.contas.append(ContaPatrimonio(
        "Convênio Federal 1/2020", itens=[ItemPatrimonio("9", "bem", Decimal("10.00"), 50)]))
    resultado = conciliar(_balancete(), patrimonio, _planilha(("Federal", [10, 11])))
    linha = next(l for l in resultado.linhas if l.conta_contabil == 10)
    assert linha.saldo_patrimonio == Decimal("100.00")          # 60 + 30 + 10
    assert "2 blocos somados" in linha.observacao
    situacoes = [situacao_conta_patrimonio(c, resultado) for c in patrimonio.contas]
    assert situacoes[0] == situacoes[-1] == SITUACAO_USADA


def test_codigo_repetido_nas_planilhas_preenche_todas_e_avisa():
    """Decisão do usuário: mesmo código em mais de uma linha -> todas preenchidas + aviso."""
    planilhas = _planilha(("Federal", [10, 11, 10]))
    planilhas.append(PlanilhaLida("Projetos_09-2026.xlsx", [AbaPlanilha("PROJETOS 1", [LinhaPlanilha(9, 10)])]))
    resultado = conciliar(_balancete(), _patrimonio(), planilhas)

    repetidas = [l for l in resultado.linhas if l.conta_contabil == 10]
    assert len(repetidas) == 3
    assert all((l.saldo_patrimonio, l.saldo_contabil) == (Decimal("90.00"), Decimal("100.00")) for l in repetidas)
    assert all("código repetido" in l.observacao for l in repetidas)

    avisos = [a for a in resultado.avisos if a.tipo == "código repetido nas planilhas"]
    assert len(avisos) == 1
    assert avisos[0].conta == "10"
    for trecho in ["3 linhas", "Federal / linha 5", "Federal / linha 7", "PROJETOS 1 / linha 9"]:
        assert trecho in avisos[0].mensagem
    # a soma da aba Federal passa a contar a conta 10 duas vezes -> R9 acusa
    assert any(a.tipo == "conferência da aba não bate" and a.aba == "Federal" for a in resultado.avisos)
