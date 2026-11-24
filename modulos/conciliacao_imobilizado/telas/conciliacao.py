"""Aba "Conciliação" do módulo Imobilizado – AME's (era interface/painel_bens.py do Conciliações AMES).

Mesmos cartões, prévias, textos e resultado da tela antiga, no layout padrão da Central:
- Patrimônio (6051) e Balancetes (865) obrigatórios; Bens adquiridos (555) e Baixa de bens (561)
  opcionais (servem para explicar diferenças); a pasta onde salvar (opcional, lembrada);
- um cartão com erro (inclusive um opcional) bloqueia o botão;
- resultado: números, tabela por situação, o pedido dos opcionais quando ajudariam, avisos e os
  botões "Abrir pasta", "Ver avisos" e "Novo".

Sem regra de negócio: a tela só chama processamento.py e mostra o que volta.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from central import tema
from central.componentes import (
    BotaoSecundario,
    Coluna,
    GrupoNumeros,
    JanelaTexto,
    LinhaConferencia,
    TabelaSimples,
    TextoQuebravel,
)
from central.painel_base import PainelPadrao, formatar_inteiro, formatar_reais
from modulos.conciliacao_imobilizado import processamento
from modulos.conciliacao_imobilizado.processamento import (
    NIVEL_ERRO,
    SITUACAO_CONFERE,
    SITUACAO_DIFERENCA,
    SITUACAO_DIFERENCA_EXPLICADA,
    SITUACAO_DIFERENCA_SEM_EXPLICACAO,
    SITUACAO_SOMENTE_BALANCETE,
    SITUACAO_SOMENTE_PATRIMONIO,
    PreviaBens,
    ResultadoBens,
)

TIPOS_TASY = [("Relatórios do Tasy (.xls)", "*.xls"), ("Todos os arquivos", "*.*")]

# Nomes curtos das situações para a tabela da tela (o Excel usa os nomes completos)
NOMES_CURTOS_BENS = {
    SITUACAO_CONFERE: "Conferem",
    SITUACAO_DIFERENCA_EXPLICADA: "Diferença explicada",
    SITUACAO_DIFERENCA: "Diferença (verificar)",
    SITUACAO_DIFERENCA_SEM_EXPLICACAO: "Diferença sem explicação",
    SITUACAO_SOMENTE_PATRIMONIO: "Somente no patrimônio",
    SITUACAO_SOMENTE_BALANCETE: "Somente no balancete",
}

TEXTO_SEM_PASTA = "Sem escolher, a planilha vai para a pasta do arquivo do patrimônio."
TEXTO_VAZIO = ("Selecione o patrimônio e os balancetes e clique em Gerar relatório. "
               "Bens adquiridos e Baixa de bens são opcionais.")


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


class PainelConciliacaoImobilizado(PainelPadrao):
    TEXTO_BOTAO = "Gerar relatório"

    def __init__(self, pai, info):
        self.resultado_conciliacao: ResultadoBens | None = None
        self.janela_avisos: JanelaTexto | None = None
        self.cartoes_relatorios: tuple = ()
        super().__init__(pai, info, com_cabecalho=False)

        self.cartao_razao = self.adicionar_arquivo(
            "Patrimônio (6051) – Razão auxiliar", tipos_arquivo=TIPOS_TASY, ao_mudar=self._ao_mudar_razao,
            titulo_dialogo="Selecione o Razão auxiliar do patrimônio (Tasy 6051)")
        self.cartao_balancetes = self.adicionar_arquivo(
            "Balancetes (865): Intangível, Imobilizado e Cessão", tipo="arquivos", tipos_arquivo=TIPOS_TASY,
            ao_mudar=self._ao_mudar_balancetes,
            titulo_dialogo="Selecione os balancetes (Tasy 865) — pode escolher os três de uma vez")
        self.cartao_bens = self.adicionar_arquivo(
            "Bens adquiridos (555) · opcional", tipos_arquivo=TIPOS_TASY, ao_mudar=self._ao_mudar_bens,
            titulo_dialogo="Selecione o relatório de Bens adquiridos (Tasy 555)")
        self.cartao_baixas = self.adicionar_arquivo(
            "Baixa de bens (561) · opcional", tipos_arquivo=TIPOS_TASY, ao_mudar=self._ao_mudar_baixas,
            titulo_dialogo="Selecione o relatório de Baixa de bens (Tasy 561)")
        # a pasta é opcional e fica com o "Novo" (é uma preferência): por isso é o cartao_saida da base
        self.cartao_pasta = self.cartao_saida = self.adicionar_arquivo(
            "Pasta para salvar a planilha · opcional", tipo="pasta", ao_mudar=self._ao_mudar_pasta,
            titulo_dialogo="Escolha a pasta onde salvar a planilha")
        self.cartoes_relatorios = (self.cartao_razao, self.cartao_balancetes, self.cartao_bens, self.cartao_baixas)

        # "Limpar tudo" ao lado de "Gerar relatório", como na tela antiga
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

    # --- escolha dos arquivos (arquivos pequenos: a prévia é rápida, sem segundo plano) ---

    @staticmethod
    def _mostrar_previa(cartao, previa: PreviaBens) -> None:
        if previa.erro:
            cartao.definir_confirmacao(previa.erro, "erro")
        elif previa.avisos:
            cartao.definir_confirmacao(f"{previa.descricao} · atenção: " + "; ".join(previa.avisos), "atencao")
        else:
            cartao.definir_confirmacao(previa.descricao, "ok")

    def _ao_mudar(self, cartao, caminhos: list[Path], funcao_previa) -> None:
        if caminhos:
            try:
                previa = funcao_previa(caminhos)
            except Exception as erro:   # rede de segurança: a prévia nunca derruba a tela
                previa = PreviaBens(erro=f"Erro inesperado ao ler o arquivo: {erro}")
            self._mostrar_previa(cartao, previa)

    def _ao_mudar_razao(self, caminhos: list[Path]) -> None:
        self._ao_mudar(self.cartao_razao, caminhos, lambda c: processamento.previa_razao(c[0]))

    def _ao_mudar_balancetes(self, caminhos: list[Path]) -> None:
        self._ao_mudar(self.cartao_balancetes, caminhos, processamento.previa_balancetes)

    def _ao_mudar_bens(self, caminhos: list[Path]) -> None:
        self._ao_mudar(self.cartao_bens, caminhos, lambda c: processamento.previa_bens_adquiridos(c[0]))

    def _ao_mudar_baixas(self, caminhos: list[Path]) -> None:
        self._ao_mudar(self.cartao_baixas, caminhos, lambda c: processamento.previa_baixas(c[0]))

    def _ao_mudar_pasta(self, caminhos: list[Path]) -> None:
        if caminhos:
            self.cartao_pasta.definir_confirmacao(f"A planilha será salva em {caminhos[0]}", "ok")
        else:
            self.cartao_pasta.definir_confirmacao(TEXTO_SEM_PASTA, None)
        processamento.salvar_pasta_lembrada(str(caminhos[0]) if caminhos else "")

    def pronto_para_processar(self) -> bool:
        if not self.cartoes_relatorios:
            return False
        obrigatorios = all(c.preenchido for c in (self.cartao_razao, self.cartao_balancetes))
        sem_erro = all(c.status_confirmacao != "erro" for c in self.cartoes_relatorios if c.preenchido)
        return obrigatorios and sem_erro

    def atualizar_botoes(self) -> None:
        super().atualizar_botoes()
        if hasattr(self, "botao_limpar_tudo"):
            algo = any(c.preenchido for c in self.cartoes_relatorios) or self.resultado_conciliacao is not None
            self.botao_limpar_tudo.habilitar(not self.ocupado and algo)
        for cartao in self.cartoes:
            cartao.botao.habilitar(not self.ocupado)
            cartao.botao_limpar.configure(state="disabled" if self.ocupado else "normal")

    # --- processamento ---

    def processar(self) -> None:
        if self.ocupado or not self.pronto_para_processar():
            return
        razao, balancetes = self.cartao_razao.caminho, self.cartao_balancetes.caminhos
        bens, baixas, pasta = self.cartao_bens.caminho, self.cartao_baixas.caminho, self.cartao_pasta.caminho
        self.executar(lambda progresso: processamento.processar(razao, balancetes, bens, baixas, pasta, progresso),
                      self.mostrar_resultado)

    def mostrar_resultado(self, resultado: ResultadoBens) -> None:
        self.resultado_conciliacao = resultado
        self.atualizar_botoes()
        cartao = self.resultado
        area = cartao.mostrar_conteudo()

        if resultado.caminho_relatorio is not None:
            cartao.definir_selo("Concluído", "ok")
        else:
            cartao.definir_selo("Relatório não gerado", "erro")
        if resultado.erro:
            LinhaConferencia(area, resultado.erro, status="erro").pack(fill="x", pady=(0, tema.ESPACO_PEQUENO))

        if resultado.itens:
            if resultado.ame or resultado.competencia_texto:
                contexto = " · ".join(t for t in (resultado.ame, resultado.competencia_texto) if t)
                TextoQuebravel(area, contexto, tema.fonte_texto_forte()).pack(fill="x", pady=(0, tema.ESPACO_PEQUENO))

            numeros = processamento.numeros_principais(resultado)
            GrupoNumeros(area, [
                (formatar_inteiro(numeros.conferem), "Conferem", "ok"),
                (formatar_inteiro(numeros.explicadas), "Diferenças explicadas", "principal"),
                (formatar_inteiro(numeros.para_analisar), "Para analisar",
                 "atencao" if numeros.para_analisar else "ok"),
            ]).pack(fill="x")

            linhas_tabela = [
                (NOMES_CURTOS_BENS.get(linha.situacao, linha.situacao),
                 formatar_inteiro(linha.contas), formatar_reais(linha.diferenca))
                for linha in processamento.linhas_do_resumo(resultado)
            ]
            TabelaSimples(area, [Coluna("Situação", peso=3), Coluna("Contas", numero=True),
                                 Coluna("Diferença (R$)", numero=True, peso=2)],
                          linhas_tabela).pack(fill="x", pady=(tema.ESPACO_ENTRE_BLOCOS, 0))

            faltando = processamento.relatorios_que_ajudariam(resultado)
            if faltando:
                LinhaConferencia(
                    area,
                    f"Há diferença sem explicação. Se houve entrada ou baixa de bens no mês, "
                    f"selecione {' e '.join(faltando)} e gere de novo.", "atencao",
                ).pack(fill="x", pady=(tema.ESPACO_ENTRE_BLOCOS, 6))

        erros = sum(1 for a in resultado.avisos if a.nivel == NIVEL_ERRO)
        avisos = sum(1 for a in resultado.avisos if not a.tipo_arquivo)
        if erros:
            texto, status = f"{erros} arquivo(s) não puderam ser lidos — veja os avisos", "erro"
        elif avisos:
            texto, status = f"{avisos} aviso(s) para conferir — veja os avisos", "atencao"
        else:
            texto, status = "Nenhum aviso", "ok"
        LinhaConferencia(area, texto, status).pack(fill="x", pady=(6, 0))

        if resultado.caminho_relatorio is not None:
            ctk.CTkLabel(area, text=f"Salvo como {resultado.caminho_relatorio.name}", font=tema.fonte_legenda(),
                         text_color=tema.COR_TEXTO_SUAVE, anchor="w", justify="left", wraplength=380
                         ).pack(fill="x", pady=(tema.ESPACO_PEQUENO, 0))

        botoes = self.definir_botoes_resultado([
            ("Abrir pasta", self.abrir_pasta, "pasta"),
            ("Ver avisos", self.ver_avisos, "alerta"),
            ("Novo", self.novo, "atualizar"),
        ])
        botoes["Abrir pasta"].habilitar(resultado.caminho_relatorio is not None)

    # --- botões do resultado ---

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
        """Limpa os arquivos e o resultado; a pasta escolhida fica (é uma preferência)."""
        self.resultado_conciliacao = None

    def mostrar_inicio(self) -> None:
        self.resultado.mostrar_vazio("Nenhum resultado ainda", TEXTO_VAZIO)
