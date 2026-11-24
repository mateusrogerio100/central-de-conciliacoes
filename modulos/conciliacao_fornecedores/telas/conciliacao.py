"""Aba "Conciliação" do módulo Fornecedores (era interface/painel_fornecedores.py do Conciliações AMES).

Mesmos cartões, prévias, textos e resultado da tela antiga, no layout padrão da Central:
- Balancete e Relatório analítico de títulos a pagar (obrigatórios, .xls como saem do Tasy; .xlsx
  também é aceito) e a pasta onde salvar (opcional, lembrada entre aberturas);
- ao escolher os dois relatórios, a tela confere se são da mesma unidade (erro bloqueia o botão);
- resultado: números, totais, o que não bateu, avisos e os botões da planilha.

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
    botoes_da_planilha,
    rotulo_arquivo_salvo,
)
from central.painel_base import PainelPadrao, formatar_inteiro, formatar_reais
from modulos.conciliacao_fornecedores import processamento
from modulos.conciliacao_fornecedores.processamento import (
    ABA_TITULOS,
    NIVEL_ERRO,
    NOMES_RESUMO,
    SITUACAO_OK,
    PreviaFornecedores,
    ResultadoFornecedores,
)

TIPOS_TASY = [("Relatórios do Tasy (.xls, .xlsx)", "*.xls *.xlsx"), ("Todos os arquivos", "*.*")]
TEXTO_SEM_PASTA = "Sem escolher, a planilha vai para a pasta do balancete."
TEXTO_VAZIO = ("Selecione o balancete e o relatório analítico de títulos a pagar (do jeito que saem do "
               "Tasy) e clique em Gerar relatório.")
MAXIMO_ITENS_NA_TELA = 12      # o resto fica na planilha
MAXIMO_LETRAS_NOME = 28        # a tabela corta o texto que não cabe: o nome é encurtado com "…"
SITUACOES_CURTAS = {"Divergente": "Divergente", "Só no Balancete": "Só no balancete",
                    "Só no Relatório Financeiro": "Só no financeiro"}


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


class PainelConciliacaoFornecedores(PainelPadrao):
    TEXTO_BOTAO = "Gerar relatório"

    def __init__(self, pai, info):
        self.resultado_conciliacao: ResultadoFornecedores | None = None
        self.janela_avisos: JanelaTexto | None = None
        self.cartoes_relatorios: tuple = ()
        super().__init__(pai, info, com_cabecalho=False)

        self.cartao_balancete = self.adicionar_arquivo(
            "Balancete (865) – conta 2111 Fornecedores", tipos_arquivo=TIPOS_TASY,
            ao_mudar=self._ao_mudar_balancete, titulo_dialogo="Selecione o Balancete (Tasy 865)")
        self.cartao_titulos = self.adicionar_arquivo(
            "Títulos a pagar – Analítico", tipos_arquivo=TIPOS_TASY, ao_mudar=self._ao_mudar_titulos,
            titulo_dialogo="Selecione o Relatório analítico de títulos a pagar (Tasy)")
        # a pasta é opcional e fica com o "Novo" (é uma preferência): por isso é o cartao_saida da base
        self.cartao_pasta = self.cartao_saida = self.adicionar_arquivo(
            "Pasta para salvar a planilha · opcional", tipo="pasta", ao_mudar=self._ao_mudar_pasta,
            titulo_dialogo="Escolha a pasta onde salvar a planilha")
        self.cartoes_relatorios = (self.cartao_balancete, self.cartao_titulos)

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

    # --- escolha dos arquivos ---

    @staticmethod
    def _mostrar_previa(cartao, previa: PreviaFornecedores) -> None:
        if previa.erro:
            cartao.definir_confirmacao(previa.erro, "erro")
        elif previa.avisos:
            cartao.definir_confirmacao(f"{previa.descricao} · atenção: " + "; ".join(previa.avisos), "atencao")
        else:
            cartao.definir_confirmacao(previa.descricao, "ok")

    def _ao_mudar(self, cartao, caminhos: list[Path], funcao_previa) -> None:
        if caminhos:
            try:
                previa = funcao_previa(caminhos[0])
            except Exception as erro:   # rede de segurança: a prévia nunca derruba a tela
                previa = PreviaFornecedores(erro=f"Erro inesperado ao ler o arquivo: {erro}")
            self._mostrar_previa(cartao, previa)
        self._conferir_par()

    def _ao_mudar_balancete(self, caminhos: list[Path]) -> None:
        self._ao_mudar(self.cartao_balancete, caminhos, processamento.previa_balancete)

    def _ao_mudar_titulos(self, caminhos: list[Path]) -> None:
        self._ao_mudar(self.cartao_titulos, caminhos, processamento.previa_titulos)

    def _conferir_par(self) -> None:
        """Com os dois escolhidos e lidos: unidade diferente → erro."""
        if not all(c.preenchido and c.status_confirmacao != "erro" for c in self.cartoes_relatorios):
            return
        try:
            par = processamento.conferir_par(self.cartao_balancete.caminho, self.cartao_titulos.caminho)
        except Exception:
            return
        if par.erro:
            self.cartao_titulos.definir_confirmacao(par.erro, "erro")
        elif par.avisos:
            texto = self.cartao_titulos.texto_confirmacao.split(" · atenção:")[0]
            self.cartao_titulos.definir_confirmacao(f"{texto} · atenção: " + "; ".join(par.avisos), "atencao")

    def _ao_mudar_pasta(self, caminhos: list[Path]) -> None:
        if caminhos:
            self.cartao_pasta.definir_confirmacao(f"A planilha será salva em {caminhos[0]}", "ok")
        else:
            self.cartao_pasta.definir_confirmacao(TEXTO_SEM_PASTA, None)
        processamento.salvar_pasta_lembrada(str(caminhos[0]) if caminhos else "")

    def pronto_para_processar(self) -> bool:
        return all(c.preenchido and c.status_confirmacao != "erro" for c in self.cartoes_relatorios)

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
        balancete, titulos, pasta = self.cartao_balancete.caminho, self.cartao_titulos.caminho, self.cartao_pasta.caminho
        self.executar(lambda progresso: processamento.processar(balancete, titulos, pasta, progresso),
                      self.mostrar_resultado)

    def mostrar_resultado(self, resultado: ResultadoFornecedores) -> None:
        self.resultado_conciliacao = resultado
        self.atualizar_botoes()
        cartao = self.resultado
        area = cartao.mostrar_conteudo()

        cartao.definir_selo("Concluído" if resultado.caminho_relatorio else "Relatório não gerado",
                            "ok" if resultado.caminho_relatorio else "erro")
        if resultado.erro:
            LinhaConferencia(area, resultado.erro, status="erro").pack(fill="x", pady=(0, tema.ESPACO_PEQUENO))

        if resultado.linhas:
            contexto = " · ".join(t for t in (processamento.nome_curto_unidade(resultado.unidade),
                                              processamento.mes_curto(resultado.mes)) if t)
            TextoQuebravel(area, contexto, tema.fonte_texto_forte()).pack(fill="x", pady=(0, tema.ESPACO_PEQUENO))

            numeros = processamento.numeros_principais(resultado)
            GrupoNumeros(area, [
                (formatar_inteiro(numeros.ok), "Fornecedores OK", "ok"),
                (formatar_inteiro(numeros.nao_ok), "Divergentes ou sem par", "atencao" if numeros.nao_ok else "ok"),
                (formatar_inteiro(numeros.linhas), "Linhas na conciliação", "principal"),
            ]).pack(fill="x")

            diferenca = (resultado.total_balancete or 0) - (resultado.total_financeiro or 0)
            TabelaSimples(area, [Coluna("Total", peso=3), Coluna("Valor (R$)", numero=True, peso=2)], [
                ("Balancete (conta 2111)", formatar_reais(resultado.total_balancete or 0)),
                ("Títulos a pagar", formatar_reais(resultado.total_financeiro or 0)),
                ("Diferença", formatar_reais(diferenca)),
            ]).pack(fill="x", pady=(tema.ESPACO_ENTRE_BLOCOS, 0))

            fora = [l for l in resultado.linhas if l.situacao != SITUACAO_OK]
            if fora:
                itens = [(encurtar(l.conta.descricao if l.conta else l.nome_financeiro),
                          SITUACOES_CURTAS[NOMES_RESUMO[l.situacao]], formatar_reais(l.diferenca))
                         for l in fora[:MAXIMO_ITENS_NA_TELA]]
                TabelaSimples(area, [Coluna("Fornecedor", peso=5), Coluna("Situação", peso=3),
                                     Coluna("Diferença", numero=True, peso=3)],
                              itens).pack(fill="x", pady=(tema.ESPACO_ENTRE_BLOCOS, 0))
                if len(fora) > MAXIMO_ITENS_NA_TELA:
                    ctk.CTkLabel(area, text=f"e mais {len(fora) - MAXIMO_ITENS_NA_TELA} na planilha",
                                 font=tema.fonte_legenda(), text_color=tema.COR_TEXTO_SUAVE,
                                 anchor="w").pack(fill="x", pady=(4, 0))
                titulos = sum(len(f.titulos) for l in fora for f in l.financeiros)
                if titulos:
                    ctk.CTkLabel(area, text=f"Nr. Doc. e Nr. Título de {formatar_inteiro(titulos)} título(s) na "
                                            f"aba \"{ABA_TITULOS}\" da planilha",
                                 font=tema.fonte_legenda(), text_color=tema.COR_TEXTO_SUAVE, anchor="w",
                                 justify="left", wraplength=300).pack(fill="x", pady=(4, 0))

        erros = sum(1 for a in resultado.avisos if a.nivel == NIVEL_ERRO)
        avisos = sum(1 for a in resultado.avisos if not a.tipo_arquivo)
        if erros:
            texto, status = f"{erros} arquivo(s) não puderam ser lidos — veja os avisos", "erro"
        elif avisos:
            texto, status = f"{avisos} aviso(s) para conferir — veja os avisos", "atencao"
        else:
            texto, status = "Nenhum aviso", "ok"
        LinhaConferencia(area, texto, status).pack(fill="x", pady=(tema.ESPACO_PEQUENO, 0))

        rotulo_arquivo_salvo(area, resultado.caminho_relatorio)
        botoes_da_planilha(cartao.rodape, resultado.caminho_relatorio, self.abrir_planilha, self.abrir_pasta,
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
        self.resultado.mostrar_vazio("Nenhum resultado ainda", TEXTO_VAZIO)

    def mostrar_inicio(self) -> None:
        self.resultado.mostrar_vazio("Nenhum resultado ainda", TEXTO_VAZIO)
