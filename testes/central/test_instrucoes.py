"""Testes da aba "Instruções de uso": leitura do Markdown, a aba em cada módulo e o arquivo de cada módulo."""

from __future__ import annotations

import pytest

from central import instrucoes, registro
from central.painel_abas import ABA_INSTRUCOES, DESCRICAO_INSTRUCOES
from testes.conftest import esperar


# ---------------------------------------------------------------------------
# Leitura do Markdown
# ---------------------------------------------------------------------------

EXEMPLO = """# Título

Primeira linha do parágrafo
continua aqui com **negrito** e `codigo`.

## Seção

- item um
  continuação do item um
- item **dois**

1. passo um
2. passo dois

> citação

| Coluna | O que mostra |
|---|---|
| Saldo | o saldo |

| Status | Cor | Significado |
|---|---|---|
| OK | verde | bate |

---
"""


def test_interpretar_blocos():
    blocos = instrucoes.interpretar(EXEMPLO)
    assert [b.tipo for b in blocos] == ["titulo", "paragrafo", "titulo", "lista", "lista", "citacao", "tabela",
                                        "tabela", "linha"]
    assert (blocos[0].nivel, blocos[0].texto) == (1, "Título")
    assert blocos[1].texto == "Primeira linha do parágrafo continua aqui com **negrito** e `codigo`."
    assert blocos[3].itens == ["item um continuação do item um", "item **dois**"] and not blocos[3].numerada
    assert blocos[4].itens == ["passo um", "passo dois"] and blocos[4].numerada
    assert blocos[5].texto == "citação"
    assert blocos[6].linhas == [["Coluna", "O que mostra"], ["Saldo", "o saldo"]]      # sem a linha ---
    assert blocos[7].linhas == [["Status", "Cor", "Significado"], ["OK", "verde", "bate"]]


def test_trechos_negrito_e_codigo():
    assert instrucoes.trechos("a **b** c `d`") == [("a ", ""), ("b", "negrito"), (" c ", ""), ("d", "codigo")]
    assert instrucoes.trechos("sem marcação") == [("sem marcação", "")]


# ---------------------------------------------------------------------------
# Arquivo de instruções de cada módulo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("chave", registro.NOMES_MODULOS)
def test_todo_modulo_tem_instrucoes_de_uso(chave):
    caminho = instrucoes.caminho_instrucoes(chave)
    assert caminho.is_file(), f"falta {caminho}"
    blocos = instrucoes.interpretar(caminho.read_text(encoding="utf-8"))
    assert blocos and blocos[0].tipo == "titulo" and blocos[0].nivel == 1
    assert sum(1 for b in blocos if b.tipo == "titulo") >= 3


@pytest.mark.parametrize("chave", registro.NOMES_MODULOS)
def test_instrucoes_nao_citam_as_janelas_antigas(chave):
    """As instruções são da Central: não mandam abrir os .exe antigos nem clicar em botões que não existem."""
    texto = instrucoes.caminho_instrucoes(chave).read_text(encoding="utf-8")
    for antigo in ("ConciliacaoBancaria.exe", "ConciliacaoSubvencoes.exe", "ConciliacaoClientesCMD.exe",
                   "Escolher...", "Salvar Como...", "Adicionar...", "Preparar modelo novo"):
        assert antigo not in texto


# ---------------------------------------------------------------------------
# A aba em cada módulo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("modulo", [m for m in registro.carregar_modulos() if m.ok], ids=lambda m: m.chave)
def test_cada_modulo_tem_a_aba_de_instrucoes(criar_painel, modulo):
    tela = criar_painel(modulo.info)
    assert list(tela.abas.botoes)[-1] == ABA_INSTRUCOES
    assert tela.instrucoes is None                        # só é montada quando aberta

    tela.mostrar_aba(ABA_INSTRUCOES)
    esperar(tela, lambda: True)

    assert tela.aba_atual == ABA_INSTRUCOES
    assert tela.cabecalho.rotulo_descricao.cget("text") == DESCRICAO_INSTRUCOES
    assert tela.instrucoes.texto is not None
    assert "instruções de uso" in tela.instrucoes.texto.texto_puro.splitlines()[0].lower()
    assert int(tela.instrucoes.texto.cget("height")) > 20  # a altura acompanha o conteúdo
    primeira = list(tela.abas.botoes)[0]
    tela.mostrar_aba(primeira)                            # e volta para a aba de trabalho
    assert tela.instrucoes.winfo_manager() == ""


def test_texto_troca_de_cor_com_o_modo(raiz_tk):
    from central import tema

    texto = instrucoes.TextoFormatado(raiz_tk, instrucoes.interpretar(EXEMPLO))
    texto._ao_mudar_modo("Dark")
    assert texto.cget("bg") == tema.COR_SUPERFICIE[1]
    texto._ao_mudar_modo("Light")
    assert texto.cget("bg") == tema.COR_SUPERFICIE[0]
    assert texto.cget("state") == "disabled"             # somente leitura
    assert "•  item um continuação do item um" in texto.texto_puro
    assert "Cor: verde" in texto.texto_puro              # tabela de 3 colunas em "ficha"
    assert "Saldo — o saldo" in texto.texto_puro         # tabela de 2 colunas em uma linha
    texto.destroy()


def test_modulo_sem_arquivo_mostra_aviso(raiz_tk, monkeypatch, tmp_path):
    monkeypatch.setattr(instrucoes, "caminho_instrucoes", lambda chave: tmp_path / "nao_existe.md")
    painel = instrucoes.PainelInstrucoes(raiz_tk, "qualquer")
    assert painel.texto is None
    painel.destroy()
