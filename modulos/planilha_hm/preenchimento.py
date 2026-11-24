"""Preenchimento da cópia da Planilha HM. Regras R3, R4, R5, R6 e R8.

Em duas passadas, como no Convênios:
1. `planejar`: descobre os eventos novos e a seção de cada um (tabela conta → seção, R5a); o que a tabela não
   resolve vira pergunta para a tela.
2. `preencher`: com as respostas, grava a cópia (nunca o arquivo escolhido):
   - aba "Senior MM AAAA": as linhas do relatório Eventos, com as fórmulas até a última linha (R3);
   - aba do ano: CC novo logo abaixo do último CC do evento (R4); evento novo no fim da seção, somado ao total
     da seção em todos os meses (R5); seção nova antes do TOTAL GERAL, somada a ele em todos os meses (R6).
     As linhas novas copiam a formatação e as fórmulas de uma linha do mesmo tipo; inserir linhas corrige as
     fórmulas de toda a planilha (R7, insercao_linhas);
   - LOTE REPASSE do mês = total do Movimento (R8).
"""

from __future__ import annotations

import copy
import io
import re
import warnings
import zipfile
from pathlib import Path

import openpyxl
from openpyxl.utils import get_column_letter

from modulos.planilha_hm import configuracao as cfg
from modulos.planilha_hm.insercao_linhas import copiar_formula, copiar_linha, inserir_linhas
from modulos.planilha_hm.leitor_movimento import contas_do_evento
from modulos.planilha_hm.leitor_planilha import COLUNA_NOME
from modulos.planilha_hm.modelos import (
    Aviso,
    ErroLeitura,
    EventoNovo,
    Eventos,
    ItemTabela,
    LinhaCC,
    LinhaCriada,
    LinhaEvento,
    Movimento,
    Pergunta,
    Planilha,
    Plano,
    Preenchimento,
    Secao,
)
from modulos.planilha_hm.normalizacao import formatar_valor, para_inteiro, texto_igual
from modulos.planilha_hm.secoes_contas import gravar_tabela, ler_tabela, montar_tabela

_RE_SOMA = re.compile(r"^=SUM\(([^()]*)\)$", re.IGNORECASE)


def _numero_ou_texto(codigo: str):
    """O código do CC como número, como estão os outros na planilha ("72" -> 72)."""
    numero = para_inteiro(codigo)
    return numero if numero is not None else codigo


# ---------------------------------------------------------------------------
# Conferências antes de começar
# ---------------------------------------------------------------------------

def conferir_entradas(eventos: Eventos, movimento: Movimento, planilha: Planilha) -> None:
    """ValueError (mensagem para o usuário) se as três entradas não forem do mesmo mês e ano."""
    if eventos.mes is None or eventos.ano is None:
        raise ValueError(f"{Path(eventos.arquivo).name}: a competência do Eventos não foi identificada.")
    if (movimento.ano, movimento.mes) != (eventos.ano, eventos.mes):
        mes_movimento = f"{movimento.mes:02d}/{movimento.ano}" if movimento.mes else "desconhecido"
        raise ValueError(f"O Eventos é de {eventos.mes:02d}/{eventos.ano} e o Movimento, de {mes_movimento}: "
                         "escolha os dois do mesmo mês.")
    if planilha.ano != eventos.ano:
        raise ValueError(f"A Planilha HM é de {planilha.ano} e o Eventos, de {eventos.ano}.")
    if eventos.mes not in planilha.seniors:
        raise ValueError(f"A Planilha HM não tem a aba \"{nome_senior(eventos.mes, planilha.ano)}\".")
    if eventos.mes not in planilha.colunas_meses:
        raise ValueError(f"A aba {planilha.aba_ano} não tem a coluna do mês {eventos.mes:02d}.")


def nome_senior(mes: int, ano: int) -> str:
    return cfg.NOME_ABA_SENIOR.format(mes=mes, ano=ano)


def mes_ja_preenchido(planilha: Planilha, mes: int) -> int:
    """Quantas linhas de dados a aba Senior do mês já tem (0 = vazia; mais = a tela pergunta antes)."""
    senior = planilha.seniors.get(mes)
    return senior.linhas_dados if senior else 0


_RE_DESENHO = re.compile(r"<(?:\w+:)?(?:sp|cxnSp|grpSp)\b")      # forma, seta/conector, grupo (a imagem vai)
_RE_IGNORAR_ERRO = re.compile(r"<(?:\w+:)?ignoredErrors\b")


def o_que_a_copia_nao_leva(origem: Path) -> list[Aviso]:
    """O openpyxl não copia desenhos (setas, formas) nem a marcação "ignorar erro" das células: avisa, para não
    sumir em silêncio (visto na planilha real em 30/10/2026: duas setas abaixo do LOTE REPASSE)."""
    avisos = []
    try:
        with zipfile.ZipFile(origem) as arquivo:
            nomes = arquivo.namelist()
            desenhos = sum(len(_RE_DESENHO.findall(arquivo.read(n).decode("utf-8", "ignore")))
                           for n in nomes if n.startswith("xl/drawings/") and n.endswith(".xml"))
            ignorar = any(_RE_IGNORAR_ERRO.search(arquivo.read(n).decode("utf-8", "ignore"))
                          for n in nomes if n.startswith("xl/worksheets/") and n.endswith(".xml"))
    except (OSError, zipfile.BadZipFile, KeyError):
        return avisos
    nome = Path(origem).name
    if desenhos:
        avisos.append(Aviso(nome, f"A planilha tem {desenhos} desenho(s) (setas, linhas ou formas) que a cópia não "
                                  "leva: o programa não consegue copiá-los. Se fizerem falta, desenhe de novo na "
                                  "cópia."))
    if ignorar:
        avisos.append(Aviso(nome, "A marcação \"ignorar erro\" das células não vai para a cópia: podem aparecer "
                                  "triângulos verdes em células de fórmula. É só aparência; nenhum valor muda."))
    return avisos


# ---------------------------------------------------------------------------
# 1ª passada: planejar
# ---------------------------------------------------------------------------

def _secoes_que_recebem_evento(planilha: Planilha) -> list[str]:
    """As seções que podem receber um evento novo: as que têm a linha de total (a seção vazia não tem)."""
    return [s.nome for s in planilha.secoes if s.linha_total is not None]


def planejar(eventos: Eventos, movimento: Movimento, planilha: Planilha, pasta_config: Path) -> Plano:
    """Os eventos novos e a seção de cada um. ErroLeitura se a tabela conta → seção estiver com problema."""
    conferir_entradas(eventos, movimento, planilha)
    caminho = Path(pasta_config) / cfg.ARQUIVO_SECOES
    tabela = ler_tabela(caminho)
    plano_perguntas: list[Pergunta] = []
    if tabela is None:
        tabela, plano_perguntas = montar_tabela(planilha, eventos, movimento, caminho)
    plano = Plano(tabela, str(caminho), perguntas=plano_perguntas, avisos=list(tabela.avisos))
    possiveis = _secoes_que_recebem_evento(planilha)
    perguntas = {p.chave: p for p in plano.perguntas}
    origem_tabela = cfg.ORIGEM_TABELA if tabela.existia else cfg.ORIGEM_TABELA_MONTADA

    for evento in eventos.eventos_ok:
        if planilha.evento(evento.numero) is not None:
            continue
        contas, como = contas_do_evento(movimento, evento.numero, evento.nome)
        novo = EventoNovo(evento, contas, como)
        plano.novos.append(novo)
        secoes = {tabela.secao(c.classificacao) for c in contas}
        if contas and len(secoes) == 1 and None not in secoes and next(iter(secoes)) in possiveis:
            novo.secao, novo.origem = next(iter(secoes)), origem_tabela
            continue
        if not contas:
            chave = f"evento {evento.numero}"
            motivo = (f"O evento {evento.numero} {evento.nome} é novo e o Movimento não mostra a conta dele. "
                      "Em qual seção ele entra?")
            nome_nova = evento.nome.upper()
        else:
            fora = [c for c in contas if tabela.secao(c.classificacao) is None]
            principal = fora[0] if fora else contas[0]
            chave, nome_nova = principal.classificacao, principal.nome.upper()
            descricao = "; ".join(f"{c.classificacao} {c.nome}" for c in contas)
            if fora:
                motivo = (f"O evento {evento.numero} {evento.nome} é novo e a conta dele ({descricao}) não está na "
                          "tabela conta → seção. Em qual seção ele entra?")
            elif len(secoes) > 1:
                motivo = (f"O evento {evento.numero} {evento.nome} é novo e as contas dele ({descricao}) estão em "
                          f"seções diferentes ({', '.join(sorted(secoes))}). Em qual seção ele entra?")
            else:
                motivo = (f"O evento {evento.numero} {evento.nome} é novo; a tabela põe a conta dele ({descricao}) "
                          f"na seção \"{next(iter(secoes))}\", que não existe na planilha (ou não tem linha de "
                          "total). Em qual seção ele entra?")
        novo.chave_pergunta = chave
        if chave in perguntas:
            perguntas[chave].eventos.append(evento.numero)
            continue
        pergunta = Pergunta(chave, motivo, contas, [evento.numero], possiveis, True, nome_nova)
        perguntas[chave] = pergunta
        plano.perguntas.append(pergunta)
    return plano


# ---------------------------------------------------------------------------
# 2ª passada: preencher
# ---------------------------------------------------------------------------

def _decidir_secoes(plano: Plano, respostas: dict[str, str]) -> dict[str, str]:
    """Aplica as respostas ao plano e à tabela; devolve {nome da seção nova: conta} das seções a criar."""
    faltam = [p.chave for p in plano.perguntas if p.chave not in respostas]
    if faltam:
        raise ValueError(f"Faltam respostas para: {', '.join(faltam)}.")
    novas: dict[str, str] = {}
    for pergunta in plano.perguntas:
        resposta = respostas[pergunta.chave]
        if resposta == cfg.RESPOSTA_SECAO_NOVA:
            if not pergunta.permite_nova:
                raise ValueError(f"{pergunta.chave}: a resposta tem que ser uma das seções "
                                 f"({', '.join(pergunta.opcoes)}).")
            secao = pergunta.nome_secao_nova
            novas.setdefault(secao, pergunta.contas[0].classificacao if pergunta.contas else "")
        elif resposta in pergunta.opcoes:
            secao = resposta
        else:
            raise ValueError(f"{pergunta.chave}: a seção \"{resposta}\" não é uma das opções.")
        for conta in pergunta.contas:
            if plano.tabela.secao(conta.classificacao) is None:
                plano.tabela.itens[conta.classificacao] = ItemTabela(conta.classificacao, conta.nome, secao)
        for novo in plano.novos:
            if novo.chave_pergunta == pergunta.chave:
                novo.secao, novo.origem = secao, cfg.ORIGEM_RESPOSTA
    return novas


class _Aba:
    """A aba do ano sendo preenchida, com a estrutura lida acompanhando as linhas inseridas."""

    def __init__(self, livro, planilha: Planilha):
        self.livro = livro
        self.planilha = copy.deepcopy(planilha)
        self.aba = livro[planilha.aba_ano]
        self.criadas: list[LinhaCriada] = []
        self.avisos: list[Aviso] = []
        self.col_evento = planilha.colunas[cfg.PLANILHA_TITULO_EVENTO]
        self.col_nome = planilha.colunas[COLUNA_NOME]
        self.col_codigo = planilha.colunas[cfg.PLANILHA_TITULO_CODIGO]
        self.col_centro = planilha.colunas[cfg.PLANILHA_TITULO_CENTRO]

    # -- inserir e acompanhar ------------------------------------------------
    def inserir(self, antes: int, quantidade: int) -> None:
        inserir_linhas(self.livro, self.planilha.aba_ano, antes, quantidade)

        def nova(linha):
            return linha + quantidade if linha is not None and linha >= antes else linha

        p = self.planilha
        for secao in p.secoes:
            secao.linha, secao.linha_total = nova(secao.linha), nova(secao.linha_total)
            secao.linhas_no_total = [nova(l) for l in secao.linhas_no_total]
            secao.linhas_no_total_mes = {m: [nova(l) for l in ls] for m, ls in secao.linhas_no_total_mes.items()}
            for evento in secao.eventos:
                evento.linha = nova(evento.linha)
                for cc in evento.ccs:
                    cc.linha = nova(cc.linha)
        p.linha_total_geral, p.linha_lote, p.linha_diferenca = (nova(p.linha_total_geral), nova(p.linha_lote),
                                                                nova(p.linha_diferenca))
        p.linhas_no_total_geral = [nova(l) for l in p.linhas_no_total_geral]
        p.linhas_no_total_geral_mes = {m: [nova(l) for l in ls] for m, ls in p.linhas_no_total_geral_mes.items()}
        for criada in self.criadas:
            criada.linha = nova(criada.linha)

    def acrescentar_ao_total(self, linha_total: int, linha: int, onde: str) -> None:
        """Soma `linha` à fórmula da linha de total, em todos os meses (R5, R6)."""
        for coluna in self.planilha.colunas_meses.values():
            celula = self.aba.cell(linha_total, coluna)
            referencia = f"{get_column_letter(coluna)}{linha}"
            formula = celula.value
            if formula is None or (isinstance(formula, str) and not formula.strip()):
                celula.value = f"={referencia}"
            elif isinstance(formula, str) and formula.startswith("="):
                soma = _RE_SOMA.match(formula)
                if soma:
                    separador = "," if "," in soma.group(1) and "+" not in soma.group(1) else "+"
                    celula.value = f"=SUM({soma.group(1)}{separador}{referencia})"
                else:
                    celula.value = f"{formula}+{referencia}"
            else:
                self.avisos.append(Aviso(f"aba {self.planilha.aba_ano} {celula.coordinate}",
                                         f"{onde}: a célula tem um valor digitado, não uma fórmula; a linha {linha} "
                                         "não foi somada a ela. Confira à mão.", erro=True))

    # -- modelos para copiar ---------------------------------------------------
    def _modelo_cc(self, evento: LinhaEvento | None, secao: Secao | None) -> LinhaCC | None:
        """Uma linha de CC (com código) para copiar: do próprio evento, da seção, ou da planilha."""
        grupos = [[evento] if evento else [], secao.eventos if secao else [], self.planilha.eventos]
        for eventos in grupos:
            for e in reversed(eventos):
                com_codigo = [cc for cc in e.ccs if cc.codigo]
                if com_codigo:
                    return com_codigo[-1]
        return None

    def _modelo_evento(self, secao: Secao) -> LinhaEvento | None:
        """A última linha de evento da seção; numa seção sem eventos, a última das seções acima."""
        indice = self.planilha.secoes.index(secao)
        for s in reversed(self.planilha.secoes[:indice + 1]):
            if s.eventos:
                return s.eventos[-1]
        return self.planilha.eventos[-1] if self.planilha.eventos else None

    # -- escrever linhas -------------------------------------------------------
    def _escrever_cc(self, modelo: LinhaCC | None, linha: int, numero: int, nome_evento, codigo: str, nome_cc: str):
        if modelo is not None:
            copiar_linha(self.aba, modelo.linha, linha)
        self.aba.cell(linha, self.col_evento).value = numero
        self.aba.cell(linha, self.col_nome).value = nome_evento
        self.aba.cell(linha, self.col_codigo).value = _numero_ou_texto(codigo)
        self.aba.cell(linha, self.col_centro).value = nome_cc

    def cc_novo(self, existente: LinhaEvento, secao: Secao, codigo: str, nome_cc: str) -> None:
        """R4: linha de CC logo abaixo da última linha do evento."""
        modelo = self._modelo_cc(existente, secao)
        antes = existente.ultima_linha + 1
        self.inserir(antes, 1)
        nome_evento = self.aba.cell(existente.linha, self.col_nome).value
        self._escrever_cc(modelo, antes, existente.numero, nome_evento, codigo, nome_cc)
        existente.ccs.append(LinhaCC(codigo, nome_cc, antes))
        self.criadas.append(LinhaCriada("CC novo", antes, existente.numero, existente.nome, codigo, nome_cc,
                                        secao.nome, motivo="o centro de custo ainda não estava no evento"))

    def secao_nova(self, nome: str, conta: str) -> Secao:
        """R6: abertura e total de uma seção nova, logo antes do TOTAL GERAL, e o total somado ao TOTAL GERAL."""
        p = self.planilha
        if p.linha_total_geral is None:
            raise ValueError("A planilha não tem a linha \"TOTAL GERAL\": não dá para criar a seção nova "
                             f"\"{nome}\".")
        modelo_abertura = p.secoes[-1].linha
        modelo_total = next(s.linha_total for s in reversed(p.secoes) if s.linha_total is not None)
        antes = p.linha_total_geral
        self.inserir(antes, 2)
        modelo_abertura = modelo_abertura + 2 if modelo_abertura >= antes else modelo_abertura
        modelo_total = modelo_total + 2 if modelo_total >= antes else modelo_total
        copiar_linha(self.aba, modelo_abertura, antes)
        self.aba.cell(antes, self.col_nome).value = nome
        copiar_linha(self.aba, modelo_total, antes + 1)
        nome_total = cfg.TEXTO_TOTAL_SECAO_NOVA.format(nome=nome)
        self.aba.cell(antes + 1, self.col_nome).value = nome_total
        for coluna in p.colunas_meses.values():
            self.aba.cell(antes + 1, coluna).value = None
        secao = Secao(nome, antes, linha_total=antes + 1, nome_total=nome_total,
                      linhas_no_total_mes={m: [] for m in p.colunas_meses})
        p.secoes.append(secao)
        self.acrescentar_ao_total(p.linha_total_geral, antes + 1, "TOTAL GERAL")
        p.linhas_no_total_geral.append(antes + 1)
        for linhas in p.linhas_no_total_geral_mes.values():
            linhas.append(antes + 1)
        self.criadas.append(LinhaCriada("seção nova", antes, secao=nome, conta=conta,
                                        motivo="conta sem seção na planilha (resposta na tela)"))
        self.criadas.append(LinhaCriada("total da seção nova", antes + 1, secao=nome, conta=conta,
                                        motivo="somado ao TOTAL GERAL em todos os meses"))
        return secao

    def evento_novo(self, novo: EventoNovo, secao: Secao) -> None:
        """R5: linha do evento + uma linha por CC no fim da seção; a linha do evento entra no total da seção."""
        evento = novo.evento
        modelo_evento = self._modelo_evento(secao)
        modelo_cc = self._modelo_cc(modelo_evento, secao)
        antes = secao.linha_total
        self.inserir(antes, 1 + len(evento.subtotais))
        if modelo_evento is not None:
            copiar_linha(self.aba, modelo_evento.linha, antes)
        self.aba.cell(antes, self.col_evento).value = evento.numero
        self.aba.cell(antes, self.col_nome).value = evento.nome
        self.aba.cell(antes, self.col_codigo).value = None
        self.aba.cell(antes, self.col_centro).value = None
        linha_evento = LinhaEvento(evento.numero, evento.nome, antes)
        secao.eventos.append(linha_evento)
        conta = "; ".join(f"{c.classificacao} {c.nome}" for c in novo.contas)
        self.criadas.append(LinhaCriada("evento novo", antes, evento.numero, evento.nome, secao=secao.nome,
                                        conta=conta, origem=novo.origem,
                                        motivo=f"conta achada no Movimento {novo.como}" if novo.como else
                                        "conta não achada no Movimento"))
        for indice, subtotal in enumerate(evento.subtotais, start=1):
            self._escrever_cc(modelo_cc, antes + indice, evento.numero, evento.nome, subtotal.codigo, subtotal.nome)
            linha_evento.ccs.append(LinhaCC(subtotal.codigo, subtotal.nome, antes + indice))
            self.criadas.append(LinhaCriada("CC novo", antes + indice, evento.numero, evento.nome, subtotal.codigo,
                                            subtotal.nome, secao.nome, motivo="centro de custo do evento novo"))
        self.acrescentar_ao_total(secao.linha_total, antes, f"total da seção \"{secao.nome}\"")
        secao.linhas_no_total.append(antes)
        for linhas in secao.linhas_no_total_mes.values():
            linhas.append(antes)


def _preencher_senior(livro, nome: str, eventos: Eventos, aba_ano: str) -> int:
    """R3: apaga os dados antigos da aba Senior, grava as linhas do Eventos e estende as fórmulas."""
    aba = livro[nome]
    titulos = [c.value for c in aba[1]]
    colunas = {}
    for titulo in cfg.SENIOR_TITULOS:
        indice = next((i for i, v in enumerate(titulos) if texto_igual(v, titulo)), None)
        if indice is None:
            raise ValueError(f"Aba \"{nome}\": o título \"{titulo}\" não foi encontrado na linha 1.")
        colunas[titulo] = indice + 1
    col_evento, col_codigo, col_centro, col_valor = (colunas[t] for t in cfg.SENIOR_TITULOS[:4])
    for linha in range(2, aba.max_row + 1):
        for coluna in (col_evento, col_codigo, col_centro, col_valor):
            aba.cell(linha, coluna).value = None
    subtotais = eventos.subtotais
    for linha, subtotal in enumerate(subtotais, start=2):
        aba.cell(linha, col_evento).value = subtotal.evento
        aba.cell(linha, col_codigo).value = _numero_ou_texto(subtotal.codigo)
        aba.cell(linha, col_centro).value = subtotal.nome
        aba.cell(linha, col_valor).value = float(subtotal.valor)
    ultima = len(subtotais) + 1
    letras = {t: get_column_letter(c) for t, c in colunas.items()}
    padroes = {
        "Concateno": f"={letras['Evento']}{{n}}&{letras['Cód.']}{{n}}",
        "Conf.": f"=VLOOKUP({letras['Concateno']}{{n}},'{aba_ano}'!C:C,1,0)",
        "Conf.1": f"={letras['Concateno']}{{n}}={letras['Conf.']}{{n}}",
    }
    for titulo in cfg.SENIOR_TITULOS[4:]:
        coluna = colunas[titulo]
        com_formula = [l for l in range(2, aba.max_row + 1)
                       if isinstance(aba.cell(l, coluna).value, str) and aba.cell(l, coluna).value.startswith("=")]
        for linha in range(2, ultima + 1):
            celula = aba.cell(linha, coluna)
            if celula.value is not None:
                continue
            anteriores = [l for l in com_formula if l < linha]
            if anteriores:
                modelo = aba.cell(anteriores[-1], coluna)
                celula.value = copiar_formula(modelo.value, linha - anteriores[-1])
                if modelo.has_style:
                    celula._style = copy.copy(modelo._style)
            else:
                celula.value = padroes[titulo].format(n=linha)
            com_formula.append(linha)
    return len(subtotais)


def preencher(origem: Path, planilha: Planilha, eventos: Eventos, movimento: Movimento, plano: Plano,
              respostas: dict[str, str], destino: Path, substituir: bool = False) -> Preenchimento:
    """Grava em `destino` a cópia de `origem` preenchida e grava a tabela conta → seção (montada ou com as
    respostas). ValueError: entradas de meses diferentes, falta resposta, aba Senior já preenchida sem
    `substituir`, destino = origem. ErroLeitura: não deu para abrir. OSError: não deu para gravar a cópia."""
    conferir_entradas(eventos, movimento, planilha)
    origem, destino = Path(origem), Path(destino)
    if destino.resolve() == origem.resolve():
        raise ValueError("A cópia não pode ter o mesmo nome da planilha escolhida (ela nunca é alterada).")
    mes, ano = eventos.mes, planilha.ano
    senior = nome_senior(mes, ano)
    ja = mes_ja_preenchido(planilha, mes)
    if ja and not substituir:
        raise ValueError(f"A aba \"{senior}\" já tem {ja} linha(s) preenchida(s): confirme a substituição.")
    tabela_antes = {k: copy.copy(v) for k, v in plano.tabela.itens.items()}
    novas = _decidir_secoes(plano, respostas)
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Print area cannot be set", category=UserWarning)
            livro = openpyxl.load_workbook(io.BytesIO(origem.read_bytes()))
    except OSError as erro:
        raise ErroLeitura(f"Não foi possível abrir {origem.name}: {erro}") from None

    resultado = Preenchimento(str(destino), mes, ano)
    resultado.linhas_senior = _preencher_senior(livro, senior, eventos, planilha.aba_ano)

    aba = _Aba(livro, planilha)
    for evento in eventos.eventos_ok:
        existente = aba.planilha.evento(evento.numero)
        if existente is not None:
            secao = aba.planilha.secao_do_evento(evento.numero)
            for subtotal in evento.subtotais:
                if subtotal.codigo not in {cc.codigo for cc in existente.ccs}:
                    aba.cc_novo(existente, secao, subtotal.codigo, subtotal.nome)
            continue
        novo = next(n for n in plano.novos if n.evento.numero == evento.numero)
        secao = next((s for s in aba.planilha.secoes if s.nome == novo.secao), None)
        if secao is None:
            secao = aba.secao_nova(novo.secao, novas.get(novo.secao, ""))
        aba.evento_novo(novo, secao)
    resultado.criadas, resultado.avisos = aba.criadas, aba.avisos + o_que_a_copia_nao_leva(origem)

    # R8: LOTE REPASSE do mês
    resultado.lote = movimento.total
    if aba.planilha.linha_lote is not None:
        aba.aba.cell(aba.planilha.linha_lote, planilha.colunas_meses[mes]).value = float(movimento.total)
    else:
        resultado.avisos.append(Aviso(planilha.aba_ano, f"Linha \"{cfg.PLANILHA_TEXTO_LOTE}\" não encontrada: o total "
                                                        f"do Movimento ({formatar_valor(movimento.total)}) não foi "
                                                        "gravado.", erro=True))

    livro.calculation.fullCalcOnLoad = True          # o Excel recalcula os totais ao abrir
    livro.save(destino)

    if not plano.tabela.existia or plano.tabela.itens != tabela_antes:
        try:
            gravar_tabela(plano.tabela, Path(plano.caminho_tabela))
            plano.tabela.existia = True
        except OSError as erro:
            resultado.avisos.append(Aviso(cfg.ARQUIVO_SECOES, f"A tabela conta → seção não foi gravada em "
                                                              f"{plano.caminho_tabela} ({erro}): na próxima vez, as "
                                                              "mesmas perguntas voltam.", erro=True))
    return resultado
