"""Excel da EST-02: abas "Grupos" e "Operações" (ESPECIFICACAO_ESTOQUE.md, seção 6.3 "Saída").

Layout aprovado no exemplo Exemplo_EST-02_Grupos_SCF_09-2026.xlsx. Diferenças, somas e a
mensagem dos pares são FÓRMULAS; a formatação é a mesma do Excel da EST-01/03 (seção 5.3).
"""

from __future__ import annotations

from pathlib import Path

import openpyxl
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Font, PatternFill

from modulos.conciliacao_estoque import configuracao
from modulos.conciliacao_estoque.modelos import ConferenciaGrupoSCF, MesReferencia, ResultadoEST02
from modulos.conciliacao_estoque.relatorio_excel import (
    COR_DIFERENCA_FUNDO,
    COR_DIFERENCA_TEXTO,
    COR_GRUPO,
    FONTE,
    _FONTE_NEGRITO,
    _FONTE_NORMAL,
    _FONTE_SECAO,
    _escrever,
    _preparar_aba,
    _valor,
)

ABA_GRUPOS = "Grupos"
ABA_OPERACOES = "Operações"
COLUNAS_GRUPOS = [
    ("Grupo do Mapa do Estoque", 40), ("Total no Mapa do Estoque", 17), ("Soma das operações (PDF)", 22), ("Diferença", 14),
    ("Operações somadas", 40),
]
COLUNAS_OPERACOES = [
    ("Código", 9), ("Operação", 38), ("Valor (PDF)", 17), ("Grupo do Mapa do Estoque", 22), ("E/S na tabela", 13),
    ("Observação", 60),
]
_FONTE_DESTAQUE = Font(name=FONTE, size=11, bold=True, color=COR_DIFERENCA_TEXTO)


def nome_arquivo_est02(mes: MesReferencia | None) -> str:
    """EST-02 Conciliação contas estoque 09-2026.xlsx (nome da etapa: decisão de 06/10/2026)"""
    if mes is None:
        raise ValueError("Mês de referência não informado.")
    return f"{configuracao.ID_EST02} {configuracao.TITULO_EST02} {mes.para_nome_arquivo}.xlsx"


def nome_do_arquivo(resultado: ResultadoEST02) -> str:
    return nome_arquivo_est02(resultado.mes_referencia)


def gerar_excel_est02(resultado: ResultadoEST02, pasta_saida) -> Path:
    """Grava o Excel na pasta de saída (substitui se existir: a tela pergunta antes) e devolve o caminho."""
    caminho = Path(pasta_saida) / nome_do_arquivo(resultado)
    pasta_trabalho = openpyxl.Workbook()
    linha_total_operacoes = _aba_operacoes(pasta_trabalho.create_sheet(ABA_OPERACOES), resultado)
    _aba_grupos(pasta_trabalho.active, resultado, linha_total_operacoes)
    pasta_trabalho.save(caminho)
    return caminho


# ---------------------------------------------------------------------------
# Aba "Grupos"
# ---------------------------------------------------------------------------


def _aba_grupos(aba, resultado: ResultadoEST02, linha_total_operacoes: int):
    aba.title = ABA_GRUPOS
    _preparar_aba(
        aba, COLUNAS_GRUPOS,
        f"{configuracao.ID_EST02} · {configuracao.TITULO_EST02} · {resultado.mes_referencia}",
        f"Mapa do Estoque: {resultado.arquivo_scf} · PDF: {resultado.arquivo_pdf} · "
        f"Configuração: {resultado.arquivo_configuracao} ({resultado.origem_configuracao})",
    )
    colunas = len(COLUNAS_GRUPOS)
    linha = 5
    linhas_totais = []
    for grupos, total in ((resultado.entradas, resultado.total_entradas), (resultado.saidas, resultado.total_saidas)):
        primeira = linha
        for grupo in grupos:
            _linha_grupo(aba, linha, grupo, colunas)
            linha += 1
        _escrever(aba, linha, {
            1: total.nome, 2: _valor(total.total_scf),
            3: f"=SUM(C{primeira}:C{linha - 1})" if grupos else 0, 4: f"=B{linha}-C{linha}",
        }, colunas, _FONTE_NEGRITO, COR_GRUPO, numericas=(2, 3, 4))
        linhas_totais.append(linha)
        linha += 1
    linha_entradas, linha_saidas = linhas_totais

    linha += 1
    aba.cell(linha, 1, "Conferências").font = _FONTE_SECAO
    linha += 1
    _escrever(aba, linha, {
        1: "Total geral do PDF", 2: _valor(resultado.total_geral_pdf),
        3: f"='{ABA_OPERACOES}'!C{linha_total_operacoes}", 4: f"=B{linha}-C{linha}",
        5: "Soma de todas as operações lidas (aba Operações)",
    }, colunas, numericas=(2, 3, 4))
    linha += 1
    _escrever(aba, linha, {
        1: "Fechamento do total geral (Mapa do Estoque)", 2: _valor(resultado.saldo_atual_scf),
        3: f"={_valor(resultado.saldo_anterior_scf)}+B{linha_entradas}-B{linha_saidas}", 4: f"=B{linha}-C{linha}",
        5: "Saldo atual x (Saldo anterior + Total (E) − Total (S))",
    }, colunas, numericas=(2, 3, 4))
    linha += 1
    primeiro_par = linha
    for par in resultado.pares:
        _escrever(aba, linha, {
            1: f"{par.nome_a} (op. {par.par.operacao_a}) x {par.nome_b} (op. {par.par.operacao_b})",
            2: _valor(par.valor_a), 3: _valor(par.valor_b), 4: f"=B{linha}-C{linha}",
            5: f'=IF(ROUND(D{linha},2)<>0,"{par.mensagem_atencao}","{par.mensagem_ok}")',
        }, colunas, numericas=(2, 3, 4))
        linha += 1
    ultima = linha - 1

    regra = dict(font=Font(color=COR_DIFERENCA_TEXTO, bold=True), fill=PatternFill("solid", bgColor=COR_DIFERENCA_FUNDO))
    aba.conditional_formatting.add(f"D5:D{ultima}", FormulaRule(formula=["AND(ISNUMBER(D5),ROUND(D5,2)<>0)"], **regra))
    if resultado.pares:
        aba.conditional_formatting.add(f"E{primeiro_par}:E{ultima}",
                                       FormulaRule(formula=[f"ROUND(D{primeiro_par},2)<>0"], **regra))
    aba.freeze_panes = "A5"


def _linha_grupo(aba, linha: int, grupo: ConferenciaGrupoSCF, colunas: int):
    _escrever(aba, linha, {
        1: grupo.nome, 2: _valor(grupo.total_scf), 3: _valor(grupo.soma_pdf), 4: f"=B{linha}-C{linha}",
        5: ", ".join(map(str, grupo.operacoes)) or "—",
    }, colunas, numericas=(2, 3, 4))


# ---------------------------------------------------------------------------
# Aba "Operações"
# ---------------------------------------------------------------------------


def _aba_operacoes(aba, resultado: ResultadoEST02) -> int:
    """Escreve a aba e devolve a linha do TOTAL (usada na conferência do Total geral)."""
    # nesta aba o cabeçalho fica na linha 3 (layout aprovado)
    _preparar_aba(aba, COLUNAS_OPERACOES, "Operações do PDF e grupo de cada uma", "", linha_cabecalho=3)

    colunas = len(COLUNAS_OPERACOES)
    linha = 4
    for operacao in resultado.operacoes:
        _escrever(aba, linha, {
            1: operacao.codigo, 2: operacao.nome, 3: _valor(operacao.valor),
            4: operacao.grupo or "Sem grupo", 5: operacao.es_tabela or None, 6: operacao.observacao or None,
        }, colunas, _FONTE_DESTAQUE if operacao.sem_grupo else _FONTE_NORMAL,
            COR_DIFERENCA_FUNDO if operacao.sem_grupo else None, numericas=(3,))
        linha += 1
    ultima = linha - 1
    _escrever(aba, linha, {2: "TOTAL", 3: f"=SUM(C4:C{ultima})" if resultado.operacoes else 0},
              colunas, _FONTE_NEGRITO, COR_GRUPO, numericas=(3,))
    aba.auto_filter.ref = f"A3:F{max(ultima, 3)}"
    aba.freeze_panes = "A4"
    return linha
