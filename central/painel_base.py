"""Base comum dos painéis dos módulos (layout padrão do GUIA_VISUAL, seção 5).

Cada módulo herda PainelPadrao e só diz quais arquivos pede, o que conferir ao escolher cada um e
o que fazer ao processar. A base cuida do que é igual em todos:
- cabeçalho (contexto, título, frase) e as duas colunas;
- cartão "Arquivos de entrada" com o botão principal, que só fica habilitado quando tudo foi
  escolhido e nada está em andamento;
- pasta de saída com a sugestão automática (a pasta do arquivo principal, até o usuário trocar);
- processamento em segundo plano com a barra de andamento;
- mensagens de erro em linguagem simples; perguntas antes de substituir arquivos;
- botões "Abrir ..." e "Novo".
Sem regra de negócio: isso fica no processamento.py de cada módulo.
"""

from __future__ import annotations

import os
from pathlib import Path
from tkinter import messagebox
from typing import Any, Callable

import customtkinter as ctk

from central import log_uso, tema
from central.componentes import (
    BotaoPrincipal,
    BotaoSecundario,
    CabecalhoModulo,
    Cartao,
    CartaoArquivo,
    CartaoResultado,
    LayoutDuasColunas,
)
from central.modulo_base import InfoModulo
from central.segundo_plano import TarefaEmSegundoPlano


# ---------------------------------------------------------------------------
# Funções de apoio (testáveis sem janela)
# ---------------------------------------------------------------------------


def pasta_saida_sugerida(atual: str, ultima_automatica: str, pasta_do_arquivo: str) -> str:
    """Pasta de saída depois de escolher o arquivo principal (regra da Conciliação Bancária original).

    Se o campo está vazio ou ainda tem a pasta preenchida automaticamente, passa a ser a pasta do
    arquivo. Se o usuário trocou a pasta (valor diferente do automático), a escolha dele é mantida.
    """
    if not atual.strip() or atual == ultima_automatica:
        return pasta_do_arquivo
    return atual


def mensagem_amigavel(erro: BaseException) -> str:
    """Mensagem para o usuário a partir de um erro do processamento."""
    if isinstance(erro, PermissionError):
        nome = Path(erro.filename).name if getattr(erro, "filename", None) else "o arquivo"
        return (f"Não foi possível gravar {nome}. Ele provavelmente está aberto no Excel: "
                "feche e tente de novo.")
    if isinstance(erro, FileNotFoundError):
        nome = Path(erro.filename).name if getattr(erro, "filename", None) else "um arquivo"
        return f"Não foi possível encontrar {nome}. Confira se ele não foi movido ou apagado."
    texto = str(erro).strip()
    if isinstance(erro, ValueError) or type(erro).__name__.startswith("Erro"):
        # erros de validação dos módulos já vêm com a mensagem pronta para o usuário
        return texto[:1].upper() + texto[1:] if texto else "Não foi possível concluir o processamento."
    return f"Erro inesperado: {texto or type(erro).__name__}"


def abrir_no_windows(caminho) -> str | None:
    """Abre o arquivo ou a pasta no programa padrão do Windows. Devolve a mensagem de erro, se houver."""
    caminho = Path(caminho) if caminho else None
    if caminho is None or not caminho.exists():
        return f"Não encontrei {caminho.name if caminho else 'o arquivo'}. Ele pode ter sido movido ou apagado."
    try:
        os.startfile(caminho)  # noqa: S606 - abre no Excel / Explorador, como os programas originais
    except OSError as erro:
        return f"Não foi possível abrir {caminho.name}: {erro}"
    return None


def formatar_reais(valor) -> str:
    """1234567.8 -> "1.234.567,80" (só para exibir)."""
    texto = f"{valor:,.2f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


def formatar_inteiro(valor: int) -> str:
    """6664 -> "6.664"."""
    return f"{valor:,}".replace(",", ".")


# ---------------------------------------------------------------------------
# Painel padrão
# ---------------------------------------------------------------------------


class PainelPadrao(ctk.CTkFrame):
    TEXTO_BOTAO = "Processar"
    ICONE_BOTAO = "seta_direita"

    def __init__(self, pai, info: InfoModulo, com_cabecalho: bool = True):
        """com_cabecalho=False: painel dentro de uma aba, abaixo do cabeçalho do módulo."""
        super().__init__(pai, fg_color="transparent")
        self.info = info
        self.ocupado = False
        self.tarefa: TarefaEmSegundoPlano | None = None
        self.cartoes: list[CartaoArquivo] = []
        self.cartao_saida: CartaoArquivo | None = None
        self._saida_automatica = ""

        self.cabecalho: CabecalhoModulo | None = None
        if com_cabecalho:
            self.cabecalho = CabecalhoModulo(self, info.contexto, info.nome, info.descricao)
            self.cabecalho.pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))
        self.layout = LayoutDuasColunas(self)
        self.layout.pack(fill="both", expand=True)

        self.cartao_entrada = Cartao(self.layout.esquerda, "Arquivos de entrada")
        self.cartao_entrada.pack(fill="both", expand=True)
        self.area_arquivos = ctk.CTkFrame(self.cartao_entrada.corpo, fg_color="transparent")
        self.area_arquivos.pack(fill="x")
        self.area_botoes = ctk.CTkFrame(self.cartao_entrada.corpo, fg_color="transparent")
        self.area_botoes.pack(fill="x", pady=(tema.ESPACO_PEQUENO, 0))
        self.botao = BotaoPrincipal(self.area_botoes, self.TEXTO_BOTAO, self.processar, icone=self.ICONE_BOTAO)
        self.botao.pack(fill="x")

        self.resultado = CartaoResultado(self.layout.direita)
        self.resultado.pack(fill="both", expand=True)
        self.mostrar_inicio()
        self.atualizar_botoes()

    # --- montagem (usada pelos módulos) ---

    def adicionar_arquivo(self, rotulo: str, tipo: str = "arquivo", ao_mudar: Callable[[list[Path]], None] | None = None,
                          **opcoes) -> CartaoArquivo:
        """Cartão de entrada. ao_mudar(caminhos) é chamado quando o usuário escolhe."""

        def mudou(caminhos):
            if ao_mudar:
                ao_mudar(caminhos)
            self.atualizar_botoes()

        cartao = CartaoArquivo(self.area_arquivos, rotulo, tipo=tipo, ao_mudar=mudou, **opcoes)
        cartao.pack(fill="x", pady=(0, tema.ESPACO_PEQUENO))
        self.cartoes.append(cartao)
        return cartao

    def adicionar_pasta_saida(self, rotulo: str = "Pasta de saída") -> CartaoArquivo:
        self.cartao_saida = self.adicionar_arquivo(rotulo, tipo="pasta", ao_mudar=self._saida_escolhida,
                                                   titulo_dialogo="Escolha onde gravar os arquivos gerados")
        return self.cartao_saida

    def sugerir_pasta_saida(self, pasta: Path) -> None:
        """Preenche a pasta de saída com `pasta`, a não ser que o usuário já tenha escolhido outra."""
        if self.cartao_saida is None:
            return
        atual = str(self.cartao_saida.caminho) if self.cartao_saida.caminho else ""
        nova = pasta_saida_sugerida(atual, self._saida_automatica, str(pasta))
        if nova == str(pasta):
            self._saida_automatica = nova
            self.cartao_saida.definir_caminhos([nova], avisar=False)
            self.cartao_saida.definir_confirmacao("Sugerida: a pasta do arquivo escolhido", None)
        self.atualizar_botoes()

    def _saida_escolhida(self, caminhos) -> None:
        if caminhos:
            self.cartao_saida.definir_confirmacao("Os arquivos gerados serão gravados aqui", None)

    @property
    def pasta_saida(self) -> Path | None:
        return self.cartao_saida.caminho if self.cartao_saida else None

    # --- estado dos botões ---

    def pronto_para_processar(self) -> bool:
        """Padrão: todos os cartões preenchidos. Os módulos podem trocar a regra."""
        return all(c.preenchido for c in self.cartoes)

    def atualizar_botoes(self) -> None:
        self.botao.habilitar(not self.ocupado and self.pronto_para_processar())

    # --- processamento ---

    def processar(self) -> None:
        """Chamado pelo botão principal. Cada módulo implementa."""
        raise NotImplementedError

    def executar(self, tarefa: Callable[[Callable], Any], ao_concluir: Callable[[Any], None],
                 texto_inicial: str = "Preparando...", registrar_uso: bool = True,
                 acao: str | None = None) -> None:
        """Roda `tarefa(progresso)` em segundo plano mostrando a barra; depois chama ao_concluir(resultado).

        registrar_uso: grava no log de uso (central/log_uso.py) o módulo, o botão e se deu certo; False nas
        leituras preparatórias (ex.: conferir os meses antes de processar), que não são um uso. acao: o nome do
        uso no log quando não é o botão principal (ex.: a etapa do Estoque)."""
        self.ocupado = True
        self.atualizar_botoes()
        barra = self.resultado.mostrar_andamento(texto_inicial)
        acao = acao or self.botao.cget("text")

        def registrar(resultado: str) -> None:
            if registrar_uso:
                log_uso.registrar(self.info.nome, acao, resultado)

        def concluiu(resultado):
            self.ocupado = False
            self.atualizar_botoes()
            # o resultado de cada módulo é diferente; um campo "erro" preenchido quer dizer que não deu certo
            registrar(log_uso.RESULTADO_ERRO if getattr(resultado, "erro", "") else log_uso.RESULTADO_OK)
            ao_concluir(resultado)

        def falhou(erro, detalhe):
            self.ocupado = False
            self.atualizar_botoes()
            registrar(log_uso.RESULTADO_ERRO)
            self.mostrar_erro(mensagem_amigavel(erro), detalhe)

        self.tarefa = TarefaEmSegundoPlano(self, tarefa, ao_progresso=barra.atualizar, ao_concluir=concluiu,
                                           ao_falhar=falhou).iniciar()

    def ler_em_segundo_plano(self, leitura: Callable[[], Any], ao_concluir: Callable[[Any], None]) -> None:
        """Leitura rápida sem barra (ex.: o mês de um arquivo); falha vira None."""

        def tarefa(_progresso):
            try:
                return leitura()
            except Exception:
                return None

        TarefaEmSegundoPlano(self, tarefa, ao_concluir=ao_concluir).iniciar()

    # --- área de resultado ---

    def mostrar_inicio(self) -> None:
        self.resultado.mostrar_vazio("Nenhum resultado ainda",
                                     "Selecione os arquivos de entrada e clique no botão para processar.")

    def mostrar_erro(self, mensagem: str, detalhe: str = "") -> None:
        self.resultado.mostrar_vazio("Não foi possível concluir", mensagem, icone="erro", tom="erro")
        self.resultado.definir_selo("Erro", "erro")
        if detalhe and mensagem.startswith("Erro inesperado"):
            # erro que ninguém previu: os detalhes ajudam quem for consertar (o .exe não tem console)
            ctk.CTkLabel(self.resultado.area, text="Detalhes técnicos (para quem for consertar):",
                         font=tema.fonte_legenda(), text_color=tema.COR_TEXTO_SUAVE, anchor="w").pack(fill="x")
            caixa = ctk.CTkTextbox(self.resultado.area, height=140, font=tema.fonte_numero(), fg_color=tema.COR_FUNDO,
                                   text_color=tema.COR_TEXTO, border_width=tema.LARGURA_BORDA,
                                   border_color=tema.COR_BORDA, corner_radius=tema.RAIO_PEQUENO)
            caixa.pack(fill="x", pady=(4, 0))
            caixa.insert("1.0", detalhe)
            caixa.configure(state="disabled")

    def definir_botoes_resultado(self, botoes: list[tuple]) -> dict[str, ctk.CTkButton]:
        """botoes = [(texto, comando, icone), ...]; o primeiro é o principal. Devolve {texto: botão}.

        Numa linha só quando cabem; senão (janela mínima) o principal fica em cima, na largura toda, e os
        outros lado a lado embaixo, como o rodapé das planilhas (botoes_da_planilha)."""
        rodape = self.resultado.rodape
        for filho in rodape.winfo_children():
            filho.destroy()
        criados = {}
        for indice, (texto, comando, icone) in enumerate(botoes):
            if indice == 0:
                botao = BotaoPrincipal(rodape, texto, comando, icone=icone)
            else:
                botao = BotaoSecundario(rodape, texto, comando, icone=icone, largura=tema.LARGURA_BOTAO_RODAPE)
            criados[texto] = botao
        self._botoes_rodape = list(criados.values())
        self.rodape_em_duas_linhas: bool | None = None
        if not getattr(self, "_rodape_vigiado", False):
            rodape.bind("<Configure>", self._arrumar_rodape, add="+")
            self._rodape_vigiado = True
        self._arrumar_rodape()
        return criados

    def _arrumar_rodape(self, evento=None) -> None:
        botoes = [b for b in getattr(self, "_botoes_rodape", []) if b.winfo_exists()]
        if not botoes:
            return
        rodape = self.resultado.rodape
        escala = ctk.ScalingTracker.get_widget_scaling(self)
        largura = int((evento.width if evento is not None else rodape.winfo_width()) / escala)
        secundarios = botoes[1:]
        precisa = (tema.LARGURA_MINIMA_PRINCIPAL_RODAPE
                   + len(secundarios) * (tema.LARGURA_BOTAO_RODAPE + tema.ESPACO_PEQUENO))
        duas_linhas = bool(secundarios) and 1 < largura < precisa
        if duas_linhas == self.rodape_em_duas_linhas:
            return
        self.rodape_em_duas_linhas = duas_linhas
        for botao in botoes:
            botao.pack_forget()
            botao.grid_forget()
        if not duas_linhas:
            botoes[0].pack(side="left", fill="x", expand=True)
            for botao in secundarios:
                botao.configure(width=tema.LARGURA_BOTAO_RODAPE)
                botao.pack(side="left", padx=(tema.ESPACO_PEQUENO, 0))
            return
        for coluna in range(len(secundarios)):
            rodape.grid_columnconfigure(coluna, weight=1, uniform="botoes")
        botoes[0].grid(row=0, column=0, columnspan=len(secundarios), sticky="ew")
        for coluna, botao in enumerate(secundarios):
            botao.configure(width=1)
            botao.grid(row=1, column=coluna, sticky="ew", pady=(tema.ESPACO_PEQUENO, 0),
                       padx=(0 if coluna == 0 else tema.ESPACO_PEQUENO, 0))

    def novo(self) -> None:
        """Botão "Novo": limpa as escolhas de entrada e o resultado (a pasta de saída fica)."""
        if self.ocupado:
            return
        for cartao in self.cartoes:
            if cartao is not self.cartao_saida:
                cartao.limpar()
        self.ao_novo()
        self.mostrar_inicio()
        self.atualizar_botoes()

    def ao_novo(self) -> None:
        """Para o módulo limpar o que guardou (ex.: mês lido)."""

    # --- diálogos ---

    def perguntar(self, texto: str) -> bool:
        return messagebox.askyesno(self.info.nome, texto, icon="warning", parent=self)

    def avisar(self, texto: str) -> None:
        messagebox.showwarning(self.info.nome, texto, parent=self)

    def informar(self, texto: str) -> None:
        messagebox.showinfo(self.info.nome, texto, parent=self)

    def confirmar_substituicao(self, caminhos: list[Path]) -> bool:
        """Confere os arquivos que serão gravados. True = pode gravar.

        - um arquivo de entrada nunca é substituído: se algum destino for uma das entradas
          escolhidas, avisa e não segue;
        - arquivos que já existem: pergunta antes de substituir.
        """
        entradas = {Path(c).resolve() for cartao in self.cartoes if cartao is not self.cartao_saida
                    for c in cartao.caminhos}
        repetidos = [Path(c) for c in caminhos if Path(c).resolve() in entradas]
        if repetidos:
            nomes = "\n".join(f"  • {c.name}" for c in repetidos)
            self.avisar(f"Estes arquivos seriam gravados por cima dos arquivos de entrada:\n\n{nomes}\n\n"
                        "Os arquivos de entrada nunca são alterados: escolha outra pasta de saída.")
            return False
        existentes = [Path(c) for c in caminhos if Path(c).exists()]
        if not existentes:
            return True
        nomes = "\n".join(f"  • {c.name}" for c in existentes)
        return self.perguntar(f"Estes arquivos já existem na pasta de saída e serão substituídos:\n\n{nomes}\n\n"
                              "Deseja substituir?")

    def abrir(self, caminho) -> None:
        erro = abrir_no_windows(caminho)
        if erro:
            self.avisar(erro)
