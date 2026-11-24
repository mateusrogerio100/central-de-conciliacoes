"""
Manda os PDFs para a impressora do Windows (ESPECIFICACAO seção 19).

Decisões do usuário (out/2026):
- **Uma impressão só** para todos os PDFs marcados: na fila da impressora (usada por várias pessoas)
  eles formam um bloco e saem juntos, na ordem da lista, sem folha de outra pessoa no meio.
- **Um lado só, uma página por folha**, mesmo que a impressora esteja com frente e verso como padrão.

O próprio programa desenha cada página na impressora com o pdfium (o mesmo leitor de PDF usado para
contar as páginas): não abre o Acrobat nem nenhuma janela. Página deitada sai em paisagem; página
maior que a área de impressão é reduzida para caber (nunca ampliada), centralizada.

A conversa com o Windows fica em `DispositivoWindows`; os testes usam um dispositivo falso ou a
impressora "Microsoft Print to PDF" gravando num arquivo (sem papel).
"""

from __future__ import annotations

import ctypes
import struct
import sys
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from modulos.imprimir_pdfs.pdfs import PdfParaImprimir, total_de_folhas

NOME_DO_PROGRAMA = "Central de Conciliações"


class ErroDeImpressao(Exception):
    """Problema ao falar com a impressora: a mensagem já está pronta para a tela."""


@dataclass
class AreaDaFolha:
    """A área imprimível da folha, em pixels da impressora, e a resolução (pontos por polegada)."""

    largura: int
    altura: int
    dpi_x: int
    dpi_y: int


@dataclass
class Envio:
    """O que foi mandado: as folhas e o nome do trabalho na fila (para acompanhá-lo depois)."""

    folhas: int
    nome_trabalho: str


def nome_do_trabalho(pdfs, hora: datetime | None = None) -> str:
    """O nome que aparece na fila: 'Central de Conciliações – 16 PDFs (18 folhas) – 10:42:05'.

    O horário deixa o nome único: é por ele que o programa acha o trabalho na fila (impressao.fila)."""
    quantidade, folhas = len(pdfs), total_de_folhas(pdfs)
    texto = (f"{NOME_DO_PROGRAMA} – {quantidade} PDF{'s' if quantidade != 1 else ''} "
             f"({folhas} folha{'s' if folhas != 1 else ''})")
    return f"{texto} – {hora:%H:%M:%S}" if hora else texto


def posicao_na_folha(largura_pt: float, altura_pt: float, area: AreaDaFolha) -> tuple[int, int, int, int]:
    """Onde desenhar a página (x, y, largura, altura em pixels): tamanho real, reduzida se não couber, centralizada."""
    largura = largura_pt / 72 * area.dpi_x
    altura = altura_pt / 72 * area.dpi_y
    escala = min(1.0, area.largura / largura, area.altura / altura)
    largura, altura = round(largura * escala), round(altura * escala)
    return (area.largura - largura) // 2, (area.altura - altura) // 2, largura, altura


def imprimir(
    pdfs: list[PdfParaImprimir],
    impressora: str,
    *,
    arquivo_saida: Path | None = None,
    ao_avancar: Callable[[int, int], None] | None = None,
    dispositivo=None,
) -> Envio:
    """
    Imprime os PDFs, na ordem, numa impressão só. Devolve as folhas mandadas e o nome do trabalho na fila.

    `ao_avancar(folha, total)` é chamado depois de cada folha (para a barra de andamento).
    `arquivo_saida` só serve para impressoras que gravam arquivo (Microsoft Print to PDF).
    Todos os PDFs são abertos antes de começar: se um não abrir, nada vai para a fila.
    """
    import pypdfium2
    import pypdfium2.raw as pdfium

    validos = [p for p in pdfs if p.folhas]
    if not validos:
        raise ErroDeImpressao("Nenhum PDF para imprimir.")
    total = total_de_folhas(validos)

    documentos = []
    try:
        for pdf in validos:
            try:
                documento = pypdfium2.PdfDocument(str(pdf.caminho))
            except Exception as erro:
                raise ErroDeImpressao(f"Não foi possível abrir {pdf.nome}: {erro}") from erro
            documentos.append(documento)
            if pdf.paginas_para_imprimir()[-1] > len(documento) or pdf.paginas_para_imprimir()[0] < 1:
                raise ErroDeImpressao(f"O arquivo {pdf.nome} mudou depois de escolhido (agora tem "
                                      f"{len(documento)} página(s)). Escolha os PDFs de novo.")

        if dispositivo is None:
            dispositivo = DispositivoWindows(impressora, arquivo_saida)
        nome = nome_do_trabalho(validos, datetime.now())
        dispositivo.iniciar(nome)
        folha = 0
        try:
            for pdf, documento in zip(validos, documentos):
                for numero in pdf.paginas_para_imprimir():
                    pagina = documento[numero - 1]
                    try:
                        largura_pt, altura_pt = pagina.get_size()
                        area = dispositivo.nova_folha(paisagem=largura_pt > altura_pt)
                        x, y, largura, altura = posicao_na_folha(largura_pt, altura_pt, area)
                        dispositivo.desenhar(pagina.raw, x, y, largura, altura,
                                             pdfium.FPDF_ANNOT | pdfium.FPDF_PRINTING)
                        dispositivo.fechar_folha()
                    finally:
                        pagina.close()
                    folha += 1
                    if ao_avancar:
                        ao_avancar(folha, total)
        except BaseException:
            dispositivo.cancelar()
            raise
        dispositivo.terminar()
        return Envio(folha, nome)
    finally:
        for documento in documentos:
            documento.close()


# ---------------------------------------------------------------------------------------------
# Windows (winspool / gdi32 pela ctypes, sem instalar nada)
# ---------------------------------------------------------------------------------------------

_PRINTER_ENUM_LOCAL = 0x2
_PRINTER_ENUM_CONNECTIONS = 0x4
_DM_OUT_BUFFER = 0x2
_DM_IN_BUFFER = 0x8
_DM_ORIENTATION = 0x1
_DM_COPIES = 0x100
_DM_DUPLEX = 0x1000
_DMORIENT_RETRATO, _DMORIENT_PAISAGEM = 1, 2
_DMDUP_SIMPLEX = 1
_HORZRES, _VERTRES, _LOGPIXELSX, _LOGPIXELSY = 8, 10, 88, 90
# Posições (em bytes) dos campos do DEVMODEW (wingdi.h)
_POS_FIELDS, _POS_ORIENTATION, _POS_COPIES, _POS_DUPLEX = 72, 76, 86, 94


class _PRINTER_INFO_4W(ctypes.Structure):
    _fields_ = [("pPrinterName", wintypes.LPWSTR), ("pServerName", wintypes.LPWSTR),
                ("Attributes", wintypes.DWORD)]


class _DOCINFOW(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_int), ("lpszDocName", wintypes.LPCWSTR),
                ("lpszOutput", wintypes.LPCWSTR), ("lpszDatatype", wintypes.LPCWSTR),
                ("fwType", wintypes.DWORD)]


def _bibliotecas():
    if sys.platform != "win32":
        raise ErroDeImpressao("A impressão só funciona no Windows.")
    winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    winspool.OpenPrinterW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.HANDLE), ctypes.c_void_p]
    winspool.ClosePrinter.argtypes = [wintypes.HANDLE]
    winspool.DocumentPropertiesW.argtypes = [wintypes.HWND, wintypes.HANDLE, wintypes.LPCWSTR,
                                             ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD]
    winspool.DocumentPropertiesW.restype = ctypes.c_long
    gdi32.CreateDCW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p]
    gdi32.CreateDCW.restype = wintypes.HDC
    gdi32.ResetDCW.argtypes = [wintypes.HDC, ctypes.c_void_p]
    gdi32.ResetDCW.restype = wintypes.HDC
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    gdi32.GetDeviceCaps.argtypes = [wintypes.HDC, ctypes.c_int]
    gdi32.StartDocW.argtypes = [wintypes.HDC, ctypes.POINTER(_DOCINFOW)]
    for nome in ("StartPage", "EndPage", "EndDoc", "AbortDoc"):
        getattr(gdi32, nome).argtypes = [wintypes.HDC]
    return winspool, gdi32


def listar_impressoras() -> list[str]:
    """As impressoras instaladas neste computador (locais e de rede), em ordem alfabética."""
    winspool, _ = _bibliotecas()
    flags = _PRINTER_ENUM_LOCAL | _PRINTER_ENUM_CONNECTIONS
    necessario, quantidade = wintypes.DWORD(), wintypes.DWORD()
    winspool.EnumPrintersW(flags, None, 4, None, 0, ctypes.byref(necessario), ctypes.byref(quantidade))
    if not necessario.value:
        return []
    memoria = ctypes.create_string_buffer(necessario.value)
    if not winspool.EnumPrintersW(flags, None, 4, memoria, necessario, ctypes.byref(necessario),
                                  ctypes.byref(quantidade)):
        return []
    itens = ctypes.cast(memoria, ctypes.POINTER(_PRINTER_INFO_4W))
    return sorted({itens[i].pPrinterName for i in range(quantidade.value)}, key=str.casefold)


def impressora_padrao() -> str:
    """A impressora padrão do Windows ('' se não houver)."""
    winspool, _ = _bibliotecas()
    tamanho = wintypes.DWORD()
    winspool.GetDefaultPrinterW(None, ctypes.byref(tamanho))
    if not tamanho.value:
        return ""
    texto = ctypes.create_unicode_buffer(tamanho.value)
    return texto.value if winspool.GetDefaultPrinterW(texto, ctypes.byref(tamanho)) else ""


class DispositivoWindows:
    """Uma impressão na fila do Windows: um lado só, uma cópia, retrato ou paisagem por folha."""

    def __init__(self, impressora: str, arquivo_saida: Path | None = None):
        self._winspool, self._gdi32 = _bibliotecas()
        self.impressora = impressora
        self.arquivo_saida = arquivo_saida
        self._configuracao = self._ler_configuracao()
        self._paisagem = False
        self._hdc = self._gdi32.CreateDCW("WINSPOOL", impressora, None, self._configuracao)
        if not self._hdc:
            raise ErroDeImpressao(f"Não foi possível usar a impressora \"{impressora}\".")
        self._iniciado = False

    def _ler_configuracao(self):
        """O DEVMODE da impressora, já com um lado só, uma cópia e retrato."""
        alca = wintypes.HANDLE()
        if not self._winspool.OpenPrinterW(self.impressora, ctypes.byref(alca), None):
            raise ErroDeImpressao(f"Impressora não encontrada: \"{self.impressora}\".")
        try:
            tamanho = self._winspool.DocumentPropertiesW(None, alca, self.impressora, None, None, 0)
            if tamanho <= 0:
                raise ErroDeImpressao(f"Não foi possível ler a configuração da impressora \"{self.impressora}\".")
            configuracao = ctypes.create_string_buffer(tamanho)
            if self._winspool.DocumentPropertiesW(None, alca, self.impressora, configuracao, None,
                                                  _DM_OUT_BUFFER) < 0:
                raise ErroDeImpressao(f"Não foi possível ler a configuração da impressora \"{self.impressora}\".")
            self._ajustar(configuracao, _DMORIENT_RETRATO)
            # o driver confere e completa o que foi mudado
            self._winspool.DocumentPropertiesW(None, alca, self.impressora, configuracao, configuracao,
                                               _DM_IN_BUFFER | _DM_OUT_BUFFER)
            return configuracao
        finally:
            self._winspool.ClosePrinter(alca)

    @staticmethod
    def _ajustar(configuracao, orientacao: int) -> None:
        campos = struct.unpack_from("<I", configuracao, _POS_FIELDS)[0]
        struct.pack_into("<I", configuracao, _POS_FIELDS, campos | _DM_ORIENTATION | _DM_COPIES | _DM_DUPLEX)
        struct.pack_into("<h", configuracao, _POS_ORIENTATION, orientacao)
        struct.pack_into("<h", configuracao, _POS_COPIES, 1)
        struct.pack_into("<h", configuracao, _POS_DUPLEX, _DMDUP_SIMPLEX)

    def iniciar(self, nome: str) -> None:
        documento = _DOCINFOW(ctypes.sizeof(_DOCINFOW), nome,
                              str(self.arquivo_saida) if self.arquivo_saida else None, None, 0)
        if self._gdi32.StartDocW(self._hdc, ctypes.byref(documento)) <= 0:
            erro = ctypes.get_last_error()
            self._liberar()
            if erro == 1223:  # ERROR_CANCELLED: a pessoa cancelou a janela da impressora
                raise ErroDeImpressao("Impressão cancelada.")
            raise ErroDeImpressao(f"A impressora \"{self.impressora}\" não aceitou a impressão (erro {erro}).")
        self._iniciado = True

    def nova_folha(self, paisagem: bool) -> AreaDaFolha:
        if paisagem != self._paisagem:
            self._ajustar(self._configuracao, _DMORIENT_PAISAGEM if paisagem else _DMORIENT_RETRATO)
            self._gdi32.ResetDCW(self._hdc, self._configuracao)
            self._paisagem = paisagem
        if self._gdi32.StartPage(self._hdc) <= 0:
            raise ErroDeImpressao("A impressora parou de responder no meio da impressão.")
        caps = self._gdi32.GetDeviceCaps
        return AreaDaFolha(caps(self._hdc, _HORZRES), caps(self._hdc, _VERTRES),
                           caps(self._hdc, _LOGPIXELSX), caps(self._hdc, _LOGPIXELSY))

    def desenhar(self, pagina, x: int, y: int, largura: int, altura: int, opcoes: int) -> None:
        import pypdfium2.raw as pdfium

        pdfium.FPDF_RenderPage(self._hdc, pagina, x, y, largura, altura, 0, opcoes)

    def fechar_folha(self) -> None:
        if self._gdi32.EndPage(self._hdc) <= 0:
            raise ErroDeImpressao("A impressora parou de responder no meio da impressão.")

    def terminar(self) -> None:
        try:
            if self._gdi32.EndDoc(self._hdc) <= 0:
                raise ErroDeImpressao("A impressora não confirmou o fim da impressão.")
            self._iniciado = False
        finally:
            self._liberar()

    def cancelar(self) -> None:
        if self._iniciado:
            self._gdi32.AbortDoc(self._hdc)
            self._iniciado = False
        self._liberar()

    def _liberar(self) -> None:
        if self._hdc:
            self._gdi32.DeleteDC(self._hdc)
            self._hdc = None
