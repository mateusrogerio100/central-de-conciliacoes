"""Aba "Preenchimento" do módulo Convênios (seção 7 da especificação).

Esquerda: o Razão Convênios do mês, a planilha RECEITAS DE CONVÊNIOS (.xlsx), a pasta das equivalências
(preenchida sozinha com a pasta config ao lado da planilha, 3.3) e a pasta de saída; o botão "Preencher".
Direita: convênios preenchidos, linhas novas e lançamentos não identificados; a tabela linha x convênio x valor;
a conferência TOTAL RECEITAS x Saldo Contábil; os botões "Abrir planilha", "Abrir relatório" e "Abrir pasta".

Mês já preenchido (P1): pergunta antes de substituir. A planilha e a pasta config podem estar na rede: tudo é
lido em segundo plano. Sem regra de negócio: tudo vem de processamento.py.
"""

from __future__ import annotations

import customtkinter as ctk

from central import tema
from central.componentes import Coluna, GrupoNumeros, LinhaConferencia, TabelaSimples
from central.painel_base import PainelPadrao
from modulos.convenios import processamento

TIPOS_RAZAO = [("Razão do Tasy", "*.xlsx *.xls"), ("Todos os arquivos", "*.*")]
TIPOS_PLANILHA = [("Planilha do Excel", "*.xlsx"), ("Todos os arquivos", "*.*")]


class PainelConvenios(PainelPadrao):
    TEXTO_BOTAO = "Preencher"

    def __init__(self, pai, info):
        self.ultimo_resultado: processamento.ResultadoConvenios | None = None
        self.competencia: tuple[int, int] | None = None          # (ano, mês) do razão escolhido
        self._equivalencias_automatica = None
        super().__init__(pai, info, com_cabecalho=False)
        self.lembrado = processamento.ler_preferencias()

        self.cartao_razao = self.adicionar_arquivo(
            "Razão Convênios do mês (Tasy: .xlsx ou .xls)", ao_mudar=self._razao_escolhido,
            tipos_arquivo=TIPOS_RAZAO, titulo_dialogo="Escolha o Razão Convênios")
        self.cartao_planilha = self.adicionar_arquivo(
            "Planilha RECEITAS DE CONVÊNIOS (.xlsx)", ao_mudar=self._planilha_escolhida,
            tipos_arquivo=TIPOS_PLANILHA, titulo_dialogo="Escolha a planilha de receitas")
        self.cartao_equivalencias = self.adicionar_arquivo(
            "Pasta das equivalências (config, com o equivalencias.csv)", tipo="pasta",
            ao_mudar=self._equivalencias_escolhidas, titulo_dialogo="Escolha a pasta do equivalencias.csv")
        self.adicionar_pasta_saida()

        if self.lembrado.get("planilha"):
            self.cartao_planilha.definir_caminhos([self.lembrado["planilha"]], avisar=False)
            self._planilha_escolhida(self.cartao_planilha.caminhos)
        if self.lembrado.get("equivalencias") and not self.cartao_equivalencias.caminho:
            self.cartao_equivalencias.definir_caminhos([self.lembrado["equivalencias"]], avisar=False)
            self._equivalencias_escolhidas(self.cartao_equivalencias.caminhos)
        if self.lembrado.get("saida"):
            self.cartao_saida.definir_caminhos([self.lembrado["saida"]], avisar=False)
            self.cartao_saida.definir_confirmacao("Os arquivos gerados serão gravados aqui", None)
        self.atualizar_botoes()

    # --- cartões ---

    def _confirmar(self, cartao, caminho, leitura, texto_lendo: str, depois=None) -> None:
        cartao.definir_carregando(texto_lendo)

        def lido(confirmacao):
            if cartao.caminho != caminho:                      # o usuário já trocou o arquivo
                return
            texto, status = confirmacao or ("Não foi possível ler", "erro")
            cartao.definir_confirmacao(texto, status)
            if depois:
                depois()
            self.atualizar_botoes()

        self.ler_em_segundo_plano(lambda: leitura(caminho), lido)

    def _razao_escolhido(self, caminhos) -> None:
        if not caminhos:
            return
        caminho = caminhos[0]
        self.competencia = None
        self.cartao_razao.definir_carregando("Lendo o razão...")
        if not self.lembrado.get("saida"):
            self.sugerir_pasta_saida(caminho.parent)

        def lido(retorno):
            if self.cartao_razao.caminho != caminho:
                return
            (texto, status), competencia = retorno or (("Não foi possível ler", "erro"), None)
            self.cartao_razao.definir_confirmacao(texto, status)
            self.competencia = competencia
            if self.cartao_planilha.caminho:                   # a aba do ano e o mês dependem do razão
                self._confirmar_planilha()
            self.atualizar_botoes()

        self.ler_em_segundo_plano(lambda: processamento.confirmar_razao(caminho), lido)

    def _confirmar_planilha(self) -> None:
        competencia = self.competencia
        self._confirmar(self.cartao_planilha, self.cartao_planilha.caminho,
                        lambda c: processamento.confirmar_planilha(c, competencia), "Lendo a planilha...")

    def _planilha_escolhida(self, caminhos) -> None:
        if not caminhos:
            return
        planilha = caminhos[0]
        self._confirmar_planilha()
        if self.cartao_equivalencias.caminho not in (None, self._equivalencias_automatica):
            return                                       # pasta escolhida à mão nunca é trocada (3.3)

        def achou(pasta):
            if pasta and self.cartao_planilha.caminho == planilha \
                    and self.cartao_equivalencias.caminho in (None, self._equivalencias_automatica):
                self._equivalencias_automatica = pasta
                self.cartao_equivalencias.definir_caminhos([pasta], avisar=False)
                self._equivalencias_escolhidas([pasta])

        self.ler_em_segundo_plano(lambda: processamento.pasta_equivalencias_sugerida(planilha), achou)

    def _equivalencias_escolhidas(self, caminhos) -> None:
        if caminhos:
            self._confirmar(self.cartao_equivalencias, caminhos[0], processamento.confirmar_equivalencias,
                            "Lendo as equivalências...")

    def pronto_para_processar(self) -> bool:
        """A pasta das equivalências é opcional (sem ela vale o modelo vazio, com aviso); razão e planilha com
        erro impedem."""
        if not hasattr(self, "cartao_equivalencias") or self.competencia is None:
            return False
        if not (self.cartao_razao.preenchido and self.cartao_planilha.preenchido and self.cartao_saida.preenchido):
            return False
        return "erro" not in (self.cartao_razao.status_confirmacao, self.cartao_planilha.status_confirmacao)

    def ao_novo(self) -> None:
        self.ultimo_resultado = None
        self.competencia = None

    # --- processar ---

    def processar(self) -> None:
        if self.ocupado or not self.pronto_para_processar():
            return
        razao, planilha, saida = self.cartao_razao.caminho, self.cartao_planilha.caminho, self.pasta_saida
        equivalencias = self.cartao_equivalencias.caminho

        def preencher(substituir: bool) -> None:
            self.executar(lambda progresso: processamento.processar(razao, planilha, saida, equivalencias,
                                                                    substituir, progresso),
                          self._mostrar_resultado, "Lendo o razão...")

        def conferido(retorno) -> None:
            mes, preenchidos = retorno
            if not preenchidos:
                preencher(False)
            elif self.perguntar(processamento.texto_pergunta_substituir(mes, preenchidos)):
                preencher(True)
            else:
                self.mostrar_inicio()

        self.executar(lambda progresso: processamento.conferir_mes(razao, planilha), conferido,
                      "Conferindo o mês na planilha...", registrar_uso=False)

    # --- resultado ---

    def mostrar_inicio(self) -> None:
        self.resultado.mostrar_vazio("Nenhuma planilha preenchida ainda",
                                     "Escolha o razão do mês, a planilha de receitas e a pasta de saída e clique em "
                                     "\"Preencher\".", icone="grafico")

    def _mostrar_resultado(self, resultado: processamento.ResultadoConvenios) -> None:
        self.ultimo_resultado = resultado
        if resultado.erro:
            self.mostrar_erro(resultado.erro)
            return
        processamento.salvar_preferencias(planilha=self.cartao_planilha.caminho,
                                          equivalencias=self.cartao_equivalencias.caminho, saida=self.pasta_saida)
        self.lembrado = processamento.ler_preferencias()
        resumo = processamento.resumir(resultado)

        area = self.resultado.mostrar_conteudo()
        self.resultado.definir_selo(*resumo.selo)
        if resumo.numeros:
            GrupoNumeros(area, resumo.numeros).pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))
        for texto, status, valor in resumo.linhas:
            LinhaConferencia(area, texto, status, valor).pack(fill="x", pady=3)
        if resumo.convenios:
            ctk.CTkLabel(area, text="Valores do mês na cópia", font=tema.fonte_texto_forte(),
                         text_color=tema.COR_TEXTO, anchor="w").pack(fill="x", pady=(tema.ESPACO_ENTRE_BLOCOS, 4))
            TabelaSimples(area, [Coluna("Linha", numero=True), Coluna("Convênio", peso=3),
                                 Coluna("Valor do mês", numero=True, peso=2)],
                          resumo.convenios).pack(fill="x")
        pasta = resultado.caminho_planilha.parent if resultado.caminho_planilha else self.pasta_saida
        self.botoes_resultado = self.definir_botoes_resultado([
            ("Abrir planilha", lambda: self.abrir(resultado.caminho_planilha), "arquivo"),
            ("Abrir relatório", lambda: self.abrir(resultado.caminho_relatorio), "olho"),
            ("Abrir pasta", lambda: self.abrir(pasta), "pasta"),
        ])
        self.botoes_resultado["Abrir planilha"].habilitar(bool(resultado.caminho_planilha))
        self.botoes_resultado["Abrir relatório"].habilitar(bool(resultado.caminho_relatorio))
