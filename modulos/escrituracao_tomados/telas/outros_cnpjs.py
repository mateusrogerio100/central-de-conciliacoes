"""Janela "Outros CNPJs da Fundação": CNPJs de outra raiz que não a 98765432 que também são da
Fundação (ex.: um AME com CNPJ próprio) e devem ser escriturados (R1 — decisão do usuário,
01/10/2026).

Só interface: quem confere os CNPJs e grava a lista é o processamento (a tela passa a função).
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from central import tema
from central.componentes import BotaoPrincipal, BotaoSecundario
from modulos.escrituracao_tomados.telas.pergunta_cidade import formatar_documento

Interpretar = Callable[[str], tuple[list[str], list[str]]]


class JanelaOutrosCnpjs(ctk.CTkToplevel):
    """resposta = lista de CNPJs depois de "Salvar"; None se o usuário cancelar/fechar."""

    def __init__(self, pai, cnpjs: list[str], interpretar: Interpretar):
        super().__init__(pai)
        self.title("Outros CNPJs da Fundação")
        self.configure(fg_color=tema.COR_FUNDO)
        self.resizable(False, False)
        self.interpretar = interpretar
        self.resposta: list[str] | None = None
        self.protocol("WM_DELETE_WINDOW", self.cancelar)

        corpo = ctk.CTkFrame(self, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=tema.ESPACO_INTERNO_CARTAO, pady=tema.ESPACO_INTERNO_CARTAO)
        ctk.CTkLabel(corpo, text="Outros CNPJs da Fundação", font=tema.fonte_subtitulo(),
                     text_color=tema.COR_TEXTO, anchor="w").pack(anchor="w")
        ctk.CTkLabel(corpo, text="Os CNPJs que começam com 98.765.432 já são reconhecidos. Informe aqui "
                                 "só os estabelecimentos com outra raiz (ex.: um AME com CNPJ próprio), "
                                 "um por linha. As notas tomadas por eles também vão para o arquivo, "
                                 "um .txt para cada CNPJ.",
                     font=tema.fonte_legenda(), text_color=tema.COR_TEXTO_SUAVE, anchor="w", justify="left",
                     wraplength=400).pack(anchor="w", pady=(4, tema.ESPACO_PEQUENO))

        self.caixa = ctk.CTkTextbox(corpo, width=400, height=150, font=tema.fonte_campo(),
                                    corner_radius=tema.RAIO_BOTAO, border_width=tema.LARGURA_BORDA,
                                    border_color=tema.COR_BORDA, fg_color=tema.COR_SUPERFICIE,
                                    text_color=tema.COR_TEXTO)
        self.caixa.pack(anchor="w")
        self.caixa.insert("1.0", "\n".join(formatar_documento(c) for c in cnpjs))

        self.rotulo_erro = ctk.CTkLabel(corpo, text="", font=tema.fonte_legenda(), text_color=tema.COR_ERRO,
                                        anchor="w", justify="left", wraplength=400)
        self.rotulo_erro.pack(anchor="w", pady=(4, 0))

        botoes = ctk.CTkFrame(corpo, fg_color="transparent")
        botoes.pack(fill="x", pady=(tema.ESPACO_PEQUENO, 0))
        BotaoPrincipal(botoes, "Salvar", self.salvar, icone="check").pack(side="left", fill="x", expand=True)
        BotaoSecundario(botoes, "Cancelar", self.cancelar, largura=140).pack(side="left",
                                                                            padx=(tema.ESPACO_PEQUENO, 0))
        self.caixa.focus_set()

    def texto(self) -> str:
        return self.caixa.get("1.0", "end")

    def definir_texto(self, texto: str) -> None:
        self.caixa.delete("1.0", "end")
        self.caixa.insert("1.0", texto)

    def salvar(self) -> None:
        cnpjs, problemas = self.interpretar(self.texto())
        if problemas:
            self.rotulo_erro.configure(text="CNPJ inválido (confira os dígitos): " + "; ".join(problemas))
            return
        self.resposta = cnpjs
        self.destroy()

    def cancelar(self) -> None:
        self.resposta = None
        self.destroy()


def editar_outros_cnpjs(pai, cnpjs: list[str], interpretar: Interpretar) -> list[str] | None:
    """Abre a janela e espera. Devolve a lista nova, ou None se o usuário cancelar."""
    janela = JanelaOutrosCnpjs(pai, cnpjs, interpretar)
    janela.transient(pai.winfo_toplevel())
    janela.grab_set()
    janela.wait_window()
    return janela.resposta
