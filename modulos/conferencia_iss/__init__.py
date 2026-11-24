"""Módulo Conferência ISS — Fundação Hospital Exemplo.

Veio do Conciliações AMES (pacote conferencia/, versão 2.14.0): Cidade Beta, Cidade Epsilon, Cidade Zeta,
Cidade Gama e Cidade Alfa, uma aba por prefeitura. Regras de negócio: ESPECIFICACAO_CONFERENCIA_ISS.md
(nesta pasta).
"""

from central.modulo_base import InfoModulo


def _criar_painel(pai):
    # importado só quando a tela é aberta: a lógica do módulo não depende da interface
    from modulos.conferencia_iss.painel import PainelModuloISS

    return PainelModuloISS(pai, MODULO)


MODULO = InfoModulo(
    chave="conferencia_iss",
    nome="Conferência ISS",
    descricao="Compara as notas de serviço do Tasy com o relatório da prefeitura.",
    contexto="Fiscal / ISS",
    icone="arquivos",
    criar_painel=_criar_painel,
)
