"""Estruturas de dados do módulo (sem regra de negócio)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum


class ErroLeitura(Exception):
    """Movimento, Check list ou arquivo de configuração que não pôde ser lido.

    A mensagem é escrita para o usuário final.
    """


@dataclass
class Aviso:
    """Algo que o usuário precisa saber e que não impede o resto (aba "Avisos" do relatório)."""

    origem: str            # arquivo ou "regra SC linha 3"
    mensagem: str


class Situacao(str, Enum):
    """Situação de cada linha do Check list (R6)."""

    IGNORADO = "IGNORADO"
    MANUAL = "MANUAL"
    CONTA_DIVERGENTE = "CONTA DIVERGENTE"
    OK = "OK"
    NAO_ENCONTRADO = "NÃO ENCONTRADO"


@dataclass
class Lancamento:
    """Uma linha de débito do movimento do Tasy (M1)."""

    estabelecimento: str       # SC ou CMD
    conta: str                 # código reduzido
    nome_conta: str
    valor: Decimal
    lote: str
    lancamento: str
    data: str                  # como veio no .csv (dd/mm/aaaa)
    complemento: str           # sem entidades HTML e com os espaços juntados
    complemento_normalizado: str
    linha_arquivo: int         # linha do .csv (a 1 é a dos títulos)
    arquivo: str = ""          # nome do .csv (a pasta pode ter um arquivo por dia)
    natureza: str = "D"        # D ou C (os créditos só servem para reconhecer estornos, M4)
    documento: str = ""        # o lançamento contábil: "lote/lançamento" ou "fato 6707509"
    centros_custo: tuple = ()  # ((nome, valor), ...) no "Movimento contábil" (rateio)

    @property
    def lote_lancamento(self) -> str:
        return f"{self.lote}/{self.lancamento}" if self.lote else self.documento


@dataclass
class Anulacao:
    """Um lançamento anulado por outro (M4): estorno do Tasy ou nota devolvida."""

    tipo: str                  # "estorno" ou "devolução"
    anulado: list[Lancamento]  # débitos e créditos do lançamento anulado
    anulador: list[Lancamento]  # débitos e créditos do estorno / da devolução


@dataclass
class Movimento:
    """O movimento de um estabelecimento, pronto para a conferência."""

    lancamentos: list[Lancamento] = field(default_factory=list)   # débitos que valem (M1, M4)
    devolucoes: list[Lancamento] = field(default_factory=list)    # débitos de devoluções (R9)
    anulacoes: list[Anulacao] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)


@dataclass
class LinhaChecklist:
    """Uma linha de uma aba do Check list (as colunas que o módulo usa)."""

    numero: int                # linha da planilha
    conta: str                 # como está na planilha ("30091", "30037 / 30081")
    descricao_conta: str
    fornecedor: str
    descricao_despesa: str
    responsavel: str
    valor_mes: object          # célula do mês: número, texto ou None
    valor_mes_anterior: object  # None também quando a coluna não existe


@dataclass
class AbaChecklist:
    """Uma aba de estabelecimento do Check list, com as colunas achadas pelo título (K1)."""

    estabelecimento: str       # SC ou CMD
    nome: str                  # nome da aba
    coluna_mes: int            # 1 = A
    coluna_mes_anterior: int | None
    linhas: list[LinhaChecklist] = field(default_factory=list)

    def linha(self, numero: int) -> LinhaChecklist | None:
        return next((l for l in self.linhas if l.numero == numero), None)


@dataclass
class Contato:
    """Uma pessoa da aba Emails: "Nome (Apelido) <email>" e, ao lado, os códigos que ela recebe."""

    nome: str                  # como está, com o apelido entre parênteses ("" = só o e-mail)
    email: str                 # minúsculo
    apelido: str = ""          # o que estava entre parênteses
    codigos: tuple[str, ...] = ()   # "13", "todos", "todos cmd"
    celula: str = ""           # "A5", para os avisos


@dataclass
class Checklist:
    """O Check list lido: as duas abas de estabelecimento e os contatos."""

    arquivo: str
    ano: int
    mes: int
    abas: dict[str, AbaChecklist]          # SC / CMD -> aba
    contatos: list[Contato] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)


@dataclass
class Regra:
    """Uma linha do regras.csv: como achar a nota de uma linha do Check list (3.3)."""

    aba: str                   # SC ou CMD
    linha: int
    fornecedor_planilha: str
    descricao_planilha: str
    contas: tuple[str, ...]
    busca_fornecedor: re.Pattern
    busca_descricao: re.Pattern | None
    excluir: re.Pattern | None
    selecao: str               # "", "maior" ou "menor"
    tipo: str                  # auto, manual ou ignorar
    obs: str
    linha_arquivo: int         # linha do regras.csv (a 1 é a dos títulos)
    centro_custo: re.Pattern | None = None   # Centro_Custo: só as NFs com um centro de custo que casa


@dataclass
class Configuracao:
    """A pasta de configuração lida (o regras.csv)."""

    regras: list[Regra] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)


@dataclass
class ResultadoLinha:
    """O que a conferência achou para uma linha do Check list (R1 a R8)."""

    regra: Regra
    linha: LinhaChecklist      # já relocalizada (K3)
    situacao: Situacao
    achados: list[Lancamento] = field(default_factory=list)      # na conta certa, depois da seleção (R2, R3)
    divergentes: list[Lancamento] = field(default_factory=list)  # conta divergente de verdade (R5)
    candidatos: list[Lancamento] = field(default_factory=list)   # todos os que casaram com a regra (R1)
    valor: Decimal | None = None          # R4 (também na CONTA DIVERGENTE, quando achou na conta certa)
    gravar: bool = False                  # R6/R7: vai para a cópia do Check list
    celula_preenchida: bool = False       # R7: a célula do mês já tinha algo
    valor_diferente: bool = False         # R7: célula com número diferente do valor achado
    provisao: bool = False                # R7a: célula com "Provisão" e valor achado (mês anterior)
    variacao: Decimal | None = None       # R8, em %
    variacao_destacada: bool = False      # R8: 10% ou mais

    @property
    def lote_lancamento(self) -> str:
        return ", ".join(l.lote_lancamento for l in self.achados)


@dataclass
class NaoVinculado:
    """Lançamento de fornecedor do Check list que nenhuma regra usou (R9)."""

    lancamento: Lancamento
    motivo: str


@dataclass
class Conferencia:
    """Resultado da conferência do mês: uma linha por regra (R10), mais o que sobrou."""

    resultados: list[ResultadoLinha] = field(default_factory=list)
    nao_vinculados: list[NaoVinculado] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)

    def contagem(self) -> dict[Situacao, int]:
        return {s: sum(1 for r in self.resultados if r.situacao == s) for s in Situacao}


@dataclass
class ListaPendente:
    """As notas pendentes de um responsável num estabelecimento (P6)."""

    estabelecimento: str       # SC ou CMD
    chave: str                 # o código ("13") ou, sem código, a chave do nome (P5)
    codigo: str                # "" quando a coluna Responsável não tem número
    responsavel: str           # nome mostrado, sem o número (a forma mais frequente, P5)
    notas: list[LinhaChecklist] = field(default_factory=list)   # na ordem da planilha


@dataclass
class Email:
    """Um e-mail de pendências: um por responsável, com uma tabela por estabelecimento (E1)."""

    chave: str
    codigo: str
    responsavel: str
    listas: list[ListaPendente]            # Hospital Exemplo antes do CMD
    para: list[str]                        # E6
    assunto: str
    html: str
    copia: list[str] = field(default_factory=list)   # E2: os contatos com "Cópia" (Cc)

    @property
    def notas(self) -> int:
        return sum(len(l.notas) for l in self.listas)


@dataclass
class SemEmail:
    """Responsável com notas pendentes cujo e-mail não pôde ser montado (E2): aparece na prévia."""

    responsavel: str
    listas: list[ListaPendente]
    motivo: str


@dataclass
class Pendencias:
    """Resultado das pendências do mês: as listas (P6), os e-mails (E1 a E6) e o que ficou sem e-mail."""

    listas: list[ListaPendente] = field(default_factory=list)
    emails: list[Email] = field(default_factory=list)
    sem_email: list[SemEmail] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)
    # P2: fora dos e-mails por CONTA DIVERGENTE (estabelecimento, linha); só aparecem na prévia
    conta_divergente: list[tuple[str, LinhaChecklist]] = field(default_factory=list)

    @property
    def notas(self) -> int:
        return sum(len(l.notas) for l in self.listas)
