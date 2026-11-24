"""Etapa Tomados 1: layout V3 e gerador do .txt.

- Testes unitários com dados fictícios (rodam sempre).
- Gabarito: monta as notas a partir de dados fixos (gabarito_danfse.csv, sem ler PDF) e confere,
  byte a byte, os arquivos de exemplos\\escrituracao_tomados\\esperado\\ (pulados sem a pasta).
"""

from __future__ import annotations

import csv
import json
from datetime import date, datetime
from decimal import Decimal

import pytest

from modulos.escrituracao_tomados import gerador_txt, layout_v3
from modulos.escrituracao_tomados.layout_v3 import Campo, Tipo
from modulos.escrituracao_tomados.modelos import Competencia, ErroLayout, NotaTomada
from testes.conftest import pasta_exemplos

AGOSTO = Competencia(2026, 8)
TOMADOR = "11222333000181"          # fictício


def nota_ficticia(**mudancas) -> NotaTomada:
    dados = dict(
        numero="123", data_emissao=date(2026, 8, 5), competencia=AGOSTO,
        prestador_documento="12345678000195", prestador_nome="Clínica Exemplo Ltda",
        prestador_cidade="São Paulo", prestador_uf="SP", tomador_documento=TOMADOR,
        situacao="Autorizada", regime="N", codigo_atividade="04.01.01",
        valor_servico=Decimal("1000.00"), aliquota=Decimal("2.00"), valor_iss=Decimal("20.00"),
        codigo_retido="Z", cfps="002",
    )
    dados.update(mudancas)
    return NotaTomada(**dados)


def campo_da_linha(linha: str, tabela, nome: str) -> str:
    campo = next(c for c in tabela if c.nome == nome)
    return gerador_txt.ler_campo(linha, campo)


# ---------------------------------------------------------------------------
# Tabela do layout
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tabela, tamanho", [
    (layout_v3.HEADER, layout_v3.TAMANHO_HEADER),
    (layout_v3.DETALHE, layout_v3.TAMANHO_DETALHE),
    (layout_v3.TRAILLER, layout_v3.TAMANHO_TRAILLER),
], ids=["header", "detalhe", "trailler"])
def test_tabela_cobre_todas_as_posicoes_sem_buraco(tabela, tamanho):
    posicao = 1
    for campo in tabela:
        assert campo.inicio == posicao, campo.nome
        assert campo.fim >= campo.inicio, campo.nome
        posicao = campo.fim + 1
    assert posicao - 1 == tamanho


def test_posicoes_principais_da_especificacao():
    campos = {c.nome: (c.inicio, c.fim) for c in layout_v3.DETALHE}
    assert campos["numero_nf"] == (179, 186)          # V2: 8 posições
    assert campos["imposto_retido"] == (242, 242)
    assert campos["cfps"] == (250, 252)
    assert campos["regime_prestador"] == (255, 255)


# ---------------------------------------------------------------------------
# Formatação de campos
# ---------------------------------------------------------------------------


def test_financeiro_em_centavos_com_zeros_a_esquerda():
    valor = Campo("v", 1, 14, Tipo.FINANCEIRO)
    aliquota = Campo("a", 1, 5, Tipo.FINANCEIRO)
    assert gerador_txt.formatar_campo(valor, Decimal("90.00")) == "00000000009000"
    assert gerador_txt.formatar_campo(valor, Decimal("0")) == "00000000000000"
    assert gerador_txt.formatar_campo(aliquota, Decimal("2.01")) == "00201"
    assert gerador_txt.formatar_campo(aliquota, Decimal("5")) == "00500"


@pytest.mark.parametrize("valor", [Decimal("1.005"), Decimal("-1.00"), 1.5])
def test_financeiro_recusa_valor_invalido(valor):
    with pytest.raises(ErroLayout):
        gerador_txt.formatar_campo(Campo("v", 1, 14, Tipo.FINANCEIRO), valor)


def test_numerico_com_zeros_a_esquerda_e_sem_cortar():
    campo = Campo("n", 1, 8, Tipo.NUMERICO)
    assert gerador_txt.formatar_campo(campo, "95") == "00000095"
    with pytest.raises(ErroLayout):
        gerador_txt.formatar_campo(campo, "123456789")
    with pytest.raises(ErroLayout):
        gerador_txt.formatar_campo(campo, "12A")


def test_texto_maiusculo_sem_acento_cortado_e_completado():
    campo = Campo("c", 1, 10, Tipo.CHAR)
    assert gerador_txt.formatar_campo(campo, "Coração") == "CORACAO   "
    assert gerador_txt.formatar_campo(campo, "Clínica  Exemplo Médica") == "CLINICA EX"
    assert gerador_txt.normalizar_texto("Alfa & Beta Exemplo – Ltda") == \
        "ALFA & BETA EXEMPLO - LTDA"
    assert gerador_txt.normalizar_texto("José Conceição") == "JOSE CONCEICAO"


# ---------------------------------------------------------------------------
# Registros
# ---------------------------------------------------------------------------


def test_header():
    linha = gerador_txt.montar_header("11.222.333/0001-81", AGOSTO, date(2026, 9, 28), "C")
    assert linha == "0T111222333000181082026" + "28092026" + "C03" + " " * 66
    assert len(linha) == 100


def test_header_recusa_tipo_de_referencia_invalido():
    with pytest.raises(ErroLayout):
        gerador_txt.montar_header(TOMADOR, AGOSTO, date(2026, 9, 28), "X")


def test_detalhe_cnpj():
    linha = gerador_txt.montar_detalhe(nota_ficticia())
    assert len(linha) == 350
    assert linha[:16] == "1112345678000195"
    assert campo_da_linha(linha, layout_v3.DETALHE, "nome_prestador").rstrip() == \
        "CLINICA EXEMPLO LTDA"
    assert campo_da_linha(linha, layout_v3.DETALHE, "cidade_prestador").rstrip() == "SAO PAULO"
    assert linha[176:255] == ("SP" "00000123" "05082026" "00000000100000" "00000000000000"
                              "00200" "00000000002000" "Z" "1" "040101" "002" "01" "N")
    assert linha[255:] == " " * 95


def test_detalhe_cpf_tipo_2_com_zeros_a_esquerda():
    linha = gerador_txt.montar_detalhe(nota_ficticia(prestador_documento="123.456.789-09",
                                                     regime="M"))
    assert linha[:16] == "12000" + "12345678909"
    assert campo_da_linha(linha, layout_v3.DETALHE, "regime_prestador") == "M"


def test_detalhe_nome_com_mais_de_100_caracteres_e_cortado():
    nome = "Prestador de Serviços Médicos " * 5
    linha = gerador_txt.montar_detalhe(nota_ficticia(prestador_nome=nome))
    assert len(linha) == 350
    assert campo_da_linha(linha, layout_v3.DETALHE, "nome_prestador") == \
        gerador_txt.normalizar_texto(nome)[:100]


def test_detalhe_numero_com_mais_de_8_digitos_nao_entra():
    with pytest.raises(ErroLayout, match="8 dígitos"):
        gerador_txt.montar_detalhe(nota_ficticia(numero="2026000000090"))


@pytest.mark.parametrize("mudanca", [
    {"codigo_retido": ""}, {"codigo_retido": "M"}, {"cfps": "1"}, {"regime": "X"},
    {"prestador_documento": "123"}, {"prestador_cidade": ""}, {"prestador_uf": "S"},
    {"codigo_atividade": "4.01"},
], ids=lambda m: next(iter(m)))
def test_detalhe_recusa_dado_invalido(mudanca):
    with pytest.raises(ErroLayout):
        gerador_txt.montar_detalhe(nota_ficticia(**mudanca))


def test_trailler_com_varias_notas():
    notas = [
        nota_ficticia(numero="1", valor_servico=Decimal("100.10"), valor_iss=Decimal("2.00")),
        nota_ficticia(numero="2", valor_servico=Decimal("0.90"), deducoes=Decimal("0.50"),
                      valor_iss=Decimal("0.02")),
        nota_ficticia(numero="3", valor_servico=Decimal("13943.28"), valor_iss=Decimal("278.87")),
    ]
    linha = gerador_txt.montar_trailler(notas)
    assert linha == ("9" "0003" "00000001404428" "00000000000050" "00000000028089"
                     + " " * 53)


# ---------------------------------------------------------------------------
# Arquivo
# ---------------------------------------------------------------------------


def test_ordem_numero_inteiro_depois_prestador():
    notas = [nota_ficticia(numero="542", prestador_documento="22222222000191"),
             nota_ficticia(numero="95"),
             nota_ficticia(numero="542", prestador_documento="11111111000191")]
    ordem = [(n.numero, n.prestador_documento) for n in gerador_txt.ordenar_notas(notas)]
    assert ordem == [("95", "12345678000195"), ("542", "11111111000191"),
                     ("542", "22222222000191")]


def test_arquivo_completo_crlf_e_conferencias(tmp_path):
    notas = [nota_ficticia(numero=str(n)) for n in (3, 1, 2)]
    conteudo = gerador_txt.gerar_conteudo(TOMADOR, AGOSTO, date(2026, 9, 28), "N", notas)
    assert conteudo.endswith("\r\n") and conteudo.count("\r\n") == 5
    assert gerador_txt.conferir_conteudo(conteudo) == []

    nome = gerador_txt.nome_arquivo("11.222.333/0001-81", AGOSTO)
    assert nome == "tomados_11222333000181_08-2026.txt"
    caminho = gerador_txt.gravar_arquivo(tmp_path / nome, conteudo)
    assert caminho.read_bytes() == conteudo.encode("latin-1")
    assert b"\r\r\n" not in caminho.read_bytes()


def test_arquivo_sem_notas_e_erro():
    with pytest.raises(ErroLayout):
        gerador_txt.gerar_conteudo(TOMADOR, AGOSTO, date(2026, 9, 28), "N", [])


def test_conferencia_acha_trailler_errado_e_nota_repetida():
    conteudo = gerador_txt.gerar_conteudo(
        TOMADOR, AGOSTO, date(2026, 9, 28), "N", [nota_ficticia(), nota_ficticia()])
    problemas = gerador_txt.conferir_conteudo(conteudo)
    assert any("repetida" in p for p in problemas)

    linhas = gerador_txt.gerar_conteudo(
        TOMADOR, AGOSTO, date(2026, 9, 28), "N", [nota_ficticia()]).split("\r\n")
    linhas[-2] = linhas[-2][:5] + "00000000099999" + linhas[-2][19:]      # total serviços errado
    problemas = gerador_txt.conferir_conteudo("\r\n".join(linhas))
    assert any("total_servicos" in p for p in problemas)

    linhas[1] = linhas[1][:-1]                                             # detalhe com 349
    assert any("349" in p for p in gerador_txt.conferir_conteudo("\r\n".join(linhas)))


# ---------------------------------------------------------------------------
# Gabarito: esperado\ gerado a partir de dados fixos (gabarito_danfse.csv), byte a byte
# ---------------------------------------------------------------------------


def _decimal(texto: str) -> Decimal:
    return Decimal(texto or "0").quantize(Decimal("0.01"))


def _notas_do_gabarito() -> list[NotaTomada]:
    arquivo = pasta_exemplos("escrituracao_tomados") / "gabarito_danfse.csv"
    notas = []
    with open(arquivo, encoding="utf-8-sig", newline="") as entrada:
        for linha in csv.DictReader(entrada, delimiter=";"):
            mes, ano = linha["competencia"].split("/")
            notas.append(NotaTomada(
                numero=linha["numero"],
                data_emissao=datetime.strptime(linha["emissao"], "%d/%m/%Y").date(),
                competencia=Competencia(int(ano), int(mes)),
                prestador_documento=linha["prestador_doc"],
                prestador_nome=linha["prestador_nome"],
                prestador_cidade=linha["prestador_cidade"],
                prestador_uf=linha["prestador_uf"],
                tomador_documento=linha["tomador_doc"],
                situacao=linha["situacao"],
                regime=linha["regime"],
                codigo_atividade=linha["atividade"],
                local_prestacao=linha["local_prestacao"],
                municipio_incidencia=linha["municipio_incidencia"],
                valor_servico=_decimal(linha["valor_servico"]),
                deducoes=_decimal(linha["deducoes"]),
                desconto_incondicionado=_decimal(linha["desconto_incondicionado"]),
                aliquota=_decimal(linha["aliquota"]),
                valor_iss=_decimal(linha["iss"]),
                codigo_retido=linha["codigo_retencao"],
                cfps=linha["cfps"],
                chave_acesso=linha["chave"],
                arquivo=linha["arquivo_pdf"],
                motivo=linha["destino_sem_resultado"],      # só para escolher as notas abaixo
                # R8 (regra de 28/09/2026): número com mais de 8 dígitos vai com os 8 últimos
                numero_arquivo=linha["numero"][-8:] if len(linha["numero"]) > 8 else "",
            ))
    return notas


def _conferir_com_esperado(nome_esperado, tomador, competencia, data_lancamento, tipo, notas):
    esperado = pasta_exemplos("escrituracao_tomados", "esperado") / nome_esperado
    conteudo = gerador_txt.gerar_conteudo(tomador, competencia, data_lancamento, tipo, notas)
    assert gerador_txt.conferir_conteudo(conteudo) == []
    gerado = conteudo.encode("latin-1")
    esperado_bytes = esperado.read_bytes()
    if gerado != esperado_bytes:
        linhas_g = gerado.split(b"\r\n")
        linhas_e = esperado_bytes.split(b"\r\n")
        diferencas = [(i + 1, e, g) for i, (e, g) in enumerate(zip(linhas_e, linhas_g)) if e != g]
        pytest.fail(f"{nome_esperado} difere do gerado: {len(linhas_e)} x {len(linhas_g)} linhas; "
                    f"primeiras diferenças (linha, esperado, gerado): {diferencas[:3]}")


FUNDACAO_MATRIZ = "98765432000198"


@pytest.mark.parametrize("competencia, nome, quantidade", [
    (Competencia(2026, 8), "teste1_tomados_98765432000198_08-2026.txt", 12),
    (Competencia(2026, 7), "teste1_tomados_98765432000198_07-2026.txt", 2),
], ids=["08-2026", "07-2026"])
def test_gabarito_teste1_so_pdfs(competencia, nome, quantidade):
    """T1: todas as notas INCLUÍDAS, agrupadas por tomador + competência; Complementar, 28/09/2026."""
    notas = [n for n in _notas_do_gabarito()
             if n.motivo == "INCLUIDA" and n.competencia == competencia]
    assert {n.tomador_documento for n in notas} == {FUNDACAO_MATRIZ}
    assert len(notas) == quantidade
    assert nome == "teste1_" + gerador_txt.nome_arquivo(FUNDACAO_MATRIZ, competencia)
    _conferir_com_esperado(nome, FUNDACAO_MATRIZ, competencia, date(2026, 9, 28), "C", notas)


def test_gabarito_teste1_totais_da_especificacao():
    notas = [n for n in _notas_do_gabarito() if n.motivo == "INCLUIDA"]
    agosto = [n for n in notas if n.competencia == Competencia(2026, 8)]
    julho = [n for n in notas if n.competencia == Competencia(2026, 7)]
    # 11 notas (R$ 21.387,95; ISS R$ 434,17) + a 2026000000090 como 00000090 (R$ 5.369,58; ISS R$ 161,09)
    assert sum(n.valor_servico for n in agosto) == Decimal("26757.53")
    assert sum(n.valor_iss for n in agosto) == Decimal("595.26")
    assert sum(n.valor_servico for n in julho) == Decimal("6315.00")
    assert sum(n.valor_iss for n in julho) == Decimal("156.61")


def test_gabarito_teste2_com_resultados():
    """T2: 95, 118, 215, 249, 337 e a 2026000000090 como 00000090 (as demais já escrituradas);
    Complementar, 24/09/2026."""
    notas = [n for n in _notas_do_gabarito()
             if n.numero in {"95", "118", "215", "249", "337", "2026000000090"}]
    assert sum(n.valor_servico for n in notas) == Decimal("25909.16")
    assert sum(n.valor_iss for n in notas) == Decimal("572.59")
    _conferir_com_esperado("teste2_tomados_98765432000198_08-2026.txt", FUNDACAO_MATRIZ,
                           Competencia(2026, 8), date(2026, 9, 24), "C", notas)


def test_gabarito_teste3_unificado_com_cidade_do_cadastro():
    """T3: 118, 249, 337 (lotes exportados), cidade/UF do cadastro de teste; Normal, 30/09/2026."""
    pasta = pasta_exemplos("escrituracao_tomados", "esperado")
    cadastro = json.loads((pasta / "cadastro_prestadores_teste.json").read_text(encoding="utf-8"))
    notas = [n for n in _notas_do_gabarito() if n.numero in {"118", "249", "337"}]
    for nota in notas:
        nota.prestador_cidade = cadastro[nota.prestador_documento]["cidade"]
        nota.prestador_uf = cadastro[nota.prestador_documento]["uf"]
    _conferir_com_esperado("teste3_unificado_98765432000198_08-2026.txt", FUNDACAO_MATRIZ,
                           Competencia(2026, 8), date(2026, 9, 30), "N", notas)
