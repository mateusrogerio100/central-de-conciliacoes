"""V6 (tela) — o módulo no menu, a tela montada sem mostrar a janela e o resumo que ela mostra.

A parte visual o usuário confere usando a Central. Todos os testes usam um %APPDATA% temporário e nunca abrem nada no
Windows; os que usam os arquivos reais são pulados sem a pasta de exemplos.
"""

from __future__ import annotations

import ast
from decimal import Decimal as D

import pytest

from central import registro
from modulos.credito_estouro import MODULO, processamento
from modulos.credito_estouro import conciliador as c
from modulos.credito_estouro.controle import gravar_controle
from testes.conftest import RAIZ, esperar
from testes.credito_estouro.test_conciliador import _controle, _eventos, _razao
from testes.credito_estouro.test_maio_real import PASTA, controle_inicial

PASTA_MODULO = RAIZ / "modulos" / "credito_estouro"
reais = pytest.mark.skipif(not (PASTA / "casos_reais.json").exists(), reason="exemplos reais fora do git")


@pytest.fixture(autouse=True)
def appdata_temporario(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))


@pytest.fixture
def tela(criar_painel, monkeypatch):
    painel = criar_painel(MODULO)
    tela = painel.conciliacao
    tela.abertos = []
    monkeypatch.setattr(tela, "abrir", tela.abertos.append)          # nunca abre nada de verdade
    return tela


# ---------------------------------------------------------------------------
# Módulo e arquitetura
# ---------------------------------------------------------------------------

def test_modulo_no_menu_em_conciliacoes_ativo():
    assert registro.SECAO_DO_MODULO["credito_estouro"] == "CONCILIAÇÕES · ATIVO"
    carregado = next(m for m in registro.carregar_modulos() if m.chave == "credito_estouro")
    assert carregado.ok and carregado.info.nome == "Crédito Estouro" and carregado.info.icone == "carteira"
    assert (RAIZ / "central" / "icones" / "carteira.png").exists()
    assert (PASTA_MODULO / "INSTRUCOES_DE_USO.md").exists()


def test_tela_so_usa_o_processamento():
    for arquivo in (PASTA_MODULO / "telas").glob("*.py"):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        usados = {no.module for no in ast.walk(arvore)
                  if isinstance(no, ast.ImportFrom) and no.module and no.module.startswith("modulos")}
        usados |= {f"{no.module}.{n.name}" for no in ast.walk(arvore)
                   if isinstance(no, ast.ImportFrom) and no.module == "modulos.credito_estouro" for n in no.names}
        assert usados <= {"modulos.credito_estouro", "modulos.credito_estouro.processamento"}, arquivo.name


def test_logica_nao_importa_customtkinter():
    for arquivo in PASTA_MODULO.glob("*.py"):
        if arquivo.name in ("painel.py",):
            continue
        assert "customtkinter" not in arquivo.read_text(encoding="utf-8"), arquivo.name


# ---------------------------------------------------------------------------
# Resumo da tela (processamento.resumir)
# ---------------------------------------------------------------------------

def test_resumo_da_tela_mes_ficticio():
    eventos = _eventos()
    controle = _controle()
    conciliacao = c.conciliar(eventos, _razao(eventos, controle.total), controle)
    resultado = processamento.ResultadoCreditoEstouro(eventos=eventos, conciliacao=conciliacao)
    resumo = processamento.resumir(resultado)
    assert resumo.numeros == [("7", "0256 do mês anterior", "principal"), ("14", "itens a conferir", "atencao"),
                              ("R$ 0,00", "diferença sem explicação", "ok")]
    assert resumo.selo == ("Conferir", "atencao")
    textos = [texto for texto, _, _ in resumo.linhas]
    assert f"1 × {c.NAO_COBRADO}" in textos
    assert "2 lançamento(s) do razão a conferir (aba \"Lançamentos do razão a conferir\")" in textos
    assert f"1 × {c.DEVOLUCAO_CONFERIR}" in textos


def test_resumo_da_tela_com_erro():
    resumo = processamento.resumir(processamento.ResultadoCreditoEstouro(erro="Razão: não é razão"))
    assert resumo.selo == ("Com erro", "erro") and resumo.linhas == [("Razão: não é razão", "erro", None)]


# ---------------------------------------------------------------------------
# Tela
# ---------------------------------------------------------------------------

def test_tela_criada_com_a_aba_e_o_botao_desligado(tela):
    painel = tela.master
    while not hasattr(painel, "abas"):
        painel = painel.master
    assert list(painel.abas.botoes) == ["Conciliação", "Instruções de uso"]
    assert tela.botao.cget("text") == "Gerar conciliação"
    assert tela.botao.cget("state") == "disabled"


def _escolher(tela, eventos, razao, controle):
    tela.cartao_eventos.definir_caminhos(eventos)
    tela.cartao_razao.definir_caminhos(razao)
    tela.cartao_controle.definir_caminhos(controle)
    esperar(tela, lambda: all(c.status_confirmacao not in (None, "carregando") and len(tela.previas) == 3
                              for c in tela.cartoes_obrigatorios))


@pytest.fixture
def controle_maio(tmp_path):
    maio = controle_inicial("2026-05")
    return gravar_controle(tmp_path / "controle_maio.xlsx", maio.competencia, "FUNDAÇÃO HOSPITAL EXEMPLO", D("98853.35"),
                           maio.itens)


@reais
def test_junho_pela_tela(tela, tmp_path, controle_maio, criar_painel):
    saida = tmp_path / "saida"
    saida.mkdir()
    tela.cartao_pasta.definir_caminhos(saida)
    _escolher(tela, next((PASTA / "2026-06").glob("EVENTOS*")), PASTA / "2026-06" / "razao_06_credito_suplemento.xls",
              controle_maio)
    assert tela.cartao_eventos.status_confirmacao == "ok"
    assert tela.cartao_razao.texto_confirmacao == "Excel · jun/2026 · 27 lançamentos · saldo final R$ 116.027,92"
    assert tela.cartao_controle.texto_confirmacao.startswith("mai/2026 · ")
    assert tela.botao.cget("state") == "normal"

    tela.processar()
    esperar(tela, lambda: not tela.ocupado and tela.ultimo_resultado is not None)
    resultado = tela.ultimo_resultado
    assert resultado.erro == resultado.erro_saida == ""
    assert resultado.caminho_planilha.parent == saida and resultado.caminho_planilha.exists()
    assert tela.resultado.selo.cget("text") == "Conferir"                 # 7 pessoas para conferir em junho
    tela.abrir_planilha()
    assert tela.abertos == [resultado.caminho_planilha]
    assert processamento.ler_pasta_lembrada() == str(saida)
    assert criar_painel(MODULO).conciliacao.cartao_pasta.caminho == saida   # a pasta volta na próxima abertura


@reais
def test_razao_em_pdf_avisa_e_controle_de_outro_mes_desliga_o_botao(tela, tmp_path):
    abril = controle_inicial("2026-04")
    controle_abril = gravar_controle(tmp_path / "controle_abril.xlsx", abril.competencia, "", D("97075.60"),
                                     abril.itens)
    _escolher(tela, next((PASTA / "2026-06").glob("EVENTOS*")), PASTA / "2026-06" / "razao_06_credito_suplemento.pdf",
              controle_abril)
    assert tela.cartao_razao.status_confirmacao == "atencao" and "Excel" in tela.cartao_razao.texto_confirmacao
    assert tela.cartao_controle.status_confirmacao == "erro"
    assert "05/2026 (o mês anterior)" in tela.cartao_controle.texto_confirmacao
    assert tela.botao.cget("state") == "disabled"


@reais
def test_arquivo_no_campo_errado(tela):
    tela.cartao_razao.definir_caminhos(next((PASTA / "2026-06").glob("EVENTOS*")))
    esperar(tela, lambda: tela.cartao_razao.status_confirmacao == "erro")
    assert "PDF de eventos" in tela.cartao_razao.texto_confirmacao
