"""
Leitura comum dos relatórios do Tasy usados na Conciliação do Imobilizado – AME's.

O Tasy salva esses relatórios com extensão .xls, mas o conteúdo é TEXTO separado por
tabulação (Windows-1252). Aqui eles viram uma lista de linhas, cada uma uma lista de células.

As colunas mudam de posição de uma página para outra (a página 2 costuma ter uma
coluna vazia a mais no começo). Por isso os leitores nunca usam posição fixa: acham os
valores pelo rótulo ("Saldo atual") ou pelo nome do cabeçalho ("VL. ORIGEM").
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from modulos.conciliacao_imobilizado.base_iss import valor_prefeitura

Linhas = list[list[str]]

# Tipos de relatório (para reconhecer arquivo escolhido no lugar errado)
RELATORIO_RAZAO = "razao"
RELATORIO_BALANCETE = "balancete"
RELATORIO_BENS_ADQUIRIDOS = "bens_adquiridos"
RELATORIO_BAIXAS = "baixas"

NOMES_RELATORIOS = {
    RELATORIO_RAZAO: "o Razão auxiliar do patrimônio (Tasy 6051)",
    RELATORIO_BALANCETE: "um Balancete (Tasy 865)",
    RELATORIO_BENS_ADQUIRIDOS: "o relatório de Bens adquiridos (Tasy 555)",
    RELATORIO_BAIXAS: "o relatório de Baixa de bens (Tasy 561)",
}
CAMPOS_RELATORIOS = {
    RELATORIO_RAZAO: "Patrimônio (6051)",
    RELATORIO_BALANCETE: "Balancetes (865)",
    RELATORIO_BENS_ADQUIRIDOS: "Bens adquiridos (555)",
    RELATORIO_BAIXAS: "Baixa de bens (561)",
}

_MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
MESES_POR_EXTENSO = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
                     "agosto", "setembro", "outubro", "novembro", "dezembro"]
_REGEX_DATA = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_REGEX_MES_ANO = re.compile(r"^([a-zç]{3})/(\d{4})$", re.IGNORECASE)
_REGEX_VALOR = re.compile(r"^-?[\d.]+,\d{2}$")
_BYTES_XLS_BINARIO = b"\xd0\xcf\x11\xe0"
_BYTES_XLSX = b"PK"


class ArquivoIlegivel(Exception):
    """O arquivo não pôde ser aberto ou não está no formato esperado (mensagem para a tela)."""


def ler_linhas(caminho: Path) -> Linhas:
    """Arquivo → linhas de células (texto, sem espaços nas pontas). Erro → ArquivoIlegivel."""
    caminho = Path(caminho)
    try:
        bruto = caminho.read_bytes()
    except OSError as erro:
        raise ArquivoIlegivel(f"Não foi possível abrir o arquivo: {erro.strerror or erro}.") from erro
    if bruto.startswith(_BYTES_XLS_BINARIO) or bruto.startswith(_BYTES_XLSX):
        raise ArquivoIlegivel(
            "O arquivo parece ter sido aberto e salvo de novo no Excel. "
            "Use o arquivo do jeito que sai do Tasy (sem abrir e salvar)."
        )
    for codificacao in ("utf-8", "cp1252"):
        try:
            texto = bruto.decode(codificacao)
            break
        except UnicodeDecodeError:
            continue
    else:
        texto = bruto.decode("latin-1")
    texto = texto.lstrip("﻿")
    return [[celula.replace("\xa0", " ").strip() for celula in linha.split("\t")]
            for linha in texto.splitlines()]


def preenchidas(linha: list[str]) -> list[str]:
    """Só as células com conteúdo, na ordem."""
    return [c for c in linha if c]


def juntar_espacos(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip()


def identificar_relatorio(linhas: Linhas) -> str | None:
    """Qual dos quatro relatórios é este (pelo título e pelo código do relatório no rodapé)."""
    texto = " ".join(c for linha in linhas[:60] for c in linha if c).casefold()
    if "razão auxiliar" in texto or "cate6051" in texto:
        return RELATORIO_RAZAO
    if "baixa de bens do ativo imobilizado" in texto or "cate561" in texto:
        return RELATORIO_BAIXAS
    if "bens adquiridos" in texto or "cate555" in texto:
        return RELATORIO_BENS_ADQUIRIDOS
    if "balancete" in texto or "wctb865" in texto:
        return RELATORIO_BALANCETE
    return None


def erro_relatorio_errado(esperado: str, encontrado: str | None) -> str | None:
    """Mensagem quando o arquivo é outro relatório (None se for o esperado)."""
    if encontrado == esperado:
        return None
    if encontrado is None:
        return (f"Este arquivo não parece ser {NOMES_RELATORIOS[esperado]}. "
                "Confira se escolheu o relatório certo do Tasy.")
    return (f"Este arquivo é {NOMES_RELATORIOS[encontrado]}, não {NOMES_RELATORIOS[esperado]}. "
            f"Escolha-o no campo \"{CAMPOS_RELATORIOS[encontrado]}\".")


def valor(texto: str) -> Decimal | None:
    """"1.234,56" → Decimal("1234.56"); vazio → None; formato inesperado → ValueError."""
    return valor_prefeitura(texto)


def reais(numero: Decimal | None) -> str:
    """Decimal("1234.5") → "1.234,50" (para as mensagens)."""
    if numero is None:
        return "—"
    texto = f"{numero:,.2f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


def parece_valor(texto: str) -> bool:
    return bool(_REGEX_VALOR.match(texto.strip()))


def data(texto: str) -> date | None:
    """"01/08/2026" → date; outro formato → None."""
    encontrado = _REGEX_DATA.match(texto.strip())
    if not encontrado:
        return None
    dia, mes, ano = (int(p) for p in encontrado.groups())
    try:
        return date(ano, mes, dia)
    except ValueError:
        return None


def competencia_de_mes_ano(texto: str) -> str:
    """"ago/2026" → "2026-08"; outro formato → ""."""
    encontrado = _REGEX_MES_ANO.match(texto.strip())
    if not encontrado or encontrado.group(1).lower() not in _MESES:
        return ""
    return f"{encontrado.group(2)}-{_MESES.index(encontrado.group(1).lower()) + 1:02d}"


def competencia_de_data(dia: date | None) -> str:
    return "" if dia is None else f"{dia.year}-{dia.month:02d}"


def competencia_por_extenso(competencia: str) -> str:
    """"2026-08" → "agosto/2026"."""
    if not re.match(r"^\d{4}-\d{2}$", competencia or ""):
        return ""
    ano, mes = competencia.split("-")
    return f"{MESES_POR_EXTENSO[int(mes) - 1]}/{ano}"


def depois_do_rotulo(linha: list[str], rotulo: str) -> str:
    """Primeira célula preenchida depois da célula `rotulo` (comparação sem maiúsculas)."""
    alvo = rotulo.casefold()
    for posicao, celula in enumerate(linha):
        if celula.casefold() == alvo:
            return next((c for c in linha[posicao + 1:] if c), "")
    return ""


def eh_rodape(linha: list[str]) -> bool:
    """"Impresso em: 06/10/2026 ..." (fim de página)."""
    return any(c.startswith("Impresso em") for c in linha)


def nome_curto_ame(ame: str) -> str:
    """"Ame - Cidade Alfa ( Fund. Hospital Exemplo ... )" → "Ame - Cidade Alfa"."""
    return juntar_espacos(ame.split("(")[0]) or juntar_espacos(ame)


class Cabecalho:
    """
    Linha de cabeçalho com colunas localizadas pelo NOME.

    Cada coluna "é dona" das células que vão da sua posição até antes da próxima coluna:
    o valor é a primeira célula preenchida nesse trecho. Assim uma descrição que começa
    duas células depois do título ("IMOBILIZADO") ainda é achada.
    """

    def __init__(self, linha: list[str]):
        self.posicoes = [(c.casefold(), i) for i, c in enumerate(linha) if c]

    def tem(self, *nomes: str) -> bool:
        presentes = {nome for nome, _ in self.posicoes}
        return all(n.casefold() in presentes for n in nomes)

    def valor(self, linha: list[str], nome: str) -> str:
        alvo = nome.casefold()
        for indice, (atual, inicio) in enumerate(self.posicoes):
            if atual != alvo:
                continue
            fim = self.posicoes[indice + 1][1] if indice + 1 < len(self.posicoes) else len(linha)
            return next((c for c in linha[inicio:fim] if c), "")
        return ""
