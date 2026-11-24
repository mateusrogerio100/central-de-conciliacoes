"""Subvenções e Projetos: balancete (.xlsx), relatório "Patrimônio - Bens Subvenção" (.xlsx) e as
planilhas do mês anterior (Subvenções_Investimento com as abas Federal e Estadual, e Projetos).

Mostra: contas preenchidas, uma com o Saldo Patrimônio diferente do Contábil, uma conta sem bens no
patrimônio (recebe zero, com aviso), uma conta do patrimônio com um bem só e sem linha de Total (P2),
uma conta do patrimônio não usada e uma conta nova no balancete que ainda não está nas planilhas.
"""

from __future__ import annotations

import datetime
from pathlib import Path

import openpyxl

from manual.ficticios import Exemplo

# código, classificação, descrição, saldo atual (None = soma das analíticas)
CONTAS = [
    (23000, "2.02.06.01", "SUBVENÇÃO FEDERAL INVESTIMENTO", None),
    (24001, "2.02.06.01.0001", "Convênio Federal 900001/2020", 12500.00),
    (24002, "2.02.06.01.0002", "Convênio Federal 900002/2021", 8300.00),
    (24003, "2.02.06.01.0003", "Convênio Federal 900003/2022", 4000.00),
    (24004, "2.02.06.01.0004", "Convênio Federal 900004/2026", 900.00),      # nova: não está nas planilhas
    (23100, "2.02.06.03", "SUBVENÇÃO ESTADUAL INVESTIMENTO", None),
    (24101, "2.02.06.03.0001", "Convênio Estadual 100/2023", 6750.00),
    (23200, "2.02.06.04", "PROJETOS", None),
    (24201, "2.02.06.04.0001", "Projeto Exemplo Saúde 01/2024", 3200.00),
    (24202, "2.02.06.04.0002", "Projeto Exemplo Equipamentos 02/2025", 1500.00),   # sem bens no patrimônio
]
PATRIMONIO = [                                      # conta, bens (código, descrição, valor), com linha Total?
    ("Convênio Federal 900001/2020", [(5001, "Monitor multiparâmetro exemplo", 7500.00),
                                      (5002, "Cama hospitalar exemplo", 5000.00)], True),
    ("Convênio Federal 900002/2021", [(5003, "Autoclave exemplo", 6000.00),
                                      (5004, "Balança digital exemplo", 2150.00)], True),
    ("Convênio Federal 900003/2022", [(5005, "Desfibrilador exemplo", 4000.00)], False),
    ("Convênio Estadual 100/2023", [(5101, "Eletrocardiógrafo exemplo", 4250.00),
                                    (5102, "Cadeira de rodas exemplo", 2500.00)], True),
    ("Projeto Exemplo Saúde 01/2024", [(5201, "Notebook exemplo", 3200.00)], True),
    ("Bens em Comodato", [(5301, "Equipamento em comodato exemplo", 1000.00)], True),
]
PLANILHAS = {                                       # arquivo: {aba: (linha dos títulos, códigos)}
    "Subvenções_Investimento_08-2026.xlsx": {"Federal": (4, [24001, 24002, 24003]), "Estadual": (4, [24101])},
    "Projetos_08-2026.xlsx": {"Projetos": (8, [24201, 24202])},
}


def _saldo(classificacao: str, saldo):
    if saldo is not None:
        return saldo
    return sum(s for _, c, _, s in CONTAS if s is not None and c.startswith(classificacao + "."))


def _balancete(caminho: Path) -> Path:
    livro = openpyxl.Workbook()
    aba = livro.active
    aba["A1"] = "Fundação Exemplo de Misericórdia"
    aba["A2"] = "Balancete"
    aba["G3"] = "Mês Referência:"
    aba["I3"] = datetime.datetime(2026, 9, 1)
    for celula, texto in {"B4": "Código", "D4": "Classificação", "F4": "Descrição", "J4": "Saldo Anterior",
                          "L4": "Movimento", "M4": "Saldo Atual"}.items():
        aba[celula] = texto
    for linha, (codigo, classificacao, descricao, saldo) in enumerate(CONTAS, start=5):
        valor = _saldo(classificacao, saldo)
        aba.cell(linha, 3, codigo)
        aba.cell(linha, 5, classificacao)
        aba.cell(linha, 6, descricao)
        aba.cell(linha, 10, valor)
        aba.cell(linha, 13, valor)
    aba.cell(len(CONTAS) + 6, 2, "Impresso em: 01/10/2026 08:00:00")
    aba.cell(len(CONTAS) + 6, 8, "Página: 1")
    caminho.parent.mkdir(parents=True, exist_ok=True)
    livro.save(caminho)
    return caminho


def _patrimonio(caminho: Path) -> Path:
    linhas = [{1: "Patrimônio - Bens Subvenção"}, {10: "Data: 01/09/26 à 30/09/26"},
              {3: "Conta Subvenção", 4: "Cód Bem", 5: "Descrição", 7: "Valor Contábil", 9: "Deprec Mês"}]
    quantidade, soma = 0, 0.0
    for nome, bens, com_total in PATRIMONIO:
        linhas.append({3: nome})
        linhas += [{4: codigo, 5: descricao, 7: valor, 9: 0} for codigo, descricao, valor in bens]
        if com_total:
            linhas.append({2: f"Total - {nome}({len(bens)})", 7: sum(b[2] for b in bens), 9: 0})
        quantidade, soma = quantidade + len(bens), soma + sum(b[2] for b in bens)
    linhas += [{2: f"Total({quantidade})", 7: soma, 9: 0},
               {3: "Impresso em:  01/10/2026 08:00:00", 6: "Página   1", 8: "Usuario", 11: "CPAT2271"}]
    livro = openpyxl.Workbook()
    aba = livro.active
    for numero, linha in enumerate(linhas, start=1):
        for coluna, valor in linha.items():
            aba.cell(numero, coluna, valor)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    livro.save(caminho)
    return caminho


def _planilha(caminho: Path, abas: dict) -> Path:
    descricoes = {codigo: descricao for codigo, _, descricao, _ in CONTAS}
    livro = openpyxl.Workbook()
    livro.remove(livro.active)
    for nome_aba, (linha_titulos, codigos) in abas.items():
        aba = livro.create_sheet(nome_aba)
        aba.cell(1, 1, f"Controle de {nome_aba} — exemplo")
        for coluna, titulo in enumerate(["Conta Contábil", "Convênio", "Saldo Patrimônio", "Saldo Contábil"], 1):
            aba.cell(linha_titulos, coluna, titulo)
        primeira = linha_titulos + 1
        for deslocamento, codigo in enumerate(codigos):
            linha = primeira + deslocamento
            aba.cell(linha, 1, codigo)
            aba.cell(linha, 2, descricoes[codigo].replace("Convênio ", "TC ").replace("Projeto Exemplo ", ""))
            aba.cell(linha, 3, 0)
            aba.cell(linha, 4, 0)
        total = primeira + len(codigos)
        ultima = total - 1
        aba.cell(total, 2, "Total")
        aba.cell(total, 3, f"=SUM(C{primeira}:C{ultima})")
        aba.cell(total, 4, f"=SUM(D{primeira}:D{ultima})")
    caminho.parent.mkdir(parents=True, exist_ok=True)
    livro.save(caminho)
    return caminho


def gerar(pasta: Path) -> list[Exemplo]:
    planilhas = [_planilha(pasta / "planilhas de agosto" / nome, abas) for nome, abas in PLANILHAS.items()]
    saida = pasta / "saida"
    saida.mkdir(parents=True, exist_ok=True)
    return [Exemplo("subvencoes", "subvencoes", "Preenchimento", "preenchimento", {
        "cartao_balancete": [_balancete(pasta / "Balancete subvenções set2026.xlsx")],
        "cartao_patrimonio": [_patrimonio(pasta / "Patrimonio bens subvencao set2026.xlsx")],
        "cartao_planilhas": planilhas, "cartao_saida": [saida]}, preparar=_esperar_mes,
        pasta_saida=saida, numeros=("6", "2", "3"))]


def _esperar_mes(tela) -> None:
    """O mês do balancete é lido em segundo plano: espera ele chegar ao campo antes de clicar em Preencher."""
    from manual.ficticios.aplicar import esperar

    esperar(tela, lambda: bool(tela.campo_mes.valor().strip()))
