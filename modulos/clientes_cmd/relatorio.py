"""Geracao do relatorio final de conciliacao em Excel (.xlsx)."""

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

_CABECALHO = ["Cod", "Contábil", "Valor Contábil", "Financeiro", "Valor Financeiro", "Dif", "Status"]

_COR_CABECALHO = "1F4E78"
_COR_SEM_PAR = "FFF2CC"
_COR_DIVERGENTE = "FFC7CE"

_LARGURA_MINIMA = 10
_LARGURA_MAXIMA = 60

_COLUNA_DF_POR_INDICE = {
    1: "codigo",
    2: "contabil",
    3: "valor_contabil",
    4: "financeiro",
    5: "valor_financeiro",
}


def _valor_ou_none(valor):
    return None if pd.isna(valor) else valor


def _codigo_para_celula(codigo):
    codigo = _valor_ou_none(codigo)
    if isinstance(codigo, float) and codigo.is_integer():
        return int(codigo)
    return codigo


def gerar_relatorio(df_combinado, caminho_saida):
    """Grava df_combinado (saida de casamento.casar) como um .xlsx formatado.

    Dif e Status sao formulas do Excel (calculadas a partir das celulas da
    propria planilha, nao valores fixos vindos do Python):
    - Dif = C-E arredondado em 2 casas; mostra "-" se os valores baterem ou
      se faltar um dos dois lados.
    - Status = "SEM CONTABIL" sem codigo, "SEM FINANCEIRO" sem nome
      financeiro, "OK" se Dif = "-", senao "DIVERGENTE".
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Conciliacao"

    ws.append(_CABECALHO)
    fonte_cabecalho = Font(bold=True, color="FFFFFF")
    preenchimento_cabecalho = PatternFill("solid", fgColor=_COR_CABECALHO)
    for celula in ws[1]:
        celula.font = fonte_cabecalho
        celula.fill = preenchimento_cabecalho
        celula.alignment = Alignment(horizontal="center", vertical="center")

    preenchimento_sem_par = PatternFill("solid", fgColor=_COR_SEM_PAR)
    preenchimento_divergente = PatternFill("solid", fgColor=_COR_DIVERGENTE)

    for i, linha in enumerate(df_combinado.itertuples(index=False), start=2):
        codigo = _codigo_para_celula(linha.codigo)
        contabil = _valor_ou_none(linha.contabil)
        valor_contabil = _valor_ou_none(linha.valor_contabil)
        financeiro = _valor_ou_none(linha.financeiro)
        valor_financeiro = _valor_ou_none(linha.valor_financeiro)

        ws.cell(row=i, column=1, value=codigo)
        ws.cell(row=i, column=2, value=contabil)
        ws.cell(row=i, column=3, value=valor_contabil).number_format = "#,##0.00"
        ws.cell(row=i, column=4, value=financeiro)
        ws.cell(row=i, column=5, value=valor_financeiro).number_format = "#,##0.00"
        ws.cell(
            row=i,
            column=6,
            value=(
                f'=IF(OR(ISBLANK(C{i}),ISBLANK(E{i})),"-",'
                f'IF(ROUND(C{i}-E{i},2)=0,"-",ROUND(C{i}-E{i},2)))'
            ),
        ).number_format = "#,##0.00"
        ws.cell(
            row=i,
            column=7,
            value=(
                f'=IF(ISBLANK(A{i}),"SEM CONTÁBIL",'
                f'IF(ISBLANK(D{i}),"SEM FINANCEIRO",'
                f'IF(F{i}="-","OK","DIVERGENTE")))'
            ),
        )

        if codigo is None or financeiro is None:
            preenchimento = preenchimento_sem_par
        elif (
            valor_contabil is not None
            and valor_financeiro is not None
            and round(valor_contabil - valor_financeiro, 2) != 0
        ):
            preenchimento = preenchimento_divergente
        else:
            preenchimento = None

        if preenchimento is not None:
            for coluna in range(1, len(_CABECALHO) + 1):
                ws.cell(row=i, column=coluna).fill = preenchimento

    total_linhas = len(df_combinado) + 1
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(_CABECALHO))}{total_linhas}"

    _ajustar_largura_colunas(ws, df_combinado)

    wb.save(caminho_saida)


def _ajustar_largura_colunas(ws, df_combinado):
    larguras_minimas_extra = {6: len("-1.234.567,89"), 7: len("SEM FINANCEIRO")}

    for indice, cabecalho in enumerate(_CABECALHO, start=1):
        maior = max(len(cabecalho), larguras_minimas_extra.get(indice, 0))
        coluna_df = _COLUNA_DF_POR_INDICE.get(indice)
        if coluna_df is not None:
            tamanhos = df_combinado[coluna_df].dropna().astype(str).map(len)
            if not tamanhos.empty:
                maior = max(maior, int(tamanhos.max()))
        largura = min(max(maior + 2, _LARGURA_MINIMA), _LARGURA_MAXIMA)
        ws.column_dimensions[get_column_letter(indice)].width = largura
