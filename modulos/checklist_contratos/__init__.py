"""Módulo Notas de Contrato — Fundação Hospital Exemplo.

Confere as notas fiscais de contrato do mês (movimento do Tasy) com o Check list da rede, grava uma cópia
preenchida, separa as notas pendentes por responsável e monta os e-mails de cobrança.
Regras de negócio: ESPECIFICACAO_CHECKLIST_CONTRATOS.md (nesta pasta).
"""

from central.modulo_base import InfoModulo


def _criar_painel(pai):
    # importado só quando a tela é aberta: a lógica do módulo não depende da interface
    from modulos.checklist_contratos.painel import PainelContratos

    return PainelContratos(pai, MODULO)


MODULO = InfoModulo(
    chave="checklist_contratos",
    nome="Notas Check-list",
    descricao="Confere as notas de contrato do mês com o Check list, preenche uma cópia e avisa quais "
              "notas faltam.",
    contexto="Escrituração / Notas de contrato",
    icone="prancheta",
    criar_painel=_criar_painel,
)
