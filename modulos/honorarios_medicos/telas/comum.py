"""O que as duas abas de Honorários Médicos têm igual (nas telas antigas era código repetido nos dois
painéis): o botão "Limpar tudo" ao lado de "Gerar relatório", a pasta onde salvar (lembrada, uma por aba),
a linha de avisos do resultado e os botões Abrir planilha / Abrir pasta / Ver avisos.

Sem regra de negócio: só monta a tela.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from tkinter import messagebox

from central import tema
from central.componentes import BotaoSecundario, JanelaTexto, LinhaConferencia, botoes_da_planilha, rotulo_arquivo_salvo
from central.painel_base import PainelPadrao, formatar_inteiro
from modulos.honorarios_medicos import processamento

TEXTO_SEM_PASTA = "Sem escolher, a planilha vai para a pasta do balancete."
MAXIMO_ITENS_NA_TELA = 10      # o resto fica na planilha
MAXIMO_LETRAS_NOME = 30


def encurtar(texto: str, maximo: int = MAXIMO_LETRAS_NOME) -> str:
    return texto if len(texto) <= maximo else texto[:maximo - 1].rstrip() + "…"


def linhas_dos_avisos(resultado) -> list[str]:
    """O texto da janela "Ver avisos" (o mesmo da janela de avisos do Conciliações AMES)."""
    arquivos = [a for a in resultado.avisos if a.tipo_arquivo]
    outros = [a for a in resultado.avisos if not a.tipo_arquivo]
    linhas = ["ARQUIVOS LIDOS"]
    for aviso in arquivos:
        lidas = "" if aviso.linhas_lidas is None else f" · {formatar_inteiro(aviso.linhas_lidas)} linhas"
        linhas.append(f"• {aviso.arquivo} ({aviso.tipo_arquivo}{lidas}): {aviso.mensagem}")
    linhas.append("")
    linhas.append(f"AVISOS ({len(outros)})")
    if not outros:
        linhas.append("Nenhum aviso.")
    for aviso in outros:
        linhas.append(f"• [{aviso.arquivo}] {aviso.mensagem}")
    return linhas


class PainelHonorariosBase(PainelPadrao):
    """Base das abas. A subclasse define ABA (processamento.ABA_*), monta os cartões dos relatórios em
    criar_cartoes() e chama super().__init__; cartoes_relatorios são os que o "Limpar tudo" esvazia."""

    TEXTO_BOTAO = "Gerar relatório"
    ABA = ""

    def __init__(self, pai, info):
        self.resultado_conciliacao = None
        self.janela_avisos: JanelaTexto | None = None
        self.cartoes_relatorios: tuple = ()
        super().__init__(pai, info, com_cabecalho=False)

        self.cartoes_relatorios = self.criar_cartoes()
        # a pasta é opcional e fica com o "Novo" (é uma preferência): por isso é o cartao_saida da base
        self.cartao_pasta = self.cartao_saida = self.adicionar_arquivo(
            "Pasta para salvar a planilha · opcional", tipo="pasta", ao_mudar=self._ao_mudar_pasta,
            titulo_dialogo="Escolha a pasta onde salvar a planilha")

        # "Limpar tudo" ao lado de "Gerar relatório", como na tela antiga
        self.botao.pack_forget()
        self.botao.pack(side="left", fill="x", expand=True)
        self.botao_limpar_tudo = BotaoSecundario(self.area_botoes, "Limpar tudo", self.novo, icone="erro")
        self.botao_limpar_tudo.pack(side="left", padx=(tema.ESPACO_PEQUENO, 0))

        pasta = processamento.ler_pasta_lembrada(self.ABA)
        if pasta and Path(pasta).is_dir():
            self.cartao_pasta.definir_caminhos([pasta], avisar=False)
            self.cartao_pasta.definir_confirmacao(f"Última pasta usada: {pasta}", "ok")
        else:
            self.cartao_pasta.definir_confirmacao(TEXTO_SEM_PASTA, None)
        self.atualizar_botoes()

    def criar_cartoes(self) -> tuple:
        raise NotImplementedError

    def _ao_mudar_pasta(self, caminhos: list[Path]) -> None:
        if caminhos:
            self.cartao_pasta.definir_confirmacao(f"A planilha será salva em {caminhos[0]}", "ok")
        else:
            self.cartao_pasta.definir_confirmacao(TEXTO_SEM_PASTA, None)
        processamento.salvar_pasta_lembrada(self.ABA, str(caminhos[0]) if caminhos else "")

    def atualizar_botoes(self) -> None:
        super().atualizar_botoes()
        if hasattr(self, "botao_limpar_tudo"):
            algo = any(c.preenchido for c in self.cartoes_relatorios) or self.resultado_conciliacao is not None
            self.botao_limpar_tudo.habilitar(not self.ocupado and algo)
        for cartao in self.cartoes:
            cartao.botao.habilitar(not self.ocupado)
            cartao.botao_limpar.configure(state="disabled" if self.ocupado else "normal")

    # --- resultado ---

    def mostrar_fim_do_resultado(self, area, rodape, resultado) -> None:
        """A linha de avisos, o "Salvo como" e os botões da planilha (o fim do resultado nas duas abas)."""
        erros = sum(1 for a in resultado.avisos if a.nivel == processamento.NIVEL_ERRO)
        avisos = sum(1 for a in resultado.avisos if not a.tipo_arquivo)
        if erros:
            texto, status = f"{erros} arquivo(s) não puderam ser lidos — veja os avisos", "erro"
        elif avisos:
            texto, status = f"{avisos} aviso(s) para conferir — veja os avisos", "atencao"
        else:
            texto, status = "Nenhum aviso", "ok"
        LinhaConferencia(area, texto, status).pack(fill="x", pady=(tema.ESPACO_PEQUENO, 0))

        rotulo_arquivo_salvo(area, resultado.caminho_relatorio)
        botoes_da_planilha(rodape, resultado.caminho_relatorio, self.abrir_planilha, self.abrir_pasta,
                           self.ver_avisos)

    # --- botões do resultado ---

    def abrir_planilha(self) -> None:
        caminho = self.resultado_conciliacao.caminho_relatorio if self.resultado_conciliacao else None
        if caminho is not None:
            self.abrir(caminho)

    def abrir_pasta(self) -> None:
        """Abre o Explorador com a planilha já selecionada."""
        caminho = self.resultado_conciliacao.caminho_relatorio if self.resultado_conciliacao else None
        if caminho is None:
            return
        try:
            if caminho.exists():
                subprocess.Popen(f'explorer /select,"{caminho}"')
            else:
                os.startfile(caminho.parent)  # noqa: S606
        except OSError as erro:
            messagebox.showerror(self.info.nome, f"Não foi possível abrir a pasta: {erro}", parent=self)

    def ver_avisos(self) -> None:
        if self.resultado_conciliacao is None:
            return
        if self.janela_avisos is not None and self.janela_avisos.winfo_exists():
            self.janela_avisos.destroy()
        self.janela_avisos = JanelaTexto(self.winfo_toplevel(), "Avisos da conciliação", "Avisos",
                                         linhas_dos_avisos(self.resultado_conciliacao))

    def ao_novo(self) -> None:
        """Limpa os relatórios e o resultado; a pasta escolhida fica (é uma preferência)."""
        self.resultado_conciliacao = None
