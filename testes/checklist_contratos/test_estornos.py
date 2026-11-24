"""M4 — estornos e notas devolvidas (decisão do usuário, 23/10/2026), e o formato "Movimento contábil"."""

from __future__ import annotations

from decimal import Decimal

import pytest

from modulos.checklist_contratos.estornos import anular_estornos_e_devolucoes
from modulos.checklist_contratos.leitor_movimento import ler_linhas, ler_movimentos
from modulos.checklist_contratos.modelos import ErroLeitura, Lancamento
from modulos.checklist_contratos.normalizacao import normalizar
from testes.checklist_contratos.conftest import escrever_movimento
from testes.conftest import pasta_exemplos

COMP = "Manutencao Exemplo Ltda NF. 2591 - Contrato de manutencao DT 10/10/2026"


def _linha(documento, natureza, conta, valor, complemento=COMP, data="16/10/2026"):
    return Lancamento("SC", conta, "Conta", Decimal(valor), "", documento, data, complemento, normalizar(complemento),
                      2, "mov.csv", natureza, f"fato {documento}")


def _nota(documento, data="16/10/2026", complemento=COMP, sinal=1):
    """Nota de 9.900,00: despesa 30039 contra fornecedor 20240 e retenção 25206 (sinal -1 = invertida)."""
    d, c = ("D", "C") if sinal == 1 else ("C", "D")
    return [_linha(documento, d, "30039", "9900.00", complemento, data),
            _linha(documento, c, "20240", "9439.65", complemento, data),
            _linha(documento, c, "25206", "460.35", complemento, data)]


def test_m4_estorno_anula_o_original_e_vale_o_relancamento():
    linhas = _nota("1") + _nota("2", "20/10/2026", sinal=-1) + _nota("3", "20/10/2026")
    movimento = anular_estornos_e_devolucoes(linhas)
    assert [(l.documento, l.conta, l.valor) for l in movimento.lancamentos] == [("fato 3", "30039", Decimal("9900.00"))]
    [anulacao] = movimento.anulacoes
    assert (anulacao.tipo, anulacao.anulado[0].documento, anulacao.anulador[0].documento) == ("estorno", "fato 1", "fato 2")


def test_m4_complemento_diferente_nao_e_estorno():
    outro = "Manutencao Exemplo Ltda NF. 2600 - Outra nota"
    movimento = anular_estornos_e_devolucoes(_nota("1") + _nota("2", "20/10/2026", outro, sinal=-1))
    assert movimento.anulacoes == [] and len(movimento.lancamentos) == 3     # 1 débito da nota + 2 da invertida


def test_m4_devolucao_inteira_anula_a_nota_devolvida():
    # o caso da linha 63 em out/2026: NF 2591 devolvida pela NF 299689 e substituída pela NF 2597
    devolucao = "Manutencao Exemplo Ltda NF. 299689 - Devolução NF 2591 devido ao erro fornecedor."
    nova = "Manutencao Exemplo Ltda NF. 2597 - Contrato de manutencao DT 20/10/2026"
    linhas = _nota("1") + _nota("2", "20/10/2026", devolucao, sinal=-1) + _nota("3", "20/10/2026", nova)
    movimento = anular_estornos_e_devolucoes(linhas)
    assert [l.complemento for l in movimento.lancamentos] == [nova]
    assert {l.conta for l in movimento.devolucoes} == {"20240", "25206"}           # vão para os não vinculados
    assert [a.tipo for a in movimento.anulacoes] == ["devolução"] and movimento.avisos == []


def test_m4_devolucao_de_nota_de_outro_mes_so_avisa():
    devolucao = "Manutencao Exemplo Ltda NF. 299432 - Devolucao NF 10880 devido ao valor incorreto."
    movimento = anular_estornos_e_devolucoes(_nota("1") + _nota("2", "13/10/2026", devolucao, sinal=-1))
    assert len(movimento.lancamentos) == 1 and movimento.anulacoes == []
    assert "NF 10880" in movimento.avisos[0].mensagem and "outro mês" in movimento.avisos[0].mensagem


def test_m4_devolucao_parcial_nao_anula_e_avisa():
    devolucao = "Manutencao Exemplo Ltda NF. 299700 - Devolucao NF 2591 parcial"
    parcial = [_linha("2", "C", "30039", "1000.00", devolucao, "20/10/2026"),
               _linha("2", "D", "20240", "1000.00", devolucao, "20/10/2026")]
    movimento = anular_estornos_e_devolucoes(_nota("1") + parcial)
    assert [l.documento for l in movimento.lancamentos] == ["fato 1"]
    assert "parcial" in movimento.avisos[0].mensagem


def test_m4_devolucao_de_outro_fornecedor_com_o_mesmo_numero_nao_anula():
    devolucao = "Outro Fornecedor Ltda NF. 299689 - Devolucao NF 2591"
    movimento = anular_estornos_e_devolucoes(_nota("1") + _nota("2", "20/10/2026", devolucao, sinal=-1))
    assert [l.documento for l in movimento.lancamentos] == ["fato 1"] and movimento.anulacoes == []


# ---------------------------------------------------------------------------
# Formato "Movimento contábil" (um dia por vez, com o centro de custo)
# ---------------------------------------------------------------------------

TITULOS_CONTABIL = ["Lançamento", "Sequência", "Fato contábil", "Data", "Valor", "Conta débito", "Conta crédito",
                    "Centro custo", "Complemento", "Conta contábil", "Centro de custo"]


def _contabil(caminho, linhas):
    padrao = {"Lançamento": "36", "Sequência": "1", "Fato contábil": "6707509", "Data": "16/10/2026", "Valor": "0",
              "Conta débito": "0", "Conta crédito": "0", "Centro custo": "", "Complemento": COMP,
              "Conta contábil": "Conta Exemplo", "Centro de custo": ""}
    return escrever_movimento(caminho, [{**padrao, **l} for l in linhas], TITULOS_CONTABIL)


def test_contabil_rateio_volta_a_ser_uma_linha_por_conta(tmp_path):
    caminho = _contabil(tmp_path / "Movimento contábil (1).csv", [
        {"Valor": "4950", "Conta débito": "30039", "Centro de custo": "U.T.I. Adulto"},
        {"Valor": "4950", "Conta débito": "30039", "Centro de custo": "UTIN/Pediátrica"},
        {"Valor": "9439,65", "Conta crédito": "20240", "Conta contábil": "Manutencao Exemplo Ltda"},
        {"Valor": "460,35", "Conta crédito": "25206"},
    ])
    debito, fornecedor, retencao = ler_linhas(caminho, "SC")
    assert (debito.natureza, debito.conta, debito.valor, debito.documento) == ("D", "30039", Decimal("9900.00"), "fato 6707509")
    assert debito.centros_custo == (("U.T.I. Adulto", Decimal("4950.00")), ("UTIN/Pediátrica", Decimal("4950.00")))
    assert (fornecedor.natureza, fornecedor.conta, fornecedor.nome_conta) == ("C", "20240", "Manutencao Exemplo Ltda")
    assert debito.lote_lancamento == "fato 6707509"


def test_contabil_pasta_diaria_com_estorno_entre_dias(tmp_path):
    _contabil(tmp_path / "dia 16.csv", [{"Valor": "9900", "Conta débito": "30039"},
                                        {"Valor": "9900", "Conta crédito": "20240"}])
    _contabil(tmp_path / "dia 20.csv", [
        {"Fato contábil": "6759145", "Data": "20/10/2026", "Valor": "9900", "Conta débito": "20240"},
        {"Fato contábil": "6759145", "Data": "20/10/2026", "Valor": "9900", "Conta crédito": "30039"},
        {"Fato contábil": "6759191", "Data": "20/10/2026", "Valor": "9900", "Conta débito": "30039"},
        {"Fato contábil": "6759191", "Data": "20/10/2026", "Valor": "9900", "Conta crédito": "20240"}])
    movimento = ler_movimentos(tmp_path, "SC")
    assert [(l.documento, l.conta) for l in movimento.lancamentos] == [("fato 6759191", "30039")]
    assert [a.tipo for a in movimento.anulacoes] == ["estorno"]


def test_contabil_coluna_faltando(tmp_path):
    titulos = [t for t in TITULOS_CONTABIL if t != "Lançamento"]
    caminho = escrever_movimento(tmp_path / "mov.csv", [{"Fato contábil": "1", "Conta débito": "30039",
                                                          "Conta crédito": "0", "Data": "01/10/2026"}], titulos)
    with pytest.raises(ErroLeitura, match="Lançamento"):
        ler_linhas(caminho, "SC")


def test_contabil_real_de_outubro_resolve_a_devolucao_da_linha_63():
    # a pasta recebe um dia novo de cada vez: o teste só confere o que já estava lá em 23/10/2026
    pasta = pasta_exemplos("conferencias_notas_contratos", "Movimento_centro_custo", "Hospital Exemplo")
    movimento = ler_movimentos(pasta, "SC")
    devolvidas = [a.anulado[0].complemento_normalizado for a in movimento.anulacoes if a.tipo == "devolução"]
    assert any("nf. 2591" in c for c in devolvidas)
    assert sum(1 for a in movimento.anulacoes if a.tipo == "estorno") >= 3
    assert any("NF 10880" in a.mensagem and "outro mês" in a.mensagem for a in movimento.avisos)
    assert not any(l.conta == "20240" and "nf. 2591" in l.complemento_normalizado for l in movimento.lancamentos)
