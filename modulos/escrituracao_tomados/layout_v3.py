"""Layout TXT de Importação da Declaração de Serviços Tomados — Versão 3 (Prefeitura de Cidade Alfa).

Fonte: exemplos\\escrituracao_tomados\\layout\\Declaracao_ServicosTomados_V3.0.pdf e seção 3 da
especificação do módulo. O gerador (gerador_txt.py) só lê estas tabelas: um layout novo da
prefeitura = tabelas novas, sem mexer no resto.

Tipos:
- NUMERICO: zeros à esquerda;
- CHAR: espaços à direita (maiúsculas sem acento);
- FINANCEIRO: centavos sem vírgula, zeros à esquerda (R$ 90,00 -> 00000000009000).

`fixo` = valor que é sempre o mesmo neste layout (preenchido pelo gerador).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Tipo(str, Enum):
    NUMERICO = "Numérico"
    CHAR = "Char"
    FINANCEIRO = "Financeiro"


@dataclass(frozen=True)
class Campo:
    nome: str
    inicio: int          # posição inicial (a primeira é 1)
    fim: int             # posição final (inclusive)
    tipo: Tipo
    fixo: str | None = None

    @property
    def tamanho(self) -> int:
        return self.fim - self.inicio + 1


N, C, F = Tipo.NUMERICO, Tipo.CHAR, Tipo.FINANCEIRO

VERSAO = "03"

HEADER = (
    Campo("tipo_registro", 1, 1, N, fixo="0"),
    Campo("tipo_declaracao", 2, 2, C, fixo="T"),          # T = tomador
    Campo("tipo_identificacao", 3, 3, N, fixo="1"),       # 1 = CNPJ do tomador
    Campo("cnpj_tomador", 4, 17, N),
    Campo("mes_referencia", 18, 19, N),
    Campo("ano_referencia", 20, 23, N),
    Campo("data_lancamento", 24, 31, N),                  # DDMMAAAA
    Campo("tipo_referencia", 32, 32, C),                  # N Normal / C Complementar
    Campo("versao_layout", 33, 34, N, fixo=VERSAO),
    Campo("filler", 35, 100, C, fixo=""),
)

DETALHE = (
    Campo("tipo_registro", 1, 1, N, fixo="1"),
    Campo("tipo_identificacao", 2, 2, N),                 # 1 CNPJ / 2 CPF
    Campo("documento_prestador", 3, 16, N),
    Campo("nome_prestador", 17, 116, C),
    Campo("cidade_prestador", 117, 176, C),
    Campo("uf_prestador", 177, 178, C),
    Campo("numero_nf", 179, 186, N),                      # 8 posições (V2)
    Campo("data_emissao", 187, 194, N),                   # DDMMAAAA
    Campo("valor_servicos", 195, 208, F),
    Campo("valor_deducoes", 209, 222, F),
    Campo("aliquota", 223, 227, F),
    Campo("valor_imposto", 228, 241, F),
    Campo("imposto_retido", 242, 242, C),                 # N S Z X (R6)
    Campo("situacao", 243, 243, N, fixo="1"),             # só notas autorizadas entram
    Campo("codigo_atividade", 244, 249, N),
    Campo("cfps", 250, 252, N),                           # 001 / 002 (R5)
    Campo("serie", 253, 254, N, fixo="01"),
    Campo("regime_prestador", 255, 255, C),               # N S M (R7)
    Campo("filler", 256, 350, C, fixo=""),
)

TRAILLER = (
    Campo("tipo_registro", 1, 1, N, fixo="9"),
    Campo("quantidade_detalhes", 2, 5, N),
    Campo("total_servicos", 6, 19, F),
    Campo("total_deducoes", 20, 33, F),
    Campo("total_impostos", 34, 47, F),
    Campo("filler", 48, 100, C, fixo=""),
)

TAMANHO_HEADER = 100
TAMANHO_DETALHE = 350
TAMANHO_TRAILLER = 100
