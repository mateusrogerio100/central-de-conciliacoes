"""Etapa Tomados 4: exportações de lotes do site, cadastro de prestadores e duplicidades (R13).

- T3: unificar lote_249.txt + lote_337_118.txt -> teste3_unificado_..._08-2026.txt byte a byte.
- T4: PDFs + exportações: 249/337/118 entram uma vez, pela versão do PDF, sem divergência.
- T5: lote antigo com N -> 95, 337 e 118 saem com Z.
- Casos unitários com dados fictícios. A consulta de CNPJ é sempre simulada (conftest.py).
"""

from __future__ import annotations

import json
import shutil
from datetime import date
from decimal import Decimal

import pytest

from modulos.escrituracao_tomados import (
    cadastro_prestadores, gerador_txt, leitor_danfse, leitor_exportacao, regras,
)
from modulos.escrituracao_tomados.cadastro_prestadores import CadastroPrestadores
from modulos.escrituracao_tomados.modelos import Competencia, Destino, ErroLeitura
from testes.conftest import pasta_exemplos

MATRIZ = "98765432000198"
AGOSTO = Competencia(2026, 8)
CABECALHO = ("cfps;nfs;situacaonf;cnpjcpf;nome;dtemissao;descratividade;vlrservicos;"
             "vlrdeducoes;descontoincondicionado;basecalculo;aliquota;impretido;vlrimposto;"
             "enquadradosn;")


class ConsultaSimulada:
    """Faz o papel da consulta pública de CNPJ; registra quem foi consultado."""

    def __init__(self, respostas=None, erro=None):
        self.respostas = respostas or {}
        self.erro = erro
        self.consultados = []

    def __call__(self, cnpj):
        self.consultados.append(cnpj)
        if self.erro:
            raise self.erro
        return self.respostas.get(cnpj)


def processar(notas, cadastro, consultar=None, perguntar=None, escrituradas=None):
    """O caminho que o processamento seguirá: duplicidades -> regras -> cidades -> regras."""
    cadastro_prestadores.aprender_dos_pdfs(notas, cadastro)
    avisos = regras.resolver_duplicidades(notas)
    regras.classificar(notas, escrituradas)
    sem_cidade = [n for n in notas if n.destino in (Destino.INCLUIDA, Destino.LANCAR_A_MAO)
                  and not n.prestador_cidade]
    avisos += cadastro_prestadores.preencher_cidades(sem_cidade, cadastro, consultar, perguntar)
    avisos += regras.classificar(notas, escrituradas)
    return avisos


def _exportacoes(*nomes):
    pasta = pasta_exemplos("escrituracao_tomados", "2026-08", "exportacoes_lotes")
    return [pasta / nome for nome in nomes]


def _cadastro_de_teste(tmp_path):
    origem = pasta_exemplos("escrituracao_tomados", "esperado") / "cadastro_prestadores_teste.json"
    copia = tmp_path / "prestadores.json"
    shutil.copy(origem, copia)
    return CadastroPrestadores(copia)


def _linhas_esperadas(nome):
    esperado = pasta_exemplos("escrituracao_tomados", "esperado") / nome
    return esperado.read_bytes().decode("latin-1").split("\r\n")


# ---------------------------------------------------------------------------
# T3, T4, T5
# ---------------------------------------------------------------------------


def test_t3_unificar_exportacoes(tmp_path):
    notas, falhas = leitor_exportacao.ler_exportacoes(
        _exportacoes("lote_249.txt", "lote_337_118.txt"), MATRIZ, AGOSTO)
    assert falhas == []
    consulta = ConsultaSimulada()
    processar(notas, _cadastro_de_teste(tmp_path), consulta)
    assert consulta.consultados == []                       # tudo estava no cadastro
    assert sorted(n.numero for n in notas if n.destino is Destino.INCLUIDA) == ["118", "249",
                                                                               "337"]
    grupos = regras.agrupar_para_arquivos(notas)
    assert len(grupos) == 1
    conteudo = gerador_txt.gerar_conteudo(MATRIZ, AGOSTO, date(2026, 9, 30), "N",
                                          grupos[0].notas)
    esperado = pasta_exemplos("escrituracao_tomados", "esperado") / \
        "teste3_unificado_98765432000198_08-2026.txt"
    assert conteudo.encode("latin-1") == esperado.read_bytes()


def test_t4_pdfs_e_exportacoes_juntos_vale_o_pdf(tmp_path):
    notas_pdf, _ = leitor_danfse.ler_pasta(pasta_exemplos("escrituracao_tomados", "2026-08",
                                                          "pdfs"))
    exportadas, falhas = leitor_exportacao.ler_exportacoes(
        _exportacoes("lote_249.txt", "lote_337_118.txt"), MATRIZ, AGOSTO)
    assert falhas == []
    avisos = processar(notas_pdf + exportadas, CadastroPrestadores(tmp_path / "p.json"),
                       ConsultaSimulada())
    assert [a for a in avisos if a.tipo == "Divergência PDF x exportação"] == []
    for nota in exportadas:
        assert nota.destino is Destino.DUPLICADA and "vale o PDF" in nota.motivo
    for numero in ("118", "249", "337"):
        incluidas = [n for n in notas_pdf + exportadas
                     if n.numero == numero and n.destino is Destino.INCLUIDA]
        assert len(incluidas) == 1 and incluidas[0].origem == "PDF"
    agosto = next(g for g in regras.agrupar_para_arquivos(notas_pdf + exportadas)
                  if g.competencia == AGOSTO)
    conteudo = gerador_txt.gerar_conteudo(MATRIZ, AGOSTO, date(2026, 9, 28), "C", agosto.notas)
    assert conteudo.split("\r\n") == _linhas_esperadas("teste1_tomados_98765432000198_08-2026.txt")


def test_t5_lote_antigo_com_n_sai_com_z(tmp_path):
    notas, falhas = leitor_exportacao.ler_exportacoes(
        _exportacoes("lote_95_337_118_com_N.csv"), MATRIZ, AGOSTO)
    assert falhas == []
    # os CNPJs vêm do próprio exemplo (dados reais não ficam escritos no código)
    documento = {n.numero: n.prestador_documento for n in notas}
    consulta = ConsultaSimulada({documento["95"]: ("Miguelópolis", "SP"),
                                 documento["337"]: ("CIDADE BETA", "SP"),
                                 documento["118"]: ("ITUVERAVA", "SP")})
    cadastro = CadastroPrestadores(tmp_path / "prestadores.json")
    processar(notas, cadastro, consulta)
    assert {n.numero: n.codigo_retido for n in notas} == {"95": "Z", "337": "Z", "118": "Z"}
    assert sorted(consulta.consultados) == sorted(documento.values())
    # cada linha é idêntica à que o site aceitou (a mesma que sai do PDF)
    conteudo = gerador_txt.gerar_conteudo(MATRIZ, AGOSTO, date(2026, 9, 28), "C", notas)
    esperadas = set(_linhas_esperadas("teste1_tomados_98765432000198_08-2026.txt")[1:-2])
    assert set(conteudo.split("\r\n")[1:-2]) <= esperadas
    cadastro.salvar()
    gravado = json.loads((tmp_path / "prestadores.json").read_text(encoding="utf-8"))
    assert gravado[documento["95"]]["cidade"] == "MIGUELOPOLIS"
    assert gravado[documento["95"]]["origem"] == "consulta CNPJ"


# ---------------------------------------------------------------------------
# Leitor de exportações (dados fictícios)
# ---------------------------------------------------------------------------


def _arquivo(tmp_path, nome, *linhas, codificacao="latin-1"):
    caminho = tmp_path / nome
    caminho.write_bytes(("\r\n".join((CABECALHO,) + linhas) + "\r\n").encode(codificacao))
    return caminho


LINHA_OK = ("1;123;Normal;12.345.678/0001-95;CLINICA EXEMPLO;05/08/2026;04.01.01  Medicina.;"
            "1.000,00;0,00;;1.000,00;2,00;NÃO;20,00;N;")


def test_linha_de_exportacao_vira_nota(tmp_path):
    notas, falhas = leitor_exportacao.ler_exportacoes(
        [_arquivo(tmp_path, "lote.csv", LINHA_OK)], "98.765.432/0001-98", AGOSTO)
    assert falhas == []
    (nota,) = notas
    assert (nota.numero, nota.prestador_documento, nota.codigo_atividade, nota.cfps_site,
            nota.iss_retido, nota.regime, nota.competencia, nota.tomador_documento) == (
        "123", "12345678000195", "040101", "001", False, "N", AGOSTO, MATRIZ)
    assert (nota.valor_servico, nota.deducoes, nota.desconto_incondicionado) == (
        Decimal("1000.00"), Decimal("0.00"), Decimal("0.00"))
    assert nota.base_calculo == Decimal("1000.00")                 # coluna basecalculo do site


def test_nao_estragado_do_site_e_nao(tmp_path):
    linha = LINHA_OK.replace("NÃO", "N�O").replace(";", "\t")
    caminho = tmp_path / "lote.txt"
    caminho.write_bytes((CABECALHO.replace(";", "\t") + "\r\n" + linha + "\r\n").encode("utf-8"))
    notas, falhas = leitor_exportacao.ler_exportacoes([caminho], MATRIZ, AGOSTO)
    assert falhas == [] and notas[0].iss_retido is False


@pytest.mark.parametrize("texto, esperado", [("SIM", True), ("NÃO", False), ("Nao", False),
                                             ("N�O", False), ("M", None), ("NAO SEI", None)])
def test_converter_retido_site(texto, esperado):
    assert leitor_exportacao.converter_retido_site(texto) is esperado


def test_linha_ruim_vira_falha_com_numero_da_linha_e_as_outras_continuam(tmp_path):
    ruim = LINHA_OK.replace("1.000,00;0,00", "mil;0,00")
    notas, falhas = leitor_exportacao.ler_exportacoes(
        [_arquivo(tmp_path, "lote.csv", ruim, LINHA_OK.replace(";123;", ";124;"))],
        MATRIZ, AGOSTO)
    assert [n.numero for n in notas] == ["124"]
    assert [f.arquivo for f in falhas] == ["lote.csv (linha 2)"]


def test_arquivo_sem_as_colunas_vira_falha(tmp_path):
    caminho = tmp_path / "outro.csv"
    caminho.write_text("nfs;cnpjcpf\n1;12345678000195\n", encoding="latin-1")
    notas, falhas = leitor_exportacao.ler_exportacoes([caminho], MATRIZ, AGOSTO)
    assert notas == [] and "vlrservicos" in falhas[0].motivo


def test_competencia_de_texto():
    assert leitor_exportacao.competencia_de_texto("08/2026") == AGOSTO
    assert leitor_exportacao.competencia_de_texto("8/2026") == AGOSTO
    for invalida in ("13/2026", "2026-08", ""):
        with pytest.raises(ErroLeitura):
            leitor_exportacao.competencia_de_texto(invalida)


# ---------------------------------------------------------------------------
# Regras para exportações e R13
# ---------------------------------------------------------------------------


def _notas(tmp_path, *linhas, nome="lote.csv"):
    notas, falhas = leitor_exportacao.ler_exportacoes([_arquivo(tmp_path, nome, *linhas)],
                                                      MATRIZ, AGOSTO)
    assert falhas == []
    return notas


def _cadastro_com_exemplo(tmp_path, cidade="Cidade Alfa"):
    cadastro = CadastroPrestadores(tmp_path / "p.json")
    cadastro.registrar("12345678000195", cidade, "SP", "teste")
    return cadastro


def test_exportacao_com_retido_m_vai_para_lancar_a_mao_sem_codigo(tmp_path):
    notas = _notas(tmp_path, LINHA_OK.replace("NÃO", "M"))
    processar(notas, _cadastro_com_exemplo(tmp_path))
    assert notas[0].destino is Destino.LANCAR_A_MAO and '"M"' in notas[0].motivo
    assert (notas[0].codigo_retido, notas[0].cfps) == ("", "001")


def test_exportacao_com_numero_grande_entra_com_os_8_ultimos_digitos(tmp_path):
    """R8 (decisão da chefia, 28/09/2026): vale também ao unificar lotes."""
    notas = _notas(tmp_path, LINHA_OK.replace(";123;", ";2026000000090;"))
    processar(notas, _cadastro_com_exemplo(tmp_path))
    assert (notas[0].destino, notas[0].numero_arquivo) == (Destino.INCLUIDA, "00000090")
    assert "corrigir no site para 2026000000090" in notas[0].motivo


def test_exportacao_cancelada_e_cfps_do_site(tmp_path):
    notas = _notas(tmp_path, LINHA_OK.replace("Normal", "Cancelada"),
                   "2" + LINHA_OK[1:].replace(";123;", ";124;"))
    processar(notas, _cadastro_com_exemplo(tmp_path, "Uberaba"))
    assert (notas[0].destino, notas[0].motivo) == (Destino.NAO_INCLUIDA, "nota cancelada")
    assert (notas[1].destino, notas[1].cfps, notas[1].codigo_retido) == (
        Destino.INCLUIDA, "002", "Z")


def test_mesma_nota_em_duas_exportacoes_entra_uma_vez(tmp_path):
    a = _notas(tmp_path, LINHA_OK, nome="a.csv")
    b = _notas(tmp_path, LINHA_OK, nome="b.csv")
    processar(a + b, _cadastro_com_exemplo(tmp_path))
    assert (a[0].destino, b[0].destino) == (Destino.INCLUIDA, Destino.DUPLICADA)
    assert "a.csv" in b[0].motivo


def test_pdf_e_exportacao_divergentes_vale_o_pdf_e_avisa(tmp_path):
    pasta = pasta_exemplos("escrituracao_tomados", "2026-08", "pdfs")
    pdf = leitor_danfse.ler_pdf(next(pasta.glob("DANFSe-337-*.pdf")))
    exportada = _notas(tmp_path, f"2;337;Normal;{pdf.prestador_documento};{pdf.prestador_nome};"
                                 "13/08/2026;04.01.01  Medicina.;13.943,00;0,00;;13.943,00;"
                                 "2,00;SIM;278,87;S;")
    avisos = processar([pdf] + exportada, CadastroPrestadores(tmp_path / "p.json"))
    assert pdf.destino is Destino.INCLUIDA and exportada[0].destino is Destino.DUPLICADA
    divergencias = [a.mensagem for a in avisos if a.tipo == "Divergência PDF x exportação"]
    assert len(divergencias) == 4
    for trecho in ("valor do serviço", "CFPS", "regime", "imposto retido"):
        assert any(trecho in d for d in divergencias), trecho


# ---------------------------------------------------------------------------
# Cadastro de prestadores (R11)
# ---------------------------------------------------------------------------


def _nota_sem_cidade(tmp_path, documento="12.345.678/0001-95"):
    (nota,) = _notas(tmp_path, LINHA_OK.replace("12.345.678/0001-95", documento))
    return nota


def test_cadastro_vazio_consulta_a_internet_simulada_e_guarda(tmp_path):
    cadastro = CadastroPrestadores(tmp_path / "p.json")
    nota = _nota_sem_cidade(tmp_path)
    consulta = ConsultaSimulada({"12345678000195": ("Cidade Beta", "sp")})
    avisos = cadastro_prestadores.preencher_cidades([nota, nota], cadastro, consulta)
    assert (nota.prestador_cidade, nota.prestador_uf) == ("CIDADE BETA", "SP")
    assert consulta.consultados == ["12345678000195"]         # uma vez por prestador
    assert [a.tipo for a in avisos] == ["Cidade pela consulta de CNPJ"]
    assert cadastro.obter("12345678000195") == ("CIDADE BETA", "SP")


def test_consulta_falha_e_a_tela_pergunta(tmp_path):
    cadastro = CadastroPrestadores(tmp_path / "p.json")
    nota = _nota_sem_cidade(tmp_path)
    perguntas = []

    def perguntar(documento, nome):
        perguntas.append((documento, nome))
        return "Cidade Alfa", "SP"

    avisos = cadastro_prestadores.preencher_cidades(
        [nota], cadastro, ConsultaSimulada(erro=OSError("sem internet")), perguntar)
    assert perguntas == [("12345678000195", "CLINICA EXEMPLO")]
    assert nota.prestador_cidade == "CIDADE ALFA"
    assert [a.tipo for a in avisos] == ["Consulta de CNPJ falhou", "Cidade informada à mão"]
    assert cadastro.dados["12345678000195"]["origem"] == "informada na tela"


def test_cpf_nao_vai_para_a_consulta(tmp_path):
    nota = _nota_sem_cidade(tmp_path, "123.456.789-09")
    consulta = ConsultaSimulada()
    cadastro_prestadores.preencher_cidades([nota], CadastroPrestadores(tmp_path / "p.json"),
                                           consulta, lambda d, n: ("Cidade Alfa", "SP"))
    assert consulta.consultados == [] and nota.prestador_cidade == "CIDADE ALFA"


def test_sem_cidade_em_lugar_nenhum_vai_para_lancar_a_mao(tmp_path):
    notas = _notas(tmp_path, LINHA_OK)
    avisos = processar(notas, CadastroPrestadores(tmp_path / "p.json"), ConsultaSimulada(),
                       lambda d, n: None)
    assert notas[0].destino is Destino.LANCAR_A_MAO
    assert "cidade do prestador" in notas[0].motivo
    assert "Cidade não encontrada" in [a.tipo for a in avisos]


def test_cadastro_aprende_com_o_pdf(tmp_path):
    pasta = pasta_exemplos("escrituracao_tomados", "2026-08", "pdfs")
    pdf = leitor_danfse.ler_pdf(next(pasta.glob("DANFSe-337-*.pdf")))
    cadastro = CadastroPrestadores(tmp_path / "p.json")
    cadastro_prestadores.aprender_dos_pdfs([pdf], cadastro)
    assert cadastro.obter(pdf.prestador_documento) == ("CIDADE BETA", "SP")
    assert cadastro.dados[pdf.prestador_documento]["origem"] == "PDF"


def test_cadastro_grava_e_le_de_novo(tmp_path):
    caminho = tmp_path / "sub" / "prestadores.json"
    cadastro = CadastroPrestadores(caminho)
    cadastro.salvar()
    assert not caminho.exists()                               # nada mudou: não grava
    cadastro.registrar("12.345.678/0001-95", "São Paulo", "SP", "teste")
    cadastro.salvar()
    assert cadastro.problema_ao_salvar == ""
    assert CadastroPrestadores(caminho).obter("12345678000195") == ("SAO PAULO", "SP")


def test_cadastro_estragado_comeca_vazio_sem_erro(tmp_path):
    caminho = tmp_path / "prestadores.json"
    caminho.write_text("{isto não é json", encoding="utf-8")
    cadastro = CadastroPrestadores(caminho)
    assert cadastro.dados == {} and "não pôde ser lido" in cadastro.problema_ao_abrir


def test_caminho_padrao_fica_no_appdata(tmp_path):
    cadastro = CadastroPrestadores()
    assert cadastro.caminho == (tmp_path / "appdata" / "CentralConciliacoes"
                                / "escrituracao_tomados" / "prestadores.json")


# ---------------------------------------------------------------------------
# Consulta pela internet: só a lógica (as respostas são simuladas)
# ---------------------------------------------------------------------------


def test_consulta_usa_a_brasilapi(monkeypatch):
    urls = []

    def baixar(url):
        urls.append(url)
        return {"municipio": "CIDADE BETA", "uf": "SP"}

    monkeypatch.setattr(cadastro_prestadores, "_baixar_json", baixar)
    assert cadastro_prestadores.consultar_cnpj_internet("22.333.444/0001-81") == (
        "CIDADE BETA", "SP")
    assert urls == ["https://brasilapi.com.br/api/cnpj/v1/22333444000181"]


def test_consulta_usa_a_reserva_se_a_brasilapi_falhar(monkeypatch):
    def baixar(url):
        if "brasilapi" in url:
            raise OSError("fora do ar")
        return {"estabelecimento": {"cidade": {"nome": "Cidade Beta"},
                                    "estado": {"sigla": "SP"}}}

    monkeypatch.setattr(cadastro_prestadores, "_baixar_json", baixar)
    assert cadastro_prestadores.consultar_cnpj_internet("22333444000181") == (
        "CIDADE BETA", "SP")


def test_consulta_levanta_erro_se_as_duas_falharem(monkeypatch):
    def baixar(url):
        raise OSError(f"falhou {url}")

    monkeypatch.setattr(cadastro_prestadores, "_baixar_json", baixar)
    with pytest.raises(OSError):
        cadastro_prestadores.consultar_cnpj_internet("22333444000181")


def test_o_cadeado_de_internet_funciona():
    with pytest.raises(AssertionError, match="internet"):
        cadastro_prestadores.consultar_cnpj_internet("22333444000181")
