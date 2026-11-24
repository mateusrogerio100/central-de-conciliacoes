"""Porta de entrada do Imprimir PDFs para a tela (ESPECIFICACAO da Central, seção 4.3).

A regra é a do Conciliações AMES, copiada sem mudanças além dos import (pdfs.py, impressora.py, fila.py;
ESPECIFICACAO_IMPRIMIR_PDFS.md). A única mudança de texto, aprovada pelo usuário (20/10/2026): o nome do
trabalho na fila da impressora passou de "Conciliações AMES – …" para "Central de Conciliações – …".
Aqui só:
- o que a tela usa, reexportado (era o impressao/__init__.py de lá). A tela chama sempre
  processamento.<função>, e os testes trocam essas funções por versões falsas (nenhum teste usa papel);
- a última pasta usada e a impressora escolhida, lembradas entre aberturas (na primeira vez, as do
  Conciliações AMES).
"""

from __future__ import annotations

from pathlib import Path

from central.preferencias import ler_preferencias_modulo, ler_programa_antigo, salvar_preferencias_modulo
from modulos.imprimir_pdfs.fila import EstadoNaFila, abrir_fila, acompanhar, listar_trabalhos  # noqa: F401
from modulos.imprimir_pdfs.impressora import (  # noqa: F401  (reexportados para a tela)
    Envio,
    ErroDeImpressao,
    impressora_padrao,
    imprimir,
    listar_impressoras,
    nome_do_trabalho,
)
from modulos.imprimir_pdfs.pdfs import (  # noqa: F401
    PdfParaImprimir,
    ler_pdf,
    ler_pdfs,
    ordenar_como_no_windows,
    pdfs_da_pasta,
    resumo,
    total_de_folhas,
)

CHAVE = "imprimir_pdfs"
# no %APPDATA%\ConferenciaISSRB\config.json do Conciliações AMES
CHAVES_PROGRAMA_ANTIGO = {"pasta": "pasta_pdfs", "impressora": "impressora"}


def _ler(campo: str, pasta_preferencias: Path | None, arquivo_antigo: Path | None) -> str:
    dados = ler_preferencias_modulo(CHAVE, pasta_preferencias)
    if campo in dados:
        valor = dados[campo]
    else:
        valor = ler_programa_antigo(arquivo_antigo).get(CHAVES_PROGRAMA_ANTIGO[campo], "")
    return valor if isinstance(valor, str) else ""


def _salvar(campo: str, valor: str, pasta_preferencias: Path | None) -> bool:
    dados = ler_preferencias_modulo(CHAVE, pasta_preferencias)
    dados[campo] = valor
    return salvar_preferencias_modulo(CHAVE, dados, pasta_preferencias)


def ler_pasta_lembrada(pasta_preferencias: Path | None = None, arquivo_antigo: Path | None = None) -> str:
    """A última pasta de onde vieram os PDFs (os seletores abrem nela)."""
    return _ler("pasta", pasta_preferencias, arquivo_antigo)


def salvar_pasta_lembrada(pasta: str, pasta_preferencias: Path | None = None) -> bool:
    return _salvar("pasta", pasta, pasta_preferencias)


def ler_impressora_lembrada(pasta_preferencias: Path | None = None, arquivo_antigo: Path | None = None) -> str:
    """A impressora escolhida da última vez ("" = nenhuma: a tela usa a padrão do Windows)."""
    return _ler("impressora", pasta_preferencias, arquivo_antigo)


def salvar_impressora_lembrada(impressora: str, pasta_preferencias: Path | None = None) -> bool:
    return _salvar("impressora", impressora, pasta_preferencias)
