"""Aba "Gabarito de contas" do módulo Conferência de NF (S14).

Esquerda: pasta do gabarito (em geral na rede, a mesma para todos) e os arquivos de Movimento
contábil já revisados (vários de uma vez: um por dia, do jeito que saem do Tasy), e o botão
"Ensinar". Direita: o que foi aprendido e os botões "Abrir gabarito", "Abrir pasta" e "Novo".

Sem regra de negócio: o que aprender e o que mostrar vem de processamento.py.
"""

from __future__ import annotations

from central import tema
from central.componentes import GrupoNumeros, LinhaConferencia
from central.painel_base import PainelPadrao
from modulos.conferencia_nf import processamento

TIPOS_MOVIMENTO = [("Movimento contábil (.csv)", "*.csv"), ("Todos os arquivos", "*.*")]


class PainelGabarito(PainelPadrao):
    TEXTO_BOTAO = "Ensinar"

    def __init__(self, pai, info):
        self.ultimo_resultado = None
        super().__init__(pai, info, com_cabecalho=False)
        self.cartao_gabarito = self.adicionar_arquivo(
            "Pasta do gabarito de contas (a mesma para todos, junto do programa)", tipo="pasta",
            ao_mudar=self._gabarito_escolhido,
            titulo_dialogo="Escolha a pasta do gabarito de contas")
        self.cartao_movimentos = self.adicionar_arquivo(
            "Movimento contábil já revisado (.csv; pode escolher vários dias de uma vez)",
            tipo="arquivos", ao_mudar=self._movimentos_escolhidos, tipos_arquivo=TIPOS_MOVIMENTO,
            titulo_dialogo="Escolha os arquivos de Movimento contábil já revisados")
        pastas = processamento.ler_pastas_usadas()
        self.cartao_movimentos.pasta_inicial = pastas.get("movimentos")
        if pastas.get("gabarito"):
            self.cartao_gabarito.definir_caminhos([pastas["gabarito"]], avisar=False)
            self._gabarito_escolhido([pastas["gabarito"]])
        self.atualizar_botoes()

    # --- escolhas ---

    def _confirmar(self, cartao, leitura, texto_lendo: str) -> None:
        caminhos = list(cartao.caminhos)
        if not caminhos:
            return
        cartao.definir_confirmacao(texto_lendo, None)

        def lido(confirmacao):
            if list(cartao.caminhos) != caminhos:        # o usuário já trocou a escolha
                return
            texto, status = confirmacao or ("Não foi possível ler", "erro")
            cartao.definir_confirmacao(texto, status)

        self.ler_em_segundo_plano(lambda: leitura(caminhos), lido)

    def _gabarito_escolhido(self, caminhos) -> None:
        self._confirmar(self.cartao_gabarito,
                        lambda c: processamento.confirmar_pasta_gabarito(c[0]),
                        "Lendo o gabarito...")

    def _movimentos_escolhidos(self, caminhos) -> None:
        self._confirmar(self.cartao_movimentos, processamento.confirmar_movimentos,
                        "Lendo os arquivos...")

    def ao_novo(self) -> None:
        self.ultimo_resultado = None
        pasta = processamento.ler_pastas_usadas().get("gabarito")
        if pasta:                                       # a pasta do gabarito continua escolhida
            self.cartao_gabarito.definir_caminhos([pasta], avisar=False)
            self._gabarito_escolhido([pasta])

    # --- ensinar ---

    def processar(self) -> None:
        if self.ocupado or not self.pronto_para_processar():
            return
        pasta, arquivos = self.cartao_gabarito.caminho, list(self.cartao_movimentos.caminhos)

        def tarefa(progresso):
            resultado = processamento.ensinar_gabarito(pasta, arquivos, progresso)
            if not resultado.erro:
                processamento.salvar_pastas_usadas(pasta_gabarito=pasta,
                                                   pasta_movimentos=arquivos[0].parent)
            return resultado

        self.executar(tarefa, self._mostrar_resultado, "Aprendendo...")

    # --- resultado ---

    def mostrar_inicio(self) -> None:
        self.resultado.mostrar_vazio(
            "Nada ensinado ainda",
            "Escolha a pasta do gabarito e os arquivos de Movimento contábil já revisados e "
            "clique em \"Ensinar\". Ensinar o mesmo mês de novo não conta em dobro.", icone="check")

    def _mostrar_resultado(self, resultado) -> None:
        self.ultimo_resultado = resultado
        if resultado.erro:
            self.mostrar_erro(resultado.erro)
            return
        area = self.resultado.mostrar_conteudo()
        self.resultado.definir_selo(*(("Concluído com alertas", "atencao") if resultado.falhas
                                      else ("Concluído", "ok")))
        GrupoNumeros(area, [
            (resultado.fatos_novos, "fatos aprendidos agora", "ok"),
            (resultado.fatos_ja_aprendidos, "já estavam no gabarito (ignorados)", "principal"),
            (resultado.lancamentos, "lançamentos de conta aprendidos", "principal"),
        ]).pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))
        LinhaConferencia(area, f"{resultado.arquivos_lidos} arquivo(s) lido(s)", "ok").pack(
            fill="x", pady=3)
        if resultado.fatos_sem_fornecedor:
            LinhaConferencia(area, "Fatos sem conta de fornecedor (recibos, doações): não entram",
                             "atencao", str(resultado.fatos_sem_fornecedor)).pack(fill="x", pady=3)
        for falha in resultado.falhas:
            LinhaConferencia(area, f"{falha.arquivo}: {falha.motivo}", "erro").pack(fill="x",
                                                                                     pady=3)
        self.definir_botoes_resultado([
            ("Abrir gabarito", lambda: self.abrir(resultado.caminho), "arquivo"),
            ("Abrir pasta", lambda: self.abrir(resultado.pasta), "pasta"),
            ("Novo", self.novo, "atualizar"),
        ])
        self._gabarito_escolhido([resultado.pasta])
