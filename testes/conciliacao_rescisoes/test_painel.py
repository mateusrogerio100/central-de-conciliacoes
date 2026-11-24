"""Tela do módulo Rescisões (montada sem mostrar a janela).

Refeitos a partir dos testes da tela antiga (test_interface_apoio.py do Conciliações AMES:
test_config_lembra_rescisoes, test_painel_rescisoes_com_arquivos_reais,
test_painel_rescisoes_financeiro_opcional e test_painel_rescisoes_aceita_varios_pdfs_de_eventos), com as
mesmas verificações, mais as regras da Central. Todos usam um %APPDATA% temporário e nunca abrem o Excel.
"""

from __future__ import annotations

import ast
import json

import pytest

from central import registro
from modulos.conciliacao_rescisoes import MODULO, processamento
from modulos.conciliacao_rescisoes.telas.conciliacao import TEXTO_SEM_FINANCEIRO
from testes.conftest import PASTA_EXEMPLOS, RAIZ, esperar

PASTA_RESCISOES = PASTA_EXEMPLOS / "conciliacao_rescisoes" / "Exemplos_Rescisoes"
RAZAO, EVENTOS, CONTROLE = "Razão 062026.xlsx", "EVENTOS 062026 COM IDENT F010405.PDF", "Rescisões a pagar.xlsx"


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
def jun2026():
    pasta = PASTA_RESCISOES / "jun2026"
    if not pasta.exists():
        pytest.skip("exemplos/conciliacao_rescisoes/Exemplos_Rescisoes não existe")
    return pasta


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
    assert registro.SECAO_DO_MODULO["conciliacao_rescisoes"] == "CONCILIAÇÕES · PASSIVO"
    carregado = next(m for m in registro.carregar_modulos() if m.chave == "conciliacao_rescisoes")
    assert carregado.ok and carregado.info.nome == "Rescisões"
    assert (RAIZ / "central" / "icones" / f"{carregado.info.icone}.png").exists()
    assert (RAIZ / "modulos" / "conciliacao_rescisoes" / "INSTRUCOES_DE_USO.md").exists()


def test_tela_so_usa_o_processamento():
    arvore = ast.parse((RAIZ / "modulos" / "conciliacao_rescisoes" / "telas" / "conciliacao.py")
                       .read_text(encoding="utf-8"))
    do_modulo = {no.module for no in ast.walk(arvore) if isinstance(no, ast.ImportFrom)
                 and no.module and no.module.startswith("modulos.")}
    assert do_modulo == {"modulos.conciliacao_rescisoes", "modulos.conciliacao_rescisoes.processamento"}


def test_modulo_nao_importa_outro_modulo():
    """O que Rescisões usa de Fornecedores está copiado na subpasta fornecedores/ do próprio módulo."""
    for arquivo in (RAIZ / "modulos" / "conciliacao_rescisoes").rglob("*.py"):
        for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
            if isinstance(no, ast.ImportFrom) and no.module and no.module.startswith("modulos."):
                assert no.module.startswith("modulos.conciliacao_rescisoes"), (arquivo.name, no.module)


def test_copia_de_fornecedores_igual_a_do_modulo_fornecedores():
    """A subpasta fornecedores/ é cópia inteira (só os import mudam): se um lado mudar, o teste avisa, para a
    mudança ser pensada nos dois módulos."""
    for nome in ("avisos", "leitores", "modelos", "pareamento", "relatorio_excel"):
        original = (RAIZ / "modulos" / "conciliacao_fornecedores" / f"{nome}.py").read_text(encoding="utf-8")
        copia = (RAIZ / "modulos" / "conciliacao_rescisoes" / "fornecedores" / f"{nome}.py").read_text(encoding="utf-8")
        assert copia == original.replace("modulos.conciliacao_fornecedores.",
                                         "modulos.conciliacao_rescisoes.fornecedores."), nome


# ---------------------------------------------------------------------------
# Pasta lembrada (era test_config_lembra_rescisoes)
# ---------------------------------------------------------------------------


def test_pasta_lembrada_salva_e_le(tmp_path):
    assert processamento.ler_pasta_lembrada(tmp_path) == ""
    assert processamento.salvar_pasta_lembrada(str(tmp_path), tmp_path)
    assert processamento.ler_pasta_lembrada(tmp_path) == str(tmp_path)


def test_pasta_vem_do_conciliacoes_ames_so_enquanto_a_central_nao_guardou(tmp_path):
    antigo = tmp_path / "config.json"
    antigo.write_text(json.dumps({"pasta_rescisoes": "C:/Conciliacoes/Rescisoes"}), encoding="utf-8")
    assert processamento.ler_pasta_lembrada(tmp_path / "central", antigo) == "C:/Conciliacoes/Rescisoes"
    processamento.salvar_pasta_lembrada("", tmp_path / "central")
    assert processamento.ler_pasta_lembrada(tmp_path / "central", antigo) == ""


def test_tela_lembra_a_pasta(criar_painel, tmp_path):
    destino = tmp_path / "planilhas"
    destino.mkdir()
    tela = criar_painel(MODULO).conciliacao
    assert not tela.cartao_pasta.preenchido
    tela.cartao_pasta.definir_caminhos([destino])
    assert processamento.ler_pasta_lembrada() == str(destino)
    tela.novo()                                                 # "Limpar tudo" não esquece a pasta
    assert tela.cartao_pasta.caminho == destino
    assert criar_painel(MODULO).conciliacao.cartao_pasta.caminho == destino


# ---------------------------------------------------------------------------
# Tela com os arquivos reais (eram test_painel_rescisoes_com_arquivos_reais, _financeiro_opcional e
# _aceita_varios_pdfs_de_eventos)
# ---------------------------------------------------------------------------


def test_tela_com_arquivos_reais(tela, jun2026, tmp_path):
    assert not tela.botao.habilitado
    razao, eventos, controle = jun2026 / RAZAO, jun2026 / EVENTOS, jun2026 / CONTROLE
    tela.cartao_razao.definir_caminhos([controle])                  # arquivo trocado
    assert tela.cartao_razao.status_confirmacao == "erro"
    tela.cartao_razao.definir_caminhos([razao])
    assert tela.cartao_razao.texto_confirmacao.endswith("92 pagamentos · saldo final R$ 132.082,98")
    tela.cartao_eventos.definir_caminhos([eventos])
    assert tela.cartao_eventos.texto_confirmacao == "0264 · jun/2026 · 85 pessoas · R$ 222.394,99"
    assert not tela.botao.habilitado
    tela.cartao_controle.definir_caminhos([controle])
    assert tela.cartao_controle.status_confirmacao == "ok"
    assert tela.botao.habilitado

    resultado = processamento.processar(razao, [eventos], controle, pasta_destino=tmp_path)
    tela.mostrar_resultado(resultado)
    tela.update()
    assert tela.resultado.selo.cget("text") == "Concluído"
    textos = _textos(tela.resultado)
    assert "Pagamentos achados" in textos and "89" in textos
    assert "Lista nova (135 rescisões)" in textos
    tela.novo()
    assert not any(c.preenchido for c in tela.cartoes_obrigatorios)


def test_financeiro_opcional(tela, jun2026, tmp_path):
    financeiro = PASTA_RESCISOES / "parte_final" / "Titulos a pagar financeiro 30092026.xlsx"
    if not financeiro.exists():
        pytest.skip("exemplos de Rescisões (parte_final) não disponíveis")
    assert tela.cartao_financeiro.texto_confirmacao == TEXTO_SEM_FINANCEIRO
    razao, eventos, controle = jun2026 / RAZAO, jun2026 / EVENTOS, jun2026 / CONTROLE
    tela.cartao_razao.definir_caminhos([razao])
    tela.cartao_eventos.definir_caminhos([eventos])
    tela.cartao_controle.definir_caminhos([controle])
    assert tela.botao.habilitado                                    # sem o financeiro: pode gerar
    tela.cartao_financeiro.definir_caminhos([controle])             # arquivo trocado: não deixa gerar
    assert tela.cartao_financeiro.status_confirmacao == "erro"
    assert not tela.botao.habilitado
    tela.cartao_financeiro.definir_caminhos([financeiro])
    assert tela.cartao_financeiro.texto_confirmacao == "98 títulos · 90 pessoas · R$ 53.836,22"
    assert tela.botao.habilitado

    resultado = processamento.processar(razao, [eventos], controle, financeiro, pasta_destino=tmp_path)
    tela.mostrar_resultado(resultado)
    tela.update()
    assert any(t.startswith("Financeiro × lista:") and "pessoa(s) para conferir" in t
               for t in _textos(tela.resultado))
    tela.cartao_financeiro.limpar_pelo_usuario()
    assert tela.cartao_financeiro.texto_confirmacao == TEXTO_SEM_FINANCEIRO
    tela.novo()
    assert not tela.cartao_financeiro.preenchido
    assert tela.cartao_financeiro.texto_confirmacao == TEXTO_SEM_FINANCEIRO


def test_aceita_varios_pdfs_de_eventos(tela, jun2026):
    nomes = [EVENTOS, "EVENTOS 062026 COM IDENT RESC COMPL.PDF", "EVENTOS COM IDENT 062026.PDF"]
    if not all((jun2026 / n).exists() for n in nomes):
        pytest.skip("PDFs complementares de jun/2026 não estão em exemplos/")
    assert tela.cartao_eventos.tipo == "arquivos"
    tela.cartao_razao.definir_caminhos([jun2026 / RAZAO])
    tela.cartao_controle.definir_caminhos([jun2026 / CONTROLE])
    tela.cartao_eventos.definir_caminhos([jun2026 / n for n in nomes])
    texto = tela.cartao_eventos.texto_confirmacao
    assert texto.startswith("3 PDFs · 0264 · jun/2026")
    assert "entram no mês: PDF mensal + PDF complementar 29/06" in texto
    assert "fora (provavelmente do mês seguinte): PDF complementar 15/07" in texto
    assert tela.botao.habilitado


def test_gerar_pela_tela_e_botoes_do_resultado(tela, jun2026, tmp_path):
    saida = tmp_path / "saida"
    saida.mkdir()
    tela.cartao_razao.definir_caminhos([jun2026 / RAZAO])
    tela.cartao_eventos.definir_caminhos([jun2026 / EVENTOS])
    tela.cartao_controle.definir_caminhos([jun2026 / CONTROLE])
    tela.cartao_pasta.definir_caminhos([saida])
    tela.processar()
    esperar(tela, lambda: not tela.ocupado)

    resultado = tela.resultado_conciliacao
    assert resultado.erro is None and resultado.caminho_relatorio == saida / "Conciliacao_Rescisoes_HospitalExemplo_jun2026.xlsx"
    botoes = {b.cget("text"): b for b in tela.resultado.rodape.winfo_children()}
    assert list(botoes)[:3] == ["Abrir planilha", "Abrir pasta", "Ver avisos"]
    botoes["Abrir planilha"].invoke()
    assert tela.abertos == [resultado.caminho_relatorio]
    botoes["Ver avisos"].invoke()
    assert tela.janela_avisos.texto.startswith("ARQUIVOS LIDOS\n•")
    tela.janela_avisos.destroy()
