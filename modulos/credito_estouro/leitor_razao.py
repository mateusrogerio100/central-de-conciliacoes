"""Leitura do razão da conta Crédito Complemento Salário (Tasy WEXE002) — ESPECIFICACAO_CREDITO_ESTOURO.md, 3.2.

Três formatos, lidos para a mesma estrutura (LeituraRazao):

- `.xls` do Tasy: na verdade um TEXTO com as células separadas por tabulação (cp1252), lido com o csv do Python
  (campo entre aspas com quebra de linha fica numa célula só, como no Excel);
- `.xlsx` (ou um `.xls` de verdade, do Excel 97-2003);
- PDF: o texto de cada página; o histórico comprido quebra em várias linhas, que são juntadas ao lançamento.

Planilha: colunas localizadas pelo título (Data · Histórico · Lote · Débitos · Créditos · Saldo); cada título "é
dono" das células até o próximo (o valor pode vir uma célula deslocado), como nas Rescisões.

Validação: saldo anterior + débitos − créditos = último saldo impresso; somas = "Total - <conta>".
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook

from modulos.credito_estouro.modelos import ZERO, Aviso, LancamentoRazao, LeituraRazao
from modulos.credito_estouro.util import (
    data_br,
    dinheiro,
    eh_pdf,
    juntar_espacos,
    paginas_do_pdf,
    reais,
    sem_acento,
)

COLUNAS_RAZAO = ["Data", "Histórico", "Lote", "Débitos", "Créditos", "Saldo"]
ERRO_NAO_EH_RAZAO = ("Este arquivo não parece ser o razão da conta do Tasy (colunas Data, Histórico, Lote, Débitos, "
                     "Créditos e Saldo). Confira se escolheu o arquivo certo.")
ERRO_EH_EVENTOS = ("Este arquivo é o PDF de eventos da folha, não o razão. Escolha-o no campo \"Eventos da folha "
                   "do mês\".")

_BYTES_XLSX = b"PK"
_BYTES_XLS_BINARIO = bytes.fromhex("D0CF11E0")
_REGEX_CONTA = re.compile(r"^(\d+)\s*-\s*(\d[\d.]*)\s+(\S.*)$")         # "10652 - 1.01.03.02.0002  Credito …"
_REGEX_DATA_TEXTO = re.compile(r"\d{2}/\d{2}/\d{4}")
_VALOR = r"-?[\d.]+,\d{2}"
_REGEX_LANCAMENTO_PDF = re.compile(
    rf"^(\d{{2}}/\d{{2}}/\d{{4}})\s+(?:(.*?)\s+)?(\d+)\s+({_VALOR})\s+({_VALOR})\s+({_VALOR})$")
_REGEX_SALDO_ANTERIOR_PDF = re.compile(rf"^Saldo anterior\s+({_VALOR})$", re.IGNORECASE)
_REGEX_TOTAL_CONTA_PDF = re.compile(rf"^Total\s*-\s*.*?\s({_VALOR})\s+({_VALOR})$")
_REGEX_TOPO_PDF = re.compile(r"^(.*?)\s+Livro:\s*\d+\s+P[áa]gina:", re.IGNORECASE)


# ---------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------
def ler_razao(caminho: Path) -> LeituraRazao:
    caminho = Path(caminho)
    leitura = LeituraRazao(arquivo=caminho.name)
    try:
        bruto = caminho.read_bytes()
    except OSError as erro:
        leitura.erro = f"Não foi possível abrir o arquivo: {erro.strerror or erro}."
        return leitura
    if eh_pdf(bruto):
        try:
            paginas = paginas_do_pdf(caminho)
        except Exception as erro:
            leitura.erro = f"Não foi possível abrir o PDF: {erro}"
            return leitura
        return ler_razao_do_texto(paginas, leitura)
    try:
        linhas = _linhas_da_planilha(caminho, bruto)
    except ValueError as erro:
        leitura.erro = str(erro)
        return leitura
    return ler_razao_da_planilha(linhas, leitura)


def _linhas_da_planilha(caminho: Path, bruto: bytes) -> list[list[object]]:
    if bruto.startswith(_BYTES_XLSX):
        try:
            livro = load_workbook(io.BytesIO(bruto), read_only=True, data_only=True)
        except Exception as erro:
            raise ValueError(f"Não foi possível abrir a planilha: {erro}") from erro
        try:
            return [list(linha) for linha in livro.worksheets[0].iter_rows(values_only=True)]
        finally:
            livro.close()
    if bruto.startswith(_BYTES_XLS_BINARIO):
        import xlrd

        try:
            livro = xlrd.open_workbook(file_contents=bruto)
        except Exception as erro:
            raise ValueError(f"Não foi possível abrir a planilha: {erro}") from erro
        aba = livro.sheet_by_index(0)
        linhas: list[list[object]] = []
        for indice in range(aba.nrows):
            linha: list[object] = []
            for celula in aba.row(indice):
                if celula.ctype == xlrd.XL_CELL_DATE:
                    linha.append(xlrd.xldate.xldate_as_datetime(celula.value, livro.datemode))
                else:
                    linha.append(celula.value)
            linhas.append(linha)
        return linhas
    for codificacao in ("utf-8", "cp1252"):
        try:
            texto = bruto.decode(codificacao)
            break
        except UnicodeDecodeError:
            continue
    else:
        texto = bruto.decode("latin-1")
    texto = texto.lstrip("﻿")
    leitor = csv.reader(io.StringIO(texto, newline=""), delimiter="\t", quotechar='"')
    return [[celula.replace("\xa0", " ").strip() for celula in linha] for linha in leitor]


# ---------------------------------------------------------------------
# Planilha (.xls do Tasy / .xlsx)
# ---------------------------------------------------------------------
class _Cabecalho:
    """Colunas pelo nome; cada uma vai da sua posição até antes da próxima."""

    def __init__(self, linha: list[object]):
        self.posicoes = [(sem_acento(c.strip()), i) for i, c in enumerate(linha) if isinstance(c, str) and c.strip()]

    @staticmethod
    def eh_cabecalho(linha: list[object]) -> bool:
        nomes = {sem_acento(c.strip()) for c in linha if isinstance(c, str)}
        return all(sem_acento(n) in nomes for n in COLUNAS_RAZAO)

    def valor(self, linha: list[object], nome: str) -> object:
        alvo = sem_acento(nome)
        for indice, (atual, inicio) in enumerate(self.posicoes):
            if atual != alvo:
                continue
            fim = self.posicoes[indice + 1][1] if indice + 1 < len(self.posicoes) else len(linha)
            return next((c for c in linha[inicio:fim] if c is not None and c != ""), None)
        return None


def _preenchidas(linha: list[object]) -> list[object]:
    return [c for c in linha if c is not None and c != ""]


def _eh_dinheiro(valor: object) -> bool:
    try:
        dinheiro(valor)
        return True
    except ValueError:
        return False


def ler_razao_da_planilha(linhas: list[list[object]], leitura: LeituraRazao) -> LeituraRazao:
    leitura.formato = "Excel"
    cabecalho: _Cabecalho | None = None
    contas: list[str] = []
    ultimo: LancamentoRazao | None = None

    for numero, linha in enumerate(linhas, start=1):
        celulas = _preenchidas(linha)
        if not celulas:
            continue
        textos = [juntar_espacos(c) for c in celulas if isinstance(c, str)]
        primeiro = textos[0] if textos else ""
        if any(t.startswith("Página:") for t in textos):
            if not leitura.unidade and primeiro and not primeiro.startswith(("Página", "Impresso")):
                leitura.unidade = primeiro
            continue
        if any(t.startswith("Impresso em") for t in textos) or textos == ["Razão"]:
            continue
        if any(t.startswith("Período") for t in textos):
            datas = [d for d in (data_br(c) for c in celulas) if d]
            if datas and leitura.inicio is None:
                leitura.inicio, leitura.fim = datas[0], datas[-1]
            continue
        if _Cabecalho.eh_cabecalho(linha):
            cabecalho = cabecalho or _Cabecalho(linha)
            continue
        if cabecalho is None:
            continue
        if len(celulas) == 1 and primeiro and _REGEX_CONTA.match(primeiro):
            if primeiro not in contas:
                contas.append(primeiro)
            ultimo = None
            continue
        valores = [c for c in celulas if not isinstance(c, str) or _eh_dinheiro(c)]
        if primeiro.casefold().startswith("saldo anterior"):
            if valores:
                leitura.saldo_anterior = dinheiro(valores[-1])
            continue
        if primeiro.startswith("Total"):
            if primeiro.startswith("Total -") and len(valores) >= 2:
                leitura.totais_impressos = (dinheiro(valores[0]), dinheiro(valores[1]))
            continue
        data = data_br(cabecalho.valor(linha, "Data"))
        historico = juntar_espacos(cabecalho.valor(linha, "Histórico") or "")
        if data is None:
            if historico and ultimo is not None and len(celulas) == 1:     # histórico que continua embaixo
                ultimo.historico = f"{ultimo.historico} {historico}"
            elif historico:
                leitura.avisos.append(Aviso(leitura.arquivo, f"Linha {numero}: linha não reconhecida (\"{historico}\")."))
            continue
        try:
            debito = dinheiro(cabecalho.valor(linha, "Débitos") or 0)
            credito = dinheiro(cabecalho.valor(linha, "Créditos") or 0)
            saldo_celula = cabecalho.valor(linha, "Saldo")
            saldo = dinheiro(saldo_celula) if saldo_celula is not None else None
        except ValueError as erro:
            leitura.avisos.append(Aviso(leitura.arquivo,
                                        f"Linha {numero}: valor não reconhecido ({erro}); o lançamento não foi lido."))
            continue
        lote = cabecalho.valor(linha, "Lote")
        ultimo = LancamentoRazao(data=data, historico=historico,
                                 lote=str(int(lote)) if isinstance(lote, (int, float)) else juntar_espacos(lote or ""),
                                 debito=debito, credito=credito, saldo=saldo, linha=numero)
        leitura.lancamentos.append(ultimo)
        if saldo is not None:
            leitura.ultimo_saldo_impresso = saldo

    if cabecalho is None:
        leitura.erro = ERRO_NAO_EH_RAZAO
        return leitura
    return _finalizar(leitura, contas)


# ---------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------
def ler_razao_do_texto(paginas: list[str], leitura: LeituraRazao) -> LeituraRazao:
    leitura.formato = "PDF"
    texto_todo = "\n".join(paginas)
    if "Total de Colaboradores" in texto_todo:
        leitura.erro = ERRO_EH_EVENTOS
        return leitura
    if not all(sem_acento(n) in sem_acento(texto_todo) for n in COLUNAS_RAZAO):
        leitura.erro = ERRO_NAO_EH_RAZAO
        return leitura

    contas: list[str] = []
    ultimo: LancamentoRazao | None = None
    numero = 0
    for texto in paginas:
        for bruta in texto.splitlines():
            numero += 1
            linha = juntar_espacos(bruta)
            if not linha:
                continue
            topo = _REGEX_TOPO_PDF.match(linha)
            if topo:
                leitura.unidade = leitura.unidade or juntar_espacos(topo.group(1))
                continue
            if linha == "Razão" or linha.startswith("Impresso em") or sem_acento(linha).startswith("data historico"):
                continue
            if linha.startswith("Período"):
                datas = [data_br(d) for d in _REGEX_DATA_TEXTO.findall(linha)]
                if datas and leitura.inicio is None:
                    leitura.inicio, leitura.fim = datas[0], datas[-1]
                continue
            saldo_anterior = _REGEX_SALDO_ANTERIOR_PDF.match(linha)
            if saldo_anterior:
                leitura.saldo_anterior = dinheiro(saldo_anterior.group(1))
                continue
            if linha.startswith("Total"):
                total = _REGEX_TOTAL_CONTA_PDF.match(linha)
                if total:
                    leitura.totais_impressos = (dinheiro(total.group(1)), dinheiro(total.group(2)))
                ultimo = None
                continue
            if _REGEX_CONTA.match(linha):
                if linha not in contas:
                    contas.append(linha)
                ultimo = None
                continue
            lancamento = _REGEX_LANCAMENTO_PDF.match(linha)
            if lancamento:
                ultimo = LancamentoRazao(data=data_br(lancamento.group(1)),
                                         historico=juntar_espacos(lancamento.group(2) or ""),
                                         lote=lancamento.group(3),
                                         debito=dinheiro(lancamento.group(4)),
                                         credito=dinheiro(lancamento.group(5)),
                                         saldo=dinheiro(lancamento.group(6)), linha=numero)
                leitura.lancamentos.append(ultimo)
                leitura.ultimo_saldo_impresso = ultimo.saldo
                continue
            if ultimo is not None:                      # histórico que quebrou na linha de baixo
                ultimo.historico = juntar_espacos(f"{ultimo.historico} {linha}")
                continue
            leitura.avisos.append(Aviso(leitura.arquivo, f"Linha {numero} do PDF não reconhecida (\"{linha}\")."))
    return _finalizar(leitura, contas)


# ---------------------------------------------------------------------
# Conferências
# ---------------------------------------------------------------------
def _finalizar(leitura: LeituraRazao, contas: list[str]) -> LeituraRazao:
    if leitura.saldo_anterior is None:
        leitura.erro = "O razão não traz o \"Saldo anterior\". Confira se escolheu o razão certo."
        return leitura
    leitura.conta = juntar_espacos(contas[0]) if contas else ""
    if len(contas) > 1:
        leitura.avisos.append(Aviso(leitura.arquivo,
                                    "ATENÇÃO: o razão tem mais de uma conta (" + "; ".join(contas)
                                    + "). Todas as linhas foram lidas juntas."))
    if leitura.ultimo_saldo_impresso is not None and leitura.saldo_final != leitura.ultimo_saldo_impresso:
        leitura.avisos.append(Aviso(
            leitura.arquivo,
            f"ATENÇÃO: saldo anterior + débitos − créditos ({reais(leitura.saldo_final)}) não bate com o último "
            f"saldo do razão ({reais(leitura.ultimo_saldo_impresso)}). A leitura pode estar incompleta."))
    if leitura.totais_impressos is None:
        leitura.avisos.append(Aviso(leitura.arquivo,
                                    "\"Total - <conta>\" não encontrado no razão: não deu para conferir as somas."))
    elif leitura.totais_impressos != (leitura.total_debitos, leitura.total_creditos):
        leitura.avisos.append(Aviso(
            leitura.arquivo,
            f"ATENÇÃO: as somas lidas (débitos {reais(leitura.total_debitos)}, créditos "
            f"{reais(leitura.total_creditos)}) não batem com o total do razão (débitos "
            f"{reais(leitura.totais_impressos[0])}, créditos {reais(leitura.totais_impressos[1])})."))
    return leitura


def _ultimo_dia(competencia: date) -> date:
    seguinte = date(competencia.year + (competencia.month == 12), competencia.month % 12 + 1, 1)
    return date.fromordinal(seguinte.toordinal() - 1)


def conferir_periodo(leitura: LeituraRazao, competencia: date) -> str | None:
    """O razão tem de ser do mês inteiro dos eventos (seção 3.2). Devolve a mensagem de erro ou None."""
    inicio, fim = competencia.replace(day=1), _ultimo_dia(competencia)
    if leitura.inicio == inicio and leitura.fim == fim:
        return None
    periodo = (f"de {leitura.inicio:%d/%m/%Y} até {leitura.fim:%d/%m/%Y}" if leitura.inicio and leitura.fim
               else "sem período")
    return (f"O razão é {periodo}, mas os eventos da folha são de {competencia:%m/%Y}. Tire no Tasy o razão só "
            f"desse mês ({inicio:%d/%m/%Y} a {fim:%d/%m/%Y}) e processe outra vez.")
