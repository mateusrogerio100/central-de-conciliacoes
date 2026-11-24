"""T0 — leitura do lote do Tasy (.csv).

Os testes com os lotes reais usam exemplos\\conferencia_nf\\ (fora do git) e são pulados sem ela.
Os demais montam um .csv pequeno no próprio teste.
"""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

import pytest

from modulos.conferencia_nf.leitor_lote import converter_valor, ler_lote
from modulos.conferencia_nf.modelos import ErroLeitura
from testes.conftest import caso_real, pasta_exemplos

TITULOS = ["Status", "Fato contábil", "Sequência", "Data movimento", "Débito", "Crédito", "Valor",
           "Histórico", "Complemento", "Conta débito", "Conta crédito", "Histórico",
           "Classificação débito", "Classificação crédito"]


def _linha(fato, sequencia, debito, credito, valor, complemento, conta, classificacao=""):
    return ["Não revisado", fato, sequencia, "01/10/2026", debito, credito, valor, "577",
            complemento, conta if debito else "", conta if credito else "", "Ref. nota fiscal",
            classificacao if debito else "", classificacao if credito else ""]


def _gravar(pasta: Path, linhas: list[list[str]], titulos=TITULOS, codificacao="utf-16-le",
            nome="lote.csv") -> Path:
    """Grava como o Tasy: UTF-16 sem BOM, ';', tudo entre aspas."""
    caminho = pasta / nome
    with caminho.open("w", encoding=codificacao, newline="") as arquivo:
        escritor = csv.writer(arquivo, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\r\n")
        escritor.writerow(titulos)
        escritor.writerows(linhas)
    return caminho


# ---------------------------------------------------------------------------
# Lotes reais (gabarito)
# ---------------------------------------------------------------------------

def _gabarito(lote: str) -> dict[str, dict]:
    caminho = pasta_exemplos("conferencia_nf", lote, "gabarito") / "gabarito_conferencia.csv"
    with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
        return {linha["fato"]: linha for linha in csv.DictReader(arquivo, delimiter=";")}


def _lote(lote: str) -> Path:
    return next(pasta_exemplos("conferencia_nf", lote).glob("Movimento*.csv"))


@pytest.mark.parametrize("lote, fatos, lancamentos", [
    ("lote_72648", 89, 211),
    ("lote_72887", 55, 122),
])
def test_lote_real_bate_com_o_gabarito(lote, fatos, lancamentos):
    gabarito = _gabarito(lote)
    lidos = ler_lote(_lote(lote))
    assert len(lidos) == fatos
    assert sum(len(f.lancamentos) for f in lidos) == lancamentos
    assert [f.fato for f in lidos] == list(gabarito)          # na ordem do lote
    for fato in lidos:
        esperado = gabarito[fato.fato]
        assert fato.total_debito == Decimal(esperado["total_debito"]), fato.fato
        assert fato.total_credito == Decimal(esperado["total_credito"]), fato.fato
        assert fato.arquivo == _lote(lote).name
        for lancamento in fato.lancamentos:
            # só uma das contas vem preenchida em cada lançamento
            assert bool(lancamento.conta_debito) != bool(lancamento.conta_credito)
            assert lancamento.nome_conta and lancamento.sequencia


def test_lote_real_complemento_com_quebra_de_linha_e_entidade_html():
    fatos = ler_lote(_lote("lote_72648"))
    recibos = [l.complemento for f in fatos for l in f.lancamentos if "Recibo" in l.complemento]
    assert recibos
    for complemento in recibos:
        assert complemento.startswith(caso_real("conferencia_nf", "inicio_do_recibo_72648"))
        assert "\n" not in complemento and "&#x" not in complemento and "  " not in complemento


def test_lote_real_classificacao_e_data_movimento():
    fato = ler_lote(_lote("lote_72887"))[0]
    assert fato.fato == "6598289"
    assert fato.data_movimento == "01/10/2026"
    primeiro = fato.lancamentos[0]
    assert (primeiro.sequencia, primeiro.conta_debito, primeiro.valor) == \
        ("15640541", "30080", Decimal("676.47"))
    assert primeiro.nome_conta == "Material p/uso manutenção predial"
    assert primeiro.classificacao == "3.01.02.07.0001"


# ---------------------------------------------------------------------------
# Casos montados no teste
# ---------------------------------------------------------------------------

def test_agrupa_por_fato_na_ordem_do_lote(tmp_path):
    caminho = _gravar(tmp_path, [
        _linha("200", "1", "30080", "", "4887,2", "Mercado X NF. 1 DT25/09/2026", "Material"),
        _linha("100", "2", "", "201777", "3420", "Fornecedor Y NF. 2", "Fornecedor Y"),
        _linha("200", "3", "", "201777", "4887,20", "Mercado X NF. 1", "Mercado X"),
        _linha("100", "4", "30080", "", "3420", "Fornecedor Y NF. 2", "Material"),
    ])
    fatos = ler_lote(caminho)
    assert [f.fato for f in fatos] == ["200", "100"]
    assert [l.sequencia for l in fatos[0].lancamentos] == ["1", "3"]
    assert fatos[0].total_debito == fatos[0].total_credito == Decimal("4887.20")
    assert fatos[1].total_debito == Decimal("3420.00")


def test_complemento_com_quebra_de_linha_e_entidade_html(tmp_path):
    caminho = _gravar(tmp_path, [
        _linha("1", "1", "30080", "", "10", "Ana Recibo n° 7\nPaciente João&#x2013;  quarto 2\r\n",
               "Material"),
    ])
    assert ler_lote(caminho)[0].lancamentos[0].complemento == \
        "Ana Recibo n° 7 Paciente João– quarto 2"


@pytest.mark.parametrize("codificacao", ["utf-16", "utf-8-sig", "latin-1"])
def test_codificacoes_aceitas(tmp_path, codificacao):
    caminho = _gravar(tmp_path, [_linha("1", "1", "30080", "", "887,93", "Saúde NF. 5", "Conta")],
                      codificacao=codificacao)
    lancamento = ler_lote(caminho)[0].lancamentos[0]
    assert lancamento.complemento == "Saúde NF. 5"
    assert lancamento.valor == Decimal("887.93")


def test_colunas_opcionais_podem_faltar(tmp_path):
    titulos = [t for t in TITULOS if not t.startswith("Classificação")
               and t != "Data movimento"]
    linha = ["Status", "1", "1", "30080", "", "10", "577", "Fornecedor NF. 1", "Conta", "", "h"]
    fato = ler_lote(_gravar(tmp_path, [linha], titulos=titulos))[0]
    assert fato.data_movimento == "" and fato.lancamentos[0].classificacao == ""


def test_coluna_obrigatoria_faltando_e_erro_com_o_nome_dela(tmp_path):
    titulos = [t for t in TITULOS if t not in ("Valor", "Complemento")]
    caminho = _gravar(tmp_path, [], titulos=titulos)
    with pytest.raises(ErroLeitura, match="Colunas não encontradas: Valor, Complemento"):
        ler_lote(caminho)


def test_valor_ilegivel_e_erro_com_a_linha(tmp_path):
    caminho = _gravar(tmp_path, [
        _linha("1", "1", "30080", "", "10", "A NF. 1", "Conta"),
        _linha("1", "2", "", "201777", "dez reais", "A NF. 1", "Conta"),
    ])
    with pytest.raises(ErroLeitura, match="Linha 3: valor \"dez reais\""):
        ler_lote(caminho)


def test_linha_com_colunas_a_menos_e_erro(tmp_path):
    caminho = _gravar(tmp_path, [["Revisado", "1", "1"]])
    with pytest.raises(ErroLeitura, match="Linha 2: tem 3 colunas"):
        ler_lote(caminho)


def test_arquivo_vazio_e_erro(tmp_path):
    caminho = tmp_path / "vazio.csv"
    caminho.write_bytes(b"")
    with pytest.raises(ErroLeitura, match="vazio"):
        ler_lote(caminho)


def test_linhas_em_branco_sao_ignoradas(tmp_path):
    caminho = _gravar(tmp_path, [_linha("1", "1", "30080", "", "10", "A NF. 1", "Conta"),
                                 [""] * len(TITULOS)])
    assert len(ler_lote(caminho)[0].lancamentos) == 1


@pytest.mark.parametrize("texto, esperado", [
    ("4887,2", "4887.20"), ("3420", "3420.00"), ("887,93", "887.93"), ("1.234,56", "1234.56"),
    ("-15,5", "-15.50"), (" 9 ", "9.00"),
])
def test_converter_valor(texto, esperado):
    assert converter_valor(texto) == Decimal(esperado)


@pytest.mark.parametrize("texto", ["", "1,234", "12.34", "R$ 10,00", "1.23,45", "abc"])
def test_converter_valor_recusa(texto):
    with pytest.raises(ErroLeitura):
        converter_valor(texto)
