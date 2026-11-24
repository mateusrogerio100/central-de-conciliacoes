"""Janela principal da Central: menu lateral + área do módulo escolhido (GUIA_VISUAL, seções 1 e 2).

A janela não conhece o conteúdo dos módulos: monta o menu a partir de registro.carregar_modulos()
(um item por módulo, agrupados pelas seções do registro) e, na primeira vez que um módulo é aberto,
chama o criar_painel dele. O painel é guardado, então ao trocar de módulo e voltar, o que já estava
escolhido continua lá (ESPECIFICACAO, seção 4.4). Um módulo com erro aparece no menu com a
explicação do problema; os outros funcionam normalmente.
"""

from __future__ import annotations

import getpass
import traceback
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from central import VERSAO, icones, log_uso, registro, tema
from central.componentes import AreaRolavel, Cartao, CabecalhoModulo, EstadoVazio, LinhaConferencia, aplicar_icone
from central.preferencias import MODO_CLARO, MODO_ESCURO, Preferencias, ler_preferencias, salvar_preferencias
from central.registro import ModuloCarregado

TITULO_JANELA = "Central de Conciliações"
NOME_INSTITUICAO = "Hospital Exemplo"
MODO_CTK = {MODO_CLARO: "light", MODO_ESCURO: "dark"}


def usuario_do_windows() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Menu lateral
# ---------------------------------------------------------------------------


class ItemMenu(ctk.CTkButton):
    """Um módulo no menu: ícone 18 px + nome. Ativo = fundo destacado e negrito."""

    def __init__(self, pai, modulo: ModuloCarregado, comando):
        self.modulo = modulo
        nome_icone = modulo.info.icone if modulo.ok else "alerta"
        self._icone_normal = icones.icone(nome_icone, tema.COR_MENU_TEXTO, tema.TAMANHO_ICONE_MENU)
        self._icone_ativo = icones.icone(nome_icone, tema.COR_MENU_TEXTO_ATIVO, tema.TAMANHO_ICONE_MENU)
        super().__init__(pai, text=modulo.nome, command=comando, image=self._icone_normal, compound="left",
                         anchor="w", height=tema.ALTURA_ITEM_MENU, corner_radius=tema.RAIO_PEQUENO,
                         fg_color="transparent", hover_color=tema.COR_MENU_ITEM_HOVER,
                         text_color=tema.COR_MENU_TEXTO, font=tema.fonte_texto(), border_spacing=10)
        self.ativo = False

    def marcar(self, ativo: bool) -> None:
        self.ativo = ativo
        if ativo:
            self.configure(fg_color=tema.COR_MENU_ITEM_ATIVO, hover_color=tema.COR_MENU_ITEM_ATIVO,
                           text_color=tema.COR_MENU_TEXTO_ATIVO, font=tema.fonte_texto_forte(),
                           image=self._icone_ativo)
        else:
            self.configure(fg_color="transparent", hover_color=tema.COR_MENU_ITEM_HOVER,
                           text_color=tema.COR_MENU_TEXTO, font=tema.fonte_texto(), image=self._icone_normal)


class MenuLateral(ctk.CTkFrame):
    def __init__(self, pai, modulos: list[ModuloCarregado], ao_escolher, ao_alternar_modo, modo: str):
        super().__init__(pai, width=tema.LARGURA_MENU, fg_color=tema.COR_MENU_FUNDO, corner_radius=0)
        self.pack_propagate(False)
        espaco = 20

        # 1. Marca (fixa no alto)
        marca = ctk.CTkFrame(self, fg_color="transparent")
        marca.pack(fill="x", padx=espaco, pady=tema.ESPACO_MARCA_MENU)
        quadro = ctk.CTkFrame(marca, width=tema.TAMANHO_MARCA, height=tema.TAMANHO_MARCA,
                              fg_color=tema.COR_MARCA, corner_radius=tema.RAIO_BOTAO)
        quadro.pack(side="left")
        quadro.pack_propagate(False)
        imagem_logo = icones.logo(tema.TAMANHO_MARCA - 8) or icones.icone("mais", tema.COR_MENU_FUNDO, 22)
        ctk.CTkLabel(quadro, text="", image=imagem_logo).place(relx=0.5, rely=0.5, anchor="center")
        textos_marca = ctk.CTkFrame(marca, fg_color="transparent")
        textos_marca.pack(side="left", padx=(12, 0))
        ctk.CTkLabel(textos_marca, text=TITULO_JANELA, font=tema.fonte_marca(), text_color=tema.COR_MENU_TEXTO_ATIVO,
                     anchor="w", justify="left", wraplength=tema.LARGURA_MENU - 100).pack(anchor="w")
        ctk.CTkLabel(textos_marca, text=NOME_INSTITUICAO, font=tema.fonte_legenda(), text_color=tema.COR_MENU_SECAO,
                     anchor="w").pack(anchor="w")

        # 6. Rodapé fixo (de baixo para cima): usuário + versão e o botão de modo. Vêm antes da área
        # rolável para nunca serem espremidos quando a janela é baixa.
        rodape = " · ".join(t for t in (usuario_do_windows(), f"versão {VERSAO}") if t)
        self.rotulo_rodape = ctk.CTkLabel(self, text=rodape, font=tema.fonte_legenda(),
                                          text_color=tema.COR_MENU_SECAO, anchor="w")
        self.rotulo_rodape.pack(side="bottom", fill="x", padx=espaco + 4, pady=(8, 20))

        # 5. Modo claro/escuro
        self.botao_modo = ctk.CTkButton(self, text="", command=ao_alternar_modo, height=tema.ALTURA_BOTAO_PEQUENO,
                                        corner_radius=tema.RAIO_PEQUENO, fg_color="transparent",
                                        hover_color=tema.COR_MENU_ITEM_HOVER, border_width=tema.LARGURA_BORDA,
                                        border_color=tema.COR_MENU_BORDA, text_color=tema.COR_MENU_TEXTO,
                                        font=tema.fonte_texto(), compound="left")
        self.botao_modo.pack(side="bottom", fill="x", padx=12, pady=(tema.ESPACO_PEQUENO, 0))
        self.mostrar_modo(modo)

        # 2 e 3. Seções e um item por módulo, no meio, numa área que rola quando não cabem
        self.area = AreaRolavel(self, tema.COR_MENU_FUNDO, tema.COR_MENU_BORDA, tema.COR_MENU_SECAO)
        self.area.pack(fill="both", expand=True)
        self.secoes: list[str] = []
        self.itens: dict[str, ItemMenu] = {}
        for modulo in modulos:
            if not self.secoes or self.secoes[-1] != modulo.secao:
                self._secao(modulo.secao, espaco, primeira=not self.secoes)
            item = ItemMenu(self.area.conteudo, modulo, lambda chave=modulo.chave: ao_escolher(chave))
            item.pack(fill="x", padx=12, pady=tema.ESPACO_ITEM_MENU)
            self.itens[modulo.chave] = item

    def _secao(self, texto: str, espaco: int, primeira: bool) -> None:
        # pouco espaço à direita: o nome da seção cabe inteiro mesmo com a barra de rolagem
        ctk.CTkLabel(self.area.conteudo, text=texto, font=tema.fonte_secao_menu(), text_color=tema.COR_MENU_SECAO,
                     anchor="w").pack(fill="x", padx=(espaco + 4, tema.LARGURA_BARRA_MENU),
                                      pady=(0 if primeira else tema.ESPACO_SECAO_MENU,
                                            tema.ESPACO_ABAIXO_SECAO_MENU))
        self.secoes.append(texto)

    def marcar_ativo(self, chave: str | None) -> None:
        for chave_item, item in self.itens.items():
            item.marcar(chave_item == chave)
        if chave in self.itens:
            # o item aberto fica à vista mesmo com o menu rolado (depois de a janela ser desenhada)
            self.after(100, lambda: self.area.mostrar(self.itens[chave]))

    def mostrar_modo(self, modo: str) -> None:
        """O botão oferece o modo contrário ao atual."""
        if modo == MODO_ESCURO:
            texto, nome_icone = "Modo claro", "sol"
        else:
            texto, nome_icone = "Modo escuro", "lua"
        self.botao_modo.configure(text=texto,
                                  image=icones.icone(nome_icone, tema.COR_MENU_TEXTO, tema.TAMANHO_ICONE_MENU))


# ---------------------------------------------------------------------------
# Janela
# ---------------------------------------------------------------------------


class PainelModuloComErro(ctk.CTkFrame):
    """Mostrado no lugar do painel quando o módulo não pôde ser carregado ou aberto."""

    def __init__(self, pai, nome: str, mensagem: str, detalhe_tecnico: str = ""):
        super().__init__(pai, fg_color="transparent")
        CabecalhoModulo(self, "Conciliações", nome, "Este módulo não pôde ser aberto.").pack(
            fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))
        cartao = Cartao(self, "O que aconteceu")
        cartao.pack(fill="x")
        LinhaConferencia(cartao.corpo, mensagem, status="erro").pack(fill="x")
        ctk.CTkLabel(cartao.corpo, text="Os outros módulos continuam funcionando normalmente.",
                     font=tema.fonte_texto(), text_color=tema.COR_TEXTO_SUAVE, anchor="w"
                     ).pack(fill="x", pady=(12, 0))
        if detalhe_tecnico:
            ctk.CTkLabel(cartao.corpo, text="Detalhes técnicos (para quem for consertar):", font=tema.fonte_legenda(),
                         text_color=tema.COR_TEXTO_SUAVE, anchor="w").pack(fill="x", pady=(16, 4))
            caixa = ctk.CTkTextbox(cartao.corpo, height=180, font=tema.fonte_numero(), fg_color=tema.COR_FUNDO,
                                   text_color=tema.COR_TEXTO, border_width=tema.LARGURA_BORDA,
                                   border_color=tema.COR_BORDA, corner_radius=tema.RAIO_PEQUENO)
            caixa.pack(fill="x")
            caixa.insert("1.0", detalhe_tecnico)
            caixa.configure(state="disabled")


class JanelaCentral(ctk.CTk):
    def __init__(self, modulos: list[ModuloCarregado] | None = None, caminho_preferencias: Path | None = None,
                 chave_inicial: str | None = None):
        """modulos=None: os do registro, abrindo em registro.MODULO_INICIAL. Com `modulos` (testes e
        demonstração), abre em `chave_inicial` ou, sem ela, no primeiro módulo da lista."""
        self.caminho_preferencias = caminho_preferencias
        self.preferencias: Preferencias = ler_preferencias(caminho_preferencias)
        ctk.set_appearance_mode(MODO_CTK[self.preferencias.modo])
        tema.carregar_fontes()
        super().__init__(fg_color=tema.COR_FUNDO)

        self.title(TITULO_JANELA)
        self.geometry(f"{tema.LARGURA_JANELA}x{tema.ALTURA_JANELA}")
        self.minsize(tema.LARGURA_MINIMA_JANELA, tema.ALTURA_MINIMA_JANELA)
        self._aplicar_icone()
        self.protocol("WM_DELETE_WINDOW", self.ao_fechar)

        modulos_do_registro = modulos is None       # a Central de verdade (não a dos testes nem a demonstração)
        if modulos is None:
            modulos = registro.carregar_modulos()
            chave_inicial = chave_inicial or registro.MODULO_INICIAL
        self.modulos = modulos
        self.paginas: dict[str, ctk.CTkFrame] = {}
        self.paineis: dict[str, object] = {}
        self.modulo_atual: str | None = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.menu = MenuLateral(self, self.modulos, self.selecionar, self.alternar_modo, self.preferencias.modo)
        self.menu.grid(row=0, column=0, sticky="ns")
        self.area_conteudo = ctk.CTkFrame(self, fg_color=tema.COR_FUNDO, corner_radius=0)
        self.area_conteudo.grid(row=0, column=1, sticky="nsew")

        inicial = registro.modulo_inicial(self.modulos, chave_inicial)
        if inicial is None:
            EstadoVazio(self.area_conteudo, "Nenhum módulo no menu",
                        "Os módulos entram no menu pelo arquivo central/registro.py.").pack(expand=True)
        else:
            self.selecionar(inicial.chave)
        if modulos_do_registro:
            log_uso.registrar(log_uso.MODULO_CENTRAL, log_uso.ACAO_ABRIR)   # pedido da chefia: quem usou e quando

    # --- módulos ---

    def modulo(self, chave: str) -> ModuloCarregado | None:
        return next((m for m in self.modulos if m.chave == chave), None)

    def selecionar(self, chave: str) -> None:
        modulo = self.modulo(chave)
        if modulo is None:
            return
        if self.modulo_atual and self.modulo_atual in self.paginas:
            self.paginas[self.modulo_atual].pack_forget()
        if chave not in self.paginas:
            self.paginas[chave] = self._criar_pagina(modulo)
        self.paginas[chave].pack(fill="both", expand=True)
        self.modulo_atual = chave
        self.menu.marcar_ativo(chave)

    def _criar_pagina(self, modulo: ModuloCarregado) -> ctk.CTkFrame:
        # a página é um frame comum (é ele que aparece/some ao trocar de módulo) com a rolagem dentro
        pagina = ctk.CTkFrame(self.area_conteudo, fg_color=tema.COR_FUNDO, corner_radius=0)
        rolagem = ctk.CTkScrollableFrame(pagina, fg_color=tema.COR_FUNDO, corner_radius=0,
                                         scrollbar_button_color=tema.COR_BORDA,
                                         scrollbar_button_hover_color=tema.COR_TEXTO_SUAVE)
        rolagem.pack(fill="both", expand=True)
        miolo = ctk.CTkFrame(rolagem, fg_color="transparent")
        miolo.pack(fill="both", expand=True, padx=tema.ESPACO_PAGINA_X, pady=tema.ESPACO_PAGINA_Y)

        if not modulo.ok:
            PainelModuloComErro(miolo, modulo.nome, modulo.erro, modulo.detalhe_tecnico).pack(fill="both", expand=True)
            return pagina
        try:
            painel = modulo.info.criar_painel(miolo)
        except Exception as erro:  # um painel com defeito não derruba a Central
            for filho in miolo.winfo_children():
                filho.destroy()
            PainelModuloComErro(miolo, modulo.nome, f"Não foi possível abrir a tela do módulo: {erro}",
                                traceback.format_exc()).pack(fill="both", expand=True)
            return pagina
        self.paineis[modulo.chave] = painel
        if hasattr(painel, "winfo_manager") and not painel.winfo_manager():
            painel.pack(fill="both", expand=True)
        return pagina

    # --- modo claro/escuro ---

    def alternar_modo(self) -> None:
        novo = MODO_CLARO if self.preferencias.modo == MODO_ESCURO else MODO_ESCURO
        self.preferencias.modo = novo
        ctk.set_appearance_mode(MODO_CTK[novo])
        self.menu.mostrar_modo(novo)
        salvar_preferencias(self.preferencias, self.caminho_preferencias)

    # --- fechar e erros ---

    def modulos_ocupados(self) -> list[str]:
        """Nomes dos módulos com processamento em andamento."""
        return [self.modulo(chave).nome for chave, painel in self.paineis.items() if getattr(painel, "ocupado", False)]

    def ao_fechar(self) -> None:
        ocupados = self.modulos_ocupados()
        if ocupados and not messagebox.askyesno(
                TITULO_JANELA, f"Há processamento em andamento ({', '.join(ocupados)}). Fechar agora pode deixar "
                               "arquivos incompletos na pasta de saída.\n\nDeseja fechar mesmo assim?",
                icon="warning", parent=self):
            return
        self.destroy()

    def report_callback_exception(self, tipo, valor, rastro):
        """Erro dentro de um botão ou tela: mostra em vez de sumir (o .exe não tem console)."""
        detalhe = "".join(traceback.format_exception(tipo, valor, rastro))
        messagebox.showerror(TITULO_JANELA, f"Erro inesperado: {valor}\n\n{detalhe[-1500:]}", parent=self)

    # --- ícone ---

    def _aplicar_icone(self) -> None:
        aplicar_icone(self)
