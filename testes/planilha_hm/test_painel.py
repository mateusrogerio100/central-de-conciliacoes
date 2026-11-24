"""PlanilhaHM 6: tela do módulo (montada sem mostrar a janela) e o apoio à tela no processamento (seção 7).

A parte visual é conferida pelo usuário ao usar a Central; aqui ficam as regras da tela: módulo no menu (logo abaixo
de Honorários Médicos), a tela só fala com o processamento, o botão só acende com o Eventos e o Movimento do mesmo
mês, as perguntas (aba Senior preenchida, cópia existente, seção do evento novo) e a pasta lembrada. Todos os
testes usam um %APPDATA% temporário e nunca abrem nada no Windows.
"""

from __future__ import annotations

import ast

import pytest

from central import registro
from modulos.planilha_hm import MODULO, processamento
from testes.conftest import RAIZ, esperar
from testes.planilha_hm.conftest import escrever_caso_ficticio

PASTA_MODULO = RAIZ / "modulos" / "planilha_hm"
CONTA_NOVA = "3.9.02.0001"

pytestmark = pytest.mark.filterwarnings("ignore:Print area cannot be set")


@pytest.fixture(autouse=True)
def appdata_temporario(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))


@pytest.fixture
def entradas(tmp_path):
    planilha, eventos, movimento = escrever_caso_ficticio(tmp_path)
    saida = tmp_path / "saida"
    saida.mkdir()
    return {"planilha": planilha, "eventos": eventos, "movimento": movimento, "saida": saida,
            "config": tmp_path / "config"}


@pytest.fixture
def tela(criar_painel, monkeypatch):
    tela = criar_painel(MODULO).preenchimento
    tela.abertos, tela.perguntas, tela.secoes_perguntadas = [], [], []
    monkeypatch.setattr(tela, "abrir", tela.abertos.append)          # nunca abre nada de verdade

    def escolher(textos, numero, total):
        tela.secoes_perguntadas.append(textos)
        return processamento.RESPOSTA_SECAO_NOVA

    monkeypatch.setattr(tela, "escolher_secao", escolher)            # nunca abre a janela de verdade
    return tela


def _escolher(tela, entradas):
    tela.cartao_eventos.definir_caminhos(entradas["eventos"])
    tela.cartao_movimento.definir_caminhos(entradas["movimento"])
    tela.cartao_planilha.definir_caminhos(entradas["planilha"])
    tela.cartao_saida.definir_caminhos(entradas["saida"])
    esperar(tela, tela.pronto_para_processar)


def _processar(tela):
    tela.processar()
    esperar(tela, lambda: not tela.ocupado)


# ---------------------------------------------------------------------------
# Módulo e arquitetura
# ---------------------------------------------------------------------------

def test_6_modulo_no_menu_logo_abaixo_de_honorarios_medicos():
    secao = dict(registro.SECOES)["CONCILIAÇÕES · PASSIVO"]
    assert secao.index("planilha_hm") == secao.index("honorarios_medicos") + 1
    carregado = next(m for m in registro.carregar_modulos() if m.chave == "planilha_hm")
    assert carregado.ok and carregado.info.nome == "Planilha HM" and carregado.info.icone == "tabela"
    assert (RAIZ / "central" / "icones" / "tabela.png").exists()
    assert (PASTA_MODULO / "INSTRUCOES_DE_USO.md").exists()


def test_6_versao_nova():
    from central import VERSAO

    assert tuple(int(p) for p in VERSAO.split(".")) >= (1, 8, 0)     # a Planilha HM entrou na 1.8.0


def test_6_telas_so_usam_o_processamento():
    for arquivo in (PASTA_MODULO / "telas").glob("*.py"):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        usados = {no.module + "." + n.name for no in ast.walk(arvore)
                  if isinstance(no, ast.ImportFrom) and no.module and no.module.startswith("modulos")
                  for n in no.names}
        assert all(m == "modulos.planilha_hm.processamento" or m.startswith("modulos.planilha_hm.telas.")
                   for m in usados), (arquivo.name, usados)


# ---------------------------------------------------------------------------
# Apoio à tela (processamento)
# ---------------------------------------------------------------------------

def test_6_confirmacoes(entradas, tmp_path):
    (texto, status), competencia = processamento.confirmar_eventos(entradas["eventos"])
    # o Eventos fictício não tem a linha do total geral do relatório: o aviso vai junto, como atenção
    assert texto == ("Eventos · set/2026 · 5 eventos · R$ 505,00; Linha do total geral do relatório não encontrada: "
                     "a soma dos eventos não foi conferida com ela.")
    assert (status, competencia) == ("atencao", (2026, 9))
    (texto, status), competencia = processamento.confirmar_movimento(entradas["movimento"])
    assert (texto, status, competencia) == ("Movimento · set/2026 · lote 70001 · R$ 505,00", "ok", (2026, 9))
    assert processamento.confirmar_planilha(entradas["planilha"], None) == \
        ("Planilha HM · aba 2026 · nenhuma competência preenchida", "ok")
    assert processamento.confirmar_planilha(entradas["planilha"], (2026, 9))[1] == "ok"
    texto, status = processamento.confirmar_planilha(entradas["planilha"], (2027, 1))
    assert status == "erro" and "a planilha é de 2026 e o Eventos, de 2027" in texto
    assert processamento.confirmar_eventos(tmp_path / "nao.XLS")[0][1] == "erro"
    assert processamento.confirmar_movimento(tmp_path / "nao.csv")[0][1] == "erro"
    assert processamento.confirmar_planilha(tmp_path / "nao.xlsx", None)[1] == "erro"
    assert processamento.texto_meses_diferentes((2026, 9), (2026, 9)) == ""
    assert processamento.texto_meses_diferentes((2026, 9), None) == ""
    assert processamento.texto_meses_diferentes((2026, 9), (2026, 8)) == \
        "o Movimento é de ago/2026 e o Eventos, de set/2026"


def test_6_planilha_com_a_senior_do_mes_preenchida(tmp_path):
    planilha, _, _ = escrever_caso_ficticio(tmp_path, senior_com_dados={8: 2, 9: 4})
    assert processamento.confirmar_planilha(planilha, None)[0].endswith("última competência preenchida: set/2026")
    texto, status = processamento.confirmar_planilha(planilha, (2026, 9))
    assert status == "atencao" and "a aba Senior 09 2026 já tem 4 linha(s)" in texto


def test_6_evento_com_erro_nao_impede(tmp_path):
    _, eventos, _ = escrever_caso_ficticio(tmp_path, total_1002=210)
    (texto, status), _ = processamento.confirmar_eventos(eventos)
    assert status == "atencao" and texto.endswith("1 evento(s) com erro ficam fora da planilha (ex.: 1002)")


def test_6_textos_da_pergunta(entradas):
    analise = processamento.analisar(entradas["eventos"], entradas["movimento"], entradas["planilha"])
    assert analise.tabela_montada and [p.chave for p in analise.plano.perguntas] == [CONTA_NOVA]
    textos = processamento.textos_da_pergunta(analise, analise.plano.perguntas[0])
    assert textos.eventos == ["1004 · HM Exemplo Outra Conta · R$ 40,00"]
    assert textos.contas == [f"{CONTA_NOVA} · Conta Exemplo Nova PJ"]
    assert textos.opcoes == [("HONORÁRIOS MÉDICOS - FIXOS", "HONORÁRIOS MÉDICOS - FIXOS"),
                             ("HM DESCONTOS", "HM DESCONTOS"),
                             (processamento.RESPOSTA_SECAO_NOVA, "Criar seção nova: CONTA EXEMPLO NOVA PJ")]


def test_6_resumo(entradas):
    analise = processamento.analisar(entradas["eventos"], entradas["movimento"], entradas["planilha"])
    resultado = processamento.processar(analise, entradas["saida"], {CONTA_NOVA: processamento.RESPOSTA_SECAO_NOVA})
    resumo = processamento.resumir(resultado)
    assert resumo.numeros == [(5, "eventos no mês", "principal"), (7, "linhas criadas na aba do ano", "atencao"),
                              (0, "eventos fora da planilha", "ok")]
    assert resumo.linhas[0] == ("TOTAL GERAL × Movimento: diferença", "ok", "R$ 0,00")
    assert ("LOTE REPASSE gravado (a linha de baixo dá zero)", "ok", "R$ 505,00") in resumo.linhas
    assert any(t.startswith("Tabela conta → seção criada agora") and s == "atencao" for t, s, _ in resumo.linhas)
    assert [c[1] for c in resumo.criadas] == ["CC novo", "evento novo", "CC novo", "seção nova", "evento novo",
                                              "CC novo", "total da seção nova"]
    assert resumo.criadas[0][2:] == (1001, "Centro Delta", "HONORÁRIOS MÉDICOS - FIXOS")
    assert resumo.selo == ("Conferir", "atencao")


def test_6_resumo_com_diferenca(tmp_path):
    planilha, eventos, movimento = escrever_caso_ficticio(tmp_path, total_1002=210)
    analise = processamento.analisar(eventos, movimento, planilha)
    resultado = processamento.processar(analise, tmp_path, {CONTA_NOVA: "HM DESCONTOS"})
    resumo = processamento.resumir(resultado)
    assert resumo.numeros[2] == (1, "eventos fora da planilha", "erro")
    assert resumo.linhas[0] == ("TOTAL GERAL × Movimento: diferença", "erro", "R$ -200,00")
    assert any(t.startswith("Evento 1002 HM Exemplo B:") and s == "erro" for t, s, _ in resumo.linhas)
    assert resumo.selo == ("Com diferença", "erro")


# ---------------------------------------------------------------------------
# Tela
# ---------------------------------------------------------------------------

def test_6_tela_criada_com_a_aba_e_o_botao_desabilitado(tela):
    painel = tela.master
    while not hasattr(painel, "abas"):
        painel = painel.master
    assert list(painel.abas.botoes) == ["Preenchimento", "Instruções de uso"]
    assert tela.botao.cget("text") == "Preencher planilha"
    assert tela.botao.cget("state") == "disabled"


def test_6_preencher_pela_tela(tela, entradas, criar_painel):
    tela.cartao_planilha.definir_caminhos(entradas["planilha"])
    esperar(tela, lambda: tela.cartao_saida.caminho is not None)
    assert tela.cartao_saida.caminho == entradas["planilha"].parent       # sugerida: a pasta da planilha
    _escolher(tela, entradas)
    assert tela.cartao_eventos.texto_confirmacao.startswith("Eventos · set/2026 · 5 eventos · R$ 505,00")
    assert tela.botao.cget("state") == "normal"

    _processar(tela)
    resultado = tela.ultimo_resultado
    assert resultado.erro == resultado.erro_saida == "" and resultado.conferencia.ok
    assert resultado.caminho_planilha.parent == entradas["saida"] and resultado.caminho_planilha.exists()
    assert [t.eventos for t in tela.secoes_perguntadas] == [["1004 · HM Exemplo Outra Conta · R$ 40,00"]]
    assert (entradas["config"] / "secoes_contas.csv").is_file()
    assert tela.resultado.estado == "concluido" and tela.resultado.selo.cget("text") == "Conferir"
    assert set(tela.botoes_resultado) == {"Abrir planilha", "Abrir conferência", "Abrir pasta"}
    tela.botoes_resultado["Abrir conferência"].invoke()
    assert tela.abertos == [resultado.caminho_relatorio]

    assert processamento.ler_preferencias() == {"saida": str(entradas["saida"])}
    nova = criar_painel(MODULO).preenchimento                           # no mês seguinte: a saída fica lembrada
    assert nova.cartao_saida.caminho == entradas["saida"] and nova.cartao_planilha.caminho is None


def test_6_meses_diferentes_nao_acendem_o_botao(tela, tmp_path):
    planilha, eventos, movimento = escrever_caso_ficticio(tmp_path, data="31/08/2026")
    tela.cartao_eventos.definir_caminhos(eventos)
    tela.cartao_movimento.definir_caminhos(movimento)
    tela.cartao_planilha.definir_caminhos(planilha)
    esperar(tela, lambda: tela.cartao_movimento.status_confirmacao == "erro")
    assert tela.cartao_movimento.texto_confirmacao.endswith("o Movimento é de ago/2026 e o Eventos, de set/2026")
    esperar(tela, lambda: tela.cartao_planilha.status_confirmacao is not None)
    assert tela.botao.cget("state") == "disabled"

    tela.cartao_eventos.limpar_pelo_usuario()                          # sem o Eventos, o aviso do mês sai
    esperar(tela, lambda: tela.cartao_movimento.status_confirmacao == "ok")


def test_6_senior_preenchida_pergunta_antes_de_substituir(tela, tmp_path, monkeypatch):
    planilha, eventos, movimento = escrever_caso_ficticio(tmp_path, senior_com_dados={9: 4})
    saida = tmp_path / "saida"
    saida.mkdir()
    respostas = [False, True]
    monkeypatch.setattr(tela, "perguntar", lambda texto: tela.perguntas.append(texto) or respostas.pop(0))
    _escolher(tela, {"eventos": eventos, "movimento": movimento, "planilha": planilha, "saida": saida})
    assert tela.cartao_planilha.status_confirmacao == "atencao"

    _processar(tela)                                                    # responde "Não": nada é gravado
    assert "Senior 09 2026" in tela.perguntas[0] and "4 linha(s)" in tela.perguntas[0]
    assert list(saida.iterdir()) == [] and tela.ultimo_resultado is None and tela.secoes_perguntadas == []
    assert tela.resultado.estado != "concluido"

    _processar(tela)                                                    # responde "Sim"
    assert tela.ultimo_resultado.conferencia.ok and tela.ultimo_resultado.preenchimento.linhas_senior == 7


def test_6_copia_existente_pergunta_antes_de_substituir(tela, entradas, monkeypatch):
    monkeypatch.setattr(tela, "perguntar", lambda texto: tela.perguntas.append(texto) or False)
    _escolher(tela, entradas)
    analise = processamento.analisar(entradas["eventos"], entradas["movimento"], entradas["planilha"])
    from datetime import datetime

    copia = entradas["saida"] / processamento.nome_da_copia(analise, datetime.now())
    copia.write_bytes(b"antiga")
    _processar(tela)
    assert copia.name in tela.perguntas[0] and copia.read_bytes() == b"antiga"
    assert tela.ultimo_resultado is None and not entradas["config"].exists()


def test_6_cancelar_a_pergunta_da_secao_nao_grava_nada(tela, entradas, monkeypatch):
    monkeypatch.setattr(tela, "escolher_secao", lambda textos, numero, total: None)
    _escolher(tela, entradas)
    _processar(tela)
    assert list(entradas["saida"].iterdir()) == [] and not entradas["config"].exists()
    assert tela.ultimo_resultado is None and tela.resultado.estado != "concluido"


def test_6_planilha_de_outro_ano_nao_acende(tela, entradas, tmp_path):
    from testes.planilha_hm.conftest import escrever_planilha

    antiga = escrever_planilha(tmp_path / "antiga.xlsx", ano=2025)
    tela.cartao_eventos.definir_caminhos(entradas["eventos"])
    tela.cartao_movimento.definir_caminhos(entradas["movimento"])
    tela.cartao_planilha.definir_caminhos(antiga)
    tela.cartao_saida.definir_caminhos(entradas["saida"])
    esperar(tela, lambda: tela.cartao_planilha.status_confirmacao == "erro")
    assert "a planilha é de 2025 e o Eventos, de 2026" in tela.cartao_planilha.texto_confirmacao
    assert tela.botao.cget("state") == "disabled"


def test_6_leitura_antiga_da_planilha_nao_apaga_a_nova(tela, tmp_path, monkeypatch):
    """A planilha escolhida antes do Eventos é lida duas vezes (sem o mês e com o mês). Se a 1ª terminar por
    último, ela não pode apagar o aviso da aba Senior preenchida que a 2ª achou."""
    import threading
    import time

    planilha, eventos, _ = escrever_caso_ficticio(tmp_path, senior_com_dados={9: 4})
    original = processamento.confirmar_planilha
    liberar = threading.Event()
    chamadas, terminadas = [], []

    def lenta_sem_o_mes(caminho, competencia):
        chamadas.append(competencia)
        if competencia is None:
            liberar.wait(30)                                            # a 1ª leitura só termina depois da 2ª
        retorno = original(caminho, competencia)
        terminadas.append(competencia)
        return retorno

    monkeypatch.setattr(processamento, "confirmar_planilha", lenta_sem_o_mes)
    tela.cartao_planilha.definir_caminhos(planilha)
    tela.cartao_eventos.definir_caminhos(eventos)
    esperar(tela, lambda: tela.cartao_planilha.status_confirmacao == "atencao")
    liberar.set()
    esperar(tela, lambda: len(terminadas) == 2)
    fim = time.time() + 1                                               # tempo para a tela receber a 1ª leitura
    while time.time() < fim:
        tela.update()
        time.sleep(0.02)
    assert chamadas == [None, (2026, 9)]
    assert tela.cartao_planilha.status_confirmacao == "atencao"
    assert "a aba Senior 09 2026 já tem 4 linha(s)" in tela.cartao_planilha.texto_confirmacao
