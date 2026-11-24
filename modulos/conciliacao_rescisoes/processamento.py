"""Porta de entrada da Conciliação de Rescisões para a tela (ESPECIFICACAO da Central, seção 4.3).

A regra de negócio é a do Conciliações AMES, copiada sem mudanças (conciliador.py, financeiro.py,
leitores.py, modelos.py, planilha_eventos.py, processar.py, relatorio_excel.py; e a subpasta
fornecedores/ com o que eles usam do módulo Fornecedores; ESPECIFICACAO_RESCISOES.md). Aqui só:
- processar(): chama processar_rescisoes traduzindo o andamento para o formato da Central,
  progresso(texto, fração de 0 a 1) (o código copiado usa ao_progredir(percentual, texto));
- as prévias e os números da tela, reexportados (era o rescisoes/__init__.py de lá);
- a pasta onde salvar, lembrada entre aberturas (na primeira vez, a do Conciliações AMES).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable, Sequence

from central.preferencias import ler_preferencias_modulo, ler_programa_antigo, salvar_preferencias_modulo
from modulos.conciliacao_rescisoes.fornecedores.avisos import NIVEL_ERRO  # noqa: F401  (reexportados para a tela)
from modulos.conciliacao_rescisoes.fornecedores.leitores import nome_curto_unidade  # noqa: F401
from modulos.conciliacao_rescisoes.fornecedores.relatorio_excel import mes_curto  # noqa: F401
from modulos.conciliacao_rescisoes.modelos import ORIGEM_NAO_ENCONTRADO, ResultadoRescisoes  # noqa: F401
from modulos.conciliacao_rescisoes.processar import (  # noqa: F401
    ComposicaoDiferenca,
    NumerosRescisoes,
    PreviaRescisoes,
    composicao_da_diferenca,
    conferir_conjunto,
    numeros_principais,
    previa_controle,
    previa_eventos,
    previa_financeiro,
    previa_razao,
    processar_rescisoes,
)
from modulos.conciliacao_rescisoes.relatorio_excel import ABA_DIFERENTES, ABA_FINANCEIRO, ABA_LISTA  # noqa: F401

CHAVE = "conciliacao_rescisoes"
CHAVE_PROGRAMA_ANTIGO = "pasta_rescisoes"         # no %APPDATA%\ConferenciaISSRB\config.json


def processar(razao: Path, eventos: Sequence[Path], lista_anterior: Path, financeiro: Path | None = None,
              pasta_destino: Path | None = None, progresso: Callable[[str, float | None], None] | None = None,
              agora: datetime | None = None) -> ResultadoRescisoes:
    """Faz a conciliação (nunca levanta exceção). pasta_destino None = pasta do razão."""
    def ao_progredir(percentual: int, texto: str) -> None:
        if progresso is not None:
            progresso(texto, percentual / 100)

    return processar_rescisoes(razao, eventos, lista_anterior, ao_progredir=ao_progredir, agora=agora,
                               pasta_destino=pasta_destino, arquivo_financeiro=financeiro)


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
    """Guarda a pasta escolhida ("" = esquecer: a planilha volta a ir para a pasta do razão)."""
    dados = ler_preferencias_modulo(CHAVE, pasta_preferencias)
    dados["pasta"] = pasta
    return salvar_preferencias_modulo(CHAVE, dados, pasta_preferencias)
