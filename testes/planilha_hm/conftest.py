"""Apoio dos testes do módulo Planilha HM.

Os exemplos reais (Eventos, Movimento e Planilha HM de ago e set/2026, com os gabaritos) ficam em
exemplos\\planilha_hm\\, fora do git: têm nomes de médicos. Sem a pasta, os testes que dependem dela são
pulados. Os demais usam arquivos fictícios montados aqui (nenhum nome real).
"""

from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import openpyxl

from testes.conftest import pasta_exemplos


def exemplos(*subpastas: str) -> Path:
    """exemplos\\planilha_hm\\<subpastas>; pula sem a pasta."""
    return pasta_exemplos("planilha_hm", *subpastas)


def gabarito_senior(mes: str) -> Counter:
    """gabarito_senior_<AAAA-MM>.csv como contagem de (evento, cód. do CC, nome do CC, valor): sem depender da
    ordem (decisão do usuário, 30/10/2026)."""
    with open(exemplos(mes, "gabarito") / f"gabarito_senior_{mes}.csv", encoding="utf-8-sig") as arquivo:
        return Counter((int(l["evento"]), l["cod_centro"], l["centro_custo"], Decimal(l["valor"].replace(",", ".")))
                       for l in csv.DictReader(arquivo, delimiter=";"))


# ---------------------------------------------------------------------------
# Eventos fictício, no formato da aba Plan1 (colunas espalhadas, valores em texto "57,03-")
# ---------------------------------------------------------------------------

def _valor_texto(valor: float) -> str:
    texto = f"{abs(valor):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{texto}-" if valor < 0 else texto


def cabecalho_pagina(pagina: int = 1, competencia=datetime(2026, 9, 1)) -> list[list]:
    return [[None] * 10 + ["Pág.:", pagina],
            [None, "Conferência Lançamentos Contábeis"],
            [None, None, None, None, "Competência:", competencia, "a", competencia]]


def rodape() -> list:
    return ["FPTE119.COL  -  01/10/2026  -  08:00:00      FUNDAÇÃO EXEMPLO      Usuário: exemplo"]


def evento(numero: int, nome: str, sinal: str = "(+)") -> list[list]:
    return [["Evento:", str(numero), nome, None, None, sinal],
            ["Médico"] + [None] * 5 + ["Conta Contábil"] + [None] * 4 + ["Valor"]]


def medico(codigo: int, valor: float, historico: int = 900) -> list:
    return [codigo, f"Medico Exemplo {codigo}", None, None, None, None, "20001", None, historico, None,
            _valor_texto(valor)]


def subtotal(codigo: int, nome: str, valor: float) -> list:
    return [None] * 5 + [str(codigo), nome, None, None, None, _valor_texto(valor)]


def total_evento(numero: int, nome: str, valor: float, historico: int = 900) -> list:
    return [None, "Total Evento", str(numero), nome, None, None, None, "30001", historico, None, _valor_texto(valor)]


def total_relatorio(valor: float) -> list:
    return [None] * 10 + [_valor_texto(valor)]


def escrever_eventos(caminho: Path, *blocos: list[list], cabecalho=None) -> Path:
    livro = openpyxl.Workbook()
    aba = livro.active
    aba.title = "Plan1"
    for linha in [*(cabecalho if cabecalho is not None else cabecalho_pagina())]:
        aba.append(linha)
    for bloco in blocos:
        for linha in bloco:
            aba.append(linha)
    livro.save(caminho)
    return caminho


def gabarito_totais(mes: str) -> list[tuple[int, str]]:
    """gabarito_totais_<AAAA-MM>.csv: (linha, nome) de cada total, do TOTAL GERAL e do LOTE REPASSE."""
    with open(exemplos(mes, "gabarito") / f"gabarito_totais_{mes}.csv", encoding="utf-8-sig") as arquivo:
        return [(int(l["linha"]), l["total"]) for l in csv.DictReader(arquivo, delimiter=";")]


def planilha_real(mes: str) -> Path:
    """A Planilha HM de entrada de setembro (= a de agosto pronta) ou o gabarito de setembro."""
    if mes == "2026-08":
        return exemplos("2026-09") / "08 Planilha HM 2026 Atualizada em 23-09-2026 COMPETENCIA 08.xlsx"
    return exemplos("2026-09", "gabarito") / "09 Planilha HM 2026 Atualizada em 29-10-2026 COMPETENCIA 09.xlsx"


# ---------------------------------------------------------------------------
# Planilha HM fictícia (mesmo desenho da aba "2026" e das abas Senior)
# ---------------------------------------------------------------------------

MESES = ["JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO",
         "NOVEMBRO", "DEZEMBRO"]
SECOES_FICTICIAS = [
    ("HONORÁRIOS MÉDICOS - FIXOS", "TOTAL HM FIXOS", [(1001, "HM Exemplo A", [(10, "Centro Alfa"), (20, "Centro Beta")]),
                                                     (1002, "HM Exemplo B", [(10, "Centro Alfa")])]),
    ("HONORÁRIOS MÉDICOS - VAZIA", None, []),
    ("HM DESCONTOS", "TOTAL DESCONTOS", [(2001, "Desconto Exemplo", [(None, "A Classificar"), (30, "Centro Gama")])]),
]


def escrever_planilha(caminho: Path, secoes=SECOES_FICTICIAS, ano: int = 2026, deslocar: int = 0,
                      senior_com_dados: dict[int, int] | None = None, abas_senior=range(1, 13),
                      total_errado: bool = False) -> Path:
    """Planilha HM fictícia. deslocar: colunas vazias antes de EVENTO (para provar que nada depende da letra).
    senior_com_dados: {mês: quantas linhas de dados}. total_errado: o total da 1ª seção esquece um evento."""
    from openpyxl.utils import get_column_letter

    livro = openpyxl.Workbook()
    aba = livro.active
    aba.title = str(ano)
    d = deslocar
    col = {nome: d + i for i, nome in enumerate(["EVENTO", "nome", "Concateno", "Cód.", "Centros"], start=1)}
    meses = {m: d + 5 + m for m in range(1, 13)}
    letra = get_column_letter
    aba.cell(1, col["nome"], f"RELATÓRIO MENSAL HONORÁRIOS MÉDICOS - {ano}")
    linha = 6
    totais = []
    for nome_secao, nome_total, eventos in secoes:
        aba.cell(linha, col["EVENTO"], "EVENTO")
        aba.cell(linha, col["nome"], nome_secao)
        aba.cell(linha, col["Concateno"], "Concateno")
        aba.cell(linha, col["Cód."], "Cód.")
        aba.cell(linha, col["Centros"], "Centros de Custos")
        for m, c in meses.items():
            aba.cell(linha, c, MESES[m - 1])
        linha += 1
        linhas_eventos = []
        for numero, nome, ccs in eventos:
            for cc, nome_cc in [(None, None), *ccs]:
                aba.cell(linha, col["EVENTO"], str(numero))
                aba.cell(linha, col["nome"], nome)
                aba.cell(linha, col["Concateno"], f"={letra(col['EVENTO'])}{linha}&{letra(col['Cód.'])}{linha}")
                if cc is not None:
                    aba.cell(linha, col["Cód."], str(cc))
                if nome_cc is not None:
                    aba.cell(linha, col["Centros"], nome_cc)
                chave = "$A:$A" if nome_cc is None else "$G:$G"
                for m, c in meses.items():
                    senior = f"'Senior {m:02d} {ano}'"
                    aba.cell(linha, c, f"=SUMIF({senior}!{chave},${letra(col['Concateno'])}{linha},{senior}!$D:$D)")
                if nome_cc is None:
                    linhas_eventos.append(linha)
                linha += 1
        if nome_total:
            somadas = linhas_eventos[1:] if total_errado and not totais else linhas_eventos
            aba.cell(linha, col["nome"], nome_total)
            for m, c in meses.items():
                aba.cell(linha, c, "=SUM(" + "+".join(f"{letra(c)}{l}" for l in somadas) + ")")
            totais.append(linha)
            linha += 1
    aba.cell(linha, col["nome"], "TOTAL GERAL")
    for m, c in meses.items():
        aba.cell(linha, c, "=" + "+".join(f"{letra(c)}{l}" for l in totais))
    total_geral = linha
    lote = linha + 3
    aba.cell(lote, col["EVENTO"], "LOTE REPASSE")
    aba.cell(lote, meses[8], 12345.67)
    for m, c in meses.items():
        aba.cell(lote + 1, c, f"={letra(c)}{total_geral}-{letra(c)}{lote}")
    for m in abas_senior:
        s = livro.create_sheet(f"Senior {m:02d} {ano}")
        s.append(["Evento", "Cód.", "Centro de custo", "Valor", None, "Concateno", "Conf.", "Conf.1"])
        for i in range(2, 2 + max((senior_com_dados or {}).get(m, 0), 3)):
            if i - 2 < (senior_com_dados or {}).get(m, 0):
                s.cell(i, 1, 1001)
                s.cell(i, 2, 10)
                s.cell(i, 3, "Centro Alfa")
                s.cell(i, 4, 1.5)
            s.cell(i, 6, f"=A{i}&B{i}")
            s.cell(i, 7, f"=VLOOKUP(F{i},'{ano}'!C:C,1,0)")
            s.cell(i, 8, f"=F{i}=G{i}")
    livro.save(caminho)
    return caminho


# ---------------------------------------------------------------------------
# Movimento fictício (.csv UTF-16 sem BOM, como o Tasy exporta)
# ---------------------------------------------------------------------------

TITULOS_MOVIMENTO = ["Status", "Fato contábil", "Sequência", "Data movimento", "Débito", "Crédito", "Valor",
                     "Histórico", "Complemento", "Conta débito", "Conta crédito", "Histórico", "Revisado",
                     "Classificação débito", "Classificação crédito"]


def lancamento(valor: str, historico: str, debito: str = "", credito: str = "", conta_debito: str = "",
               classificacao_debito: str = "", codigo_historico: str = "900", data: str = "30/09/2026",
               lote: str = "70001") -> list[str]:
    return ["Não revisado", lote, "1", data, debito, credito, valor, codigo_historico, "0926", conta_debito,
            "Medico Exemplo" if credito else "", historico, "Não revisado", classificacao_debito,
            "2.01.03.02.0001" if credito else ""]


def escrever_movimento(caminho: Path, *linhas: list[str], titulos=TITULOS_MOVIMENTO, bom: bool = False) -> Path:
    texto = "\r\n".join(";".join(f'"{c}"' for c in linha) for linha in [titulos, *linhas]) + "\r\n"
    caminho.write_bytes(texto.encode("utf-16" if bom else "utf-16-le"))
    return caminho


# ---------------------------------------------------------------------------
# Caso fictício completo (PlanilhaHM 4 e 5)
# ---------------------------------------------------------------------------

CONTA_FIXOS = dict(debito="30001", conta_debito="Conta Exemplo Fixos PJ", classificacao_debito="3.9.01.0001")
CONTA_MEDICO = dict(debito="20001", conta_debito="Medico Exemplo", classificacao_debito="2.9.01.0001")
CONTA_NOVA = dict(debito="30002", conta_debito="Conta Exemplo Nova PJ", classificacao_debito="3.9.02.0001")


def bloco_evento(numero, nome, ccs, historico, sinal="(+)", total=None):
    linhas = [*evento(numero, nome, sinal)]
    for codigo, nome_cc, valor in ccs:
        linhas += [medico(numero, valor), subtotal(codigo, nome_cc, valor)]
    linhas.append(total_evento(numero, nome, sum(v for *_, v in ccs) if total is None else total, historico))
    return linhas


def escrever_caso_ficticio(tmp_path: Path, total_1002=None, data="30/09/2026", **opcoes_planilha):
    """O caso fictício completo de set/2026: (planilha, eventos, movimento). Planilha = SECOES_FICTICIAS; o 1001
    ganha o CC 40 (R4); o 1003 é novo e a conta dele já é de FIXOS; o 1004 é novo, com conta fora das seções."""
    planilha = escrever_planilha(tmp_path / "planilha.xlsx", **opcoes_planilha)
    eventos = escrever_eventos(
        tmp_path / "eventos.xlsx",
        bloco_evento(1001, "HM Exemplo A",
                     [(10, "Centro Alfa", 100), (20, "Centro Beta", 50), (40, "Centro Delta", 25)], 901),
        bloco_evento(1002, "HM Exemplo B", [(10, "Centro Alfa", 200)], 902, total=total_1002),
        bloco_evento(2001, "Desconto Exemplo", [(30, "Centro Gama", 30)], 903, "(-)"),
        bloco_evento(1003, "HM Exemplo Novo", [(10, "Centro Alfa", 60)], 904),
        bloco_evento(1004, "HM Exemplo Outra Conta", [(50, "Centro Epsilon", 40)], 905))
    movimento = escrever_movimento(
        tmp_path / "movimento.csv",
        lancamento("175,00", "Pagamento HM", credito="1", codigo_historico="901", data=data, **CONTA_FIXOS),
        lancamento("200,00", "HM Exemplo B (Evento 1002)", credito="1", codigo_historico="902", data=data,
                   **CONTA_FIXOS),
        lancamento("30,00", "Desconto", credito="2", codigo_historico="903", data=data, **CONTA_MEDICO),
        lancamento("60,00", "HM Exemplo Novo (Evento 1003)", credito="1", codigo_historico="904", data=data,
                   **CONTA_FIXOS),
        lancamento("40,00", "Evento 1004 - HM Exemplo Outra Conta", credito="1", codigo_historico="905", data=data,
                   **CONTA_NOVA))
    return planilha, eventos, movimento
