"""Aba "E-mails" do módulo Notas Pendentes (seção 7 da especificação).

Esquerda: competência e prazo para registro; a pasta das notas do mês, o Check list (aba Emails), o modelo do
e-mail (preenchido sozinho com o da pasta config, 3.3) e a pasta de saída; o botão "Gerar e-mails".
Direita: notas anexadas, e-mails e notas sem e-mail; a tabela número x notas x destinatários; os botões
"Abrir prévia", "Texto Claude" (E7), "Abrir relatório" e "Abrir pasta".

Tudo o que fica na rede é lido em segundo plano: a tela nunca espera a rede ao abrir.
Sem regra de negócio: tudo vem de processamento.py.
"""

from __future__ import annotations

import customtkinter as ctk

from central import tema
from central.componentes import CampoRotulado, Coluna, GrupoNumeros, LinhaConferencia, TabelaSimples
from central.painel_base import PainelPadrao
from modulos.notas_pendentes import processamento

TIPOS_CHECKLIST = [("Planilha do Excel", "*.xlsx"), ("Todos os arquivos", "*.*")]
TIPOS_MODELO = [("Modelo do e-mail", "*.txt"), ("Todos os arquivos", "*.*")]
TEXTO_PRAZO_INVALIDO = "Prazo inválido: use DD/MM/AAAA (ex.: 29/10/2026)."
TEXTO_COMPETENCIA_INVALIDA = "Competência inválida: use MM/AAAA (ex.: 10/2026)."


class PainelGerar(PainelPadrao):
    TEXTO_BOTAO = "Gerar e-mails"

    def __init__(self, pai, info):
        self.ultimo_resultado: processamento.ResultadoGeracao | None = None
        self.campo_competencia: CampoRotulado | None = None
        self.campo_prazo: CampoRotulado | None = None
        self._prazo_automatico = ""
        self._modelo_automatico = None
        super().__init__(pai, info, com_cabecalho=False)
        self.lembrado = processamento.ler_preferencias()

        campos = ctk.CTkFrame(self.cartao_entrada.corpo, fg_color="transparent")
        campos.pack(fill="x", pady=(0, tema.ESPACO_PEQUENO), before=self.area_arquivos)
        self.campo_competencia = CampoRotulado(campos, "Competência (MM/AAAA)", largura=150,
                                               texto_inicial=self.lembrado.get("competencia", ""),
                                               ao_mudar=self._competencia_mudou)
        self.campo_competencia.pack(side="left", padx=(0, tema.ESPACO_PEQUENO))
        self.campo_prazo = CampoRotulado(campos, "Prazo para registro (DD/MM/AAAA)", largura=170,
                                         ao_mudar=lambda _texto: self._validar_campos())
        self.campo_prazo.pack(side="left")
        self.aviso_campos = ctk.CTkLabel(self.cartao_entrada.corpo, text="", font=tema.fonte_legenda(),
                                         text_color=tema.COR_ERRO, anchor="w")
        self.aviso_campos.pack(fill="x", before=self.area_arquivos)

        self.cartao_pasta = self.adicionar_arquivo(
            "Pasta das notas do mês (na rede; cada PDF começa com o número do responsável)", tipo="pasta",
            ao_mudar=self._pasta_escolhida, titulo_dialogo="Escolha a pasta das notas do mês")
        self.cartao_checklist = self.adicionar_arquivo(
            "Check list de contratos (os contatos da aba Emails)", ao_mudar=self._checklist_escolhido,
            tipos_arquivo=TIPOS_CHECKLIST, titulo_dialogo="Escolha o Check list")
        self.cartao_modelo = self.adicionar_arquivo(
            "Modelo do e-mail (opcional: sem ele, o texto de fábrica)", ao_mudar=self._modelo_escolhido,
            tipos_arquivo=TIPOS_MODELO, titulo_dialogo="Escolha o modelo do e-mail")
        self.adicionar_pasta_saida()

        self._sugerir_prazo()
        for chave, cartao, ao_escolher in (("pasta_notas", self.cartao_pasta, self._confirmar_pasta),
                                           ("checklist", self.cartao_checklist, self._checklist_escolhido),
                                           ("modelo", self.cartao_modelo, self._modelo_escolhido)):
            if self.lembrado.get(chave):
                cartao.definir_caminhos([self.lembrado[chave]], avisar=False)
                ao_escolher(cartao.caminhos)
        if self.lembrado.get("saida"):
            self.cartao_saida.definir_caminhos([self.lembrado["saida"]], avisar=False)
            self.cartao_saida.definir_confirmacao("Os arquivos gerados serão gravados aqui", None)
        self._validar_campos()

    # --- campos ---

    @property
    def competencia(self) -> tuple[int, int] | None:
        return processamento.interpretar_competencia(self.campo_competencia.valor()) if self.campo_competencia \
            else None

    @property
    def prazo(self):
        return processamento.interpretar_prazo(self.campo_prazo.valor()) if self.campo_prazo else None

    def _validar_campos(self) -> None:
        """A tela diz por que o botão não libera (3.4)."""
        if self.campo_prazo is None:
            return
        avisos = []
        if self.campo_competencia.valor() and self.competencia is None:
            avisos.append(TEXTO_COMPETENCIA_INVALIDA)
        if self.campo_prazo.valor() and self.prazo is None:
            avisos.append(TEXTO_PRAZO_INVALIDO)
        self.aviso_campos.configure(text=" ".join(avisos))
        self.atualizar_botoes()

    def _sugerir_prazo(self) -> None:
        """3.4: o mesmo dia do último prazo, no mês da competência; só troca o que a própria tela sugeriu."""
        if not self.competencia:
            return
        if self.campo_prazo.valor() not in ("", self._prazo_automatico):
            return
        sugestao = processamento.prazo_sugerido(self.lembrado.get("prazo", ""), *self.competencia)
        self._prazo_automatico = sugestao
        self.campo_prazo.definir(sugestao)

    def _competencia_mudou(self, _texto: str) -> None:
        if self.campo_prazo is None:
            return
        competencia = self.competencia
        if competencia:
            self._sugerir_prazo()
            atual = self.cartao_pasta.caminho
            if atual:
                def achou(pasta):
                    if pasta and self.cartao_pasta.caminho == atual and self.competencia == competencia:
                        self.cartao_pasta.definir_caminhos([pasta])

                self.ler_em_segundo_plano(lambda: processamento.pasta_do_mes(atual, *competencia), achou)
        self._validar_campos()

    # --- cartões ---

    def _confirmar(self, cartao, caminhos, leitura, texto_lendo: str) -> None:
        if not caminhos:
            return
        caminho = caminhos[0]
        cartao.definir_carregando(texto_lendo)

        def lido(confirmacao):
            if cartao.caminho != caminho:
                return
            texto, status = confirmacao or ("Não foi possível ler", "erro")
            cartao.definir_confirmacao(texto, status)
            self.atualizar_botoes()

        self.ler_em_segundo_plano(lambda: leitura(caminho), lido)

    def _confirmar_pasta(self, caminhos) -> None:
        self._confirmar(self.cartao_pasta, caminhos, processamento.confirmar_pasta_notas, "Lendo a pasta das notas...")

    def _pasta_escolhida(self, caminhos) -> None:
        self._confirmar_pasta(caminhos)
        if not caminhos:
            return
        pasta = caminhos[0]
        if self.cartao_modelo.caminho not in (None, self._modelo_automatico):
            return                                   # modelo escolhido à mão nunca é trocado (3.3)

        def achou(modelo):
            if modelo and self.cartao_pasta.caminho == pasta \
                    and self.cartao_modelo.caminho in (None, self._modelo_automatico):
                self._modelo_automatico = modelo
                self.cartao_modelo.definir_caminhos([modelo], avisar=False)
                self._modelo_escolhido([modelo])

        self.ler_em_segundo_plano(lambda: processamento.modelo_sugerido(pasta), achou)

    def _checklist_escolhido(self, caminhos) -> None:
        self._confirmar(self.cartao_checklist, caminhos, processamento.confirmar_checklist, "Lendo os contatos...")

    def _modelo_escolhido(self, caminhos) -> None:
        self._confirmar(self.cartao_modelo, caminhos, processamento.confirmar_modelo, "Lendo o modelo...")

    def pronto_para_processar(self) -> bool:
        """O modelo é opcional; um modelo com erro impede (3.3)."""
        if self.campo_prazo is None or self.competencia is None or self.prazo is None:
            return False
        if not (self.cartao_pasta.preenchido and self.cartao_checklist.preenchido and self.cartao_saida
                and self.cartao_saida.preenchido):
            return False
        return not (self.cartao_modelo.preenchido and self.cartao_modelo.status_confirmacao == "erro")

    def ao_novo(self) -> None:
        self.ultimo_resultado = None

    # --- processar ---

    def processar(self) -> None:
        if self.ocupado or not self.pronto_para_processar():
            return
        (ano, mes), prazo = self.competencia, self.prazo
        pasta, checklist, modelo, saida = (self.cartao_pasta.caminho, self.cartao_checklist.caminho,
                                           self.cartao_modelo.caminho, self.pasta_saida)

        def tarefa(progresso):
            return processamento.gerar(pasta, checklist, saida, ano, mes, prazo, modelo, progresso)

        self.executar(tarefa, self._mostrar_resultado, "Lendo a pasta das notas...")

    # --- resultado ---

    def mostrar_inicio(self) -> None:
        self.resultado.mostrar_vazio("Nenhum e-mail gerado ainda",
                                     "Informe a competência e o prazo, escolha a pasta das notas, o Check list e "
                                     "a pasta de saída e clique em \"Gerar e-mails\".", icone="envelope")

    def _mostrar_resultado(self, resultado: processamento.ResultadoGeracao) -> None:
        self.ultimo_resultado = resultado
        if resultado.erro:
            self.mostrar_erro(resultado.erro)
            return
        processamento.salvar_preferencias(
            pasta_notas=self.cartao_pasta.caminho, checklist=self.cartao_checklist.caminho,
            modelo=self.cartao_modelo.caminho, saida=self.pasta_saida,
            competencia=processamento.texto_competencia(resultado.ano, resultado.mes),
            prazo=f"{resultado.prazo:%d/%m/%Y}")
        self.lembrado = processamento.ler_preferencias()
        resumo = processamento.resumir(resultado)

        area = self.resultado.mostrar_conteudo()
        self.resultado.definir_selo(*resumo.selo)
        GrupoNumeros(area, resumo.numeros).pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))
        if resumo.emails:
            ctk.CTkLabel(area, text="E-mails por número do responsável", font=tema.fonte_texto_forte(),
                         text_color=tema.COR_TEXTO, anchor="w").pack(fill="x", pady=(0, 4))
            TabelaSimples(area, [Coluna("Número", numero=True), Coluna("Notas", numero=True),
                                 Coluna("Destinatários", numero=True), Coluna("Anexos", numero=True)],
                          resumo.emails).pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))
        for texto, status in resumo.linhas:
            LinhaConferencia(area, texto, status).pack(fill="x", pady=3)
        pasta = resultado.caminho_previa.parent if resultado.caminho_previa else self.pasta_saida
        self.botoes_resultado = self.definir_botoes_resultado([
            ("Abrir prévia", lambda: self.abrir(resultado.caminho_previa), "olho"),
            ("Texto Claude", lambda: self.abrir(resultado.caminho_texto), "arquivo"),
            ("Abrir relatório", lambda: self.abrir(resultado.caminho_relatorio), "arquivo"),
            ("Abrir pasta", lambda: self.abrir(pasta), "pasta"),
        ])
