"""E2 — leitura do SCF - Movimento Estoque (Contabilidade) (ESPECIFICACAO_ESTOQUE.md, seções 3.3 e 7.1)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from modulos.conciliacao_estoque import configuracao
from modulos.conciliacao_estoque.leitor_scf import ler_scf, posicao_do_titulo
from modulos.conciliacao_estoque.modelos import ErroArquivo, Gravidade, MesReferencia
from testes.conciliacao_estoque.conftest import ler_gabarito_estoque
from testes.conftest import pasta_exemplos

# ---------------------------------------------------------------------------
# Arquivo real de setembro/2026
# ---------------------------------------------------------------------------


def test_setembro_locais_mes_e_sem_erros(caminho_scf):
    scf = ler_scf(caminho_scf)
    assert scf.mes_referencia == MesReferencia(2026, 9)
    assert len(scf.locais) == 40
    assert scf.quantidade_total == 40
    assert scf.linhas_ignoradas == 0
    assert scf.avisos == []
    assert all(len(l.valores) == 13 for l in scf.locais)


def test_setembro_pagina_2_com_colunas_deslocadas(caminho_scf):
    scf = ler_scf(caminho_scf)
    central = scf.local(14)
    assert central.descricao == "Farmácia - Hospital Central (14)"
    assert central.saldo_anterior == Decimal("1258547.20")
    assert central.saldo_atual == Decimal("1138854.36")
    pagina_2 = [l.codigo for l in scf.locais if l.linha > central.linha - 1]
    assert pagina_2 == [14, 79, 1, 80, 16, 15, 22]
    farmacia_central = scf.local(1)
    assert farmacia_central.valores == [Decimal(v) for v in (
        "303512.19", "90201.07", "0.00", "0.00", "559384.63", "649585.70",
        "96232.63", "0.00", "492680.26", "0.00", "50502.94", "639415.83", "312737.62",
    )]


def test_setembro_total_igual_soma_dos_locais(caminho_scf):
    scf = ler_scf(caminho_scf)
    assert scf.total_na_posicao(1) == Decimal("6558659.62")
    assert scf.total_na_posicao(13) == Decimal("6034965.49")
    for posicao in range(1, 14):
        assert sum(l.valor(posicao) for l in scf.locais) == scf.total_na_posicao(posicao)


def test_setembro_fechamento_por_local_nao_gera_aviso(caminho_scf):
    """Decisão do usuário: o fechamento por local não é conferido (Almoxarifado (12) difere 723,28)."""
    scf = ler_scf(caminho_scf)
    almox = scf.local(12)
    assert almox.saldo_atual - (almox.saldo_anterior + almox.valor(6) - almox.valor(12)) == Decimal("723.28")
    assert scf.avisos == []


def test_setembro_igual_ao_gabarito(caminho_scf):
    scf = ler_scf(caminho_scf)
    campo = {"saldo_anterior": "saldo_anterior", "saldo_atual": "saldo_atual"}
    for linha in ler_gabarito_estoque():
        local = scf.local(int(linha["local_scf"]))
        assert local.descricao == linha["descricao_scf"]
        assert getattr(local, campo[linha["parte"]]) == linha["saldo_scf"], linha["local_scf"]


def test_mapa_movimentacao_da_os_mesmos_valores(caminho_scf, caminho_mapa):
    """O mesmo SCF nos dois formatos de número dá exatamente os mesmos valores (seção 7.1)."""
    scf = ler_scf(caminho_scf)
    mapa = ler_scf(caminho_mapa)
    assert mapa.avisos == []
    assert mapa.mes_referencia == scf.mes_referencia
    assert mapa.total == scf.total
    assert [(l.codigo, l.descricao, l.valores) for l in mapa.locais] == [
        (l.codigo, l.descricao, l.valores) for l in scf.locais
    ]


def test_posicao_do_titulo():
    assert posicao_do_titulo("Saldo Anterior") == 1
    assert posicao_do_titulo("saldo atual") == 13
    assert posicao_do_titulo("Total (E)") == 6
    assert posicao_do_titulo("Total (S)") == 12
    with pytest.raises(ValueError):
        posicao_do_titulo("Outro")


# ---------------------------------------------------------------------------
# Casos construídos
# ---------------------------------------------------------------------------

TITULOS = "Descrição\t" + "\t".join(configuracao.SCF_TITULOS)
CABECALHO = [
    "\t\t\tSCF - Movimento Estoque (Contabilidade)",
    "\t\tMês competência:\t\t01/09/2026",
    TITULOS,
]


def _linha(descricao: str, valores: list[str]) -> str:
    return descricao + "\t" + "\t\t".join(valores)


def _scf(tmp_path, *linhas: str, cabecalho=CABECALHO):
    arquivo = tmp_path / "scf.xls"
    arquivo.write_bytes("\n".join([*cabecalho, *linhas]).encode("cp1252"))
    return ler_scf(arquivo)


VALORES_A = ["10,00", "5,00", "0", "0", "0", "5,00", "3,00", "0", "0", "0", "0", "3,00", "12,00"]
VALORES_B = ["1,00", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "1,00"]
TOTAL = ["11,00", "5,00", "0", "0", "0", "5,00", "3,00", "0", "0", "0", "0", "3,00", "13,00"]


def test_caso_simples_sem_avisos(tmp_path):
    scf = _scf(tmp_path, _linha("Local A (1)", VALORES_A), "\t" + _linha("Local B (2)", VALORES_B),
               _linha("Total(2)", TOTAL))
    assert [l.codigo for l in scf.locais] == [1, 2]
    assert scf.avisos == []


def test_local_sem_13_numeros_gera_erro_e_e_ignorado(tmp_path):
    scf = _scf(tmp_path, _linha("Local A (1)", VALORES_A[:12]), _linha("Total(1)", VALORES_A))
    assert scf.locais == []
    assert scf.linhas_ignoradas == 1
    tipos = [a.tipo for a in scf.avisos if a.gravidade == Gravidade.ERRO]
    assert tipos[0] == "linha não reconhecida"
    assert "quantidade de locais" in tipos      # Total(1), mas 0 locais lidos


def test_soma_dos_locais_diferente_do_total_gera_erro(tmp_path):
    scf = _scf(tmp_path, _linha("Local A (1)", VALORES_A), _linha("Total(1)", TOTAL))
    erros = [a for a in scf.avisos if a.tipo == "soma dos locais diferente do total"]
    assert len(erros) == 2      # Saldo Anterior (10 x 11) e Saldo Atual (12 x 13)


def test_sem_linha_total_gera_erro(tmp_path):
    scf = _scf(tmp_path, _linha("Local A (1)", VALORES_A))
    assert [a.tipo for a in scf.avisos] == ["total não encontrado"]


def test_linha_com_valores_sem_codigo_do_local(tmp_path):
    scf = _scf(tmp_path, _linha("Local sem código", VALORES_A), _linha("Total(0)", ["0"] * 13))
    assert scf.locais == []
    assert scf.linhas_ignoradas == 1
    assert scf.avisos[0].tipo == "linha não reconhecida"


def test_local_repetido_gera_erro(tmp_path):
    scf = _scf(tmp_path, _linha("Local A (1)", VALORES_B), _linha("Outro A (1)", VALORES_B),
               _linha("Total(2)", ["2,00"] + ["0"] * 11 + ["2,00"]))
    assert [l.descricao for l in scf.locais] == ["Local A (1)"]
    assert "local repetido no Mapa do Estoque" in [a.tipo for a in scf.avisos]


def test_titulos_diferentes_param_a_leitura(tmp_path):
    titulos = TITULOS.replace("Pacientes", "Pacientes\tNova Coluna")
    with pytest.raises(ErroArquivo, match="títulos das colunas do Mapa do Estoque"):
        _scf(tmp_path, cabecalho=[CABECALHO[0], CABECALHO[1], titulos])


def test_arquivo_que_nao_e_scf(tmp_path):
    arquivo = tmp_path / "outro.xls"
    arquivo.write_bytes("Balancete\nqualquer coisa\t1,00\n".encode("cp1252"))
    with pytest.raises(ErroArquivo, match="não parece ser o relatório SCF"):
        ler_scf(arquivo)


def test_mes_nao_encontrado_gera_atencao(tmp_path):
    scf = _scf(tmp_path, _linha("Local B (2)", VALORES_B), _linha("Total(1)", VALORES_B),
               cabecalho=[CABECALHO[0], TITULOS])
    assert scf.mes_referencia is None
    assert [a.tipo for a in scf.avisos] == ["mês não encontrado"]


# ---------------------------------------------------------------------------
# SCF do CMD e dos AMES: sem a coluna Subvenção e com um número a mais no fim
# ---------------------------------------------------------------------------

TITULOS_CMD_AMES = "\tDescrição\t" + "\t".join(
    t for t in configuracao.SCF_TITULOS if t != "Subvenção"
).replace("Emprestimo", "Empréstimo").replace("Out.Entradas", "Out. Entradas").replace("Out.Saídas", "Out. Saídas")
CABECALHO_CMD_AMES = [
    "\t\t\tMovimento Estoque (Contabilidade)",
    "\t\tMês competência:\t\t01/09/2026",
    TITULOS_CMD_AMES,
]
# 12 valores (sem Subvenção) + o número sem título, zerado
VALORES_CMD = ["10,00", "5,00", "0", "0", "1,00", "6,00", "3,00", "0", "0", "2,00", "5,00", "11,00", "0,00"]
TOTAL_CMD = VALORES_CMD


def test_cmd_ames_sem_subvencao_le_as_13_posicoes(tmp_path):
    scf = _scf(tmp_path, "\t" + _linha("Estoque X (101)", VALORES_CMD), _linha("Total(1)", TOTAL_CMD),
               cabecalho=CABECALHO_CMD_AMES)
    local = scf.local(101)
    assert local.valores == [Decimal(v) for v in (
        "10.00", "5.00", "0.00", "0.00", "1.00", "6.00", "3.00", "0.00", "0.00", "0.00", "2.00", "5.00", "11.00",
    )]
    assert local.valor(posicao_do_titulo("Subvenção")) == Decimal("0.00")
    assert scf.total == local.valores
    assert scf.mes_referencia == MesReferencia(2026, 9)
    assert scf.linhas_ignoradas == 0
    assert [(a.gravidade, a.tipo) for a in scf.avisos] == [
        (Gravidade.INFO, "coluna ausente no Mapa do Estoque"), (Gravidade.INFO, "coluna sem título"),
    ]


def test_cmd_ames_numero_a_mais_diferente_de_zero_nao_e_usado(tmp_path):
    valores = VALORES_CMD[:-1] + ["7,00"]
    scf = _scf(tmp_path, _linha("Estoque X (101)", valores), _linha("Total(1)", TOTAL_CMD),
               cabecalho=CABECALHO_CMD_AMES)
    assert scf.locais == []
    assert scf.linhas_ignoradas == 1
    assert "linha não reconhecida" in [a.tipo for a in scf.avisos if a.gravidade == Gravidade.ERRO]


def test_falta_de_titulo_que_nao_e_opcional_para_a_leitura(tmp_path):
    titulos = TITULOS.replace("\tConsumo", "")
    with pytest.raises(ErroArquivo, match="títulos das colunas do Mapa do Estoque"):
        _scf(tmp_path, cabecalho=[CABECALHO[0], CABECALHO[1], titulos])


@pytest.mark.parametrize("nome, locais", [("Mapa01.xls", 4), ("Mapa02.xls", 7)])
def test_arquivos_reais_do_cmd_e_dos_ames(nome, locais):
    caminho = pasta_exemplos("conciliacao_estoque") / nome
    if not caminho.is_file():
        pytest.skip(f"Arquivo de exemplo {caminho} não encontrado")
    scf = ler_scf(caminho)
    assert scf.mes_referencia == MesReferencia(2026, 9)
    assert len(scf.locais) == scf.quantidade_total == locais
    assert scf.linhas_ignoradas == 0
    assert all(a.gravidade == Gravidade.INFO for a in scf.avisos)
