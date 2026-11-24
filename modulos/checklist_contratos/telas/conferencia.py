"""Aba "Conferência" do módulo Notas de Contrato (seção 7 da especificação).

Esquerda: mês de referência, pasta do movimento da Hospital Exemplo e do CMD (um .csv por dia, M3), Check list,
pasta de configuração e pasta de saída, e o botão "Conferir mês".
Direita: os quatro números, as contas divergentes, os destaques (R7, R8, avisos) e os botões "Abrir
relatório", "Abrir cópia do Check list" e "Abrir pasta".

Os caminhos lembrados são preenchidos sem tocar na rede; a confirmação de cada um (que lê o arquivo)
roda em segundo plano (o Check list fica numa pasta da rede). Sem regra de negócio: tudo vem de
processamento.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import customtkinter as ctk

from central import tema
from central.componentes import CampoRotulado, Coluna, GrupoNumeros, LinhaConferencia, TabelaSimples
from central.painel_base import PainelPadrao
from modulos.checklist_contratos import processamento

TIPOS_CHECKLIST = [("Planilha do Excel", "*.xlsx"), ("Todos os arquivos", "*.*")]


class PainelConferencia(PainelPadrao):
    TEXTO_BOTAO = "Conferir mês"

    def __init__(self, pai, info, ao_conferir: Callable[[processamento.ResultadoMes], None] | None = None):
        """ao_conferir(resultado): avisa o painel do módulo (a aba Pendências usa o relatório)."""
        self.ao_conferir = ao_conferir
        self._configuracao_automatica = None    # a pasta preenchida sozinha (ao lado do Check list)
        self.ultimo_resultado: processamento.ResultadoMes | None = None
        self.campo_mes: CampoRotulado | None = None
        super().__init__(pai, info, com_cabecalho=False)
        lembrado = processamento.ler_preferencias()
        self.campo_mes = CampoRotulado(self.cartao_entrada.corpo, "Mês de referência (MM/AAAA)", largura=150,
                                       texto_inicial=lembrado.get("mes", ""), ao_mudar=self._mes_mudou)
        self.campo_mes.pack(anchor="w", pady=(0, tema.ESPACO_PEQUENO), before=self.area_arquivos)
        self.cartao_sc = self.adicionar_arquivo(
            "Movimento da Hospital Exemplo: pasta com os .csv do Tasy (um por dia)", tipo="pasta",
            ao_mudar=lambda c: self._movimento_escolhido(self.cartao_sc, c, "SC"),
            titulo_dialogo="Escolha a pasta do movimento da Hospital Exemplo")
        self.cartao_cmd = self.adicionar_arquivo(
            "Movimento do CMD: pasta com os .csv do Tasy (um por dia)", tipo="pasta",
            ao_mudar=lambda c: self._movimento_escolhido(self.cartao_cmd, c, "CMD"),
            titulo_dialogo="Escolha a pasta do movimento do CMD")
        self.cartao_checklist = self.adicionar_arquivo(
            "Check list (o da rede, já atualizado)", ao_mudar=self._checklist_escolhido,
            tipos_arquivo=TIPOS_CHECKLIST, titulo_dialogo="Escolha o Check list")
        self.cartao_configuracao = self.adicionar_arquivo(
            "Pasta das regras (onde está o regras.csv; a pasta \"config\" ao lado do Check list entra sozinha)",
            tipo="pasta", ao_mudar=self._configuracao_escolhida,
            titulo_dialogo="Escolha a pasta onde está o regras.csv")
        self.adicionar_pasta_saida()
        self._usar_lembrados(lembrado)
        self.atualizar_botoes()

    # --- caminhos lembrados (sem tocar na rede ao abrir) ---

    def _usar_lembrados(self, lembrado: dict[str, str]) -> None:
        for cartao, chave, conferir in ((self.cartao_sc, "movimento_sc", lambda c: self._movimento_escolhido(
                                             self.cartao_sc, c, "SC")),
                                        (self.cartao_cmd, "movimento_cmd", lambda c: self._movimento_escolhido(
                                             self.cartao_cmd, c, "CMD")),
                                        (self.cartao_checklist, "checklist", self._checklist_escolhido),
                                        (self.cartao_configuracao, "configuracao", self._configuracao_escolhida)):
            if lembrado.get(chave):
                cartao.definir_caminhos([lembrado[chave]], avisar=False)
                conferir(cartao.caminhos)
        if lembrado.get("saida"):
            self.cartao_saida.definir_caminhos([lembrado["saida"]], avisar=False)
            self.cartao_saida.definir_confirmacao("Os arquivos gerados serão gravados aqui", None)

    # --- escolhas ---

    @property
    def mes(self) -> tuple[int, int] | None:
        return processamento.interpretar_mes(self.campo_mes.valor()) if self.campo_mes else None

    def _mes_mudou(self, _texto: str) -> None:
        if self.mes and self.cartao_checklist.caminho:
            self._checklist_escolhido(self.cartao_checklist.caminhos)
        self.atualizar_botoes()

    def _confirmar(self, cartao, caminhos, leitura, texto_lendo: str) -> None:
        """Lê o que foi escolhido em segundo plano e mostra o resultado no cartão."""
        if not caminhos:
            return
        caminho = caminhos[0]
        cartao.definir_carregando(texto_lendo)

        def lido(confirmacao):
            if cartao.caminho != caminho:            # o usuário já trocou
                return
            texto, status = confirmacao or ("Não foi possível ler", "erro")
            cartao.definir_confirmacao(texto, status)

        self.ler_em_segundo_plano(lambda: leitura(caminho), lido)

    def _movimento_escolhido(self, cartao, caminhos, estabelecimento: str) -> None:
        self._confirmar(cartao, caminhos, lambda c: processamento.confirmar_movimento(c, estabelecimento),
                        "Lendo o movimento...")

    def _checklist_escolhido(self, caminhos) -> None:
        mes = self.mes
        self._confirmar(self.cartao_checklist, caminhos,
                        lambda c: processamento.confirmar_checklist(c, *(mes or (None, None))),
                        "Lendo o Check list...")
        self._sugerir_configuracao(caminhos)

    def _sugerir_configuracao(self, caminhos) -> None:
        """A pasta "config" ao lado do Check list vira a pasta de configuração, a não ser que o usuário já
        tenha escolhido outra (a procura toca na rede: segundo plano)."""
        atual = self.cartao_configuracao.caminho
        if not caminhos or (atual is not None and atual != self._configuracao_automatica):
            return
        checklist = caminhos[0]

        def achou(pasta):
            atual = self.cartao_configuracao.caminho
            if pasta is None or self.cartao_checklist.caminho != checklist or \
                    (atual is not None and atual != self._configuracao_automatica):
                return
            self._configuracao_automatica = pasta
            self.cartao_configuracao.definir_caminhos([pasta], avisar=False)
            self._configuracao_escolhida([pasta])
            self.atualizar_botoes()

        self.ler_em_segundo_plano(lambda: processamento.pasta_configuracao_sugerida(checklist), achou)

    def _configuracao_escolhida(self, caminhos) -> None:
        self._confirmar(self.cartao_configuracao, caminhos, processamento.confirmar_configuracao,
                        "Lendo a configuração...")

    def pronto_para_processar(self) -> bool:
        return self.mes is not None and all(c.preenchido for c in self.cartoes)

    def ao_novo(self) -> None:
        self.ultimo_resultado = None

    # --- processar ---

    def processar(self) -> None:
        if self.ocupado or not self.pronto_para_processar():
            return
        ano, mes = self.mes
        sc, cmd = self.cartao_sc.caminho, self.cartao_cmd.caminho
        checklist, configuracao, saida = (self.cartao_checklist.caminho, self.cartao_configuracao.caminho,
                                          self.pasta_saida)
        existentes = processamento.arquivos_que_seriam_substituidos(saida, ano, mes)
        substituir = bool(existentes) and self.perguntar(
            f"A cópia preenchida do mês já existe na pasta de saída:\n\n  • {existentes[0].name}\n\n"
            "Deseja substituí-la? (Não = gravar uma nova, com _2 no nome)")

        def tarefa(progresso):
            return processamento.conferir(sc, cmd, checklist, configuracao, saida, ano, mes, progresso,
                                          substituir=substituir)

        self.executar(tarefa, self._mostrar_resultado, "Lendo o movimento da Hospital Exemplo...")

    # --- resultado ---

    def mostrar_inicio(self) -> None:
        self.resultado.mostrar_vazio("Nenhuma conferência ainda",
                                     "Informe o mês, escolha os movimentos, o Check list, a configuração e a "
                                     "pasta de saída e clique em \"Conferir mês\".", icone="prancheta")

    def _mostrar_resultado(self, resultado: processamento.ResultadoMes) -> None:
        self.ultimo_resultado = resultado
        if resultado.erro:
            self.mostrar_erro(resultado.erro)
            return
        processamento.salvar_preferencias(
            movimento_sc=self.cartao_sc.caminho, movimento_cmd=self.cartao_cmd.caminho,
            checklist=self.cartao_checklist.caminho, configuracao=self.cartao_configuracao.caminho,
            saida=self.pasta_saida, mes=processamento.texto_do_mes(resultado.ano, resultado.mes),
            relatorio=resultado.caminho_relatorio)
        resumo = processamento.resumir_conferencia(resultado)

        area = self.resultado.mostrar_conteudo()
        self.resultado.definir_selo(*resumo.selo)
        GrupoNumeros(area, resumo.numeros).pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))
        if resumo.divergencias:
            ctk.CTkLabel(area, text="Conta divergente: corrigir no Tasy", font=tema.fonte_texto_forte(),
                         text_color=tema.COR_TEXTO, anchor="w").pack(fill="x", pady=(0, 4))
            TabelaSimples(area, [Coluna("Fornecedor", peso=3), Coluna("Esperada x lançada", peso=2),
                                 Coluna("Valor", numero=True), Coluna("Lote/lanç.", peso=2)],
                          resumo.divergencias).pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))
        for texto, status in resumo.linhas:
            LinhaConferencia(area, texto, status).pack(fill="x", pady=3)
        self.botoes_resultado = self.definir_botoes_resultado([
            ("Abrir relatório", lambda: self.abrir(resultado.caminho_relatorio), "arquivo"),
            ("Abrir cópia", lambda: self.abrir(resultado.caminho_copia), "arquivos"),
            ("Abrir pasta", lambda: self.abrir(self._pasta_do(resultado)), "pasta"),
        ])
        if self.ao_conferir:
            self.ao_conferir(resultado)

    @staticmethod
    def _pasta_do(resultado: processamento.ResultadoMes) -> Path | None:
        caminho = resultado.caminho_relatorio or resultado.caminho_copia
        return caminho.parent if caminho else None
