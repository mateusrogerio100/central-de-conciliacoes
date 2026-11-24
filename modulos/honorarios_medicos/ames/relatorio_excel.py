"""
Planilha da Conciliação Honorários (ESPECIFICACAO seção 18.3), no modelo da planilha conferida pelo
Usuário (Conciliacao_HonorariosMedicos_CidadeDelta_set2026.xlsx): abas "Resumo", "Conciliação Completa"
(uma coluna de repasse por grupo) e "Repasses (detalhe)" (um repasse por linha).

Totais, diferenças, retenções e contagens são FÓRMULAS do Excel, para quem concilia poder conferir.
Arial 10 em tudo, exceto os títulos. Quem decide nome e pasta é processar_honorarios().
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from modulos.honorarios_medicos.fornecedores.leitores import nome_curto_unidade
from modulos.honorarios_medicos.fornecedores.relatorio_excel import (
    AMARELO_FUNDO,
    AMARELO_TEXTO,
    AZUL,
    BORDA,
    CINZA,
    FORMATO_NOTA,
    FORMATO_VALOR,
    TOTAL_FUNDO,
    TRAVESSAO,
    VERMELHO_FUNDO,
    VERMELHO_TEXTO,
    _cabecalho,
    _fonte,
    _preencher,
    mes_curto,
)
from modulos.honorarios_medicos.ames.modelos import (
    NOMES_RESUMO,
    SITUACAO_DIVERGENTE,
    SITUACAO_OK,
    SITUACAO_SO_BALANCETE,
    SITUACAO_SO_REPASSE,
    ResultadoHonorarios,
)

ABA_RESUMO = "Resumo"
ABA_COMPLETA = "Conciliação Completa"
ABA_DETALHE = "Repasses (detalhe)"

COLUNAS_DETALHE = ["Grupo", "Terceiro", "Nr Repasse", "Dt Ref", "Status", "Vl repasse (bruto)",
                   "Vl. Líquido", "Retenções (bruto − líquido)", "Conta Balancete"]
LARGURAS_DETALHE = {"A": 18, "B": 46, "C": 12, "D": 12, "E": 8, "F": 16, "G": 16, "H": 18, "I": 14}
COLUNAS_RESUMO = ["Código", "Médico/clínica", "Saldo Balancete", "Total Repasse (bruto)", "Diferença",
                  "Situação"]
LARGURAS_RESUMO = {"A": 2, "B": 14, "C": 40, "D": 18, "E": 20, "F": 16, "G": 16}
FORMATO_DATA = "dd/mm/yyyy"


def _borda() -> Border:
    lado = Side(style="thin", color=BORDA)
    return Border(left=lado, right=lado, top=lado, bottom=lado)


def _unidade_titulo(resultado: ResultadoHonorarios) -> str:
    return nome_curto_unidade(resultado.unidade).replace(" - ", " ")


def gerar_relatorio_honorarios(resultado: ResultadoHonorarios, caminho: Path) -> Path:
    livro = Workbook()
    resumo = livro.active
    resumo.title = ABA_RESUMO
    completa = livro.create_sheet(ABA_COMPLETA)
    detalhe = livro.create_sheet(ABA_DETALHE)
    total_completa, ultima_completa, colunas = _aba_completa(completa, resultado)
    ultima_detalhe = _aba_detalhe(detalhe, resultado)
    _aba_resumo(resumo, resultado, total_completa, ultima_completa, colunas, ultima_detalhe)
    caminho = Path(caminho)
    livro.save(caminho)
    return caminho


def _aba_completa(aba, resultado: ResultadoHonorarios) -> tuple[int, int, dict[str, str]]:
    """Devolve (linha do TOTAL, última linha de dados, letras das colunas)."""
    grupos = resultado.grupos
    n = len(grupos)
    letra = {
        "saldo": "D",
        "primeiro_grupo": "E",
        "ultimo_grupo": get_column_letter(4 + max(n, 1)),
        "total": get_column_letter(5 + n),
        "diferenca": get_column_letter(6 + n),
        "nota": get_column_letter(7 + n),
        "situacao": get_column_letter(8 + n),
        "liquido": get_column_letter(9 + n),
    }
    cabecalho = (["Código (Balancete)", "Descrição (Balancete)", "Terceiro (Repasse SCF)", "Saldo Balancete"]
                 + [f"Repasse {g}" for g in grupos]
                 + ["Total Repasse (bruto)", "Diferença", "Confiança do Pareamento", "Situação",
                    "Vl. Líquido (Repasse)"])
    aba["A1"] = (f"Conciliação Completa — Honorários Médicos — {_unidade_titulo(resultado)} "
                 f"({mes_curto(resultado.mes)})")
    aba["A1"].font = _fonte(size=14, bold=True, color=AZUL)
    for coluna, texto in enumerate(cabecalho, start=1):
        _cabecalho(aba.cell(row=3, column=coluna, value=texto))
    aba.row_dimensions[3].height = 30

    borda = _borda()
    colunas_dinheiro = {4, *range(5, 5 + n), 5 + n, 6 + n, 9 + n}
    numero = 3
    for linha in resultado.linhas:
        numero += 1
        conta = linha.conta
        valores = [
            conta.codigo if conta else TRAVESSAO,
            conta.descricao if conta else TRAVESSAO,
            linha.nome_repasse or TRAVESSAO,
            linha.saldo_balancete,
        ]
        for grupo in grupos:
            tem = any(r.grupo == grupo for t in linha.terceiros for r in t.repasses)
            valores.append(linha.bruto_do_grupo(grupo) if tem else None)
        valores += [
            f"=SUM({letra['primeiro_grupo']}{numero}:{letra['ultimo_grupo']}{numero})",
            f"={letra['saldo']}{numero}-{letra['total']}{numero}",
            round(linha.nota, 2) if linha.nota is not None else TRAVESSAO,
            linha.situacao,
            linha.total_liquido,
        ]
        for coluna, valor in enumerate(valores, start=1):
            celula = aba.cell(row=numero, column=coluna, value=valor)
            celula.font = _fonte()
            celula.border = borda
            if coluna in colunas_dinheiro:
                celula.number_format = FORMATO_VALOR
            elif coluna == 7 + n:
                celula.number_format = FORMATO_NOTA
    ultima = max(numero, 4)

    linha_total = ultima + 2
    aba.cell(row=linha_total, column=2, value="TOTAL")
    for coluna in sorted(colunas_dinheiro):
        l = get_column_letter(coluna)
        aba.cell(row=linha_total, column=coluna, value=f"=SUM({l}4:{l}{ultima})")
    for coluna in range(1, len(cabecalho) + 1):
        celula = aba.cell(row=linha_total, column=coluna)
        celula.font = _fonte(bold=True)
        celula.border = borda
        _preencher(celula, TOTAL_FUNDO)
        if coluna in colunas_dinheiro:
            celula.number_format = FORMATO_VALOR

    intervalo = f"{letra['situacao']}4:{letra['situacao']}{ultima}"
    for situacao, fundo, texto in [(SITUACAO_DIVERGENTE, VERMELHO_FUNDO, VERMELHO_TEXTO),
                                   (SITUACAO_SO_BALANCETE, AMARELO_FUNDO, AMARELO_TEXTO),
                                   (SITUACAO_SO_REPASSE, AMARELO_FUNDO, AMARELO_TEXTO)]:
        aba.conditional_formatting.add(intervalo, CellIsRule(
            operator="equal", formula=[f'"{situacao}"'], font=Font(color=texto),
            fill=PatternFill("solid", start_color=fundo, end_color=fundo)))
    aba.freeze_panes = "D4"
    aba.auto_filter.ref = f"A3:{letra['liquido']}{ultima}"
    larguras = [12, 40, 40, 15] + [15] * n + [16, 13, 13, 17, 16]
    for coluna, largura in enumerate(larguras, start=1):
        aba.column_dimensions[get_column_letter(coluna)].width = largura
    return linha_total, ultima, letra


def _aba_detalhe(aba, resultado: ResultadoHonorarios) -> int:
    """Um repasse por linha. Devolve a última linha de dados."""
    aba["A1"] = (f"Repasses por Terceiro — SCF Repasse Sintético — {_unidade_titulo(resultado)} "
                 f"({mes_curto(resultado.mes)})")
    aba["A1"].font = _fonte(size=14, bold=True, color=AZUL)
    for coluna, texto in enumerate(COLUNAS_DETALHE, start=1):
        _cabecalho(aba.cell(row=3, column=coluna, value=texto))
    aba.row_dimensions[3].height = 30

    borda = _borda()
    numero = 3
    for repasse in resultado.repasses:
        numero += 1
        valores = [
            repasse.grupo,
            repasse.terceiro,
            int(repasse.numero) if repasse.numero.isdigit() else (repasse.numero or TRAVESSAO),
            repasse.data_referencia or TRAVESSAO,
            repasse.status,
            repasse.bruto,
            repasse.liquido,
            f"=F{numero}-G{numero}",
            resultado.conta_do_repasse.get(id(repasse), TRAVESSAO),
        ]
        for coluna, valor in enumerate(valores, start=1):
            celula = aba.cell(row=numero, column=coluna, value=valor)
            celula.font = _fonte()
            celula.border = borda
            if coluna == 3 and isinstance(valor, int):
                celula.number_format = "0"
            elif coluna == 4 and valor is not TRAVESSAO:
                celula.number_format = FORMATO_DATA
            elif coluna in (6, 7, 8):
                celula.number_format = FORMATO_VALOR
    ultima = max(numero, 4)

    linha_total = ultima + 2
    aba.cell(row=linha_total, column=2, value="TOTAL")
    for coluna, l in ((6, "F"), (7, "G"), (8, "H")):
        aba.cell(row=linha_total, column=coluna, value=f"=SUM({l}4:{l}{ultima})")
    for coluna in range(1, len(COLUNAS_DETALHE) + 1):
        celula = aba.cell(row=linha_total, column=coluna)
        celula.font = _fonte(bold=True)
        celula.border = borda
        _preencher(celula, TOTAL_FUNDO)
        if coluna in (6, 7, 8):
            celula.number_format = FORMATO_VALOR
    aba.freeze_panes = "A4"
    aba.auto_filter.ref = f"A3:I{ultima}"
    for coluna, largura in LARGURAS_DETALHE.items():
        aba.column_dimensions[coluna].width = largura
    return ultima


def _aba_resumo(aba, resultado: ResultadoHonorarios, total_completa: int, ultima_completa: int,
                letra: dict[str, str], ultima_detalhe: int) -> None:
    completa, detalhe = f"'{ABA_COMPLETA}'", f"'{ABA_DETALHE}'"
    conta = resultado.conta_total
    aba["B2"] = "Conciliação — Balancete de Honorários Médicos x Repasse Médico (SCF)"
    aba["B2"].font = _fonte(size=14, bold=True, color=AZUL)
    aba["B3"] = f"{resultado.unidade} — Mês Referência: {mes_curto(resultado.mes)}"
    aba["B4"] = (f"{resultado.arquivo_balancete} (Balancete — conta {conta.codigo}, saldo atual)  x  "
                 f"{resultado.arquivo_repasse} (SCF - Repasse Sintético, valor bruto do repasse)")
    for celula in ("B3", "B4"):
        aba[celula].font = _fonte(color=CINZA)

    situacao = f"{completa}!{letra['situacao']}4:{letra['situacao']}{ultima_completa}"
    totais = [
        (f"Total contábil (Balancete — conta {conta.codigo}, {conta.descricao})", resultado.total_balancete, True),
        ("Total do Repasse Médico (Vl repasse bruto)", f"={completa}!{letra['total']}{total_completa}", True),
        ("Diferença total",
         f"={completa}!{letra['saldo']}{total_completa}-{completa}!{letra['total']}{total_completa}", True),
        ("Médicos/clínicas conciliados sem divergência", f'=COUNTIF({situacao},"OK")', False),
        ("Itens com divergência ou sem correspondência", f'=COUNTIFS({situacao},"<>OK")', False),
    ]
    for deslocamento, (rotulo, valor, eh_dinheiro) in enumerate(totais):
        linha = 6 + deslocamento
        aba.cell(row=linha, column=2, value=rotulo).font = _fonte(bold=True)
        celula = aba.cell(row=linha, column=5, value=valor)
        celula.font = _fonte(bold=True)
        celula.number_format = FORMATO_VALOR if eh_dinheiro else "0"

    # Composição do repasse por grupo (SUMIF na aba de detalhe)
    aba["B12"] = "Composição do Repasse"
    aba["B12"].font = _fonte(size=12, bold=True, color=AZUL)
    for coluna, texto in ((2, "Grupo"), (4, "Vl repasse (bruto)"), (5, "Vl. Líquido"), (6, "Retenções")):
        _cabecalho(aba.cell(row=13, column=coluna, value=texto))
    _cabecalho(aba.cell(row=13, column=3))
    aba.merge_cells("B13:C13")
    faixa_grupo = f"{detalhe}!A4:A{ultima_detalhe}"
    numero = 13
    for grupo in resultado.grupos:
        numero += 1
        aba.merge_cells(start_row=numero, start_column=2, end_row=numero, end_column=3)
        aba.cell(row=numero, column=2, value=grupo).font = _fonte()
        for coluna, l in ((4, "F"), (5, "G")):
            celula = aba.cell(row=numero, column=coluna,
                              value=f'=SUMIF({faixa_grupo},"{grupo}",{detalhe}!{l}4:{l}{ultima_detalhe})')
            celula.font = _fonte()
            celula.number_format = FORMATO_VALOR
        celula = aba.cell(row=numero, column=6, value=f"=D{numero}-E{numero}")
        celula.font = _fonte()
        celula.number_format = FORMATO_VALOR
    numero += 1
    aba.merge_cells(start_row=numero, start_column=2, end_row=numero, end_column=3)
    aba.cell(row=numero, column=2, value="Total")
    for coluna, l in ((4, "D"), (5, "E"), (6, "F")):
        aba.cell(row=numero, column=coluna, value=f"=SUM({l}14:{l}{numero - 1})")
    for coluna in range(2, 7):
        celula = aba.cell(row=numero, column=coluna)
        celula.font = _fonte(bold=True)
        _preencher(celula, TOTAL_FUNDO)
        if coluna >= 4:
            celula.number_format = FORMATO_VALOR

    # Divergências
    numero += 3
    aba.cell(row=numero, column=2, value="Divergências e Itens Sem Correspondência").font = \
        _fonte(size=12, bold=True, color=AZUL)
    problemas = [l for l in resultado.linhas if l.situacao != SITUACAO_OK]
    numero += 1
    if not problemas:
        aba.cell(row=numero, column=2,
                 value="Nenhuma divergência: todos os médicos/clínicas do Balancete batem com o Repasse, e "
                       "não há repasse sem conta contábil.").font = _fonte(color=CINZA)
    else:
        for coluna, texto in enumerate(COLUNAS_RESUMO, start=2):
            _cabecalho(aba.cell(row=numero, column=coluna, value=texto))
        for linha in problemas:
            numero += 1
            valores = [
                linha.conta.codigo if linha.conta else TRAVESSAO,
                linha.conta.descricao if linha.conta else linha.nome_repasse,
                linha.saldo_balancete if linha.conta else TRAVESSAO,
                linha.total_repasse if linha.terceiros else TRAVESSAO,
                linha.diferenca,
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
        aba.cell(row=numero, column=2, value=f"Nota {posicao_nota}: {texto}").font = \
            _fonte(italic=True, color=CINZA)
        numero += 1
    for coluna, largura in LARGURAS_RESUMO.items():
        aba.column_dimensions[coluna].width = largura


__all__ = ["gerar_relatorio_honorarios", "mes_curto", "ABA_RESUMO", "ABA_COMPLETA", "ABA_DETALHE"]
