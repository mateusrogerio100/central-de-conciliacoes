"""Módulo Conferência de Notas Fiscais — Fundação Hospital Exemplo.

Confere o lote de Notas Fiscais importado no Tasy contra os PDFs das notas (DANFE e DANFSe):
número, data de emissão, valor e partidas x contrapartidas de cada fato contábil.
Regras de negócio: ESPECIFICACAO_CONFERENCIA_NF.md (nesta pasta).
"""

from central.modulo_base import InfoModulo


def _criar_painel(pai):
    # importado só quando a tela é aberta: a lógica do módulo não depende da interface
    from modulos.conferencia_nf.painel import PainelConferenciaNF

    return PainelConferenciaNF(pai, MODULO)


MODULO = InfoModulo(
    chave="conferencia_nf",
    nome="Conferência de NF",
    descricao="Confere o lote de Notas Fiscais do Tasy com os PDFs das notas: número, data, valor "
              "e partidas.",
    contexto="Escrituração / Notas fiscais",
    icone="check",
    criar_painel=_criar_painel,
)
