"""Aba "Histórico" do módulo Histórico de uso.

Esquerda: a pasta do log de uso (a da rede, já preenchida) e a pasta de saída, e o botão "Gerar planilha".
Direita: usuários, usos dos módulos e aberturas da Central; a tabela por usuário; os botões "Abrir planilha" e
"Abrir pasta". A pasta do log fica na rede: a tela só a mostra ao abrir e confere em segundo plano.
"""

from __future__ import annotations

import customtkinter as ctk

from central import tema
from central.componentes import Coluna, GrupoNumeros, LinhaConferencia, TabelaSimples
from central.painel_base import PainelPadrao
from modulos.historico_uso import processamento


class PainelHistorico(PainelPadrao):
    TEXTO_BOTAO = "Gerar planilha"

    def __init__(self, pai, info):
        self.ultimo_resultado: processamento.ResultadoHistorico | None = None
        super().__init__(pai, info, com_cabecalho=False)
        lembrado = processamento.ler_preferencias()
        self.cartao_log = self.adicionar_arquivo(
            "Pasta do log de uso (na rede; cada computador grava o seu arquivo)", tipo="pasta",
            ao_mudar=self._log_escolhido, titulo_dialogo="Escolha a pasta do log de uso")
        self.adicionar_pasta_saida()
        self.cartao_log.definir_caminhos([lembrado.get("pasta_log") or processamento.pasta_log_padrao()],
                                         avisar=False)
        self._log_escolhido(self.cartao_log.caminhos)
        if lembrado.get("saida"):
            self.cartao_saida.definir_caminhos([lembrado["saida"]], avisar=False)
            self.cartao_saida.definir_confirmacao("A planilha será gravada aqui", None)
        self.atualizar_botoes()

    def _log_escolhido(self, caminhos) -> None:
        if not caminhos:
            return
        caminho = caminhos[0]
        self.cartao_log.definir_carregando("Procurando os arquivos do log...")

        def lido(confirmacao):
            if self.cartao_log.caminho != caminho:
                return
            texto, status = confirmacao or ("Não foi possível ler a pasta", "erro")
            self.cartao_log.definir_confirmacao(texto, status)

        self.ler_em_segundo_plano(lambda: processamento.confirmar_pasta_log(caminho), lido)

    def ao_novo(self) -> None:
        self.ultimo_resultado = None

    def processar(self) -> None:
        if self.ocupado or not self.pronto_para_processar():
            return
        pasta_log, saida = self.cartao_log.caminho, self.pasta_saida
        self.executar(lambda progresso: processamento.gerar_planilha(pasta_log, saida, progresso),
                      self._mostrar_resultado, "Lendo os arquivos do log de uso...")

    def mostrar_inicio(self) -> None:
        self.resultado.mostrar_vazio("Nenhuma planilha gerada ainda",
                                     "Escolha a pasta de saída e clique em \"Gerar planilha\": ela junta o uso "
                                     "de todos os computadores.", icone="relogio")

    def _mostrar_resultado(self, resultado: processamento.ResultadoHistorico) -> None:
        self.ultimo_resultado = resultado
        if resultado.erro:
            self.mostrar_erro(resultado.erro)
            return
        processamento.salvar_preferencias(pasta_log=self.cartao_log.caminho, saida=self.pasta_saida)
        area = self.resultado.mostrar_conteudo()
        self.resultado.definir_selo(*(("Conferir", "atencao") if resultado.avisos else ("Concluído", "ok")))
        GrupoNumeros(area, [(resultado.usuarios, "Usuários", "principal"),
                            (resultado.processamentos, "Usos dos módulos", "ok"),
                            (resultado.aberturas, "Aberturas da Central", "principal")]
                     ).pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))
        linhas = processamento.resumo_por_usuario(resultado)
        if linhas:
            ctk.CTkLabel(area, text="Por usuário (os mais recentes)", font=tema.fonte_texto_forte(),
                         text_color=tema.COR_TEXTO, anchor="w").pack(fill="x", pady=(0, 4))
            TabelaSimples(area, [Coluna("Usuário", peso=3), Coluna("Usos", numero=True),
                                 Coluna("Aberturas", numero=True), Coluna("Último uso", peso=2)],
                          linhas).pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))
        for aviso in resultado.avisos:
            LinhaConferencia(area, aviso, "atencao").pack(fill="x", pady=3)
        caminho = resultado.caminho_planilha
        self.botoes_resultado = self.definir_botoes_resultado([
            ("Abrir planilha", lambda: self.abrir(caminho), "arquivo"),
            ("Abrir pasta", lambda: self.abrir(caminho.parent if caminho else None), "pasta"),
        ])
