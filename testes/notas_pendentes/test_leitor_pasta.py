"""N1: leitura da pasta das notas do mês (seção 3.1, regras L1 a L5)."""

from __future__ import annotations

import pytest

from modulos.notas_pendentes.leitor_pasta import dados_do_nome, ler_pasta
from modulos.notas_pendentes.modelos import ErroLeitura
from testes.notas_pendentes.conftest import CHAVE_FICTICIA, criar_pdf, exemplos


@pytest.mark.parametrize("nome, numero", [
    (f"1.DANFSe-10-Fornecedor Exemplo Ltda-{CHAVE_FICTICIA}", "1"),
    (f"13+DANFSe-22-Fornecedor Exemplo Ltda-{CHAVE_FICTICIA}", "13"),
    (f"15-DANFSe-80-Fornecedor Exemplo Ltda-{CHAVE_FICTICIA}", "15"),
    (f"4 - DANFSe-103-Fornecedor Exemplo Ltda-{CHAVE_FICTICIA}", "4"),
    (f"7_DANFSe-438-Fornecedor Exemplo Ltda-{CHAVE_FICTICIA}", "7"),
    (f"013.DANFSe-1-Fornecedor Exemplo Ltda-{CHAVE_FICTICIA}", "13"),
    (f" 9 .DANFSe-35-Fornecedor Exemplo Ltda-{CHAVE_FICTICIA}", "9"),
])
def test_l1_numero_com_cada_separador(nome, numero):
    assert dados_do_nome(nome)[0] == numero


@pytest.mark.parametrize("nome", [
    f"DANFSe-10-Fornecedor Exemplo Ltda-{CHAVE_FICTICIA}",     # sem número
    "ANA - DANFSe-5-Fornecedor Exemplo Ltda",                 # o jeito antigo, com o nome da pessoa
    "35381",                                                  # só número, sem separador
    "",
])
def test_l2_sem_numero(nome):
    assert dados_do_nome(nome) == ("", "", "")


def test_l3_nota_e_fornecedor_do_nome():
    nome = f"12.DANFSe-11643-Fornecedor Exemplo - Equipamentos Ltda-{CHAVE_FICTICIA}"
    assert dados_do_nome(nome) == ("12", "11643", "Fornecedor Exemplo - Equipamentos Ltda")
    assert dados_do_nome(f"2.DANFE-108949-Distribuidora Exemplo Ltda-{CHAVE_FICTICIA}") == \
        ("2", "108949", "Distribuidora Exemplo Ltda")
    assert dados_do_nome("20.Nota do mês") == ("20", "", "")


def test_l1_a_l5_pasta_ficticia(tmp_path):
    pasta = tmp_path / "102026"
    criar_pdf(pasta, f"2.DANFSe-90-Hotel Exemplo Ltda-{CHAVE_FICTICIA}.pdf", tamanho=300)
    criar_pdf(pasta, f"10.DANFSe-4615-Clinica Exemplo Ltda-{CHAVE_FICTICIA}.PDF")
    criar_pdf(pasta, f"2.DANFSe-13833-Laboratorio Exemplo Ltda-{CHAVE_FICTICIA}.pdf")
    criar_pdf(pasta, "13+Nota escaneada.pdf")
    criar_pdf(pasta, f"DANFSe-5-Fornecedor Sem Numero Ltda-{CHAVE_FICTICIA}.pdf")
    (pasta / "Acompanhamento.xlsx").write_bytes(b"x")
    (pasta / "~$Acompanhamento.xlsx").write_bytes(b"x")
    criar_pdf(pasta / "antigas", f"2.DANFSe-1-Outro Ltda-{CHAVE_FICTICIA}.pdf")
    antes = {p: p.read_bytes() for p in pasta.rglob("*") if p.is_file()}

    resultado = ler_pasta(pasta)

    assert [n.nome[:12] for n in resultado.notas] == [
        "10.DANFSe-46", "13+Nota esca", "2.DANFSe-138", "2.DANFSe-90-", "DANFSe-5-For"]
    grupos = resultado.por_numero()
    assert list(grupos) == ["2", "10", "13"]                    # ordem numérica, não de texto
    assert [n.nota for n in grupos["2"]] == ["13833", "90"]     # ordem do nome do arquivo
    assert grupos["2"][1].tamanho == 300
    assert grupos["2"][1].descricao == "NF 90 – Hotel Exemplo Ltda"
    assert grupos["13"][0].descricao == "13+Nota escaneada.pdf"
    assert [n.nome[:9] for n in resultado.sem_numero] == ["DANFSe-5-"]
    assert [i.nome for i in resultado.ignorados] == ["Acompanhamento.xlsx"]     # o ~$ some sem aviso
    origens = [a.origem for a in resultado.avisos]
    assert "Acompanhamento.xlsx" in origens and "antigas" in origens
    assert any(o.startswith("DANFSe-5-") for o in origens)
    assert not any(o.startswith("~$") for o in origens)
    # L5 / seção 1: a pasta nunca muda
    assert {p: p.read_bytes() for p in pasta.rglob("*") if p.is_file()} == antes


def test_l4_nome_com_caractere_estragado(tmp_path):
    pasta = tmp_path / "102026"
    criar_pdf(pasta, f"20.DANFSe-392-MN SERVI├çOS EXEMPLO LTDA-{CHAVE_FICTICIA}.pdf")
    nota = ler_pasta(pasta).notas[0]
    assert (nota.numero, nota.nota, nota.fornecedor) == ("20", "392", "MN SERVI├çOS EXEMPLO LTDA")


def test_pasta_vazia_e_pasta_que_nao_existe(tmp_path):
    vazia = tmp_path / "vazia"
    vazia.mkdir()
    assert ler_pasta(vazia).notas == []
    with pytest.raises(ErroLeitura, match="Pasta não encontrada"):
        ler_pasta(tmp_path / "nao_existe")


def test_pasta_real_de_outubro():
    """Cópia da pasta da rede de 26/10/2026; contagem por número feita à parte, pelo PowerShell."""
    pasta = exemplos("2026-10", "HOSPITAL EXEMPLO", "102026")
    resultado = ler_pasta(pasta)
    assert len(resultado.notas) == 89
    assert resultado.sem_numero == [] and resultado.ignorados == [] and resultado.avisos == []
    assert {numero: len(notas) for numero, notas in resultado.por_numero().items()} == {
        "1": 1, "2": 19, "4": 6, "7": 6, "8": 2, "9": 20, "10": 2, "12": 7, "13": 6, "15": 2, "18": 3,
        "19": 4, "20": 8, "21": 3}
    assert all(n.nota and n.fornecedor for n in resultado.notas)    # todos no padrão DANFSe
    assert sum(n.tamanho for n in resultado.por_numero()["9"]) < 1024 * 1024
