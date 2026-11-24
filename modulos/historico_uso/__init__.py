"""Módulo Histórico de uso (ferramenta) — Fundação Hospital Exemplo.

Pedido da chefia (23/10/2026): junta numa planilha quem usou a Central, quando, quais módulos e quantas vezes.
O registro de cada uso é feito pela própria Central (central/log_uso.py); este módulo só lê a pasta do log.
"""

from central.modulo_base import InfoModulo


def _criar_painel(pai):
    # importado só quando a tela é aberta: a lógica do módulo não depende da interface
    from modulos.historico_uso.painel import PainelModuloHistorico

    return PainelModuloHistorico(pai, MODULO)


MODULO = InfoModulo(
    chave="historico_uso",
    nome="Histórico de uso",
    descricao="Junta numa planilha quem usou a Central, quando, quais módulos e quantas vezes.",
    contexto="Ferramentas",
    icone="relogio",
    criar_painel=_criar_painel,
)
