"""Peças visuais reutilizáveis da Central (GUIA_VISUAL, seções 3 a 5).

Todos os módulos montam as suas telas com estas peças. Nenhuma cor, fonte ou medida é escrita
aqui: tudo vem de central/tema.py. As peças só exibem o que o módulo manda; não têm regra de
negócio.
"""

from __future__ import annotations

import tkinter
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog
from typing import Callable

import customtkinter as ctk

from central import icones, tema
from central.caminhos import caminho_interno

# Tom -> (cor forte, cor suave). "ok", "atencao" e "erro" também servem de status.
TONS = {
    "principal": (tema.COR_PRINCIPAL, tema.COR_PRINCIPAL_SUAVE),
    "ok": (tema.COR_OK, tema.COR_OK_SUAVE),
    "atencao": (tema.COR_ATENCAO, tema.COR_ATENCAO_SUAVE),
    "erro": (tema.COR_ERRO, tema.COR_ERRO_SUAVE),
}
ICONE_DO_STATUS = {"ok": "check", "atencao": "alerta", "erro": "erro"}

TIPOS_PLANILHA = [("Planilhas Excel", "*.xlsx"), ("Todos os arquivos", "*.*")]


def _tom(nome: str) -> tuple:
    if nome not in TONS:
        raise ValueError(f"Tom desconhecido: {nome!r}. Use um de {sorted(TONS)}.")
    return TONS[nome]


def _limpar(frame) -> None:
    for filho in frame.winfo_children():
        filho.destroy()


def _frame_vazio(pai) -> ctk.CTkFrame:
    """Frame transparente que só ocupa espaço quando recebe conteúdo (o CTkFrame vazio mede 200 px)."""
    return ctk.CTkFrame(pai, fg_color="transparent", width=1, height=1)


TOLERANCIA_QUEBRA = 4   # px: diferenças menores não mudam a quebra de linha (ver _quebrar_em)


def _quebrar_em(rotulo, largura: int) -> None:
    """Muda a largura de quebra do texto só se a diferença passar de TOLERANCIA_QUEBRA.

    Sem essa folga, os 3 quadros de números da janela mínima entravam em ciclo sem fim: requebrar o
    texto mudava em 1 px a divisão da largura entre eles, o que requebrava o texto de novo... e o
    programa travava (visto na tela de Rescisões do Conciliações AMES, versão 2.4.0)."""
    if abs(int(rotulo.cget("wraplength")) - largura) > TOLERANCIA_QUEBRA:
        rotulo.configure(wraplength=largura)


def aplicar_icone(janela) -> None:
    """Ícone da barra de título (recursos/icone.ico). Sem ele a janela funciona igual."""
    caminho = caminho_interno("recursos", "icone.ico")
    if caminho.is_file():
        try:
            janela.iconbitmap(str(caminho))
        except Exception:
            pass


class Separador(tkinter.Frame):
    """Linha fina de 1 px na cor da borda. (O CTkFrame não desenha nada com 1 px de altura,
    por isso é um Frame do Tkinter que troca de cor sozinho quando o modo claro/escuro muda.)"""

    def __init__(self, pai, cor: tuple[str, str] = tema.COR_BORDA):
        super().__init__(pai, height=tema.LARGURA_BORDA, borderwidth=0, highlightthickness=0)
        self.cor = cor
        self._ao_mudar_modo(ctk.get_appearance_mode())
        ctk.AppearanceModeTracker.add(self._ao_mudar_modo, self)

    def _ao_mudar_modo(self, modo: str) -> None:
        self.configure(bg=self.cor[1] if modo.lower() == "dark" else self.cor[0])

    def destroy(self):
        ctk.AppearanceModeTracker.remove(self._ao_mudar_modo)
        super().destroy()


class AreaRolavel(ctk.CTkFrame):
    """Área que rola na vertical (usada no meio do menu lateral). Os itens vão em `.conteudo`.

    Diferente do CTkScrollableFrame, a barra só aparece quando o conteúdo não cabe, e a roda do
    mouse só rola esta área quando o ponteiro está sobre ela. (Trazida do Conciliações AMES.)
    """

    PASSO_RODA = 24                       # px por "dente" da roda do mouse

    def __init__(self, pai, cor_fundo: tuple[str, str], cor_barra: tuple[str, str],
                 cor_barra_destaque: tuple[str, str]):
        super().__init__(pai, fg_color=cor_fundo, corner_radius=0)
        self.cor_fundo = cor_fundo
        self.canvas = tkinter.Canvas(self, height=1, highlightthickness=0, borderwidth=0,
                                     yscrollincrement=1)
        self.barra = ctk.CTkScrollbar(self, orientation="vertical", command=self.canvas.yview,
                                      width=tema.LARGURA_BARRA_MENU, fg_color=cor_fundo,
                                      button_color=cor_barra, button_hover_color=cor_barra_destaque)
        self.canvas.configure(yscrollcommand=self.barra.set)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.barra_visivel = False
        self.destruida = False
        self._a_mostrar = None            # último widget pedido em mostrar(): vale quando a barra aparecer

        self.conteudo = ctk.CTkFrame(self.canvas, fg_color=cor_fundo, corner_radius=0)
        self._janela = self.canvas.create_window(0, 0, window=self.conteudo, anchor="nw")
        self.conteudo.bind("<Configure>", self._ajustar, add="+")
        self.canvas.bind("<Configure>", self._ajustar, add="+")
        self.canvas.bind("<Map>", self._ajustar, add="+")
        self.canvas.bind_all("<MouseWheel>", self._rodar, add="+")   # o CTkFrame não aceita bind_all
        self._ao_mudar_modo(ctk.get_appearance_mode())
        ctk.AppearanceModeTracker.add(self._ao_mudar_modo, self)

    def _ao_mudar_modo(self, modo: str) -> None:
        if not self.destruida:
            self.canvas.configure(bg=self.cor_fundo[1] if modo.lower() == "dark" else self.cor_fundo[0])

    def destroy(self) -> None:
        # Ao fechar, nada de ajustar a barra (ela se redesenha durante o fechamento e chamaria
        # os ajustes com os widgets já pela metade).
        self.destruida = True
        self.canvas.configure(yscrollcommand="")
        ctk.AppearanceModeTracker.remove(self._ao_mudar_modo)
        super().destroy()

    def precisa_rolar(self) -> bool:
        # Só depois de a janela aparecer: mostrar e esconder a barra durante a montagem (quando o
        # canvas ainda tem poucos px) deixava o canvas escondido e o menu vazio até redimensionar.
        visivel = bool(self.canvas.winfo_viewable())
        return visivel and self.conteudo.winfo_reqheight() > self.canvas.winfo_height() > 1

    def _ajustar(self, _evento=None) -> None:
        if self.destruida:
            return
        self.canvas.itemconfigure(self._janela, width=self.canvas.winfo_width())
        self.canvas.configure(scrollregion=(0, 0, self.canvas.winfo_width(), self.conteudo.winfo_reqheight()))
        precisa = self.precisa_rolar()
        if precisa and not self.barra_visivel:
            self.barra.grid(row=0, column=1, sticky="ns")
            if self._a_mostrar is not None:
                # o pedido veio antes de a janela aparecer (no .exe ela demora mais): vale agora
                self.after_idle(lambda: self.mostrar(self._a_mostrar))
        elif not precisa and self.barra_visivel:
            self.barra.grid_remove()
            self.canvas.yview_moveto(0)
        self.barra_visivel = precisa

    def _rodar(self, evento) -> None:
        if self.destruida or not self.barra_visivel:
            return
        try:
            dentro = str(evento.widget).startswith(str(self.canvas))
        except Exception:      # widget já destruído ou nome estranho
            return
        if dentro:
            dentes = -1 if evento.delta > 0 else 1
            self.canvas.yview_scroll(dentes * self.PASSO_RODA, "units")

    def mostrar(self, widget) -> None:
        """Rola o mínimo para o widget (um item de dentro de .conteudo) ficar visível. Sem barra ainda (a
        janela não apareceu ou o conteúdo cabe), o pedido fica guardado e vale quando a barra aparecer."""
        self._a_mostrar = widget
        try:
            if self.destruida or not widget.winfo_exists():
                return
        except tkinter.TclError:          # janela já fechada
            return
        self._ajustar()
        if not self.barra_visivel:
            return
        if widget.winfo_height() <= 1:
            # a barra apareceu antes de o item ganhar lugar na tela: tenta de novo em seguida
            self.after(50, lambda: self._a_mostrar is widget and self.mostrar(widget))
            return
        topo = widget.winfo_rooty() - self.conteudo.winfo_rooty()
        fim = topo + widget.winfo_height()
        total = max(self.conteudo.winfo_reqheight(), 1)
        visivel_topo = self.canvas.canvasy(0)
        visivel_fim = visivel_topo + self.canvas.winfo_height()
        if topo < visivel_topo:
            self.canvas.yview_moveto(topo / total)
        elif fim > visivel_fim:
            self.canvas.yview_moveto((fim - self.canvas.winfo_height()) / total)


# ---------------------------------------------------------------------------
# Estrutura da página
# ---------------------------------------------------------------------------


class CabecalhoModulo(ctk.CTkFrame):
    """Contexto (pequeno), título e frase do módulo; à direita, campos gerais (area_direita)."""

    def __init__(self, pai, contexto: str, titulo: str, descricao: str):
        super().__init__(pai, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)

        textos = ctk.CTkFrame(self, fg_color="transparent")
        textos.grid(row=0, column=0, sticky="nw")
        self.rotulo_contexto = ctk.CTkLabel(textos, text=contexto, font=tema.fonte_contexto(),
                                            text_color=tema.COR_TEXTO_SUAVE, anchor="w")
        self.rotulo_contexto.pack(anchor="w")
        self.rotulo_titulo = ctk.CTkLabel(textos, text=titulo, font=tema.fonte_titulo(),
                                          text_color=tema.COR_TEXTO, anchor="w")
        self.rotulo_titulo.pack(anchor="w", pady=(2, 4))
        self.rotulo_descricao = ctk.CTkLabel(textos, text=descricao, font=tema.fonte_texto(),
                                             text_color=tema.COR_TEXTO_SUAVE, anchor="w", justify="left",
                                             wraplength=640)
        self.rotulo_descricao.pack(anchor="w")

        self.area_direita = _frame_vazio(self)
        self.area_direita.grid(row=0, column=1, sticky="ne", padx=(tema.ESPACO_ENTRE_BLOCOS, 0))


class CampoRotulado(ctk.CTkFrame):
    """Rótulo de 12 px em negrito e, abaixo, um campo de altura 44 com fonte de números."""

    def __init__(self, pai, rotulo: str, largura: int = 150, texto_inicial: str = "",
                 ao_mudar: Callable[[str], None] | None = None):
        super().__init__(pai, fg_color="transparent")
        self.rotulo = ctk.CTkLabel(self, text=rotulo, font=tema.fonte_rotulo(), text_color=tema.COR_TEXTO,
                                   anchor="w")
        self.rotulo.pack(anchor="w", pady=(0, 4))
        self.variavel = ctk.StringVar(value=texto_inicial)
        self.entrada = ctk.CTkEntry(self, width=largura, height=tema.ALTURA_CAMPO, font=tema.fonte_campo(),
                                    corner_radius=tema.RAIO_BOTAO, border_width=tema.LARGURA_BORDA,
                                    border_color=tema.COR_BORDA, fg_color=tema.COR_SUPERFICIE,
                                    text_color=tema.COR_TEXTO, textvariable=self.variavel)
        self.entrada.pack(anchor="w")
        if ao_mudar:
            self.variavel.trace_add("write", lambda *_: ao_mudar(self.valor()))

    def valor(self) -> str:
        return self.variavel.get().strip()

    def definir(self, texto: str) -> None:
        self.variavel.set(texto)


class CampoComLista(ctk.CTkFrame):
    """Como o CampoRotulado, mas com uma lista de valores já usados para escolher (e aceita digitar)."""

    def __init__(self, pai, rotulo: str, opcoes: list[str] | None = None, largura: int = 220,
                 texto_inicial: str = "", ao_mudar: Callable[[str], None] | None = None):
        super().__init__(pai, fg_color="transparent")
        self.rotulo = ctk.CTkLabel(self, text=rotulo, font=tema.fonte_rotulo(), text_color=tema.COR_TEXTO,
                                   anchor="w")
        self.rotulo.pack(anchor="w", pady=(0, 4))
        self.variavel = ctk.StringVar(value=texto_inicial)
        self.lista = ctk.CTkComboBox(self, values=list(opcoes or []), variable=self.variavel, width=largura,
                                     height=tema.ALTURA_CAMPO, font=tema.fonte_campo(),
                                     dropdown_font=tema.fonte_campo(), corner_radius=tema.RAIO_BOTAO,
                                     border_width=tema.LARGURA_BORDA, border_color=tema.COR_BORDA,
                                     fg_color=tema.COR_SUPERFICIE, text_color=tema.COR_TEXTO,
                                     button_color=tema.COR_BORDA, button_hover_color=tema.COR_PRINCIPAL_SUAVE,
                                     dropdown_fg_color=tema.COR_SUPERFICIE, dropdown_text_color=tema.COR_TEXTO,
                                     dropdown_hover_color=tema.COR_PRINCIPAL_SUAVE)
        self.lista.pack(anchor="w")
        self.variavel.set(texto_inicial)          # o CTkComboBox põe o 1º item da lista se ninguém mandar
        if ao_mudar:
            self.variavel.trace_add("write", lambda *_: ao_mudar(self.valor()))

    def valor(self) -> str:
        return self.variavel.get().strip()

    def definir(self, texto: str) -> None:
        self.variavel.set(texto)

    def definir_opcoes(self, opcoes: list[str]) -> None:
        self.lista.configure(values=list(opcoes))

    @property
    def opcoes(self) -> list[str]:
        return list(self.lista.cget("values"))


class SeletorOpcoes(ctk.CTkFrame):
    """Rótulo e uma linha de opções das quais só uma fica marcada (ex.: Normal | Complementar).

    A marcada tem o visual da aba ativa (fundo suave, borda e texto na cor principal). Pode começar
    sem nenhuma marcada, para obrigar a escolha. ao_mudar(opcao) é chamado quando o usuário escolhe.
    """

    def __init__(self, pai, rotulo: str, opcoes: list[str], valor_inicial: str | None = None,
                 ao_mudar: Callable[[str], None] | None = None):
        super().__init__(pai, fg_color="transparent")
        self.ao_mudar = ao_mudar
        self.rotulo = ctk.CTkLabel(self, text=rotulo, font=tema.fonte_rotulo(), text_color=tema.COR_TEXTO,
                                   anchor="w")
        self.rotulo.pack(anchor="w", pady=(0, 4))
        linha = ctk.CTkFrame(self, fg_color="transparent")
        linha.pack(anchor="w")
        self.botoes: dict[str, ctk.CTkButton] = {}
        for opcao in opcoes:
            botao = ctk.CTkButton(linha, text=opcao, command=lambda o=opcao: self.selecionar(o, avisar=True),
                                  height=tema.ALTURA_CAMPO, corner_radius=tema.RAIO_BOTAO,
                                  border_width=tema.LARGURA_BORDA, font=tema.fonte_texto(), width=120)
            botao.pack(side="left", padx=(0, tema.ESPACO_PEQUENO // 2))
            self.botoes[opcao] = botao
        self.valor: str | None = None
        self.selecionar(valor_inicial)

    def selecionar(self, opcao: str | None, avisar: bool = False) -> None:
        if opcao is not None and opcao not in self.botoes:
            raise ValueError(f"Opção desconhecida: {opcao!r}")
        for chave, botao in self.botoes.items():
            if chave == opcao:
                botao.configure(fg_color=tema.COR_PRINCIPAL_SUAVE, hover_color=tema.COR_PRINCIPAL_SUAVE,
                                border_color=tema.COR_PRINCIPAL, text_color=tema.COR_PRINCIPAL,
                                font=tema.fonte_texto_forte())
            else:
                botao.configure(fg_color=tema.COR_SUPERFICIE, hover_color=tema.COR_PRINCIPAL_SUAVE,
                                border_color=tema.COR_BORDA, text_color=tema.COR_TEXTO, font=tema.fonte_texto())
        self.valor = opcao
        if avisar and self.ao_mudar:
            self.ao_mudar(opcao)


class LayoutDuasColunas(ctk.CTkFrame):
    """Duas colunas de mesma largura, com 24 px entre elas (GUIA_VISUAL, seção 5)."""

    def __init__(self, pai):
        super().__init__(pai, fg_color="transparent")
        self.grid_columnconfigure((0, 1), weight=1, uniform="colunas")
        self.grid_rowconfigure(0, weight=1)
        metade = tema.ESPACO_ENTRE_BLOCOS // 2
        self.esquerda = ctk.CTkFrame(self, fg_color="transparent")
        self.esquerda.grid(row=0, column=0, sticky="nsew", padx=(0, metade))
        self.direita = ctk.CTkFrame(self, fg_color="transparent")
        self.direita.grid(row=0, column=1, sticky="nsew", padx=(metade, 0))


class Cartao(ctk.CTkFrame):
    """Bloco com fundo de superfície, borda fina e cantos arredondados. Conteúdo vai em `corpo`."""

    def __init__(self, pai, titulo: str | None = None):
        super().__init__(pai, fg_color=tema.COR_SUPERFICIE, border_width=tema.LARGURA_BORDA,
                         border_color=tema.COR_BORDA, corner_radius=tema.RAIO_CARTAO)
        espaco = tema.ESPACO_INTERNO_CARTAO
        self.cabecalho = _frame_vazio(self)
        self.rotulo_titulo = None
        if titulo:
            self.cabecalho.pack(fill="x", padx=espaco, pady=(espaco, 0))
            self.rotulo_titulo = ctk.CTkLabel(self.cabecalho, text=titulo, font=tema.fonte_subtitulo(),
                                              text_color=tema.COR_TEXTO, anchor="w")
            self.rotulo_titulo.pack(side="left")
        self.corpo = ctk.CTkFrame(self, fg_color="transparent")
        self.corpo.pack(fill="both", expand=True, padx=espaco,
                        pady=(tema.ESPACO_PEQUENO if titulo else espaco, espaco))


# ---------------------------------------------------------------------------
# Botões
# ---------------------------------------------------------------------------


class BotaoPrincipal(ctk.CTkButton):
    """Botão de ação principal. `habilitar(False)` deixa-o apagado (cor suave) e sem clique."""

    def __init__(self, pai, texto: str, comando: Callable[[], None] | None = None,
                 icone: str | None = None, altura: int = tema.ALTURA_BOTAO):
        imagem = icones.icone(icone, tema.COR_TEXTO_SOBRE_PRINCIPAL, tema.TAMANHO_ICONE_BOTAO) if icone else None
        super().__init__(pai, text=texto, command=comando, image=imagem, compound="left", height=altura,
                         corner_radius=tema.RAIO_BOTAO, font=tema.fonte_texto_forte(),
                         fg_color=tema.COR_PRINCIPAL, hover_color=tema.COR_PRINCIPAL_HOVER,
                         text_color=tema.COR_TEXTO_SOBRE_PRINCIPAL, text_color_disabled=tema.COR_TEXTO_SUAVE)

    def habilitar(self, sim: bool = True) -> None:
        if sim:
            self.configure(state="normal", fg_color=tema.COR_PRINCIPAL)
        else:
            self.configure(state="disabled", fg_color=tema.COR_PRINCIPAL_SUAVE)

    @property
    def habilitado(self) -> bool:
        return self.cget("state") == "normal"


class BotaoSecundario(ctk.CTkButton):
    """Botão de apoio: fundo transparente e borda fina ("Ver avisos", "Novo", "Trocar")."""

    def __init__(self, pai, texto: str, comando: Callable[[], None] | None = None,
                 icone: str | None = None, altura: int = tema.ALTURA_BOTAO, largura: int = 140):
        imagem = icones.icone(icone, tema.COR_TEXTO, tema.TAMANHO_ICONE_BOTAO) if icone else None
        super().__init__(pai, text=texto, command=comando, image=imagem, compound="left", height=altura,
                         width=largura, corner_radius=tema.RAIO_BOTAO, font=tema.fonte_texto(),
                         fg_color="transparent", hover_color=tema.COR_PRINCIPAL_SUAVE,
                         border_width=tema.LARGURA_BORDA, border_color=tema.COR_BORDA,
                         text_color=tema.COR_TEXTO, text_color_disabled=tema.COR_TEXTO_SUAVE)

    def habilitar(self, sim: bool = True) -> None:
        self.configure(state="normal" if sim else "disabled")

    @property
    def habilitado(self) -> bool:
        return self.cget("state") == "normal"


# ---------------------------------------------------------------------------
# Entrada de arquivos
# ---------------------------------------------------------------------------


class CartaoArquivo(ctk.CTkFrame):
    """Escolha de arquivo(s) ou pasta, com o nome escolhido e uma linha de confirmação.

    tipo: "arquivo" (um), "arquivos" (vários) ou "pasta".
    ao_mudar(caminhos) é chamado depois de o usuário escolher: o módulo confere o arquivo e chama
    definir_confirmacao(texto, status) com status "ok", "atencao" ou "erro".
    acumular=True (só com "arquivos"): cada escolha ACRESCENTA à lista (botão "Adicionar arquivos"), para
    juntar arquivos de pastas diferentes; "Limpar" esvazia a lista.
    """

    TEXTO_SEM_ARQUIVO = "Nenhum arquivo selecionado"
    TEXTO_SEM_PASTA = "Nenhuma pasta selecionada"
    # com menos que isto para os nomes (ex.: "Adicionar arquivos" na janela mínima), os botões descem para
    # baixo dos nomes: senão os nomes dos arquivos quebravam no meio da palavra ("Balancet / e PF")
    LARGURA_MINIMA_TEXTOS = 150

    def __init__(self, pai, rotulo: str, tipo: str = "arquivo", icone: str | None = None,
                 tipos_arquivo: list[tuple[str, str]] | None = None,
                 ao_mudar: Callable[[list[Path]], None] | None = None, titulo_dialogo: str | None = None,
                 acumular: bool = False):
        if tipo not in ("arquivo", "arquivos", "pasta"):
            raise ValueError(f"Tipo de CartaoArquivo desconhecido: {tipo!r}")
        super().__init__(pai, fg_color=tema.COR_SUPERFICIE, border_width=tema.LARGURA_BORDA,
                         border_color=tema.COR_BORDA, corner_radius=tema.RAIO_BOTAO)
        self.tipo = tipo
        self.acumular = acumular and tipo == "arquivos"
        self.rotulo = rotulo
        self.tipos_arquivo = tipos_arquivo or TIPOS_PLANILHA
        self.ao_mudar = ao_mudar
        self.titulo_dialogo = titulo_dialogo or f"Selecionar: {rotulo}"
        self._caminhos: list[Path] = []
        self.status_confirmacao: str | None = None
        self.barra_carregando: ctk.CTkProgressBar | None = None   # definir_carregando()
        # pasta em que o seletor do Windows abre (ex.: a última usada); None = o padrão do Windows
        self.pasta_inicial: Path | None = None

        espaco = tema.ESPACO_INTERNO_ARQUIVO
        self.grid_columnconfigure(1, weight=1)

        quadro = ctk.CTkFrame(self, width=tema.TAMANHO_QUADRO_ICONE, height=tema.TAMANHO_QUADRO_ICONE,
                              fg_color=tema.COR_PRINCIPAL_SUAVE, corner_radius=tema.RAIO_PEQUENO)
        quadro.grid(row=0, column=0, padx=(espaco, espaco), pady=espaco, sticky="n")
        quadro.grid_propagate(False)
        nome_icone = icone or ("pasta" if tipo == "pasta" else "arquivos" if tipo == "arquivos" else "arquivo")
        ctk.CTkLabel(quadro, text="", image=icones.icone(nome_icone, tema.COR_PRINCIPAL, tema.TAMANHO_ICONE_CARTAO)
                     ).place(relx=0.5, rely=0.5, anchor="center")

        textos = self._textos = ctk.CTkFrame(self, fg_color="transparent", width=1, height=1)
        textos.grid(row=0, column=1, sticky="ew", pady=espaco)
        self.rotulo_rotulo = ctk.CTkLabel(textos, text=rotulo, font=tema.fonte_legenda(),
                                          text_color=tema.COR_TEXTO_SUAVE, anchor="w", justify="left", wraplength=200)
        self.rotulo_rotulo.pack(anchor="w", fill="x")
        self.rotulo_nome = ctk.CTkLabel(textos, text="", font=tema.fonte_texto_forte(), text_color=tema.COR_TEXTO,
                                        anchor="w", justify="left", wraplength=200)
        self.rotulo_nome.pack(anchor="w", fill="x")
        self.rotulo_confirmacao = ctk.CTkLabel(textos, text="", font=tema.fonte_legenda(), anchor="w",
                                               justify="left", wraplength=200)
        self.rotulo_confirmacao.pack(anchor="w", fill="x")
        # os textos quebram a linha conforme a largura real do cartão (nomes compridos não são cortados)
        textos.bind("<Configure>", self._ajustar_quebra, add="+")

        botoes = self._botoes = ctk.CTkFrame(self, fg_color="transparent")
        botoes.grid(row=0, column=2, padx=espaco, pady=espaco)
        self.botoes_embaixo = False
        self.bind("<Configure>", self._arrumar_botoes, add="+")
        self.botao = BotaoSecundario(botoes, self._texto_botao(False), self.selecionar,
                                     altura=tema.ALTURA_BOTAO_PEQUENO, largura=150 if self.acumular else 110)
        self.botao.pack()
        # "Limpar": tira a seleção deste cartão (só aparece quando há algo escolhido)
        self.botao_limpar = ctk.CTkButton(botoes, text="Limpar", command=self.limpar_pelo_usuario,
                                          height=tema.ALTURA_SELO, width=110, corner_radius=tema.RAIO_PEQUENO,
                                          fg_color="transparent", hover_color=tema.COR_PRINCIPAL_SUAVE,
                                          border_width=0, text_color=tema.COR_TEXTO_SUAVE,
                                          font=tema.fonte_legenda())
        self._atualizar()

    def _arrumar_botoes(self, evento) -> None:
        """Botões ao lado dos nomes; embaixo deles quando sobra pouco espaço para os nomes."""
        escala = ctk.ScalingTracker.get_widget_scaling(self)
        espaco = tema.ESPACO_INTERNO_ARQUIVO
        largura_botoes = int(self.botao.cget("width")) + 2 * espaco
        para_textos = int(evento.width / escala) - (tema.TAMANHO_QUADRO_ICONE + 2 * espaco) - largura_botoes
        embaixo = para_textos < self.LARGURA_MINIMA_TEXTOS
        if embaixo == self.botoes_embaixo:
            return
        self.botoes_embaixo = embaixo
        if embaixo:
            self._textos.grid(pady=(espaco, 6), padx=(0, espaco))
            self._botoes.grid(row=1, column=1, columnspan=2, sticky="w", padx=(0, espaco),
                                        pady=(0, espaco))
        else:
            self._textos.grid(pady=espaco, padx=0)
            self._botoes.grid(row=0, column=2, columnspan=1, sticky="", padx=espaco, pady=espaco)

    def _ajustar_quebra(self, evento) -> None:
        escala = ctk.ScalingTracker.get_widget_scaling(self)
        largura = int(evento.width / escala) - 8
        if largura > 60:
            for rotulo in (self.rotulo_rotulo, self.rotulo_nome, self.rotulo_confirmacao):
                _quebrar_em(rotulo, largura)

    # --- dados ---

    @property
    def caminhos(self) -> list[Path]:
        return list(self._caminhos)

    @property
    def caminho(self) -> Path | None:
        return self._caminhos[0] if self._caminhos else None

    @property
    def preenchido(self) -> bool:
        return bool(self._caminhos)

    def definir_caminhos(self, caminhos, avisar: bool = True) -> None:
        """Define o(s) caminho(s) escolhido(s). avisar=True chama ao_mudar (como uma escolha do usuário)."""
        if isinstance(caminhos, (str, Path)):
            caminhos = [caminhos]
        self._caminhos = [Path(c) for c in caminhos if c]
        self.status_confirmacao = None
        self._atualizar()
        if avisar and self.ao_mudar:
            self.ao_mudar(self.caminhos)

    def limpar(self) -> None:
        """Tira a seleção sem avisar o módulo (usado pelo "Novo", que já limpa tudo)."""
        self.definir_caminhos([], avisar=False)

    def limpar_pelo_usuario(self) -> None:
        """Botão "Limpar": tira a seleção e avisa o módulo (ao_mudar([])), como uma escolha."""
        self.definir_caminhos([], avisar=True)

    def definir_carregando(self, texto: str) -> None:
        """Enquanto o módulo lê o arquivo em segundo plano: o texto suave e uma barrinha em movimento embaixo
        (sem ela, uma leitura demorada parecia a tela travada). Some na próxima definir_confirmacao."""
        self.definir_confirmacao(texto, None)
        if self.barra_carregando is None:
            self.barra_carregando = ctk.CTkProgressBar(
                self._textos, mode="indeterminate", height=tema.ALTURA_BARRA_CARTAO,
                progress_color=tema.COR_PRINCIPAL, fg_color=tema.COR_PRINCIPAL_SUAVE,
                corner_radius=tema.ALTURA_BARRA_CARTAO)
        self.barra_carregando.pack(anchor="w", fill="x", pady=(4, 0))
        self.barra_carregando.start()

    @property
    def carregando(self) -> bool:
        return self.barra_carregando is not None and self.barra_carregando.winfo_manager() == "pack"

    def _parar_carregando(self) -> None:
        if self.carregando:
            self.barra_carregando.stop()
            self.barra_carregando.pack_forget()

    def destroy(self):
        if self.barra_carregando is not None:
            self.barra_carregando.stop()
        super().destroy()

    def definir_confirmacao(self, texto: str, status: str | None = "ok") -> None:
        """Linha abaixo do nome: status "ok" (verde), "atencao" (laranja), "erro" (vermelho) ou None (suave)."""
        self._parar_carregando()
        cor = _tom(status)[0] if status else tema.COR_TEXTO_SUAVE
        self.status_confirmacao = status
        self.rotulo_confirmacao.configure(text=texto, text_color=cor)

    @property
    def texto_nome(self) -> str:
        return self.rotulo_nome.cget("text")

    @property
    def texto_confirmacao(self) -> str:
        return self.rotulo_confirmacao.cget("text")

    # --- tela ---

    def selecionar(self) -> None:
        """Abre o seletor do Windows (arquivo, arquivos ou pasta)."""
        opcoes = {"title": self.titulo_dialogo}
        if self.pasta_inicial is not None and Path(self.pasta_inicial).is_dir():
            opcoes["initialdir"] = str(self.pasta_inicial)
        if self.tipo == "pasta":
            escolha = filedialog.askdirectory(**opcoes)
            escolhidos = [escolha] if escolha else []
        elif self.tipo == "arquivos":
            escolhidos = list(filedialog.askopenfilenames(filetypes=self.tipos_arquivo, **opcoes))
        else:
            escolha = filedialog.askopenfilename(filetypes=self.tipos_arquivo, **opcoes)
            escolhidos = [escolha] if escolha else []
        if escolhidos:
            if self.acumular:
                escolhidos = list(dict.fromkeys([*self._caminhos, *(Path(e) for e in escolhidos)]))
            self.definir_caminhos(escolhidos)

    def _texto_botao(self, preenchido: bool) -> str:
        if self.acumular:
            return "Adicionar arquivos"
        return "Trocar" if preenchido else "Selecionar"

    def _atualizar(self) -> None:
        self._parar_carregando()
        if self._caminhos:
            self.rotulo_nome.configure(text=_nomes_curtos(self._caminhos))
            self.botao.configure(text=self._texto_botao(True))
            self.rotulo_confirmacao.configure(text="", text_color=tema.COR_TEXTO_SUAVE)
            self.botao_limpar.pack(pady=(4, 0))
        else:
            vazio = self.TEXTO_SEM_PASTA if self.tipo == "pasta" else self.TEXTO_SEM_ARQUIVO
            self.rotulo_nome.configure(text="—")
            self.botao.configure(text=self._texto_botao(False))
            self.rotulo_confirmacao.configure(text=vazio, text_color=tema.COR_TEXTO_SUAVE)
            self.botao_limpar.pack_forget()

    @property
    def mostra_limpar(self) -> bool:
        return self.botao_limpar.winfo_manager() == "pack"


def _nomes_curtos(caminhos: list[Path], maximo: int = 3) -> str:
    """Nomes dos arquivos para exibir: até `maximo` nomes; o resto vira "e mais N"."""
    nomes = [c.name or str(c) for c in caminhos]
    if len(nomes) <= maximo:
        return "\n".join(nomes)
    return "\n".join(nomes[:maximo]) + f"\ne mais {len(nomes) - maximo}"


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------


class NumeroResumo(ctk.CTkFrame):
    """Número grande sobre fundo suave, com legenda de 12 px. Usado em grupos de 3."""

    MARGEM = 16           # margem interna, dos lados
    MARGEM_MINIMA = 6     # na janela mínima a margem encolhe para a palavra mais comprida caber inteira

    def __init__(self, pai, numero, legenda: str, tom: str = "principal"):
        forte, suave = _tom(tom)
        super().__init__(pai, fg_color=suave, corner_radius=tema.RAIO_BOTAO)
        self.margem = self.MARGEM
        self._largura = 0
        self.fonte_numero = tema.fonte_numero_grande()
        self.fonte_numero_minima = tema.fonte_numero_grande(tema.TAMANHO_NUMERO_GRANDE_MINIMO)   # só para medir
        self.rotulo_numero = ctk.CTkLabel(self, text=str(numero), font=self.fonte_numero,
                                          text_color=forte, anchor="w")
        self.rotulo_numero.pack(anchor="w", padx=self.margem, pady=(12, 0))
        self.rotulo_legenda = ctk.CTkLabel(self, text=legenda, font=tema.fonte_legenda(),
                                           text_color=tema.COR_TEXTO_SUAVE, anchor="w", justify="left",
                                           wraplength=120)
        self.rotulo_legenda.pack(anchor="w", fill="x", padx=self.margem, pady=(0, 12))
        # a legenda quebra a linha conforme a largura real do bloco (evita texto cortado)
        self.bind("<Configure>", self._ajustar_quebra, add="+")

    def _maior_palavra(self) -> int:
        """Largura (em px da tela, sem a escala do Windows) da palavra mais comprida da legenda."""
        fonte = self.rotulo_legenda.cget("font")
        escala = ctk.ScalingTracker.get_widget_scaling(self)
        palavras = str(self.rotulo_legenda.cget("text")).split() or [""]
        return max(int(fonte.measure(p) / escala) for p in palavras) + 2

    def _ajustar_quebra(self, evento=None) -> None:
        if evento is not None:
            self._largura = int(evento.width / ctk.ScalingTracker.get_widget_scaling(self))
        if not self._largura:
            return
        # o Windows quebra no meio da palavra quando ela não cabe ("Não encontrado s", visto em Rescisões
        # na janela mínima): aí a margem encolhe até a palavra caber
        margem = self.MARGEM
        maior = max(self._maior_palavra(), self._largura_numero(self.fonte_numero_minima))
        if self._largura - 2 * margem < maior:
            margem = max(self.MARGEM_MINIMA, (self._largura - maior) // 2)
        if margem != self.margem:
            self.margem = margem
            self.rotulo_numero.pack(padx=margem)
            self.rotulo_legenda.pack(padx=margem)
        largura = self._largura - 2 * margem
        if largura > 40:
            _quebrar_em(self.rotulo_legenda, largura)
        self._ajustar_numero(largura)

    def _largura_numero(self, fonte: ctk.CTkFont | None = None) -> int:
        """Largura (em px da tela, sem a escala do Windows) do número na fonte dada (padrão: a atual)."""
        escala = ctk.ScalingTracker.get_widget_scaling(self)
        fonte = fonte or self.fonte_numero
        return int(fonte.measure(str(self.rotulo_numero.cget("text"))) / escala) + 2

    def _ajustar_numero(self, largura: int) -> None:
        """Número que não cabe no quadro (ex.: "R$ -810,50" na janela pequena) diminui a fonte até caber; com a
        janela maior, volta ao tamanho normal."""
        tamanho = tema.TAMANHO_NUMERO_GRANDE
        self.fonte_numero.configure(size=tamanho)
        while tamanho > tema.TAMANHO_NUMERO_GRANDE_MINIMO and self._largura_numero() > largura:
            tamanho -= 1
            self.fonte_numero.configure(size=tamanho)

    def atualizar(self, numero, legenda: str | None = None, tom: str | None = None) -> None:
        self.rotulo_numero.configure(text=str(numero))
        self._ajustar_quebra()
        if legenda is not None:
            self.rotulo_legenda.configure(text=legenda)
            self._ajustar_quebra()
        if tom is not None:
            forte, suave = _tom(tom)
            self.configure(fg_color=suave)
            self.rotulo_numero.configure(text_color=forte)


class GrupoNumeros(ctk.CTkFrame):
    """Linha de NumeroResumo lado a lado, com a mesma largura."""

    def __init__(self, pai, numeros: list[tuple] | None = None):
        super().__init__(pai, fg_color="transparent")
        self.blocos: list[NumeroResumo] = []
        if numeros:
            self.definir(numeros)

    def definir(self, numeros: list[tuple]) -> None:
        """numeros = [(numero, legenda, tom), ...] (tom opcional)."""
        _limpar(self)
        self.blocos = []
        for coluna, item in enumerate(numeros):
            numero, legenda, *resto = item
            bloco = NumeroResumo(self, numero, legenda, resto[0] if resto else "principal")
            bloco.grid(row=0, column=coluna, sticky="nsew",
                       padx=(0 if coluna == 0 else tema.ESPACO_PEQUENO // 2,
                             0 if coluna == len(numeros) - 1 else tema.ESPACO_PEQUENO // 2))
            self.grid_columnconfigure(coluna, weight=1, uniform="numeros")
            self.blocos.append(bloco)


class SeloStatus(ctk.CTkLabel):
    """"Pílula" pequena: texto em negrito sobre fundo suave da mesma cor (OK, ATENÇÃO, ERRO, Concluído)."""

    def __init__(self, pai, texto: str, status: str = "ok"):
        forte, suave = _tom(status)
        super().__init__(pai, text=texto, font=tema.fonte_rotulo(), text_color=forte, fg_color=suave,
                         corner_radius=tema.ALTURA_SELO // 2, height=tema.ALTURA_SELO)
        self.status = status

    def atualizar(self, texto: str, status: str) -> None:
        forte, suave = _tom(status)
        self.status = status
        self.configure(text=texto, text_color=forte, fg_color=suave)


@dataclass
class Coluna:
    titulo: str
    numero: bool = False    # True: fonte de números, alinhada à direita
    peso: int = 1           # largura relativa


class TabelaSimples(ctk.CTkFrame):
    """Tabela curta de resumo (até ~15 linhas): cabeçalho suave, separadores finos, números à direita."""

    ESPACO_COLUNAS = 8

    def __init__(self, pai, colunas: list[Coluna], linhas: list[tuple] | None = None):
        super().__init__(pai, fg_color="transparent")
        self.colunas = colunas
        self.linhas: list[tuple] = []
        self._rotulos_texto: dict[int, list] = {}
        # Cada coluna fica com a largura proporcional ao peso. Na janela mínima, uma coluna de valores
        # nunca fica mais estreita que o maior valor dela (antes, "5.838.244,51" aparecia ".838.244,51"):
        # quem cede espaço são as colunas de texto, que quebram a linha entre as palavras.
        for indice, coluna in enumerate(colunas):
            self.grid_columnconfigure(indice, weight=coluna.peso)
        self.bind("<Configure>", self._distribuir, add="+")
        self.definir_linhas(linhas or [])

    def definir_linhas(self, linhas: list[tuple]) -> None:
        _limpar(self)
        self.linhas = [tuple(l) for l in linhas]
        self._rotulos_texto = {indice: [] for indice, coluna in enumerate(self.colunas) if not coluna.numero}
        for indice, coluna in enumerate(self.colunas):
            titulo = ctk.CTkLabel(self, text=coluna.titulo, font=tema.fonte_legenda(),
                                  text_color=tema.COR_TEXTO_SUAVE, anchor="e" if coluna.numero else "w",
                                  justify="right" if coluna.numero else "left")
            titulo.grid(row=0, column=indice, sticky="ew", padx=self._espaco(indice), pady=(0, 6))
            if not coluna.numero:
                self._rotulos_texto[indice].append(titulo)
        linha_grade = 1
        for valores in self.linhas:
            self._separador(linha_grade)
            linha_grade += 1
            for indice, (coluna, valor) in enumerate(zip(self.colunas, valores)):
                rotulo = ctk.CTkLabel(self, text="" if valor is None else str(valor),
                                      font=tema.fonte_numero() if coluna.numero else tema.fonte_texto(),
                                      text_color=tema.COR_TEXTO, anchor="e" if coluna.numero else "w",
                                      justify="left")
                rotulo.grid(row=linha_grade, column=indice, sticky="ew", padx=self._espaco(indice), pady=6)
                if not coluna.numero:
                    self._rotulos_texto[indice].append(rotulo)
            linha_grade += 1
        self._largura = 0
        if self.winfo_width() > 1:
            self._distribuir()

    def _espaco(self, indice: int) -> tuple[int, int]:
        return (0 if indice == 0 else self.ESPACO_COLUNAS, 0)

    def _largura_do_texto(self, rotulo) -> int:
        escala = ctk.ScalingTracker.get_widget_scaling(self)
        return int(rotulo.cget("font").measure(rotulo.cget("text")) / escala) + 2

    def _distribuir(self, evento=None) -> None:
        """Divide a largura entre as colunas: proporcional ao peso, mas cada coluna de valores com pelo menos
        a largura do maior valor; as colunas de texto ficam com o resto e quebram a linha nele."""
        escala = ctk.ScalingTracker.get_widget_scaling(self)
        largura = int((evento.width if evento is not None else self.winfo_width()) / escala)
        if largura <= 1 or abs(largura - getattr(self, "_largura", 0)) <= TOLERANCIA_QUEBRA:
            return
        self._largura = largura
        util = largura - self.ESPACO_COLUNAS * (len(self.colunas) - 1)
        minimos = {}
        for indice, coluna in enumerate(self.colunas):
            if coluna.numero:
                rotulos = [r for r in self.grid_slaves(column=indice) if isinstance(r, ctk.CTkLabel)]
                minimos[indice] = max((self._largura_do_texto(r) for r in rotulos), default=0)
        peso_total = sum(c.peso for c in self.colunas) or 1
        larguras = {i: util * c.peso / peso_total for i, c in enumerate(self.colunas)}
        falta = sum(max(0, minimos[i] - larguras[i]) for i in minimos)
        if falta:
            for i in minimos:
                larguras[i] = max(larguras[i], minimos[i])
            textos = [i for i in larguras if i not in minimos]
            peso_textos = sum(self.colunas[i].peso for i in textos) or 1
            for i in textos:
                larguras[i] = max(40, larguras[i] - falta * self.colunas[i].peso / peso_textos)
        for indice, coluna in enumerate(self.colunas):
            # largura fixa (minsize + peso zero): a grade não redistribui pelo tamanho dos textos
            self.grid_columnconfigure(indice, minsize=int(larguras[indice] * escala), weight=0)
            if not coluna.numero:
                for rotulo in self._rotulos_texto.get(indice, []):
                    _quebrar_em(rotulo, max(20, int(larguras[indice]) - 2))

    def _separador(self, linha: int) -> None:
        Separador(self).grid(row=linha, column=0, columnspan=len(self.colunas), sticky="ew")


class TextoQuebravel(ctk.CTkFrame):
    """Texto que quebra a linha entre as palavras conforme a largura que recebe (use com pack(fill="x")).

    Um CTkLabel comum não quebra: na janela mínima o fim do texto era cortado (ex.: "unidade · mês" no
    resultado de Rescisões). A largura é a deste quadro, não a do rótulo: o aviso de tamanho de um CTkLabel
    vem do texto de dentro, que encolhe a cada quebra (o texto ia ficando cada vez mais estreito e a janela
    travava)."""

    def __init__(self, pai, texto: str, fonte=None, cor=tema.COR_TEXTO):
        super().__init__(pai, fg_color="transparent", width=1, height=1)
        self.rotulo = ctk.CTkLabel(self, text=texto, font=fonte or tema.fonte_texto(), text_color=cor,
                                   anchor="w", justify="left", wraplength=1000)
        self.rotulo.pack(fill="x")
        self.bind("<Configure>", self._ajustar_quebra, add="+")

    @property
    def texto(self) -> str:
        return self.rotulo.cget("text")

    def _ajustar_quebra(self, evento) -> None:
        largura = int(evento.width / ctk.ScalingTracker.get_widget_scaling(self)) - 4
        if largura > 40:
            _quebrar_em(self.rotulo, largura)


class LinhaConferencia(ctk.CTkFrame):
    """Ícone (check verde, alerta laranja ou erro vermelho) + texto, com valor opcional à direita."""

    def __init__(self, pai, texto: str, status: str = "ok", valor: str | None = None):
        super().__init__(pai, fg_color="transparent")
        self.status = status
        cor = _tom(status)[0]
        self.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self, text="", image=icones.icone(ICONE_DO_STATUS[status], cor, tema.TAMANHO_ICONE_CONFERENCIA)
                     ).grid(row=0, column=0, padx=(0, 10), sticky="n", pady=2)
        self.rotulo_texto = ctk.CTkLabel(self, text=texto, font=tema.fonte_texto(), text_color=tema.COR_TEXTO,
                                         anchor="w", justify="left", wraplength=380)
        self.rotulo_texto.grid(row=0, column=1, sticky="ew")
        self.rotulo_valor: ctk.CTkLabel | None = None
        if valor is not None:
            self.rotulo_valor = ctk.CTkLabel(self, text=valor, font=tema.fonte_numero(), text_color=tema.COR_TEXTO,
                                             anchor="e")
            self.rotulo_valor.grid(row=0, column=2, padx=(10, 0), sticky="e")
        # o texto quebra conforme a largura real (com 380 px fixos, na janela mínima o fim era cortado)
        self.bind("<Configure>", self._ajustar_quebra, add="+")

    def _ajustar_quebra(self, evento) -> None:
        escala = ctk.ScalingTracker.get_widget_scaling(self)
        largura = int(evento.width / escala) - tema.TAMANHO_ICONE_CONFERENCIA - 10 - 4
        if self.rotulo_valor is not None:
            largura -= int(self.rotulo_valor.winfo_reqwidth() / escala) + 10
        if largura > 60:
            _quebrar_em(self.rotulo_texto, largura)


class EstadoVazio(ctk.CTkFrame):
    """Ícone grande em quadrado suave, título curto e frase de orientação, centralizados."""

    def __init__(self, pai, titulo: str, frase: str, icone: str = "caixa", tom: str = "principal"):
        super().__init__(pai, fg_color="transparent")
        forte, suave = _tom(tom)
        quadro = ctk.CTkFrame(self, width=tema.TAMANHO_QUADRO_VAZIO, height=tema.TAMANHO_QUADRO_VAZIO,
                              fg_color=suave, corner_radius=tema.RAIO_CARTAO)
        quadro.pack(pady=(24, 16))
        quadro.pack_propagate(False)
        ctk.CTkLabel(quadro, text="", image=icones.icone(icone, forte, tema.TAMANHO_ICONE_VAZIO)
                     ).place(relx=0.5, rely=0.5, anchor="center")
        self.rotulo_titulo = ctk.CTkLabel(self, text=titulo, font=tema.fonte_subtitulo(), text_color=tema.COR_TEXTO)
        self.rotulo_titulo.pack()
        self.rotulo_frase = ctk.CTkLabel(self, text=frase, font=tema.fonte_texto(), text_color=tema.COR_TEXTO_SUAVE,
                                         wraplength=360, justify="center")
        self.rotulo_frase.pack(pady=(6, 24))
        # a frase acompanha a largura do cartão (na janela mínima ele tem menos de 360 px)
        self.bind("<Configure>", self._ajustar_quebra, add="+")

    def _ajustar_quebra(self, evento) -> None:
        largura = min(360, max(160, evento.width - 24))
        _quebrar_em(self.rotulo_frase, largura)


class BarraProgresso(ctk.CTkFrame):
    """Barra na cor principal + texto da etapa atual ("Lendo patrimônio...").

    atualizar(texto, fracao): fracao de 0 a 1; None = andamento sem porcentagem (barra em movimento).
    Deve ser chamada na thread da janela (ver central/segundo_plano.py).
    """

    def __init__(self, pai, texto: str = "Preparando..."):
        super().__init__(pai, fg_color="transparent")
        self.rotulo = ctk.CTkLabel(self, text=texto, font=tema.fonte_texto(), text_color=tema.COR_TEXTO, anchor="w")
        self.rotulo.pack(anchor="w", fill="x", pady=(0, 8))
        self.barra = ctk.CTkProgressBar(self, height=tema.ALTURA_BARRA_PROGRESSO, progress_color=tema.COR_PRINCIPAL,
                                        fg_color=tema.COR_PRINCIPAL_SUAVE, corner_radius=tema.ALTURA_BARRA_PROGRESSO)
        self.barra.pack(fill="x")
        self.barra.set(0)
        self.fracao: float | None = 0.0
        self._em_movimento = False

    def atualizar(self, texto: str | None = None, fracao: float | None = None) -> None:
        if texto:
            self.rotulo.configure(text=texto.strip())
        if fracao is None:
            if not self._em_movimento:
                self.barra.configure(mode="indeterminate")
                self.barra.start()
                self._em_movimento = True
        else:
            if self._em_movimento:
                self.barra.stop()
                self.barra.configure(mode="determinate")
                self._em_movimento = False
            self.barra.set(max(0.0, min(1.0, float(fracao))))
        self.fracao = fracao

    @property
    def texto(self) -> str:
        return self.rotulo.cget("text")

    def destroy(self):
        if self._em_movimento:
            self.barra.stop()
        super().destroy()


class CartaoResultado(Cartao):
    """Cartão "Resultado" do layout padrão, com três estados (GUIA_VISUAL, seção 5):

    - mostrar_vazio(): EstadoVazio antes de processar;
    - mostrar_andamento(): BarraProgresso durante o processamento (devolve a barra);
    - mostrar_conteudo(): área limpa para o módulo preencher depois (números, tabela, conferências).
    O selo ("Concluído") fica ao lado do título; os botões do rodapé vão em `rodape`.
    """

    def __init__(self, pai, titulo: str = "Resultado"):
        super().__init__(pai, titulo=titulo)
        self.selo: SeloStatus | None = None
        self.area = ctk.CTkFrame(self.corpo, fg_color="transparent")
        self.area.pack(fill="both", expand=True)
        self.rodape = _frame_vazio(self.corpo)
        self.barra: BarraProgresso | None = None
        self.estado = ""

    def definir_selo(self, texto: str | None, status: str = "ok") -> None:
        if self.selo is not None:
            self.selo.destroy()
            self.selo = None
        if texto:
            self.selo = SeloStatus(self.cabecalho, texto, status)
            self.selo.pack(side="left", padx=(12, 0))

    def _trocar(self, estado: str, mostrar_rodape: bool) -> ctk.CTkFrame:
        _limpar(self.area)
        self.barra = None
        self.estado = estado
        if mostrar_rodape:
            self.rodape.pack(fill="x", pady=(tema.ESPACO_ENTRE_BLOCOS, 0))
        else:
            self.rodape.pack_forget()
        return self.area

    def mostrar_vazio(self, titulo: str = "Nenhum resultado ainda",
                      frase: str = "Selecione os arquivos de entrada e clique no botão para processar.",
                      icone: str = "caixa", tom: str = "principal") -> EstadoVazio:
        self.definir_selo(None)
        area = self._trocar("vazio", mostrar_rodape=False)
        vazio = EstadoVazio(area, titulo, frase, icone, tom)
        vazio.pack(fill="both", expand=True)
        return vazio

    def mostrar_andamento(self, texto: str = "Preparando...") -> BarraProgresso:
        self.definir_selo(None)
        area = self._trocar("andamento", mostrar_rodape=False)
        self.barra = BarraProgresso(area, texto)
        self.barra.pack(fill="x", pady=(24, 24))
        return self.barra

    def mostrar_conteudo(self, mostrar_rodape: bool = True) -> ctk.CTkFrame:
        return self._trocar("concluido", mostrar_rodape)


class Abas(ctk.CTkFrame):
    """Linha de abas de um módulo (ex.: "Conciliação de clientes" | "Import Contábil").

    A aba ativa fica com fundo suave, borda e texto na cor principal; as outras, com borda fina.
    ao_trocar(nome) é chamado quando o usuário escolhe outra aba.
    """

    def __init__(self, pai, nomes: list[str], ao_trocar: Callable[[str], None] | None = None):
        super().__init__(pai, fg_color="transparent")
        self.ao_trocar = ao_trocar
        self.botoes: dict[str, ctk.CTkButton] = {}
        for nome in nomes:
            botao = ctk.CTkButton(self, text=nome, command=lambda n=nome: self.selecionar(n, avisar=True),
                                  width=tema.LARGURA_MINIMA_ABA, height=tema.ALTURA_BOTAO_PEQUENO,
                                  corner_radius=tema.RAIO_PEQUENO, border_width=tema.LARGURA_BORDA,
                                  font=tema.fonte_texto())
            botao.pack(side="left", padx=(0, tema.ESPACO_PEQUENO // 2))
            self.botoes[nome] = botao
        self.atual: str | None = None
        if nomes:
            self.selecionar(nomes[0])

    def selecionar(self, nome: str, avisar: bool = False) -> None:
        if nome not in self.botoes:
            raise ValueError(f"Aba desconhecida: {nome!r}")
        for chave, botao in self.botoes.items():
            if chave == nome:
                botao.configure(fg_color=tema.COR_PRINCIPAL_SUAVE, hover_color=tema.COR_PRINCIPAL_SUAVE,
                                border_color=tema.COR_PRINCIPAL, text_color=tema.COR_PRINCIPAL,
                                font=tema.fonte_texto_forte())
            else:
                botao.configure(fg_color="transparent", hover_color=tema.COR_PRINCIPAL_SUAVE,
                                border_color=tema.COR_BORDA, text_color=tema.COR_TEXTO, font=tema.fonte_texto())
        mudou = nome != self.atual
        self.atual = nome
        if avisar and mudou and self.ao_trocar:
            self.ao_trocar(nome)


# ---------------------------------------------------------------------------
# Rodapé do resultado e janela de avisos (trazidos do Conciliações AMES)
# ---------------------------------------------------------------------------


def botoes_da_planilha(rodape, caminho_relatorio: Path | None, abrir_planilha: Callable[[], None],
                       abrir_pasta: Callable[[], None], ver_avisos: Callable[[], None]) -> None:
    """Rodapé do resultado das conciliações: "Abrir planilha" em cima, na largura toda; "Abrir pasta"
    e "Ver avisos" lado a lado embaixo. (Os três numa linha só ficavam cortados na janela mínima.)"""
    _limpar(rodape)
    for coluna in (0, 1):
        rodape.grid_columnconfigure(coluna, weight=1, uniform="botoes")
    botao_abrir = BotaoPrincipal(rodape, "Abrir planilha", abrir_planilha, icone="arquivo")
    botao_abrir.habilitar(caminho_relatorio is not None)
    botao_abrir.grid(row=0, column=0, columnspan=2, sticky="ew")
    for coluna, (texto, comando, icone) in enumerate((("Abrir pasta", abrir_pasta, "pasta"),
                                                      ("Ver avisos", ver_avisos, "alerta"))):
        botao = BotaoSecundario(rodape, texto, comando, icone=icone)
        botao.configure(width=1)
        botao.grid(row=1, column=coluna, sticky="ew", pady=(tema.ESPACO_PEQUENO, 0),
                   padx=(0 if coluna == 0 else tema.ESPACO_PEQUENO, 0))


def rotulo_arquivo_salvo(area, caminho_relatorio: Path | None) -> None:
    """"Salvo como" e, na linha de baixo, o nome inteiro do arquivo (quebrado no meio ficava "….xl / sx")."""
    if caminho_relatorio is not None:
        ctk.CTkLabel(area, text=f"Salvo como\n{caminho_relatorio.name}", font=tema.fonte_legenda(),
                     text_color=tema.COR_TEXTO_SUAVE, anchor="w", justify="left"
                     ).pack(fill="x", pady=(tema.ESPACO_PEQUENO, 0))


class JanelaTexto(ctk.CTkToplevel):
    """Janela secundária com um texto só para ler (ex.: os avisos do último processamento).

    O módulo monta as linhas; a janela só mostra (a Central não conhece os avisos de cada módulo).
    """

    def __init__(self, pai, titulo: str, titulo_cartao: str, linhas: list[str]):
        super().__init__(pai, fg_color=tema.COR_FUNDO)
        self.title(titulo)
        self.geometry("820x520")
        self.transient(pai)
        # o CustomTkinter troca o ícone das janelas secundárias logo depois de abrir
        self.after(250, lambda: aplicar_icone(self))

        cartao = Cartao(self, titulo_cartao)
        cartao.pack(fill="both", expand=True, padx=tema.ESPACO_ENTRE_BLOCOS, pady=tema.ESPACO_ENTRE_BLOCOS)
        self.caixa = ctk.CTkTextbox(cartao.corpo, font=tema.fonte_texto(), fg_color=tema.COR_FUNDO,
                                    text_color=tema.COR_TEXTO, border_width=tema.LARGURA_BORDA,
                                    border_color=tema.COR_BORDA, corner_radius=tema.RAIO_PEQUENO, wrap="word")
        self.caixa.pack(fill="both", expand=True)
        self.caixa.insert("1.0", "\n".join(linhas))
        self.caixa.configure(state="disabled")

        BotaoSecundario(cartao.corpo, "Fechar", self.destroy, altura=tema.ALTURA_BOTAO_PEQUENO
                        ).pack(anchor="e", pady=(tema.ESPACO_PEQUENO, 0))
        self.after(100, self.lift)

    @property
    def texto(self) -> str:
        return self.caixa.get("1.0", "end").rstrip("\n")
