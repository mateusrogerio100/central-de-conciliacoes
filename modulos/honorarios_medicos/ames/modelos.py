"""
Estruturas de dados da Conciliação Honorários (ESPECIFICACAO seção 18).

Compara, por unidade (AME ou Hospital Exemplo) e por mês, o Balancete da conta de Honorários médicos
a pagar (no AME, 2132 – 2.01.03.02; Saldo Atual de cada conta de médico/clínica) com o relatório
"SCF – Repasse Sintético" (um repasse por linha, em grupos como Administrativo, Deslocamento e
Produção Médica), ambos baixados do Tasy (.xls). O repasse não tem código contábil: o pareamento
é pelo nome do terceiro, e o saldo da conta é comparado com a SOMA dos repasses BRUTOS do terceiro.

Dinheiro sempre em Decimal. A nota de semelhança dos nomes (0 a 1) é float: não é dinheiro.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from modulos.honorarios_medicos.fornecedores.avisos import Aviso
from modulos.honorarios_medicos.fornecedores.modelos import ContaFornecedor

# Uma conta do balancete (a linha sintética de total ou uma conta de médico/clínica).
ContaHonorario = ContaFornecedor

SITUACAO_OK = "OK"
SITUACAO_DIVERGENTE = "DIVERGENTE"
SITUACAO_SO_BALANCETE = "SÓ NO BALANCETE"
SITUACAO_SO_REPASSE = "SÓ NO REPASSE"

NOMES_RESUMO = {
    SITUACAO_DIVERGENTE: "Divergente",
    SITUACAO_SO_BALANCETE: "Só no Balancete",
    SITUACAO_SO_REPASSE: "Só no Repasse",
}

PAREAMENTO_NOME = "nome"
PAREAMENTO_VALOR = "valor"               # mesmo valor + nome parecido o bastante: confirmar

TIPO_BALANCETE = "Balancete (865)"
TIPO_REPASSE = "Repasse médico (SCF)"


@dataclass
class Repasse:
    """Uma linha do SCF – Repasse Sintético."""

    grupo: str                           # "Produção Médica" (sem o " - Ame Cidade Delta")
    terceiro: str
    numero: str                          # Nr Repasse
    data_referencia: date | None         # Dt Ref
    status: str                          # "F"
    bruto: Decimal                       # Vl repasse
    liquido: Decimal                     # Vl. Líquido

    @property
    def retencao(self) -> Decimal:
        return self.bruto - self.liquido


@dataclass
class Terceiro:
    """Todos os repasses do mesmo terceiro (nome igual sem acento/maiúsculas), em qualquer grupo."""

    nome: str                            # como aparece no primeiro repasse
    repasses: list[Repasse] = field(default_factory=list)

    @property
    def bruto(self) -> Decimal:
        return sum((r.bruto for r in self.repasses), Decimal(0))

    @property
    def liquido(self) -> Decimal:
        return sum((r.liquido for r in self.repasses), Decimal(0))

    def bruto_do_grupo(self, grupo: str) -> Decimal:
        return sum((r.bruto for r in self.repasses if r.grupo == grupo), Decimal(0))


@dataclass
class TotalGrupo:
    """Linha "Total - <grupo>(n)" do repasse, para conferir a leitura."""

    quantidade: int
    bruto: Decimal
    liquido: Decimal


@dataclass
class LeituraBalancete:
    arquivo: str
    unidade: str = ""                    # "AME - Cidade Delta (Fund. Hospital Exemplo ...)"
    mes: date | None = None
    total: ContaHonorario | None = None  # linha sintética (2.01.03.02 no AME)
    contas: list[ContaHonorario] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)
    erro: str | None = None


@dataclass
class LeituraRepasse:
    arquivo: str
    unidade: str = ""                    # "AME - Cidade Delta"
    mes: date | None = None              # mês do Dt Ref
    repasses: list[Repasse] = field(default_factory=list)
    grupos: list[str] = field(default_factory=list)          # na ordem do relatório
    totais_grupo: dict[str, TotalGrupo] = field(default_factory=dict)
    total_geral: TotalGrupo | None = None                    # linha "Total(n)"
    avisos: list[Aviso] = field(default_factory=list)
    erro: str | None = None

    @property
    def total_bruto(self) -> Decimal:
        return sum((r.bruto for r in self.repasses), Decimal(0))

    @property
    def total_liquido(self) -> Decimal:
        return sum((r.liquido for r in self.repasses), Decimal(0))


@dataclass
class LinhaHonorario:
    """Uma linha da aba "Conciliação Completa"."""

    situacao: str
    conta: ContaHonorario | None = None
    terceiros: list[Terceiro] = field(default_factory=list)
    nota: float | None = None
    pareamento: str = ""

    @property
    def saldo_balancete(self) -> Decimal | None:
        return None if self.conta is None else self.conta.saldo_atual

    @property
    def total_repasse(self) -> Decimal | None:
        if not self.terceiros:
            return None
        return sum((t.bruto for t in self.terceiros), Decimal(0))

    @property
    def total_liquido(self) -> Decimal | None:
        if not self.terceiros:
            return None
        return sum((t.liquido for t in self.terceiros), Decimal(0))

    @property
    def diferenca(self) -> Decimal:
        """Balancete − repasse bruto (lado que falta conta como zero)."""
        return (self.saldo_balancete or Decimal(0)) - (self.total_repasse or Decimal(0))

    @property
    def nome_repasse(self) -> str:
        return " + ".join(t.nome for t in self.terceiros)

    def bruto_do_grupo(self, grupo: str) -> Decimal:
        return sum((t.bruto_do_grupo(grupo) for t in self.terceiros), Decimal(0))


@dataclass
class ResultadoHonorarios:
    """Tudo o que processar_honorarios() devolve para a interface."""

    linhas: list[LinhaHonorario] = field(default_factory=list)
    repasses: list[Repasse] = field(default_factory=list)
    grupos: list[str] = field(default_factory=list)
    conta_do_repasse: dict[int, str] = field(default_factory=dict)  # id(Repasse) → código da conta
    notas: list[str] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)
    unidade: str = ""
    mes: date | None = None
    conta_total: ContaHonorario | None = None
    total_balancete: Decimal | None = None
    total_repasse: Decimal | None = None                     # bruto
    total_liquido: Decimal | None = None
    arquivo_balancete: str = ""
    arquivo_repasse: str = ""
    caminho_relatorio: Path | None = None
    erro: str | None = None
