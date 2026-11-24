"""Gera a planilha de saída da conciliação (seção 8 da especificação).

Abas:
  Resumo       competência, data/hora da geração, contagens por status (fórmulas: mudou o status
               na aba Conciliação ou Arquivos, a contagem se ajusta sozinha; pedido do usuário, 06/11/2026)
  Conciliação  uma linha por conta do balancete + NÃO ESTÁ NO BALANCETE
  Arquivos     uma linha por arquivo encontrado na pasta
  Detalhe      uma linha por saldo lido de cada extrato
"""

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from .comparador import DIFERENCA, NAO_ESTA_NO_BALANCETE, OK, SEM_EXTRATO, LinhaConciliacao
from .identificador import (DUPLICADO, ERRO_DE_LEITURA, ESCANEADO, LIDO,
                            MODELO_NAO_RECONHECIDO, ResumoArquivo)
from .modelos import SaldoExtraido

FORMATO_VALOR = "#,##0.00"
LARGURA_MAXIMA = 60

_VERDE = PatternFill("solid", fgColor="C6EFCE")
_VERMELHO = PatternFill("solid", fgColor="FFC7CE")
_AMARELO = PatternFill("solid", fgColor="FFEB9C")
_CINZA = PatternFill("solid", fgColor="D9D9D9")

COR_POR_STATUS = {
    OK: _VERDE,
    DIFERENCA: _VERMELHO,
    SEM_EXTRATO: _AMARELO,
    NAO_ESTA_NO_BALANCETE: _AMARELO,
    ESCANEADO: _CINZA,
    ERRO_DE_LEITURA: _CINZA,
    MODELO_NAO_RECONHECIDO: _CINZA,
    DUPLICADO: _CINZA,
}

CABECALHO_CONCILIACAO = [
    "Código", "Classificação", "Descrição", "Banco", "Tipo", "Conta",
    "Saldo Balancete", "Saldo Disponível (extrato)", "Saldo Bloqueado (extrato)",
    "Saldo Total (extrato)", "Diferença", "Status", "Arquivos", "Observação",
]
STATUS_CONCILIACAO = (OK, DIFERENCA, SEM_EXTRATO, NAO_ESTA_NO_BALANCETE)
SITUACOES_ARQUIVO = (LIDO, ESCANEADO, MODELO_NAO_RECONHECIDO, ERRO_DE_LEITURA, DUPLICADO)
ABA_CONCILIACAO, ABA_ARQUIVOS = "Conciliação", "Arquivos"

CABECALHO_ARQUIVOS = ["Subpasta", "Arquivo", "Modelo", "Situação", "Contas extraídas", "Mensagem"]
CABECALHO_DETALHE = [
    "Arquivo", "Modelo", "Banco", "Tipo", "Conta original", "Conta normalizada",
    "Disponível", "Bloqueado", "Total", "Fonte secundária", "Observação",
]


def nome_padrao(competencia: date) -> str:
    return f"conciliacao_bancaria_{competencia:%Y-%m}.xlsx"


def gerar_relatorio(saida: Path, competencia: date, linhas: list[LinhaConciliacao],
                    arquivos: list[ResumoArquivo]) -> Path:
    """Grava a planilha e devolve o caminho do arquivo gerado.

    `saida` pode ser uma pasta (o arquivo recebe o nome padrão) ou o
    caminho completo do .xlsx.
    """
    saida = Path(saida)
    if saida.suffix.lower() != ".xlsx":
        saida.mkdir(parents=True, exist_ok=True)
        saida = saida / nome_padrao(competencia)
    else:
        saida.parent.mkdir(parents=True, exist_ok=True)

    pasta = Workbook()
    _aba_resumo(pasta.active, competencia, linhas, arquivos)
    _aba_conciliacao(pasta.create_sheet(ABA_CONCILIACAO), linhas)
    _aba_arquivos(pasta.create_sheet(ABA_ARQUIVOS), arquivos)
    _aba_detalhe(pasta.create_sheet("Detalhe"), arquivos)
    pasta.save(saida)
    return saida


# ---------------------------------------------------------------------------
# Abas
# ---------------------------------------------------------------------------

def _aba_resumo(aba, competencia, linhas, arquivos):
    aba.title = "Resumo"
    aba.append(["Conciliação bancária"])
    aba["A1"].font = Font(bold=True, size=14)
    aba.append([])
    aba.append(["Competência", f"{competencia:%m/%Y}"])
    aba.append(["Gerado em", datetime.now().strftime("%d/%m/%Y %H:%M")])
    aba.append([])

    # As quantidades são fórmulas (CONT.SE) sobre a coluna de status da outra aba: quem resolve uma
    # pendência e troca o status lá vê o Resumo se ajustar sozinho.
    _contagens(aba, "Contas por status", STATUS_CONCILIACAO, ABA_CONCILIACAO,
               CABECALHO_CONCILIACAO.index("Status") + 1, len(linhas))
    aba.append([])
    _contagens(aba, "Arquivos por situação", SITUACOES_ARQUIVO, ABA_ARQUIVOS,
               CABECALHO_ARQUIVOS.index("Situação") + 1, len(arquivos))
    aba.append(["Observação", "As quantidades são fórmulas: mudou o status na aba Conciliação ou Arquivos, "
                              "o Resumo se ajusta sozinho."])
    _ajustar_larguras(aba)
    aba.column_dimensions["B"].width = 14


def _contagens(aba, titulo: str, rotulos, aba_origem: str, coluna_status: int, total_linhas: int):
    """Bloco "rótulo | =CONT.SE(coluna de status; rótulo)" e a linha Total (=SOMA), mais a linha
    "Outros" para status digitado diferente dos da lista (a soma sempre bate com o total de linhas)."""
    letra = get_column_letter(coluna_status)
    faixa = f"'{aba_origem}'!${letra}$2:${letra}${max(total_linhas + 1, 2)}"
    aba.append([titulo, "Quantidade"])
    _negrito(aba, aba.max_row)
    primeira = aba.max_row + 1
    for rotulo in rotulos:
        aba.append([rotulo, f"=COUNTIF({faixa},A{aba.max_row + 1})"])
        if rotulo in COR_POR_STATUS:
            aba.cell(aba.max_row, 1).fill = COR_POR_STATUS[rotulo]
    ultima = aba.max_row
    aba.append(["Outros (status digitado fora da lista)",
                f"=COUNTA({faixa})-SUM(B{primeira}:B{ultima})"])
    aba.append(["Total", f"=COUNTA({faixa})"])
    _negrito(aba, aba.max_row)


def _aba_conciliacao(aba, linhas: list[LinhaConciliacao]):
    aba.append(CABECALHO_CONCILIACAO)
    for linha in linhas:
        conta = linha.conta_balancete
        grupo = linha.grupo
        aba.append([
            _numero_se_possivel(conta.codigo) if conta else None,
            conta.classificacao if conta else None,
            conta.descricao if conta else None,
            linha.banco or None,
            linha.tipo or None,
            linha.conta or None,
            linha.saldo_balancete,
            grupo.saldo_disponivel if grupo else None,
            grupo.saldo_bloqueado if grupo else None,
            grupo.saldo_total if grupo else None,
            linha.diferenca,
            linha.status,
            ", ".join(linha.arquivos) or None,
            linha.observacao or None,
        ])
    _formatar_tabela(aba, colunas_valor=(7, 8, 9, 10, 11), coluna_status=12)
    _status_editavel(aba, 12, STATUS_CONCILIACAO)


def _aba_arquivos(aba, arquivos: list[ResumoArquivo]):
    aba.append(CABECALHO_ARQUIVOS)
    for resumo in arquivos:
        aba.append([
            resumo.subpasta or None,
            resumo.arquivo.name,
            resumo.modelo or None,
            resumo.situacao,
            "; ".join(_descrever_saldo(s) for s in resumo.saldos) or None,
            resumo.mensagem or None,
        ])
    _formatar_tabela(aba, colunas_valor=(), coluna_status=4)
    _status_editavel(aba, 4, SITUACOES_ARQUIVO)


def _aba_detalhe(aba, arquivos: list[ResumoArquivo]):
    aba.append(CABECALHO_DETALHE)
    for resumo in arquivos:
        for saldo in resumo.saldos:
            aba.append([
                resumo.arquivo.name,
                saldo.modelo,
                saldo.banco,
                saldo.tipo,
                saldo.conta_original,
                saldo.conta,
                saldo.saldo_disponivel,
                saldo.saldo_bloqueado,
                saldo.saldo_total,
                "Sim" if saldo.fonte_secundaria else "Não",
                saldo.observacao or None,
            ])
    _formatar_tabela(aba, colunas_valor=(7, 8, 9), coluna_status=None)


# ---------------------------------------------------------------------------
# Formatação
# ---------------------------------------------------------------------------

def _formatar_tabela(aba, colunas_valor, coluna_status):
    """Cabeçalho em negrito e congelado, filtro, formato de valor e cores."""
    _negrito(aba, 1)
    aba.freeze_panes = "A2"
    aba.auto_filter.ref = aba.dimensions
    for num_linha in range(2, aba.max_row + 1):
        for coluna in colunas_valor:
            aba.cell(num_linha, coluna).number_format = FORMATO_VALOR
        if coluna_status:
            cor = COR_POR_STATUS.get(aba.cell(num_linha, coluna_status).value)
            if cor:
                for coluna in range(1, aba.max_column + 1):
                    aba.cell(num_linha, coluna).fill = cor
    _ajustar_larguras(aba)


def _status_editavel(aba, coluna_status: int, opcoes):
    """Lista suspensa com os status possíveis (aviso, sem bloquear, se digitarem outro) e a cor da
    linha acompanhando o status quando ele é trocado na planilha."""
    if aba.max_row < 2:
        return
    letra = get_column_letter(coluna_status)
    faixa = f"{letra}2:{letra}{aba.max_row}"
    lista = DataValidation(type="list", formula1='"' + ",".join(opcoes) + '"', allow_blank=True,
                           errorStyle="warning", showErrorMessage=True, errorTitle="Status fora da lista",
                           error="Esse status não está na lista e não entra nas contagens do Resumo.")
    lista.add(faixa)
    aba.add_data_validation(lista)
    linhas = f"A2:{get_column_letter(aba.max_column)}{aba.max_row}"
    for opcao in opcoes:
        if opcao in COR_POR_STATUS:
            aba.conditional_formatting.add(linhas, FormulaRule(
                formula=[f'${letra}2="{opcao}"'], fill=COR_POR_STATUS[opcao], stopIfTrue=True))


def _negrito(aba, num_linha):
    for celula in aba[num_linha]:
        celula.font = Font(bold=True)


def _ajustar_larguras(aba):
    for num_coluna, coluna in enumerate(aba.iter_cols(), 1):
        maior = max((len(_texto_exibido(c.value)) for c in coluna), default=0)
        aba.column_dimensions[get_column_letter(num_coluna)].width = min(maior + 2, LARGURA_MAXIMA)


def _texto_exibido(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, Decimal):
        return f"{valor:,.2f}"
    return str(valor)


def _descrever_saldo(saldo: SaldoExtraido) -> str:
    texto = f"{saldo.tipo} {saldo.conta_original}"
    return texto + " (fonte secundária)" if saldo.fonte_secundaria else texto


def _numero_se_possivel(texto: str):
    """Código "10007" vira número no Excel (para ordenar/filtrar certo)."""
    return int(texto) if texto.isdigit() else texto
