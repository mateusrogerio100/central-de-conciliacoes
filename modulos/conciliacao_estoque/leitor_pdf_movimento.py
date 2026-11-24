"""Leitura do PDF "Movimento estoque" do Tasy, quebra por Operação (ESPECIFICACAO_ESTOQUE.md, seção 3.5).

Como o texto é lido (linha por linha, página por página):
- "Data de Referência : 01/09/2026" -> mês de referência;
- ou, quando o relatório foi tirado por período, "De : 01/10/2026 00:00 Até : 31/10/2026 23:59"
  -> mês de referência, se o período for um mês inteiro (do dia 1 ao último dia; ajuste de 04/11/2026);
- "Operação <código>" abre uma operação (o nome dela é ignorado: vem quebrado em várias linhas,
  às vezes acima da linha "Operação"; o nome exibido vem da configuração);
- a próxima linha "Total ..." fecha a operação: o VALOR é o último número da linha;
- uma linha "Total ..." sem operação aberta é a soma do relatório (ignorada);
- "Total geral: <quantidade> <valor>" -> total geral (o último número).
Conferência obrigatória: soma das operações = Total geral.
"""

from __future__ import annotations

import calendar
import re
from datetime import date
from pathlib import Path

import pdfplumber

from modulos.conciliacao_estoque import configuracao
from modulos.conciliacao_estoque.modelos import (
    Aviso,
    ErroArquivo,
    Gravidade,
    MesReferencia,
    MovimentoEstoquePDF,
    OperacaoPDF,
)
from modulos.conciliacao_estoque.utilitarios import (
    formatar_valor,
    mes_de_texto,
    normalizar_texto,
    para_decimal,
    texto_comeca_com,
)

_PADRAO_OPERACAO = re.compile(r"^Opera[çc][ãa]o\s+(\d+)\b", re.IGNORECASE)
_PADRAO_TOTAL_GERAL = re.compile(r"^Total\s+geral\s*:", re.IGNORECASE)
_PADRAO_TOTAL = re.compile(r"^Total\b", re.IGNORECASE)
_PADRAO_DATA = re.compile(r"(\d{2}/\d{2}/\d{4})")
_PADRAO_PERIODO = re.compile(
    r"^De\s*:\s*(\d{2})/(\d{2})/(\d{4}).*?At[ée]\s*:\s*(\d{2})/(\d{2})/(\d{4})", re.IGNORECASE
)


def ler_paginas(caminho: Path) -> list[str]:
    """Texto de cada página do PDF."""
    try:
        with pdfplumber.open(caminho) as pdf:
            return [pagina.extract_text() or "" for pagina in pdf.pages]
    except FileNotFoundError:
        raise ErroArquivo(f"{caminho.name}: arquivo não encontrado.")
    except PermissionError:
        raise ErroArquivo(f"{caminho.name}: o arquivo está aberto em outro programa (feche e tente de novo).")
    except Exception as erro:       # pdfplumber/pdfminer levantam vários tipos para PDF inválido
        raise ErroArquivo(f"{caminho.name}: não foi possível ler o PDF ({erro}).")


def ler_pdf_movimento(caminho) -> MovimentoEstoquePDF:
    caminho = Path(caminho)
    return ler_texto_movimento(ler_paginas(caminho), caminho.name)


def ler_texto_movimento(paginas: list[str], nome_arquivo: str) -> MovimentoEstoquePDF:
    """Interpreta o texto já extraído (separado para os testes poderem montar casos)."""
    movimento = MovimentoEstoquePDF(arquivo=nome_arquivo)

    def avisar(gravidade, tipo, mensagem, conta=""):
        movimento.avisos.append(Aviso(gravidade, tipo, mensagem, arquivo=nome_arquivo, conta=conta))

    if not any(normalizar_texto(configuracao.PDF_TITULO) in normalizar_texto(p) for p in paginas):
        raise ErroArquivo(
            f"{nome_arquivo}: não parece ser o relatório '{configuracao.PDF_TITULO}' do Tasy "
            "(se for um PDF escaneado, gere de novo pelo Tasy)."
        )

    aberta: tuple[int, int] | None = None       # (código, página) da operação sem Total ainda
    for numero_pagina, texto in enumerate(paginas, start=1):
        for linha in (l.strip() for l in texto.splitlines()):
            if not linha or any(texto_comeca_com(linha, r) for r in configuracao.PDF_RODAPES):
                continue
            if texto_comeca_com(linha, configuracao.PDF_ROTULO_MES):
                _ler_mes(movimento, linha, avisar)
                continue
            periodo = _PADRAO_PERIODO.match(linha)
            if periodo:
                _ler_periodo(movimento, periodo, linha, avisar)
                continue
            operacao = _PADRAO_OPERACAO.match(linha)
            if operacao:
                if aberta is not None:
                    avisar(Gravidade.ERRO, "operação sem total",
                           f"Operação {aberta[0]} sem linha 'Total' antes da operação {operacao.group(1)}.",
                           str(aberta[0]))
                aberta = (int(operacao.group(1)), numero_pagina)
                continue
            if _PADRAO_TOTAL_GERAL.match(linha):
                movimento.total_geral = _ultimo_numero(linha)
                if movimento.total_geral is None:
                    avisar(Gravidade.ERRO, "total geral ilegível", f"Linha do Total geral sem valor: {linha!r}.")
                continue
            if _PADRAO_TOTAL.match(linha) and aberta is not None:
                _fechar_operacao(movimento, aberta, linha, avisar)
                aberta = None

    if aberta is not None:
        avisar(Gravidade.ERRO, "operação sem total", f"Operação {aberta[0]} sem linha 'Total'.", str(aberta[0]))
    if movimento.mes_referencia is None:
        avisar(Gravidade.ATENCAO, "mês não encontrado",
               f"'{configuracao.PDF_ROTULO_MES}' (ou período 'De … Até …' de um mês inteiro) não encontrada no PDF.")
    _conferir_total_geral(movimento, avisar)
    return movimento


def _ultimo_numero(linha: str):
    numeros = [para_decimal(p) for p in linha.split() if para_decimal(p) is not None]
    return numeros[-1] if numeros else None


def _ler_mes(movimento, linha, avisar):
    data = _PADRAO_DATA.search(linha)
    mes = mes_de_texto(data.group(1)) if data else None
    if mes is None:
        avisar(Gravidade.ATENCAO, "mês não reconhecido", f"Não foi possível ler o mês de referência: {linha!r}.")
    elif movimento.mes_referencia is None:
        movimento.mes_referencia = mes


def _ler_periodo(movimento, periodo, linha, avisar):
    """Relatório tirado por período: vale como mês de referência só se for um mês inteiro."""
    try:
        dia_i, mes_i, ano_i, dia_f, mes_f, ano_f = (int(g) for g in periodo.groups())
        inicio, fim = date(ano_i, mes_i, dia_i), date(ano_f, mes_f, dia_f)
    except ValueError:
        avisar(Gravidade.ATENCAO, "mês não reconhecido", f"Não foi possível ler o período do relatório: {linha!r}.")
        return
    ultimo_dia = calendar.monthrange(inicio.year, inicio.month)[1]
    if inicio.day != 1 or fim != date(inicio.year, inicio.month, ultimo_dia):
        avisar(Gravidade.ATENCAO, "período não é um mês inteiro",
               f"O PDF foi tirado de {inicio:%d/%m/%Y} a {fim:%d/%m/%Y}, que não é um mês inteiro: "
               "confira se os valores são os do mês da conciliação.")
        return
    if movimento.mes_referencia is None:
        movimento.mes_referencia = MesReferencia(inicio.year, inicio.month)


def _fechar_operacao(movimento, aberta, linha, avisar):
    codigo, pagina = aberta
    valor = _ultimo_numero(linha)
    if valor is None:
        avisar(Gravidade.ERRO, "operação sem valor", f"Operação {codigo}: linha Total sem valor ({linha!r}).",
               str(codigo))
        return
    if any(o.codigo == codigo for o in movimento.operacoes):
        avisar(Gravidade.ERRO, "operação repetida",
               f"Operação {codigo} aparece mais de uma vez no PDF; vale a primeira.", str(codigo))
        return
    movimento.operacoes.append(OperacaoPDF(codigo=codigo, valor=valor, pagina=pagina))


def _conferir_total_geral(movimento, avisar):
    if movimento.total_geral is None:
        avisar(Gravidade.ERRO, "total geral não encontrado",
               "Linha 'Total geral:' não encontrada no PDF; não dá para conferir se a leitura está completa.")
    elif movimento.soma_operacoes != movimento.total_geral:
        avisar(Gravidade.ERRO, "soma diferente do total geral",
               f"Soma das operações lidas {formatar_valor(movimento.soma_operacoes)} diferente do Total geral "
               f"{formatar_valor(movimento.total_geral)} (alguma operação não foi lida).")
