"""Log de uso da Central (central/log_uso.py): quem usou, quando, quais módulos.

Tudo em pastas temporárias: nenhum teste grava na pasta da rede (o log fica desligado nos outros testes,
pela variável de testes\\conftest.py; aqui ele é religado só dentro de cada teste).
"""

from __future__ import annotations

import time
from datetime import datetime

import pytest

from central import VERSAO, log_uso
from testes.conftest import abrir_janela_ctk

MOMENTO = datetime(2026, 10, 23, 9, 15, 0)


@pytest.fixture
def pastas(monkeypatch, tmp_path):
    """Log ligado, com a fila local e a "rede" em pastas temporárias; usuário e computador fictícios."""
    monkeypatch.delenv(log_uso.VARIAVEL_DESLIGADO, raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv(log_uso.VARIAVEL_PASTA, str(tmp_path / "rede"))
    monkeypatch.setattr(log_uso, "usuario", lambda: "usuario.exemplo")
    monkeypatch.setattr(log_uso, "computador", lambda: "PC-EXEMPLO")
    return log_uso.pasta_local(), log_uso.pasta_rede()


def _linhas(arquivo):
    return arquivo.read_text(encoding="utf-8-sig").splitlines()


def test_cada_uso_vira_uma_linha_no_arquivo_do_computador(pastas):
    local, rede = pastas
    log_uso.registrar("Central", "Abriu a Central", agora=MOMENTO, esperar=True)
    log_uso.registrar("Notas de Contrato", "Conferir mês", "erro", agora=MOMENTO.replace(minute=20), esperar=True)
    arquivo = rede / "2026-10 - PC-EXEMPLO - usuario.exemplo.csv"
    assert _linhas(arquivo) == [
        "Data;Hora;Usuário;Computador;Versão;Módulo;Ação;Resultado",
        f"23/10/2026;09:15:00;usuario.exemplo;PC-EXEMPLO;{VERSAO};Central;Abriu a Central;ok",
        f"23/10/2026;09:20:00;usuario.exemplo;PC-EXEMPLO;{VERSAO};Notas de Contrato;Conferir mês;erro",
    ]
    assert not (local / log_uso.NOME_FILA).exists()                     # a fila local ficou vazia


def test_um_arquivo_por_mes(pastas):
    _, rede = pastas
    log_uso.registrar("Central", "Abriu a Central", agora=MOMENTO, esperar=True)
    log_uso.registrar("Central", "Abriu a Central", agora=datetime(2026, 11, 3, 8, 0), esperar=True)
    assert sorted(p.name for p in rede.iterdir()) == ["2026-10 - PC-EXEMPLO - usuario.exemplo.csv",
                                                      "2026-11 - PC-EXEMPLO - usuario.exemplo.csv"]


def test_rede_fora_do_ar_guarda_e_manda_depois(pastas, tmp_path):
    local, rede = pastas
    fora = tmp_path / "um_arquivo"
    fora.write_text("não é pasta", encoding="utf-8")                      # gravar "dentro" dele falha
    log_uso.registrar("Central", "Abriu a Central", agora=MOMENTO, rede=fora / "log", esperar=True)
    assert len(_linhas(local / log_uso.NOME_FILA)) == 2                   # título + o uso, esperando a rede
    log_uso.registrar("Bancos", "Processar", agora=MOMENTO.replace(hour=10), esperar=True)   # a rede voltou
    linhas = _linhas(rede / "2026-10 - PC-EXEMPLO - usuario.exemplo.csv")
    assert [l.split(";")[6] for l in linhas[1:]] == ["Abriu a Central", "Processar"]
    assert not (local / log_uso.NOME_FILA).exists()


def test_remessa_interrompida_vai_na_proxima(pastas):
    local, rede = pastas
    local.mkdir(parents=True)
    (local / log_uso.NOME_ENVIANDO).write_text(
        "Data;Hora;Usuário;Computador;Versão;Módulo;Ação;Resultado\r\n"
        "22/10/2026;17:00:00;usuario.exemplo;PC-EXEMPLO;1.4.2;Central;Abriu a Central;ok\r\n", encoding="utf-8-sig")
    log_uso.registrar("Central", "Abriu a Central", agora=MOMENTO, esperar=True)
    assert len(_linhas(rede / "2026-10 - PC-EXEMPLO - usuario.exemplo.csv")) == 3
    assert not (local / log_uso.NOME_ENVIANDO).exists()


def test_desligado_nao_grava_nada(pastas, monkeypatch):
    local, rede = pastas
    monkeypatch.setenv(log_uso.VARIAVEL_DESLIGADO, "1")
    log_uso.registrar("Central", "Abriu a Central", agora=MOMENTO, esperar=True)
    assert not local.exists() and not rede.exists()


def test_nunca_atrapalha_o_trabalho(pastas, tmp_path):
    bloqueio = tmp_path / "bloqueio"
    bloqueio.write_text("", encoding="utf-8")
    log_uso.registrar("Central", "Abriu a Central", local=bloqueio / "x", esperar=True)   # sem erro
    assert log_uso.enviar_pendentes(bloqueio / "x") == 0


def test_em_segundo_plano(pastas):
    _, rede = pastas
    log_uso.registrar("Central", "Abriu a Central", agora=MOMENTO)
    limite = time.time() + 10
    while not (rede / "2026-10 - PC-EXEMPLO - usuario.exemplo.csv").exists() and time.time() < limite:
        time.sleep(0.05)
    assert (rede / "2026-10 - PC-EXEMPLO - usuario.exemplo.csv").exists()


def test_nome_do_arquivo_sem_caracteres_proibidos():
    assert log_uso.nome_do_arquivo("01/12/2026", "PC:1", "DOMINIO\\fulano") == "2026-12 - PC_1 - DOMINIO_fulano.csv"


def test_pasta_da_rede_combinada():
    assert str(log_uso.PASTA_REDE_PADRAO) == r"\\servidor-arquivos\contabilidade\CONCILIAÇÕES 2026\Automações\Dados\Log de uso"


def test_a_central_registra_a_abertura(pastas):
    from central import janela as modulo_janela

    janela = abrir_janela_ctk(modulo_janela.JanelaCentral)
    try:
        limite = time.time() + 10
        arquivo = pastas[1] / f"{datetime.now():%Y-%m} - PC-EXEMPLO - usuario.exemplo.csv"
        while not arquivo.exists() and time.time() < limite:
            janela.update()
            time.sleep(0.05)
        assert _linhas(arquivo)[1].endswith(";Central;Abriu a Central;ok")
    finally:
        janela.destroy()
