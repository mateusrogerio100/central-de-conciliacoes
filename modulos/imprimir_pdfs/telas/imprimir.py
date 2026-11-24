"""Aba "Imprimir" do módulo Imprimir PDFs (era interface/painel_impressao.py do Conciliações AMES, seção
FERRAMENTAS do menu). Mesma tela, mesmos textos e mesmo comportamento; na Central o cabeçalho vem do módulo,
e a pasta e a impressora ficam guardadas pelo processamento.py.

Esquerda: a escolha dos PDFs (vários arquivos ou uma pasta inteira) e a lista, com uma caixinha
por arquivo e a quantidade de folhas. Direita: o total de folhas para colocar na impressora, a
escolha da impressora (lembrada entre aberturas) e o botão Imprimir, com o andamento.

Sem regra de negócio: a tela só chama processamento.py e mostra o que volta.
"""

from __future__ import annotations

import threading
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable

import customtkinter as ctk

from central import log_uso, tema
from central.componentes import (
    BarraProgresso,
    BotaoPrincipal,
    BotaoSecundario,
    Cartao,
    CampoComLista,
    GrupoNumeros,
    LayoutDuasColunas,
    LinhaConferencia,
    Separador,
    _quebrar_em,
)
from central.painel_base import formatar_inteiro
from central.segundo_plano import TarefaEmSegundoPlano
from modulos.imprimir_pdfs import processamento
from modulos.imprimir_pdfs.processamento import Envio, ErroDeImpressao, EstadoNaFila, PdfParaImprimir

TIPOS_PDF = [("Arquivos PDF", "*.pdf"), ("Todos os arquivos", "*.*")]
ACAO_LOG = "Imprimir"               # o nome deste uso no log de uso da Central (central/log_uso.py)
TEXTO_SEM_PDFS = "Nenhum PDF escolhido. Escolha os arquivos ou a pasta inteira."
TEXTO_COMO_IMPRIME = ("Um lado só, uma página por folha. Todos os PDFs marcados vão juntos numa impressão "
                      "só: na fila da impressora, nada de outra pessoa sai no meio.")
TEXTO_SEM_IMPRESSORA = "Nenhuma impressora encontrada neste computador."


def plural(quantidade: int, singular: str, plural_: str | None = None) -> str:
    return f"{formatar_inteiro(quantidade)} {singular if quantidade == 1 else (plural_ or singular + 's')}"


class LinhaPdf(ctk.CTkFrame):
    """Uma linha da lista: caixinha com o nome do arquivo e, à direita, as folhas (ou o problema).

    PDF com 2 ou mais páginas ganha, embaixo do nome, uma caixinha por página (todas marcadas ao escolher)
    e os atalhos "Só a 1ª" e "Todas" (pedido do usuário, out/2026: de alguns PDFs só se imprime a 1ª folha).
    Desmarcar todas as páginas desmarca o arquivo; marcar uma página de um arquivo desmarcado o marca.
    """

    LARGURA_PAGINA = 72          # cada caixinha "Pág. N" (cabe até "Pág. 99")
    ESPACO_PAGINA = 6
    RECUO_PAGINAS = 30           # as páginas ficam recuadas, embaixo do nome do arquivo

    def __init__(self, pai, pdf: PdfParaImprimir, ao_mudar: Callable[[], None]):
        super().__init__(pai, fg_color="transparent")
        self.pdf = pdf
        self._ao_mudar = ao_mudar
        self.variavel = ctk.BooleanVar(value=pdf.pode_imprimir)
        self.caixas_paginas: list[ctk.CTkCheckBox] = []
        self.variaveis_paginas: list[ctk.BooleanVar] = []
        self.atalhos: list[ctk.CTkButton] = []
        self.quadro_atalhos: ctk.CTkFrame | None = None
        self.paginas_por_linha = 0
        self.grid_columnconfigure(0, weight=1)
        self.caixa = self._caixinha(self, pdf.nome, self.variavel, self._ao_marcar_arquivo, tema.fonte_texto(), 20)
        self.caixa.grid(row=0, column=0, sticky="w", pady=6)
        if not pdf.pode_imprimir:
            self.caixa.configure(state="disabled")
            ctk.CTkLabel(self, text=pdf.erro, font=tema.fonte_legenda(), text_color=tema.COR_ERRO,
                         anchor="e", justify="right", wraplength=200
                         ).grid(row=0, column=1, sticky="e", padx=(8, 0))
            return
        self.rotulo_folhas = ctk.CTkLabel(self, text="", font=tema.fonte_numero(), text_color=tema.COR_TEXTO,
                                          anchor="e")
        self.rotulo_folhas.grid(row=0, column=1, sticky="e", padx=(8, 0))
        if pdf.paginas >= 2:
            self._montar_paginas()
        self._mostrar_folhas()

    @staticmethod
    def _caixinha(pai, texto, variavel, comando, fonte, lado: int) -> ctk.CTkCheckBox:
        return ctk.CTkCheckBox(
            pai, text=texto, variable=variavel, command=comando, font=fonte,
            text_color=tema.COR_TEXTO, text_color_disabled=tema.COR_TEXTO_SUAVE, fg_color=tema.COR_PRINCIPAL,
            hover_color=tema.COR_PRINCIPAL_HOVER, border_color=tema.COR_BORDA,
            checkmark_color=tema.COR_TEXTO_SOBRE_PRINCIPAL, corner_radius=tema.RAIO_PEQUENO // 2,
            checkbox_width=lado, checkbox_height=lado, border_width=2)

    def _montar_paginas(self) -> None:
        quadro = ctk.CTkFrame(self, fg_color="transparent")
        quadro.grid(row=1, column=0, columnspan=2, sticky="w", padx=(self.RECUO_PAGINAS, 0), pady=(0, 8))
        for numero in range(1, self.pdf.paginas + 1):
            variavel = ctk.BooleanVar(value=True)
            caixa = self._caixinha(quadro, f"Pág. {numero}", variavel, self._ao_marcar_pagina,
                                   tema.fonte_legenda(), 16)
            caixa.configure(width=self.LARGURA_PAGINA)
            self.caixas_paginas.append(caixa)
            self.variaveis_paginas.append(variavel)
        atalhos = self.quadro_atalhos = ctk.CTkFrame(quadro, fg_color="transparent")
        self._arrumar_paginas(6)
        # quantas caixinhas cabem por linha depende da largura da lista (na janela mínima, menos)
        self.bind("<Configure>", self._ao_mudar_largura, add="+")
        for texto, comando in (("Só a 1ª", self.so_a_primeira), ("Todas", self.todas_as_paginas)):
            botao = ctk.CTkButton(atalhos, text=texto, command=comando, height=tema.ALTURA_SELO - 2, width=1,
                                  corner_radius=tema.RAIO_PEQUENO, fg_color="transparent",
                                  hover_color=tema.COR_PRINCIPAL_SUAVE, border_width=0,
                                  text_color=tema.COR_PRINCIPAL, font=tema.fonte_legenda())
            botao.pack(side="left", padx=(0, tema.ESPACO_PEQUENO))
            self.atalhos.append(botao)

    def _arrumar_paginas(self, por_linha: int) -> None:
        por_linha = max(1, por_linha)
        if por_linha == self.paginas_por_linha:
            return
        self.paginas_por_linha = por_linha
        for indice, caixa in enumerate(self.caixas_paginas):
            linha, coluna = divmod(indice, por_linha)
            caixa.grid(row=linha, column=coluna, sticky="w", padx=(0, self.ESPACO_PAGINA), pady=2)
        self.quadro_atalhos.grid(row=(len(self.caixas_paginas) - 1) // por_linha + 1, column=0,
                                 columnspan=por_linha, sticky="w", pady=(2, 0))

    def _ao_mudar_largura(self, evento) -> None:
        largura = int(evento.width / ctk.ScalingTracker.get_widget_scaling(self)) - self.RECUO_PAGINAS
        self._arrumar_paginas(largura // (self.LARGURA_PAGINA + self.ESPACO_PAGINA))

    # --- marcação ---

    @property
    def paginas_marcadas(self) -> list[int]:
        if not self.variaveis_paginas:
            return list(range(1, self.pdf.paginas + 1))
        return [n for n, v in enumerate(self.variaveis_paginas, start=1) if v.get()]

    @property
    def marcado(self) -> bool:
        return self.pdf.pode_imprimir and self.variavel.get() and bool(self.paginas_marcadas)

    @property
    def pdf_para_imprimir(self) -> PdfParaImprimir:
        """O PDF com as páginas escolhidas (None quando são todas)."""
        paginas = self.paginas_marcadas
        return replace(self.pdf, escolhidas=None if len(paginas) == self.pdf.paginas else tuple(paginas))

    def marcar(self, sim: bool) -> None:
        if self.pdf.pode_imprimir:
            self.variavel.set(sim)
            if sim and not self.paginas_marcadas:
                self.todas_as_paginas(avisar=False)
            self._mostrar_folhas()

    def so_a_primeira(self) -> None:
        for numero, variavel in enumerate(self.variaveis_paginas, start=1):
            variavel.set(numero == 1)
        self._ao_marcar_pagina()

    def todas_as_paginas(self, avisar: bool = True) -> None:
        for variavel in self.variaveis_paginas:
            variavel.set(True)
        if avisar:
            self._ao_marcar_pagina()

    def _ao_marcar_arquivo(self) -> None:
        if self.variavel.get() and not self.paginas_marcadas:
            self.todas_as_paginas(avisar=False)
        self._mostrar_folhas()
        self._ao_mudar()

    def _ao_marcar_pagina(self) -> None:
        self.variavel.set(bool(self.paginas_marcadas))
        self._mostrar_folhas()
        self._ao_mudar()

    def _mostrar_folhas(self) -> None:
        escolhidas, total = len(self.paginas_marcadas), self.pdf.paginas
        texto = plural(total, "folha") if escolhidas == total else f"{escolhidas} de {plural(total, 'folha')}"
        self.rotulo_folhas.configure(text=texto)

    def habilitar(self, sim: bool) -> None:
        if not self.pdf.pode_imprimir:
            return
        estado = "normal" if sim else "disabled"
        for widget in (self.caixa, *self.caixas_paginas, *self.atalhos):
            widget.configure(state=estado)


class PainelImprimirPdfs(ctk.CTkFrame):
    def __init__(self, pai, info):
        super().__init__(pai, fg_color="transparent")
        self.info = info
        self.ocupado = False
        self.pasta = ""
        pasta_inicial = processamento.ler_pasta_lembrada()
        if pasta_inicial:
            threading.Thread(target=self._conferir_pasta_lembrada, args=(pasta_inicial,), daemon=True).start()
        impressora_inicial = processamento.ler_impressora_lembrada()
        self.linhas: list[LinhaPdf] = []
        self.tarefa: TarefaEmSegundoPlano | None = None
        self.acompanhamento = 0              # conta os acompanhamentos da fila (um novo encerra o anterior)
        self.linha_fila: LinhaConferencia | None = None

        layout = LayoutDuasColunas(self)
        layout.pack(fill="both", expand=True)

        # Esquerda: os PDFs
        entrada = Cartao(layout.esquerda, "PDFs para imprimir")
        entrada.pack(fill="both", expand=True)
        escolha = ctk.CTkFrame(entrada.corpo, fg_color="transparent")
        escolha.pack(fill="x")
        for coluna in (0, 1):
            escolha.grid_columnconfigure(coluna, weight=1, uniform="escolha")
        self.botao_arquivos = BotaoSecundario(escolha, "Escolher PDFs", self.escolher_arquivos, icone="arquivos",
                                              altura=tema.ALTURA_BOTAO_PEQUENO)
        self.botao_arquivos.configure(width=1)
        self.botao_arquivos.grid(row=0, column=0, sticky="ew")
        self.botao_pasta = BotaoSecundario(escolha, "Escolher pasta", self.escolher_pasta, icone="pasta",
                                           altura=tema.ALTURA_BOTAO_PEQUENO)
        self.botao_pasta.configure(width=1)
        self.botao_pasta.grid(row=0, column=1, sticky="ew", padx=(tema.ESPACO_PEQUENO, 0))

        self.rotulo_origem = ctk.CTkLabel(entrada.corpo, text=TEXTO_SEM_PDFS, font=tema.fonte_legenda(),
                                          text_color=tema.COR_TEXTO_SUAVE, anchor="w", justify="left",
                                          wraplength=420)
        self.rotulo_origem.pack(fill="x", pady=(tema.ESPACO_PEQUENO, 0))

        self.barra_marcar = ctk.CTkFrame(entrada.corpo, fg_color="transparent")
        estilo = dict(height=tema.ALTURA_SELO, width=1, corner_radius=tema.RAIO_PEQUENO, fg_color="transparent",
                      hover_color=tema.COR_PRINCIPAL_SUAVE, border_width=0, text_color=tema.COR_PRINCIPAL,
                      font=tema.fonte_legenda())
        self.botao_marcar = ctk.CTkButton(self.barra_marcar, text="Marcar todos",
                                          command=lambda: self.marcar_todos(True), **estilo)
        self.botao_marcar.pack(side="left")
        self.botao_desmarcar = ctk.CTkButton(self.barra_marcar, text="Desmarcar todos",
                                             command=lambda: self.marcar_todos(False), **estilo)
        self.botao_desmarcar.pack(side="left", padx=(tema.ESPACO_PEQUENO, 0))
        self.lista = ctk.CTkFrame(entrada.corpo, fg_color="transparent")

        # Direita: a impressão
        saida = Cartao(layout.direita, "Impressão")
        saida.pack(fill="x", anchor="n")          # fica no alto, junto do começo da lista
        self.numeros = GrupoNumeros(saida.corpo, [
            ("0", "Folhas para colocar na impressora", "principal"),
            ("0", "PDFs marcados", "principal"),
            ("0", "Com problema", "ok"),
        ])
        self.numeros.pack(fill="x")

        self.impressoras = self._ler_impressoras()
        self.campo_impressora = CampoComLista(saida.corpo, "Impressora", self.impressoras, largura=360,
                                              texto_inicial=self._impressora_inicial(impressora_inicial),
                                              ao_mudar=self._ao_mudar_impressora)
        self.campo_impressora.lista.configure(state="readonly")
        self.campo_impressora.pack(fill="x", pady=(tema.ESPACO_ENTRE_BLOCOS, 0))
        self.rotulo_como = ctk.CTkLabel(saida.corpo, text=TEXTO_COMO_IMPRIME if self.impressoras
                                        else TEXTO_SEM_IMPRESSORA, font=tema.fonte_legenda(),
                                        text_color=tema.COR_TEXTO_SUAVE if self.impressoras else tema.COR_ERRO,
                                        anchor="w", justify="left", wraplength=400)
        self.rotulo_como.pack(fill="x", pady=(tema.ESPACO_PEQUENO, 0))

        acoes = ctk.CTkFrame(saida.corpo, fg_color="transparent")
        acoes.pack(fill="x", pady=(tema.ESPACO_ENTRE_BLOCOS, 0))
        self.botao_imprimir = BotaoPrincipal(acoes, "Imprimir", self.imprimir, icone="impressora")
        self.botao_imprimir.pack(side="left", fill="x", expand=True)
        self.botao_limpar_tudo = BotaoSecundario(acoes, "Limpar tudo", self.novo, icone="erro")
        self.botao_limpar_tudo.pack(side="left", padx=(tema.ESPACO_PEQUENO, 0))
        # a janela da fila do Windows: ver o estado das impressões, continuar uma pausada ou cancelar
        self.botao_fila = BotaoSecundario(saida.corpo, "Ver fila da impressora", self.ver_fila, icone="olho",
                                          altura=tema.ALTURA_BOTAO_PEQUENO)
        self.botao_fila.pack(fill="x", pady=(tema.ESPACO_PEQUENO, 0))
        self.area_status = ctk.CTkFrame(saida.corpo, fg_color="transparent", width=1, height=1)
        self.area_status.pack(fill="x", pady=(tema.ESPACO_PEQUENO, 0))

        # os textos quebram a linha conforme a largura real dos cartões (na janela mínima eles são estreitos)
        saida.corpo.bind("<Configure>", self._ajustar_quebra_direita, add="+")
        entrada.corpo.bind("<Configure>", lambda e: self._quebrar(self.rotulo_origem, e.width), add="+")
        self._largura_direita = 0
        self._atualizar()

    def _conferir_pasta_lembrada(self, pasta: str) -> None:
        """Roda fora da tela: com a pasta lembrada num servidor fora do ar, o Windows leva ~21 s para
        responder, e a Central abria travada nesse tempo. Só vale se o usuário ainda não escolheu outra."""
        if Path(pasta).is_dir() and not self.pasta:
            self.pasta = pasta

    def _quebrar(self, rotulo, largura_tela: int) -> None:
        largura = int(largura_tela / ctk.ScalingTracker.get_widget_scaling(self)) - 8
        if largura > 60:
            _quebrar_em(rotulo, largura)

    def _ajustar_quebra_direita(self, evento=None) -> None:
        if evento is not None:
            self._largura_direita = evento.width
        if not self._largura_direita:
            return
        self._quebrar(self.rotulo_como, self._largura_direita)
        for linha in self.area_status.winfo_children():
            if isinstance(linha, LinhaConferencia):
                self._quebrar(linha.rotulo_texto, self._largura_direita - 28)   # menos o ícone

    # --- impressoras ---

    @staticmethod
    def _ler_impressoras() -> list[str]:
        try:
            return processamento.listar_impressoras()
        except (ErroDeImpressao, OSError):
            return []

    def _impressora_inicial(self, lembrada: str) -> str:
        """A lembrada da última vez; senão a padrão do Windows; senão a primeira da lista."""
        if lembrada in self.impressoras:
            return lembrada
        try:
            padrao = processamento.impressora_padrao()
        except (ErroDeImpressao, OSError):
            padrao = ""
        if padrao in self.impressoras:
            return padrao
        return self.impressoras[0] if self.impressoras else ""

    @property
    def impressora(self) -> str:
        return self.campo_impressora.valor()

    def _ao_mudar_impressora(self, nome: str) -> None:
        if nome:
            processamento.salvar_impressora_lembrada(nome)
        self._atualizar()

    # --- escolha dos PDFs ---

    def escolher_arquivos(self) -> None:
        escolhidos = filedialog.askopenfilenames(title="Selecione os PDFs para imprimir", filetypes=TIPOS_PDF,
                                                 initialdir=self.pasta or None)
        if escolhidos:
            self.definir_arquivos(escolhidos)

    def escolher_pasta(self) -> None:
        pasta = filedialog.askdirectory(title="Escolha a pasta com os PDFs para imprimir",
                                        initialdir=self.pasta or None)
        if pasta:
            self.definir_pasta(pasta)

    def definir_arquivos(self, caminhos) -> None:
        caminhos = [Path(c) for c in caminhos]
        self._lembrar_pasta(caminhos[0].parent)
        self._mostrar_lista(processamento.ler_pdfs(caminhos),
                            f"{plural(len(caminhos), 'arquivo escolhido', 'arquivos escolhidos')} da pasta {caminhos[0].parent.name}")

    def definir_pasta(self, pasta) -> None:
        pasta = Path(pasta)
        self._lembrar_pasta(pasta)
        try:
            pdfs = processamento.pdfs_da_pasta(pasta)
        except OSError as erro:
            pdfs = []
            origem = f"Não foi possível abrir a pasta {pasta}: {erro}"
        else:
            origem = f"Pasta {pasta.name}" if pdfs else f"A pasta {pasta.name} não tem nenhum PDF."
        self._mostrar_lista(pdfs, origem)

    def _lembrar_pasta(self, pasta: Path) -> None:
        self.pasta = str(pasta)
        processamento.salvar_pasta_lembrada(self.pasta)

    def _mostrar_lista(self, pdfs: list[PdfParaImprimir], origem: str) -> None:
        for filho in self.lista.winfo_children():
            filho.destroy()
        self.linhas = []
        for posicao, pdf in enumerate(pdfs):
            if posicao:
                Separador(self.lista).pack(fill="x")
            linha = LinhaPdf(self.lista, pdf, self._atualizar)
            linha.pack(fill="x")
            self.linhas.append(linha)
        self.rotulo_origem.configure(text=origem)
        if self.linhas:
            self.barra_marcar.pack(fill="x", pady=(tema.ESPACO_PEQUENO, 0))
            self.lista.pack(fill="x", pady=(4, 0))
        else:
            self.barra_marcar.pack_forget()
            self.lista.pack_forget()
        self._limpar_status()
        self._atualizar()

    def marcar_todos(self, sim: bool) -> None:
        for linha in self.linhas:
            linha.marcar(sim)
        self._atualizar()

    @property
    def marcados(self) -> list[PdfParaImprimir]:
        return [l.pdf_para_imprimir for l in self.linhas if l.marcado]

    # --- números e botões ---

    def _atualizar(self) -> None:
        marcados = self.marcados
        folhas = processamento.total_de_folhas(marcados)
        com_problema = sum(1 for l in self.linhas if not l.pdf.pode_imprimir)
        blocos = self.numeros.blocos
        blocos[0].atualizar(formatar_inteiro(folhas))
        validos = sum(1 for l in self.linhas if l.pdf.pode_imprimir)
        blocos[1].atualizar(formatar_inteiro(len(marcados)),
                            f"PDFs marcados (de {validos})" if self.linhas else "PDFs marcados")
        blocos[2].atualizar(formatar_inteiro(com_problema), tom="erro" if com_problema else "ok")

        self.botao_imprimir.configure(text=f"Imprimir {plural(folhas, 'folha')}" if folhas else "Imprimir")
        self.botao_imprimir.habilitar(bool(marcados) and bool(self.impressora) and not self.ocupado)
        self.botao_limpar_tudo.habilitar(bool(self.linhas) and not self.ocupado)
        self.botao_fila.habilitar(bool(self.impressora))
        for botao in (self.botao_arquivos, self.botao_pasta, self.botao_marcar, self.botao_desmarcar):
            botao.configure(state="disabled" if self.ocupado else "normal")
        self.campo_impressora.lista.configure(state="disabled" if self.ocupado else "readonly")
        for linha in self.linhas:
            linha.habilitar(not self.ocupado)

    def _limpar_status(self) -> None:
        self.acompanhamento += 1             # para de acompanhar a impressão anterior
        self.linha_fila = None
        for filho in self.area_status.winfo_children():
            filho.destroy()

    # --- impressão ---

    def imprimir(self) -> None:
        if self.ocupado:
            return
        pdfs, impressora = self.marcados, self.impressora
        if not pdfs or not impressora:
            return
        folhas = processamento.total_de_folhas(pdfs)
        if not messagebox.askyesno(
                self.info.nome,
                f"Mandar {plural(folhas, 'folha')} ({plural(len(pdfs), 'PDF')}) para a impressora\n"
                f"{impressora}?\n\nConfira se há pelo menos {plural(folhas, 'folha')} de papel na impressora.",
                parent=self):
            return
        self.iniciar_impressao(pdfs, impressora)

    def iniciar_impressao(self, pdfs: list[PdfParaImprimir], impressora: str) -> None:
        """Manda para a impressora em segundo plano (a janela não congela), mostrando o andamento."""
        self.ocupado = True
        self._atualizar()
        self._limpar_status()
        barra = BarraProgresso(self.area_status, "Preparando a impressão...")
        barra.pack(fill="x", pady=(tema.ESPACO_PEQUENO, 0))
        total = processamento.total_de_folhas(pdfs)

        def tarefa(progresso):
            return processamento.imprimir(
                pdfs, impressora,
                ao_avancar=lambda folha, _total: progresso(f"Mandando a folha {folha} de {total}...", folha / total))

        self.tarefa = TarefaEmSegundoPlano(
            self, tarefa, ao_progresso=barra.atualizar,
            ao_concluir=lambda envio: self._ao_mandar(envio, impressora),
            ao_falhar=self._falhar).iniciar()

    def _ao_mandar(self, envio: Envio, impressora: str) -> None:
        log_uso.registrar(self.info.nome, ACAO_LOG)
        self._terminar(f"{plural(envio.folhas, 'folha mandada', 'folhas mandadas')} para {impressora} às "
                       f"{datetime.now():%H:%M}.", "ok")
        if self.winfo_exists():
            self.acompanhar_fila(envio.nome_trabalho, impressora)

    # --- fila da impressora ---

    def acompanhar_fila(self, nome_trabalho: str, impressora: str) -> None:
        """Depois de mandar, acompanha o trabalho na fila (em segundo plano) e mostra o estado abaixo do aviso
        de "mandadas": imprimindo, aguardando a vez, pausado, sem papel... (pedido do usuário, out/2026)."""
        self.acompanhamento += 1
        numero = self.acompanhamento

        def tarefa(progresso):
            # o estado vai pela fila de andamento no lugar do texto (ver segundo_plano.py)
            return processamento.acompanhar(nome_trabalho, lambda: processamento.listar_trabalhos(impressora),
                                        ao_mudar=lambda estado: progresso(estado, None),
                                        parar=lambda: numero != self.acompanhamento)

        self.tarefa_fila = TarefaEmSegundoPlano(
            self, tarefa, ao_progresso=lambda estado, _fracao: self._mostrar_fila(estado, numero),
            ao_concluir=lambda estado: self._mostrar_fila(estado, numero),
            ao_falhar=lambda erro, detalhe: self._mostrar_fila(
                EstadoNaFila(f"Não foi possível acompanhar a fila da impressora ({erro}).", "atencao", True),
                numero)).iniciar()

    def _mostrar_fila(self, estado: EstadoNaFila, numero: int) -> None:
        if numero != self.acompanhamento or not self.winfo_exists():
            return                           # outra impressão começou, ou a lista foi limpa
        if self.linha_fila is not None:
            self.linha_fila.destroy()
        texto = estado.texto if estado.final else f"{estado.texto} (acompanhando a fila...)"
        self.linha_fila = LinhaConferencia(self.area_status, texto, estado.nivel)
        self.linha_fila.pack(fill="x", pady=(6, 0))
        self._ajustar_quebra_direita()

    def ver_fila(self) -> None:
        if not self.impressora:
            return
        try:
            processamento.abrir_fila(self.impressora)
        except ErroDeImpressao as erro:
            messagebox.showerror(self.info.nome, str(erro), parent=self)

    def _falhar(self, erro: BaseException, detalhe: str) -> None:
        log_uso.registrar(self.info.nome, ACAO_LOG, log_uso.RESULTADO_ERRO)
        texto = str(erro) if isinstance(erro, ErroDeImpressao) else f"Erro inesperado ao imprimir: {erro}"
        self._terminar(f"{texto} Confira na impressora se alguma folha chegou a sair.", "erro")

    def _terminar(self, texto: str, status: str) -> None:
        self.ocupado = False
        if not self.winfo_exists():
            return
        self._limpar_status()
        LinhaConferencia(self.area_status, texto, status).pack(fill="x", pady=(tema.ESPACO_PEQUENO, 0))
        self._ajustar_quebra_direita()
        self._atualizar()

    def novo(self) -> None:
        """Limpa a lista; a pasta e a impressora ficam (são preferências)."""
        if self.ocupado:
            return
        self._mostrar_lista([], TEXTO_SEM_PDFS)
