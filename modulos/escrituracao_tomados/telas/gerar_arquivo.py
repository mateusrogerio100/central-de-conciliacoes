"""Aba "Gerar arquivo" do módulo Serviços Tomados (seção 8 da especificação do módulo).

Sem regra de negócio: escolhe as entradas, o tipo da declaração, a data e a pasta, e mostra o
resultado. Tudo o que decide está em processamento.py.

O processamento roda em segundo plano e às vezes precisa perguntar algo (a cidade de um
prestador, R11.4; se pode substituir arquivos, R17). A classe PerguntasDaTarefa leva a pergunta
para a janela e devolve a resposta.
"""

from __future__ import annotations

import queue
import threading
from datetime import date

import customtkinter as ctk

from central import tema
from central.componentes import (
    BotaoSecundario, CampoComLista, CampoRotulado, Coluna, GrupoNumeros, LinhaConferencia, SeletorOpcoes,
    TabelaSimples,
)
from central.painel_base import PainelPadrao, formatar_inteiro, formatar_reais
from modulos.escrituracao_tomados import processamento
from modulos.escrituracao_tomados.telas import outros_cnpjs, pergunta_cidade

TIPOS_EXPORTACAO = [("Exportações do site", "*.txt *.csv"), ("Todos os arquivos", "*.*")]
TIPOS_REFERENCIA = {"Normal": "N", "Complementar": "C"}
# R9: só aparece quando há exportações (unificar) e resultados ao mesmo tempo
AVISO_RESULTADOS = "não inclua a exportação dos lotes que serão substituídos"
SUBPASTA_SAIDA = "saida"


def legenda_nao_incluidas(resultado) -> str:
    """"não incluídas" + de onde vêm (só as partes que existem), ex.:
    "não incluídas: 8 já escrituradas · 1 duplicada · 5 por outro motivo"."""
    partes = []
    somadas = 0
    for quantidade, singular, plural in (
            (resultado.ja_escrituradas, "já escriturada", "já escrituradas"),
            (resultado.canceladas, "cancelada", "canceladas"),
            (resultado.duplicadas, "duplicada", "duplicadas"),
            (resultado.erros_de_leitura, "com erro de leitura", "com erro de leitura")):
        if quantidade:
            partes.append(f"{quantidade} {singular if quantidade == 1 else plural}")
            somadas += quantidade
    outras = resultado.nao_incluidas - somadas
    if outras:
        partes.append(f"{outras} por outro motivo")
    return "não incluídas" + (": " + " · ".join(partes) if partes else "")


class PerguntasDaTarefa:
    """Leva perguntas da thread de trabalho para a thread da janela e devolve a resposta."""

    INTERVALO_MS = 50

    def __init__(self, widget):
        self.widget = widget
        self._fila: queue.Queue = queue.Queue()
        self._ativo = False

    def iniciar(self) -> None:
        if not self._ativo:
            self._ativo = True
            self._atender()

    def parar(self) -> None:
        self._ativo = False

    def perguntar(self, funcao, *argumentos):
        """Chamada na thread de trabalho: espera a janela responder."""
        pronto, caixa = threading.Event(), {}
        self._fila.put((funcao, argumentos, pronto, caixa))
        pronto.wait()
        if "erro" in caixa:
            raise caixa["erro"]
        return caixa.get("resposta")

    def _atender(self) -> None:
        while True:
            try:
                funcao, argumentos, pronto, caixa = self._fila.get_nowait()
            except queue.Empty:
                break
            try:
                caixa["resposta"] = funcao(*argumentos)
            except Exception as erro:
                caixa["erro"] = erro
            finally:
                pronto.set()
        if self._ativo:
            try:
                self.widget.after(self.INTERVALO_MS, self._atender)
            except Exception:          # a janela foi fechada
                self._ativo = False


class PainelGerarArquivo(PainelPadrao):
    TEXTO_BOTAO = "Gerar arquivo"

    def __init__(self, pai, info):
        self.ultimo_resultado = None
        super().__init__(pai, info, com_cabecalho=False)
        self.perguntas = PerguntasDaTarefa(self)

        self.cartao_pdfs = self.adicionar_arquivo(
            "PDFs das notas (DANFSe)", tipo="pasta", ao_mudar=self._pdfs_escolhidos,
            titulo_dialogo="Escolha a pasta com os PDFs das notas")

        self.cartao_exportacoes = self.adicionar_arquivo(
            "Exportações de lotes (unificar)", tipo="arquivos",
            ao_mudar=self._exportacoes_escolhidas, tipos_arquivo=TIPOS_EXPORTACAO,
            titulo_dialogo="Escolha as exportações dos lotes")
        self.area_exportacao = ctk.CTkFrame(self.area_arquivos, fg_color="transparent")
        self.campo_tomador = CampoComLista(self.area_exportacao, "CNPJ do tomador",
                                           processamento.tomadores_usados(), largura=220,
                                           ao_mudar=lambda _: self.atualizar_botoes())
        self.campo_tomador.pack(side="left")
        self.campo_competencia = CampoRotulado(self.area_exportacao, "Competência (MM/AAAA)", largura=150,
                                               ao_mudar=lambda _: self.atualizar_botoes())
        self.campo_competencia.pack(side="left", padx=(tema.ESPACO_PEQUENO, 0))

        self.cartao_resultados = self.adicionar_arquivo(
            "Já escrituradas (opcional)", tipo="arquivos",
            ao_mudar=self._resultados_escolhidos, tipos_arquivo=TIPOS_EXPORTACAO,
            titulo_dialogo="Escolha os resultados exportados do site (notas já escrituradas)")

        linha = ctk.CTkFrame(self.area_arquivos, fg_color="transparent")
        linha.pack(fill="x", pady=(0, tema.ESPACO_PEQUENO))
        self.seletor_tipo = SeletorOpcoes(linha, "Tipo da declaração", list(TIPOS_REFERENCIA),
                                          ao_mudar=lambda _: self.atualizar_botoes())
        self.seletor_tipo.pack(side="left")
        self.campo_data = CampoRotulado(linha, "Data de lançamento", largura=150,
                                        texto_inicial=date.today().strftime("%d/%m/%Y"),
                                        ao_mudar=lambda _: self.atualizar_botoes())
        self.campo_data.pack(side="left", padx=(tema.ESPACO_ENTRE_BLOCOS, 0))

        linha_cnpjs = ctk.CTkFrame(self.area_arquivos, fg_color="transparent")
        linha_cnpjs.pack(fill="x", pady=(0, tema.ESPACO_PEQUENO))
        self.botao_outros_cnpjs = BotaoSecundario(linha_cnpjs, "Outros CNPJs da Fundação",
                                                  self.editar_outros_cnpjs, largura=220)
        self.botao_outros_cnpjs.pack(side="left")
        self.rotulo_outros_cnpjs = ctk.CTkLabel(linha_cnpjs, text="", font=tema.fonte_legenda(),
                                                text_color=tema.COR_TEXTO_SUAVE, anchor="w")
        self.rotulo_outros_cnpjs.pack(side="left", padx=(tema.ESPACO_PEQUENO, 0))
        self._mostrar_outros_cnpjs()

        self.adicionar_pasta_saida()
        self.atualizar_botoes()

    # --- escolhas ---

    def _pdfs_escolhidos(self, caminhos):
        if not caminhos:
            return
        pasta = caminhos[0]
        self.cartao_pdfs.definir_confirmacao("Contando os PDFs...", None)
        self.sugerir_pasta_saida(pasta / SUBPASTA_SAIDA)

        def contado(quantidade):
            if self.cartao_pdfs.caminho != pasta:
                return
            if not quantidade:
                self.cartao_pdfs.definir_confirmacao("Nenhum PDF encontrado nesta pasta", "atencao")
            else:
                plural = "s" if quantidade > 1 else ""
                self.cartao_pdfs.definir_confirmacao(f"{formatar_inteiro(quantidade)} PDF{plural} "
                                                     f"encontrado{plural}", "ok")

        self.ler_em_segundo_plano(lambda: processamento.contar_pdfs(pasta), contado)

    def _exportacoes_escolhidas(self, caminhos):
        self._mostrar_campos_exportacao(bool(caminhos))
        self._resultados_escolhidos(self.cartao_resultados.caminhos)
        if not caminhos:
            return
        if not self.cartao_pdfs.preenchido:
            self.sugerir_pasta_saida(caminhos[0].parent)
        self.cartao_exportacoes.definir_confirmacao("Contando as notas...", None)

        def contado(contagem):
            if self.cartao_exportacoes.caminhos != caminhos or contagem is None:
                return
            notas, lidos, falhas = contagem
            texto = f"{formatar_inteiro(notas)} nota{'s' if notas != 1 else ''} em {lidos} " \
                    f"arquivo{'s' if lidos != 1 else ''}"
            if falhas:
                texto += f" · {falhas} não parece{'m' if falhas > 1 else ''} exportação do site"
            self.cartao_exportacoes.definir_confirmacao(texto, "atencao" if falhas or not notas else "ok")

        self.ler_em_segundo_plano(lambda: processamento.contar_notas_exportacoes(caminhos), contado)

    def _mostrar_campos_exportacao(self, mostrar: bool) -> None:
        if mostrar:
            self.area_exportacao.pack(fill="x", pady=(0, tema.ESPACO_PEQUENO), after=self.cartao_exportacoes)
        else:
            self.area_exportacao.pack_forget()

    def _resultados_escolhidos(self, caminhos):
        if not caminhos:
            return
        quantidade = len(caminhos)
        texto = f"{quantidade} resultado{'s' if quantidade > 1 else ''} da prefeitura"
        if self.cartao_exportacoes.preenchido:
            self.cartao_resultados.definir_confirmacao(f"{texto} · {AVISO_RESULTADOS}", "atencao")
        else:
            self.cartao_resultados.definir_confirmacao(texto, "ok")

    def _mostrar_outros_cnpjs(self) -> None:
        quantidade = len(processamento.outros_cnpjs_fundacao())
        if quantidade:
            texto = (f"além da raiz 98.765.432, {quantidade} CNPJ{'s' if quantidade > 1 else ''} "
                     "de outra raiz")
        else:
            texto = "só os CNPJs com a raiz 98.765.432"
        self.rotulo_outros_cnpjs.configure(text=texto)

    def editar_outros_cnpjs(self):
        nova = outros_cnpjs.editar_outros_cnpjs(self, processamento.outros_cnpjs_fundacao(),
                                                processamento.interpretar_outros_cnpjs)
        if nova is None:
            return
        problema = processamento.salvar_outros_cnpjs_fundacao(nova)
        if problema:
            self.avisar(problema)
        self._mostrar_outros_cnpjs()

    def ao_novo(self):
        self.ultimo_resultado = None
        self._mostrar_campos_exportacao(False)
        self.campo_competencia.definir("")
        self.seletor_tipo.selecionar(None)
        self.campo_data.definir(date.today().strftime("%d/%m/%Y"))

    # --- validação ---

    def pronto_para_processar(self) -> bool:
        if not hasattr(self, "campo_data"):                 # a base confere antes de a tela ficar pronta
            return False
        tem_entrada = self.cartao_pdfs.preenchido or self.cartao_exportacoes.preenchido
        return (tem_entrada and self.seletor_tipo.valor is not None
                and processamento.interpretar_data(self.campo_data.valor()) is not None
                and self.cartao_saida is not None and self.cartao_saida.preenchido)

    def validar(self) -> str | None:
        """Mensagem do que falta (None = pode gerar)."""
        faltando = []
        if not (self.cartao_pdfs.preenchido or self.cartao_exportacoes.preenchido):
            faltando.append("a pasta com os PDFs ou as exportações de lotes")
        if self.seletor_tipo.valor is None:
            faltando.append("o tipo da declaração (Normal ou Complementar)")
        if not self.cartao_saida.preenchido:
            faltando.append("a pasta de saída")
        if faltando:
            return "Falta escolher: " + ", ".join(faltando) + "."
        if processamento.interpretar_data(self.campo_data.valor()) is None:
            return "Informe a data de lançamento no formato DD/MM/AAAA (ex.: 28/09/2026)."
        if self.cartao_exportacoes.preenchido:
            cnpj = "".join(c for c in self.campo_tomador.valor() if c.isdigit())
            if len(cnpj) != 14:
                return "Informe o CNPJ do tomador das exportações (14 dígitos)."
            if processamento.interpretar_competencia(self.campo_competencia.valor()) is None:
                return "Informe a competência das exportações no formato MM/AAAA (ex.: 08/2026)."
        return None

    # --- processar ---

    def processar(self):
        if self.ocupado:
            return
        erro = self.validar()
        if erro:
            self.avisar(erro)
            return
        exportacoes = self.cartao_exportacoes.caminhos
        parametros = dict(
            pasta_pdfs=self.cartao_pdfs.caminho,
            exportacoes=exportacoes,
            resultados=self.cartao_resultados.caminhos,
            cnpj_tomador=self.campo_tomador.valor() if exportacoes else "",
            competencia=(processamento.interpretar_competencia(self.campo_competencia.valor())
                         if exportacoes else None),
            tipo_referencia=TIPOS_REFERENCIA[self.seletor_tipo.valor],
            data_lancamento=processamento.interpretar_data(self.campo_data.valor()),
            pasta_saida=self.pasta_saida,
            perguntar_cidade=lambda documento, nome: self.perguntas.perguntar(
                pergunta_cidade.perguntar_cidade, self, documento, nome),
            perguntar_substituir=lambda caminhos: self.perguntas.perguntar(
                self.confirmar_substituicao, caminhos),
        )
        self.perguntas.iniciar()
        texto = "Lendo PDFs..." if self.cartao_pdfs.preenchido else "Lendo as exportações..."
        self.executar(lambda progresso: processamento.gerar(**parametros, progresso=progresso),
                      self._mostrar_resultado, texto)

    def mostrar_erro(self, mensagem: str, detalhe: str = "") -> None:
        self.perguntas.parar()
        super().mostrar_erro(mensagem, detalhe)

    # --- resultado ---

    def _mostrar_resultado(self, resultado):
        self.perguntas.parar()
        self.ultimo_resultado = resultado
        self.campo_tomador.definir_opcoes(processamento.tomadores_usados())
        if resultado.cancelado:
            self.mostrar_inicio()
            self.informar("Nada foi gravado: os arquivos já existiam e não foram substituídos.")
            return

        area = self.resultado.mostrar_conteudo()
        if resultado.tudo_certo and not resultado.erro_relatorio:
            self.resultado.definir_selo("Concluído", "ok")
        else:
            self.resultado.definir_selo("Concluído com avisos", "atencao")

        GrupoNumeros(area, [
            (resultado.notas_no_arquivo, "notas no arquivo", "ok" if resultado.notas_no_arquivo else "principal"),
            (resultado.lancar_a_mao, "lançar à mão", "atencao" if resultado.lancar_a_mao else "ok"),
            (resultado.nao_incluidas, legenda_nao_incluidas(resultado),
             "erro" if resultado.erros_de_leitura else "principal"),
        ]).pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))

        if resultado.arquivos:
            TabelaSimples(area, [Coluna("Tomador (login)", peso=4), Coluna("Mês", peso=2),
                                 Coluna("Qtd.", numero=True, peso=1), Coluna("Serviços", numero=True, peso=3),
                                 Coluna("ISS", numero=True, peso=2)],
                          [(pergunta_cidade.formatar_documento(a.tomador_documento), a.competencia.texto,
                            a.quantidade, formatar_reais(a.total_servicos), formatar_reais(a.total_iss))
                           for a in resultado.arquivos]).pack(fill="x", pady=(0, tema.ESPACO_ENTRE_BLOCOS))
        for conferencia in resultado.conferencias:
            texto = conferencia.descricao + (f" — {conferencia.detalhe}" if conferencia.detalhe else "")
            LinhaConferencia(area, texto, "ok" if conferencia.ok else "atencao").pack(fill="x", pady=3)
        if resultado.erro_relatorio:
            LinhaConferencia(area, resultado.erro_relatorio, "erro").pack(fill="x", pady=3)

        self.botoes_resultado = self.definir_botoes_resultado([
            ("Abrir pasta", lambda: self.abrir(resultado.pasta_saida), "pasta"),
            ("Ver avisos", lambda: self.abrir(resultado.caminho_relatorio), "olho"),
            ("Novo", self.novo, "atualizar"),
        ])
        self.botoes_resultado["Ver avisos"].habilitar(bool(resultado.caminho_relatorio))
