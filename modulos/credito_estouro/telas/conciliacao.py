"""Aba "Conciliação" do módulo Crédito Estouro (ESPECIFICACAO_CREDITO_ESTOURO.md, seção 7).

Esquerda: os eventos da folha do mês (PDF), o razão da conta (Excel do Tasy ou PDF), o controle do mês anterior (o
Excel que o módulo gerou) e a pasta onde salvar (opcional, lembrada). Cada arquivo é lido em segundo plano ao ser
escolhido (a confirmação aparece no cartão); com os três lidos, a tela já avisa se os meses não combinam.
Direita: os números, as conferências, o que precisa conferir e os botões da planilha.

Sem regra de negócio: a tela só chama processamento.py e mostra o que volta.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from tkinter import messagebox

from central import tema
from central.componentes import (
    BotaoSecundario,
    GrupoNumeros,
    JanelaTexto,
    LinhaConferencia,
    TextoQuebravel,
    botoes_da_planilha,
    rotulo_arquivo_salvo,
)
from central.painel_base import PainelPadrao
from modulos.credito_estouro import processamento

TIPOS_EVENTOS = [("PDF de eventos da folha (.pdf)", "*.pdf"), ("Todos os arquivos", "*.*")]
TIPOS_RAZAO = [("Razão do Tasy (.xls, .xlsx ou .pdf)", "*.xls *.xlsx *.pdf"), ("Todos os arquivos", "*.*")]
TIPOS_CONTROLE = [("Excel do Crédito Estouro (.xlsx)", "*.xlsx"), ("Todos os arquivos", "*.*")]
TEXTO_SEM_PASTA = "Sem escolher, a planilha vai para a pasta do razão."
TEXTO_VAZIO = "Selecione os três arquivos e clique em Gerar conciliação."


class PainelCreditoEstouro(PainelPadrao):
    TEXTO_BOTAO = "Gerar conciliação"

    def __init__(self, pai, info):
        self.ultimo_resultado: processamento.ResultadoCreditoEstouro | None = None
        self.janela_avisos: JanelaTexto | None = None
        self.previas: dict[str, processamento.Previa] = {}
        self.cartoes_obrigatorios: tuple = ()
        super().__init__(pai, info, com_cabecalho=False)

        self.cartao_eventos = self.adicionar_arquivo(
            "Eventos da folha do mês (PDF) – 0256, 0258, 0241, 1204 e o PDF do 0775 · um ou mais", tipo="arquivos",
            tipos_arquivo=TIPOS_EVENTOS,
            ao_mudar=lambda c: self._ler(self.cartao_eventos, "eventos", c, processamento.previa_eventos, todos=True),
            titulo_dialogo="Selecione os PDFs de eventos da folha do mês (o de eventos e, se houver, o do 0775)")
        self.cartao_razao = self.adicionar_arquivo(
            "Razão da conta Crédito Complemento Salário (Excel do Tasy ou PDF)", tipos_arquivo=TIPOS_RAZAO,
            ao_mudar=lambda c: self._ler(self.cartao_razao, "razao", c, processamento.previa_razao),
            titulo_dialogo="Selecione o razão da conta Crédito Complemento Salário (de preferência o .xls)")
        self.cartao_controle = self.adicionar_arquivo(
            "Controle do mês anterior (Excel gerado pelo Crédito Estouro)", tipos_arquivo=TIPOS_CONTROLE,
            ao_mudar=lambda c: self._ler(self.cartao_controle, "controle", c, processamento.previa_controle),
            titulo_dialogo="Selecione o Excel do Crédito Estouro do mês anterior")
        # a pasta é opcional e fica com o "Novo" (é uma preferência): por isso é o cartao_saida da base
        self.cartao_pasta = self.cartao_saida = self.adicionar_arquivo(
            "Pasta para salvar a planilha · opcional", tipo="pasta", ao_mudar=self._ao_mudar_pasta,
            titulo_dialogo="Escolha a pasta onde salvar a planilha")
        self.cartoes_obrigatorios = (self.cartao_eventos, self.cartao_razao, self.cartao_controle)

        self.botao.pack_forget()
        self.botao.pack(side="left", fill="x", expand=True)
        self.botao_limpar_tudo = BotaoSecundario(self.area_botoes, "Limpar tudo", self.novo, icone="erro")
        self.botao_limpar_tudo.pack(side="left", padx=(tema.ESPACO_PEQUENO, 0))

        pasta = processamento.ler_pasta_lembrada()
        if pasta and Path(pasta).is_dir():
            self.cartao_pasta.definir_caminhos([pasta], avisar=False)
            self.cartao_pasta.definir_confirmacao(f"Última pasta usada: {pasta}", "ok")
        else:
            self.cartao_pasta.definir_confirmacao(TEXTO_SEM_PASTA, None)
        self.atualizar_botoes()

    # --- escolha dos arquivos ---

    def _ler(self, cartao, chave: str, caminhos: list[Path], funcao_previa, todos: bool = False) -> None:
        self.previas.pop(chave, None)
        if not caminhos:
            return
        caminho = caminhos[0]
        entrada = list(caminhos) if todos else caminho
        cartao.definir_carregando("Lendo o arquivo...")

        def lido(previa) -> None:
            if (list(cartao.caminhos) if todos else cartao.caminho) != entrada:   # o usuário já trocou o arquivo
                return
            previa = previa or processamento.Previa(erro="Não foi possível ler o arquivo.")
            self.previas[chave] = previa
            if previa.erro:
                cartao.definir_confirmacao(previa.erro, "erro")
            elif previa.avisos:
                cartao.definir_confirmacao(f"{previa.texto} · atenção: " + "; ".join(previa.avisos), "atencao")
            else:
                cartao.definir_confirmacao(previa.texto, "ok")
            self._conferir_meses()
            self.atualizar_botoes()

        self.ler_em_segundo_plano(lambda: funcao_previa(entrada), lido)

    def _conferir_meses(self) -> None:
        """Com os três lidos: meses que não combinam viram erro no cartão do controle (o botão fica desligado)."""
        if not all(chave in self.previas and not self.previas[chave].erro for chave in ("eventos", "razao", "controle")):
            return
        erro = processamento.conferir_previas(self.previas["eventos"], self.previas["razao"], self.previas["controle"])
        if erro:
            cartao = self.cartao_razao if "razão é" in erro else self.cartao_controle
            cartao.definir_confirmacao(erro, "erro")

    def _ao_mudar_pasta(self, caminhos: list[Path]) -> None:
        if caminhos:
            self.cartao_pasta.definir_confirmacao(f"A planilha será salva em {caminhos[0]}", "ok")
        else:
            self.cartao_pasta.definir_confirmacao(TEXTO_SEM_PASTA, None)
        processamento.salvar_pasta_lembrada(str(caminhos[0]) if caminhos else "")

    def pronto_para_processar(self) -> bool:
        if not self.cartoes_obrigatorios:
            return False
        return all(c.preenchido and c.status_confirmacao not in (None, "erro") for c in self.cartoes_obrigatorios)

    def atualizar_botoes(self) -> None:
        super().atualizar_botoes()
        if hasattr(self, "botao_limpar_tudo"):
            algo = any(c.preenchido for c in self.cartoes_obrigatorios) or self.ultimo_resultado is not None
            self.botao_limpar_tudo.habilitar(not self.ocupado and algo)

    # --- processamento ---

    def processar(self) -> None:
        if self.ocupado or not self.pronto_para_processar():
            return
        eventos, razao, controle = self.cartao_eventos.caminhos, self.cartao_razao.caminho, self.cartao_controle.caminho
        pasta = self.cartao_pasta.caminho
        self.executar(lambda progresso: processamento.processar(eventos, razao, controle, pasta, progresso),
                      self.mostrar_resultado, "Lendo os arquivos...")

    def mostrar_inicio(self) -> None:
        self.resultado.mostrar_vazio("Nenhum resultado ainda", TEXTO_VAZIO)

    def mostrar_resultado(self, resultado: processamento.ResultadoCreditoEstouro) -> None:
        self.ultimo_resultado = resultado
        self.atualizar_botoes()
        if resultado.erro:
            self.mostrar_erro(resultado.erro)
            return
        resumo = processamento.resumir(resultado)
        cartao = self.resultado
        area = cartao.mostrar_conteudo()
        cartao.definir_selo(*resumo.selo)
        TextoQuebravel(area, resumo.contexto, tema.fonte_texto_forte()).pack(fill="x", pady=(0, tema.ESPACO_PEQUENO))
        GrupoNumeros(area, resumo.numeros).pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))
        for texto, status, valor in resumo.linhas:
            LinhaConferencia(area, texto, status, valor).pack(fill="x", pady=3)
        rotulo_arquivo_salvo(area, resultado.caminho_planilha)
        botoes_da_planilha(cartao.rodape, resultado.caminho_planilha, self.abrir_planilha, self.abrir_pasta,
                           self.ver_avisos)

    # --- botões do resultado ---

    def abrir_planilha(self) -> None:
        if self.ultimo_resultado and self.ultimo_resultado.caminho_planilha:
            self.abrir(self.ultimo_resultado.caminho_planilha)

    def abrir_pasta(self) -> None:
        """Abre o Explorador com a planilha já selecionada."""
        caminho = self.ultimo_resultado.caminho_planilha if self.ultimo_resultado else None
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
        if self.ultimo_resultado is None:
            return
        avisos = self.ultimo_resultado.avisos
        linhas = [f"AVISOS ({len(avisos)})"] + ([f"• [{a.arquivo}] {a.mensagem}" for a in avisos] or ["Nenhum aviso."])
        if self.janela_avisos is not None and self.janela_avisos.winfo_exists():
            self.janela_avisos.destroy()
        self.janela_avisos = JanelaTexto(self.winfo_toplevel(), "Avisos da conciliação", "Avisos", linhas)

    def ao_novo(self) -> None:
        self.ultimo_resultado = None
        self.previas = {}
