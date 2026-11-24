"""O aviso da aba Avisos, COPIADO de conferencia/modelos.py do Conciliações AMES (só a classe Aviso e os
níveis, sem nenhuma mudança). Um módulo da Central nunca importa outro (ESPECIFICACAO, seção 5.7)."""

from __future__ import annotations

from dataclasses import dataclass

# Níveis de aviso
NIVEL_OK = "OK"
NIVEL_AVISO = "Aviso"
NIVEL_ERRO = "Erro"


@dataclass
class Aviso:
    """
    Um registro da aba Avisos.

    Avisos de arquivo trazem tipo_arquivo, linhas_lidas e unidades;
    avisos de nota/linha trazem só arquivo e mensagem.
    """

    arquivo: str
    mensagem: str                    # "OK" ou a descrição do problema
    nivel: str = NIVEL_AVISO         # NIVEL_OK, NIVEL_AVISO ou NIVEL_ERRO
    tipo_arquivo: str = ""           # TIPO_ARQUIVO_TASY ou TIPO_ARQUIVO_PREFEITURA
    linhas_lidas: int | None = None
    unidades: str = ""

    @property
    def eh_erro(self) -> bool:
        return self.nivel == NIVEL_ERRO
