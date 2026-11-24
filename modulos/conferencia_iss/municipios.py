"""
As cidades (prefeituras) que o programa confere e o que muda de uma para outra.

Os CSVs do Tasy, a comparação e a planilha são os mesmos. O que muda por cidade:
o relatório da prefeitura (formato e colunas), o nome da coluna de valor e o nome
do arquivo gerado. Para incluir uma cidade nova: um leitor novo e uma entrada aqui
(e as colunas da prefeitura em relatorio_excel.COLUNAS_PREFEITURA).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from modulos.conferencia_iss.leitor_prefeitura import LeituraPrefeitura, ler_relatorio_prefeitura
from modulos.conferencia_iss.leitor_prefeitura_av import ler_relatorio_cidade_zeta
from modulos.conferencia_iss.leitor_prefeitura_cp import ler_relatorio_cidade_gama
from modulos.conferencia_iss.leitor_prefeitura_fr import ler_relatorio_cidade_alfa
from modulos.conferencia_iss.leitor_prefeitura_sj import ler_relatorio_cidade_epsilon
from modulos.conferencia_iss.modelos import (
    MUNICIPIO_AV,
    MUNICIPIO_CP,
    MUNICIPIO_FR,
    MUNICIPIO_RB,
    MUNICIPIO_SJ,
)

# O que o relatório da prefeitura traz para identificar a unidade (Resumo e prévia)
IDENTIFICACAO_INSCRICAO = "inscricao"         # inscrição municipal
IDENTIFICACAO_CNPJ = "cnpj"                   # CNPJ da unidade (Cidade Gama)
IDENTIFICACAO_NENHUMA = ""                    # nada (Cidade Alfa)


@dataclass(frozen=True)
class Municipio:
    codigo: str                                   # MUNICIPIO_RB / MUNICIPIO_SJ
    nome: str                                     # "Cidade Beta"
    nome_relatorio: str                           # nome do relatório no site da prefeitura
    rotulo_valor: str                             # coluna de valor comparada com o Tasy
    prefixo_arquivo: str                          # início do nome do .xlsx gerado
    ler_relatorio: Callable[..., LeituraPrefeitura]
    tem_situacao_nf: bool = False                 # relatório traz notas canceladas
    rotulo_arquivo: str = "Relatório da prefeitura (.xls)"   # cartão da tela
    padrao_arquivo: str = "*.xls *.xlsx"                     # filtro da janela "abrir"
    artigo_relatorio: str = "o"                              # "o Relatório" / "a Declaração"
    compara_por_nome: bool = False                # relatório sem CNPJ do prestador (Cidade Gama)
    identificacao: str = IDENTIFICACAO_INSCRICAO  # IDENTIFICACAO_*

    @property
    def titulo(self) -> str:
        return f"Conferência ISS {self.nome}"


MUNICIPIOS: dict[str, Municipio] = {
    MUNICIPIO_RB: Municipio(
        codigo=MUNICIPIO_RB,
        nome="Cidade Beta",
        nome_relatorio="Relatório de Serviços Contratados",
        rotulo_valor="Valor do Doc.",
        prefixo_arquivo="Conferencia_ISS_RB",
        ler_relatorio=ler_relatorio_prefeitura,
    ),
    MUNICIPIO_SJ: Municipio(
        codigo=MUNICIPIO_SJ,
        nome="Cidade Epsilon",
        nome_relatorio="Relatório de Serviços Tomados",
        rotulo_valor="Vlr. Nota",
        prefixo_arquivo="Conferencia_ISS_SJ",
        ler_relatorio=ler_relatorio_cidade_epsilon,
        tem_situacao_nf=True,
    ),
    MUNICIPIO_AV: Municipio(
        codigo=MUNICIPIO_AV,
        nome="Cidade Zeta",
        nome_relatorio="Declaração Completa de Tomador",
        rotulo_valor="Valor do Serviço",
        prefixo_arquivo="Conferencia_ISS_AV",
        ler_relatorio=ler_relatorio_cidade_zeta,
        tem_situacao_nf=True,
        rotulo_arquivo="Relatório da prefeitura (.pdf)",
        padrao_arquivo="*.pdf",
        artigo_relatorio="a",
    ),
    MUNICIPIO_CP: Municipio(
        codigo=MUNICIPIO_CP,
        nome="Cidade Gama",
        nome_relatorio="Relatório de Nota Fiscal",
        rotulo_valor="Valor Serviço",
        prefixo_arquivo="Conferencia_ISS_CP",
        ler_relatorio=ler_relatorio_cidade_gama,
        tem_situacao_nf=True,
        rotulo_arquivo="Relatório da prefeitura (.xlsx)",
        padrao_arquivo="*.xlsx *.xls",
        compara_por_nome=True,
        identificacao=IDENTIFICACAO_CNPJ,
    ),
    MUNICIPIO_FR: Municipio(
        codigo=MUNICIPIO_FR,
        nome="Cidade Alfa",
        nome_relatorio="relatório de notas tomadas",
        rotulo_valor="Valor dos serviços",
        prefixo_arquivo="Conferencia_ISS_FR",
        ler_relatorio=ler_relatorio_cidade_alfa,
        tem_situacao_nf=True,
        rotulo_arquivo="Relatório da prefeitura (.csv)",
        padrao_arquivo="*.csv",
        identificacao=IDENTIFICACAO_NENHUMA,
    ),
}


def municipio(codigo: str) -> Municipio:
    """Cadastro da cidade pelo código; código desconhecido → ValueError."""
    try:
        return MUNICIPIOS[codigo]
    except KeyError:
        raise ValueError(f"Cidade desconhecida: {codigo!r}") from None
