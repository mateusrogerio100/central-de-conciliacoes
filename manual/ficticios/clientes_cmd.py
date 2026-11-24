"""Clientes CMD, as duas abas.

Conciliação de clientes: balancete de clientes e Títulos a Receber (.xlsx). Mostra nomes idênticos,
nome cortado no financeiro, empresa com pontuação diferente, um valor divergente, um cliente só no
balancete e um só no financeiro.

Import Contábil: a pasta com os relatórios do mês (três planilhas, uma delas com o valor no formato
quebrado "1,234,56" e o Complemento com aspas sobrando, que o programa corrige) → Rel_Geral → .txt.
"""

from __future__ import annotations

from pathlib import Path

from manual.ficticios import Exemplo
from manual.ficticios.tasy import planilha

# --- Conciliação de clientes ----------------------------------------------------------------------------
CLIENTES = [                                          # código, nome no balancete, saldo
    (5101, "Ana Exemplo da Silva", 350.00),
    (5102, "Bruno Teste Oliveira", 1200.00),
    (5103, "Carla Exemplo Souza Pereira", 89.90),
    (5104, "Empresa Exemplo Comércio Ltda", 4500.00),
    (5105, "Diego Teste Lima", 220.00),
    (5106, "Gabriela Teste Martins", 640.00),
]
TITULOS = [                                           # nome no financeiro, valor do título, saldo
    ("ANA EXEMPLO DA SILVA", 350.00, 350.00),
    ("BRUNO TESTE OLIVEIRA", 1500.00, 1150.00),
    ("CARLA EXEMPLO SOUZA PER", 89.90, 89.90),        # o relatório corta o nome
    ("EMPRESA EXEMPLO COMERCIO LTDA.", 4500.00, 4500.00),
    ("GABRIELA TESTE MARTINS", 640.00, 640.00),
    ("FERNANDA EXEMPLO ROCHA", 75.00, 75.00),
]


def _balancete(caminho: Path) -> Path:
    linhas = [["Fundação Exemplo de Misericórdia"], ["Balancete"], [None, None, None, "Mês Referência:", "set/2026"],
              ["Código", "Classificação", "Descrição", "Saldo Anterior", "Débitos", "Créditos", "Saldo Atual"],
              [1120, "1.01.02.01", "CLIENTES", 0, 0, 0, sum(c[2] for c in CLIENTES)]]
    for posicao, (codigo, nome, saldo) in enumerate(CLIENTES, start=1):
        linhas.append([codigo, f"1.01.02.01.{posicao:04d}", nome, 0, saldo, 0, saldo])
    return planilha(caminho, linhas)


def _titulos(caminho: Path) -> Path:
    linhas = [["Títulos a Receber - Clientes"], [],
              ["Pessoa", "Vl titulo", "Vl juros + multa", "Vl baixa", "Vl saldo"]]
    for nome, titulo, saldo in TITULOS:
        linhas.append([nome, titulo, 0.0, round(titulo - saldo, 2), saldo])
    linhas.append(["Total geral", sum(t[1] for t in TITULOS), 0.0, None, sum(t[2] for t in TITULOS)])
    return planilha(caminho, linhas)


# --- Import Contábil ------------------------------------------------------------------------------------
CABECALHO_FONTE = ["Contrato", "Dia lançamento", "Conta debito", "Conta credito", "Vl parcela formatado",
                   "Historico", "Complemento", "Centro custo", "Vl parcela formatado"]
RELATORIOS = {
    "Cartao de Credito.xlsx": [
        ["C-101", 30, 11205, 31101, "1.250,00", 1030, "Recebimento cartão exemplo 01", 1007, "1.250,00"],
        ["C-102", 30, 11205, 31101, "2,614,91", 1030, "Recebimento cartão exemplo 02", 1007, "2,614,91"],
    ],
    "Clientes PJ receita.xlsx": [
        ["P-201", 30, 11201, 31102, "4.500,00", 1031, '""Empresa Exemplo Comércio Ltda""', 1012, "4.500,00"],
        ["P-202", 30, 11201, 31102, "980,40", 1031, "Clínica Exemplo Teste", 1012, "980,40"],
    ],
    "Clientes PJ provisao.xlsx": [
        ["P-301", 30, 11202, 21501, "1.100,00", 1032, "Provisão contrato exemplo", None, None],
    ],
}


def _relatorios(pasta: Path) -> Path:
    for nome, linhas in RELATORIOS.items():
        planilha(pasta / nome, [CABECALHO_FONTE] + linhas)
    return pasta


def gerar(pasta: Path) -> list[Exemplo]:
    conciliacao, importacao = pasta / "Conciliacao", pasta / "Import Contabil"
    saida_conciliacao, saida_import = conciliacao / "saida", importacao / "saida"
    for saida in (saida_conciliacao, saida_import):
        saida.mkdir(parents=True, exist_ok=True)
    relatorios = _relatorios(importacao / "relatorios 09-2026")
    return [
        Exemplo("clientes_cmd", "clientes_cmd_conciliacao", "Conciliação de clientes", "conciliacao", {
            "cartao_balancete": [_balancete(conciliacao / "Balancete clientes set2026.xlsx")],
            "cartao_financeiro": [_titulos(conciliacao / "Titulos a receber set2026.xlsx")],
            "cartao_saida": [saida_conciliacao]}, pasta_saida=saida_conciliacao, numeros=("4", "1", "2")),
        Exemplo("clientes_cmd", "clientes_cmd_import", "Import Contábil", "import_contabil", {
            "cartao_relatorios": [relatorios], "cartao_saida": [saida_import]},
            preparar=lambda tela: tela.campo_mes.definir("09/2026"),
            acao=["processar", "gerar_import"], pasta_saida=saida_import, numeros=("5", "10")),
    ]
