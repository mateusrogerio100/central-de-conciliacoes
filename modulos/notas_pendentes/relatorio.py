"""Relatório do mês (Excel). Seção 5 da especificação.

Abas: Resumo, Arquivos (todo arquivo da pasta, com o que aconteceu com ele: L5) e Avisos. Cores: verde
anexada, rosa sem e-mail, cinza ignorado. Filtro e primeira linha congelada nas abas de lista.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from modulos.notas_pendentes import configuracao as cfg
from modulos.notas_pendentes.emails import competencia
from modulos.notas_pendentes.modelos import EmailsDoMes, PastaNotas

FONTE_TITULO = Font(bold=True, color=cfg.COR_FONTE_TITULO)
FUNDO_TITULO = PatternFill("solid", start_color=cfg.COR_FUNDO_TITULO)


def _fundo(cor: str) -> PatternFill:
    return PatternFill("solid", start_color=cor)


def _aba(livro: Workbook, nome: str, titulos: list[str], larguras: list[int]):
    aba = livro.create_sheet(nome)
    aba.append(titulos)
    for coluna, largura in enumerate(larguras, start=1):
        celula = aba.cell(row=1, column=coluna)
        celula.font, celula.fill = FONTE_TITULO, FUNDO_TITULO
        celula.alignment = Alignment(vertical="center", wrap_text=True)
        aba.column_dimensions[get_column_letter(coluna)].width = largura
    aba.freeze_panes = "A2"
    return aba


def linhas_dos_arquivos(pasta: PastaNotas, emails: EmailsDoMes) -> list[list]:
    """Uma linha por arquivo da pasta, na ordem do nome: arquivo, número, nota, fornecedor, KB, situação,
    destinatários, motivo."""
    situacao = {}
    for email in emails.emails:
        for nota in email.anexos:
            situacao[nota.nome] = (cfg.SITUACAO_ANEXADA, "; ".join(email.para)
                                   + (f" (cópia: {'; '.join(email.copia)})" if email.copia else ""), "")
    for sem in emails.sem_email:
        for nota in sem.notas:
            situacao[nota.nome] = (sem.situacao, "", sem.motivo)
    linhas = [[n.nome, int(n.numero) if n.numero else None, n.nota, n.fornecedor,
               round(n.tamanho / 1024, 1), *situacao[n.nome]] for n in pasta.notas]
    linhas += [[i.nome, None, "", "", None, cfg.SITUACAO_IGNORADO, "", i.motivo] for i in pasta.ignorados]
    # célula vazia no Excel em vez de texto vazio
    return sorted(([valor if valor != "" else None for valor in linha] for linha in linhas),
                  key=lambda linha: linha[0].casefold())


def _aba_resumo(livro, pasta: PastaNotas, emails: EmailsDoMes, ano: int, mes: int, prazo: date,
                arquivos: dict[str, str], agora: datetime):
    aba = livro.active
    aba.title = cfg.ABA_RESUMO
    sem = sum(len(s.notas) for s in emails.sem_email)
    linhas = [
        ("Notas pendentes de registro", competencia(ano, mes)),
        ("Prazo para registro", f"{prazo:%d/%m/%Y}"),
        ("Gerado em", f"{agora:%d/%m/%Y %H:%M}"),
        (),
        ("PDFs na pasta", len(pasta.notas)),
        ("E-mails", len(emails.emails)),
        ("Notas anexadas", sum(len(e.anexos) for e in emails.emails)),
        ("Notas sem e-mail", sem),
        ("Arquivos ignorados (não PDF)", len(pasta.ignorados)),
        ("Avisos", len(emails.avisos)),
        (),
        ("Arquivos usados", ""),
        *arquivos.items(),
    ]
    for linha in linhas:
        aba.append(list(linha))
    for linha in (1, 5, 6, 7, 8, 9, 10, 12):
        aba.cell(row=linha, column=1).font = Font(bold=True)
    if sem:
        aba.cell(row=8, column=2).fill = _fundo(cfg.COR_PROBLEMA)
    aba.column_dimensions["A"].width = 32
    aba.column_dimensions["B"].width = 110


def _aba_arquivos(livro, pasta: PastaNotas, emails: EmailsDoMes):
    aba = _aba(livro, cfg.ABA_ARQUIVOS,
               ["Arquivo", "Número", "Nº da nota", "Fornecedor", "Tamanho (KB)", "Situação", "Destinatários",
                "Motivo"], [70, 9, 12, 45, 12, 22, 70, 60])
    cores = {cfg.SITUACAO_ANEXADA: cfg.COR_ANEXADA, cfg.SITUACAO_IGNORADO: cfg.COR_IGNORADO}
    for linha in linhas_dos_arquivos(pasta, emails):
        aba.append(linha)
        aba.cell(row=aba.max_row, column=6).fill = _fundo(cores.get(linha[5], cfg.COR_PROBLEMA))
    aba.auto_filter.ref = aba.dimensions


def _aba_avisos(livro, emails: EmailsDoMes):
    aba = _aba(livro, cfg.ABA_AVISOS, ["Origem", "Aviso"], [60, 120])
    for a in emails.avisos:
        aba.append([a.origem, a.mensagem])
    aba.auto_filter.ref = aba.dimensions


def gerar_relatorio(caminho: Path, pasta: PastaNotas, emails: EmailsDoMes, ano: int, mes: int, prazo: date,
                    arquivos: dict[str, str], agora: datetime | None = None) -> Path:
    """Grava o relatório. Levanta OSError se não puder gravar (ex.: aberto no Excel)."""
    livro = Workbook()
    _aba_resumo(livro, pasta, emails, ano, mes, prazo, arquivos, agora or datetime.now())
    _aba_arquivos(livro, pasta, emails)
    _aba_avisos(livro, emails)
    livro.save(caminho)
    return Path(caminho)
