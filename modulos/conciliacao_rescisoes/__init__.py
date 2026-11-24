"""Módulo Conciliação de Rescisões — Fundação Hospital Exemplo.

Veio do Conciliações AMES (pacote rescisoes/, versão 2.14.0). Regras de negócio:
ESPECIFICACAO_RESCISOES.md (nesta pasta).
"""

from central.modulo_base import InfoModulo


def _criar_painel(pai):
    # importado só quando a tela é aberta: a lógica do módulo não depende da interface
    from modulos.conciliacao_rescisoes.painel import PainelModuloRescisoes

    return PainelModuloRescisoes(pai, MODULO)


MODULO = InfoModulo(
    chave="conciliacao_rescisoes",
    nome="Rescisões",
    descricao=("Procura cada pagamento do razão nos eventos da folha (0264, PDF ou Excel) e na lista do mês "
               "anterior, e monta a lista nova de rescisões a pagar."),
    contexto="Conciliações / Passivo circulante",
    icone="porta_saida",
    criar_painel=_criar_painel,
)
