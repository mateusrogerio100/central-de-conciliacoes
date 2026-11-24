"""O "contrato" que todo módulo da Central segue (ESPECIFICACAO, seção 4).

Cada pasta de modulos/ define, no seu __init__.py, uma variável MODULO do tipo InfoModulo.
É só isso que a Central precisa saber de um módulo para colocá-lo no menu.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

# chave: letras minúsculas sem acento, números e "_", começando por letra (ex.: "clientes_cmd")
_PADRAO_CHAVE = re.compile(r"^[a-z][a-z0-9_]*$")


class ErroModulo(Exception):
    """Módulo com informações inválidas ou que não pôde ser carregado.

    A mensagem é escrita para o usuário final.
    """


@dataclass(frozen=True)
class InfoModulo:
    chave: str                              # identificador interno, único (ex.: "subvencoes")
    nome: str                               # texto do menu e título da tela
    descricao: str                          # frase abaixo do título
    contexto: str                           # linha pequena acima do título
    icone: str                              # nome do PNG em central/icones/ (sem extensão)
    criar_painel: Callable[[Any], Any]      # recebe o frame onde desenhar e devolve o painel

    def __post_init__(self):
        if not isinstance(self.chave, str) or not _PADRAO_CHAVE.match(self.chave):
            raise ErroModulo(
                f"Chave de módulo inválida: {self.chave!r}. Use só letras minúsculas sem acento, "
                "números e '_', começando por letra."
            )
        for campo in ("nome", "descricao", "contexto", "icone"):
            valor = getattr(self, campo)
            if not isinstance(valor, str) or not valor.strip():
                raise ErroModulo(f"O módulo '{self.chave}' está sem o campo '{campo}'.")
        if not callable(self.criar_painel):
            raise ErroModulo(f"O módulo '{self.chave}' não informou a função criar_painel.")
