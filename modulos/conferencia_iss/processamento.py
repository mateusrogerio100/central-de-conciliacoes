"""Porta de entrada da Conferência ISS para a tela (ESPECIFICACAO da Central, seção 4.3).

A regra de negócio é a do Conciliações AMES, copiada sem mudanças (comparador.py, leitor_*.py,
modelos.py, municipios.py, normalizar.py, processar.py, relatorio_excel.py, resumo.py;
ESPECIFICACAO_CONFERENCIA_ISS.md). Aqui só:
- processar(): chama o processar() copiado traduzindo o andamento para o formato da Central,
  progresso(texto, fração de 0 a 1) (o código copiado usa ao_progredir(percentual, texto));
- as cidades, as prévias e os números da tela, reexportados (era o conferencia/__init__.py de lá);
- a última cidade aberta, lembrada entre aberturas (na primeira vez, a do Conciliações AMES).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

from central.preferencias import ler_preferencias_modulo, ler_programa_antigo, salvar_preferencias_modulo
from modulos.conferencia_iss import processar as _processar
from modulos.conferencia_iss.modelos import (  # noqa: F401  (reexportados para a tela)
    MUNICIPIO_AV,
    MUNICIPIO_CP,
    MUNICIPIO_FR,
    MUNICIPIO_RB,
    MUNICIPIO_SJ,
    NIVEL_ERRO,
    SITUACAO_CANCELADA_COM_TASY,
    SITUACAO_CANCELADA_SEM_TASY,
    SITUACAO_CONFERIDA,
    SITUACAO_CONFERIDA_AJUSTADO,
    SITUACAO_CONFERIDA_SEM_CPF,
    SITUACAO_DIVERGENCIA,
    SITUACAO_NOME_DIFERENTE,
    SITUACAO_SOMENTE_PREFEITURA,
    SITUACAO_SOMENTE_TASY,
    Resultado,
)
from modulos.conferencia_iss.municipios import (  # noqa: F401
    IDENTIFICACAO_CNPJ,
    IDENTIFICACAO_INSCRICAO,
    MUNICIPIOS,
    Municipio,
    municipio,
)
from modulos.conferencia_iss.processar import (  # noqa: F401
    PreviaPrefeitura,
    PreviaTasy,
    previa_prefeitura,
    previa_tasy,
)
from modulos.conferencia_iss.resumo import (  # noqa: F401
    conferencia_nada_sumiu,
    linhas_do_resumo,
    numeros_principais,
)

CHAVE = "conferencia_iss"
CHAVE_PROGRAMA_ANTIGO = "cidade"        # no %APPDATA%\ConferenciaISSRB\config.json (último item aberto)


def processar(arquivos_tasy: list[Path], arquivo_prefeitura: Path, municipio: str = MUNICIPIO_RB,
              progresso: Callable[[str, float | None], None] | None = None,
              agora: datetime | None = None) -> Resultado:
    """Faz a conferência da cidade (nunca levanta exceção). A planilha vai para a pasta do relatório
    da prefeitura."""
    def ao_progredir(percentual: int, texto: str) -> None:
        if progresso is not None:
            progresso(texto, percentual / 100)

    return _processar.processar(arquivos_tasy, arquivo_prefeitura, ao_progredir=ao_progredir,
                                agora=agora, municipio=municipio)


# ---------------------------------------------------------------------------
# Última cidade aberta
# ---------------------------------------------------------------------------


def ler_cidade_lembrada(pasta_preferencias: Path | None = None, arquivo_antigo: Path | None = None) -> str:
    """O código da última cidade aberta (MUNICIPIO_*). Sem nada guardado na Central, a do Conciliações
    AMES, se lá o último item aberto foi uma cidade; senão (ou código desconhecido), Cidade Beta."""
    dados = ler_preferencias_modulo(CHAVE, pasta_preferencias)
    if "cidade" in dados:
        cidade = dados["cidade"]
    else:
        cidade = ler_programa_antigo(arquivo_antigo).get(CHAVE_PROGRAMA_ANTIGO, "")
    return cidade if isinstance(cidade, str) and cidade in MUNICIPIOS else MUNICIPIO_RB


def salvar_cidade_lembrada(cidade: str, pasta_preferencias: Path | None = None) -> bool:
    dados = ler_preferencias_modulo(CHAVE, pasta_preferencias)
    dados["cidade"] = cidade
    return salvar_preferencias_modulo(CHAVE, dados, pasta_preferencias)
