"""Notas de Contrato: o movimento do Tasy (uma pasta por estabelecimento, .csv em UTF-16 como o Tasy grava), o
Check list (abas HOSPITAL EXEMPLO, CENTRO MULTIDISCIPLINAR e Emails, com os números dos responsáveis) e o regras.csv.

Conferência mostra: três notas achadas (uma com variação de mais de 10%), uma na conta errada, uma que não chegou
e uma manual. Pendências (com o Check list já atualizado e o relatório da Conferência, que a tela lembra e tira a
nota da conta errada) mostra: duas notas pendentes, um e-mail e um responsável sem contato na aba Emails.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

import openpyxl

from manual.ficticios import Exemplo

TITULOS_MOVIMENTO = ["Status", "Lançamento", "Data movimento", "Valor", "Complemento", "Lote contábil",
                     "Débito/Crédito", "Conta", "Estabelecimento", "Conta contábil"]
TITULOS_REGRAS = ["Aba", "Linha", "Fornecedor_Planilha", "Descricao_Planilha", "Contas", "Busca_Fornecedor",
                  "Busca_Descricao", "Excluir", "Selecao", "Tipo", "Obs"]
# aba, conta, fornecedor, descrição, responsável, set/26, valor lançado em out/26, conta lançada, tipo
CONTRATOS = [
    ("SC", "30091", "Alfa Exemplo Sistemas Ltda", "Licença de software", "1 - Ana Exemplo", 1200, 1200.00,
     "30091", "auto"),
    ("SC", "30130", "Beta Exemplo Telefonia S.A.", "Telefonia fixa", "2 - Bruno Exemplo", 700, 850.00,
     "30130", "auto"),
    ("SC", "30044", "Gama Exemplo Equipamentos Ltda", "Locação de equipamento", "1 - Ana Exemplo", 3100, 3100.00,
     "30999", "auto"),
    ("SC", "30092", "Delta Exemplo Locações Ltda", "Locação de impressoras", "2 - Bruno Exemplo", 450, None,
     None, "auto"),
    ("SC", "30160", "Epsilon Exemplo Serviços Ltda", "Manutenção predial", "3 - Carla Exemplo", 2500, 2500.00,
     "30160", "manual"),
    ("CMD", "30140", "Zeta Exemplo Energia S.A.", "Energia elétrica", "1 - Ana Exemplo", 980, 1010.00,
     "30140", "auto"),
]
CONTATOS = [("Ana Exemplo <ana.exemplo@exemplo.org.br>", "1"), ("Bruno Exemplo <bruno.exemplo@exemplo.org.br>", "2"),
            ("Contabilidade Exemplo <contabilidade@exemplo.org.br>", "Todos"),
            ("Administrativo CMD Exemplo <administrativo.cmd@exemplo.org.br>", "Todos CMD")]
MESES = [datetime(2026, m, 1) for m in range(1, 11)]


def _movimento(pasta: Path, estabelecimento: str) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / "Movimentos_NF_10_2026.csv"
    with caminho.open("w", encoding="utf-16-le", newline="") as arquivo:   # como o Tasy: UTF-16 sem BOM
        escritor = csv.writer(arquivo, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\r\n")
        escritor.writerow(TITULOS_MOVIMENTO)
        for numero, (aba, _conta, fornecedor, _desc, _resp, _ant, valor, conta_lancada, _tipo) in enumerate(
                CONTRATOS, start=101):
            if aba == estabelecimento and valor is not None:
                escritor.writerow(["Liberado", str(numero), "15/10/2026", f"{valor:.2f}".replace(".", ","),
                                   f"{fornecedor} NF {numero} DT10/10/2026", "70100", "D", "Despesa",
                                   "Estabelecimento Exemplo", conta_lancada])
    return caminho


def _checklist(caminho: Path, preenchidos: bool) -> Path:
    """preenchidos=True: o Check list depois de copiar os valores da conferência (para as pendências)."""
    livro = openpyxl.Workbook()
    livro.active.title = "Resumo"
    abas = {"SC": ("HOSPITAL EXEMPLO", ["Conta Contábil", "Descrição Conta", "Fornecedor", "Descrição da despesa",
                                  "Responsável"]),
            "CMD": ("CENTRO MULTIDISCIPLINAR", ["Conta", "Descrição Conta", "Fornecedor", "Descrição da despesa",
                                                "Responsável"])}
    planilhas = {}
    for chave, (nome, titulos) in abas.items():
        planilhas[chave] = livro.create_sheet(nome)
        planilhas[chave].append(titulos + MESES)
    for aba, conta, fornecedor, descricao, responsavel, anterior, valor, conta_lancada, tipo in CONTRATOS:
        outubro = valor if preenchidos and conta_lancada == conta and tipo == "auto" else None
        planilhas[aba].append([int(conta), "Despesa", fornecedor, descricao, responsavel]
                              + [None] * 8 + [anterior, outubro])
    emails = livro.create_sheet("Emails")
    for linha, (contato, codigos) in enumerate(CONTATOS, start=2):
        emails.cell(linha, 1, contato)
        emails.cell(linha, 2, codigos)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    livro.save(caminho)
    return caminho


def _regras(pasta: Path) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    linhas = {"SC": 1, "CMD": 1}
    with (pasta / "regras.csv").open("w", encoding="utf-8-sig", newline="") as arquivo:
        escritor = csv.writer(arquivo, delimiter=";")
        escritor.writerow(TITULOS_REGRAS)
        for aba, conta, fornecedor, descricao, _resp, _ant, _valor, _lancada, tipo in CONTRATOS:
            linhas[aba] += 1
            busca = "^" + " ".join(fornecedor.lower().split()[:2])
            escritor.writerow([aba, linhas[aba], fornecedor, descricao, conta, busca, "", "", "", tipo, ""])
    return pasta


def _mes(tela) -> None:
    tela.campo_mes.definir("10/2026")
    tela.atualizar_botoes()


def gerar(pasta: Path) -> list[Exemplo]:
    sc, cmd = _movimento(pasta / "Movimento Hospital Exemplo", "SC").parent, _movimento(pasta / "Movimento CMD", "CMD").parent
    configuracao = _regras(pasta / "configuracao")
    saida = pasta / "saida"
    saida.mkdir(parents=True, exist_ok=True)
    return [
        Exemplo("checklist_contratos", "checklist_contratos", "Conferência", "conferencia", {
            "cartao_sc": [sc], "cartao_cmd": [cmd],
            "cartao_checklist": [_checklist(pasta / "Check list 2026.xlsx", preenchidos=False)],
            "cartao_configuracao": [configuracao], "cartao_saida": [saida]},
            preparar=_mes, pasta_saida=saida, numeros=("3", "1", "1", "1")),
        Exemplo("checklist_contratos", "checklist_contratos_pendencias", "Pendências", "pendencias", {
            "cartao_checklist": [_checklist(pasta / "rede" / "Check list 2026.xlsx", preenchidos=True)],
            "cartao_saida": [saida]},
            preparar=_mes, pasta_saida=saida, numeros=("2", "1", "1")),
    ]
