"""Demonstração do visual da Central, com dados FICTÍCIOS (não lê nenhum arquivo).

Serve para aprovar o visual antes de os módulos reais entrarem no menu (Etapa 6) e para
conferir o visual depois de mudar o tema. Abrir, na raiz do projeto:
    python -m central.demonstracao

Cada item do menu mostra um estado diferente do layout padrão (GUIA_VISUAL, seção 5):
- Conciliação Bancária: antes de processar (estado vazio);
- Clientes CMD: botão que simula um processamento (barra de andamento e depois o resultado);
- Subvenções e Projetos: resultado concluído (números, tabela e conferências);
- Módulo com defeito: como aparece um módulo que não pôde ser carregado.
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

import customtkinter as ctk

from central import tema
from central.componentes import (
    BotaoPrincipal,
    BotaoSecundario,
    CabecalhoModulo,
    CampoRotulado,
    Cartao,
    CartaoArquivo,
    CartaoResultado,
    Coluna,
    GrupoNumeros,
    LayoutDuasColunas,
    LinhaConferencia,
    TabelaSimples,
)
from central.janela import JanelaCentral
from central.modulo_base import InfoModulo
from central.registro import ModuloCarregado
from central.segundo_plano import TarefaEmSegundoPlano

CONTEXTO = "Demonstração · dados fictícios"


class PainelDemonstracao(ctk.CTkFrame):
    def __init__(self, pai, titulo: str, descricao: str, estado: str, arquivos: list[tuple], mes: bool = True):
        super().__init__(pai, fg_color="transparent")
        cabecalho = CabecalhoModulo(self, CONTEXTO, titulo, descricao)
        cabecalho.pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))
        if mes:
            CampoRotulado(cabecalho.area_direita, "Mês de referência", texto_inicial="08/2026").pack()

        layout = LayoutDuasColunas(self)
        layout.pack(fill="both", expand=True)

        entrada = Cartao(layout.esquerda, "Arquivos de entrada")
        entrada.pack(fill="both", expand=True)
        self.cartoes = []
        for rotulo, tipo, nome, confirmacao, status in arquivos:
            cartao = CartaoArquivo(entrada.corpo, rotulo, tipo=tipo)
            cartao.pack(fill="x", pady=(0, tema.ESPACO_PEQUENO))
            if nome:
                cartao.definir_caminhos([Path(tempfile.gettempdir(), n) for n in nome], avisar=False)
                cartao.definir_confirmacao(confirmacao, status)
            self.cartoes.append(cartao)
        self.botao = BotaoPrincipal(entrada.corpo, "Processar", self._simular, icone="seta_direita")
        self.botao.pack(fill="x", pady=(tema.ESPACO_PEQUENO, 0))

        self.resultado = CartaoResultado(layout.direita)
        self.resultado.pack(fill="both", expand=True)

        if estado == "vazio":
            self.botao.habilitar(False)
            self.resultado.mostrar_vazio()
        elif estado == "andamento":
            self.botao.habilitar(False)
            barra = self.resultado.mostrar_andamento("Lendo os relatórios do mês...")
            barra.atualizar(fracao=None)
        elif estado == "concluido":
            self._mostrar_concluido()
        else:
            self.resultado.mostrar_vazio("Pronto para processar", "Clique em Processar para ver a barra de andamento.")

    def _simular(self) -> None:
        self.botao.habilitar(False)
        barra = self.resultado.mostrar_andamento()

        def tarefa(progresso):
            passos = ["Lendo o balancete...", "Lendo os Títulos a Receber...", "Casando os clientes...",
                      "Gravando a planilha..."]
            for numero, texto in enumerate(passos):
                progresso(texto, numero / len(passos))
                time.sleep(0.8)
            progresso("Concluído.", 1.0)

        def concluir(_):
            self.botao.habilitar(True)
            self._mostrar_concluido()

        TarefaEmSegundoPlano(self, tarefa, ao_progresso=barra.atualizar, ao_concluir=concluir).iniciar()

    def _mostrar_concluido(self) -> None:
        area = self.resultado.mostrar_conteudo()
        self.resultado.definir_selo("Concluído", "ok")
        GrupoNumeros(area, [(42, "contas preenchidas"), (3, "contas com diferença a analisar", "atencao"),
                            (5, "avisos · 1 erro", "erro")]).pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))
        TabelaSimples(area, [Coluna("Aba", peso=2), Coluna("Contas", numero=True), Coluna("Com diferença", numero=True)],
                      [("Federal", 12, 1), ("Estadual", 18, 2), ("Municipal", 7, 0), ("PROJETOS 1", 5, 0)]
                      ).pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))
        LinhaConferencia(area, "Soma dos bens = total do relatório", "ok", "1.234.567,89").pack(fill="x", pady=3)
        LinhaConferencia(area, "Saldo contábil de cada aba = balancete", "atencao", "1 aba").pack(fill="x", pady=3)
        LinhaConferencia(area, "Planilha de Projetos não gravada: aberta no Excel", "erro").pack(fill="x", pady=3)
        rodape = self.resultado.rodape
        for filho in rodape.winfo_children():
            filho.destroy()
        BotaoPrincipal(rodape, "Abrir pasta", icone="pasta").pack(side="left", fill="x", expand=True)
        BotaoSecundario(rodape, "Ver avisos", icone="olho").pack(side="left", padx=(tema.ESPACO_PEQUENO, 0))
        BotaoSecundario(rodape, "Novo", icone="atualizar", largura=110).pack(side="left",
                                                                             padx=(tema.ESPACO_PEQUENO, 0))


def _info(chave, nome, icone, descricao, estado, arquivos, mes=True) -> InfoModulo:
    return InfoModulo(chave=chave, nome=nome, descricao=descricao, contexto=CONTEXTO, icone=icone,
                      criar_painel=lambda pai: PainelDemonstracao(pai, nome, descricao, estado, arquivos, mes))


def modulos_de_demonstracao() -> list[ModuloCarregado]:
    infos = [
        _info("bancos", "Conciliação Bancária", "banco",
              "Compara o saldo de cada conta bancária do balancete com o extrato do banco.", "vazio",
              [("Balancete bancário", "arquivo", None, "", None), ("Pasta dos extratos (PDF)", "pasta", None, "", None)],
              mes=False),
        _info("clientes_cmd", "Clientes CMD", "pessoas",
              "Casa o balancete de clientes com os Títulos a Receber pelo nome do cliente.", "pronto",
              [("Balancete de clientes", "arquivo", ["Balancete_clientes.xlsx"], "Mês de referência 08/2026", "ok"),
               ("Títulos a Receber", "arquivo", ["Titulos_receber_ago.xlsx"], "Mês do relatório diferente: 07/2026",
                "atencao")], mes=False),
        _info("subvencoes", "Subvenções e Projetos", "moedas",
              "Preenche os saldos das planilhas de Subvenções e Projetos a partir do balancete e do patrimônio.",
              "concluido",
              [("Balancete", "arquivo", ["Balancete.xlsx"], "Mês de referência 08/2026", "ok"),
               ("Relatório de patrimônio", "arquivo", ["patrimonio.xlsx"], "Mês de referência 08/2026", "ok"),
               ("Planilhas a preencher", "arquivos", ["Subvenções 08-2026.xlsx", "Projetos 08-2026.xlsx"],
                "2 planilhas", "ok")]),
    ]
    modulos = [ModuloCarregado(nome_pasta=i.chave, info=i) for i in infos]
    modulos.append(ModuloCarregado(nome_pasta="modulo_com_defeito",
                                   erro="Não foi possível carregar o módulo 'modulo_com_defeito': "
                                        "No module named 'biblioteca_que_falta'",
                                   detalhe_tecnico="Traceback (exemplo fictício)\n"
                                                   "ModuleNotFoundError: No module named 'biblioteca_que_falta'"))
    return modulos


def main() -> None:
    os.environ["CENTRAL_LOG_USO_DESLIGADO"] = "1"     # a demonstração não entra no log de uso
    caminho = Path(tempfile.gettempdir()) / "central_demonstracao_preferencias.json"
    janela = JanelaCentral(modulos=modulos_de_demonstracao(), caminho_preferencias=caminho)
    janela.title("Central de Conciliações — demonstração")
    janela.mainloop()


if __name__ == "__main__":
    main()
