"""Resultados esperados de cada PDF de exemplo (seção 11 da especificação).

Valores conferidos manualmente pelo autor. Os PDFs ficam em subpastas de
exemplos/2026-08/extratos/ e são localizados pelo nome do arquivo.

Cada saldo esperado: (banco, tipo, conta normalizada, total, bloqueado,
fonte secundária). ESCANEADO marca PDFs que não devem ser lidos.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

COMPETENCIA = date(2026, 8, 1)
ESCANEADO = "escaneado"


@dataclass
class SaldoEsperado:
    banco: str
    tipo: str
    conta: str
    total: str
    bloqueado: str = "0"
    fonte_secundaria: bool = False

    @property
    def valores(self) -> tuple:
        return (self.banco, self.tipo, self.conta, Decimal(self.total),
                Decimal(self.bloqueado), self.fonte_secundaria)


@dataclass
class ArquivoEsperado:
    arquivo: str
    modelo: str                    # nome do leitor, ou ESCANEADO
    saldos: list[SaldoEsperado] = field(default_factory=list)
    competencia: date = COMPETENCIA   # mês do extrato (os modelos novos podem ser de outro mês)


GABARITO = [
    ArquivoEsperado("1144 4ok.pdf", "BB - CDB", [
        SaldoEsperado("BB", "APLICACAO", "11444", "8893.49"),
    ]),
    ArquivoEsperado("1179 7.pdf", "BB - Conta corrente", [
        SaldoEsperado("BB", "CC", "11797", "0.00"),
    ]),
    ArquivoEsperado("1179 7 Poupançaok.pdf", "BB - Poupança", [
        SaldoEsperado("BB", "POUPANCA", "11797", "223374.00"),
    ]),
    ArquivoEsperado("534 7 Rende Fácilok.pdf", "BB - Rende Fácil", [
        SaldoEsperado("BB", "APLICACAO", "5347", "228.18"),
    ]),
    ArquivoEsperado("400500 7 Fundos.pdf", "BB - Fundos", [
        SaldoEsperado("BB", "APLICACAO", "4005007", "153727.22"),
    ]),
    ArquivoEsperado("400585 6 CDBok.pdf", "BB - CDB", [
        SaldoEsperado("BB", "APLICACAO", "4005856", "4927281.60"),
    ]),
    ArquivoEsperado("568630703 9 Correnteok.pdf", "CEF - Conta corrente", [
        SaldoEsperado("CEF", "CC", "5686307039", "93.56"),
    ]),
    ArquivoEsperado("13003634 5 Conta Corrente.pdf", "Santander - Conta corrente", [
        SaldoEsperado("SANTANDER", "CC", "130036345", "0.00"),
    ]),
    ArquivoEsperado("13003636 9 Conta Corrente.pdf", "Santander - Conta corrente", [
        SaldoEsperado("SANTANDER", "CC", "130036369", "0.00"),
    ]),
    ArquivoEsperado("13003638 3 Aplicação.pdf", "Santander - ContaMax", [
        SaldoEsperado("SANTANDER", "APLICACAO", "130036383", "132.59"),
    ]),
    ArquivoEsperado("2004834 3ok.pdf", "Sicoob - Conta corrente", [
        SaldoEsperado("SICOOB", "CC", "20048343", "4186.14", bloqueado="50.00"),
    ]),
    ArquivoEsperado("Aplicações ok.pdf", ESCANEADO),
]


# ---------------------------------------------------------------------------
# Modelos novos (Etapa 10): PDFs em exemplos/modelos/, um por modelo criado
# pelo /novo-modelo. Não entram na conciliação de agosto; cada um informa a
# sua própria competência. Exemplo de linha:
#
#   ArquivoEsperado("extrato itau.pdf", "Itaú - Conta corrente", [
#       SaldoEsperado("ITAU", "CC", "123456", "1500.00"),
#   ], competencia=date(2026, 9, 1)),
# ---------------------------------------------------------------------------

GABARITO_MODELOS: list[ArquivoEsperado] = [
    # Conta corrente do BB salva da tela "Consultas - Extrato de conta corrente" (sem "BB Cash"),
    # outubro/2026. Os extratos vão até 01/11; o saldo é o da última linha até 31/10.
    ArquivoEsperado("1169-X EXTRATO.pdf", "BB - Conta corrente", [
        SaldoEsperado("BB", "CC", "1169X", "0.00"),
    ], competencia=date(2026, 10, 1)),
    ArquivoEsperado("1192-4 EXTRATO.pdf", "BB - Conta corrente", [
        SaldoEsperado("BB", "CC", "11924", "0.00"),
    ], competencia=date(2026, 10, 1)),
    ArquivoEsperado("1215-7 EXTRATO.pdf", "BB - Conta corrente", [
        SaldoEsperado("BB", "CC", "12157", "0.00"),
    ], competencia=date(2026, 10, 1)),
    # Santander, outubro/2026: extratos de conta corrente de 01/10 a 01/11 (saldo até 31/10).
    ArquivoEsperado("13005148-9 EXTRATO.pdf", "Santander - Conta corrente", [
        SaldoEsperado("SANTANDER", "CC", "130051489", "0.00"),
    ], competencia=date(2026, 10, 1)),
    ArquivoEsperado("13005157-5 EXTRATO.pdf", "Santander - Conta corrente", [
        SaldoEsperado("SANTANDER", "CC", "130051575", "0.00"),
    ], competencia=date(2026, 10, 1)),
    ArquivoEsperado("13005158-2 EXTRATO.pdf", "Santander - Conta corrente", [
        SaldoEsperado("SANTANDER", "CC", "130051582", "0.00"),
    ], competencia=date(2026, 10, 1)),
    # Santander ContaMax salvo pelo Chrome: o ano do mês vaza para a coluna do Saldo Bruto Anterior.
    ArquivoEsperado("13005148-9 INVESTIMENTO.pdf", "Santander - ContaMax", [
        SaldoEsperado("SANTANDER", "APLICACAO", "130051489", "0.00"),
    ], competencia=date(2026, 10, 1)),
    ArquivoEsperado("13005157-5 INVESTIMENTO.pdf", "Santander - ContaMax", [
        SaldoEsperado("SANTANDER", "APLICACAO", "130051575", "0.00"),
    ], competencia=date(2026, 10, 1)),
    ArquivoEsperado("13005158-2 INVESTIMENTO.pdf", "Santander - ContaMax", [
        SaldoEsperado("SANTANDER", "APLICACAO", "130051582", "0.00"),
    ], competencia=date(2026, 10, 1)),
]
