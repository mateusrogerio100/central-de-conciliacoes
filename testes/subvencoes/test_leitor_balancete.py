import datetime
from decimal import Decimal

import openpyxl
import pytest

from modulos.subvencoes.leitor_balancete import ler_balancete
from modulos.subvencoes.modelos import ErroArquivo, Gravidade, MesReferencia
from testes.subvencoes.conftest import arquivos_do_mes, ler_gabarito

SINTETICAS_DAS_PLANILHAS = ["2.02.06.01", "2.02.06.03", "2.02.06.04", "2.02.06.09"]


# ---------------------------------------------------------------------------
# Exemplos reais
# ---------------------------------------------------------------------------


def test_mes_de_referencia(arquivos, mes_exemplo):
    balancete = ler_balancete(arquivos.balancete)
    ano, mes = map(int, mes_exemplo.split("-"))
    assert balancete.mes_referencia == MesReferencia(ano, mes)


def test_sem_avisos_nos_exemplos(arquivos):
    balancete = ler_balancete(arquivos.balancete)
    assert balancete.avisos == []


@pytest.mark.parametrize("classificacao", SINTETICAS_DAS_PLANILHAS + ["2.02.06.08"])
def test_sintetica_igual_soma_das_analiticas(arquivos, classificacao):
    balancete = ler_balancete(arquivos.balancete)
    sintetica = balancete.por_classificacao(classificacao)
    assert sintetica is not None, f"sintética {classificacao} não encontrada"
    assert not sintetica.analitica
    filhas = balancete.filhas(classificacao)
    assert filhas
    assert sum(c.saldo_atual for c in filhas) == sintetica.saldo_atual


def test_grupo_2_02_06_igual_soma_das_sinteticas(arquivos):
    balancete = ler_balancete(arquivos.balancete)
    grupo = balancete.por_classificacao("2.02.06")
    sinteticas = [c for c in balancete.sinteticas() if c.classificacao_pai == "2.02.06"]
    assert sum(c.saldo_atual for c in sinteticas) == grupo.saldo_atual


def test_conta_lida_por_completo():
    balancete = ler_balancete(arquivos_do_mes("2026-07").balancete)
    conta = balancete.contas[24876]
    assert conta.classificacao == "2.02.06.01.0020"
    assert conta.descricao == "Convenio Federal 773672/2012"
    assert conta.saldo_atual == Decimal("569.57")
    assert conta.analitica
    assert conta.classificacao_pai == "2.02.06.01"
    # espaço no fim da descrição é removido
    assert balancete.contas[200781].descricao == "Convênio Federal 937610/2022"


def test_saldo_atual_confere_com_gabarito(arquivos):
    """Todo código do gabarito que está no balancete tem o Saldo Atual igual ao Saldo Contábil esperado;
    os que não estão têm Saldo Contábil 0 no gabarito (R5)."""
    balancete = ler_balancete(arquivos.balancete)
    for linha in ler_gabarito(arquivos.gabarito):
        conta = balancete.contas.get(linha["conta_contabil"])
        esperado = linha["saldo_contabil"]
        if conta is None:
            assert esperado == 0, f"{linha['conta_contabil']} fora do balancete mas gabarito = {esperado}"
        else:
            assert conta.saldo_atual == esperado, f"conta {linha['conta_contabil']}"


def test_colunas_extras_de_julho_sao_ignoradas(tmp_path):
    """Julho tem colunas de conferência (N–R) à direita do Saldo Atual.
    O resultado deve ser igual ao do mesmo arquivo sem essas colunas."""
    original = arquivos_do_mes("2026-07").balancete
    pasta = openpyxl.load_workbook(original)
    aba = pasta.worksheets[0]
    assert aba.max_column > 13, "o exemplo de julho deveria ter colunas extras"
    aba.delete_cols(14, aba.max_column - 13)  # tudo à direita de M (Saldo Atual)
    sem_extras = tmp_path / "balancete_sem_extras.xlsx"
    pasta.save(sem_extras)

    com = ler_balancete(original)
    sem = ler_balancete(sem_extras)
    assert com.contas == sem.contas
    assert com.mes_referencia == sem.mes_referencia
    assert com.avisos == sem.avisos == []


def test_lixo_a_direita_do_saldo_atual_e_ignorado(tmp_path):
    """Classificações, textos e números colocados à direita do Saldo Atual não mudam nada."""
    original = arquivos_do_mes("2026-08").balancete
    pasta = openpyxl.load_workbook(original)
    aba = pasta.worksheets[0]
    for linha in range(1, aba.max_row + 1):
        aba.cell(linha, 14, "9.99.99.99.9999")
        aba.cell(linha, 15, 123456.78)
        aba.cell(linha, 16, "Saldo Atual" if linha == 20 else "texto")
    alterado = tmp_path / "balancete_lixo.xlsx"
    pasta.save(alterado)
    assert ler_balancete(alterado).contas == ler_balancete(original).contas


# ---------------------------------------------------------------------------
# Casos construídos (não dependem dos exemplos)
# ---------------------------------------------------------------------------


def _balancete_minimo(caminho, titulos=True, mes=datetime.datetime(2026, 9, 1)):
    pasta = openpyxl.Workbook()
    aba = pasta.active
    aba["A1"] = "Fundação Hospital Exemplo"
    aba["A2"] = "Balancete"
    aba["G3"] = "Mês Referência:"
    aba["I3"] = mes
    if titulos:
        for celula, texto in {"B4": "Código", "D4": "Classificação", "F4": "Descrição",
                              "J4": "Saldo Anterior", "L4": "Movimento", "M4": "Saldo Atual"}.items():
            aba[celula] = texto
    dados = [
        (5, 23056, "2.02.06.01", "SUBVENÇÃO FEDERAL", 300.00),
        (6, 24876, "2.02.06.01.0020", "  Convenio Federal 773672/2012 ", 100.10),
        (7, 24870, "2.02.06.01.0022", "Convênio Federal 773671/2012", 199.90),
    ]
    for linha, codigo, classificacao, descricao, saldo in dados:
        aba.cell(linha, 3, codigo)
        aba.cell(linha, 5, classificacao)
        aba.cell(linha, 6, descricao)
        aba.cell(linha, 10, 1.0)
        aba.cell(linha, 13, saldo)
    aba["B8"] = "Impresso em: 01/10/2026 08:00:00"
    aba["H8"] = "Página: 1"
    pasta.save(caminho)
    return caminho


def test_balancete_minimo(tmp_path):
    balancete = ler_balancete(_balancete_minimo(tmp_path / "b.xlsx"))
    assert balancete.mes_referencia == MesReferencia(2026, 9)
    assert set(balancete.contas) == {23056, 24876, 24870}
    assert balancete.contas[24876].descricao == "Convenio Federal 773672/2012"
    assert balancete.contas[24876].saldo_atual == Decimal("100.10")
    assert [c.codigo for c in balancete.analiticas()] == [24876, 24870]
    assert balancete.avisos == []


def test_mes_em_texto(tmp_path):
    balancete = ler_balancete(_balancete_minimo(tmp_path / "b.xlsx", mes="01/10/2026"))
    assert balancete.mes_referencia == MesReferencia(2026, 10)


def test_sem_titulo_saldo_atual_e_erro_de_arquivo(tmp_path):
    with pytest.raises(ErroArquivo, match="Saldo Atual"):
        ler_balancete(_balancete_minimo(tmp_path / "b.xlsx", titulos=False))


def test_linha_sem_codigo_ou_sem_saldo_vira_erro(tmp_path):
    caminho = _balancete_minimo(tmp_path / "b.xlsx")
    pasta = openpyxl.load_workbook(caminho)
    aba = pasta.active
    aba["C6"] = None          # conta sem código
    aba["M7"] = None          # conta sem saldo
    pasta.save(caminho)
    balancete = ler_balancete(caminho)
    assert set(balancete.contas) == {23056}
    assert len(balancete.avisos) == 2
    assert all(a.gravidade == Gravidade.ERRO and a.tipo == "linha não reconhecida" for a in balancete.avisos)
    assert {a.linha for a in balancete.avisos} == {6, 7}


def test_codigo_repetido_gera_aviso(tmp_path):
    caminho = _balancete_minimo(tmp_path / "b.xlsx")
    pasta = openpyxl.load_workbook(caminho)
    aba = pasta.active
    aba["C7"] = 24876
    pasta.save(caminho)
    balancete = ler_balancete(caminho)
    assert balancete.contas[24876].linha == 6
    assert [a.tipo for a in balancete.avisos] == ["código repetido no balancete"]


def test_sem_mes_referencia_gera_aviso(tmp_path):
    caminho = _balancete_minimo(tmp_path / "b.xlsx")
    pasta = openpyxl.load_workbook(caminho)
    pasta.active["G3"] = None
    pasta.active["I3"] = None
    pasta.save(caminho)
    balancete = ler_balancete(caminho)
    assert balancete.mes_referencia is None
    assert [a.tipo for a in balancete.avisos] == ["mês não encontrado"]
