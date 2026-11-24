"""Conciliação bancária completa. É o único módulo que a tela (painel) chama.

Veio da função executar() do conciliar.py do programa original. A única mudança: o andamento,
que antes era impresso com print, agora vai para a função opcional progresso(texto, fracao)
(ESPECIFICACAO da Central, regra 4.3.3). A linha de comando (ferramentas.py) imprime esses
mesmos textos, então a saída no terminal continua igual.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable

from .balancete import ler_balancete
from .comparador import DIFERENCA, OK, LinhaConciliacao, conciliar, contar_por_status
from .identificador import LIDO, MODELO_NAO_RECONHECIDO, ResumoArquivo, identificar_pasta
from .relatorio_excel import gerar_relatorio, nome_padrao  # noqa: F401 (nome_padrao: usado pela tela)

PASTA_SAIDA_PADRAO = Path("saidas")

# Faixa da barra de andamento usada pela leitura dos PDFs (a parte mais demorada).
_INICIO_EXTRATOS = 0.1
_FIM_EXTRATOS = 0.9


class ErroConciliacao(Exception):
    """Problema que impede a conciliação (mensagem pronta para o usuário)."""


@dataclass
class Execucao:
    """O que uma conciliação produziu (usado pela janela)."""

    caminho: Path                               # planilha gerada
    competencia: date
    arquivos: list[ResumoArquivo] = field(default_factory=list)
    linhas: list[LinhaConciliacao] = field(default_factory=list)   # uma por conta (para o resumo da tela)


@dataclass
class ResumoBancos:
    """O que a tela mostra depois de conciliar (as mesmas contagens que o terminal imprime)."""

    contas_por_status: dict[str, int]
    arquivos: int                               # PDFs encontrados
    problemas: list[ResumoArquivo]              # PDFs que não foram lidos (situação diferente de LIDO)
    nao_reconhecidos: list[ResumoArquivo]       # MODELO NÃO RECONHECIDO (botão "Preparar modelo novo")

    @property
    def ok(self) -> int:
        return self.contas_por_status.get(OK, 0)

    @property
    def diferenca(self) -> int:
        return self.contas_por_status.get(DIFERENCA, 0)


def resumir(execucao: Execucao) -> ResumoBancos:
    problemas = [a for a in execucao.arquivos if a.situacao != LIDO]
    return ResumoBancos(
        contas_por_status=contar_por_status(execucao.linhas),
        arquivos=len(execucao.arquivos),
        problemas=problemas,
        nao_reconhecidos=[a for a in problemas if a.situacao == MODELO_NAO_RECONHECIDO],
    )


def executar(balancete: Path, extratos: Path, saida: Path = PASTA_SAIDA_PADRAO,
             progresso: Callable[[str, float | None], None] | None = None) -> Execucao:
    """Conciliação completa. Informa o andamento por `progresso(texto, fracao)` e devolve a
    planilha gerada, a competência e o resumo de cada arquivo lido.
    Levanta ErroConciliacao se não puder seguir."""
    if progresso is None:
        progresso = _sem_progresso
    balancete, extratos = Path(balancete), Path(extratos)
    if not balancete.is_file():
        raise ErroConciliacao(f"balancete não encontrado: {balancete}")
    if not extratos.is_dir():
        raise ErroConciliacao(f"pasta de extratos não encontrada: {extratos}")

    progresso(f"Lendo o balancete: {balancete}", 0.0)
    try:
        dados_balancete = ler_balancete(balancete)
    except Exception as erro:
        raise ErroConciliacao(f"não foi possível ler o balancete: {erro}")
    competencia = dados_balancete.competencia
    if not dados_balancete.contas:
        # Caso real (06/11/2026): o Tasy exportou só o cabeçalho; sem contas, tudo sairia
        # "NÃO ESTÁ NO BALANCETE". Para logo, com o motivo.
        raise ErroConciliacao(
            "o balancete não tem nenhuma conta de caixa e bancos (só o cabeçalho). "
            "Tire o balancete de novo no Tasy, conferindo se as contas aparecem, e rode outra vez.")
    progresso(f"Competência: {competencia:%m/%Y} — {len(dados_balancete.contas)} contas bancárias\n",
              _INICIO_EXTRATOS)

    progresso(f"Lendo os extratos: {extratos}", _INICIO_EXTRATOS)

    def mostrar_andamento(numero, total, arquivo):
        fracao = _INICIO_EXTRATOS + (_FIM_EXTRATOS - _INICIO_EXTRATOS) * (numero - 1) / total
        progresso(f"  [{numero}/{total}] {arquivo.relative_to(extratos)}", fracao)

    identificacao = identificar_pasta(extratos, competencia, progresso=mostrar_andamento)
    linhas = conciliar(dados_balancete.contas, identificacao.saldos)

    try:
        caminho = gerar_relatorio(saida, competencia, linhas, identificacao.arquivos)
    except PermissionError:
        raise ErroConciliacao(
            f"não foi possível gravar a planilha em {saida}. "
            "Se ela estiver aberta no Excel, feche e rode de novo.")

    progresso("\nContas por status:", _FIM_EXTRATOS)
    for status, quantidade in contar_por_status(linhas).items():
        progresso(f"    {status:<24}{quantidade:>5}", _FIM_EXTRATOS)

    problemas = [a for a in identificacao.arquivos if a.situacao != LIDO]
    progresso(f"\nArquivos: {len(identificacao.arquivos)} encontrados, "
              f"{len(identificacao.arquivos) - len(problemas)} lidos", _FIM_EXTRATOS)
    for resumo in problemas:
        progresso(f"    {resumo.situacao}: {Path(resumo.subpasta, resumo.arquivo.name)}", _FIM_EXTRATOS)
        if resumo.mensagem:
            progresso(f"        {resumo.mensagem}", _FIM_EXTRATOS)

    progresso(f"\nPlanilha gerada: {caminho}", 1.0)
    return Execucao(caminho=caminho, competencia=competencia,
                    arquivos=identificacao.arquivos, linhas=linhas)


def _sem_progresso(texto: str, fracao: float | None) -> None:
    """Usado quando ninguém acompanha o andamento."""


def competencia_do_balancete(balancete: Path) -> date:
    """Mês do balancete, para mostrar na tela e montar o nome da planilha.
    Levanta ErroConciliacao (mensagem para o usuário) se não conseguir ler."""
    try:
        return ler_balancete(Path(balancete)).competencia
    except Exception as erro:
        raise ErroConciliacao(f"Não foi possível ler o balancete: {erro}")
