"""Módulo Imprimir PDFs (ferramenta) — Fundação Hospital Exemplo.

Veio do Conciliações AMES (pacote impressao/, versão 2.14.0). Não é conciliação: escolhe os PDFs, mostra
o total de folhas e manda todos para a impressora numa impressão só. Regras: ESPECIFICACAO_IMPRIMIR_PDFS.md
(nesta pasta).
"""

from central.modulo_base import InfoModulo


def _criar_painel(pai):
    # importado só quando a tela é aberta: a lógica do módulo não depende da interface
    from modulos.imprimir_pdfs.painel import PainelModuloImprimirPdfs

    return PainelModuloImprimirPdfs(pai, MODULO)


MODULO = InfoModulo(
    chave="imprimir_pdfs",
    nome="Imprimir PDFs",
    descricao=("Escolha os PDFs, confira quantas folhas vão ser usadas e mande todos para a impressora de uma "
               "vez, um por folha."),
    contexto="Ferramentas",
    icone="impressora",
    criar_painel=_criar_painel,
)
