"""T10 — tela do módulo Notas de Contrato (montada sem mostrar a janela).

A parte visual é conferida pelo usuário ao usar a Central; aqui ficam as regras da tela: módulo no
registro, arquitetura (tela só fala com o processamento), botões habilitados só com tudo escolhido,
o mês inteiro pela tela (Conferência -> Pendências -> E-mails, com o Gmail simulado) e as escolhas
lembradas. Todos os testes usam um %APPDATA% temporário, nunca abrem o Excel nem acessam a internet.
"""

from __future__ import annotations

import ast
import time

import pytest

from central import registro
from modulos.checklist_contratos import MODULO, processamento
from testes.checklist_contratos.conftest import escrever_checklist, escrever_movimento
from testes.checklist_contratos.test_gmail import GmailSimulado
from testes.conftest import RAIZ, esperar

PASTA_MODULO = RAIZ / "modulos" / "checklist_contratos"
TITULOS_REGRAS = "Aba;Linha;Fornecedor_Planilha;Descricao_Planilha;Contas;Busca_Fornecedor;Busca_Descricao;" \
                 "Excluir;Selecao;Tipo;Obs"


@pytest.fixture(autouse=True)
def appdata_temporario(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))


@pytest.fixture
def painel(criar_painel, monkeypatch):
    painel = criar_painel(MODULO)
    for aba in ("conferencia", "pendencias", "emails"):
        tela = getattr(painel, aba)
        tela.abertos = []
        monkeypatch.setattr(tela, "abrir", tela.abertos.append)      # nunca abre o Excel de verdade
        monkeypatch.setattr(tela, "perguntar", lambda texto: True)
        monkeypatch.setattr(tela, "informar", lambda texto: None)
    return painel


@pytest.fixture
def mes_ficticio(tmp_path):
    """Um mês fictício: Alfa achada (OK), Beta não chegou, Gama na conta errada (CMD)."""
    base = tmp_path / "mes"
    for pasta in ("sc", "cmd", "config", "saida"):
        (base / pasta).mkdir(parents=True)
    escrever_movimento(base / "sc" / "Movimento contábil (1).csv", [
        {"Complemento": "Fornecedor Alfa NF 10", "Conta contábil": "30091", "Valor": "100,00",
         "Data movimento": "05/10/2026"}])
    escrever_movimento(base / "cmd" / "Movimento contábil (1).csv", [
        {"Complemento": "Fornecedor Gama NF 20", "Conta contábil": "30999", "Valor": "50,00",
         "Data movimento": "06/10/2026"}])
    sc = [[30091, "Conta", None, "Fornecedor Alfa", 100, "Licença", "1 - Ana"] + [None] * 10,
          [30092, "Conta", None, "Fornecedor Beta", 100, "Suporte", "2 - Bruno"] + [None] * 10]
    cmd = [[30130, "Conta", "Fornecedor Gama", 50, "Energia", "1 - Ana"] + [None] * 9]
    checklist = escrever_checklist(base / "Check list 2026.xlsx", linhas_sc=sc, linhas_cmd=cmd, emails=[
        ("Ana Exemplo <ana@exemplo.org.br>", "1"), ("Bruno Exemplo <bruno@exemplo.org.br>", "2"),
        ("Contabilidade <contabil@exemplo.org.br>", "Todos")])
    (base / "config" / "regras.csv").write_text("\n".join([
        TITULOS_REGRAS,
        "SC;2;Fornecedor Alfa;Licença;30091;^fornecedor alfa;;;;auto;",
        "SC;3;Fornecedor Beta;Suporte;30092;^fornecedor beta;;;;auto;",
        "CMD;2;Fornecedor Gama;Energia;30130;^fornecedor gama;;;;auto;"]) + "\n", encoding="utf-8-sig")
    return {"sc": base / "sc", "cmd": base / "cmd", "checklist": checklist, "config": base / "config",
            "saida": base / "saida"}


def _confirmacao(tela, cartao):
    esperar(tela, lambda: cartao.status_confirmacao is not None)
    return cartao.texto_confirmacao, cartao.status_confirmacao


# ---------------------------------------------------------------------------
# Módulo e arquitetura
# ---------------------------------------------------------------------------

def test_t10_modulo_no_registro_na_secao_fiscal():
    assert registro.SECAO_DO_MODULO["checklist_contratos"] == "FISCAL"
    carregado = next(m for m in registro.carregar_modulos() if m.chave == "checklist_contratos")
    assert carregado.ok and carregado.info.nome == "Notas Check-list"
    assert carregado.info.icone == "prancheta"
    assert (RAIZ / "central" / "icones" / "prancheta.png").exists()
    assert (PASTA_MODULO / "INSTRUCOES_DE_USO.md").exists()


def test_t10_telas_so_usam_o_processamento():
    for arquivo in (PASTA_MODULO / "telas").glob("*.py"):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        usados = {no.module + "." + n.name for no in ast.walk(arvore)
                  if isinstance(no, ast.ImportFrom) and no.module and no.module.startswith("modulos")
                  for n in no.names}
        assert usados <= {"modulos.checklist_contratos.processamento"}, arquivo.name


def test_t10_logica_nao_importa_customtkinter_nem_outro_modulo():
    for arquivo in PASTA_MODULO.glob("*.py"):
        if arquivo.name == "painel.py":
            continue
        for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
            nomes = [a.name for a in no.names] if isinstance(no, ast.Import) else \
                [no.module or ""] if isinstance(no, ast.ImportFrom) else []
            for nome in nomes:
                assert not nome.startswith("customtkinter"), arquivo.name
                assert not nome.startswith("modulos.") or nome.startswith("modulos.checklist_contratos"), \
                    (arquivo.name, nome)


# ---------------------------------------------------------------------------
# Tela
# ---------------------------------------------------------------------------

def test_t10_tela_criada_com_as_abas_e_botoes_desabilitados(painel):
    assert painel.abas.atual == "Conferência"
    assert list(painel.abas.botoes) == ["Conferência", "Pendências", "E-mails", "Instruções de uso"]
    assert painel.conferencia.botao.cget("text") == "Conferir mês"
    for tela in (painel.conferencia, painel.pendencias, painel.emails):
        assert tela.botao.cget("state") == "disabled"
    assert painel.emails.campo_remetente.valor() == "contabilidade@hospitalexemplo.com.br"


def test_t10_mes_invalido_nao_habilita(painel, mes_ficticio):
    tela = painel.conferencia
    for cartao, chave in ((tela.cartao_sc, "sc"), (tela.cartao_cmd, "cmd"), (tela.cartao_checklist, "checklist"),
                          (tela.cartao_configuracao, "config"), (tela.cartao_saida, "saida")):
        cartao.definir_caminhos(mes_ficticio[chave])
    tela.campo_mes.definir("13/2026")
    assert tela.botao.cget("state") == "disabled"
    tela.campo_mes.definir("10/2026")
    assert tela.botao.cget("state") == "normal"


def test_t10_o_mes_inteiro_pela_tela(painel, mes_ficticio, monkeypatch):
    conferencia = painel.conferencia
    conferencia.campo_mes.definir("10/2026")
    for cartao, chave in ((conferencia.cartao_sc, "sc"), (conferencia.cartao_cmd, "cmd"),
                          (conferencia.cartao_checklist, "checklist"), (conferencia.cartao_configuracao, "config"),
                          (conferencia.cartao_saida, "saida")):
        cartao.definir_caminhos(mes_ficticio[chave])
    assert _confirmacao(conferencia, conferencia.cartao_sc) == ("1 lançamento(s) de débito", "ok")
    assert not conferencia.cartao_sc.carregando                         # a barrinha some ao terminar
    assert _confirmacao(conferencia, conferencia.cartao_checklist) == (
        "2 linhas Hospital Exemplo, 1 CMD, 3 contatos", "ok")
    assert _confirmacao(conferencia, conferencia.cartao_configuracao) == ("3 regra(s)", "ok")

    # 1. Conferência
    conferencia.processar()
    esperar(conferencia, lambda: not conferencia.ocupado)
    resultado = conferencia.ultimo_resultado
    assert resultado.erro == "" and resultado.preenchidas == 1
    assert conferencia.resultado.estado == "concluido"
    assert conferencia.resultado.selo.cget("text") == "Conferir"           # há conta divergente
    assert set(conferencia.botoes_resultado) == {"Abrir relatório", "Abrir cópia", "Abrir pasta"}
    conferencia.botoes_resultado["Abrir cópia"].invoke()
    assert conferencia.abertos == [resultado.caminho_copia]

    # o relatório novo já vai para a aba Pendências, com o mês
    pendencias = painel.pendencias
    assert pendencias.cartao_relatorio.caminho == resultado.caminho_relatorio
    assert pendencias.campo_mes.valor() == "10/2026"

    # 2. Pendências (o Check list da rede ainda sem o valor da Alfa: ela também aparece)
    pendencias.cartao_checklist.definir_caminhos(mes_ficticio["checklist"])
    pendencias.cartao_saida.definir_caminhos(mes_ficticio["saida"])
    _confirmacao(pendencias, pendencias.cartao_checklist)
    assert pendencias.botao.cget("state") == "normal"
    pendencias.processar()
    esperar(pendencias, lambda: not pendencias.ocupado)
    gerado = pendencias.ultimo_resultado
    assert gerado.erro == "" and gerado.pendencias.notas == 2               # Gama (divergente) fica fora
    assert [e.responsavel for e in gerado.pendencias.emails] == ["Ana", "Bruno"]
    assert set(pendencias.botoes_resultado) == {"Abrir prévia", "Texto Claude", "Abrir pasta"}
    pendencias.botoes_resultado["Texto Claude"].invoke()
    assert pendencias.abertos == [gerado.caminho_texto] and gerado.caminho_texto.exists()

    # 3. E-mails: sem credencial o botão fica apagado; com ela, rascunhos no Gmail simulado
    painel.mostrar_aba("E-mails")
    emails = painel.emails
    assert emails.resultado.estado == "concluido"                           # a lista dos e-mails
    assert emails.botao.cget("state") == "disabled"
    credenciais = mes_ficticio["config"] / "credentials.json"
    credenciais.write_text('{"installed": {"client_id": "simulado"}}', encoding="utf-8")
    emails.cartao_credenciais.definir_caminhos(credenciais)
    assert _confirmacao(emails, emails.cartao_credenciais)[1] == "ok"
    emails.campo_remetente.definir("contabil@exemplo.org.br")
    assert emails.botao.cget("state") == "normal"

    simulado = GmailSimulado()
    original = processamento.criar_rascunhos
    monkeypatch.setattr(processamento, "criar_rascunhos",
                        lambda *args: original(*args, cliente=simulado))
    emails.processar()
    esperar(emails, lambda: not emails.ocupado)
    assert emails.ultimo_resultado.criados == 2 and len(simulado.rascunhos) == 2
    assert emails.resultado.selo.cget("text") == "Concluído"
    assert emails.ultimo_resultado.caminho_registro.parent == mes_ficticio["saida"]
    assert set(emails.botoes_resultado) == {"Abrir registro", "Abrir pasta", "Trocar conta"}

    # tudo lembrado para o dia seguinte
    lembrado = processamento.ler_preferencias()
    assert lembrado["checklist"] == str(mes_ficticio["checklist"]) and lembrado["mes"] == "10/2026"
    assert lembrado["remetente"] == "contabil@exemplo.org.br" and lembrado["credenciais"] == str(credenciais)


def test_t10_erro_de_leitura_aparece_na_tela(painel, mes_ficticio):
    tela = painel.conferencia
    tela.campo_mes.definir("11/2026")                                      # o Check list não tem nov/26
    for cartao, chave in ((tela.cartao_sc, "sc"), (tela.cartao_cmd, "cmd"), (tela.cartao_checklist, "checklist"),
                          (tela.cartao_configuracao, "config"), (tela.cartao_saida, "saida")):
        cartao.definir_caminhos(mes_ficticio[chave])
    tela.processar()
    esperar(tela, lambda: not tela.ocupado)
    assert tela.resultado.selo.cget("text") == "Erro"


def test_t10_abre_com_as_escolhas_lembradas_sem_esperar_a_rede(criar_painel, mes_ficticio, tmp_path):
    processamento.salvar_preferencias(movimento_sc=mes_ficticio["sc"], checklist=tmp_path / "nao_existe.xlsx",
                                      saida=mes_ficticio["saida"], mes="10/2026")
    inicio = time.perf_counter()
    painel = criar_painel(MODULO)
    tela = painel.conferencia
    assert time.perf_counter() - inicio < 5
    assert tela.campo_mes.valor() == "10/2026" and tela.pasta_saida == mes_ficticio["saida"]
    assert tela.cartao_checklist.caminho == tmp_path / "nao_existe.xlsx"    # preenchido na hora...
    assert _confirmacao(tela, tela.cartao_checklist)[1] == "erro"          # ...conferido em segundo plano
    assert _confirmacao(tela, tela.cartao_sc) == ("1 lançamento(s) de débito", "ok")


def test_t10_pasta_config_ao_lado_do_check_list_entra_sozinha(painel, mes_ficticio, tmp_path):
    tela = painel.conferencia
    tela.campo_mes.definir("10/2026")
    tela.cartao_checklist.definir_caminhos(mes_ficticio["checklist"])        # tem a pasta "config" ao lado
    assert tela.cartao_checklist.carregando                             # lendo: a barrinha aparece
    esperar(tela, lambda: tela.cartao_configuracao.caminho is not None)
    assert tela.cartao_configuracao.caminho == mes_ficticio["config"]
    assert _confirmacao(tela, tela.cartao_configuracao) == ("3 regra(s)", "ok")

    # a escolha do usuário é respeitada: trocar o Check list não troca a pasta escolhida à mão
    outra = tmp_path / "minhas regras"
    outra.mkdir()
    (outra / "regras.csv").write_text(TITULOS_REGRAS + "\n", encoding="utf-8-sig")
    tela.cartao_configuracao.definir_caminhos(outra)
    tela.cartao_checklist.definir_caminhos(mes_ficticio["checklist"])
    esperar(tela, lambda: tela.cartao_checklist.status_confirmacao is not None)
    assert tela.cartao_configuracao.caminho == outra


def test_t10_regras_na_propria_pasta_do_check_list(painel, tmp_path):
    tela = painel.conferencia
    (tmp_path / "sozinho").mkdir()
    checklist = escrever_checklist(tmp_path / "sozinho" / "Check list 2026.xlsx")
    assert processamento.pasta_configuracao_sugerida(checklist) is None
    (tmp_path / "sozinho" / "regras.csv").write_text(TITULOS_REGRAS + "\n", encoding="utf-8-sig")
    assert processamento.pasta_configuracao_sugerida(checklist) == tmp_path / "sozinho"   # na própria pasta
    tela.cartao_checklist.definir_caminhos(checklist)
    esperar(tela, lambda: tela.cartao_configuracao.caminho is not None)
    assert tela.cartao_configuracao.caminho == tmp_path / "sozinho"
