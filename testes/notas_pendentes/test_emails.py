"""N3: e-mails (E1 a E6) com PDFs, contatos e modelo fictícios."""

from __future__ import annotations

from datetime import date

from modulos.notas_pendentes import configuracao as cfg
from modulos.notas_pendentes.emails import (
    competencia_por_extenso, montar_emails, preencher, previa_html, tamanho_legivel, texto_para_claude_desktop,
)
from modulos.notas_pendentes.leitor_modelo import ler_modelo
from modulos.notas_pendentes.leitor_pasta import ler_pasta
from modulos.notas_pendentes.modelos import Contato
from testes.notas_pendentes.conftest import CHAVE_FICTICIA, criar_pdf

PRAZO = date(2026, 10, 29)
CONTATOS = [
    Contato("Ana", "ana@exemplo.com.br", codigos=("2",)),
    Contato("Supervisão", "supervisao@exemplo.com.br", codigos=("todos",)),
    Contato("Bruno", "bruno@exemplo.com.br", codigos=("2", "13")),
    Contato("Ana de novo", "ana@exemplo.com.br", codigos=("13",)),       # mesmo endereço: não repete
    Contato("Administrativo", "adm@exemplo.com.br", codigos=("todos cmd",)),
    Contato("Gerente", "gerente@exemplo.com.br", codigos=("6", "todos")),
]


def _pasta(tmp_path):
    pasta = tmp_path / "102026"
    criar_pdf(pasta, f"2.DANFSe-90-Hotel Exemplo Ltda-{CHAVE_FICTICIA}.pdf")
    criar_pdf(pasta, f"2.DANFSe-13833-Laboratorio Exemplo Ltda-{CHAVE_FICTICIA}.pdf")
    criar_pdf(pasta, "13+Nota escaneada.pdf")
    criar_pdf(pasta, f"21.DANFSe-765-Transportadora Exemplo Ltda-{CHAVE_FICTICIA}.pdf")
    criar_pdf(pasta, f"DANFSe-5-Fornecedor Sem Numero Ltda-{CHAVE_FICTICIA}.pdf")
    return ler_pasta(pasta)


def test_um_email_por_numero_com_o_texto_de_fabrica(tmp_path):
    emails = montar_emails(_pasta(tmp_path), CONTATOS, ler_modelo(None), 2026, 10, PRAZO)

    assert [e.numero for e in emails.emails] == ["2", "13"]
    dois, treze = emails.emails
    # E2: os do número na ordem da aba, depois os Todos; sem repetir; "Todos CMD" não entra
    assert dois.para == ["ana@exemplo.com.br", "bruno@exemplo.com.br", "supervisao@exemplo.com.br",
                         "gerente@exemplo.com.br"]
    assert treze.para == ["bruno@exemplo.com.br", "ana@exemplo.com.br", "supervisao@exemplo.com.br",
                          "gerente@exemplo.com.br"]
    # E3: assunto e texto com a competência e o prazo
    assert dois.assunto == "Notas fiscais pendentes de registro - Competência 10/2026"
    assert "referentes à competência de outubro/2026 que ainda não foram" in dois.corpo
    assert "dentro da competência 10/2026\n" in dois.corpo
    assert "registradas até o dia 29/10/2026, garantindo" in dois.corpo
    assert dois.corpo.endswith("Contamos com a colaboração de todos.\n\nNotas pendentes (anexas):\n"
                               "- NF 13833 – Laboratorio Exemplo Ltda\n- NF 90 – Hotel Exemplo Ltda\n\n"
                               "Contabilidade")
    assert "- 13+Nota escaneada.pdf\n" in treze.corpo         # fora do padrão: o nome do arquivo
    assert "{" not in dois.assunto + dois.corpo
    # E4: anexos na ordem do nome, com o arquivo original
    assert [a.nome[:16] for a in dois.anexos] == ["2.DANFSe-13833-L", "2.DANFSe-90-Hote"]
    assert all(a.caminho.is_file() for a in dois.anexos)

    # E2 e L2: número sem contato próprio (só os Todos não bastam) e PDF sem número
    assert [(s.numero, len(s.notas), s.situacao) for s in emails.sem_email] == [
        ("21", 1, cfg.SITUACAO_SEM_CONTATO), ("", 1, cfg.SITUACAO_SEM_NUMERO)]
    assert emails.sem_email[0].motivo == "Nenhum contato da aba Emails tem o número 21."


def test_modelo_editado_com_marcador_com_acento(tmp_path):
    caminho = tmp_path / "modelo_email.txt"
    caminho.write_text("Assunto: Pendências {Competência_extenso}\n\nAté {PRAZO}:\n{lista_notas}", encoding="utf-8")
    emails = montar_emails(_pasta(tmp_path), CONTATOS, ler_modelo(caminho), 2026, 1, date(2026, 2, 3))
    assert emails.emails[0].assunto == "Pendências janeiro/2026"
    assert emails.emails[0].corpo.startswith("Até 03/02/2026:\n- NF 13833")


def test_e5_anexos_acima_do_limite(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "LIMITE_ANEXOS_BYTES", 250)
    pasta = tmp_path / "102026"
    criar_pdf(pasta, f"2.DANFSe-1-Grande Ltda-{CHAVE_FICTICIA}.pdf", tamanho=200)
    criar_pdf(pasta, f"2.DANFSe-2-Grande Ltda-{CHAVE_FICTICIA}.pdf", tamanho=200)
    criar_pdf(pasta, f"13.DANFSe-3-Pequeno Ltda-{CHAVE_FICTICIA}.pdf", tamanho=200)
    emails = montar_emails(ler_pasta(pasta), CONTATOS, ler_modelo(None), 2026, 10, PRAZO)
    assert [e.numero for e in emails.emails] == ["13"]
    assert emails.sem_email[0].situacao == cfg.SITUACAO_LIMITE
    assert "Os anexos somam 1 KB" in emails.sem_email[0].motivo


def test_auxiliares():
    assert competencia_por_extenso(2026, 3) == "março/2026"
    assert tamanho_legivel(540_000) == "527 KB" and tamanho_legivel(21 * 1024 * 1024) == "21,0 MB"
    assert tamanho_legivel(10) == "1 KB"
    assert preencher("{competencia} e {Prazo}", {"competencia": "10/2026", "prazo": "29/10/2026"}) == \
        "10/2026 e 29/10/2026"


def test_previa(tmp_path):
    emails = montar_emails(_pasta(tmp_path), CONTATOS, ler_modelo(None), 2026, 10, PRAZO)
    html = previa_html(emails, 2026, 10, PRAZO, "modelo de fábrica")
    assert html.count("<b>Para:</b>") == 2
    assert "Prazo para registro: <b>29/10/2026</b>" in html
    assert "<b>2</b> e-mail(s) com <b>3</b> nota(s) anexada(s)" in html and "2 nota(s) sem e-mail" in html
    assert "Sem e-mail (número 21): 1 nota(s)." in html and "Sem e-mail (sem número): 1 nota(s)." in html
    assert "Anexos (2, 1 KB):" in html
    assert "NF 13833 – Laboratorio Exemplo Ltda" in html


def test_e7_texto_para_o_claude_desktop_sem_anexos(tmp_path):
    emails = montar_emails(_pasta(tmp_path), CONTATOS, ler_modelo(None), 2026, 10, PRAZO)
    texto = texto_para_claude_desktop(emails, 2026, 10, PRAZO)
    assert texto.startswith("RASCUNHOS DE E-MAIL - NOTAS FISCAIS PENDENTES DE REGISTRO - COMPETÊNCIA 10/2026 "
                            "(prazo 29/10/2026)")
    assert "NÃO ENVIE NENHUM" in texto and "NÃO ANEXE NENHUM ARQUIVO" in texto
    assert "Total: 2 e-mail(s)." in texto
    assert "E-MAIL 1 de 2 - número do responsável: 2 (2 nota(s))" in texto
    assert ("PARA: ana@exemplo.com.br; bruno@exemplo.com.br; supervisao@exemplo.com.br; gerente@exemplo.com.br"
            in texto)
    assert "ASSUNTO: Notas fiscais pendentes de registro - Competência 10/2026" in texto
    assert emails.emails[0].corpo in texto                          # o corpo inteiro, como na prévia
    pasta = tmp_path / "102026"
    assert f"ANEXAR À MÃO (não anexar agora), da pasta {pasta}:\n  2.DANFSe-13833-" in texto
    assert "  13+Nota escaneada.pdf" in texto
    # quem ficou sem e-mail não entra (está na prévia)
    assert "Transportadora" not in texto and "Sem Numero" not in texto


def test_e2_contato_com_copia_vai_em_cc():
    """"Cópia" na aba Emails: em Cc de todos os e-mails, menos quando já está no Para (28/10/2026)."""
    from modulos.notas_pendentes.emails import copia, destinatarios
    contatos = [Contato("Ana", "ana@exemplo.com.br", codigos=("2",)),
                Contato("Lia", "lia@exemplo.com.br", codigos=("6", "copia")),
                Contato("Contabil", "contabil@exemplo.com.br", codigos=("copia",))]
    para, _ = destinatarios("2", contatos)
    assert (para, copia(para, contatos)) == (["ana@exemplo.com.br"], ["lia@exemplo.com.br", "contabil@exemplo.com.br"])
    para, _ = destinatarios("6", contatos)
    assert (para, copia(para, contatos)) == (["lia@exemplo.com.br"], ["contabil@exemplo.com.br"])
