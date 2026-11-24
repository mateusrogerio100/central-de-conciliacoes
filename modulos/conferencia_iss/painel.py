"""Tela do módulo Conferência ISS: uma aba por prefeitura (telas/cidade.py) e a aba "Instruções de uso"
(INSTRUCOES_DE_USO.md, acrescentada pela Central).

No Conciliações AMES cada cidade era um item do menu; aqui é uma aba. A última cidade aberta é
lembrada (processamento.ler_cidade_lembrada) e o módulo abre nela; as outras abas só são montadas
quando alguém clica nelas.
"""

from __future__ import annotations

from central.painel_abas import Aba, PainelComAbas
from modulos.conferencia_iss import processamento
from modulos.conferencia_iss.telas.cidade import PainelCidadeISS, descricao_da_cidade

# atributo de cada aba (ex.: painel.cidade_epsilon), pelo código da cidade
ATRIBUTOS = {
    processamento.MUNICIPIO_RB: "cidade_beta",
    processamento.MUNICIPIO_SJ: "cidade_epsilon",
    processamento.MUNICIPIO_AV: "cidade_zeta",
    processamento.MUNICIPIO_CP: "cidade_gama",
    processamento.MUNICIPIO_FR: "cidade_alfa",
}


class PainelModuloISS(PainelComAbas):
    def __init__(self, pai, info):
        self._codigo_da_aba = {cidade.nome: codigo for codigo, cidade in processamento.MUNICIPIOS.items()}
        self._lembrar = False                   # não grava a aba mostrada ao abrir
        abas = [
            Aba(cidade.nome, lambda p, cidade=cidade: PainelCidadeISS(p, info, cidade),
                descricao_da_cidade(cidade), ATRIBUTOS[codigo])
            for codigo, cidade in processamento.MUNICIPIOS.items()
        ]
        inicial = processamento.MUNICIPIOS[processamento.ler_cidade_lembrada()].nome
        super().__init__(pai, info, abas, aba_inicial=inicial)
        self._lembrar = True

    def mostrar_aba(self, nome: str) -> None:
        super().mostrar_aba(nome)
        if self._lembrar and nome in self._codigo_da_aba:
            processamento.salvar_cidade_lembrada(self._codigo_da_aba[nome])
