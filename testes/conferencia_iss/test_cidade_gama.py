"""
Testes da conferência de Cidade Gama: leitor do Relatório de Nota Fiscal, comparação por
número, valor e nome parecido (o relatório não traz o CNPJ do prestador), planilha e
processar() de ponta a ponta.

- Casos sintéticos: planilhas .xlsx montadas no teste (dados inventados).
- Exemplos reais (exemplos/Exemplos_Cidade_Gama, competência 09/2026): pula se não existirem.
"""

import shutil
from dataclasses import replace
from datetime import datetime
from decimal import Decimal

import pytest
from openpyxl import Workbook, load_workbook

from modulos.conferencia_iss.processamento import (
    MUNICIPIO_AV,
    MUNICIPIO_CP,
    MUNICIPIO_RB,
    MUNICIPIO_SJ,
    MUNICIPIOS,
    conferencia_nada_sumiu,
    numeros_principais,
    previa_prefeitura,
)
from modulos.conferencia_iss.processar import processar
from modulos.conferencia_iss.comparador import comparar_por_nome
from modulos.conferencia_iss.leitor_prefeitura_cp import ler_relatorio_cidade_gama
from modulos.conferencia_iss.modelos import (
    SITUACAO_CANCELADA_COM_TASY,
    SITUACAO_CANCELADA_SEM_TASY,
    SITUACAO_CONFERIDA,
    SITUACAO_CONFERIDA_AJUSTADO,
    SITUACAO_DIVERGENCIA,
    SITUACAO_NOME_DIFERENTE,
    SITUACAO_SOMENTE_PREFEITURA,
    SITUACAO_SOMENTE_TASY,
    Resultado,
    situacao_escriturada_varias_vezes,
)
from modulos.conferencia_iss.normalizar import nomes_parecidos, normalizar_numero, palavras_do_nome
from modulos.conferencia_iss.relatorio_excel import (
    ABA_CANCELADAS,
    ABA_CONFERIDAS,
    ABA_NOME_DIFERENTE,
    ABA_RESUMO,
)
from testes.conferencia_iss.pastas_exemplos import PASTA_CP
from testes.conferencia_iss.test_comparador import linha, nota, situacoes

AGORA = datetime(2026, 10, 2, 16, 0)
RELATORIO_CP = "Nota Fiscal_Cidade_Gama.xlsx"
CNPJ_UNIDADE = "98.765.432/0008-64"

CABECALHO = [
    "Situação", "Nr. NF", "Nr. RPS", "Nº Documento Escriturado", "Emissão", "Compet.",
    "Pagamento", "Nome Empresarial", "CNAE", "Valor Serviço", "Base Cálculo", "Valor ISS",
]


def _linha_planilha(numero, valor, prestador="VERANO SERVIÇOS MÉDICOS LTDA",
                    situacao="Ativa", escriturado="", competencia="09/2026",
                    base=None, iss="7,55"):
    return [situacao, numero, "", escriturado, "11/09/2026 17:34:37", competencia, "",
            prestador, "863050100", valor, valor if base is None else base, iss]


def _planilha(tmp_path, linhas, cabecalho=CABECALHO, usuario=f"{CNPJ_UNIDADE} - FUNDACAO",
              nome="relatorio.xlsx"):
    """Monta um relatório no formato de Cidade Gama (tudo texto, como o site entrega)."""
    livro = Workbook()
    aba = livro.active
    aba.append(["Prefeitura Municipal Cidade Gama", "", "", "", "", "", "DSF_NOTAFISCAL"])
    aba.append(["Secretaria Municipal de Finanças", "", "", "", "", "", "Emitido",
                "02/10/2026 13:47"])
    aba.append(["Departamento de Receitas Mobiliárias", "Relatório de Nota Fiscal", "", "", "",
                "", "Usuário", usuario])
    aba.append([])
    aba.append([])
    aba.append(cabecalho)
    for linha_ in linhas:
        aba.append(linha_)
    caminho = tmp_path / nome
    livro.save(caminho)
    return caminho


def linha_cp(numero, valor, prestador="Prestador Teste", cancelada=False, escriturado=""):
    """Linha da prefeitura de Cidade Gama: sem CNPJ, com o Nº Documento Escriturado opcional."""
    alternativo = normalizar_numero(escriturado.split("/")[0])
    return replace(
        linha(numero, valor, documento="", prestador=prestador),
        cancelada=cancelada, numero_escriturado=escriturado,
        numero_alternativo=alternativo if alternativo != normalizar_numero(numero) else "",
    )


# ---------------------------------------------------------------------
# Nomes parecidos
# ---------------------------------------------------------------------
def test_palavras_do_nome_ignora_acento_pontuacao_e_genericas():
    assert palavras_do_nome("VERANO SERVIÇOS MÉDICOS LTDA") == {"VERANO"}
    assert palavras_do_nome("QX SERVIÇOS MEDICOS S/S LTDA - ME") == {"QX"}
    assert palavras_do_nome("12.345.678 Joao Exemplo") == {"JOAO", "EXEMPLO"}


def test_letras_soltas_viram_uma_palavra():
    assert palavras_do_nome("K&W SERVICOS MEDICOS LTDA") == {"KW"}
    assert palavras_do_nome("R T V Engenharia Ltda") == {"RTV", "ENGENHARIA"}


@pytest.mark.parametrize("tasy, prefeitura", [
    ("Verano Servicos Medicos Ltda", "VERANO SERVIÇOS MÉDICOS LTDA"),
    ("TERRAVIVA CONTROLE DE PRAGAS URBANAS EIRELI", "TERRAVIVA CONTROLE DE PRAGAS URBANAS LTDA"),
    ("K&w Servicos Medicos Ltda", "K&W SERVICOS MEDICOS LTDA"),
    ("Vitalle Servicos de Saude Ltda", "VITALLE SERVICOS DE SAUDE SS LTDA"),
])
def test_nomes_parecidos(tasy, prefeitura):
    assert nomes_parecidos(tasy, prefeitura)


@pytest.mark.parametrize("tasy, prefeitura", [
    ("B D F Clinica Medica Ltda", "MARIA EXEMPLO DA SILVA"),
    ("Kkpt Serviços Médicos Ltda", "TORVALE SERVICOS MEDICOS LTDA"),
    ("Clinica Medica Ltda", "Servicos Medicos Ltda"),     # só palavras genéricas
])
def test_nomes_diferentes(tasy, prefeitura):
    assert not nomes_parecidos(tasy, prefeitura)


# ---------------------------------------------------------------------
# Comparação por número, valor e nome
# ---------------------------------------------------------------------
def test_numero_valor_e_nome_conferida():
    r = comparar_por_nome([nota("10", "100.00", emitente="Verano Ltda")],
                          [linha_cp("10", "100.00", "VERANO SERVIÇOS MÉDICOS LTDA")])
    assert situacoes(r) == [SITUACAO_CONFERIDA]


def test_numero_e_nome_com_valor_diferente_e_divergencia():
    r = comparar_por_nome([nota("10", "100.01", emitente="Verano Ltda")],
                          [linha_cp("10", "100.00", "VERANO LTDA")])
    assert situacoes(r) == [SITUACAO_DIVERGENCIA]
    assert r.itens[0].diferenca == Decimal("0.01")


def test_numero_e_valor_com_nome_diferente_vai_para_verificar():
    r = comparar_por_nome([nota("10", "100.00", emitente="Nome Fantasia Ltda")],
                          [linha_cp("10", "100.00", "RAZAO SOCIAL NOVA LTDA")])
    assert situacoes(r) == [SITUACAO_NOME_DIFERENTE]
    assert r.itens[0].linha_prefeitura is not None


def test_mesmo_numero_de_outro_prestador_nao_casa():
    """Exemplo real: a nota 54 existe de dois prestadores (nomes trocados aqui); cada uma acha a sua."""
    notas = [nota("54", "2250.00", emitente="B D F Clinica Medica Ltda"),
             nota("54", "12300.00", emitente="Maria Exemplo da Silva")]
    r = comparar_por_nome(notas, [linha_cp("54", "12300.00", "MARIA EXEMPLO DA SILVA")])
    assert situacoes(r) == [SITUACAO_SOMENTE_TASY, SITUACAO_CONFERIDA]


def test_numero_igual_sem_nome_e_sem_valor_fica_dos_dois_lados():
    r = comparar_por_nome([nota("10", "100.00", emitente="Alfa Ltda")],
                          [linha_cp("10", "200.00", "BETA LTDA")])
    assert situacoes(r) == [SITUACAO_SOMENTE_TASY, SITUACAO_SOMENTE_PREFEITURA]


def test_nome_parecido_vence_o_nome_diferente():
    """A linha do prestador certo é usada antes de qualquer casamento por nome diferente."""
    notas = [nota("10", "100.00", emitente="Outro Nome Ltda"),
             nota("10", "100.00", emitente="Verano Ltda")]
    r = comparar_por_nome(notas, [linha_cp("10", "100.00", "VERANO LTDA")])
    assert situacoes(r) == [SITUACAO_SOMENTE_TASY, SITUACAO_CONFERIDA]


def test_numero_e_valor_com_varias_candidatas_de_nome_diferente_avisa():
    r = comparar_por_nome([nota("10", "100.00", emitente="Alfa Ltda")],
                          [linha_cp("10", "100.00", "BETA LTDA"),
                           linha_cp("10", "100.00", "GAMA LTDA")])
    assert situacoes(r) == [SITUACAO_SOMENTE_TASY, SITUACAO_SOMENTE_PREFEITURA,
                            SITUACAO_SOMENTE_PREFEITURA]
    assert any("nome diferente" in a.mensagem for a in r.avisos)


def test_escriturada_duas_vezes():
    r = comparar_por_nome([nota("10", "100.00", emitente="Verano Ltda")],
                          [linha_cp("10", "100.00", "VERANO LTDA"),
                           linha_cp("10", "100.00", "VERANO LTDA")])
    assert situacoes(r) == [situacao_escriturada_varias_vezes(2)] * 2


def test_numero_ajustado():
    r = comparar_por_nome([nota("2026000000122", "100.00", emitente="Verano Ltda")],
                          [linha_cp("122", "100.00", "VERANO LTDA")])
    assert situacoes(r) == [SITUACAO_CONFERIDA_AJUSTADO]


def test_numero_do_documento_escriturado():
    """Exemplo real (nome trocado aqui): Nr. NF 812 e Nº Documento Escriturado "2543 / 1"."""
    r = comparar_por_nome([nota("2543", "588.84", emitente="Orbix Softhouse Ltda")],
                          [linha_cp("812", "588.84", "ORBIX SOFTHOUSE LTDA", escriturado="2543 / 1")])
    assert situacoes(r) == [SITUACAO_CONFERIDA]


def test_canceladas():
    notas = [nota("10", "100.00", emitente="Verano Ltda")]
    linhas = [linha_cp("10", "100.00", "VERANO LTDA", cancelada=True),
              linha_cp("11", "50.00", "VERANO LTDA", cancelada=True)]
    r = comparar_por_nome(notas, linhas)
    assert situacoes(r) == [SITUACAO_CANCELADA_COM_TASY, SITUACAO_CANCELADA_SEM_TASY]


def test_cancelada_nao_conta_como_escrituracao():
    notas = [nota("10", "100.00", emitente="Verano Ltda")]
    linhas = [linha_cp("10", "100.00", "VERANO LTDA"),
              linha_cp("10", "100.00", "VERANO LTDA", cancelada=True)]
    r = comparar_por_nome(notas, linhas)
    assert situacoes(r) == [SITUACAO_CONFERIDA, SITUACAO_CANCELADA_SEM_TASY]


# ---------------------------------------------------------------------
# Leitor
# ---------------------------------------------------------------------
def test_leitor_campos(tmp_path):
    caminho = _planilha(tmp_path, [
        _linha_planilha("512", "1.220,98"),
        _linha_planilha("812", "588,84", "ORBIX SOFTHOUSE LTDA", escriturado="2543 / 1"),
        _linha_planilha("511", "214,90", situacao="Cancelada"),
    ])
    leitura = ler_relatorio_cidade_gama(caminho)
    assert leitura.erro is None
    assert leitura.avisos == []
    assert leitura.competencia == "2026-09"
    assert leitura.competencia_texto == "setembro/2026"
    assert leitura.documento_tomador == "98765432000864"
    primeira, segunda, terceira = leitura.linhas
    assert primeira.numero == "512"
    assert primeira.valor_doc == Decimal("1220.98")
    assert primeira.prestador == "VERANO SERVIÇOS MÉDICOS LTDA"
    assert primeira.documento == ""
    assert primeira.data_emissao == "11/09/2026"
    assert primeira.valor_imposto == Decimal("7.55")
    assert segunda.numero == "812" and segunda.numero_alternativo == "2543"
    assert segunda.numero_escriturado == "2543 / 1"
    assert terceira.cancelada and not primeira.cancelada


def test_leitor_valores_ocultos(tmp_path):
    caminho = _planilha(tmp_path, [_linha_planilha("1185", "4.923,04", base="*****", iss="*****")])
    leitura = ler_relatorio_cidade_gama(caminho)
    assert leitura.avisos == []
    linha_ = leitura.linhas[0]
    assert linha_.valor_doc == Decimal("4923.04")
    assert linha_.valor_tributavel is None and linha_.valor_imposto is None
    assert linha_.valores_ocultos


def test_leitor_situacao_desconhecida_avisa(tmp_path):
    caminho = _planilha(tmp_path, [_linha_planilha("1", "10,00", situacao="Substituída")])
    leitura = ler_relatorio_cidade_gama(caminho)
    assert not leitura.linhas[0].cancelada
    assert any("Substituída" in a.mensagem for a in leitura.avisos)


def test_leitor_sem_coluna_obrigatoria(tmp_path):
    cabecalho = [c if c != "Nome Empresarial" else "Prestador" for c in CABECALHO]
    leitura = ler_relatorio_cidade_gama(_planilha(tmp_path, [], cabecalho=cabecalho))
    assert "Nome Empresarial" in leitura.erro
    assert leitura.linhas == []


def test_leitor_sem_cnpj_da_unidade_avisa(tmp_path):
    caminho = _planilha(tmp_path, [_linha_planilha("1", "10,00")], usuario="")
    leitura = ler_relatorio_cidade_gama(caminho)
    assert leitura.documento_tomador == ""
    assert any("CNPJ da unidade" in a.mensagem for a in leitura.avisos)


def test_arquivo_que_nao_e_planilha(tmp_path):
    caminho = tmp_path / "x.xlsx"
    caminho.write_text("qualquer coisa", encoding="utf-8")
    assert "não é uma planilha" in ler_relatorio_cidade_gama(caminho).erro


# ---------------------------------------------------------------------
# Ponta a ponta com os exemplos reais
# ---------------------------------------------------------------------
pula_sem_exemplos = pytest.mark.skipif(not PASTA_CP.exists(),
                                       reason="exemplos/Exemplos_Cidade_Gama não existe")


@pytest.fixture
def pasta_cp(tmp_path):
    # Só os arquivos de entrada (nem relatórios gerados, nem o "~$..." do Excel aberto)
    for arquivo in [*PASTA_CP.glob("*.csv"), PASTA_CP / RELATORIO_CP]:
        if not arquivo.name.startswith("~$"):
            shutil.copy(arquivo, tmp_path / arquivo.name)
    return tmp_path


def _processar(pasta):
    return processar(sorted(pasta.glob("*.csv")), pasta / RELATORIO_CP,
                     agora=AGORA, municipio=MUNICIPIO_CP)


@pula_sem_exemplos
def test_gabarito_cidade_gama(pasta_cp):                                  # gabarito 8.6
    r = _processar(pasta_cp)
    assert r.erro is None
    assert r.competencia == "2026-09"
    assert r.documento_tomador == "98765432000864"
    assert r.unidades == ["AME - Cidade Gama"]
    assert len(r.notas_tasy) == 196
    assert len(r.linhas_prefeitura) == 64
    numeros = numeros_principais(r)
    assert numeros.conferidas == 60
    assert numeros.somente_tasy == 136
    assert numeros.para_analisar == 0
    assert numeros.divergencias == 0
    assert numeros.nome_diferente == 0
    assert numeros.somente_prefeitura == 0
    assert numeros.canceladas_sem_tasy == 4
    assert conferencia_nada_sumiu(r) == ((196, 196), (64, 64))
    assert [a for a in r.avisos if not a.tipo_arquivo] == []
    total_conferidas = sum(i.linha_prefeitura.valor_doc for i in r.itens
                           if i.situacao == SITUACAO_CONFERIDA)
    assert total_conferidas == Decimal("507234.35")
    escriturada = next(i for i in r.itens if i.nota_tasy and i.nota_tasy.numero == "2543")
    assert escriturada.situacao == SITUACAO_CONFERIDA and escriturada.linha_prefeitura.numero_doc == "812"


@pula_sem_exemplos
def test_planilha_cidade_gama(pasta_cp):
    r = _processar(pasta_cp)
    assert r.caminho_relatorio.name == "Conferencia_ISS_CP_2026-09_AME_-_Cidade_Gama_16h00.xlsx"
    livro = load_workbook(r.caminho_relatorio)
    assert ABA_NOME_DIFERENTE in livro.sheetnames
    assert livro[ABA_RESUMO]["A1"].value == "Conferência ISS Cidade Gama"
    resumo = {linha_[0]: linha_[1] for linha_ in livro[ABA_RESUMO].iter_rows(values_only=True)}
    assert resumo["CNPJ da unidade"] == CNPJ_UNIDADE
    conferidas = livro[ABA_CONFERIDAS]
    titulos = [c.value for c in conferidas[2]]
    assert titulos[5:8] == ["Valor Serviço", "Diferença (mercadoria − Valor Serviço)",
                            "Nome Empresarial"]
    assert conferidas.max_row - 2 == 60
    assert livro[ABA_CANCELADAS].max_row - 2 == 4
    # nº 1185: Base Cálculo e Valor ISS vieram como "*****"
    base, iss = titulos.index("Base Cálculo"), titulos.index("Valor ISS")
    nota_1185 = next(l for l in conferidas.iter_rows(min_row=3, values_only=True) if l[3] == "1185")
    assert (nota_1185[base], nota_1185[iss]) == ("*****", "*****")


@pula_sem_exemplos
def test_relatorio_de_outra_unidade_avisa(pasta_cp):
    caminho = _planilha(pasta_cp, [_linha_planilha("512", "220,98")],
                        usuario="98.765.432/0001-98 - FUNDACAO", nome=RELATORIO_CP)
    r = processar(sorted(pasta_cp.glob("*.csv")), caminho, agora=AGORA, municipio=MUNICIPIO_CP)
    assert any("ATENÇÃO" in a.mensagem and "98.765.432/0001-98" in a.mensagem
               for a in r.avisos)


@pula_sem_exemplos
def test_previa_cidade_gama():
    previa = previa_prefeitura(PASTA_CP / RELATORIO_CP, municipio=MUNICIPIO_CP)
    assert previa.erro is None
    assert previa.linhas == 64
    assert previa.competencia_texto == "setembro/2026"


@pula_sem_exemplos
@pytest.mark.parametrize("codigo, item", [
    (MUNICIPIO_RB, "aba Cidade Beta"), (MUNICIPIO_SJ, "aba Cidade Epsilon"),
    (MUNICIPIO_AV, "aba Cidade Zeta"),
])
def test_relatorio_de_cidade_gama_no_item_de_outra_cidade(codigo, item):
    leitura = MUNICIPIOS[codigo].ler_relatorio(PASTA_CP / RELATORIO_CP)
    assert "Cidade Gama" in leitura.erro and "aba Cidade Gama" in leitura.erro
    assert item not in leitura.erro


def test_nome_diferente_conta_em_para_analisar():
    r = comparar_por_nome([nota("10", "100.00", emitente="Nome Fantasia Ltda"),
                           nota("11", "50.00", emitente="Verano Ltda")],
                          [linha_cp("10", "100.00", "RAZAO SOCIAL NOVA LTDA"),
                           linha_cp("11", "50.00", "VERANO LTDA")])
    resultado = Resultado(itens=r.itens, municipio=MUNICIPIO_CP)
    numeros = numeros_principais(resultado)
    assert (numeros.conferidas, numeros.nome_diferente, numeros.para_analisar) == (1, 1, 1)


@pula_sem_exemplos
def test_previa_mostra_cnpj_da_unidade():
    previa = previa_prefeitura(PASTA_CP / RELATORIO_CP, municipio=MUNICIPIO_CP)
    assert previa.documento_tomador == CNPJ_UNIDADE
    assert previa.inscricao_municipal == ""
    assert MUNICIPIOS[MUNICIPIO_CP].identificacao == "cnpj"


def test_nomes_casos_reais():
    """Os nomes reais que estavam nestes testes no Conciliações AMES (fora do git)."""
    from testes.conferencia_iss.pastas_exemplos import caso_real

    casos = caso_real("cp_nomes")
    for nome, palavras in casos["palavras_do_nome"]:
        assert palavras_do_nome(nome) == set(palavras)
    for tasy, prefeitura in casos["parecidos"]:
        assert nomes_parecidos(tasy, prefeitura)
    for tasy, prefeitura in casos["diferentes"]:
        assert not nomes_parecidos(tasy, prefeitura)
    tasy, prefeitura = casos["documento_escriturado"]
    r = comparar_por_nome([nota("2543", "588.84", emitente=tasy)],
                          [linha_cp("812", "588.84", prefeitura, escriturado="2543 / 1")])
    assert situacoes(r) == [SITUACAO_CONFERIDA]
