"""Módulo Notas Pendentes de Registro — Fundação Hospital Exemplo.

Lê a pasta da rede com as notas fiscais de serviço que ainda não foram encaminhadas para registro (cada
PDF começa com o número do responsável), junta os PDFs por número e monta um e-mail para cada responsável,
com os PDFs anexados. Os destinatários vêm da aba Emails do Check list de contratos.
Regras de negócio: ESPECIFICACAO_NOTAS_PENDENTES.md (nesta pasta).
"""

from central.modulo_base import InfoModulo


def _criar_painel(pai):
    # importado só quando a tela é aberta: a lógica do módulo não depende da interface
    from modulos.notas_pendentes.painel import PainelNotasPendentes

    return PainelNotasPendentes(pai, MODULO)


MODULO = InfoModulo(
    chave="notas_pendentes",
    nome="Notas Pendentes",
    descricao="Junta as notas pendentes de registro da pasta da rede por responsável e monta um e-mail para "
              "cada um, com os PDFs anexados.",
    contexto="Escrituração / Notas pendentes de registro",
    icone="envelope",
    criar_painel=_criar_painel,
)
