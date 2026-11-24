"""T0 — leitura do movimento do Tasy (seção 3.1 e regra M1)."""

from __future__ import annotations

import os
from decimal import Decimal

import pytest

from modulos.checklist_contratos.leitor_movimento import converter_valor, ler_movimento, ler_movimentos
from modulos.checklist_contratos.modelos import ErroLeitura
from modulos.checklist_contratos.normalizacao import chave_responsavel, normalizar
from testes.checklist_contratos.conftest import TITULOS_MOVIMENTO, escrever_movimento, exemplos

# Contados à parte, com o Import-Csv do PowerShell (como o protótipo lê): linhas "D" e soma do Valor.
MOVIMENTOS_REAIS = [
    ("2026-09", "Movimentos_NF_09_SC.csv", "SC", 2069, Decimal("8980738.17")),
    ("2026-09", "Movimentos_NF_09_CMD.csv", "CMD", 45, Decimal("415267.69")),
    ("2026-10", "Movimentos_NF_10_SC.csv", "SC", 991, Decimal("6943923.84")),
    ("2026-10", "Movimentos_NF_10_CMD.csv", "CMD", 32, Decimal("567267.37")),
]


@pytest.mark.parametrize("mes, arquivo, estabelecimento, debitos, soma", MOVIMENTOS_REAIS,
                         ids=[m[1] for m in MOVIMENTOS_REAIS])
def test_t0_movimentos_reais(mes, arquivo, estabelecimento, debitos, soma):
    lancamentos = ler_movimento(exemplos(mes) / arquivo, estabelecimento)
    assert len(lancamentos) == debitos
    assert sum((l.valor for l in lancamentos), Decimal("0")) == soma
    assert {l.estabelecimento for l in lancamentos} == {estabelecimento}
    assert all(l.conta and l.lote and l.lancamento for l in lancamentos)
    assert all("\n" not in l.complemento for l in lancamentos)


def test_t0_so_debitos_e_campos(tmp_path):
    caminho = escrever_movimento(tmp_path / "Movimentos_NF_10_SC.csv", [
        {"Débito/Crédito": "D", "Valor": "21585,5", "Conta contábil": "30091", "Conta": "Software",
         "Lote contábil": "72970", "Lançamento": "21554", "Data movimento": "05/10/2026",
         "Complemento": "Fornecedor Exemplo Ltda NF. 1234 - Locação de Sistema DT 01/10/2026"},
        {"Débito/Crédito": "C", "Valor": "21585,5", "Conta contábil": "23334"},
    ])
    [lancamento] = ler_movimento(caminho, "SC")
    assert lancamento.valor == Decimal("21585.50")
    assert (lancamento.conta, lancamento.nome_conta, lancamento.lote, lancamento.lancamento,
            lancamento.data) == ("30091", "Software", "72970", "21554", "05/10/2026")
    assert lancamento.complemento_normalizado == \
        "fornecedor exemplo ltda nf. 1234 - locacao de sistema dt 01/10/2026"
    assert lancamento.linha_arquivo == 2


def test_t0_quebra_de_linha_dentro_das_aspas_e_entidade_html(tmp_path):
    caminho = escrever_movimento(tmp_path / "mov.csv", [
        {"Complemento": "Fornecedor Exemplo NF. 10\r\nManutenção  &#x2013; Elevador", "Valor": "10"},
        {"Complemento": "Outro Fornecedor NF. 11", "Valor": "20"},
    ])
    primeiro, segundo = ler_movimento(caminho, "CMD")
    assert primeiro.complemento == "Fornecedor Exemplo NF. 10 Manutenção – Elevador"
    assert primeiro.complemento_normalizado == "fornecedor exemplo nf. 10 manutencao – elevador"
    assert segundo.valor == Decimal("20.00")


def test_t0_nome_do_arquivo_com_espaco_sobrando(tmp_path):
    caminho = escrever_movimento(tmp_path / "Movimentos_NF_09_SC .csv", [{"Valor": "1.234,56"}])
    assert ler_movimento(caminho, "SC")[0].valor == Decimal("1234.56")


def test_t0_coluna_faltando_e_erro_com_o_nome_da_coluna(tmp_path):
    titulos = [t for t in TITULOS_MOVIMENTO if t != "Lote contábil"]
    caminho = escrever_movimento(tmp_path / "mov.csv", [{}], titulos)
    with pytest.raises(ErroLeitura, match="Lote contábil"):
        ler_movimento(caminho, "SC")


def test_t0_valor_ilegivel_diz_a_linha(tmp_path):
    caminho = escrever_movimento(tmp_path / "mov.csv", [{"Valor": "10"}, {"Valor": "dez reais"}])
    with pytest.raises(ErroLeitura, match="Linha 3"):
        ler_movimento(caminho, "SC")


def test_t0_arquivo_vazio_ou_inexistente(tmp_path):
    (tmp_path / "vazio.csv").write_bytes(b"")
    with pytest.raises(ErroLeitura, match="vazio"):
        ler_movimento(tmp_path / "vazio.csv", "SC")
    with pytest.raises(ErroLeitura, match="abrir"):
        ler_movimento(tmp_path / "nao_existe.csv", "SC")


@pytest.mark.parametrize("texto, esperado", [("21585,5", "21585.50"), ("3420", "3420.00"),
                                             ("1.234,56", "1234.56"), ("-12,3", "-12.30")])
def test_t0_converter_valor(texto, esperado):
    assert converter_valor(texto) == Decimal(esperado)


def test_m2_normalizacao():
    assert normalizar("  Manutenção\r\n  PREVENTIVA\tÁgua ") == "manutencao preventiva agua"
    assert normalizar(None) == ""
    assert normalizar(30091) == "30091"


def test_p5_chave_do_responsavel():
    assert chave_responsavel("Ana/Bruno") == chave_responsavel("Ana e Bruno") == "ana/bruno"
    assert chave_responsavel("Márcia") == chave_responsavel("Marcia") == "marcia"
    assert chave_responsavel("Carlos manutenção") != chave_responsavel("Carlos engenharia")
    assert chave_responsavel("Ana, Bruno; Carla & Davi") == "ana/bruno/carla/davi"


# ---------------------------------------------------------------------------
# M3 — pasta com um arquivo por dia
# ---------------------------------------------------------------------------


def test_m3_pasta_com_um_arquivo_por_dia(tmp_path):
    escrever_movimento(tmp_path / "dia 01.csv", [{"Data movimento": "01/10/2026", "Valor": "10"}])
    escrever_movimento(tmp_path / "dia 02.csv", [{"Data movimento": "02/10/2026", "Valor": "20"},
                                                 {"Data movimento": "02/10/2026", "Valor": "30"}])
    (tmp_path / "anotacoes.txt").write_text("não é movimento", encoding="utf-8")
    movimento = ler_movimentos(tmp_path, "SC")
    lancamentos, avisos = movimento.lancamentos, movimento.avisos
    assert [(l.arquivo, l.valor) for l in lancamentos] == [
        ("dia 01.csv", Decimal("10.00")), ("dia 02.csv", Decimal("20.00")), ("dia 02.csv", Decimal("30.00"))]
    assert avisos == []


def test_m3_dia_repetido_vale_o_arquivo_mais_recente(tmp_path):
    antigo = escrever_movimento(tmp_path / "Movimento (3).csv", [{"Data movimento": "15/10/2026", "Valor": "10"}])
    novo = escrever_movimento(tmp_path / "Movimento (1).csv", [{"Data movimento": "15/10/2026", "Valor": "10"},
                                                               {"Data movimento": "15/10/2026", "Valor": "99"}])
    escrever_movimento(tmp_path / "Movimento (2).csv", [{"Data movimento": "16/10/2026", "Valor": "5"}])
    os.utime(antigo, (1_000_000, 1_000_000))
    os.utime(novo, (2_000_000, 2_000_000))
    movimento = ler_movimentos(tmp_path, "CMD")
    lancamentos, avisos = movimento.lancamentos, movimento.avisos
    assert sorted(l.valor for l in lancamentos) == [Decimal("5.00"), Decimal("10.00"), Decimal("99.00")]
    assert {l.arquivo for l in lancamentos if l.data == "15/10/2026"} == {"Movimento (1).csv"}
    [aviso] = avisos
    assert "15/10/2026 está em 2 arquivos" in aviso.mensagem and "Movimento (1).csv" in aviso.mensagem


def test_m3_arquivo_com_erro_na_pasta_vira_aviso(tmp_path):
    escrever_movimento(tmp_path / "bom.csv", [{"Valor": "10"}])
    escrever_movimento(tmp_path / "ruim.csv", [{"Valor": "dez"}])
    movimento = ler_movimentos(tmp_path, "SC")
    lancamentos, avisos = movimento.lancamentos, movimento.avisos
    assert len(lancamentos) == 1
    assert [a.origem for a in avisos] == ["ruim.csv"] and "deixado de fora" in avisos[0].mensagem


def test_m3_arquivo_unico_e_pasta_vazia(tmp_path):
    caminho = escrever_movimento(tmp_path / "mes.csv", [{"Valor": "10"}])
    assert len(ler_movimentos(caminho, "SC").lancamentos) == 1
    escrever_movimento(tmp_path / "ruim.csv", [{"Valor": "dez"}])
    with pytest.raises(ErroLeitura, match="Linha 2"):              # arquivo único com erro: erro mesmo
        ler_movimentos(tmp_path / "ruim.csv", "SC")
    vazia = tmp_path / "vazia"
    vazia.mkdir()
    with pytest.raises(ErroLeitura, match="nenhum arquivo"):
        ler_movimentos(vazia, "SC")


def test_m3_pasta_com_o_mes_real_igual_ao_arquivo(tmp_path):
    import shutil

    shutil.copy(exemplos("2026-10") / "Movimentos_NF_10_CMD.csv", tmp_path)
    movimento = ler_movimentos(tmp_path, "CMD")
    lancamentos, avisos = movimento.lancamentos, movimento.avisos
    assert len(lancamentos) == 32 and avisos == []
