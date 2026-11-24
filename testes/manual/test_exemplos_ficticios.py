"""Os exemplos fictícios do manual (manual\\ficticios) continuam valendo.

Cada exemplo abre a tela do módulo (escondida), escolhe os arquivos gerados, gera o resultado e não pode
dar erro: se um módulo mudar o formato que lê, este teste avisa que o exemplo do manual precisa mudar
junto. As preferências e o cadastro de prestadores vão para uma pasta temporária (nunca os de verdade).
"""

from __future__ import annotations

import pytest

from central import registro
from manual.ficticios import GERADORES, gerar_todos
from manual.ficticios.aplicar import aplicar, numeros_na_tela


@pytest.fixture(autouse=True)
def appdata_temporario(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))


@pytest.fixture(scope="module")
def exemplos(tmp_path_factory):
    return gerar_todos(tmp_path_factory.mktemp("ficticios"))


def test_todo_modulo_do_menu_tem_exemplo():
    assert sorted(GERADORES) == sorted(registro.NOMES_MODULOS)


def test_nomes_dos_prints_nao_se_repetem(exemplos):
    nomes = [e.nome for e in exemplos]
    assert len(nomes) == len(set(nomes))


@pytest.mark.parametrize("chave", GERADORES)
def test_exemplo_gera_o_resultado_sem_erro(chave, exemplos, criar_painel, monkeypatch):
    info = next(m.info for m in registro.carregar_modulos() if m.ok and m.info.chave == chave)
    do_modulo = [e for e in exemplos if e.chave == chave]
    assert do_modulo
    for exemplo in do_modulo:
        for alvo, substituta in exemplo.substituicoes.items():
            monkeypatch.setattr(alvo, substituta)
        tela = aplicar(criar_painel(info), exemplo)
        assert tela.mensagens == [], exemplo.nome
        assert exemplo.numeros, f"{exemplo.nome}: informe os números que o print mostra"
        if exemplo.acao is None:                 # Imprimir PDFs: só a lista (nada vai para a impressora)
            assert numeros_na_tela(tela) == exemplo.numeros
            continue
        assert tela.resultado.estado == "concluido", exemplo.nome
        assert numeros_na_tela(tela.resultado) == exemplo.numeros, exemplo.nome
        assert tela.resultado.selo is not None and tela.resultado.selo.status != "erro", exemplo.nome
        if exemplo.pasta_saida is not None:
            assert any(exemplo.pasta_saida.iterdir()), f"{exemplo.nome}: nada gravado na pasta de saída"
