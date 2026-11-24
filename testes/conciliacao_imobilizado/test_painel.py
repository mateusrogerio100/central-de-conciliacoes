"""Tela do módulo Imobilizado – AME's (montada sem mostrar a janela).

Refeitos a partir dos testes da tela antiga (test_interface_apoio.py do Conciliações AMES:
test_config_lembra_conciliacao_bens, test_painel_bens_abre_pelo_menu_e_e_lembrado,
test_painel_bens_com_arquivos_reais, test_config_lembra_pasta_do_imobilizado e
test_painel_imobilizado_lembra_a_pasta), com as mesmas verificações, mais as regras da Central.
"Lembrar o item aberto" não existe mais: a Central abre sempre no mesmo módulo (ESPECIFICACAO, seção 7).
Todos usam um %APPDATA% temporário e nunca abrem o Excel.
"""

from __future__ import annotations

import ast
import json
import shutil

import pytest

from central import registro
from modulos.conciliacao_imobilizado import MODULO, processamento
from testes.conftest import RAIZ, esperar, pasta_exemplos

BALANCETES = ("intangivel_ame_cidade_alfa.xls", "imobilizado_ame_cidade_alfa.xls", "cessao_ame_cidade_alfa.xls")
RAZAO = "Patrimonio_razao_ame_cidade_alfa.xls"


@pytest.fixture(autouse=True)
def appdata_temporario(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))


@pytest.fixture
def tela(criar_painel, monkeypatch):
    painel = criar_painel(MODULO).conciliacao
    painel.abertos = []
    monkeypatch.setattr(painel, "abrir", painel.abertos.append)   # nunca abre o Excel de verdade
    return painel


@pytest.fixture
def exemplos(tmp_path):
    """Os relatórios do AME Cidade Alfa (ago/2026) copiados para uma pasta temporária."""
    pasta = pasta_exemplos("conciliacao_imobilizado", "Exemplos_Patrimonio_AME")
    copia = tmp_path / "relatorios"
    copia.mkdir()
    for arquivo in pasta.glob("*.xls"):
        shutil.copy(arquivo, copia / arquivo.name)
    return copia


def _textos(widget):
    """Todos os textos de rótulos dentro de um widget (para conferir o que a tela mostra)."""
    textos = []
    for filho in widget.winfo_children():
        try:
            texto = filho.cget("text")
        except Exception:
            texto = None
        if isinstance(texto, str):
            textos.append(texto)
        textos.extend(_textos(filho))
    return textos


# ---------------------------------------------------------------------------
# Módulo e arquitetura (era test_painel_bens_abre_pelo_menu_e_e_lembrado)
# ---------------------------------------------------------------------------


def test_modulo_no_registro_na_secao_do_ativo():
    assert registro.SECAO_DO_MODULO["conciliacao_imobilizado"] == "CONCILIAÇÕES · ATIVO"
    carregado = next(m for m in registro.carregar_modulos() if m.chave == "conciliacao_imobilizado")
    assert carregado.ok and carregado.info.nome == "Imobilizado – AME's"
    assert (RAIZ / "central" / "icones" / f"{carregado.info.icone}.png").exists()
    assert (RAIZ / "modulos" / "conciliacao_imobilizado" / "INSTRUCOES_DE_USO.md").exists()


def test_tela_abre_com_o_botao_apagado(tela):
    assert not tela.botao.habilitado


def test_tela_so_usa_o_processamento():
    arvore = ast.parse((RAIZ / "modulos" / "conciliacao_imobilizado" / "telas" / "conciliacao.py")
                       .read_text(encoding="utf-8"))
    do_modulo = {no.module for no in ast.walk(arvore) if isinstance(no, ast.ImportFrom)
                 and no.module and no.module.startswith("modulos.")}
    assert do_modulo == {"modulos.conciliacao_imobilizado", "modulos.conciliacao_imobilizado.processamento"}


def test_modulo_nao_importa_outro_modulo():
    for arquivo in (RAIZ / "modulos" / "conciliacao_imobilizado").rglob("*.py"):
        for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
            if isinstance(no, ast.ImportFrom) and no.module and no.module.startswith("modulos."):
                assert no.module.startswith("modulos.conciliacao_imobilizado"), (arquivo.name, no.module)


# ---------------------------------------------------------------------------
# Pasta lembrada (eram test_config_lembra_pasta_do_imobilizado e test_painel_imobilizado_lembra_a_pasta)
# ---------------------------------------------------------------------------


def test_pasta_lembrada_salva_e_le(tmp_path):
    assert processamento.ler_pasta_lembrada(tmp_path) == ""
    assert processamento.salvar_pasta_lembrada(str(tmp_path), tmp_path)
    assert processamento.ler_pasta_lembrada(tmp_path) == str(tmp_path)


def test_pasta_vem_do_conciliacoes_ames_so_enquanto_a_central_nao_guardou(tmp_path):
    antigo = tmp_path / "config.json"
    antigo.write_text(json.dumps({"pasta_imobilizado": "C:/Conciliacoes/Imobilizado"}), encoding="utf-8")
    assert processamento.ler_pasta_lembrada(tmp_path / "central", antigo) == "C:/Conciliacoes/Imobilizado"
    processamento.salvar_pasta_lembrada("", tmp_path / "central")
    assert processamento.ler_pasta_lembrada(tmp_path / "central", antigo) == ""


def test_tela_lembra_a_pasta(criar_painel, tmp_path):
    destino = tmp_path / "planilhas"
    destino.mkdir()
    tela = criar_painel(MODULO).conciliacao
    assert not tela.cartao_pasta.preenchido
    tela.cartao_pasta.definir_caminhos([destino])               # como se o usuário escolhesse
    assert processamento.ler_pasta_lembrada() == str(destino)
    tela.novo()                                                 # "Limpar tudo" não esquece a pasta
    assert tela.cartao_pasta.caminho == destino

    outra = criar_painel(MODULO).conciliacao                    # abre de novo: pasta lembrada
    assert outra.cartao_pasta.caminho == destino
    outra.cartao_pasta.limpar_pelo_usuario()
    assert processamento.ler_pasta_lembrada() == ""


# ---------------------------------------------------------------------------
# Tela com os arquivos reais (era test_painel_bens_com_arquivos_reais)
# ---------------------------------------------------------------------------


def test_tela_com_arquivos_reais(tela, exemplos):
    tela.cartao_razao.definir_caminhos([exemplos / RAZAO])
    assert tela.cartao_razao.texto_confirmacao == "agosto/2026 · 9 contas"
    assert not tela.botao.habilitado                            # faltam os balancetes
    tela.cartao_balancetes.definir_caminhos([exemplos / n for n in BALANCETES])
    assert tela.cartao_balancetes.texto_confirmacao == "Ame - Cidade Alfa · agosto/2026 · 9 contas"
    assert tela.botao.habilitado

    # opcional errado (o patrimônio no lugar dos bens adquiridos) bloqueia o botão
    tela.cartao_bens.definir_caminhos([exemplos / RAZAO])
    assert tela.cartao_bens.status_confirmacao == "erro"
    assert not tela.botao.habilitado
    tela.cartao_bens.limpar_pelo_usuario()
    assert tela.botao.habilitado

    # o resultado mostrado é o mesmo que o processamento devolve
    resultado = processamento.processar(tela.cartao_razao.caminho, tela.cartao_balancetes.caminhos)
    tela.mostrar_resultado(resultado)
    tela.update()
    assert tela.resultado_conciliacao is resultado
    assert tela.resultado.selo.cget("text") == "Concluído"
    tela.novo()
    assert not any(c.preenchido for c in tela.cartoes_relatorios)


def test_gerar_pela_tela_e_botoes_do_resultado(tela, exemplos, tmp_path):
    saida = tmp_path / "saida"
    saida.mkdir()
    tela.cartao_razao.definir_caminhos([exemplos / RAZAO])
    tela.cartao_balancetes.definir_caminhos([exemplos / n for n in BALANCETES])
    tela.cartao_pasta.definir_caminhos([saida])
    tela.processar()
    esperar(tela, lambda: not tela.ocupado)

    resultado = tela.resultado_conciliacao
    assert resultado.erro is None and resultado.caminho_relatorio.parent == saida
    assert resultado.caminho_relatorio.name.startswith("Conciliacao_imobilizado_2026-08_Ame_Cidade_Alfa_")
    botoes = {b.cget("text"): b for b in tela.resultado.rodape.winfo_children()}
    assert list(botoes) == ["Abrir pasta", "Ver avisos", "Novo"]
    # sem os opcionais e com a diferença de 0,03: a tela pede os relatórios que ajudariam
    assert any(t.startswith("Há diferença sem explicação.") for t in _textos(tela.resultado))
    botoes["Ver avisos"].invoke()
    assert tela.janela_avisos.texto.startswith("ARQUIVOS LIDOS\n•")
    tela.janela_avisos.destroy()
    botoes["Novo"].invoke()
    assert not tela.cartao_razao.preenchido and tela.cartao_pasta.caminho == saida


# ---------------------------------------------------------------------------
# Aba "Comparação Ativo x Passivo" (pedido do usuário, 05/11/2026)
# ---------------------------------------------------------------------------

PASTA_AP = ("conciliacao_imobilizado", "ativo_passivo_2026-10_cidade_gama")
RAZAO_ATIVO, RAZAO_PASSIVO = "Imobilizado Ativo.xls", "Imobilizado Passivo .xls"


@pytest.fixture
def tela_ap(criar_painel, monkeypatch):
    return criar_painel(MODULO).ativo_passivo


@pytest.fixture
def razoes(tmp_path):
    pasta = pasta_exemplos(*PASTA_AP)
    copia = tmp_path / "razoes"
    copia.mkdir()
    for arquivo in pasta.glob("*.xls"):
        shutil.copy(arquivo, copia / arquivo.name)
    return copia


def test_abas_do_modulo(criar_painel):
    painel = criar_painel(MODULO)
    assert list(painel.abas.botoes) == ["Conciliação", "Comparação Ativo x Passivo", "Instruções de uso"]


def test_aba_ativo_passivo_so_usa_o_processamento():
    arvore = ast.parse((RAIZ / "modulos" / "conciliacao_imobilizado" / "telas" / "ativo_passivo.py")
                       .read_text(encoding="utf-8"))
    do_modulo = {no.module for no in ast.walk(arvore) if isinstance(no, ast.ImportFrom)
                 and no.module and no.module.startswith("modulos.")}
    assert do_modulo == {"modulos.conciliacao_imobilizado", "modulos.conciliacao_imobilizado.processamento"}


def test_aba_ativo_passivo_cartoes_e_botao(tela_ap, razoes):
    assert not tela_ap.botao.habilitado
    tela_ap.cartao_ativo.definir_caminhos([razoes / RAZAO_PASSIVO])          # trocado: erro e botão apagado
    assert tela_ap.cartao_ativo.status_confirmacao == "erro"
    tela_ap.cartao_ativo.definir_caminhos([razoes / RAZAO_ATIVO])
    assert tela_ap.cartao_ativo.texto_confirmacao == "AME - Cidade Gama · outubro/2026 · 10 contas"
    assert not tela_ap.botao.habilitado
    tela_ap.cartao_passivo.definir_caminhos([razoes / RAZAO_PASSIVO])
    assert tela_ap.botao.habilitado


def test_aba_ativo_passivo_gera_e_mostra_a_diferenca(tela_ap, razoes, tmp_path):
    saida = tmp_path / "saida"
    saida.mkdir()
    tela_ap.cartao_ativo.definir_caminhos([razoes / RAZAO_ATIVO])
    tela_ap.cartao_passivo.definir_caminhos([razoes / RAZAO_PASSIVO])
    tela_ap.cartao_pasta.definir_caminhos([saida])
    tela_ap.processar()
    esperar(tela_ap, lambda: not tela_ap.ocupado)

    resultado = tela_ap.resultado_comparacao
    assert resultado.erro == "" and resultado.caminho_relatorio.parent == saida
    assert resultado.caminho_relatorio.name.startswith("Conciliacao_ativo_passivo_2026-10_AME_Cidade_Gama_")
    assert tela_ap.resultado.selo.cget("text") == "Concluído"
    textos = _textos(tela_ap.resultado)
    assert "Equipamentos hospitalares - AME Cidade Gama" in textos and "69.500,00" in textos
    botoes = {b.cget("text"): b for b in tela_ap.resultado.rodape.winfo_children()}
    assert list(botoes) == ["Abrir pasta", "Ver avisos", "Novo"]
    botoes["Ver avisos"].invoke()
    assert tela_ap.janela_avisos.texto.startswith("ARQUIVOS LIDOS\n•")
    tela_ap.janela_avisos.destroy()
    botoes["Novo"].invoke()
    assert not tela_ap.cartao_ativo.preenchido and tela_ap.cartao_pasta.caminho == saida
