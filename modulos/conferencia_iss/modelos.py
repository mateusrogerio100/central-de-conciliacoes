"""
Estruturas de dados da conferência (a "ficha" de cada coisa que o programa manipula).

- NotaTasy: uma nota lida de um CSV do Tasy.
- LinhaPrefeitura: uma linha (nota) do relatório da prefeitura (Cidade Beta, Cidade Epsilon,
  Cidade Zeta, Cidade Gama ou Cidade Alfa).
- ItemResultado: uma linha do relatório final (nota do Tasy, linha da prefeitura ou as duas).
- Aviso: um registro da aba Avisos (um por arquivo lido + avisos de nota/linha).
- Resultado: tudo o que processar() devolve para a interface.

Dinheiro é sempre Decimal (nunca float).
A coluna Observação do Tasy NÃO existe aqui de propósito: ela tem dados sensíveis
(LGPD) e não pode chegar ao relatório.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path


# ---------------------------------------------------------------------
# Situações (textos exatamente como aparecem no relatório)
# ---------------------------------------------------------------------
SITUACAO_CONFERIDA = "Conferida"
SITUACAO_CONFERIDA_AJUSTADO = "Conferida (número ajustado)"
SITUACAO_CONFERIDA_SEM_CPF = "Conferida sem CPF (por número e valor)"
SITUACAO_DIVERGENCIA = "Divergência de valor"
SITUACAO_SOMENTE_TASY = (
    "Notas encontradas somente no Tasy, verificar se precisam escriturar na prefeitura"
)
SITUACAO_SOMENTE_PREFEITURA = "Notas encontradas somente no site da prefeitura"
# Só em Cidade Epsilon e Cidade Zeta, cujos relatórios trazem a situação da nota (Normal / Cancelada)
SITUACAO_CANCELADA_COM_TASY = "Cancelada na prefeitura (lançada no Tasy)"
SITUACAO_CANCELADA_SEM_TASY = "Cancelada na prefeitura (sem nota no Tasy)"
# Só em Cidade Gama, cujo relatório não traz o CNPJ do prestador (casa por número, valor e nome)
SITUACAO_NOME_DIFERENTE = "Número e valor iguais, nome diferente — verificar"


def situacao_escriturada_varias_vezes(vezes: int) -> str:
    """Ex.: 2 → "Notas escrituradas 2 vezes na prefeitura"."""
    return f"Notas escrituradas {vezes} vezes na prefeitura"


# Cidades (prefeituras) atendidas
MUNICIPIO_RB = "RB"           # Cidade Beta
MUNICIPIO_SJ = "SJ"           # Cidade Epsilon
MUNICIPIO_AV = "AV"           # Cidade Zeta
MUNICIPIO_CP = "CP"           # Cidade Gama
MUNICIPIO_FR = "FR"           # Cidade Alfa

# Tipos de arquivo (coluna "Tipo" da aba Avisos)
TIPO_ARQUIVO_TASY = "Tasy"
TIPO_ARQUIVO_PREFEITURA = "Prefeitura"

# Níveis de aviso
NIVEL_OK = "OK"
NIVEL_AVISO = "Aviso"
NIVEL_ERRO = "Erro"


# ---------------------------------------------------------------------
# Dados de entrada
# ---------------------------------------------------------------------
@dataclass
class NotaTasy:
    """Uma nota de um CSV do Tasy, já normalizada (seção 3 da especificação)."""

    arquivo: str                     # nome do CSV de origem
    linha: int                       # nº da linha no CSV (para o usuário achar a nota)
    nota_fiscal: str                 # número como veio no Tasy (exibição)
    numero: str                      # número normalizado (só dígitos, sem zeros à esquerda)
    numero_ajustado: str | None      # ex.: 2026000000122 → "122"; None se não se aplica
    emitente: str
    codigo_emitente: str             # como veio (CNPJ na PJ; código interno do Tasy na PF)
    documento: str                   # só dígitos; vazio nas notas de pessoa física
    tipo_nota: str
    eh_pessoa_fisica: bool
    valor_mercadoria: Decimal        # valor comparado com a prefeitura
    valor_nota: Decimal | None = None  # líquido, só exibição
    data_emissao: str = ""
    data_entrada: str = ""
    estabelecimento: str = ""
    nome_fantasia: str = ""
    situacao: str = ""
    serie: str = ""
    documento_destinatario: str = ""   # CNPJ da unidade (Código destinatário), só dígitos


@dataclass
class LinhaPrefeitura:
    """
    Uma linha do relatório da prefeitura, já normalizada.

    Os campos do começo existem nas duas cidades. Os outros vêm só de uma delas e ficam
    vazios nas outras (ex.: chave_acesso só existe em Cidade Epsilon; os tributos federais, em Cidade Zeta).
    """

    linha: int                       # nº da linha na tabela (1 = primeira após o cabeçalho)
    documento: str                   # só dígitos (CNPJ ou CPF)
    documento_original: str          # como veio (ex.: "00.111.222/0001-33")
    prestador: str
    numero_doc: str                  # como veio (exibição)
    numero: str                      # normalizado
    valor_doc: Decimal | None        # None quando a prefeitura manda vazio
    inscricao_prestador: str = ""
    modelo: str = ""
    item_lc: str = ""
    unidade_economica: str = ""
    aliquota: str = ""
    dia: str = ""
    imp_ret: str = ""
    sn_mei: str = ""
    nat_operacao: str = ""
    valor_tributavel: Decimal | None = None
    valor_imposto: Decimal | None = None
    # Cidade Epsilon (e Cidade Zeta)
    cancelada: bool = False          # situação Cancelada: fica fora da conferência normal
    situacao_nf: str = ""
    competencia: str = ""            # como veio (ex.: "09/2026")
    atividade: str = ""
    data_emissao: str = ""
    incidencia_fora: str = ""
    valor_deducoes: Decimal | None = None
    chave_acesso: str = ""
    # Cidade Zeta (PDF "Declaração Completa de Tomador")
    serie: str = ""
    especie: str = ""
    optante: str = ""
    exigibilidade: str = ""
    regime: str = ""
    incidencia: str = ""                       # cidade de incidência do ISS
    valor_desconto: Decimal | None = None      # Desc. Incond.
    valor_cofins: Decimal | None = None
    valor_csll: Decimal | None = None
    valor_inss: Decimal | None = None
    valor_irrf: Decimal | None = None
    valor_pis: Decimal | None = None
    # Cidade Gama ("Relatório de Nota Fiscal", sem CNPJ do prestador)
    numero_rps: str = ""
    numero_escriturado: str = ""               # "Nº Documento Escriturado" como veio ("2543 / 1")
    numero_alternativo: str = ""               # o mesmo, normalizado ("2543"); vazio se não há
    cnae: str = ""
    data_pagamento: str = ""
    valores_ocultos: bool = False              # Base Cálculo / Valor ISS vieram como "*****"
    # Cidade Alfa (CSV)
    cfps: str = ""


# ---------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------
@dataclass
class ItemResultado:
    """
    Uma linha do relatório final.

    - casamento: nota_tasy e linha_prefeitura preenchidas;
    - somente no Tasy: só nota_tasy;
    - somente na prefeitura: só linha_prefeitura.
    """

    situacao: str
    nota_tasy: NotaTasy | None = None
    linha_prefeitura: LinhaPrefeitura | None = None

    @property
    def diferenca(self) -> Decimal | None:
        """Valor da mercadoria − Valor do Doc.; None se faltar um dos lados."""
        if self.nota_tasy is None or self.linha_prefeitura is None:
            return None
        if self.linha_prefeitura.valor_doc is None:
            return None
        return self.nota_tasy.valor_mercadoria - self.linha_prefeitura.valor_doc

    @property
    def valor_confere(self) -> bool | None:
        """True se a diferença é exatamente zero; None se não há o que comparar."""
        diferenca = self.diferenca
        return None if diferenca is None else diferenca == 0


@dataclass
class Aviso:
    """
    Um registro da aba Avisos.

    Avisos de arquivo trazem tipo_arquivo, linhas_lidas e unidades;
    avisos de nota/linha trazem só arquivo e mensagem.
    """

    arquivo: str
    mensagem: str                    # "OK" ou a descrição do problema
    nivel: str = NIVEL_AVISO         # NIVEL_OK, NIVEL_AVISO ou NIVEL_ERRO
    tipo_arquivo: str = ""           # TIPO_ARQUIVO_TASY ou TIPO_ARQUIVO_PREFEITURA
    linhas_lidas: int | None = None
    unidades: str = ""

    @property
    def eh_erro(self) -> bool:
        return self.nivel == NIVEL_ERRO


@dataclass
class Resultado:
    """Tudo o que processar() devolve para a interface."""

    itens: list[ItemResultado] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)
    notas_tasy: list[NotaTasy] = field(default_factory=list)
    linhas_prefeitura: list[LinhaPrefeitura] = field(default_factory=list)
    municipio: str = MUNICIPIO_RB    # MUNICIPIO_RB, MUNICIPIO_SJ, MUNICIPIO_AV, MUNICIPIO_CP ou MUNICIPIO_FR
    competencia: str = ""            # "2026-09"
    competencia_texto: str = ""      # "setembro/2026"
    inscricao_municipal: str = ""
    documento_tomador: str = ""      # CNPJ da unidade no relatório da prefeitura (Cidade Gama)
    unidades: list[str] = field(default_factory=list)  # nomes fantasia do Tasy
    caminho_relatorio: Path | None = None
    erro: str | None = None          # erro que impediu o relatório (ex.: sem permissão na pasta)
