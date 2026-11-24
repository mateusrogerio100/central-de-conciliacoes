"""
Regra de negócio da Conciliação Honorários Hospital Exemplo (ESPECIFICACAO seção 20), sem nenhuma tela.

Compara o Saldo Atual de cada médico/clínica no Balancete (2131 – PF e 2132 – PJ) com a soma do HM PF/PJ
Senior (S. Atual) e dos PDFs do SCF – Repasse Sintético (Relatório 6095 – Deslocamento e Remoção/Transporte;
Vl repasse), pareando pelo nome. O Excel sai com uma aba para PF e outra para PJ.

    from modulos.honorarios_medicos.hospital_exemplo import processar_honorarios_hospital_exemplo
    resultado = processar_honorarios_hospital_exemplo([pasta_ou_arquivos...], pasta_destino=pasta)
"""

from modulos.honorarios_medicos.hospital_exemplo.processar import (
    NumerosHospitalExemplo,
    PreviaHospitalExemplo,
    arquivos_da_pasta,
    numeros_principais,
    previa_arquivos,
    processar_honorarios_hospital_exemplo,
)

__all__ = [
    "processar_honorarios_hospital_exemplo",
    "arquivos_da_pasta",
    "numeros_principais",
    "NumerosHospitalExemplo",
    "PreviaHospitalExemplo",
    "previa_arquivos",
]
