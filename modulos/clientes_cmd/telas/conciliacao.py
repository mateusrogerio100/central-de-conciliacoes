"""Aba "Conciliação de clientes" do módulo Clientes CMD (substitui a aba "Conciliação de Clientes"
de src/interface.py do programa original).

Sem regra de negócio: escolhe os dois relatórios e a pasta de saída, pergunta antes de substituir
a planilha e mostra o resumo. A conciliação e o resumo estão em processamento.py.
"""

from __future__ import annotations

from central import tema
from central.componentes import Coluna, GrupoNumeros, LinhaConferencia, TabelaSimples
from central.painel_base import PainelPadrao, formatar_inteiro
from modulos.clientes_cmd import processamento


# o .xls como sai do Tasy (texto) ou o .xlsx salvo no Excel
TIPOS_TASY = [("Relatórios do Tasy", "*.xls *.xlsx"), ("Todos os arquivos", "*.*")]


class PainelConciliacaoClientes(PainelPadrao):
    TEXTO_BOTAO = "Gerar conciliação"

    def __init__(self, pai, info):
        self.ultimo_resultado = None
        super().__init__(pai, info, com_cabecalho=False)
        self.cartao_balancete = self.adicionar_arquivo("Balancete de clientes (.xls do Tasy ou .xlsx)",
                                                       ao_mudar=self._balancete_escolhido, tipos_arquivo=TIPOS_TASY,
                                                       titulo_dialogo="Selecione o Balancete")
        self.cartao_financeiro = self.adicionar_arquivo("Títulos a Receber (.xls do Tasy ou .xlsx)",
                                                        tipos_arquivo=TIPOS_TASY,
                                                        titulo_dialogo="Selecione o relatório de Títulos a Receber")
        self.adicionar_pasta_saida()
        self.atualizar_botoes()

    def _balancete_escolhido(self, caminhos):
        if caminhos:
            self.sugerir_pasta_saida(caminhos[0].parent)

    def ao_novo(self):
        self.ultimo_resultado = None

    def processar(self):
        if self.ocupado or not self.pronto_para_processar():
            return
        balancete, financeiro = self.cartao_balancete.caminho, self.cartao_financeiro.caminho
        destino = self.pasta_saida / processamento.NOME_PADRAO_SAIDA
        if not self.confirmar_substituicao([destino]):
            return
        self.executar(lambda progresso: processamento.processar(balancete, financeiro, destino, progresso=progresso),
                      self._mostrar_resultado, "Lendo o balancete...")

    def _mostrar_resultado(self, resultado):
        self.ultimo_resultado = resultado
        resumo = resultado.resumo
        sem_par = resumo.sem_contabil + resumo.sem_financeiro
        area = self.resultado.mostrar_conteudo()
        self.resultado.definir_selo("Concluído", "ok")

        GrupoNumeros(area, [
            (resumo.ok, "clientes OK", "ok"),
            (resumo.divergente, "clientes DIVERGENTES", "erro" if resumo.divergente else "ok"),
            (sem_par, f"sem par ({resumo.sem_contabil} sem contábil · {resumo.sem_financeiro} sem financeiro)",
             "atencao" if sem_par else "ok"),
        ]).pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))
        TabelaSimples(area, [Coluna("Status", peso=3), Coluna("Clientes", numero=True)], [
            ("OK", resumo.ok),
            ("DIVERGENTE", resumo.divergente),
            ("SEM CONTÁBIL", resumo.sem_contabil),
            ("SEM FINANCEIRO", resumo.sem_financeiro),
            ("Total", formatar_inteiro(resumo.total)),
        ]).pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))

        if resumo.divergente or sem_par:
            LinhaConferencia(area, "O casamento pelo nome é automático e não é 100% garantido: revise na planilha "
                             "os clientes com status diferente de OK.", "atencao").pack(fill="x", pady=3)
        else:
            LinhaConferencia(area, "Todos os clientes casados e com valores iguais", "ok").pack(fill="x", pady=3)

        self.botoes_resultado = self.definir_botoes_resultado([
            ("Abrir planilha", lambda: self.abrir(resultado.caminho), "arquivo"),
            ("Abrir pasta", lambda: self.abrir(resultado.caminho.parent), "pasta"),
            ("Novo", self.novo, "atualizar"),
        ])
