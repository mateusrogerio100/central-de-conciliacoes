"""Módulo Planilha HM — Fundação Hospital Exemplo.

Preenche o relatório mensal de honorários médicos (Planilha HM) que vai para a Controladoria, a partir do
relatório Eventos e do Movimento do lote de Repasse a terceiros do Tasy. Não confundir com o módulo Honorários
Médicos, que confere o balancete. Regras de negócio: ESPECIFICACAO_PLANILHA_HM.md (nesta pasta).
"""

from central.modulo_base import InfoModulo


def _criar_painel(pai):
    # importado só quando a tela é aberta: a lógica do módulo não depende da interface
    from modulos.planilha_hm.painel import PainelModuloPlanilhaHM

    return PainelModuloPlanilhaHM(pai, MODULO)


MODULO = InfoModulo(
    chave="planilha_hm",
    nome="Planilha HM",
    descricao="Preenche a Planilha HM do mês (aba Senior, eventos novos e LOTE REPASSE) a partir do Eventos e do "
              "Movimento do lote de Repasse a terceiros do Tasy, e confere o TOTAL GERAL com o Movimento.",
    contexto="Conciliações / Passivo circulante",
    icone="tabela",
    criar_painel=_criar_painel,
)
