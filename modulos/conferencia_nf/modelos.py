"""Estruturas de dados do módulo (sem regra de negócio)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum


class ErroLeitura(Exception):
    """Lote ou PDF que não pôde ser lido (estragado, de outro modelo, coluna ou campo faltando).

    A mensagem é escrita para o usuário final.
    """


@dataclass
class FalhaLeitura:
    """Um arquivo que deu erro de leitura: aparece na aba "Erros de leitura" (L5)."""

    arquivo: str
    motivo: str


class Situacao(str, Enum):
    """Situação de cada fato contábil (S5)."""

    OK = "OK"
    DIVERGENTE = "DIVERGENTE"
    CONFERIR = "CONFERIR"
    SEM_PDF = "SEM PDF"
    SEM_NUMERO = "SEM Nº DE NOTA"
    ESTORNO = "ESTORNO"
    RETENCAO = "CONFERIR RETENÇÃO"     # S13: retenção da nota x lançamento (roxo)


@dataclass
class Lancamento:
    """Uma linha do lote do Tasy. Só uma das contas (débito ou crédito) vem preenchida."""

    sequencia: str
    conta_debito: str          # código reduzido; vazio quando o lançamento é a crédito
    conta_credito: str         # código reduzido; vazio quando o lançamento é a débito
    nome_conta: str            # nome da conta preenchida (débito ou crédito)
    classificacao: str         # ex.: 1.01.04.01.0013 (vazio se a coluna não veio)
    valor: Decimal
    complemento: str           # já sem entidades HTML e com os espaços juntados
    centro_custo: str = ""     # código (só na exportação "Movimento contábil"); vazio = sem
    nome_centro_custo: str = ""


@dataclass
class Fato:
    """Os lançamentos de um fato contábil (uma nota, um recibo, uma doação...)."""

    arquivo: str               # nome do .csv do lote
    fato: str                  # número do fato contábil
    data_movimento: str = ""
    lancamentos: list[Lancamento] = field(default_factory=list)
    com_centro_custo: bool = False   # o arquivo traz o centro de custo (S11 pode ser conferida)

    @property
    def total_debito(self) -> Decimal:
        return sum((l.valor for l in self.lancamentos if l.conta_debito), Decimal("0.00"))

    @property
    def total_credito(self) -> Decimal:
        return sum((l.valor for l in self.lancamentos if l.conta_credito), Decimal("0.00"))


@dataclass
class NotaPdf:
    """O que foi lido do PDF de uma nota (DANFE ou DANFSe)."""

    tipo: str                  # "NF-e" (DANFE) ou "NFS-e" (DANFSe)
    numero: str                # sem zeros à esquerda
    emissao: date
    valor: Decimal             # DANFE: valor total da nota; DANFSe: valor do serviço
    emitente_nome: str
    emitente_documento: str    # CNPJ (14) ou CPF (11), só dígitos
    situacao: str              # só na DANFSe (Autorizada, Cancelada...)
    chave: str                 # chave de acesso, só dígitos
    arquivo: str               # caminho relativo à pasta dos PDFs
    usada: bool = False        # já casou com um fato (C4)
    repetida_de: str = ""      # mesma chave já lida neste arquivo (L6)
    # S15: CNPJ/CPF do destinatário (DANFE) ou do tomador (DANFSe), só dígitos; "" = não lido
    destinatario_documento: str = ""
    # X1-X5: de onde vieram os dados. Nota lida do XML: `arquivo` é o .xml; com o PDF da mesma
    # nota na pasta, `arquivo_pdf` é o .pdf e a situação (cancelada...) vem dele.
    xml: bool = False
    arquivo_pdf: str = ""
    diferencas_pdf: list[str] = field(default_factory=list)   # X4: XML x PDF da mesma nota
    # só DANFSe, só para o relatório (S10); None = não lido. "-" na nota = Decimal("0.00")
    regime: str = ""                          # "Não Optante", "Optante - ...", como está na nota
    atividade: str = ""                       # "04.01.01 - Medicina."
    aliquota_iss: Decimal | None = None
    valor_iss: Decimal | None = None
    retencao_iss: str = ""                    # "Não Retido", "Retido", como está na nota
    irrf: Decimal | None = None
    previdencia_retida: Decimal | None = None
    contribuicoes_retidas: Decimal | None = None      # PIS/COFINS/CSLL retidos
    descricao_contribuicoes: str = ""

    @property
    def federais_lidos(self) -> bool:
        return None not in (self.irrf, self.previdencia_retida, self.contribuicoes_retidas)


@dataclass
class NotaSemPdf:
    """Uma nota listada no _sem_pdf.txt (veio sem DANFE no download, seção 3.4)."""

    chave: str
    emitente_documento: str    # CNPJ do emitente, tirado da chave
    numero: str                # número da nota, tirado da chave (sem zeros à esquerda)
    arquivo: str               # o _sem_pdf.txt de onde veio (relativo à pasta)


@dataclass
class Resultado:
    """A conferência de um fato contábil (regras F, C e S)."""

    fato: Fato
    fornecedor: str
    numeros: list[str]
    datas: list[date]
    partidas_ok: bool
    nota: NotaPdf | None = None
    confere_numero: str = ""
    confere_data: str = ""
    confere_valor: str = ""
    confere_destinatario: str = ""     # S15: "OK", "ERRADO" ou "NÃO LIDO" (só fato casado)
    situacao: Situacao | None = None
    observacoes: list[str] = field(default_factory=list)
    sem_centro_custo: list[Lancamento] = field(default_factory=list)    # S11
    centro_custo_cmd: list[Lancamento] = field(default_factory=list)    # S18: 539 - CMD, trocar pelo ativo
    diluicao: list[Lancamento] = field(default_factory=list)            # S19: software, uniforme, enxoval
    reclassificar: list[Lancamento] = field(default_factory=list)       # S20: Fornecedores a reclassificar
    motivo_aviso: str = ""     # S18/S19/S20: o aviso que fez o fato OK virar CONFERIR (motivo no relatório)
    retencoes: list["Retencao"] = field(default_factory=list)            # S13
    aliquotas_erradas: list[str] = field(default_factory=list)           # S16: uma frase por imposto
    contas: list = field(default_factory=list)    # S14: gabarito.AvaliacaoConta de cada débito


@dataclass
class Retencao:
    """S13: um imposto retido na nota de serviço x o crédito na conta dele no fato."""

    imposto: str               # "IRRF", "INSS", "PIS/COFINS/CSLL", "ISS"
    conta: str                 # código reduzido da conta de retenção
    nota: Decimal | None       # None = não lido na nota
    lancado: Decimal

    @property
    def confere(self) -> bool:
        return self.nota is not None and self.nota == self.lancado
