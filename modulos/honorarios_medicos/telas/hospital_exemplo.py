"""Aba "Hospital Exemplo (PF e PJ)" de Honorários Médicos (era interface/painel_honorarios_hospital_exemplo.py do
Conciliações AMES, item "Honorários Hospital Exemplo" do menu).

Mesmos cartões, conferência, textos e resultado da tela antiga, no layout padrão da Central:
- um cartão só para os relatórios do mês, com o botão "Adicionar arquivos" (pedido do usuário: o mais
  simples possível): dá para escolher todos de uma vez ou ir adicionando (os da pasta PF, depois os da PJ).
  O programa reconhece cada relatório pelo conteúdo; a conferência, que diz o que foi reconhecido e o que
  falta, roda em segundo plano (abrir os PDFs leva alguns segundos). Mais a pasta onde salvar (opcional,
  lembrada entre aberturas);
- resultado: números, totais por lado (contábil, Senior, PDFs de repasse, diferença), PDFs sem conta, o que
  não bateu, avisos e os botões da planilha.

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
    SITUACAO_DIVERGENTE_HOSPITAL_EXEMPLO,
    SITUACAO_OK_HOSPITAL_EXEMPLO,
    SITUACAO_SO_BALANCETE_HOSPITAL_EXEMPLO,
    SITUACAO_SO_SENIOR,
    PreviaHospitalExemplo,
    ResultadoHospitalExemplo,
)
from modulos.honorarios_medicos.telas.comum import MAXIMO_ITENS_NA_TELA, PainelHonorariosBase, encurtar

TIPOS_RELATORIOS = [("Relatórios do Tasy e PDFs (.xls, .xlsx, .pdf)", "*.xls *.xlsx *.pdf"),
                    ("Todos os arquivos", "*.*")]
TEXTO_VAZIO = ("Clique em Adicionar arquivos e escolha os relatórios do mês: balancete, HM PF e PJ Senior e os "
               "PDFs de Remoção, 6095 e 6203. Pode escolher todos de uma vez ou ir adicionando. Depois clique em "
               "Gerar relatório.")
TEXTO_CONFERINDO = "Conferindo os arquivos..."
# curtas: a coluna Situação é estreita ("PF · Sem par")
SITUACOES_CURTAS = {SITUACAO_DIVERGENTE_HOSPITAL_EXEMPLO: "Divergente", SITUACAO_SO_BALANCETE_HOSPITAL_EXEMPLO: "Sem par",
                    SITUACAO_SO_SENIOR: "Só Senior"}


class PainelHonorariosHospitalExemplo(PainelHonorariosBase):
    ABA = processamento.ABA_HOSPITAL_EXEMPLO

    def __init__(self, pai, info):
        self.previa: PreviaHospitalExemplo | None = None
        self._rodada_previa = 0          # conta as conferências (vale a da escolha mais nova)
        super().__init__(pai, info)

    def criar_cartoes(self) -> tuple:
        self.cartao_arquivos = self.adicionar_arquivo(
            "Relatórios do mês (todos de uma vez ou um por um)", tipo="arquivos", acumular=True,
            tipos_arquivo=TIPOS_RELATORIOS, ao_mudar=self._ao_mudar_relatorios,
            titulo_dialogo="Selecione os relatórios do mês (balancete, HM Senior e PDFs)")
        return (self.cartao_arquivos,)

    # --- escolha dos arquivos ---

    @property
    def escolhidos(self) -> list[Path]:
        return self.cartao_arquivos.caminhos

    def _ao_mudar_relatorios(self, caminhos: list[Path]) -> None:
        """Confere todos os escolhidos em segundo plano (vale a conferência da escolha mais nova)."""
        self._rodada_previa += 1
        rodada = self._rodada_previa
        self.previa = None
        escolhidos = self.escolhidos
        if not escolhidos:
            self.atualizar_botoes()
            return
        self.cartao_arquivos.definir_confirmacao(TEXTO_CONFERINDO, None)
        self.atualizar_botoes()
        self.ler_em_segundo_plano(lambda: processamento.previa_arquivos(escolhidos),
                                  lambda previa: self._concluir_previa(previa, rodada))

    def _concluir_previa(self, previa: PreviaHospitalExemplo | None, rodada: int) -> None:
        if rodada != self._rodada_previa or not self.winfo_exists():
            return                       # o usuário mudou a escolha no meio: vale a mais nova
        if previa is None:               # ler_em_segundo_plano devolve None quando a leitura falha
            previa = PreviaHospitalExemplo(erro="Erro inesperado ao ler os arquivos.")
        self.previa = previa
        self._mostrar_previa(self.cartao_arquivos, previa)
        self.atualizar_botoes()

    @staticmethod
    def _mostrar_previa(cartao, previa: PreviaHospitalExemplo) -> None:
        if previa.erro:
            texto = f"{previa.descricao} · {previa.erro}" if previa.descricao else previa.erro
            cartao.definir_confirmacao(texto, "erro")
        elif previa.avisos:
            cartao.definir_confirmacao(f"{previa.descricao} · " + "; ".join(previa.avisos), "atencao")
        else:
            cartao.definir_confirmacao(previa.descricao, "ok")

    def pronto_para_processar(self) -> bool:
        if not self.cartoes_relatorios:
            return False
        return self.previa is not None and self.previa.erro is None and bool(self.escolhidos)

    # --- processamento ---

    def processar(self) -> None:
        if self.ocupado or not self.pronto_para_processar():
            return
        escolhidos, pasta = self.escolhidos, self.cartao_pasta.caminho
        self.executar(lambda progresso: processamento.processar_hospital_exemplo(escolhidos, pasta, progresso),
                      self.mostrar_resultado)

    def mostrar_resultado(self, resultado: ResultadoHospitalExemplo) -> None:
        self.resultado_conciliacao = resultado
        self.atualizar_botoes()
        cartao = self.resultado
        area = cartao.mostrar_conteudo()

        cartao.definir_selo("Concluído" if resultado.caminho_relatorio else "Relatório não gerado",
                            "ok" if resultado.caminho_relatorio else "erro")
        if resultado.erro:
            LinhaConferencia(area, resultado.erro, status="erro").pack(fill="x", pady=(0, tema.ESPACO_PEQUENO))

        if resultado.lados:
            contexto = " · ".join(t for t in (processamento.nome_curto_unidade(resultado.unidade),
                                              processamento.mes_curto(resultado.mes)) if t)
            TextoQuebravel(area, contexto, tema.fonte_texto_forte()).pack(fill="x", pady=(0, tema.ESPACO_PEQUENO))

            numeros = processamento.numeros_hospital_exemplo(resultado)
            GrupoNumeros(area, [
                (formatar_inteiro(numeros.ok), "Médicos OK", "ok"),
                (formatar_inteiro(numeros.nao_ok), "Com diferença ou sem par", "atencao" if numeros.nao_ok else "ok"),
                (formatar_inteiro(numeros.linhas), "Linhas na conciliação", "principal"),
            ]).pack(fill="x")

            colunas = [Coluna("Total", peso=4)] + [Coluna(f"{lado} (R$)", numero=True, peso=3)
                                                    for lado in resultado.lados]
            linhas_total = [
                ("Contábil (" + " / ".join(resultado.contas_total[l].codigo for l in resultado.lados) + ")",
                 *(formatar_reais(resultado.totais_balancete[l]) for l in resultado.lados)),
                ("Senior", *(formatar_reais(resultado.totais_senior.get(l, 0)) for l in resultado.lados)),
                ("PDFs de repasse", *(formatar_reais(resultado.remocao_do_lado(l)) for l in resultado.lados)),
                ("Diferença", *(formatar_reais(sum((x.diferenca for x in resultado.linhas[l]), 0))
                                for l in resultado.lados)),
            ]
            TabelaSimples(area, colunas, linhas_total).pack(fill="x", pady=(tema.ESPACO_ENTRE_BLOCOS, 0))
            if resultado.repasses_sem_conta:
                total = sum((r.bruto for r in resultado.repasses_sem_conta), 0)
                LinhaConferencia(area, f"{len(resultado.repasses_sem_conta)} linha(s) dos PDFs sem conta no "
                                       f"balancete (R$ {formatar_reais(total)}) — veja a aba da Remoção",
                                 "atencao").pack(fill="x", pady=(tema.ESPACO_PEQUENO, 0))

            fora = [l for lado in resultado.lados for l in resultado.linhas[lado] if l.situacao != SITUACAO_OK_HOSPITAL_EXEMPLO]
            if fora:
                itens = [(encurtar(l.conta.descricao if l.conta else l.nome_senior),
                          f"{l.lado} · {SITUACOES_CURTAS[l.situacao]}", formatar_reais(l.diferenca))
                         for l in fora[:MAXIMO_ITENS_NA_TELA]]
                TabelaSimples(area, [Coluna("Médico/clínica", peso=5), Coluna("Situação", peso=3),
                                     Coluna("Diferença", numero=True, peso=3)],
                              itens).pack(fill="x", pady=(tema.ESPACO_ENTRE_BLOCOS, 0))
                if len(fora) > MAXIMO_ITENS_NA_TELA:
                    ctk.CTkLabel(area, text=f"e mais {len(fora) - MAXIMO_ITENS_NA_TELA} na planilha",
                                 font=tema.fonte_legenda(), text_color=tema.COR_TEXTO_SUAVE,
                                 anchor="w").pack(fill="x", pady=(4, 0))

        self.mostrar_fim_do_resultado(area, cartao.rodape, resultado)

    def ao_novo(self) -> None:
        super().ao_novo()
        self._rodada_previa += 1         # descarta uma conferência que ainda esteja rodando
        self.previa = None

    def mostrar_inicio(self) -> None:
        self.resultado.mostrar_vazio("Nenhum resultado ainda", TEXTO_VAZIO)
