"""
Estruturas de dados da Conciliação do Imobilizado – AME's (ESPECIFICACAO seção 15).

Compara, conta por conta, o Saldo atual do Razão auxiliar do patrimônio (Tasy 6051)
com o Saldo atual dos balancetes (Tasy 865: Intangível, Imobilizado e Cessão).
Quando há diferença, os relatórios opcionais de Bens adquiridos (555) e Baixa de bens (561)
servem para tentar explicá-la.

Dinheiro sempre em Decimal. Os avisos usam o mesmo Aviso da Conferência ISS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from modulos.conciliacao_imobilizado.base_iss import Aviso

# ---------------------------------------------------------------------
# Situações de cada conta (textos exatos da planilha)
# ---------------------------------------------------------------------
SITUACAO_CONFERE = "Confere"
SITUACAO_DIFERENCA = "Diferença — verificar"     # sem os relatórios de bens adquiridos/baixas
SITUACAO_DIFERENCA_EXPLICADA = "Diferença explicada pelos bens adquiridos/baixados"
SITUACAO_DIFERENCA_SEM_EXPLICACAO = "Diferença sem explicação — verificar"
SITUACAO_SOMENTE_PATRIMONIO = "Somente no patrimônio"
SITUACAO_SOMENTE_BALANCETE = "Somente no balancete"

# Ordem em que as situações aparecem no resumo
ORDEM_SITUACOES = [
    SITUACAO_CONFERE,
    SITUACAO_DIFERENCA_EXPLICADA,
    SITUACAO_DIFERENCA,
    SITUACAO_DIFERENCA_SEM_EXPLICACAO,
    SITUACAO_SOMENTE_PATRIMONIO,
    SITUACAO_SOMENTE_BALANCETE,
]
SITUACOES_PARA_ANALISAR = (
    SITUACAO_DIFERENCA,
    SITUACAO_DIFERENCA_SEM_EXPLICACAO,
    SITUACAO_SOMENTE_PATRIMONIO,
    SITUACAO_SOMENTE_BALANCETE,
)

# Tipos de arquivo (coluna "Tipo" da aba Avisos)
TIPO_RAZAO = "Patrimônio (6051)"
TIPO_BALANCETE = "Balancete (865)"
TIPO_BENS_ADQUIRIDOS = "Bens adquiridos (555)"
TIPO_BAIXAS = "Baixa de bens (561)"


# ---------------------------------------------------------------------
# O que vem de cada relatório
# ---------------------------------------------------------------------
@dataclass
class ContaPatrimonio:
    """Um bloco do Razão auxiliar do patrimônio (6051)."""

    codigo: str                          # "11038"
    nome: str                            # "Aparelhos de informática AME"
    saldo_anterior: Decimal | None = None
    entradas: Decimal | None = None
    baixas: Decimal | None = None
    transf_entrada: Decimal | None = None
    transf_saida: Decimal | None = None
    saldo_atual: Decimal | None = None
    linha: int = 0                       # linha do título da conta no arquivo

    @property
    def diferenca_movimento(self) -> Decimal | None:
        """
        Saldo atual − (saldo anterior + entradas − baixas + transf. entrada − transf. saída).

        Diferente de zero = o próprio relatório não fecha (aviso). None = faltou algum valor.
        """
        partes = (self.saldo_anterior, self.entradas, self.baixas,
                  self.transf_entrada, self.transf_saida, self.saldo_atual)
        if any(p is None for p in partes):
            return None
        esperado = (self.saldo_anterior + self.entradas - self.baixas
                    + self.transf_entrada - self.transf_saida)
        return self.saldo_atual - esperado


@dataclass
class ContaBalancete:
    """Uma linha de conta do balancete (865)."""

    codigo: str                          # "11038" (conta-mãe: "1320")
    classificacao: str                   # "1.02.05.06.0001"
    descricao: str
    saldo_anterior: Decimal
    debitos: Decimal
    creditos: Decimal
    saldo_atual: Decimal
    arquivo: str = ""
    sintetica: bool = False              # conta-mãe (soma das outras); não entra na comparação


@dataclass
class BemAdquirido:
    """Um bem do relatório Bens adquiridos no período (555)."""

    centro: str
    conta_codigo: str
    conta_nome: str
    codigo_bem: str
    descricao: str
    data_aquisicao: date | None
    valor: Decimal                       # Vl original


@dataclass
class BemBaixado:
    """Um bem do relatório Baixa de bens do ativo imobilizado (561)."""

    conta_nome: str                      # o relatório agrupa pelo nome da conta, sem código
    chapa: str
    descricao: str
    tipo: str
    motivo: str
    valor_origem: Decimal                # é este valor que sai do saldo da conta
    valor_depreciacao: Decimal | None
    valor_atual: Decimal | None
    data: date | None
    conta_codigo: str = ""               # achado pelo nome na conciliação ("" = não achou)


# ---------------------------------------------------------------------
# Leituras (uma por arquivo)
# ---------------------------------------------------------------------
@dataclass
class LeituraRazao:
    arquivo: str
    contas: list[ContaPatrimonio] = field(default_factory=list)
    data_referencia: date | None = None
    avisos: list[Aviso] = field(default_factory=list)
    erro: str | None = None


@dataclass
class LeituraBalancete:
    arquivo: str
    contas: list[ContaBalancete] = field(default_factory=list)
    ame: str = ""                        # "Ame - Cidade Alfa ( Fund. Hospital Exemplo ... )"
    competencia: str = ""                # "2026-08"
    avisos: list[Aviso] = field(default_factory=list)
    erro: str | None = None


@dataclass
class LeituraBensAdquiridos:
    arquivo: str
    bens: list[BemAdquirido] = field(default_factory=list)
    periodo_inicio: date | None = None
    periodo_fim: date | None = None
    avisos: list[Aviso] = field(default_factory=list)
    erro: str | None = None


@dataclass
class LeituraBaixas:
    arquivo: str
    bens: list[BemBaixado] = field(default_factory=list)
    ame: str = ""
    avisos: list[Aviso] = field(default_factory=list)
    erro: str | None = None


# ---------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------
@dataclass
class ItemConciliacao:
    """Uma conta comparada (uma linha da aba Contas)."""

    codigo: str
    nome: str
    situacao: str
    conta_patrimonio: ContaPatrimonio | None = None
    conta_balancete: ContaBalancete | None = None
    entradas: Decimal = Decimal(0)       # soma dos bens adquiridos da conta
    baixas: Decimal = Decimal(0)         # soma das baixas da conta (Vl. origem)
    explicacao: str = ""

    @property
    def saldo_patrimonio(self) -> Decimal | None:
        return None if self.conta_patrimonio is None else self.conta_patrimonio.saldo_atual

    @property
    def saldo_balancete(self) -> Decimal | None:
        return None if self.conta_balancete is None else self.conta_balancete.saldo_atual

    @property
    def diferenca(self) -> Decimal | None:
        """Patrimônio − balancete (só quando a conta está nos dois)."""
        if self.saldo_patrimonio is None or self.saldo_balancete is None:
            return None
        return self.saldo_patrimonio - self.saldo_balancete


@dataclass
class ResultadoBens:
    """Tudo o que processar_bens() devolve para a interface."""

    itens: list[ItemConciliacao] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)
    contas_maes: list[ContaBalancete] = field(default_factory=list)
    bens_adquiridos: list[BemAdquirido] = field(default_factory=list)
    bens_baixados: list[BemBaixado] = field(default_factory=list)
    leu_bens_adquiridos: bool = False
    leu_baixas: bool = False
    ame: str = ""                        # nome curto: "Ame - Cidade Alfa"
    competencia: str = ""                # "2026-08"
    competencia_texto: str = ""          # "agosto/2026"
    caminho_relatorio: Path | None = None
    erro: str | None = None
