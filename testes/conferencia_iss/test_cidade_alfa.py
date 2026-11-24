"""
Testes da conferência de Cidade Alfa: leitor do relatório de notas tomadas (CSV), notas
repetidas no relatório (escrituração em dobro), planilha e processar() de ponta a ponta.

- Casos sintéticos: CSVs montados no teste (dados inventados).
- Exemplos reais (exemplos/Exemplos_Cidade_Alfa, competência 09/2026): pula se não existirem.
"""

import shutil
from datetime import datetime
from decimal import Decimal

import pytest
from openpyxl import load_workbook

from modulos.conferencia_iss.processamento import (
    MUNICIPIO_AV,
    MUNICIPIO_CP,
    MUNICIPIO_FR,
    MUNICIPIO_RB,
    MUNICIPIO_SJ,
    MUNICIPIOS,
    conferencia_nada_sumiu,
    numeros_principais,
    previa_prefeitura,
)
from modulos.conferencia_iss.processar import processar
from modulos.conferencia_iss.leitor_prefeitura_fr import ler_relatorio_cidade_alfa
from modulos.conferencia_iss.leitor_tasy import ler_csv_tasy
from modulos.conferencia_iss.modelos import (
    SITUACAO_CONFERIDA_AJUSTADO,
    SITUACAO_DIVERGENCIA,
    situacao_escriturada_varias_vezes,
)
from modulos.conferencia_iss.relatorio_excel import ABA_ESCRITURADAS, ABA_RESUMO
from testes.conferencia_iss.pastas_exemplos import PASTA_FR

AGORA = datetime(2026, 10, 2, 17, 0)
RELATORIO_FR = "resultado_Prefeitura_Cidade_Alfa.csv"

CABECALHO = ("nfs;situacaonf;cnpjcpf;nome;dtemissao;vlrservicos;descratividade;cfps;vlrdeducoes;"
             "descontoincondicionado;basecalculo;aliquota;impretido;vlrimposto;enquadradosn;")


def _linha_csv(numero, valor, situacao="Normal", documento="11.222.333/0001-81",
               emissao="10/09/2026", cfps="1", deducoes="0,00"):
    return (f"{numero};{situacao};{documento};PRESTADOR TESTE LTDA;{emissao};{valor};"
            f"04.01.01  Medicina.;{cfps};{deducoes};{deducoes};{valor};2,00;NÃO;20,00;N;")


def _csv(tmp_path, linhas, cabecalho=CABECALHO, nome="relatorio.csv"):
    """Monta um relatório no formato de Cidade Alfa (Windows-1252, CRLF)."""
    caminho = tmp_path / nome
    caminho.write_bytes("\r\n".join([cabecalho, *linhas, ""]).encode("cp1252"))
    return caminho


# ---------------------------------------------------------------------
# Leitor
# ---------------------------------------------------------------------
def test_leitor_campos(tmp_path):
    caminho = _csv(tmp_path, [
        _linha_csv("98", "1.127,50"),
        _linha_csv("98", "1.127,50", cfps="2", deducoes=""),
        _linha_csv("737", "35.178,24", situacao="Cancelada"),
    ])
    leitura = ler_relatorio_cidade_alfa(caminho)
    assert leitura.erro is None
    assert leitura.avisos == []
    assert leitura.competencia == "2026-09"
    assert leitura.competencia_texto == "setembro/2026"
    assert leitura.inscricao_municipal == "" and leitura.documento_tomador == ""
    primeira, segunda, terceira = leitura.linhas
    assert primeira.documento == "11222333000181"
    assert primeira.numero == "98"
    assert primeira.valor_doc == Decimal("1127.50")
    assert primeira.imp_ret == "NÃO"
    assert primeira.valor_deducoes == Decimal("0.00")
    assert segunda.valor_deducoes is None and segunda.cfps == "2"
    assert terceira.cancelada and not primeira.cancelada


def test_competencia_pelo_mes_que_mais_aparece(tmp_path):
    caminho = _csv(tmp_path, [_linha_csv("1", "10,00"), _linha_csv("2", "10,00"),
                              _linha_csv("3", "10,00", emissao="30/08/2026")])
    leitura = ler_relatorio_cidade_alfa(caminho)
    assert leitura.competencia == "2026-09"
    assert any("08/2026" in a.mensagem for a in leitura.avisos)


def test_valor_invalido_avisa_e_linha_fica(tmp_path):
    leitura = ler_relatorio_cidade_alfa(_csv(tmp_path, [_linha_csv("1", "abc")]))
    assert len(leitura.linhas) == 1 and leitura.linhas[0].valor_doc is None
    assert any("vlrservicos inválido" in a.mensagem for a in leitura.avisos)


def test_situacao_desconhecida_avisa(tmp_path):
    leitura = ler_relatorio_cidade_alfa(_csv(tmp_path, [_linha_csv("1", "10,00", situacao="Substituída")]))
    assert not leitura.linhas[0].cancelada
    assert any("Substituída" in a.mensagem for a in leitura.avisos)


def test_sem_coluna_obrigatoria(tmp_path):
    leitura = ler_relatorio_cidade_alfa(_csv(tmp_path, [], cabecalho=CABECALHO.replace("cnpjcpf", "doc")))
    assert "cnpjcpf" in leitura.erro
    assert leitura.linhas == []


def test_relatorio_de_cidade_alfa_no_cartao_do_tasy(tmp_path):
    leitura = ler_csv_tasy(_csv(tmp_path, [_linha_csv("1", "10,00")]))
    assert "Prefeitura de Cidade Alfa" in leitura.erro and "aba Cidade Alfa" in leitura.erro


# ---------------------------------------------------------------------
# Ponta a ponta com os exemplos reais
# ---------------------------------------------------------------------
pula_sem_exemplos = pytest.mark.skipif(not PASTA_FR.exists(),
                                       reason="exemplos/Exemplos_Cidade_Alfa não existe")


@pytest.fixture
def pasta_fr(tmp_path):
    for arquivo in PASTA_FR.glob("*.csv"):
        shutil.copy(arquivo, tmp_path / arquivo.name)
    return tmp_path


def _processar(pasta):
    tasy = sorted(p for p in pasta.glob("*.csv") if p.name != RELATORIO_FR)
    return processar(tasy, pasta / RELATORIO_FR, agora=AGORA, municipio=MUNICIPIO_FR)


@pula_sem_exemplos
def test_gabarito_cidade_alfa(pasta_fr):                                    # gabarito 8.7
    r = _processar(pasta_fr)
    assert r.erro is None
    assert r.competencia == "2026-09"
    assert r.unidades == ["Ambulatório Médico de Especialidades"]
    assert len(r.notas_tasy) == 167
    assert len(r.linhas_prefeitura) == 155
    numeros = numeros_principais(r)
    assert numeros.conferidas == 109
    assert numeros.somente_tasy == 41
    assert numeros.para_analisar == 21
    assert numeros.divergencias == 1
    assert numeros.escrituradas == 16
    assert numeros.somente_prefeitura == 4
    assert numeros.canceladas_com_tasy == 0
    assert numeros.canceladas_sem_tasy == 9
    assert conferencia_nada_sumiu(r) == ((167, 167), (155, 155))
    assert [a for a in r.avisos if not a.tipo_arquivo] == []
    por_numero = {i.nota_tasy.numero: i for i in r.itens if i.nota_tasy}
    assert por_numero["27"].situacao == SITUACAO_DIVERGENCIA
    assert por_numero["27"].diferenca == Decimal("2966.24") - Decimal("13073.00")
    assert por_numero["2026000000033"].situacao == SITUACAO_CONFERIDA_AJUSTADO
    assert por_numero["98"].situacao == situacao_escriturada_varias_vezes(2)


@pula_sem_exemplos
def test_planilha_cidade_alfa(pasta_fr):
    r = _processar(pasta_fr)
    assert r.caminho_relatorio.name == (
        "Conferencia_ISS_FR_2026-09_Ambulatorio_Medico_de_Especialidades_17h00.xlsx")
    livro = load_workbook(r.caminho_relatorio)
    resumo = livro[ABA_RESUMO]
    assert resumo["A1"].value == "Conferência ISS Cidade Alfa"
    rotulos = [linha[0] for linha in resumo.iter_rows(values_only=True)]
    assert "Inscrição municipal" not in rotulos and "CNPJ da unidade" not in rotulos
    escrituradas = livro[ABA_ESCRITURADAS]
    titulos = [c.value for c in escrituradas[2]]
    assert escrituradas.max_row - 2 == 32
    # nº 98: as duas linhas diferem no CFPS e nas deduções ("0,00" × vazio)
    cfps, deducoes = titulos.index("CFPS"), titulos.index("Deduções")
    nota_98 = [l for l in escrituradas.iter_rows(min_row=3, values_only=True) if l[3] == "98"]
    assert sorted((l[cfps], l[deducoes]) for l in nota_98) == [("1", 0), ("2", None)]


@pula_sem_exemplos
def test_previa_cidade_alfa():
    previa = previa_prefeitura(PASTA_FR / RELATORIO_FR, municipio=MUNICIPIO_FR)
    assert previa.erro is None
    assert previa.linhas == 155
    assert previa.competencia_texto == "setembro/2026"


@pula_sem_exemplos
@pytest.mark.parametrize("codigo", [MUNICIPIO_RB, MUNICIPIO_SJ, MUNICIPIO_AV, MUNICIPIO_CP])
def test_relatorio_de_cidade_alfa_no_item_de_outra_cidade(codigo):
    leitura = MUNICIPIOS[codigo].ler_relatorio(PASTA_FR / RELATORIO_FR)
    assert "aba Cidade Alfa" in leitura.erro


@pula_sem_exemplos
def test_csv_do_tasy_no_item_cidade_alfa():
    csv_tasy = next(p for p in PASTA_FR.glob("Notas*.csv"))
    leitura = ler_relatorio_cidade_alfa(csv_tasy)
    assert "CSV do Tasy" in leitura.erro


@pula_sem_exemplos
def test_previa_cidade_alfa_sem_identificacao_da_unidade():
    """A tela mostra só competência e linhas: o relatório de Cidade Alfa não identifica a unidade."""
    previa = previa_prefeitura(PASTA_FR / RELATORIO_FR, municipio=MUNICIPIO_FR)
    assert previa.inscricao_municipal == "" and previa.documento_tomador == ""
    assert MUNICIPIOS[MUNICIPIO_FR].identificacao == ""
