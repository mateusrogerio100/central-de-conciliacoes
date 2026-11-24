"""Porta de entrada de Honorários Médicos para a tela (ESPECIFICACAO da Central, seção 4.3).

A regra de negócio é a do Conciliações AMES, copiada sem mudanças: ames/ (era honorarios/, a aba "AMEs"),
hospital_exemplo/ (era honorarios_hospital_exemplo/, a aba "Hospital Exemplo (PF e PJ)"; usa o código de ames/ direto, por
ser o mesmo módulo) e a subpasta fornecedores/ com o que os dois usam do módulo Fornecedores
(ESPECIFICACAO_HONORARIOS.md). Aqui só:
- processar_ames() e processar_hospital_exemplo(): chamam o código copiado traduzindo o andamento para o formato
  da Central, progresso(texto, fração de 0 a 1) (o código copiado usa ao_progredir(percentual, texto));
- as prévias e os números da tela, reexportados (eram os __init__.py de lá); os nomes que existem nas
  duas partes ganham o sufixo _ames ou _hospital_exemplo;
- a pasta onde salvar, uma para cada aba, e a última aba aberta, lembradas entre aberturas (na primeira
  vez, as do Conciliações AMES).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable, Sequence

from central.preferencias import ler_preferencias_modulo, ler_programa_antigo, salvar_preferencias_modulo
from modulos.honorarios_medicos.ames.modelos import NOMES_RESUMO, ResultadoHonorarios  # noqa: F401
from modulos.honorarios_medicos.ames.modelos import SITUACAO_OK as SITUACAO_OK_AMES  # noqa: F401
from modulos.honorarios_medicos.ames.processar import (  # noqa: F401  (reexportados para a tela)
    NumerosHonorarios,
    PreviaHonorarios,
    conferir_par,
    previa_balancete,
    previa_repasse,
    processar_honorarios,
)
from modulos.honorarios_medicos.ames.processar import numeros_principais as numeros_ames  # noqa: F401
from modulos.honorarios_medicos.fornecedores.avisos import NIVEL_ERRO  # noqa: F401
from modulos.honorarios_medicos.fornecedores.leitores import nome_curto_unidade  # noqa: F401
from modulos.honorarios_medicos.fornecedores.relatorio_excel import mes_curto  # noqa: F401
from modulos.honorarios_medicos.hospital_exemplo.modelos import (  # noqa: F401
    SITUACAO_DIVERGENTE as SITUACAO_DIVERGENTE_HOSPITAL_EXEMPLO,
    SITUACAO_OK as SITUACAO_OK_HOSPITAL_EXEMPLO,
    SITUACAO_SO_BALANCETE as SITUACAO_SO_BALANCETE_HOSPITAL_EXEMPLO,
    SITUACAO_SO_SENIOR,
    ResultadoHospitalExemplo,
)
from modulos.honorarios_medicos.hospital_exemplo.processar import (  # noqa: F401
    NumerosHospitalExemplo,
    PreviaHospitalExemplo,
    arquivos_da_pasta,
    previa_arquivos,
    processar_honorarios_hospital_exemplo,
)
from modulos.honorarios_medicos.hospital_exemplo.processar import numeros_principais as numeros_hospital_exemplo  # noqa: F401

CHAVE = "honorarios_medicos"
ABA_AMES = "ames"
ABA_HOSPITAL_EXEMPLO = "hospital_exemplo"
# no %APPDATA%\ConferenciaISSRB\config.json do Conciliações AMES
CHAVES_PROGRAMA_ANTIGO = {ABA_AMES: "pasta_honorarios", ABA_HOSPITAL_EXEMPLO: "pasta_honorarios_hospital_exemplo"}
ITEM_ANTIGO_HOSPITAL_EXEMPLO = "HONSC"      # "cidade" (último item aberto) quando foi o Honorários Hospital Exemplo


def _ao_progredir(progresso: Callable[[str, float | None], None] | None):
    def ao_progredir(percentual: int, texto: str) -> None:
        if progresso is not None:
            progresso(texto, percentual / 100)

    return ao_progredir


def processar_ames(balancete: Path, repasse: Path, pasta_destino: Path | None = None,
                   progresso: Callable[[str, float | None], None] | None = None,
                   agora: datetime | None = None) -> ResultadoHonorarios:
    """Conciliação de um AME (nunca levanta exceção). pasta_destino None = pasta do balancete."""
    return processar_honorarios(balancete, repasse, ao_progredir=_ao_progredir(progresso), agora=agora,
                                pasta_destino=pasta_destino)


def processar_hospital_exemplo(arquivos: Sequence[Path], pasta_destino: Path | None = None,
                         progresso: Callable[[str, float | None], None] | None = None) -> ResultadoHospitalExemplo:
    """Conciliação da Hospital Exemplo, PF e PJ (nunca levanta exceção). pasta_destino None = pasta do balancete."""
    return processar_honorarios_hospital_exemplo(list(arquivos), ao_progredir=_ao_progredir(progresso),
                                           pasta_destino=pasta_destino)


# ---------------------------------------------------------------------------
# Preferências: pasta de cada aba e a última aba aberta
# ---------------------------------------------------------------------------


def ler_pasta_lembrada(aba: str, pasta_preferencias: Path | None = None, arquivo_antigo: Path | None = None) -> str:
    """A última pasta escolhida para salvar na aba (ABA_AMES ou ABA_HOSPITAL_EXEMPLO). Sem nada guardado na
    Central, a do Conciliações AMES."""
    dados = ler_preferencias_modulo(CHAVE, pasta_preferencias)
    chave = f"pasta_{aba}"
    if chave in dados:
        return dados[chave] if isinstance(dados[chave], str) else ""
    antiga = ler_programa_antigo(arquivo_antigo).get(CHAVES_PROGRAMA_ANTIGO[aba], "")
    return antiga if isinstance(antiga, str) else ""


def salvar_pasta_lembrada(aba: str, pasta: str, pasta_preferencias: Path | None = None) -> bool:
    """Guarda a pasta escolhida ("" = esquecer: a planilha volta a ir para a pasta do balancete)."""
    dados = ler_preferencias_modulo(CHAVE, pasta_preferencias)
    dados[f"pasta_{aba}"] = pasta
    return salvar_preferencias_modulo(CHAVE, dados, pasta_preferencias)


def ler_aba_lembrada(pasta_preferencias: Path | None = None, arquivo_antigo: Path | None = None) -> str:
    """A última aba aberta (ABA_AMES ou ABA_HOSPITAL_EXEMPLO). Sem nada guardado na Central: Hospital Exemplo se foi o
    último item aberto no Conciliações AMES; senão, AMEs."""
    dados = ler_preferencias_modulo(CHAVE, pasta_preferencias)
    if dados.get("aba") in (ABA_AMES, ABA_HOSPITAL_EXEMPLO):
        return dados["aba"]
    if "aba" not in dados and ler_programa_antigo(arquivo_antigo).get("cidade") == ITEM_ANTIGO_HOSPITAL_EXEMPLO:
        return ABA_HOSPITAL_EXEMPLO
    return ABA_AMES


def salvar_aba_lembrada(aba: str, pasta_preferencias: Path | None = None) -> bool:
    dados = ler_preferencias_modulo(CHAVE, pasta_preferencias)
    dados["aba"] = aba
    return salvar_preferencias_modulo(CHAVE, dados, pasta_preferencias)
