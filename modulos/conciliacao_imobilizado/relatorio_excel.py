"""
Planilha da Conciliação do Imobilizado – AME's (openpyxl), no mesmo estilo da Conferência ISS.

Abas: Resumo, Contas, [Diferenças — só se houver], [Bens adquiridos — se o relatório foi
informado], [Baixas — idem] e Avisos.

Valores gravados como número (Decimal) com formato #,##0.00. Quem decide o nome e a pasta
é processar_bens(); erro ao gravar sobe como OSError.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Callable

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from modulos.conciliacao_imobilizado.base_iss import (
    COLUNAS_AVISOS,
    COR_ERRO,
    COR_GERAL,
    COR_OK,
    COR_PREFEITURA,
    COR_TASY,
    FORMATO_DATA,
    FORMATO_TEXTO,
    FORMATO_VALOR,
    _ajustar_larguras,
    _estilo_cabecalho,
)
from modulos.conciliacao_imobilizado.modelos import ORDEM_SITUACOES, SITUACAO_CONFERE, ItemConciliacao, ResultadoBens
from modulos.conciliacao_imobilizado.resumo import linhas_do_resumo

TITULO_RELATORIO = "Conciliação do Imobilizado – AME's"

ABA_RESUMO = "Resumo"
ABA_CONTAS = "Contas"
ABA_DIFERENCAS = "Diferenças"
ABA_BENS_ADQUIRIDOS = "Bens adquiridos"
ABA_BAIXAS = "Baixas"
ABA_AVISOS = "Avisos"

COR_PATRIMONIO = COR_TASY            # colunas do patrimônio (6051)
COR_BALANCETE = COR_PREFEITURA       # colunas do balancete (865)


@dataclass(frozen=True)
class Coluna:
    titulo: str
    cor: str
    valor: Callable[[object], object]
    formato: str = ""


def _do_patrimonio(campo: str):
    return lambda i: None if i.conta_patrimonio is None else getattr(i.conta_patrimonio, campo)


def _do_balancete(campo: str):
    return lambda i: None if i.conta_balancete is None else getattr(i.conta_balancete, campo)


COLUNAS_CONTAS = [
    Coluna("Código", COR_GERAL, lambda i: i.codigo, FORMATO_TEXTO),
    Coluna("Conta", COR_GERAL, lambda i: i.nome),
    Coluna("Saldo atual (patrimônio)", COR_PATRIMONIO, lambda i: i.saldo_patrimonio, FORMATO_VALOR),
    Coluna("Saldo atual (balancete)", COR_BALANCETE, lambda i: i.saldo_balancete, FORMATO_VALOR),
    Coluna("Diferença (patrimônio − balancete)", COR_GERAL, lambda i: i.diferenca, FORMATO_VALOR),
    Coluna("Situação", COR_GERAL, lambda i: i.situacao),
    Coluna("Explicação", COR_GERAL, lambda i: i.explicacao or None),
    Coluna("Entradas (bens adquiridos)", COR_GERAL, lambda i: i.entradas or None, FORMATO_VALOR),
    Coluna("Baixas (baixa de bens)", COR_GERAL, lambda i: i.baixas or None, FORMATO_VALOR),
    Coluna("Saldo anterior (patrimônio)", COR_PATRIMONIO, _do_patrimonio("saldo_anterior"), FORMATO_VALOR),
    Coluna("Entradas (patrimônio)", COR_PATRIMONIO, _do_patrimonio("entradas"), FORMATO_VALOR),
    Coluna("Baixas (patrimônio)", COR_PATRIMONIO, _do_patrimonio("baixas"), FORMATO_VALOR),
    Coluna("Transf. entrada (patrimônio)", COR_PATRIMONIO, _do_patrimonio("transf_entrada"), FORMATO_VALOR),
    Coluna("Transf. saída (patrimônio)", COR_PATRIMONIO, _do_patrimonio("transf_saida"), FORMATO_VALOR),
    Coluna("Balancete (arquivo)", COR_BALANCETE, _do_balancete("arquivo")),
    Coluna("Classificação", COR_BALANCETE, _do_balancete("classificacao"), FORMATO_TEXTO),
    Coluna("Saldo anterior (balancete)", COR_BALANCETE, _do_balancete("saldo_anterior"), FORMATO_VALOR),
    Coluna("Débitos", COR_BALANCETE, _do_balancete("debitos"), FORMATO_VALOR),
    Coluna("Créditos", COR_BALANCETE, _do_balancete("creditos"), FORMATO_VALOR),
]

COLUNAS_BENS_ADQUIRIDOS = [
    Coluna("Conta", COR_GERAL, lambda b: b.conta_codigo, FORMATO_TEXTO),
    Coluna("Nome da conta", COR_GERAL, lambda b: b.conta_nome),
    Coluna("Centro de custo", COR_GERAL, lambda b: b.centro),
    Coluna("Código do bem", COR_GERAL, lambda b: b.codigo_bem, FORMATO_TEXTO),
    Coluna("Descrição", COR_GERAL, lambda b: b.descricao),
    Coluna("Dt. aquisição", COR_GERAL, lambda b: b.data_aquisicao),
    Coluna("Vl original", COR_GERAL, lambda b: b.valor, FORMATO_VALOR),
]

COLUNAS_BAIXAS = [
    Coluna("Conta", COR_GERAL, lambda b: b.conta_codigo or "não encontrada", FORMATO_TEXTO),
    Coluna("Nome da conta (no relatório)", COR_GERAL, lambda b: b.conta_nome),
    Coluna("Chapa", COR_GERAL, lambda b: b.chapa, FORMATO_TEXTO),
    Coluna("Descrição", COR_GERAL, lambda b: b.descricao),
    Coluna("Tipo", COR_GERAL, lambda b: b.tipo or None),
    Coluna("Motivo", COR_GERAL, lambda b: b.motivo or None),
    Coluna("Vl. origem", COR_GERAL, lambda b: b.valor_origem, FORMATO_VALOR),
    Coluna("Vl. deprec.", COR_GERAL, lambda b: b.valor_depreciacao, FORMATO_VALOR),
    Coluna("Vl. atual", COR_GERAL, lambda b: b.valor_atual, FORMATO_VALOR),
    Coluna("Data", COR_GERAL, lambda b: b.data),
]


def gerar_relatorio_bens(resultado: ResultadoBens, caminho: Path,
                         gerado_em: datetime | None = None) -> Path:
    gerado_em = gerado_em or datetime.now()
    livro = Workbook()
    _aba_resumo(livro.active, resultado, gerado_em)
    _aba_tabela(livro, ABA_CONTAS, resultado.itens, COLUNAS_CONTAS)
    diferencas = [i for i in resultado.itens if i.situacao != SITUACAO_CONFERE]
    if diferencas:
        _aba_tabela(livro, ABA_DIFERENCAS, diferencas, COLUNAS_CONTAS)
    if resultado.leu_bens_adquiridos:
        _aba_tabela(livro, ABA_BENS_ADQUIRIDOS, resultado.bens_adquiridos, COLUNAS_BENS_ADQUIRIDOS)
    if resultado.leu_baixas:
        _aba_tabela(livro, ABA_BAIXAS, resultado.bens_baixados, COLUNAS_BAIXAS)
    _aba_avisos(livro, resultado)
    caminho = Path(caminho)
    livro.save(caminho)
    return caminho


def _aba_tabela(livro: Workbook, titulo: str, registros: list, colunas: list[Coluna]) -> None:
    aba = livro.create_sheet(titulo)
    for posicao, coluna in enumerate(colunas, start=1):
        _estilo_cabecalho(aba.cell(row=1, column=posicao, value=coluna.titulo), coluna.cor)
    for numero, registro in enumerate(registros, start=2):
        for posicao, coluna in enumerate(colunas, start=1):
            valor = coluna.valor(registro)
            celula = aba.cell(row=numero, column=posicao, value=None if valor == "" else valor)
            if coluna.formato:
                celula.number_format = coluna.formato
            elif isinstance(valor, date):
                celula.number_format = FORMATO_DATA
    aba.freeze_panes = "C2"
    aba.auto_filter.ref = f"A1:{get_column_letter(len(colunas))}{max(1, len(registros) + 1)}"
    _ajustar_larguras(aba)


def _aba_resumo(aba, resultado: ResultadoBens, gerado_em: datetime) -> None:
    aba.title = ABA_RESUMO
    negrito = Font(bold=True)
    aba.append([TITULO_RELATORIO])
    aba["A1"].font = Font(bold=True, size=14, color=COR_GERAL)
    aba.append([])

    for rotulo, valor in [
        ("AME", resultado.ame or "—"),
        ("Mês", resultado.competencia_texto or resultado.competencia or "—"),
        ("Gerado em", gerado_em.strftime("%d/%m/%Y %H:%M")),
    ]:
        aba.append([rotulo, valor])
        aba.cell(row=aba.max_row, column=1).font = negrito

    aba.append(["Arquivos lidos"])
    aba.cell(row=aba.max_row, column=1).font = negrito
    for aviso in (a for a in resultado.avisos if a.tipo_arquivo):
        linhas = "" if aviso.linhas_lidas is None else f" · {aviso.linhas_lidas} linhas"
        aba.append(["", f"{aviso.arquivo} ({aviso.tipo_arquivo}{linhas}) — {aviso.mensagem}"])
    if not resultado.leu_bens_adquiridos:
        aba.append(["", "Bens adquiridos (555): não informado"])
    if not resultado.leu_baixas:
        aba.append(["", "Baixa de bens (561): não informado"])
    aba.append([])

    # Tabela por situação
    cabecalho = ["Situação", "Contas", "Saldo atual (patrimônio)", "Saldo atual (balancete)",
                 "Diferença"]
    aba.append(cabecalho)
    linha_cabecalho = aba.max_row
    for posicao in range(1, len(cabecalho) + 1):
        _estilo_cabecalho(aba.cell(row=linha_cabecalho, column=posicao), COR_GERAL)
    linhas = linhas_do_resumo(resultado)
    for linha in linhas:
        aba.append([linha.situacao, linha.contas, linha.saldo_patrimonio, linha.saldo_balancete,
                    linha.diferenca])
    aba.append(["Total", sum(l.contas for l in linhas),
                sum((l.saldo_patrimonio for l in linhas), Decimal(0)),
                sum((l.saldo_balancete for l in linhas), Decimal(0)),
                sum((l.diferenca for l in linhas), Decimal(0))])
    for celula in aba[aba.max_row]:
        celula.font = negrito
    for numero in range(linha_cabecalho + 1, aba.max_row + 1):
        for coluna in (3, 4, 5):
            aba.cell(row=numero, column=coluna).number_format = FORMATO_VALOR
    aba.append([])

    # Totais de cada balancete (contas-mães) × soma das mesmas contas no patrimônio
    if resultado.contas_maes:
        cabecalho = ["Total do balancete (conta-mãe)", "Conta", "Saldo atual (balancete)",
                     "Mesmas contas no patrimônio", "Diferença"]
        aba.append(cabecalho)
        linha_cabecalho = aba.max_row
        for posicao in range(1, len(cabecalho) + 1):
            _estilo_cabecalho(aba.cell(row=linha_cabecalho, column=posicao), COR_GERAL)
        for mae in resultado.contas_maes:
            prefixo = mae.classificacao + "."
            no_patrimonio = sum(
                (i.saldo_patrimonio or Decimal(0) for i in resultado.itens
                 if i.conta_balancete is not None
                 and i.conta_balancete.classificacao.startswith(prefixo)),
                Decimal(0))
            aba.append([mae.descricao, mae.codigo, mae.saldo_atual, no_patrimonio,
                        no_patrimonio - mae.saldo_atual])
            for coluna in (3, 4, 5):
                aba.cell(row=aba.max_row, column=coluna).number_format = FORMATO_VALOR
        aba.append([])

    # Nada sumiu
    no_relatorio = sum(1 for i in resultado.itens if i.situacao in ORDEM_SITUACOES)
    ok = no_relatorio == len(resultado.itens)
    aba.append([f"Todas as contas aparecem no relatório ({no_relatorio} de {len(resultado.itens)})",
                "OK" if ok else "ATENÇÃO: confira"])
    aba.cell(row=aba.max_row, column=2).font = Font(bold=True, color=COR_OK if ok else COR_ERRO)

    _ajustar_larguras(aba, primeira_linha=3)
    aba.column_dimensions["A"].width = 45


def _aba_avisos(livro: Workbook, resultado: ResultadoBens) -> None:
    aba = livro.create_sheet(ABA_AVISOS)
    aba.append(COLUNAS_AVISOS)
    for posicao in range(1, len(COLUNAS_AVISOS) + 1):
        _estilo_cabecalho(aba.cell(row=1, column=posicao), COR_GERAL)
    for aviso in sorted(resultado.avisos, key=lambda a: 0 if a.tipo_arquivo else 1):
        aba.append([aviso.arquivo, aviso.tipo_arquivo or None, aviso.nivel, aviso.linhas_lidas,
                    aviso.unidades or None, aviso.mensagem])
        if aviso.eh_erro:
            aba.cell(row=aba.max_row, column=3).font = Font(bold=True, color=COR_ERRO)
    aba.freeze_panes = "A2"
    aba.auto_filter.ref = f"A1:{get_column_letter(len(COLUNAS_AVISOS))}{max(1, aba.max_row)}"
    _ajustar_larguras(aba)
