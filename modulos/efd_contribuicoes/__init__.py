"""Módulo EFD Contribuições — Fundação Hospital Exemplo.

Gera o SPED EFD-Contribuições (.txt) das notas de serviço emitidas (DANFSe) do mês. Veio da aplicação
Automacao-Notas-Fiscais-EFD. Regras de negócio: ESPECIFICACAO_EFD_CONTRIBUICOES.md (nesta pasta).
"""

from central.modulo_base import InfoModulo


def _criar_painel(pai):
    # importado só quando a tela é aberta: a lógica do módulo não depende da interface
    from modulos.efd_contribuicoes.painel import PainelModuloEfd

    return PainelModuloEfd(pai, MODULO)


MODULO = InfoModulo(
    chave="efd_contribuicoes",
    nome="EFD Contribuições",
    descricao="Gera o SPED EFD-Contribuições do mês com as notas de serviço emitidas (DANFSe), para importar "
              "no programa da Receita.",
    contexto="Fiscal / Notas de serviço emitidas",
    icone="importar",
    criar_painel=_criar_painel,
)
