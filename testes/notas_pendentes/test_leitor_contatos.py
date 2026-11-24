"""N2: aba Emails do Check list de contratos (seção 3.2)."""

from __future__ import annotations

import pytest

from modulos.notas_pendentes.leitor_contatos import ler_contatos
from modulos.notas_pendentes.modelos import ErroLeitura
from testes.notas_pendentes.conftest import escrever_checklist, exemplos


def test_formatos_e_codigos(tmp_path):
    caminho = escrever_checklist(tmp_path / "Check list.xlsx", emails=[
        ("Ana Exemplo <ana.exemplo@exemplo.com.br>,", "1"),
        ("José Exemplo (Juca) <JOSE.EXEMPLO@exemplo.com.br>", "11; 12; 13"),
        ("<setor@exemplo.com.br>", 21),                       # número gravado como número no Excel
        ("outro.setor@exemplo.com.br ", "6; Todos"),
        ("Administrativo <adm@exemplo.com.br>", "Todos CMD"),
        ("Bruno Exemplo <bruno@exemplo.com.br>", None),       # sem número: aviso
        ("Carla Exemplo <carla@exemplo.com.br>", "3; talvez"),
        ("isto não é contato", "4"),
    ])
    lidos = ler_contatos(caminho)
    assert [(c.email, c.codigos) for c in lidos.contatos] == [
        ("ana.exemplo@exemplo.com.br", ("1",)),
        ("jose.exemplo@exemplo.com.br", ("11", "12", "13")),
        ("setor@exemplo.com.br", ("21",)),
        ("outro.setor@exemplo.com.br", ("6", "todos")),
        ("adm@exemplo.com.br", ("todos cmd",)),
        ("bruno@exemplo.com.br", ()),
        ("carla@exemplo.com.br", ("3",)),
    ]
    assert lidos.contatos[1].apelido == "Juca"
    mensagens = " | ".join(f"{a.origem}: {a.mensagem}" for a in lidos.avisos)
    assert "bruno@exemplo.com.br não tem número ao lado" in mensagens
    assert "\"talvez\" não é um número" in mensagens
    assert "\"isto não é contato\" não está no formato" in mensagens


def test_sem_aba_emails_e_arquivo_que_nao_existe(tmp_path):
    with pytest.raises(ErroLeitura, match="não tem a aba \"Emails\""):
        ler_contatos(escrever_checklist(tmp_path / "Check list.xlsx", com_aba_emails=False))
    with pytest.raises(ErroLeitura, match="Arquivo não encontrado"):
        ler_contatos(tmp_path / "nao_existe.xlsx")
    (tmp_path / "estragado.xlsx").write_bytes(b"isto nao e um xlsx")
    with pytest.raises(ErroLeitura, match="não pôde ser aberto"):
        ler_contatos(tmp_path / "estragado.xlsx")


def test_original_nao_muda(tmp_path):
    caminho = escrever_checklist(tmp_path / "Check list.xlsx", emails=[("Ana <ana@exemplo.com.br>", "1")])
    antes = caminho.read_bytes()
    ler_contatos(caminho)
    assert caminho.read_bytes() == antes


def test_checklist_real_de_26_10():
    """Cópia da rede de 26/10/2026: todo número da pasta de outubro tem contato próprio."""
    lidos = ler_contatos(exemplos("2026-10") / "Check list 2026 (26-10).xlsx")
    numeros = {c for contato in lidos.contatos for c in contato.codigos}
    assert {"1", "2", "4", "7", "8", "9", "10", "12", "13", "15", "18", "19", "20", "21"} <= numeros
    assert sum("21" in c.codigos for c in lidos.contatos) == 2           # cadastrado pelo usuário em 26/10
    assert sum("todos" in c.codigos for c in lidos.contatos) == 3


def test_n2_copia_na_celula_dos_numeros():
    from modulos.notas_pendentes.leitor_contatos import codigos_da_celula
    assert codigos_da_celula("6; Cópia") == (["6", "copia"], [])
    assert codigos_da_celula("COPIA") == (["copia"], [])
    assert codigos_da_celula("Cópia CMD") == (["copia cmd"], [])         # reconhecida (sem aviso), não usada
