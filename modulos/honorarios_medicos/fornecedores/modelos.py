"""
Estruturas de dados da Conciliação Fornecedores (ESPECIFICACAO seção 16).

Compara, por unidade (AME ou Hospital Exemplo) e por mês, o Balancete (conta 2111 – Fornecedores
no País, Saldo Atual de cada conta de fornecedor) com o Relatório analítico de títulos a pagar
(uma linha por título; o saldo do fornecedor é a soma dos seus títulos), ambos baixados do
Tasy (.xls). O financeiro não tem código contábil: o pareamento é pelo nome do fornecedor.
Os títulos (Nr. Doc. e Nr. Título) dos fornecedores com diferença vão para uma aba própria.

Dinheiro sempre em Decimal. A nota de semelhança dos nomes (0 a 1) é float: não é dinheiro.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from modulos.honorarios_medicos.fornecedores.avisos import Aviso

# Situações (texto da aba "Conciliação Completa"; o Resumo usa o nome amigável)
SITUACAO_OK = "OK"
SITUACAO_DIVERGENTE = "DIVERGENTE"
SITUACAO_SO_BALANCETE = "SÓ NO BALANCETE"
SITUACAO_SO_RELATORIO = "SÓ NO RELATÓRIO"

NOMES_RESUMO = {
    SITUACAO_DIVERGENTE: "Divergente",
    SITUACAO_SO_BALANCETE: "Só no Balancete",
    SITUACAO_SO_RELATORIO: "Só no Relatório Financeiro",
}

# Como o par foi formado
PAREAMENTO_NOME = "nome"
PAREAMENTO_VALOR = "valor"               # mesmo valor + nome parecido o bastante: confirmar

TIPO_BALANCETE = "Balancete (865)"
TIPO_TITULOS = "Títulos a pagar"


@dataclass
class ContaFornecedor:
    """Uma conta da 2111 no Balancete (ou a própria linha de total 2.01.01.01)."""

    codigo: str                          # "23280"
    classificacao: str                   # "2.01.01.01.1223"
    descricao: str
    saldo_anterior: Decimal
    debitos: Decimal
    creditos: Decimal
    saldo_atual: Decimal

    @property
    def a_reclassificar(self) -> bool:
        """Contas "Fornecedores a reclassificar..." nunca são pareadas."""
        return self.descricao.casefold().startswith("fornecedores a reclassificar")


@dataclass
class TituloPagar:
    """Uma linha do Relatório analítico de títulos a pagar (a Observação nunca é lida)."""

    documento: str                       # Nr. Doc. (pode vir vazio, ex.: boleto)
    numero: str                          # Nr. Título
    tipo: str = ""                       # "Nota Fiscal", "Bloqueto"...
    situacao: str = ""                   # Sit. ("A")
    emissao: date | None = None
    vencimento: date | None = None       # Dt. Vencto. Atu.
    saldo: Decimal = Decimal(0)          # Vl. Saldo


@dataclass
class FornecedorFinanceiro:
    """Um fornecedor do Relatório de títulos a pagar: saldo = soma dos seus títulos."""

    nome: str
    saldo: Decimal
    titulos: list[TituloPagar] = field(default_factory=list)
    cnpj: str = ""          # filiais (CNPJ diferente) com o mesmo nome são cadastros separados


@dataclass
class LeituraBalancete:
    arquivo: str
    unidade: str = ""                    # "AME - Cidade Delta (Fund. Hospital Exemplo ...)"
    mes: date | None = None              # Mês Referência (dia 1)
    total: ContaFornecedor | None = None # linha 2.01.01.01
    contas: list[ContaFornecedor] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)
    erro: str | None = None


@dataclass
class LeituraTitulos:
    arquivo: str
    unidade: str = ""                    # coluna Estabelecimento: "Ame - Cidade Epsilon ( Fund. ... )"
    fornecedores: list[FornecedorFinanceiro] = field(default_factory=list)
    quantidade_titulos: int = 0
    avisos: list[Aviso] = field(default_factory=list)
    erro: str | None = None


@dataclass
class LinhaConciliacao:
    """Uma linha da aba "Conciliação Completa"."""

    situacao: str
    conta: ContaFornecedor | None = None
    financeiros: list[FornecedorFinanceiro] = field(default_factory=list)
    nota: float | None = None            # confiança do pareamento (None = não pareado)
    pareamento: str = ""                 # PAREAMENTO_NOME ou PAREAMENTO_VALOR

    @property
    def saldo_balancete(self) -> Decimal | None:
        return None if self.conta is None else self.conta.saldo_atual

    @property
    def saldo_financeiro(self) -> Decimal | None:
        if not self.financeiros:
            return None
        return sum((f.saldo for f in self.financeiros), Decimal(0))

    @property
    def diferenca(self) -> Decimal:
        """Balancete − financeiro (lado que falta conta como zero)."""
        return (self.saldo_balancete or Decimal(0)) - (self.saldo_financeiro or Decimal(0))

    @property
    def nome_financeiro(self) -> str:
        """"Nome 1 + Nome 2" quando o mesmo fornecedor tem dois cadastros no financeiro."""
        return " + ".join(dict.fromkeys(f.nome for f in self.financeiros))   # o mesmo nome aparece uma vez


@dataclass
class ResultadoFornecedores:
    """Tudo o que processar_fornecedores() devolve para a interface."""

    linhas: list[LinhaConciliacao] = field(default_factory=list)
    notas: list[str] = field(default_factory=list)       # notas do Resumo (sem o "Nota N:")
    avisos: list[Aviso] = field(default_factory=list)
    unidade: str = ""                    # nome completo, do Balancete
    mes: date | None = None
    total_balancete: Decimal | None = None               # linha 2.01.01.01
    total_financeiro: Decimal | None = None              # soma dos títulos lidos
    quantidade_titulos: int = 0
    arquivo_balancete: str = ""
    arquivo_titulos: str = ""
    caminho_relatorio: Path | None = None
    erro: str | None = None
