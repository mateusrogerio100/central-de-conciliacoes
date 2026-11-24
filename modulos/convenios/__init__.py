"""Módulo Convênios — Fundação Hospital Exemplo.

Lê o Razão das contas de receita de convênios do Tasy e preenche o total do mês de cada convênio numa cópia
da planilha RECEITAS DE CONVÊNIOS. Regras de negócio: ESPECIFICACAO_CONVENIOS.md (nesta pasta).
"""

from central.modulo_base import InfoModulo


def _criar_painel(pai):
    # importado só quando a tela é aberta: a lógica do módulo não depende da interface
    from modulos.convenios.painel import PainelModuloConvenios

    return PainelModuloConvenios(pai, MODULO)


MODULO = InfoModulo(
    chave="convenios",
    nome="Convênios",
    descricao="Preenche o mês de cada convênio na planilha RECEITAS DE CONVÊNIOS a partir do razão das contas "
              "de receita de convênios do Tasy.",
    contexto="Receitas / Receita de convênios",
    icone="grafico",
    criar_painel=_criar_painel,
)
