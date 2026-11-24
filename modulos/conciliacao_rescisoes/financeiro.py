"""
Lista nova de Rescisões a pagar × relatório de títulos a pagar do financeiro (ESPECIFICACAO seção 17).

Última parte da conciliação: o relatório analítico de títulos a pagar do Tasy (WFIN 563, o mesmo da
Conciliação Fornecedores, lido por fornecedores.leitores.ler_titulos — a coluna Observação nunca é lida)
tem um ou mais títulos por pessoa; a lista nova pode ter mais de uma rescisão da mesma pessoa. Os dois
lados são somados por pessoa e pareados pelo nome com a MESMA regra da Conciliação Fornecedores
(fornecedores.pareamento.parear): guloso por nome (nota ≥ 0,60), cadastro duplicado somado (≥ 0,85) e,
entre as sobras, mesmo valor + nome minimamente parecido (≥ 0,40). Nome de pessoa varia menos que nome de
empresa: um par com nome só parecido (nota < 0,85) E valor diferente é desfeito (provavelmente são duas pessoas,
ex.: "PAULA CRISTINA ..." × "Vanessa Cristiane ...") e vira SÓ NA LISTA + SÓ NO FINANCEIRO.

Situação: OK (mesmo valor), DIVERGENTE, SÓ NA LISTA, SÓ NO FINANCEIRO.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from modulos.conciliacao_rescisoes.fornecedores.modelos import PAREAMENTO_VALOR, FornecedorFinanceiro, LeituraTitulos
from modulos.conciliacao_rescisoes.fornecedores.pareamento import normalizar_nome, parear
from modulos.conciliacao_rescisoes.modelos import ItemLista

SITUACAO_OK = "OK"
SITUACAO_DIVERGENTE = "DIVERGENTE"
SITUACAO_SO_LISTA = "SÓ NA LISTA"
SITUACAO_SO_FINANCEIRO = "SÓ NO FINANCEIRO"
NOTA_MINIMA_DIVERGENTE = 0.85          # abaixo disso, valor diferente = pessoas diferentes
ORDEM_SITUACOES = (SITUACAO_DIVERGENTE, SITUACAO_SO_LISTA, SITUACAO_SO_FINANCEIRO, SITUACAO_OK)


@dataclass
class PessoaLista:
    """As rescisões da lista nova de uma pessoa (somadas). Tem o formato que parear() espera de uma conta."""

    nome: str
    itens: list[ItemLista] = field(default_factory=list)
    a_reclassificar: bool = False

    @property
    def descricao(self) -> str:
        return self.nome

    @property
    def saldo_atual(self) -> Decimal:
        return sum((i.valor for i in self.itens), Decimal(0))


@dataclass
class LinhaFinanceiro:
    """Uma linha da aba "Financeiro × lista"."""

    situacao: str
    pessoa: PessoaLista | None = None
    financeiros: list[FornecedorFinanceiro] = field(default_factory=list)
    nota: float | None = None            # confiança do nome (None = não pareado)
    por_valor: bool = False              # pareado pelo valor igual, com nome pouco parecido: confirmar

    @property
    def valor_lista(self) -> Decimal | None:
        return None if self.pessoa is None else self.pessoa.saldo_atual

    @property
    def valor_financeiro(self) -> Decimal | None:
        if not self.financeiros:
            return None
        return sum((f.saldo for f in self.financeiros), Decimal(0))

    @property
    def diferenca(self) -> Decimal:
        """Lista − financeiro (lado que falta conta como zero)."""
        return (self.valor_lista or Decimal(0)) - (self.valor_financeiro or Decimal(0))

    @property
    def nome_financeiro(self) -> str:
        return " + ".join(f.nome for f in self.financeiros)

    @property
    def titulos(self) -> list:
        return [t for f in self.financeiros for t in f.titulos]

    @property
    def nome_parecido(self) -> bool:
        """Pareado com nome escrito diferente (confirmar)."""
        return self.por_valor or (self.nota is not None and self.nota < 1)


@dataclass
class ComparacaoFinanceiro:
    arquivo: str
    linhas: list[LinhaFinanceiro] = field(default_factory=list)
    quantidade_titulos: int = 0

    @property
    def total_lista(self) -> Decimal:
        return sum((l.valor_lista or Decimal(0) for l in self.linhas), Decimal(0))

    @property
    def total_financeiro(self) -> Decimal:
        return sum((l.valor_financeiro or Decimal(0) for l in self.linhas), Decimal(0))

    @property
    def diferenca(self) -> Decimal:
        return self.total_lista - self.total_financeiro

    def linhas_de(self, situacao: str) -> list[LinhaFinanceiro]:
        return [l for l in self.linhas if l.situacao == situacao]

    @property
    def para_conferir(self) -> list[LinhaFinanceiro]:
        """Tudo o que não é OK."""
        return [l for l in self.linhas if l.situacao != SITUACAO_OK]

    @property
    def nomes_parecidos(self) -> list[LinhaFinanceiro]:
        return [l for l in self.linhas if l.situacao == SITUACAO_OK and l.nome_parecido]


def agrupar_lista(lista_nova: list[ItemLista]) -> list[PessoaLista]:
    """Rescisões da mesma pessoa (nome igual sem acento, maiúsculas e "de/da/dos") juntas, na ordem da lista."""
    por_chave: dict[str, PessoaLista] = {}
    for item in lista_nova:
        chave = normalizar_nome(item.nome) or item.nome.casefold()
        if chave not in por_chave:
            por_chave[chave] = PessoaLista(nome=item.nome)
        por_chave[chave].itens.append(item)
    return list(por_chave.values())


def comparar_com_financeiro(lista_nova: list[ItemLista], titulos: LeituraTitulos) -> ComparacaoFinanceiro:
    """Pareia as pessoas da lista nova com as do financeiro; linhas na ordem: o que conferir primeiro
    (divergente, só na lista, só no financeiro), depois as OK — cada grupo na ordem da lista."""
    pessoas = agrupar_lista(lista_nova)
    comparacao = ComparacaoFinanceiro(arquivo=titulos.arquivo, quantidade_titulos=titulos.quantidade_titulos)
    for linha in parear(pessoas, titulos.fornecedores).linhas:
        nova = LinhaFinanceiro(situacao="", pessoa=linha.conta, financeiros=list(linha.financeiros),
                               nota=linha.nota, por_valor=linha.pareamento == PAREAMENTO_VALOR)
        if nova.pessoa is None:
            nova.situacao = SITUACAO_SO_FINANCEIRO
        elif not nova.financeiros:
            nova.situacao = SITUACAO_SO_LISTA
        elif nova.diferenca == 0:
            nova.situacao = SITUACAO_OK
        elif (nova.nota or 0) < NOTA_MINIMA_DIVERGENTE:     # nome só parecido e valor diferente: separa
            comparacao.linhas.append(LinhaFinanceiro(situacao=SITUACAO_SO_LISTA, pessoa=nova.pessoa))
            comparacao.linhas += [LinhaFinanceiro(situacao=SITUACAO_SO_FINANCEIRO, financeiros=[f])
                                  for f in nova.financeiros]
            continue
        else:
            nova.situacao = SITUACAO_DIVERGENTE
        comparacao.linhas.append(nova)
    comparacao.linhas.sort(key=lambda l: ORDEM_SITUACOES.index(l.situacao))   # sort estável: mantém a ordem
    return comparacao
