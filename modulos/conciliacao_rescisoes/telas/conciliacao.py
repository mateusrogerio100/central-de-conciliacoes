"""Aba "Conciliação" do módulo Rescisões (era interface/painel_rescisoes.py do Conciliações AMES).

Mesmos cartões, prévias, textos e resultado da tela antiga, no layout padrão da Central:
- Razão da conta Rescisões a pagar, eventos da folha em PDF ou Excel (0264 – Líquido Rescisão; um ou mais:
  o mensal e os complementares) e a lista de Rescisões a pagar do mês anterior (os três obrigatórios), os
  títulos a pagar do financeiro (opcional: comparados com a lista nova) e a pasta onde salvar (opcional,
  lembrada entre aberturas);
- com os três escolhidos, a tela diz quais PDFs entram no mês e avisa se o mês do razão e o do PDF não
  batem, ou se o saldo anterior não bate com a lista anterior;
- resultado: números, saldo final × lista nova com a composição da diferença, os não encontrados, o
  financeiro, avisos e os botões da planilha.

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
from modulos.conciliacao_rescisoes import processamento
from modulos.conciliacao_rescisoes.processamento import (
    ABA_DIFERENTES,
    ABA_FINANCEIRO,
    ABA_LISTA,
    NIVEL_ERRO,
    ORIGEM_NAO_ENCONTRADO,
    PreviaRescisoes,
    ResultadoRescisoes,
)

TIPOS_TASY = [("Relatórios do Tasy (.xls, .xlsx)", "*.xls *.xlsx"), ("Todos os arquivos", "*.*")]
TIPOS_PDF = [("PDF ou Excel da folha (.pdf, .xlsx)", "*.pdf *.xlsx"), ("Todos os arquivos", "*.*")]
TIPOS_PLANILHA = [("Planilhas (.xlsx, .xls)", "*.xlsx *.xls"), ("Todos os arquivos", "*.*")]
TEXTO_SEM_PASTA = "Sem escolher, a planilha vai para a pasta do razão."
TEXTO_SEM_FINANCEIRO = "Sem escolher, a lista nova não é comparada com o financeiro."
TEXTO_VAZIO = "Selecione os três arquivos e clique em Gerar relatório."
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


class PainelConciliacaoRescisoes(PainelPadrao):
    TEXTO_BOTAO = "Gerar relatório"

    def __init__(self, pai, info):
        self.resultado_conciliacao: ResultadoRescisoes | None = None
        self.janela_avisos: JanelaTexto | None = None
        self.cartoes_obrigatorios: tuple = ()
        super().__init__(pai, info, com_cabecalho=False)

        self.cartao_razao = self.adicionar_arquivo(
            "Razão – conta Rescisões a pagar", tipos_arquivo=TIPOS_TASY, ao_mudar=self._ao_mudar_razao,
            titulo_dialogo="Selecione o Razão da conta Rescisões a pagar (Tasy)")
        self.cartao_eventos = self.adicionar_arquivo(
            "Eventos da folha (PDF ou Excel) – 0264 Líquido Rescisão · um ou mais", tipo="arquivos",
            tipos_arquivo=TIPOS_PDF, ao_mudar=self._ao_mudar_eventos,
            titulo_dialogo="Selecione os eventos da folha – PDF ou Excel (mensal e complementares)")
        self.cartao_controle = self.adicionar_arquivo(
            "Rescisões a pagar – lista do mês anterior", tipos_arquivo=TIPOS_PLANILHA,
            ao_mudar=self._ao_mudar_controle,
            titulo_dialogo="Selecione a planilha Rescisões a pagar do mês anterior")
        self.cartao_financeiro = self.adicionar_arquivo(
            "Títulos a pagar do financeiro · opcional", tipos_arquivo=TIPOS_TASY,
            ao_mudar=self._ao_mudar_financeiro,
            titulo_dialogo="Selecione o relatório de títulos a pagar do financeiro (Tasy)")
        # a pasta é opcional e fica com o "Novo" (é uma preferência): por isso é o cartao_saida da base
        self.cartao_pasta = self.cartao_saida = self.adicionar_arquivo(
            "Pasta para salvar a planilha · opcional", tipo="pasta", ao_mudar=self._ao_mudar_pasta,
            titulo_dialogo="Escolha a pasta onde salvar a planilha")
        self.cartoes_obrigatorios = (self.cartao_razao, self.cartao_eventos, self.cartao_controle)
        self.cartao_financeiro.definir_confirmacao(TEXTO_SEM_FINANCEIRO, None)

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
    def _mostrar_previa(cartao, previa: PreviaRescisoes) -> None:
        if previa.erro:
            cartao.definir_confirmacao(previa.erro, "erro")
        elif previa.avisos:
            cartao.definir_confirmacao(f"{previa.descricao} · atenção: " + "; ".join(previa.avisos), "atencao")
        else:
            cartao.definir_confirmacao(previa.descricao, "ok")

    def _ao_mudar(self, cartao, caminhos: list[Path], funcao_previa, todos: bool = False) -> None:
        if caminhos:
            try:
                previa = funcao_previa(caminhos if todos else caminhos[0])
            except Exception as erro:   # rede de segurança: a prévia nunca derruba a tela
                previa = PreviaRescisoes(erro=f"Erro inesperado ao ler o arquivo: {erro}")
            self._mostrar_previa(cartao, previa)
        self._conferir_conjunto()

    def _ao_mudar_razao(self, caminhos: list[Path]) -> None:
        self._ao_mudar(self.cartao_razao, caminhos, processamento.previa_razao)

    def _ao_mudar_eventos(self, caminhos: list[Path]) -> None:
        self._ao_mudar(self.cartao_eventos, caminhos, processamento.previa_eventos, todos=True)

    def _ao_mudar_controle(self, caminhos: list[Path]) -> None:
        self._ao_mudar(self.cartao_controle, caminhos, processamento.previa_controle)

    def _ao_mudar_financeiro(self, caminhos: list[Path]) -> None:
        if caminhos:
            self._ao_mudar(self.cartao_financeiro, caminhos, processamento.previa_financeiro)
        else:
            self.cartao_financeiro.definir_confirmacao(TEXTO_SEM_FINANCEIRO, None)

    def _conferir_conjunto(self) -> None:
        """Com os três escolhidos e lidos: mês diferente ou saldo anterior ≠ lista anterior → aviso."""
        if not all(c.preenchido and c.status_confirmacao != "erro" for c in self.cartoes_obrigatorios):
            return
        try:
            conjunto = processamento.conferir_conjunto(self.cartao_razao.caminho, self.cartao_eventos.caminhos,
                                                       self.cartao_controle.caminho)
        except Exception:
            return
        if conjunto.descricao:              # com vários PDFs: quais entram no mês
            texto = self.cartao_eventos.texto_confirmacao.split(" · entram no mês:")[0]
            self.cartao_eventos.definir_confirmacao(f"{texto} · {conjunto.descricao}",
                                                    self.cartao_eventos.status_confirmacao)
        if conjunto.avisos:
            texto = self.cartao_controle.texto_confirmacao.split(" · atenção:")[0]
            avisos = "; ".join(a.replace("ATENÇÃO: ", "") for a in conjunto.avisos)
            self.cartao_controle.definir_confirmacao(f"{texto} · atenção: {avisos}", "atencao")

    def _ao_mudar_pasta(self, caminhos: list[Path]) -> None:
        if caminhos:
            self.cartao_pasta.definir_confirmacao(f"A planilha será salva em {caminhos[0]}", "ok")
        else:
            self.cartao_pasta.definir_confirmacao(TEXTO_SEM_PASTA, None)
        processamento.salvar_pasta_lembrada(str(caminhos[0]) if caminhos else "")

    def pronto_para_processar(self) -> bool:
        if not self.cartoes_obrigatorios:
            return False
        obrigatorios = all(c.preenchido and c.status_confirmacao != "erro" for c in self.cartoes_obrigatorios)
        financeiro_ok = not (self.cartao_financeiro.preenchido and self.cartao_financeiro.status_confirmacao == "erro")
        return obrigatorios and financeiro_ok

    def atualizar_botoes(self) -> None:
        super().atualizar_botoes()
        if hasattr(self, "botao_limpar_tudo"):
            algo = (any(c.preenchido for c in (*self.cartoes_obrigatorios, self.cartao_financeiro))
                    or self.resultado_conciliacao is not None)
            self.botao_limpar_tudo.habilitar(not self.ocupado and algo)
        for cartao in self.cartoes:
            cartao.botao.habilitar(not self.ocupado)
            cartao.botao_limpar.configure(state="disabled" if self.ocupado else "normal")

    # --- processamento ---

    def processar(self) -> None:
        if self.ocupado or not self.pronto_para_processar():
            return
        razao, eventos, controle = self.cartao_razao.caminho, self.cartao_eventos.caminhos, self.cartao_controle.caminho
        financeiro = self.cartao_financeiro.caminho if self.cartao_financeiro.preenchido else None
        pasta = self.cartao_pasta.caminho
        self.executar(lambda progresso: processamento.processar(razao, eventos, controle, financeiro, pasta, progresso),
                      self.mostrar_resultado)

    def mostrar_resultado(self, resultado: ResultadoRescisoes) -> None:
        self.resultado_conciliacao = resultado
        self.atualizar_botoes()
        cartao = self.resultado
        area = cartao.mostrar_conteudo()

        cartao.definir_selo("Concluído" if resultado.caminho_relatorio else "Relatório não gerado",
                            "ok" if resultado.caminho_relatorio else "erro")
        if resultado.erro:
            LinhaConferencia(area, resultado.erro, status="erro").pack(fill="x", pady=(0, tema.ESPACO_PEQUENO))

        if resultado.baixas or resultado.lista_nova:
            contexto = " · ".join(t for t in (processamento.nome_curto_unidade(resultado.unidade),
                                              processamento.mes_curto(resultado.competencia)) if t)
            TextoQuebravel(area, contexto, tema.fonte_texto_forte()).pack(fill="x", pady=(0, tema.ESPACO_PEQUENO))

            numeros = processamento.numeros_principais(resultado)
            GrupoNumeros(area, [
                (formatar_inteiro(numeros.achados_pdf + numeros.achados_lista), "Pagamentos achados", "ok"),
                (formatar_inteiro(numeros.valores_diferentes), "Valores diferentes",
                 "atencao" if numeros.valores_diferentes else "ok"),
                (formatar_inteiro(numeros.nao_encontrados), "Não encontrados",
                 "atencao" if numeros.nao_encontrados else "ok"),
            ]).pack(fill="x")

            composicao = processamento.composicao_da_diferenca(resultado)
            TabelaSimples(area, [Coluna("Conferência", peso=4), Coluna("Valor (R$)", numero=True, peso=2)], [
                ("Saldo final do razão", formatar_reais(resultado.saldo_final or 0)),
                (f"Lista nova ({formatar_inteiro(numeros.lista_nova)} rescisões)",
                 formatar_reais(resultado.total_lista_nova)),
                ("Diferença", formatar_reais(composicao.diferenca)),
                ("  créditos do razão − PDFs", formatar_reais(composicao.creditos_menos_pdf)),
                ("  pagos a maior", formatar_reais(composicao.valores_diferentes)),
                ("  pagamentos não encontrados", formatar_reais(composicao.nao_encontrados)),
            ] + ([("  composição da lista anterior", formatar_reais(composicao.composicao_anterior))]
                 if resultado.composicao_anterior else []) + [
                ("Sem explicação", formatar_reais(composicao.sem_explicacao)),
            ]).pack(fill="x", pady=(tema.ESPACO_ENTRE_BLOCOS, 0))

            fora = resultado.baixas_de(ORIGEM_NAO_ENCONTRADO)
            if fora:
                itens = [(encurtar(b.pagamento.nome), formatar_reais(b.pagamento.valor))
                         for b in fora[:MAXIMO_ITENS_NA_TELA]]
                TabelaSimples(area, [Coluna("Pagamento não encontrado", peso=5),
                                     Coluna("Valor (R$)", numero=True, peso=2)],
                              itens).pack(fill="x", pady=(tema.ESPACO_ENTRE_BLOCOS, 0))
                if len(fora) > MAXIMO_ITENS_NA_TELA:
                    ctk.CTkLabel(area, text=f"e mais {len(fora) - MAXIMO_ITENS_NA_TELA} na planilha",
                                 font=tema.fonte_legenda(), text_color=tema.COR_TEXTO_SUAVE,
                                 anchor="w").pack(fill="x", pady=(4, 0))
            if resultado.pdfs_fora:
                ctk.CTkLabel(area, text="Não lançado(s) no razão deste mês (provavelmente do mês seguinte), fora "
                                        "da conciliação: " + ", ".join(
                                            f"{l.rotulo} (R$ {formatar_reais(l.total)})" for l in resultado.pdfs_fora),
                             font=tema.fonte_legenda(), text_color=tema.COR_TEXTO_SUAVE, anchor="w",
                             justify="left", wraplength=300).pack(fill="x", pady=(4, 0))
            financeiro = resultado.financeiro
            if financeiro is not None:
                if financeiro.para_conferir:
                    texto = (f"Financeiro × lista: {formatar_inteiro(len(financeiro.para_conferir))} pessoa(s) para "
                             f"conferir (diferença R$ {formatar_reais(financeiro.diferenca)}) — aba "
                             f"\"{ABA_FINANCEIRO}\"")
                    status = "atencao"
                else:
                    texto = f"Financeiro × lista: bate pessoa a pessoa (R$ {formatar_reais(financeiro.total_financeiro)})"
                    if financeiro.nomes_parecidos:
                        texto += f"; {formatar_inteiro(len(financeiro.nomes_parecidos))} com nome escrito diferente"
                    status = "ok"
                LinhaConferencia(area, texto, status).pack(fill="x", pady=(tema.ESPACO_PEQUENO, 0))
            if numeros.valores_diferentes:
                ctk.CTkLabel(area, text=f"Os valores diferentes estão na aba \"{ABA_DIFERENTES}\" da planilha; "
                                        f"a lista nova, na aba \"{ABA_LISTA}\".",
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
        """Limpa os arquivos e o resultado; a pasta escolhida fica (é uma preferência)."""
        self.resultado_conciliacao = None
        self.cartao_financeiro.definir_confirmacao(TEXTO_SEM_FINANCEIRO, None)

    def mostrar_inicio(self) -> None:
        self.resultado.mostrar_vazio("Nenhum resultado ainda", TEXTO_VAZIO)
