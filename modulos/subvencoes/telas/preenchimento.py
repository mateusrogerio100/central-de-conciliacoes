"""Aba "Preenchimento" do módulo Subvenções e Projetos (substitui subvencoes/interface.py do original).

Sem regra de negócio: escolhe arquivos, mês e pasta, faz as perguntas das regras R10 (meses
diferentes) e R11 (substituir arquivos) e mostra o resultado. Tudo o que decide valores está em
processamento.py; o que a tela exibe vem de resumo_tela.py.
"""

from __future__ import annotations

from central import tema
from central.componentes import CampoRotulado, Coluna, GrupoNumeros, LinhaConferencia, TabelaSimples
from central.painel_base import PainelPadrao
from modulos.subvencoes import processamento
from modulos.subvencoes.resumo_tela import resumir

TIPOS_EXCEL = [("Planilhas do Excel", "*.xlsx *.xlsm"), ("Todos os arquivos", "*.*")]
# balancete e patrimônio: o .xls como sai do Tasy (texto) ou o .xlsx salvo no Excel
TIPOS_TASY = [("Relatórios do Tasy", "*.xls *.xlsx"), ("Todos os arquivos", "*.*")]


class PainelSubvencoes(PainelPadrao):
    TEXTO_BOTAO = "Preencher"

    def __init__(self, pai, info):
        self._mes_balancete = None       # (caminho, mês lido ou None)
        self._mes_patrimonio = None
        self.ultimo_resultado = None
        super().__init__(pai, info, com_cabecalho=False)

        # dentro da aba o cabeçalho é o do módulo: o mês fica no topo do cartão de entrada
        self.campo_mes = CampoRotulado(self.cartao_entrada.corpo, "Mês de referência", largura=150)
        self.campo_mes.pack(anchor="w", pady=(0, tema.ESPACO_PEQUENO), before=self.area_arquivos)

        self.cartao_balancete = self.adicionar_arquivo("Balancete", ao_mudar=self._balancete_escolhido,
                                                       tipos_arquivo=TIPOS_TASY, titulo_dialogo="Escolha o Balancete")
        self.cartao_patrimonio = self.adicionar_arquivo("Relatório de patrimônio", ao_mudar=self._patrimonio_escolhido,
                                                        tipos_arquivo=TIPOS_TASY,
                                                        titulo_dialogo="Escolha o relatório de Patrimônio")
        self.cartao_planilhas = self.adicionar_arquivo("Planilhas a preencher", tipo="arquivos",
                                                       ao_mudar=self._planilhas_escolhidas, tipos_arquivo=TIPOS_EXCEL,
                                                       titulo_dialogo="Escolha as planilhas a preencher")
        self.adicionar_pasta_saida()
        self.atualizar_botoes()

    # --- escolhas ---

    def _balancete_escolhido(self, caminhos):
        if not caminhos:
            return
        caminho = caminhos[0]
        self._mes_balancete = None
        self.cartao_balancete.definir_confirmacao("Lendo o mês do balancete...", None)
        self.sugerir_pasta_saida(caminho.parent)

        def lido(mes):
            if self.cartao_balancete.caminho != caminho:     # o usuário já trocou o arquivo
                return
            self._mes_balancete = (caminho, mes)
            if mes is None:
                self.cartao_balancete.definir_confirmacao("Mês não identificado: confira o arquivo", "atencao")
                return
            self.campo_mes.definir(str(mes))                  # R10: o mês lido vai para o campo (editável)
            self.cartao_balancete.definir_confirmacao(f"Mês de referência {mes}", "ok")
            self._conferir_mes_patrimonio()

        self.ler_em_segundo_plano(lambda: processamento.mes_do_balancete(caminho), lido)

    def _patrimonio_escolhido(self, caminhos):
        if not caminhos:
            return
        caminho = caminhos[0]
        self._mes_patrimonio = None
        self.cartao_patrimonio.definir_confirmacao("Lendo o mês do patrimônio...", None)

        def lido(mes):
            if self.cartao_patrimonio.caminho != caminho:
                return
            self._mes_patrimonio = (caminho, mes)
            self._conferir_mes_patrimonio()

        self.ler_em_segundo_plano(lambda: processamento.mes_do_patrimonio(caminho), lido)

    def _conferir_mes_patrimonio(self):
        if self._mes_patrimonio is None:
            return
        mes_p = self._mes_patrimonio[1]
        mes_b = self._mes_balancete[1] if self._mes_balancete else None
        if mes_p is None:
            self.cartao_patrimonio.definir_confirmacao("Mês não identificado: confira o arquivo", "atencao")
        elif mes_b is not None and mes_b != mes_p:
            self.cartao_patrimonio.definir_confirmacao(f"Mês {mes_p}: diferente do balancete ({mes_b})", "atencao")
        else:
            self.cartao_patrimonio.definir_confirmacao(f"Mês de referência {mes_p}", "ok")

    def _planilhas_escolhidas(self, caminhos):
        if caminhos:
            quantidade = len(caminhos)
            self.cartao_planilhas.definir_confirmacao(f"{quantidade} planilha{'s' if quantidade > 1 else ''}", "ok")

    def ao_novo(self):
        self._mes_balancete = None
        self._mes_patrimonio = None
        self.ultimo_resultado = None
        self.campo_mes.definir("")

    # --- processar ---

    def validar(self):
        """Confere se tudo foi escolhido. Devolve (mensagem de erro ou None, mês)."""
        faltando = []
        if not self.cartao_balancete.preenchido:
            faltando.append("o Balancete")
        if not self.cartao_patrimonio.preenchido:
            faltando.append("o relatório de Patrimônio")
        if not self.cartao_planilhas.preenchido:
            faltando.append("pelo menos uma planilha a preencher")
        if not self.cartao_saida.preenchido:
            faltando.append("a pasta de saída")
        if faltando:
            return "Falta escolher: " + ", ".join(faltando) + ".", None
        mes = processamento.interpretar_mes(self.campo_mes.valor())
        if mes is None:
            return "Informe o mês de referência no formato MM/AAAA (ex.: 08/2026).", None
        return None, mes

    def processar(self):
        if self.ocupado:
            return
        erro, mes = self.validar()
        if erro:
            self.avisar(erro)
            return

        balancete, patrimonio = self.cartao_balancete.caminho, self.cartao_patrimonio.caminho
        planilhas, pasta_saida = self.cartao_planilhas.caminhos, self.pasta_saida
        mes_b = self._mes_ja_lido(self._mes_balancete, balancete)
        mes_p = self._mes_ja_lido(self._mes_patrimonio, patrimonio)

        def ler_meses(progresso):
            progresso("Conferindo os meses...", None)
            return (mes_b or processamento.mes_do_balancete(balancete),
                    mes_p or processamento.mes_do_patrimonio(patrimonio))

        def depois_dos_meses(meses):
            if not self._pode_seguir(meses, planilhas, pasta_saida, mes):
                self.mostrar_inicio()
                return
            self.executar(lambda progresso: processamento.processar(balancete, patrimonio, planilhas, pasta_saida,
                                                                    mes, progresso=progresso),
                          self._mostrar_resultado, "Lendo o balancete...")

        self.executar(ler_meses, depois_dos_meses, "Conferindo os meses...", registrar_uso=False)

    def _pode_seguir(self, meses, planilhas, pasta_saida, mes) -> bool:
        mes_b, mes_p = meses
        # R10: meses diferentes -> pergunta, não bloqueia
        if mes_b and mes_p and mes_b != mes_p:
            if not self.perguntar(f"O balancete é de {mes_b}, mas o relatório de patrimônio é de {mes_p}.\n\n"
                                  "Deseja continuar mesmo assim?"):
                return False
        # R11: arquivos que já existem -> pergunta antes de substituir
        return self.confirmar_substituicao(processamento.arquivos_de_saida(planilhas, pasta_saida, mes))

    @staticmethod
    def _mes_ja_lido(lido, caminho):
        return lido[1] if lido is not None and lido[0] == caminho else None

    # --- resultado ---

    def _mostrar_resultado(self, resultado):
        self.ultimo_resultado = resultado
        resumo = resumir(resultado)
        area = self.resultado.mostrar_conteudo()
        self.resultado.definir_selo(*resumo.selo)

        GrupoNumeros(area, [
            (resumo.contas_preenchidas, "contas preenchidas"),
            (resumo.contas_com_diferenca, "contas com diferença a analisar",
             "atencao" if resumo.contas_com_diferenca else "ok"),
            (resumo.avisos, resumo.legenda_avisos, "erro" if resumo.erros else "principal"),
        ]).pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))

        if resumo.abas:
            TabelaSimples(area, [Coluna("Aba", peso=2), Coluna("Contas", numero=True),
                                 Coluna("Com diferença", numero=True)],
                          [(a.aba, a.contas, a.com_diferenca) for a in resumo.abas]
                          ).pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))
        for conferencia in resumo.conferencias:
            LinhaConferencia(area, conferencia.texto, conferencia.status, conferencia.valor).pack(fill="x", pady=3)

        self.botoes_resultado = self.definir_botoes_resultado([
            ("Abrir pasta", lambda: self.abrir(resultado.pasta_saida), "pasta"),
            ("Ver avisos", lambda: self.abrir(resultado.caminho_relatorio), "olho"),
            ("Novo", self.novo, "atualizar"),
        ])
        self.botoes_resultado["Ver avisos"].habilitar(bool(resultado.caminho_relatorio))
