"""Conciliação Bancária: balancete bancário (o ".xls" de texto do Tasy) e a pasta dos extratos em PDF
(modelo BB Cash – conta corrente).

Mostra: contas que batem, uma com diferença, uma sem extrato e um extrato de conta que não está no
balancete.
"""

from __future__ import annotations

from pathlib import Path

from manual.ficticios import Exemplo
from manual.ficticios.pdf_simples import gravar_pdf
from manual.ficticios.tasy import numero_br, texto_tasy

CONTAS = [                                  # código, conta BB, saldo no balancete, saldo no extrato (None = sem PDF)
    ("10007", "9001-1", 152340.18, 152340.18),
    ("10008", "9002-X", 48200.00, 47950.00),
    ("10009", "9003-8", 12500.00, None),
    ("10010", "9004-6", 3210.55, 3210.55),
]
SO_NO_EXTRATO = ("9005-4", 870.00)


def _balancete(caminho: Path) -> Path:
    def linha(codigo, classificacao, descricao, saldo):
        return ["", "", codigo, "", classificacao, descricao, "", "", "0,00", "", "0,00", "", "0,00",
                numero_br(saldo), ""]

    linhas = [
        ["Fundação Exemplo de Misericórdia"], ["Balancete"],
        ["", "", "", "", "", "", "Mês Referência:", "", "", "set/2026"],
        ["", "Código", "", "Classificação", "", "Descrição", "", "", "Saldo Anterior", "", "Débitos", "",
         "Créditos", "Saldo Atual", ""],
        linha("1112", "1.01.01.02", "   DEPOSITOS BANCARIOS", sum(c[2] for c in CONTAS)),
    ]
    for posicao, (codigo, conta, saldo, _) in enumerate(CONTAS, start=1):
        linhas.append(linha(codigo, f"1.01.01.02.01.{posicao:04d}", f"      BB C/C {conta}", saldo))
    return texto_tasy(caminho, linhas)


def _extrato(pasta: Path, conta: str, saldo: float) -> Path:
    anterior = round(saldo * 0.9, 2)
    linhas = [
        "BB Cash - Conta corrente - Extrato de conta corrente",
        f"Conta corrente {conta} FUNDACAO EXEMPLO",
        "Período do",
        "de 01 / 09 / 2026 até 30 / 09 / 2026",
        "extrato",
        f"31/08/2026 0000 00000 Saldo Anterior {numero_br(anterior)} C",
        f"15/09/2026 0000 14060 Transferência recebida {numero_br(round(saldo - anterior, 2))} C",
        f"30/09/2026 0000 00000 S A L D O {numero_br(saldo)} C",
    ]
    return gravar_pdf(pasta / f"Extrato BB {conta} set2026.pdf", [linhas])


def gerar(pasta: Path) -> list[Exemplo]:
    balancete = _balancete(pasta / "balancete_bancario_set2026.xls")
    extratos = pasta / "extratos"
    for _codigo, conta, _saldo, saldo_extrato in CONTAS:
        if saldo_extrato is not None:
            _extrato(extratos, conta, saldo_extrato)
    _extrato(extratos, *SO_NO_EXTRATO)
    saida = pasta / "saida"
    saida.mkdir(parents=True, exist_ok=True)
    return [Exemplo("bancos", "bancos", "Conciliação", "conciliacao", {
        "cartao_balancete": [balancete], "cartao_extratos": [extratos], "cartao_saida": [saida]},
        pasta_saida=saida,
        numeros=("2", "1", "0"))]
