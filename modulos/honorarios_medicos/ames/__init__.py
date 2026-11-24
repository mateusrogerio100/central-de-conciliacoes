"""
Regra de negócio da Conciliação Honorários (ESPECIFICACAO seção 18), sem nenhuma tela.

Compara, por unidade (AME ou Hospital Exemplo) e mês, o Balancete da conta de Honorários médicos a pagar
(no AME, 2132) com o relatório SCF – Repasse Sintético do Tasy, pareando os médicos/clínicas pelo nome
e comparando o saldo de cada conta com a soma dos repasses brutos do terceiro.

    from modulos.honorarios_medicos.ames import processar_honorarios
    resultado = processar_honorarios(balancete, repasse, pasta_destino=pasta)
"""

from modulos.honorarios_medicos.ames.processar import (
    NumerosHonorarios,
    PreviaHonorarios,
    conferir_par,
    numeros_principais,
    previa_balancete,
    previa_repasse,
    processar_honorarios,
)

__all__ = [
    "processar_honorarios",
    "numeros_principais",
    "NumerosHonorarios",
    "PreviaHonorarios",
    "previa_balancete",
    "previa_repasse",
    "conferir_par",
]
