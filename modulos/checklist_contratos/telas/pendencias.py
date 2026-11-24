"""Aba "Pendências" do módulo Notas de Contrato (seção 7 da especificação).

Esquerda: mês de referência, Check list da rede (já revisado), relatório da conferência do mês
(opcional, P2) e pasta de saída, e o botão "Gerar pendências".
Direita: notas pendentes, e-mails e quem ficou sem e-mail; a tabela responsável x notas; os botões
"Abrir prévia", "Abrir texto para o Claude Desktop" (E8) e "Abrir pasta".

Sem regra de negócio: tudo vem de processamento.py.
"""

from __future__ import annotations

import customtkinter as ctk

from central import tema
from central.componentes import CampoRotulado, Coluna, GrupoNumeros, LinhaConferencia, TabelaSimples
from central.painel_base import PainelPadrao
from modulos.checklist_contratos import processamento

TIPOS_CHECKLIST = [("Planilha do Excel", "*.xlsx"), ("Todos os arquivos", "*.*")]
TIPOS_RELATORIO = [("Relatório da conferência", "Conferencia_Contratos_*.xlsx"), ("Planilha do Excel", "*.xlsx"),
                   ("Todos os arquivos", "*.*")]


class PainelPendencias(PainelPadrao):
    TEXTO_BOTAO = "Gerar pendências"

    def __init__(self, pai, info):
        self.ultimo_resultado: processamento.ResultadoPendencias | None = None
        self.campo_mes: CampoRotulado | None = None
        super().__init__(pai, info, com_cabecalho=False)
        lembrado = processamento.ler_preferencias()
        self.campo_mes = CampoRotulado(self.cartao_entrada.corpo, "Mês de referência (MM/AAAA)", largura=150,
                                       texto_inicial=lembrado.get("mes", ""), ao_mudar=self._mes_mudou)
        self.campo_mes.pack(anchor="w", pady=(0, tema.ESPACO_PEQUENO), before=self.area_arquivos)
        self.cartao_checklist = self.adicionar_arquivo(
            "Check list da rede (já revisado)", ao_mudar=self._checklist_escolhido,
            tipos_arquivo=TIPOS_CHECKLIST, titulo_dialogo="Escolha o Check list")
        self.cartao_relatorio = self.adicionar_arquivo(
            "Relatório da conferência do mês (opcional: tira as contas divergentes)",
            ao_mudar=self._relatorio_escolhido, tipos_arquivo=TIPOS_RELATORIO,
            titulo_dialogo="Escolha o relatório da conferência do mês")
        self.adicionar_pasta_saida()
        if lembrado.get("checklist"):
            self.cartao_checklist.definir_caminhos([lembrado["checklist"]], avisar=False)
            self._checklist_escolhido(self.cartao_checklist.caminhos)
        if lembrado.get("relatorio"):
            self.usar_relatorio(lembrado["relatorio"])
        if lembrado.get("saida"):
            self.cartao_saida.definir_caminhos([lembrado["saida"]], avisar=False)
            self.cartao_saida.definir_confirmacao("Os arquivos gerados serão gravados aqui", None)
        self.atualizar_botoes()

    @property
    def mes(self) -> tuple[int, int] | None:
        return processamento.interpretar_mes(self.campo_mes.valor()) if self.campo_mes else None

    def usar_relatorio(self, caminho, mes: tuple[int, int] | None = None) -> None:
        """Relatório da última conferência (lembrado ou acabado de gerar na aba Conferência)."""
        if mes and not self.mes:
            self.campo_mes.definir(processamento.texto_do_mes(*mes))
        self.cartao_relatorio.definir_caminhos([caminho], avisar=False)
        self._relatorio_escolhido(self.cartao_relatorio.caminhos)
        self.atualizar_botoes()

    # --- escolhas ---

    def _mes_mudou(self, _texto: str) -> None:
        if self.mes:
            if self.cartao_checklist.caminho:
                self._checklist_escolhido(self.cartao_checklist.caminhos)
            if self.cartao_relatorio.caminho:
                self._relatorio_escolhido(self.cartao_relatorio.caminhos)
        self.atualizar_botoes()

    def _confirmar(self, cartao, caminhos, leitura, texto_lendo: str) -> None:
        if not caminhos:
            return
        caminho = caminhos[0]
        cartao.definir_carregando(texto_lendo)

        def lido(confirmacao):
            if cartao.caminho != caminho:
                return
            texto, status = confirmacao or ("Não foi possível ler", "erro")
            cartao.definir_confirmacao(texto, status)
            self.atualizar_botoes()

        self.ler_em_segundo_plano(lambda: leitura(caminho), lido)

    def _checklist_escolhido(self, caminhos) -> None:
        mes = self.mes
        self._confirmar(self.cartao_checklist, caminhos,
                        lambda c: processamento.confirmar_checklist(c, *(mes or (None, None))),
                        "Lendo o Check list...")

    def _relatorio_escolhido(self, caminhos) -> None:
        mes = self.mes
        self._confirmar(self.cartao_relatorio, caminhos,
                        lambda c: processamento.confirmar_relatorio(c, *(mes or (None, None))),
                        "Conferindo o relatório...")

    def pronto_para_processar(self) -> bool:
        """O relatório é opcional; um relatório de outro mês impede (P2)."""
        if self.mes is None or not (self.cartao_checklist.preenchido and self.cartao_saida
                                    and self.cartao_saida.preenchido):
            return False
        return not (self.cartao_relatorio.preenchido and self.cartao_relatorio.status_confirmacao == "erro")

    def ao_novo(self) -> None:
        self.ultimo_resultado = None

    # --- processar ---

    def processar(self) -> None:
        if self.ocupado or not self.pronto_para_processar():
            return
        ano, mes = self.mes
        checklist, relatorio, saida = self.cartao_checklist.caminho, self.cartao_relatorio.caminho, self.pasta_saida

        def tarefa(progresso):
            return processamento.gerar_pendencias(checklist, saida, ano, mes, relatorio, progresso)

        self.executar(tarefa, self._mostrar_resultado, "Lendo o Check list...")

    # --- resultado ---

    def mostrar_inicio(self) -> None:
        self.resultado.mostrar_vazio("Nenhuma pendência gerada ainda",
                                     "Informe o mês, escolha o Check list da rede e a pasta de saída e clique "
                                     "em \"Gerar pendências\".", icone="prancheta")

    def _mostrar_resultado(self, resultado: processamento.ResultadoPendencias) -> None:
        self.ultimo_resultado = resultado
        if resultado.erro:
            self.mostrar_erro(resultado.erro)
            return
        processamento.salvar_preferencias(checklist=self.cartao_checklist.caminho, saida=self.pasta_saida,
                                          mes=processamento.texto_do_mes(resultado.ano, resultado.mes))
        resumo = processamento.resumir_pendencias(resultado)

        area = self.resultado.mostrar_conteudo()
        self.resultado.definir_selo(*resumo.selo)
        GrupoNumeros(area, resumo.numeros).pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))
        if resumo.responsaveis:
            ctk.CTkLabel(area, text="E-mails por responsável", font=tema.fonte_texto_forte(),
                         text_color=tema.COR_TEXTO, anchor="w").pack(fill="x", pady=(0, 4))
            TabelaSimples(area, [Coluna("Responsável", peso=3), Coluna("Notas de", peso=2),
                                 Coluna("Notas", numero=True), Coluna("Destinatários", numero=True)],
                          resumo.responsaveis).pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))
        for texto, status in resumo.linhas:
            LinhaConferencia(area, texto, status).pack(fill="x", pady=3)
        pasta = resultado.caminho_previa.parent if resultado.caminho_previa else self.pasta_saida
        self.botoes_resultado = self.definir_botoes_resultado([
            ("Abrir prévia", lambda: self.abrir(resultado.caminho_previa), "olho"),
            ("Texto Claude", lambda: self.abrir(resultado.caminho_texto), "arquivo"),
            ("Abrir pasta", lambda: self.abrir(pasta), "pasta"),
        ])
