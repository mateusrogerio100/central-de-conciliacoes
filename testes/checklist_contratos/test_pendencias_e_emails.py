"""T7 e T8 — pendências por responsável (P1 a P6) e e-mails (E1 a E7).

Gabarito de outubro (exemplos\\...\\2026-10\\gabarito\\):
- gabarito_pendencias.csv e rascunhos.json: feitos pelo protótipo com o Check list de 22/10/2026;
- gabarito_emails_codigos.csv: os destinatários pelos códigos, montado com a tabela de contatos que o
  Usuário aprovou em 23/10/2026 (o gabarito_emails.csv do protótipo usava os .csv aposentados).
A entrada é "Check list 2026 (22-10 com códigos).xlsx": o de 22/10/2026 com a coluna Responsável e a
aba Emails da rede de 23/10/2026 (os números dos responsáveis).
"""

from __future__ import annotations

import csv
import json
from datetime import date, datetime
from html import unescape

import openpyxl
import pytest

from modulos.checklist_contratos.emails import (
    corpo_do_email, montar_emails, nomes_da_saudacao, previa_html, texto_para_claude_desktop,
)
from modulos.checklist_contratos.leitor_checklist import ler_checklist
from modulos.checklist_contratos.modelos import ErroLeitura, Pendencias
from modulos.checklist_contratos.pendencias import (
    avisos_dos_codigos, codigo_e_nome, gerar_listas, linhas_divergentes, notas_conta_divergente,
)
from modulos.checklist_contratos.processamento import conferir, gerar_pendencias
from testes.checklist_contratos.conftest import escrever_checklist, exemplos

AGORA = datetime(2026, 10, 22, 9, 0)
POSICAO = AGORA.date()


def _sc(conta, fornecedor, descricao, responsavel, mes=None, anterior=None):
    """Linha da aba HOSPITAL EXEMPLO do Check list fictício (jan a out/26)."""
    return [conta, "Conta Exemplo", None, fornecedor, 100, descricao, responsavel] + [None] * 8 + [anterior, mes]


def _cmd(conta, fornecedor, descricao, responsavel, mes=None, anterior=None):
    """Linha da aba CENTRO MULTIDISCIPLINAR (sem jul/26: ago, set e out são as três últimas)."""
    return [conta, "Conta Exemplo", fornecedor, 100, descricao, responsavel] + [None] * 7 + [anterior, mes]


LINHAS_SC = [
    _sc(30091, "Fornecedor A", "Licença", "1 - Ana manutenção"),                   # 2: pendente
    _sc(30092, "Fornecedor B", "Suporte", "1 - Ana manutenção", mes=500),          # 3: preenchida (P1)
    _sc(30093, "Fornecedor C", "Locação", "1 - Ana manutenção", mes="Provisão"),   # 4: texto (P2)
    _sc(30094, "Fornecedor D", "Serviço", "2 - Bruno/Carla", anterior="Rescindido em set"),   # 5: encerrado
    _sc(30095, "Fornecedor E", "Serviço", "2 - Bruno e Carla"),                    # 6: pendente
    _sc(30096, "Fornecedor F", "Serviço", "Davi"),                                 # 7: sem número
    _sc(30097, "Fornecedor G", "Serviço", None),                                   # 8: sem responsável
    _sc(30098, "Fornecedor H", "Serviço", "3 - Eva"),                              # 9: número sem contato
    _sc(30099, "Fornecedor I", "Serviço", "1 - Ana manutenção"),                   # 10: CONTA DIVERGENTE
    _sc(None, None, None, None),                                                   # 11: vazia
]
LINHAS_CMD = [
    _cmd(30130, "Fornecedor J", "Telefone; fixo", "1 - Ana manutenção"),           # 2: SC + CMD num e-mail só
    _cmd(30131, "Fornecedor K", "Energia", "4 - Fabio"),                           # 3: só CMD
]
EMAILS = [
    ("Ana Exemplo <ana@exemplo.org.br>,", "1"),
    ("<manutencao@exemplo.org.br>", "1; 4"),
    ("Bruno Exemplo (Beto) <bruno@exemplo.org.br>", "2"),
    ("carla@exemplo.org.br", "2"),
    ("Contabilidade <contabil@exemplo.org.br>", "Todos"),
    ("Administrativo CMD <adm.cmd@exemplo.org.br>", "Todos CMD"),
    ("Fabio Exemplo <fabio@exemplo.org.br>", "4; 9"),
]


@pytest.fixture
def checklist_ficticio(tmp_path):
    return escrever_checklist(tmp_path / "Check list 2026.xlsx", linhas_sc=LINHAS_SC, linhas_cmd=LINHAS_CMD,
                              emails=EMAILS)


def _pendencias(caminho, divergentes=frozenset()):
    checklist = ler_checklist(caminho, 2026, 10)
    listas, avisos = gerar_listas(checklist, divergentes)
    pendencias = Pendencias(listas, avisos=avisos)
    montar_emails(pendencias, checklist.contatos, 2026, 10, POSICAO)
    return checklist, pendencias


# ---------------------------------------------------------------------------
# T7 — pendências
# ---------------------------------------------------------------------------

def test_t7_codigo_e_nome_do_responsavel():
    assert codigo_e_nome("13 - Carlos manutenção") == ("13", "Carlos manutenção")
    assert codigo_e_nome(" 07 – Ana/Bruno ") == ("7", "Ana/Bruno")
    assert codigo_e_nome("Ana") == ("", "Ana")
    assert codigo_e_nome("") == ("", "")


def test_t7_quem_fica_de_fora_e_agrupamento(checklist_ficticio):
    _, pendencias = _pendencias(checklist_ficticio, {("SC", 10)})
    resumo = [(l.estabelecimento, l.codigo, l.responsavel, [n.numero for n in l.notas]) for l in pendencias.listas]
    assert resumo == [
        ("SC", "1", "Ana manutenção", [2]),          # 3 preenchida, 4 com texto, 10 divergente (P1, P2)
        ("SC", "2", "Bruno/Carla", [6]),             # 5 encerrado no mês anterior (P2)
        ("SC", "", "Davi", [7]),
        ("SC", "", "Sem responsável", [8]),          # P3
        ("SC", "3", "Eva", [9]),
        ("CMD", "1", "Ana manutenção", [2]),
        ("CMD", "4", "Fabio", [3]),
    ]
    assert pendencias.notas == 7


def test_t7_mesmo_numero_com_nomes_diferentes_avisa(tmp_path):
    caminho = escrever_checklist(tmp_path / "c.xlsx", linhas_sc=[
        _sc(30091, "F1", "D", "5 - Ana"), _sc(30092, "F2", "D", "5 - Ana"), _sc(30093, "F3", "D", "5 - Bruno")])
    _, pendencias = _pendencias(caminho)
    assert [(l.responsavel, len(l.notas)) for l in pendencias.listas] == [("Ana", 3)]   # o nome mais frequente
    assert [a.origem for a in pendencias.avisos] == ["Responsável 5"]


def test_t7_linhas_divergentes_do_relatorio(tmp_path, checklist_ficticio):
    checklist = ler_checklist(checklist_ficticio, 2026, 10)
    relatorio = tmp_path / "Conferencia_Contratos_2026-10_2026-10-22_090000.xlsx"
    livro = openpyxl.Workbook()
    aba = livro.active
    aba.title = "Conferência"
    aba.append(["Aba", "Linha", "Conta esperada", "Fornecedor", "Descrição da despesa", "Situação"])
    aba.append(["HOSPITAL EXEMPLO", 10, "30099", "Fornecedor I", "Serviço", "CONTA DIVERGENTE"])
    aba.append(["HOSPITAL EXEMPLO", 2, "30091", "Fornecedor A", "Licença", "NÃO ENCONTRADO"])
    aba.append(["CENTRO MULTIDISCIPLINAR", 3, "30131", "Fornecedor K", "Energia", "CONTA DIVERGENTE"])
    livro.save(relatorio)
    assert linhas_divergentes(relatorio, 2026, 10, checklist) == {("SC", 10), ("CMD", 3)}
    with pytest.raises(ErroLeitura, match="não é da conferência de set/26"):
        linhas_divergentes(relatorio, 2026, 9, checklist)
    with pytest.raises(ErroLeitura, match="não é um relatório"):
        linhas_divergentes(checklist_ficticio, 2026, 10, checklist)


def _gabarito_pendencias():
    linhas = []
    with open(exemplos("2026-10", "gabarito") / "gabarito_pendencias.csv", encoding="utf-8-sig", newline="") as f:
        leitor = csv.reader(f, delimiter=";")
        next(leitor)
        for campos in leitor:
            # o protótipo gravou sem aspas: um ";" na descrição virou colunas a mais (linha dos telefones do CMD)
            linhas.append(tuple(campos[:4]) + (";".join(campos[4:]),))
    return linhas


@pytest.fixture(scope="module")
def outubro(tmp_path_factory):
    """Relatório do módulo para out/2026 (= gabarito, T3) e as pendências com o Check list com códigos."""
    pasta = tmp_path_factory.mktemp("outubro")
    base = exemplos("2026-10")
    conferencia = conferir(base / "Movimentos_NF_10_SC.csv", base / "Movimentos_NF_10_CMD.csv",
                           base / "Check list 2026.xlsx", exemplos("config_gabarito_22-10-2026"), pasta,
                           2026, 10, agora=AGORA)
    resultado = gerar_pendencias(base / "Check list 2026 (22-10 com códigos).xlsx", pasta, 2026, 10,
                                 relatorio=conferencia.caminho_relatorio, agora=AGORA)
    assert resultado.erro == "" and resultado.erro_previa == ""
    return resultado


def test_t7_gabarito_de_outubro(outubro):
    nomes = {"SC": "Hospital Exemplo", "CMD": "CMD"}
    nossas = [(nomes[l.estabelecimento], l.responsavel, n.conta, n.fornecedor, n.descricao_despesa)
              for l in outubro.pendencias.listas for n in l.notas]
    assert nossas == _gabarito_pendencias()
    assert outubro.pendencias.notas == 60 and len(outubro.pendencias.listas) == 10
    assert sum(1 for l in outubro.pendencias.listas if l.estabelecimento == "SC") == 8


def test_t7_relatorio_do_prototipo_tambem_vale():
    base = exemplos("2026-10")
    checklist = ler_checklist(base / "Check list 2026 (22-10 com códigos).xlsx", 2026, 10)
    prototipo = linhas_divergentes(base / "gabarito" / "Conferencia_2026-10 (prototipo).xlsx", 2026, 10, checklist)
    assert len(prototipo) == 5                     # as 5 CONTA DIVERGENTE de outubro


# ---------------------------------------------------------------------------
# T8 — e-mails
# ---------------------------------------------------------------------------

def test_t8_saudacao():
    assert nomes_da_saudacao("Carlos manutenção") == ["Carlos"]
    assert nomes_da_saudacao("Ana/Bruno") == ["Ana", "Bruno"]
    assert nomes_da_saudacao("lídia e bruno, carla") == ["Lídia", "Bruno", "Carla"]


def test_t8_emails_por_codigo(checklist_ficticio):
    _, pendencias = _pendencias(checklist_ficticio, {("SC", 10)})
    resumo = [(e.responsavel, e.notas, e.assunto, e.para) for e in pendencias.emails]
    assert resumo == [
        # SC + CMD num e-mail só; "Todos CMD" só porque tem nota do CMD; sem repetir endereço
        ("Ana manutenção", 2, "Notas fiscais pendentes - Hospital Exemplo e CMD - Outubro/2026",
         ["ana@exemplo.org.br", "manutencao@exemplo.org.br", "contabil@exemplo.org.br", "adm.cmd@exemplo.org.br"]),
        ("Bruno/Carla", 1, "Notas fiscais pendentes - Hospital Exemplo - Outubro/2026",
         ["bruno@exemplo.org.br", "carla@exemplo.org.br", "contabil@exemplo.org.br"]),
        ("Fabio", 1, "Notas fiscais pendentes - CMD - Outubro/2026",
         ["manutencao@exemplo.org.br", "fabio@exemplo.org.br", "contabil@exemplo.org.br", "adm.cmd@exemplo.org.br"]),
    ]
    sem = {s.responsavel: s.motivo for s in pendencias.sem_email}
    assert list(sem) == ["Davi", "Sem responsável", "Eva"]
    assert "número" in sem["Davi"] and "sem responsável" in sem["Sem responsável"] and "número 3" in sem["Eva"]

    ana, bruno, fabio = pendencias.emails
    assert "<p>Olá, Ana,</p>" in ana.html and "sua responsabilidade" in ana.html
    assert ana.html.index("<b>Hospital Exemplo</b>") < ana.html.index("<b>CMD - Centro Multidisciplinar</b>")
    assert ana.html.count("<table") == 2 and "Telefone; fixo" in ana.html
    assert "<p>Olá, Bruno e Carla,</p>" in bruno.html and "responsabilidade de vocês" in bruno.html
    assert "contrato do <b>CMD - Centro Multidisciplinar</b> sob sua" in fabio.html
    assert "(posição em 22/10/2026)" in fabio.html and "<b>Outubro/2026</b>" in fabio.html


def test_t8_avisos_dos_codigos(checklist_ficticio):
    checklist = ler_checklist(checklist_ficticio, 2026, 10)
    avisos = [(a.origem, a.mensagem) for a in avisos_dos_codigos(checklist)]
    assert [o for o, _ in avisos] == ["Emails A8", "Responsável 3"]
    assert "número 9" in avisos[0][1]


def test_t8_texto_escapado():
    from modulos.checklist_contratos.modelos import LinhaChecklist, ListaPendente

    nota = LinhaChecklist(2, "30091", "C", "A & B <Ltda>", 'Licença "Escala"', "1 - Ana", None, None)
    html = corpo_do_email("Ana", [ListaPendente("SC", "1", "1", "Ana", [nota])], 2026, 10, date(2026, 10, 22))
    assert "A &amp; B &lt;Ltda&gt;" in html and "Licença &quot;Escala&quot;" in html


def test_t8_gabarito_de_outubro(outubro):
    with open(exemplos("2026-10", "gabarito") / "gabarito_emails_codigos.csv", encoding="utf-8-sig") as f:
        esperados = list(csv.DictReader(f, delimiter=";"))
    rascunhos = json.loads((exemplos("2026-10", "gabarito") / "rascunhos.json").read_text(encoding="utf-8-sig"))
    emails = outubro.pendencias.emails
    assert outubro.pendencias.sem_email == []
    assert [(e.responsavel, e.assunto, e.notas) for e in emails] == [
        (g["Responsavel"], g["Assunto"], int(g["Notas"])) for g in esperados]
    for email, esperado, rascunho in zip(emails, esperados, rascunhos):
        assert email.para == esperado["Para"].split(","), email.responsavel
        # o texto do protótipo, sem o "tudo bem?" da saudação (pedido do usuário, 23/10/2026)
        esperado = unescape(rascunho["Html"]).replace(", tudo bem?</p>", ",</p>", 1)
        assert unescape(email.html) == esperado, email.responsavel


def test_t8_previa(outubro):
    previa = outubro.caminho_previa
    assert previa.name == "Previa_emails_2026-10_2026-10-22_090000.html"
    texto = previa.read_text(encoding="utf-8")
    assert texto.count("<b>Assunto:</b>") == 10 and "<b>60</b> nota(s) pendente(s)" in texto


def test_t8_previa_mostra_quem_ficou_sem_email(checklist_ficticio):
    checklist, pendencias = _pendencias(checklist_ficticio)
    pendencias.avisos += avisos_dos_codigos(checklist)
    texto = previa_html(pendencias, 2026, 10, POSICAO)
    assert "Sem e-mail: Davi" in texto and "Fornecedor F" in texto      # as notas dele aparecem
    assert "Sem e-mail: Eva" in texto and "Avisos" in texto


def test_t8_previa_lista_as_notas_de_conta_divergente(checklist_ficticio):
    """P2: a nota de CONTA DIVERGENTE não vai no e-mail, mas aparece na prévia (pedido do usuário, 28/10/2026)."""
    checklist, pendencias = _pendencias(checklist_ficticio, {("SC", 10), ("SC", 3)})
    pendencias.conta_divergente = notas_conta_divergente(checklist, {("SC", 10), ("SC", 3)})
    assert [(e, l.numero) for e, l in pendencias.conta_divergente] == [("SC", 10)]   # a 3 já está preenchida
    assert all("Fornecedor I" not in e.html for e in pendencias.emails)
    texto = previa_html(pendencias, 2026, 10, POSICAO)
    assert "Fora dos e-mails: conta divergente (1 nota(s))" in texto
    assert "<td>10</td><td>30099</td><td>Fornecedor I</td>" in texto
    assert "Fornecedor I" not in texto_para_claude_desktop(pendencias, 2026, 10, POSICAO)


def test_t8_previa_sem_conta_divergente_nao_mostra_a_secao(checklist_ficticio):
    _, pendencias = _pendencias(checklist_ficticio)
    assert "conta divergente" not in previa_html(pendencias, 2026, 10, POSICAO)


# ---------------------------------------------------------------------------
# processamento.gerar_pendencias
# ---------------------------------------------------------------------------

def test_processamento_chamada_incompleta(tmp_path):
    with pytest.raises(ValueError):
        gerar_pendencias("", tmp_path, 2026, 10)


def test_processamento_erro_de_leitura_e_progresso(tmp_path, checklist_ficticio):
    passos = []
    resultado = gerar_pendencias(checklist_ficticio, tmp_path, 2026, 11, progresso=lambda t, f: passos.append(f))
    assert "nov/26" in resultado.erro and resultado.pendencias is None and passos[-1] == 1.0
    resultado = gerar_pendencias(checklist_ficticio, tmp_path, 2026, 10, relatorio=tmp_path / "nao_existe.xlsx")
    assert "não encontrado" in resultado.erro


def test_processamento_nao_sobrescreve_a_previa(tmp_path, checklist_ficticio):
    primeiro = gerar_pendencias(checklist_ficticio, tmp_path, 2026, 10, agora=AGORA)
    segundo = gerar_pendencias(checklist_ficticio, tmp_path, 2026, 10, agora=AGORA)
    assert primeiro.caminho_previa != segundo.caminho_previa and segundo.caminho_previa.stem.endswith("_2")
    assert len(primeiro.pendencias.emails) == 3


# ---------------------------------------------------------------------------
# E8 — texto para o Claude Desktop (enquanto não há o credentials.json)
# ---------------------------------------------------------------------------

def test_e8_texto_para_claude_desktop(checklist_ficticio):
    _, pendencias = _pendencias(checklist_ficticio, {("SC", 10)})
    texto = texto_para_claude_desktop(pendencias, 2026, 10, POSICAO)
    assert texto.startswith("RASCUNHOS DE E-MAIL - NOTAS FISCAIS DE CONTRATO PENDENTES - OUTUBRO/2026 "
                            "(posição em 22/10/2026)")
    assert "NÃO ENVIE NENHUM" in texto and "Total: 3 e-mail(s)." in texto
    assert "E-MAIL 1 de 3 - responsável no Check list: Ana manutenção (2 nota(s))" in texto
    assert ("PARA: ana@exemplo.org.br; manutencao@exemplo.org.br; contabil@exemplo.org.br; adm.cmd@exemplo.org.br\n"
            "ASSUNTO: Notas fiscais pendentes - Hospital Exemplo e CMD - Outubro/2026\nCORPO:\n\nOlá, Ana,\n\n") in texto
    assert ("[Hospital Exemplo]\nConta | Fornecedor | Descrição da despesa\n30091 | Fornecedor A | Licença\n\n"
            "[CMD - Centro Multidisciplinar]\nConta | Fornecedor | Descrição da despesa\n"
            "30130 | Fornecedor J | Telefone; fixo") in texto
    assert "Olá, Bruno e Carla,\n\nSegue a relação das notas fiscais de contrato sob responsabilidade de vocês" in texto
    assert "contrato do CMD - Centro Multidisciplinar sob sua responsabilidade" in texto
    assert "Davi" not in texto                    # sem e-mail: só na prévia
    assert texto.rstrip().endswith("Atenciosamente,\nContabilidade")


def test_e8_texto_de_outubro(outubro):
    texto = outubro.caminho_texto.read_text(encoding="utf-8-sig")
    assert outubro.caminho_texto.name == "Emails_para_Claude_Desktop_2026-10_2026-10-22_090000.txt"
    assert "Total: 10 e-mail(s)." in texto
    for email in outubro.pendencias.emails:
        assert f"PARA: {'; '.join(email.para)}\nASSUNTO: {email.assunto}\n" in texto
        for lista in email.listas:
            for nota in lista.notas:
                assert f"{nota.conta} | {nota.fornecedor} | {nota.descricao_despesa}\n" in texto


# ---------------------------------------------------------------------------
# "Cópia" na aba Emails: vai em Cc de todos os e-mails (28/10/2026)
# ---------------------------------------------------------------------------

def test_e2_contato_com_copia_vai_em_cc(tmp_path):
    caminho = escrever_checklist(
        tmp_path / "c.xlsx",
        linhas_sc=[_sc(30091, "Fornecedor A", "Licença", "1 - Ana"), _sc(30092, "Fornecedor B", "Suporte", "6 - Lia")],
        linhas_cmd=[_cmd(30130, "Fornecedor J", "Telefone", "1 - Ana")],
        emails=[("Ana <ana@exemplo.org.br>", "1"), ("Lia <lia@exemplo.org.br>", "6; Cópia"),
                ("Contabil <contabil@exemplo.org.br>", "copia"), ("Adm CMD <adm.cmd@exemplo.org.br>", "Cópia CMD")])
    checklist, pendencias = _pendencias(caminho)
    assert [a for a in checklist.avisos if "Emails" in a.origem] == []
    ana, lia = pendencias.emails
    # "Cópia CMD" só no e-mail que tem notas do CMD (o da Ana)
    assert (ana.para, ana.copia) == (["ana@exemplo.org.br"],
                                     ["lia@exemplo.org.br", "contabil@exemplo.org.br", "adm.cmd@exemplo.org.br"])
    # quem já está no Para (o próprio número) não se repete na cópia
    assert (lia.para, lia.copia) == (["lia@exemplo.org.br"], ["contabil@exemplo.org.br"])
    previa = previa_html(pendencias, 2026, 10, POSICAO)
    assert "<b>Cópia:</b> lia@exemplo.org.br; contabil@exemplo.org.br; adm.cmd@exemplo.org.br" in previa
    texto = texto_para_claude_desktop(pendencias, 2026, 10, POSICAO)
    assert "CÓPIA: lia@exemplo.org.br; contabil@exemplo.org.br; adm.cmd@exemplo.org.br" in texto
    assert "no campo Cc" in texto
