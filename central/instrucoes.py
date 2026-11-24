"""Aba "Instruções de uso": mostra o INSTRUCOES_DE_USO.md de cada módulo, formatado.

Entende um subconjunto simples de Markdown, o suficiente para instruções:
- títulos (#, ##, ###), parágrafos, listas (- ou 1.), citações (>), linha (---);
- **negrito** e `código` dentro do texto;
- tabelas: com 2 colunas viram "**primeira** — segunda"; com mais colunas, a primeira em negrito
  e as outras abaixo, como "Título da coluna: valor" (cabe na largura da tela sem cortar).

O texto é mostrado num Text do Tkinter (dá para selecionar e copiar), com cores e fontes do tema.
"""

from __future__ import annotations

import re
import tkinter
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import font as tkfont

import customtkinter as ctk

from central import tema
from central.caminhos import caminho_interno
from central.componentes import Cartao, EstadoVazio

NOME_ARQUIVO = "INSTRUCOES_DE_USO.md"


# ---------------------------------------------------------------------------
# Leitura do Markdown (sem tela)
# ---------------------------------------------------------------------------


@dataclass
class Bloco:
    tipo: str                         # titulo, paragrafo, lista, citacao, tabela, linha
    texto: str = ""
    nivel: int = 0                    # títulos: 1 a 3
    itens: list[str] = field(default_factory=list)       # listas
    numerada: bool = False
    linhas: list[list[str]] = field(default_factory=list)  # tabelas: [cabeçalho, linha, linha...]


_PADRAO_TITULO = re.compile(r"^(#{1,3})\s+(.*)$")
_PADRAO_ITEM = re.compile(r"^\s*(?:[-*]|(\d+)[.)])\s+(.*)$")
_PADRAO_SEPARADOR_TABELA = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
_PADRAO_INLINE = re.compile(r"(\*\*.+?\*\*|`[^`]+`)")


def caminho_instrucoes(chave_modulo: str) -> Path:
    """modulos/<chave>/INSTRUCOES_DE_USO.md (funciona no Python e no .exe)."""
    return caminho_interno("modulos", chave_modulo, NOME_ARQUIVO)


def _celulas(linha: str) -> list[str]:
    texto = linha.strip()
    if texto.startswith("|"):
        texto = texto[1:]
    if texto.endswith("|"):
        texto = texto[:-1]
    return [c.strip() for c in texto.split("|")]


def interpretar(texto: str) -> list[Bloco]:
    """Markdown -> lista de blocos."""
    blocos: list[Bloco] = []
    linhas = texto.replace("\r\n", "\n").split("\n")
    i = 0
    while i < len(linhas):
        linha = linhas[i]
        limpa = linha.strip()
        if not limpa:
            i += 1
            continue
        if limpa in ("---", "***", "___"):
            blocos.append(Bloco("linha"))
            i += 1
            continue
        titulo = _PADRAO_TITULO.match(limpa)
        if titulo:
            blocos.append(Bloco("titulo", titulo.group(2).strip(), nivel=len(titulo.group(1))))
            i += 1
            continue
        if limpa.startswith("|"):
            tabela = []
            while i < len(linhas) and linhas[i].strip().startswith("|"):
                if not _PADRAO_SEPARADOR_TABELA.match(linhas[i].strip()):
                    tabela.append(_celulas(linhas[i]))
                i += 1
            blocos.append(Bloco("tabela", linhas=tabela))
            continue
        if limpa.startswith(">"):
            partes = []
            while i < len(linhas) and linhas[i].strip().startswith(">"):
                partes.append(linhas[i].strip()[1:].strip())
                i += 1
            blocos.append(Bloco("citacao", " ".join(p for p in partes if p)))
            continue
        item = _PADRAO_ITEM.match(linha)
        if item:
            numerada = item.group(1) is not None
            itens = []
            while i < len(linhas):
                atual = _PADRAO_ITEM.match(linhas[i])
                if atual:
                    itens.append(atual.group(2).strip())
                elif linhas[i].strip() and linhas[i].startswith((" ", "\t")) and itens:
                    itens[-1] += " " + linhas[i].strip()     # continuação do item na linha de baixo
                else:
                    break
                i += 1
            blocos.append(Bloco("lista", itens=itens, numerada=numerada))
            continue
        partes = []
        while i < len(linhas):
            atual = linhas[i].strip()
            if (not atual or _PADRAO_TITULO.match(atual) or atual.startswith(("|", ">"))
                    or _PADRAO_ITEM.match(linhas[i]) or atual in ("---", "***", "___")):
                break
            partes.append(atual)
            i += 1
        blocos.append(Bloco("paragrafo", " ".join(partes)))
    return blocos


def trechos(texto: str) -> list[tuple[str, str]]:
    """Texto com **negrito** e `código` -> [(trecho, estilo)], estilo "", "negrito" ou "codigo"."""
    resultado = []
    for parte in _PADRAO_INLINE.split(texto):
        if not parte:
            continue
        if parte.startswith("**") and parte.endswith("**") and len(parte) > 4:
            resultado.append((parte[2:-2], "negrito"))
        elif parte.startswith("`") and parte.endswith("`") and len(parte) > 2:
            resultado.append((parte[1:-1], "codigo"))
        else:
            resultado.append((parte, ""))
    return resultado


# ---------------------------------------------------------------------------
# Tela
# ---------------------------------------------------------------------------


class TextoFormatado(tkinter.Text):
    """Text somente leitura que desenha os blocos com as fontes e cores do tema.

    A altura acompanha o conteúdo (quem rola é a página da Central, não o texto).
    """

    def __init__(self, pai, blocos: list[Bloco]):
        super().__init__(pai, wrap="word", borderwidth=0, highlightthickness=0, padx=0, pady=0,
                         cursor="arrow", height=1, takefocus=0)
        self._fontes = self._criar_fontes()
        self.configure(font=self._fontes["texto"], spacing1=0, spacing3=0)
        self._configurar_tags()
        self._ao_mudar_modo(ctk.get_appearance_mode())
        ctk.AppearanceModeTracker.add(self._ao_mudar_modo, self)
        self.escrever(blocos)
        self.bind("<Configure>", lambda _e: self.after_idle(self.ajustar_altura), add="+")

    # --- fontes e cores ---

    def _criar_fontes(self) -> dict[str, tkfont.Font]:
        escala = ctk.ScalingTracker.get_widget_scaling(self)

        def fonte(familia, tamanho, peso="normal"):
            return tkfont.Font(self, family=familia, size=-round(tamanho * escala), weight=peso)

        return {
            "texto": fonte(tema.FAMILIA_TEXTO, 14),
            "negrito": fonte(tema.FAMILIA_TEXTO, 14, "bold"),
            "codigo": fonte(tema.FAMILIA_NUMEROS, 13),
            "titulo1": fonte(tema.FAMILIA_TEXTO, 22, "bold"),
            "titulo2": fonte(tema.FAMILIA_TEXTO, 17, "bold"),
            "titulo3": fonte(tema.FAMILIA_TEXTO, 15, "bold"),
        }

    def _configurar_tags(self) -> None:
        f = self._fontes
        self.tag_configure("titulo1", font=f["titulo1"], spacing1=4, spacing3=10)
        self.tag_configure("titulo2", font=f["titulo2"], spacing1=18, spacing3=8)
        self.tag_configure("titulo3", font=f["titulo3"], spacing1=12, spacing3=6)
        self.tag_configure("paragrafo", spacing3=10)
        self.tag_configure("item", lmargin1=8, lmargin2=26, spacing3=5)
        self.tag_configure("item_fim", lmargin1=8, lmargin2=26, spacing3=14)
        self.tag_configure("citacao", lmargin1=16, lmargin2=16, spacing3=10)
        self.tag_configure("ficha", spacing1=6, spacing3=2)
        self.tag_configure("ficha_detalhe", lmargin1=18, lmargin2=18, spacing3=2)
        self.tag_configure("ficha_fim", spacing3=2)
        self.tag_configure("negrito", font=f["negrito"])
        self.tag_configure("codigo", font=f["codigo"])

    def _ao_mudar_modo(self, modo: str) -> None:
        indice = 1 if modo.lower() == "dark" else 0
        self.configure(bg=tema.COR_SUPERFICIE[indice], fg=tema.COR_TEXTO[indice],
                       selectbackground=tema.COR_PRINCIPAL_SUAVE[indice], selectforeground=tema.COR_TEXTO[indice],
                       inactiveselectbackground=tema.COR_PRINCIPAL_SUAVE[indice])
        self.tag_configure("citacao", foreground=tema.COR_TEXTO_SUAVE[indice])
        self.tag_configure("rotulo", foreground=tema.COR_TEXTO_SUAVE[indice])
        self.tag_configure("marcador", foreground=tema.COR_PRINCIPAL[indice])
        self.tag_configure("codigo", background=tema.COR_PRINCIPAL_SUAVE[indice])
        for nivel in (1, 2, 3):
            self.tag_configure(f"titulo{nivel}", foreground=tema.COR_TEXTO[indice])

    def destroy(self):
        ctk.AppearanceModeTracker.remove(self._ao_mudar_modo)
        super().destroy()

    # --- conteúdo ---

    def _inserir(self, texto: str, *tags: str) -> None:
        for trecho, estilo in trechos(texto):
            self.insert("end", trecho, tags + ((estilo,) if estilo else ()))

    def escrever(self, blocos: list[Bloco]) -> None:
        self.configure(state="normal")
        self.delete("1.0", "end")
        for bloco in blocos:
            if bloco.tipo == "titulo":
                # o título já é negrito: **...** e `...` só perdem as marcas
                texto = "".join(trecho for trecho, _estilo in trechos(bloco.texto))
                self.insert("end", texto + "\n", (f"titulo{bloco.nivel}",))
            elif bloco.tipo == "paragrafo":
                self._inserir(bloco.texto, "paragrafo")
                self.insert("end", "\n", ("paragrafo",))
            elif bloco.tipo == "citacao":
                self._inserir(bloco.texto, "citacao")
                self.insert("end", "\n", ("citacao",))
            elif bloco.tipo == "lista":
                for numero, item in enumerate(bloco.itens, 1):
                    marcador = f"{numero}.  " if bloco.numerada else "•  "
                    tag = "item_fim" if numero == len(bloco.itens) else "item"
                    self.insert("end", marcador, (tag, "marcador"))
                    self._inserir(item, tag)
                    self.insert("end", "\n", (tag,))
            elif bloco.tipo == "tabela":
                self._escrever_tabela(bloco.linhas)
            elif bloco.tipo == "linha":
                pass   # a linha "---" só separa seções no arquivo; na tela o título seguinte já separa
        self.configure(state="disabled")
        self.ajustar_altura()

    def _escrever_tabela(self, linhas: list[list[str]]) -> None:
        if not linhas:
            return
        cabecalho, dados = linhas[0], [c for c in linhas[1:] if c]
        for numero, celulas in enumerate(dados, 1):
            if len(cabecalho) <= 2:
                tag = "item_fim" if numero == len(dados) else "item"
                self.insert("end", "•  ", (tag, "marcador"))
                self._inserir(celulas[0], tag, "negrito")
                if len(celulas) > 1 and celulas[1]:
                    self._inserir(" — " + celulas[1], tag)
                self.insert("end", "\n", (tag,))
            else:
                self._inserir(celulas[0], "ficha", "negrito")
                self.insert("end", "\n", ("ficha",))
                for titulo, valor in zip(cabecalho[1:], celulas[1:]):
                    if not valor:
                        continue
                    self.insert("end", f"{titulo}: ", ("ficha_detalhe", "rotulo"))
                    self._inserir(valor, "ficha_detalhe")
                    self.insert("end", "\n", ("ficha_detalhe",))
                self.insert("end", "\n", ("ficha_fim",))

    def ajustar_altura(self) -> None:
        """Altura = altura do conteúdo, para o texto não ter rolagem própria."""
        try:
            pixels = self.count("1.0", "end", "ypixels")
        except tkinter.TclError:
            return
        pixels = pixels[0] if isinstance(pixels, tuple) else pixels
        if not pixels:
            return
        linha = self._fontes["texto"].metrics("linespace") or 1
        linhas = max(1, round(pixels / linha) + 1)
        if int(self.cget("height")) != linhas:
            self.configure(height=linhas)

    @property
    def texto_puro(self) -> str:
        return self.get("1.0", "end")


class PainelInstrucoes(ctk.CTkFrame):
    """Conteúdo da aba "Instruções de uso" de um módulo."""

    def __init__(self, pai, chave_modulo: str):
        super().__init__(pai, fg_color="transparent")
        self.caminho = caminho_instrucoes(chave_modulo)
        self.texto: TextoFormatado | None = None
        try:
            conteudo = self.caminho.read_text(encoding="utf-8")
        except OSError:
            EstadoVazio(self, "Instruções não encontradas",
                        f"O arquivo {NOME_ARQUIVO} deste módulo não foi encontrado.", icone="alerta",
                        tom="atencao").pack(fill="x")
            return
        cartao = Cartao(self)
        cartao.pack(fill="both", expand=True)
        self.texto = TextoFormatado(cartao.corpo, interpretar(conteudo))
        self.texto.pack(fill="both", expand=True)
