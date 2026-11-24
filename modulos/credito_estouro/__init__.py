"""Módulo Crédito Estouro — Fundação Hospital Exemplo.

Concilia a conta Crédito Complemento Salário: os eventos 0241, 0256, 0258, 1204 e 0775 da folha × o razão da conta
× o controle do mês anterior. Regras de negócio: ESPECIFICACAO_CREDITO_ESTOURO.md (nesta pasta).
"""

from central.modulo_base import InfoModulo


def _criar_painel(pai):
    # importado só quando a tela é aberta: a lógica do módulo não depende da interface
    from modulos.credito_estouro.painel import PainelModuloCreditoEstouro

    return PainelModuloCreditoEstouro(pai, MODULO)


MODULO = InfoModulo(
    chave="credito_estouro",
    nome="Crédito Estouro",
    descricao=("Confere, colaborador por colaborador, o crédito estouro da folha (0256, 0258, 0241, 1204) com o "
               "razão da conta Crédito Complemento Salário e carrega o que ficou em aberto para o mês seguinte."),
    contexto="Conciliações / Ativo circulante",
    icone="carteira",
    criar_painel=_criar_painel,
)
