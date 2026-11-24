"""Aba "Import Contábil" do módulo Clientes CMD (substitui a aba "Import Contábil" de
src/interface.py do programa original).

Dois passos, como na janela original:
1. "Gerar Rel_Geral": junta os relatórios da pasta do mês;
2. "Gerar arquivo de import": a partir do Rel_Geral (o do passo 1 ou um montado à mão).
Sem regra de negócio: a consolidação, o .txt e os nomes dos arquivos estão em processamento.py.
"""

from __future__ import annotations

from pathlib import Path

from central import tema
from central.componentes import BotaoPrincipal, CampoRotulado, Coluna, GrupoNumeros, LinhaConferencia, TabelaSimples
from central.painel_base import PainelPadrao, formatar_inteiro
from modulos.clientes_cmd.import_contabil import processamento


class PainelImportContabil(PainelPadrao):
    TEXTO_BOTAO = "1. Gerar Rel_Geral"

    def __init__(self, pai, info):
        self.ultimo_resultado = None
        super().__init__(pai, info, com_cabecalho=False)
        # dentro da aba o cabeçalho é o do módulo: o mês fica no topo do cartão de entrada
        mes, ano = processamento.mes_anterior()
        self.campo_mes = CampoRotulado(self.cartao_entrada.corpo, "Mês de referência", largura=150,
                                       texto_inicial=processamento.formatar_mes(mes, ano),
                                       ao_mudar=lambda _texto: self.atualizar_botoes())
        self.campo_mes.pack(anchor="w", pady=(0, tema.ESPACO_PEQUENO), before=self.area_arquivos)

        self.cartao_relatorios = self.adicionar_arquivo("Pasta com os relatórios do mês", tipo="pasta",
                                                        ao_mudar=self._relatorios_escolhidos,
                                                        titulo_dialogo="Selecione a pasta com os relatórios de origem")
        self.cartao_rel_geral = self.adicionar_arquivo("Rel_Geral (gerado no passo 1 ou montado à mão)",
                                                       ao_mudar=self._rel_geral_escolhido,
                                                       titulo_dialogo="Selecione o Rel_Geral")
        self.adicionar_pasta_saida()

        self.botao_import = BotaoPrincipal(self.area_botoes, "2. Gerar arquivo de import", self.gerar_import,
                                           icone="importar")
        self.botao_import.pack(fill="x", pady=(tema.ESPACO_PEQUENO, 0))
        self.atualizar_botoes()

    # --- escolhas e botões ---

    def _relatorios_escolhidos(self, caminhos):
        if not caminhos:
            return
        pasta = caminhos[0]
        quantidade = processamento.contar_relatorios(pasta)
        if quantidade:
            self.cartao_relatorios.definir_confirmacao(f"{quantidade} relatório(s) encontrado(s)", "ok")
        else:
            self.cartao_relatorios.definir_confirmacao("Nenhum relatório .xlsx ou .xls nesta pasta", "atencao")
        # sugere a pasta ACIMA da dos relatórios: um Rel_Geral gravado junto deles seria juntado de novo
        self.sugerir_pasta_saida(pasta.parent)

    def _rel_geral_escolhido(self, caminhos):
        if caminhos:
            self.cartao_rel_geral.definir_confirmacao("Rel_Geral escolhido", None)

    def mes_ano(self) -> tuple[int, int] | None:
        return processamento.interpretar_mes(self.campo_mes.valor())

    def pronto_para_processar(self) -> bool:
        if not hasattr(self, "cartao_relatorios"):      # a base confere os botões antes de a tela estar pronta
            return False
        return (self.mes_ano() is not None and self.cartao_relatorios.preenchido
                and self.cartao_saida is not None and self.cartao_saida.preenchido)

    def pronto_para_import(self) -> bool:
        if not hasattr(self, "cartao_rel_geral"):
            return False
        return (self.mes_ano() is not None and self.cartao_rel_geral.preenchido
                and self.cartao_saida is not None and self.cartao_saida.preenchido)

    def atualizar_botoes(self) -> None:
        super().atualizar_botoes()
        if hasattr(self, "botao_import"):
            self.botao_import.habilitar(not self.ocupado and self.pronto_para_import())

    def ao_novo(self):
        self.ultimo_resultado = None

    # --- passo 1 ---

    def processar(self):
        if self.ocupado:
            return
        mes_ano = self.mes_ano()
        if mes_ano is None:
            self.avisar("Informe o mês de referência no formato MM/AAAA (ex.: 08/2026).")
            return
        pasta, saida = self.cartao_relatorios.caminho, self.pasta_saida
        if pasta is None or saida is None:
            self.avisar("Escolha a pasta com os relatórios do mês e a pasta de saída.")
            return
        if Path(saida).resolve() == Path(pasta).resolve():
            self.avisar("Escolha uma pasta de saída diferente da pasta dos relatórios: um Rel_Geral gravado lá "
                        "seria juntado aos relatórios da próxima vez.")
            return
        destino = saida / processamento.nome_rel_geral(*mes_ano)
        if not self.confirmar_substituicao([destino]):
            return
        self.executar(lambda progresso: processamento.gerar_rel_geral(pasta, destino, progresso=progresso),
                      self._rel_geral_gerado, "Lendo os relatórios do mês...")

    def _rel_geral_gerado(self, resultado):
        self.ultimo_resultado = resultado
        self.cartao_rel_geral.definir_caminhos([resultado.caminho], avisar=False)
        self.cartao_rel_geral.definir_confirmacao(f"Gerado agora: {formatar_inteiro(resultado.total)} lançamentos",
                                                  "ok")
        self.atualizar_botoes()

        area = self.resultado.mostrar_conteudo()
        self.resultado.definir_selo(f"Rel_Geral {self.campo_mes.valor()} gerado", "ok")
        GrupoNumeros(area, [
            (len(resultado.linhas_por_arquivo), "relatórios juntados"),
            (formatar_inteiro(resultado.total), "lançamentos no Rel_Geral"),
        ]).pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))
        TabelaSimples(area, [Coluna("Relatório", peso=4), Coluna("Linhas", numero=True)],
                      [(nome, formatar_inteiro(linhas)) for nome, linhas in resultado.linhas_por_arquivo.items()]
                      ).pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))
        LinhaConferencia(area, "Confira o Rel_Geral se precisar e clique em \"2. Gerar arquivo de import\".", "ok"
                         ).pack(fill="x", pady=3)
        self.botoes_resultado = self.definir_botoes_resultado([
            ("Abrir Rel_Geral", lambda: self.abrir(resultado.caminho), "arquivo"),
            ("Abrir pasta", lambda: self.abrir(resultado.caminho.parent), "pasta"),
            ("Novo", self.novo, "atualizar"),
        ])

    # --- passo 2 ---

    def gerar_import(self):
        if self.ocupado:
            return
        mes_ano = self.mes_ano()
        if mes_ano is None:
            self.avisar("Informe o mês de referência no formato MM/AAAA (ex.: 08/2026).")
            return
        rel_geral, saida = self.cartao_rel_geral.caminho, self.pasta_saida
        if rel_geral is None or saida is None:
            self.avisar("Escolha o Rel_Geral e a pasta de saída.")
            return
        destino = saida / processamento.nome_import(*mes_ano)
        if not self.confirmar_substituicao([destino]):
            return
        mes, ano = mes_ano
        self.executar(lambda progresso: processamento.gerar_arquivo_import(rel_geral, mes, ano, destino,
                                                                           progresso=progresso),
                      self._import_gerado, "Gerando o arquivo de import...")

    def _import_gerado(self, resultado):
        self.ultimo_resultado = resultado
        area = self.resultado.mostrar_conteudo()
        self.resultado.definir_selo(f"Import {processamento.formatar_mes(resultado.mes, resultado.ano)} gerado", "ok")
        GrupoNumeros(area, [
            (formatar_inteiro(resultado.total), "lançamentos"),
            (formatar_inteiro(2 * resultado.total), "linhas no arquivo (duas por lançamento)"),
        ]).pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))
        LinhaConferencia(area, f"Arquivo {resultado.caminho.name} gravado no formato do sistema contábil "
                         "(ISO-8859-1, quebras de linha CRLF)", "ok").pack(fill="x", pady=3)
        self.botoes_resultado = self.definir_botoes_resultado([
            ("Abrir pasta", lambda: self.abrir(resultado.caminho.parent), "pasta"),
            ("Abrir arquivo", lambda: self.abrir(resultado.caminho), "arquivo"),
            ("Novo", self.novo, "atualizar"),
        ])
