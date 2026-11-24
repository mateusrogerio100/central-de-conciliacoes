"""
Lista os PDFs a imprimir e conta as páginas de cada um (ESPECIFICACAO seção 19).

Cada página é uma folha: a impressão é sempre de um lado só (decisão do usuário, out/2026 — o
frente e verso, quando preciso, ele escolhe na própria impressora). Um PDF que não abre
(corrompido, com senha) não derruba a lista: fica com o erro e não entra na conta de folhas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PdfParaImprimir:
    """Um PDF escolhido: o caminho, quantas páginas tem e, se não abriu, o motivo.

    `escolhidas`: as páginas a imprimir (contadas a partir de 1), quando não são todas — ex.: só a
    primeira de um PDF de duas páginas (pedido do usuário, out/2026). None = todas.
    """

    caminho: Path
    paginas: int = 0
    erro: str = ""
    escolhidas: tuple[int, ...] | None = None

    @property
    def nome(self) -> str:
        return self.caminho.name

    @property
    def pode_imprimir(self) -> bool:
        return not self.erro and self.paginas > 0

    def paginas_para_imprimir(self) -> list[int]:
        """As páginas que vão para a impressora (a partir de 1), em ordem e sem repetir."""
        if self.escolhidas is None:
            return list(range(1, self.paginas + 1))
        return sorted(set(self.escolhidas))

    @property
    def folhas(self) -> int:
        """Folhas que este PDF gasta: uma por página escolhida (impressão de um lado só)."""
        return len(self.paginas_para_imprimir()) if self.pode_imprimir else 0


def _chave_natural(caminho: Path) -> list:
    """Ordem do Explorador do Windows: números comparados como números ("1546" antes de "12206")."""
    partes = re.split(r"(\d+)", caminho.name.casefold())
    return [(0, int(p), "") if p.isdigit() else (1, 0, p) for p in partes]


def ordenar_como_no_windows(caminhos) -> list[Path]:
    return sorted((Path(c) for c in caminhos), key=_chave_natural)


def contar_paginas(caminho: Path) -> int:
    """Quantidade de páginas do PDF. Erro do pdfium (arquivo ruim, com senha) sobe como exceção."""
    import pypdfium2

    documento = pypdfium2.PdfDocument(str(caminho))
    try:
        return len(documento)
    finally:
        documento.close()


def _motivo(erro: Exception) -> str:
    texto = str(erro).casefold()
    if "password" in texto:
        return "PDF protegido por senha"
    if isinstance(erro, FileNotFoundError) or "no such file" in texto or "not found" in texto:
        return "arquivo não encontrado"
    return "não foi possível abrir o PDF (arquivo danificado ou não é PDF)"


def ler_pdf(caminho) -> PdfParaImprimir:
    caminho = Path(caminho)
    if not caminho.is_file():
        return PdfParaImprimir(caminho, erro="arquivo não encontrado")
    try:
        paginas = contar_paginas(caminho)
    except Exception as erro:  # o pdfium avisa qualquer problema do arquivo com exceção
        return PdfParaImprimir(caminho, erro=_motivo(erro))
    if paginas == 0:
        return PdfParaImprimir(caminho, erro="o PDF não tem nenhuma página")
    return PdfParaImprimir(caminho, paginas)


def ler_pdfs(caminhos) -> list[PdfParaImprimir]:
    """Lê os PDFs na ordem do Explorador do Windows, sem repetir o mesmo arquivo."""
    vistos: set[str] = set()
    pdfs = []
    for caminho in ordenar_como_no_windows(caminhos):
        chave = str(caminho.resolve()).casefold()
        if chave in vistos:
            continue
        vistos.add(chave)
        pdfs.append(ler_pdf(caminho))
    return pdfs


def pdfs_da_pasta(pasta) -> list[PdfParaImprimir]:
    """Todos os PDFs de uma pasta (sem entrar nas subpastas)."""
    pasta = Path(pasta)
    return ler_pdfs(c for c in pasta.iterdir() if c.is_file() and c.suffix.casefold() == ".pdf")


def total_de_folhas(pdfs) -> int:
    return sum(p.folhas for p in pdfs)


def resumo(pdfs) -> str:
    """'16 PDFs · 18 folhas' (os que não abriram ficam fora da conta)."""
    validos = [p for p in pdfs if p.pode_imprimir]
    folhas = total_de_folhas(validos)
    texto = f"{len(validos)} PDF{'s' if len(validos) != 1 else ''} · {folhas} folha{'s' if folhas != 1 else ''}"
    com_erro = len(pdfs) - len(validos)
    if com_erro:
        texto += f" · {com_erro} com problema"
    return texto
