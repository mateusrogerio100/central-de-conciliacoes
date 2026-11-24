"""Testes das preferências do usuário (modo claro/escuro, preferências de cada módulo e as do
programa antigo Conciliações AMES, que só são lidas)."""

from __future__ import annotations

import json

from central import preferencias as pref
from central.preferencias import Preferencias


def test_sem_arquivo_usa_valores_padrao(tmp_path):
    lidas = pref.ler_preferencias(tmp_path / "nao_existe.json")
    assert lidas == Preferencias(modo="claro")


def test_salvar_e_ler_de_volta(tmp_path):
    caminho = tmp_path / "sub" / "preferencias.json"  # a pasta é criada ao salvar
    assert pref.salvar_preferencias(Preferencias(modo="escuro"), caminho)
    assert pref.ler_preferencias(caminho) == Preferencias(modo="escuro")


def test_arquivo_estragado_usa_valores_padrao(tmp_path):
    caminho = tmp_path / "preferencias.json"
    caminho.write_text("{ isto não é json", encoding="utf-8")
    assert pref.ler_preferencias(caminho) == Preferencias()


def test_arquivo_com_lista_em_vez_de_objeto(tmp_path):
    caminho = tmp_path / "preferencias.json"
    caminho.write_text("[1, 2, 3]", encoding="utf-8")
    assert pref.ler_preferencias(caminho) == Preferencias()


def test_valores_invalidos_sao_trocados_pelo_padrao(tmp_path):
    caminho = tmp_path / "preferencias.json"
    caminho.write_text(json.dumps({"modo": "roxo"}), encoding="utf-8")
    assert pref.ler_preferencias(caminho) == Preferencias()


def test_campos_antigos_e_extras_sao_ignorados(tmp_path):
    # até a versão 1.3.8 o arquivo tinha "ultimo_modulo"; hoje a Central abre sempre no mesmo módulo
    caminho = tmp_path / "preferencias.json"
    caminho.write_text(json.dumps({"modo": "escuro", "ultimo_modulo": "bancos", "extra": 1}), encoding="utf-8")
    assert pref.ler_preferencias(caminho) == Preferencias(modo="escuro")


def test_falha_ao_salvar_nao_levanta_erro(tmp_path):
    arquivo_no_caminho = tmp_path / "sou_um_arquivo"
    arquivo_no_caminho.write_text("x", encoding="utf-8")
    # a "pasta" onde gravar é, na verdade, um arquivo: não dá para gravar
    assert pref.salvar_preferencias(Preferencias(), arquivo_no_caminho / "preferencias.json") is False


def test_caminho_padrao_fica_no_appdata(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert pref.caminho_padrao() == tmp_path / "CentralConciliacoes" / "preferencias.json"
    assert pref.caminho_programa_antigo() == tmp_path / "ConferenciaISSRB" / "config.json"
    assert pref.caminho_modulo("imprimir_pdfs") == tmp_path / "CentralConciliacoes" / "imprimir_pdfs.json"


# ---------------------------------------------------------------------------
# Programa antigo (Conciliações AMES): só leitura
# ---------------------------------------------------------------------------


def _programa_antigo(pasta, dados) -> None:
    (pasta / "ConferenciaISSRB").mkdir(parents=True)
    (pasta / "ConferenciaISSRB" / "config.json").write_text(json.dumps(dados), encoding="utf-8")


def test_sem_preferencias_da_central_o_modo_vem_do_programa_antigo(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    _programa_antigo(tmp_path, {"modo": "escuro", "cidade": "RB", "pasta_fornecedores": "C:/x"})
    antes = (tmp_path / "ConferenciaISSRB" / "config.json").read_bytes()

    assert pref.ler_preferencias() == Preferencias(modo="escuro")
    assert pref.ler_programa_antigo()["pasta_fornecedores"] == "C:/x"
    assert (tmp_path / "ConferenciaISSRB" / "config.json").read_bytes() == antes     # nunca alterado


def test_com_preferencias_da_central_o_programa_antigo_nao_manda(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    _programa_antigo(tmp_path, {"modo": "escuro"})
    pref.salvar_preferencias(Preferencias(modo="claro"))
    assert pref.ler_preferencias() == Preferencias(modo="claro")


def test_programa_antigo_ausente_ou_estragado_e_vazio(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert pref.ler_programa_antigo() == {}
    assert pref.ler_preferencias() == Preferencias()
    (tmp_path / "ConferenciaISSRB").mkdir()
    (tmp_path / "ConferenciaISSRB" / "config.json").write_text("{ estragado", encoding="utf-8")
    assert pref.ler_programa_antigo() == {}
    assert pref.ler_preferencias() == Preferencias()


# ---------------------------------------------------------------------------
# Preferências de cada módulo
# ---------------------------------------------------------------------------


def test_preferencias_do_modulo_salvar_e_ler(tmp_path):
    assert pref.ler_preferencias_modulo("fornecedores", tmp_path) == {}
    assert pref.salvar_preferencias_modulo("fornecedores", {"pasta": "C:/saida"}, tmp_path / "sub")
    assert pref.ler_preferencias_modulo("fornecedores", tmp_path / "sub") == {"pasta": "C:/saida"}


def test_preferencias_do_modulo_estragadas_viram_vazio(tmp_path):
    (tmp_path / "fornecedores.json").write_text("[1, 2]", encoding="utf-8")
    assert pref.ler_preferencias_modulo("fornecedores", tmp_path) == {}


def test_preferencias_do_modulo_falha_ao_salvar_nao_levanta_erro(tmp_path):
    arquivo = tmp_path / "sou_um_arquivo"
    arquivo.write_text("x", encoding="utf-8")
    assert pref.salvar_preferencias_modulo("fornecedores", {"a": 1}, arquivo) is False
    assert pref.salvar_preferencias_modulo("fornecedores", {"a": object()}, tmp_path) is False
