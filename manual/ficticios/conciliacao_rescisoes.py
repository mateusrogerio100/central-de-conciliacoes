"""Rescisões: razão da conta Rescisões a pagar (.xlsx), eventos da folha em PDF (0264 – Líquido
Rescisão) e a lista de rescisões a pagar do mês anterior.

Mostra: pagamentos achados no PDF e na lista anterior (um com o nome abreviado no PDF), um pago com
valor diferente, um não encontrado e uma rescisão nova que fica para pagar. A prova fecha: saldo final −
lista nova = −300,00 (pago a mais) − 640,00 (não encontrado).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from openpyxl import Workbook

from manual.ficticios import Exemplo
from manual.ficticios.pdf_simples import gravar_pdf
from manual.ficticios.tasy import numero_br, planilha

UNIDADE = "Fundação Exemplo de Misericórdia"

PAGAMENTOS = [                                   # razão: débitos de junho
    ("Eduardo Lima Exemplo", 2850.00),
    ("Ana Paula Teste", 1320.00),                # está na lista do mês anterior
    ("Fernanda Costa Exemplo", 3400.00),         # o PDF diz 3.100,00
    ("Gabriel Ribeiro Alves Exemplo", 1980.00),  # o PDF abrevia o nome
    ("Igor Nunes Teste", 640.00),                # em lugar nenhum
]
EVENTOS_0264 = [                                 # matrícula, nome no PDF, valor
    ("101", "EDUARDO LIMA EXEMPLO", 2850.00),
    ("102", "FERNANDA COSTA EXEMPLO", 3100.00),
    ("103", "GABRIEL R ALVES EXEMPLO", 1980.00),
    ("104", "HELENA DIAS EXEMPLO", 2450.00),     # ainda não paga: entra na lista nova
]
PENDENTES = [                                    # lista do mês anterior
    (datetime(2026, 5, 1), "ANA PAULA TESTE", 1320.00),
    (datetime(2026, 4, 1), "CARLA MENDES EXEMPLO", 760.00),    # continua a pagar
]
SALDO_ANTERIOR = sum(p[2] for p in PENDENTES)
CREDITO = sum(e[2] for e in EVENTOS_0264)


def _razao(pasta: Path) -> Path:
    topo = [
        [None, UNIDADE] + [None] * 8 + ["Livro: 0", None, "Página: 1"],
        ["Razão"],
        [None, None, None, "Período:", datetime(2026, 6, 1), "até:", None, datetime(2026, 6, 30)],
        [None, "Data", "Histórico", None, None, None, "Lote", None, None, "Débitos", None, "Créditos", None,
         None, "Saldo"],
    ]
    saldo = SALDO_ANTERIOR
    linhas = topo + [[None, "20763 - 2.01.03.04.0002  Rescisões a pagar"],
                     [None, None, "Saldo anterior "] + [None] * 11 + [saldo]]
    for posicao, (nome, valor) in enumerate(PAGAMENTOS, start=1):
        saldo = round(saldo - valor, 2)
        linhas.append([None, datetime(2026, 6, 4 + posicao), f"Pagamento de Rescisão conf. bordero n.  90010{posicao:02d} "
                       f"{nome}", None, None, None, 70849, None, None, valor, None, 0, None, None, saldo])
    saldo = round(saldo + CREDITO, 2)
    linhas.append([None, datetime(2026, 6, 30), "Líquido Rescisão 0626", None, None, None, 71112, None, None, 0,
                   None, CREDITO, None, None, saldo])
    debitos = round(sum(v for _, v in PAGAMENTOS), 2)
    linhas.append([None, None, "Total - 20763 - 2.01.03.04.0002  Rescisões a pagar"] + [None] * 6
                  + [debitos, None, CREDITO])
    linhas.append([None, f"Total ({len(PAGAMENTOS) + 1})"] + [None] * 7 + [debitos, None, CREDITO])
    linhas.append([None, "Impresso em: 07/07/2026 16:12:40", None, "Página: 1", None, None, None, None, "USR",
                   None, None, None, None, "WEXE002"])
    return planilha(pasta / "Razao_rescisoes_062026.xlsx", linhas)


def _eventos(pasta: Path) -> Path:
    linhas = [
        "0001 -FUNDAÇÃO EXEMPLO DE MISER. Pág.: 1",
        "EVENTOS 06/2026 C/IDENT",
        "Período: 06/2026 a 06/2026 Tipo: Cálculo Mensal",
        "Evento Colaborador SIT Competência Pagamento Referência Valor",
        "0256-Cred. Estouro do Mes",
        "26 OUTRA PESSOA EXEMPLO 003 06/2026 06/07/2026 0,00 99,00",
        "Total de Colaboradores: 01 0,00 99,00",
        "0264-Liquido Rescisao",
    ]
    linhas += [f"{matricula} {nome} 007 06/2026 06/07/2026 0,00 {numero_br(valor)}"
               for matricula, nome, valor in EVENTOS_0264]
    linhas += [f"Total de Colaboradores: {len(EVENTOS_0264):02d} 0,00 {numero_br(CREDITO)}",
               "FPRF404.OPE - 08/07/2026 - 14:54:02 FUNDAÇÃO EXEMPLO"]
    return gravar_pdf(pasta / "EVENTOS 062026 COM IDENT.pdf", [linhas])


def _lista_anterior(pasta: Path) -> Path:
    livro = Workbook()
    aba = livro.active
    aba.title = "Rescisões a pagar"
    aba.append([])
    aba.append(["Periodo", "Colaborador", "Valor"])
    for pendente in PENDENTES:
        aba.append(list(pendente))
    aba.append([None, None, f"=SUM(C3:C{len(PENDENTES) + 2})"])
    caminho = pasta / "Rescisoes a pagar 052026.xlsx"
    livro.save(caminho)
    return caminho


def gerar(pasta: Path) -> list[Exemplo]:
    pasta.mkdir(parents=True, exist_ok=True)
    saida = pasta / "saida"
    saida.mkdir(exist_ok=True)
    return [Exemplo("conciliacao_rescisoes", "rescisoes", "Conciliação", "conciliacao", {
        "cartao_razao": [_razao(pasta)], "cartao_eventos": [_eventos(pasta)],
        "cartao_controle": [_lista_anterior(pasta)], "cartao_pasta": [saida]}, pasta_saida=saida,
        numeros=("4", "1", "1"))]
