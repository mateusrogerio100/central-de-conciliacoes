"""Log de uso da Central (pedido da chefia, 23/10/2026): quem usou, quando e quais módulos.

Cada uso vira uma linha: data, hora, usuário do Windows, computador, versão, módulo, ação e resultado. São
registrados a abertura da Central e cada processamento (o botão principal de cada módulo).

Como as Centrais "se encontram": cada computador grava o SEU arquivo numa pasta da rede
(`<AAAA-MM> - <computador> - <usuário>.csv`), então ninguém escreve no arquivo de outro. O módulo Histórico
de uso lê todos e monta a planilha.

A tela nunca espera a rede (GUIA_DE_MANUTENCAO, seção 17): a linha é gravada primeiro numa fila local
(`%APPDATA%\\CentralConciliacoes\\log_uso_pendente.csv`) e mandada para a rede em segundo plano. Rede fora do
ar: a linha fica na fila e vai na próxima vez. Nada aqui levanta erro: o log nunca atrapalha o trabalho.

Os testes desligam o log (variável CENTRAL_LOG_USO_DESLIGADO, em testes\\conftest.py): nunca gravam na rede.
"""

from __future__ import annotations

import csv
import getpass
import io
import os
import re
import socket
import threading
from datetime import datetime
from pathlib import Path

from central import VERSAO

# A pasta da rede (decisão do usuário, 23/10/2026). Mudou? Troque aqui, ou use a variável de ambiente.
PASTA_REDE_PADRAO = Path(r"\\servidor-arquivos\contabilidade\CONCILIAÇÕES 2026\Automações\Dados\Log de uso")
VARIAVEL_PASTA = "CENTRAL_PASTA_LOG_USO"
VARIAVEL_DESLIGADO = "CENTRAL_LOG_USO_DESLIGADO"

COLUNAS = ("Data", "Hora", "Usuário", "Computador", "Versão", "Módulo", "Ação", "Resultado")
SEPARADOR = ";"
CODIFICACAO = "utf-8-sig"                  # o Excel abre com os acentos certos
NOME_ARQUIVO = "{ano_mes} - {computador} - {usuario}.csv"
NOME_FILA = "log_uso_pendente.csv"
NOME_ENVIANDO = "log_uso_enviando.csv"
MODULO_CENTRAL = "Central"
ACAO_ABRIR = "Abriu a Central"
RESULTADO_OK = "ok"
RESULTADO_ERRO = "erro"

_trava = threading.Lock()
_enviando = threading.Event()


def desligado() -> bool:
    return bool(os.environ.get(VARIAVEL_DESLIGADO))


def pasta_rede() -> Path:
    return Path(os.environ.get(VARIAVEL_PASTA) or PASTA_REDE_PADRAO)


def pasta_local() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "CentralConciliacoes"


def usuario() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return "desconhecido"


def computador() -> str:
    return os.environ.get("COMPUTERNAME") or socket.gethostname() or "desconhecido"


def _sem_caracteres_proibidos(texto: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", texto).strip() or "desconhecido"


def nome_do_arquivo(data: str, computador_: str, usuario_: str) -> str:
    """"23/10/2026" -> "2026-10 - CONT-05 - usuario.csv"."""
    dia, mes, ano = data.split("/")
    return NOME_ARQUIVO.format(ano_mes=f"{ano}-{mes}", computador=_sem_caracteres_proibidos(computador_),
                               usuario=_sem_caracteres_proibidos(usuario_))


def _texto_csv(linhas: list[list[str]], com_titulos: bool) -> str:
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=SEPARADOR, lineterminator="\r\n")
    if com_titulos:
        escritor.writerow(COLUNAS)
    escritor.writerows(linhas)
    return saida.getvalue()


def _ler_linhas(arquivo: Path) -> list[list[str]]:
    try:
        texto = arquivo.read_text(encoding=CODIFICACAO)
    except (OSError, UnicodeDecodeError):
        return []
    return [l for l in csv.reader(io.StringIO(texto), delimiter=SEPARADOR) if len(l) == len(COLUNAS)
            and tuple(l) != COLUNAS]


def _acrescentar(arquivo: Path, linhas: list[list[str]]) -> None:
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    novo = not arquivo.exists() or arquivo.stat().st_size == 0
    with open(arquivo, "a", encoding="utf-8" if not novo else CODIFICACAO, newline="") as saida:
        saida.write(_texto_csv(linhas, com_titulos=novo))


def registrar(modulo: str, acao: str, resultado: str = RESULTADO_OK, agora: datetime | None = None,
              local: Path | None = None, rede: Path | None = None, esperar: bool = False) -> None:
    """Grava o uso na fila local e manda para a rede em segundo plano. Nunca levanta erro.

    local / rede / esperar: só para os testes (pastas temporárias; esperar = manda já, na mesma thread).
    """
    if desligado():
        return
    agora = agora or datetime.now()
    linha = [agora.strftime("%d/%m/%Y"), agora.strftime("%H:%M:%S"), usuario(), computador(), VERSAO,
             modulo, acao, resultado]
    try:
        with _trava:
            _acrescentar((local or pasta_local()) / NOME_FILA, [linha])
    except OSError:
        return
    if esperar:
        enviar_pendentes(local, rede)
    else:
        enviar_em_segundo_plano(local, rede)


def enviar_pendentes(local: Path | None = None, rede: Path | None = None) -> int:
    """Manda a fila local para os arquivos da rede. Devolve quantas linhas foram. Rede fora: ficam na fila."""
    local, rede = local or pasta_local(), rede or pasta_rede()
    fila, enviando = local / NOME_FILA, local / NOME_ENVIANDO
    try:
        with _trava:
            # uma remessa interrompida (programa fechado no meio) vai antes; depois o que chegou
            if fila.exists():
                linhas = _ler_linhas(enviando) + _ler_linhas(fila)
                enviando.write_text(_texto_csv(linhas, com_titulos=True), encoding=CODIFICACAO)
                fila.unlink()
        linhas = _ler_linhas(enviando)
        if not linhas:
            enviando.unlink(missing_ok=True)
            return 0
    except OSError:
        return 0
    por_arquivo: dict[str, list[list[str]]] = {}
    for linha in linhas:
        por_arquivo.setdefault(nome_do_arquivo(linha[0], linha[3], linha[2]), []).append(linha)
    enviadas, sobra = 0, []
    for nome, grupo in por_arquivo.items():
        try:
            _acrescentar(rede / nome, grupo)
            enviadas += len(grupo)
        except OSError:
            sobra += grupo
    try:
        with _trava:
            enviando.unlink(missing_ok=True)
            if sobra:
                _acrescentar(fila, sobra)          # tenta de novo na próxima vez
    except OSError:
        pass
    return enviadas


def enviar_em_segundo_plano(local: Path | None = None, rede: Path | None = None) -> None:
    """Manda a fila numa thread separada (uma de cada vez): a tela nunca espera a rede."""
    if desligado() or _enviando.is_set():
        return
    _enviando.set()

    def enviar():
        try:
            enviar_pendentes(local, rede)
        finally:
            _enviando.clear()

    threading.Thread(target=enviar, daemon=True, name="log_uso").start()
