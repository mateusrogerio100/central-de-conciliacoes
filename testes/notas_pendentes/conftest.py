"""Apoio dos testes do módulo Notas Pendentes.

Os exemplos reais (cópia da pasta de out/2026 e do Check list) ficam em exemplos\\notas_pendentes\\, fora do
git. Sem a pasta, os testes que dependem dela são pulados. Os demais usam PDFs e Check list fictícios.
"""

from __future__ import annotations

from pathlib import Path

import openpyxl

from testes.conftest import pasta_exemplos

CHAVE_FICTICIA = "3516200121234567800019900000000012326100000000000"


def exemplos(*subpastas: str) -> Path:
    """exemplos\\notas_pendentes\\<subpastas>; pula sem a pasta."""
    return pasta_exemplos("notas_pendentes", *subpastas)


def criar_pdf(pasta: Path, nome: str, tamanho: int = 100) -> Path:
    """Um "PDF" fictício: só o nome importa (o módulo não abre o arquivo)."""
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / nome
    caminho.write_bytes(b"%PDF-1.4\n" + b"0" * max(0, tamanho - 9))
    return caminho


def escrever_checklist(caminho: Path, emails=None, com_aba_emails: bool = True) -> Path:
    """Check list fictício: as abas de contratos vazias e a aba Emails.

    emails: "Nome <email>" ou ("Nome <email>", "1; Todos").
    """
    planilha = openpyxl.Workbook()
    planilha.active.title = "HOSPITAL EXEMPLO"
    planilha.create_sheet("CENTRO MULTIDISCIPLINAR")
    if com_aba_emails:
        aba = planilha.create_sheet("Emails")
        for i, contato in enumerate(emails or [], start=2):
            for coluna, texto in enumerate(contato if isinstance(contato, tuple) else (contato,), start=1):
                aba.cell(i, coluna, texto)
    planilha.save(caminho)
    return caminho
