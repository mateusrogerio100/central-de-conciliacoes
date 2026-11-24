"""Estruturas de dados do módulo Crédito Estouro (ESPECIFICACAO_CREDITO_ESTOURO.md, seções 3 e 4).

Dinheiro sempre em Decimal com 2 casas.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

ZERO = Decimal("0.00")

# Eventos da folha usados pela conciliação (seção 2.1)
EVENTO_REEMBOLSO_AFASTADO = "0241"
EVENTO_CREDITO_ESTOURO = "0256"
EVENTO_DEBITO_ESTOURO = "0258"
EVENTO_PARCELADO = "1204"
EVENTO_DEVOLUCAO = "0775"
EVENTOS_USADOS = (EVENTO_REEMBOLSO_AFASTADO, EVENTO_CREDITO_ESTOURO, EVENTO_DEBITO_ESTOURO,
                  EVENTO_PARCELADO, EVENTO_DEVOLUCAO)
NOMES_EVENTOS = {
    EVENTO_REEMBOLSO_AFASTADO: "Reembolso débito afastado",
    EVENTO_CREDITO_ESTOURO: "Crédito estouro do mês",
    EVENTO_DEBITO_ESTOURO: "Débito estouro mês anterior",
    EVENTO_PARCELADO: "Débito estouro parcelado",
    EVENTO_DEVOLUCAO: "Devolução crédito estouro indevido",
}


@dataclass
class Aviso:
    """Uma linha da aba Avisos: de que arquivo veio e o que aconteceu."""

    arquivo: str
    mensagem: str


# ---------------------------------------------------------------------
# Eventos da folha (PDF FPRF404)
# ---------------------------------------------------------------------
@dataclass
class LinhaEvento:
    """Uma pessoa num bloco de evento do PDF."""

    evento: str                       # "0256"
    matricula: str
    nome: str
    valor: Decimal
    data_pagamento: date | None = None
    pagina: int = 0


@dataclass
class TotalImpresso:
    """O "Total de Colaboradores: N 0,00 V" de um bloco."""

    quantidade: int
    valor: Decimal


@dataclass
class LeituraEventos:
    arquivo: str
    unidade: str = ""
    competencia: date | None = None   # dia 1 do mês do "Período:"
    tipo: str = ""                    # "Cálculo Mensal", "Complementar Rescisão"…
    linhas: list[LinhaEvento] = field(default_factory=list)
    totais_impressos: dict[str, TotalImpresso] = field(default_factory=dict)
    avisos: list[Aviso] = field(default_factory=list)
    erro: str | None = None
    assinatura: str = ""              # sha256 do arquivo (PDF repetido)

    def do_evento(self, evento: str) -> list[LinhaEvento]:
        return [linha for linha in self.linhas if linha.evento == evento]

    def total(self, evento: str) -> Decimal:
        return sum((linha.valor for linha in self.do_evento(evento)), ZERO)

    def quantidade(self, evento: str) -> int:
        return len(self.do_evento(evento))

    def por_matricula(self, evento: str) -> dict[str, Decimal]:
        """Soma por matrícula (a mesma pessoa pode aparecer mais de uma vez no bloco)."""
        somas: dict[str, Decimal] = defaultdict(lambda: ZERO)
        for linha in self.do_evento(evento):
            somas[linha.matricula] += linha.valor
        return dict(somas)


# ---------------------------------------------------------------------
# Controle (o que fica em aberto de um mês para o outro — seção 3.3)
# ---------------------------------------------------------------------
TIPO_0256 = "0256 a cobrar"
TIPO_PARCELAMENTO = "Parcelamento"
TIPO_DIFERENCA_0241 = "Diferença do 0241"
TIPO_PENDENCIA = "Pendência a conferir"
TIPO_ACERTO = "Acerto manual do razão"
# "quem paga por quem" (decisão do usuário, 13/11/2026): pagamentos no razão em nome do pagador contam para o
# colaborador da linha (ex.: o dependente que paga o plano de saúde do afastado). Valor sempre zero.
TIPO_VINCULO = "Pagamento por outra pessoa"
TIPOS_COM_VALOR = (TIPO_0256, TIPO_PARCELAMENTO, TIPO_DIFERENCA_0241, TIPO_PENDENCIA, TIPO_ACERTO)
TIPOS_CONTROLE = TIPOS_COM_VALOR + (TIPO_VINCULO,)


@dataclass
class ItemControle:
    """Um valor em aberto. `valor` é o efeito no saldo da conta: positivo = o colaborador ainda deve."""

    matricula: str
    nome: str
    tipo: str
    origem: date | None               # mês em que o valor nasceu (dia 1)
    valor: Decimal
    parcela: Decimal | None = None    # só no parcelamento
    observacao: str = ""
    pagador: str = ""                 # só no TIPO_VINCULO: o nome que aparece no histórico do razão


# ---------------------------------------------------------------------
# Razão da conta (Tasy WEXE002)
# ---------------------------------------------------------------------
@dataclass
class LancamentoRazao:
    data: date | None
    historico: str
    lote: str
    debito: Decimal
    credito: Decimal
    saldo: Decimal | None = None
    linha: int = 0                    # linha da planilha ou do texto do PDF (para os avisos)


@dataclass
class LeituraRazao:
    arquivo: str
    formato: str = ""                 # "Excel" ou "PDF"
    unidade: str = ""
    conta: str = ""                   # "10652 - 1.01.03.02.0002 Credito Complemento Salario"
    inicio: date | None = None
    fim: date | None = None
    saldo_anterior: Decimal | None = None
    lancamentos: list[LancamentoRazao] = field(default_factory=list)
    totais_impressos: tuple[Decimal, Decimal] | None = None   # (débitos, créditos) do "Total - <conta>"
    ultimo_saldo_impresso: Decimal | None = None
    avisos: list[Aviso] = field(default_factory=list)
    erro: str | None = None

    @property
    def total_debitos(self) -> Decimal:
        return sum((l.debito for l in self.lancamentos), ZERO)

    @property
    def total_creditos(self) -> Decimal:
        return sum((l.credito for l in self.lancamentos), ZERO)

    @property
    def saldo_final(self) -> Decimal | None:
        """Conta do ativo: saldo anterior + débitos − créditos."""
        if self.saldo_anterior is None:
            return None
        return self.saldo_anterior + self.total_debitos - self.total_creditos
