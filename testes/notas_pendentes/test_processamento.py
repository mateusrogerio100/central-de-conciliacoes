"""N4 (gabarito de out/2026) e N5 (relatório e processamento.gerar)."""

from __future__ import annotations

import csv
from datetime import date, datetime

import openpyxl
import pytest

from modulos.notas_pendentes import configuracao as cfg
from modulos.notas_pendentes.processamento import gerar, interpretar_competencia, interpretar_prazo
from testes.notas_pendentes.conftest import CHAVE_FICTICIA, criar_pdf, escrever_checklist, exemplos

PRAZO = date(2026, 10, 29)
AGORA = datetime(2026, 10, 26, 15, 30, 0)


def _entradas(tmp_path):
    pasta = tmp_path / "HOSPITAL EXEMPLO" / "102026"
    criar_pdf(pasta, f"2.DANFSe-90-Hotel Exemplo Ltda-{CHAVE_FICTICIA}.pdf", tamanho=2048)
    criar_pdf(pasta, f"21.DANFSe-765-Transportadora Exemplo Ltda-{CHAVE_FICTICIA}.pdf")
    criar_pdf(pasta, f"DANFSe-5-Fornecedor Sem Numero Ltda-{CHAVE_FICTICIA}.pdf")
    (pasta / "Acompanhamento.xlsx").write_bytes(b"x")
    checklist = escrever_checklist(tmp_path / "Check list 2026.xlsx", emails=[
        ("Ana Exemplo <ana@exemplo.com.br>", "2"), ("Supervisão <supervisao@exemplo.com.br>", "Todos")])
    saida = tmp_path / "saida"
    saida.mkdir()
    return pasta, checklist, saida


def test_interpretar_competencia_e_prazo():
    assert interpretar_competencia("10/2026") == (2026, 10)
    assert interpretar_competencia(" 1 / 2027 ") == (2027, 1)
    assert interpretar_competencia("13/2026") is None and interpretar_competencia("out/26") is None
    assert interpretar_prazo("29/10/2026") == PRAZO
    assert interpretar_prazo("31/11/2026") is None and interpretar_prazo("29-10-2026") is None
    assert interpretar_prazo("") is None


def test_gerar_grava_previa_e_relatorio(tmp_path):
    pasta, checklist, saida = _entradas(tmp_path)
    antes = {p.name: p.read_bytes() for p in pasta.iterdir()}
    progresso = []

    resultado = gerar(pasta, checklist, saida, 2026, 10, PRAZO, progresso=lambda t, f: progresso.append(f),
                      agora=AGORA)

    assert resultado.erro == "" and resultado.erro_saida == ""
    assert [e.numero for e in resultado.emails.emails] == ["2"]
    assert resultado.emails.emails[0].para == ["ana@exemplo.com.br", "supervisao@exemplo.com.br"]
    assert resultado.caminho_previa.name == "Previa_notas_pendentes_2026-10_2026-10-26_153000.html"
    assert resultado.caminho_relatorio.name == "Notas_pendentes_2026-10_2026-10-26_153000.xlsx"
    assert resultado.caminho_texto.name == "Emails_para_Claude_Desktop_2026-10_2026-10-26_153000.txt"
    assert "NÃO ENVIE NENHUM" in resultado.caminho_texto.read_text(encoding="utf-8-sig")
    assert resultado.origem_modelo == "modelo de fábrica"
    assert any("modelo de fábrica" in a.mensagem for a in resultado.emails.avisos)    # sem modelo: aviso
    assert progresso[-1] == 1.0
    # a pasta das notas nunca muda e nunca recebe nada
    assert {p.name: p.read_bytes() for p in pasta.iterdir()} == antes

    livro = openpyxl.load_workbook(resultado.caminho_relatorio)
    assert livro.sheetnames == ["Resumo", "Arquivos", "Avisos"]
    resumo = {r[0]: r[1] for r in livro["Resumo"].iter_rows(values_only=True) if r and r[0]}
    assert (resumo["PDFs na pasta"], resumo["E-mails"], resumo["Notas anexadas"], resumo["Notas sem e-mail"],
            resumo["Arquivos ignorados (não PDF)"]) == (3, 1, 1, 2, 1)
    assert resumo["Prazo para registro"] == "29/10/2026"
    linhas = list(livro["Arquivos"].iter_rows(min_row=2, values_only=True))
    assert [(l[0][:12], l[1], l[2], l[4], l[5]) for l in linhas] == [
        ("2.DANFSe-90-", 2, "90", 2.0, cfg.SITUACAO_ANEXADA),
        ("21.DANFSe-76", 21, "765", 0.1, cfg.SITUACAO_SEM_CONTATO),
        ("Acompanhamen", None, None, None, cfg.SITUACAO_IGNORADO),
        ("DANFSe-5-For", None, None, 0.1, cfg.SITUACAO_SEM_NUMERO),
    ]
    assert linhas[0][6] == "ana@exemplo.com.br; supervisao@exemplo.com.br"
    assert linhas[1][7] == "Nenhum contato da aba Emails tem o número 21."
    avisos = [r[0] for r in livro["Avisos"].iter_rows(min_row=2, values_only=True)]
    assert "Acompanhamento.xlsx" in avisos and "modelo_email.txt" in avisos
    livro.close()

    # mesmo segundo: não sobrescreve, ganha _2
    segundo = gerar(pasta, checklist, saida, 2026, 10, PRAZO, agora=AGORA)
    assert segundo.caminho_previa.name.endswith("_153000_2.html")
    assert segundo.caminho_relatorio.name.endswith("_153000_2.xlsx")


def test_gerar_com_entrada_com_problema(tmp_path):
    pasta, checklist, saida = _entradas(tmp_path)
    assert "Pasta não encontrada" in gerar(tmp_path / "nao", checklist, saida, 2026, 10, PRAZO).erro
    assert "Arquivo não encontrado" in gerar(pasta, tmp_path / "nao.xlsx", saida, 2026, 10, PRAZO).erro
    modelo = tmp_path / "modelo_email.txt"
    modelo.write_text("Assunto: x {prazoo}\n\ny", encoding="utf-8")
    resultado = gerar(pasta, checklist, saida, 2026, 10, PRAZO, modelo=modelo)
    assert "{prazoo}" in resultado.erro and resultado.caminho_previa is None
    assert list(saida.iterdir()) == []                  # com erro, nada é gravado
    with pytest.raises(ValueError):
        gerar(pasta, checklist, saida, 2026, 10, None)
    with pytest.raises(ValueError, match="nunca recebe nada"):
        gerar(pasta, checklist, pasta, 2026, 10, PRAZO)


def test_gerar_com_saida_que_nao_pode_ser_gravada(tmp_path):
    pasta, checklist, _ = _entradas(tmp_path)
    resultado = gerar(pasta, checklist, tmp_path / "nao_existe", 2026, 10, PRAZO, agora=AGORA)
    assert resultado.erro == "" and len(resultado.emails.emails) == 1
    assert "Não foi possível gravar a prévia" in resultado.erro_saida
    assert "Não foi possível gravar o relatório" in resultado.erro_saida
    assert "Não foi possível gravar o texto para o Claude Desktop" in resultado.erro_saida


def test_gabarito_de_outubro(tmp_path):
    """N4: a pasta real de out/2026 e o Check list de 26/10/2026 = gabarito montado por fora do módulo."""
    base = exemplos("2026-10")
    with open(base / "gabarito" / "gabarito_emails.csv", encoding="utf-8-sig", newline="") as arquivo:
        gabarito = {int(l["Numero"]): (int(l["PDFs"]), l["Para"].split("; "))
                    for l in csv.DictReader(arquivo, delimiter=";")}
    resultado = gerar(base / "HOSPITAL EXEMPLO" / "102026", base / "Check list 2026 (26-10).xlsx", tmp_path,
                      2026, 10, PRAZO, agora=AGORA)
    assert resultado.erro == "" and resultado.emails.sem_email == []
    assert {int(e.numero): (len(e.anexos), e.para) for e in resultado.emails.emails} == gabarito
    assert sum(len(e.anexos) for e in resultado.emails.emails) == 89
    assert max(e.tamanho for e in resultado.emails.emails) < cfg.LIMITE_ANEXOS_BYTES
