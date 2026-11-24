"""Planilha HM: o Eventos de set/2026 (no formato da aba Plan1, como o relatório sai do Tasy), o Movimento do lote
de Repasse a terceiros (.csv UTF-16) e a Planilha HM de agosto.

Mostra: 5 eventos, um centro de custo novo num evento que já existe (R4), um evento novo que entra na seção de
fixos pela conta dele no Movimento (R5, tabela conta → seção montada na primeira vez) e o TOTAL GERAL fechando
com o Movimento.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import openpyxl
from openpyxl.utils import get_column_letter

from manual.ficticios import Exemplo

ANO, MES = 2026, 9
MESES = ["JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO",
         "NOVEMBRO", "DEZEMBRO"]
SECOES = [  # (seção, total, [(evento, nome, [(cód. do CC, centro de custo)])])
    ("HONORÁRIOS MÉDICOS - FIXOS", "TOTAL HM FIXOS",
     [(1001, "HM Plantão Exemplo", [(10, "Pronto Socorro Exemplo"), (20, "UTI Exemplo")]),
      (1002, "HM Consulta Exemplo", [(10, "Pronto Socorro Exemplo")])]),
    ("HONORÁRIOS MÉDICOS - PRODUÇÃO", "TOTAL HM PRODUÇÃO",
     [(1101, "HM Produção Exemplo", [(30, "Centro Cirúrgico Exemplo")])]),
    ("HM DESCONTOS", "TOTAL DESCONTOS", [(2001, "Desconto Exemplo", [(30, "Centro Cirúrgico Exemplo")])]),
]
FIXOS = ("30001", "Honorários Médicos Exemplo Fixos PJ", "3.9.01.0001")
PRODUCAO = ("30002", "Honorários Médicos Exemplo Produção PJ", "3.9.01.0002")
MEDICO = ("20001", "Médico Exemplo", "2.9.01.0001")
EVENTOS = [  # (evento, nome, sinal, código do histórico, [(cód. do CC, centro de custo, valor)], conta, histórico)
    (1001, "HM Plantão Exemplo", "(+)", 901,
     [(10, "Pronto Socorro Exemplo", 18500.00), (20, "UTI Exemplo", 12300.00), (40, "Maternidade Exemplo", 4200.00)],
     FIXOS, "HM Plantão Exemplo (Evento 1001)"),
    (1002, "HM Consulta Exemplo", "(+)", 902, [(10, "Pronto Socorro Exemplo", 9750.40)], FIXOS,
     "HM Consulta Exemplo (Evento 1002)"),
    (1101, "HM Produção Exemplo", "(+)", 903, [(30, "Centro Cirúrgico Exemplo", 23880.15)], PRODUCAO,
     "HM Produção Exemplo (Evento 1101)"),
    (2001, "Desconto Exemplo", "(-)", 904, [(30, "Centro Cirúrgico Exemplo", 1250.00)], MEDICO, "Desconto Exemplo"),
    (1003, "HM Sobreaviso Exemplo", "(+)", 905, [(20, "UTI Exemplo", 6400.00)], FIXOS,
     "HM Sobreaviso Exemplo (Evento 1003)"),
]


def _br(valor: float) -> str:
    return f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _eventos(caminho: Path) -> Path:
    livro = openpyxl.Workbook()
    aba = livro.active
    aba.title = "Plan1"
    competencia = datetime(ANO, MES, 1)
    aba.append([None] * 10 + ["Pág.:", 1])
    aba.append([None, "Conferência Lançamentos Contábeis"])
    aba.append([None, None, None, None, "Competência:", competencia, "a", competencia])
    for numero, nome, sinal, historico, ccs, _, _ in EVENTOS:
        aba.append(["Evento:", str(numero), nome, None, None, sinal])
        aba.append(["Médico"] + [None] * 5 + ["Conta Contábil"] + [None] * 4 + ["Valor"])
        for codigo, centro, valor in ccs:
            aba.append([numero, f"Médico Exemplo {numero}", None, None, None, None, "20001", None, historico, None,
                        _br(valor)])
            aba.append([None] * 5 + [str(codigo), centro, None, None, None, _br(valor)])
        aba.append([None, "Total Evento", str(numero), nome, None, None, None, "30001", historico, None,
                    _br(sum(v for *_, v in ccs))])
    aba.append([None] * 10 + [_br(sum(v for e in EVENTOS for *_, v in e[4]))])
    livro.save(caminho)
    return caminho


def _movimento(caminho: Path) -> Path:
    titulos = ["Status", "Fato contábil", "Sequência", "Data movimento", "Débito", "Crédito", "Valor", "Histórico",
               "Complemento", "Conta débito", "Conta crédito", "Histórico", "Revisado", "Classificação débito",
               "Classificação crédito"]
    linhas = [titulos]
    for _, _, _, historico, ccs, (debito, conta, classificacao), texto in EVENTOS:
        linhas.append(["Não revisado", "70001", "1", f"30/{MES:02d}/{ANO}", debito, "1",
                       _br(sum(v for *_, v in ccs)), str(historico), "0926", conta, "Médico Exemplo", texto,
                       "Não revisado", classificacao, "2.9.01.0001"])
    texto = "\r\n".join(";".join(f'"{c}"' for c in linha) for linha in linhas) + "\r\n"
    caminho.write_bytes(texto.encode("utf-16-le"))
    return caminho


def _planilha(caminho: Path) -> Path:
    """O mesmo desenho da Planilha HM: seções com a linha de abertura, eventos (D vazia) e CCs, totais, TOTAL GERAL,
    LOTE REPASSE e uma aba Senior por mês (a de agosto preenchida)."""
    livro = openpyxl.Workbook()
    aba = livro.active
    aba.title = str(ANO)
    L = get_column_letter
    meses = {m: 5 + m for m in range(1, 13)}                # F (janeiro) a Q (dezembro)
    aba["B1"] = f"RELATÓRIO MENSAL HONORÁRIOS MÉDICOS - {ANO}"
    linha, totais = 6, []
    for secao, nome_total, eventos in SECOES:
        for coluna, texto in enumerate(["EVENTO", secao, "Concateno", "Cód.", "Centros de Custos"], start=1):
            aba.cell(linha, coluna, texto)
        for m, c in meses.items():
            aba.cell(linha, c, MESES[m - 1])
        linha += 1
        linhas_eventos = []
        for numero, nome, ccs in eventos:
            for codigo, centro in [(None, None), *ccs]:
                aba.cell(linha, 1, str(numero))
                aba.cell(linha, 2, nome)
                aba.cell(linha, 3, f"=A{linha}&D{linha}")
                if codigo is not None:
                    aba.cell(linha, 4, str(codigo))
                    aba.cell(linha, 5, centro)
                chave = "$A:$A" if codigo is None else "$F:$F"
                for m, c in meses.items():
                    senior = f"'Senior {m:02d} {ANO}'"
                    aba.cell(linha, c, f"=SUMIF({senior}!{chave},$C{linha},{senior}!$D:$D)")
                if codigo is None:
                    linhas_eventos.append(linha)
                linha += 1
        aba.cell(linha, 2, nome_total)
        for c in meses.values():
            aba.cell(linha, c, "=SUM(" + "+".join(f"{L(c)}{l}" for l in linhas_eventos) + ")")
        totais.append(linha)
        linha += 1
    aba.cell(linha, 2, "TOTAL GERAL")
    for c in meses.values():
        aba.cell(linha, c, "=" + "+".join(f"{L(c)}{l}" for l in totais))
    total_geral, lote = linha, linha + 3
    aba.cell(lote, 1, "LOTE REPASSE")
    aba.cell(lote, meses[8], 70250.30)
    for c in meses.values():
        aba.cell(lote + 1, c, f"={L(c)}{total_geral}-{L(c)}{lote}")
    agosto = [(1001, 10, "Pronto Socorro Exemplo", 18000.00), (1001, 20, "UTI Exemplo", 12000.00),
              (1002, 10, "Pronto Socorro Exemplo", 9500.30), (1101, 30, "Centro Cirúrgico Exemplo", 31950.00),
              (2001, 30, "Centro Cirúrgico Exemplo", 1200.00)]
    for m in range(1, 13):
        senior = livro.create_sheet(f"Senior {m:02d} {ANO}")
        senior.append(["Evento", "Cód.", "Centro de custo", "Valor", None, "Concateno", "Conf.", "Conf.1"])
        dados = agosto if m == 8 else []
        for i in range(2, 2 + max(len(dados), 3)):
            if i - 2 < len(dados):
                for coluna, valor in enumerate(dados[i - 2], start=1):
                    senior.cell(i, coluna, valor)
            senior.cell(i, 6, f"=A{i}&B{i}")
            senior.cell(i, 7, f"=VLOOKUP(F{i},'{ANO}'!C:C,1,0)")
            senior.cell(i, 8, f"=F{i}=G{i}")
    livro.save(caminho)
    return caminho


def gerar(pasta: Path) -> list[Exemplo]:
    pasta.mkdir(parents=True, exist_ok=True)
    tabela = pasta / "config" / "secoes_contas.csv"
    if tabela.exists():                                    # o print mostra a tabela montada na primeira vez
        tabela.unlink()
    eventos = _eventos(pasta / "Eventos 09-2026.xlsx")
    movimento = _movimento(pasta / "Movimento lote 70001.csv")
    planilha = _planilha(pasta / "08 Planilha HM 2026 Atualizada em 23-09-2026 COMPETENCIA 08.xlsx")
    saida = pasta / "saida"
    saida.mkdir(exist_ok=True)
    return [Exemplo("planilha_hm", "planilha_hm", "Preenchimento", "preenchimento",
                    {"cartao_eventos": [eventos], "cartao_movimento": [movimento], "cartao_planilha": [planilha],
                     "cartao_saida": [saida]},
                    pasta_saida=saida, numeros=("5", "3", "0"))]
