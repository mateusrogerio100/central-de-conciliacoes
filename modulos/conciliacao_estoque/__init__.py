"""Módulo Conciliação de Estoque — Fundação Hospital Exemplo.

Regras de negócio: ESPECIFICACAO_ESTOQUE.md e MAPA_CONCILIACAO_ESTOQUE.md (na raiz da Central).
"""

from central.modulo_base import InfoModulo


def _criar_painel(pai):
    # importado só quando a tela é aberta: a lógica do módulo não depende da interface
    from modulos.conciliacao_estoque.painel import PainelModuloEstoque

    return PainelModuloEstoque(pai, MODULO)


MODULO = InfoModulo(
    chave="conciliacao_estoque",
    nome="Estoque",
    descricao="Concilia o estoque do balancete com o Mapa do Estoque (saldo anterior e saldo atual) e confere "
              "os grupos do Mapa do Estoque com o PDF Movimento estoque.",
    contexto="Conciliações / Ativo circulante",
    icone="caixa",
    criar_painel=_criar_painel,
)
