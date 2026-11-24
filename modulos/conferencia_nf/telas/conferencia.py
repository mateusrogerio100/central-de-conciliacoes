"""Aba "Conferir lote" do módulo Conferência de NF (seção 7 da especificação).

Esquerda: unidade conferida (S15), lote do Tasy (.csv), pasta dos PDFs, pasta do gabarito de contas (opcional, S14) e pasta
de saída, e o botão "Conferir lote".
Direita: os três números, a tabela "Conferir à mão, por motivo", as conferências e os botões
"Abrir relatório", "Abrir pasta" e "Novo".

Sem regra de negócio: o que conferir e o que mostrar vem de processamento.py.
"""

from __future__ import annotations

from pathlib import Path

import customtkinter as ctk

from central import tema
from central.componentes import CampoComLista, Coluna, GrupoNumeros, LinhaConferencia, TabelaSimples
from central.painel_base import PainelPadrao
from modulos.conferencia_nf import processamento

TIPOS_LOTE = [("Lote do Tasy (.csv)", "*.csv"), ("Todos os arquivos", "*.*")]


class PainelConferencia(PainelPadrao):
    TEXTO_BOTAO = "Conferir lote"

    def __init__(self, pai, info):
        self.ultimo_resultado: processamento.ResultadoConferencia | None = None
        self.campo_unidade: CampoComLista | None = None
        super().__init__(pai, info, com_cabecalho=False)
        # S15: o CNPJ do destinatário / tomador de cada nota tem que ser o desta unidade
        self.campo_unidade = CampoComLista(
            self.area_arquivos, "Unidade conferida (o CNPJ das notas tem que ser o dela)",
            processamento.opcoes_unidades(), largura=420,
            texto_inicial=processamento.opcao_do_cnpj(processamento.ler_unidade_usada()),
            ao_mudar=lambda _: self.atualizar_botoes())
        self.campo_unidade.lista.configure(state="readonly")   # só as unidades da lista
        self.campo_unidade.pack(fill="x", pady=(0, tema.ESPACO_PEQUENO))
        self.cartao_lote = self.adicionar_arquivo(
            "Lote do Tasy (.csv: Movimento contábil ou movimento do lote)", ao_mudar=self._lote_escolhido,
            tipos_arquivo=TIPOS_LOTE, titulo_dialogo="Escolha o lote exportado do Tasy (.csv)")
        self.cartao_pdfs = self.adicionar_arquivo(
            "Pasta das notas: PDFs e XMLs (DANFE e DANFSe, com as subpastas)", tipo="pasta",
            ao_mudar=self._pdfs_escolhidos, titulo_dialogo="Escolha a pasta com os PDFs e XMLs das notas")
        self.cartao_gabarito = self.adicionar_arquivo(
            "Pasta do gabarito de contas (opcional)", tipo="pasta",
            ao_mudar=self._gabarito_escolhido,
            titulo_dialogo="Escolha a pasta do gabarito de contas")
        self.adicionar_pasta_saida()
        self._lembrar_pastas(processamento.ler_pastas_usadas())
        self._usar_gabarito_lembrado()
        self.atualizar_botoes()

    @property
    def cnpj_unidade(self) -> str | None:
        if self.campo_unidade is None:
            return None
        return processamento.cnpj_da_opcao(self.campo_unidade.valor())

    def pronto_para_processar(self) -> bool:
        """A unidade é obrigatória; o gabarito de contas é opcional."""
        return self.cnpj_unidade is not None and             all(c.preenchido for c in self.cartoes if c is not self.cartao_gabarito)

    def _usar_gabarito_lembrado(self) -> None:
        pasta = processamento.ler_pastas_usadas().get("gabarito")
        if pasta and not self.cartao_gabarito.caminho:
            self.cartao_gabarito.definir_caminhos([pasta], avisar=False)
            self._gabarito_escolhido([pasta])

    def _lembrar_pastas(self, pastas: dict[str, Path]) -> None:
        """Os seletores abrem nas pastas da última conferência."""
        self.cartao_lote.pasta_inicial = pastas.get("lote")
        self.cartao_pdfs.pasta_inicial = pastas.get("pdfs")
        self.cartao_saida.pasta_inicial = pastas.get("saida")

    # --- escolhas ---

    def _confirmar(self, cartao, caminhos, leitura, texto_lendo: str) -> None:
        """Confere o arquivo escolhido em segundo plano e mostra o resultado no cartão."""
        if not caminhos:
            return
        caminho = caminhos[0]
        cartao.definir_confirmacao(texto_lendo, None)

        def lido(confirmacao):
            if cartao.caminho != caminho:            # o usuário já trocou o arquivo
                return
            texto, status = confirmacao or ("Não foi possível ler o arquivo", "erro")
            cartao.definir_confirmacao(texto, status)

        self.ler_em_segundo_plano(lambda: leitura(caminho), lido)

    def _lote_escolhido(self, caminhos) -> None:
        if caminhos:
            self.sugerir_pasta_saida(caminhos[0].parent)
        self._confirmar(self.cartao_lote, caminhos, processamento.confirmar_lote, "Lendo o lote...")

    def _pdfs_escolhidos(self, caminhos) -> None:
        self._confirmar(self.cartao_pdfs, caminhos, processamento.confirmar_pasta_pdfs,
                        "Contando os PDFs e XMLs...")

    def _gabarito_escolhido(self, caminhos) -> None:
        self._confirmar(self.cartao_gabarito, caminhos, processamento.confirmar_pasta_gabarito,
                        "Lendo o gabarito...")

    def ao_novo(self) -> None:
        self.ultimo_resultado = None
        self._usar_gabarito_lembrado()             # a pasta do gabarito continua escolhida

    # --- processar ---

    def processar(self) -> None:
        if self.ocupado or not self.pronto_para_processar():
            return
        lote, pdfs, saida = self.cartao_lote.caminho, self.cartao_pdfs.caminho, self.pasta_saida
        gabarito, unidade = self.cartao_gabarito.caminho, self.cnpj_unidade

        def tarefa(progresso):
            resultado = processamento.processar(lote, pdfs, saida, progresso, gabarito, unidade)
            if resultado.caminho_relatorio is not None:
                processamento.salvar_pastas_usadas(lote, pdfs, saida, gabarito,
                                                   cnpj_unidade=unidade)
            return resultado

        self.executar(tarefa, self._mostrar_resultado, "Lendo o lote do Tasy...")

    # --- resultado ---

    def mostrar_inicio(self) -> None:
        self.resultado.mostrar_vazio("Nenhuma conferência ainda",
                                     "Escolha a unidade, o lote do Tasy e a pasta dos PDFs e clique em "
                                     "\"Conferir lote\".", icone="check")

    def _mostrar_resultado(self, resultado: processamento.ResultadoConferencia) -> None:
        self.ultimo_resultado = resultado
        resumo = processamento.resumir(resultado)
        if resumo.erro:
            self.mostrar_erro(resumo.erro)
            return
        self._lembrar_pastas(processamento.ler_pastas_usadas())

        area = self.resultado.mostrar_conteudo()
        self.resultado.definir_selo(*resumo.selo)
        GrupoNumeros(area, resumo.numeros).pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))
        ctk.CTkLabel(area, text="Conferir à mão, por motivo", font=tema.fonte_texto_forte(),
                     text_color=tema.COR_TEXTO, anchor="w").pack(fill="x", pady=(0, 4))
        TabelaSimples(area, [Coluna("Motivo", peso=3), Coluna("Fatos", numero=True)],
                      resumo.motivos).pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))
        for linha in resumo.conferencias:
            LinhaConferencia(area, linha.texto, linha.status, linha.valor).pack(fill="x", pady=3)
        self.botoes_resultado = self.definir_botoes_resultado([
            ("Abrir relatório", lambda: self.abrir(resultado.caminho_relatorio), "arquivo"),
            ("Abrir pasta", lambda: self.abrir(resultado.pasta_saida), "pasta"),
            ("Novo", self.novo, "atualizar"),
        ])
