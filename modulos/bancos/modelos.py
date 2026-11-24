"""Estruturas de dados compartilhadas por todo o programa."""

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

# Tipos de conta aceitos (os mesmos no extrato e no balancete).
TIPOS = ("CC", "APLICACAO", "POUPANCA", "OUTRO")


@dataclass
class SaldoExtraido:
    """Um saldo lido de um extrato (um arquivo pode gerar mais de um)."""

    banco: str                 # "BB", "SICOOB", "CEF", "SANTANDER"
    tipo: str                  # um de TIPOS
    conta: str                 # normalizada (ver util.normalizar_conta)
    conta_original: str        # como aparece no arquivo, para exibir
    saldo_total: Decimal       # É ESTE que é comparado com o balancete
    saldo_bloqueado: Decimal = Decimal("0")
    arquivo: Path | None = None
    modelo: str = ""           # nome do leitor que gerou
    fonte_secundaria: bool = False   # ver seção 7.3 da especificação
    observacao: str = ""

    @property
    def saldo_disponivel(self) -> Decimal:
        return self.saldo_total - self.saldo_bloqueado


@dataclass
class ContaBalancete:
    """Uma conta bancária analítica lida do balancete."""

    codigo: str
    classificacao: str
    descricao: str
    banco: str
    tipo: str
    conta: str                 # normalizada
    saldo_atual: Decimal
