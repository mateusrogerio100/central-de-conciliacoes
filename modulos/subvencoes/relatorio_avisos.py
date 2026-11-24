"""Gera o relatório Avisos_MM-AAAA.xlsx (seção 4.2 da especificação).

Abas:
- Resumo:      mês, arquivos lidos e o que aconteceu com cada um, planilhas geradas,
               total geral do patrimônio, conferência por aba (R9), avisos por gravidade;
- Avisos:      um aviso por linha, ERRO primeiro, depois ATENÇÃO e INFO;
- Conferência: todas as linhas de conta de todas as planilhas (R13);
- Patrimônio:  todas as contas do relatório de patrimônio, com a situação (R8, R13).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from modulos.subvencoes.conciliacao import situacao_conta_patrimonio
from modulos.subvencoes.modelos import ErroArquivo, Gravidade, ResultadoProcessamento
from modulos.subvencoes.utilitarios import para_float_excel

FORMATO_DINHEIRO = "#,##0.00;-#,##0.00"
_NEGRITO = Font(bold=True)
_TITULO = Font(bold=True, size=14)
_FUNDO_TITULO = PatternFill("solid", fgColor="D9E1F2")
_CORES_GRAVIDADE = {
    Gravidade.ERRO: PatternFill("solid", fgColor="F8CBAD"),
    Gravidade.ATENCAO: PatternFill("solid", fgColor="FFE699"),
    Gravidade.INFO: None,
}
_ORDEM_GRAVIDADE = {Gravidade.ERRO: 0, Gravidade.ATENCAO: 1, Gravidade.INFO: 2}


def gerar_relatorio(resultado: ResultadoProcessamento, caminho) -> Path:
    caminho = Path(caminho)
    pasta = Workbook()
    _aba_resumo(pasta.active, resultado)
    _aba_avisos(pasta.create_sheet("Avisos"), resultado)
    _aba_conferencia(pasta.create_sheet("Conferência"), resultado)
    _aba_patrimonio(pasta.create_sheet("Patrimônio"), resultado)
    _salvar(pasta, caminho)
    return caminho


# ---------------------------------------------------------------------------
# Auxiliares de formatação
# ---------------------------------------------------------------------------


def _dinheiro(valor):
    return None if valor is None else para_float_excel(valor)


def _tabela(aba, linha_inicial: int, titulos: list[str], linhas: list[list], colunas_dinheiro=(), larguras=None):
    """Escreve uma tabela com títulos em negrito, filtro e congelamento dos títulos."""
    for coluna, titulo in enumerate(titulos, 1):
        celula = aba.cell(linha_inicial, coluna, titulo)
        celula.font, celula.fill = _NEGRITO, _FUNDO_TITULO
        celula.alignment = Alignment(wrap_text=True, vertical="center")
    for deslocamento, valores in enumerate(linhas, 1):
        for coluna, valor in enumerate(valores, 1):
            celula = aba.cell(linha_inicial + deslocamento, coluna, valor)
            if coluna in colunas_dinheiro:
                celula.number_format = FORMATO_DINHEIRO
    ultima = linha_inicial + max(len(linhas), 1)
    aba.auto_filter.ref = f"A{linha_inicial}:{get_column_letter(len(titulos))}{ultima}"
    aba.freeze_panes = aba.cell(linha_inicial + 1, 1)
    for coluna, largura in enumerate(larguras or [], 1):
        aba.column_dimensions[get_column_letter(coluna)].width = largura


# ---------------------------------------------------------------------------
# Abas
# ---------------------------------------------------------------------------


def _aba_resumo(aba, resultado: ResultadoProcessamento):
    aba.title = "Resumo"
    linha = 1

    def escrever(*valores, negrito=False, fonte=None):
        nonlocal linha
        for coluna, valor in enumerate(valores, 1):
            celula = aba.cell(linha, coluna, valor)
            if isinstance(valor, float):          # no Resumo, todo float é dinheiro
                celula.number_format = FORMATO_DINHEIRO
            if negrito:
                celula.font = _NEGRITO
            if fonte:
                celula.font = fonte
        linha += 1

    def secao(titulo):
        nonlocal linha
        linha += 1
        escrever(titulo, fonte=Font(bold=True, size=12))

    escrever("Conciliação de Subvenções e Projetos", fonte=_TITULO)
    escrever("Mês de referência", str(resultado.mes_referencia))
    escrever("Pasta de saída", resultado.pasta_saida)

    # Avisos por gravidade
    secao("Avisos por gravidade")
    for gravidade, quantidade in resultado.quantidade_por_gravidade().items():
        escrever(gravidade.value, quantidade)
        if _CORES_GRAVIDADE[gravidade] and quantidade:
            aba.cell(linha - 1, 1).fill = _CORES_GRAVIDADE[gravidade]

    # Arquivos lidos (R13)
    secao("Arquivos de entrada")
    escrever("Tipo", "Arquivo", "Mês lido", "Situação", "Detalhe", negrito=True)
    for arquivo in resultado.arquivos:
        escrever(arquivo.tipo, arquivo.nome, str(arquivo.mes_lido) if arquivo.mes_lido else "",
                 arquivo.status.value, arquivo.detalhe)
        if arquivo.status.value in ("falhou", "não processado"):
            aba.cell(linha - 1, 4).fill = _CORES_GRAVIDADE[Gravidade.ERRO]

    # Planilhas geradas
    secao("Planilhas")
    escrever("Planilha de entrada", "Arquivo gerado", "Linhas preenchidas",
             "Linhas com Saldo Patrimônio ≠ Saldo Contábil", "Abas sem contas", negrito=True)
    for planilha in resultado.planilhas:
        escrever(planilha.nome, Path(planilha.destino).name if planilha.destino else "(não gerado)",
                 planilha.linhas_preenchidas, planilha.linhas_com_diferenca, ", ".join(planilha.abas_sem_contas))

    # Conferência por aba (R9)
    if resultado.conciliacao is not None:
        secao("Conferência por aba (soma do Saldo Contábil x conta sintética do balancete)")
        escrever("Planilha", "Aba", "Soma Saldo Contábil", "Conta sintética", "Saldo Atual da sintética",
                 "Confere?", negrito=True)
        for conferencia in resultado.conciliacao.conferencias_aba:
            sintetica = conferencia.sintetica
            escrever(conferencia.planilha, conferencia.aba, _dinheiro(conferencia.soma_saldo_contabil),
                     f"{sintetica.classificacao} {sintetica.descricao}" if sintetica
                     else ", ".join(conferencia.classificacoes_sinteticas),
                     _dinheiro(sintetica.saldo_atual) if sintetica else None,
                     "sim" if conferencia.confere else "NÃO")
            if not conferencia.confere:
                aba.cell(linha - 1, 6).fill = _CORES_GRAVIDADE[Gravidade.ATENCAO]

    # Total geral do patrimônio
    patrimonio = resultado.patrimonio
    if patrimonio is not None:
        secao("Total geral do patrimônio")
        escrever("Soma dos bens lidos", _dinheiro(patrimonio.soma_itens))
        escrever("Total do sistema (linha Total)", _dinheiro(patrimonio.total_geral_sistema))
        escrever("Diferença", _dinheiro(patrimonio.soma_itens - patrimonio.total_geral_sistema)
                 if patrimonio.total_geral_sistema is not None else None)
        escrever("Bens lidos / do sistema", f"{patrimonio.quantidade_itens} / {patrimonio.quantidade_geral_sistema}")
        escrever("Confere?", "sim" if patrimonio.total_geral_confere else "NÃO")
        if not patrimonio.total_geral_confere:
            aba.cell(linha - 1, 2).fill = _CORES_GRAVIDADE[Gravidade.ERRO]

    for coluna, largura in zip("ABCDEF", (34, 42, 20, 38, 60, 12)):
        aba.column_dimensions[coluna].width = largura


def _aba_avisos(aba, resultado: ResultadoProcessamento):
    avisos = sorted(resultado.avisos, key=lambda a: _ORDEM_GRAVIDADE[a.gravidade])   # sort estável
    linhas = [[a.gravidade.value, a.tipo, a.arquivo, a.aba, a.linha, a.conta, a.mensagem] for a in avisos]
    _tabela(aba, 1, ["Gravidade", "Tipo", "Arquivo", "Aba", "Linha", "Conta", "Mensagem"], linhas,
            larguras=[11, 30, 36, 24, 8, 32, 110])
    for deslocamento, aviso in enumerate(avisos, 2):
        cor = _CORES_GRAVIDADE[aviso.gravidade]
        if cor:
            aba.cell(deslocamento, 1).fill = cor


def _aba_conferencia(aba, resultado: ResultadoProcessamento):
    linhas_conciliadas = resultado.conciliacao.linhas if resultado.conciliacao else []
    linhas = [
        [l.planilha, l.aba, l.linha, l.conta_contabil, l.convenio, l.descricao_balancete,
         _dinheiro(l.saldo_patrimonio), _dinheiro(l.saldo_contabil), _dinheiro(l.diferenca), l.observacao]
        for l in linhas_conciliadas
    ]
    _tabela(aba, 1, ["Planilha", "Aba", "Linha", "Conta Contábil", "Convênio", "Descrição no balancete",
                     "Saldo Patrimônio", "Saldo Contábil", "Patrimônio − Contábil", "Observação"],
            linhas, colunas_dinheiro=(7, 8, 9), larguras=[36, 24, 8, 14, 36, 44, 17, 17, 17, 60])


def _aba_patrimonio(aba, resultado: ResultadoProcessamento):
    patrimonio = resultado.patrimonio
    linhas = []
    if patrimonio is not None and resultado.conciliacao is not None:
        for conta in patrimonio.contas:
            linhas.append([conta.nome, _dinheiro(conta.soma_itens), _dinheiro(conta.total_sistema),
                           len(conta.itens), conta.quantidade_sistema,
                           situacao_conta_patrimonio(conta, resultado.conciliacao)])
    _tabela(aba, 1, ["Conta", "Soma dos bens", "Total do sistema", "Qtd itens lida", "Qtd do sistema",
                     "Situação"], linhas, colunas_dinheiro=(2, 3), larguras=[60, 17, 17, 14, 14, 20])


def _salvar(pasta, caminho: Path):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    descritor, temporario = tempfile.mkstemp(suffix=".xlsx", prefix="~tmp_", dir=caminho.parent)
    os.close(descritor)
    try:
        pasta.save(temporario)
        os.replace(temporario, caminho)
    except PermissionError:
        raise ErroArquivo(f"{caminho.name}: não foi possível gravar. Feche o arquivo no Excel e tente de novo.")
    finally:
        if os.path.exists(temporario):
            os.remove(temporario)
