"""Estruturas de dados usadas em todo o programa."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from pathlib import Path

from modulos.subvencoes import configuracao


class ErroArquivo(Exception):
    """Arquivo que não pôde ser lido (inexistente, aberto no Excel, .xls, formato inesperado).

    A mensagem é escrita para o usuário final.
    """


class Gravidade(str, Enum):
    ERRO = "ERRO"
    ATENCAO = "ATENÇÃO"
    INFO = "INFO"


@dataclass
class Aviso:
    gravidade: Gravidade
    tipo: str
    mensagem: str
    arquivo: str = ""
    aba: str = ""
    linha: int | None = None
    conta: str = ""


@dataclass(frozen=True, order=True)
class MesReferencia:
    ano: int
    mes: int

    def __post_init__(self):
        if not 1 <= self.mes <= 12:
            raise ValueError(f"Mês inválido: {self.mes}")

    def __str__(self) -> str:
        """Formato de tela: MM/AAAA."""
        return f"{self.mes:02d}/{self.ano}"

    @property
    def para_nome_arquivo(self) -> str:
        """Formato dos nomes de arquivo: MM-AAAA."""
        return f"{self.mes:02d}-{self.ano}"


# ---------------------------------------------------------------------------
# Balancete
# ---------------------------------------------------------------------------


@dataclass
class ContaBalancete:
    codigo: int
    classificacao: str
    descricao: str
    saldo_atual: Decimal
    linha: int

    @property
    def analitica(self) -> bool:
        ultimo = self.classificacao.split(".")[-1]
        return len(ultimo) == configuracao.BALANCETE_DIGITOS_ANALITICA

    @property
    def classificacao_pai(self) -> str:
        """Classificação da conta sintética que agrupa esta (ex.: 2.02.06.01.0020 -> 2.02.06.01)."""
        return self.classificacao.rsplit(".", 1)[0]


@dataclass
class Balancete:
    arquivo: str
    mes_referencia: MesReferencia | None
    contas: dict[int, ContaBalancete] = field(default_factory=dict)
    avisos: list[Aviso] = field(default_factory=list)

    def analiticas(self) -> list[ContaBalancete]:
        return [c for c in self.contas.values() if c.analitica]

    def sinteticas(self) -> list[ContaBalancete]:
        return [c for c in self.contas.values() if not c.analitica]

    def por_classificacao(self, classificacao: str) -> ContaBalancete | None:
        for conta in self.contas.values():
            if conta.classificacao == classificacao:
                return conta
        return None

    def filhas(self, classificacao: str) -> list[ContaBalancete]:
        """Contas analíticas diretamente agrupadas pela sintética indicada."""
        return [c for c in self.analiticas() if c.classificacao_pai == classificacao]


# ---------------------------------------------------------------------------
# Patrimônio
# ---------------------------------------------------------------------------


@dataclass
class ItemPatrimonio:
    codigo_bem: str
    descricao: str
    valor: Decimal
    linha: int


def _somar_itens(itens: list[ItemPatrimonio]) -> Decimal:
    return sum((item.valor for item in itens), Decimal("0.00"))


@dataclass
class ContaPatrimonio:
    nome: str
    itens: list[ItemPatrimonio] = field(default_factory=list)
    total_sistema: Decimal | None = None      # valor da linha "Total - ..."; None se não houver (P2)
    quantidade_sistema: int | None = None     # número entre parênteses na linha Total
    linha_cabecalho: int | None = None
    linha_total: int | None = None
    cabecalho_ausente: bool = False           # P4: conta identificada só pela linha Total

    @property
    def soma_itens(self) -> Decimal:
        """Saldo Patrimônio da conta (R4): sempre a soma dos itens, nunca a linha Total."""
        return _somar_itens(self.itens)

    @property
    def total_divergente(self) -> bool:
        """P3: a linha Total do sistema não bate com a soma dos itens."""
        return self.total_sistema is not None and self.total_sistema != self.soma_itens

    @property
    def quantidade_divergente(self) -> bool:
        return self.quantidade_sistema is not None and self.quantidade_sistema != len(self.itens)


@dataclass
class RelatorioPatrimonio:
    arquivo: str
    mes_referencia: MesReferencia | None
    contas: list[ContaPatrimonio] = field(default_factory=list)
    total_geral_sistema: Decimal | None = None       # valor da linha "Total(...)"
    quantidade_geral_sistema: int | None = None      # número entre parênteses da linha "Total(...)"
    linhas_nao_reconhecidas: list[int] = field(default_factory=list)
    itens_sem_conta: list[ItemPatrimonio] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)

    @property
    def soma_itens(self) -> Decimal:
        """Soma de todos os itens de todas as contas (conferida contra a linha "Total(...)")."""
        return sum((conta.soma_itens for conta in self.contas), Decimal("0.00"))

    @property
    def quantidade_itens(self) -> int:
        return sum(len(conta.itens) for conta in self.contas)

    @property
    def total_geral_confere(self) -> bool:
        return self.total_geral_sistema is not None and self.total_geral_sistema == self.soma_itens


# ---------------------------------------------------------------------------
# Planilhas a preencher (estrutura lida pelo preenchedor)
# ---------------------------------------------------------------------------


@dataclass
class LinhaPlanilha:
    """Uma linha de conta de uma aba: tem número inteiro na coluna "Conta Contábil"."""
    linha: int
    conta_contabil: int
    convenio: str = ""


@dataclass
class CorrecaoFormula:
    """Fórmula de total incompleta que a cópia gerada recebe corrigida (ex.: D35 SUM(D5:D33) -> SUM(D5:D34))."""
    linha: int
    coluna: int
    celula: str                      # ex.: "D35"
    formula_original: str
    formula_corrigida: str


@dataclass
class AbaPlanilha:
    nome: str
    linhas: list[LinhaPlanilha] = field(default_factory=list)
    correcoes_formula: list[CorrecaoFormula] = field(default_factory=list)
    # posição dos títulos (números de linha/coluna do Excel, começando em 1)
    linha_titulos: int | None = None
    coluna_conta: int | None = None
    coluna_convenio: int | None = None
    coluna_saldo_patrimonio: int | None = None
    coluna_saldo_contabil: int | None = None


@dataclass
class PlanilhaLida:
    arquivo: str                     # nome do arquivo de entrada (ex.: Projetos_08-2026.xlsx)
    abas: list[AbaPlanilha] = field(default_factory=list)
    abas_sem_contas: list[str] = field(default_factory=list)   # abas sem a linha de títulos
    avisos: list[Aviso] = field(default_factory=list)          # R12 e problemas de estrutura


# ---------------------------------------------------------------------------
# Resultado da conciliação
# ---------------------------------------------------------------------------


@dataclass
class ResultadoLinha:
    """O que vai para as células Saldo Patrimônio / Saldo Contábil de uma linha (aba "Conferência")."""
    planilha: str
    aba: str
    linha: int
    conta_contabil: int
    convenio: str
    descricao_balancete: str
    saldo_patrimonio: Decimal
    saldo_contabil: Decimal
    observacoes: list[str] = field(default_factory=list)

    @property
    def diferenca(self) -> Decimal:
        """Patrimônio − Contábil."""
        return self.saldo_patrimonio - self.saldo_contabil

    @property
    def observacao(self) -> str:
        return "; ".join(self.observacoes)


@dataclass
class ConferenciaAba:
    """R9: soma do Saldo Contábil da aba x Saldo Atual da conta sintética do balancete."""
    planilha: str
    aba: str
    soma_saldo_contabil: Decimal
    classificacoes_sinteticas: list[str]
    sintetica: ContaBalancete | None = None

    @property
    def confere(self) -> bool:
        return self.sintetica is not None and self.sintetica.saldo_atual == self.soma_saldo_contabil


@dataclass
class ResultadoConciliacao:
    linhas: list[ResultadoLinha] = field(default_factory=list)
    conferencias_aba: list[ConferenciaAba] = field(default_factory=list)
    # contas do patrimônio ligadas a alguma linha de planilha (nomes normalizados) — R8
    contas_patrimonio_usadas: set[str] = field(default_factory=set)
    avisos: list[Aviso] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Resultado do processamento (o que a interface e o relatório recebem)
# ---------------------------------------------------------------------------


class StatusArquivo(str, Enum):
    LIDO = "lido"
    GERADO = "gerado"
    FALHOU = "falhou"
    NAO_PROCESSADO = "não processado"


@dataclass
class ArquivoResumo:
    """Uma linha do Resumo: um arquivo de entrada e o que aconteceu com ele (R13)."""
    caminho: str
    tipo: str                                # Balancete / Patrimônio / Planilha
    status: StatusArquivo
    mes_lido: MesReferencia | None = None
    detalhe: str = ""
    # só para planilhas
    destino: str = ""
    linhas_preenchidas: int = 0
    linhas_com_diferenca: int = 0            # Saldo Patrimônio ≠ Saldo Contábil
    abas_sem_contas: list[str] = field(default_factory=list)

    @property
    def nome(self) -> str:
        return Path(self.caminho).name


@dataclass
class ResultadoProcessamento:
    mes_referencia: MesReferencia
    pasta_saida: str
    arquivos: list[ArquivoResumo] = field(default_factory=list)
    balancete: Balancete | None = None
    patrimonio: RelatorioPatrimonio | None = None
    conciliacao: ResultadoConciliacao | None = None
    avisos: list[Aviso] = field(default_factory=list)
    caminho_relatorio: str = ""
    erro_relatorio: str = ""                 # preenchido se o relatório não pôde ser gravado

    def quantidade_por_gravidade(self) -> dict[Gravidade, int]:
        return {g: sum(1 for a in self.avisos if a.gravidade == g) for g in Gravidade}

    @property
    def planilhas(self) -> list[ArquivoResumo]:
        return [a for a in self.arquivos if a.tipo == TIPO_PLANILHA]

    @property
    def planilhas_geradas(self) -> list[ArquivoResumo]:
        return [a for a in self.planilhas if a.status == StatusArquivo.GERADO]


TIPO_BALANCETE = "Balancete"
TIPO_PATRIMONIO = "Patrimônio"
TIPO_PLANILHA = "Planilha"
