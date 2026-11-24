"""Aba "Preenchimento" do módulo Planilha HM (seção 7 da especificação).

Esquerda: o Eventos do mês (.XLS do Tasy), o Movimento do lote de Repasse a terceiros (.csv), a Planilha HM do
mês anterior (.xlsx) e a pasta de saída (sugerida: a pasta da planilha; fica lembrada); o botão "Preencher
planilha", que só acende com o Eventos e o Movimento do mesmo mês.
Direita: TOTAL GERAL × Movimento em destaque, as linhas criadas na aba do ano e os botões "Abrir planilha",
"Abrir conferência" e "Abrir pasta".

Ao clicar: lê tudo (1ª passada); pergunta antes de substituir a aba Senior do mês ou a cópia; abre a janela da
seção de cada evento novo que a tabela conta → seção não resolve (R5, item 4); grava (2ª passada). A planilha
pode estar na rede: tudo é lido em segundo plano. Sem regra de negócio: tudo vem de processamento.py.
"""

from __future__ import annotations

from datetime import datetime

import customtkinter as ctk

from central import tema
from central.componentes import Coluna, GrupoNumeros, LinhaConferencia, TabelaSimples
from central.painel_base import PainelPadrao
from modulos.planilha_hm import processamento
from modulos.planilha_hm.telas.pergunta_secao import perguntar_secao

TIPOS_EVENTOS = [("Eventos do Tasy", "*.xls *.XLS"), ("Todos os arquivos", "*.*")]
TIPOS_MOVIMENTO = [("Movimento do Tasy", "*.csv"), ("Todos os arquivos", "*.*")]
TIPOS_PLANILHA = [("Planilha do Excel", "*.xlsx"), ("Todos os arquivos", "*.*")]


class PainelPlanilhaHM(PainelPadrao):
    TEXTO_BOTAO = "Preencher planilha"

    def __init__(self, pai, info):
        self.ultimo_resultado: processamento.ResultadoPlanilhaHM | None = None
        self.competencia_eventos: processamento.Competencia | None = None
        self.competencia_movimento: processamento.Competencia | None = None
        self._confirmacao_movimento: processamento.Confirmacao | None = None
        self._leituras_planilha = 0
        super().__init__(pai, info, com_cabecalho=False)
        self.lembrado = processamento.ler_preferencias()

        self.cartao_eventos = self.adicionar_arquivo(
            "Eventos do mês (Tasy: .XLS)", ao_mudar=self._eventos_escolhido, tipos_arquivo=TIPOS_EVENTOS,
            titulo_dialogo="Escolha o relatório Eventos do mês")
        self.cartao_movimento = self.adicionar_arquivo(
            "Movimento do lote de Repasse a terceiros (Tasy: .csv)", ao_mudar=self._movimento_escolhido,
            tipos_arquivo=TIPOS_MOVIMENTO, titulo_dialogo="Escolha o Movimento do lote de Repasse a terceiros")
        self.cartao_planilha = self.adicionar_arquivo(
            "Planilha HM do mês anterior (.xlsx)", ao_mudar=self._planilha_escolhida, tipos_arquivo=TIPOS_PLANILHA,
            titulo_dialogo="Escolha a Planilha HM do mês anterior")
        self.adicionar_pasta_saida()

        if self.lembrado.get("saida"):
            self.cartao_saida.definir_caminhos([self.lembrado["saida"]], avisar=False)
            self.cartao_saida.definir_confirmacao("Os arquivos gerados serão gravados aqui", None)
        self.atualizar_botoes()

    # --- cartões ---

    def _eventos_escolhido(self, caminhos) -> None:
        self.competencia_eventos = None
        if not caminhos:                                          # "Limpar"
            self._conferir_meses()
            return
        caminho = caminhos[0]
        self.cartao_eventos.definir_carregando("Lendo o Eventos...")

        def lido(retorno):
            if self.cartao_eventos.caminho != caminho:            # o usuário já trocou o arquivo
                return
            (texto, status), competencia = retorno or (("Não foi possível ler", "erro"), None)
            self.cartao_eventos.definir_confirmacao(texto, status)
            self.competencia_eventos = competencia
            self._conferir_meses()
            if self.cartao_planilha.caminho:                      # o ano e a aba Senior dependem do Eventos
                self._confirmar_planilha()
            self.atualizar_botoes()

        self.ler_em_segundo_plano(lambda: processamento.confirmar_eventos(caminho), lido)

    def _movimento_escolhido(self, caminhos) -> None:
        self.competencia_movimento = self._confirmacao_movimento = None
        if not caminhos:
            return
        caminho = caminhos[0]
        self.cartao_movimento.definir_carregando("Lendo o Movimento...")

        def lido(retorno):
            if self.cartao_movimento.caminho != caminho:
                return
            self._confirmacao_movimento, self.competencia_movimento = \
                retorno or (("Não foi possível ler", "erro"), None)
            self._conferir_meses()
            self.atualizar_botoes()

        self.ler_em_segundo_plano(lambda: processamento.confirmar_movimento(caminho), lido)

    def _conferir_meses(self) -> None:
        """Movimento de outro mês: o cartão dele fica vermelho e o botão não acende (seção 3)."""
        if self._confirmacao_movimento is None:
            return
        texto, status = self._confirmacao_movimento
        diferente = processamento.texto_meses_diferentes(self.competencia_eventos, self.competencia_movimento)
        if diferente:
            texto, status = f"{texto}; {diferente}", "erro"
        self.cartao_movimento.definir_confirmacao(texto, status)

    def _confirmar_planilha(self) -> None:
        """A planilha é lida de novo quando o Eventos chega (o ano e a aba Senior dependem do mês). Só vale a leitura
        mais recente: a que começou sem o mês e terminou depois não apaga a confirmação certa."""
        caminho, competencia = self.cartao_planilha.caminho, self.competencia_eventos
        self._leituras_planilha += 1
        leitura = self._leituras_planilha
        self.cartao_planilha.definir_carregando("Lendo a planilha...")

        def lido(confirmacao):
            if leitura != self._leituras_planilha or self.cartao_planilha.caminho != caminho:
                return
            texto, status = confirmacao or ("Não foi possível ler", "erro")
            self.cartao_planilha.definir_confirmacao(texto, status)
            self.atualizar_botoes()

        self.ler_em_segundo_plano(lambda: processamento.confirmar_planilha(caminho, competencia), lido)

    def _planilha_escolhida(self, caminhos) -> None:
        if not caminhos:
            return
        self._confirmar_planilha()
        if not self.lembrado.get("saida"):
            self.sugerir_pasta_saida(caminhos[0].parent)          # seção 3: padrão = a pasta da planilha

    def pronto_para_processar(self) -> bool:
        if not hasattr(self, "cartao_planilha"):
            return False
        cartoes = (self.cartao_eventos, self.cartao_movimento, self.cartao_planilha)
        if not all(c.preenchido and c.status_confirmacao is not None for c in cartoes):
            return False
        if self.competencia_eventos is None or self.competencia_movimento is None:
            return False
        if processamento.texto_meses_diferentes(self.competencia_eventos, self.competencia_movimento):
            return False
        return self.cartao_saida.preenchido and all(c.status_confirmacao != "erro" for c in cartoes)

    def ao_novo(self) -> None:
        self.ultimo_resultado = None
        self.competencia_eventos = self.competencia_movimento = self._confirmacao_movimento = None

    # --- processar ---

    def escolher_secao(self, textos, numero: int, total: int) -> str | None:
        """A janela da pergunta da R5 (item 4). None = cancelou."""
        return perguntar_secao(self, textos, numero, total)

    def processar(self) -> None:
        if self.ocupado or not self.pronto_para_processar():
            return
        eventos, movimento, planilha = self.cartao_eventos.caminho, self.cartao_movimento.caminho, \
            self.cartao_planilha.caminho
        self.executar(lambda progresso: processamento.analisar(eventos, movimento, planilha, progresso=progresso),
                      self._analisado, "Lendo os arquivos...", registrar_uso=False)

    def _cancelado(self, motivo: str) -> None:
        self.resultado.mostrar_vazio("Nada foi gravado", motivo, icone="alerta", tom="atencao")

    def _analisado(self, analise: processamento.Analise) -> None:
        if analise.erro:
            self.mostrar_erro(analise.erro)
            return
        substituir_senior = bool(analise.linhas_senior_preenchidas)
        if substituir_senior and not self.perguntar(processamento.texto_pergunta_senior(analise)):
            self._cancelado("A aba Senior do mês já estava preenchida e você escolheu não substituir.")
            return
        agora = datetime.now()
        copia = self.pasta_saida / processamento.nome_da_copia(analise, agora)
        if not self.confirmar_substituicao([copia]):
            self._cancelado(f"A cópia {copia.name} não foi gravada.")
            return
        substituir_copia = copia.exists()

        respostas = {}
        perguntas = analise.plano.perguntas
        for numero, pergunta in enumerate(perguntas, start=1):
            resposta = self.escolher_secao(processamento.textos_da_pergunta(analise, pergunta), numero,
                                           len(perguntas))
            if resposta is None:
                self._cancelado("A seção de um evento novo ficou sem resposta. Escolha a seção para preencher.")
                return
            respostas[pergunta.chave] = resposta

        saida = self.pasta_saida
        self.executar(lambda progresso: processamento.processar(analise, saida, respostas, substituir_senior,
                                                                substituir_copia, progresso, agora),
                      self._mostrar_resultado, "Gravando a cópia da Planilha HM...")

    # --- resultado ---

    def mostrar_inicio(self) -> None:
        self.resultado.mostrar_vazio("Nenhuma planilha preenchida ainda",
                                     "Escolha o Eventos, o Movimento e a Planilha HM do mês anterior e clique em "
                                     "\"Preencher planilha\".", icone="estetoscopio")

    def _mostrar_resultado(self, resultado: processamento.ResultadoPlanilhaHM) -> None:
        self.ultimo_resultado = resultado
        if resultado.erro:
            self.mostrar_erro(resultado.erro)
            return
        processamento.salvar_preferencias(saida=self.pasta_saida)
        self.lembrado = processamento.ler_preferencias()
        resumo = processamento.resumir(resultado)

        area = self.resultado.mostrar_conteudo()
        self.resultado.definir_selo(*resumo.selo)
        GrupoNumeros(area, resumo.numeros).pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))
        for texto, status, valor in resumo.linhas:
            LinhaConferencia(area, texto, status, valor).pack(fill="x", pady=3)
        if resumo.criadas:
            ctk.CTkLabel(area, text="Linhas criadas na aba do ano", font=tema.fonte_texto_forte(),
                         text_color=tema.COR_TEXTO, anchor="w").pack(fill="x", pady=(tema.ESPACO_ENTRE_BLOCOS, 4))
            TabelaSimples(area, [Coluna("Linha", numero=True), Coluna("O quê", peso=2), Coluna("Evento", numero=True),
                                 Coluna("Evento / centro de custo", peso=3), Coluna("Seção", peso=3)],
                          resumo.criadas).pack(fill="x")
        pasta = resultado.caminho_planilha.parent if resultado.caminho_planilha else self.pasta_saida
        self.botoes_resultado = self.definir_botoes_resultado([
            ("Abrir planilha", lambda: self.abrir(resultado.caminho_planilha), "arquivo"),
            ("Abrir conferência", lambda: self.abrir(resultado.caminho_relatorio), "olho"),
            ("Abrir pasta", lambda: self.abrir(pasta), "pasta"),
        ])
        self.botoes_resultado["Abrir planilha"].habilitar(bool(resultado.caminho_planilha))
        self.botoes_resultado["Abrir conferência"].habilitar(bool(resultado.caminho_relatorio))
