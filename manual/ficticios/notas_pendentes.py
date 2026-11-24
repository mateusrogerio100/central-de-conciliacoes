"""Notas Pendentes: a pasta do mês com os PDFs (cada nome começa com o número do responsável) e o Check list
com a aba Emails.

Mostra: quatro notas anexadas em dois e-mails (os números 1 e 2) e uma nota do número 3, que não tem contato
na aba Emails (sem e-mail). O modelo do e-mail é o de fábrica.
"""

from __future__ import annotations

from pathlib import Path

import openpyxl

from manual.ficticios import Exemplo
from manual.ficticios.pdf_simples import gravar_pdf

CHAVE = "3516200121234567800019900000000012326100000000000"
NOTAS = [
    ("1.DANFSe-1201-Alfa Exemplo Sistemas Ltda", "Alfa Exemplo Sistemas Ltda - NFS-e 1201"),
    ("1.DANFSe-1202-Alfa Exemplo Sistemas Ltda", "Alfa Exemplo Sistemas Ltda - NFS-e 1202"),
    ("2.DANFSe-88-Beta Exemplo Laboratorio Ltda", "Beta Exemplo Laboratorio Ltda - NFS-e 88"),
    ("2-DANFSe-4510-Gama Exemplo Hotelaria Ltda", "Gama Exemplo Hotelaria Ltda - NFS-e 4510"),
    ("3+DANFSe-77-Delta Exemplo Transportes Ltda", "Delta Exemplo Transportes Ltda - NFS-e 77"),
]
CONTATOS = [("Ana Exemplo <ana.exemplo@exemplo.org.br>", "1"), ("Bruno Exemplo <bruno.exemplo@exemplo.org.br>", "2"),
            ("Contabilidade Exemplo <contabilidade@exemplo.org.br>", "Todos")]


def _checklist(caminho: Path) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    planilha = openpyxl.Workbook()
    planilha.active.title = "HOSPITAL EXEMPLO"
    planilha.create_sheet("CENTRO MULTIDISCIPLINAR")
    aba = planilha.create_sheet("Emails")
    for linha, (contato, numeros) in enumerate(CONTATOS, start=2):
        aba.cell(linha, 1, contato)
        aba.cell(linha, 2, numeros)
    planilha.save(caminho)
    return caminho


def _datas(tela) -> None:
    tela.campo_competencia.definir("10/2026")
    tela.campo_prazo.definir("29/10/2026")
    tela.atualizar_botoes()


def gerar(pasta: Path) -> list[Exemplo]:
    notas = pasta / "HOSPITAL EXEMPLO" / "102026"
    notas.mkdir(parents=True, exist_ok=True)
    for nome, texto in NOTAS:
        gravar_pdf(notas / f"{nome}-{CHAVE}.pdf", [[texto]])
    checklist = _checklist(pasta / "Check list 2026.xlsx")
    saida = pasta / "saida"
    saida.mkdir(parents=True, exist_ok=True)
    return [Exemplo("notas_pendentes", "notas_pendentes", "E-mails", "gerar",
                    {"cartao_pasta": [notas], "cartao_checklist": [checklist], "cartao_saida": [saida]},
                    preparar=_datas, pasta_saida=saida, numeros=("4", "2", "1"))]
