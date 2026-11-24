"""Janela da pergunta da R5 (item 4): em qual seção da aba do ano entra um evento novo cuja conta não está na
tabela conta → seção. Também serve para a conta que aparece em duas seções ao montar a tabela (R5a).

Só interface: os textos vêm prontos do processamento (TextosPergunta) e a resposta volta para ele, que grava a
seção na tabela conta → seção.
"""

from __future__ import annotations

import customtkinter as ctk

from central import tema
from central.componentes import BotaoPrincipal, BotaoSecundario, aplicar_icone

ALTURA_LISTA = 260


class JanelaSecao(ctk.CTkToplevel):
    """resposta = a resposta escolhida (o nome da seção ou a de "seção nova") depois de "Confirmar"; None se o
    usuário cancelar ou fechar (nada é gravado)."""

    def __init__(self, pai, textos, numero: int = 1, total: int = 1):
        super().__init__(pai)
        self.title("Seção do evento novo")
        self.configure(fg_color=tema.COR_FUNDO)
        self.resizable(False, False)
        aplicar_icone(self)
        self.resposta: str | None = None
        self.escolhida: str | None = None
        self.protocol("WM_DELETE_WINDOW", self.cancelar)

        corpo = ctk.CTkFrame(self, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=tema.ESPACO_INTERNO_CARTAO, pady=tema.ESPACO_INTERNO_CARTAO)
        titulo = "Em qual seção o evento entra?" + (f"  ({numero} de {total})" if total > 1 else "")
        ctk.CTkLabel(corpo, text=titulo, font=tema.fonte_subtitulo(), text_color=tema.COR_TEXTO,
                     anchor="w").pack(anchor="w")
        ctk.CTkLabel(corpo, text=textos.motivo, font=tema.fonte_texto(), text_color=tema.COR_TEXTO_SUAVE,
                     anchor="w", justify="left", wraplength=520).pack(anchor="w", pady=(4, tema.ESPACO_PEQUENO))
        for rotulo, itens in (("Evento", textos.eventos), ("Conta no Movimento", textos.contas)):
            if not itens:
                continue
            ctk.CTkLabel(corpo, text=rotulo, font=tema.fonte_rotulo(), text_color=tema.COR_TEXTO,
                         anchor="w").pack(anchor="w")
            ctk.CTkLabel(corpo, text="\n".join(itens), font=tema.fonte_texto(), text_color=tema.COR_TEXTO,
                         anchor="w", justify="left", wraplength=520).pack(anchor="w", pady=(0, tema.ESPACO_PEQUENO))

        ctk.CTkLabel(corpo, text="Seção", font=tema.fonte_rotulo(), text_color=tema.COR_TEXTO,
                     anchor="w").pack(anchor="w")
        lista = ctk.CTkScrollableFrame(corpo, width=520, height=ALTURA_LISTA, fg_color=tema.COR_SUPERFICIE,
                                       border_width=tema.LARGURA_BORDA, border_color=tema.COR_BORDA,
                                       corner_radius=tema.RAIO_BOTAO)
        lista.pack(fill="x", pady=(4, 0))
        self.botoes: dict[str, ctk.CTkButton] = {}
        for resposta, texto in textos.opcoes:
            botao = ctk.CTkButton(lista, text=texto, anchor="w", height=tema.ALTURA_BOTAO_PEQUENO,
                                  corner_radius=tema.RAIO_PEQUENO, border_width=tema.LARGURA_BORDA,
                                  command=lambda r=resposta: self.escolher(r))
            botao.pack(fill="x", pady=2, padx=2)
            self.botoes[resposta] = botao
        ctk.CTkLabel(corpo, text="A escolha vai para a tabela conta → seção e não será perguntada de novo.",
                     font=tema.fonte_legenda(), text_color=tema.COR_TEXTO_SUAVE, anchor="w", justify="left",
                     wraplength=520).pack(anchor="w", pady=(4, 0))

        botoes = ctk.CTkFrame(corpo, fg_color="transparent")
        botoes.pack(fill="x", pady=(tema.ESPACO_PEQUENO, 0))
        self.botao_confirmar = BotaoPrincipal(botoes, "Confirmar", self.confirmar, icone="check")
        self.botao_confirmar.pack(side="left", fill="x", expand=True)
        BotaoSecundario(botoes, "Cancelar", self.cancelar, largura=140).pack(side="left",
                                                                            padx=(tema.ESPACO_PEQUENO, 0))
        self.escolher(None)

    def escolher(self, resposta: str | None) -> None:
        """Marca a opção (com o visual da aba ativa, como o SeletorOpcoes) e acende o "Confirmar"."""
        self.escolhida = resposta
        for chave, botao in self.botoes.items():
            if chave == resposta:
                botao.configure(fg_color=tema.COR_PRINCIPAL_SUAVE, hover_color=tema.COR_PRINCIPAL_SUAVE,
                                border_color=tema.COR_PRINCIPAL, text_color=tema.COR_PRINCIPAL,
                                font=tema.fonte_texto_forte())
            else:
                botao.configure(fg_color=tema.COR_SUPERFICIE, hover_color=tema.COR_PRINCIPAL_SUAVE,
                                border_color=tema.COR_SUPERFICIE, text_color=tema.COR_TEXTO, font=tema.fonte_texto())
        self.botao_confirmar.habilitar(resposta is not None)

    def confirmar(self) -> None:
        if self.escolhida is None:
            return
        self.resposta = self.escolhida
        self.destroy()

    def cancelar(self) -> None:
        self.resposta = None
        self.destroy()


def perguntar_secao(pai, textos, numero: int = 1, total: int = 1) -> str | None:
    """Abre a janela e espera a resposta (None = cancelou: nada é gravado)."""
    janela = JanelaSecao(pai, textos, numero, total)
    janela.transient(pai.winfo_toplevel())
    janela.grab_set()
    janela.wait_window()
    return janela.resposta
