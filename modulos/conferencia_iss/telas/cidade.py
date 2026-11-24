"""Aba de uma prefeitura no módulo Conferência ISS (era a PainelISS de interface/janela.py do
Conciliações AMES, um item do menu por cidade).

Mesmos cartões, prévias, textos e resultado da tela antiga, no layout padrão da Central; o que muda
de uma cidade para outra vem do cadastro (municipios.py):
- CSVs do Tasy (um ou mais) e o relatório da prefeitura; um cartão com erro bloqueia o botão;
- a prévia do relatório da prefeitura roda em segundo plano (o PDF de Cidade Zeta leva alguns segundos)
  e uma leitura antiga (arquivo trocado ou limpo no meio) é ignorada;
- resultado: números, tabela por situação, as conferências de "nada sumiu", avisos e os botões
  "Abrir pasta", "Ver avisos" e "Novo".

Sem regra de negócio: a tela só chama processamento.py e mostra o que volta.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from central import tema
from central.componentes import BotaoSecundario, Coluna, GrupoNumeros, JanelaTexto, LinhaConferencia, TabelaSimples
from central.painel_base import PainelPadrao, formatar_inteiro, formatar_reais
from modulos.conferencia_iss import processamento
from modulos.conferencia_iss.processamento import (
    IDENTIFICACAO_CNPJ,
    IDENTIFICACAO_INSCRICAO,
    NIVEL_ERRO,
    SITUACAO_CANCELADA_COM_TASY,
    SITUACAO_CANCELADA_SEM_TASY,
    SITUACAO_CONFERIDA,
    SITUACAO_CONFERIDA_AJUSTADO,
    SITUACAO_CONFERIDA_SEM_CPF,
    SITUACAO_DIVERGENCIA,
    SITUACAO_NOME_DIFERENTE,
    SITUACAO_SOMENTE_PREFEITURA,
    SITUACAO_SOMENTE_TASY,
    Municipio,
    PreviaPrefeitura,
    Resultado,
)

TIPOS_CSV = [("Relatórios do Tasy (CSV)", "*.csv"), ("Todos os arquivos", "*.*")]

# Nomes curtos das situações para a tabela da tela (o Excel usa os nomes completos)
NOMES_CURTOS = {
    SITUACAO_CONFERIDA: "Conferidas",
    SITUACAO_CONFERIDA_AJUSTADO: "Conferidas (número ajustado)",
    SITUACAO_CONFERIDA_SEM_CPF: "Conferidas sem CPF",
    SITUACAO_DIVERGENCIA: "Divergência de valor",
    SITUACAO_NOME_DIFERENTE: "Nome diferente (verificar)",
    SITUACAO_SOMENTE_TASY: "Somente no Tasy",
    SITUACAO_SOMENTE_PREFEITURA: "Somente na prefeitura",
    SITUACAO_CANCELADA_COM_TASY: "Canceladas (lançadas no Tasy)",
    SITUACAO_CANCELADA_SEM_TASY: "Canceladas (sem nota no Tasy)",
}
# Situações sem nota do Tasy: a tabela mostra linhas e valor da prefeitura
SITUACOES_SO_PREFEITURA = (SITUACAO_SOMENTE_PREFEITURA, SITUACAO_CANCELADA_SEM_TASY)

TEXTO_VAZIO = "Selecione os CSVs do Tasy e o relatório da prefeitura e clique em Gerar relatório."


def nome_curto(situacao: str) -> str:
    if situacao in NOMES_CURTOS:
        return NOMES_CURTOS[situacao]
    # "Notas escrituradas 2 vezes na prefeitura" → "Escrituradas 2 vezes"
    return situacao.replace("Notas escrituradas", "Escrituradas").replace(" na prefeitura", "")


def descricao_da_cidade(cidade: Municipio) -> str:
    """A frase do cabeçalho com a aba da cidade aberta (a mesma da tela antiga)."""
    return (f"Compara as notas do Tasy com {cidade.artigo_relatorio} {cidade.nome_relatorio} "
            f"da Prefeitura de {cidade.nome}.")


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


class PainelCidadeISS(PainelPadrao):
    TEXTO_BOTAO = "Gerar relatório"

    def __init__(self, pai, info, cidade: Municipio):
        self.cidade = cidade
        self.resultado_conferencia: Resultado | None = None
        self.janela_avisos: JanelaTexto | None = None
        self.lendo_prefeitura = False        # prévia do relatório da prefeitura em andamento
        self._leitura_prefeitura = 0         # conta as leituras (ignora o resultado de uma antiga)
        super().__init__(pai, info, com_cabecalho=False)

        self.cartao_tasy = self.adicionar_arquivo(
            "Relatórios do Tasy (CSV)", tipo="arquivos", tipos_arquivo=TIPOS_CSV, ao_mudar=self._ao_mudar_tasy,
            titulo_dialogo="Selecione um ou mais CSVs do Tasy")
        self.cartao_prefeitura = self.adicionar_arquivo(
            cidade.rotulo_arquivo,
            tipos_arquivo=[("Relatório da prefeitura", cidade.padrao_arquivo), ("Todos os arquivos", "*.*")],
            ao_mudar=self._ao_mudar_prefeitura,
            titulo_dialogo=f"Selecione {cidade.artigo_relatorio} {cidade.nome_relatorio} ({cidade.nome})")

        # "Limpar tudo" ao lado de "Gerar relatório", como na tela antiga
        self.botao.pack_forget()
        self.botao.pack(side="left", fill="x", expand=True)
        self.botao_limpar_tudo = BotaoSecundario(self.area_botoes, "Limpar tudo", self.novo, icone="erro")
        self.botao_limpar_tudo.pack(side="left", padx=(tema.ESPACO_PEQUENO, 0))
        self.atualizar_botoes()

    # --- escolha dos arquivos ---

    def _ao_mudar_tasy(self, caminhos: list[Path]) -> None:
        if not caminhos:
            return
        try:
            previa = processamento.previa_tasy(caminhos)
        except Exception as erro:   # rede de segurança: a prévia nunca derruba a tela
            self.cartao_tasy.definir_confirmacao(f"Erro inesperado ao ler os arquivos: {erro}", "erro")
            return
        if previa.notas == 0 and previa.erros:
            self.cartao_tasy.definir_confirmacao(previa.erros[0], "erro")
            return
        texto = f"{formatar_inteiro(previa.notas)} notas"
        status = "ok"
        if previa.unidades_misturadas:
            texto += " · atenção: unidades misturadas (" + ", ".join(previa.unidades) + ")"
            status = "atencao"
        elif previa.unidades:
            texto += f" · unidade {previa.unidades[0]}"
        if previa.erros:
            texto += f" · {len(previa.erros)} arquivo(s) com erro: " + "; ".join(previa.erros)
            status = "atencao"
        self.cartao_tasy.definir_confirmacao(texto, status)

    def _ao_mudar_prefeitura(self, caminhos: list[Path]) -> None:
        # A prévia roda em segundo plano: o PDF de Cidade Zeta leva alguns segundos para ler
        # e a janela não pode congelar. Uma leitura antiga (arquivo trocado) é ignorada.
        self._leitura_prefeitura += 1
        self.lendo_prefeitura = bool(caminhos)
        if caminhos:
            leitura = self._leitura_prefeitura
            caminho, codigo = caminhos[0], self.cidade.codigo
            self.cartao_prefeitura.definir_confirmacao("Lendo o arquivo...", None)
            self.ler_em_segundo_plano(lambda: processamento.previa_prefeitura(caminho, codigo),
                                      lambda previa: self._mostrar_previa_prefeitura(previa, leitura))

    def _mostrar_previa_prefeitura(self, previa: PreviaPrefeitura | None, leitura: int) -> None:
        if leitura != self._leitura_prefeitura or not self.winfo_exists():
            return                       # o arquivo foi trocado ou limpo enquanto lia
        self.lendo_prefeitura = False
        if previa is None:               # ler_em_segundo_plano devolve None quando a leitura falha
            previa = PreviaPrefeitura(erro="Erro inesperado ao ler o arquivo.")
        if previa.erro:
            self.cartao_prefeitura.definir_confirmacao(previa.erro, "erro")
        else:
            competencia = (f"Competência {previa.competencia_texto}" if previa.competencia_texto
                           else "Competência não encontrada")
            if self.cidade.identificacao == IDENTIFICACAO_INSCRICAO:
                identificacao = previa.inscricao_municipal
                texto_identificacao = f"Inscr. {identificacao}" if identificacao else "inscrição não encontrada"
            elif self.cidade.identificacao == IDENTIFICACAO_CNPJ:   # Cidade Gama
                identificacao = previa.documento_tomador
                texto_identificacao = (f"CNPJ {identificacao}" if identificacao
                                       else "CNPJ da unidade não encontrado")
            else:                        # Cidade Alfa: o relatório não identifica a unidade
                identificacao, texto_identificacao = "-", ""
            partes = [competencia, texto_identificacao, f"{formatar_inteiro(previa.linhas)} linhas"]
            texto = " · ".join(p for p in partes if p)
            completo = previa.competencia_texto and identificacao
            self.cartao_prefeitura.definir_confirmacao(texto, "ok" if completo else "atencao")
        self.atualizar_botoes()

    def pronto_para_processar(self) -> bool:
        if len(self.cartoes) < 2:
            return False
        return all(c.preenchido and c.status_confirmacao != "erro" for c in self.cartoes) \
            and not self.lendo_prefeitura

    def atualizar_botoes(self) -> None:
        super().atualizar_botoes()
        if hasattr(self, "botao_limpar_tudo"):
            algo = any(c.preenchido for c in self.cartoes) or self.resultado_conferencia is not None
            self.botao_limpar_tudo.habilitar(not self.ocupado and algo)
        for cartao in self.cartoes:
            cartao.botao.habilitar(not self.ocupado)
            cartao.botao_limpar.configure(state="disabled" if self.ocupado else "normal")

    # --- processamento ---

    def processar(self) -> None:
        if self.ocupado or not self.pronto_para_processar():
            return
        tasy, prefeitura, codigo = self.cartao_tasy.caminhos, self.cartao_prefeitura.caminho, self.cidade.codigo
        self.executar(lambda progresso: processamento.processar(tasy, prefeitura, codigo, progresso),
                      self.mostrar_resultado)

    def mostrar_resultado(self, resultado: Resultado) -> None:
        self.resultado_conferencia = resultado
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
            numeros = processamento.numeros_principais(resultado)
            GrupoNumeros(area, [
                (formatar_inteiro(numeros.conferidas), "Conferidas", "ok"),
                (formatar_inteiro(numeros.somente_tasy), "Somente no Tasy", "principal"),
                (formatar_inteiro(numeros.para_analisar), "Para analisar",
                 "atencao" if numeros.para_analisar else "ok"),
            ]).pack(fill="x")

            linhas_tabela = []
            for situacao, notas, linhas, total_tasy, total_prefeitura in processamento.linhas_do_resumo(resultado):
                if situacao in SITUACOES_SO_PREFEITURA:
                    linhas_tabela.append((nome_curto(situacao), formatar_inteiro(linhas),
                                          formatar_reais(total_prefeitura)))
                else:
                    linhas_tabela.append((nome_curto(situacao), formatar_inteiro(notas), formatar_reais(total_tasy)))
            TabelaSimples(area, [Coluna("Situação", peso=3), Coluna("Qtd.", numero=True),
                                 Coluna("Valor (R$)", numero=True, peso=2)],
                          linhas_tabela).pack(fill="x", pady=(tema.ESPACO_ENTRE_BLOCOS, 0))

            (notas_rel, notas_lidas), (linhas_rel, linhas_lidas) = processamento.conferencia_nada_sumiu(resultado)
            conferencias = ctk.CTkFrame(area, fg_color="transparent")
            conferencias.pack(fill="x", pady=(tema.ESPACO_ENTRE_BLOCOS, 0))
            for texto, no_relatorio, lidas in [
                ("Notas do Tasy no relatório", notas_rel, notas_lidas),
                ("Linhas da prefeitura no relatório", linhas_rel, linhas_lidas),
            ]:
                LinhaConferencia(conferencias, texto, "ok" if no_relatorio == lidas else "erro",
                                 f"{formatar_inteiro(no_relatorio)} de {formatar_inteiro(lidas)}"
                                 ).pack(fill="x", pady=(0, 6))

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
        caminho = self.resultado_conferencia.caminho_relatorio if self.resultado_conferencia else None
        if caminho is None:
            return
        try:
            if caminho.exists():
                subprocess.Popen(f'explorer /select,"{caminho}"')
            else:
                os.startfile(caminho.parent)  # noqa: S606
        except OSError as erro:
            messagebox.showerror(self.cidade.titulo, f"Não foi possível abrir a pasta: {erro}", parent=self)

    def ver_avisos(self) -> None:
        if self.resultado_conferencia is None:
            return
        if self.janela_avisos is not None and self.janela_avisos.winfo_exists():
            self.janela_avisos.destroy()
        self.janela_avisos = JanelaTexto(self.winfo_toplevel(), "Avisos da conferência", "Avisos",
                                         linhas_dos_avisos(self.resultado_conferencia))

    def ao_novo(self) -> None:
        self.resultado_conferencia = None
        self._leitura_prefeitura += 1        # descarta uma prévia que ainda esteja lendo
        self.lendo_prefeitura = False

    def mostrar_inicio(self) -> None:
        self.resultado.mostrar_vazio("Nenhum resultado ainda", TEXTO_VAZIO)
