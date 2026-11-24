"""Crédito Estouro: PDF de eventos de junho (0256, 0258, 0241, 1204), o razão da conta Crédito Complemento Salário
(.xls do Tasy) e o controle de maio (o Excel que o módulo gera).

Mostra: um 0256 cobrado no 0258, um que virou parcelamento, um baixado na rescisão negativa do razão, um não cobrado
(para conferir), um parcelamento quitado no 1204 e dois afastados (um pagou certo, um pagou a menos). A prova
fecha: saldo final do razão R$ 1.080,00 = 0256 de junho 570,00 + parcelamento 280,00 + pendência 200,00 + diferença
do 0241 30,00.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from manual.ficticios import Exemplo
from manual.ficticios.pdf_simples import gravar_pdf
from manual.ficticios.tasy import numero_br, texto_tasy
from modulos.credito_estouro.controle import gravar_controle
from modulos.credito_estouro.modelos import TIPO_0256, TIPO_PARCELAMENTO, ItemControle

UNIDADE = "FUNDAÇÃO EXEMPLO DE MISERICÓRDIA"
CONTA = "10652 - 1.01.03.02.0002  Credito Complemento Salario"
MAIO = date(2026, 5, 1)

CONTROLE_MAIO = [
    ItemControle("101", "ANA LIMA EXEMPLO", TIPO_0256, MAIO, Decimal("300.00")),         # cobrada no 0258
    ItemControle("102", "BRUNO COSTA TESTE", TIPO_0256, MAIO, Decimal("150.00")),        # cobrado no 0258
    ItemControle("103", "CARLA DIAS EXEMPLO", TIPO_0256, MAIO, Decimal("420.00")),       # vira parcelamento
    ItemControle("104", "DANIEL ROCHA TESTE", TIPO_0256, MAIO, Decimal("500.00")),       # desligado
    ItemControle("105", "ELISA MOURA EXEMPLO", TIPO_0256, MAIO, Decimal("200.00")),      # não cobrada
    ItemControle("201", "FABIO NUNES EXEMPLO", TIPO_PARCELAMENTO, MAIO, Decimal("373.21"), Decimal("373.14")),
]
EVENTOS = {                                     # evento: [(matrícula, nome, valor)]
    "0241-Reembolso Debito Afastado": [("301", "GISELE PRADO EXEMPLO", 250.00), ("302", "HUGO SALES TESTE", 180.00)],
    "0256-Cred. Estouro do Mes": [("101", "ANA LIMA EXEMPLO", 320.00), ("301", "GISELE PRADO EXEMPLO", 250.00)],
    "0258-Deb. Estouro Mes Anterior": [("101", "ANA LIMA EXEMPLO", 300.00), ("102", "BRUNO COSTA TESTE", 150.00)],
    "1204-Deb. Estouro Parcelado": [("103", "CARLA DIAS EXEMPLO", 140.00), ("201", "FABIO NUNES EXEMPLO", 373.21)],
}
MANUAIS = [                                     # (dia, histórico, crédito)
    (10, "Desconto Plano de Saúde em folha  Título 9001 Gisele Prado Exemplo", 250.00),
    (15, "Recebimento de valores na tesouraria Hugo Sales Teste plano de saude do funcionario afastado", 150.00),
    (30, "Referente Rescisão negativa do colaborador Daniel Rocha Teste crachá 104", 500.00),
]


def _total(evento: str) -> float:
    return round(sum(valor for _, _, valor in EVENTOS[evento]), 2)


def _eventos(pasta: Path) -> Path:
    linhas = ["0001 -FUNDAÇÃO EXEMPLO DE MISER. Pág.: 1", "EVENTOS 06/2026 C/IDENT",
              "Período: 06/2026 a 06/2026 Tipo: Cálculo Mensal",
              "Evento Colaborador SIT Competência Pagamento Referência Valor"]
    for evento, pessoas in EVENTOS.items():
        linhas.append(evento)
        linhas += [f"{matricula} {nome} 003 06/2026 06/07/2026 0,00 {numero_br(valor)}"
                   for matricula, nome, valor in pessoas]
        linhas.append(f"Total de Colaboradores: {len(pessoas):02d} 0,00 {numero_br(_total(evento))}")
    linhas.append("FPRF404.OPE - 08/07/2026 - 14:54:02 FUNDAÇÃO EXEMPLO")
    return gravar_pdf(pasta / "EVENTOS 062026 COM IDENT.pdf", [linhas])


def _razao(pasta: Path) -> Path:
    saldo = float(sum(i.valor for i in CONTROLE_MAIO))
    linhas = [
        [None, "Fundação Exemplo de Misericórdia"] + [None] * 8 + ["Livro: 0", None, "Página: 1"],
        ["Razão"],
        [None, None, None, "Período:", datetime(2026, 6, 1), "até:", None, datetime(2026, 6, 30)],
        [None, "Data", "Histórico", None, None, None, "Lote", None, None, "Débitos", None, "Créditos", None, None,
         "Saldo"],
        [None, CONTA],
        [None, None, "Saldo anterior "] + [None] * 11 + [saldo],
    ]
    for dia, historico, credito in MANUAIS:
        saldo = round(saldo - credito, 2)
        linhas.append([None, datetime(2026, 6, dia), historico, None, None, None, 70900, None, None, 0, None, credito,
                       None, None, saldo])
    folha_credito = round(_total("0256-Cred. Estouro do Mes") + _total("0241-Reembolso Debito Afastado"), 2)
    folha_desconto = round(_total("0258-Deb. Estouro Mes Anterior") + _total("1204-Deb. Estouro Parcelado"), 2)
    saldo = round(saldo + folha_credito, 2)
    linhas.append([None, datetime(2026, 6, 30), "Credito complemento salário no mês 0626", None, None, None, 71112,
                   None, None, folha_credito, None, 0, None, None, saldo])
    saldo = round(saldo - folha_desconto, 2)
    linhas.append([None, datetime(2026, 6, 30), "Desconto crédito complemento salário no mês 0626", None, None, None,
                   71112, None, None, 0, None, folha_desconto, None, None, saldo])
    creditos = round(sum(c for _, _, c in MANUAIS) + folha_desconto, 2)
    linhas.append([None, None, f"Total - {CONTA}"] + [None] * 6 + [folha_credito, None, creditos])
    linhas.append([None, f"Total ({len(MANUAIS) + 3})"] + [None] * 7 + [folha_credito, None, creditos])
    linhas.append([None, "Impresso em: 08/07/2026 10:00:00", None, "Página: 1", None, None, None, None, "USR", None,
                   None, "WEXE002"])
    return texto_tasy(pasta / "razao_credito_complemento_062026.xls", linhas)


def _controle(pasta: Path) -> Path:
    total = sum(i.valor for i in CONTROLE_MAIO)
    return gravar_controle(pasta / "CreditoEstouro_mai2026.xlsx", MAIO, UNIDADE, total,
                           CONTROLE_MAIO)


def gerar(pasta: Path) -> list[Exemplo]:
    pasta.mkdir(parents=True, exist_ok=True)
    saida = pasta / "saida"
    saida.mkdir(exist_ok=True)
    return [Exemplo("credito_estouro", "credito_estouro", "Conciliação", "conciliacao", {
        "cartao_eventos": [_eventos(pasta)], "cartao_razao": [_razao(pasta)], "cartao_controle": [_controle(pasta)],
        "cartao_pasta": [saida]}, pasta_saida=saida, numeros=("5", "2", "R$ 0,00"))]
