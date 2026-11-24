"""Exemplos fictícios de cada módulo (um arquivo por módulo, com `gerar(pasta) -> list[Exemplo]`).

Os nomes de pessoas e empresas levam "Exemplo" ou "Teste", e os CNPJs e CPFs são inventados, para
nunca coincidirem com alguém real. Os valores são escolhidos para a tela mostrar os casos que o
manual explica (conta que bate, diferença, sem par etc.).

Um `Exemplo` diz como a tela recebe os arquivos: a aba, o nome da tela dentro do painel do módulo
(o `atributo` da Aba) e, para cada cartão, os caminhos. O script de prints e o teste
(testes\\manual) usam essa mesma receita.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# um arquivo por módulo, na ordem do manual (a do menu)
GERADORES = [
    "conferencia_nf",
    "checklist_contratos",
    "notas_pendentes",
    "escrituracao_tomados",
    "conferencia_iss",
    "efd_contribuicoes",
    "bancos",
    "clientes_cmd",
    "conciliacao_estoque",
    "conciliacao_imobilizado",
    "credito_estouro",
    "conciliacao_fornecedores",
    "conciliacao_rescisoes",
    "honorarios_medicos",
    "planilha_hm",
    "subvencoes",
    "convenios",
    "imprimir_pdfs",
    "historico_uso",
]


@dataclass
class Exemplo:
    chave: str                                  # módulo (pasta em modulos\)
    nome: str                                   # nome do print (ex.: "fornecedores")
    aba: str                                    # aba de trabalho onde os arquivos são escolhidos
    atributo: str                               # a tela dessa aba dentro do painel (Aba.atributo)
    arquivos: dict[str, list[Path]] = field(default_factory=dict)   # cartão -> caminhos
    preparar: Callable | None = None            # ajustes na tela antes de processar (ex.: mês)
    # método(s) da tela que geram o resultado, ou uma função que recebe a tela (None = só mostra)
    acao: str | Callable | list | None = "processar"
    pasta_saida: Path | None = None             # onde o resultado é gravado (cartão de pasta, se houver)
    # trocas feitas ANTES de abrir a Central ("modulo.funcao": substituta), para o print não mostrar nada
    # do computador (ex.: a lista de impressoras da rede)
    substituicoes: dict[str, Callable] = field(default_factory=dict)
    # os números grandes do resultado, na ordem da tela (o teste confere: são os que o print do manual mostra)
    numeros: tuple[str, ...] = ()


def gerar_todos(pasta: Path) -> list[Exemplo]:
    """Grava os arquivos de todos os módulos em pasta\\<chave>\\ e devolve as receitas."""
    exemplos = []
    for nome in GERADORES:
        gerador = importlib.import_module(f"manual.ficticios.{nome}")
        exemplos += gerador.gerar(pasta / nome)
    return exemplos


def aplicar_substituicoes(exemplos: list[Exemplo]) -> None:
    """Faz as trocas de todos os exemplos (antes de abrir a Central)."""
    for exemplo in exemplos:
        for alvo, substituta in exemplo.substituicoes.items():
            nome_modulo, nome_funcao = alvo.rsplit(".", 1)
            setattr(importlib.import_module(nome_modulo), nome_funcao, substituta)
