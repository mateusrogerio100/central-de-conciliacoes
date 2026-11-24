"""Proteções dos testes do módulo Escrituração de Serviços Tomados.

- Nenhum teste acessa a internet: a consulta de CNPJ é sempre simulada. Se algum código tentar
  abrir uma conexão, o teste falha na hora.
- O %APPDATA% aponta para uma pasta temporária: o cadastro de prestadores real nunca é tocado.
"""

from __future__ import annotations

import socket
import urllib.request

import pytest


class AcessoAInternetNoTeste(AssertionError):
    pass


def _bloqueado(*_, **__):
    raise AcessoAInternetNoTeste("um teste tentou acessar a internet")


@pytest.fixture(autouse=True)
def sem_internet_e_appdata_temporario(monkeypatch, tmp_path):
    monkeypatch.setattr(urllib.request, "urlopen", _bloqueado)
    monkeypatch.setattr(socket.socket, "connect", _bloqueado)
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
