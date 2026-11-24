"""Módulo Subvenções e Projetos — Fundação Hospital Exemplo.

Regras de negócio: ESPECIFICACAO_SUBVENCOES.md (nesta pasta).
"""

from central.modulo_base import InfoModulo


def _criar_painel(pai):
    # importado só quando a tela é aberta: a lógica do módulo não depende da interface
    from modulos.subvencoes.painel import PainelModuloSubvencoes

    return PainelModuloSubvencoes(pai, MODULO)


MODULO = InfoModulo(
    chave="subvencoes",
    nome="Subvenções e Projetos",
    descricao="Preenche o Saldo Patrimônio e o Saldo Contábil das planilhas de Subvenções e Projetos "
              "a partir do balancete e do relatório de patrimônio.",
    contexto="Conciliações / Passivo não circulante",
    icone="moedas",
    criar_painel=_criar_painel,
)
