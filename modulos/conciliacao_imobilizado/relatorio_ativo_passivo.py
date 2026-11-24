"""
Planilha da Comparação Ativo x Passivo (ESPECIFICACAO_IMOBILIZADO.md, seção 6), no estilo da planilha
da conciliação (cores e cabeçalhos de base_iss.py).

Abas: "Ativo x Passivo" (cabeçalho com AME, mês e arquivos; uma linha por par; Total) e "Avisos".
Valores gravados como número (formato #,##0.00). Quem decide o nome e a pasta é salvar_comparacao().
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

from modulos.conciliacao_imobilizado.ativo_passivo import (
    SITUACAO_AP_CONFERE,
    ParAtivoPassivo,
    ResultadoAtivoPassivo,
)
from modulos.conciliacao_imobilizado.base_iss import (
    COLUNAS_AVISOS,
    COR_ERRO,
    COR_GERAL,
    COR_OK,
    COR_PREFEITURA,
    COR_TASY,
    FORMATO_TEXTO,
    FORMATO_VALOR,
    _ajustar_larguras,
    _estilo_cabecalho,
)

TITULO_COMPARACAO = "Comparação Ativo x Passivo – Imobilizado AME's"
ABA_ATIVO_PASSIVO = "Ativo x Passivo"
ABA_AVISOS_AP = "Avisos"
PREFIXO_ARQUIVO_AP = "Conciliacao_ativo_passivo"

COR_ATIVO = COR_TASY
COR_PASSIVO = COR_PREFEITURA

# (título, cor do cabeçalho, valor, formato)
COLUNAS_PARES = [
    ("Grupo", COR_GERAL, lambda p: p.nome_grupo, FORMATO_TEXTO),
    ("Conta do Ativo", COR_ATIVO, lambda p: p.ativo.descricao if p.ativo else None, ""),
    ("Saldo Ativo", COR_ATIVO, lambda p: p.saldo_ativo, FORMATO_VALOR),
    ("Conta do Passivo", COR_PASSIVO, lambda p: p.passivo.descricao if p.passivo else None, ""),
    ("Saldo Passivo", COR_PASSIVO, lambda p: p.saldo_passivo, FORMATO_VALOR),
    ("Diferença (Ativo − Passivo)", COR_GERAL, lambda p: p.diferenca, FORMATO_VALOR),
    ("Situação", COR_GERAL, lambda p: p.situacao, ""),
    ("Observação", COR_GERAL, lambda p: p.observacao or None, ""),
]


def gerar_relatorio_ativo_passivo(resultado: ResultadoAtivoPassivo, caminho: Path,
                                  gerado_em: datetime | None = None) -> Path:
    gerado_em = gerado_em or datetime.now()
    livro = Workbook()
    _aba_pares(livro.active, resultado, gerado_em)
    _aba_avisos(livro, resultado)
    caminho = Path(caminho)
    livro.save(caminho)
    return caminho


def _aba_pares(aba, resultado: ResultadoAtivoPassivo, gerado_em: datetime) -> None:
    aba.title = ABA_ATIVO_PASSIVO
    aba["A1"] = TITULO_COMPARACAO
    aba["A1"].font = Font(bold=True, size=14)
    informacoes = [
        ("AME", resultado.ame),
        ("Mês", resultado.competencia_texto),
        ("Razão do Ativo", resultado.arquivo_ativo),
        ("Razão do Passivo", resultado.arquivo_passivo),
        ("Gerado em", f"{gerado_em:%d/%m/%Y %H:%M}"),
    ]
    for linha, (rotulo, texto) in enumerate(informacoes, start=2):
        aba.cell(row=linha, column=1, value=rotulo).font = Font(bold=True)
        aba.cell(row=linha, column=2, value=texto)

    inicio = len(informacoes) + 3
    for posicao, (titulo, cor, _, _) in enumerate(COLUNAS_PARES, start=1):
        _estilo_cabecalho(aba.cell(row=inicio, column=posicao, value=titulo), cor)
    for numero, par in enumerate(resultado.pares, start=inicio + 1):
        for posicao, (_, _, funcao, formato) in enumerate(COLUNAS_PARES, start=1):
            celula = aba.cell(row=numero, column=posicao, value=_para_excel(funcao(par)))
            if formato:
                celula.number_format = formato
        _cor_da_situacao(aba.cell(row=numero, column=7), par)

    total = inicio + len(resultado.pares) + 1
    aba.cell(row=total, column=2, value="Total").font = Font(bold=True)
    for coluna, campo in ((3, "saldo_ativo"), (5, "saldo_passivo"), (6, "diferenca")):
        celula = aba.cell(row=total, column=coluna, value=float(resultado.total(campo)))
        celula.number_format = FORMATO_VALOR
        celula.font = Font(bold=True)
    aba.freeze_panes = aba.cell(row=inicio + 1, column=1)
    _ajustar_larguras(aba, primeira_linha=inicio)


def _cor_da_situacao(celula, par: ParAtivoPassivo) -> None:
    celula.font = Font(bold=True, color=COR_OK if par.situacao == SITUACAO_AP_CONFERE else COR_ERRO)


def _aba_avisos(livro: Workbook, resultado: ResultadoAtivoPassivo) -> None:
    aba = livro.create_sheet(ABA_AVISOS_AP)
    for posicao, titulo in enumerate(COLUNAS_AVISOS, start=1):
        _estilo_cabecalho(aba.cell(row=1, column=posicao, value=titulo), COR_GERAL)
    for numero, aviso in enumerate(resultado.avisos, start=2):
        valores = [aviso.arquivo, aviso.tipo_arquivo or None, aviso.nivel, aviso.linhas_lidas,
                   aviso.unidades or None, aviso.mensagem]
        for posicao, valor in enumerate(valores, start=1):
            aba.cell(row=numero, column=posicao, value=valor)
    if not resultado.avisos:
        aba.cell(row=2, column=6, value="Nenhum aviso.")
    _ajustar_larguras(aba)


def _para_excel(valor):
    return float(valor) if isinstance(valor, Decimal) else valor
