"""Apoio dos testes do módulo Notas de Contrato.

Os exemplos reais (movimentos, Check list, configuração e gabaritos) ficam em
exemplos\\conferencias_notas_contratos\\checklist_contratos\\, fora do git. Sem a pasta, os testes
que dependem dela são pulados.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import openpyxl

from testes.conftest import pasta_exemplos

PASTA_EXEMPLOS_MODULO = ("conferencias_notas_contratos", "checklist_contratos")


def exemplos(*subpastas: str) -> Path:
    """exemplos\\conferencias_notas_contratos\\checklist_contratos\\<subpastas>; pula sem a pasta."""
    return pasta_exemplos(*PASTA_EXEMPLOS_MODULO, *subpastas)


TITULOS_MOVIMENTO = ["Status", "Lançamento", "Data movimento", "Conta débito", "Conta crédito", "Valor",
                     "Complemento", "Lote contábil", "Débito/Crédito", "Conta", "Estabelecimento",
                     "Conta contábil"]


def escrever_movimento(caminho: Path, linhas: list[dict], titulos: list[str] = TITULOS_MOVIMENTO) -> Path:
    """Grava um .csv como o Tasy: UTF-16 sem marca, ';', tudo entre aspas."""
    def campo(texto) -> str:
        return '"' + str(texto).replace('"', '""') + '"'

    padrao = {"Status": "Liberado", "Lançamento": "1", "Data movimento": "01/10/2026",
              "Conta débito": "", "Conta crédito": "", "Valor": "100", "Complemento": "",
              "Lote contábil": "70000", "Débito/Crédito": "D", "Conta": "Conta Exemplo",
              "Estabelecimento": "Estabelecimento Exemplo", "Conta contábil": "30091"}
    texto = ";".join(campo(t) for t in titulos) + "\r\n"
    for linha in linhas:
        dados = {**padrao, **linha}
        texto += ";".join(campo(dados.get(t, "")) for t in titulos) + "\r\n"
    caminho.write_bytes(texto.encode("utf-16-le"))
    return caminho


def escrever_checklist(caminho: Path, meses_sc=None, meses_cmd=None, linhas_sc=None, linhas_cmd=None,
                       emails=None) -> Path:
    """Check list fictício com as duas abas (títulos como os de verdade) e a aba Emails."""
    meses_sc = meses_sc or [(2026, m) for m in range(1, 11)]
    meses_cmd = meses_cmd or [(2026, m) for m in (1, 2, 3, 4, 5, 6, 8, 9, 10)]       # sem jul, como o de verdade
    planilha = openpyxl.Workbook()
    planilha.active.title = "2016 (2)"
    abas = (
        ("HOSPITAL EXEMPLO", ["Conta Contábil", "Descrição Conta", "Nº Espelho de contrato", "Fornecedor",
                        "Valor mensal", "Descrição da despesa", "Responsável"], meses_sc, linhas_sc),
        ("CENTRO MULTIDISCIPLINAR", ["Conta", "Descrição Conta", "Fornecedor", "Valor",
                                     "Descrição da despesa", "Responsável"], meses_cmd, linhas_cmd),
    )
    for nome, titulos, meses, linhas in abas:
        aba = planilha.create_sheet(nome)
        aba.append(titulos + [datetime(a, m, 1) for a, m in meses] + ["Variação (%)"])
        for linha in linhas or []:
            aba.append(linha)
    aba = planilha.create_sheet("Emails")
    for i, contato in enumerate(emails or [], start=2):       # "Nome <email>" ou ("Nome <email>", "1; Todos")
        for coluna, texto in enumerate(contato if isinstance(contato, tuple) else (contato,), start=1):
            aba.cell(i, coluna, texto)
    planilha.save(caminho)
    return caminho
