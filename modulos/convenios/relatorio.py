"""Relatório de conferência do mês (Excel). Seção 5 da especificação.

Abas: Resumo (total do razão por conta, total preenchido, diferença), Por convênio (cada linha da planilha:
situação, valor anterior, valor do mês, lançamentos e nomes do razão; mais o não identificado), Lançamentos
(todo lançamento do razão com a linha em que entrou: P6) e Avisos.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from modulos.convenios import configuracao as cfg
from modulos.convenios.classificacao import COMO_DENTRO, COMO_NAO_IDENTIFICADO, COMO_NOVA, Classificacao
from modulos.convenios.modelos import Aviso, Razao
from modulos.convenios.preenchimento import Preenchimento

FONTE_TITULO = Font(bold=True, color=cfg.COR_FONTE_TITULO)
FUNDO_TITULO = PatternFill("solid", start_color=cfg.COR_FUNDO_TITULO)
FORMATO_VALOR = "#,##0.00;-#,##0.00"
NEGRITO = Font(bold=True)


def _fundo(cor: str) -> PatternFill:
    return PatternFill("solid", start_color=cor)


def _numero(valor: Decimal | None) -> float | None:
    return None if valor is None else float(valor)


def _aba(livro: Workbook, nome: str, titulos: list[str], larguras: list[int]):
    aba = livro.create_sheet(nome)
    aba.append(titulos)
    for coluna, largura in enumerate(larguras, start=1):
        celula = aba.cell(row=1, column=coluna)
        celula.font, celula.fill = FONTE_TITULO, FUNDO_TITULO
        celula.alignment = Alignment(vertical="center", wrap_text=True)
        aba.column_dimensions[get_column_letter(coluna)].width = largura
    aba.freeze_panes = "A2"
    return aba


def _formatar_valores(aba, colunas: list[int], primeira: int = 2):
    for linha in aba.iter_rows(min_row=primeira):
        for coluna in colunas:
            linha[coluna - 1].number_format = FORMATO_VALOR


def _aba_resumo(livro, razao: Razao, classificacao: Classificacao, preenchimento: Preenchimento,
                arquivos: dict[str, str], avisos: list[Aviso], agora: datetime):
    aba = livro.active
    aba.title = cfg.ABA_RESUMO
    linhas = [
        ("Receita de convênios", f"{preenchimento.mes:02d}/{preenchimento.ano}"),
        ("Gerado em", f"{agora:%d/%m/%Y %H:%M}"),
        (),
        ("Razão por conta", ""),
        *[(f"{c.codigo} - {c.classificacao} {c.nome}", _numero(c.total)) for c in razao.contas],
        ("Saldo Contábil (total do razão)", _numero(preenchimento.saldo_contabil)),
        (),
        ("TOTAL RECEITAS do mês na cópia", _numero(preenchimento.total_preenchido)),
        ("Diferença", _numero(preenchimento.diferenca)),
        ("Não identificado (preencher à mão)", _numero(classificacao.total_nao_identificado)),
        ("Linhas novas", ", ".join(l.nome for l in preenchimento.linhas_novas) or "nenhuma"),
        ("Avisos", len(avisos)),
        (),
        ("Arquivos usados", ""),
        *arquivos.items(),
    ]
    for linha in linhas:
        aba.append(list(linha))
    for numero, linha in enumerate(linhas, start=1):
        if linha and linha[0] in ("Receita de convênios", "Razão por conta", "Saldo Contábil (total do razão)",
                                  "TOTAL RECEITAS do mês na cópia", "Diferença", "Arquivos usados"):
            aba.cell(numero, 1).font = NEGRITO
        if linha and isinstance(linha[1], float):
            aba.cell(numero, 2).number_format = FORMATO_VALOR
            aba.cell(numero, 2).alignment = Alignment(horizontal="right")
        if linha and linha[0] == "Diferença":
            aba.cell(numero, 2).fill = _fundo(cfg.COR_OK if preenchimento.diferenca == 0 else cfg.COR_PROBLEMA)
    aba.column_dimensions["A"].width = 55
    aba.column_dimensions["B"].width = 90


def _aba_por_convenio(livro, classificacao: Classificacao, preenchimento: Preenchimento):
    aba = _aba(livro, cfg.ABA_POR_CONVENIO,
               ["Linha na cópia", "Convênio", "Situação", "Valor anterior", "Valor do mês", "Nº de lançamentos",
                "Nomes no razão"], [10, 45, 32, 16, 16, 12, 90])
    cores = {cfg.SITUACAO_NOVA: cfg.COR_ATENCAO, cfg.SITUACAO_MANTIDA: cfg.COR_ATENCAO,
             cfg.SITUACAO_SEM_MOVIMENTO: cfg.COR_CINZA}
    for l in preenchimento.linhas:
        destinos = l.total.destinos if l.total else []
        aba.append([l.linha, l.nome, l.situacao, _numero(l.anterior), _numero(l.novo), len(destinos) or None,
                    "; ".join(l.total.nomes_lidos) if destinos else None])
        if l.situacao in cores:
            aba.cell(aba.max_row, 3).fill = _fundo(cores[l.situacao])
    if classificacao.nao_identificados:
        nomes = sorted({d.nome_lido or d.lancamento.historico for d in classificacao.nao_identificados})
        aba.append([None, "Não identificado", cfg.SITUACAO_NAO_IDENTIFICADO, None,
                    _numero(classificacao.total_nao_identificado), len(classificacao.nao_identificados),
                    "; ".join(nomes)])
        aba.cell(aba.max_row, 3).fill = _fundo(cfg.COR_PROBLEMA)
    aba.append([None, cfg.PLANILHA_TOTAL, None, None, _numero(preenchimento.total_preenchido)])
    aba.append([preenchimento.linha_saldo, cfg.PLANILHA_SALDO_CONTABIL, None, _numero(preenchimento.saldo_anterior),
                _numero(preenchimento.saldo_contabil)])
    aba.append([None, cfg.PLANILHA_DIFERENCA, None, None, _numero(preenchimento.diferenca)])
    for linha in range(aba.max_row - 2, aba.max_row + 1):
        aba.cell(linha, 2).font = NEGRITO
    aba.cell(aba.max_row, 5).fill = _fundo(cfg.COR_OK if preenchimento.diferenca == 0 else cfg.COR_PROBLEMA)
    _formatar_valores(aba, [4, 5])
    aba.auto_filter.ref = f"A1:G{aba.max_row - 3}"


def _aba_lancamentos(livro, classificacao: Classificacao):
    aba = _aba(livro, cfg.ABA_LANCAMENTOS,
               ["Conta", "Data", "Histórico", "Lote", "Débito", "Crédito", "Valor", "Nome lido", "Linha da planilha",
                "Como", "Obs", "Linha no razão"], [9, 11, 80, 9, 14, 14, 14, 40, 40, 34, 40, 10])
    cores = {COMO_NAO_IDENTIFICADO: cfg.COR_PROBLEMA, COMO_DENTRO: cfg.COR_ATENCAO, COMO_NOVA: cfg.COR_ATENCAO}
    for d in classificacao.destinos:
        l = d.lancamento
        aba.append([l.conta, l.data, l.historico, l.lote, _numero(l.debito), _numero(l.credito), _numero(l.valor),
                    d.nome_lido or None, d.linha or "Não identificado", d.como, d.obs or None, l.linha])
        aba.cell(aba.max_row, 2).number_format = "dd/mm/yyyy"
        if d.como in cores:
            aba.cell(aba.max_row, 10).fill = _fundo(cores[d.como])
    _formatar_valores(aba, [5, 6, 7])
    aba.auto_filter.ref = aba.dimensions


def _aba_avisos(livro, avisos: list[Aviso]):
    aba = _aba(livro, cfg.ABA_AVISOS, ["Origem", "Aviso", "Tipo"], [45, 130, 12])
    for a in avisos:
        aba.append([a.origem, a.mensagem, "erro" if a.erro else "atenção"])
        aba.cell(aba.max_row, 3).fill = _fundo(cfg.COR_PROBLEMA if a.erro else cfg.COR_ATENCAO)
    aba.auto_filter.ref = aba.dimensions


def gerar_relatorio(caminho: Path, razao: Razao, classificacao: Classificacao, preenchimento: Preenchimento,
                    arquivos: dict[str, str], avisos: list[Aviso], agora: datetime | None = None) -> Path:
    """Grava o relatório. Levanta OSError se não puder gravar (ex.: aberto no Excel)."""
    livro = Workbook()
    _aba_resumo(livro, razao, classificacao, preenchimento, arquivos, avisos, agora or datetime.now())
    _aba_por_convenio(livro, classificacao, preenchimento)
    _aba_lancamentos(livro, classificacao)
    _aba_avisos(livro, avisos)
    livro.save(caminho)
    return Path(caminho)
