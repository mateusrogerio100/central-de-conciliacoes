"""Módulo Conciliação Bancária: extratos (PDF) x balancete contábil.

Regras de negócio: ESPECIFICACAO_BANCOS.md (nesta pasta).
Modelo novo de extrato: COMO_ADICIONAR_MODELO.md e o roteiro /novo-modelo do Claude Code.
"""

from central.modulo_base import InfoModulo


def _criar_painel(pai):
    # importado só quando a tela é aberta: a lógica do módulo não depende da interface
    from modulos.bancos.painel import PainelModuloBancos

    return PainelModuloBancos(pai, MODULO)


MODULO = InfoModulo(
    chave="bancos",
    nome="Conciliação Bancária",
    descricao="Compara o saldo de cada conta bancária do balancete com o extrato do banco (PDF) "
              "e gera a planilha com o status de cada conta.",
    contexto="Conciliações / Disponível",
    icone="banco",
    criar_painel=_criar_painel,
)
