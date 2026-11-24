"""Módulo Clientes CMD, com duas abas:
- Conciliação de clientes: balancete de clientes x Títulos a Receber (ESPECIFICACAO_CLIENTES_CMD.md);
- Import Contábil: relatórios do mês -> Rel_Geral -> .txt de importação (ESPECIFICACAO_IMPORT_CONTABIL.md,
  código em import_contabil/).
"""

from central.modulo_base import InfoModulo


def _criar_painel(pai):
    # importado só quando a tela é aberta: a lógica do módulo não depende da interface
    from modulos.clientes_cmd.painel import PainelClientesCMD

    return PainelClientesCMD(pai, MODULO)


MODULO = InfoModulo(
    chave="clientes_cmd",
    nome="Clientes CMD",
    descricao="Conciliação de clientes (balancete x Títulos a Receber) e Import Contábil "
              "(relatórios do mês -> arquivo de importação).",
    contexto="Conciliações / Clientes",
    icone="pessoas",
    criar_painel=_criar_painel,
)
