"""Imobilizado – AME's: razão auxiliar (6051), os três balancetes (865), bens adquiridos (555) e baixas
(561), como saem do Tasy (.xls que é texto separado por tabulação).

Mostra: contas que conferem, uma diferença explicada pelos bens adquiridos, uma explicada pela baixa
e uma diferença de centavos sem explicação.
"""

from __future__ import annotations

from pathlib import Path

from manual.ficticios import Exemplo
from manual.ficticios.tasy import numero_br, texto_tasy

AME = "Ame - Cidade Exemplo ( Fund. Hospital Exemplo )"
MES = "ago/2026"

# código, nome, saldo anterior, entradas, baixas, saldo atual (razão) e o saldo do balancete
CONTAS = [
    ("11060", "Softwares AME", 15000.00, 0, 0, 15000.00, 15000.00),
    ("11038", "Aparelhos de informática AME", 100000.00, 2500.00, 0, 102500.00, 100000.00),
    ("11042", "Equipamentos hospitalares AME", 350000.00, 0, 1200.00, 348800.00, 350000.00),
    ("11047", "Máquinas e equipamentos AME", 80000.00, 0, 0, 80000.00, 80000.00),
    ("11049", "Instrumentos médicos AME", 12000.00, 0, 0, 12000.00, 11999.97),
    ("11050", "Móveis e utensílios AME", 45320.00, 0, 0, 45320.00, 45320.00),
    ("11070", "Equipamentos em cessão de uso AME", 60000.00, 0, 0, 60000.00, 60000.00),
]
BALANCETES = {                                # arquivo: (conta-mãe, classificação, descrição, contas)
    "intangivel_ago2026.xls": ("1330", "1.02.06.01", "INTANGÍVEL AMBULATÓRIO", ["11060"]),
    "imobilizado_ago2026.xls": ("1320", "1.02.05.06", "IMOBILIZADO AMBULATÓRIO",
                                ["11038", "11042", "11047", "11049", "11050"]),
    "cessao_ago2026.xls": ("1340", "1.02.05.08", "BENS EM CESSÃO DE USO", ["11070"]),
}


def _bloco_razao(codigo, nome, anterior, entradas, baixas, atual):
    return [
        ["", f"{codigo} - {nome}", "", ""],
        ["", "Saldo anterior", numero_br(anterior), "", "", "", "Deprec mes anterior", "", "", "0,00"],
        ["", "Entradas", numero_br(entradas), "", "", "", "Deprec mes", "", "", "0,00"],
        ["", "Baixas", numero_br(baixas), "", "", "", "Baixa deprec", "", "", "0,00"],
        ["", "Transf bem (entrada)", "0,00"],
        ["", "Transf bem (saída)", "0,00"],
        ["", "Saldo atual", numero_br(atual), "", "", "", "Deprec acum mes", "", "", "0,00"],
        ["", "Valor contábil liquido", numero_br(atual), "", "", "", "Situação", "", "", "", "", "ATIVO"],
    ]


def _razao(pasta: Path) -> Path:
    linhas = [["", "", ""], ["Patrimônio - Razão auxiliar (NOVO)", "", ""],
              ["", "", "", "Data referência", "", "01/08/2026"]]
    for codigo, nome, anterior, entradas, baixas, atual, _ in CONTAS:
        linhas += _bloco_razao(codigo, nome, anterior, entradas, baixas, atual)
    totais = [sum(c[i] for c in CONTAS) for i in (2, 3, 4, 5)]
    linhas += [["", "  Total Geral"]] + _bloco_razao("0", "x", *totais)[1:]
    linhas += [["", "Impresso em:  06/09/2026 14:32:59", "", "Página   1", "", "CATE6051"]]
    return texto_tasy(pasta / "patrimonio_razao_6051_ago2026.xls", linhas)


def _balancete(pasta: Path, nome: str, mae: str, classificacao: str, descricao: str, codigos: list[str]) -> Path:
    contas = [c for c in CONTAS if c[0] in codigos]
    linhas = [
        [AME, "", ""], ["Balancete", "", ""], ["", "", "", "", "", "", "Mês Referência:", "", "", MES],
        ["", "Código", "", "Classificação", "", "Descrição", "", "", "Saldo Anterior", "",
         "Débitos", "", "Créditos", "Saldo Atual", ""],
        ["", "Ativo"],
    ]
    total = numero_br(sum(c[6] for c in contas))
    linhas.append(["", "", mae, "", classificacao, "", "   " + descricao, "", "", total, "", "0,00", "", "0,00",
                   total, ""])
    for posicao, (codigo, descricao_conta, *_, saldo) in enumerate(contas, start=1):
        valor = numero_br(saldo)
        linhas.append(["", "", codigo, "", f"{classificacao}.{posicao:04d}", "", "      " + descricao_conta, "", "",
                       valor, "", "0,00", "", "0,00", valor, ""])
    linhas.append(["", "Impresso em: 06/09/2026 14:37:41", "", "", "", "", "", "Página: 1", "",
                   "", "", "USUARIO", "", "", "WEXE001"])
    return texto_tasy(pasta / nome, linhas)


def _bens(pasta: Path) -> Path:
    linhas = [
        ["Patrimonio - Bens adquiridos no período por centro custo", ""],
        ["", "", "", "", "", "Bens adquiridos de:", "", "01/08/2026", "até:  ", "", "31/08/2026"],
        ["", "Centro", "Conta", "Código Bem", "Descrição Bem", "", "", "", "", "", "",
         "Dt. Aquisição", "Dt. Início ", "", "Taxa Deprec", "Vl original"],
        ["", "10 - Administrativo Exemplo"],
        ["", "", "11038 Aparelhos de informática AME"],
        ["", "", "", "AME1201", "Notebook exemplo", "", "", "", "", "", "", "18/08/2026", "18/08/2026", "",
         "0,00", "2.500,00"],
        ["Total(1)"] + [""] * 14 + ["2.500,00"],
        ["", "Impresso em:  06/09/2026 14:42:10", "", "", "", "", "Página   1", "", "", "USUARIO", "", "", "",
         "UEXE001"],
    ]
    return texto_tasy(pasta / "bens_adquiridos_555_ago2026.xls", linhas)


def _baixas(pasta: Path) -> Path:
    conta = "Equipamentos hospitalares AME"
    linhas = [
        [""] * 10 + ["RESPONSÁVEL: ________"],
        [""] * 10 + ["PATRIMÔNIO:________"],
        ["", "", "", "", "BAIXA DE BENS DO ATIVO IMOBILIZADO"],
        ["", "", AME],
        ["CHAPA", "IMOBILIZADO", "", "", "", "", "TIPO", "MOTIVO", "", "VL. ORIGEM", "", "VL. DEPREC.", "",
         "VL. ATUAL", "DATA"],
        [conta],
        ["AME0907", "", "", "Monitor multiparâmetro exemplo", "", "", "Baixa", "Processo: 1", "", "1.200,00", "",
         "0,00", "", "1.200,00", "12/08/2026"],
        [f"Total - {conta}(1)"] + [""] * 9 + ["1.200,00"],
        ["Total(1)"] + [""] * 9 + ["1.200,00"],
        ["", "Impresso em:  06/09/2026 16:12:33", "", "", "", "", "Página   1"],
    ]
    return texto_tasy(pasta / "baixa_de_bens_561_ago2026.xls", linhas)


def gerar(pasta: Path) -> list[Exemplo]:
    balancetes = [_balancete(pasta, nome, *dados) for nome, dados in BALANCETES.items()]
    saida = pasta / "saida"
    saida.mkdir(parents=True, exist_ok=True)
    return [Exemplo("conciliacao_imobilizado", "imobilizado", "Conciliação", "conciliacao", {
        "cartao_razao": [_razao(pasta)], "cartao_balancetes": balancetes, "cartao_bens": [_bens(pasta)],
        "cartao_baixas": [_baixas(pasta)], "cartao_pasta": [saida]}, pasta_saida=saida, numeros=("4", "2", "1"))]
