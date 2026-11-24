"""Estruturas de dados do módulo (sem lógica)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum


class ErroLayout(Exception):
    """Valor que não cabe no layout do arquivo (ex.: número da nota com mais de 8 dígitos).

    A mensagem é escrita para o usuário final.
    """


class ErroLeitura(Exception):
    """PDF ou arquivo que não pôde ser lido (modelo diferente, estragado, campo obrigatório vazio).

    A mensagem é escrita para o usuário final.
    """


@dataclass
class FalhaLeitura:
    """Um arquivo que deu erro de leitura: aparece no relatório como ERRO DE LEITURA (R15)."""

    arquivo: str
    motivo: str
    origem: str = ""          # "PDF", "Exportação" ou "Resultado" (preenchido no processamento)


class Destino(str, Enum):
    """O que aconteceu com cada nota (R15)."""

    INCLUIDA = "INCLUÍDA"
    JA_ESCRITURADA = "JÁ ESCRITURADA"
    LANCAR_A_MAO = "LANÇAR À MÃO"
    NAO_INCLUIDA = "NÃO INCLUÍDA"
    DUPLICADA = "DUPLICADA"
    ERRO_LEITURA = "ERRO DE LEITURA"


@dataclass(frozen=True, order=True)
class Competencia:
    """Mês/ano de competência da nota (a prefeitura declara por ela, V11)."""

    ano: int
    mes: int

    @property
    def texto(self) -> str:
        """08/2026"""
        return f"{self.mes:02d}/{self.ano}"

    @property
    def texto_arquivo(self) -> str:
        """08-2026 (para nomes de arquivo)"""
        return f"{self.mes:02d}-{self.ano}"


@dataclass
class Aviso:
    """Ponto a conferir, que não impede a geração (aba "Avisos" do relatório)."""

    tipo: str
    mensagem: str
    arquivo: str = ""
    nota: str = ""


@dataclass
class GrupoArquivo:
    """As notas de um arquivo .txt: um por CNPJ do tomador + competência (R4)."""

    tomador_documento: str
    tomador_nome: str
    competencia: Competencia
    notas: list["NotaTomada"] = field(default_factory=list)


@dataclass
class NotaTomada:
    """Uma nota de serviço tomado, lida de um PDF (DANFSe) ou de uma exportação do site.

    Dados do PRESTADOR, exceto os campos tomador_*. Valores em Decimal com 2 casas;
    alíquota em percentual (2,01% = Decimal("2.01")).
    """

    numero: str                          # só dígitos, como está na nota
    data_emissao: date
    competencia: Competencia | None
    prestador_documento: str             # CNPJ (14) ou CPF (11), só dígitos
    prestador_nome: str
    prestador_cidade: str = ""
    prestador_uf: str = ""
    tomador_documento: str = ""          # vazio = tomador não identificado na nota
    tomador_nome: str = ""
    intermediario_documento: str = ""    # só lido quando o tomador não é identificado
    situacao: str = ""                   # Autorizada, Cancelada, Substituída...
    regime: str = ""                     # N / S / M (R7)
    codigo_atividade: str = ""           # 6 dígitos (04.01.01 -> 040101)
    local_prestacao: str = ""
    municipio_incidencia: str = ""
    tipo_tributacao: str = ""
    valor_servico: Decimal = Decimal("0.00")
    deducoes: Decimal = Decimal("0.00")
    desconto_incondicionado: Decimal = Decimal("0.00")
    aliquota: Decimal = Decimal("0.00")
    valor_iss: Decimal = Decimal("0.00")
    base_calculo: Decimal | None = None  # "BC ISSQN" da nota (None = não informada)
    iss_retido: bool | None = None
    descricao_atividade: str = ""        # texto do código de atividade na DANFSe ("Medicina.")
    # impostos federais retidos (R19); None = não lido (exportação, modelo de SP, campo fora do
    # formato). "-" na nota = Decimal("0.00")
    irrf: Decimal | None = None
    previdencia_retida: Decimal | None = None
    contribuicoes_retidas: Decimal | None = None      # PIS/COFINS/CSLL retidos
    descricao_contribuicoes: str = ""                  # "Código 3" etc., como está na nota
    chave_acesso: str = ""
    origem: str = ""                     # "PDF" ou "Exportação"
    arquivo: str = ""                    # nome do arquivo de onde veio
    # só nas exportações do site (não trazem local da prestação nem separam N de Z, V9)
    cfps_site: str = ""                  # cfps do site: 001 / 002
    retido_site: str = ""                # impretido do site, como veio (SIM / NÃO / M...)
    # modelo de nota que não cabe no arquivo (NFS-e de São Paulo, R18): vai para lançar à mão
    motivo_leitura: str = ""
    # preenchidos pelas regras (regras.py)
    numero_arquivo: str = ""             # número com mais de 8 dígitos: os 8 últimos, que vão no .txt (R8)
    iss_calculado: bool = False          # ISS da nota zerado com alíquota: usado o calculado (R10)
    aliquota_calculada: bool = False     # alíquota em branco com ISS: calculada ISS ÷ serviço (R10)
    codigo_retido: str = ""              # N / S / Z / X (R6)
    cfps: str = ""                       # 001 / 002 (R5)
    destino: Destino | None = None
    motivo: str = ""
    falar_com_fornecedor: bool = False   # Não Optante sem imposto federal retido (R19)

    @property
    def federais_lidos(self) -> bool:
        return None not in (self.irrf, self.previdencia_retida, self.contribuicoes_retidas)

    @property
    def total_federais_retidos(self) -> Decimal | None:
        if not self.federais_lidos:
            return None
        return self.irrf + self.previdencia_retida + self.contribuicoes_retidas
