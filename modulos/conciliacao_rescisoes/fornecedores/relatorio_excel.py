"""
Planilha da Conciliação Fornecedores (ESPECIFICACAO seção 16.5), no modelo das planilhas
conferidas pelo usuário: abas "Resumo" e "Conciliação Completa", mais a aba "Títulos das
diferenças" (uma linha por título dos fornecedores que não deram OK, com Nr. Doc. na coluna B e
Nr. Título na coluna C, para procurar no Tasy).

Diferença, TOTAL e contagens são FÓRMULAS do Excel, para quem concilia poder conferir.
Arial 10 em tudo, exceto os títulos. Quem decide nome e pasta é processar_fornecedores().
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from modulos.conciliacao_rescisoes.fornecedores.leitores import nome_curto_unidade, reais
from modulos.conciliacao_rescisoes.fornecedores.modelos import (
    NOMES_RESUMO,
    SITUACAO_DIVERGENTE,
    SITUACAO_OK,
    SITUACAO_SO_BALANCETE,
    SITUACAO_SO_RELATORIO,
    ResultadoFornecedores,
)

ABA_RESUMO = "Resumo"
ABA_COMPLETA = "Conciliação Completa"
ABA_TITULOS = "Títulos das diferenças"
TRAVESSAO = "—"

AZUL = "1F4E78"
CINZA = "595959"
VERMELHO_FUNDO, VERMELHO_TEXTO = "FFC7CE", "9C0006"
AMARELO_FUNDO, AMARELO_TEXTO = "FFEB9C", "9C6500"
TOTAL_FUNDO = "D9E1F2"
BORDA = "BFBFBF"

FORMATO_VALOR = "#,##0.00_);[Red](#,##0.00)"
FORMATO_NOTA = "0.00"
FONTE = "Arial"

_MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

COLUNAS_COMPLETA = ["Código (Balancete)", "Descrição (Balancete)", "Fornecedor (Rel. Financeiro)",
                    "Saldo Balancete", "Saldo Rel. Financeiro", "Diferença", "Confiança do Pareamento",
                    "Situação"]
LARGURAS_COMPLETA = {"A": 16, "B": 42, "C": 42, "D": 16, "E": 18, "F": 14, "G": 16, "H": 20}
COLUNAS_RESUMO = ["Código", "Fornecedor", "Saldo Balancete", "Saldo Rel. Financeiro", "Diferença",
                  "Situação"]
LARGURAS_RESUMO = {"A": 2, "B": 12, "C": 40, "D": 18, "E": 20, "F": 16, "G": 24}
COLUNAS_TITULOS = ["Fornecedor (Rel. Financeiro)", "Nr. Doc.", "Nr. Título", "Tipo Título", "Dt. Emissão",
                   "Dt. Vencimento", "Vl. Saldo", "Código (Balancete)", "Situação"]
LARGURAS_TITULOS = {"A": 42, "B": 16, "C": 14, "D": 14, "E": 13, "F": 15, "G": 16, "H": 18, "I": 20}
FORMATO_DATA = "dd/mm/yyyy"


def mes_curto(mes: date | None) -> str:
    """date(2026, 9, 1) → "set/2026"."""
    return "" if mes is None else f"{_MESES[mes.month - 1]}/{mes.year}"


def _fonte(**extras) -> Font:
    return Font(name=FONTE, size=extras.pop("size", 10), **extras)


def _preencher(celula, cor: str) -> None:
    celula.fill = PatternFill("solid", start_color=cor, end_color=cor)


def _cabecalho(celula) -> None:
    celula.font = _fonte(bold=True, color="FFFFFF")
    _preencher(celula, AZUL)
    celula.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def gerar_relatorio_fornecedores(resultado: ResultadoFornecedores, caminho: Path) -> Path:
    livro = Workbook()
    resumo = livro.active
    resumo.title = ABA_RESUMO
    completa = livro.create_sheet(ABA_COMPLETA)
    linha_total, ultima = _aba_completa(completa, resultado)
    _aba_resumo(resumo, resultado, linha_total, ultima)
    _aba_titulos(livro.create_sheet(ABA_TITULOS), resultado)
    caminho = Path(caminho)
    livro.save(caminho)
    return caminho


def _aba_completa(aba, resultado: ResultadoFornecedores) -> tuple[int, int]:
    """Devolve (linha do TOTAL, última linha de dados)."""
    unidade = nome_curto_unidade(resultado.unidade).replace(" - ", " ")
    titulo = f"Conciliação Completa — Fornecedores — {unidade} ({mes_curto(resultado.mes)})"
    aba["A1"] = titulo
    aba["A1"].font = _fonte(size=14, bold=True, color=AZUL)

    for coluna, texto in enumerate(COLUNAS_COMPLETA, start=1):
        _cabecalho(aba.cell(row=3, column=coluna, value=texto))
    aba.row_dimensions[3].height = 30

    lado = Side(style="thin", color=BORDA)
    borda = Border(left=lado, right=lado, top=lado, bottom=lado)
    numero = 3
    for linha in resultado.linhas:
        numero += 1
        conta = linha.conta
        valores = [
            conta.codigo if conta else TRAVESSAO,
            conta.descricao if conta else TRAVESSAO,
            linha.nome_financeiro or TRAVESSAO,
            linha.saldo_balancete if conta else TRAVESSAO,
            linha.saldo_financeiro if linha.financeiros else TRAVESSAO,
            (f"=D{numero}-E{numero}" if conta and linha.financeiros
             else linha.saldo_balancete if conta else f"=-E{numero}"),
            round(linha.nota, 2) if linha.nota is not None else TRAVESSAO,
            linha.situacao,
        ]
        for coluna, valor in enumerate(valores, start=1):
            celula = aba.cell(row=numero, column=coluna, value=valor)
            celula.font = _fonte()
            celula.border = borda
            if coluna in (4, 5, 6):
                celula.number_format = FORMATO_VALOR
            elif coluna == 7:
                celula.number_format = FORMATO_NOTA
    ultima = max(numero, 4)

    linha_total = ultima + 2
    aba.cell(row=linha_total, column=2, value="TOTAL")
    aba.cell(row=linha_total, column=4, value=f"=SUM(D4:D{ultima})")
    aba.cell(row=linha_total, column=5, value=f"=SUM(E4:E{ultima})")
    aba.cell(row=linha_total, column=6, value=f"=D{linha_total}-E{linha_total}")
    for coluna in range(1, 9):
        celula = aba.cell(row=linha_total, column=coluna)
        celula.font = _fonte(bold=True)
        celula.border = borda
        _preencher(celula, TOTAL_FUNDO)
        if coluna in (4, 5, 6):
            celula.number_format = FORMATO_VALOR

    intervalo = f"H4:H{ultima}"
    for situacao, fundo, texto in [(SITUACAO_DIVERGENTE, VERMELHO_FUNDO, VERMELHO_TEXTO),
                                   (SITUACAO_SO_BALANCETE, AMARELO_FUNDO, AMARELO_TEXTO),
                                   (SITUACAO_SO_RELATORIO, AMARELO_FUNDO, AMARELO_TEXTO)]:
        aba.conditional_formatting.add(intervalo, CellIsRule(
            operator="equal", formula=[f'"{situacao}"'], font=Font(color=texto),
            fill=PatternFill("solid", start_color=fundo, end_color=fundo)))
    aba.freeze_panes = "A4"
    aba.auto_filter.ref = f"A3:H{ultima}"
    for coluna, largura in LARGURAS_COMPLETA.items():
        aba.column_dimensions[coluna].width = largura
    return linha_total, ultima


def _aba_resumo(aba, resultado: ResultadoFornecedores, linha_total: int, ultima: int) -> None:
    completa = f"'{ABA_COMPLETA}'"
    aba["B2"] = "Conciliação — Balancete de Fornecedores x Relatório Financeiro"
    aba["B2"].font = _fonte(size=14, bold=True, color=AZUL)
    aba["B3"] = f"{resultado.unidade} — Mês Referência: {mes_curto(resultado.mes)}"
    aba["B4"] = (f"{resultado.arquivo_balancete} (contábil, saldo atual)  x  {resultado.arquivo_titulos} "
                 f"(títulos a pagar, analítico)")
    for celula in ("B3", "B4"):
        aba[celula].font = _fonte(color=CINZA)

    totais = [
        ("Total contábil (Balancete — conta 2111, Fornecedores no País)", resultado.total_balancete, True),
        ("Total apurado no Relatório Financeiro (Títulos a pagar)", f"={completa}!E{linha_total}", True),
        ("Diferença total", f"={completa}!D{linha_total}-{completa}!E{linha_total}", True),
        ("Fornecedores conciliados sem divergência", f'=COUNTIF({completa}!H4:H{ultima},"OK")', False),
        ("Itens com divergência ou sem correspondência",
         f'=COUNTIFS({completa}!H4:H{ultima},"<>OK")', False),
    ]
    for deslocamento, (rotulo, valor, eh_dinheiro) in enumerate(totais):
        linha = 6 + deslocamento
        aba.cell(row=linha, column=2, value=rotulo).font = _fonte(bold=True)
        celula = aba.cell(row=linha, column=5, value=valor)
        celula.font = _fonte(bold=True)
        celula.number_format = FORMATO_VALOR if eh_dinheiro else "0"

    aba["B12"] = "Divergências e Itens Sem Correspondência"
    aba["B12"].font = _fonte(size=12, bold=True, color=AZUL)
    for coluna, texto in enumerate(COLUNAS_RESUMO, start=2):
        _cabecalho(aba.cell(row=13, column=coluna, value=texto))

    numero = 13
    for linha in (l for l in resultado.linhas if l.situacao != SITUACAO_OK):
        numero += 1
        conta = linha.conta
        if linha.situacao == SITUACAO_DIVERGENTE:
            diferenca = f"=D{numero}-E{numero}"
        else:
            diferenca = linha.diferenca
        valores = [
            conta.codigo if conta else TRAVESSAO,
            conta.descricao if conta else linha.nome_financeiro,
            linha.saldo_balancete if conta else TRAVESSAO,
            linha.saldo_financeiro if linha.financeiros else TRAVESSAO,
            diferenca,
            NOMES_RESUMO[linha.situacao],
        ]
        for coluna, valor in enumerate(valores, start=2):
            celula = aba.cell(row=numero, column=coluna, value=valor)
            celula.font = _fonte(bold=True, color=VERMELHO_TEXTO)
            _preencher(celula, VERMELHO_FUNDO)
            if coluna in (4, 5, 6):
                celula.number_format = FORMATO_VALOR

    numero += 2
    for posicao_nota, texto in enumerate(resultado.notas, start=1):
        celula = aba.cell(row=numero, column=2, value=f"Nota {posicao_nota}: {texto}")
        celula.font = _fonte(italic=True, color=CINZA)
        numero += 1
    for coluna, largura in LARGURAS_RESUMO.items():
        aba.column_dimensions[coluna].width = largura


def _numero_documento(texto: str):
    """Só dígitos → número (o Excel não reclama de "número salvo como texto"); outro → texto."""
    return int(texto) if texto.isdigit() and len(texto) <= 15 else (texto or TRAVESSAO)


def _aba_titulos(aba, resultado: ResultadoFornecedores) -> None:
    """Uma linha por título dos fornecedores que não deram OK (DIVERGENTE ou SÓ NO RELATÓRIO)."""
    unidade = nome_curto_unidade(resultado.unidade).replace(" - ", " ")
    aba["A1"] = f"Títulos das diferenças — Fornecedores — {unidade} ({mes_curto(resultado.mes)})"
    aba["A1"].font = _fonte(size=14, bold=True, color=AZUL)
    aba["A2"] = ("Títulos do relatório analítico dos fornecedores com diferença. Use o Nr. Doc. e o "
                 "Nr. Título para procurar no Tasy. Contas só no balancete não têm títulos no financeiro.")
    aba["A2"].font = _fonte(italic=True, color=CINZA)
    for coluna, texto in enumerate(COLUNAS_TITULOS, start=1):
        _cabecalho(aba.cell(row=3, column=coluna, value=texto))
    aba.row_dimensions[3].height = 30

    lado = Side(style="thin", color=BORDA)
    borda = Border(left=lado, right=lado, top=lado, bottom=lado)
    numero = 3
    for linha in resultado.linhas:
        if linha.situacao == SITUACAO_OK:
            continue
        for fornecedor in linha.financeiros:
            for titulo in fornecedor.titulos:
                numero += 1
                valores = [
                    fornecedor.nome,
                    _numero_documento(titulo.documento),
                    _numero_documento(titulo.numero),
                    titulo.tipo or TRAVESSAO,
                    titulo.emissao or TRAVESSAO,
                    titulo.vencimento or TRAVESSAO,
                    titulo.saldo,
                    linha.conta.codigo if linha.conta else TRAVESSAO,
                    linha.situacao,
                ]
                for coluna, valor in enumerate(valores, start=1):
                    celula = aba.cell(row=numero, column=coluna, value=valor)
                    celula.font = _fonte()
                    celula.border = borda
                    if coluna in (2, 3) and isinstance(valor, int):
                        celula.number_format = "0"
                    elif coluna in (5, 6) and isinstance(valor, date):
                        celula.number_format = FORMATO_DATA
                    elif coluna == 7:
                        celula.number_format = FORMATO_VALOR

    if numero == 3:
        aba["A4"] = "Nenhum fornecedor com diferença tem títulos no relatório financeiro."
        aba["A4"].font = _fonte(italic=True, color=CINZA)
    else:
        linha_total = numero + 2
        aba.cell(row=linha_total, column=1, value="TOTAL")
        aba.cell(row=linha_total, column=7, value=f"=SUM(G4:G{numero})")
        for coluna in range(1, len(COLUNAS_TITULOS) + 1):
            celula = aba.cell(row=linha_total, column=coluna)
            celula.font = _fonte(bold=True)
            celula.border = borda
            _preencher(celula, TOTAL_FUNDO)
            if coluna == 7:
                celula.number_format = FORMATO_VALOR
        aba.auto_filter.ref = f"A3:I{numero}"
    aba.freeze_panes = "A4"
    for coluna, largura in LARGURAS_TITULOS.items():
        aba.column_dimensions[coluna].width = largura


__all__ = ["gerar_relatorio_fornecedores", "mes_curto", "reais", "ABA_TITULOS"]
