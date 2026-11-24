"""Funções de apoio: valores em reais, números de conta e texto de PDF."""

import logging
import re
import unicodedata
from decimal import Decimal
from pathlib import Path

import pdfplumber
import pypdfium2

# A biblioteca de PDF (pdfminer) avisa sobre fontes mal descritas em alguns
# extratos ("Could not get FontBBox..."). Não afeta o texto; só polui a tela.
logging.getLogger("pdfminer").setLevel(logging.ERROR)

# Um PDF é considerado escaneado (imagem, sem texto) quando tem, em média,
# menos do que isto de caracteres não-brancos por página.
MINIMO_CARACTERES_POR_PAGINA = 20

# Número no formato brasileiro, sempre com 2 casas decimais:
# "1.117.461,33" (com ponto de milhar) ou "8893,49" (sem ponto de milhar).
# Os leitores usam PADRAO_VALOR dentro das suas expressões regulares.
PADRAO_VALOR = r"(?:\d{1,3}(?:\.\d{3})+|\d+),\d{2}"
# O mesmo, seguido de C (credor) ou D (devedor): "0,00 C", "4.136,14C".
PADRAO_VALOR_CD = PADRAO_VALOR + r"\s?[CD]\b"
_PADRAO_NUMERO_BR = re.compile(PADRAO_VALOR)


def converter_valor(texto: str) -> Decimal:
    """Converte um valor escrito no formato brasileiro para Decimal.

    Aceita:
      "1.117.461,33"  -> 1117461.33
      "8893,49"       -> 8893.49   (sem ponto de milhar)
      "539.300,00 D"  -> -539300.00 (D = devedor = negativo)
      "0,00 C"        -> 0.00       (C = credor = positivo)
      "R$ 228,18"     -> 228.18     (o "R$" é ignorado)
      "50,00C*"       -> 50.00      (o asterisco final é ignorado)
      "-1.234,56"     -> -1234.56

    Levanta ValueError se o texto não for um valor reconhecível — nunca
    devolve zero "por não ter entendido".
    """
    limpo = texto.strip().replace("R$", "").strip().rstrip("*").strip()

    negativo = False
    if limpo[-1:].upper() in ("C", "D"):
        negativo = limpo[-1].upper() == "D"
        limpo = limpo[:-1].strip()
    if limpo.startswith("-"):
        negativo = not negativo
        limpo = limpo[1:].strip()

    if not _PADRAO_NUMERO_BR.fullmatch(limpo):
        raise ValueError(f"valor em formato não reconhecido: {texto!r}")

    valor = Decimal(limpo.replace(".", "").replace(",", "."))
    if negativo and valor != 0:
        valor = -valor
    return valor


MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]


def numero_do_mes(nome: str) -> int | None:
    """"Agosto", "AGOSTO", "março", "MARCO" -> número do mês (1 a 12)."""
    simples = _sem_acento(nome.strip().lower())
    for numero, mes in enumerate(MESES, 1):
        if _sem_acento(mes) == simples:
            return numero
    return None


def _sem_acento(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def formatar_valor(valor: Decimal) -> str:
    """Escreve um valor no formato brasileiro: Decimal("-1234.5") -> "-1.234,50"."""
    texto = f"{abs(valor):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"-{texto}" if valor < 0 else texto


def valor_de_float(valor: float | int) -> Decimal:
    """Converte um número vindo do Excel (float) para Decimal com 2 casas.

    O Excel guarda 640,44 como 640.44000000000005; arredondar antes de
    converter evita carregar esse "lixo" para a comparação.
    """
    return Decimal(str(round(valor, 2))).quantize(Decimal("0.01"))


def normalizar_conta(texto: str) -> str:
    """Deixa o número da conta num formato único, para comparar.

    Mantém só dígitos e X (dígito verificador "x" vira "X") e remove os
    zeros à esquerda:
      "000568630703-9" -> "5686307039"
      "2.004.834-3"    -> "20048343"
      "400759-x"       -> "400759X"
    """
    so_digitos = re.sub(r"[^0-9X]", "", texto.upper())
    sem_zeros = so_digitos.lstrip("0")
    # Conta formada só de zeros: mantém um zero em vez de ficar vazia.
    if not sem_zeros and so_digitos:
        return "0"
    return sem_zeros


def extrair_paginas_pdf(arquivo: Path) -> list[str]:
    """Devolve o texto de cada página do PDF (página sem texto vira "")."""
    with pdfplumber.open(arquivo) as pdf:
        return [pagina.extract_text() or "" for pagina in pdf.pages]


def extrair_paginas_rapido(arquivo: Path) -> list[str]:
    """Texto de cada página por um caminho rápido (pypdfium2), só para a checagem de escaneado.

    O pdfplumber analisa cada traço desenhado na página antes de concluir que não há texto:
    num PDF do "Microsoft Print to PDF" (texto virado desenho) isso leva de segundos a minutos.
    O pypdfium2 responde em centésimos de segundo. O texto que os leitores usam continua vindo
    do pdfplumber (extrair_paginas_pdf): este aqui serve só para dizer "não tem texto".
    """
    documento = pypdfium2.PdfDocument(arquivo)
    try:
        paginas = []
        for numero in range(len(documento)):
            pagina = documento[numero]
            texto_pagina = pagina.get_textpage()
            paginas.append(texto_pagina.get_text_range())
            texto_pagina.close()
            pagina.close()
        return paginas
    finally:
        documento.close()


# Origem gravada no PDF ("Producer") quando ele foi salvo pela impressora do Windows: as letras viram
# desenho e o programa não acha texto. Pedido do usuário (12/11/2026): o aviso diz como salvar de novo.
PRODUTOR_PRINT_TO_PDF = "microsoft: print to pdf"


def produtor_do_pdf(arquivo: Path) -> str:
    """Programa que gerou o PDF (campo "Producer"), ou "" se não der para ler."""
    try:
        documento = pypdfium2.PdfDocument(arquivo)
    except Exception:
        return ""
    try:
        return (documento.get_metadata_dict().get("Producer") or "").strip()
    except Exception:
        return ""
    finally:
        documento.close()


def mensagem_pdf_sem_texto(arquivo: Path, quantidade_paginas: int) -> str:
    """Mensagem do ESCANEADO: se o PDF veio do "Microsoft Print to PDF", diz como salvar de novo."""
    inicio = f"PDF sem texto ({quantidade_paginas} página(s))"
    if produtor_do_pdf(arquivo).lower() == PRODUTOR_PRINT_TO_PDF:
        return (f"{inicio}: foi salvo pelo \"Microsoft Print to PDF\", que grava as letras como imagem. "
                "Salve de novo pelo navegador (Imprimir → Destino \"Salvar como PDF\") e rode outra vez")
    return f"{inicio}; provavelmente escaneado"


def juntar_paginas(paginas: list[str]) -> str:
    """Junta o texto das páginas num texto só, uma página após a outra."""
    return "\n".join(paginas)


def extrair_texto_pdf(arquivo: Path) -> str:
    """Devolve o texto completo do PDF (todas as páginas concatenadas)."""
    return juntar_paginas(extrair_paginas_pdf(arquivo))


def texto_com_paginas(paginas: list[str]) -> str:
    """Texto do PDF com uma linha separando cada página (formato do --mostrar-texto)."""
    partes = []
    for numero, texto in enumerate(paginas, 1):
        partes.append(f"===== Página {numero} de {len(paginas)} =====")
        partes.append(texto)
    return "\n".join(partes)


def parece_escaneado(paginas: list[str]) -> bool:
    """True se o PDF parece ser só imagem (escaneado), sem texto de verdade.

    Soma os caracteres não-brancos de todas as páginas e compara com
    MINIMO_CARACTERES_POR_PAGINA vezes o número de páginas.
    """
    if not paginas:
        return True
    caracteres = sum(len(re.sub(r"\s", "", pagina)) for pagina in paginas)
    return caracteres < MINIMO_CARACTERES_POR_PAGINA * len(paginas)
