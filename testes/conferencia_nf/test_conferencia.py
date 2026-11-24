"""T4 e T5 — conferência dos fatos com os PDFs.

T4 usa os lotes reais de exemplos\\conferencia_nf\\ (pulado sem a pasta) e compara com o
gabarito_conferencia.csv. T5 monta fatos e notas fictícios no próprio teste (sem PDF).
"""

from __future__ import annotations

import csv
import shutil
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path, PurePosixPath

import pytest

from modulos.conferencia_nf import leitor_pdfs
from modulos.conferencia_nf.conferencia import (
    chave_nome, conferir, escriturar_na_prefeitura, falar_com_fornecedor, formatar_data,
    formatar_valor, fornecedor_do_fato, semelhanca_nome,
)
from modulos.conferencia_nf.leitor_lote import ler_lote
from modulos.conferencia_nf.modelos import Fato, Lancamento, NotaPdf, NotaSemPdf, Situacao
from testes.conferencia_nf.conftest import ler_pdfs_do_lote
from testes.conftest import pasta_exemplos

# ---------------------------------------------------------------------------
# T4 — lotes reais x gabarito
# ---------------------------------------------------------------------------


def _como_gabarito(r) -> dict:
    n = r.nota
    return {
        "fato": r.fato.fato, "situacao": r.situacao.value, "fornecedor": r.fornecedor,
        "numeros": ", ".join(r.numeros), "datas": ", ".join(formatar_data(d) for d in r.datas),
        "total_debito": str(r.fato.total_debito), "total_credito": str(r.fato.total_credito),
        "partidas_ok": "S" if r.partidas_ok else "N", "arquivo_pdf": n.arquivo if n else "",
        "valor_nota": str(n.valor) if n else "", "observacoes": " ".join(r.observacoes),
    }


def _conferir_lote(lote: Path, pasta_pdfs: Path):
    fatos = ler_lote(next(lote.glob("Movimento*.csv")))
    if pasta_pdfs == lote:
        notas, falhas, _ = ler_pdfs_do_lote(lote.name)
    else:
        notas, falhas = leitor_pdfs.ler_pasta(pasta_pdfs)
    return conferir(fatos, notas, leitor_pdfs.ler_sem_pdf(pasta_pdfs)), notas, falhas


def _gabarito(lote: Path) -> dict[str, dict]:
    with (lote / "gabarito" / "gabarito_conferencia.csv").open(encoding="utf-8-sig",
                                                               newline="") as arquivo:
        return {g["fato"]: g for g in csv.DictReader(arquivo, delimiter=";")}


@pytest.mark.parametrize("nome, contagem, sem_lancamento", [
    ("lote_72648", {"OK": 75, "CONFERIR": 1, "SEM PDF": 11, "SEM Nº DE NOTA": 2}, 102),   # 1 CONFERIR: S19
    ("lote_72887", {"OK": 40, "ESTORNO": 4, "CONFERIR": 2, "SEM PDF": 4, "SEM Nº DE NOTA": 5}, 0),
])
def test_t4_lote_completo_igual_ao_gabarito(nome, contagem, sem_lancamento):
    lote = pasta_exemplos("conferencia_nf", nome)
    resultados, notas, falhas = _conferir_lote(lote, lote)
    gabarito = _gabarito(lote)
    assert falhas == []
    assert [r.fato.fato for r in resultados] == list(gabarito)
    for r in resultados:
        assert _como_gabarito(r) == gabarito[r.fato.fato], r.fato.fato
    assert Counter(r.situacao.value for r in resultados) == contagem
    assert sum(1 for n in notas if not n.usada and not n.repetida_de) == sem_lancamento


def test_t4_lote_72648_so_com_as_duas_pastas_novas(tmp_path):
    lote = pasta_exemplos("conferencia_nf", "lote_72648")
    for subpasta in ("Notas Fiscais/danfe-lote (2)", "Notas Fiscais de Serviço/danfse-lote (11)"):
        shutil.copytree(lote / subpasta, tmp_path / subpasta)
    resultados, notas, falhas = _conferir_lote(lote, tmp_path)
    gabarito = _gabarito(lote)
    assert (len(notas), len(falhas)) == (84, 0)
    for r in resultados:
        lido, esperado = _como_gabarito(r), dict(gabarito[r.fato.fato])
        # as notas que estavam repetidas casam com a cópia das pastas novas: mesmo arquivo,
        # outra pasta
        assert PurePosixPath(lido.pop("arquivo_pdf")).name == \
            PurePosixPath(esperado.pop("arquivo_pdf")).name
        assert lido == esperado, r.fato.fato
    assert sum(1 for n in notas if not n.usada) == 8


def test_t4_estornos_do_lote_72887():
    lote = pasta_exemplos("conferencia_nf", "lote_72887")
    fatos = ler_lote(next(lote.glob("Movimento*.csv")))
    resultados = {r.fato.fato: r for r in conferir(fatos, [], [])}
    estornos = {f for f, r in resultados.items() if r.situacao == Situacao.ESTORNO}
    assert estornos == {"6597265", "6597343", "6599323", "6605899"}
    assert "O que vale é o fato 6597557." in resultados["6597265"].observacoes[0]
    assert resultados["6597557"].situacao == Situacao.SEM_PDF      # sem PDF neste teste


# ---------------------------------------------------------------------------
# T5 — casos montados no teste
# ---------------------------------------------------------------------------

FORNECEDOR = "Cirurgica Exemplo Comercio de Produtos Medicos Ltda"
EMITENTE = "CIRURGICA EXEMPLO COMERCIO E PRODUTOS MEDICOS LTDA"
FUNDACAO, AME_CIDADE_ALFA = "98765432000198", "98765432000430"
ESTOQUE, FORNECEDORES, DESCONTOS, FRETE = "30080", "201777", "40010", "30090"
NOMES_CONTAS = {ESTOQUE: "Material médico", FORNECEDORES: "Cirurgica Exemplo", DESCONTOS: "Descontos obtidos",
                FRETE: "Fretes e carretos custos"}
_sequencia = iter(range(1, 10_000))


def _lanc(lado: str, conta: str, valor: str, complemento: str) -> Lancamento:
    return Lancamento(sequencia=str(next(_sequencia)),
                      conta_debito=conta if lado == "D" else "",
                      conta_credito=conta if lado == "C" else "",
                      nome_conta=NOMES_CONTAS[conta], classificacao="",
                      valor=Decimal(valor), complemento=complemento)


def _fato(numero: str, *lancamentos: Lancamento) -> Fato:
    return Fato("lote.csv", numero, "01/10/2026", list(lancamentos))


def _compra(numero_fato="100", valor="29.80", nf="1851605", dt="25/09/2026", invertido=False,
            fornecedor=FORNECEDOR) -> Fato:
    """Compra simples: débito no estoque, crédito no fornecedor (invertido = estorno)."""
    complemento = f"{fornecedor} NF. {nf} DT{dt} O.C 811215"
    debito, credito = (FORNECEDORES, ESTOQUE) if invertido else (ESTOQUE, FORNECEDORES)
    return _fato(numero_fato, _lanc("D", debito, valor, complemento),
                 _lanc("C", credito, valor, complemento))


def _nota(numero="1851605", valor="29.80", emissao=date(2026, 9, 25), emitente=EMITENTE,
          situacao="", arquivo=None, tipo="NF-e") -> NotaPdf:
    nota = NotaPdf(tipo=tipo, numero=numero, emissao=emissao, valor=Decimal(valor),
                   emitente_nome=emitente, emitente_documento="00909901000109",
                   situacao=situacao, chave="", arquivo=arquivo or f"{emitente}-{numero}.pdf",
                   destinatario_documento=FUNDACAO)
    if tipo == "NFS-e":            # DANFSe lida, sem nenhuma retenção (S10, S13)
        nota.irrf = nota.previdencia_retida = nota.contribuicoes_retidas = Decimal("0.00")
        nota.retencao_iss, nota.valor_iss = "Não Retido", Decimal("0.00")
    return nota


def _um(fatos, notas=(), sem_pdf=()):
    return conferir(list(fatos), list(notas), list(sem_pdf))


# ---------------------------------------------------------------------------
# S15 — CNPJ do destinatário / tomador x unidade escolhida na tela
# ---------------------------------------------------------------------------


def _com_unidade(nota: NotaPdf, unidade=FUNDACAO, fato=None):
    return conferir([fato or _compra()], [nota], [], unidade)[0]


def test_s15_cnpj_da_unidade_escolhida_fica_ok():
    r = _com_unidade(_nota())
    assert (r.situacao, r.confere_destinatario, r.observacoes) == (Situacao.OK, "OK", [])


def test_s15_nota_de_outra_unidade_fica_divergente():
    r = _com_unidade(_nota(), unidade=AME_CIDADE_ALFA)
    assert (r.situacao, r.confere_destinatario) == (Situacao.DIVERGENTE, "ERRADO")
    assert r.observacoes == [
        "CNPJ do destinatário errado: a nota veio para Fundação Hospital Exemplo "
        "(98.765.432/0001-98); a unidade conferida é AME Cidade Alfa (98.765.432/0004-30)."]


def test_s15_cmd_e_uma_unidade():
    # Pedido do usuário (04/11/2026): as notas do CMD também são conferidas
    cmd = "98765432000945"

    def nota_do_cmd():
        nota = _nota()
        nota.destinatario_documento = cmd
        return nota

    assert _com_unidade(nota_do_cmd(), unidade=cmd).situacao == Situacao.OK
    r = _com_unidade(nota_do_cmd())
    assert r.situacao == Situacao.DIVERGENTE
    assert r.observacoes == [
        "CNPJ do destinatário errado: a nota veio para CMD (98.765.432/0009-45); a unidade "
        "conferida é Fundação Hospital Exemplo (98.765.432/0001-98)."]


def test_s15_cnpj_fora_da_fundacao_e_nota_de_servico_falam_do_tomador():
    nota = _nota(tipo="NFS-e")
    nota.destinatario_documento = "52998224725"
    r = _com_unidade(nota)
    assert r.situacao == Situacao.DIVERGENTE
    assert r.observacoes == [
        "CNPJ do tomador errado: a nota veio para 529.982.247-25, que não é de nenhuma unidade da "
        "Fundação; a unidade conferida é Fundação Hospital Exemplo (98.765.432/0001-98)."]


def test_s15_cnpj_nao_lido_fica_conferir():
    nota = _nota()
    nota.destinatario_documento = ""
    r = _com_unidade(nota)
    assert (r.situacao, r.confere_destinatario) == (Situacao.CONFERIR, "NÃO LIDO")
    assert "não foi lido" in r.observacoes[0]


def test_s15_vermelho_ganha_do_roxo_da_retencao():
    nota = _nota(tipo="NFS-e")
    nota.irrf = Decimal("15.00")                   # retido na nota, sem crédito no fato
    r = _com_unidade(nota, unidade=AME_CIDADE_ALFA)
    assert r.situacao == Situacao.DIVERGENTE
    assert [o.split(":")[0] for o in r.observacoes] == [
        "CNPJ do tomador errado", "Alíquota do IRRF da nota",                 # S15, S16
        "Retenção de IRRF (conta 20776)"]                                     # S13


def test_s15_sem_unidade_nao_confere_e_fato_sem_pdf_fica_de_fora():
    assert _um([_compra()], [_nota()])[0].confere_destinatario == ""
    r = conferir([_compra()], [], [], AME_CIDADE_ALFA)[0]
    assert (r.situacao, r.confere_destinatario) == (Situacao.SEM_PDF, "")


@pytest.mark.parametrize("nome", ["lote_72648", "lote_72887"])
def test_s15_lotes_reais(nome):
    """Conferidos como Fundação, ficam iguais ao gabarito; como AME Cidade Alfa, todo fato casado
    fica vermelho."""
    lote = pasta_exemplos("conferencia_nf", nome)
    fatos = ler_lote(next(lote.glob("Movimento*.csv")))
    sem_pdf = leitor_pdfs.ler_sem_pdf(lote)
    gabarito = _gabarito(lote)
    notas, _, _ = ler_pdfs_do_lote(nome)
    for r in conferir(fatos, notas, sem_pdf, FUNDACAO):
        assert _como_gabarito(r) == gabarito[r.fato.fato], r.fato.fato
    notas, _, _ = ler_pdfs_do_lote(nome)
    casados = [r for r in conferir(fatos, notas, sem_pdf, AME_CIDADE_ALFA) if r.nota]
    assert casados and all(r.situacao == Situacao.DIVERGENTE for r in casados)


def test_s9_so_nota_casada_com_danfse_vai_para_a_prefeitura():
    servico, compra, sem_pdf = _um([_compra("1", nf="1"), _compra("2", nf="2"), _compra("3", nf="3")],
                                   [_nota("1", tipo="NFS-e"), _nota("2")])
    assert escriturar_na_prefeitura(servico)
    assert not escriturar_na_prefeitura(compra)
    assert not escriturar_na_prefeitura(sem_pdf)


def _servico(**campos) -> NotaPdf:
    nota = _nota("1", tipo="NFS-e", situacao="Autorizada")
    federais = dict(regime="Não Optante", irrf=Decimal("0.00"), previdencia_retida=Decimal("0.00"),
                    contribuicoes_retidas=Decimal("0.00"))
    for campo, valor in {**federais, **campos}.items():
        setattr(nota, campo, valor)
    return nota


@pytest.mark.parametrize("campos, esperado", [
    ({}, True),                                                     # Não Optante sem federal
    ({"retencao_iss": "Retido"}, True),                             # o ISS não entra na regra
    ({"irrf": Decimal("15.00")}, False),
    ({"previdencia_retida": Decimal("110.00")}, False),
    ({"contribuicoes_retidas": Decimal("46.50")}, False),
    ({"regime": "Optante - Microempresa ou Empresa de Pequeno Porte (ME/EPP)"}, False),
    ({"regime": ""}, False),                                        # regime não lido
    ({"irrf": None}, False),                                        # federal não lido
])
def test_s10_falar_com_o_fornecedor(campos, esperado):
    (r,) = _um([_compra("1", nf="1")], [_servico(**campos)])
    assert falar_com_fornecedor(r) is esperado
    # S10 é só informativa; a retenção na nota sem o crédito no fato é a S13 (roxo)
    assert r.situacao in (Situacao.OK, Situacao.RETENCAO)


def test_s10_compra_e_fato_sem_pdf_nunca_entram():
    compra = _nota("1")
    compra.regime = "Não Optante"
    (r_compra,) = _um([_compra("1", nf="1")], [compra])
    (r_sem_pdf,) = _um([_compra("2", nf="2")])
    assert not falar_com_fornecedor(r_compra) and not falar_com_fornecedor(r_sem_pdf)


def test_tudo_confere_fica_ok():
    r, = _um([_compra()], [_nota()])
    assert (r.situacao, r.confere_numero, r.confere_data, r.confere_valor, r.observacoes) == \
        (Situacao.OK, "OK", "OK", "OK", [])


def test_valor_diferente_fica_divergente_com_os_dois_valores():
    r, = _um([_compra(valor="29.80")], [_nota(valor="19.80")])
    assert r.situacao == Situacao.DIVERGENTE and r.confere_valor == "DIVERGE"
    assert r.observacoes == ["Valor: Tasy (total dos débitos) 29,80 x nota 19,80 "
                             "(diferença 10,00)."]


def test_dt_diferente_fica_divergente():
    r, = _um([_compra(dt="24/09/2026")], [_nota()])
    assert r.situacao == Situacao.DIVERGENTE and r.confere_data == "DIVERGE"
    assert r.observacoes == ["Data de emissão: Tasy 24/09/2026 x nota 25/09/2026."]


def test_complemento_sem_dt_fica_divergente():
    complemento = f"{FORNECEDOR} NF. 1851605"
    fato = _fato("100", _lanc("D", ESTOQUE, "29.80", complemento),
                 _lanc("C", FORNECEDORES, "29.80", complemento))
    r, = _um([fato], [_nota()])
    assert (r.situacao, r.confere_data) == (Situacao.DIVERGENTE, "SEM DT")
    assert "Complemento sem a data de emissão (DT)." in r.observacoes


def test_linha_de_retencao_sem_dt_nao_atrapalha():
    """Linha de retenção (nota 1248 do lote): a linha de retenção traz só "NF. número"; vale a DT das outras."""
    com_dt, sem_dt = f"{FORNECEDOR} NF. 1248 DT 16/09/2026", f"{FORNECEDOR} NF. 1248"
    fato = _fato("100", _lanc("D", ESTOQUE, "1000.00", com_dt),
                 _lanc("C", FORNECEDORES, "985.00", com_dt),
                 _lanc("C", FORNECEDORES, "15.00", sem_dt))
    r, = _um([fato], [_nota("1248", "1000.00", date(2026, 9, 16))])
    assert r.situacao == Situacao.OK


def test_dois_numeros_no_mesmo_fato_fica_divergente():
    a, b = f"{FORNECEDOR} NF. 1851605 DT25/09/2026", f"{FORNECEDOR} NF. 1851606 DT25/09/2026"
    fato = _fato("100", _lanc("D", ESTOQUE, "29.80", a), _lanc("C", FORNECEDORES, "29.80", b))
    r, = _um([fato], [_nota()])
    assert (r.situacao, r.confere_numero) == (Situacao.DIVERGENTE, "DIVERGE")
    assert "Os lançamentos do fato citam números de nota diferentes: 1851605, 1851606." \
        in r.observacoes


def test_partidas_que_nao_fecham_ficam_divergentes_mesmo_com_o_resto_ok():
    complemento = f"{FORNECEDOR} NF. 1851605 DT25/09/2026"
    fato = _fato("100", _lanc("D", ESTOQUE, "29.80", complemento),
                 _lanc("C", FORNECEDORES, "28.80", complemento))
    r, = _um([fato], [_nota()])
    assert not r.partidas_ok and r.situacao == Situacao.DIVERGENTE
    assert "Partidas e contrapartidas não fecham: débitos 29,80 x créditos 28,80 (diferença " \
           "1,00)." in r.observacoes


def test_partidas_sem_credito_nao_fecham():
    fato = _fato("100", _lanc("D", ESTOQUE, "29.80", f"{FORNECEDOR} NF. 1 DT25/09/2026"))
    r, = _um([fato])
    assert not r.partidas_ok


def test_mesmo_numero_de_outro_fornecedor_e_outro_valor_nao_casa():
    r, = _um([_compra()], [_nota(emitente="FARMACIA EXEMPLO LTDA", valor="50.00")])
    assert r.situacao == Situacao.SEM_PDF and r.nota is None
    assert r.observacoes == ["Há PDF com o mesmo número, mas de outro fornecedor e outro valor "
                             "(FARMACIA EXEMPLO LTDA, R$ 50,00): não foi considerado."]


def test_mesmo_numero_escolhe_o_fornecedor_certo():
    outro = _nota(emitente="FARMACIA EXEMPLO LTDA", valor="29.80")
    certo = _nota()
    r, = _um([_compra()], [outro, certo])
    assert r.nota is certo and r.situacao == Situacao.OK and not outro.usada


def test_nome_diferente_mas_mesmo_valor_casa_e_fica_amarelo():
    r, = _um([_compra(fornecedor="Omega Exemplo Do Brasil Ltda.")],
             [_nota(emitente="OXB BR I.C.P.S.LTDA")])
    assert r.situacao == Situacao.CONFERIR and r.nota is not None
    assert r.observacoes == ["Número, data e valor conferem com o PDF, mas o nome do fornecedor é "
                             "diferente (na nota: OXB BR I.C.P.S.LTDA)."]


def test_nome_diferente_mesmo_valor_e_dt_errada_fica_divergente():
    r, = _um([_compra(fornecedor="Omega Exemplo Do Brasil Ltda.", dt="20/09/2026")],
             [_nota(emitente="OXB BR I.C.P.S.LTDA")])
    assert r.situacao == Situacao.DIVERGENTE
    assert r.observacoes[-1] == ("Casada pelo número e pelo valor, mas o nome do fornecedor é "
                                 "diferente (na nota: OXB BR I.C.P.S.LTDA): conferir.")


def test_nota_cancelada_fica_conferir():
    r, = _um([_compra(nf="967")], [_nota("967", situacao="Cancelada", tipo="NFS-e")])
    assert r.situacao == Situacao.CONFERIR
    assert r.observacoes == ["Situação da nota no PDF: Cancelada."]


def test_recibo_e_doacao_ficam_sem_numero():
    recibo = _fato("1", _lanc("D", ESTOQUE, "216.00", "Pessoa Exemplo Lima Recibo n° 107 - Biopsia"),
                   _lanc("C", FORNECEDORES, "216.00", "Pessoa Exemplo Lima Recibo n° 107 - Biopsia"))
    doacao = _fato("2", _lanc("D", ESTOQUE, "790.09", "Secretaria de Estado da Saúde 3005813 - "
                                                      "Doação"),
                   _lanc("C", FORNECEDORES, "790.09", "Secretaria de Estado da Saúde 3005813 - "
                                                      "Doação"))
    r1, r2 = _um([recibo, doacao])
    assert (r1.situacao, r1.fornecedor) == (Situacao.SEM_NUMERO, "Pessoa Exemplo Lima")
    assert r1.observacoes == ["Complemento sem \"NF. número\" (recibo): conferir à mão."]
    assert (r2.situacao, r2.fornecedor) == (Situacao.SEM_NUMERO, "Secretaria de Estado da Saúde")
    assert "doação, taxa ou outro documento" in r2.observacoes[0]


def test_sem_pdf_e_nota_listada_no_sem_pdf_txt():
    a, b = _um([_compra("1", nf="1851605"), _compra("2", nf="688389")],
               sem_pdf=[NotaSemPdf("3526...", "11444777000161", "688389", "_sem_pdf.txt")])
    assert (a.situacao, a.observacoes) == (Situacao.SEM_PDF,
                                           ["PDF da nota não encontrado na pasta."])
    assert b.situacao == Situacao.SEM_PDF
    assert b.observacoes == ["Nota listada em _sem_pdf.txt: veio sem DANFE (precisa do XML "
                             "completo)."]


def test_c4_o_pdf_casa_com_um_fato_so():
    primeiro = _compra("1")
    segundo = _fato("2", *_compra("2").lancamentos[:1],
                    _lanc("C", FRETE, "29.80", f"{FORNECEDOR} NF. 1851605 DT25/09/2026"))
    r1, r2 = _um([primeiro, segundo], [_nota()])
    assert r1.situacao == Situacao.OK
    assert r2.situacao == Situacao.SEM_PDF
    assert r2.observacoes == ["O PDF desta nota existe, mas já foi usado no fato 1: a mesma nota "
                              "aparece em mais de um fato do lote."]


def test_pdf_repetido_nao_entra_no_casamento():
    repetido = _nota(arquivo="b.pdf")
    repetido.repetida_de = "a.pdf"
    r, = _um([_compra()], [repetido])
    assert r.situacao == Situacao.SEM_PDF and not repetido.usada


# --- estorno (F6)

def test_lancamento_e_estorno_se_anulam():
    r1, r2 = _um([_compra("100"), _compra("101", invertido=True)], [_nota()])
    assert r1.situacao == r2.situacao == Situacao.ESTORNO
    assert r1.observacoes == ["Os fatos 100 e 101 são o mesmo lançamento com débito e crédito "
                              "invertidos (lançamento e estorno): um anula o outro. Não sobrou "
                              "lançamento deste documento no lote."]
    assert r1.nota is None and r2.nota is None


def test_lancamento_estorno_e_novo_lancamento_vale_o_novo():
    resultados = _um([_compra("102"), _compra("100"), _compra("101", invertido=True)], [_nota()])
    por_fato = {r.fato.fato: r for r in resultados}
    assert por_fato["100"].situacao == por_fato["101"].situacao == Situacao.ESTORNO
    assert por_fato["100"].observacoes[0].endswith("O que vale é o fato 102.")
    assert por_fato["102"].situacao == Situacao.OK and por_fato["102"].nota is not None


def test_estorno_compara_o_numero_do_fato_como_numero():
    """6599323 e 6605899: o fato 99 vem antes do 100 (não é ordem de texto)."""
    resultados = _um([_compra("100", invertido=True), _compra("99")])
    assert {r.situacao for r in resultados} == {Situacao.ESTORNO}
    assert resultados[0].observacoes[0].startswith("Os fatos 99 e 100 ")


def test_lancamento_repetido_sem_estorno_nao_fica_verde():
    r1, r2 = _um([_compra("100"), _compra("101")], [_nota()])
    assert r1.situacao == Situacao.CONFERIR
    assert r1.observacoes == ["Mesmo lançamento repetido no fato 101."]
    assert r2.situacao == Situacao.SEM_PDF
    assert "Mesmo lançamento repetido no fato 100." in r2.observacoes


# --- desconto lançado à parte (S3a)

def _com_desconto(conta_credito: str, desconto: str = "10.00") -> Fato:
    complemento = f"{FORNECEDOR} NF. 1851605 DT25/09/2026"
    return _fato("100", _lanc("D", ESTOQUE, "29.80", complemento),
                 _lanc("C", FORNECEDORES, str(Decimal("29.80") - Decimal(desconto)), complemento),
                 _lanc("C", conta_credito, desconto, complemento))


def test_desconto_a_parte_a_credito_fica_ok():
    r, = _um([_com_desconto(DESCONTOS)], [_nota(valor="19.80")])
    assert r.situacao == Situacao.OK
    assert r.confere_valor == "OK (desconto à parte de 10,00)"


def test_desconto_com_valor_errado_fica_divergente():
    r, = _um([_com_desconto(DESCONTOS, desconto="5.00")], [_nota(valor="19.80")])
    assert r.situacao == Situacao.DIVERGENTE and r.confere_valor == "DIVERGE"


def test_credito_em_conta_que_nao_e_de_desconto_fica_divergente():
    r, = _um([_com_desconto(FRETE)], [_nota(valor="19.80")])
    assert r.situacao == Situacao.DIVERGENTE and r.confere_valor == "DIVERGE"


# --- funções de apoio

def test_fornecedor_sem_nada_vem_do_maior_credito():
    fato = _fato("1", _lanc("D", ESTOQUE, "10.00", "texto"), _lanc("C", FORNECEDORES, "10.00",
                                                                   "texto"))
    assert fornecedor_do_fato(fato) == "Cirurgica Exemplo"


@pytest.mark.parametrize("a, b, minimo", [
    ("Cirurgica Exemplo Comercio de Produtos Medicos Ltda", EMITENTE, 0.6),
    ("Locadora Exemplo Rent A Car S/A", "LOCADORA EXEMPLO RENT A CAR SA", 1.0),
    ("Bioexemplo Comercial Médica Ltda.", "BIOEXEMPLO Comercial Médica Ltda.", 1.0),
])
def test_semelhanca_de_nomes(a, b, minimo):
    assert semelhanca_nome(a, b) >= minimo


def test_nomes_diferentes_ficam_abaixo_do_minimo():
    assert semelhanca_nome("Omega Exemplo Do Brasil Ltda.", "OXB BR I.C.P.S.LTDA") < 0.6
    assert semelhanca_nome("", "X") == 0.0


def test_chave_nome():
    assert chave_nome("Pharmácia Exemplar Ltda. - ME") == "PHARMACIA EXEMPLAR"


@pytest.mark.parametrize("valor, texto", [
    ("29.8", "29,80"), ("1234567.5", "1.234.567,50"), ("-10", "-10,00"), ("0", "0,00"),
])
def test_formatar_valor(valor, texto):
    assert formatar_valor(Decimal(valor)) == texto
