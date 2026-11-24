"""T1 — leitura do Check list (seção 3.2 e regra K1)."""

from __future__ import annotations

import msvcrt

import pytest

from modulos.checklist_contratos.leitor_checklist import ler_checklist, nome_do_mes
from modulos.checklist_contratos.modelos import ErroLeitura
from testes.checklist_contratos.conftest import escrever_checklist, exemplos

LINHAS_SC = [
    [30091, "Software", None, "Fornecedor Exemplo Ltda", 1000, "Licença de Sistema", "Ana", 900, 950,
     "Provisão"],
    ["30037 / 30081", "Água", None, "Companhia de Água Exemplo", None, "Água e esgoto", "Bruno/Carla"],
    [None, None, None, None, None, None, None],                    # linha vazia: fica de fora
]
LINHAS_CMD = [["30041/30089 ", "Energia", "Energia Exemplo S.A.", 500, "Energia elétrica", "Davi"]]
EMAILS = [
    ("Ana Exemplo <ana.exemplo@exemplo.org.br>,", 1),
    ("José Exemplo (Juca) <JOSE.EXEMPLO@exemplo.org.br >", "2; 13 ;Todos"),
    ("<sem.nome@exemplo.org.br>", "todos cmd"),
    "Só Um Nome",
    ("so.email@exemplo.org.br,", "3, Fulano"),
]


@pytest.fixture
def checklist_ficticio(tmp_path):
    return escrever_checklist(tmp_path / "Check list 2026.xlsx", linhas_sc=LINHAS_SC,
                              linhas_cmd=LINHAS_CMD, emails=EMAILS)


def test_t1_colunas_pelo_titulo_e_coluna_do_mes_pela_data(checklist_ficticio):
    checklist = ler_checklist(checklist_ficticio, 2026, 3)
    sc = checklist.abas["SC"]
    assert sc.nome == "HOSPITAL EXEMPLO" and sc.coluna_mes == 10 and sc.coluna_mes_anterior == 9
    primeira, segunda = sc.linhas
    assert (primeira.numero, primeira.conta, primeira.fornecedor, primeira.descricao_despesa,
            primeira.responsavel) == (2, "30091", "Fornecedor Exemplo Ltda", "Licença de Sistema", "Ana")
    assert (primeira.valor_mes, primeira.valor_mes_anterior) == ("Provisão", 950)
    assert (segunda.conta, segunda.valor_mes, segunda.valor_mes_anterior) == ("30037 / 30081", None, None)


def test_t1_aba_cmd_sem_julho(checklist_ficticio):
    cmd = ler_checklist(checklist_ficticio, 2026, 8).abas["CMD"]
    assert cmd.coluna_mes == 13 and cmd.coluna_mes_anterior is None       # jul/26 não existe
    assert cmd.linhas[0].conta == "30041/30089"
    with pytest.raises(ErroLeitura, match="CENTRO MULTIDISCIPLINAR não tem a coluna de jul/26"):
        ler_checklist(checklist_ficticio, 2026, 7)


def test_t1_mes_inexistente_e_erro_claro(checklist_ficticio):
    with pytest.raises(ErroLeitura, match="HOSPITAL EXEMPLO não tem a coluna de nov/26"):
        ler_checklist(checklist_ficticio, 2026, 11)
    assert nome_do_mes(2027, 1) == "jan/27"


def test_t1_aba_emails(checklist_ficticio):
    checklist = ler_checklist(checklist_ficticio, 2026, 10)
    # "Nome <email>", "<email>" e só o e-mail; os códigos vêm da célula ao lado
    assert [(c.nome, c.email, c.apelido, c.codigos, c.celula) for c in checklist.contatos] == [
        ("Ana Exemplo", "ana.exemplo@exemplo.org.br", "", ("1",), "A2"),
        ("José Exemplo (Juca)", "jose.exemplo@exemplo.org.br", "Juca", ("2", "13", "todos"), "A3"),
        ("", "sem.nome@exemplo.org.br", "", ("todos cmd",), "A4"),
        ("", "so.email@exemplo.org.br", "", ("3",), "A6"),
    ]
    assert [a.origem for a in checklist.avisos] == ["Emails A5", "Emails B6"]   # nada some em silêncio
    assert "Fulano" in checklist.avisos[1].mensagem


def test_t1_aba_faltando(tmp_path):
    import openpyxl

    caminho = tmp_path / "outro.xlsx"
    planilha = openpyxl.Workbook()
    planilha.active.title = "HOSPITAL EXEMPLO"
    planilha.save(caminho)
    with pytest.raises(ErroLeitura):
        ler_checklist(caminho, 2026, 10)


def test_t1_arquivo_aberto_por_outro_programa_e_lido(checklist_ficticio):
    with open(checklist_ficticio, "r+b"):                     # outro programa com o arquivo aberto
        assert len(ler_checklist(checklist_ficticio, 2026, 10).abas["SC"].linhas) == 2


def test_t1_arquivo_bloqueado_da_mensagem_clara(checklist_ficticio):
    with open(checklist_ficticio, "r+b") as arquivo:
        tamanho = checklist_ficticio.stat().st_size
        msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, tamanho)
        try:
            with pytest.raises(ErroLeitura, match="bloqueado"):
                ler_checklist(checklist_ficticio, 2026, 10)
        finally:
            arquivo.seek(0)
            msvcrt.locking(arquivo.fileno(), msvcrt.LK_UNLCK, tamanho)


def test_t1_arquivo_que_nao_e_planilha(tmp_path):
    (tmp_path / "falso.xlsx").write_text("não sou uma planilha", encoding="utf-8")
    with pytest.raises(ErroLeitura, match="planilha"):
        ler_checklist(tmp_path / "falso.xlsx", 2026, 10)


def test_t1_check_list_real():
    checklist = ler_checklist(exemplos("2026-10") / "Check list 2026.xlsx", 2026, 10)
    assert len(checklist.abas["SC"].linhas) == 141 and len(checklist.abas["CMD"].linhas) == 17
    assert checklist.abas["SC"].coluna_mes == 19 and checklist.abas["SC"].coluna_mes_anterior == 18
    assert checklist.abas["CMD"].coluna_mes == 19
    # 15 "Nome <email>" + 3 só com o e-mail (o protótipo ignorava esses; aceitos desde 23/10/2026)
    assert len(checklist.contatos) == 18
    assert sum(1 for c in checklist.contatos if c.apelido) == 1
    assert sum(1 for c in checklist.contatos if not c.nome) == 3
    with pytest.raises(ErroLeitura, match="jul/26"):
        ler_checklist(exemplos("2026-10") / "Check list 2026.xlsx", 2026, 7)
