"""
A fila da impressora: abrir a janela da fila do Windows e acompanhar o trabalho mandado (ESPECIFICACAO 19.1).

Pedido do usuário (out/2026): às vezes a impressora fica "aguardando" e não imprime — foi visto um trabalho do
programa parado na fila do servidor como "Pausado, Colocando no spool", com 0 bytes. Depois de mandar, a tela
acompanha o trabalho por um tempo e avisa se ele ficar pausado, com erro, sem papel etc.

O trabalho é achado na fila pelo nome (com o horário, único: impressora.nome_do_trabalho) e pelo usuário,
porque o número do trabalho no computador pode ser diferente do número no servidor de impressão.
"""

from __future__ import annotations

import ctypes
import getpass
import subprocess
import sys
import time
from ctypes import wintypes
from dataclasses import dataclass
from typing import Callable

from modulos.imprimir_pdfs.impressora import ErroDeImpressao

# Status do trabalho (winspool.h, JOB_STATUS_*)
PAUSADO = 0x1
ERRO = 0x2
APAGANDO = 0x4
NO_SPOOL = 0x8
IMPRIMINDO = 0x10
DESLIGADA = 0x20
SEM_PAPEL = 0x40
IMPRESSO = 0x80
APAGADO = 0x100
BLOQUEADO = 0x200
PRECISA_DE_ALGUEM = 0x400
COMPLETO = 0x1000

OK, ATENCAO, PROBLEMA = "ok", "atencao", "erro"


@dataclass
class TrabalhoNaFila:
    """Um trabalho da fila, como o Windows informa."""

    documento: str
    usuario: str
    status: int = 0
    texto_status: str = ""      # texto livre que o driver às vezes põe ("Aguardando…")
    posicao: int = 0
    paginas: int = 0
    paginas_impressas: int = 0


@dataclass
class EstadoNaFila:
    """O que a tela mostra sobre o trabalho: o texto, o tom (ok/atencao/erro) e se já acabou de acompanhar."""

    texto: str
    nivel: str
    final: bool = False


def interpretar(trabalho: TrabalhoNaFila | None, ja_visto: bool) -> EstadoNaFila:
    """Traduz o estado do trabalho na fila para a tela.

    `trabalho` None = não está na fila. Se ele já tinha sido visto, saiu (foi para a impressora); se nunca
    apareceu, ainda pode estar a caminho do servidor."""
    if trabalho is None:
        if ja_visto:
            return EstadoNaFila("Saiu da fila: já foi para a impressora.", OK, final=True)
        return EstadoNaFila("Procurando a impressão na fila...", ATENCAO)
    status = trabalho.status
    extra = f" ({trabalho.texto_status})" if trabalho.texto_status else ""
    problemas = [
        # na empresa, um programa de cota suspende as impressões de quem passou do limite (visto em out/2026)
        (PAUSADO, "está PAUSADA na fila. Pode ser o limite de impressões da sua conta (cota) — fale com o TI —, "
                  "ou clique em Ver fila da impressora e em Continuar"),
        (SEM_PAPEL, "está parada: a impressora está SEM PAPEL"),
        (DESLIGADA, "está parada: a impressora está DESLIGADA ou fora da rede"),
        (PRECISA_DE_ALGUEM, "está parada: a impressora precisa de atenção (veja o visor dela)"),
        (BLOQUEADO, "está BLOQUEADA na fila. Abra a fila da impressora para ver o motivo"),
        (ERRO, "deu ERRO na fila. Abra a fila da impressora para ver o motivo"),
    ]
    for bit, texto in problemas:
        if status & bit:
            return EstadoNaFila(f"A impressão {texto}{extra}.", PROBLEMA)
    if status & (APAGANDO | APAGADO):
        return EstadoNaFila("A impressão foi cancelada na fila.", PROBLEMA, final=True)
    if status & (IMPRESSO | COMPLETO):
        return EstadoNaFila("A impressora recebeu a impressão.", OK, final=True)
    if status & IMPRIMINDO:
        andamento = (f": página {trabalho.paginas_impressas} de {trabalho.paginas}"
                     if trabalho.paginas and trabalho.paginas_impressas else "")
        return EstadoNaFila(f"Imprimindo{andamento}{extra}.", OK)
    if trabalho.posicao > 1:
        return EstadoNaFila(f"Na fila, aguardando a vez: há {trabalho.posicao - 1} impressão(ões) na frente{extra}.",
                            ATENCAO)
    if status & NO_SPOOL:
        return EstadoNaFila(f"Chegando no servidor de impressão{extra}...", ATENCAO)
    return EstadoNaFila(f"Na fila, esperando a impressora começar{extra}.", ATENCAO)


def procurar(trabalhos: list[TrabalhoNaFila], nome_trabalho: str, usuario: str | None = None) -> TrabalhoNaFila | None:
    usuario = (usuario or usuario_atual()).casefold()
    for trabalho in trabalhos:
        if trabalho.documento == nome_trabalho and (not trabalho.usuario or trabalho.usuario.casefold() == usuario):
            return trabalho
    return None


def usuario_atual() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return ""


def acompanhar(
    nome_trabalho: str,
    consultar: Callable[[], list[TrabalhoNaFila]],
    ao_mudar: Callable[[EstadoNaFila], None],
    parar: Callable[[], bool] = lambda: False,
    intervalo: float = 2.0,
    limite: float = 120.0,
    espera: Callable[[float], None] = time.sleep,
) -> EstadoNaFila:
    """Consulta a fila a cada `intervalo` segundos até o trabalho sair dela (ou `limite` segundos).

    Chama `ao_mudar(estado)` só quando o texto muda. Um problema não encerra: a pessoa pode clicar em
    Continuar na fila e a impressão seguir. Erro ao consultar a fila não derruba nada: vira um aviso."""
    ja_visto = False
    ultimo: EstadoNaFila | None = None
    decorrido = 0.0
    while True:
        try:
            trabalho = procurar(consultar(), nome_trabalho)
        except (ErroDeImpressao, OSError) as erro:
            estado = EstadoNaFila(f"Não foi possível consultar a fila da impressora ({erro}).", ATENCAO, final=True)
        else:
            ja_visto = ja_visto or trabalho is not None
            estado = interpretar(trabalho, ja_visto)
            if trabalho is None and not ja_visto and decorrido >= 6:
                # impressão rápida sai da fila antes da primeira consulta; as que travam ficam à vista
                estado = EstadoNaFila("A impressão já não está na fila: foi para a impressora. Se não saiu nada, "
                                      "clique em Ver fila da impressora.", OK, final=True)
        if ultimo is None or estado.texto != ultimo.texto:
            ao_mudar(estado)
        ultimo = estado
        if estado.final or parar():
            return estado
        if decorrido >= limite:
            final = EstadoNaFila(f"Depois de {int(limite // 60)} minutos a impressão continua na fila: "
                                 f"{estado.texto[0].lower()}{estado.texto[1:]} Abra a fila da impressora para "
                                 "conferir.", PROBLEMA if estado.nivel == PROBLEMA else ATENCAO, final=True)
            ao_mudar(final)
            return final
        espera(intervalo)
        decorrido += intervalo


# ---------------------------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------------------------

class _SYSTEMTIME(ctypes.Structure):
    _fields_ = [(nome, wintypes.WORD) for nome in ("wYear", "wMonth", "wDayOfWeek", "wDay", "wHour", "wMinute",
                                                   "wSecond", "wMilliseconds")]


class _JOB_INFO_1W(ctypes.Structure):
    _fields_ = [("JobId", wintypes.DWORD), ("pPrinterName", wintypes.LPWSTR), ("pMachineName", wintypes.LPWSTR),
                ("pUserName", wintypes.LPWSTR), ("pDocument", wintypes.LPWSTR), ("pDatatype", wintypes.LPWSTR),
                ("pStatus", wintypes.LPWSTR), ("Status", wintypes.DWORD), ("Priority", wintypes.DWORD),
                ("Position", wintypes.DWORD), ("TotalPages", wintypes.DWORD), ("PagesPrinted", wintypes.DWORD),
                ("Submitted", _SYSTEMTIME)]


def listar_trabalhos(impressora: str) -> list[TrabalhoNaFila]:
    """Os trabalhos que estão agora na fila da impressora (de todos os usuários que o Windows mostrar)."""
    if sys.platform != "win32":
        raise ErroDeImpressao("A fila da impressora só pode ser consultada no Windows.")
    winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)
    winspool.OpenPrinterW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.HANDLE), ctypes.c_void_p]
    winspool.ClosePrinter.argtypes = [wintypes.HANDLE]
    winspool.EnumJobsW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                   wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD)]
    alca = wintypes.HANDLE()
    if not winspool.OpenPrinterW(impressora, ctypes.byref(alca), None):
        raise ErroDeImpressao(f"impressora \"{impressora}\" não encontrada")
    try:
        necessario, quantidade = wintypes.DWORD(), wintypes.DWORD()
        winspool.EnumJobsW(alca, 0, 999, 1, None, 0, ctypes.byref(necessario), ctypes.byref(quantidade))
        if not necessario.value:
            return []
        memoria = ctypes.create_string_buffer(necessario.value)
        if not winspool.EnumJobsW(alca, 0, 999, 1, memoria, necessario, ctypes.byref(necessario),
                                  ctypes.byref(quantidade)):
            raise ErroDeImpressao(f"erro {ctypes.get_last_error()} ao ler a fila")
        itens = ctypes.cast(memoria, ctypes.POINTER(_JOB_INFO_1W))
        return [TrabalhoNaFila(documento=itens[i].pDocument or "", usuario=itens[i].pUserName or "",
                               status=itens[i].Status, texto_status=(itens[i].pStatus or "").strip(),
                               posicao=itens[i].Position, paginas=itens[i].TotalPages,
                               paginas_impressas=itens[i].PagesPrinted)
                for i in range(quantidade.value)]
    finally:
        winspool.ClosePrinter(alca)


def abrir_fila(impressora: str) -> None:
    """Abre a janela da fila de impressão do Windows para a impressora (a mesma de Configurações → Impressoras)."""
    if sys.platform != "win32":
        raise ErroDeImpressao("A fila da impressora só pode ser aberta no Windows.")
    try:
        subprocess.Popen(["rundll32.exe", "printui.dll,PrintUIEntry", "/o", "/n", impressora])
    except OSError as erro:
        raise ErroDeImpressao(f"Não foi possível abrir a fila da impressora: {erro}") from erro
