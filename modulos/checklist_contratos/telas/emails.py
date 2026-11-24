"""Aba "E-mails" do módulo Notas de Contrato (seção 7 da especificação; regras G1 a G6).

Esquerda: o credentials.json do Google (escolhido uma vez), o remetente esperado (G2) e o botão "Criar
rascunhos no Gmail" (só rascunho, G1), habilitado depois de gerar as pendências.
Direita: os e-mails gerados na aba Pendências; depois de criar, a conta autorizada e o resultado de
cada e-mail, com os botões "Abrir registro", "Abrir pasta" e "Trocar conta".
Sem credencial: o texto de como pedir à TI (G6) e o lembrete do texto para o Claude Desktop (E8).

Sem regra de negócio: tudo vem de processamento.py.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from central import tema
from central.componentes import CampoRotulado, Coluna, GrupoNumeros, LinhaConferencia, TabelaSimples, TextoQuebravel
from central.painel_base import PainelPadrao
from modulos.checklist_contratos import processamento

TIPOS_CREDENCIAIS = [("Credencial do Google", "*.json"), ("Todos os arquivos", "*.*")]


class PainelEmails(PainelPadrao):
    TEXTO_BOTAO = "Criar rascunhos no Gmail"

    def __init__(self, pai, info, obter_pendencias: Callable[[], processamento.ResultadoPendencias | None]):
        """obter_pendencias(): o último resultado da aba Pendências (None se ainda não gerou)."""
        self.obter_pendencias = obter_pendencias
        self.ultimo_resultado: processamento.ResultadoRascunhos | None = None
        self.campo_remetente: CampoRotulado | None = None
        super().__init__(pai, info, com_cabecalho=False)
        lembrado = processamento.ler_preferencias()
        self.cartao_credenciais = self.adicionar_arquivo(
            "Credencial do Google (credentials.json, pedido à TI)", ao_mudar=self._credenciais_escolhidas,
            tipos_arquivo=TIPOS_CREDENCIAIS, titulo_dialogo="Escolha o credentials.json do Google")
        self.campo_remetente = CampoRotulado(
            self.area_arquivos, "Remetente esperado (a conta do Gmail autorizada)", largura=360,
            texto_inicial=lembrado.get("remetente", processamento.REMETENTE_PADRAO),
            ao_mudar=lambda _: self.atualizar_botoes())
        self.campo_remetente.pack(anchor="w", pady=(0, tema.ESPACO_PEQUENO))
        if lembrado.get("credenciais"):
            self.cartao_credenciais.definir_caminhos([lembrado["credenciais"]], avisar=False)
            self._credenciais_escolhidas(self.cartao_credenciais.caminhos)
        self.atualizar_botoes()
        self.mostrar_inicio()

    @property
    def pendencias(self) -> processamento.ResultadoPendencias | None:
        resultado = self.obter_pendencias()
        return resultado if resultado is not None and resultado.pendencias is not None else None

    def _credenciais_escolhidas(self, caminhos) -> None:
        if not caminhos:
            self.mostrar_inicio()
            return
        caminho = caminhos[0]
        self.cartao_credenciais.definir_carregando("Conferindo...")

        def lido(confirmacao):
            if self.cartao_credenciais.caminho != caminho:
                return
            texto, status = confirmacao or ("Não foi possível ler", "erro")
            self.cartao_credenciais.definir_confirmacao(texto, status)
            self.atualizar_botoes()
            if not self.ocupado and self.ultimo_resultado is None:
                self.mostrar_inicio()

        self.ler_em_segundo_plano(lambda: processamento.confirmar_credenciais(caminho), lido)

    def pronto_para_processar(self) -> bool:
        if self.campo_remetente is None or not self.campo_remetente.valor():
            return False
        pendencias = self.pendencias
        return (pendencias is not None and bool(pendencias.pendencias.emails)
                and self.cartao_credenciais.preenchido and self.cartao_credenciais.status_confirmacao != "erro")

    def ao_ver_a_aba(self) -> None:
        """A aba foi aberta: mostra os e-mails das pendências mais recentes."""
        self.atualizar_botoes()
        if not self.ocupado and self.ultimo_resultado is None:
            self.mostrar_inicio()

    def ao_novo(self) -> None:
        self.ultimo_resultado = None

    # --- processar ---

    def processar(self) -> None:
        if self.ocupado or not self.pronto_para_processar():
            return
        pendencias = self.pendencias
        emails = pendencias.pendencias.emails
        if not self.perguntar(f"Criar {len(emails)} rascunho(s) no Gmail de {self.campo_remetente.valor()}?\n\n"
                              "Nada é enviado: os rascunhos ficam no Gmail para você revisar e enviar.\n"
                              "Na primeira vez o navegador abre para autorizar."):
            return
        credenciais, remetente = self.cartao_credenciais.caminho, self.campo_remetente.valor()
        pasta = pendencias.caminho_previa.parent if pendencias.caminho_previa else None

        def tarefa(progresso):
            return processamento.criar_rascunhos(emails, credenciais, remetente, pasta, progresso)

        self.executar(tarefa, self._mostrar_resultado, "Conectando ao Gmail...")

    # --- resultado ---

    def mostrar_inicio(self) -> None:
        if self.campo_remetente is None:          # ainda montando a tela
            super().mostrar_inicio()
            return
        pendencias = self.pendencias
        if pendencias is None:
            self.resultado.mostrar_vazio("Nenhum e-mail ainda",
                                         "Gere as pendências na aba \"Pendências\": os e-mails aparecem aqui.",
                                         icone="prancheta")
            return
        area = self.resultado.mostrar_conteudo(mostrar_rodape=False)
        emails = pendencias.pendencias.emails
        GrupoNumeros(area, [(len(emails), "E-mails para criar", "principal"),
                            (len(pendencias.pendencias.sem_email), "Sem e-mail",
                             "erro" if pendencias.pendencias.sem_email else "ok")]
                     ).pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))
        TabelaSimples(area, [Coluna("Responsável", peso=2), Coluna("Notas", numero=True), Coluna("Assunto", peso=4)],
                      [(e.responsavel, e.notas, e.assunto) for e in emails]
                      ).pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))
        if not self.cartao_credenciais.preenchido or self.cartao_credenciais.status_confirmacao == "erro":
            TextoQuebravel(area, processamento.TEXTO_SEM_CREDENCIAL, cor=tema.COR_TEXTO_SUAVE
                           ).pack(fill="x", pady=(0, tema.ESPACO_PEQUENO))

    def _mostrar_resultado(self, resultado: processamento.ResultadoRascunhos) -> None:
        self.ultimo_resultado = resultado
        if resultado.erro:
            self.mostrar_erro(resultado.erro)
            self.definir_botoes_resultado([("Trocar conta", self._trocar_conta, "atualizar")])
            self.resultado.rodape.pack(fill="x", pady=(tema.ESPACO_ENTRE_BLOCOS, 0))
            return
        processamento.salvar_preferencias(credenciais=self.cartao_credenciais.caminho,
                                          remetente=self.campo_remetente.valor())
        erros = len(resultado.itens) - resultado.criados
        area = self.resultado.mostrar_conteudo()
        self.resultado.definir_selo(*(("Com erro", "erro") if erros else ("Concluído", "ok")))
        GrupoNumeros(area, [(resultado.criados, "Rascunhos criados", "ok"),
                            (erros, "Com erro", "erro" if erros else "ok")]
                     ).pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))
        ctk.CTkLabel(area, text=f"Conta: {resultado.conta}", font=tema.fonte_texto_forte(),
                     text_color=tema.COR_TEXTO, anchor="w").pack(fill="x", pady=(0, 4))
        for item in resultado.itens:
            texto = f"{item.email.responsavel}: {item.erro}" if item.erro else \
                f"{item.email.responsavel}: rascunho criado ({item.email.notas} nota(s))"
            LinhaConferencia(area, texto, "erro" if item.erro else "ok").pack(fill="x", pady=3)
        if resultado.erro_registro:
            LinhaConferencia(area, resultado.erro_registro, "erro").pack(fill="x", pady=3)
        registro = resultado.caminho_registro
        self.botoes_resultado = self.definir_botoes_resultado([
            ("Abrir registro", lambda: self.abrir(registro), "arquivo"),
            ("Abrir pasta", lambda: self.abrir(registro.parent if registro else None), "pasta"),
            ("Trocar conta", self._trocar_conta, "atualizar"),
        ])

    def _trocar_conta(self) -> None:
        if self.perguntar("Esquecer a autorização do Gmail? Na próxima vez o navegador abre para você "
                          "entrar com a conta certa."):
            processamento.esquecer_autorizacao()
            self.informar("Pronto. Clique em \"Criar rascunhos no Gmail\" para autorizar de novo.")
