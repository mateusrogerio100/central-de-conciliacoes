"""Aba "Comparação Ativo x Passivo" do módulo Imobilizado – AME's (pedido do usuário, 05/11/2026).

Cartões: Razão do Ativo, Razão do Passivo (obrigatórios) e a pasta onde salvar (opcional; a mesma pasta
lembrada da aba "Conciliação"). Resultado: AME e mês, números (Conferem, Diferenças, Sem par), a tabela das
contas que não conferem, os totais, avisos e os botões "Abrir pasta", "Ver avisos" e "Novo".

Sem regra de negócio: a tela só chama processamento.py e mostra o que volta (ESPECIFICACAO_IMOBILIZADO.md, seção 6).
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
    LADO_ATIVO,
    LADO_PASSIVO,
    NIVEL_ERRO,
    SITUACAO_AP_CONFERE,
    SITUACAO_AP_DIFERENCA,
    SITUACAO_AP_SEM_PAR,
    PreviaRazaoContabil,
    ResultadoAtivoPassivo,
)

TIPOS_TASY = [("Relatórios do Tasy (.xls)", "*.xls"), ("Todos os arquivos", "*.*")]
TEXTO_SEM_PASTA = "Sem escolher, a planilha vai para a pasta do razão do Ativo."
TEXTO_VAZIO = ("Selecione o razão do Ativo e o razão do Passivo (os dois do Tasy, do mesmo AME e mês) "
               "e clique em Comparar Ativo x Passivo.")


def linhas_dos_avisos(resultado: ResultadoAtivoPassivo) -> list[str]:
    """O texto da janela "Ver avisos" (mesmo formato da aba "Conciliação")."""
    arquivos = [a for a in resultado.avisos if a.tipo_arquivo]
    outros = [a for a in resultado.avisos if not a.tipo_arquivo]
    linhas = ["ARQUIVOS LIDOS"]
    for aviso in arquivos:
        linhas.append(f"• {aviso.arquivo} ({aviso.tipo_arquivo}): {aviso.mensagem}")
    linhas.append("")
    linhas.append(f"AVISOS ({len(outros)})")
    if not outros:
        linhas.append("Nenhum aviso.")
    for aviso in outros:
        linhas.append(f"• [{aviso.arquivo}] {aviso.mensagem}")
    return linhas


class PainelAtivoPassivo(PainelPadrao):
    TEXTO_BOTAO = "Comparar Ativo x Passivo"

    def __init__(self, pai, info):
        self.resultado_comparacao: ResultadoAtivoPassivo | None = None
        self.janela_avisos: JanelaTexto | None = None
        self.cartoes_relatorios: tuple = ()
        super().__init__(pai, info, com_cabecalho=False)

        self.cartao_ativo = self.adicionar_arquivo(
            "Razão do Ativo (contas 1.x)", tipos_arquivo=TIPOS_TASY,
            ao_mudar=lambda c: self._ao_mudar(self.cartao_ativo, c, LADO_ATIVO),
            titulo_dialogo="Selecione o razão contábil do Ativo (Tasy)")
        self.cartao_passivo = self.adicionar_arquivo(
            "Razão do Passivo (contas 2.x)", tipos_arquivo=TIPOS_TASY,
            ao_mudar=lambda c: self._ao_mudar(self.cartao_passivo, c, LADO_PASSIVO),
            titulo_dialogo="Selecione o razão contábil do Passivo (Tasy)")
        self.cartao_pasta = self.cartao_saida = self.adicionar_arquivo(
            "Pasta para salvar a planilha · opcional", tipo="pasta", ao_mudar=self._ao_mudar_pasta,
            titulo_dialogo="Escolha a pasta onde salvar a planilha")
        self.cartoes_relatorios = (self.cartao_ativo, self.cartao_passivo)

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

    # --- escolha dos arquivos (pequenos: a prévia é rápida, sem segundo plano) ---

    def _ao_mudar(self, cartao, caminhos: list[Path], lado: str) -> None:
        if not caminhos:
            return
        try:
            previa = processamento.previa_razao_contabil(caminhos[0], lado)
        except Exception as erro:   # rede de segurança: a prévia nunca derruba a tela
            previa = PreviaRazaoContabil(erro=f"Erro inesperado ao ler o arquivo: {erro}")
        if previa.erro:
            cartao.definir_confirmacao(previa.erro, "erro")
        elif previa.avisos:
            cartao.definir_confirmacao(f"{previa.descricao} · atenção: " + "; ".join(previa.avisos), "atencao")
        else:
            cartao.definir_confirmacao(previa.descricao, "ok")

    def _ao_mudar_pasta(self, caminhos: list[Path]) -> None:
        if caminhos:
            self.cartao_pasta.definir_confirmacao(f"A planilha será salva em {caminhos[0]}", "ok")
        else:
            self.cartao_pasta.definir_confirmacao(TEXTO_SEM_PASTA, None)
        processamento.salvar_pasta_lembrada(str(caminhos[0]) if caminhos else "")

    def pronto_para_processar(self) -> bool:
        if not self.cartoes_relatorios:
            return False
        return all(c.preenchido and c.status_confirmacao != "erro" for c in self.cartoes_relatorios)

    def atualizar_botoes(self) -> None:
        super().atualizar_botoes()
        if hasattr(self, "botao_limpar_tudo"):
            algo = any(c.preenchido for c in self.cartoes_relatorios) or self.resultado_comparacao is not None
            self.botao_limpar_tudo.habilitar(not self.ocupado and algo)
        for cartao in self.cartoes:
            cartao.botao.habilitar(not self.ocupado)
            cartao.botao_limpar.configure(state="disabled" if self.ocupado else "normal")

    # --- processamento ---

    def processar(self) -> None:
        if self.ocupado or not self.pronto_para_processar():
            return
        ativo, passivo, pasta = self.cartao_ativo.caminho, self.cartao_passivo.caminho, self.cartao_pasta.caminho
        self.executar(lambda progresso: processamento.processar_ativo_passivo(ativo, passivo, pasta, progresso),
                      self.mostrar_resultado)

    def mostrar_resultado(self, resultado: ResultadoAtivoPassivo) -> None:
        self.resultado_comparacao = resultado
        self.atualizar_botoes()
        cartao = self.resultado
        area = cartao.mostrar_conteudo()

        if resultado.caminho_relatorio is not None:
            cartao.definir_selo("Concluído", "ok")
        else:
            cartao.definir_selo("Relatório não gerado", "erro")
        if resultado.erro:
            LinhaConferencia(area, resultado.erro, status="erro").pack(fill="x", pady=(0, tema.ESPACO_PEQUENO))

        if resultado.pares:
            contexto = " · ".join(t for t in (resultado.ame, resultado.competencia_texto) if t)
            if contexto:
                TextoQuebravel(area, contexto, tema.fonte_texto_forte()).pack(fill="x", pady=(0, tema.ESPACO_PEQUENO))
            diferencas = resultado.contar(SITUACAO_AP_DIFERENCA)
            sem_par = resultado.contar(SITUACAO_AP_SEM_PAR)
            GrupoNumeros(area, [
                (formatar_inteiro(resultado.contar(SITUACAO_AP_CONFERE)), "Conferem", "ok"),
                (formatar_inteiro(diferencas), "Diferenças", "atencao" if diferencas else "ok"),
                (formatar_inteiro(sem_par), "Sem par", "atencao" if sem_par else "ok"),
            ]).pack(fill="x")

            pendentes = [p for p in resultado.pares if p.situacao != SITUACAO_AP_CONFERE]
            if pendentes:
                linhas = [((p.ativo or p.passivo).nome, formatar_reais(p.diferenca),
                           "Sem par" if p.situacao == SITUACAO_AP_SEM_PAR else "Diferença")
                          for p in pendentes]
                TabelaSimples(area, [Coluna("Conta", peso=4), Coluna("Diferença (R$)", numero=True, peso=2),
                                     Coluna("Situação", peso=2)],
                              linhas).pack(fill="x", pady=(tema.ESPACO_ENTRE_BLOCOS, 0))
            else:
                LinhaConferencia(area, "Todas as contas do Ativo conferem com as do Passivo.", "ok").pack(
                    fill="x", pady=(tema.ESPACO_ENTRE_BLOCOS, 0))
            TextoQuebravel(
                area,
                f"Total Ativo {formatar_reais(resultado.total('saldo_ativo'))} · Total Passivo "
                f"{formatar_reais(resultado.total('saldo_passivo'))} · Diferença {formatar_reais(resultado.total('diferenca'))}",
                tema.fonte_legenda(),
            ).pack(fill="x", pady=(tema.ESPACO_PEQUENO, 0))

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
        caminho = self.resultado_comparacao.caminho_relatorio if self.resultado_comparacao else None
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
        if self.resultado_comparacao is None:
            return
        if self.janela_avisos is not None and self.janela_avisos.winfo_exists():
            self.janela_avisos.destroy()
        self.janela_avisos = JanelaTexto(self.winfo_toplevel(), "Avisos da comparação Ativo x Passivo", "Avisos",
                                         linhas_dos_avisos(self.resultado_comparacao))

    def ao_novo(self) -> None:
        """Limpa os razões e o resultado; a pasta escolhida fica (é uma preferência)."""
        self.resultado_comparacao = None

    def mostrar_inicio(self) -> None:
        self.resultado.mostrar_vazio("Nenhum resultado ainda", TEXTO_VAZIO)
