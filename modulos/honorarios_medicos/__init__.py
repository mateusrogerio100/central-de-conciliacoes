"""Módulo Honorários Médicos — Fundação Hospital Exemplo.

Veio do Conciliações AMES (pacotes honorarios/ e honorarios_hospital_exemplo/, versão 2.14.0), que lá eram dois
itens do menu e aqui são duas abas: "AMEs" (ames/) e "Hospital Exemplo (PF e PJ)" (hospital_exemplo/). Regras de
negócio: ESPECIFICACAO_HONORARIOS.md (nesta pasta).
"""

from central.modulo_base import InfoModulo


def _criar_painel(pai):
    # importado só quando a tela é aberta: a lógica do módulo não depende da interface
    from modulos.honorarios_medicos.painel import PainelModuloHonorarios

    return PainelModuloHonorarios(pai, MODULO)


MODULO = InfoModulo(
    chave="honorarios_medicos",
    nome="Honorários Médicos",
    descricao=("Compara o saldo de cada médico/clínica na conta de Honorários médicos a pagar com os "
               "repasses do Tasy (AMEs) ou com o HM Senior e os PDFs de repasse (Hospital Exemplo, PF e PJ)."),
    contexto="Conciliações / Passivo circulante",
    icone="estetoscopio",
    criar_painel=_criar_painel,
)
