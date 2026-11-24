"""L2a e X1a — Nota Fiscal Paulistana (NFS-e da Prefeitura de São Paulo), no PDF e no XML.

Pedido do usuário (18/11/2026). O texto e o XML montados aqui têm CNPJ e nome fictícios (o texto é o
que o pdfplumber tira da 1ª página do PDF). O teste com a nota real (exemplos\\conferencia_nf\\paulistana\\,
fora do git) é pulado sem a pasta.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from modulos.conferencia_nf import leitor_pdfs
from modulos.conferencia_nf.conferencia import conferir
from modulos.conferencia_nf.leitor_paulistana import e_paulistana, ler_paulistana_pdf
from modulos.conferencia_nf.leitor_xml import ler_xml
from modulos.conferencia_nf.modelos import ErroLeitura, Fato, Lancamento, Situacao
from testes.conftest import pasta_exemplos

EMITENTE = "11222333000181"
FUNDACAO = "98765432000198"
# Identificador Nacional: município (7), ambiente (1), tipo de inscrição (1), CNPJ (14), número (13),
# ano e mês (4), código (9), dígito (1)
CHAVE = "3550308" + "1" + "2" + EMITENTE + "0000000004321" + "2611" + "123456789" + "0"

FEDERAIS_NOVO = (
    "Contribuição Previdenciária - Retida (R$) IRRF (R$) COFINS (R$) PIS/PASEP (R$) IPI (R$)\n"
    "0,00 15,00 0,00 0,00 0,00\n"
    "Contribuições Sociais - Retidas (R$) Descrição Contribuições Sociais - Retidas\n"
    "46,50 3 - PIS/COFINS/CSLL Retidos.\n")
FEDERAIS_ANTIGO = "INSS (R$) IRRF (R$) CSLL (R$) COFINS (R$) PIS/PASEP (R$)\n0,00 15,00 10,00 30,00 6,50\n"


def _texto(numero="00004321", chave=CHAVE, cancelada=False, iss_retido=False, layout_novo=True):
    if iss_retido:
        outras = "(3) O ISS desta NFS-e será RETIDO pelo Tomador de Serviço;"
    else:
        outras = "(3) Data de vencimento do ISS desta NFS-e: 10/12/2026;"
    partes = [
        "Número da Nota", "PREFEITURA DO MUNICÍPIO DE SÃO PAULO", numero,
        "SECRETARIA MUNICIPAL DA FAZENDA Data e Hora de Emissão", "03/11/2026 16:39:34",
        "NOTA FISCAL ELETRÔNICA DE SERVIÇOS - NFS-e",
        "NFS-e CANCELADA" if cancelada else "",
        f"Identificador Nacional: {chave}" if chave else "",
        "PRESTADOR DE SERVIÇOS",
        "CPF/CNPJ: 11.222.333/0001-81 Inscrição Municipal:1.234.567-8",
        "Nome/Razão Social: SISTEMAS  TESTE LTDA", "Município: São Paulo UF: SP",
        "TOMADOR DE SERVIÇOS", "Nome/Razão Social: FUNDAÇÃO HOSPITAL EXEMPLO",
        "CPF/CNPJ: 98.765.432/0001-98 Inscrição Municipal:----",
        "INTERMEDIÁRIO DE SERVIÇOS", "CPF/CNPJ: ---- Nome/Razão Social: ----",
        "DISCRIMINAÇÃO DE SERVIÇOS", "Licença mensal.", "VALOR TOTAL DO SERVIÇO = R$ 1.000,00",
        (FEDERAIS_NOVO if layout_novo else FEDERAIS_ANTIGO).rstrip("\n"),
        "Código do Serviço",
        "02800 - Licenciamento ou cessão de direito de uso de programas de computação.",
        "Valor Total das Deduções (R$) Base de Cálculo (R$) Alíquota (%) Valor do ISS (R$) Crédito (R$)",
        "0,00 1.000,00 2,90% 29,00 0,00", "OUTRAS INFORMAÇÕES", outras,
    ]
    return "\n".join(p for p in partes if p) + "\n"


def _xml(status="N", codigo="<RetencaoPisCofins>3</RetencaoPisCofins>", chave=CHAVE, numero="4321",
         iss_retido="false"):
    return ('<?xml version="1.0" encoding="UTF-8"?><NFe xmlns=""><Assinatura>x</Assinatura>'
            f"<ChaveNFe><InscricaoPrestador>12345678</InscricaoPrestador><NumeroNFe>{numero}</NumeroNFe>"
            f"<ChaveNotaNacional>{chave}</ChaveNotaNacional></ChaveNFe>"
            "<DataEmissaoNFe>2026-11-03T16:39:34</DataEmissaoNFe>"
            f"<CPFCNPJPrestador><CNPJ>{EMITENTE}</CNPJ></CPFCNPJPrestador>"
            "<RazaoSocialPrestador>SISTEMAS TESTE LTDA</RazaoSocialPrestador>"
            f"<StatusNFe>{status}</StatusNFe><OpcaoSimples>0</OpcaoSimples>"
            "<ValorServicos>1000.00</ValorServicos><ValorIR>15.00</ValorIR><ValorCSLL>46.50</ValorCSLL>"
            "<CodigoServico>2800</CodigoServico><AliquotaServicos>0.029</AliquotaServicos>"
            f"<ValorISS>29.00</ValorISS><ISSRetido>{iss_retido}</ISSRetido>"
            f"<CPFCNPJTomador><CNPJ>{FUNDACAO}</CNPJ></CPFCNPJTomador>{codigo}</NFe>")


def _gravar_xml(tmp_path, conteudo, nome="NFSe-SP.xml"):
    caminho = tmp_path / nome
    caminho.write_text(conteudo, encoding="utf-8")
    return caminho


# ---------------------------------------------------------------------------
# PDF (pelo texto da 1ª página)
# ---------------------------------------------------------------------------

def test_l2a_pdf_da_nota_paulistana_lido():
    assert e_paulistana(_texto()) and not e_paulistana("DANFE CHAVE DE ACESSO")
    n = ler_paulistana_pdf(_texto(), "nota.pdf")
    assert (n.tipo, n.numero, n.emissao, n.valor) == ("NFS-e", "4321", date(2026, 11, 3), Decimal("1000.00"))
    assert (n.emitente_nome, n.emitente_documento, n.destinatario_documento) == (
        "SISTEMAS TESTE LTDA", EMITENTE, FUNDACAO)
    assert n.chave == CHAVE and n.situacao == "" and not n.xml
    assert (n.irrf, n.previdencia_retida, n.contribuicoes_retidas) == (
        Decimal("15.00"), Decimal("0.00"), Decimal("46.50"))
    assert n.descricao_contribuicoes == "Código 3"
    assert (n.aliquota_iss, n.valor_iss, n.retencao_iss) == (Decimal("2.90"), Decimal("29.00"), "Não Retido")
    assert n.atividade == "02800 - Licenciamento ou cessão de direito de uso de programas de computação."
    assert n.regime == ""                                     # o PDF não diz


def test_l2a_pdf_iss_retido_cancelada_layout_antigo_e_sem_identificador():
    assert ler_paulistana_pdf(_texto(iss_retido=True), "n.pdf").retencao_iss == "Retido"
    assert ler_paulistana_pdf(_texto(cancelada=True), "n.pdf").situacao == "Cancelada"
    antigo = ler_paulistana_pdf(_texto(layout_novo=False), "n.pdf")
    assert antigo.contribuicoes_retidas is None and antigo.irrf is None     # não lido: conferir à mão
    sem_chave = ler_paulistana_pdf(_texto(chave=""), "n.pdf")
    assert sem_chave.chave == "SP" + EMITENTE + "4321".zfill(13)


def test_l2a_numero_que_nao_bate_com_o_identificador_nacional_e_erro():
    with pytest.raises(ErroLeitura, match="Identificador Nacional"):
        ler_paulistana_pdf(_texto(numero="00004322"), "n.pdf")


# ---------------------------------------------------------------------------
# XML
# ---------------------------------------------------------------------------

def test_x1a_xml_da_nota_paulistana_igual_ao_pdf(tmp_path):
    n = ler_xml(_gravar_xml(tmp_path, _xml()), "NFSe-SP.xml")
    pdf = ler_paulistana_pdf(_texto(), "nota.pdf")
    assert n.xml and n.chave == pdf.chave
    for campo in ("tipo", "numero", "emissao", "valor", "emitente_documento", "destinatario_documento",
                  "irrf", "contribuicoes_retidas", "descricao_contribuicoes", "aliquota_iss", "valor_iss",
                  "retencao_iss"):
        assert getattr(n, campo) == getattr(pdf, campo), campo
    assert (n.regime, n.atividade, n.situacao) == ("Não Optante", "02800", "")


def test_x1a_xml_cancelado_iss_retido_e_layout_antigo(tmp_path):
    assert ler_xml(_gravar_xml(tmp_path, _xml(status="C")), "x.xml").situacao == "Cancelada"
    assert ler_xml(_gravar_xml(tmp_path, _xml(iss_retido="true")), "x.xml").retencao_iss == "Retido"
    assert ler_xml(_gravar_xml(tmp_path, _xml(codigo="")), "x.xml").contribuicoes_retidas is None
    with pytest.raises(ErroLeitura, match="Identificador Nacional"):
        ler_xml(_gravar_xml(tmp_path, _xml(numero="4322")), "x.xml")


def test_x1a_nfe_de_compra_sem_protocolo_continua_com_o_aviso_dela(tmp_path):
    nfe = '<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe Id="NFe1"></infNFe></NFe>'
    with pytest.raises(ErroLeitura, match="protocolo"):
        ler_xml(_gravar_xml(tmp_path, nfe), "x.xml")


# ---------------------------------------------------------------------------
# Na conferência: casa com o fato e confere as retenções
# ---------------------------------------------------------------------------

def _l(seq, lado, conta, classificacao, valor, nome, centro_custo=""):
    return Lancamento(sequencia=seq, conta_debito=conta if lado == "D" else "",
                      conta_credito=conta if lado == "C" else "", nome_conta=nome,
                      classificacao=classificacao, valor=Decimal(valor),
                      complemento="Sistemas Teste Ltda NF. 4321 DT 03/11/2026",
                      centro_custo=centro_custo, nome_centro_custo="Controladoria" if centro_custo else "")


def test_l2a_nota_paulistana_casa_com_o_fato_e_confere_retencoes():
    fato = Fato("mov.csv", "900", "04/11/2026", [
        _l("1", "D", "30091", "3.01.02.08.0015", "1000.00", "Licenças", "424"),
        _l("2", "C", "20776", "2.01.03.06.0008", "15.00", "IRRF"),
        _l("3", "C", "25206", "2.01.03.06.0013", "46.50", "Pis/Cofins/CSLL"),
        _l("4", "C", "201777", "2.01.01.01.1842", "938.50", "Sistemas Teste Ltda"),
    ], com_centro_custo=True)
    (r,) = conferir([fato], [ler_paulistana_pdf(_texto(), "nota.pdf")], [], FUNDACAO)
    assert r.nota is not None and r.situacao == Situacao.OK, r.observacoes
    assert {x.imposto for x in r.retencoes} == {"IRRF", "PIS/COFINS/CSLL"}
    assert all(x.confere for x in r.retencoes)


# ---------------------------------------------------------------------------
# Nota real (fora do git)
# ---------------------------------------------------------------------------

def test_nota_paulistana_real_pdf_e_xml_iguais():
    pasta = pasta_exemplos("conferencia_nf", "paulistana")
    notas, falhas = leitor_pdfs.ler_pasta(pasta)
    assert falhas == []
    (nota,) = notas                                           # X2: PDF e XML viram uma nota só
    assert nota.xml and nota.arquivo_pdf.endswith(".pdf") and nota.diferencas_pdf == []
    assert (nota.numero, nota.valor, nota.irrf, nota.contribuicoes_retidas) == (
        "7566", Decimal("2827.35"), Decimal("42.41"), Decimal("131.47"))
    assert nota.destinatario_documento == FUNDACAO and nota.descricao_contribuicoes == "Código 3"
