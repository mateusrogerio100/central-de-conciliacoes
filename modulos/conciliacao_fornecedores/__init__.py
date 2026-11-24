"""Módulo Conciliação Fornecedores — Fundação Hospital Exemplo.

Veio do Conciliações AMES (pacote fornecedores/, versão 2.14.0). Regras de negócio:
ESPECIFICACAO_FORNECEDORES.md (nesta pasta).
"""

from central.modulo_base import InfoModulo


def _criar_painel(pai):
    # importado só quando a tela é aberta: a lógica do módulo não depende da interface
    from modulos.conciliacao_fornecedores.painel import PainelModuloFornecedores

    return PainelModuloFornecedores(pai, MODULO)


MODULO = InfoModulo(
    chave="conciliacao_fornecedores",
    nome="Fornecedores",
    descricao="Compara o saldo de cada fornecedor no balancete (conta 2111) com o relatório de títulos a "
              "pagar do Tasy.",
    contexto="Conciliações / Passivo circulante",
    icone="caminhao",
    criar_painel=_criar_painel,
)
