"""Linha de comando da conciliação bancária (ferramenta de manutenção, não entra no .exe).

Veio do conciliar.py do programa original; a conciliação em si agora está em processamento.py.
Rodar na raiz da Central, com o .venv:

Modos disponíveis:
  python -m modulos.bancos.ferramentas --balancete <arquivo .xls ou .xlsx> --extratos <pasta> [--saida <pasta ou .xlsx>]
      Conciliação completa: lê o balancete e os extratos, compara e gera a
      planilha (padrão: pasta "saidas", arquivo conciliacao_bancaria_AAAA-MM.xlsx).
  python -m modulos.bancos.ferramentas --mostrar-texto <arquivo.pdf>
      Mostra o texto que o programa extrai do PDF (para criar leitores novos).
  python -m modulos.bancos.ferramentas --identificar <pasta> [--competencia AAAA-MM]
      Lista cada arquivo da pasta (e subpastas), o modelo reconhecido e os
      saldos extraídos, sem comparar com o balancete.
"""

import argparse
import sys
from datetime import date
from pathlib import Path

from .identificador import identificar_pasta
from .processamento import PASTA_SAIDA_PADRAO, ErroConciliacao, Execucao, executar  # noqa: F401
from .util import (extrair_paginas_pdf, formatar_valor, mensagem_pdf_sem_texto, parece_escaneado,
                   texto_com_paginas)


def main(argumentos: list[str] | None = None) -> int:
    # O terminal do Windows nem sempre aceita acentos; evita erro ao imprimir.
    for saida in (sys.stdout, sys.stderr):
        if hasattr(saida, "reconfigure"):
            saida.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Conciliação bancária: extratos (PDF) x balancete.")
    parser.add_argument("--balancete", metavar="ARQUIVO", type=Path,
                        help="balancete exportado do Tasy (.xls) ou salvo no Excel (.xlsx)")
    parser.add_argument("--extratos", metavar="PASTA", type=Path,
                        help="pasta com os extratos (as subpastas também são lidas)")
    parser.add_argument("--saida", metavar="PASTA", type=Path, default=PASTA_SAIDA_PADRAO,
                        help='pasta (ou arquivo .xlsx) de saída; padrão: "saidas"')
    modo = parser.add_mutually_exclusive_group()
    modo.add_argument("--mostrar-texto", metavar="ARQUIVO", type=Path,
                      help="mostra o texto extraído de um PDF")
    modo.add_argument("--identificar", metavar="PASTA", type=Path,
                      help="lista modelo e saldos de cada arquivo da pasta, sem comparar")
    parser.add_argument("--competencia", metavar="AAAA-MM",
                        help="só com --identificar: mês dos extratos "
                             "(padrão: mês anterior ao atual)")
    args = parser.parse_args(argumentos)

    if args.mostrar_texto:
        return mostrar_texto(args.mostrar_texto)
    if args.identificar:
        try:
            competencia = ler_competencia(args.competencia)
        except ValueError as erro:
            parser.error(str(erro))
        return identificar(args.identificar, competencia)
    if not args.balancete or not args.extratos:
        parser.error("informe --balancete e --extratos (ou use --identificar / --mostrar-texto)")
    try:
        executar(args.balancete, args.extratos, args.saida, progresso=_imprimir)
    except ErroConciliacao as erro:
        print(f"\nERRO: {erro}", file=sys.stderr)
        return 1
    return 0


def _imprimir(texto: str, fracao: float | None) -> None:
    """Andamento da conciliação no terminal (o mesmo texto que o programa original imprimia)."""
    print(texto)


def ler_competencia(texto: str | None) -> date:
    """"2026-08" -> 01/08/2026. Sem texto: mês anterior ao de hoje."""
    if not texto:
        hoje = date.today()
        if hoje.month == 1:
            return date(hoje.year - 1, 12, 1)
        return date(hoje.year, hoje.month - 1, 1)
    try:
        ano, mes = texto.split("-")
        return date(int(ano), int(mes), 1)
    except ValueError:
        raise ValueError(f"competência inválida: {texto!r} (use AAAA-MM, ex.: 2026-08)")


def mostrar_texto(arquivo: Path) -> int:
    if not arquivo.is_file():
        print(f"Arquivo não encontrado: {arquivo}", file=sys.stderr)
        return 1
    paginas = extrair_paginas_pdf(arquivo)
    print(texto_com_paginas(paginas))
    if parece_escaneado(paginas):
        print("\n>>> Este PDF parece ESCANEADO (quase sem texto): "
              + mensagem_pdf_sem_texto(arquivo, len(paginas)))
    return 0


def identificar(pasta: Path, competencia: date) -> int:
    if not pasta.is_dir():
        print(f"Pasta não encontrada: {pasta}", file=sys.stderr)
        return 1
    print(f"Pasta: {pasta}")
    print(f"Competência: {competencia:%m/%Y}\n")

    resultado = identificar_pasta(pasta, competencia)
    for resumo in resultado.arquivos:
        caminho = Path(resumo.subpasta, resumo.arquivo.name)
        print(f"{caminho}")
        print(f"    {resumo.situacao}" + (f" — {resumo.modelo}" if resumo.modelo else ""))
        if resumo.mensagem:
            print(f"    {resumo.mensagem}")
        for saldo in resumo.saldos:
            linha = (f"    {saldo.tipo:<10} conta {saldo.conta_original:<16} "
                     f"total {formatar_valor(saldo.saldo_total):>16}")
            if saldo.saldo_bloqueado:
                linha += f"  bloqueado {formatar_valor(saldo.saldo_bloqueado)}"
            if saldo.fonte_secundaria:
                linha += "  (fonte secundária)"
            print(linha)
            if saldo.observacao:
                print(f"        obs.: {saldo.observacao}")

    contagem: dict[str, int] = {}
    for resumo in resultado.arquivos:
        contagem[resumo.situacao] = contagem.get(resumo.situacao, 0) + 1
    print(f"\n{len(resultado.arquivos)} arquivo(s):")
    for situacao, quantidade in sorted(contagem.items()):
        print(f"    {situacao}: {quantidade}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
