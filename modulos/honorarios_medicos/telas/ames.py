"""Aba "AMEs" de Honorários Médicos (era interface/painel_honorarios.py do Conciliações AMES, item
"Honorários" do menu).

Mesmos cartões, prévias, textos e resultado da tela antiga, no layout padrão da Central:
- Balancete (conta de Honorários médicos a pagar) e SCF – Repasse Sintético (obrigatórios, .xls como saem
  do Tasy; .xlsx também é aceito) e a pasta onde salvar (opcional, lembrada entre aberturas);
- com os dois escolhidos, a tela confere se são da mesma unidade (erro) e do mesmo mês (atenção);
- resultado: números, totais (balancete, repasse bruto, diferença, retenções), o que não bateu, avisos e os
  botões da planilha.

Sem regra de negócio: a tela só chama processamento.py e mostra o que volta.
"""

from __future__ import annotations

from pathlib import Path

import customtkinter as ctk

from central import tema
from central.componentes import Coluna, GrupoNumeros, LinhaConferencia, TabelaSimples, TextoQuebravel
from central.painel_base import formatar_inteiro, formatar_reais
from modulos.honorarios_medicos import processamento
from modulos.honorarios_medicos.processamento import (
    NOMES_RESUMO,
    SITUACAO_OK_AMES,
    PreviaHonorarios,
    ResultadoHonorarios,
)
from modulos.honorarios_medicos.telas.comum import MAXIMO_ITENS_NA_TELA, PainelHonorariosBase, encurtar

TIPOS_TASY = [("Relatórios do Tasy (.xls, .xlsx)", "*.xls *.xlsx"), ("Todos os arquivos", "*.*")]
TEXTO_VAZIO = ("Selecione o balancete e o relatório de repasse médico (do jeito que saem do Tasy) e "
               "clique em Gerar relatório.")
SITUACOES_CURTAS = {"Divergente": "Divergente", "Só no Balancete": "Só no balancete",
                    "Só no Repasse": "Só no repasse"}


class PainelHonorariosAmes(PainelHonorariosBase):
    ABA = processamento.ABA_AMES

    def criar_cartoes(self) -> tuple:
        self.cartao_balancete = self.adicionar_arquivo(
            "Balancete (865) – Honorários", tipos_arquivo=TIPOS_TASY, ao_mudar=self._ao_mudar_balancete,
            titulo_dialogo="Selecione o Balancete (Tasy 865)")
        self.cartao_repasse = self.adicionar_arquivo(
            "Repasse médico (SCF)", tipos_arquivo=TIPOS_TASY, ao_mudar=self._ao_mudar_repasse,
            titulo_dialogo="Selecione o relatório SCF – Repasse Sintético (Tasy)")
        return self.cartao_balancete, self.cartao_repasse

    # --- escolha dos arquivos ---

    @staticmethod
    def _mostrar_previa(cartao, previa: PreviaHonorarios) -> None:
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
                previa = PreviaHonorarios(erro=f"Erro inesperado ao ler o arquivo: {erro}")
            self._mostrar_previa(cartao, previa)
        self._conferir_par()

    def _ao_mudar_balancete(self, caminhos: list[Path]) -> None:
        self._ao_mudar(self.cartao_balancete, caminhos, processamento.previa_balancete)

    def _ao_mudar_repasse(self, caminhos: list[Path]) -> None:
        self._ao_mudar(self.cartao_repasse, caminhos, processamento.previa_repasse)

    def _conferir_par(self) -> None:
        """Com os dois escolhidos e lidos: unidade diferente → erro; mês diferente → atenção."""
        if not all(c.preenchido and c.status_confirmacao != "erro" for c in self.cartoes_relatorios):
            return
        try:
            par = processamento.conferir_par(self.cartao_balancete.caminho, self.cartao_repasse.caminho)
        except Exception:
            return
        if par.erro:
            self.cartao_repasse.definir_confirmacao(par.erro, "erro")
        elif par.avisos:
            texto = self.cartao_repasse.texto_confirmacao.split(" · atenção:")[0]
            self.cartao_repasse.definir_confirmacao(f"{texto} · atenção: " + "; ".join(par.avisos), "atencao")

    def pronto_para_processar(self) -> bool:
        if not self.cartoes_relatorios:
            return False
        return all(c.preenchido and c.status_confirmacao != "erro" for c in self.cartoes_relatorios)

    # --- processamento ---

    def processar(self) -> None:
        if self.ocupado or not self.pronto_para_processar():
            return
        balancete, repasse, pasta = self.cartao_balancete.caminho, self.cartao_repasse.caminho, self.cartao_pasta.caminho
        self.executar(lambda progresso: processamento.processar_ames(balancete, repasse, pasta, progresso),
                      self.mostrar_resultado)

    def mostrar_resultado(self, resultado: ResultadoHonorarios) -> None:
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

            numeros = processamento.numeros_ames(resultado)
            GrupoNumeros(area, [
                (formatar_inteiro(numeros.ok), "Médicos OK", "ok"),
                (formatar_inteiro(numeros.nao_ok), "Com diferença ou sem par", "atencao" if numeros.nao_ok else "ok"),
                (formatar_inteiro(numeros.linhas), "Linhas na conciliação", "principal"),
            ]).pack(fill="x")

            diferenca = (resultado.total_balancete or 0) - (resultado.total_repasse or 0)
            conta = resultado.conta_total.codigo if resultado.conta_total else ""
            TabelaSimples(area, [Coluna("Total", peso=3), Coluna("Valor (R$)", numero=True, peso=2)], [
                (f"Balancete (conta {conta})", formatar_reais(resultado.total_balancete or 0)),
                ("Repasse bruto", formatar_reais(resultado.total_repasse or 0)),
                ("Diferença", formatar_reais(diferenca)),
                ("Retenções (bruto − líquido)",
                 formatar_reais((resultado.total_repasse or 0) - (resultado.total_liquido or 0))),
            ]).pack(fill="x", pady=(tema.ESPACO_ENTRE_BLOCOS, 0))

            fora = [l for l in resultado.linhas if l.situacao != SITUACAO_OK_AMES]
            if fora:
                itens = [(encurtar(l.conta.descricao if l.conta else l.nome_repasse),
                          SITUACOES_CURTAS[NOMES_RESUMO[l.situacao]], formatar_reais(l.diferenca))
                         for l in fora[:MAXIMO_ITENS_NA_TELA]]
                TabelaSimples(area, [Coluna("Médico/clínica", peso=5), Coluna("Situação", peso=3),
                                     Coluna("Diferença", numero=True, peso=3)],
                              itens).pack(fill="x", pady=(tema.ESPACO_ENTRE_BLOCOS, 0))
                if len(fora) > MAXIMO_ITENS_NA_TELA:
                    ctk.CTkLabel(area, text=f"e mais {len(fora) - MAXIMO_ITENS_NA_TELA} na planilha",
                                 font=tema.fonte_legenda(), text_color=tema.COR_TEXTO_SUAVE,
                                 anchor="w").pack(fill="x", pady=(4, 0))

        self.mostrar_fim_do_resultado(area, cartao.rodape, resultado)

    def mostrar_inicio(self) -> None:
        self.resultado.mostrar_vazio("Nenhum resultado ainda", TEXTO_VAZIO)
