"""Apoio dos testes do EFD Contribuições: arquivos de exemplo (fora do git) e um SPED fictício.

Os exemplos reais (exemplos/efd_contribuicoes/: o SPED original de agosto/2026, 5 DANFSe e o clientes.json)
têm nomes e CNPJs reais e nunca vão para o git; sem eles, os testes que os usam são pulados.
O SPED fictício abaixo imita o layout do real com dados inventados.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from testes.conftest import pasta_exemplos


@pytest.fixture
def cadastro_fora_da_rede(tmp_path):
    """Uma pasta temporária fazendo o papel da pasta da rede onde fica o clientes.json (nenhum teste usa a rede)."""
    pasta = tmp_path / "cadastro_rede_de_teste"
    pasta.mkdir()
    return pasta


def exemplo_efd(*partes: str) -> Path:
    caminho = pasta_exemplos("efd_contribuicoes").joinpath(*partes)
    if not caminho.exists():
        pytest.skip(f"Exemplo {caminho} não encontrado")
    return caminho


# SPED fictício (layout do real; empresa e clientes inventados). 2 clientes, 2 notas de 100,00 e 50,50.
LINHAS_SPED_FICTICIO = [
    "|0000|006|0|||01072026|31072026|EMPRESA FICTICIA|00000000000191|SP|3516200||00|9|",
    "|0001|0|",
    "|0100|CONTADOR FICTICIO|00000000000|1SP000000|||||||||||",
    "|0110|1|1||1|",
    "|0140||EMPRESA FICTICIA|00000000000191|SP||3516200|||",
    "|0150|1|CLIENTE FICTICIO UM|1058|11111111000191|||3516200||||||",
    "|0150|2|CLIENTE FICTICIO DOIS|1058|22222222000191|||3509502||||||",
    "|0200|1|SERVICOS||||||||||",
    "|0990|9|",
    "|A001|0|",
    "|A010|00000000000191|",
    "|A100|1|0|1|00|||101||02072026|02072026|100|0||100|0|100|0||||",
    "|A170|1|1||100||||07|100|||07|100|||||",
    "|A100|1|0|2|00|||102||03072026|03072026|50,5|0||50,5|0|50,5|0||||",
    "|A170|1|1||50,5||||07|50,5|||07|50,5|||||",
    "|A990|7|",
    "|C001|1|", "|C990|2|", "|D001|1|", "|D990|2|", "|F001|1|", "|F990|2|", "|I001|1|", "|I990|2|",
    "|M001|0|", "|M200|0|0|0|0|0|0|0|0|0|0|0|0|",
    "|M400|07|150,5|||", "|M410|202|150,5|||",
    "|M600|0|0|0|0|0|0|0|0|0|0|0|0|",
    "|M800|07|150,5|||", "|M810|202|150,5|||",
    "|M990|8|",
    "|P001|1|", "|P990|2|", "|1001|1|", "|1990|2|",
    "|9001|0|",
]


def gravar_sped(pasta: Path, linhas: list[str], nome: str = "sped.txt", assinatura: bytes = b"") -> Path:
    caminho = pasta / nome
    caminho.write_bytes(("\r\n".join(linhas) + "\r\n").encode("iso-8859-1") + assinatura)
    return caminho


@pytest.fixture
def sped_ficticio(tmp_path) -> Path:
    return gravar_sped(tmp_path, com_bloco9(LINHAS_SPED_FICTICIO), assinatura=b"\x00\x01ASSINATURA-BINARIA")


def com_bloco9(linhas: list[str]) -> list[str]:
    """Acrescenta os 9900 (um por tipo, na ordem em que aparecem), o 9990 e o 9999, com as contagens certas."""
    tipos = [l.split("|")[1] for l in linhas] + ["9990", "9999"]
    ordem = list(dict.fromkeys(tipos))
    linhas_9900 = [f"|9900|{t}|{tipos.count(t)}|" for t in ordem] + [f"|9900|9900|{len(ordem) + 1}|"]
    bloco9 = sum(1 for l in linhas if l.startswith("|9")) + len(linhas_9900) + 2
    total = len(linhas) + len(linhas_9900) + 2
    return linhas + linhas_9900 + [f"|9990|{bloco9}|", f"|9999|{total}|"]
