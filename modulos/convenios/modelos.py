"""Estruturas de dados do módulo Convênios."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

ZERO = Decimal("0.00")


class ErroLeitura(Exception):
    """Problema que impede ler uma entrada; a mensagem é para o usuário."""


@dataclass
class Aviso:
    """Algo que o usuário precisa saber e que não impede o resto (aba "Avisos" do relatório)."""

    origem: str            # arquivo e linha ("Razao Convenios 092026.xlsx linha 40")
    mensagem: str
    erro: bool = False     # True = a conferência não fecha (vermelho); False = atenção


# ---------------------------------------------------------------------------
# Razão (3.1)
# ---------------------------------------------------------------------------

@dataclass
class Lancamento:
    """Um lançamento do razão: valor = crédito − débito (débito diminui o convênio)."""

    conta: str             # código reduzido ("40075")
    data: date
    historico: str
    lote: str
    debito: Decimal
    credito: Decimal
    linha: int             # linha da planilha do razão

    @property
    def valor(self) -> Decimal:
        return self.credito - self.debito


@dataclass
class ContaRazao:
    """Uma conta do razão, com os lançamentos e a linha "Total - <conta>" (para conferir a leitura)."""

    codigo: str
    classificacao: str
    nome: str
    lancamentos: list[Lancamento] = field(default_factory=list)
    total_debito: Decimal | None = None      # da linha "Total"; None = linha não encontrada
    total_credito: Decimal | None = None

    @property
    def soma_debitos(self) -> Decimal:
        return sum((l.debito for l in self.lancamentos), ZERO)

    @property
    def soma_creditos(self) -> Decimal:
        return sum((l.credito for l in self.lancamentos), ZERO)

    @property
    def total(self) -> Decimal:
        return self.soma_creditos - self.soma_debitos


@dataclass
class Razao:
    arquivo: str
    ano: int | None = None
    mes: int | None = None
    contas: list[ContaRazao] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)

    @property
    def lancamentos(self) -> list[Lancamento]:
        return [l for c in self.contas for l in c.lancamentos]

    @property
    def total(self) -> Decimal:
        """Saldo Contábil do mês (P3): créditos − débitos de todas as contas."""
        return sum((c.total for c in self.contas), ZERO)


# ---------------------------------------------------------------------------
# Planilha de receitas (3.2)
# ---------------------------------------------------------------------------

@dataclass
class LinhaConvenio:
    nome: str              # como está na planilha, sem os espaços das pontas
    linha: int


@dataclass
class Planilha:
    arquivo: str
    aba: str
    ano: int
    linha_titulos: int
    coluna_nome: int
    colunas_mes: dict[int, int]              # mês (1 a 12) -> coluna
    coluna_acumulado: int | None
    convenios: list[LinhaConvenio]
    linha_total: int
    linha_saldo: int | None
    linha_diferenca: int | None
    valores: dict[tuple[int, int], object] = field(default_factory=dict)   # (linha, mês) -> o que está na célula
    avisos: list[Aviso] = field(default_factory=list)

    def preenchidas_no_mes(self, mes: int) -> list[LinhaConvenio]:
        """Linhas de convênio que já têm algo na coluna do mês (P1: a tela pergunta antes de substituir)."""
        return [c for c in self.convenios if self.valores.get((c.linha, mes)) not in (None, "")]


# ---------------------------------------------------------------------------
# Equivalências (3.3)
# ---------------------------------------------------------------------------

@dataclass
class Equivalencia:
    nome_no_razao: str
    linha_da_planilha: str
    obs: str
    linha_arquivo: int


@dataclass
class Equivalencias:
    caminho: str
    de_fabrica: bool
    itens: list[Equivalencia] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)
