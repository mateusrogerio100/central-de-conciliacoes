"""X1 a X5 — leitura dos XMLs das notas (NF-e e NFS-e nacional) e junção com o PDF da mesma nota.

Os XMLs montados aqui têm CNPJs fictícios. Os testes com o lote real 72929 (exemplos\\conferencia_nf\\,
fora do git: PDFs e XMLs do dia 02/10/2026) são pulados sem a pasta.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from modulos.conferencia_nf import leitor_pdfs
from modulos.conferencia_nf.conferencia import conferir
from modulos.conferencia_nf.leitor_lote import ler_lote
from modulos.conferencia_nf.leitor_xml import ler_xml
from modulos.conferencia_nf.modelos import ErroLeitura, NotaPdf, Situacao
from testes.conferencia_nf.test_conferencia import _compra
from testes.conftest import pasta_exemplos

EMITENTE = "11222333000181"
FUNDACAO = "98765432000198"
# chave: UF(2) AAMM(4) CNPJ(14) modelo(2) série(3) número(9) tipo de emissão(1) código(8) DV(1)
CHAVE_NFE = "35" + "2609" + EMITENTE + "55" + "001" + "000078055" + "1" + "59140100" + "0"


def _nfe(chave=CHAVE_NFE, numero="78055", cstat="100", protocolo=True, destinatario=FUNDACAO,
         raiz="nfeProc"):
    prot = (f"<protNFe><infProt><cStat>{cstat}</cStat><xMotivo>Uso Denegado</xMotivo></infProt>"
            "</protNFe>") if protocolo else ""
    return (f'<{raiz} xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe Id="NFe{chave}">'
            f"<ide><nNF>{numero}</nNF><dhEmi>2026-09-21T16:10:00-03:00</dhEmi></ide>"
            f"<emit><CNPJ>{EMITENTE}</CNPJ><xNome>BIOLOGICOS   TESTE LTDA</xNome></emit>"
            f"<dest><CNPJ>{destinatario}</CNPJ><xNome>FUNDACAO</xNome></dest>"
            "<total><ICMSTot><vProd>3369.10</vProd><vNF>3369.10</vNF></ICMSTot></total>"
            f"</infNFe></NFe>{prot}</{raiz}>")


def _nfse(retencoes=True, iss=True):
    federais = ("<piscofins><tpRetPisCofins>3</tpRetPisCofins></piscofins>"
                "<vRetIRRF>262.50</vRetIRRF><vRetCP>110.00</vRetCP><vRetCSLL>813.75</vRetCSLL>"
                if retencoes else "")
    valores_iss = "<pAliqAplic>2.00</pAliqAplic><vISSQN>350.00</vISSQN>" if iss else ""
    return ('<?xml version="1.0" encoding="UTF-8"?><NFSe xmlns="http://www.sped.fazenda.gov.br/nfse">'
            '<infNFSe Id="NFS35162001112223330001810000000000033932610032182425">'
            "<nNFSe>3393</nNFSe><xTribNac>Medicina.</xTribNac><cStat>100</cStat>"
            "<dhProc>2026-10-01T00:00:00-03:00</dhProc>"
            f"<emit><CNPJ>{EMITENTE}</CNPJ><xNome>SERVIÇOS MÉDICOS TESTE LTDA</xNome></emit>"
            f"<valores><vBC>17500.00</vBC>{valores_iss}<vLiq>16423.75</vLiq></valores>"
            '<DPS><infDPS Id="DPS1"><dhEmi>2026-09-30T00:00:00-03:00</dhEmi>'
            "<prest><CNPJ>11222333000181</CNPJ><regTrib><opSimpNac>1</opSimpNac></regTrib></prest>"
            f"<toma><CNPJ>{FUNDACAO}</CNPJ><xNome>FUNDACAO</xNome></toma>"
            "<serv><cServ><cTribNac>040101</cTribNac></cServ></serv>"
            "<valores><vServPrest><vServ>17500.00</vServ></vServPrest><trib>"
            "<tribMun><tpRetISSQN>2</tpRetISSQN></tribMun>"
            f"<tribFed>{federais}</tribFed></trib></valores>"
            "</infDPS></DPS></infNFSe></NFSe>")


def _ler(tmp_path, conteudo: str, nome="nota.xml") -> NotaPdf:
    caminho = tmp_path / nome
    caminho.write_text(conteudo, encoding="utf-8")
    return ler_xml(caminho, nome)


# ---------------------------------------------------------------------------
# NF-e
# ---------------------------------------------------------------------------

def test_x1_nfe(tmp_path):
    nota = _ler(tmp_path, _nfe())
    assert (nota.tipo, nota.numero, nota.emissao, nota.valor) == (
        "NF-e", "78055", date(2026, 9, 21), Decimal("3369.10"))
    assert (nota.emitente_nome, nota.emitente_documento, nota.destinatario_documento) == (
        "BIOLOGICOS TESTE LTDA", EMITENTE, FUNDACAO)
    assert (nota.chave, nota.situacao, nota.xml, nota.arquivo) == (
        CHAVE_NFE, "", True, "nota.xml")


def test_x1_nfe_nao_autorizada_fica_com_a_situacao(tmp_path):
    assert _ler(tmp_path, _nfe(cstat="110")).situacao == \
        "Não autorizada (código 110: Uso Denegado)"


@pytest.mark.parametrize("conteudo, mensagem", [
    (_nfe(protocolo=False), "sem o protocolo de autorização"),
    (_nfe(raiz="NFe", protocolo=False), "sem o protocolo de autorização"),
    (_nfe(numero="78056"), "não conferem com a chave"),
    ("<procEventoNFe><evento/></procEventoNFe>", "não é NF-e nem NFS-e"),
    ("<nfeProc><NFe><infNFe", "estragado"),
])
def test_x1_xml_com_problema_e_erro_de_leitura(tmp_path, conteudo, mensagem):
    with pytest.raises(ErroLeitura, match=mensagem):
        _ler(tmp_path, conteudo)


# ---------------------------------------------------------------------------
# NFS-e
# ---------------------------------------------------------------------------

def test_x1_nfse(tmp_path):
    nota = _ler(tmp_path, _nfse())
    assert (nota.tipo, nota.numero, nota.emissao, nota.valor) == (
        "NFS-e", "3393", date(2026, 10, 1), Decimal("17500.00"))   # emissão da NFS-e (dhProc)
    assert (nota.emitente_nome, nota.emitente_documento, nota.destinatario_documento) == (
        "SERVIÇOS MÉDICOS TESTE LTDA", EMITENTE, FUNDACAO)
    assert nota.situacao == ""                     # X2: o XML não diz se foi cancelada depois
    assert (nota.regime, nota.atividade) == ("Não Optante", "04.01.01 - Medicina.")
    assert (nota.aliquota_iss, nota.valor_iss, nota.retencao_iss) == (
        Decimal("2.00"), Decimal("350.00"), "Retido")
    assert (nota.irrf, nota.previdencia_retida, nota.contribuicoes_retidas) == (
        Decimal("262.50"), Decimal("110.00"), Decimal("813.75"))
    assert nota.descricao_contribuicoes == "Código 3"               # S16a, como na DANFSe


def test_x1_nfse_sem_retencoes_nem_iss_fica_zero(tmp_path):
    nota = _ler(tmp_path, _nfse(retencoes=False, iss=False))
    assert nota.federais_lidos
    assert (nota.irrf, nota.previdencia_retida, nota.contribuicoes_retidas, nota.aliquota_iss,
            nota.valor_iss) == (Decimal("0.00"),) * 5


# ---------------------------------------------------------------------------
# Pasta: XML + PDF, repetidos e diferenças (X2 a X4)
# ---------------------------------------------------------------------------

def _pdf(chave=CHAVE_NFE, **campos) -> NotaPdf:
    nota = NotaPdf("NF-e", "78055", date(2026, 9, 21), Decimal("3369.10"), "BIOLOGICOS",
                   EMITENTE, "", chave, "nota.pdf", destinatario_documento=FUNDACAO)
    for campo, valor in campos.items():
        setattr(nota, campo, valor)
    return nota


def test_x2_xml_e_pdf_da_mesma_nota_viram_uma(tmp_path):
    xml = _ler(tmp_path, _nfe())
    juntas = leitor_pdfs._juntar_xml_e_pdf([_pdf(situacao="Cancelada"), xml])
    assert juntas == [xml]
    assert (xml.arquivo_pdf, xml.situacao, xml.diferencas_pdf) == ("nota.pdf", "Cancelada", [])


def test_x2_pdf_de_outra_nota_continua(tmp_path):
    xml = _ler(tmp_path, _nfe())
    outro = _pdf(chave="1" * 44)
    assert leitor_pdfs._juntar_xml_e_pdf([xml, outro]) == [xml, outro]
    assert xml.arquivo_pdf == ""


def test_x3_mesmo_xml_em_duas_pastas_e_repetido(tmp_path):
    for pasta in ("a", "b"):
        (tmp_path / pasta).mkdir()
        (tmp_path / pasta / "nota.xml").write_text(_nfe(), encoding="utf-8")
    notas, falhas = leitor_pdfs.ler_pasta(tmp_path)
    assert falhas == [] and [n.repetida_de for n in notas] == ["", "a/nota.xml"]


def test_x4_xml_e_pdf_diferentes_fica_amarelo(tmp_path):
    xml = _ler(tmp_path, _nfe())
    leitor_pdfs._juntar_xml_e_pdf([_pdf(valor=Decimal("3369.00")), xml])
    assert xml.diferencas_pdf == ["valor: XML 3369.10 x PDF 3369.00"]
    fato = _compra(valor="3369.10", nf="78055", dt="21/09/2026",
                   fornecedor="Biologicos Teste Ltda")
    r = conferir([fato], [xml])[0]
    assert r.situacao == Situacao.CONFERIR
    assert r.observacoes == ["O XML e o PDF da nota não dizem o mesmo (a conferência usou o XML): "
                             "valor: XML 3369.10 x PDF 3369.00."]


def test_x5_xml_estragado_vira_falha_e_o_resto_continua(tmp_path):
    (tmp_path / "boa.xml").write_text(_nfe(), encoding="utf-8")
    (tmp_path / "ruim.xml").write_text("<nfeProc>", encoding="utf-8")
    notas, falhas = leitor_pdfs.ler_pasta(tmp_path)
    assert [n.arquivo for n in notas] == ["boa.xml"]
    assert [f.arquivo for f in falhas] == ["ruim.xml"] and "estragado" in falhas[0].motivo


# ---------------------------------------------------------------------------
# Lote real 72929 (02/10/2026): 61 NF-e e 5 NFS-e, cada uma em PDF e em XML
# ---------------------------------------------------------------------------

CAMPOS = ("tipo", "numero", "emissao", "valor", "emitente_documento", "destinatario_documento",
          "chave")
CAMPOS_SERVICO = ("retencao_iss", "aliquota_iss", "valor_iss", "irrf", "previdencia_retida",
                  "contribuicoes_retidas", "descricao_contribuicoes")


@pytest.fixture(scope="module")
def lote_72929():
    lote = pasta_exemplos("conferencia_nf", "lote_72929")
    so_pdf, falhas_pdf = leitor_pdfs.ler_pasta(lote / "danfe-lote (2)")
    so_xml, falhas_xml = leitor_pdfs.ler_pasta(lote / "Notas_XML")
    assert falhas_pdf == falhas_xml == []
    return lote, so_pdf, so_xml


def test_x1_lote_72929_xml_igual_ao_pdf(lote_72929):
    """O que o XML diz é o que o programa já lia do PDF, campo por campo."""
    _, so_pdf, so_xml = lote_72929
    assert len(so_pdf) == len(so_xml) == 66
    xml_por_chave = {n.chave: n for n in so_xml}
    for pdf in so_pdf:
        xml = xml_por_chave[pdf.chave]
        campos = CAMPOS + (CAMPOS_SERVICO if pdf.tipo == "NFS-e" else ())
        assert [getattr(xml, c) for c in campos] == [getattr(pdf, c) for c in campos], pdf.arquivo
        if pdf.tipo == "NFS-e":
            # a DANFSe corta o regime longo ("Optante - Microempresa ou Empresa de ..."); o XML
            # traz o texto inteiro
            assert xml.regime.startswith(pdf.regime.removesuffix("...").strip()), pdf.arquivo


def test_x2_lote_72929_pasta_inteira(lote_72929):
    lote, _, _ = lote_72929
    notas, falhas = leitor_pdfs.ler_pasta(lote)
    assert falhas == [] and len(notas) == 66
    assert all(n.xml and n.arquivo_pdf and not n.diferencas_pdf for n in notas)
    assert {n.situacao for n in notas if n.tipo == "NFS-e"} == {"Autorizada"}   # veio do PDF


def test_x2_lote_72929_conferencia_igual_so_com_pdf(lote_72929):
    """Conferir com XML + PDF dá o mesmo resultado que conferir só com os PDFs."""
    lote, so_pdf, _ = lote_72929
    fatos = ler_lote(next(lote.glob("Movimento*.csv")))
    notas, _ = leitor_pdfs.ler_pasta(lote)
    com_xml = conferir(fatos, notas, [], FUNDACAO)
    fatos = ler_lote(next(lote.glob("Movimento*.csv")))
    so_com_pdf = conferir(fatos, so_pdf, [], FUNDACAO)
    for a, b in zip(com_xml, so_com_pdf):
        assert (a.fato.fato, a.situacao, a.observacoes, a.nota.chave if a.nota else None) == \
            (b.fato.fato, b.situacao, b.observacoes, b.nota.chave if b.nota else None)
