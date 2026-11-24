"""Tela do módulo Fornecedores (montada sem mostrar a janela).

Refeitos a partir dos testes da tela antiga (test_interface_apoio.py do Conciliações AMES:
test_config_lembra_fornecedores e test_painel_fornecedores_com_arquivos_reais), com as mesmas
verificações, mais as regras da Central (registro, tela que só fala com o processamento.py).
Todos usam um %APPDATA% temporário e nunca abrem o Excel.
"""

from __future__ import annotations

import ast
import json

import pytest

from central import registro
from modulos.conciliacao_fornecedores import MODULO, processamento
from testes.conftest import RAIZ, pasta_exemplos


@pytest.fixture(autouse=True)
def appdata_temporario(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    return tmp_path / "appdata"


@pytest.fixture
def tela(criar_painel, monkeypatch):
    painel = criar_painel(MODULO).conciliacao
    painel.abertos = []
    monkeypatch.setattr(painel, "abrir", painel.abertos.append)   # nunca abre o Excel de verdade
    return painel


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
# Módulo e arquitetura
# ---------------------------------------------------------------------------


def test_modulo_no_registro_na_secao_do_passivo():
    assert registro.SECAO_DO_MODULO["conciliacao_fornecedores"] == "CONCILIAÇÕES · PASSIVO"
    carregado = next(m for m in registro.carregar_modulos() if m.chave == "conciliacao_fornecedores")
    assert carregado.ok and carregado.info.nome == "Fornecedores"
    assert (RAIZ / "central" / "icones" / f"{carregado.info.icone}.png").exists()
    assert (RAIZ / "modulos" / "conciliacao_fornecedores" / "INSTRUCOES_DE_USO.md").exists()


def test_tela_so_usa_o_processamento():
    """A tela não tem regra de negócio: do módulo, só conversa com processamento.py."""
    arvore = ast.parse((RAIZ / "modulos" / "conciliacao_fornecedores" / "telas" / "conciliacao.py")
                       .read_text(encoding="utf-8"))
    do_modulo = {no.module for no in ast.walk(arvore) if isinstance(no, ast.ImportFrom)
                 and no.module and no.module.startswith("modulos.")}
    assert do_modulo == {"modulos.conciliacao_fornecedores", "modulos.conciliacao_fornecedores.processamento"}


def test_modulo_nao_importa_outro_modulo():
    pasta = RAIZ / "modulos" / "conciliacao_fornecedores"
    for arquivo in pasta.rglob("*.py"):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, ast.ImportFrom) and no.module and no.module.startswith("modulos."):
                assert no.module.startswith("modulos.conciliacao_fornecedores"), (arquivo.name, no.module)


# ---------------------------------------------------------------------------
# Pasta lembrada (era test_config_lembra_fornecedores)
# ---------------------------------------------------------------------------


def test_pasta_lembrada_salva_e_le(tmp_path):
    assert processamento.ler_pasta_lembrada(tmp_path) == ""
    assert processamento.salvar_pasta_lembrada(str(tmp_path), tmp_path)
    assert processamento.ler_pasta_lembrada(tmp_path) == str(tmp_path)
    assert processamento.salvar_pasta_lembrada("", tmp_path)               # "Limpar" esquece
    assert processamento.ler_pasta_lembrada(tmp_path) == ""


def test_pasta_vem_do_conciliacoes_ames_so_enquanto_a_central_nao_guardou(tmp_path):
    antigo = tmp_path / "config.json"
    antigo.write_text(json.dumps({"modo": "claro", "pasta_fornecedores": "C:/Conciliacoes/Fornecedores"}),
                      encoding="utf-8")
    assert processamento.ler_pasta_lembrada(tmp_path / "central", antigo) == "C:/Conciliacoes/Fornecedores"
    processamento.salvar_pasta_lembrada("", tmp_path / "central")          # a Central já guardou (vazio)
    assert processamento.ler_pasta_lembrada(tmp_path / "central", antigo) == ""


def test_tela_abre_com_a_pasta_lembrada(criar_painel, tmp_path):
    processamento.salvar_pasta_lembrada(str(tmp_path))
    tela = criar_painel(MODULO).conciliacao
    assert tela.cartao_pasta.caminho == tmp_path
    assert tela.cartao_pasta.texto_confirmacao == f"Última pasta usada: {tmp_path}"
    tela.cartao_pasta.limpar_pelo_usuario()
    assert processamento.ler_pasta_lembrada() == ""
    assert tela.cartao_pasta.texto_confirmacao.startswith("Sem escolher")


# ---------------------------------------------------------------------------
# Tela com os arquivos reais (era test_painel_fornecedores_com_arquivos_reais)
# ---------------------------------------------------------------------------


def test_tela_com_arquivos_reais(tela, tmp_path):
    assert not tela.botao.habilitado
    exemplos = pasta_exemplos("conciliacao_fornecedores", "Exemplos_Fornecedores")
    vale, cidade_delta = exemplos / "vale_zeta_set2026", exemplos / "cidade_delta_set2026"

    tela.cartao_balancete.definir_caminhos([vale / "balancete_VJ.xls"])
    assert tela.cartao_balancete.texto_confirmacao.startswith("Ame - Vale Zeta · set/2026 · 54 contas")
    tela.cartao_titulos.definir_caminhos([cidade_delta / "titulos_pagar_SC.xls"])
    assert tela.cartao_titulos.status_confirmacao == "erro"             # unidades diferentes
    assert not tela.botao.habilitado
    tela.cartao_titulos.definir_caminhos([vale / "titulos_pagar_VJ.xls"])
    assert tela.cartao_titulos.status_confirmacao == "ok"
    assert tela.botao.habilitado
    tela.cartao_titulos.definir_caminhos([vale / "balancete_VJ.xls"])    # relatório trocado
    assert tela.cartao_titulos.status_confirmacao == "erro"
    tela.cartao_titulos.definir_caminhos([vale / "titulos_pagar_VJ.xls"])

    resultado = processamento.processar(vale / "balancete_VJ.xls", vale / "titulos_pagar_VJ.xls", tmp_path)
    tela.mostrar_resultado(resultado)
    tela.update()
    assert tela.resultado.selo.cget("text") == "Concluído"
    assert not any("Nr. Doc." in texto for texto in _textos(tela.resultado))   # sem títulos

    # Cidade Delta tem fornecedores só no financeiro: a tela aponta a aba dos títulos
    resultado = processamento.processar(cidade_delta / "balancete_SC.xls", cidade_delta / "titulos_pagar_SC.xls",
                                        tmp_path)
    tela.mostrar_resultado(resultado)
    tela.update()
    assert any("Nr. Doc. e Nr. Título de 4 título(s)" in texto for texto in _textos(tela.resultado))
    tela.novo()
    assert not any(c.preenchido for c in tela.cartoes_relatorios)


def test_gerar_pela_tela_e_botoes_do_resultado(tela, tmp_path):
    from testes.conftest import esperar

    vale = pasta_exemplos("conciliacao_fornecedores", "Exemplos_Fornecedores", "vale_zeta_set2026")
    tela.cartao_balancete.definir_caminhos([vale / "balancete_VJ.xls"])
    tela.cartao_titulos.definir_caminhos([vale / "titulos_pagar_VJ.xls"])
    tela.cartao_pasta.definir_caminhos([tmp_path])
    tela.processar()
    esperar(tela, lambda: not tela.ocupado)

    resultado = tela.resultado_conciliacao
    assert resultado.erro is None and resultado.caminho_relatorio.parent == tmp_path
    assert resultado.caminho_relatorio.name == "Conciliacao_Fornecedores_ValeZeta_set2026.xlsx"
    botoes = {b.cget("text"): b for b in tela.resultado.rodape.winfo_children()}
    assert list(botoes) == ["Abrir planilha", "Abrir pasta", "Ver avisos"]
    botoes["Abrir planilha"].invoke()
    assert tela.abertos == [resultado.caminho_relatorio]
    botoes["Ver avisos"].invoke()
    assert tela.janela_avisos.texto.startswith("ARQUIVOS LIDOS\n• balancete_VJ.xls")
    tela.janela_avisos.destroy()


# ---------------------------------------------------------------------------
# Casos com nomes reais: ficam fora do git (exemplos\conciliacao_fornecedores\casos_reais.json)
# ---------------------------------------------------------------------------


def test_nota_de_semelhanca_casos_reais():
    from modulos.conciliacao_fornecedores.pareamento import nota_semelhanca

    casos = json.loads((pasta_exemplos("conciliacao_fornecedores") / "casos_reais.json").read_text(encoding="utf-8"))
    for nome_balancete, nome_financeiro in casos["pares_que_pareiam"]:
        assert nota_semelhanca(nome_balancete, nome_financeiro) >= 0.60
