"""Histórico de uso: junta os arquivos do log de uso numa planilha (e o próprio uso entra no log)."""

from __future__ import annotations

import ast
import time
from datetime import datetime

import openpyxl
import pytest

from central import log_uso, registro
from modulos.historico_uso import MODULO, processamento
from testes.conftest import RAIZ, esperar

TITULOS = "Data;Hora;Usuário;Computador;Versão;Módulo;Ação;Resultado"


@pytest.fixture(autouse=True)
def appdata_temporario(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))


@pytest.fixture
def pasta_log(tmp_path):
    """Dois computadores, dois meses (fictícios)."""
    pasta = tmp_path / "Log de uso"
    pasta.mkdir()
    (pasta / "2026-10 - PC-1 - ana.exemplo.csv").write_text("\r\n".join([
        TITULOS,
        "22/10/2026;08:00:00;ana.exemplo;PC-1;1.5.0;Central;Abriu a Central;ok",
        "22/10/2026;08:05:00;ana.exemplo;PC-1;1.5.0;Notas de Contrato;Conferir mês;ok",
        "23/10/2026;09:00:00;ana.exemplo;PC-1;1.5.0;Notas de Contrato;Conferir mês;erro",
        "linha estragada"]) + "\r\n", encoding="utf-8-sig")
    (pasta / "2026-09 - PC-2 - bruno.exemplo.csv").write_text("\r\n".join([
        TITULOS,
        "30/09/2026;14:00:00;bruno.exemplo;PC-2;1.4.2;Central;Abriu a Central;ok",
        "30/09/2026;14:10:00;bruno.exemplo;PC-2;1.4.2;Conciliação Bancária;Processar;ok"]) + "\r\n",
        encoding="utf-8-sig")
    return pasta


def test_le_todos_os_arquivos(pasta_log):
    resultado = processamento.ler_usos(pasta_log)
    assert resultado.arquivos == 2 and len(resultado.usos) == 5
    assert (resultado.usuarios, resultado.aberturas, resultado.processamentos) == (2, 2, 3)
    assert resultado.usos[0].momento == datetime(2026, 10, 23, 9, 0)          # o mais recente primeiro
    assert resultado.avisos == ["2026-10 - PC-1 - ana.exemplo.csv: 1 linha(s) fora do formato, ignorada(s)."]


def test_pasta_inexistente_da_mensagem_clara(tmp_path):
    assert "não foi encontrada" in processamento.ler_usos(tmp_path / "nao_existe").erro
    assert processamento.confirmar_pasta_log(tmp_path / "nao_existe")[1] == "erro"


def test_planilha(pasta_log, tmp_path):
    resultado = processamento.gerar_planilha(pasta_log, tmp_path, agora=datetime(2026, 10, 23, 18, 0))
    assert resultado.caminho_planilha.name == "Historico_de_uso_2026-10-23_180000.xlsx"
    livro = openpyxl.load_workbook(resultado.caminho_planilha)
    assert livro.sheetnames == ["Resumo por mês", "Por usuário", "Histórico", "Avisos"]
    resumo = [tuple(l[:5]) for l in livro["Resumo por mês"].iter_rows(min_row=2, values_only=True)]
    assert resumo == [("2026-10", "ana.exemplo", "Notas de Contrato", 2, 1),
                      ("2026-10", "ana.exemplo", "Central (aberturas)", 1, 0),
                      ("2026-09", "bruno.exemplo", "Conciliação Bancária", 1, 0),
                      ("2026-09", "bruno.exemplo", "Central (aberturas)", 1, 0)]
    usuarios = [tuple(l[:5]) for l in livro["Por usuário"].iter_rows(min_row=2, values_only=True)]
    assert usuarios[0] == ("ana.exemplo", "PC-1", 1, 2, "Notas de Contrato (2)")
    historico = list(livro["Histórico"].iter_rows(min_row=2, values_only=True))
    assert len(historico) == 5 and historico[0][7] == "erro"
    assert livro["Histórico"].cell(row=2, column=8).fill.fgColor.rgb.endswith(processamento.COR_ERRO)


def test_os_arquivos_da_rede_nunca_mudam(pasta_log, tmp_path):
    antes = {p.name: p.read_bytes() for p in pasta_log.iterdir()}
    processamento.gerar_planilha(pasta_log, tmp_path)
    assert {p.name: p.read_bytes() for p in pasta_log.iterdir()} == antes


def test_le_o_que_o_log_grava(monkeypatch, tmp_path):
    """O formato do log (central/log_uso.py) e a leitura daqui andam juntos."""
    monkeypatch.delenv(log_uso.VARIAVEL_DESLIGADO, raising=False)
    log_uso.registrar("Notas de Contrato", "Gerar pendências", agora=datetime(2026, 10, 23, 10, 0),
                      local=tmp_path / "local", rede=tmp_path / "rede", esperar=True)
    usos = processamento.ler_usos(tmp_path / "rede").usos
    assert [(u.modulo, u.acao, u.resultado) for u in usos] == [("Notas de Contrato", "Gerar pendências", "ok")]


# ---------------------------------------------------------------------------
# Tela
# ---------------------------------------------------------------------------

def test_modulo_no_menu_em_ferramentas():
    assert registro.SECAO_DO_MODULO["historico_uso"] == "FERRAMENTAS"
    assert MODULO.icone == "relogio" and (RAIZ / "central" / "icones" / "relogio.png").exists()
    assert (RAIZ / "modulos" / "historico_uso" / "INSTRUCOES_DE_USO.md").exists()


def test_tela_so_usa_o_processamento():
    arvore = ast.parse((RAIZ / "modulos" / "historico_uso" / "telas" / "historico.py").read_text(encoding="utf-8"))
    usados = {no.module for no in ast.walk(arvore) if isinstance(no, ast.ImportFrom) and no.module
              and no.module.startswith("modulos")}
    assert usados == {"modulos.historico_uso"}


def test_gerar_pela_tela_e_o_uso_entra_no_log(criar_painel, pasta_log, tmp_path, monkeypatch):
    monkeypatch.delenv(log_uso.VARIAVEL_DESLIGADO, raising=False)
    monkeypatch.setenv(log_uso.VARIAVEL_PASTA, str(tmp_path / "rede"))
    tela = criar_painel(MODULO).historico
    tela.abertos = []
    monkeypatch.setattr(tela, "abrir", tela.abertos.append)
    assert tela.cartao_log.caminho == tmp_path / "rede"                  # a pasta da rede já vem escolhida
    tela.cartao_log.definir_caminhos(pasta_log)
    tela.cartao_saida.definir_caminhos(tmp_path)
    tela.processar()
    esperar(tela, lambda: not tela.ocupado)
    assert tela.ultimo_resultado.caminho_planilha.exists()
    assert tela.resultado.selo.cget("text") == "Conferir"                # a linha estragada vira aviso
    tela.botoes_resultado["Abrir planilha"].invoke()
    assert tela.abertos == [tela.ultimo_resultado.caminho_planilha]
    assert processamento.ler_preferencias()["pasta_log"] == str(pasta_log)

    # o uso desta tela também foi registrado (o gancho do botão principal, em central/painel_base.py)
    limite = time.time() + 10
    while not list((tmp_path / "rede").glob("*.csv")) and time.time() < limite:
        time.sleep(0.05)
    usos = processamento.ler_usos(tmp_path / "rede").usos
    assert [(u.modulo, u.acao, u.resultado) for u in usos] == [("Histórico de uso", "Gerar planilha", "ok")]
