"""Excel de conferência do EFD Contribuições — ESPECIFICACAO_EFD_CONTRIBUICOES.md, seção 5.

Abas: "Notas" (uma linha por PDF, com a situação; totais no fim), "Clientes novos" e "Avisos".
Valores gravados como número (Decimal → float só na hora de gravar).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from modulos.efd_contribuicoes import configuracao as cfg

ABA_NOTAS = "Notas"
ABA_CLIENTES_NOVOS = "Clientes novos"
ABA_AVISOS = "Avisos"

COLUNAS_NOTAS = [
    ("Nº NFS-e", 11), ("Competência", 12), ("Data de emissão", 15), ("Tomador", 45), ("CNPJ/CPF", 20),
    ("PJ/PF", 7), ("Código IBGE", 12), ("Valor (R$)", 15), ("Situação", 30), ("Observação", 50),
    ("CNPJ do prestador", 20), ("Arquivo", 40),
]
COLUNAS_CLIENTES = [("Código", 9), ("Nome", 50), ("CNPJ", 18), ("Código IBGE", 12), ("De onde veio o IBGE", 20)]
FORMATO_VALOR = "#,##0.00"

_TITULO = Font(bold=True, color=cfg.COR_FONTE_TITULO)
_NEGRITO = Font(bold=True)


def _fundo(cor: str) -> PatternFill:
    return PatternFill("solid", start_color=cor, end_color=cor)


def _cabecalho(aba, colunas, linha: int = 1) -> None:
    for posicao, (titulo, largura) in enumerate(colunas, start=1):
        celula = aba.cell(linha, posicao, titulo)
        celula.font = _TITULO
        celula.fill = _fundo(cfg.COR_FUNDO_TITULO)
        aba.column_dimensions[get_column_letter(posicao)].width = largura
    aba.freeze_panes = aba.cell(linha + 1, 1)


def _cor_da_situacao(situacao: str) -> str:
    if situacao in (cfg.SITUACAO_NO_SPED, cfg.SITUACAO_INCLUIDA):
        return cfg.COR_OK
    if situacao in (cfg.SITUACAO_NAO_LIDO, cfg.SITUACAO_CONFLITO):
        return cfg.COR_PROBLEMA
    return cfg.COR_ATENCAO


def _numero(valor: Decimal | None):
    return None if valor is None else float(valor)


def gerar_excel(resultado, caminho: Path) -> Path:
    """`resultado`: ResultadoEFD do processamento (notas classificadas, clientes novos, avisos, totais)."""
    livro = Workbook()
    _aba_notas(livro.active, resultado)
    _aba_clientes_novos(livro.create_sheet(ABA_CLIENTES_NOVOS), resultado)
    _aba_avisos(livro.create_sheet(ABA_AVISOS), resultado)
    caminho = Path(caminho)
    livro.save(caminho)
    return caminho


def _aba_notas(aba, resultado) -> None:
    aba.title = ABA_NOTAS
    _cabecalho(aba, COLUNAS_NOTAS)
    for linha, item in enumerate(resultado.selecao.notas, start=2):
        nota = item.nota
        valores = [nota.numero_nfse, nota.competencia, nota.data_emissao, nota.tomador, nota.doc_tomador,
                   nota.tipo_pessoa, nota.codigo_ibge_tomador, _numero(nota.valor), item.situacao,
                   item.observacao or None, nota.doc_prestador, nota.arquivo]
        for coluna, valor in enumerate(valores, start=1):
            aba.cell(linha, coluna, valor)
        aba.cell(linha, 3).number_format = "DD/MM/YYYY"
        aba.cell(linha, 8).number_format = FORMATO_VALOR
        aba.cell(linha, 9).fill = _fundo(_cor_da_situacao(item.situacao))
    linha = len(resultado.selecao.notas) + 3
    for rotulo, quantidade, valor in resultado.totais():
        aba.cell(linha, 4, f"{rotulo} ({quantidade})").font = _NEGRITO
        celula = aba.cell(linha, 8, _numero(valor))
        celula.number_format = FORMATO_VALOR
        celula.font = _NEGRITO
        linha += 1
    if resultado.selecao.notas:
        aba.auto_filter.ref = f"A1:{get_column_letter(len(COLUNAS_NOTAS))}{len(resultado.selecao.notas) + 1}"


def _aba_clientes_novos(aba, resultado) -> None:
    _cabecalho(aba, COLUNAS_CLIENTES)
    for linha, (cliente, origem) in enumerate(resultado.clientes_novos, start=2):
        for coluna, valor in enumerate([cliente["cod_part"], cliente["nome"], cliente["cnpj"],
                                        cliente["codigo_ibge"] or None, origem or None], start=1):
            aba.cell(linha, coluna, valor)
    if not resultado.clientes_novos:
        aba.cell(2, 2, "Nenhum cliente novo nesta geração.")


def _aba_avisos(aba, resultado) -> None:
    _cabecalho(aba, [("Aviso", 120)])
    for linha, aviso in enumerate(resultado.avisos, start=2):
        aba.cell(linha, 1, aviso)
    if not resultado.avisos:
        aba.cell(2, 1, "Nenhum aviso.")


def nome_do_excel(competencia: str, agora: datetime) -> str:
    mes, ano = competencia.split("/")
    return f"Conferencia_EFD_{mes}_{ano}_{agora:%Hh%M}.xlsx"
