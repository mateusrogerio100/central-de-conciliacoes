"""
Testes da conferência de Cidade Epsilon: leitor do Relatório de Serviços Tomados,
regra das notas canceladas na prefeitura, planilha e processar() de ponta a ponta.

- Casos sintéticos: planilhas .xlsx montadas no teste (dados inventados).
- Exemplos reais (exemplos/Exemplos_SJ, competência 09/2026): pula se não existirem.
"""

import shutil
from datetime import datetime
from decimal import Decimal

import pytest
from openpyxl import Workbook, load_workbook

from modulos.conferencia_iss.processamento import (
    MUNICIPIO_RB,
    MUNICIPIO_SJ,
    numeros_principais,
    previa_prefeitura,
)
from modulos.conferencia_iss.processar import processar
from modulos.conferencia_iss.comparador import comparar
from modulos.conferencia_iss.leitor_prefeitura_sj import ler_relatorio_cidade_epsilon
from modulos.conferencia_iss.modelos import (
    SITUACAO_CANCELADA_COM_TASY,
    SITUACAO_CANCELADA_SEM_TASY,
    SITUACAO_CONFERIDA,
    SITUACAO_CONFERIDA_AJUSTADO,
    SITUACAO_CONFERIDA_SEM_CPF,
    SITUACAO_DIVERGENCIA,
    SITUACAO_SOMENTE_PREFEITURA,
    SITUACAO_SOMENTE_TASY,
    Resultado,
    situacao_escriturada_varias_vezes,
)
from modulos.conferencia_iss.processar import nome_do_relatorio
from modulos.conferencia_iss.relatorio_excel import (
    ABA_AVISOS,
    ABA_CANCELADAS,
    ABA_CONFERIDAS,
    ABA_DIVERGENCIA,
    ABA_ESCRITURADAS,
    ABA_RESUMO,
    ABA_SOMENTE_PREFEITURA,
    ABA_SOMENTE_TASY,
    gerar_relatorio,
)
from modulos.conferencia_iss.resumo import linhas_do_resumo
from testes.conferencia_iss.pastas_exemplos import PASTA_EXEMPLOS, PASTA_RB, PASTA_SJ, caso_real
from testes.conferencia_iss.test_comparador import linha, nota, situacoes

AGORA = datetime(2026, 10, 2, 9, 30)
CSV_PJ = "Notas fiscais PJ_SJ.csv"
CSV_HN = "Notas fiscais SJ_HN.csv"
RELATORIO_SJ = "nfe SJ.xls"

CABECALHO = [
    "Competência", "Dia", "Mês", "Ano", "Nº Nota", "Atividade", "Situação NF", "CNPJ/CPF",
    "Razão Social / Nome", "Vlr. Nota", "Vlr. Deduções", "Base Cálculo", "Alíquota",
    "Incidência Fora", "Retido", "Imposto", "Data Emissão", "Chave Acesso",
]


def _linha_planilha(numero, valor, situacao="Normal", documento="11.222.333/0001-81",
                    competencia="09/2026"):
    return [competencia, 1, 9, 2026, numero, "04.01.02", situacao, documento,
            "PRESTADOR TESTE LTDA", valor, 0, valor, 2.5, "Não", "Não", 1.5, "01/09/2026",
            "3549" + "0" * 46]


def _planilha(tmp_path, linhas, cabecalho=CABECALHO, nome="relatorio.xlsx",
              inscricao="Inscrição Municipal: 35882"):
    """Monta um relatório no formato de Cidade Epsilon (salvo como .xlsx)."""
    livro = Workbook()
    aba = livro.active
    aba.append(["Relatório de Serviços Tomados"])
    aba.append([])
    aba.append(["FUNDACAO HOSPITAL EXEMPLO"])
    aba.append([inscricao])
    aba.append([])
    aba.append(["Detalhes"])
    aba.append(cabecalho)
    for linha_ in linhas:
        aba.append(linha_)
    caminho = tmp_path / nome
    livro.save(caminho)
    return caminho


def _exige_exemplos_sj():
    if not (PASTA_SJ / RELATORIO_SJ).exists():
        pytest.skip("exemplos de Cidade Epsilon não existem (dados reais ficam fora do git)")


# ---------------------------------------------------------------------
# Leitor — casos sintéticos
# ---------------------------------------------------------------------
def test_le_planilha_sintetica(tmp_path):
    caminho = _planilha(tmp_path, [
        _linha_planilha(634.0, 667.0),
        _linha_planilha(100022673, 493.12, situacao="Cancelada"),
    ])
    leitura = ler_relatorio_cidade_epsilon(caminho)
    assert leitura.erro is None
    assert leitura.avisos == []
    assert leitura.inscricao_municipal == "35882"
    assert leitura.competencia == "2026-09"
    assert leitura.competencia_texto == "setembro/2026"
    assert len(leitura.linhas) == 2

    primeira, segunda = leitura.linhas
    assert primeira.numero_doc == "634"                  # 634.0 da planilha vira "634"
    assert primeira.numero == "634"
    assert primeira.documento == "11222333000181"
    assert primeira.valor_doc == Decimal("667.00")
    assert primeira.aliquota == "2,50"
    assert primeira.valor_imposto == Decimal("1.50")
    assert primeira.data_emissao == "01/09/2026"
    assert not primeira.cancelada
    assert segunda.cancelada
    assert segunda.situacao_nf == "Cancelada"
    assert segunda.valor_doc == Decimal("493.12")         # sem "sujeira" de float


def test_valor_em_texto_formato_brasileiro(tmp_path):
    caminho = _planilha(tmp_path, [_linha_planilha("10", "1.234,56")])
    assert ler_relatorio_cidade_epsilon(caminho).linhas[0].valor_doc == Decimal("1234.56")


def test_valor_vazio_vira_aviso_e_linha_e_mantida(tmp_path):
    caminho = _planilha(tmp_path, [_linha_planilha(10, None)])
    leitura = ler_relatorio_cidade_epsilon(caminho)
    assert len(leitura.linhas) == 1
    assert leitura.linhas[0].valor_doc is None
    assert any("Vlr. Nota vazio" in a.mensagem for a in leitura.avisos)


def test_situacao_desconhecida_e_conferida_com_aviso(tmp_path):
    caminho = _planilha(tmp_path, [_linha_planilha(10, 100, situacao="Substituída")])
    leitura = ler_relatorio_cidade_epsilon(caminho)
    assert not leitura.linhas[0].cancelada
    assert any("Substituída" in a.mensagem for a in leitura.avisos)


def test_colunas_em_outra_ordem(tmp_path):
    ordem = list(reversed(range(len(CABECALHO))))
    cabecalho = [CABECALHO[i] for i in ordem]
    dados = _linha_planilha(77, 250.5)
    caminho = _planilha(tmp_path, [[dados[i] for i in ordem]], cabecalho=cabecalho)
    lida = ler_relatorio_cidade_epsilon(caminho).linhas[0]
    assert (lida.numero, lida.valor_doc) == ("77", Decimal("250.50"))


def test_linhas_em_branco_sao_ignoradas(tmp_path):
    caminho = _planilha(tmp_path, [_linha_planilha(1, 10), [], _linha_planilha(2, 20)])
    assert [l.linha for l in ler_relatorio_cidade_epsilon(caminho).linhas] == [1, 2]


def test_mais_de_uma_competencia_avisa(tmp_path):
    caminho = _planilha(tmp_path, [
        _linha_planilha(1, 10), _linha_planilha(2, 20),
        _linha_planilha(3, 30, competencia="08/2026"),
    ])
    leitura = ler_relatorio_cidade_epsilon(caminho)
    assert leitura.competencia == "2026-09"
    assert any("08/2026" in a.mensagem for a in leitura.avisos)


def test_sem_inscricao_avisa(tmp_path):
    caminho = _planilha(tmp_path, [_linha_planilha(1, 10)], inscricao="")
    leitura = ler_relatorio_cidade_epsilon(caminho)
    assert leitura.erro is None
    assert any("Inscrição municipal" in a.mensagem for a in leitura.avisos)


def test_sem_coluna_situacao_avisa_e_nada_e_cancelado(tmp_path):
    posicao = CABECALHO.index("Situação NF")
    cabecalho = CABECALHO[:posicao] + CABECALHO[posicao + 1:]
    dados = _linha_planilha(1, 10, situacao="Cancelada")
    caminho = _planilha(tmp_path, [dados[:posicao] + dados[posicao + 1:]], cabecalho=cabecalho)
    leitura = ler_relatorio_cidade_epsilon(caminho)
    assert not leitura.linhas[0].cancelada
    assert any("Situação NF" in a.mensagem for a in leitura.avisos)


def test_coluna_obrigatoria_faltando_e_erro(tmp_path):
    cabecalho = [c if c != "Vlr. Nota" else "Valor" for c in CABECALHO]
    caminho = _planilha(tmp_path, [_linha_planilha(1, 10)], cabecalho=cabecalho)
    leitura = ler_relatorio_cidade_epsilon(caminho)
    assert "Vlr. Nota" in leitura.erro
    assert leitura.linhas == []


def test_arquivo_vazio_e_inexistente(tmp_path):
    vazio = tmp_path / "vazio.xls"
    vazio.write_bytes(b"")
    assert ler_relatorio_cidade_epsilon(vazio).erro == "Arquivo vazio."
    assert "Não foi possível abrir" in ler_relatorio_cidade_epsilon(tmp_path / "nao_existe.xls").erro


def test_arquivo_que_nao_e_planilha(tmp_path):
    html = tmp_path / "outro.xls"
    html.write_text("<html><table><tr><td>Qualquer coisa</td></tr></table></html>",
                    encoding="utf-8")
    leitura = ler_relatorio_cidade_epsilon(html)
    assert "não é uma planilha do Excel" in leitura.erro
    assert "Cidade Beta" not in leitura.erro


def test_planilha_corrompida_vira_erro(tmp_path):
    ruim = tmp_path / "ruim.xls"
    ruim.write_bytes(b"\xd0\xcf\x11\xe0" + b"\x00" * 100)
    leitura = ler_relatorio_cidade_epsilon(ruim)
    assert leitura.erro.startswith("Não foi possível ler a planilha")


# ---------------------------------------------------------------------
# Leitor — arquivo real
# ---------------------------------------------------------------------
def test_relatorio_real_cidade_epsilon():
    _exige_exemplos_sj()
    leitura = ler_relatorio_cidade_epsilon(PASTA_SJ / RELATORIO_SJ)
    assert leitura.erro is None
    assert leitura.avisos == []
    assert len(leitura.linhas) == 85
    assert sum(l.cancelada for l in leitura.linhas) == 17
    assert leitura.competencia == "2026-09"
    assert leitura.inscricao_municipal == "35882"
    assert sum(l.valor_doc for l in leitura.linhas) == Decimal("327649.88")

    primeira = leitura.linhas[0]
    assert primeira.documento_original == caso_real("sj_8_4", "primeira_linha_documento_original")
    assert primeira.numero == "634"
    assert primeira.valor_doc == Decimal("667.00")
    assert primeira.cancelada
    assert primeira.chave_acesso == caso_real("sj_8_4", "primeira_linha_chave_acesso")


# ---------------------------------------------------------------------
# Comparador — notas canceladas na prefeitura
# ---------------------------------------------------------------------
def _cancelada(numero, valor, **kwargs):
    linha_ = linha(numero, valor, **kwargs)
    linha_.cancelada = True
    linha_.situacao_nf = "Cancelada"
    return linha_


def test_cancelada_sem_nota_no_tasy():
    r = comparar([nota("10", "100.00")], [linha("10", "100.00"), _cancelada("11", "50.00")])
    assert situacoes(r) == [SITUACAO_CONFERIDA, SITUACAO_CANCELADA_SEM_TASY]


def test_cancelada_com_nota_no_tasy():
    r = comparar([nota("10", "100.00")], [_cancelada("10", "100.00")])
    assert situacoes(r) == [SITUACAO_CANCELADA_COM_TASY]
    assert r.itens[0].nota_tasy is not None
    assert r.itens[0].linha_prefeitura is not None


def test_cancelada_com_nota_no_tasy_mesmo_com_valor_diferente():
    r = comparar([nota("10", "100.00")], [_cancelada("10", "90.00")])
    assert situacoes(r) == [SITUACAO_CANCELADA_COM_TASY]
    assert r.itens[0].diferenca == Decimal("10.00")


def test_cancelada_nao_conta_como_escriturada_duas_vezes():
    # Nota cancelada e reemitida com o mesmo número: vale a Normal.
    r = comparar([nota("10", "100.00")], [_cancelada("10", "100.00"), linha("10", "100.00")])
    assert situacoes(r) == [SITUACAO_CONFERIDA, SITUACAO_CANCELADA_SEM_TASY]


def test_duas_normais_continuam_escrituradas_duas_vezes_com_cancelada_junto():
    r = comparar([nota("10", "100.00")],
                 [linha("10", "100.00"), linha("10", "100.00"), _cancelada("10", "100.00")])
    escriturada = situacao_escriturada_varias_vezes(2)
    assert situacoes(r) == [escriturada, escriturada, SITUACAO_CANCELADA_SEM_TASY]


def test_cancelada_pelo_numero_ajustado():
    r = comparar([nota("2026000000122", "100.00")], [_cancelada("122", "100.00")])
    assert situacoes(r) == [SITUACAO_CANCELADA_COM_TASY]


def test_cancelada_de_pessoa_fisica_por_numero_e_valor():
    r = comparar([nota("55", "300.00", pf=True)],
                 [_cancelada("55", "300.00", documento="123.456.789-09")])
    assert situacoes(r) == [SITUACAO_CANCELADA_COM_TASY]


def test_sem_canceladas_nada_muda():
    notas = [nota("10", "100.00"), nota("11", "5.00"), nota("2026000000122", "7.00")]
    linhas = [linha("10", "100.00"), linha("122", "7.00"), linha("99", "1.00")]
    assert situacoes(comparar(notas, linhas)) == [
        SITUACAO_CONFERIDA, SITUACAO_SOMENTE_TASY, SITUACAO_CONFERIDA_AJUSTADO,
        SITUACAO_SOMENTE_PREFEITURA,
    ]


def test_numeros_principais_com_canceladas():
    r = comparar([nota("10", "100.00"), nota("11", "5.00")],
                 [_cancelada("10", "100.00"), _cancelada("12", "1.00")])
    resultado = Resultado(itens=r.itens, municipio=MUNICIPIO_SJ)
    numeros = numeros_principais(resultado)
    assert numeros.canceladas_com_tasy == 1
    assert numeros.canceladas_sem_tasy == 1
    assert numeros.somente_tasy == 1
    assert numeros.para_analisar == 1               # só a cancelada lançada no Tasy
    nomes = [l[0] for l in linhas_do_resumo(resultado)]
    assert SITUACAO_CANCELADA_COM_TASY in nomes
    assert SITUACAO_CONFERIDA_SEM_CPF not in nomes


# ---------------------------------------------------------------------
# Planilha
# ---------------------------------------------------------------------
def test_planilha_cidade_epsilon_tem_aba_de_canceladas(tmp_path):
    notas = [nota("10", "100.00"), nota("20", "50.00")]
    linhas_ = [linha("10", "100.00"), _cancelada("20", "50.00"), _cancelada("30", "9.00")]
    r = comparar(notas, linhas_)
    resultado = Resultado(itens=r.itens, notas_tasy=notas, linhas_prefeitura=linhas_,
                          municipio=MUNICIPIO_SJ)
    livro = load_workbook(gerar_relatorio(resultado, tmp_path / "sj.xlsx", AGORA))

    assert livro.sheetnames == [
        ABA_RESUMO, ABA_CONFERIDAS, ABA_DIVERGENCIA, ABA_SOMENTE_TASY, ABA_SOMENTE_PREFEITURA,
        ABA_ESCRITURADAS, ABA_CANCELADAS, ABA_AVISOS,
    ]
    assert livro[ABA_RESUMO]["A1"].value == "Conferência ISS Cidade Epsilon"

    canceladas = livro[ABA_CANCELADAS]
    titulos = [c.value for c in canceladas[2]]
    assert titulos[:7] == [
        "Situação", "CNPJ/CPF", "Emitente", "Nota Fiscal", "Valor da mercadoria",
        "Vlr. Nota", "Diferença (mercadoria − Vlr. Nota)",
    ]
    assert "Situação NF" in titulos and "Chave Acesso" in titulos
    assert "Observação" not in titulos
    dados = [l for l in canceladas.iter_rows(min_row=3, values_only=True) if any(l)]
    assert [l[0] for l in dados] == [SITUACAO_CANCELADA_COM_TASY, SITUACAO_CANCELADA_SEM_TASY]
    chave = canceladas.cell(row=3, column=titulos.index("Chave Acesso") + 1)
    assert chave.number_format == "@"


def test_planilha_cidade_beta_continua_sem_aba_de_canceladas(tmp_path):
    r = comparar([nota("10", "100.00")], [linha("10", "100.00")])
    resultado = Resultado(itens=r.itens, municipio=MUNICIPIO_RB)
    livro = load_workbook(gerar_relatorio(resultado, tmp_path / "rb.xlsx", AGORA))
    assert ABA_CANCELADAS not in livro.sheetnames
    assert livro[ABA_RESUMO]["A1"].value == "Conferência ISS Cidade Beta"


# ---------------------------------------------------------------------
# processar() de ponta a ponta (exemplos reais)
# ---------------------------------------------------------------------
@pytest.fixture
def pasta_sj(tmp_path):
    _exige_exemplos_sj()
    for nome in (CSV_PJ, CSV_HN, RELATORIO_SJ):
        shutil.copy(PASTA_SJ / nome, tmp_path / nome)
    return tmp_path


def _contagens(resultado):
    return {situacao: (notas, linhas) for situacao, notas, linhas, _, _ in
            linhas_do_resumo(resultado)}


def test_cidade_epsilon_ponta_a_ponta(pasta_sj):
    resultado = processar([pasta_sj / CSV_PJ, pasta_sj / CSV_HN], pasta_sj / RELATORIO_SJ,
                          agora=AGORA, municipio=MUNICIPIO_SJ)
    assert resultado.erro is None
    assert resultado.municipio == MUNICIPIO_SJ
    assert resultado.competencia == "2026-09"
    assert resultado.inscricao_municipal == "35882"
    assert resultado.caminho_relatorio.name.startswith("Conferencia_ISS_SJ_2026-09_")

    contagens = _contagens(resultado)
    assert contagens[SITUACAO_CONFERIDA] == (59, 59)
    assert contagens[situacao_escriturada_varias_vezes(2)] == (1, 2)      # nº 925
    assert contagens[SITUACAO_DIVERGENCIA] == (1, 1)                      # nº 7939
    assert contagens[SITUACAO_SOMENTE_TASY] == (20, 0)
    assert contagens[SITUACAO_SOMENTE_PREFEITURA] == (0, 6)
    assert contagens[SITUACAO_CANCELADA_SEM_TASY] == (0, 17)
    assert SITUACAO_CANCELADA_COM_TASY not in contagens

    divergencia = next(i for i in resultado.itens if i.situacao == SITUACAO_DIVERGENCIA)
    assert divergencia.nota_tasy.nota_fiscal == "7939"
    assert divergencia.diferenca == Decimal("-150.00")

    # Nada some: 81 notas do Tasy e 85 linhas da prefeitura.
    livro = load_workbook(resultado.caminho_relatorio)
    textos = [str(l[0]) for l in livro[ABA_RESUMO].iter_rows(values_only=True) if l[0]]
    assert any("(81 de 81)" in t for t in textos)
    assert any("(85 de 85)" in t for t in textos)
    assert len([l for l in livro[ABA_CANCELADAS].iter_rows(min_row=3, values_only=True)
                if any(l)]) == 17


def test_previa_cidade_epsilon(pasta_sj):
    previa = previa_prefeitura(pasta_sj / RELATORIO_SJ, MUNICIPIO_SJ)
    assert previa.erro is None
    assert (previa.linhas, previa.competencia_texto, previa.inscricao_municipal) == (
        85, "setembro/2026", "35882")


def test_relatorio_de_cidade_epsilon_no_item_cidade_beta_da_erro_claro(pasta_sj):
    previa = previa_prefeitura(pasta_sj / RELATORIO_SJ, MUNICIPIO_RB)
    assert previa.erro.startswith("Este é o Relatório de Serviços Tomados de Cidade Epsilon")
    assert "aba Cidade Epsilon" in previa.erro
    resultado = processar([pasta_sj / CSV_PJ], pasta_sj / RELATORIO_SJ, agora=AGORA)
    assert resultado.erro.startswith("Relatório não gerado")
    assert resultado.caminho_relatorio is None


def test_relatorio_de_cidade_beta_no_item_cidade_epsilon_da_erro_claro(tmp_path):
    if not PASTA_EXEMPLOS.exists():
        pytest.skip("pasta exemplos/ não existe (dados reais ficam fora do git)")
    origem = PASTA_RB / "Relatorio_de_Servicos_Contratados.xls"
    shutil.copy(origem, tmp_path / origem.name)
    previa = previa_prefeitura(tmp_path / origem.name, MUNICIPIO_SJ)
    assert previa.erro.startswith("Este é o Relatório de Serviços Contratados de Cidade Beta")
    assert "aba Cidade Beta" in previa.erro


def test_cidade_desconhecida_nao_vira_excecao(tmp_path):
    resultado = processar([], tmp_path / "x.xls", municipio="XX")
    assert "Cidade desconhecida" in resultado.erro


def test_nome_do_relatorio_cidade_epsilon():
    assert nome_do_relatorio("2026-09", ["AME Cidade Epsilon"], AGORA, "Conferencia_ISS_SJ") == (
        "Conferencia_ISS_SJ_2026-09_AME_Cidade_Epsilon_09h30.xlsx")
