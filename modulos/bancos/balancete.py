"""Leitor do balancete contábil (relatório WEXE001 do Tasy).

Aceita o arquivo como ele sai do Tasy (".xls" que na verdade é texto separado por tabulação,
em cp1252) ou já salvo no Excel como .xlsx. O formato é reconhecido pelo CONTEÚDO, não pela
extensão (mesma ideia do leitor do módulo Estoque, copiada aqui: um módulo não importa outro).

Lê só as contas bancárias analíticas (último nível) dos grupos:
  1.01.01.02.  Depósitos bancários (conta movimento)
  1.01.01.03.  Aplicações financeiras
  1.01.01.04.  Poupança
"""

import calendar
import io
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import openpyxl
from openpyxl.utils.datetime import from_excel

from .modelos import ContaBalancete
from .util import normalizar_conta, valor_de_float

PREFIXOS_BANCARIOS = ("1.01.01.02.", "1.01.01.03.", "1.01.01.04.")

# Conta analítica = classificação com 6 partes (ex.: 1.01.01.02.01.0003).
_PADRAO_ANALITICA = re.compile(r"\d+(?:\.\d+){5}")

# Textos do cabeçalho que identificam cada coluna usada.
COLUNA_CODIGO = "codigo"
COLUNA_CLASSIFICACAO = "classificacao"
COLUNA_DESCRICAO = "descricao"
COLUNA_SALDO_ATUAL = "saldo atual"
_COLUNAS_OBRIGATORIAS = (COLUNA_CODIGO, COLUNA_CLASSIFICACAO,
                         COLUNA_DESCRICAO, COLUNA_SALDO_ATUAL)

# Descrição: "<BANCO> <TIPO> <NÚMERO>[ texto livre]".
_PADRAO_DESCRICAO = re.compile(
    r"^(?P<banco>\S+)\s+(?P<tipo>\S+)\s+(?P<numero>\d[\d.]*(?:-[0-9xX])?)(?=\s|$)"
)
BANCOS = {"BB": "BB", "SICOOB": "SICOOB", "CEF": "CEF", "SANTANDER": "SANTANDER"}
# "S/A" (Sociedade Anônima, o regime da empresa) aparece em algumas contas
# correntes, ex.: "BB S/A 5749-5"; confirmado pelo autor que é conta corrente.
TIPOS_DESCRICAO = {"C/C": "CC", "S/A": "CC", "APLICACAO": "APLICACAO", "POUPANCA": "POUPANCA"}


@dataclass
class Balancete:
    competencia: date                  # 1º dia do mês de referência
    contas: list[ContaBalancete] = field(default_factory=list)

    @property
    def data_referencia(self) -> date:
        """Último dia do mês de competência (data dos saldos)."""
        ultimo_dia = calendar.monthrange(self.competencia.year,
                                         self.competencia.month)[1]
        return self.competencia.replace(day=ultimo_dia)


def _simplificar(texto) -> str:
    """Minúsculas, sem acento e sem espaços nas pontas (para comparar)."""
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.strip().lower()


# Texto do Tasy: tabulação, cp1252, números no formato brasileiro ("48.980.877,93", "-6.569,00").
_SEPARADOR_TASY = "\t"
_CODIFICACAO_TASY = "cp1252"
_ASSINATURA_ZIP = b"PK"                     # .xlsx
_ASSINATURA_XLS_BINARIO = b"\xd0\xcf\x11\xe0"  # Excel 97-2003 de verdade
_PADRAO_NUMERO_BR = re.compile(r"-?\d{1,3}(?:\.\d{3})*,\d+|-?\d+,\d+")
_MESES = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
          "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}


def ler_linhas(arquivo: Path) -> list[list]:
    """Linhas do balancete, cada uma uma lista de células (None = vazia)."""
    arquivo = Path(arquivo)
    with open(arquivo, "rb") as entrada:
        inicio = entrada.read(4)
    if inicio.startswith(_ASSINATURA_XLS_BINARIO):
        raise ValueError("o arquivo é um Excel antigo (.xls 97-2003): abra no Excel e salve como "
                         ".xlsx, ou use o arquivo como ele sai do Tasy")
    if inicio.startswith(_ASSINATURA_ZIP):
        # pelo conteúdo: o openpyxl recusa um .xlsx que tenha extensão .xls
        pasta = openpyxl.load_workbook(io.BytesIO(arquivo.read_bytes()), data_only=True,
                                       read_only=True)
        try:
            return [list(linha) for linha in pasta.active.iter_rows(values_only=True)]
        finally:
            pasta.close()
    texto = arquivo.read_text(encoding=_CODIFICACAO_TASY, errors="replace")
    return [[_celula_do_texto(c) for c in linha.split(_SEPARADOR_TASY)]
            for linha in texto.splitlines()]


def _celula_do_texto(celula: str):
    """Célula do texto do Tasy: vazia -> None; número brasileiro -> Decimal; resto -> texto."""
    if celula.strip() == "":
        return None
    if _PADRAO_NUMERO_BR.fullmatch(celula.strip()):
        return Decimal(celula.strip().replace(".", "").replace(",", "."))
    return celula


def ler_balancete(arquivo: Path) -> Balancete:
    """Lê o balancete e devolve a competência e as contas bancárias."""
    linhas = ler_linhas(arquivo)

    competencia = _achar_competencia(linhas)
    faixas = _achar_colunas(linhas)

    contas = []
    for linha in linhas:
        classificacao = _valor_na_faixa(linha, faixas[COLUNA_CLASSIFICACAO])
        if classificacao is None:
            continue
        classificacao = str(classificacao).strip()
        if not _PADRAO_ANALITICA.fullmatch(classificacao):
            continue
        if not classificacao.startswith(PREFIXOS_BANCARIOS):
            continue
        contas.append(_montar_conta(linha, classificacao, faixas))

    return Balancete(competencia=competencia, contas=contas)


def _achar_competencia(linhas) -> date:
    """Acha "Mês Referência:" e lê a data na primeira célula preenchida à direita."""
    for linha in linhas:
        for i, celula in enumerate(linha):
            if celula is None or not _simplificar(celula).startswith("mes referencia"):
                continue
            valor = next((v for v in linha[i + 1:] if v is not None), None)
            data = _converter_data(valor)
            if data is None:
                raise ValueError(f"'Mês Referência' com valor não reconhecido: {valor!r}")
            return data.replace(day=1)
    raise ValueError("balancete sem 'Mês Referência'")


def _converter_data(valor) -> date | None:
    # O Excel pode entregar a data já como data, ou como número serial
    # (ex.: 46235 = 01/08/2026), dependendo da formatação da célula.
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, (int, float)):
        return from_excel(valor).date()
    if isinstance(valor, str):
        # texto do Tasy: "set/2026" (ou "01/09/2026")
        achado = re.fullmatch(r"\s*([a-zA-Z]{3})/(\d{4})\s*", valor)
        if achado and _simplificar(achado[1]) in _MESES:
            return date(int(achado[2]), _MESES[_simplificar(achado[1])], 1)
        achado = re.fullmatch(r"\s*(\d{2})/(\d{2})/(\d{4})\s*", valor)
        if achado:
            return date(int(achado[3]), int(achado[2]), int(achado[1]))
    return None


def _achar_colunas(linhas) -> dict[str, range]:
    """Localiza as colunas pelo texto do cabeçalho.

    No relatório o rótulo do cabeçalho nem sempre fica na mesma coluna do
    dado (ex.: "Código" na coluna B e os códigos na C). Por isso cada
    coluna vai do seu rótulo até antes do rótulo seguinte.
    """
    for linha in linhas:
        rotulos = {_simplificar(v): i for i, v in enumerate(linha) if v is not None}
        if not all(nome in rotulos for nome in _COLUNAS_OBRIGATORIAS):
            continue
        inicios = sorted(rotulos.values())
        faixas = {}
        for nome in _COLUNAS_OBRIGATORIAS:
            inicio = rotulos[nome]
            seguintes = [i for i in inicios if i > inicio]
            fim = seguintes[0] if seguintes else len(linha)
            faixas[nome] = range(inicio, fim)
        return faixas
    raise ValueError(
        "cabeçalho do balancete não encontrado (esperado: Código, "
        "Classificação, Descrição e Saldo Atual na mesma linha)"
    )


def _valor_na_faixa(linha, faixa: range):
    """Primeira célula preenchida dentro da faixa de colunas."""
    for i in faixa:
        if i < len(linha) and linha[i] is not None and str(linha[i]).strip() != "":
            return linha[i]
    return None


def _montar_conta(linha, classificacao: str, faixas) -> ContaBalancete:
    codigo = _valor_na_faixa(linha, faixas[COLUNA_CODIGO])
    if isinstance(codigo, float) and codigo.is_integer():
        codigo = int(codigo)
    if isinstance(codigo, Decimal):
        codigo = int(codigo)
    codigo = "" if codigo is None else str(codigo).strip()

    descricao = _valor_na_faixa(linha, faixas[COLUNA_DESCRICAO])
    descricao = "" if descricao is None else str(descricao).strip()

    saldo = _valor_na_faixa(linha, faixas[COLUNA_SALDO_ATUAL])
    if not isinstance(saldo, (int, float, Decimal)):
        raise ValueError(
            f"conta {codigo} ({classificacao}) com Saldo Atual inválido: {saldo!r}"
        )

    banco, tipo, conta = interpretar_descricao(descricao)
    return ContaBalancete(
        codigo=codigo,
        classificacao=classificacao,
        descricao=descricao,
        banco=banco,
        tipo=tipo,
        conta=conta,
        saldo_atual=(saldo.quantize(Decimal("0.01")) if isinstance(saldo, Decimal)
                     else valor_de_float(saldo)),
    )


def interpretar_descricao(descricao: str) -> tuple[str, str, str]:
    """Extrai (banco, tipo, conta normalizada) da descrição da conta.

    "BB C/C 8036-5"                  -> ("BB", "CC", "80365")
    "BB Aplicação 400759-x - Res..." -> ("BB", "APLICACAO", "400759X")
    "BB S/A 5749-5"                  -> ("BB", "CC", "57495")

    Se a descrição não seguir o padrão, devolve ("", "", "") — a conta
    aparece no relatório como "descrição não reconhecida".
    """
    achado = _PADRAO_DESCRICAO.match(descricao.strip())
    if not achado:
        return "", "", ""
    banco = BANCOS.get(_simplificar(achado["banco"]).upper())
    if banco is None:
        return "", "", ""
    tipo = TIPOS_DESCRICAO.get(_simplificar(achado["tipo"]).upper(), "OUTRO")
    return banco, tipo, normalizar_conta(achado["numero"])
