"""Etapa Tomados 2: leitura dos PDFs (DANFSe v2.0).

- T0: cada PDF de exemplos\\escrituracao_tomados\\2026-08\\pdfs\\ lido = linha correspondente do
  gabarito_danfse.csv, em todos os campos que vêm da leitura. (cfps, codigo_retencao, destino e
  motivo dependem das regras: são conferidos na Tomados 3.) A cópia da 249 é duplicada.
- Conversões e erros de leitura com dados fictícios (rodam sempre).
"""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal

import pytest

from modulos.escrituracao_tomados import leitor_danfse
from modulos.escrituracao_tomados.gerador_txt import normalizar_texto
from modulos.escrituracao_tomados.modelos import Competencia, Destino, ErroLeitura
from testes.conftest import pasta_exemplos

# ---------------------------------------------------------------------------
# T0 — PDFs reais x gabarito
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def leitura():
    pasta = pasta_exemplos("escrituracao_tomados", "2026-08", "pdfs")
    avisos = []
    notas, falhas = leitor_danfse.ler_pasta(pasta, lambda texto, fracao: avisos.append(fracao))
    return notas, falhas, avisos


@pytest.fixture(scope="module")
def gabarito():
    arquivo = pasta_exemplos("escrituracao_tomados") / "gabarito_danfse.csv"
    with open(arquivo, encoding="utf-8-sig", newline="") as entrada:
        return {linha["arquivo_pdf"]: linha for linha in csv.DictReader(entrada, delimiter=";")}


def _decimal(texto: str) -> Decimal:
    return Decimal(texto or "0")


def _como_gabarito(nota) -> dict:
    """A nota lida, nos mesmos formatos das colunas do gabarito."""
    return {
        "chave": nota.chave_acesso,
        "numero": nota.numero,
        "competencia": nota.competencia.texto,
        "emissao": nota.data_emissao.strftime("%d/%m/%Y"),
        "situacao": nota.situacao,
        "prestador_doc": nota.prestador_documento,
        "prestador_nome": normalizar_texto(nota.prestador_nome),
        "prestador_cidade": normalizar_texto(nota.prestador_cidade),
        "prestador_uf": nota.prestador_uf,
        "tomador_doc": nota.tomador_documento,
        "regime": nota.regime,
        "atividade": nota.codigo_atividade,
        "local_prestacao": normalizar_texto(nota.local_prestacao),
        "municipio_incidencia": normalizar_texto(nota.municipio_incidencia),
        "valor_servico": nota.valor_servico,
        "deducoes": nota.deducoes,
        "desconto_incondicionado": nota.desconto_incondicionado,
        "aliquota": nota.aliquota,
        "iss": nota.valor_iss,
        "retencao": "Retido" if nota.iss_retido else "Não Retido",
    }


CAMPOS_DA_LEITURA = (
    "chave", "numero", "competencia", "emissao", "situacao", "prestador_doc", "prestador_nome",
    "prestador_cidade", "prestador_uf", "tomador_doc", "regime", "atividade", "local_prestacao",
    "municipio_incidencia", "valor_servico", "deducoes", "desconto_incondicionado", "aliquota",
    "iss", "retencao",
)
CAMPOS_EM_DINHEIRO = {"valor_servico", "deducoes", "desconto_incondicionado", "aliquota", "iss"}


def _esperado(linha: dict) -> dict:
    return {campo: (_decimal(linha[campo]) if campo in CAMPOS_EM_DINHEIRO else linha[campo])
            for campo in CAMPOS_DA_LEITURA}


def test_t0_todos_os_pdfs_lidos_sem_falha(leitura, gabarito):
    notas, falhas, _ = leitura
    assert falhas == []
    assert len(notas) == 20                      # 19 distintas + a cópia da 249
    lidas = {n.arquivo for n in notas}
    assert set(gabarito) <= lidas


def test_t0_cada_pdf_igual_ao_gabarito(leitura, gabarito):
    notas, _, _ = leitura
    diferencas = []
    for nota in notas:
        linha = gabarito.get(nota.arquivo)
        if linha is None:
            continue                             # a cópia: conferida no teste abaixo
        lido, esperado = _como_gabarito(nota), _esperado(linha)
        for campo in esperado:
            if lido[campo] != esperado[campo]:
                diferencas.append((nota.arquivo[:40], campo, esperado[campo], lido[campo]))
    assert diferencas == []


def test_t0_copia_da_249_e_duplicada(leitura):
    notas, _, _ = leitura
    copia = next(n for n in notas if n.arquivo.startswith("copia_DANFSe-249"))
    original = next(n for n in notas if n.arquivo.startswith("DANFSe-249"))
    assert copia.destino is Destino.DUPLICADA
    assert original.arquivo in copia.motivo
    assert original.destino is None
    assert copia.chave_acesso == original.chave_acesso
    assert [n for n in notas if n.destino is Destino.DUPLICADA] == [copia]


def test_r19_impostos_federais_e_descricao_da_atividade(leitura):
    notas, _, _ = leitura
    por_numero = {n.numero: n for n in notas if n.destino is not Destino.DUPLICADA}
    coop = por_numero["2026000000090"]              # PIS/COFINS/CSLL retidos
    assert (coop.irrf, coop.previdencia_retida, coop.contribuicoes_retidas) == (
        Decimal("0.00"), Decimal("0.00"), Decimal("195.99"))
    assert coop.descricao_contribuicoes == "Código 4"
    bruno = por_numero["337"]                       # nenhum federal retido ("-" = 0,00)
    assert (bruno.irrf, bruno.previdencia_retida, bruno.contribuicoes_retidas) == (
        Decimal("0.00"), Decimal("0.00"), Decimal("0.00"))
    assert bruno.descricao_atividade == "Medicina."
    assert por_numero["29555"].descricao_atividade == "Serviços farmacêuticos."
    assert all(n.federais_lidos for n in notas)     # o quadro foi lido em todas


def test_r19_federal_fora_do_formato_nao_derruba_a_leitura():
    assert leitor_danfse.converter_opcional("-", "IRRF") == Decimal("0.00")
    assert leitor_danfse.converter_opcional("R$ 1.234,56", "IRRF") == Decimal("1234.56")
    assert leitor_danfse.converter_opcional("ilegível", "IRRF") is None
    assert leitor_danfse.converter_opcional(None, "IRRF") is None


def test_t0_progresso_informado(leitura):
    _, _, fracoes = leitura
    assert fracoes[0] == 0 and fracoes[-1] == 1.0
    assert fracoes == sorted(fracoes)


# ---------------------------------------------------------------------------
# PDFs com problema: erro de leitura, o resto continua
# ---------------------------------------------------------------------------


def test_pdf_estragado_e_pdf_de_outro_modelo_viram_falha(tmp_path):
    (tmp_path / "estragado.pdf").write_bytes(b"isto nao e um pdf")
    layout = pasta_exemplos("escrituracao_tomados", "layout") / "Declaracao_ServicosTomados_V3.0.pdf"
    subpasta = tmp_path / "sub"
    subpasta.mkdir()
    (subpasta / "layout.PDF").write_bytes(layout.read_bytes())
    (tmp_path / "anotacoes.txt").write_text("ignorado")

    notas, falhas = leitor_danfse.ler_pasta(tmp_path)
    assert notas == []
    motivos = {f.arquivo: f.motivo for f in falhas}
    assert set(motivos) == {"estragado.pdf", "sub/layout.PDF"}
    assert "estragado" in motivos["estragado.pdf"]
    assert "DANFSe v2.0" in motivos["sub/layout.PDF"]


def test_pasta_mista_le_as_boas_e_registra_as_ruins(tmp_path):
    pasta = pasta_exemplos("escrituracao_tomados", "2026-08", "pdfs")
    boa = next(pasta.glob("DANFSe-337-*.pdf"))
    (tmp_path / boa.name).write_bytes(boa.read_bytes())
    (tmp_path / "ruim.pdf").write_bytes(b"%PDF-1.4 quebrado")
    notas, falhas = leitor_danfse.ler_pasta(tmp_path)
    assert [n.numero for n in notas] == ["337"]
    assert [f.arquivo for f in falhas] == ["ruim.pdf"]


# ---------------------------------------------------------------------------
# Modelos que apareceram depois (exemplos\escrituracao_tomados\casos_novos\)
# ---------------------------------------------------------------------------


def test_operacao_nao_sujeita_ao_issqn_e_lida_e_vai_para_lancar_a_mao():
    """Nota 140 (08/2026): o quadro municipal vem só com "OPERAÇÃO NÃO SUJEITA AO ISSQN"."""
    from modulos.escrituracao_tomados import regras

    pasta = pasta_exemplos("escrituracao_tomados", "casos_novos")
    nota = leitor_danfse.ler_pdf(next(pasta.glob("DANFSe-140-*.pdf")))
    assert (nota.numero, nota.tipo_tributacao, nota.iss_retido) == (
        "140", "Operação não sujeita ao ISSQN", False)
    assert (nota.valor_servico, nota.aliquota, nota.valor_iss) == (
        Decimal("80.00"), Decimal("0.00"), Decimal("0.00"))
    assert nota.codigo_atividade == "990101" and nota.municipio_incidencia == ""
    regras.classificar([nota])
    assert nota.destino is Destino.LANCAR_A_MAO and "não sujeita" in nota.motivo


def test_tomador_nao_identificado_fica_nao_incluida():
    """Nota 585 (08/2026): sem tomador, a Fundação como intermediária. Decisão de 28/09/2026."""
    from modulos.escrituracao_tomados import regras

    pasta = pasta_exemplos("escrituracao_tomados", "casos_novos")
    nota = leitor_danfse.ler_pdf(next(pasta.glob("DANFSe-585-*.pdf")))
    assert (nota.tomador_documento, nota.intermediario_documento) == ("", "98765432000198")
    regras.classificar([nota])
    assert (nota.destino, nota.motivo) == (
        Destino.NAO_INCLUIDA,
        "tomador não identificado na nota; a Fundação aparece como intermediária")


def test_nota_com_valor_zero_fica_nao_incluida():
    """Notas 8592262 e 8592280 (08/2026): taxa de administração R$ 0,00 ("-"). Decisão de 28/09/2026."""
    from modulos.escrituracao_tomados import regras

    pasta = pasta_exemplos("escrituracao_tomados", "casos_novos")
    notas = [leitor_danfse.ler_pdf(c) for c in sorted(pasta.glob("DANFSe-85922*.pdf"))]
    assert [(n.numero, n.valor_servico, n.codigo_atividade) for n in notas] == [
        ("8592262", Decimal("0.00"), "171201"), ("8592280", Decimal("0.00"), "171201")]
    regras.classificar(notas)
    assert {(n.destino, n.motivo) for n in notas} == {
        (Destino.NAO_INCLUIDA, "nota sem valor de serviço (R$ 0,00)")}


def test_os_casos_novos_sao_lidos(tmp_path):
    notas, falhas = leitor_danfse.ler_pasta(pasta_exemplos("escrituracao_tomados", "casos_novos"))
    assert falhas == [] and len(notas) == 10


@pytest.mark.parametrize("padrao, base, iss", [
    ("DANFSe-46-*.pdf", Decimal("16234.77"), Decimal("487.04")),
    ("DANFSe-139-*.pdf", Decimal("3156.15"), Decimal("94.68")),
])
def test_iss_conferido_sobre_a_bc_issqn(padrao, base, iss):
    """29/09/2026 (Usuário): o ISS da nota é calculado sobre a "BC ISSQN" (já sem o desconto
    incondicionado de R$ 57,03), e não sobre o valor da operação — sem aviso falso de divergência."""
    from modulos.escrituracao_tomados import regras

    pasta = pasta_exemplos("escrituracao_tomados", "casos_novos")
    nota = leitor_danfse.ler_pdf(next(pasta.glob(padrao)))
    assert (nota.base_calculo, nota.valor_iss, nota.desconto_incondicionado) == (
        base, iss, Decimal("57.03"))
    avisos = regras.classificar([nota])
    assert avisos == []
    assert nota.destino is Destino.LANCAR_A_MAO and "desconto incondicionado" in nota.motivo


def test_bc_issqn_vazia_fica_sem_base(leitura):
    """Notas de serviço prestado pela Fundação (BC "-"): base não informada."""
    notas, _, _ = leitura
    assert next(n for n in notas if n.numero == "89504").base_calculo is None
    assert next(n for n in notas if n.numero == "337").base_calculo == Decimal("13943.28")


@pytest.mark.parametrize("padrao, situacao, motivo", [
    ("DANFSe-104-*.pdf", "Cancelada", "nota cancelada"),
    ("DANFSe-71-*.pdf", "Substituída", "nota substituída"),
])
def test_marca_dagua_cancelada_ou_substituida_nao_atrapalha_a_leitura(padrao, situacao, motivo):
    """07/2026: a marca d'água em letras gigantes grudava nos valores ("E" + "Não" = "ENão")."""
    from modulos.escrituracao_tomados import regras

    pasta = pasta_exemplos("escrituracao_tomados", "casos_novos")
    nota = leitor_danfse.ler_pdf(next(pasta.glob(padrao)))
    assert nota.situacao == situacao and nota.iss_retido is False
    regras.classificar([nota])
    assert (nota.destino, nota.motivo) == (Destino.NAO_INCLUIDA, motivo)


def test_aliquota_em_branco_com_iss_vai_com_a_aliquota_calculada():
    """Nota 10418 (07/2026): alíquota "-" e ISS R$ 0,94; o site recusou alíquota 0 com
    imposto 0,94. Decisão de 29/09/2026: alíquota = ISS ÷ serviço (3,24%)."""
    from modulos.escrituracao_tomados import gerador_txt, regras

    pasta = pasta_exemplos("escrituracao_tomados", "casos_novos")
    nota = leitor_danfse.ler_pdf(next(pasta.glob("DANFSe-10418-*.pdf")))
    assert (nota.aliquota, nota.valor_iss) == (Decimal("0.00"), Decimal("0.94"))     # como na nota
    avisos = regras.classificar([nota])
    assert (nota.destino, nota.aliquota, nota.valor_iss) == (
        Destino.INCLUIDA, Decimal("3.24"), Decimal("0.94"))
    assert [a.tipo for a in avisos] == ["Alíquota em branco: calculada"]
    linha = gerador_txt.montar_detalhe(nota)
    assert (linha[222:227], linha[227:241]) == ("00324", "00000000000094")


def test_intermediario_so_e_lido_quando_falta_o_tomador(leitura):
    notas, _, _ = leitura
    assert all(n.intermediario_documento == "" for n in notas)


# ---------------------------------------------------------------------------
# Conversões (dados fictícios)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("texto, esperado", [
    ("R$ 13.943,28", Decimal("13943.28")), ("R$ 0,88", Decimal("0.88")),
    ("2,01 %", Decimal("2.01")), ("-", Decimal("0.00")), (None, Decimal("0.00")),
    ("R$ 1.234.567,00", Decimal("1234567.00")),
])
def test_converter_valor(texto, esperado):
    assert leitor_danfse.converter_valor(texto, "x") == esperado


@pytest.mark.parametrize("texto", ["R$ 13,9", "abc", "1.2345,00"])
def test_converter_valor_invalido(texto):
    with pytest.raises(ErroLeitura):
        leitor_danfse.converter_valor(texto, "x")


@pytest.mark.parametrize("texto, esperado", [
    ("Não Optante", "N"),
    ("Optante - Microempresa ou Empresa de ...", "S"),
    ("Optante - Microempreendedor Individual (MEI)", "M"),
    ("Optante - MEI", "M"),
])
def test_converter_regime(texto, esperado):
    assert leitor_danfse.converter_regime(texto) == esperado


@pytest.mark.parametrize("texto", ["-", "Outro regime", None])
def test_regime_nao_reconhecido_e_erro_de_leitura(texto):
    with pytest.raises(ErroLeitura):
        leitor_danfse.converter_regime(texto)


def test_converter_retencao():
    assert leitor_danfse.converter_retencao("Não Retido") is False
    assert leitor_danfse.converter_retencao("Retido pelo Tomador") is True
    with pytest.raises(ErroLeitura):
        leitor_danfse.converter_retencao("-")


def test_separar_municipio():
    assert leitor_danfse.separar_municipio("Cidade Beta / SP") == ("Cidade Beta", "SP")
    assert leitor_danfse.separar_municipio("SAO JOAQUIM DA BARRA / SP") == \
        ("SAO JOAQUIM DA BARRA", "SP")
    assert leitor_danfse.separar_municipio("Cidade Alfa") == ("Cidade Alfa", "")
    assert leitor_danfse.separar_municipio("-") == ("", "")


def test_converter_documento_data_e_atividade():
    assert leitor_danfse.converter_documento("529.982.247-25", "x") == "52998224725"
    assert leitor_danfse.converter_documento("98.765.432/0001-98", "x") == "98765432000198"
    with pytest.raises(ErroLeitura):
        leitor_danfse.converter_documento("123", "x")
    assert leitor_danfse.converter_data("13/08/2026 14:17:07", "x") == date(2026, 8, 13)
    with pytest.raises(ErroLeitura):
        leitor_danfse.converter_data("31/02/2026", "x")
    assert leitor_danfse.converter_atividade("04.01.01") == "040101"
    with pytest.raises(ErroLeitura):
        leitor_danfse.converter_atividade("-")


def test_competencia_usa_so_mes_e_ano():
    assert Competencia(2026, 7).texto == "07/2026"
