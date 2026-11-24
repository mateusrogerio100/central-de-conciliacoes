"""E8 — tela do módulo Estoque (aba "Conciliação", um botão por etapa).

A parte visual é conferida pelo usuário ao usar a Central; aqui ficam as regras da tela:
botões habilitados conforme os arquivos de cada etapa, mês lido dos arquivos, perguntas antes
de seguir e as três etapas de setembro. Todos os testes usam um %APPDATA% temporário (a
configuração do usuário nunca é tocada) e nunca abrem o Excel.
"""

from __future__ import annotations

import ast

import pytest

from modulos.conciliacao_estoque import MODULO
from modulos.conciliacao_estoque.modelos import MesReferencia
from testes.conciliacao_estoque.conftest import arquivo_exemplo
from testes.conftest import RAIZ, esperar

BALANCETE = "Balancete_estoque_completo.xls"
SCF = "SCF - Movimento Estoque (Contabilidade).xls"
PDF = "Movimento_estoque_PDF.pdf"


@pytest.fixture(autouse=True)
def appdata_temporario(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))


@pytest.fixture
def painel(criar_painel, monkeypatch):
    tela = criar_painel(MODULO).conciliacao
    tela.abertos = []
    monkeypatch.setattr(tela, "abrir", tela.abertos.append)        # nunca abre o Excel/Explorer de verdade
    esperar(tela, lambda: tela.status_configuracao is not None)
    return tela


def _escolher(painel, saida, mes="09/2026", balancete=True, scf=True, pdf=True):
    if balancete:
        painel.cartao_balancete.definir_caminhos(arquivo_exemplo(BALANCETE), avisar=False)
    if scf:
        painel.cartao_scf.definir_caminhos(arquivo_exemplo(SCF), avisar=False)
    if pdf:
        painel.cartao_pdf.definir_caminhos(arquivo_exemplo(PDF), avisar=False)
    painel.cartao_saida.definir_caminhos(saida, avisar=False)
    painel.campo_mes.definir(mes)
    painel.atualizar_botoes()


def _habilitados(painel):
    return [id_etapa for id_etapa, botao in painel.botoes_etapa.items() if botao.habilitado]


def test_tela_so_usa_processamento_e_resumo():
    """A tela não tem regra de negócio: não importa leitores, comparação nem relatórios."""
    arvore = ast.parse((RAIZ / "modulos" / "conciliacao_estoque" / "telas" / "conciliacao.py").read_text(encoding="utf-8"))
    usados = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.ImportFrom) and no.module and no.module.startswith("modulos"):
            if no.module == "modulos.conciliacao_estoque":
                usados.update(f"{no.module}.{n.name}" for n in no.names)
            else:
                usados.add(no.module)
    assert usados <= {"modulos.conciliacao_estoque.processamento", "modulos.conciliacao_estoque.resumo_tela"}


def test_modulo_no_menu():
    from central import registro

    assert "conciliacao_estoque" in registro.NOMES_MODULOS
    assert (MODULO.nome, MODULO.icone) == ("Estoque", "caixa")


def test_um_botao_por_etapa(painel):
    assert [b.cget("text") for b in painel.botoes_etapa.values()] == [
        "EST-01 · Conciliação saldo anterior estoque",
        "EST-02 · Conciliação contas estoque",
        "EST-03 · Conciliação saldo atual estoque",
    ]
    assert _habilitados(painel) == []
    assert painel.botao.winfo_manager() == ""                      # o botão único da base fica escondido


def test_cada_botao_so_pede_o_que_usa(painel, tmp_path):
    _escolher(painel, tmp_path, balancete=False, pdf=False)
    assert _habilitados(painel) == []                              # só o SCF: nenhuma etapa completa
    _escolher(painel, tmp_path, balancete=False)
    assert _habilitados(painel) == ["EST-02"]                      # SCF + PDF
    _escolher(painel, tmp_path)
    assert _habilitados(painel) == ["EST-01", "EST-02", "EST-03"]
    painel.cartao_pdf.limpar()
    painel.atualizar_botoes()
    assert _habilitados(painel) == ["EST-01", "EST-03"]


def test_validacao(painel, tmp_path):
    erro, mes = painel.validar("EST-02")
    assert "EST-02" in erro and "Mapa do Estoque" in erro and "PDF" in erro and "Balancete" not in erro and mes is None
    _escolher(painel, tmp_path, mes="13/2026")
    assert "MM/AAAA" in painel.validar("EST-01")[0]
    painel.campo_mes.definir("09/2026")
    assert painel.validar("EST-03") == (None, MesReferencia(2026, 9))


def test_configuracao_de_fabrica_na_tela(painel):
    assert painel.status_configuracao == "ok"
    assert "de fábrica, 62 operações" in painel.rotulo_configuracao.cget("text")


def test_editar_configuracao_cria_a_copia_e_abre(painel, dialogos, tmp_path):
    painel.editar_configuracao()
    esperado = tmp_path / "appdata" / "CentralConciliacoes" / "configuracoes" / "Configuracao_EST-02_Itens_mapa_estoque.xlsx"
    assert painel.abertos == [esperado] and esperado.is_file()
    assert "salve e feche" in dialogos.informacoes[0]
    esperar(painel, lambda: "sua (editada)" in painel.rotulo_configuracao.cget("text"))


def test_meses_lidos_ao_escolher(painel):
    painel.cartao_scf.definir_caminhos(arquivo_exemplo(SCF))         # como se o usuário escolhesse
    esperar(painel, lambda: "scf" in painel._meses)
    assert painel.campo_mes.valor() == "09/2026"                     # sem balancete, vale o mês do SCF
    painel.cartao_balancete.definir_caminhos(arquivo_exemplo(BALANCETE))
    painel.cartao_pdf.definir_caminhos(arquivo_exemplo(PDF))
    esperar(painel, lambda: len(painel._meses) == 3)
    for cartao in (painel.cartao_balancete, painel.cartao_scf, painel.cartao_pdf):
        assert (cartao.texto_confirmacao, cartao.status_confirmacao) == ("Mês de referência 09/2026", "ok")
    assert painel.pasta_saida == arquivo_exemplo(SCF).parent


@pytest.mark.parametrize("id_etapa, arquivo", [
    ("EST-01", "EST-01 Conciliação saldo anterior estoque 09-2026.xlsx"),
    ("EST-02", "EST-02 Conciliação contas estoque 09-2026.xlsx"),
    ("EST-03", "EST-03 Conciliação saldo atual estoque 09-2026.xlsx"),
])
def test_cada_etapa_pela_tela(painel, dialogos, tmp_path, id_etapa, arquivo):
    _escolher(painel, tmp_path)
    painel.botoes_etapa[id_etapa].invoke()
    assert painel.ocupado and _habilitados(painel) == []
    esperar(painel, lambda: painel.ultimo_resultado is not None)

    assert [p.name for p in tmp_path.glob("*.xlsx")] == [arquivo]
    assert dialogos.perguntas == []
    assert painel.resultado.estado == "concluido" and len(_habilitados(painel)) == 3
    assert painel.resultado.selo.cget("text") == "Concluído"

    painel.botoes_resultado["Abrir Excel"].invoke()
    painel.botoes_resultado["Abrir pasta"].invoke()
    assert painel.abertos == [tmp_path / arquivo, str(tmp_path)]


def test_novo_limpa_as_escolhas(painel, tmp_path):
    _escolher(painel, tmp_path)
    painel.novo()
    assert not painel.cartao_balancete.preenchido and painel.campo_mes.valor() == ""
    assert painel.cartao_saida.preenchido                             # a pasta de saída fica
    assert _habilitados(painel) == []


def test_etapa_que_falha_mostra_o_motivo(painel, dialogos, tmp_path):
    falso = tmp_path / "falso.pdf"
    falso.write_bytes(b"nao e pdf")
    _escolher(painel, tmp_path)
    painel.cartao_pdf.definir_caminhos(falso, avisar=False)
    painel.botoes_etapa["EST-02"].invoke()
    esperar(painel, lambda: painel.ultimo_resultado is not None)
    assert painel.resultado.selo.cget("text") == "Erro"
    assert list(tmp_path.glob("*.xlsx")) == []


def test_mes_informado_diferente_pergunta(painel, dialogos, tmp_path):
    _escolher(painel, tmp_path, mes="10/2026")
    dialogos.resposta = False
    painel.botoes_etapa["EST-03"].invoke()
    esperar(painel, lambda: dialogos.perguntas and not painel.ocupado)
    assert "Os meses não batem" in dialogos.perguntas[0]
    assert list(tmp_path.glob("*.xlsx")) == []
    assert painel.resultado.estado == "vazio"


def test_pergunta_antes_de_substituir(painel, dialogos, tmp_path):
    existente = tmp_path / "EST-02 Conciliação contas estoque 09-2026.xlsx"
    existente.write_bytes(b"antigo")
    _escolher(painel, tmp_path)
    dialogos.resposta = False
    painel.botoes_etapa["EST-02"].invoke()
    esperar(painel, lambda: dialogos.perguntas and not painel.ocupado)
    assert "já existem" in dialogos.perguntas[0]
    assert existente.read_bytes() == b"antigo"
