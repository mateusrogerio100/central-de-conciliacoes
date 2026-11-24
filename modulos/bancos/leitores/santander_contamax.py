"""Leitor: Santander — ContaMax empresarial (Posição Consolidada Mensal).

A tabela tem uma linha por mês (ex.: Julho, Agosto, Setembro). O texto
corrido do PDF não serve para lê-la: o Santander corta o conteúdo na borda
de cada célula, e o texto sai grudado ("Agosto 202155.447,14") ou com
dígitos a menos em valores grandes. Por isso a leitura usa a POSIÇÃO de
cada caractere na página:

  1. as bordas das colunas vêm da tabela do cabeçalho (linhas desenhadas
     no PDF), e cada coluna é localizada pelo texto do cabeçalho
     ("Saldo Bruto Final", "Resgates Brutos"...), não pela ordem;
  2. cada caractere de cada linha vai para a coluna onde ele está.

(O extract_table do pdfplumber foi testado e perde linhas desta tabela.)

Conferência: pela nota (3) do próprio extrato,
    Saldo Bruto Final = Anterior + Aplicações + Rendimento Total - Resgates.
Se a conta não fechar (ex.: valor cortado pelo banco), a leitura para.

PDF salvo pelo navegador (ajuste de 04/11/2026): a tabela sai mais estreita e o ano do mês vaza
para a coluna ao lado ("Outubro 20" + "2 0,00" no Saldo Bruto Anterior; "Novembro" com o ano
inteiro fora). Por isso o valor de cada célula é o último pedaço dela, e o mês sem ano vale
quando for a única linha daquele mês (a tabela traz três meses seguidos).
"""

import re
import unicodedata
from datetime import date
from decimal import Decimal
from pathlib import Path

import pdfplumber

from ..modelos import SaldoExtraido
from ..util import converter_valor, normalizar_conta, numero_do_mes
from .base import LeitorBase, LeituraError, buscar

# Texto do cabeçalho de cada coluna usada (minúsculas, sem acento).
CABECALHOS = {
    "mes": "mes",
    "anterior": "saldo bruto anterior",
    "aplicacoes": "aplicacoes (r$)",
    "resgates": "resgates brutos",
    "rendimento_total": "total no mes",
    "final": "saldo bruto final",
}

# Tolerância (em pontos) para considerar dois caracteres na mesma linha.
_TOLERANCIA_LINHA = 2


class LeitorSantanderContaMax(LeitorBase):
    nome = "Santander - ContaMax"
    banco = "SANTANDER"

    def reconhece(self, texto: str) -> bool:
        return "ContaMax empresarial" in texto and "Posição Consolidada Mensal" in texto

    def ler(self, texto: str, arquivo: Path, competencia: date) -> list[SaldoExtraido]:
        conta = buscar(r"Conta:\s*(\d[\d.\-]*[0-9Xx])\b", texto, "número da conta").group(1)
        linhas = linhas_da_tabela(arquivo)
        return [SaldoExtraido(
            banco=self.banco,
            tipo="APLICACAO",
            conta=normalizar_conta(conta),
            conta_original=conta,
            saldo_total=saldo_do_mes(linhas, competencia),
            arquivo=arquivo,
            modelo=self.nome,
        )]


def saldo_do_mes(linhas: list[dict[str, str]], competencia: date) -> Decimal:
    """Saldo Bruto Final da linha do mês de competência.

    `linhas`: uma por mês, com o texto de cada coluna (chaves de CABECALHOS).
    """
    escolhidas = []
    for linha in linhas:
        partes = linha["mes"].split()
        if len(partes) not in (1, 2) or numero_do_mes(partes[0]) != competencia.month:
            continue
        # o ano vem cortado: "202" ou "2" valem para 2026; sem ano = cortado inteiro
        if len(partes) == 1 or str(competencia.year).startswith(partes[1]):
            escolhidas.append(linha)
    if not escolhidas:
        raise LeituraError(
            f"linha do mês de competência ({competencia:%m/%Y}) não encontrada na tabela"
        )
    if len(escolhidas) > 1:
        raise LeituraError("mais de uma linha para o mês de competência; não dá para saber o ano")

    linha = escolhidas[0]
    try:
        valores = {chave: converter_valor(_ultimo_pedaco(linha[chave]))
                   for chave in CABECALHOS if chave != "mes"}
    except ValueError as erro:
        raise LeituraError(f"valor ilegível na linha de {linha['mes']}: {erro}")

    esperado = (valores["anterior"] + valores["aplicacoes"]
                + valores["rendimento_total"] - valores["resgates"])
    if esperado != valores["final"]:
        raise LeituraError(
            "a linha do mês não fecha (Anterior + Aplicações + Rendimento − Resgates "
            "≠ Saldo Bruto Final); algum valor pode ter sido cortado no PDF"
        )
    return valores["final"]


def _ultimo_pedaco(texto: str) -> str:
    """"2 0,00" (o ano do mês vazou para a célula) -> "0,00". Um valor nunca tem espaço dentro."""
    pedacos = texto.split()
    return pedacos[-1] if pedacos else texto


def linhas_da_tabela(arquivo: Path) -> list[dict[str, str]]:
    """Lê as linhas de meses da tabela, separando os caracteres por coluna."""
    with pdfplumber.open(arquivo) as pdf:
        for pagina in pdf.pages:
            colunas = _colunas_do_cabecalho(pagina)
            if colunas is None:
                continue
            return _linhas_por_coluna(pagina, colunas)
    raise LeituraError("cabeçalho da tabela 'Posição Consolidada Mensal' não encontrado")


def _simplificar(texto: str | None) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().lower()


def _colunas_do_cabecalho(pagina) -> dict[str, tuple[float, float, float]] | None:
    """{chave: (x inicial, x final, y do fim do cabeçalho)} ou None se não achar."""
    for tabela in pagina.find_tables():
        textos = tabela.extract()
        if not textos or _simplificar(textos[0][0]) != "mes":
            continue
        colunas = {}
        for num_linha, linha in enumerate(textos):
            for num_coluna, texto in enumerate(linha):
                celula = tabela.rows[num_linha].cells[num_coluna]
                if celula is None:
                    continue
                for chave, cabecalho in CABECALHOS.items():
                    if chave not in colunas and _simplificar(texto).startswith(cabecalho):
                        colunas[chave] = (celula[0], celula[2], tabela.bbox[3])
        if len(colunas) == len(CABECALHOS):
            return colunas
    return None


def _linhas_por_coluna(pagina, colunas) -> list[dict[str, str]]:
    fim_cabecalho = min(c[2] for c in colunas.values())
    caracteres = sorted(
        (c for c in pagina.chars if c["top"] >= fim_cabecalho),
        key=lambda c: (c["top"], c["x0"]),
    )

    # Agrupa os caracteres em linhas pela altura na página.
    grupos: list[list[dict]] = []
    for caractere in caracteres:
        if grupos and abs(caractere["top"] - grupos[-1][0]["top"]) <= _TOLERANCIA_LINHA:
            grupos[-1].append(caractere)
        else:
            grupos.append([caractere])

    linhas = []
    for grupo in grupos:
        linha = {chave: "" for chave in colunas}
        for caractere in sorted(grupo, key=lambda c: c["x0"]):
            centro = (caractere["x0"] + caractere["x1"]) / 2
            for chave, (x0, x1, _) in colunas.items():
                if x0 <= centro < x1:
                    linha[chave] += caractere["text"]
        linha = {chave: texto.strip() for chave, texto in linha.items()}
        partes = linha["mes"].split()
        if partes and numero_do_mes(partes[0]):
            linhas.append(linha)
    return linhas
