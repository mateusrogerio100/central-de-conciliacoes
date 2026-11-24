"""Porta de entrada da Conciliação Fornecedores para a tela (ESPECIFICACAO da Central, seção 4.3).

A regra de negócio é a do Conciliações AMES, copiada sem mudanças (leitores.py, modelos.py,
pareamento.py, processar.py, relatorio_excel.py; ESPECIFICACAO_FORNECEDORES.md). Aqui só:
- processar(): chama processar_fornecedores traduzindo o andamento para o formato da Central,
  progresso(texto, fração de 0 a 1) (o código copiado usa ao_progredir(percentual, texto));
- as prévias e os números da tela, reexportados do processar.py;
- a pasta onde salvar, lembrada entre aberturas (na primeira vez, a do Conciliações AMES).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

from central.preferencias import ler_preferencias_modulo, ler_programa_antigo, salvar_preferencias_modulo
from modulos.conciliacao_fornecedores.processar import (  # noqa: F401  (reexportados para a tela)
    NumerosFornecedores,
    PreviaFornecedores,
    conferir_par,
    numeros_principais,
    previa_balancete,
    previa_titulos,
    processar_fornecedores,
)
from modulos.conciliacao_fornecedores.avisos import NIVEL_ERRO  # noqa: F401
from modulos.conciliacao_fornecedores.leitores import nome_curto_unidade  # noqa: F401
from modulos.conciliacao_fornecedores.modelos import NOMES_RESUMO, SITUACAO_OK, ResultadoFornecedores  # noqa: F401
from modulos.conciliacao_fornecedores.relatorio_excel import ABA_TITULOS, mes_curto  # noqa: F401

CHAVE = "conciliacao_fornecedores"
CHAVE_PROGRAMA_ANTIGO = "pasta_fornecedores"      # no %APPDATA%\ConferenciaISSRB\config.json


def processar(balancete: Path, titulos: Path, pasta_destino: Path | None = None,
              progresso: Callable[[str, float | None], None] | None = None,
              agora: datetime | None = None) -> ResultadoFornecedores:
    """Faz a conciliação (nunca levanta exceção). pasta_destino None = pasta do balancete."""
    def ao_progredir(percentual: int, texto: str) -> None:
        if progresso is not None:
            progresso(texto, percentual / 100)

    return processar_fornecedores(balancete, titulos, ao_progredir=ao_progredir, agora=agora,
                                  pasta_destino=pasta_destino)


# ---------------------------------------------------------------------------
# Pasta lembrada
# ---------------------------------------------------------------------------


def ler_pasta_lembrada(pasta_preferencias: Path | None = None, arquivo_antigo: Path | None = None) -> str:
    """A última pasta escolhida para salvar. Sem nada guardado na Central, a do Conciliações AMES."""
    dados = ler_preferencias_modulo(CHAVE, pasta_preferencias)
    if "pasta" in dados:
        return dados["pasta"] if isinstance(dados["pasta"], str) else ""
    antiga = ler_programa_antigo(arquivo_antigo).get(CHAVE_PROGRAMA_ANTIGO, "")
    return antiga if isinstance(antiga, str) else ""


def salvar_pasta_lembrada(pasta: str, pasta_preferencias: Path | None = None) -> bool:
    """Guarda a pasta escolhida ("" = esquecer: a planilha volta a ir para a pasta do balancete)."""
    dados = ler_preferencias_modulo(CHAVE, pasta_preferencias)
    dados["pasta"] = pasta
    return salvar_preferencias_modulo(CHAVE, dados, pasta_preferencias)
