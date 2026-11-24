"""Testes da base comum dos painéis e do registro real dos módulos."""

from __future__ import annotations

import ast

import pytest
from PIL import Image

from central import painel_base, registro
from central.caminhos import caminho_interno
from central.janela import JanelaCentral

from testes.conftest import RAIZ, abrir_janela_ctk


# Regra do "Salvar em" (veio da janela da Conciliação Bancária original)
@pytest.mark.parametrize("atual, automatica, pasta_arquivo, esperado", [
    ("", "", r"C:\julho", r"C:\julho"),                          # vazio: preenche
    (r"C:\julho", r"C:\julho", r"C:\agosto", r"C:\agosto"),       # ainda automático: acompanha
    (r"C:\minha", r"C:\julho", r"C:\agosto", r"C:\minha"),        # trocado pelo usuário: mantém
    ("   ", r"C:\julho", r"C:\agosto", r"C:\agosto"),             # só espaços = vazio
])
def test_pasta_saida_sugerida(atual, automatica, pasta_arquivo, esperado):
    assert painel_base.pasta_saida_sugerida(atual, automatica, pasta_arquivo) == esperado


def test_icone_do_programa_tem_varios_tamanhos():
    icone = caminho_interno("recursos", "icone.ico")
    with Image.open(icone) as imagem:
        tamanhos = imagem.info["sizes"]
    assert (16, 16) in tamanhos and (256, 256) in tamanhos


@pytest.mark.parametrize("erro, trecho", [
    (PermissionError(13, "Permission denied", r"C:\saida\Avisos_08-2026.xlsx"), "Avisos_08-2026.xlsx"),
    (PermissionError(13, "Permission denied", r"C:\saida\x.xlsx"), "aberto no Excel"),
    (FileNotFoundError(2, "No such file", r"C:\e\Balancete.xlsx"), "Balancete.xlsx"),
    (ValueError("nenhum arquivo .xlsx encontrado em: C:\\x"), "Nenhum arquivo .xlsx"),
    (KeyError("coluna"), "Erro inesperado"),
])
def test_mensagem_amigavel(erro, trecho):
    assert trecho in painel_base.mensagem_amigavel(erro)


def test_erro_dos_modulos_vem_com_mensagem_pronta():
    class ErroConciliacao(Exception):
        pass

    assert painel_base.mensagem_amigavel(ErroConciliacao("balancete não encontrado: x")) == \
        "Balancete não encontrado: x"


def test_formatacao():
    assert painel_base.formatar_reais(1234567.8) == "1.234.567,80"
    assert painel_base.formatar_inteiro(6664) == "6.664"


def test_abrir_arquivo_inexistente_devolve_mensagem(tmp_path):
    assert "Não encontrei" in painel_base.abrir_no_windows(tmp_path / "nao_existe.xlsx")


def test_registro_real_tem_os_modulos_na_ordem_do_menu():
    carregados = registro.carregar_modulos()
    assert [(m.secao, m.chave) for m in carregados] == [
        ("FISCAL", "conferencia_nf"), ("FISCAL", "checklist_contratos"), ("FISCAL", "notas_pendentes"),
        ("FISCAL", "escrituracao_tomados"),
        ("FISCAL", "conferencia_iss"), ("FISCAL", "efd_contribuicoes"),
        ("CONCILIAÇÕES · ATIVO", "bancos"), ("CONCILIAÇÕES · ATIVO", "clientes_cmd"),
        ("CONCILIAÇÕES · ATIVO", "conciliacao_estoque"), ("CONCILIAÇÕES · ATIVO", "conciliacao_imobilizado"),
        ("CONCILIAÇÕES · ATIVO", "credito_estouro"),
        ("CONCILIAÇÕES · PASSIVO", "conciliacao_fornecedores"), ("CONCILIAÇÕES · PASSIVO", "conciliacao_rescisoes"),
        ("CONCILIAÇÕES · PASSIVO", "honorarios_medicos"), ("CONCILIAÇÕES · PASSIVO", "planilha_hm"),
        ("CONCILIAÇÕES · PASSIVO", "subvencoes"), ("RECEITAS", "convenios"), ("FERRAMENTAS", "imprimir_pdfs"), ("FERRAMENTAS", "historico_uso"),
    ]
    assert all(m.ok for m in carregados), [m.erro for m in carregados if not m.ok]


def test_main_abre_a_central():
    arvore = ast.parse((RAIZ / "main.py").read_text(encoding="utf-8"))
    importados = [(n.module, [a.name for a in n.names]) for n in ast.walk(arvore) if isinstance(n, ast.ImportFrom)]
    assert ("central.janela", ["JanelaCentral"]) in importados


def test_todos_os_paineis_reais_abrem(tmp_path):
    janela = abrir_janela_ctk(JanelaCentral, caminho_preferencias=tmp_path / "pref.json")
    try:
        for modulo in janela.modulos:
            janela.selecionar(modulo.chave)
        assert set(janela.paineis) == set(registro.NOMES_MODULOS)
    finally:
        janela.destroy()


def test_fechar_com_processamento_em_andamento_pergunta(tmp_path, dialogos):
    janela = abrir_janela_ctk(JanelaCentral, caminho_preferencias=tmp_path / "pref.json",
                              chave_inicial="clientes_cmd")
    painel = janela.paineis["clientes_cmd"].import_contabil     # a aba Import (montada aqui) processando
    painel.ocupado = True
    dialogos.resposta = False

    janela.ao_fechar()                                   # responde "Não": continua aberta

    assert len(dialogos.perguntas) == 1 and "Clientes CMD" in dialogos.perguntas[0]
    assert janela.winfo_exists()
    painel.ocupado = False
    janela.ao_fechar()                                   # nada em andamento: fecha sem perguntar
    assert len(dialogos.perguntas) == 1
