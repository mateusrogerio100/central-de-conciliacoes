"""Leitura do relatório Eventos do Tasy ("Conferência Lançamentos Contábeis"). Seção 2.1, regras R1 e R2.

- O arquivo do Tasy é um .XLS muito antigo (Excel 2.1, BIFF2), lido pelo xlrd. Aceita também o .xlsx
  "tratado" de agosto/2026 (aba Plan1, colunas espalhadas e valores em texto "57,03-"), só para o teste de
  agosto (decisão do usuário, 30/10/2026).
- As colunas mudam de lugar entre os dois formatos: cada linha é lida pelas células preenchidas, na ordem,
  nunca pela letra da coluna.
- Blocos por evento: "Evento:" (número, nome, sinal) → médicos → subtotal de cada centro de custo → "Total
  Evento". Cabeçalho e rodapé de página no meio do bloco são ignorados e não interrompem o bloco (R1).
- R1: subtotal de CC = linha com exatamente três células: código inteiro, nome (texto) e valor.
- R2: a soma dos subtotais de CC = o valor do "Total Evento". Se não bater, ou sem "Total Evento", o evento
  fica com erro e não entra na planilha (aparece no relatório).
- Conferência extra da leitura: a linha do total geral, no fim do relatório, = a soma dos "Total Evento".
"""

from __future__ import annotations

import io
import zipfile
from datetime import date, datetime
from pathlib import Path

import openpyxl
import xlrd

from modulos.planilha_hm import configuracao as cfg
from modulos.planilha_hm.modelos import Aviso, ErroLeitura, Evento, Eventos, SubtotalCC
from modulos.planilha_hm.normalizacao import formatar_valor, normalizar, para_decimal, para_inteiro, texto_igual


def _ler_bytes(caminho: Path) -> bytes:
    try:
        return caminho.read_bytes()
    except FileNotFoundError:
        raise ErroLeitura(f"Arquivo não encontrado: {caminho}") from None
    except PermissionError:
        raise ErroLeitura(f"{caminho.name}: o arquivo está bloqueado por outro programa. Feche e tente de novo.") from None


def _linhas_xlsx(nome: str, conteudo: bytes) -> list[tuple]:
    try:
        livro = openpyxl.load_workbook(io.BytesIO(conteudo), read_only=True, data_only=True)
    except (zipfile.BadZipFile, KeyError, OSError, ValueError) as erro:
        raise ErroLeitura(f"{nome}: não foi possível abrir como planilha .xlsx ({erro}).") from None
    try:
        aba = livro[cfg.EVENTOS_ABA_XLSX] if cfg.EVENTOS_ABA_XLSX in livro.sheetnames else livro.worksheets[0]
        return [tuple(v) for v in aba.iter_rows(values_only=True)]
    finally:
        livro.close()


def _linhas_xls(nome: str, conteudo: bytes) -> list[tuple]:
    try:
        # logfile: o xlrd escreve avisos ("No CODEPAGE record") na tela; aqui eles não interessam
        livro = xlrd.open_workbook(file_contents=conteudo, logfile=io.StringIO())
    except xlrd.XLRDError as erro:
        raise ErroLeitura(f"{nome}: não foi possível abrir como planilha .XLS ({erro}).") from None
    aba = livro.sheet_by_index(0)
    return [tuple(aba.row_values(r)) for r in range(aba.nrows)]


def _linhas(caminho: Path) -> list[tuple]:
    conteudo = _ler_bytes(caminho)
    if conteudo.startswith(b"PK"):
        return _linhas_xlsx(caminho.name, conteudo)
    return _linhas_xls(caminho.name, conteudo)


def _preenchidas(valores: tuple) -> list:
    """As células preenchidas da linha, na ordem (0 conta como preenchido; texto em branco não)."""
    return [v for v in valores if v is not None and not (isinstance(v, str) and not v.strip())]


def _texto(valor) -> str:
    return " ".join(str(valor).split()) if valor is not None else ""


def _competencia(valor) -> tuple[int, int] | None:
    if isinstance(valor, (datetime, date)):
        return valor.year, valor.month
    achado = cfg.RE_COMPETENCIA_TEXTO.match(str(valor))
    if achado and 1 <= int(achado.group(1)) <= 12:
        return int(achado.group(2)), int(achado.group(1))
    return None


def _e_subtotal_cc(celulas: list) -> bool:
    """R1: código inteiro, nome em texto e valor; nada mais na linha."""
    return (len(celulas) == 3 and para_inteiro(celulas[0]) is not None
            and isinstance(celulas[1], str) and para_decimal(celulas[1]) is None
            and para_decimal(celulas[2]) is not None)


def _e_medico(celulas: list) -> bool:
    """Linha de médico: código do médico, nome, contas e valor (ao menos quatro células, valor no fim)."""
    return len(celulas) >= 4 and para_inteiro(celulas[0]) is not None and para_decimal(celulas[-1]) is not None


def ler_eventos(caminho: Path) -> Eventos:
    """Lê o relatório. Levanta ErroLeitura se o arquivo não for o Eventos (sem o título ou sem nenhum evento)."""
    caminho = Path(caminho)
    eventos = Eventos(arquivo=caminho.name)
    linhas = _linhas(caminho)

    def avisar(numero, mensagem, erro=False):
        eventos.avisos.append(Aviso(f"{caminho.name} linha {numero}", mensagem, erro))

    tem_titulo = False
    atual: Evento | None = None          # o evento cujo bloco está aberto (até o "Total Evento")
    for numero, valores in enumerate(linhas, start=1):
        celulas = _preenchidas(valores)
        if not celulas:
            continue
        primeira = celulas[0]

        if isinstance(primeira, str):
            texto = normalizar(primeira)
            if texto.startswith(normalizar(cfg.EVENTOS_INICIO_RODAPE)) or any(
                    texto_igual(primeira, t) for t in cfg.EVENTOS_TEXTOS_CABECALHO):
                continue
            if texto_igual(primeira, cfg.EVENTOS_TITULO):
                tem_titulo = True
                continue
            if texto_igual(primeira, cfg.EVENTOS_TEXTO_COMPETENCIA):
                _ler_competencia(eventos, celulas, numero, avisar)
                continue
            if texto_igual(primeira, cfg.EVENTOS_TEXTO_EVENTO):
                atual = _novo_evento(eventos, celulas, numero, avisar)
                continue
            if texto_igual(primeira, cfg.EVENTOS_TEXTO_TOTAL):
                _ler_total(atual, celulas, numero, avisar)
                atual = None
                continue

        if _e_subtotal_cc(celulas):
            if atual is None:
                avisar(numero, f"Subtotal do centro de custo {_texto(celulas[0])} {_texto(celulas[1])} fora de um "
                               "evento: ignorado.", erro=True)
                continue
            atual.subtotais.append(SubtotalCC(atual.numero, str(para_inteiro(celulas[0])), _texto(celulas[1]),
                                              para_decimal(celulas[2]), numero))
            continue
        if _e_medico(celulas):
            continue
        if len(celulas) == 1 and para_decimal(primeira) is not None and atual is None:
            eventos.total_relatorio = para_decimal(primeira)
            continue
        avisar(numero, f"Linha não reconhecida ({' | '.join(_texto(c) for c in celulas)[:120]}): ignorada.")

    if not tem_titulo:
        raise ErroLeitura(f"{caminho.name}: não parece ser o relatório Eventos do Tasy (título "
                          f"'{cfg.EVENTOS_TITULO}' não encontrado).")
    if not eventos.eventos:
        raise ErroLeitura(f"{caminho.name}: nenhum evento encontrado no relatório.")
    if eventos.mes is None:
        eventos.avisos.append(Aviso(caminho.name, "Competência não encontrada: mês do relatório desconhecido.",
                                    erro=True))
    for evento in eventos.eventos:
        _conferir_evento(evento, caminho.name)
    _conferir_total_relatorio(eventos, caminho.name)
    return eventos


def _ler_competencia(eventos: Eventos, celulas: list, numero: int, avisar) -> None:
    competencias = [c for c in (_competencia(v) for v in celulas[1:]) if c]
    if not competencias or eventos.mes is not None:
        return
    eventos.ano, eventos.mes = competencias[0]
    if competencias[-1] != competencias[0]:
        avisar(numero, f"A competência do relatório vai de {competencias[0][1]:02d}/{competencias[0][0]} a "
                       f"{competencias[-1][1]:02d}/{competencias[-1][0]}: mais de um mês. Vale o primeiro.", erro=True)


def _novo_evento(eventos: Eventos, celulas: list, numero: int, avisar) -> Evento | None:
    numero_evento = para_inteiro(celulas[1]) if len(celulas) > 1 else None
    if numero_evento is None:
        avisar(numero, "Linha \"Evento:\" sem o número do evento: bloco ignorado.", erro=True)
        return None
    if any(e.numero == numero_evento for e in eventos.eventos):
        avisar(numero, f"O evento {numero_evento} aparece de novo no relatório: os dois blocos ficam separados.",
               erro=True)
    nome = _texto(celulas[2]) if len(celulas) > 2 else ""
    sinal = _texto(celulas[3]) if len(celulas) > 3 else ""
    evento = Evento(numero_evento, nome, sinal, numero)
    eventos.eventos.append(evento)
    return evento


def _ler_total(atual: Evento | None, celulas: list, numero: int, avisar) -> None:
    """"Total Evento": número, nome, [conta], código do histórico, valor (o valor é sempre a última célula)."""
    numero_evento = para_inteiro(celulas[1]) if len(celulas) > 1 else None
    if atual is None or numero_evento != atual.numero:
        avisar(numero, f"Linha \"Total Evento\" do evento {numero_evento} fora do lugar: ignorada.", erro=True)
        return
    atual.total = para_decimal(celulas[-1])
    if len(celulas) >= 5 and para_inteiro(celulas[-2]) is not None:
        atual.codigo_historico = str(para_inteiro(celulas[-2]))


def _conferir_evento(evento: Evento, arquivo: str) -> None:
    """R2."""
    if evento.total is None:
        evento.erro = "Linha \"Total Evento\" não encontrada: não dá para conferir o evento."
    elif not evento.subtotais:
        evento.erro = "Nenhum subtotal de centro de custo no evento."
    elif evento.soma_subtotais != evento.total:
        evento.erro = (f"Soma dos centros de custo ({formatar_valor(evento.soma_subtotais)}) diferente do Total "
                       f"Evento ({formatar_valor(evento.total)}).")


def _conferir_total_relatorio(eventos: Eventos, arquivo: str) -> None:
    if eventos.total_relatorio is None:
        eventos.avisos.append(Aviso(arquivo, "Linha do total geral do relatório não encontrada: a soma dos eventos "
                                             "não foi conferida com ela."))
    elif eventos.total_relatorio != eventos.total:
        eventos.avisos.append(Aviso(arquivo, f"Soma dos Total Evento ({formatar_valor(eventos.total)}) diferente do "
                                             f"total geral do relatório ({formatar_valor(eventos.total_relatorio)}): "
                                             "algum evento não foi lido.", erro=True))
