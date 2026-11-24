"""N7 — tela do módulo Notas Pendentes (montada sem mostrar a janela) e o apoio à tela no processamento.

A parte visual é conferida pelo usuário ao usar a Central; aqui ficam as regras da tela: módulo no registro,
arquitetura (tela só fala com o processamento), botão só com tudo escolhido, sugestões (prazo, pasta do mês,
modelo) e as escolhas lembradas. Todos os testes usam um %APPDATA% temporário e nunca abrem nada no Windows.
"""

from __future__ import annotations

import ast

import pytest

from central import registro
from modulos.notas_pendentes import MODULO, processamento
from testes.conftest import RAIZ, esperar
from testes.notas_pendentes.conftest import CHAVE_FICTICIA, criar_pdf, escrever_checklist

PASTA_MODULO = RAIZ / "modulos" / "notas_pendentes"


@pytest.fixture(autouse=True)
def appdata_temporario(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))


@pytest.fixture
def entradas(tmp_path):
    """HOSPITAL EXEMPLO\\102026 (3 PDFs), HOSPITAL EXEMPLO\\112026 (1 PDF), config\\modelo_email.txt, Check list e saída."""
    base = tmp_path / "HOSPITAL EXEMPLO"
    criar_pdf(base / "102026", f"1.DANFSe-10-Alfa Exemplo Ltda-{CHAVE_FICTICIA}.pdf")
    criar_pdf(base / "102026", f"2.DANFSe-20-Beta Exemplo Ltda-{CHAVE_FICTICIA}.pdf")
    criar_pdf(base / "102026", f"9.DANFSe-30-Gama Exemplo Ltda-{CHAVE_FICTICIA}.pdf")
    criar_pdf(base / "112026", f"1.DANFSe-11-Alfa Exemplo Ltda-{CHAVE_FICTICIA}.pdf")
    (base / "config").mkdir()
    (base / "config" / "modelo_email.txt").write_text(
        "Assunto: Pendências {competencia}\n\nRegistrar até {prazo}:\n{lista_notas}\n", encoding="utf-8")
    checklist = escrever_checklist(tmp_path / "Check list 2026.xlsx", emails=[
        ("Ana Exemplo <ana@exemplo.org.br>", "1"), ("Bruno Exemplo <bruno@exemplo.org.br>", "2"),
        ("Contabilidade <contabil@exemplo.org.br>", "Todos")])
    saida = tmp_path / "saida"
    saida.mkdir()
    return {"outubro": base / "102026", "novembro": base / "112026", "modelo": base / "config" / "modelo_email.txt",
            "checklist": checklist, "saida": saida}


@pytest.fixture
def tela(criar_painel, monkeypatch):
    painel = criar_painel(MODULO)
    tela = painel.gerar
    tela.abertos = []
    monkeypatch.setattr(tela, "abrir", tela.abertos.append)          # nunca abre nada de verdade
    return tela


def _confirmacao(tela, cartao):
    esperar(tela, lambda: cartao.status_confirmacao is not None)
    return cartao.texto_confirmacao, cartao.status_confirmacao


# ---------------------------------------------------------------------------
# Módulo e arquitetura
# ---------------------------------------------------------------------------

def test_n7_modulo_no_registro_na_secao_fiscal():
    assert registro.SECAO_DO_MODULO["notas_pendentes"] == "FISCAL"
    assert registro.SECOES[0][1].index("notas_pendentes") == registro.SECOES[0][1].index("checklist_contratos") + 1
    carregado = next(m for m in registro.carregar_modulos() if m.chave == "notas_pendentes")
    assert carregado.ok and carregado.info.nome == "Notas Pendentes"
    assert carregado.info.icone == "envelope"
    assert (RAIZ / "central" / "icones" / "envelope.png").exists()
    assert (PASTA_MODULO / "INSTRUCOES_DE_USO.md").exists()


def test_n7_telas_so_usam_o_processamento():
    for arquivo in (PASTA_MODULO / "telas").glob("*.py"):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        usados = {no.module + "." + n.name for no in ast.walk(arvore)
                  if isinstance(no, ast.ImportFrom) and no.module and no.module.startswith("modulos")
                  for n in no.names}
        assert usados <= {"modulos.notas_pendentes.processamento"}, arquivo.name


# ---------------------------------------------------------------------------
# Apoio à tela (processamento)
# ---------------------------------------------------------------------------

def test_prazo_sugerido():
    assert processamento.prazo_sugerido("29/10/2026", 2026, 11) == "29/11/2026"
    assert processamento.prazo_sugerido("31/10/2026", 2026, 11) == "30/11/2026"     # novembro não tem 31
    assert processamento.prazo_sugerido("29/01/2027", 2027, 2) == "28/02/2027"
    assert processamento.prazo_sugerido("", 2026, 11) == ""


def test_pasta_do_mes(entradas, tmp_path):
    assert processamento.pasta_do_mes(entradas["outubro"], 2026, 11) == entradas["novembro"]
    assert processamento.pasta_do_mes(entradas["outubro"], 2026, 12) is None          # ainda não existe
    assert processamento.pasta_do_mes(entradas["outubro"], 2026, 10) is None          # já é ela
    assert processamento.pasta_do_mes(tmp_path / "outra pasta", 2026, 11) is None     # nome fora do padrão


def test_confirmacoes(entradas, tmp_path):
    assert processamento.confirmar_pasta_notas(entradas["outubro"]) == ("3 PDF(s) de 3 responsável(is)", "ok")
    criar_pdf(tmp_path / "mista", "Nota sem numero.pdf")
    assert processamento.confirmar_pasta_notas(tmp_path / "mista")[1] == "atencao"
    assert processamento.confirmar_pasta_notas(tmp_path / "nao")[1] == "erro"
    assert processamento.confirmar_checklist(entradas["checklist"]) == ("3 contato(s) na aba Emails", "ok")
    assert processamento.confirmar_modelo(entradas["modelo"]) == ("Assunto: Pendências {competencia}", "ok")
    errado = tmp_path / "errado.txt"
    errado.write_text("Assunto: x {mes}\n\ny", encoding="utf-8")
    assert processamento.confirmar_modelo(errado)[1] == "erro"


# ---------------------------------------------------------------------------
# Tela
# ---------------------------------------------------------------------------

def test_n7_tela_criada_com_a_aba_e_o_botao_desabilitado(tela):
    painel = tela.master
    while not hasattr(painel, "abas"):
        painel = painel.master
    assert list(painel.abas.botoes) == ["E-mails", "Instruções de uso"]
    assert tela.botao.cget("text") == "Gerar e-mails"
    assert tela.botao.cget("state") == "disabled"


def test_n7_campos_invalidos_nao_habilitam(tela, entradas):
    tela.cartao_pasta.definir_caminhos(entradas["outubro"])
    tela.cartao_checklist.definir_caminhos(entradas["checklist"])
    tela.cartao_saida.definir_caminhos(entradas["saida"])
    tela.campo_competencia.definir("13/2026")
    tela.campo_prazo.definir("31/11/2026")
    assert tela.botao.cget("state") == "disabled"
    assert "Competência inválida" in tela.aviso_campos.cget("text")
    assert "Prazo inválido" in tela.aviso_campos.cget("text")
    tela.campo_competencia.definir("10/2026")
    tela.campo_prazo.definir("29/10/2026")
    assert tela.aviso_campos.cget("text") == ""
    assert tela.botao.cget("state") == "normal"


def test_n7_o_mes_pela_tela(tela, entradas, criar_painel):
    tela.campo_competencia.definir("10/2026")
    tela.campo_prazo.definir("29/10/2026")
    tela.cartao_pasta.definir_caminhos(entradas["outubro"])
    tela.cartao_checklist.definir_caminhos(entradas["checklist"])
    tela.cartao_saida.definir_caminhos(entradas["saida"])
    assert _confirmacao(tela, tela.cartao_pasta) == ("3 PDF(s) de 3 responsável(is)", "ok")
    assert _confirmacao(tela, tela.cartao_checklist) == ("3 contato(s) na aba Emails", "ok")
    # o modelo da pasta config entra sozinho
    esperar(tela, lambda: tela.cartao_modelo.caminho == entradas["modelo"])
    assert _confirmacao(tela, tela.cartao_modelo)[1] == "ok"

    tela.processar()
    esperar(tela, lambda: not tela.ocupado)
    resultado = tela.ultimo_resultado
    assert resultado.erro == "" and [e.numero for e in resultado.emails.emails] == ["1", "2"]
    assert resultado.emails.emails[0].assunto == "Pendências 10/2026"
    assert tela.resultado.estado == "concluido"
    assert tela.resultado.selo.cget("text") == "Conferir"                  # o número 9 ficou sem e-mail
    assert set(tela.botoes_resultado) == {"Abrir prévia", "Texto Claude", "Abrir relatório", "Abrir pasta"}
    tela.botoes_resultado["Abrir prévia"].invoke()
    assert tela.abertos == [resultado.caminho_previa] and resultado.caminho_previa.exists()
    tela.botoes_resultado["Texto Claude"].invoke()
    assert tela.abertos[-1] == resultado.caminho_texto and resultado.caminho_texto.exists()

    # tudo lembrado para o mês seguinte
    lembrado = processamento.ler_preferencias()
    assert lembrado["competencia"] == "10/2026" and lembrado["prazo"] == "29/10/2026"
    assert lembrado["pasta_notas"] == str(entradas["outubro"]) and lembrado["modelo"] == str(entradas["modelo"])

    # no mês seguinte: a tela abre com tudo e, ao trocar a competência, sugere o prazo e a pasta de novembro
    nova = criar_painel(MODULO).gerar
    assert nova.cartao_pasta.caminho == entradas["outubro"] and nova.campo_prazo.valor() == "29/10/2026"
    nova.campo_competencia.definir("11/2026")
    assert nova.campo_prazo.valor() == "29/11/2026"
    esperar(nova, lambda: nova.cartao_pasta.caminho == entradas["novembro"])
    assert _confirmacao(nova, nova.cartao_pasta) == ("1 PDF(s) de 1 responsável(is)", "ok")


def test_n7_prazo_digitado_a_mao_nao_e_trocado(tela, entradas):
    processamento.salvar_preferencias(prazo="29/10/2026")
    tela.lembrado = processamento.ler_preferencias()
    tela.campo_competencia.definir("11/2026")
    assert tela.campo_prazo.valor() == "29/11/2026"
    tela.campo_prazo.definir("05/12/2026")                               # o usuário corrigiu
    tela.campo_competencia.definir("12/2026")
    assert tela.campo_prazo.valor() == "05/12/2026"


def test_n7_modelo_escolhido_a_mao_nunca_e_trocado(tela, entradas, tmp_path):
    proprio = tmp_path / "meu_modelo.txt"
    proprio.write_text("Assunto: Meu {competencia}\n\nTexto {prazo} {lista_notas}", encoding="utf-8")
    tela.cartao_modelo.definir_caminhos(proprio)
    tela.cartao_pasta.definir_caminhos(entradas["outubro"])
    _confirmacao(tela, tela.cartao_pasta)
    for _ in range(20):
        tela.update()
    assert tela.cartao_modelo.caminho == proprio


def test_n7_modelo_com_erro_nao_habilita(tela, entradas, tmp_path):
    errado = tmp_path / "errado.txt"
    errado.write_text("Assunto: x {mes}\n\ny", encoding="utf-8")
    tela.campo_competencia.definir("10/2026")
    tela.campo_prazo.definir("29/10/2026")
    for cartao, chave in ((tela.cartao_pasta, "outubro"), (tela.cartao_checklist, "checklist"),
                          (tela.cartao_saida, "saida")):
        cartao.definir_caminhos(entradas[chave])
    tela.cartao_modelo.definir_caminhos(errado)
    assert _confirmacao(tela, tela.cartao_modelo)[1] == "erro"
    assert tela.botao.cget("state") == "disabled"


def test_n7_erro_de_leitura_aparece_na_tela(tela, entradas, tmp_path):
    tela.campo_competencia.definir("10/2026")
    tela.campo_prazo.definir("29/10/2026")
    tela.cartao_pasta.definir_caminhos(entradas["outubro"])
    tela.cartao_checklist.definir_caminhos(tmp_path / "nao_existe.xlsx")
    tela.cartao_saida.definir_caminhos(entradas["saida"])
    tela.processar()
    esperar(tela, lambda: not tela.ocupado)
    assert "Arquivo não encontrado" in tela.ultimo_resultado.erro
    assert tela.resultado.selo.cget("text") == "Erro"
