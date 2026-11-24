"""Módulo Escrituração de Serviços Tomados — Fundação Hospital Exemplo.

Gera o .txt de importação da Declaração de Serviços Tomados do site da Prefeitura de Cidade Alfa
(Layout V3). Regras de negócio: ESPECIFICACAO_ESCRITURACAO_TOMADOS.md (nesta pasta).
"""

from central.modulo_base import InfoModulo


def _criar_painel(pai):
    # importado só quando a tela é aberta: a lógica do módulo não depende da interface
    from modulos.escrituracao_tomados.painel import PainelEscrituracaoTomados

    return PainelEscrituracaoTomados(pai, MODULO)


MODULO = InfoModulo(
    chave="escrituracao_tomados",
    nome="Serviços Tomados",
    descricao="Gera o arquivo de importação da Declaração de Serviços Tomados para o site da "
              "Prefeitura de Cidade Alfa.",
    contexto="Escrituração / ISS",
    icone="arquivo",
    criar_painel=_criar_painel,
)
