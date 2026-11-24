"""
Planilha da Conciliação Honorários Hospital Exemplo (ESPECIFICACAO seção 20.3), no modelo da planilha do usuário
(Conciliacao_Honorarios_Medicos_PF_PJ_08_2026_1.xlsx): abas "Resumo", "PF - Conciliação",
"PJ - Conciliação" e "Remoção-Deslocamento PFxPJ".

Totais, Senior ajustado e diferenças são FÓRMULAS do Excel; o Resumo soma as abas PF e PJ (na planilha
feita à mão os totais do Resumo tinham sido digitados e não batiam com as linhas). Cores do modelo:
amarelo = sem correspondência, vermelho = ainda diverge, azul = acertado pela Remoção/Deslocamento.
Quem decide nome e pasta é processar_honorarios_hospital_exemplo().
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from modulos.honorarios_medicos.fornecedores.leitores import nome_curto_unidade
from modulos.honorarios_medicos.hospital_exemplo.leitores import GRUPO_PAGAMENTO
from modulos.honorarios_medicos.hospital_exemplo.modelos import (
    LADO_PF,
    LADO_PJ,
    PAREAMENTO_VALOR,
    SITUACAO_SO_BALANCETE,
    SITUACAO_SO_SENIOR,
    LinhaHospitalExemplo,
    ResultadoHospitalExemplo,
)

ABA_RESUMO = "Resumo"
ABAS_LADO = {LADO_PF: "PF - Conciliação", LADO_PJ: "PJ - Conciliação"}
ABA_REMOCAO = "Remoção-Deslocamento PFxPJ"

FONTE = "Arial"
AZUL = "1F4E78"
CINZA = "595959"
BORDA = "BFBFBF"
AMARELO = "FFEB9C"
VERMELHO = "FFC7CE"
AZUL_CLARO = "DDEBF7"
VERDE_CLARO = "E2EFDA"
FORMATO_VALOR = "#,##0.00"
FORMATO_DATA = "dd/mm/yyyy"

COLUNAS_LADO = ["Nome (Contábil)", "Cód. Contábil", "Saldo Contábil (R$)", "Nome (Senior)", "Cód. Senior",
                "Saldo Senior Original (R$)", "Remoção/Deslocamento (R$)", "Saldo Senior Ajustado (R$)",
                "Diferença Ajustada (R$)", "Terceiro na Remoção", "Tipo Match", "Score", "Situação"]
LARGURAS_LADO = {"A": 3, "B": 36, "C": 12, "D": 15, "E": 36, "F": 12, "G": 15, "H": 16, "I": 16, "J": 15,
                 "K": 24, "L": 16, "M": 8, "N": 17}
COLUNAS_REMOCAO = ["Tipo", "Categoria", "Terceiro", "Nº Repasse", "Data Ref.", "Status", "Vl. Repasse (R$)",
                   "Vl. Líquido (R$)", "Conta Balancete", "Arquivo"]
LARGURAS_REMOCAO = {"A": 3, "B": 8, "C": 20, "D": 42, "E": 12, "F": 12, "G": 10, "H": 16, "I": 16, "J": 15,
                    "K": 40}
SEM_CONTA = "Sem conta"


def _fonte(**extras) -> Font:
    return Font(name=FONTE, size=extras.pop("size", 10), **extras)


def _borda() -> Border:
    lado = Side(style="thin", color=BORDA)
    return Border(left=lado, right=lado, top=lado, bottom=lado)


def _preencher(celula, cor: str) -> None:
    celula.fill = PatternFill("solid", start_color=cor, end_color=cor)


def _cabecalho(celula) -> None:
    celula.font = _fonte(bold=True, color="FFFFFF")
    _preencher(celula, AZUL)
    celula.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    celula.border = _borda()


def _titulo(aba, texto: str, subtitulo: str | None = None) -> None:
    aba["B2"] = texto
    aba["B2"].font = _fonte(size=14, bold=True, color=AZUL)
    if subtitulo:
        aba["B3"] = subtitulo
        aba["B3"].font = _fonte(size=11, color=CINZA)


def _competencia(resultado: ResultadoHospitalExemplo) -> str:
    return f"{resultado.mes.month:02d}/{resultado.mes.year}" if resultado.mes else "mês não encontrado"


def gerar_relatorio_hospital_exemplo(resultado: ResultadoHospitalExemplo, caminho: Path) -> Path:
    livro = Workbook()
    resumo = livro.active
    resumo.title = ABA_RESUMO
    totais = {}
    for lado in resultado.lados:
        totais[lado] = _aba_lado(livro.create_sheet(ABAS_LADO[lado]), lado, resultado)
    _aba_remocao(livro.create_sheet(ABA_REMOCAO), resultado)
    _aba_resumo(resumo, resultado, totais)
    caminho = Path(caminho)
    livro.save(caminho)
    return caminho


# ---------------------------------------------------------------------
# Abas PF e PJ
# ---------------------------------------------------------------------
def _tipo_match(linha: LinhaHospitalExemplo) -> str:
    if linha.situacao == SITUACAO_SO_SENIOR:
        return "só no Senior"
    if linha.situacao == SITUACAO_SO_BALANCETE:
        return "sem par"
    if linha.senior:
        return "valor (confirmar)" if linha.pareamento == PAREAMENTO_VALOR else "nome"
    return "só Remoção"


def _cor(linha: LinhaHospitalExemplo) -> str | None:
    if linha.sem_correspondencia:
        return AMARELO
    if linha.diferenca != 0:
        return VERMELHO
    if linha.acertada_pela_remocao:
        return AZUL_CLARO
    return None


def _aba_lado(aba, lado: str, resultado: ResultadoHospitalExemplo) -> int:
    """Devolve a linha do TOTAL (o Resumo aponta para ela)."""
    aba.sheet_view.showGridLines = False
    _titulo(aba, f"Honorários Médicos {lado} — Contábil x Senior (Ajustado c/ Remoção/Deslocamento) — "
                 f"{_competencia(resultado)}")
    for coluna, largura in LARGURAS_LADO.items():
        aba.column_dimensions[coluna].width = largura
    for posicao, nome in enumerate(COLUNAS_LADO, start=2):
        _cabecalho(aba.cell(row=4, column=posicao, value=nome))
    aba.row_dimensions[4].height = 34.5

    linhas = resultado.linhas.get(lado, [])
    for numero, linha in enumerate(linhas, start=5):
        valores = [
            linha.conta.descricao if linha.conta else None,
            linha.conta.codigo if linha.conta else None,
            linha.saldo_contabil,
            linha.nome_senior or None,
            linha.codigo_senior or None,
            linha.saldo_senior,
            linha.valor_remocao,
            f'=IF(G{numero}="",0,G{numero})+IF(H{numero}="",0,H{numero})',
            f"=D{numero}-I{numero}",
            linha.nome_remocao or None,
            _tipo_match(linha),
            None if linha.nota is None else round(linha.nota * 100, 1),
            linha.situacao,
        ]
        cor = _cor(linha)
        for posicao, valor in enumerate(valores, start=2):
            celula = aba.cell(row=numero, column=posicao, value=valor)
            celula.font = _fonte(size=9, color=CINZA) if posicao == 11 else _fonte()
            celula.border = _borda()
            if posicao in (4, 7, 8, 9, 10):
                celula.number_format = FORMATO_VALOR
            if cor:
                _preencher(celula, cor)

    primeira, ultima = 5, 4 + len(linhas)
    total = ultima + 1
    aba.cell(row=total, column=2, value="TOTAL")
    for coluna in "DGHIJ":
        aba[f"{coluna}{total}"] = f"=SUM({coluna}{primeira}:{coluna}{ultima})" if linhas else 0
    for posicao in range(2, 2 + len(COLUNAS_LADO)):
        celula = aba.cell(row=total, column=posicao)
        celula.font = _fonte(bold=True)
        celula.border = _borda()
        if posicao in (4, 7, 8, 9, 10):
            celula.number_format = FORMATO_VALOR

    legenda = total + 2
    aba.cell(row=legenda, column=2, value="Legenda:").font = _fonte(bold=True)
    for deslocamento, (texto, cor) in enumerate((
            ("Amarelo: sem correspondência (nem Senior, nem Remoção/Deslocamento)", AMARELO),
            ("Vermelho: ainda divergente após o ajuste", VERMELHO),
            ("Azul: ajustado pela Remoção/Deslocamento e já batendo", AZUL_CLARO)), start=1):
        celula = aba.cell(row=legenda + deslocamento, column=2, value=texto)
        celula.font = _fonte()
        _preencher(celula, cor)

    aba.freeze_panes = "B5"
    aba.auto_filter.ref = f"B4:N{max(ultima, 4)}"
    return total


# ---------------------------------------------------------------------
# Aba da Remoção/Deslocamento
# ---------------------------------------------------------------------
def _aba_remocao(aba, resultado: ResultadoHospitalExemplo) -> None:
    aba.sheet_view.showGridLines = False
    particular = any(r.grupo == GRUPO_PAGAMENTO for r in resultado.repasses)
    _titulo(aba, "Relatório 6095 — Remoção e Deslocamento"
                 + (" (+ Rel. 6203 – Pagamento particular)" if particular else "") + ", separado por PF x PJ",
            f"Base: SCF – Repasse Sintético — Competência {_competencia(resultado)}")
    for coluna, largura in LARGURAS_REMOCAO.items():
        aba.column_dimensions[coluna].width = largura
    for posicao, nome in enumerate(COLUNAS_REMOCAO, start=2):
        _cabecalho(aba.cell(row=5, column=posicao, value=nome))

    ordem = {LADO_PF: 0, LADO_PJ: 1}
    repasses = sorted(resultado.repasses,
                      key=lambda r: (ordem.get(resultado.lado_do_repasse.get(id(r), ""), 2), r.grupo,
                                     r.terceiro.casefold()))
    for numero, repasse in enumerate(repasses, start=6):
        lado = resultado.lado_do_repasse.get(id(repasse), "")
        valores = [lado or SEM_CONTA, repasse.grupo, repasse.terceiro, repasse.numero, repasse.data_referencia,
                   repasse.status, repasse.bruto, repasse.liquido,
                   resultado.conta_do_repasse.get(id(repasse), "—"), resultado.origem_do_repasse.get(id(repasse))]
        cor = {LADO_PF: AZUL_CLARO, LADO_PJ: VERDE_CLARO}.get(lado, AMARELO)
        for posicao, valor in enumerate(valores, start=2):
            celula = aba.cell(row=numero, column=posicao, value=valor)
            celula.font = _fonte(bold=posicao == 2)
            celula.border = _borda()
            _preencher(celula, cor)
            if posicao in (8, 9):
                celula.number_format = FORMATO_VALOR
            elif posicao == 6:
                celula.number_format = FORMATO_DATA

    primeira, ultima = 6, 5 + len(repasses)
    total = ultima + 1
    aba.cell(row=total, column=3, value="TOTAL")
    for coluna in "HI":
        aba[f"{coluna}{total}"] = f"=SUM({coluna}{primeira}:{coluna}{ultima})" if repasses else 0
    for posicao in range(2, 2 + len(COLUNAS_REMOCAO)):
        celula = aba.cell(row=total, column=posicao)
        celula.font = _fonte(bold=True)
        celula.border = _borda()
        if posicao in (8, 9):
            celula.number_format = FORMATO_VALOR

    linha = total + 2
    for rotulo, chave in (("Subtotal PF", LADO_PF), ("Subtotal PJ", LADO_PJ), ("Sem conta no balancete", SEM_CONTA)):
        if chave == SEM_CONTA and not resultado.repasses_sem_conta:
            continue
        aba.cell(row=linha, column=3, value=rotulo).font = _fonte(bold=True)
        celula = aba.cell(row=linha, column=8,
                          value=f'=SUMIF(B{primeira}:B{max(ultima, primeira)},"{chave}",'
                                f'H{primeira}:H{max(ultima, primeira)})')
        celula.font = _fonte(bold=True)
        celula.number_format = FORMATO_VALOR
        linha += 1
    aba.freeze_panes = "B6"


# ---------------------------------------------------------------------
# Resumo
# ---------------------------------------------------------------------
def _aba_resumo(aba, resultado: ResultadoHospitalExemplo, totais: dict[str, int]) -> None:
    aba.sheet_view.showGridLines = False
    unidade = nome_curto_unidade(resultado.unidade) or "Hospital Exemplo"
    _titulo(aba, "Conciliação Honorários Médicos — Posição Contábil x Posição Senior (+ Remoção/Deslocamento)",
            f"Competência {_competencia(resultado)} — {unidade}")
    for coluna, largura in {"A": 3, "B": 72, "C": 3, "D": 18}.items():
        aba.column_dimensions[coluna].width = largura

    linha = 5
    celulas_ajustadas = []
    for lado in resultado.lados:
        aba_lado, total = f"'{ABAS_LADO[lado]}'", totais[lado]
        aba.cell(row=linha, column=2, value=f"HONORÁRIOS {lado}").font = _fonte(size=11, bold=True, color=AZUL)
        conta = resultado.contas_total[lado]
        itens = [
            (f"Total Posição Contábil ({lado}) — conta {conta.codigo}", f"={aba_lado}!D{total}", False),
            (f"Total Posição Senior ({lado})", f"={aba_lado}!G{total}", False),
            (f"(+) Total Remoção/Deslocamento ({lado})", f"={aba_lado}!H{total}", False),
            (f"(=) Posição Senior Ajustada ({lado})", f"=D{linha + 2}+D{linha + 3}", True),
            (f"Diferença Contábil x Senior original ({lado})", f"=D{linha + 1}-D{linha + 2}", True),
            (f"Diferença Contábil x Senior AJUSTADA ({lado})", f"=D{linha + 1}-D{linha + 4}", True),
        ]
        for deslocamento, (rotulo, formula, negrito) in enumerate(itens, start=1):
            aba.cell(row=linha + deslocamento, column=2, value=rotulo).font = _fonte()
            celula = aba.cell(row=linha + deslocamento, column=4, value=formula)
            celula.font = _fonte(bold=negrito)
            celula.number_format = FORMATO_VALOR
        celulas_ajustadas.append(f"D{linha + 6}")
        linha += 8

    if len(celulas_ajustadas) > 1:
        aba.cell(row=linha, column=2, value="Diferença AJUSTADA Total (PF + PJ)").font = _fonte(bold=True)
        celula = aba.cell(row=linha, column=4, value="=" + "+".join(celulas_ajustadas))
        celula.font = _fonte(bold=True)
        celula.number_format = FORMATO_VALOR
        linha += 1
    if resultado.repasses_sem_conta:
        aba.cell(row=linha, column=2, value="Remoção/Deslocamento sem conta no balancete (fora das abas PF e PJ)"
                 ).font = _fonte()
        celula = aba.cell(row=linha, column=4,
                          value=sum(r.bruto for r in resultado.repasses_sem_conta))
        celula.font = _fonte()
        celula.number_format = FORMATO_VALOR
        linha += 1

    linha += 1
    aba.cell(row=linha, column=2, value="Arquivos:").font = _fonte(bold=True)
    for arquivo in resultado.arquivos:
        linha += 1
        aba.cell(row=linha, column=2, value=arquivo).font = _fonte(size=9, color=CINZA)

    linha += 2
    aba.cell(row=linha, column=2, value="Observações:").font = _fonte(bold=True)
    for nota in resultado.notas:
        linha += 1
        celula = aba.cell(row=linha, column=2, value=nota)
        celula.font = _fonte(size=9, color=CINZA)
        celula.alignment = Alignment(wrap_text=True, vertical="top")
        aba.row_dimensions[linha].height = 12 * max(1, len(nota) // 95 + 1)
