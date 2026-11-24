"""T9 — S13: retenções da nota de serviço (DANFSe) x créditos nas contas de imposto (roxo).

Nos lotes de exemplo as retenções das cinco notas de serviço com imposto retido batem
(o gabarito não muda); os erros são montados com dados fictícios.
"""

from __future__ import annotations

from decimal import Decimal

import openpyxl
import pytest

from modulos.conferencia_nf import leitor_pdfs
from modulos.conferencia_nf.conferencia import conferir
from modulos.conferencia_nf.leitor_lote import ler_lote
from modulos.conferencia_nf.modelos import Fato, Lancamento, Situacao
from modulos.conferencia_nf.relatorio import gerar_relatorio
from testes.conferencia_nf.conftest import ler_pdfs_do_lote
from testes.conferencia_nf.test_conferencia import _nota
from testes.conftest import pasta_exemplos

ZERO = Decimal("0.00")
COMPLEMENTO = "Cirurgica Exemplo Comercio de Produtos Medicos Ltda NF. 1851605 DT25/09/2026 O.C 811215"


@pytest.mark.parametrize("lote, com_retencao", [
    ("lote_72648", {"6580774", "6580776", "6581027"}),
    ("lote_72887", {"6599846", "6599901"}),
])
def test_t9_retencoes_dos_lotes_de_exemplo_batem(lote, com_retencao):
    pasta = pasta_exemplos("conferencia_nf", lote)
    notas, _, _ = ler_pdfs_do_lote(lote)
    resultados = conferir(ler_lote(next(pasta.glob("Movimento*.csv"))), notas,
                          leitor_pdfs.ler_sem_pdf(pasta))
    assert {r.fato.fato for r in resultados if r.retencoes} == com_retencao
    assert all(x.confere for r in resultados for x in r.retencoes)
    assert not any(r.situacao == Situacao.RETENCAO for r in resultados)


def _l(lado, conta, valor) -> Lancamento:
    return Lancamento(sequencia=conta, conta_debito=conta if lado == "D" else "",
                      conta_credito=conta if lado == "C" else "", nome_conta=f"Conta {conta}",
                      classificacao="", valor=Decimal(valor), complemento=COMPLEMENTO)


def _servico(*retencoes, total="29.80") -> Fato:
    """Despesa de 29,80 a débito; créditos: as retenções e o líquido ao fornecedor."""
    retido = sum((Decimal(v) for _, v in retencoes), ZERO)
    return Fato("lote.csv", "900", "01/10/2026",
                [_l("D", "30080", total)] + [_l("C", conta, v) for conta, v in retencoes]
                + [_l("C", "201777", str(Decimal(total) - retido))])


def _danfse(documento="00909901000109", irrf=ZERO, inss=ZERO, cs=ZERO, iss_retido=False,
            iss=ZERO):
    nota = _nota(tipo="NFS-e", situacao="Autorizada")
    nota.emitente_documento = documento
    nota.irrf, nota.previdencia_retida, nota.contribuicoes_retidas = irrf, inss, cs
    nota.retencao_iss = "Retido" if iss_retido else "Não Retido"
    nota.valor_iss = iss
    return nota


def _um(fato, nota):
    (r,) = conferir([fato], [nota])
    return r


def test_s13_todas_as_retencoes_batem_fica_ok():
    r = _um(_servico(("20776", "0.45"), ("20769", "3.28"), ("25206", "1.39"), ("21996", "0.60")),
            _danfse(irrf=Decimal("0.45"), inss=Decimal("3.28"), cs=Decimal("1.39"),
                    iss_retido=True, iss=Decimal("0.60")))
    assert r.situacao == Situacao.OK
    assert [(x.imposto, x.conta) for x in r.retencoes] == [
        ("IRRF", "20776"), ("INSS", "20769"), ("PIS/COFINS/CSLL", "25206"), ("ISS", "21996")]


@pytest.mark.parametrize("creditos, nota, frase", [
    ((), dict(inss=Decimal("3.28")), "Retenção de INSS (conta 20769): nota 3,28 x lançado 0,00."),
    ((("25206", "1.30"),), dict(cs=Decimal("1.39")),
     "Retenção de PIS/COFINS/CSLL (conta 25206): nota 1,39 x lançado 1,30."),
    ((("20776", "0.45"),), {}, "Retenção de IRRF (conta 20776): nota 0,00 x lançado 0,45."),
    ((("21996", "0.60"),), dict(iss=Decimal("0.60")),        # ISS da nota "Não Retido"
     "Retenção de ISS (conta 21996): nota 0,00 x lançado 0,60."),
    ((), dict(iss_retido=True, iss=Decimal("0.60")),
     "Retenção de ISS (conta 21996): nota 0,60 x lançado 0,00."),
])
def test_s13_retencao_que_nao_bate_fica_roxa(creditos, nota, frase):
    r = _um(_servico(*creditos), _danfse(**nota))
    assert r.situacao == Situacao.RETENCAO
    assert frase in r.observacoes


def test_s13_irrf_de_pessoa_fisica_vai_na_20775():
    certo = _um(_servico(("20775", "0.45")), _danfse(documento="52998224725",
                                                     irrf=Decimal("0.45")))
    assert certo.situacao == Situacao.OK
    errado = _um(_servico(("20776", "0.45")), _danfse(documento="52998224725",
                                                      irrf=Decimal("0.45")))
    assert errado.situacao == Situacao.RETENCAO


def test_s13_imposto_nao_lido_na_nota_fica_roxo_para_conferir_no_pdf():
    r = _um(_servico(("20776", "0.45")), _danfse(irrf=None))
    assert r.situacao == Situacao.RETENCAO
    assert any("não foi possível ler na nota" in o for o in r.observacoes)


def test_s13_divergente_continua_vermelho_e_compra_nao_e_conferida():
    errado = _servico(total="30.00")                            # nota de 29,80
    r = _um(errado, _danfse(inss=Decimal("3.28")))
    assert r.situacao == Situacao.DIVERGENTE
    assert any(o.startswith("Retenção de INSS") for o in r.observacoes)
    compra = _um(_servico(("20769", "3.28")), _nota())             # DANFE: S13 não se aplica
    assert compra.retencoes == [] and compra.situacao == Situacao.OK


def test_s13_relatorio_em_roxo_com_o_motivo(tmp_path):
    nota = _danfse(inss=Decimal("3.28"))
    resultados = conferir([_servico()], [nota])
    caminho = gerar_relatorio(tmp_path / "r.xlsx", resultados, [nota], [], [], [], ["lote.csv"])
    livro = openpyxl.load_workbook(caminho)
    aba = livro["Conferir à mão"]
    assert aba["A2"].value == "Retenção da nota não bate com o lançamento"
    assert aba["A2"].fill.fgColor.rgb.endswith("D9C2EC")
    resumo = {l[0]: l[1] for l in livro["Resumo"].iter_rows(values_only=True)}
    assert resumo["      retenção da nota não bate com o lançamento (roxo)"] == 1


# ---------------------------------------------------------------------------
# S16 — alíquota de cada retenção sobre o valor do serviço
# ---------------------------------------------------------------------------

def _servico_mil(nota_valor="1000.00", documento="00909901000109", **retidos):
    """Nota de serviço de R$ 1.000,00 com as retenções dadas, lançadas iguais (a S13 confere)."""
    nota = _danfse(documento=documento, **{k: Decimal(v) for k, v in retidos.items()})
    nota.valor = Decimal(nota_valor)
    contas = {"irrf": "20775" if len(documento) == 11 else "20776", "inss": "20769",
              "cs": "25206"}
    return _um(_servico(*[(contas[k], v) for k, v in retidos.items()], total=nota_valor), nota)


def test_s16_aliquotas_certas_ficam_ok():
    r = _servico_mil(irrf="15.00", cs="46.50", inss="110.00")
    assert (r.situacao, r.aliquotas_erradas) == (Situacao.OK, [])
    assert _servico_mil(inss="200.00").situacao == Situacao.OK            # INSS de 20%


def test_s16_aceita_um_centavo_de_arredondamento():
    # uma nota do lote 72648: 3.816,96 x 4,65% = 177,4886 (177,49); a nota cortou para 177,48
    assert _servico_mil("3816.96", cs="177.48").situacao == Situacao.OK
    assert _servico_mil("3816.96", cs="177.51").situacao == Situacao.RETENCAO      # 2 centavos


@pytest.mark.parametrize("retidos, frase", [
    (dict(irrf="10.00"), "Alíquota do IRRF da nota: R$ 10,00 = 1% do serviço (R$ 1.000,00); "
                         "esperado 1,5% = R$ 15,00."),
    (dict(cs="30.00"), "Alíquota do PIS/COFINS/CSLL da nota: R$ 30,00 = 3% do serviço "
                       "(R$ 1.000,00); esperado 4,65% = R$ 46,50."),
    (dict(inss="35.00"), "Alíquota do INSS da nota: R$ 35,00 = 3,5% do serviço (R$ 1.000,00); "
                         "esperado 11% = R$ 110,00 ou 20% = R$ 200,00."),
])
def test_s16_aliquota_errada_fica_roxa_com_o_motivo(retidos, frase, tmp_path):
    r = _servico_mil(**retidos)
    assert r.situacao == Situacao.RETENCAO
    assert r.aliquotas_erradas == [frase] and frase in r.observacoes
    caminho = gerar_relatorio(tmp_path / "r.xlsx", [r], [r.nota], [], [], [], ["lote.csv"])
    assert openpyxl.load_workbook(caminho)["Conferir à mão"]["A2"].value == \
        "Alíquota da retenção diferente da esperada"


def test_s16_irrf_de_pessoa_fisica_e_imposto_zerado_nao_sao_conferidos():
    assert _servico_mil(documento="52998224725", irrf="75.00").situacao == Situacao.OK
    assert _servico_mil().aliquotas_erradas == []                    # nada retido


def test_s16_lancamento_errado_continua_com_o_motivo_da_s13():
    nota = _danfse(irrf=Decimal("10.00"))
    nota.valor = Decimal("1000.00")
    r = _um(_servico(total="1000.00"), nota)                         # IRRF não lançado
    assert r.situacao == Situacao.RETENCAO and len(r.aliquotas_erradas) == 1
    caminho_motivo = [o for o in r.observacoes if o.startswith("Retenção de IRRF")]
    assert caminho_motivo                                            # as duas frases aparecem


# ---------------------------------------------------------------------------
# S16a — alíquota do PIS/COFINS/CSLL pelo código da nota ("Código 3")
# ---------------------------------------------------------------------------

def _com_codigo(descricao, cs):
    nota = _danfse(cs=Decimal(cs))
    nota.valor, nota.descricao_contribuicoes = Decimal("1000.00"), descricao
    return _um(_servico(("25206", cs), total="1000.00"), nota)


@pytest.mark.parametrize("descricao, cs", [
    ("Código 3", "46.50"), ("Código 4", "36.50"), ("Código 5", "6.50"), ("Código 6", "30.00"),
    ("Código 7", "40.00"), ("Código 8", "10.00"), ("Código 9", "16.50"),
    ("Código 1", "36.50"), ("Código 1", "46.50"),         # antigos: com e sem a CSLL
    ("Código 2", "10.00"), ("", "46.50"),                 # sem código: os três (4,65%)
])
def test_s16a_aliquota_pelo_codigo_fica_ok(descricao, cs):
    r = _com_codigo(descricao, cs)
    assert (r.situacao, r.aliquotas_erradas) == (Situacao.OK, [])


@pytest.mark.parametrize("descricao, cs, frase", [
    ("Código 4", "46.50", "Alíquota do PIS/COFINS/CSLL da nota: R$ 46,50 = 4,65% do serviço "
                          "(R$ 1.000,00); esperado pelo código 4 da nota (PIS/COFINS retidos, "
                          "CSLL não retida) 3,65% = R$ 36,50."),
    ("Código 0", "46.50", "Alíquota do PIS/COFINS/CSLL da nota: R$ 46,50 = 4,65% do serviço "
                          "(R$ 1.000,00); esperado pelo código 0 da nota (PIS/COFINS/CSLL não "
                          "retidos) 0% = R$ 0,00."),
    ("", "36.50", "Alíquota do PIS/COFINS/CSLL da nota: R$ 36,50 = 3,65% do serviço "
                  "(R$ 1.000,00); esperado 4,65% = R$ 46,50."),
])
def test_s16a_aliquota_diferente_do_codigo_fica_roxa(descricao, cs, frase):
    r = _com_codigo(descricao, cs)
    assert r.situacao == Situacao.RETENCAO and r.aliquotas_erradas == [frase]


def test_s16a_codigo_e_legenda_na_aba_da_prefeitura(tmp_path):
    r = _com_codigo("Código 3", "46.50")
    caminho = gerar_relatorio(tmp_path / "r.xlsx", [r], [r.nota], [], [], [], ["lote.csv"])
    aba = openpyxl.load_workbook(caminho)["Escriturar na prefeitura"]
    titulos = [c.value for c in aba[1]]
    assert aba.cell(row=2, column=titulos.index("Descrição contrib. sociais") + 1).value == \
        "Código 3 - PIS/COFINS/CSLL retidos"
    assert aba.auto_filter.ref.endswith("2")                         # a legenda fica fora do filtro
    legenda = [linha[0] for linha in aba.iter_rows(min_row=4, values_only=True)]
    assert legenda[0].startswith("Códigos da coluna \"Descrição contrib. sociais\"")
    assert "Código 3 - PIS/COFINS/CSLL retidos: 4,65% do serviço" in legenda
    assert "Código 1 - PIS/COFINS retidos (código antigo; não diz da CSLL): 3,65% ou 4,65% do " \
           "serviço" in legenda
    assert len(legenda) == 12 and legenda[-1].startswith("A coluna \"Contribuições Sociais")
