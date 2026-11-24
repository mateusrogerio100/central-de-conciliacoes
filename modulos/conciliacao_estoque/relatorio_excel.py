"""Excel da EST-01 e da EST-03: abas "Conciliação" e "Análise" (ESPECIFICACAO_ESTOQUE.md, seção 5).

Layout aprovado no exemplo Exemplo_Conciliacao_Estoque_09-2026.xlsx, com os acréscimos da
especificação (título com a etapa, conferência de cada grupo e do SCF com os locais sem conta).
Diferenças e totais são FÓRMULAS; os valores são gravados em float arredondado a 2 casas.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import openpyxl
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from modulos.conciliacao_estoque.comparacao import RECOMENDACAO_CONTAS_ZERADAS
from modulos.conciliacao_estoque.modelos import ComoCasou, Etapa, LinhaComparacao, MesReferencia, ResultadoComparacao

# ---------------------------------------------------------------------------
# Formatação (seção 5.3)
# ---------------------------------------------------------------------------

FONTE = "Arial"
COR_PRINCIPAL = "0F5C63"        # cabeçalho e título
COR_SUBTITULO = "586462"
COR_GRUPO = "E3EEEC"            # linhas de grupo e de total
COR_SUBTOTAL = "F4F2EC"
COR_BORDA = "E2DED3"
COR_DIFERENCA_FUNDO = "FBEEDD"
COR_DIFERENCA_TEXTO = "A44A07"
FORMATO_NUMERO = '#,##0.00;[Red]-#,##0.00;"-"'

_FONTE_NORMAL = Font(name=FONTE, size=11)
_FONTE_NEGRITO = Font(name=FONTE, size=11, bold=True)
_FONTE_TITULO = Font(name=FONTE, size=14, bold=True, color=COR_PRINCIPAL)
_FONTE_SUBTITULO = Font(name=FONTE, size=10, color=COR_SUBTITULO)
_FONTE_CABECALHO = Font(name=FONTE, size=11, bold=True, color="FFFFFF")
_FONTE_SECAO = Font(name=FONTE, size=11, bold=True, color=COR_PRINCIPAL)
_BORDA = Border(bottom=Side(style="thin", color=COR_BORDA))
_ALINHAMENTO = Alignment(vertical="bottom", wrap_text=False)
_ALINHAMENTO_CABECALHO = Alignment(horizontal="center", vertical="center", wrap_text=True)

ABA_CONCILIACAO = "Conciliação"
ABA_ANALISE = "Análise"

COLUNAS_CONCILIACAO = [
    ("Classificação", 17), ("Código", 9), ("Descrição no balancete", 46), ("Saldo balancete", 16),
    ("Descrição no Mapa do Estoque", 46), ("Saldo Mapa do Estoque", 16), ("Diferença", 14), ("Como casou", 26), ("Observação", 40),
]
COLUNAS_ANALISE = [
    ("Classificação", 17), ("Descrição no balancete", 48), ("Saldo balancete", 17), ("Saldo Mapa do Estoque", 15),
    ("Diferença", 15), ("Código", 10), ("Observação", 48),
]


def nome_arquivo_etapa(etapa: Etapa, mes: MesReferencia | None) -> str:
    """EST-01 Conciliação saldo anterior estoque 09-2026.xlsx (nome da etapa: decisão de 06/10/2026)"""
    if mes is None:
        raise ValueError("Mês de referência não informado.")
    return f"{etapa.id} {etapa.titulo} {mes.para_nome_arquivo}.xlsx"


def nome_do_arquivo(resultado: ResultadoComparacao) -> str:
    return nome_arquivo_etapa(resultado.etapa, resultado.mes_referencia)


def gerar_excel(resultado: ResultadoComparacao, pasta_saida) -> Path:
    """Grava o Excel na pasta de saída (substitui se existir: a tela pergunta antes) e devolve o caminho."""
    caminho = Path(pasta_saida) / nome_do_arquivo(resultado)
    pasta_trabalho = openpyxl.Workbook()
    _aba_conciliacao(pasta_trabalho.active, resultado)
    _aba_analise(pasta_trabalho.create_sheet(ABA_ANALISE), resultado)
    pasta_trabalho.save(caminho)
    return caminho


# ---------------------------------------------------------------------------
# Peças comuns
# ---------------------------------------------------------------------------


def _valor(numero: Decimal | None) -> float | None:
    return None if numero is None else float(round(numero, 2))


def _preparar_aba(aba, colunas, titulo: str, subtitulo: str, linha_cabecalho: int = 4):
    aba.sheet_view.showGridLines = False
    for indice, (nome, largura) in enumerate(colunas, start=1):
        aba.column_dimensions[get_column_letter(indice)].width = largura
        celula = aba.cell(linha_cabecalho, indice, nome)
        celula.font = _FONTE_CABECALHO
        celula.fill = PatternFill("solid", fgColor=COR_PRINCIPAL)
        celula.alignment = _ALINHAMENTO_CABECALHO
    aba.cell(1, 1, titulo).font = _FONTE_TITULO
    if subtitulo:
        aba.cell(2, 1, subtitulo).font = _FONTE_SUBTITULO
        aba.row_dimensions[2].height = 15
    aba.row_dimensions[1].height = 17.35
    aba.row_dimensions[linha_cabecalho].height = 30


def _escrever(aba, linha: int, valores: dict[int, object], quantidade_colunas: int,
              fonte=_FONTE_NORMAL, preenchimento: str | None = None, numericas=()):
    """Escreve uma linha: valores por coluna (1 = A), borda inferior em todas as colunas."""
    for coluna in range(1, quantidade_colunas + 1):
        celula = aba.cell(linha, coluna)
        if coluna in valores and valores[coluna] is not None:
            celula.value = valores[coluna]
        celula.font = fonte
        celula.border = _BORDA
        celula.alignment = _ALINHAMENTO
        if preenchimento:
            celula.fill = PatternFill("solid", fgColor=preenchimento)
        if coluna in numericas:
            celula.number_format = FORMATO_NUMERO
    aba.row_dimensions[linha].height = 15


def _destacar_diferencas(aba, coluna: str, primeira: int, ultima: int):
    """Diferença (arredondada) diferente de zero: fundo laranja-claro e texto laranja-escuro em negrito."""
    if ultima < primeira:
        return
    aba.conditional_formatting.add(
        f"{coluna}{primeira}:{coluna}{ultima}",
        FormulaRule(
            formula=[f"ROUND({coluna}{primeira},2)<>0"],
            font=Font(color=COR_DIFERENCA_TEXTO, bold=True),
            fill=PatternFill("solid", bgColor=COR_DIFERENCA_FUNDO),
        ),
    )


def _locais_sem_conta(resultado: ResultadoComparacao) -> list[LinhaComparacao]:
    return sorted(resultado.locais_sem_conta, key=lambda l: l.local_scf)


# ---------------------------------------------------------------------------
# Aba "Conciliação"
# ---------------------------------------------------------------------------


def _aba_conciliacao(aba, resultado: ResultadoComparacao):
    etapa = resultado.etapa
    aba.title = ABA_CONCILIACAO
    _preparar_aba(
        aba, COLUNAS_CONCILIACAO,
        f"{etapa.id} · {etapa.titulo} · {resultado.mes_referencia}",
        f"Mês de referência: {resultado.mes_referencia}   ·   Balancete: {resultado.arquivo_balancete}"
        f"   ·   Mapa do Estoque: {resultado.arquivo_scf}",
    )
    colunas = len(COLUNAS_CONCILIACAO)
    numericas = (4, 6, 7)
    linha = 5

    linhas_subtotal: dict[str, int] = {}
    for grupo in resultado.grupos:
        _escrever(aba, linha, {1: grupo.classificacao, 3: grupo.descricao}, colunas,
                  _FONTE_NEGRITO, COR_GRUPO)
        linha += 1
        primeira = linha
        for conta in (c for c in resultado.contas if c.grupo == grupo.classificacao):
            _escrever(aba, linha, {
                1: conta.classificacao, 2: conta.codigo, 3: conta.descricao_balancete,
                4: _valor(conta.saldo_balancete), 5: conta.descricao_scf or None,
                6: _valor(conta.saldo_scf), 7: f"=D{linha}-F{linha}",
                8: conta.como.texto, 9: conta.observacao or None,
            }, colunas, numericas=numericas)
            linha += 1
        if linha > primeira:
            somas = {c: f"=SUM({l}{primeira}:{l}{linha - 1})" for c, l in ((4, "D"), (6, "F"), (7, "G"))}
        else:
            somas = {4: 0, 6: 0, 7: 0}
        _escrever(aba, linha, {3: f"Subtotal {grupo.classificacao}", **somas}, colunas,
                  _FONTE_NEGRITO, COR_SUBTOTAL, numericas)
        linhas_subtotal[grupo.classificacao] = linha
        linha += 1

    linha_total = linha
    if linhas_subtotal:
        totais = {c: "=" + "+".join(f"{l}{n}" for n in linhas_subtotal.values())
                  for c, l in ((4, "D"), (6, "F"), (7, "G"))}
    else:
        totais = {4: 0, 6: 0, 7: 0}
    _escrever(aba, linha_total, {3: "TOTAL GERAL", **totais}, colunas, _FONTE_NEGRITO, COR_GRUPO, numericas)
    _destacar_diferencas(aba, "G", 5, linha_total)

    # Os locais sem conta ficam no fim; a conferência do SCF precisa saber onde.
    locais = _locais_sem_conta(resultado)
    linha_conferencias = linha_total + 2
    quantidade_conferencias = 2 + len(resultado.grupos)
    linha_secao_locais = linha_conferencias + quantidade_conferencias + 2
    primeira_local, ultima_local = linha_secao_locais + 1, linha_secao_locais + len(locais)

    aba.cell(linha_conferencias, 3, "Conferências").font = _FONTE_SECAO
    linha = linha_conferencias + 1
    _conferencia(aba, linha, "Saldo do grupo 1.01.04 ESTOQUES no balancete", resultado.saldo_sintetica_raiz,
                 "Diferença para a soma das contas:", f"=D{linha}-D{linha_total}")
    linha += 1
    soma_scf = f"F{linha_total}" + (f"+SUM(F{primeira_local}:F{ultima_local})" if locais else "")
    _conferencia(aba, linha, 'Total geral do Mapa do Estoque (linha "Total")', resultado.total_scf,
                 "Diferença para as contas e os locais sem conta:", f"=D{linha}-({soma_scf})")
    linha += 1
    for grupo in resultado.grupos:
        _conferencia(aba, linha, f"Saldo do grupo {grupo.classificacao} {grupo.descricao} no balancete".replace("  ", " "),
                     grupo.saldo_sintetica, "Diferença para o subtotal do grupo:",
                     f"=D{linha}-D{linhas_subtotal[grupo.classificacao]}",
                     f"{grupo.causa_provavel}. {RECOMENDACAO_CONTAS_ZERADAS}." if grupo.causa_provavel else "")
        linha += 1
    _destacar_diferencas(aba, "F", linha_conferencias + 1, linha - 1)

    _escrever(aba, linha_secao_locais, {1: "Locais do Mapa do Estoque sem conta no balancete"}, colunas,
              _FONTE_NEGRITO, COR_GRUPO)
    for linha, local in enumerate(locais, start=primeira_local):
        _escrever(aba, linha, {
            5: local.descricao_scf, 6: _valor(local.saldo_scf), 8: ComoCasou.SEM_PAR.texto, 9: local.observacao,
        }, colunas, numericas=(6,))

    aba.freeze_panes = "D5"


def _conferencia(aba, linha, rotulo, valor, rotulo_diferenca, formula, observacao=""):
    for coluna, conteudo in ((3, rotulo), (4, _valor(valor)), (5, rotulo_diferenca), (6, formula),
                             (7, observacao or None)):
        celula = aba.cell(linha, coluna)
        if conteudo is not None:
            celula.value = conteudo
        celula.font = _FONTE_NORMAL
        celula.border = _BORDA
        celula.alignment = _ALINHAMENTO
        if coluna in (4, 6):
            celula.number_format = FORMATO_NUMERO
    aba.row_dimensions[linha].height = 15


# ---------------------------------------------------------------------------
# Aba "Análise"
# ---------------------------------------------------------------------------


def _aba_analise(aba, resultado: ResultadoComparacao):
    _preparar_aba(
        aba, COLUNAS_ANALISE,
        f"Análise das diferenças — {resultado.mes_referencia}",
        "Use o filtro da coluna Diferença para ver só o que precisa corrigir.",
    )
    colunas = len(COLUNAS_ANALISE)
    numericas = (3, 4, 5)
    linhas = resultado.contas + _locais_sem_conta(resultado)
    linha = 5
    for item in linhas:
        _escrever(aba, linha, {
            1: item.classificacao or None,     # decisão do usuário (06/10/2026): classificação
            2: item.descricao_balancete or item.descricao_scf,
            3: _valor(item.saldo_balancete), 4: _valor(item.saldo_scf), 5: f"=C{linha}-D{linha}",
            # pedido do usuário (05/11/2026): o código da conta ao lado da diferença, para lançar a correção no Tasy
            6: item.codigo,
            7: item.observacao or None,
        }, colunas, numericas=numericas)
        linha += 1
    ultima = linha - 1
    somas = {c: f"=SUBTOTAL(9,{l}5:{l}{ultima})" for c, l in ((3, "C"), (4, "D"), (5, "E"))} if linhas else {}
    _escrever(aba, linha, {2: "TOTAL", **somas}, colunas, _FONTE_NEGRITO, COR_GRUPO, numericas)
    aba.auto_filter.ref = f"A4:G{max(ultima, 4)}"
    _destacar_diferencas(aba, "E", 5, ultima)
    aba.freeze_panes = "A5"
