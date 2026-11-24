"""V6 — tela do módulo Convênios (montada sem mostrar a janela) e o apoio à tela no processamento.

A parte visual é conferida pelo usuário ao usar a Central; aqui ficam as regras da tela: módulo no registro (seção
RECEITAS), arquitetura (tela só fala com o processamento), botão só com tudo certo, pasta config sugerida, a
pergunta antes de substituir um mês preenchido e as escolhas lembradas. Todos os testes usam um %APPDATA%
temporário e nunca abrem nada no Windows.
"""

from __future__ import annotations

import ast

import pytest

from central import registro
from modulos.convenios import MODULO, processamento
from testes.conftest import RAIZ, esperar
from testes.convenios.conftest import conta, escrever_planilha, escrever_razao, lancamento, total

PASTA_MODULO = RAIZ / "modulos" / "convenios"
C1 = ("40075", "4.01.05.01.0001", "Convênio Prefeitura Exemplo")


@pytest.fixture(autouse=True)
def appdata_temporario(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))


def _fat(nome: str) -> str:
    return f"Faturamento Mês NF 1 {nome} Set/2026 Protocolo 1"


@pytest.fixture
def entradas(tmp_path):
    """Razão de set/2026 (Alfa 10, Bravo 5), a planilha (Alfa e Charlie; Charlie já tem setembro na versão
    "preenchida"), a pasta config ao lado da planilha e a saída."""
    razao = escrever_razao(tmp_path / "Razao.xlsx", conta(*C1), lancamento(_fat("Alfa"), credito=10),
                           lancamento(_fat("Bravo"), credito=5), total(*C1, credito=15))
    receitas = tmp_path / "receitas"
    receitas.mkdir()
    planilha = escrever_planilha(receitas / "RECEITAS.xlsx", [("Alfa", {8: 1}), ("Charlie", {})])
    preenchida = escrever_planilha(receitas / "RECEITAS preenchida.xlsx", [("Alfa", {}), ("Charlie", {9: 7})])
    (receitas / "config").mkdir()
    (receitas / "config" / "equivalencias.csv").write_text("Nome_no_razao;Linha_da_planilha;Obs\n", encoding="utf-8")
    saida = tmp_path / "saida"
    saida.mkdir()
    return {"razao": razao, "planilha": planilha, "preenchida": preenchida, "config": receitas / "config",
            "saida": saida}


@pytest.fixture
def tela(criar_painel, monkeypatch):
    painel = criar_painel(MODULO)
    tela = painel.preenchimento
    tela.abertos, tela.perguntas = [], []
    monkeypatch.setattr(tela, "abrir", tela.abertos.append)          # nunca abre nada de verdade
    return tela


def _confirmacao(tela, cartao):
    esperar(tela, lambda: cartao.status_confirmacao is not None)
    return cartao.texto_confirmacao, cartao.status_confirmacao


def _escolher(tela, entradas, planilha="planilha"):
    tela.cartao_razao.definir_caminhos(entradas["razao"])
    tela.cartao_planilha.definir_caminhos(entradas[planilha])
    tela.cartao_saida.definir_caminhos(entradas["saida"])
    esperar(tela, tela.pronto_para_processar)


# ---------------------------------------------------------------------------
# Módulo e arquitetura
# ---------------------------------------------------------------------------

def test_v6_modulo_no_registro_na_secao_receitas():
    assert registro.SECAO_DO_MODULO["convenios"] == "RECEITAS"
    nomes_secoes = [secao for secao, _ in registro.SECOES]
    assert nomes_secoes.index("RECEITAS") == nomes_secoes.index("FERRAMENTAS") - 1
    carregado = next(m for m in registro.carregar_modulos() if m.chave == "convenios")
    assert carregado.ok and carregado.info.nome == "Convênios" and carregado.info.icone == "grafico"
    assert (RAIZ / "central" / "icones" / "grafico.png").exists()
    assert (PASTA_MODULO / "INSTRUCOES_DE_USO.md").exists()


def test_v6_telas_so_usam_o_processamento():
    for arquivo in (PASTA_MODULO / "telas").glob("*.py"):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        usados = {no.module + "." + n.name for no in ast.walk(arvore)
                  if isinstance(no, ast.ImportFrom) and no.module and no.module.startswith("modulos")
                  for n in no.names}
        assert usados <= {"modulos.convenios.processamento"}, arquivo.name


# ---------------------------------------------------------------------------
# Apoio à tela (processamento)
# ---------------------------------------------------------------------------

def test_v6_confirmacoes(entradas, tmp_path):
    (texto, status), competencia = processamento.confirmar_razao(entradas["razao"])
    assert (texto, status, competencia) == ("Mês 09/2026 · 1 conta(s) · R$ 15,00", "ok", (2026, 9))
    assert processamento.confirmar_razao(tmp_path / "nao.xlsx")[0][1] == "erro"
    assert processamento.confirmar_planilha(entradas["planilha"], (2026, 9)) == \
        ("Aba 2026 · 2 convênios · setembro vazio", "ok")
    assert processamento.confirmar_planilha(entradas["preenchida"], (2026, 9)) == \
        ("Aba 2026 · 2 convênios · setembro já preenchido em 1 linha(s)", "atencao")
    assert processamento.confirmar_planilha(entradas["planilha"], (2027, 1))[1] == "erro"     # sem a aba 2027
    assert processamento.confirmar_planilha(entradas["planilha"], None)[1] is None
    assert processamento.confirmar_equivalencias(entradas["config"]) == ("0 equivalência(s) no equivalencias.csv",
                                                                        "ok")
    assert processamento.confirmar_equivalencias(tmp_path)[1] == "erro"
    assert processamento.pasta_equivalencias_sugerida(entradas["planilha"]) == entradas["config"]
    assert processamento.conferir_mes(entradas["razao"], entradas["preenchida"]) == ("09/2026", ["Charlie"])
    assert processamento.conferir_mes(entradas["razao"], entradas["planilha"]) == ("09/2026", [])


def test_v6_resumo(entradas):
    r = processamento.processar(entradas["razao"], entradas["planilha"], entradas["saida"], entradas["config"])
    resumo = processamento.resumir(r)
    assert resumo.numeros == [(2, "convênios preenchidos", "principal"), (1, "linhas novas", "atencao"),
                              (0, "lançamentos não identificados", "ok")]
    assert resumo.convenios == [(5, "Alfa", "10,00"), (6, "Bravo", "5,00")]
    assert resumo.linhas[0] == ("TOTAL RECEITAS × Saldo Contábil: diferença", "ok", "R$ 0,00")
    assert resumo.selo == ("Conferir", "atencao")                        # a linha nova pede conferência


# ---------------------------------------------------------------------------
# Tela
# ---------------------------------------------------------------------------

def test_v6_tela_criada_com_a_aba_e_o_botao_desabilitado(tela):
    painel = tela.master
    while not hasattr(painel, "abas"):
        painel = painel.master
    assert list(painel.abas.botoes) == ["Preenchimento", "Instruções de uso"]
    assert tela.botao.cget("text") == "Preencher"
    assert tela.botao.cget("state") == "disabled"


def test_v6_preencher_pela_tela(tela, entradas, criar_painel):
    _escolher(tela, entradas)
    assert _confirmacao(tela, tela.cartao_razao) == ("Mês 09/2026 · 1 conta(s) · R$ 15,00", "ok")
    esperar(tela, lambda: tela.cartao_equivalencias.caminho == entradas["config"])     # a pasta config entra sozinha
    esperar(tela, lambda: tela.cartao_planilha.texto_confirmacao.startswith("Aba 2026"))
    assert tela.botao.cget("state") == "normal"

    tela.processar()
    esperar(tela, lambda: not tela.ocupado and tela.ultimo_resultado is not None)
    resultado = tela.ultimo_resultado
    assert resultado.erro == resultado.erro_saida == "" and resultado.caminho_planilha.exists()
    assert tela.resultado.estado == "concluido" and tela.resultado.selo.cget("text") == "Conferir"
    assert set(tela.botoes_resultado) == {"Abrir planilha", "Abrir relatório", "Abrir pasta"}
    tela.botoes_resultado["Abrir planilha"].invoke()
    assert tela.abertos == [resultado.caminho_planilha]

    lembrado = processamento.ler_preferencias()
    assert lembrado == {"planilha": str(entradas["planilha"]), "equivalencias": str(entradas["config"]),
                        "saida": str(entradas["saida"])}
    nova = criar_painel(MODULO).preenchimento                           # no mês seguinte: só falta o razão
    assert nova.cartao_planilha.caminho == entradas["planilha"] and nova.cartao_razao.caminho is None
    assert nova.cartao_saida.caminho == entradas["saida"]


def test_v6_mes_preenchido_pergunta_antes_de_substituir(tela, entradas, monkeypatch):
    respostas = [False, True]
    monkeypatch.setattr(tela, "perguntar", lambda texto: tela.perguntas.append(texto) or respostas.pop(0))
    _escolher(tela, entradas, "preenchida")
    assert _confirmacao(tela, tela.cartao_planilha)[1] == "atencao"

    tela.processar()                                                    # responde "Não": nada é gravado
    esperar(tela, lambda: not tela.ocupado and tela.perguntas)
    assert "09/2026 já está preenchido em 1 linha(s)" in tela.perguntas[0]
    assert list(entradas["saida"].iterdir()) == [] and tela.ultimo_resultado is None

    tela.processar()                                                    # responde "Sim"
    esperar(tela, lambda: not tela.ocupado and tela.ultimo_resultado is not None)
    situacoes = {l.nome: l.situacao for l in tela.ultimo_resultado.preenchimento.linhas}
    assert situacoes["Charlie"] == "mantida: sem lançamento no razão"


def test_v6_pasta_escolhida_a_mao_nunca_e_trocada(tela, entradas, tmp_path):
    propria = tmp_path / "minha_config"
    propria.mkdir()
    tela.cartao_equivalencias.definir_caminhos(propria)
    tela.cartao_planilha.definir_caminhos(entradas["planilha"])
    for _ in range(20):
        tela.update()
    assert tela.cartao_equivalencias.caminho == propria


def test_v6_planilha_sem_a_aba_do_ano_nao_habilita(tela, entradas, tmp_path):
    antiga = escrever_planilha(tmp_path / "antiga.xlsx", [("Alfa", {})], ano=2025, abas_antigas=())
    tela.cartao_razao.definir_caminhos(entradas["razao"])
    tela.cartao_planilha.definir_caminhos(antiga)
    tela.cartao_saida.definir_caminhos(entradas["saida"])
    esperar(tela, lambda: tela.cartao_planilha.status_confirmacao == "erro")
    assert "não tem a aba" in tela.cartao_planilha.texto_confirmacao
    assert tela.botao.cget("state") == "disabled"
