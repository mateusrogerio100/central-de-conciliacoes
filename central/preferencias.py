"""Preferências do usuário (ESPECIFICACAO, seção 7).

- Da Central: modo claro/escuro, em %APPDATA%\\CentralConciliacoes\\preferencias.json.
- De cada módulo (pastas e escolhas lembradas): %APPDATA%\\CentralConciliacoes\\<chave>.json,
  um dicionário que só o módulo entende (ler_preferencias_modulo / salvar_preferencias_modulo).
- Do programa antigo Conciliações AMES (%APPDATA%\\ConferenciaISSRB\\config.json): só LIDO, nunca
  alterado (o .exe antigo continua em uso). Serve de valor inicial enquanto a Central ainda não
  guardou nada: o modo, e as pastas e a impressora que cada módulo novo aproveita.

Tudo fica fora do projeto e do git. Arquivo ausente ou estragado nunca é erro: valem os padrões.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

MODO_CLARO = "claro"
MODO_ESCURO = "escuro"
MODOS = (MODO_CLARO, MODO_ESCURO)

NOME_PASTA = "CentralConciliacoes"
NOME_ARQUIVO = "preferencias.json"
PASTA_PROGRAMA_ANTIGO = "ConferenciaISSRB"       # Conciliações AMES (antes de vir para a Central)
ARQUIVO_PROGRAMA_ANTIGO = "config.json"


@dataclass
class Preferencias:
    modo: str = MODO_CLARO


def _pasta_appdata() -> Path:
    return Path(os.environ.get("APPDATA") or str(Path.home()))


def caminho_padrao() -> Path:
    """%APPDATA%\\CentralConciliacoes\\preferencias.json (ou a pasta do usuário, se não houver APPDATA)."""
    return _pasta_appdata() / NOME_PASTA / NOME_ARQUIVO


def caminho_programa_antigo() -> Path:
    """%APPDATA%\\ConferenciaISSRB\\config.json, as preferências do Conciliações AMES."""
    return _pasta_appdata() / PASTA_PROGRAMA_ANTIGO / ARQUIVO_PROGRAMA_ANTIGO


def _ler_json(caminho: Path) -> dict | None:
    """Conteúdo do arquivo, ou None se ele não existir, estiver estragado ou não for um dicionário."""
    try:
        dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return dados if isinstance(dados, dict) else None


def ler_programa_antigo(caminho: Path | None = None) -> dict:
    """As preferências do Conciliações AMES (só leitura). Ausente ou estragado = vazio."""
    return _ler_json(Path(caminho) if caminho else caminho_programa_antigo()) or {}


def ler_preferencias(caminho: Path | None = None, caminho_antigo: Path | None = None) -> Preferencias:
    """Lê as preferências. Qualquer problema no arquivo devolve os valores padrão.

    Só no uso normal (sem `caminho`): se a Central ainda não tem o arquivo, o modo vem do
    Conciliações AMES. Os testes passam `caminho` e nunca leem o arquivo real do programa antigo.
    """
    if caminho is None:
        caminho = caminho_padrao()
        if not caminho.exists():
            dados = ler_programa_antigo(caminho_antigo)
            return Preferencias(modo=dados["modo"]) if dados.get("modo") in MODOS else Preferencias()
    dados = _ler_json(caminho)
    if dados is None:
        return Preferencias()

    preferencias = Preferencias()
    if dados.get("modo") in MODOS:
        preferencias.modo = dados["modo"]
    return preferencias


def salvar_preferencias(preferencias: Preferencias, caminho: Path | None = None) -> bool:
    """Grava as preferências. Devolve False se não conseguir (sem erro: não é algo essencial)."""
    caminho = Path(caminho) if caminho else caminho_padrao()
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(json.dumps(asdict(preferencias), ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        return False
    return True


# ---------------------------------------------------------------------------
# Preferências de cada módulo
# ---------------------------------------------------------------------------


def caminho_modulo(chave: str, pasta: Path | None = None) -> Path:
    """<pasta>\\<chave>.json; sem pasta, %APPDATA%\\CentralConciliacoes\\<chave>.json."""
    return (Path(pasta) if pasta else _pasta_appdata() / NOME_PASTA) / f"{chave}.json"


def ler_preferencias_modulo(chave: str, pasta: Path | None = None) -> dict:
    """O que o módulo guardou (pastas, escolhas). Ausente ou estragado = vazio."""
    return _ler_json(caminho_modulo(chave, pasta)) or {}


def salvar_preferencias_modulo(chave: str, dados: dict, pasta: Path | None = None) -> bool:
    """Grava o dicionário do módulo. Devolve False se não conseguir (sem erro: não é essencial)."""
    caminho = caminho_modulo(chave, pasta)
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    except (OSError, TypeError, ValueError):
        return False
    return True
