"""Aba "Conciliação" do módulo Estoque: escolhe os arquivos, o mês e a pasta, e roda uma etapa por botão.

Um botão por etapa (decisão do usuário, 06/10/2026): EST-01, EST-02 e EST-03, cada um gerando o seu
Excel e habilitado quando os arquivos que ele usa foram escolhidos.

Sem regra de negócio: faz as perguntas (meses diferentes, substituir arquivo) e mostra o
resultado. Tudo o que decide valores está em processamento.py; o que a tela exibe vem de
resumo_tela.py.
"""

from __future__ import annotations

from pathlib import Path

import customtkinter as ctk

from central import tema
from central.componentes import (
    BotaoPrincipal,
    BotaoSecundario,
    CampoRotulado,
    Coluna,
    GrupoNumeros,
    LinhaConferencia,
    TabelaSimples,
)
from central.painel_base import PainelPadrao
from modulos.conciliacao_estoque import processamento
from modulos.conciliacao_estoque.resumo_tela import resumir

TIPOS_TASY = [("Relatórios do Tasy", "*.xls *.xlsx"), ("Todos os arquivos", "*.*")]
TIPOS_PDF = [("PDF", "*.pdf"), ("Todos os arquivos", "*.*")]
NOMES_ARQUIVOS = {processamento.BALANCETE: "o Balancete", processamento.SCF: "o Mapa do Estoque",
                  processamento.PDF: "o PDF Movimento estoque"}


class PainelEstoque(PainelPadrao):
    def __init__(self, pai, info, pasta_configuracao: Path | None = None):
        """pasta_configuracao: só para os testes (no uso normal, a pasta do usuário no %APPDATA%)."""
        self.pasta_configuracao = pasta_configuracao
        self._meses: dict[str, tuple] = {}          # balancete/scf/pdf -> (caminho, mês lido ou None)
        self.botoes_etapa: dict[str, BotaoPrincipal] = {}
        self.ultimo_resultado = None
        super().__init__(pai, info, com_cabecalho=False)

        self.campo_mes = CampoRotulado(self.cartao_entrada.corpo, "Mês de referência", largura=150)
        self.campo_mes.pack(anchor="w", pady=(0, tema.ESPACO_PEQUENO), before=self.area_arquivos)

        self.cartoes_entrada = {
            processamento.BALANCETE: self.adicionar_arquivo(
                "Balancete (grupo 1.01.04 Estoques) — EST-01 e EST-03", ao_mudar=self._balancete_escolhido,
                tipos_arquivo=TIPOS_TASY, titulo_dialogo="Escolha o Balancete exportado do Tasy"),
            processamento.SCF: self.adicionar_arquivo(
                "Mapa do Estoque (Contabilidade) — as três etapas", ao_mudar=self._scf_escolhido,
                tipos_arquivo=TIPOS_TASY, titulo_dialogo="Escolha o Mapa do Estoque (SCF - Movimento Estoque do Tasy)"),
            processamento.PDF: self.adicionar_arquivo(
                "PDF Movimento estoque — EST-02", ao_mudar=self._pdf_escolhido, tipos_arquivo=TIPOS_PDF,
                titulo_dialogo="Escolha o PDF Movimento estoque"),
        }
        self.cartao_balancete = self.cartoes_entrada[processamento.BALANCETE]
        self.cartao_scf = self.cartoes_entrada[processamento.SCF]
        self.cartao_pdf = self.cartoes_entrada[processamento.PDF]
        self.adicionar_pasta_saida()

        # configuração da EST-02: qual vale e o botão para editar
        self.area_configuracao = ctk.CTkFrame(self.cartao_entrada.corpo, fg_color="transparent")
        self.area_configuracao.pack(fill="x", pady=(0, tema.ESPACO_PEQUENO), before=self.area_botoes)
        self.area_configuracao.grid_columnconfigure(0, weight=1)
        self.rotulo_configuracao = ctk.CTkLabel(self.area_configuracao, text="", font=tema.fonte_legenda(),
                                                text_color=tema.COR_TEXTO_SUAVE, anchor="w", justify="left",
                                                wraplength=260)
        self.rotulo_configuracao.grid(row=0, column=0, sticky="ew")
        self.botao_configuracao = BotaoSecundario(self.area_configuracao, "Editar configuração",
                                                  self.editar_configuracao, altura=tema.ALTURA_BOTAO_PEQUENO,
                                                  largura=170)
        self.botao_configuracao.grid(row=0, column=1, padx=(tema.ESPACO_PEQUENO, 0))
        self.status_configuracao: str | None = None

        # um botão por etapa, no lugar do botão único da base
        self.botao.pack_forget()
        for indice, etapa in enumerate(processamento.ETAPAS_DA_TELA):
            botao = BotaoPrincipal(self.area_botoes, etapa.texto_botao,
                                   lambda id_etapa=etapa.id: self.processar_etapa(id_etapa), icone=self.ICONE_BOTAO)
            botao.pack(fill="x", pady=(0 if indice == 0 else tema.ESPACO_PEQUENO // 2, 0))
            self.botoes_etapa[etapa.id] = botao

        self.atualizar_configuracao()
        self.atualizar_botoes()

    # --- botões ---

    def pronta(self, id_etapa: str) -> bool:
        """A etapa tem os arquivos que usa e a pasta de saída."""
        etapa = processamento.etapa_da_tela(id_etapa)
        return self.cartao_saida is not None and self.cartao_saida.preenchido and all(
            self.cartoes_entrada[chave].preenchido for chave in etapa.arquivos)

    def pronto_para_processar(self) -> bool:
        return any(self.pronta(e.id) for e in processamento.ETAPAS_DA_TELA)

    def atualizar_botoes(self) -> None:
        super().atualizar_botoes()
        if not hasattr(self, "cartoes_entrada"):        # ainda montando a tela
            return
        for id_etapa, botao in self.botoes_etapa.items():
            botao.habilitar(not self.ocupado and self.pronta(id_etapa))

    # --- configuração da EST-02 ---

    def atualizar_configuracao(self) -> None:
        def lida(situacao):
            texto, status = situacao or ("Configuração da EST-02 não pôde ser lida", "erro")
            self.status_configuracao = status
            self.rotulo_configuracao.configure(text=texto,
                                               text_color=tema.COR_ERRO if status == "erro" else tema.COR_TEXTO_SUAVE)

        self.ler_em_segundo_plano(lambda: processamento.situacao_configuracao(self.pasta_configuracao), lida)

    def editar_configuracao(self) -> None:
        try:
            caminho = processamento.preparar_configuracao(self.pasta_configuracao)
        except OSError as erro:
            self.avisar(f"Não foi possível preparar a configuração para edição: {erro}")
            return
        self.informar("A configuração da EST-02 vai abrir no Excel.\n\n"
                      "Depois de alterar, salve e feche o arquivo antes de gerar a EST-02.")
        self.abrir(caminho)
        self.atualizar_configuracao()

    # --- escolhas ---

    def _ler_mes(self, chave, caminhos, leitura):
        if not caminhos:
            return
        caminho, cartao = caminhos[0], self.cartoes_entrada[chave]
        self._meses.pop(chave, None)
        cartao.definir_confirmacao("Lendo o mês...", None)

        def lido(mes):
            if cartao.caminho != caminho:            # o usuário já trocou o arquivo
                return
            self._meses[chave] = (caminho, mes)
            # o mês do balancete vai para o campo (editável); sem balancete, vale o do SCF
            if mes is not None and (chave == processamento.BALANCETE or
                                    (chave == processamento.SCF and not self.campo_mes.valor())):
                self.campo_mes.definir(str(mes))
            self._conferir_meses()

        self.ler_em_segundo_plano(lambda: leitura(caminho), lido)

    def _balancete_escolhido(self, caminhos):
        if caminhos:
            self.sugerir_pasta_saida(caminhos[0].parent)
        self._ler_mes(processamento.BALANCETE, caminhos, processamento.mes_do_balancete)

    def _scf_escolhido(self, caminhos):
        if caminhos:
            self.sugerir_pasta_saida(caminhos[0].parent)
        self._ler_mes(processamento.SCF, caminhos, processamento.mes_do_scf)

    def _pdf_escolhido(self, caminhos):
        self._ler_mes(processamento.PDF, caminhos, processamento.mes_do_pdf)

    def _conferir_meses(self):
        """Linha de confirmação de cada cartão: mês lido e se bate com o do balancete (ou do SCF)."""
        referencia = (self._mes_ja_lido(processamento.BALANCETE, self.cartao_balancete.caminho)
                      or self._mes_ja_lido(processamento.SCF, self.cartao_scf.caminho))
        for chave, cartao in self.cartoes_entrada.items():
            if chave not in self._meses or cartao.caminho != self._meses[chave][0]:
                continue
            mes = self._meses[chave][1]
            if mes is None:
                cartao.definir_confirmacao("Mês não identificado: confira o arquivo", "atencao")
            elif referencia is not None and mes != referencia:
                cartao.definir_confirmacao(f"Mês {mes}: diferente dos outros arquivos ({referencia})", "atencao")
            else:
                cartao.definir_confirmacao(f"Mês de referência {mes}", "ok")

    def _mes_ja_lido(self, chave, caminho):
        lido = self._meses.get(chave)
        return lido[1] if lido is not None and lido[0] == caminho else None

    def ao_novo(self):
        self._meses = {}
        self.ultimo_resultado = None
        self.campo_mes.definir("")

    # --- processar ---

    def validar(self, id_etapa: str):
        """Confere se o que a etapa usa foi escolhido. Devolve (mensagem de erro ou None, mês)."""
        etapa = processamento.etapa_da_tela(id_etapa)
        faltando = [NOMES_ARQUIVOS[chave] for chave in etapa.arquivos if not self.cartoes_entrada[chave].preenchido]
        if not self.cartao_saida.preenchido:
            faltando.append("a pasta de saída")
        if faltando:
            return f"Para a {etapa.id}, falta escolher: " + ", ".join(faltando) + ".", None
        mes = processamento.interpretar_mes(self.campo_mes.valor())
        if mes is None:
            return "Informe o mês de referência no formato MM/AAAA (ex.: 09/2026).", None
        return None, mes

    def processar(self):
        """Botão único da base (escondido): não é usado; cada etapa tem o seu."""

    def processar_etapa(self, id_etapa: str):
        if self.ocupado:
            return
        erro, mes = self.validar(id_etapa)
        if erro:
            self.avisar(erro)
            return
        etapa = processamento.etapa_da_tela(id_etapa)
        caminhos = {chave: self.cartoes_entrada[chave].caminho for chave in etapa.arquivos}
        leituras = {processamento.BALANCETE: processamento.mes_do_balancete, processamento.SCF: processamento.mes_do_scf,
                    processamento.PDF: processamento.mes_do_pdf}
        ja_lidos = {chave: self._mes_ja_lido(chave, caminho) for chave, caminho in caminhos.items()}
        pasta_saida = self.pasta_saida

        def ler_meses(progresso):
            progresso("Conferindo os meses...", None)
            return {chave: ja_lidos[chave] or leituras[chave](caminho) for chave, caminho in caminhos.items()}

        def depois_dos_meses(meses):
            if not self._pode_seguir(id_etapa, meses, pasta_saida, mes):
                self.mostrar_inicio()
                return
            self.executar(lambda progresso: processamento.processar(
                id_etapa, pasta_saida, mes, progresso=progresso, pasta_configuracao=self.pasta_configuracao,
                **caminhos), self._mostrar_resultado, "Lendo os arquivos...", acao=etapa.texto_botao)

        self.executar(ler_meses, depois_dos_meses, "Conferindo os meses...", registrar_uso=False)

    def _pode_seguir(self, id_etapa, meses, pasta_saida, mes) -> bool:
        lidos = [(NOMES_ARQUIVOS[chave], m) for chave, m in meses.items() if m is not None]
        if any(m != mes for _, m in lidos):
            linhas = "\n".join(f"  • {nome}: {m}" for nome, m in lidos)
            if not self.perguntar(f"Os meses não batem (mês informado: {mes}):\n\n{linhas}\n\n"
                                  "Deseja continuar mesmo assim?"):
                return False
        return self.confirmar_substituicao([processamento.arquivo_de_saida(id_etapa, pasta_saida, mes)])

    # --- resultado ---

    def _mostrar_resultado(self, resultado):
        self.ultimo_resultado = resultado
        resumo = resumir(resultado)
        if resultado.caminho_excel is None:
            self.mostrar_erro(f"{resumo.titulo}: {resultado.falha}")
            area = self.resultado.area
        else:
            area = self.resultado.mostrar_conteudo()
            self.resultado.definir_selo(*resumo.selo)
            ctk.CTkLabel(area, text=resumo.titulo, font=tema.fonte_texto_forte(), text_color=tema.COR_TEXTO,
                         anchor="w").pack(fill="x", pady=(0, tema.ESPACO_PEQUENO))
            GrupoNumeros(area, [(n.valor, n.legenda, n.tom) for n in resumo.numeros]
                         ).pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))
            primeira, *demais = resumo.colunas
            TabelaSimples(area, [Coluna(primeira, peso=2)] + [Coluna(c, numero=True) for c in demais],
                          resumo.linhas).pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))
            for conferencia in resumo.conferencias:
                LinhaConferencia(area, conferencia.texto, conferencia.status, conferencia.valor).pack(fill="x", pady=3)
            self.botoes_resultado = self.definir_botoes_resultado([
                ("Abrir Excel", lambda: self.abrir(resultado.caminho_excel), "arquivo"),
                ("Abrir pasta", lambda: self.abrir(resultado.pasta_saida), "pasta"),
                ("Novo", self.novo, "atualizar"),
            ])

        if resumo.avisos:
            ctk.CTkLabel(area, text="Avisos", font=tema.fonte_texto_forte(), text_color=tema.COR_TEXTO,
                         anchor="w").pack(fill="x", pady=(tema.ESPACO_ENTRE_BLOCOS, 4))
            for aviso in resumo.avisos:
                LinhaConferencia(area, aviso.texto, aviso.status).pack(fill="x", pady=3)
