"""Configuração comum dos testes: localiza a pasta exemplos/ de cada módulo.

Os exemplos têm dados reais e não vão para o git. Se a pasta de um módulo não existir,
os testes que dependem dela são pulados (os demais continuam rodando).
"""

from __future__ import annotations

import os
from pathlib import Path

import openpyxl
import pytest

RAIZ = Path(__file__).resolve().parent.parent
# Nenhum teste grava o log de uso na rede (central/log_uso.py): os testes do log usam pastas temporárias.
os.environ["CENTRAL_LOG_USO_DESLIGADO"] = "1"
PASTA_EXEMPLOS = RAIZ / "exemplos"


def pasta_exemplos(modulo: str, *subpastas: str) -> Path:
    """exemplos/<modulo>/<subpastas...>; pula o teste se a pasta não existir."""
    pasta = PASTA_EXEMPLOS.joinpath(modulo, *subpastas)
    if not pasta.is_dir():
        pytest.skip(f"Pasta de exemplos {pasta} não encontrada")
    return pasta


def caso_real(modulo: str, chave: str):
    """Dado real (nome, CNPJ...) de exemplos/<modulo>/casos_reais.json; pula o teste sem o arquivo.

    Os testes que conferem os arquivos reais leem daqui o que identifica alguém: no código só
    ficam nomes fictícios.
    """
    import json

    arquivo = PASTA_EXEMPLOS / modulo / "casos_reais.json"
    if not arquivo.exists():
        pytest.skip(f"{arquivo} não encontrado (dados reais ficam fora do git)")
    return json.loads(arquivo.read_text(encoding="utf-8"))[chave]


def diferencas_entre_planilhas(esperada: Path, gerada: Path) -> list[tuple]:
    """Compara duas planilhas célula por célula (valores e fórmulas, como estão gravados).

    Devolve a lista de diferenças: (aba, célula, valor esperado, valor gerado). Vazia = iguais.
    """
    livro_esperado = openpyxl.load_workbook(esperada)
    livro_gerado = openpyxl.load_workbook(gerada)
    if livro_esperado.sheetnames != livro_gerado.sheetnames:
        return [("abas", "", livro_esperado.sheetnames, livro_gerado.sheetnames)]
    diferencas = []
    for nome in livro_esperado.sheetnames:
        aba_esperada, aba_gerada = livro_esperado[nome], livro_gerado[nome]
        linhas = max(aba_esperada.max_row, aba_gerada.max_row)
        colunas = max(aba_esperada.max_column, aba_gerada.max_column)
        for linha in range(1, linhas + 1):
            for coluna in range(1, colunas + 1):
                valor_esperado = aba_esperada.cell(linha, coluna).value
                valor_gerado = aba_gerada.cell(linha, coluna).value
                if valor_esperado != valor_gerado:
                    celula = aba_esperada.cell(linha, coluna).coordinate
                    diferencas.append((nome, celula, valor_esperado, valor_gerado))
    return diferencas


# ---------------------------------------------------------------------------
# Telas: janela escondida, espera do segundo plano e respostas aos diálogos
# ---------------------------------------------------------------------------


def pular_se_sem_tela(erro: Exception) -> None:
    """Pula o teste SÓ quando não há tela disponível (ex.: servidor sem monitor). Qualquer outro
    erro é um defeito de verdade e tem de aparecer como falha, nunca como teste pulado."""
    texto = str(erro).lower()
    if "display" in texto or "no screen" in texto:
        pytest.skip(f"Sem ambiente gráfico: {erro}")
    raise erro


def abrir_janela_ctk(classe=None, **opcoes):
    """Cria uma janela (CTk ou JanelaCentral) escondida, pulando o teste só se não houver tela."""
    import customtkinter as ctk

    try:
        janela = (classe or ctk.CTk)(**opcoes)
    except Exception as erro:
        pular_se_sem_tela(erro)
    janela.withdraw()
    return janela


@pytest.fixture(scope="module")
def raiz_tk():
    """Uma janela CustomTkinter escondida para montar painéis.

    Uma por arquivo de testes (e não uma para a rodada toda): duas janelas principais abertas ao
    mesmo tempo não compartilham ícones, e os testes da JanelaCentral abrem a sua própria.
    """
    janela = abrir_janela_ctk()
    yield janela
    janela.destroy()


def esperar(widget, condicao, limite_segundos: float = 180) -> None:
    """Processa os eventos da janela até `condicao()` ser verdadeira (ou estourar o limite)."""
    import time

    inicio = time.time()
    while not condicao():
        widget.update()
        if time.time() - inicio > limite_segundos:
            raise TimeoutError("a tela não terminou a tempo")
        time.sleep(0.02)
    for _ in range(5):
        widget.update()


class Dialogos:
    """Registra os diálogos abertos e responde às perguntas (sim/não) no lugar do usuário."""

    def __init__(self):
        self.perguntas: list[str] = []
        self.avisos: list[str] = []
        self.erros: list[str] = []
        self.informacoes: list[str] = []
        self.resposta = True

    def _askyesno(self, titulo, texto, **_):
        self.perguntas.append(texto)
        return self.resposta

    def _showwarning(self, titulo, texto, **_):
        self.avisos.append(texto)

    def _showerror(self, titulo, texto, **_):
        self.erros.append(texto)

    def _showinfo(self, titulo, texto, **_):
        self.informacoes.append(texto)


@pytest.fixture
def dialogos(monkeypatch):
    from tkinter import messagebox

    registro = Dialogos()
    monkeypatch.setattr(messagebox, "askyesno", registro._askyesno)
    monkeypatch.setattr(messagebox, "showwarning", registro._showwarning)
    monkeypatch.setattr(messagebox, "showerror", registro._showerror)
    monkeypatch.setattr(messagebox, "showinfo", registro._showinfo)
    return registro


@pytest.fixture
def criar_painel(raiz_tk):
    """criar_painel(MODULO) -> painel montado na janela escondida; destruído no fim do teste."""
    criados = []

    def _criar(info):
        painel = info.criar_painel(raiz_tk)
        painel.pack()
        criados.append(painel)
        return painel

    yield _criar
    import gc

    for painel in criados:
        esperar(painel, lambda: not getattr(painel, "ocupado", False))
        painel.destroy()
    gc.collect()      # restos da tela são apagados aqui, na thread da janela (ver central/segundo_plano.py)
