"""Módulo Conciliação do Imobilizado – AME's — Fundação Hospital Exemplo.

Veio do Conciliações AMES (pacote patrimonio/, versão 2.14.0). Regras de negócio:
ESPECIFICACAO_IMOBILIZADO.md (nesta pasta).
"""

from central.modulo_base import InfoModulo


def _criar_painel(pai):
    # importado só quando a tela é aberta: a lógica do módulo não depende da interface
    from modulos.conciliacao_imobilizado.painel import PainelModuloImobilizado

    return PainelModuloImobilizado(pai, MODULO)


MODULO = InfoModulo(
    chave="conciliacao_imobilizado",
    nome="Imobilizado – AME's",
    descricao="Compara o saldo atual de cada conta do patrimônio com o dos balancetes do Tasy.",
    contexto="Conciliações / Ativo não circulante",
    icone="predio",
    criar_painel=_criar_painel,
)
