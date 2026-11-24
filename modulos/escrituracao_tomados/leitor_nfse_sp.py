"""Leitura da NFS-e no modelo da Prefeitura de São Paulo -> NotaTomada (R18 da especificação).

Esse modelo não é a DANFSe nacional: não traz competência, regime do prestador (Simples) nem
se o ISS foi retido, e o código do serviço é o municipal de São Paulo (5 dígitos). Por isso a
nota é lida só para aparecer na aba "Lançar à mão" com os dados que tem (decisão do usuário,
08/10/2026): número, emissão, prestador, tomador, valores e local da prestação.

O texto do PDF sai em linhas ("Rótulo: valor"), lidas por expressões regulares. Campo
obrigatório que não for achado: ErroLeitura, como na DANFSe.
"""

from __future__ import annotations

import re
from pathlib import Path

import pdfplumber

from modulos.escrituracao_tomados import configuracao as cfg
from modulos.escrituracao_tomados.gerador_txt import normalizar_texto, so_digitos
from modulos.escrituracao_tomados.modelos import Competencia, ErroLeitura, NotaTomada

RE_NUMERO = re.compile(r"^\s*(\d{8})\s*$", re.MULTILINE)
RE_EMISSAO = re.compile(r"(\d{2}/\d{2}/\d{4}) \d{2}:\d{2}:\d{2}")
RE_CHAVE = re.compile(r"Identificador Nacional:\s*(\d{50})")
RE_DOCUMENTO = re.compile(r"CPF/CNPJ:\s*([\d./-]+)")
RE_NOME = re.compile(r"Nome/Razão Social:\s*(.+)")
RE_MUNICIPIO = re.compile(r"Município:\s*(.+?)\s+UF:\s*([A-Z]{2})")
RE_VALOR_TOTAL = re.compile(r"VALOR TOTAL DO SERVIÇO = R\$\s*([\d.,]+)")
RE_VALORES_ISS = re.compile(r"Valor Total das Deduções.*\n\s*([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)%\s+([\d.,]+)")
RE_CODIGO_SERVICO = re.compile(r"Código do Serviço\s*\n\s*(\d+)\s*-\s*(.+?)\.?\s*$", re.MULTILINE)
RE_LOCAL_PRESTACAO = re.compile(r"Local de prestação:\s*\d{7}\s*-\s*(.+?)\s*-\s*([A-Z]{2})")


def e_nfse_sp(texto: str) -> bool:
    chave = normalizar_texto(texto)
    return all(t in chave for t in cfg.SP_IDENTIFICACAO)


def _bloco(texto: str, inicio: str, fim: str) -> str:
    """Trecho entre dois títulos ("PRESTADOR DE SERVIÇOS" ... "TOMADOR DE SERVIÇOS")."""
    a = texto.find(inicio)
    b = texto.find(fim, a + 1)
    if a < 0 or b < 0:
        raise ErroLeitura(f"Bloco \"{inicio}\" não encontrado na NFS-e de São Paulo.")
    return texto[a:b]


def _achar(regex: re.Pattern, texto: str, nome: str) -> re.Match:
    achado = regex.search(texto)
    if achado is None:
        raise ErroLeitura(f"Campo \"{nome}\" não encontrado na NFS-e de São Paulo.")
    return achado


def _documento(texto: str, nome: str) -> str:
    digitos = so_digitos(_achar(RE_DOCUMENTO, texto, nome).group(1))
    if len(digitos) not in (11, 14):
        raise ErroLeitura(f"{nome} não tem 11 (CPF) nem 14 (CNPJ) dígitos.")
    return digitos


def ler_textos(caminho: Path) -> list[str]:
    """Texto de cada página. Levanta ErroLeitura se o PDF não abrir."""
    try:
        with pdfplumber.open(caminho) as pdf:
            return [pagina.extract_text() or "" for pagina in pdf.pages]
    except Exception:
        raise ErroLeitura("Não foi possível abrir o PDF (arquivo estragado ou protegido).") from None


def ler_pdf(paginas: list[str], nome_arquivo: str) -> NotaTomada:
    # leitor_danfse importado aqui dentro: ele chama este módulo (sem import circular)
    from modulos.escrituracao_tomados.leitor_danfse import converter_data, converter_valor

    texto = paginas[0]
    resto = "\n".join(paginas[1:])
    prestador = _bloco(texto, "PRESTADOR DE SERVIÇOS", "TOMADOR DE SERVIÇOS")
    tomador = _bloco(texto, "TOMADOR DE SERVIÇOS", "INTERMEDIÁRIO DE SERVIÇOS")

    numero = _achar(RE_NUMERO, texto, "Número da Nota").group(1)
    emissao = converter_data(_achar(RE_EMISSAO, texto, "Data e Hora de Emissão").group(1),
                             "Data de emissão")
    documento_prestador = _documento(prestador, "CNPJ/CPF do prestador")
    chave = RE_CHAVE.search(texto)
    municipio = RE_MUNICIPIO.search(prestador)
    local = RE_LOCAL_PRESTACAO.search(resto)
    deducoes, base, aliquota, iss = _achar(RE_VALORES_ISS, texto, "Valor do ISS").groups()
    servico = _achar(RE_CODIGO_SERVICO, texto, "Código do Serviço")

    return NotaTomada(
        numero=numero.lstrip("0") or "0",
        data_emissao=emissao,
        # o modelo não tem competência: usado o mês da emissão (a nota vai para lançar à mão)
        competencia=Competencia(emissao.year, emissao.month),
        prestador_documento=documento_prestador,
        prestador_nome=" ".join(_achar(RE_NOME, prestador, "Nome do prestador").group(1).split()),
        prestador_cidade=municipio.group(1).strip() if municipio else "",
        prestador_uf=municipio.group(2) if municipio else "",
        tomador_documento=_documento(tomador, "CNPJ/CPF do tomador"),
        tomador_nome=" ".join((RE_NOME.search(tomador).group(1) if RE_NOME.search(tomador)
                               else "").split()),
        situacao="Autorizada",
        codigo_atividade=f"{servico.group(1)} - {servico.group(2).strip()} (código de São Paulo)",
        local_prestacao=local.group(1).strip() if local else "",
        valor_servico=converter_valor(_achar(RE_VALOR_TOTAL, texto, "Valor total do serviço")
                                      .group(1), "Valor total do serviço"),
        deducoes=converter_valor(deducoes, "Valor Total das Deduções"),
        aliquota=converter_valor(aliquota, "Alíquota"),
        valor_iss=converter_valor(iss, "Valor do ISS"),
        base_calculo=converter_valor(base, "Base de Cálculo"),
        iss_retido=None,
        chave_acesso=chave.group(1) if chave else f"SP{documento_prestador}{numero}",
        origem="PDF",
        arquivo=nome_arquivo,
        motivo_leitura=cfg.SP_MOTIVO_LANCAR_A_MAO,
    )
