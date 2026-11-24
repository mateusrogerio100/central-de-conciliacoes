"""Aba "Geração do SPED" do módulo EFD Contribuições (ESPECIFICACAO_EFD_CONTRIBUICOES.md, seção 7).

Cartões: pasta das DANFSe, SPED do mês anterior, cadastro de clientes (clientes.json, escolhido aqui e lembrado;
lido em segundo plano, porque costuma ficar na rede) e pasta de saída (lembrada); campo da competência (sugerida
pelo SPED anterior). Sem cadastro ainda: o botão "Criar cadastro a partir do SPED anterior".

"Gerar SPED" roda em duas partes (processamento.preparar / gerar): entre elas, a tela oferece incluir as notas que
ficaram fora por causa das datas (ajuste de 05/11/2026), pergunta sobre os PDFs não lidos (R6) e pede o Código IBGE
dos clientes novos que vieram sem ele (R7).
Sem regra de negócio: a tela só chama processamento.py e mostra o que volta.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from central import tema
from central.componentes import (
    BotaoPrincipal,
    BotaoSecundario,
    CampoRotulado,
    Coluna,
    GrupoNumeros,
    JanelaTexto,
    LinhaConferencia,
    TabelaSimples,
    TextoQuebravel,
    aplicar_icone,
)
from central.painel_base import PainelPadrao, formatar_inteiro, formatar_reais
from central.preferencias import ler_preferencias_modulo, salvar_preferencias_modulo
from modulos.efd_contribuicoes import processamento

CHAVE = "efd_contribuicoes"
TIPOS_SPED = [("SPED (.txt)", "*.txt"), ("Todos os arquivos", "*.*")]
TIPOS_JSON = [("Cadastro de clientes (.json)", "*.json"), ("Todos os arquivos", "*.*")]
TEXTO_VAZIO = ("Escolha a pasta com as DANFSe do mês, o SPED do mês anterior e a pasta de saída, confira a "
               "competência e clique em Gerar SPED.")
SITUACOES_NA_TELA = [   # (situação, nome curto na tabela do resultado)
    ("No SPED", "No SPED"), ("Fora: PF", "PF"), ("Fora: competência ≠ emissão", "Competência ≠ emissão"),
    ("Fora: emissão fora do mês", "Emissão fora do mês"), ("Fora: repetida", "Repetida"),
    ("Fora: não lido", "Não lido"), ("No SPED (incluída à mão)", "Incluída à mão"),
]


# As duas janelas seguem o modelo da janela de seção da Planilha HM: textos com largura fixa (wraplength), sem
# peças que se reajustam sozinhas ao tamanho (o TextoQuebravel e o Cartao numa janela solta ficavam trocando de
# tamanho sem parar e a janela "tremia"), ícone na hora, fechar no X = cancelar.
LARGURA_JANELA = 620
ALTURA_LISTA = 300


def _janela_base(janela, titulo: str, pergunta: str, explicacao: str, ao_fechar) -> ctk.CTkFrame:
    janela.title(titulo)
    janela.configure(fg_color=tema.COR_FUNDO)
    janela.resizable(False, False)
    aplicar_icone(janela)
    janela.protocol("WM_DELETE_WINDOW", ao_fechar)
    corpo = ctk.CTkFrame(janela, fg_color="transparent")
    corpo.pack(fill="both", expand=True, padx=tema.ESPACO_INTERNO_CARTAO, pady=tema.ESPACO_INTERNO_CARTAO)
    ctk.CTkLabel(corpo, text=pergunta, font=tema.fonte_subtitulo(), text_color=tema.COR_TEXTO,
                 anchor="w").pack(anchor="w")
    ctk.CTkLabel(corpo, text=explicacao, font=tema.fonte_texto(), text_color=tema.COR_TEXTO_SUAVE, anchor="w",
                 justify="left", wraplength=LARGURA_JANELA).pack(anchor="w", pady=(4, tema.ESPACO_PEQUENO))
    return corpo


def _lista_rolavel(corpo, quantidade: int, altura_item: int) -> ctk.CTkScrollableFrame:
    lista = ctk.CTkScrollableFrame(corpo, width=LARGURA_JANELA, height=min(ALTURA_LISTA, quantidade * altura_item),
                                   fg_color=tema.COR_SUPERFICIE, border_width=tema.LARGURA_BORDA,
                                   border_color=tema.COR_BORDA, corner_radius=tema.RAIO_BOTAO)
    lista.pack(fill="x")
    return lista


def _botoes(corpo, texto_principal: str, ao_confirmar, texto_cancelar: str, ao_cancelar) -> None:
    botoes = ctk.CTkFrame(corpo, fg_color="transparent")
    botoes.pack(fill="x", pady=(tema.ESPACO_PEQUENO, 0))
    BotaoPrincipal(botoes, texto_principal, ao_confirmar, icone="check").pack(side="left", fill="x", expand=True)
    BotaoSecundario(botoes, texto_cancelar, ao_cancelar, largura=170).pack(side="left", padx=(tema.ESPACO_PEQUENO, 0))


def _esperar_resposta(painel, janela) -> None:
    """Janela por cima da Central, só ela recebendo cliques, até ser fechada."""
    janela.transient(painel.winfo_toplevel())
    janela.update_idletasks()
    janela.grab_set()
    janela.focus_set()
    janela.wait_window()


class JanelaCodigosIbge(ctk.CTkToplevel):
    """R7: um campo por cliente novo sem Código IBGE. `respostas` = {cnpj: código} ao confirmar; None ao cancelar."""

    def __init__(self, pai, clientes: list[dict]):
        super().__init__(pai)
        self.respostas: dict[str, str] | None = None
        corpo = _janela_base(self, "Código IBGE dos clientes novos", "Clientes novos sem Código IBGE",
                             "O EFD Contribuições não aceita cliente sem o código do município. Digite o Código IBGE "
                             "de cada um (7 números, ex.: 3516200); ele fica guardado no cadastro.", self.cancelar)
        lista = _lista_rolavel(corpo, len(clientes), 86)
        self.campos: dict[str, CampoRotulado] = {}
        for cliente in clientes:
            campo = CampoRotulado(lista, f"{cliente['nome']} (CNPJ {cliente['cnpj']})", largura=150)
            campo.rotulo.configure(wraplength=LARGURA_JANELA - 40, justify="left")
            campo.pack(anchor="w", pady=(4, tema.ESPACO_PEQUENO), padx=8)
            self.campos[cliente["cnpj"]] = campo
        self.mensagem = ctk.CTkLabel(corpo, text="", font=tema.fonte_legenda(), text_color=tema.COR_ERRO, anchor="w")
        self.mensagem.pack(fill="x", pady=(4, 0))
        _botoes(corpo, "Continuar", self.confirmar, "Cancelar", self.cancelar)

    def confirmar(self) -> None:
        respostas = {cnpj: campo.valor() for cnpj, campo in self.campos.items()}
        invalidos = [c for c, codigo in respostas.items() if not processamento.codigo_ibge_valido(codigo)]
        if invalidos:
            self.mensagem.configure(text="Preencha todos com 7 números (ex.: 3516200).")
            return
        self.respostas = respostas
        self.destroy()

    def cancelar(self) -> None:
        self.respostas = None
        self.destroy()


class JanelaIncluirNotas(ctk.CTkToplevel):
    """Notas fora por causa das datas, cada uma com uma caixinha "incluir" (desmarcadas).
    `escolhidas` = arquivos marcados ao continuar (lista vazia = nenhuma); None = cancelou a geração."""

    def __init__(self, pai, itens):
        super().__init__(pai)
        self.escolhidas: list[str] | None = None
        corpo = _janela_base(self, "Notas fora do SPED pelas datas", "Incluir alguma destas notas no SPED?",
                             "Estas notas ficaram fora porque a competência é diferente da data de emissão ou porque "
                             "foram emitidas fora do mês do SPED. Marque as que devem entrar mesmo assim; as "
                             "desmarcadas continuam fora.", self.cancelar)
        lista = _lista_rolavel(corpo, len(itens), 64)
        self.variaveis: dict[str, ctk.BooleanVar] = {}
        for item in itens:
            nota = item.nota
            variavel = ctk.BooleanVar(value=False)
            linha = ctk.CTkFrame(lista, fg_color="transparent")
            linha.pack(fill="x", pady=4, padx=4)
            ctk.CTkCheckBox(linha, text="", width=24, variable=variavel, fg_color=tema.COR_PRINCIPAL,
                            hover_color=tema.COR_PRINCIPAL_HOVER, border_color=tema.COR_BORDA,
                            checkmark_color=tema.COR_TEXTO_SOBRE_PRINCIPAL, corner_radius=tema.RAIO_PEQUENO // 2,
                            border_width=2).pack(side="left", anchor="n", pady=2)
            textos = ctk.CTkFrame(linha, fg_color="transparent")
            textos.pack(side="left", fill="x", expand=True, padx=(6, 0))
            ctk.CTkLabel(textos, text=f"NFS-e {nota.numero_nfse} · {formatar_reais(nota.valor)} · {nota.tomador}",
                         font=tema.fonte_texto_forte(), text_color=tema.COR_TEXTO, anchor="w", justify="left",
                         wraplength=LARGURA_JANELA - 70).pack(anchor="w")
            ctk.CTkLabel(textos, text=f"{item.situacao.removeprefix('Fora: ')}: {item.observacao}",
                         font=tema.fonte_legenda(), text_color=tema.COR_TEXTO_SUAVE, anchor="w", justify="left",
                         wraplength=LARGURA_JANELA - 70).pack(anchor="w")
            self.variaveis[nota.arquivo] = variavel
        _botoes(corpo, "Continuar", self.confirmar, "Cancelar geração", self.cancelar)

    def confirmar(self) -> None:
        self.escolhidas = [arquivo for arquivo, variavel in self.variaveis.items() if variavel.get()]
        self.destroy()

    def cancelar(self) -> None:
        self.escolhidas = None
        self.destroy()


class PainelGeracaoSped(PainelPadrao):
    TEXTO_BOTAO = "Gerar SPED"

    def __init__(self, pai, info):
        self.cadastro: processamento.Cadastro | None = None
        self.lendo_cadastro = False
        self.resultado_geracao: processamento.ResultadoEFD | None = None
        self.competencia_sugerida = ""
        self.janela_avisos: JanelaTexto | None = None
        super().__init__(pai, info, com_cabecalho=False)

        self.campo_competencia = CampoRotulado(self.cartao_entrada.corpo, "Competência do novo SPED (MM/AAAA)",
                                               largura=150, ao_mudar=lambda _: self.atualizar_botoes())
        self.campo_competencia.pack(anchor="w", pady=(0, tema.ESPACO_PEQUENO), before=self.area_arquivos)

        self.cartao_pdfs = self.adicionar_arquivo(
            "Pasta com as DANFSe (PDF) do mês", tipo="pasta", ao_mudar=self._pdfs_escolhidos,
            titulo_dialogo="Escolha a pasta com as DANFSe do mês")
        self.cartao_sped = self.adicionar_arquivo(
            "SPED do mês anterior (.txt)", tipos_arquivo=TIPOS_SPED, ao_mudar=self._sped_escolhido,
            titulo_dialogo="Escolha o SPED EFD-Contribuições do mês anterior")
        self.cartao_cadastro = self.adicionar_arquivo(
            "Cadastro de clientes (clientes.json)", tipos_arquivo=TIPOS_JSON, ao_mudar=self._cadastro_escolhido,
            titulo_dialogo="Escolha o cadastro de clientes (clientes.json)")
        self.botao_criar_cadastro = BotaoSecundario(
            self.area_arquivos, "Não tenho o cadastro: criar a partir do SPED anterior", self.criar_cadastro_do_sped,
            altura=tema.ALTURA_BOTAO_PEQUENO)
        self.botao_criar_cadastro.pack(anchor="w", pady=(0, tema.ESPACO_PEQUENO), after=self.cartao_cadastro)
        self.adicionar_pasta_saida("Pasta para salvar o SPED e o Excel")

        preferencias = ler_preferencias_modulo(CHAVE)
        pasta = preferencias.get("pasta_saida", "")
        if isinstance(pasta, str) and pasta and Path(pasta).is_dir():
            self.cartao_saida.definir_caminhos([pasta], avisar=False)
            self.cartao_saida.definir_confirmacao(f"Última pasta usada: {pasta}", "ok")
        arquivo = preferencias.get("cadastro", "")
        if isinstance(arquivo, str) and arquivo:
            # não confere se existe aqui: o arquivo costuma ficar na rede, e a tela nunca espera a rede
            self.cartao_cadastro.definir_caminhos([arquivo], avisar=False)
            self.cartao_cadastro.pasta_inicial = Path(arquivo).parent
            self.ler_cadastro()
        self.atualizar_botoes()

    # --- cadastro de clientes ---

    def _cadastro_escolhido(self, caminhos: list[Path]) -> None:
        self.cadastro = None
        if not caminhos:
            return
        dados = ler_preferencias_modulo(CHAVE)
        dados["cadastro"] = str(caminhos[0])
        salvar_preferencias_modulo(CHAVE, dados)
        self.ler_cadastro()

    def ler_cadastro(self) -> None:
        """Lê o clientes.json do cartão em segundo plano (pode estar na rede)."""
        caminho = self.cartao_cadastro.caminho
        if caminho is None:
            return
        self.cadastro = None
        self.lendo_cadastro = True
        self.cartao_cadastro.definir_confirmacao("Lendo o cadastro de clientes...", None)

        def leitura():
            try:
                return processamento.carregar_cadastro(caminho), ""
            except processamento.ErroCadastro as erro:
                return None, str(erro)

        def lido(resposta):
            self.lendo_cadastro = False
            if not self.winfo_exists() or self.cartao_cadastro.caminho != caminho:
                return
            cadastro, erro = resposta if resposta else (None, "Erro inesperado ao ler o cadastro.")
            self.cadastro = cadastro
            if erro:
                self.cartao_cadastro.definir_confirmacao(erro, "erro")
            else:
                self._mostrar_cadastro_lido()
            self.atualizar_botoes()

        self.ler_em_segundo_plano(leitura, lido)

    def _mostrar_cadastro_lido(self) -> None:
        novo = "" if self.cadastro.existe else " (cadastro novo: o arquivo é criado ao gerar)"
        self.cartao_cadastro.definir_confirmacao(
            f"{formatar_inteiro(len(self.cadastro.clientes))} clientes{novo}", "ok")

    def criar_cadastro_do_sped(self, destino: Path | None = None) -> None:
        if not self.cartao_sped.preenchido or self.cartao_sped.status_confirmacao == "erro":
            self.avisar("Escolha primeiro o SPED do mês anterior: o cadastro é criado com os clientes (0150) dele.")
            return
        destino = destino or filedialog.asksaveasfilename(
            parent=self, title="Onde guardar o cadastro de clientes novo", initialfile=processamento.cfg.NOME_CADASTRO,
            defaultextension=".json", filetypes=TIPOS_JSON)
        if not destino:
            return
        try:
            cadastro = processamento.novo_cadastro(Path(destino), processamento.ler_molde(self.cartao_sped.caminho))
        except (processamento.ErroCadastro, processamento.ErroSped) as erro:
            self.avisar(str(erro))
            return
        self.cartao_cadastro.definir_caminhos([destino], avisar=False)
        dados = ler_preferencias_modulo(CHAVE)
        dados["cadastro"] = str(destino)
        salvar_preferencias_modulo(CHAVE, dados)
        self.cadastro = cadastro
        self._mostrar_cadastro_lido()
        self.atualizar_botoes()

    def novo(self) -> None:
        """"Novo" limpa as entradas do mês; o cadastro (como a pasta de saída) fica escolhido."""
        if self.ocupado:
            return
        caminho, cadastro = self.cartao_cadastro.caminho, self.cadastro
        super().novo()
        if caminho is not None:
            self.cartao_cadastro.definir_caminhos([caminho], avisar=False)
            self.cadastro = cadastro
            if cadastro is not None:
                self._mostrar_cadastro_lido()
            self.atualizar_botoes()

    # --- escolhas ---

    def _pdfs_escolhidos(self, caminhos: list[Path]) -> None:
        if not caminhos:
            return
        quantos = len(list(Path(caminhos[0]).glob("*.pdf")))
        if quantos:
            self.cartao_pdfs.definir_confirmacao(f"{formatar_inteiro(quantos)} PDF(s) na pasta", "ok")
        else:
            self.cartao_pdfs.definir_confirmacao("Nenhum PDF nesta pasta", "erro")

    def _sped_escolhido(self, caminhos: list[Path]) -> None:
        if not caminhos:
            return
        previa = processamento.previa_sped(caminhos[0])
        if previa.erro:
            self.cartao_sped.definir_confirmacao(previa.erro, "erro")
            return
        self.cartao_sped.definir_confirmacao(previa.descricao, "ok")
        atual = self.campo_competencia.valor()
        if not atual or atual == self.competencia_sugerida:
            self.competencia_sugerida = previa.competencia_seguinte
            self.campo_competencia.definir(previa.competencia_seguinte)

    def _saida_escolhida(self, caminhos) -> None:
        super()._saida_escolhida(caminhos)
        if caminhos:
            dados = ler_preferencias_modulo(CHAVE)
            dados["pasta_saida"] = str(caminhos[0])
            salvar_preferencias_modulo(CHAVE, dados)

    def pronto_para_processar(self) -> bool:
        if not hasattr(self, "campo_competencia") or not hasattr(self, "cartao_sped"):
            return False
        cartoes_ok = all(c.preenchido and c.status_confirmacao != "erro" for c in self.cartoes)
        if not hasattr(self, "cartao_cadastro"):
            return False
        cadastro_ok = self.cadastro is not None and (self.cadastro.existe or bool(self.cadastro.clientes))
        return cartoes_ok and cadastro_ok and processamento.competencia_valida(self.campo_competencia.valor())

    # --- geração em duas partes ---

    def processar(self) -> None:
        if self.ocupado or not self.pronto_para_processar():
            return
        pdfs, sped, competencia = self.cartao_pdfs.caminho, self.cartao_sped.caminho, self.campo_competencia.valor()
        cadastro = self.cadastro
        self.executar(lambda progresso: processamento.preparar(pdfs, sped, competencia, cadastro, progresso),
                      self._preparado, texto_inicial="Lendo as notas...", registrar_uso=False)

    def _preparado(self, preparacao: processamento.Preparacao) -> None:
        if preparacao.bloqueios:
            self.mostrar_erro(" ".join(preparacao.bloqueios))
            return
        # enquanto as janelas esperam a resposta, o resultado diz isso (e não fica a barra parada em 100%)
        self.resultado.mostrar_vazio("Aguardando a sua resposta", "Responda na janela que abriu para continuar.",
                                     icone="alerta", tom="atencao")
        if preparacao.incluiveis:
            escolhidas = self.escolher_notas_para_incluir(preparacao.incluiveis)
            if escolhidas is None:
                self.mostrar_erro("Geração cancelada. Nada foi gravado.")
                return
            processamento.incluir_notas(preparacao, escolhidas)
        aceitar = True
        if preparacao.nao_lidas:
            nomes = "\n".join(f"  • {i.nota.arquivo} — {i.observacao}" for i in preparacao.nao_lidas)
            aceitar = self.perguntar(f"{len(preparacao.nao_lidas)} PDF(s) não puderam ser lidos:\n\n{nomes}\n\n"
                                     "Gerar o SPED sem eles?")
            if not aceitar:
                self.mostrar_erro("Geração cancelada: há PDF(s) que não puderam ser lidos. Nada foi gravado.")
                return
        sem_ibge = preparacao.novos_sem_ibge()
        if sem_ibge:
            respostas = self.pedir_codigos_ibge(sem_ibge)
            if not respostas:
                self.mostrar_erro("Geração cancelada: faltou o Código IBGE de cliente(s) novo(s). Nada foi gravado.")
                return
            for cnpj, codigo in respostas.items():
                preparacao.cadastro.definir_ibge(cnpj, codigo)
        saida = self.pasta_saida
        self.executar(lambda progresso: processamento.gerar(preparacao, saida, aceitar, progresso),
                      self.mostrar_resultado, texto_inicial="Gerando o SPED...")

    def escolher_notas_para_incluir(self, itens) -> list[str] | None:
        """Abre a janela e espera a resposta (os testes trocam este método)."""
        janela = JanelaIncluirNotas(self.winfo_toplevel(), itens)
        _esperar_resposta(self, janela)
        return janela.escolhidas

    def pedir_codigos_ibge(self, clientes: list[dict]) -> dict[str, str] | None:
        """Abre a janela e espera a resposta (os testes trocam este método)."""
        janela = JanelaCodigosIbge(self.winfo_toplevel(), clientes)
        _esperar_resposta(self, janela)
        return janela.respostas

    # --- resultado ---

    def mostrar_resultado(self, resultado: processamento.ResultadoEFD) -> None:
        self.resultado_geracao = resultado
        # a geração pode ter mudado o cadastro da rede (cliente novo, primeiro uso) ou achado outra pessoa
        # gravando: lê de novo, para a próxima geração usar a lista atual
        self.ler_cadastro()
        if resultado.erro and resultado.caminho_sped is None:
            self.mostrar_erro(resultado.erro)
            return
        cartao = self.resultado
        area = cartao.mostrar_conteudo()
        cartao.definir_selo("Concluído" if not resultado.erro else "Atenção", "ok" if not resultado.erro else "atencao")
        if resultado.erro:
            LinhaConferencia(area, resultado.erro, "erro").pack(fill="x", pady=(0, tema.ESPACO_PEQUENO))

        selecao = resultado.selecao
        no_sped = len(selecao.no_sped)
        fora = len(selecao.notas) - no_sped
        TextoQuebravel(area, f"SPED de {resultado.competencia} · receita {formatar_reais(resultado.total_receita)}",
                       tema.fonte_texto_forte()).pack(fill="x", pady=(0, tema.ESPACO_PEQUENO))
        GrupoNumeros(area, [
            (formatar_inteiro(no_sped), "Notas no SPED", "ok"),
            (formatar_inteiro(fora), "Fora do SPED", "atencao" if fora else "ok"),
            (formatar_inteiro(len(resultado.clientes_novos)), "Clientes novos", "principal"),
        ]).pack(fill="x")
        linhas = [(curto, formatar_inteiro(selecao.contar(situacao)))
                  for situacao, curto in SITUACOES_NA_TELA if selecao.contar(situacao)]
        TabelaSimples(area, [Coluna("Situação", peso=3), Coluna("PDFs", numero=True)], linhas).pack(
            fill="x", pady=(tema.ESPACO_ENTRE_BLOCOS, 0))
        for cliente, origem in resultado.clientes_novos:
            LinhaConferencia(area, f"Cliente novo {cliente['cod_part']}: {cliente['nome']} (IBGE "
                                   f"{cliente['codigo_ibge']}{', digitado' if origem == 'digitado' else ''})",
                             "atencao").pack(fill="x", pady=(4, 0))
        prestador = len(resultado.preparacao.avisos_prestador)
        if prestador:
            LinhaConferencia(area, f"{prestador} PDF(s) com prestador de CNPJ diferente dos outros — veja os avisos",
                             "atencao").pack(fill="x", pady=(6, 0))
        avisos = len(resultado.avisos)
        LinhaConferencia(area, f"{avisos} aviso(s) — veja os avisos" if avisos else "Nenhum aviso",
                         "atencao" if avisos else "ok").pack(fill="x", pady=(6, 0))
        if resultado.caminho_sped is not None:
            ctk.CTkLabel(area, text=f"Salvo como {resultado.caminho_sped.name} e {resultado.caminho_excel.name}"
                         if resultado.caminho_excel else f"Salvo como {resultado.caminho_sped.name}",
                         font=tema.fonte_legenda(), text_color=tema.COR_TEXTO_SUAVE, anchor="w", justify="left",
                         wraplength=380).pack(fill="x", pady=(tema.ESPACO_PEQUENO, 0))
        botoes = self.definir_botoes_resultado([
            ("Abrir pasta", self.abrir_pasta, "pasta"),
            ("Abrir Excel", self.abrir_excel, "tabela"),
            ("Ver avisos", self.ver_avisos, "alerta"),
            ("Novo", self.novo, "atualizar"),
        ])
        botoes["Abrir Excel"].habilitar(resultado.caminho_excel is not None)

    def abrir_pasta(self) -> None:
        caminho = self.resultado_geracao.caminho_sped if self.resultado_geracao else None
        if caminho is None:
            return
        try:
            if caminho.exists():
                subprocess.Popen(f'explorer /select,"{caminho}"')
            else:
                os.startfile(caminho.parent)  # noqa: S606
        except OSError as erro:
            messagebox.showerror(self.info.nome, f"Não foi possível abrir a pasta: {erro}", parent=self)

    def abrir_excel(self) -> None:
        if self.resultado_geracao and self.resultado_geracao.caminho_excel:
            self.abrir(self.resultado_geracao.caminho_excel)

    def ver_avisos(self) -> None:
        if self.resultado_geracao is None:
            return
        if self.janela_avisos is not None and self.janela_avisos.winfo_exists():
            self.janela_avisos.destroy()
        linhas = [f"• {a}" for a in self.resultado_geracao.avisos] or ["Nenhum aviso."]
        self.janela_avisos = JanelaTexto(self.winfo_toplevel(), "Avisos da geração do SPED", "Avisos", linhas)

    def ao_novo(self) -> None:
        self.resultado_geracao = None
        self.competencia_sugerida = ""
        self.campo_competencia.definir("")

    def mostrar_inicio(self) -> None:
        self.resultado.mostrar_vazio("Nenhum resultado ainda", TEXTO_VAZIO)
