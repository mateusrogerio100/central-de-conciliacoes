"""Excel de saída do Crédito Estouro — ESPECIFICACAO_CREDITO_ESTOURO.md, seção 5.

CreditoEstouro_<mmmaaaa>.xlsx (pedido do usuário, 16/11/2026; se já existir, _2, _3…: nada é substituído), com as abas
Resumo, 0256 do mês anterior, 0241 – afastados, Parcelamentos, Lançamentos do razão a conferir, Controle (a entrada
do mês seguinte) e Avisos.

O Resumo usa fórmulas (GUIA_DE_MANUTENCAO, seção 51): as contagens por situação (=CONT.SE na coluna Situação de
cada aba, com lista suspensa) e a composição do saldo (=SOMASE na aba Controle). Quem trocar uma situação ou
apagar uma linha acertada do controle vê o Resumo se ajustar sozinho. Só openpyxl, nunca o Excel.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from modulos.credito_estouro import conciliador as c
from modulos.credito_estouro.controle import ABA_CONTROLE, COLUNAS as COLUNAS_CONTROLE, escrever_aba_controle
from modulos.credito_estouro.modelos import TIPOS_COM_VALOR, Aviso

PREFIXO_ARQUIVO = "CreditoEstouro"
ABA_RESUMO = "Resumo"
ABA_COBRANCAS = "0256 do mês anterior"
ABA_AFASTADOS = "0241 – afastados"
ABA_PARCELAMENTOS = "Parcelamentos"
ABA_DEVOLUCOES = "0775 – devoluções"
ABA_A_CONFERIR = "Lançamentos do razão a conferir"
ABA_AVISOS = "Avisos"
ABA_LISTAS = "Listas"        # escondida: as opções das listas suspensas da coluna Situação

SITUACOES_COBRANCA = [c.COBRADO, c.COBRADO_DIFERENTE, c.PARCELAMENTO_NOVO, c.BAIXADO, c.BAIXADO_DIFERENTE,
                      c.NAO_COBRADO, c.COBRADO_SEM_0256]
SITUACOES_AFASTADO = [c.PAGOU_CERTO, c.PAGOU_A_MAIS, c.PAGOU_A_MENOS, c.NAO_PAGOU, c.SEM_MOVIMENTO]
SITUACOES_PARCELAMENTO = [c.PARCELA_DESCONTADA, c.QUITADO_1204, c.QUITADO_RAZAO, c.PARCELAMENTO_NOVO,
                          c.PARCELA_DIFERENTE, c.PARCELA_MAIOR, c.PAGO_RAZAO_DIFERENTE, c.PARCELA_NAO_DESCONTADA,
                          c.PARCELA_SEM_CONTROLE]
# coluna de cada lista na aba Listas (a lista suspensa aponta para a faixa: o Excel não aceita mais de 255 letras
# numa lista escrita direto na regra, e as frases do 0256 e dos parcelamentos passam disso)
COLUNA_LISTA = {"cobrancas": 1, "afastados": 2, "parcelamentos": 3, "devolucoes": 4}
SITUACOES_DEVOLUCAO = [c.DEVOLUCAO_ZEROU, c.DEVOLUCAO_CONFERIR]
LINHAS_EXTRAS = 200          # linhas a mais nas faixas das fórmulas: o que for acrescentado à mão também conta

_MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
_FORMATO_VALOR = '#,##0.00;[Red]-#,##0.00'
_FORMATO_DATA = "dd/mm/yyyy"
_COR_CABECALHO = PatternFill("solid", start_color="1F4E78", end_color="1F4E78")
_COR_OK = PatternFill("solid", start_color="E2EFDA", end_color="E2EFDA")
_COR_CONFERIR = PatternFill("solid", start_color="FFF2CC", end_color="FFF2CC")
_COR_DESTAQUE = PatternFill("solid", start_color="FCE4D6", end_color="FCE4D6")
_SITUACOES_OK = {c.COBRADO, c.BAIXADO, c.PAGOU_CERTO, c.PARCELA_DESCONTADA, c.QUITADO_1204, c.QUITADO_RAZAO,
                 c.DEVOLUCAO_ZEROU}
_LARGURA_MAXIMA = 70


# ---------------------------------------------------------------------
# Nome do arquivo
# ---------------------------------------------------------------------
def mes_curto(mes: date | None) -> str:
    """date(2026, 6, 1) → "jun/2026"."""
    return "" if mes is None else f"{_MESES[mes.month - 1]}/{mes.year}"


def unidade_para_arquivo(unidade: str) -> str:
    """"FUNDAÇÃO HOSPITAL EXEMPLO DE MISER. DE CIDADE ALFA" → "HospitalExemplo"; "AME - Cidade Delta (...)" → "CidadeDelta"."""
    curto = re.sub(r"\s+", " ", unidade.split("(")[0]).strip()
    if not re.match(r"^\s*ame\b", curto, re.IGNORECASE) and "hospital exemplo" in curto.casefold():
        return "HospitalExemplo"
    curto = re.sub(r"^\s*ame\s*-?\s*", "", curto, flags=re.IGNORECASE) or curto
    sem_acento = unicodedata.normalize("NFKD", curto).encode("ascii", "ignore").decode()
    palavras = re.findall(r"[A-Za-z0-9]+", sem_acento)
    return "".join(p[:1].upper() + p[1:].lower() for p in palavras) or "Unidade"


def caminho_do_relatorio(pasta: Path, unidade: str, mes: date | None) -> Path:
    mes_texto = mes_curto(mes).replace("/", "") or "sem_mes"
    # só o mês no nome (pedido do usuário, 16/11/2026); a unidade fica dentro da planilha (Resumo e Controle)
    original = Path(pasta) / f"{PREFIXO_ARQUIVO}_{mes_texto}.xlsx"
    caminho, contador = original, 2
    while caminho.exists():
        caminho = original.with_name(f"{original.stem}_{contador}{original.suffix}")
        contador += 1
    return caminho


# ---------------------------------------------------------------------
# Apoio
# ---------------------------------------------------------------------
def _f(valor: Decimal | None) -> float | None:
    return float(valor) if valor is not None else None


def _cabecalho(aba, titulos: list[str]) -> None:
    aba.append(titulos)
    for celula in aba[aba.max_row]:
        celula.font = Font(bold=True, color="FFFFFF")
        celula.fill = _COR_CABECALHO
        celula.alignment = Alignment(vertical="center", wrap_text=True)
    aba.freeze_panes = f"A{aba.max_row + 1}"          # texto: não cria uma célula vazia na linha de baixo


def _formatar_valores(aba, colunas: tuple[int, ...], primeira_linha: int = 2) -> None:
    for coluna in colunas:
        for linha in range(primeira_linha, aba.max_row + 1):
            aba.cell(row=linha, column=coluna).number_format = _FORMATO_VALOR


def _ajustar_larguras(aba) -> None:
    for numero, coluna in enumerate(aba.iter_cols(), start=1):
        maior = max((len(_texto(c.value)) for c in coluna), default=0)
        aba.column_dimensions[get_column_letter(numero)].width = max(10, min(maior + 2, _LARGURA_MAXIMA))


def _texto(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float):
        return f"{valor:,.2f}"
    if isinstance(valor, str) and valor.startswith("="):
        return "0000000000"
    return str(valor)


def _situacao_editavel(aba, coluna: int, opcoes: list[str], lista: str) -> None:
    """Lista suspensa (avisa sem bloquear), com as opções na aba Listas, e a cor da linha acompanhando a situação."""
    if aba.max_row < 2:
        return
    letra = get_column_letter(coluna)
    letra_lista = get_column_letter(COLUNA_LISTA[lista])
    faixa_lista = f"'{ABA_LISTAS}'!${letra_lista}$1:${letra_lista}${len(opcoes)}"
    validacao = DataValidation(type="list", formula1=faixa_lista, allow_blank=True,
                               errorStyle="warning", showErrorMessage=True, errorTitle="Situação fora da lista",
                               error="Essa situação não está na lista e não entra nas contagens do Resumo.")
    validacao.add(f"{letra}2:{letra}{aba.max_row + LINHAS_EXTRAS}")
    aba.add_data_validation(validacao)
    linhas = f"A2:{get_column_letter(aba.max_column)}{aba.max_row}"
    for opcao in opcoes:
        cor = _COR_OK if opcao in _SITUACOES_OK else _COR_CONFERIR
        aba.conditional_formatting.add(linhas, FormulaRule(formula=[f'${letra}2="{opcao}"'], fill=cor,
                                                           stopIfTrue=True))


def _faixa(aba_origem: str, coluna: int, primeira: int, ultima: int) -> str:
    letra = get_column_letter(coluna)
    return f"'{aba_origem}'!${letra}${primeira}:${letra}${ultima}"


# ---------------------------------------------------------------------
# Abas de detalhe
# ---------------------------------------------------------------------
COLUNAS_COBRANCAS = ["Matrícula", "Colaborador", "0256 do mês anterior", "0258 do mês", "1204 do mês",
                     "Rescisão no razão", "Situação", "Fica no controle"]
COLUNAS_AFASTADOS = ["Matrícula", "Colaborador", "0241 do mês", "Diferença anterior", "Pago no razão",
                     "Diferença nova", "Situação", "Pagamentos no razão"]
COLUNAS_PARCELAMENTOS = ["Matrícula", "Colaborador", "Saldo anterior", "Parcela", "1204 do mês", "Pago no razão",
                         "Saldo novo", "Situação"]
COLUNAS_DEVOLUCOES = ["Matrícula", "Colaborador", "0775 do mês", "Pendência de cobrado a mais zerada", "Situação"]
COLUNAS_A_CONFERIR = ["Data", "Histórico", "Lote", "Débito", "Crédito", "Efeito no saldo", "Matrícula",
                      "Colaborador", "Motivo"]


def _ordem(situacao: str) -> tuple[int, str]:
    """O que precisa de atenção primeiro."""
    return (1 if any(situacao.startswith(ok) for ok in _SITUACOES_OK) else 0, situacao)


def _aba_cobrancas(aba, conciliacao: c.Conciliacao) -> None:
    _cabecalho(aba, COLUNAS_COBRANCAS)
    for l in sorted(conciliacao.cobrancas, key=lambda l: (_ordem(l.situacao), l.nome)):
        aba.append([l.matricula, l.nome, _f(l.valor_0256), _f(l.valor_0258), _f(l.valor_1204), _f(l.valor_rescisao),
                    l.situacao, _f(l.diferenca)])
    _formatar_valores(aba, (3, 4, 5, 6, 8))
    _situacao_editavel(aba, 7, SITUACOES_COBRANCA, "cobrancas")


def _aba_afastados(aba, conciliacao: c.Conciliacao) -> None:
    _cabecalho(aba, COLUNAS_AFASTADOS)
    for l in sorted(conciliacao.afastados, key=lambda l: (_ordem(l.situacao), l.nome)):
        pagamentos = " | ".join(f"{p.data:%d/%m} {p.historico} (R$ {p.credito - p.debito:,.2f})" if p.data
                                else p.historico for p in l.pagamentos)
        aba.append([l.matricula, l.nome, _f(l.devido), _f(l.diferenca_anterior), _f(l.pago), _f(l.diferenca_nova),
                    l.situacao, pagamentos])
    _formatar_valores(aba, (3, 4, 5, 6))
    _situacao_editavel(aba, 7, SITUACOES_AFASTADO, "afastados")


def _aba_parcelamentos(aba, conciliacao: c.Conciliacao) -> None:
    _cabecalho(aba, COLUNAS_PARCELAMENTOS)
    for l in conciliacao.parcelamentos:
        situacao = c.PARCELAMENTO_NOVO if l.situacao.startswith(c.PARCELAMENTO_NOVO) else l.situacao
        aba.append([l.matricula, l.nome, _f(l.saldo_anterior), _f(l.parcela), _f(l.descontado_1204),
                    _f(l.pago_razao), _f(l.saldo_novo), situacao])
    _formatar_valores(aba, (3, 4, 5, 6, 7))
    _situacao_editavel(aba, 8, SITUACOES_PARCELAMENTO, "parcelamentos")


def _aba_devolucoes(aba, conciliacao: c.Conciliacao) -> None:
    _cabecalho(aba, COLUNAS_DEVOLUCOES)
    for l in conciliacao.devolucoes:
        aba.append([l.matricula, l.nome, _f(l.valor), _f(l.pendencia) if l.pendencia else None, l.situacao])
    if not conciliacao.devolucoes:
        aba.append([None, "Nenhum 0775 nos PDFs de eventos escolhidos."])
    _formatar_valores(aba, (3, 4))
    if conciliacao.devolucoes:
        _situacao_editavel(aba, 5, SITUACOES_DEVOLUCAO, "devolucoes")


def _aba_a_conferir(aba, conciliacao: c.Conciliacao) -> None:
    _cabecalho(aba, COLUNAS_A_CONFERIR)
    for a in conciliacao.a_conferir:
        l = a.lancamento
        aba.append([l.data, l.historico, l.lote, _f(l.debito), _f(l.credito), _f(a.efeito), a.matricula or None,
                    a.nome or None, a.motivo])
        aba.cell(row=aba.max_row, column=1).number_format = _FORMATO_DATA
    if not conciliacao.a_conferir:
        aba.append([None, "Nenhum lançamento a conferir: todos os lançamentos do razão foram explicados."])
    _formatar_valores(aba, (4, 5, 6))


def _aba_avisos(aba, avisos: list[Aviso]) -> None:
    _cabecalho(aba, ["Arquivo", "Aviso"])
    for aviso in avisos:
        aba.append([aviso.arquivo, aviso.mensagem])
        if aviso.mensagem.startswith("ATENÇÃO"):
            for celula in aba[aba.max_row]:
                celula.fill = _COR_DESTAQUE
    if not avisos:
        aba.append([None, "Nenhum aviso."])


# ---------------------------------------------------------------------
# Resumo
# ---------------------------------------------------------------------
def _negrito(aba, linha: int) -> None:
    for celula in aba[linha]:
        celula.font = Font(bold=True)


def _titulo_bloco(aba, texto: str, segunda: str = "") -> None:
    aba.append([])
    aba.append([texto, segunda] if segunda else [texto])
    _negrito(aba, aba.max_row)


def _contagens(aba, titulo: str, aba_origem: str, coluna: int, total_linhas: int, rotulos: list[str]) -> None:
    faixa = _faixa(aba_origem, coluna, 2, max(total_linhas + 1, 2) + LINHAS_EXTRAS)
    _titulo_bloco(aba, titulo, "Quantidade")
    primeira = aba.max_row + 1
    for rotulo in rotulos:
        aba.append([rotulo, f"=COUNTIF({faixa},A{aba.max_row + 1})"])
        aba.cell(row=aba.max_row, column=1).fill = _COR_OK if rotulo in _SITUACOES_OK else _COR_CONFERIR
    ultima = aba.max_row
    aba.append(["Outros (situação digitada fora da lista)", f"=COUNTA({faixa})-SUM(B{primeira}:B{ultima})"])
    aba.append(["Total", f"=COUNTA({faixa})"])
    _negrito(aba, aba.max_row)


def _aba_resumo(aba, conciliacao: c.Conciliacao, arquivos: dict[str, str], agora: datetime,
                linhas_controle: int) -> None:
    aba.append([f"Crédito Estouro — {conciliacao.unidade} — {mes_curto(conciliacao.competencia)}"])
    aba["A1"].font = Font(bold=True, size=13)
    aba.append([f"Gerado em {agora:%d/%m/%Y %H:%M}"])
    _titulo_bloco(aba, "Arquivos usados")
    for rotulo, nome in arquivos.items():
        aba.append([rotulo, nome])

    _titulo_bloco(aba, "Razão da conta", "Valor")
    aba.append(["Saldo anterior", _f(conciliacao.saldo_anterior_razao)])
    aba.append(["Saldo final", _f(conciliacao.saldo_final_razao)])
    linha_saldo_final = aba.max_row
    aba.append(["Controle do mês anterior (deve ser igual ao saldo anterior)", _f(conciliacao.total_controle_anterior)])

    _titulo_bloco(aba, "Folha × razão", "Razão")
    aba.cell(row=aba.max_row, column=3, value="Eventos").font = Font(bold=True)
    aba.cell(row=aba.max_row, column=4, value="Diferença").font = Font(bold=True)
    for conferencia in conciliacao.conferencias_folha:
        aba.append([conferencia.descricao, _f(conferencia.razao), _f(conferencia.folha), _f(conferencia.diferenca)])
        if conferencia.diferenca:
            aba.cell(row=aba.max_row, column=4).fill = _COR_DESTAQUE

    # composição do saldo: =SOMASE na aba Controle (acompanha linha apagada ou acrescentada lá)
    ultima_controle = 5 + linhas_controle + LINHAS_EXTRAS
    tipos = _faixa(ABA_CONTROLE, COLUNAS_CONTROLE.index("Tipo") + 1, 6, ultima_controle)
    valores = _faixa(ABA_CONTROLE, COLUNAS_CONTROLE.index("Valor") + 1, 6, ultima_controle)
    _titulo_bloco(aba, "Composição do saldo (aba Controle)", "Valor")
    primeira = aba.max_row + 1
    for tipo in TIPOS_COM_VALOR:
        aba.append([tipo, f"=SUMIF({tipos},A{aba.max_row + 1},{valores})"])
    aba.append(["Total do controle", f"=SUM(B{primeira}:B{aba.max_row})"])
    linha_total = aba.max_row
    _negrito(aba, linha_total)
    aba.append(["Diferença sem explicação (saldo final do razão − total do controle; deve ser zero)",
                f"=ROUND(B{linha_saldo_final}-B{linha_total},2)"])
    _negrito(aba, aba.max_row)
    aba.cell(row=aba.max_row, column=2).fill = _COR_DESTAQUE if conciliacao.diferenca_sem_explicacao else _COR_OK
    for linha in range(4, aba.max_row + 1):
        for coluna in (2, 3, 4):
            aba.cell(row=linha, column=coluna).number_format = _FORMATO_VALOR

    _contagens(aba, "0256 do mês anterior", ABA_COBRANCAS, 7, len(conciliacao.cobrancas), SITUACOES_COBRANCA)
    _contagens(aba, "0241 – afastados", ABA_AFASTADOS, 7, len(conciliacao.afastados), SITUACOES_AFASTADO)
    _contagens(aba, "Parcelamentos", ABA_PARCELAMENTOS, 8, len(conciliacao.parcelamentos), SITUACOES_PARCELAMENTO)
    _contagens(aba, "0775 – devoluções", ABA_DEVOLUCOES, 5, len(conciliacao.devolucoes), SITUACOES_DEVOLUCAO)
    _titulo_bloco(aba, "Lançamentos do razão a conferir", "Quantidade")
    aba.append(["Lançamentos que nenhuma regra explicou (entram como acerto manual)", len(conciliacao.a_conferir)])
    aba.column_dimensions["A"].width = 75
    for coluna in "BCD":
        aba.column_dimensions[coluna].width = 16


# ---------------------------------------------------------------------
# Gravação
# ---------------------------------------------------------------------
def gravar_relatorio(caminho: Path, conciliacao: c.Conciliacao, avisos: list[Aviso], arquivos: dict[str, str],
                     agora: datetime | None = None) -> Path:
    """Grava o Excel e devolve o caminho. Levanta OSError se não der para gravar."""
    agora = agora or datetime.now()
    livro = Workbook()
    resumo = livro.active
    resumo.title = ABA_RESUMO
    for titulo, montar in ((ABA_COBRANCAS, _aba_cobrancas), (ABA_AFASTADOS, _aba_afastados),
                           (ABA_PARCELAMENTOS, _aba_parcelamentos), (ABA_DEVOLUCOES, _aba_devolucoes),
                           (ABA_A_CONFERIR, _aba_a_conferir)):
        aba = livro.create_sheet(titulo)
        montar(aba, conciliacao)
        _ajustar_larguras(aba)
    controle = livro.create_sheet(ABA_CONTROLE)
    fim_do_mes = None
    if conciliacao.competencia:
        seguinte = date(conciliacao.competencia.year + (conciliacao.competencia.month == 12),
                        conciliacao.competencia.month % 12 + 1, 1)
        fim_do_mes = date.fromordinal(seguinte.toordinal() - 1)
    escrever_aba_controle(controle, conciliacao.competencia, conciliacao.unidade, conciliacao.saldo_final_razao,
                          conciliacao.controle_novo, fim_do_mes)
    for celula in controle[5]:
        celula.font = Font(bold=True)
    controle.freeze_panes = "A6"
    _formatar_valores(controle, (5, 6), primeira_linha=6)
    controle["C3"].number_format = _FORMATO_VALOR
    _ajustar_larguras(controle)
    controle.column_dimensions["A"].width = 14
    _aba_avisos(livro.create_sheet(ABA_AVISOS), avisos)
    _ajustar_larguras(livro[ABA_AVISOS])
    _aba_resumo(resumo, conciliacao, arquivos, agora, len(conciliacao.controle_novo))
    listas = livro.create_sheet(ABA_LISTAS)
    for chave, opcoes in (("cobrancas", SITUACOES_COBRANCA), ("afastados", SITUACOES_AFASTADO),
                          ("parcelamentos", SITUACOES_PARCELAMENTO), ("devolucoes", SITUACOES_DEVOLUCAO)):
        for linha, opcao in enumerate(opcoes, start=1):
            listas.cell(row=linha, column=COLUNA_LISTA[chave], value=opcao)
    listas.sheet_state = "hidden"
    livro.save(caminho)
    return Path(caminho)
