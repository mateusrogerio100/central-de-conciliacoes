"""Gera os arquivos fictícios de todos os módulos: python -m manual.gerar_exemplos [pasta]

Sem pasta, grava em exemplos_ficticios\\ na raiz do projeto (fora do git: planilhas e PDFs nunca vão
para o git; quem precisar dos arquivos roda este comando de novo).
"""

from __future__ import annotations

import sys
from pathlib import Path

from manual.ficticios import gerar_todos

PASTA_PADRAO = Path(__file__).resolve().parent.parent / "exemplos_ficticios"


def main() -> None:
    pasta = Path(sys.argv[1]) if len(sys.argv) > 1 else PASTA_PADRAO
    exemplos = gerar_todos(pasta)
    print(f"{len(exemplos)} exemplo(s) gravado(s) em {pasta}")
    for exemplo in exemplos:
        print(f"  {exemplo.nome}: {sum(len(c) for c in exemplo.arquivos.values())} arquivo(s)/pasta(s)")


if __name__ == "__main__":
    main()
