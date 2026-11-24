"""Aba "Conciliação" do módulo Conciliação Bancária (substitui interface.py do programa original).

Sem regra de negócio: escolhe o balancete, a pasta dos extratos e onde salvar, pergunta antes de
substituir a planilha e mostra o resultado. A conciliação está em processamento.py; o pacote de
modelo novo, em pacote_modelo.py.
"""

from __future__ import annotations

from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from central import tema
from central.componentes import BotaoPrincipal, BotaoSecundario, Coluna, GrupoNumeros, LinhaConferencia, TabelaSimples
from central.painel_base import PainelPadrao, formatar_inteiro
from modulos.bancos import pacote_modelo, processamento
from modulos.bancos.comparador import STATUS
from modulos.bancos.modelos import TIPOS
from modulos.bancos.pacote_modelo import BANCOS_CONHECIDOS

MAXIMO_ARQUIVOS_NA_TELA = 6
# o ".xls" do Tasy (texto) ou o .xlsx salvo no Excel
TIPOS_BALANCETE = [("Balancete (Tasy ou Excel)", "*.xls *.xlsx"), ("Todos os arquivos", "*.*")]
TITULO_FORMULARIO = "Preparar modelo novo"


class PainelBancos(PainelPadrao):
    TEXTO_BOTAO = "Conciliar"

    def __init__(self, pai, info):
        self._competencia = None          # lida do balancete escolhido
        self._competencia_de = None       # caminho do balancete de onde ela foi lida
        self.execucao = None
        self.pacotes_criados: list[Path] = []
        super().__init__(pai, info, com_cabecalho=False)
        self.cartao_balancete = self.adicionar_arquivo("Balancete bancário (.xls do Tasy ou .xlsx)",
                                                       ao_mudar=self._balancete_escolhido,
                                                       tipos_arquivo=TIPOS_BALANCETE,
                                                       titulo_dialogo="Escolha o balancete")
        self.cartao_extratos = self.adicionar_arquivo("Pasta dos extratos (PDF, com subpastas)", tipo="pasta",
                                                      ao_mudar=self._extratos_escolhidos,
                                                      titulo_dialogo="Escolha a pasta dos extratos")
        self.adicionar_pasta_saida("Salvar em")
        self.atualizar_botoes()

    # --- escolhas ---

    def _balancete_escolhido(self, caminhos):
        if not caminhos:
            return
        caminho = caminhos[0]
        self.sugerir_pasta_saida(caminho.parent)
        self._competencia, self._competencia_de = None, None
        self.cartao_balancete.definir_confirmacao("Lendo a competência...", None)

        def lido(competencia):
            if self.cartao_balancete.caminho != caminho:
                return
            self._mostrar_competencia(caminho, competencia)

        self.ler_em_segundo_plano(lambda: self._ler_competencia(caminho), lido)

    @staticmethod
    def _ler_competencia(caminho):
        try:
            return processamento.competencia_do_balancete(caminho)
        except processamento.ErroConciliacao as erro:
            return erro

    def _mostrar_competencia(self, caminho, competencia) -> None:
        self._competencia_de = caminho
        if isinstance(competencia, Exception) or competencia is None:
            self._competencia = None
            self.cartao_balancete.definir_confirmacao(str(competencia or "Não foi possível ler o balancete."),
                                                      "erro")
        else:
            self._competencia = competencia
            self.cartao_balancete.definir_confirmacao(f"Competência {competencia:%m/%Y}", "ok")

    def _extratos_escolhidos(self, caminhos):
        if not caminhos:
            return
        quantidade = sum(1 for _ in caminhos[0].rglob("*.pdf"))
        if quantidade:
            self.cartao_extratos.definir_confirmacao(f"{formatar_inteiro(quantidade)} arquivo(s) PDF encontrado(s)",
                                                     "ok")
        else:
            self.cartao_extratos.definir_confirmacao("Nenhum PDF nesta pasta nem nas subpastas", "atencao")

    def ao_novo(self):
        self._competencia, self._competencia_de = None, None
        self.execucao = None
        self.pacotes_criados = []

    # --- conciliar ---

    def processar(self):
        if self.ocupado:
            return
        balancete, extratos, pasta_saida = self.cartao_balancete.caminho, self.cartao_extratos.caminho, self.pasta_saida
        if balancete is None or not balancete.is_file():
            self.avisar("Escolha o arquivo do balancete.")
            return
        if extratos is None or not extratos.is_dir():
            self.avisar("Escolha a pasta dos extratos.")
            return
        if pasta_saida is None:
            self.avisar("Escolha a pasta onde salvar a planilha.")
            return
        if self._competencia is None or self._competencia_de != balancete:
            # a competência ainda não foi lida (ou falhou): lê agora
            self._mostrar_competencia(balancete, self._ler_competencia(balancete))
            if self._competencia is None:
                self.avisar(self.cartao_balancete.texto_confirmacao)
                return

        destino = (pasta_saida / processamento.nome_padrao(self._competencia)).resolve()
        if not self.confirmar_substituicao([destino]):
            return
        self.executar(lambda progresso: processamento.executar(balancete, extratos, destino, progresso=progresso),
                      self._mostrar_resultado, "Lendo o balancete...")

    # --- resultado ---

    def _mostrar_resultado(self, execucao):
        self.execucao = execucao
        self.pacotes_criados = []
        resumo = processamento.resumir(execucao)
        area = self.resultado.mostrar_conteudo()
        self.resultado.definir_selo("Concluído", "ok")

        GrupoNumeros(area, [
            (resumo.ok, "contas OK", "ok"),
            (resumo.diferenca, "contas com DIFERENÇA", "erro" if resumo.diferenca else "ok"),
            (len(resumo.problemas), "extratos com problema", "atencao" if resumo.problemas else "ok"),
        ]).pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))
        TabelaSimples(area, [Coluna("Status", peso=3), Coluna("Contas", numero=True)],
                      [(status, resumo.contas_por_status.get(status, 0)) for status in STATUS]
                      ).pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))

        self.area_conferencias = ctk.CTkFrame(area, fg_color="transparent")
        self.area_conferencias.pack(fill="x")
        if not resumo.problemas:
            LinhaConferencia(self.area_conferencias, f"Todos os {resumo.arquivos} extratos foram lidos", "ok"
                             ).pack(fill="x", pady=3)
        for arquivo in resumo.problemas[:MAXIMO_ARQUIVOS_NA_TELA]:
            nome = Path(arquivo.subpasta, arquivo.arquivo.name)
            LinhaConferencia(self.area_conferencias, f"{arquivo.situacao}: {nome}", "atencao").pack(fill="x", pady=3)
        if len(resumo.problemas) > MAXIMO_ARQUIVOS_NA_TELA:
            LinhaConferencia(self.area_conferencias, f"... e mais {len(resumo.problemas) - MAXIMO_ARQUIVOS_NA_TELA} "
                             "(veja a aba Arquivos da planilha)", "atencao").pack(fill="x", pady=3)
        if resumo.nao_reconhecidos:
            LinhaConferencia(self.area_conferencias, "Há extrato(s) de modelo não reconhecido. Para preparar o "
                             "leitor novo, clique em \"Modelo novo\".", "atencao").pack(fill="x", pady=3)

        botoes = [("Abrir planilha", lambda: self.abrir(execucao.caminho), "arquivo"),
                  ("Abrir pasta", lambda: self.abrir(Path(execucao.caminho).parent), "pasta")]
        if resumo.nao_reconhecidos:
            botoes.append(("Modelo novo", self.preparar_modelo_novo, "mais"))
        botoes.append(("Novo", self.novo, "atualizar"))
        self.botoes_resultado = self.definir_botoes_resultado(botoes)

    # --- modelo novo ---

    def nao_reconhecidos(self) -> list:
        return processamento.resumir(self.execucao).nao_reconhecidos if self.execucao else []

    def preparar_modelo_novo(self):
        arquivos = self.nao_reconhecidos()
        if not arquivos or self.ocupado:
            return None
        return FormularioModeloNovo(self, arquivos, self.execucao.competencia, Path(self.execucao.caminho).parent)

    def registrar_pacote(self, pasta: Path, descricao: str):
        """Chamado pelo formulário quando um pacote é criado."""
        self.pacotes_criados.append(pasta)
        comando = f'/novo-modelo "{pasta}"'
        try:
            self.clipboard_clear()
            self.clipboard_append(comando)
        except Exception:
            pass
        LinhaConferencia(self.area_conferencias, f"Pacote criado ({descricao}). No Claude Code, digite: {comando} "
                         "(o comando já foi copiado)", "ok").pack(fill="x", pady=3)


class FormularioModeloNovo(ctk.CTkToplevel):
    """Formulário para conferir os dados de cada PDF não reconhecido.

    Só coleta o que o autor digita; quem valida e monta o pacote é pacote_modelo.
    """

    def __init__(self, painel: PainelBancos, arquivos: list, competencia, pasta_saida: Path):
        super().__init__(painel, fg_color=tema.COR_FUNDO)
        self.painel = painel
        self.arquivos = arquivos
        self.competencia = competencia
        self.pasta_saida = Path(pasta_saida)
        self.indice = 0
        self.pacotes_criados: list[Path] = []

        self.title(TITULO_FORMULARIO)
        self.geometry("780x680")
        self.transient(painel.winfo_toplevel())
        espaco = tema.ESPACO_INTERNO_CARTAO
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self.rotulo_arquivo = ctk.CTkLabel(self, text="", font=tema.fonte_subtitulo(), text_color=tema.COR_TEXTO,
                                           anchor="w")
        self.rotulo_arquivo.grid(row=0, column=0, columnspan=2, padx=espaco, pady=(espaco, 4), sticky="ew")
        ctk.CTkLabel(self, text="Confira no PDF o saldo do fim do mês e preencha abaixo. "
                                "Início do texto que o programa lê:",
                     font=tema.fonte_texto(), text_color=tema.COR_TEXTO_SUAVE, anchor="w", justify="left"
                     ).grid(row=1, column=0, columnspan=2, padx=espaco, sticky="ew")
        self.previa = ctk.CTkTextbox(self, font=tema.fonte_numero(), wrap="none", height=180,
                                     fg_color=tema.COR_SUPERFICIE, text_color=tema.COR_TEXTO,
                                     border_width=tema.LARGURA_BORDA, border_color=tema.COR_BORDA,
                                     corner_radius=tema.RAIO_PEQUENO)
        self.previa.grid(row=2, column=0, columnspan=2, padx=espaco, pady=12, sticky="nsew")

        self.var_banco = ctk.StringVar()
        self.var_tipo = ctk.StringVar(value="CC")
        self.var_conta = ctk.StringVar()
        self.var_saldo = ctk.StringVar()
        self.var_bloqueado = ctk.StringVar(value="0,00")
        self.var_observacao = ctk.StringVar()
        opcoes_campo = dict(height=tema.ALTURA_BOTAO_PEQUENO, font=tema.fonte_texto(), fg_color=tema.COR_SUPERFICIE,
                            text_color=tema.COR_TEXTO, border_color=tema.COR_BORDA, corner_radius=tema.RAIO_PEQUENO)
        campos = [
            ("Banco", ctk.CTkComboBox(self, values=list(BANCOS_CONHECIDOS), variable=self.var_banco,
                                      button_color=tema.COR_PRINCIPAL, button_hover_color=tema.COR_PRINCIPAL_HOVER,
                                      **opcoes_campo)),
            ("Tipo", ctk.CTkOptionMenu(self, values=list(TIPOS), variable=self.var_tipo, height=tema.ALTURA_BOTAO_PEQUENO,
                                       font=tema.fonte_texto(), fg_color=tema.COR_PRINCIPAL,
                                       button_color=tema.COR_PRINCIPAL, button_hover_color=tema.COR_PRINCIPAL_HOVER,
                                       text_color=tema.COR_TEXTO_SOBRE_PRINCIPAL, corner_radius=tema.RAIO_PEQUENO)),
            ("Conta (como no extrato)", ctk.CTkEntry(self, textvariable=self.var_conta, **opcoes_campo)),
            ("Saldo total conferido (R$)", ctk.CTkEntry(self, textvariable=self.var_saldo, **opcoes_campo)),
            ("Saldo bloqueado (R$)", ctk.CTkEntry(self, textvariable=self.var_bloqueado, **opcoes_campo)),
            ("Observação (opcional)", ctk.CTkEntry(self, textvariable=self.var_observacao, **opcoes_campo)),
        ]
        for linha, (rotulo, campo) in enumerate(campos, start=3):
            ctk.CTkLabel(self, text=rotulo, font=tema.fonte_rotulo(), text_color=tema.COR_TEXTO, anchor="w").grid(
                row=linha, column=0, padx=(espaco, 12), pady=4, sticky="w")
            campo.grid(row=linha, column=1, padx=(0, espaco), pady=4, sticky="ew")

        botoes = ctk.CTkFrame(self, fg_color="transparent")
        botoes.grid(row=9, column=0, columnspan=2, padx=espaco, pady=espaco, sticky="e")
        BotaoSecundario(botoes, "Pular este arquivo", self.pular, largura=170).pack(side="left", padx=(0, 12))
        BotaoPrincipal(botoes, "Salvar pacote", self.salvar, icone="check").pack(side="left")

        self._mostrar_arquivo()

    @property
    def resumo_atual(self):
        return self.arquivos[self.indice]

    def _mostrar_arquivo(self):
        resumo = self.resumo_atual
        self.rotulo_arquivo.configure(text=f"Arquivo {self.indice + 1} de {len(self.arquivos)}: {resumo.arquivo.name}")
        try:
            previa = pacote_modelo.texto_inicial(resumo.arquivo)
        except Exception as erro:
            previa = f"(não foi possível ler o texto: {erro})"
        self.previa.configure(state="normal")
        self.previa.delete("1.0", "end")
        self.previa.insert("end", previa)
        self.previa.configure(state="disabled")
        for variavel in (self.var_banco, self.var_conta, self.var_saldo, self.var_observacao):
            variavel.set("")
        self.var_tipo.set("CC")
        self.var_bloqueado.set("0,00")

    def _dados(self) -> pacote_modelo.DadosModeloNovo:
        return pacote_modelo.DadosModeloNovo(
            banco=self.var_banco.get(), tipo=self.var_tipo.get(), conta=self.var_conta.get(),
            saldo_total=self.var_saldo.get(), saldo_bloqueado=self.var_bloqueado.get(),
            observacao=self.var_observacao.get())

    def salvar(self):
        resumo = self.resumo_atual
        try:
            dados = pacote_modelo.validar(self._dados())
        except ValueError as erro:
            messagebox.showerror(TITULO_FORMULARIO, str(erro), parent=self)
            return
        destino = pacote_modelo.caminho_do_pacote(self.pasta_saida, resumo.arquivo, self.competencia)
        if destino.exists() and not messagebox.askyesno(
                TITULO_FORMULARIO, f"Já existe um pacote para este arquivo:\n{destino}\n\nDeseja substituí-lo?",
                parent=self):
            return
        try:
            pasta = pacote_modelo.criar_pacote(self.pasta_saida, resumo.arquivo, self.competencia, dados,
                                               resumo.subpasta)
        except OSError as erro:
            messagebox.showerror(TITULO_FORMULARIO, f"Não foi possível criar o pacote: {erro}", parent=self)
            return
        self.pacotes_criados.append(pasta)
        self.painel.registrar_pacote(pasta, pacote_modelo.descrever(dados))
        self._proximo()

    def pular(self):
        self._proximo()

    def _proximo(self):
        self.indice += 1
        if self.indice >= len(self.arquivos):
            self.destroy()
        else:
            self._mostrar_arquivo()
