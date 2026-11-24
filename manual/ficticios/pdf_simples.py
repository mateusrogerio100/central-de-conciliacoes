"""Grava PDFs com texto (o que os leitores dos módulos procuram), sem biblioteca nova: usa o pypdfium2.

Cada linha vira um objeto de texto na posição pedida; o pdfplumber lê de volta o mesmo texto, com
acentos. Fonte Courier (largura fixa) por padrão, para as colunas ficarem alinhadas como nos
relatórios do Tasy.
"""

from __future__ import annotations

import ctypes
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as raw

A4 = (595, 842)                          # pontos (1/72 pol.)
MARGEM_ESQUERDA = 28
MARGEM_TOPO = 36


def _escrever(documento, pagina, x: float, y: float, texto: str, fonte: str, tamanho: float) -> None:
    objeto = raw.FPDFPageObj_NewTextObj(documento.raw, fonte.encode("ascii"), ctypes.c_float(tamanho))
    buffer = ctypes.create_string_buffer((texto + "\0").encode("utf-16-le"))
    raw.FPDFText_SetText(objeto, ctypes.cast(buffer, ctypes.POINTER(raw.FPDF_WCHAR)))
    raw.FPDFPageObj_Transform(objeto, 1, 0, 0, 1, x, y)
    raw.FPDFPage_InsertObject(pagina.raw, objeto)


def gravar_pdf(caminho: Path, paginas: list[list[str]], fonte: str = "Courier", tamanho: float = 7.5,
               entrelinha: float = 11, tamanho_pagina: tuple[int, int] = A4) -> Path:
    """paginas: as linhas de texto de cada página, de cima para baixo."""
    largura, altura = tamanho_pagina
    documento = pdfium.PdfDocument.new()
    for linhas in paginas:
        pagina = documento.new_page(largura, altura)
        y = altura - MARGEM_TOPO
        for linha in linhas:
            if linha.strip():
                _escrever(documento, pagina, MARGEM_ESQUERDA, y, linha, fonte, tamanho)
            y -= entrelinha
        raw.FPDFPage_GenerateContent(pagina.raw)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    documento.save(caminho)
    documento.close()
    return caminho


def gravar_pdf_posicionado(caminho: Path, paginas: list[list[tuple[float, float, str]]], fonte: str = "Helvetica",
                           tamanho: float = 8, tamanho_pagina: tuple[int, int] = A4) -> Path:
    """paginas: (x, y a partir do topo, texto) de cada pedaço, para leitores que usam a posição na página."""
    largura, altura = tamanho_pagina
    documento = pdfium.PdfDocument.new()
    for pedacos in paginas:
        pagina = documento.new_page(largura, altura)
        for x, y, texto in pedacos:
            _escrever(documento, pagina, x, altura - y, texto, fonte, tamanho)
        raw.FPDFPage_GenerateContent(pagina.raw)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    documento.save(caminho)
    documento.close()
    return caminho
