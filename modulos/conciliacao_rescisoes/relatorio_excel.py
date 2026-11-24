"""
Planilha da Conciliação de Rescisões a pagar (ESPECIFICACAO seção 17.3).

Abas: "Resumo" (com uma linha por PDF de eventos usado e os PDFs deixados de fora),
"Pagamentos" (todos os pagamentos do razão e onde cada um foi achado — o PDF diz qual: "PDF mensal",
"PDF complementar 29/06"),
"Valores diferentes" (achados, mas com valor pago diferente — para análise), "Não encontrados"
(pagamentos sem rescisão no PDF nem na lista anterior) e "Rescisões a pagar" (a lista nova, no
mesmo formato da planilha de controle: serve de entrada no mês seguinte) e, se o relatório de títulos a
pagar do financeiro foi escolhido, "Financeiro × lista" (cada pessoa da lista nova × os títulos dela no
financeiro; o que conferir vem primeiro).

Diferenças, totais e contagens são FÓRMULAS do Excel. Quem decide nome e pasta é processar_rescisoes().
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from modulos.conciliacao_rescisoes.fornecedores.leitores import nome_curto_unidade, reais
from modulos.conciliacao_rescisoes.fornecedores.relatorio_excel import (
    AMARELO_FUNDO,
    AMARELO_TEXTO,
    AZUL,
    BORDA,
    CINZA,
    FONTE,
    FORMATO_NOTA,
    FORMATO_VALOR,
    TOTAL_FUNDO,
    TRAVESSAO,
    VERMELHO_FUNDO,
    VERMELHO_TEXTO,
    mes_curto,
)
from modulos.conciliacao_rescisoes.financeiro import (
    SITUACAO_DIVERGENTE,
    SITUACAO_OK,
    SITUACAO_SO_FINANCEIRO,
    SITUACAO_SO_LISTA,
)
from modulos.conciliacao_rescisoes.modelos import (
    ORIGEM_NAO_ENCONTRADO,
    ORIGEM_PDF,
    ORIGEM_PENDENTE,
    ROTULO_COMPOSICAO,
    ROTULO_SALDO_RAZAO,
    ROTULO_TOTAL_COMPOSICAO,
    TEXTO_AVISO_COMPOSICAO,
    TEXTO_SEM_COMPOSICAO,
    ResultadoRescisoes,
)

ABA_RESUMO = "Resumo"
ABA_PAGAMENTOS = "Pagamentos"
ABA_DIFERENTES = "Valores diferentes"
ABA_NAO_ENCONTRADOS = "Não encontrados"
ABA_LISTA = "Rescisões a pagar"           # mesmo nome da aba da planilha de controle
ABA_FINANCEIRO = "Financeiro × lista"

FORMATO_DATA = "dd/mm/yyyy"
FORMATO_PERIODO = "mm/yyyy"

COLUNAS_PAGAMENTOS = ["Data", "Borderô", "Nome no razão", "Valor pago", "Onde foi achado", "Nome encontrado",
                      "Valor da rescisão", "Diferença (rescisão − pago)", "Confiança do nome"]
LARGURAS_PAGAMENTOS = {"A": 12, "B": 11, "C": 42, "D": 14, "E": 22, "F": 42, "G": 16, "H": 16, "I": 12}
COLUNAS_DIFERENTES = ["Data", "Borderô", "Nome no razão", "Onde foi achado", "Nome encontrado",
                      "Valor da rescisão", "Valor pago", "Diferença (rescisão − pago)", "O que foi feito"]
LARGURAS_DIFERENTES = {"A": 12, "B": 11, "C": 42, "D": 22, "E": 42, "F": 16, "G": 14, "H": 16, "I": 52}
TEXTO_PAGO_A_MENOR = "Pago a menor: o restante continua na lista nova"
TEXTO_PAGO_A_MAIOR = "Pago a maior: saiu da lista; diferença na composição (rodapé)"
COLUNAS_NAO_ENCONTRADOS = ["Data", "Borderô", "Nome no razão", "Histórico do razão", "Valor pago", "Observação"]
LARGURAS_NAO_ENCONTRADOS = {"A": 12, "B": 11, "C": 42, "D": 60, "E": 14, "F": 80}
COLUNAS_LISTA = ["Periodo", "Colaborador", "Valor", "Origem"]
LARGURAS_LISTA = {"A": 12, "B": 48, "C": 14, "D": 46}
COLUNAS_FINANCEIRO = ["Situação", "Colaborador (lista nova)", "Valor na lista", "Nome no financeiro",
                      "Títulos no financeiro (Nr. Título – emissão – saldo)", "Valor no financeiro",
                      "Diferença (lista − financeiro)", "Confiança do nome"]
LARGURAS_FINANCEIRO = {"A": 18, "B": 42, "C": 14, "D": 42, "E": 52, "F": 14, "G": 16, "H": 12}


def _fonte(**extras) -> Font:
    return Font(name=FONTE, size=extras.pop("size", 10), **extras)


def _preencher(celula, cor: str) -> None:
    celula.fill = PatternFill("solid", start_color=cor, end_color=cor)


def _cabecalho(aba, linha: int, colunas: list[str], coluna_inicial: int = 1) -> None:
    for coluna, texto in enumerate(colunas, start=coluna_inicial):
        celula = aba.cell(row=linha, column=coluna, value=texto)
        celula.font = _fonte(bold=True, color="FFFFFF")
        _preencher(celula, AZUL)
        celula.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    aba.row_dimensions[linha].height = 30


_LADO = Side(style="thin", color=BORDA)
_BORDA = Border(left=_LADO, right=_LADO, top=_LADO, bottom=_LADO)


def _escrever_linha(aba, linha: int, valores: list, dinheiro: tuple[int, ...] = (),
                    datas: tuple[int, ...] = (), notas: tuple[int, ...] = ()) -> None:
    for coluna, valor in enumerate(valores, start=1):
        celula = aba.cell(row=linha, column=coluna, value=valor)
        celula.font = _fonte()
        celula.border = _BORDA
        if coluna in dinheiro:
            celula.number_format = FORMATO_VALOR
        elif coluna in datas and isinstance(valor, date):
            celula.number_format = FORMATO_DATA
        elif coluna in notas:
            celula.number_format = FORMATO_NOTA


def _linha_total(aba, linha: int, colunas: int, rotulo_coluna: int, somas: dict[int, str]) -> None:
    aba.cell(row=linha, column=rotulo_coluna, value="TOTAL")
    for coluna, formula in somas.items():
        aba.cell(row=linha, column=coluna, value=formula)
    for coluna in range(1, colunas + 1):
        celula = aba.cell(row=linha, column=coluna)
        celula.font = _fonte(bold=True)
        celula.border = _BORDA
        _preencher(celula, TOTAL_FUNDO)
        if coluna in somas:
            celula.number_format = FORMATO_VALOR


def _titulo(aba, texto: str, subtitulo: str = "") -> None:
    aba["A1"] = texto
    aba["A1"].font = _fonte(size=14, bold=True, color=AZUL)
    if subtitulo:
        aba["A2"] = subtitulo
        aba["A2"].font = _fonte(italic=True, color=CINZA)


def _larguras(aba, larguras: dict[str, int]) -> None:
    for coluna, largura in larguras.items():
        aba.column_dimensions[coluna].width = largura


def gerar_relatorio_rescisoes(resultado: ResultadoRescisoes, caminho: Path) -> Path:
    livro = Workbook()
    resumo = livro.active
    resumo.title = ABA_RESUMO
    ultima_pagamentos = _aba_pagamentos(livro.create_sheet(ABA_PAGAMENTOS), resultado)
    total_diferentes = _aba_diferentes(livro.create_sheet(ABA_DIFERENTES), resultado)
    total_nao_encontrados = _aba_nao_encontrados(livro.create_sheet(ABA_NAO_ENCONTRADOS), resultado)
    total_lista = _aba_lista(livro.create_sheet(ABA_LISTA), resultado)
    financeiro = (_aba_financeiro(livro.create_sheet(ABA_FINANCEIRO), resultado)
                  if resultado.financeiro is not None else None)
    _aba_resumo(resumo, resultado, ultima_pagamentos, total_diferentes, total_nao_encontrados, total_lista,
                financeiro)
    caminho = Path(caminho)
    livro.save(caminho)
    return caminho


def _descrever_pdf(leitura) -> str:
    """"EVENTOS ... .PDF — Complementar Rescisão — pagamento 29/06/2026"."""
    partes = [leitura.arquivo, leitura.tipo or "tipo não informado"]
    if leitura.data_pagamento:
        partes.append(f"pagamento {leitura.data_pagamento:%d/%m/%Y}")
    return " — ".join(partes)


def _contexto(resultado: ResultadoRescisoes) -> str:
    return f"{nome_curto_unidade(resultado.unidade)} ({mes_curto(resultado.competencia)})"


def _aba_pagamentos(aba, resultado: ResultadoRescisoes) -> int:
    """Devolve a última linha de dados."""
    _titulo(aba, f"Pagamentos de rescisão do mês — {_contexto(resultado)}",
            "Cada pagamento do razão e onde a rescisão foi achada: primeiro no PDF (0264), depois na lista "
            "do mês anterior.")
    _cabecalho(aba, 3, COLUNAS_PAGAMENTOS)
    numero = 3
    for baixa in resultado.baixas:
        numero += 1
        pagamento, referencia = baixa.pagamento, baixa.valor_referencia
        _escrever_linha(aba, numero, [
            pagamento.data or TRAVESSAO,
            pagamento.bordero or TRAVESSAO,
            pagamento.nome,
            pagamento.valor,
            baixa.onde_achado,
            baixa.nome_encontrado or TRAVESSAO,
            referencia if referencia is not None else TRAVESSAO,
            f"=G{numero}-D{numero}" if referencia is not None else TRAVESSAO,
            baixa.nota if baixa.nota is not None else TRAVESSAO,
        ], dinheiro=(4, 7, 8), datas=(1,), notas=(9,))
    ultima = max(numero, 4)
    _linha_total(aba, ultima + 2, len(COLUNAS_PAGAMENTOS), 3, {4: f"=SUM(D4:D{ultima})"})
    aba.conditional_formatting.add(f"E4:E{ultima}", CellIsRule(
        operator="equal", formula=[f'"{ORIGEM_NAO_ENCONTRADO}"'], font=Font(color=VERMELHO_TEXTO),
        fill=PatternFill("solid", start_color=VERMELHO_FUNDO, end_color=VERMELHO_FUNDO)))
    aba.conditional_formatting.add(f"H4:H{ultima}", CellIsRule(
        operator="notEqual", formula=["0"], font=Font(color=AMARELO_TEXTO),
        fill=PatternFill("solid", start_color=AMARELO_FUNDO, end_color=AMARELO_FUNDO)))
    aba.freeze_panes = "A4"
    aba.auto_filter.ref = f"A3:I{ultima}"
    _larguras(aba, LARGURAS_PAGAMENTOS)
    return ultima


def _aba_diferentes(aba, resultado: ResultadoRescisoes) -> str:
    """Devolve a fórmula da soma das diferenças dos pagos a maior (as que vão para a composição da diferença)."""
    _titulo(aba, f"Valores diferentes — {_contexto(resultado)}",
            "A pessoa foi achada, mas o valor pago é diferente do valor da rescisão. Pago a menor: o que faltou "
            "pagar continua na lista nova. Pago a maior: a rescisão saiu da lista e a diferença está na composição.")
    _cabecalho(aba, 3, COLUNAS_DIFERENTES)
    numero = 3
    for baixa in resultado.valores_diferentes:
        numero += 1
        pagamento = baixa.pagamento
        _escrever_linha(aba, numero, [
            pagamento.data or TRAVESSAO, pagamento.bordero or TRAVESSAO, pagamento.nome, baixa.onde_achado,
            baixa.nome_encontrado, baixa.valor_referencia, pagamento.valor, f"=F{numero}-G{numero}",
            TEXTO_PAGO_A_MENOR if baixa.diferenca > 0 else TEXTO_PAGO_A_MAIOR,
        ], dinheiro=(6, 7, 8), datas=(1,))
    if numero == 3:
        aba["A4"] = "Nenhum pagamento com valor diferente da rescisão."
        aba["A4"].font = _fonte(italic=True, color=CINZA)
        linha_total = 6
        _linha_total(aba, linha_total, len(COLUNAS_DIFERENTES), 3, {8: "=0"})
    else:
        linha_total = numero + 2
        _linha_total(aba, linha_total, len(COLUNAS_DIFERENTES), 3,
                     {6: f"=SUM(F4:F{numero})", 7: f"=SUM(G4:G{numero})", 8: f"=SUM(H4:H{numero})"})
        aba.auto_filter.ref = f"A3:I{numero}"
    aba.freeze_panes = "A4"
    _larguras(aba, LARGURAS_DIFERENTES)
    if numero == 3:
        return f"'{ABA_DIFERENTES}'!H{linha_total}"
    return f"SUMIF('{ABA_DIFERENTES}'!H4:H{numero},\"<0\")"


def _aba_nao_encontrados(aba, resultado: ResultadoRescisoes) -> str:
    _titulo(aba, f"Pagamentos não encontrados — {_contexto(resultado)}",
            "Pagamentos do razão sem rescisão no PDF (0264) nem na lista do mês anterior.")
    _cabecalho(aba, 3, COLUNAS_NAO_ENCONTRADOS)
    numero = 3
    for baixa in resultado.baixas_de(ORIGEM_NAO_ENCONTRADO):
        numero += 1
        pagamento = baixa.pagamento
        _escrever_linha(aba, numero, [pagamento.data or TRAVESSAO, pagamento.bordero or TRAVESSAO, pagamento.nome,
                                      pagamento.historico, pagamento.valor, baixa.observacao or TRAVESSAO],
                        dinheiro=(5,), datas=(1,))
        aba.cell(row=numero, column=6).alignment = Alignment(wrap_text=True, vertical="top")
    if numero == 3:
        aba["A4"] = "Todos os pagamentos foram achados."
        aba["A4"].font = _fonte(italic=True, color=CINZA)
        linha_total = 6
        _linha_total(aba, linha_total, len(COLUNAS_NAO_ENCONTRADOS), 3, {5: "=0"})
    else:
        linha_total = numero + 2
        _linha_total(aba, linha_total, len(COLUNAS_NAO_ENCONTRADOS), 3, {5: f"=SUM(E4:E{numero})"})
    aba.freeze_panes = "A4"
    _larguras(aba, LARGURAS_NAO_ENCONTRADOS)
    return f"'{ABA_NAO_ENCONTRADOS}'!E{linha_total}"


def _aba_lista(aba, resultado: ResultadoRescisoes) -> str:
    """Lista nova, no formato da planilha de controle (cabeçalho na linha 2, total logo depois)."""
    fim = f"{resultado.data_final:%d/%m/%Y}" if resultado.data_final else mes_curto(resultado.competencia)
    aba["A1"] = f"Rescisões a pagar — {nome_curto_unidade(resultado.unidade)} — posição {fim}"
    aba["A1"].font = _fonte(size=12, bold=True, color=AZUL)
    _cabecalho(aba, 2, COLUNAS_LISTA)
    numero = 2
    for item in resultado.lista_nova:
        numero += 1
        _escrever_linha(aba, numero, [item.periodo, item.nome, item.valor, item.texto_origem], dinheiro=(3,))
        if isinstance(item.periodo, date):
            aba.cell(row=numero, column=1).number_format = FORMATO_PERIODO
    ultima = max(numero, 3)
    linha_total = numero + 1             # logo depois (sem colaborador): marca o fim da lista
    celula = aba.cell(row=linha_total, column=3, value=f"=SUM(C3:C{ultima})")
    celula.font = _fonte(bold=True)
    celula.number_format = FORMATO_VALOR
    _preencher(celula, TOTAL_FUNDO)
    _composicao_da_lista(aba, resultado, linha_total)
    aba.freeze_panes = "A3"
    aba.auto_filter.ref = f"A2:D{ultima}"
    _larguras(aba, LARGURAS_LISTA)
    return f"'{ABA_LISTA}'!C{linha_total}"


def _composicao_da_lista(aba, resultado: ResultadoRescisoes, linha_total: int) -> None:
    """Rodapé abaixo do total: o que explica "saldo do razão − lista" (lido de volta no mês seguinte)."""
    linha = linha_total + 2
    aba.cell(row=linha, column=2, value=ROTULO_COMPOSICAO).font = _fonte(bold=True, color=AZUL)
    primeira = linha + 1
    for texto, valor in resultado.composicao_nova:
        linha += 1
        aba.cell(row=linha, column=2, value=texto).font = _fonte()
        celula = aba.cell(row=linha, column=3, value=valor)
        celula.font = _fonte()
        celula.number_format = FORMATO_VALOR
    if not resultado.composicao_nova:
        linha += 1
        aba.cell(row=linha, column=2, value=TEXTO_SEM_COMPOSICAO).font = _fonte(italic=True, color=CINZA)
    linha += 1
    aba.cell(row=linha, column=2, value=ROTULO_TOTAL_COMPOSICAO).font = _fonte(bold=True)
    total = aba.cell(row=linha, column=3, value=f"=SUM(C{primeira}:C{linha - 1})")
    total.font = _fonte(bold=True)
    total.number_format = FORMATO_VALOR
    fim = f"{resultado.data_final:%d/%m/%Y}" if resultado.data_final else mes_curto(resultado.competencia)
    aba.cell(row=linha + 1, column=2, value=f"{ROTULO_SALDO_RAZAO} {fim} (lista + composição)").font =         _fonte(bold=True)
    saldo = aba.cell(row=linha + 1, column=3, value=f"=C{linha_total}+C{linha}")
    saldo.font = _fonte(bold=True)
    saldo.number_format = FORMATO_VALOR
    aba.cell(row=linha + 3, column=2, value=TEXTO_AVISO_COMPOSICAO).font = _fonte(italic=True, color=CINZA)


def _descrever_titulos(linha) -> str:
    """"1318304 – 26/05/2026 – 53,67; 1203972 – 14/01/2025 – 83,44"."""
    partes = []
    for titulo in linha.titulos:
        emissao = f" – {titulo.emissao:%d/%m/%Y}" if titulo.emissao else ""
        partes.append(f"{titulo.numero or '?'}{emissao} – {reais(titulo.saldo)}")
    return "; ".join(partes)


def _aba_financeiro(aba, resultado: ResultadoRescisoes) -> tuple[str, str, str]:
    """Lista nova × títulos a pagar do financeiro. Devolve (faixa da situação, total da lista, total do financeiro)."""
    financeiro = resultado.financeiro
    _titulo(aba, f"Lista nova × títulos a pagar do financeiro — {_contexto(resultado)}",
            f"Cada pessoa da lista nova (aba '{ABA_LISTA}') e os títulos dela no financeiro ({financeiro.arquivo}), "
            "somados por pessoa. Nomes escritos de jeitos diferentes foram juntados por semelhança: confira os de "
            "confiança menor que 1.")
    _cabecalho(aba, 3, COLUNAS_FINANCEIRO)
    numero = 3
    for linha in financeiro.linhas:
        numero += 1
        _escrever_linha(aba, numero, [
            linha.situacao,
            linha.pessoa.nome if linha.pessoa else TRAVESSAO,
            linha.valor_lista,
            linha.nome_financeiro or TRAVESSAO,
            _descrever_titulos(linha) or TRAVESSAO,
            linha.valor_financeiro,
            f"=C{numero}-F{numero}",
            linha.nota if linha.nota is not None else TRAVESSAO,
        ], dinheiro=(3, 6, 7), notas=(8,))
        aba.cell(row=numero, column=5).alignment = Alignment(wrap_text=True, vertical="top")
    ultima = max(numero, 4)
    if numero == 3:
        aba["A4"] = "A lista nova e o relatório do financeiro estão vazios."
        aba["A4"].font = _fonte(italic=True, color=CINZA)
    linha_total = ultima + 2
    _linha_total(aba, linha_total, len(COLUNAS_FINANCEIRO), 2,
                 {3: f"=SUM(C4:C{ultima})", 6: f"=SUM(F4:F{ultima})", 7: f"=SUM(G4:G{ultima})"})
    intervalo = f"A4:A{ultima}"
    for situacao, fundo, texto in [(SITUACAO_DIVERGENTE, VERMELHO_FUNDO, VERMELHO_TEXTO),
                                   (SITUACAO_SO_LISTA, AMARELO_FUNDO, AMARELO_TEXTO),
                                   (SITUACAO_SO_FINANCEIRO, AMARELO_FUNDO, AMARELO_TEXTO)]:
        aba.conditional_formatting.add(intervalo, CellIsRule(
            operator="equal", formula=[f'"{situacao}"'], font=Font(color=texto),
            fill=PatternFill("solid", start_color=fundo, end_color=fundo)))
    aba.conditional_formatting.add(f"H4:H{ultima}", CellIsRule(
        operator="lessThan", formula=["1"], font=Font(color=AMARELO_TEXTO),
        fill=PatternFill("solid", start_color=AMARELO_FUNDO, end_color=AMARELO_FUNDO)))
    aba.freeze_panes = "A4"
    aba.auto_filter.ref = f"A3:H{ultima}"
    _larguras(aba, LARGURAS_FINANCEIRO)
    return (f"'{ABA_FINANCEIRO}'!A4:A{ultima}", f"'{ABA_FINANCEIRO}'!C{linha_total}",
            f"'{ABA_FINANCEIRO}'!F{linha_total}")


def _aba_resumo(aba, resultado: ResultadoRescisoes, ultima_pagamentos: int, total_diferentes: str,
                total_nao_encontrados: str, total_lista: str,
                financeiro: tuple[str, str, str] | None = None) -> None:
    pagamentos = f"'{ABA_PAGAMENTOS}'"
    aba["B2"] = "Conciliação — Rescisões a pagar"
    aba["B2"].font = _fonte(size=14, bold=True, color=AZUL)
    aba["B3"] = f"{resultado.unidade} — {mes_curto(resultado.competencia)}"
    aba["B4"] = (f"{resultado.arquivo_razao} (razão)  ·  {resultado.arquivo_eventos} (eventos 0264)  ·  "
                 f"{resultado.arquivo_controle} (lista do mês anterior)")
    if resultado.arquivo_financeiro:
        aba["B4"] = aba["B4"].value + f"  ·  {resultado.arquivo_financeiro} (títulos a pagar do financeiro)"
    for celula in ("B3", "B4"):
        aba[celula].font = _fonte(color=CINZA)

    linha = 6

    def bloco(titulo: str) -> None:
        nonlocal linha
        aba.cell(row=linha, column=2, value=titulo).font = _fonte(size=12, bold=True, color=AZUL)
        linha += 1

    def item(rotulo: str, valor, negrito: bool = False, formato: str = FORMATO_VALOR, destaque: bool = False) -> int:
        nonlocal linha
        aba.cell(row=linha, column=2, value=rotulo).font = _fonte(bold=negrito)
        celula = aba.cell(row=linha, column=5, value=valor)
        celula.font = _fonte(bold=negrito or destaque, color=VERMELHO_TEXTO if destaque else None)
        celula.number_format = formato
        linha += 1
        return linha - 1

    bloco("Movimento do razão")
    l_anterior = item("Saldo anterior", resultado.saldo_anterior)
    l_creditos = item("(+) Rescisões lançadas no mês (créditos)", resultado.total_creditos)
    l_pagos = item("(−) Pagamentos de rescisão (débitos)", f"=SUM({pagamentos}!D4:D{ultima_pagamentos})")
    l_final = item("Saldo final", f"=E{l_anterior}+E{l_creditos}-E{l_pagos}", negrito=True)
    linha += 1

    bloco("Conferências")
    l_controle = item("Total da lista do mês anterior", resultado.total_controle)
    if resultado.composicao_anterior:
        l_comp_anterior = item("(+) Composição da diferença da lista anterior (rodapé)",
                               sum((v for _, v in resultado.composicao_anterior), 0))
        item("Diferença: saldo anterior − (lista anterior + composição)",
             f"=E{l_anterior}-E{l_controle}-E{l_comp_anterior}")
    else:
        item("Diferença: saldo anterior − lista anterior", f"=E{l_anterior}-E{l_controle}")
    # uma linha por PDF de eventos usado (arquivo, tipo, data de pagamento, total), o total e a diferença
    primeira_pdf = linha
    for leitura in resultado.pdfs_usados:
        item(f"{leitura.formato} usado: {_descrever_pdf(leitura)}", leitura.total)
    if not resultado.pdfs_usados:                    # (não acontece: sem PDF não há relatório)
        item("PDF usado: nenhum", 0)
    l_pdf = item("Total dos PDFs usados (0264 – Líquido Rescisão)", f"=SUM(E{primeira_pdf}:E{linha - 1})",
                 negrito=True)
    l_dif_pdf = item("Diferença: créditos do razão − PDFs", f"=E{l_creditos}-E{l_pdf}")
    l_complementares = item("   soma dos pagamentos complementares (regra 1a)",
                            sum((b.pagamento.valor for b in resultado.complementares), 0))
    item("   diferença restante", f"=E{l_dif_pdf}-E{l_complementares}")
    for credito in resultado.creditos_sem_pdf:
        item(f"      crédito do razão sem PDF de valor igual: {credito.descricao}", credito.valor)
    for leitura in resultado.pdfs_sem_credito:
        item(f"      {leitura.formato} usado sem lançamento de crédito igual no razão: {leitura.arquivo}",
             -leitura.total)
    linha += 1

    if resultado.pdfs_fora:
        bloco("PDFs não lançados no razão deste mês (provavelmente do mês seguinte)")
        aba.cell(row=linha, column=2, value="Arquivo — tipo — data de pagamento").font = _fonte(italic=True,
                                                                                               color=CINZA)
        aba.cell(row=linha, column=4, value="Pessoas").font = _fonte(italic=True, color=CINZA)
        aba.cell(row=linha, column=5, value="Total (0264)").font = _fonte(italic=True, color=CINZA)
        linha += 1
        for leitura in resultado.pdfs_fora:
            aba.cell(row=linha, column=2, value=_descrever_pdf(leitura)).font = _fonte()
            aba.cell(row=linha, column=4, value=len(leitura.rescisoes)).font = _fonte()
            celula = aba.cell(row=linha, column=5, value=leitura.total)
            celula.font = _fonte()
            celula.number_format = FORMATO_VALOR
            linha += 1
        aba.cell(row=linha, column=2, value="Estes PDFs não entraram no casamento nem na lista nova.").font = \
            _fonte(italic=True, color=CINZA)
        linha += 2

    bloco("Pagamentos do mês")
    faixa_origem = f"{pagamentos}!E4:E{ultima_pagamentos}"
    faixa_valor = f"{pagamentos}!D4:D{ultima_pagamentos}"
    rotulos_pdf = list(dict.fromkeys(r.pdf for l in resultado.pdfs_usados for r in l.rescisoes if r.pdf))
    for origem in (rotulos_pdf or [ORIGEM_PDF]) + [ORIGEM_PENDENTE, ORIGEM_NAO_ENCONTRADO]:
        aba.cell(row=linha, column=2, value=origem).font = _fonte()
        quantidade = aba.cell(row=linha, column=4, value=f'=COUNTIF({faixa_origem},"{origem}")')
        quantidade.font = _fonte()
        valor = aba.cell(row=linha, column=5, value=f'=SUMIF({faixa_origem},"{origem}",{faixa_valor})')
        valor.font = _fonte()
        valor.number_format = FORMATO_VALOR
        linha += 1
    item("Pagamentos com valor diferente da rescisão (quantidade)", len(resultado.valores_diferentes), formato="0")
    linha += 1

    bloco("Saldo final × lista nova de Rescisões a pagar")
    l_saldo = item("Saldo final do razão", f"=E{l_final}")
    l_lista = item(f"Total da lista nova (aba '{ABA_LISTA}')", f"={total_lista}")
    l_dif = item("Diferença", f"=E{l_saldo}-E{l_lista}", negrito=True)
    l_a = item("   explicada pela diferença créditos − PDFs", f"=E{l_dif_pdf}")
    l_b = item(f"   explicada pelos pagamentos a maior (aba '{ABA_DIFERENTES}'; o pago a menor está na lista)",
               f"={total_diferentes}")
    l_c = item(f"   explicada pelos pagamentos não encontrados (aba '{ABA_NAO_ENCONTRADOS}')",
               f"=-{total_nao_encontrados}")
    explicado = f"E{l_dif}-E{l_a}-E{l_b}-E{l_c}"
    if resultado.composicao_anterior:
        l_d = item("   explicada pela composição da diferença da lista anterior", f"=E{l_comp_anterior}")
        explicado += f"-E{l_d}"
    item("Diferença sem explicação", f"=ROUND({explicado},2)", negrito=True)
    aba.cell(row=linha, column=2,
             value=f"Os itens desta diferença estão no rodapé da aba '{ABA_LISTA}' (composição da diferença).").font =         _fonte(italic=True, color=CINZA)
    linha += 1
    linha += 1

    if financeiro is not None:
        faixa, total_lista_fin, total_fin = financeiro
        dados = resultado.financeiro
        bloco("Lista nova × títulos a pagar do financeiro")
        l_lista_fin = item(f"Total da lista nova (aba '{ABA_LISTA}')", f"={total_lista_fin}")
        l_fin = item(f"Total dos títulos a pagar do financeiro ({dados.quantidade_titulos} títulos)", f"={total_fin}")
        item("Diferença: lista nova − financeiro", f"=E{l_lista_fin}-E{l_fin}", negrito=True)
        for situacao, rotulo in ((SITUACAO_OK, "   pessoas com o mesmo valor (OK)"),
                                 (SITUACAO_DIVERGENTE, "   pessoas com valor diferente (DIVERGENTE)"),
                                 (SITUACAO_SO_LISTA, "   pessoas só na lista nova (SÓ NA LISTA)"),
                                 (SITUACAO_SO_FINANCEIRO, "   pessoas só no financeiro (SÓ NO FINANCEIRO)")):
            item(rotulo, f'=COUNTIF({faixa},"{situacao}")', formato="0")
        item("   das OK, com o nome escrito diferente (confira)", len(dados.nomes_parecidos), formato="0")
        aba.cell(row=linha, column=2, value=f"Pessoa a pessoa na aba '{ABA_FINANCEIRO}'.").font = \
            _fonte(italic=True, color=CINZA)
        linha += 2

    for posicao, texto in enumerate(resultado.notas, start=1):
        aba.cell(row=linha, column=2, value=f"Nota {posicao}: {texto}").font = _fonte(italic=True, color=CINZA)
        linha += 1
    for coluna, largura in {"A": 2, "B": 62, "C": 2, "D": 12, "E": 18}.items():
        aba.column_dimensions[coluna].width = largura


__all__ = ["gerar_relatorio_rescisoes", "ABA_RESUMO", "ABA_PAGAMENTOS", "ABA_DIFERENTES",
           "ABA_NAO_ENCONTRADOS", "ABA_LISTA", "ABA_FINANCEIRO"]
