"""Pasta das notas -> notas lidas + falhas de leitura. Regras L1, L2, L5, L6, X1 a X4 e seção 3.4.

- L1: todos os .pdf (e .xml, X1) da pasta e das subpastas, em ordem de caminho (a mesma a cada
  execução).
- L2: o tipo do PDF sai do texto: "DANFSe" = nota de serviço; "DANFE" e "CHAVE DE ACESSO" = nota
  de compra; senão, erro de leitura. L2a: a Nota Paulistana (NFS-e de São Paulo) também é nota de
  serviço (leitor_paulistana.py).
- L5: um PDF com problema vira FalhaLeitura com a explicação e os demais continuam.
- L6: mesma chave de acesso em dois arquivos: vale o primeiro; o outro fica marcado como repetido.
- 3.4: o _sem_pdf.txt do download em lote traz as chaves das notas que vieram sem DANFE.
- X2: XML e PDF da mesma nota (mesma chave) viram uma nota só: os dados vêm do XML; a situação
  (cancelada, substituída) vem do PDF, porque o XML não diz se a nota foi cancelada depois.
- X3: a L6 vale entre XMLs (mesma chave em dois XMLs) e entre PDFs, separadamente.
- X4: o que o XML e o PDF da mesma nota disserem de diferente fica em `diferencas_pdf`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pdfplumber

from modulos.conferencia_nf import configuracao as cfg
from modulos.conferencia_nf.leitor_danfe import cnpj_da_chave, ler_danfe, numero_da_chave
from modulos.conferencia_nf.leitor_danfse import ler_danfse, palavras_sem_marca_dagua
from modulos.conferencia_nf.leitor_paulistana import e_paulistana, ler_paulistana_pdf
from modulos.conferencia_nf.leitor_xml import ler_xml
from modulos.conferencia_nf.modelos import ErroLeitura, FalhaLeitura, NotaPdf, NotaSemPdf

Progresso = Callable[[str, float | None], None]


def _ordem_do_caminho(caminho: Path, pasta: Path) -> list[str]:
    return [parte.casefold() for parte in caminho.relative_to(pasta).parts]


def listar_notas(pasta: Path, extensoes: tuple[str, ...] = (".pdf", ".xml")) -> list[Path]:
    """L1 e X1: PDFs e XMLs da pasta e das subpastas, em ordem de caminho (pasta por pasta, sem
    diferença de maiúsculas): "danfe-lote" vem antes de "danfe-lote (2)"."""
    pasta = Path(pasta)
    return sorted((p for p in pasta.rglob("*") if p.is_file() and p.suffix.lower() in extensoes),
                  key=lambda p: _ordem_do_caminho(p, pasta))


def listar_pdfs(pasta: Path) -> list[Path]:
    return listar_notas(pasta, (".pdf",))


def listar_xmls(pasta: Path) -> list[Path]:
    return listar_notas(pasta, (".xml",))


def ler_pdf(caminho: Path, arquivo: str) -> NotaPdf:
    """Lê um PDF (DANFE, DANFSe ou Nota Paulistana). Levanta ErroLeitura com a explicação para o usuário."""
    try:
        with pdfplumber.open(caminho) as pdf:
            if not pdf.pages:
                raise ErroLeitura("O PDF não tem páginas.")
            pagina = pdf.pages[0]
            texto = pagina.extract_text() or ""
            # a DANFSe é lida pela posição das palavras; a DANFE, pelo texto
            palavras = palavras_sem_marca_dagua(pagina) if cfg.PDF_TEXTO_DANFSE in texto else None
    except ErroLeitura:
        raise
    except Exception:
        raise ErroLeitura("Não foi possível abrir o PDF (arquivo estragado ou protegido).") from None
    if not texto.strip():
        raise ErroLeitura("O PDF não tem texto (escaneado?).")
    if palavras is not None:
        return ler_danfse(palavras, arquivo)
    if e_paulistana(texto):                       # L2a
        return ler_paulistana_pdf(texto, arquivo)
    if all(t in texto for t in cfg.PDF_TEXTOS_DANFE):
        return ler_danfe(texto, arquivo)
    raise ErroLeitura("Modelo não reconhecido: o PDF não é uma DANFE (nota de compra), uma "
                      "DANFSe nem uma Nota Paulistana (nota de serviço).")


def _diferencas(xml: NotaPdf, pdf: NotaPdf) -> list[str]:
    """X4: o que o XML e o PDF da mesma nota dizem de diferente (campo não lido no PDF não conta)."""
    campos = [("número", xml.numero, pdf.numero), ("emissão", xml.emissao, pdf.emissao),
              ("valor", xml.valor, pdf.valor),
              ("CNPJ do emitente", xml.emitente_documento, pdf.emitente_documento)]
    if pdf.destinatario_documento:
        campos.append(("CNPJ do destinatário", xml.destinatario_documento,
                       pdf.destinatario_documento))
    return [f"{nome}: XML {a} x PDF {b}" for nome, a, b in campos if a != b]


def _juntar_xml_e_pdf(notas: list[NotaPdf]) -> list[NotaPdf]:
    """X2: o PDF da mesma nota que um XML some da lista; o XML fica com a situação do PDF."""
    pdf_por_chave = {n.chave: n for n in notas if not n.xml and not n.repetida_de}
    juntados = set()
    for xml in (n for n in notas if n.xml and not n.repetida_de):
        pdf = pdf_por_chave.get(xml.chave)
        if pdf is None:
            continue
        xml.arquivo_pdf = pdf.arquivo
        xml.situacao = xml.situacao or pdf.situacao
        xml.descricao_contribuicoes = xml.descricao_contribuicoes or pdf.descricao_contribuicoes
        xml.diferencas_pdf = _diferencas(xml, pdf)
        juntados.add(id(pdf))
    return [n for n in notas if id(n) not in juntados]


def ler_pasta(pasta: Path, progresso: Progresso | None = None
              ) -> tuple[list[NotaPdf], list[FalhaLeitura]]:
    """Lê todos os PDFs e XMLs. Devolve (notas lidas, falhas de leitura), na ordem da L1.

    As notas repetidas (L6, X3) continuam na lista, com `repetida_de` = arquivo da primeira. O PDF
    da mesma nota de um XML não aparece: está no `arquivo_pdf` do XML (X2).
    """
    pasta = Path(pasta)
    arquivos = listar_notas(pasta)
    tem_xml = any(c.suffix.lower() == ".xml" for c in arquivos)
    rotulo = "PDFs e XMLs" if tem_xml else "PDFs"
    notas: list[NotaPdf] = []
    falhas: list[FalhaLeitura] = []
    primeira_por_chave: dict[tuple[bool, str], NotaPdf] = {}
    for posicao, caminho in enumerate(arquivos, start=1):
        if progresso:
            progresso(f"Lendo {rotulo}... {posicao} de {len(arquivos)}",
                      (posicao - 1) / len(arquivos))
        arquivo = caminho.relative_to(pasta).as_posix()
        e_xml = caminho.suffix.lower() == ".xml"
        try:
            nota = ler_xml(caminho, arquivo) if e_xml else ler_pdf(caminho, arquivo)
        except ErroLeitura as erro:
            falhas.append(FalhaLeitura(arquivo, str(erro)))
            continue
        except Exception as erro:          # nada derruba o processamento inteiro
            falhas.append(FalhaLeitura(
                arquivo, f"Erro inesperado ao ler o {'XML' if e_xml else 'PDF'}: {erro}"))
            continue
        primeira = primeira_por_chave.setdefault((nota.xml, nota.chave), nota)
        if primeira is not nota:
            nota.repetida_de = primeira.arquivo
        notas.append(nota)
    if progresso:
        progresso(f"{rotulo} lidos: {len(arquivos)}", 1.0)
    return _juntar_xml_e_pdf(notas), falhas


def ler_sem_pdf(pasta: Path) -> list[NotaSemPdf]:
    """Notas dos _sem_pdf.txt da pasta e das subpastas (chaves de 44 dígitos, uma por linha).

    Linhas que não são uma chave (em branco, título) são ignoradas.
    """
    pasta = Path(pasta)
    achadas = []
    for caminho in sorted(pasta.rglob(cfg.ARQUIVO_SEM_PDF),
                          key=lambda p: _ordem_do_caminho(p, pasta)):
        arquivo = caminho.relative_to(pasta).as_posix()
        for linha in caminho.read_text(encoding="utf-8", errors="replace").splitlines():
            chave = linha.strip()
            if len(chave) == cfg.TAMANHO_CHAVE and chave.isdigit():
                achadas.append(NotaSemPdf(chave, cnpj_da_chave(chave), numero_da_chave(chave),
                                          arquivo))
    return achadas
