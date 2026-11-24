"""E6 — planilha de configuração da EST-02 (ESPECIFICACAO_ESTOQUE.md, seções 3.6 e 7.1).

Todos os testes usam uma pasta temporária como "pasta do usuário": nunca tocam no %APPDATA% real.
"""

from __future__ import annotations

import shutil

import openpyxl
import pytest

from modulos.conciliacao_estoque import configuracao
from modulos.conciliacao_estoque.configuracao_est02 import (
    caminho_fabrica,
    caminho_usuario,
    carregar_configuracao_estoque,
    preparar_configuracao_do_usuario,
)
from modulos.conciliacao_estoque.modelos import ErroArquivo, Gravidade


def test_configuracao_de_fabrica(tmp_path):
    config = carregar_configuracao_estoque(pasta=tmp_path)
    assert config.de_fabrica and config.descricao_origem == "configuração de fábrica"
    assert config.valida
    assert len(config.itens) == 62
    assert [g.nome for g in config.grupos] == [
        "Notas Fiscais", "Emprestimo", "Inventário (entrada)", "Out.Entradas",
        "Consumo", "Inventário (saída)", "Pacientes", "Subvenção", "Out.Saídas",
    ]
    assert [g.posicao for g in config.grupos] == [2, 3, 4, 5, 7, 8, 9, 10, 11]
    assert {g.tipo for g in config.grupos[:4]} == {"Entrada"} and {g.tipo for g in config.grupos[4:]} == {"Saída"}
    assert config.itens[126].grupo == "Consumo"           # decisão de 06/10/2026
    assert [(p.operacao_a, p.operacao_b) for p in config.pares] == [(15, 16)]
    assert [(a.gravidade, a.conta) for a in config.avisos] == [(Gravidade.INFO, "82")]   # 82 – Estorno de Saída


def test_fabrica_e_igual_a_dos_exemplos():
    from testes.conciliacao_estoque.conftest import arquivo_exemplo

    assert caminho_fabrica().read_bytes() == arquivo_exemplo(configuracao.EST02_NOME_ARQUIVO).read_bytes()


def test_editar_configuracao_copia_a_de_fabrica_uma_vez(tmp_path):
    destino = preparar_configuracao_do_usuario(pasta=tmp_path)
    assert destino == caminho_usuario(tmp_path) and destino.read_bytes() == caminho_fabrica().read_bytes()
    config = carregar_configuracao_estoque(pasta=tmp_path)
    assert not config.de_fabrica and config.descricao_origem == "configuração do usuário"

    _editar(destino, "Itens", lambda aba: aba.append([999, "E - Operação nova", "E", "Teste", "Out.Entradas"]))
    preparar_configuracao_do_usuario(pasta=tmp_path)     # já existe: não sobrescreve
    assert 999 in carregar_configuracao_estoque(pasta=tmp_path).itens


# ---------------------------------------------------------------------------
# Configuração do usuário com problemas
# ---------------------------------------------------------------------------


def _editar(caminho, aba, alterar):
    pasta = openpyxl.load_workbook(caminho)
    alterar(pasta[aba])
    pasta.save(caminho)


def _configuracao_alterada(tmp_path, aba, alterar):
    destino = preparar_configuracao_do_usuario(pasta=tmp_path)
    _editar(destino, aba, alterar)
    return carregar_configuracao_estoque(pasta=tmp_path)


def _erros(config):
    return [a.tipo for a in config.avisos if a.gravidade == Gravidade.ERRO]


def test_codigo_repetido_impede_a_execucao(tmp_path):
    config = _configuracao_alterada(tmp_path, "Itens", lambda aba: aba.append([1, "S - Consumo de novo", "S", "", "Consumo"]))
    assert _erros(config) == ["código repetido"]
    assert not config.valida


def test_codigo_vazio_ou_nao_numerico(tmp_path):
    def alterar(aba):
        aba.append([None, "Sem código", "E", "", "Out.Entradas"])
        aba.append(["abc", "Código texto", "E", "", "Out.Entradas"])
    assert _erros(_configuracao_alterada(tmp_path, "Itens", alterar)) == ["código inválido", "código inválido"]


def test_grupo_que_nao_existe(tmp_path):
    config = _configuracao_alterada(tmp_path, "Itens", lambda aba: aba.append([998, "Nova", "E", "", "Outras Entradas"]))
    assert _erros(config) == ["grupo inexistente"]


def test_par_com_operacao_fora_dos_itens_ou_repetida(tmp_path):
    def alterar(aba):
        aba.append([15, "E - Produção", 997, "Inexistente", ""])
        aba.append([16, "S - Consumo na Produção", 16, "S - Consumo na Produção", ""])
    config = _configuracao_alterada(tmp_path, "Pares iguais", alterar)
    assert _erros(config) == ["par inválido", "par inválido"]
    assert [(p.operacao_a, p.operacao_b) for p in config.pares] == [(15, 16)]


def test_operacao_removida_da_configuracao(tmp_path):
    """Remover uma operação é permitido; na EST-02 ela vira "sem grupo" (testado na E7)."""
    def alterar(aba):
        linha = next(c.row for c in aba["A"] if c.value == 87)
        aba.delete_rows(linha)
    config = _configuracao_alterada(tmp_path, "Itens", alterar)
    assert config.valida and 87 not in config.itens
    assert config.grupo_da_operacao(87) is None


def test_aba_faltando(tmp_path):
    destino = preparar_configuracao_do_usuario(pasta=tmp_path)
    pasta = openpyxl.load_workbook(destino)
    del pasta["Grupos"]
    pasta.save(destino)
    config = carregar_configuracao_estoque(pasta=tmp_path)
    assert "aba não encontrada" in _erros(config)
    assert not config.valida


def test_arquivo_que_nao_e_planilha(tmp_path):
    caminho_usuario(tmp_path).write_bytes(b"isto nao e uma planilha")
    with pytest.raises(ErroArquivo):
        carregar_configuracao_estoque(pasta=tmp_path)


def test_pasta_do_usuario_fica_no_appdata(monkeypatch, tmp_path):
    from modulos.conciliacao_estoque.configuracao_est02 import pasta_usuario

    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert pasta_usuario() == tmp_path / "CentralConciliacoes" / "configuracoes"
    shutil.rmtree(tmp_path / "CentralConciliacoes", ignore_errors=True)
