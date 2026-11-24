"""Janela que pergunta a cidade/UF de um prestador que não foi encontrada em lugar nenhum (R11.4).

Só interface: a resposta volta para o processamento, que guarda no cadastro de prestadores.
"""

from __future__ import annotations

import customtkinter as ctk

from central import tema
from central.componentes import BotaoPrincipal, BotaoSecundario, CampoRotulado


def formatar_documento(documento: str) -> str:
    d = "".join(c for c in documento if c.isdigit())
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    return documento


class JanelaCidade(ctk.CTkToplevel):
    """resposta = (cidade, uf) depois de "Confirmar"; None se o usuário não souber/fechar."""

    def __init__(self, pai, documento: str, nome: str):
        super().__init__(pai)
        self.title("Cidade do prestador")
        self.configure(fg_color=tema.COR_FUNDO)
        self.resizable(False, False)
        self.resposta: tuple[str, str] | None = None
        self.protocol("WM_DELETE_WINDOW", self.nao_sei)

        corpo = ctk.CTkFrame(self, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=tema.ESPACO_INTERNO_CARTAO, pady=tema.ESPACO_INTERNO_CARTAO)
        ctk.CTkLabel(corpo, text="Não encontrei a cidade deste prestador", font=tema.fonte_subtitulo(),
                     text_color=tema.COR_TEXTO, anchor="w").pack(anchor="w")
        ctk.CTkLabel(corpo, text=f"{nome}\n{formatar_documento(documento)}", font=tema.fonte_texto(),
                     text_color=tema.COR_TEXTO_SUAVE, anchor="w", justify="left").pack(anchor="w", pady=(4, 0))
        ctk.CTkLabel(corpo, text="Ela vai para o cadastro de prestadores e não será perguntada de novo.",
                     font=tema.fonte_legenda(), text_color=tema.COR_TEXTO_SUAVE, anchor="w", justify="left",
                     wraplength=380).pack(anchor="w", pady=(4, tema.ESPACO_PEQUENO))

        linha = ctk.CTkFrame(corpo, fg_color="transparent")
        linha.pack(anchor="w")
        self.campo_cidade = CampoRotulado(linha, "Cidade", largura=280)
        self.campo_cidade.pack(side="left")
        self.campo_uf = CampoRotulado(linha, "UF", largura=70)
        self.campo_uf.pack(side="left", padx=(tema.ESPACO_PEQUENO, 0))

        self.rotulo_erro = ctk.CTkLabel(corpo, text="", font=tema.fonte_legenda(), text_color=tema.COR_ERRO,
                                        anchor="w")
        self.rotulo_erro.pack(anchor="w", pady=(4, 0))

        botoes = ctk.CTkFrame(corpo, fg_color="transparent")
        botoes.pack(fill="x", pady=(tema.ESPACO_PEQUENO, 0))
        BotaoPrincipal(botoes, "Confirmar", self.confirmar, icone="check").pack(side="left", fill="x", expand=True)
        BotaoSecundario(botoes, "Não sei", self.nao_sei, largura=140).pack(side="left",
                                                                          padx=(tema.ESPACO_PEQUENO, 0))
        self.campo_cidade.entrada.focus_set()
        self.bind("<Return>", lambda _: self.confirmar())

    def confirmar(self) -> None:
        cidade, uf = self.campo_cidade.valor(), self.campo_uf.valor().upper()
        if not cidade:
            self.rotulo_erro.configure(text="Informe a cidade.")
            return
        if len(uf) != 2 or not uf.isalpha():
            self.rotulo_erro.configure(text="Informe a UF com 2 letras (ex.: SP).")
            return
        self.resposta = (cidade, uf)
        self.destroy()

    def nao_sei(self) -> None:
        self.resposta = None
        self.destroy()


def perguntar_cidade(pai, documento: str, nome: str) -> tuple[str, str] | None:
    """Abre a janela e espera a resposta (a nota fica em "lançar à mão" se não houver resposta)."""
    janela = JanelaCidade(pai, documento, nome)
    janela.transient(pai.winfo_toplevel())
    janela.grab_set()
    janela.wait_window()
    return janela.resposta
