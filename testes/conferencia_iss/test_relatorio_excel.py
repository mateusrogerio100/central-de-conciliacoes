"""
Testes do relatório Excel (Etapa 5): gera o .xlsx, abre de novo e confere
abas, contagens, formatos e a ausência da Observação.
"""

import csv
import io
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import load_workbook

from modulos.conferencia_iss.comparador import comparar
from modulos.conferencia_iss.leitor_prefeitura import ler_relatorio_prefeitura
from modulos.conferencia_iss.leitor_tasy import ler_csv_tasy
from modulos.conferencia_iss.modelos import (
    NIVEL_OK,
    TIPO_ARQUIVO_PREFEITURA,
    TIPO_ARQUIVO_TASY,
    Aviso,
    LinhaPrefeitura,
    NotaTasy,
    Resultado,
)
from modulos.conferencia_iss.relatorio_excel import (
    ABA_AVISOS,
    ABA_CONFERIDAS,
    ABA_DIVERGENCIA,
    ABA_ESCRITURADAS,
    ABA_RESUMO,
    ABA_SOMENTE_PREFEITURA,
    ABA_SOMENTE_TASY,
    COLUNA_CONFERE,
    COLUNA_DIFERENCA,
    COLUNAS_DETALHE,
    COLUNAS_TASY,
    gerar_relatorio,
)

from testes.conferencia_iss.pastas_exemplos import PASTA_EXEMPLOS, PASTA_RB, caso_real  # noqa: E402
PASTA_2026_09 = PASTA_RB
CSV_PF = PASTA_EXEMPLOS / "pf" / "Notas_fiscais_PF_exemplo.csv"

ABAS = [ABA_RESUMO, ABA_CONFERIDAS, ABA_DIVERGENCIA, ABA_SOMENTE_TASY,
        ABA_SOMENTE_PREFEITURA, ABA_ESCRITURADAS, ABA_AVISOS]


def _resultado_dos_exemplos(com_pf: bool) -> Resultado:
    """Monta o Resultado como o processar() da Etapa 6 vai montar."""
    if not PASTA_EXEMPLOS.exists():
        pytest.skip("pasta exemplos/ não existe (dados reais ficam fora do git)")
    arquivos = [PASTA_2026_09 / "Servico_PJ_RB.csv", PASTA_2026_09 / "Honorario_PJ_RB.csv"]
    if com_pf:
        arquivos.append(CSV_PF)
    resultado = Resultado()
    for arquivo in arquivos:
        leitura = ler_csv_tasy(arquivo)
        resultado.notas_tasy += leitura.notas
        resultado.avisos.append(Aviso(
            arquivo=leitura.arquivo, mensagem="OK", nivel=NIVEL_OK,
            tipo_arquivo=TIPO_ARQUIVO_TASY, linhas_lidas=len(leitura.notas),
            unidades=", ".join(leitura.unidades),
        ))
        for unidade in leitura.unidades:
            if unidade not in resultado.unidades:
                resultado.unidades.append(unidade)
    prefeitura = ler_relatorio_prefeitura(PASTA_2026_09 / "Relatorio_de_Servicos_Contratados.xls")
    resultado.linhas_prefeitura = prefeitura.linhas
    resultado.competencia = prefeitura.competencia
    resultado.competencia_texto = prefeitura.competencia_texto
    resultado.inscricao_municipal = prefeitura.inscricao_municipal
    resultado.avisos.append(Aviso(
        arquivo=prefeitura.arquivo, mensagem="OK", nivel=NIVEL_OK,
        tipo_arquivo=TIPO_ARQUIVO_PREFEITURA, linhas_lidas=len(prefeitura.linhas),
    ))
    resultado.avisos += prefeitura.avisos
    comparacao = comparar(resultado.notas_tasy, resultado.linhas_prefeitura)
    resultado.itens = comparacao.itens
    resultado.avisos += comparacao.avisos
    return resultado


def _linhas_de_dados(aba):
    """Linhas de dados de uma aba de detalhe (cabeçalho ocupa as linhas 1 e 2)."""
    return [linha for linha in aba.iter_rows(min_row=3, values_only=True) if any(linha)]


def _coluna(aba, nome):
    return [c.value for c in aba[2]].index(nome)


def _texto_de_todas_as_celulas(livro):
    return {
        str(celula) for aba in livro.worksheets
        for linha in aba.iter_rows(values_only=True) for celula in linha if celula is not None
    }


@pytest.fixture
def livro_8_1(tmp_path):
    resultado = _resultado_dos_exemplos(com_pf=False)
    caminho = gerar_relatorio(resultado, tmp_path / "teste.xlsx", datetime(2026, 10, 1, 14, 5))
    return load_workbook(caminho)


# ---------------------------------------------------------------------
# Exemplos reais
# ---------------------------------------------------------------------
def test_abas_na_ordem(livro_8_1):
    assert livro_8_1.sheetnames == ABAS


def test_quantidade_de_linhas_por_aba(livro_8_1):
    assert len(_linhas_de_dados(livro_8_1[ABA_CONFERIDAS])) == 119       # 118 + 1 ajustado
    assert len(_linhas_de_dados(livro_8_1[ABA_DIVERGENCIA])) == 0
    assert len(_linhas_de_dados(livro_8_1[ABA_SOMENTE_TASY])) == 36
    assert len(_linhas_de_dados(livro_8_1[ABA_SOMENTE_PREFEITURA])) == 3
    assert len(_linhas_de_dados(livro_8_1[ABA_ESCRITURADAS])) == 8        # 4 notas × 2 linhas


def test_cabecalho_das_abas_de_detalhe(livro_8_1):
    for nome in (ABA_CONFERIDAS, ABA_DIVERGENCIA, ABA_SOMENTE_TASY, ABA_SOMENTE_PREFEITURA):
        aba = livro_8_1[nome]
        assert [c.value for c in aba[2]] == COLUNAS_DETALHE
        faixa = [c.value for c in aba[1] if c.value]
        assert faixa == ["Tasy", "Prefeitura", "Prefeitura", "Tasy — outros dados"]
        assert aba.freeze_panes == "B3"
        assert aba.auto_filter.ref.startswith("A2:")
        assert aba["A2"].font.bold
        # Tasy e Prefeitura com cores de cabeçalho diferentes
        cor = {c.value: c.fill.start_color.rgb for c in aba[2]}
        assert cor["Valor da mercadoria"] != cor["Valor do Doc."]
        assert cor["Valor da mercadoria"] == cor["Arquivo"]
    escrituradas = livro_8_1[ABA_ESCRITURADAS]
    colunas = [c.value for c in escrituradas[2]]
    assert colunas.index(COLUNA_CONFERE) == colunas.index(COLUNA_DIFERENCA) + 1
    assert [c for c in colunas if c != COLUNA_CONFERE] == COLUNAS_DETALHE


def test_ordem_das_colunas_valores_lado_a_lado(livro_8_1):
    """Pedido do usuário: os valores comparados e a diferença lado a lado no começo;
    Valor da nota, Arquivo, Tipo de nota, Emissão e Entrada no final."""
    colunas = [c.value for c in livro_8_1[ABA_CONFERIDAS][2]]
    assert colunas[:7] == [
        "Situação", "CNPJ/CPF", "Emitente", "Nota Fiscal",
        "Valor da mercadoria", "Valor do Doc.", COLUNA_DIFERENCA,
    ]
    assert colunas[-5:] == ["Valor da nota", "Arquivo", "Tipo de nota", "Emissão", "Entrada"]

    escrituradas = [c.value for c in livro_8_1[ABA_ESCRITURADAS][2]]
    assert escrituradas[:8] == colunas[:7] + [COLUNA_CONFERE]


def test_valores_gravados_como_numero_com_formato(livro_8_1):
    aba = livro_8_1[ABA_SOMENTE_TASY]
    posicao = _coluna(aba, "Valor da mercadoria")
    celulas = [linha[posicao] for linha in aba.iter_rows(min_row=3)]
    assert all(isinstance(c.value, (int, float)) for c in celulas)
    assert all(c.number_format == "#,##0.00" for c in celulas)
    total = sum(Decimal(str(c.value)) for c in celulas)
    assert total == Decimal("445180.46")


def test_documento_e_numero_como_texto(livro_8_1):
    aba = livro_8_1[ABA_CONFERIDAS]
    ajustada = [l for l in _linhas_de_dados(aba) if l[_coluna(aba, "Nota Fiscal")] == "2026000000122"]
    assert len(ajustada) == 1
    linha = ajustada[0]
    documento = caso_real("rb_8_1", "numero_ajustado_formatado")
    assert linha[_coluna(aba, "Situação")] == "Conferida (número ajustado)"
    assert linha[_coluna(aba, "CNPJ/CPF")] == documento
    assert linha[_coluna(aba, "CPF/CNPJ")] == documento
    assert linha[_coluna(aba, "Nº Doc.")] == "122"
    assert isinstance(linha[_coluna(aba, "Emissão")], datetime)


def test_escrituradas_sim_e_nao(livro_8_1):
    aba = livro_8_1[ABA_ESCRITURADAS]
    documento = caso_real("rb_8_1", "escriturada_2_vezes_com_diferenca_formatado")
    do_prestador = [l for l in _linhas_de_dados(aba) if l[_coluna(aba, "CNPJ/CPF")] == documento]
    resultado = {
        Decimal(str(l[_coluna(aba, "Valor do Doc.")])): (
            l[_coluna(aba, COLUNA_CONFERE)], Decimal(str(l[_coluna(aba, COLUNA_DIFERENCA)]))
        )
        for l in do_prestador
    }
    assert resultado == {
        Decimal("7590"): ("Sim", Decimal("0")),
        Decimal("7123.21"): ("Não", Decimal("466.79")),
    }


def test_somente_prefeitura_lado_tasy_em_branco(livro_8_1):
    aba = livro_8_1[ABA_SOMENTE_PREFEITURA]
    for linha in _linhas_de_dados(aba):
        assert all(linha[_coluna(aba, nome)] is None for nome in COLUNAS_TASY)
        assert linha[_coluna(aba, COLUNA_DIFERENCA)] is None
    valor_vazio = [l for l in _linhas_de_dados(aba) if l[_coluna(aba, "Nº Doc.")] == "8905486"]
    assert valor_vazio[0][_coluna(aba, "Valor do Doc.")] is None


def test_resumo(livro_8_1):
    aba = livro_8_1[ABA_RESUMO]
    linhas = [l for l in aba.iter_rows(values_only=True) if any(v is not None for v in l)]
    por_rotulo = {l[0]: l for l in linhas if l[0]}

    assert por_rotulo["Unidade(s)"][1] == "AME Cidade Beta"
    assert por_rotulo["Competência"][1] == "setembro/2026"
    assert por_rotulo["Inscrição municipal"][1] == "20164715"
    assert por_rotulo["Gerado em"][1] == "01/10/2026 14:05"

    def valores(situacao):
        l = por_rotulo[situacao]
        return l[1], l[2], Decimal(str(l[3])), Decimal(str(l[4]))

    assert valores("Conferida")[:3] == (118, 118, Decimal("1448484.54"))
    assert valores("Conferida (número ajustado)")[:3] == (1, 1, Decimal("6927.15"))
    assert valores("Notas escrituradas 2 vezes na prefeitura")[:3] == (4, 8, Decimal("15412.39"))
    assert valores("Divergência de valor") == (0, 0, Decimal(0), Decimal(0))
    somente_tasy = "Notas encontradas somente no Tasy, verificar se precisam escriturar na prefeitura"
    assert valores(somente_tasy)[:3] == (36, 0, Decimal("445180.46"))
    assert valores("Notas encontradas somente no site da prefeitura") == (
        0, 3, Decimal(0), Decimal("9979.71")
    )
    total = valores("Total")
    assert total[:3] == (159, 130, Decimal("1916004.54"))
    assert total[3] == Decimal("1495749.39")
    assert "Conferida sem CPF (por número e valor)" not in por_rotulo   # não há PF neste caso

    textos = [str(l[0]) for l in linhas]
    assert "Todas as notas do Tasy aparecem no relatório (159 de 159)" in textos
    assert "Todas as linhas da prefeitura aparecem no relatório (130 de 130)" in textos
    arquivos = " ".join(str(l[1]) for l in linhas if l[0] in (None, ""))
    for nome in ("Servico_PJ_RB.csv", "Honorario_PJ_RB.csv", "Relatorio_de_Servicos_Contratados.xls"):
        assert nome in arquivos


def test_avisos(livro_8_1):
    aba = livro_8_1[ABA_AVISOS]
    linhas = list(aba.iter_rows(min_row=2, values_only=True))
    arquivos = [l for l in linhas if l[1]]
    assert len(arquivos) == 3
    assert all(l[2] == "OK" for l in arquivos)
    assert [l[3] for l in arquivos] == [75, 84, 130]
    outros = [l for l in linhas if not l[1]]
    assert len(outros) == 1
    assert "Valor do Doc. vazio" in outros[0][5]


def test_observacao_nao_aparece_em_nenhuma_aba(tmp_path):
    resultado = _resultado_dos_exemplos(com_pf=True)
    livro = load_workbook(gerar_relatorio(resultado, tmp_path / "pf.xlsx"))

    textos = _texto_de_todas_as_celulas(livro)
    assert not any("observa" in t.casefold() for t in textos)

    texto = CSV_PF.read_bytes().decode("utf-16-le")
    registros = list(csv.reader(io.StringIO(texto, newline=""), delimiter=";"))
    posicao = registros[0].index("Observação")
    observacoes = {r[posicao].strip() for r in registros[1:] if len(r[posicao].strip()) > 10}
    assert observacoes
    assert not any(obs in t for obs in observacoes for t in textos)


def test_caso_com_pf_tem_47_somente_tasy_e_aviso_de_unidades(tmp_path):
    resultado = _resultado_dos_exemplos(com_pf=True)
    livro = load_workbook(gerar_relatorio(resultado, tmp_path / "pf.xlsx"))
    assert len(_linhas_de_dados(livro[ABA_SOMENTE_TASY])) == 47
    mensagens = [l[5] for l in livro[ABA_AVISOS].iter_rows(min_row=2, values_only=True)]
    assert any("unidades diferentes misturados" in m for m in mensagens)
    aba = livro[ABA_SOMENTE_TASY]
    pf = [l for l in _linhas_de_dados(aba)
          if l[_coluna(aba, "Tipo de nota")] == "Entrada por pessoa física"]
    assert len(pf) == 9
    # PF sem documento: código do Tasy não vira CPF
    assert all(l[_coluna(aba, "CNPJ/CPF")] is None for l in pf)


# ---------------------------------------------------------------------
# Casos inventados
# ---------------------------------------------------------------------
def test_resultado_vazio_gera_arquivo_com_todas_as_abas(tmp_path):
    livro = load_workbook(gerar_relatorio(Resultado(), tmp_path / "vazio.xlsx"))
    assert livro.sheetnames == ABAS
    textos = _texto_de_todas_as_celulas(livro)
    assert "Todas as notas do Tasy aparecem no relatório (0 de 0)" in textos


def test_conferida_sem_cpf_aparece_no_resumo_e_nas_conferidas(tmp_path):
    from modulos.conferencia_iss.modelos import SITUACAO_CONFERIDA_SEM_CPF, ItemResultado

    nota = NotaTasy(
        arquivo="pf.csv", linha=2, nota_fiscal="247", numero="247", numero_ajustado=None,
        emitente="Dra. Teste", codigo_emitente="1079616", documento="",
        tipo_nota="Entrada por pessoa física", eh_pessoa_fisica=True,
        valor_mercadoria=Decimal("1100"), data_emissao="02/09/2026",
    )
    linha = LinhaPrefeitura(
        linha=1, documento="12345678909", documento_original="123.456.789-09",
        prestador="TESTE MEDICA", numero_doc="247", numero="247", valor_doc=Decimal("1100"),
    )
    resultado = Resultado(
        itens=[ItemResultado(SITUACAO_CONFERIDA_SEM_CPF, nota, linha)],
        notas_tasy=[nota], linhas_prefeitura=[linha],
    )
    livro = load_workbook(gerar_relatorio(resultado, tmp_path / "pf.xlsx"))
    aba = livro[ABA_CONFERIDAS]
    dados = _linhas_de_dados(aba)
    assert len(dados) == 1
    assert dados[0][_coluna(aba, "Emitente")] == "Dra. Teste"
    assert dados[0][_coluna(aba, "Prestador")] == "TESTE MEDICA"
    assert dados[0][_coluna(aba, "CPF/CNPJ")] == "123.456.789-09"
    assert dados[0][_coluna(aba, "Emissão")].date() == date(2026, 9, 2)
    assert "Conferida sem CPF (por número e valor)" in _texto_de_todas_as_celulas(livro)


def test_pasta_inexistente_levanta_oserror(tmp_path):
    with pytest.raises(OSError):
        gerar_relatorio(Resultado(), tmp_path / "nao_existe" / "relatorio.xlsx")
