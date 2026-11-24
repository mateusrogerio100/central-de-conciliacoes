"""Trechos do pacote conferencia/ (Conferência ISS) do Conciliações AMES usados pelo Imobilizado,
COPIADOS sem nenhuma mudança (um módulo da Central nunca importa outro; ESPECIFICACAO, seção 5.7).

Origem de cada trecho (conciliacoes_ames/conferencia/, versão 2.14.0):
- modelos.py, linhas 57 a 60
- modelos.py, linhas 184 a 202
- normalizar.py, linhas 18 a 18
- normalizar.py, linhas 55 a 68
- normalizar.py, linhas 83 a 92
- processar.py, linhas 35 a 38
- processar.py, linhas 263 a 293
- relatorio_excel.py, linhas 61 a 72
- relatorio_excel.py, linhas 284 a 284
- relatorio_excel.py, linhas 328 a 332
- relatorio_excel.py, linhas 343 a 357
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


# --- modelos.py, linhas 57-60 ---
# Níveis de aviso
NIVEL_OK = "OK"
NIVEL_AVISO = "Aviso"
NIVEL_ERRO = "Erro"


# --- modelos.py, linhas 184-202 ---
@dataclass
class Aviso:
    """
    Um registro da aba Avisos.

    Avisos de arquivo trazem tipo_arquivo, linhas_lidas e unidades;
    avisos de nota/linha trazem só arquivo e mensagem.
    """

    arquivo: str
    mensagem: str                    # "OK" ou a descrição do problema
    nivel: str = NIVEL_AVISO         # NIVEL_OK, NIVEL_AVISO ou NIVEL_ERRO
    tipo_arquivo: str = ""           # TIPO_ARQUIVO_TASY ou TIPO_ARQUIVO_PREFEITURA
    linhas_lidas: int | None = None
    unidades: str = ""

    @property
    def eh_erro(self) -> bool:
        return self.nivel == NIVEL_ERRO


# --- normalizar.py, linhas 18-18 ---
_REGEX_DECIMAL = re.compile(r"^-?\d+(\.\d+)?$")


# --- normalizar.py, linhas 55-68 ---
def _para_decimal(texto: str, original: str) -> Decimal:
    if not _REGEX_DECIMAL.match(texto):
        raise ValueError(f"Valor inválido: {original!r}")
    try:
        return Decimal(texto)
    except InvalidOperation as erro:
        raise ValueError(f"Valor inválido: {original!r}") from erro


def _limpar(texto: str | None) -> str:
    """Tira espaços comuns e o &nbsp; (\\xa0) que a prefeitura usa para vazio."""
    if texto is None:
        return ""
    return texto.replace("\xa0", " ").strip()


# --- normalizar.py, linhas 83-92 ---
def valor_prefeitura(texto: str | None) -> Decimal | None:
    """
    Valor da prefeitura: "1.234,56" (ponto de milhar, vírgula decimal) → Decimal("1234.56").

    Vazio ou &nbsp; → None. Formato inesperado → ValueError.
    """
    limpo = _limpar(texto)
    if not limpo:
        return None
    return _para_decimal(limpo.replace(".", "").replace(",", "."), texto)


# --- processar.py, linhas 35-38 ---
PREFIXO_ARQUIVO = "Conferencia_ISS_RB"        # padrão (Cidade Beta)
NOME_VARIAS_UNIDADES = "Varias_unidades"
NOME_SEM_UNIDADE = "Sem_unidade"
NOME_SEM_COMPETENCIA = "sem_competencia"


# --- processar.py, linhas 263-293 ---
def nome_para_arquivo(texto: str) -> str:
    """"AME Cidade Beta" → "AME_Cidade_Beta" (sem acentos; espaços → _)."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    limpo = re.sub(r"[^A-Za-z0-9._-]+", "_", sem_acento.strip())
    return re.sub(r"_+", "_", limpo).strip("_.")


def nome_do_relatorio(competencia: str, unidades: list[str], agora: datetime,
                      prefixo: str = PREFIXO_ARQUIVO) -> str:
    """Conferencia_ISS_RB_<AAAA-MM>_<Unidade>_<HHhMM>.xlsx (ou Conferencia_ISS_SJ_...)"""
    if len(unidades) > 1:
        unidade = NOME_VARIAS_UNIDADES
    elif unidades:
        unidade = nome_para_arquivo(unidades[0]) or NOME_SEM_UNIDADE
    else:
        unidade = NOME_SEM_UNIDADE
    return f"{prefixo}_{competencia or NOME_SEM_COMPETENCIA}_{unidade}_{agora:%Hh%M}.xlsx"


def caminho_do_relatorio(pasta: Path, competencia: str, unidades: list[str],
                         agora: datetime, prefixo: str = PREFIXO_ARQUIVO) -> Path:
    """Caminho livre na pasta: se o nome já existe, acrescenta _2, _3..."""
    original = Path(pasta) / nome_do_relatorio(competencia, unidades, agora, prefixo)
    caminho = original
    contador = 2
    while caminho.exists():
        caminho = original.with_name(f"{original.stem}_{contador}{original.suffix}")
        contador += 1
    return caminho


# --- relatorio_excel.py, linhas 61-72 ---
COR_GERAL = "0E3B3E"          # tema.COR_MENU_FUNDO  — Situação, Diferença, Resumo
COR_TASY = "0F5C63"           # tema.COR_PRINCIPAL   — colunas do Tasy
COR_PREFEITURA = "E7B75F"     # tema.COR_MARCA       — colunas da prefeitura
COR_TEXTO_CLARO = "FFFFFF"
COR_TEXTO_ESCURO = "1B2424"   # tema.COR_TEXTO
COR_OK = "1B6E45"             # tema.COR_OK
COR_ERRO = "B42318"           # tema.COR_ERRO

FORMATO_VALOR = "#,##0.00"
FORMATO_DATA = "DD/MM/YYYY"
FORMATO_TEXTO = "@"
LARGURA_MAXIMA = 50


# --- relatorio_excel.py, linhas 284-284 ---
COLUNAS_AVISOS = ["Arquivo", "Tipo", "Nível", "Linhas lidas", "Unidade(s)", "Mensagem"]


# --- relatorio_excel.py, linhas 328-332 ---
def _estilo_cabecalho(celula, cor: str) -> None:
    texto = COR_TEXTO_ESCURO if cor == COR_PREFEITURA else COR_TEXTO_CLARO
    celula.font = Font(bold=True, color=texto)
    celula.fill = PatternFill("solid", start_color=cor, end_color=cor)
    celula.alignment = Alignment(vertical="center", wrap_text=True)


# --- relatorio_excel.py, linhas 343-357 ---
def _ajustar_larguras(aba, primeira_linha: int = 1) -> None:
    larguras: dict[int, int] = {}
    for linha in aba.iter_rows(min_row=primeira_linha):
        for celula in linha:
            if celula.value is None:
                continue
            if isinstance(celula.value, (int, float, Decimal)):
                tamanho = len(f"{celula.value:,.2f}")
            elif isinstance(celula.value, (date, datetime)):
                tamanho = 10
            else:
                tamanho = max(len(parte) for parte in str(celula.value).split("\n"))
            larguras[celula.column] = max(larguras.get(celula.column, 0), tamanho)
    for coluna, tamanho in larguras.items():
        aba.column_dimensions[get_column_letter(coluna)].width = min(tamanho + 2, LARGURA_MAXIMA)
