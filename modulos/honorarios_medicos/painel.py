"""Tela do módulo Honorários Médicos: abas "AMEs" (telas/ames.py) e "Hospital Exemplo (PF e PJ)"
(telas/hospital_exemplo.py), mais a aba "Instruções de uso" (INSTRUCOES_DE_USO.md, acrescentada pela Central).

No Conciliações AMES eram dois itens do menu ("Honorários" e "Honorários Hospital Exemplo"); aqui são abas. A
última aba aberta é lembrada (processamento.ler_aba_lembrada) e o módulo abre nela; a outra só é montada
quando alguém clica nela.
"""

from __future__ import annotations

from central.painel_abas import Aba, PainelComAbas
from modulos.honorarios_medicos import processamento
from modulos.honorarios_medicos.telas.ames import PainelHonorariosAmes
from modulos.honorarios_medicos.telas.hospital_exemplo import PainelHonorariosHospitalExemplo

ABA_AMES = "AMEs"
ABA_HOSPITAL_EXEMPLO = "Hospital Exemplo (PF e PJ)"
# nome da aba na tela → como ela fica guardada nas preferências
CODIGO_DA_ABA = {ABA_AMES: processamento.ABA_AMES, ABA_HOSPITAL_EXEMPLO: processamento.ABA_HOSPITAL_EXEMPLO}


class PainelModuloHonorarios(PainelComAbas):
    def __init__(self, pai, info):
        self._lembrar = False                   # não grava a aba mostrada ao abrir
        abas = [
            Aba(ABA_AMES, lambda p: PainelHonorariosAmes(p, info),
                "Compara o saldo de cada médico/clínica no balancete (Honorários médicos a pagar) com a soma "
                "dos repasses brutos do relatório de repasse do Tasy.", "ames"),
            Aba(ABA_HOSPITAL_EXEMPLO, lambda p: PainelHonorariosHospitalExemplo(p, info),
                "Compara o saldo de cada médico/clínica no balancete (2131 – PF e 2132 – PJ) com a soma do HM "
                "Senior e dos PDFs de Remoção/Deslocamento (6095) e Pagamento particular (6203).", "hospital_exemplo"),
        ]
        inicial = ABA_HOSPITAL_EXEMPLO if processamento.ler_aba_lembrada() == processamento.ABA_HOSPITAL_EXEMPLO else ABA_AMES
        super().__init__(pai, info, abas, aba_inicial=inicial)
        self._lembrar = True

    def mostrar_aba(self, nome: str) -> None:
        super().mostrar_aba(nome)
        if self._lembrar and nome in CODIGO_DA_ABA:
            processamento.salvar_aba_lembrada(CODIGO_DA_ABA[nome])
