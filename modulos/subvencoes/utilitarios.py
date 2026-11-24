"""Funções auxiliares: texto, dinheiro (Decimal), mês de referência e abertura de planilhas."""

from __future__ import annotations

import csv
import datetime
import io
import re
import unicodedata
import zipfile
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

import openpyxl

from modulos.subvencoes import configuracao
from modulos.subvencoes.modelos import ErroArquivo, MesReferencia

CENTAVO = Decimal("0.01")


# ---------------------------------------------------------------------------
# Texto
# ---------------------------------------------------------------------------


def normalizar_texto(valor) -> str:
    """Remove acentos, passa para minúsculas, junta espaços repetidos e tira espaços das pontas.

    "  Convênio Federal   937610/2022 " -> "convenio federal 937610/2022"
    """
    if valor is None:
        return ""
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.lower().split())


def texto_igual(valor, procurado: str) -> bool:
    """Compara um texto de célula com um título procurado, ignorando acentos, caixa e ':' final."""
    if not isinstance(valor, str):
        return False
    return normalizar_texto(valor).rstrip(":").strip() == normalizar_texto(procurado).rstrip(":").strip()


def texto_comeca_com(valor, prefixo: str) -> bool:
    if not isinstance(valor, str):
        return False
    return normalizar_texto(valor).startswith(normalizar_texto(prefixo))


# ---------------------------------------------------------------------------
# Dinheiro
# ---------------------------------------------------------------------------


def arredondar(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def para_decimal(valor) -> Decimal | None:
    """Converte o conteúdo de uma célula em Decimal com 2 casas. Devolve None se não for número.

    Números vindos do Excel como float são convertidos pelo texto (repr), para não
    carregar a imprecisão do float (ex.: 0.1 vira Decimal("0.10"), não 0.1000000000000000055...).
    Textos no formato brasileiro ("1.234,56") também são aceitos.
    """
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, Decimal):
        return arredondar(valor)
    if isinstance(valor, int):
        return arredondar(Decimal(valor))
    if isinstance(valor, float):
        if valor != valor or valor in (float("inf"), float("-inf")):
            return None
        return arredondar(Decimal(repr(valor)))
    if isinstance(valor, str):
        texto = valor.strip().replace(" ", "")
        if not texto:
            return None
        if "," in texto:
            texto = texto.replace(".", "").replace(",", ".")
        try:
            return arredondar(Decimal(texto))
        except InvalidOperation:
            return None
    return None


def para_float_excel(valor: Decimal) -> float:
    """Única conversão para float do programa: no momento de gravar no Excel."""
    return float(arredondar(valor))


def para_inteiro(valor) -> int | None:
    """Converte um código de conta (ex.: 24876, 24876.0, "24876") em int. None se não for inteiro."""
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float):
        return int(valor) if valor.is_integer() else None
    if isinstance(valor, str):
        texto = valor.strip()
        return int(texto) if texto.isdigit() else None
    return None


# ---------------------------------------------------------------------------
# Mês de referência
# ---------------------------------------------------------------------------

_PADRAO_DATA_TEXTO = re.compile(r"^(?:(\d{1,2})/)?(\d{1,2})/(\d{2}|\d{4})$")


def mes_de_valor(valor) -> MesReferencia | None:
    """Lê o mês de uma célula: data do Excel, "01/08/2026", "08/2026" ou "01/08/26"."""
    if isinstance(valor, (datetime.date, datetime.datetime)):
        return MesReferencia(valor.year, valor.month)
    if isinstance(valor, str):
        return mes_de_texto(valor)
    return None


def mes_de_texto(texto: str) -> MesReferencia | None:
    """Converte "MM/AAAA", "DD/MM/AAAA" ou "DD/MM/AA" em MesReferencia. None se inválido."""
    encontrado = _PADRAO_DATA_TEXTO.match(texto.strip())
    if not encontrado:
        return None
    mes = int(encontrado.group(2))
    ano = int(encontrado.group(3))
    if ano < 100:
        ano += 2000
    if not 1 <= mes <= 12:
        return None
    return MesReferencia(ano, mes)


def nome_com_mes(nome_arquivo: str, mes: MesReferencia) -> str:
    """Troca o MM-AAAA do nome pelo mês de referência (R11).

    "Projetos_08-2026.xlsx" -> "Projetos_09-2026.xlsx"
    "Planilha.xlsx"          -> "Planilha_09-2026.xlsx"
    Se houver mais de um MM-AAAA no nome, troca o último.
    """
    caminho = Path(nome_arquivo)
    base, extensao = caminho.stem, caminho.suffix
    ocorrencias = list(re.finditer(configuracao.PADRAO_MES_ANO_NOME_ARQUIVO, base))
    if ocorrencias:
        ultimo = ocorrencias[-1]
        base = base[: ultimo.start()] + mes.para_nome_arquivo + base[ultimo.end():]
    else:
        base = f"{base}_{mes.para_nome_arquivo}"
    return base + extensao


# ---------------------------------------------------------------------------
# Abertura de planilhas
# ---------------------------------------------------------------------------


# --- Relatórios do Tasy (balancete e patrimônio) ---------------------------------------------
# O Tasy entrega um ".xls" que na verdade é TEXTO separado por tabulação (cp1252). O formato é
# reconhecido pelo CONTEÚDO, não pela extensão (mesma ideia do leitor do Bancos, copiada aqui: um
# módulo não importa outro). Cada célula passa pela mesma conversão que o Excel faz ao abrir o
# arquivo e "Salvar como .xlsx" (número inteiro, número brasileiro, "out/2026" vira data), e por
# isso os leitores do balancete e do patrimônio leem o .xls do Tasy e o .xlsx do mesmo jeito.

_SEPARADOR_TASY = "\t"
_CODIFICACAO_TASY = "cp1252"
_ASSINATURA_ZIP = b"PK"                         # .xlsx (mesmo que esteja com extensão .xls)
_ASSINATURA_XLS_BINARIO = bytes.fromhex("D0CF11E0")   # Excel 97-2003 de verdade
_PADRAO_INTEIRO = re.compile(r"-?\d+")
_PADRAO_NUMERO_BR = re.compile(r"-?\d{1,3}(?:\.\d{3})*,\d+|-?\d+,\d+")
_PADRAO_MES_ABREVIADO = re.compile(r"([a-zç]{3})/(\d{4})", re.IGNORECASE)
_MESES = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
          "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}


def celula_do_texto(celula: str):
    """Converte uma célula do texto do Tasy como o Excel faria ao abrir o arquivo.

    "" -> None; "017161" -> 17161; "30.712.933,62" -> Decimal; "out/2026" -> data (01/10/2026);
    o resto continua texto, do jeito que veio.
    """
    limpo = celula.strip()
    if limpo == "":
        return None
    if _PADRAO_INTEIRO.fullmatch(limpo):
        return int(limpo)
    if _PADRAO_NUMERO_BR.fullmatch(limpo):
        return Decimal(limpo.replace(".", "").replace(",", "."))
    mes = _PADRAO_MES_ABREVIADO.fullmatch(limpo)
    if mes and mes.group(1).lower() in _MESES:
        return datetime.datetime(int(mes.group(2)), _MESES[mes.group(1).lower()], 1)
    return celula


class _Celula:
    __slots__ = ("row", "column", "value")

    def __init__(self, row, column, value):
        self.row, self.column, self.value = row, column, value


class _AbaTexto:
    """Aba montada a partir do texto do Tasy, com o mesmo jeito de ler de uma aba do openpyxl."""

    def __init__(self, titulo: str, linhas: list[list]):
        self.title = titulo
        self._linhas = linhas

    def iter_rows(self, values_only: bool = False):
        for numero, linha in enumerate(self._linhas, start=1):
            if values_only:
                yield tuple(linha)
            else:
                celulas = tuple(_Celula(numero, coluna, valor) for coluna, valor in enumerate(linha, start=1))
                yield celulas or (_Celula(numero, 1, None),)


class _PastaTexto:
    def __init__(self, aba: _AbaTexto):
        self.worksheets = [aba]

    def close(self):
        pass


def abrir_relatorio_tasy(caminho):
    """Abre o balancete ou o patrimônio: o .xls (texto) como sai do Tasy ou o .xlsx salvo no Excel."""
    caminho = Path(caminho)
    nome = caminho.name
    if not caminho.exists():
        raise ErroArquivo(f"Arquivo não encontrado: {nome}")
    try:
        conteudo = caminho.read_bytes()
    except PermissionError:
        raise ErroArquivo(f"{nome}: sem permissão para abrir. Feche o arquivo no Excel e tente de novo.")
    if conteudo.startswith(_ASSINATURA_XLS_BINARIO):
        raise ErroArquivo(
            f"{nome}: é um Excel antigo (.xls 97-2003) e não o arquivo como sai do Tasy. "
            "Use o arquivo exportado pelo Tasy, ou abra no Excel e use 'Salvar como' > "
            "'Pasta de Trabalho do Excel (.xlsx)'."
        )
    if conteudo.startswith(_ASSINATURA_ZIP):
        try:
            return openpyxl.load_workbook(io.BytesIO(conteudo), data_only=True)
        except (zipfile.BadZipFile, KeyError, OSError, ValueError) as erro:
            raise ErroArquivo(f"{nome}: não foi possível abrir (arquivo corrompido). Detalhe: {erro}")
    texto = conteudo.decode(_CODIFICACAO_TASY, errors="replace")
    # Descrição com quebra de linha vem entre aspas e continua na linha de baixo ("Lentes ... C-Mount
    # <quebra>"): como o Excel, o leitor de CSV junta tudo numa célula só e a linha do bem não se perde.
    leitor = csv.reader(io.StringIO(texto, newline=""), delimiter=_SEPARADOR_TASY, quotechar='"')
    linhas = [[celula_do_texto(c) for c in linha] for linha in leitor]
    return _PastaTexto(_AbaTexto(caminho.stem[:31], linhas))


def abrir_planilha(caminho, somente_valores: bool = True, manter_vinculos: bool = False):
    """Abre um .xlsx com openpyxl, trocando os erros técnicos por mensagens claras (ErroArquivo)."""
    caminho = Path(caminho)
    nome = caminho.name
    if not caminho.exists():
        raise ErroArquivo(f"Arquivo não encontrado: {nome}")
    if caminho.suffix.lower() == ".xls":
        raise ErroArquivo(
            f"{nome}: a planilha a preencher precisa ser .xlsx. "
            "Abra no Excel e use 'Salvar como' > 'Pasta de Trabalho do Excel (.xlsx)'."
        )
    if caminho.suffix.lower() not in configuracao.EXTENSOES_ACEITAS:
        raise ErroArquivo(f"{nome}: formato não suportado (use .xlsx).")
    try:
        return openpyxl.load_workbook(caminho, data_only=somente_valores, keep_links=manter_vinculos)
    except PermissionError:
        raise ErroArquivo(f"{nome}: sem permissão para abrir. Feche o arquivo no Excel e tente de novo.")
    except (zipfile.BadZipFile, KeyError, OSError, ValueError) as erro:
        raise ErroArquivo(f"{nome}: não foi possível abrir (arquivo corrompido ou não é .xlsx). Detalhe: {erro}")
