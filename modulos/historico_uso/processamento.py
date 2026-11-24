"""Histórico de uso: junta os arquivos do log de uso da pasta da rede numa planilha (pedido da chefia,
23/10/2026). É o único arquivo do módulo que a tela chama.

Os arquivos são gravados pela Central de cada computador (central/log_uso.py): um por mês, computador e
usuário, com uma linha por uso (abrir a Central ou processar num módulo). Este módulo só lê: nunca altera
nem apaga os arquivos da rede.
"""

from __future__ import annotations

import csv
import io
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from central import log_uso
from central.preferencias import ler_preferencias_modulo, salvar_preferencias_modulo

Progresso = Callable[[str, float | None], None]

CHAVE_PREFERENCIAS = "historico_uso"
NOME_PLANILHA = "Historico_de_uso_{data_hora}.xlsx"
FORMATO_DATA_HORA_NOME = "%Y-%m-%d_%H%M%S"
COR_FUNDO_TITULO = "1F4E78"
COR_FONTE_TITULO = "FFFFFF"
COR_ERRO = "FFC7CE"
ABA_RESUMO = "Resumo por mês"
ABA_USUARIOS = "Por usuário"
ABA_HISTORICO = "Histórico"
ABA_AVISOS = "Avisos"


@dataclass
class Uso:
    """Uma linha do log: um uso da Central."""

    momento: datetime
    usuario: str
    computador: str
    versao: str
    modulo: str
    acao: str
    resultado: str

    @property
    def abertura(self) -> bool:
        return self.modulo == log_uso.MODULO_CENTRAL and self.acao == log_uso.ACAO_ABRIR

    @property
    def mes(self) -> str:
        return f"{self.momento:%Y-%m}"


@dataclass
class ResultadoHistorico:
    usos: list[Uso] = field(default_factory=list)
    arquivos: int = 0
    avisos: list[str] = field(default_factory=list)
    caminho_planilha: Path | None = None
    erro: str = ""

    @property
    def usuarios(self) -> int:
        return len({u.usuario for u in self.usos})

    @property
    def aberturas(self) -> int:
        return sum(1 for u in self.usos if u.abertura)

    @property
    def processamentos(self) -> int:
        return sum(1 for u in self.usos if not u.abertura)


def pasta_log_padrao() -> Path:
    """A pasta da rede onde as Centrais gravam o log (a tela mostra sem tocar nela)."""
    return log_uso.pasta_rede()


def ler_preferencias() -> dict[str, str]:
    dados = ler_preferencias_modulo(CHAVE_PREFERENCIAS)
    return {c: v for c, v in dados.items() if c in ("pasta_log", "saida") and isinstance(v, str) and v}


def salvar_preferencias(**valores) -> bool:
    dados = ler_preferencias()
    dados.update({c: str(v) for c, v in valores.items() if v})
    return salvar_preferencias_modulo(CHAVE_PREFERENCIAS, dados)


def _ler_arquivo(arquivo: Path) -> tuple[list[Uso], list[str]]:
    try:
        texto = arquivo.read_text(encoding=log_uso.CODIFICACAO)
    except (OSError, UnicodeDecodeError) as erro:
        return [], [f"{arquivo.name}: não foi possível ler ({erro})."]
    usos, invalidas = [], 0
    for numero, campos in enumerate(csv.reader(io.StringIO(texto), delimiter=log_uso.SEPARADOR), start=1):
        if not campos or tuple(campos) == log_uso.COLUNAS:
            continue
        try:
            data, hora, usuario, computador, versao, modulo, acao, resultado = campos
            usos.append(Uso(datetime.strptime(f"{data} {hora}", "%d/%m/%Y %H:%M:%S"), usuario, computador,
                            versao, modulo, acao, resultado))
        except ValueError:
            invalidas += 1
    avisos = [f"{arquivo.name}: {invalidas} linha(s) fora do formato, ignorada(s)."] if invalidas else []
    return usos, avisos


def ler_usos(pasta: Path) -> ResultadoHistorico:
    """Todos os usos dos arquivos .csv da pasta do log, do mais recente para o mais antigo."""
    resultado = ResultadoHistorico()
    pasta = Path(pasta)
    if not pasta.is_dir():
        resultado.erro = (f"A pasta do log de uso não foi encontrada: {pasta}. Ela é criada na primeira vez que "
                          "alguém usa a Central com a rede no ar.")
        return resultado
    arquivos = sorted(pasta.glob("*.csv"))
    resultado.arquivos = len(arquivos)
    for arquivo in arquivos:
        usos, avisos = _ler_arquivo(arquivo)
        resultado.usos += usos
        resultado.avisos += avisos
    resultado.usos.sort(key=lambda u: u.momento, reverse=True)
    return resultado


def confirmar_pasta_log(pasta: Path) -> tuple[str, str]:
    """Para o cartão da tela (em segundo plano: a pasta fica na rede)."""
    pasta = Path(pasta)
    if not pasta.is_dir():
        return "Pasta não encontrada (ela é criada no primeiro uso com a rede no ar)", "erro"
    quantidade = sum(1 for _ in pasta.glob("*.csv"))
    if not quantidade:
        return "Nenhum arquivo de log ainda", "atencao"
    return f"{quantidade} arquivo(s) de log", "ok"


# ---------------------------------------------------------------------------
# Planilha
# ---------------------------------------------------------------------------

def _aba(livro: Workbook, nome: str, titulos: list[str], larguras: list[int]):
    aba = livro.create_sheet(nome)
    aba.append(titulos)
    for coluna, largura in enumerate(larguras, start=1):
        aba.column_dimensions[get_column_letter(coluna)].width = largura
        celula = aba.cell(row=1, column=coluna)
        celula.font = Font(bold=True, color=COR_FONTE_TITULO)
        celula.fill = PatternFill("solid", fgColor=COR_FUNDO_TITULO)
    aba.freeze_panes = "A2"
    return aba


def _fechar(aba) -> None:
    aba.auto_filter.ref = aba.dimensions


def _resumo_por_mes(livro: Workbook, usos: list[Uso]) -> None:
    aba = _aba(livro, ABA_RESUMO, ["Mês", "Usuário", "Módulo", "Vezes", "Com erro", "Último uso"],
               [10, 24, 28, 9, 10, 18])
    grupos: dict[tuple[str, str, str], list[Uso]] = defaultdict(list)
    for uso in usos:
        grupos[(uso.mes, uso.usuario, uso.modulo if not uso.abertura else "Central (aberturas)")].append(uso)
    for (mes, usuario, modulo), lista in sorted(grupos.items(), key=lambda i: (i[0][0], i[0][1].lower(),
                                                                              i[0][2]))[::-1]:
        erros = sum(1 for u in lista if u.resultado == log_uso.RESULTADO_ERRO)
        aba.append([mes, usuario, modulo, len(lista), erros, max(u.momento for u in lista)])
        aba.cell(row=aba.max_row, column=6).number_format = "dd/mm/yyyy hh:mm"
    _fechar(aba)


def _por_usuario(livro: Workbook, usos: list[Uso]) -> None:
    aba = _aba(livro, ABA_USUARIOS, ["Usuário", "Computador(es)", "Aberturas da Central", "Usos dos módulos",
                                     "Módulos usados", "Primeiro uso", "Último uso"], [24, 22, 12, 12, 60, 18, 18])
    por_usuario: dict[str, list[Uso]] = defaultdict(list)
    for uso in usos:
        por_usuario[uso.usuario].append(uso)
    for usuario, lista in sorted(por_usuario.items(), key=lambda i: max(u.momento for u in i[1]), reverse=True):
        modulos = Counter(u.modulo for u in lista if not u.abertura)
        aba.append([usuario, ", ".join(sorted({u.computador for u in lista})),
                    sum(1 for u in lista if u.abertura), sum(modulos.values()),
                    ", ".join(f"{m} ({n})" for m, n in modulos.most_common()),
                    min(u.momento for u in lista), max(u.momento for u in lista)])
        for coluna in (6, 7):
            aba.cell(row=aba.max_row, column=coluna).number_format = "dd/mm/yyyy hh:mm"
    _fechar(aba)


def _historico(livro: Workbook, usos: list[Uso]) -> None:
    aba = _aba(livro, ABA_HISTORICO, list(log_uso.COLUNAS), [12, 10, 24, 18, 9, 28, 30, 10])
    fundo_erro = PatternFill("solid", fgColor=COR_ERRO)
    for uso in usos:
        aba.append([uso.momento.date(), uso.momento.time(), uso.usuario, uso.computador, uso.versao, uso.modulo,
                    uso.acao, uso.resultado])
        linha = aba.max_row
        aba.cell(row=linha, column=1).number_format = "dd/mm/yyyy"
        aba.cell(row=linha, column=2).number_format = "hh:mm:ss"
        if uso.resultado == log_uso.RESULTADO_ERRO:
            aba.cell(row=linha, column=8).fill = fundo_erro
    _fechar(aba)


def _caminho_livre(caminho: Path) -> Path:
    numero, original = 2, caminho
    while caminho.exists():
        caminho = original.with_name(f"{original.stem}_{numero}{original.suffix}")
        numero += 1
    return caminho


def gerar_planilha(pasta_log: Path, pasta_saida: Path, progresso: Progresso | None = None,
                   agora: datetime | None = None) -> ResultadoHistorico:
    """Lê os logs e grava Historico_de_uso_<data e hora>.xlsx na pasta de saída."""
    if not (pasta_log and pasta_saida):
        raise ValueError("Escolha a pasta do log de uso e a pasta de saída.")
    agora = agora or datetime.now()
    if progresso:
        progresso("Lendo os arquivos do log de uso...", None)
    resultado = ler_usos(Path(pasta_log))
    if resultado.erro:
        return resultado
    if progresso:
        progresso("Montando a planilha...", 0.8)
    livro = Workbook()
    livro.remove(livro.active)
    _resumo_por_mes(livro, resultado.usos)
    _por_usuario(livro, resultado.usos)
    _historico(livro, resultado.usos)
    if resultado.avisos:
        aba = _aba(livro, ABA_AVISOS, ["Aviso"], [100])
        for aviso in resultado.avisos:
            aba.append([aviso])
    caminho = _caminho_livre(Path(pasta_saida) / NOME_PLANILHA.format(data_hora=agora.strftime(FORMATO_DATA_HORA_NOME)))
    try:
        livro.save(caminho)
    except OSError as erro:
        resultado.erro = f"Não foi possível gravar {caminho.name}: {erro}"
        return resultado
    resultado.caminho_planilha = caminho
    if progresso:
        progresso("Planilha gravada.", 1.0)
    return resultado


def resumo_por_usuario(resultado: ResultadoHistorico, maximo: int = 10) -> list[tuple]:
    """Para a tabela da tela: (usuário, usos dos módulos, aberturas, último uso), os mais recentes primeiro."""
    por_usuario: dict[str, list[Uso]] = defaultdict(list)
    for uso in resultado.usos:
        por_usuario[uso.usuario].append(uso)
    linhas = []
    for usuario, lista in sorted(por_usuario.items(), key=lambda i: max(u.momento for u in i[1]), reverse=True):
        linhas.append((usuario, sum(1 for u in lista if not u.abertura), sum(1 for u in lista if u.abertura),
                       f"{max(u.momento for u in lista):%d/%m/%Y %H:%M}"))
    return linhas[:maximo]
