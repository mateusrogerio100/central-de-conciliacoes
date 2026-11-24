"""Relatório de conferência do mês (Excel). Seção 5 da especificação.

Abas: Resumo (Total Eventos, TOTAL GERAL, Movimento, diferença, total de cada seção), Eventos (cada evento do
relatório: total, CCs, seção, valor no Movimento, situação), Linhas criadas (o que foi acrescentado à aba do ano
e por quê), Movimento sem evento (só quando o TOTAL GERAL não bate: as linhas para conferir à mão, R9) e Avisos.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from modulos.planilha_hm import configuracao as cfg
from modulos.planilha_hm.modelos import Aviso, Conferencia, Eventos, Movimento, Planilha, Plano, Preenchimento

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


def _aba_resumo(livro, eventos: Eventos, movimento: Movimento, plano: Plano, preenchimento: Preenchimento,
                conferencia: Conferencia, arquivos: dict[str, str], avisos: list[Aviso], agora: datetime):
    aba = livro.active
    aba.title = cfg.ABA_RESUMO
    com_erro = [e for e in eventos.eventos if not e.ok]
    destaques = ("Planilha HM", "TOTAL GERAL do mês na cópia", "Diferença (TOTAL GERAL − Movimento)",
                 "Total de cada seção", "Arquivos usados")
    linhas = [
        ("Planilha HM", f"{conferencia.mes:02d}/{conferencia.ano}"),
        ("Gerado em", f"{agora:%d/%m/%Y %H:%M}"),
        (),
        (f"Total Eventos ({len(eventos.eventos)} eventos)", _numero(conferencia.total_eventos)),
        ("TOTAL GERAL do mês na cópia", _numero(conferencia.total_geral)),
        (f"Movimento (lote {movimento.lote})", _numero(conferencia.total_movimento)),
        ("Diferença (TOTAL GERAL − Movimento)", _numero(conferencia.diferenca)),
        ("LOTE REPASSE gravado", _numero(preenchimento.lote)),
        (),
        ("Linhas na aba " + cfg.NOME_ABA_SENIOR.format(mes=preenchimento.mes, ano=preenchimento.ano),
         preenchimento.linhas_senior),
        ("Linhas criadas na aba do ano", len(preenchimento.criadas)),
        ("Eventos com erro (fora da planilha)", len(com_erro)),
        ("Tabela conta → seção", plano.caminho_tabela),
        ("Avisos", len(avisos)),
        (),
        ("Total de cada seção", ""),
        *[(t.nome_total, _numero(t.valor)) for t in conferencia.totais],
        (),
        ("Arquivos usados", ""),
        *arquivos.items(),
    ]
    for linha in linhas:
        aba.append(list(linha))
    for numero, linha in enumerate(linhas, start=1):
        if linha and linha[0] in destaques:
            aba.cell(numero, 1).font = NEGRITO
        if linha and isinstance(linha[1], float):
            aba.cell(numero, 2).number_format = FORMATO_VALOR
            aba.cell(numero, 2).alignment = Alignment(horizontal="right")
        if linha and linha[0] == "Diferença (TOTAL GERAL − Movimento)":
            aba.cell(numero, 2).fill = _fundo(cfg.COR_OK if conferencia.ok else cfg.COR_PROBLEMA)
        if linha and linha[0] == "Eventos com erro (fora da planilha)" and com_erro:
            aba.cell(numero, 2).fill = _fundo(cfg.COR_PROBLEMA)
    aba.column_dimensions["A"].width = 55
    aba.column_dimensions["B"].width = 90


def _aba_eventos(livro, eventos: Eventos, final: Planilha, preenchimento: Preenchimento, conferencia: Conferencia):
    aba = _aba(livro, cfg.ABA_EVENTOS,
               ["Evento", "Nome", "Sinal", "Total Evento", "Soma dos CCs", "Nº de CCs", "Código do histórico",
                "Seção na cópia", "Valor no Movimento", "Diferença", "Situação"],
               [9, 40, 7, 16, 16, 9, 11, 45, 16, 14, 60])
    novos = {c.evento for c in preenchimento.criadas if c.tipo == "evento novo"}
    com_cc_novo = {c.evento for c in preenchimento.criadas if c.tipo == "CC novo"}
    fora = {e.numero for e in conferencia.eventos_fora}
    no_movimento = {c.evento: c for c in conferencia.comparacao}
    for evento in eventos.eventos:
        secao = final.secao_do_evento(evento.numero)
        if not evento.ok:
            situacao, cor = f"erro: {evento.erro}", cfg.COR_PROBLEMA
        elif evento.numero in fora:
            situacao, cor = cfg.SITUACAO_FORA, cfg.COR_PROBLEMA
        elif evento.numero in novos:
            situacao, cor = cfg.SITUACAO_NOVO, cfg.COR_ATENCAO
        elif evento.numero in com_cc_novo:
            situacao, cor = cfg.SITUACAO_CC_NOVO, cfg.COR_ATENCAO
        else:
            situacao, cor = cfg.SITUACAO_OK, None
        comparacao = no_movimento.get(evento.numero)
        aba.append([evento.numero, evento.nome, evento.sinal, _numero(evento.total), _numero(evento.soma_subtotais),
                    len(evento.subtotais), evento.codigo_historico or None, secao.nome if secao else None,
                    _numero(comparacao.valor_movimento) if comparacao else None,
                    _numero(comparacao.diferenca) if comparacao else None, situacao])
        if cor:
            aba.cell(aba.max_row, 11).fill = _fundo(cor)
        if comparacao and comparacao.diferenca:
            aba.cell(aba.max_row, 10).fill = _fundo(cfg.COR_PROBLEMA)
    _formatar_valores(aba, [4, 5, 9, 10])
    aba.auto_filter.ref = aba.dimensions


def _aba_linhas_criadas(livro, preenchimento: Preenchimento):
    aba = _aba(livro, cfg.ABA_LINHAS_CRIADAS,
               ["Linha na cópia", "O quê", "Evento", "Nome do evento", "Cód. do CC", "Centro de custo", "Seção",
                "Conta (Movimento)", "De onde veio a seção", "Por quê"],
               [10, 20, 9, 35, 9, 40, 40, 50, 24, 50])
    for c in sorted(preenchimento.criadas, key=lambda c: c.linha):
        aba.append([c.linha, c.tipo, c.evento, c.nome_evento or None, c.codigo_cc or None, c.nome_cc or None,
                    c.secao or None, c.conta or None, c.origem or None, c.motivo or None])
    aba.auto_filter.ref = aba.dimensions


def _aba_sem_evento(livro, conferencia: Conferencia):
    aba = _aba(livro, cfg.ABA_SEM_EVENTO,
               ["Linha no Movimento", "Débito", "Conta débito", "Classificação", "Valor", "Código do histórico",
                "Histórico"], [10, 10, 40, 20, 14, 11, 90])
    for l in conferencia.linhas_sem_evento:
        aba.append([l.linha, l.debito, l.conta_debito, l.classificacao_debito, _numero(l.valor),
                    l.codigo_historico or None, l.historico])
    _formatar_valores(aba, [5])
    aba.auto_filter.ref = aba.dimensions


def _aba_avisos(livro, avisos: list[Aviso]):
    aba = _aba(livro, cfg.ABA_AVISOS, ["Origem", "Aviso", "Tipo"], [45, 130, 12])
    for a in avisos:
        aba.append([a.origem, a.mensagem, "erro" if a.erro else "atenção"])
        aba.cell(aba.max_row, 3).fill = _fundo(cfg.COR_PROBLEMA if a.erro else cfg.COR_ATENCAO)
    aba.auto_filter.ref = aba.dimensions


def gerar_relatorio(caminho: Path, eventos: Eventos, movimento: Movimento, plano: Plano,
                    preenchimento: Preenchimento, final: Planilha, conferencia: Conferencia,
                    arquivos: dict[str, str], avisos: list[Aviso], agora: datetime | None = None) -> Path:
    """Grava o relatório. Levanta OSError se não puder gravar (ex.: aberto no Excel)."""
    livro = Workbook()
    _aba_resumo(livro, eventos, movimento, plano, preenchimento, conferencia, arquivos, avisos,
                agora or datetime.now())
    _aba_eventos(livro, eventos, final, preenchimento, conferencia)
    _aba_linhas_criadas(livro, preenchimento)
    if not conferencia.ok:
        _aba_sem_evento(livro, conferencia)
    _aba_avisos(livro, avisos)
    livro.save(caminho)
    return Path(caminho)
