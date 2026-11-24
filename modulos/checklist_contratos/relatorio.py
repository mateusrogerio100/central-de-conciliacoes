"""Relatório da conferência do mês (Excel). Seção 5 da especificação.

Abas: Resumo, Conferência (uma linha por regra, R10), Conta divergente, Manuais, Não vinculados,
Estornos e devoluções (M4) e Avisos. Cores: verde OK, laranja divergente, rosa não encontrado,
amarelo manual; laranja forte no valor diferente da célula já preenchida (R7) e na variação de 10% ou
mais (R8). Filtro e primeira linha congelada em todas as abas de lista.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from modulos.checklist_contratos import configuracao as cfg
from modulos.checklist_contratos.modelos import (
    Aviso, Checklist, Conferencia, Lancamento, Movimento, Situacao,
)

FONTE_TITULO = Font(bold=True, color=cfg.COR_FONTE_TITULO)
FUNDO_TITULO = PatternFill("solid", start_color=cfg.COR_FUNDO_TITULO)
FUNDO_DESTAQUE = PatternFill("solid", start_color=cfg.COR_DESTAQUE)


def _fundo(cor: str) -> PatternFill:
    return PatternFill("solid", start_color=cor)


def _numero(valor) -> float | None:
    """Decimal -> float só aqui, ao gravar no Excel."""
    return float(valor) if isinstance(valor, Decimal) else valor


def _celula(valor):
    """Valor de célula do Check list como veio (número ou texto sem espaços sobrando)."""
    return valor.strip() if isinstance(valor, str) else valor


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


def _fechar(aba, colunas_valor: tuple[int, ...] = ()):
    for coluna in colunas_valor:
        for linha in range(2, aba.max_row + 1):
            aba.cell(row=linha, column=coluna).number_format = cfg.FORMATO_VALOR_EXCEL
    aba.auto_filter.ref = aba.dimensions


def _situacao(r) -> str:
    if r.situacao == Situacao.OK and r.celula_preenchida:
        return "OK (célula já preenchida)"
    return r.situacao.value


def _obs(r) -> str:
    """Obs da regra e, na R7a, o aviso de que o valor achado é do mês anterior (provisionado)."""
    return " · ".join(t for t in ((cfg.AVISO_PROVISAO + ".") if r.provisao else "", r.regra.obs) if t)


def _descricao_lancamento(l: Lancamento) -> str:
    return f"[{l.valor:.2f}] {l.complemento}"


def _aba_resumo(livro, conferencia: Conferencia, checklist: Checklist, movimentos: dict[str, Movimento],
                arquivos: dict[str, str], agora: datetime):
    aba = livro.active
    aba.title = cfg.ABA_RESUMO
    mes = f"{cfg.MESES_POR_EXTENSO[checklist.mes - 1]}/{checklist.ano}"
    contagem = conferencia.contagem()
    linhas = [
        ("Conferência das notas de contrato", mes),
        ("Gerado em", agora.strftime("%d/%m/%Y %H:%M")),
        ("", ""),
    ]
    linhas += [(s.value, contagem[s]) for s in (Situacao.OK, Situacao.CONTA_DIVERGENTE, Situacao.NAO_ENCONTRADO,
                                                 Situacao.MANUAL, Situacao.IGNORADO)]
    linhas += [
        ("Linhas preenchidas na cópia", sum(1 for r in conferencia.resultados if r.gravar)),
        ("Célula já preenchida com valor diferente (R7)", sum(1 for r in conferencia.resultados if r.valor_diferente)),
        ("\"Provisão\" na planilha e valor achado: se refere ao mês anterior (R7a)",
         sum(1 for r in conferencia.resultados if r.provisao)),
        ("Variação de 10% ou mais (R8)", sum(1 for r in conferencia.resultados if r.variacao_destacada)),
        ("Lançamentos em conta divergente", sum(len(r.divergentes) for r in conferencia.resultados
                                                if r.situacao == Situacao.CONTA_DIVERGENTE)),
        ("Não vinculados", len(conferencia.nao_vinculados)),
        ("Estornos e devoluções anulados", sum(len(m.anulacoes) for m in movimentos.values() if m)),
        ("Avisos", sum(1 for _ in _todos_os_avisos(conferencia, checklist, movimentos))),
        ("", ""),
    ]
    linhas += [(f"Arquivo: {nome}", caminho) for nome, caminho in arquivos.items()]
    for titulo, valor in linhas:
        aba.append([titulo, valor])
    aba["A1"].font = Font(bold=True, size=13)
    for linha in range(4, 9):
        situacao = aba.cell(row=linha, column=1).value
        aba.cell(row=linha, column=1).fill = _fundo(cfg.CORES_SITUACAO[situacao])
    aba.column_dimensions["A"].width = 48
    aba.column_dimensions["B"].width = 90


def _aba_conferencia(livro, conferencia: Conferencia, checklist: Checklist):
    titulos = ["Aba", "Linha", "Conta esperada", "Fornecedor", "Descrição da despesa", "Situação", "Valor achado",
               "Mês anterior", "Já na planilha", "Var %", "Lote/lançamento", "Lançamentos usados", "Obs"]
    aba = _aba(livro, cfg.ABA_CONFERENCIA, titulos, [26, 7, 15, 34, 44, 26, 14, 14, 14, 9, 26, 70, 40])
    for r in conferencia.resultados:
        usados = r.achados + r.divergentes if r.situacao != Situacao.MANUAL else r.candidatos
        aba.append([checklist.abas[r.regra.aba].nome, r.linha.numero, "/".join(r.regra.contas), r.linha.fornecedor,
                    r.linha.descricao_despesa, _situacao(r), _numero(r.valor), _celula(r.linha.valor_mes_anterior),
                    _celula(r.linha.valor_mes), _numero(r.variacao), r.lote_lancamento,
                    " || ".join(_descricao_lancamento(l) for l in usados), _obs(r)])
        linha = aba.max_row
        aba.cell(row=linha, column=6).fill = _fundo(cfg.CORES_SITUACAO[r.situacao.value])
        if r.valor_diferente or r.provisao:
            aba.cell(row=linha, column=9).fill = FUNDO_DESTAQUE
        if r.variacao_destacada:
            aba.cell(row=linha, column=10).fill = FUNDO_DESTAQUE
        aba.cell(row=linha, column=10).number_format = cfg.FORMATO_PERCENTUAL_EXCEL
    _fechar(aba, (7, 8, 9))


def _aba_divergente(livro, conferencia: Conferencia, checklist: Checklist):
    titulos = ["Aba", "Linha", "Fornecedor", "Descrição da despesa", "Conta esperada", "Conta lançada",
               "Nome da conta lançada", "Valor", "Lote", "Lançamento", "Data", "Complemento"]
    aba = _aba(livro, cfg.ABA_DIVERGENTE, titulos, [26, 7, 34, 40, 15, 13, 34, 14, 10, 14, 12, 80])
    for r in conferencia.resultados:
        if r.situacao != Situacao.CONTA_DIVERGENTE:
            continue
        for l in r.divergentes:
            aba.append([checklist.abas[r.regra.aba].nome, r.linha.numero, r.linha.fornecedor, r.linha.descricao_despesa,
                        "/".join(r.regra.contas), l.conta, l.nome_conta, _numero(l.valor), l.lote or l.documento,
                        l.lancamento, l.data, l.complemento])
    _fechar(aba, (8,))


def _aba_manuais(livro, conferencia: Conferencia, checklist: Checklist):
    titulos = ["Aba", "Linha", "Fornecedor", "Descrição da despesa", "Conta esperada", "Conta lançada", "Valor",
               "Lote/lançamento", "Data", "Centros de custo", "Complemento", "Obs"]
    aba = _aba(livro, cfg.ABA_MANUAIS, titulos, [26, 7, 34, 44, 15, 13, 14, 22, 12, 40, 80, 40])
    for r in conferencia.resultados:
        if r.situacao != Situacao.MANUAL:
            continue
        for l in r.candidatos or [None]:
            if l is None:
                aba.append([checklist.abas[r.regra.aba].nome, r.linha.numero, r.linha.fornecedor,
                            r.linha.descricao_despesa, "/".join(r.regra.contas), "", None, "", "", "",
                            "(nenhum lançamento candidato)", r.regra.obs])
                continue
            centros = "; ".join(f"{nome or '(sem)'}: {valor:.2f}" for nome, valor in l.centros_custo)
            aba.append([checklist.abas[r.regra.aba].nome, r.linha.numero, r.linha.fornecedor, r.linha.descricao_despesa,
                        "/".join(r.regra.contas), l.conta, _numero(l.valor), l.lote_lancamento, l.data, centros,
                        l.complemento, r.regra.obs])
    _fechar(aba, (7,))


def _aba_nao_vinculados(livro, conferencia: Conferencia, checklist: Checklist):
    titulos = ["Aba", "Motivo", "Conta", "Nome da conta", "Valor", "Lote/lançamento", "Data", "Complemento"]
    aba = _aba(livro, cfg.ABA_NAO_VINCULADOS, titulos, [26, 46, 10, 34, 14, 22, 12, 90])
    for n in conferencia.nao_vinculados:
        l = n.lancamento
        aba.append([checklist.abas[l.estabelecimento].nome, n.motivo, l.conta, l.nome_conta, _numero(l.valor),
                    l.lote_lancamento, l.data, l.complemento])
    _fechar(aba, (5,))


def _aba_estornos(livro, checklist: Checklist, movimentos: dict[str, Movimento]):
    titulos = ["Aba", "Tipo", "Anulado (lançamento)", "Data", "Complemento do anulado", "Débitos do anulado",
               "Anulado por (lançamento)", "Data ", "Complemento de quem anulou"]
    aba = _aba(livro, cfg.ABA_ESTORNOS, titulos, [26, 11, 22, 12, 70, 40, 22, 12, 70])
    for estabelecimento, movimento in movimentos.items():
        for a in (movimento.anulacoes if movimento else []):
            debitos = "; ".join(f"{l.conta}: {l.valor:.2f}" for l in a.anulado if l.natureza == cfg.MOV_DEBITO)
            aba.append([checklist.abas[estabelecimento].nome, a.tipo, a.anulado[0].lote_lancamento, a.anulado[0].data,
                        a.anulado[0].complemento, debitos, a.anulador[0].lote_lancamento, a.anulador[0].data,
                        a.anulador[0].complemento])
    _fechar(aba)


def _todos_os_avisos(conferencia: Conferencia, checklist: Checklist, movimentos: dict[str, Movimento]):
    for estabelecimento, movimento in movimentos.items():
        for a in (movimento.avisos if movimento else []):
            yield Aviso(f"Movimento {checklist.abas[estabelecimento].nome}: {a.origem}", a.mensagem)
    yield from checklist.avisos
    yield from conferencia.avisos


def _aba_avisos(livro, conferencia: Conferencia, checklist: Checklist, movimentos: dict[str, Movimento],
                avisos_extras: list[Aviso]):
    aba = _aba(livro, cfg.ABA_AVISOS, ["Origem", "Aviso"], [50, 120])
    for a in list(_todos_os_avisos(conferencia, checklist, movimentos)) + avisos_extras:
        aba.append([a.origem, a.mensagem])
    _fechar(aba)


def gerar_relatorio(caminho: Path, conferencia: Conferencia, checklist: Checklist, movimentos: dict[str, Movimento],
                    arquivos: dict[str, str], avisos_extras: list[Aviso] | None = None,
                    agora: datetime | None = None) -> Path:
    """Grava o relatório. Levanta OSError se não puder gravar (ex.: aberto no Excel)."""
    agora = agora or datetime.now()
    livro = Workbook()
    _aba_resumo(livro, conferencia, checklist, movimentos, arquivos, agora)
    _aba_conferencia(livro, conferencia, checklist)
    _aba_divergente(livro, conferencia, checklist)
    _aba_manuais(livro, conferencia, checklist)
    _aba_nao_vinculados(livro, conferencia, checklist)
    _aba_estornos(livro, checklist, movimentos)
    _aba_avisos(livro, conferencia, checklist, movimentos, avisos_extras or [])
    livro.save(caminho)
    return Path(caminho)
