"""
Leitura do relatório de notas tomadas da Prefeitura de Cidade Alfa (CSV).

- O site entrega um CSV de texto (Windows-1252), separado por ";", com o cabeçalho
  nfs;situacaonf;cnpjcpf;nome;dtemissao;vlrservicos;... Valores "1.127,50"; datas "10/09/2026".
- O arquivo NÃO traz competência, inscrição nem o CNPJ da unidade: a competência é o mês
  que mais aparece nas datas de emissão.
- Traz o CNPJ do prestador: a comparação é a normal (CNPJ + número).
- Notas repetidas no relatório (mesmo CNPJ e número) ficam como "Notas escrituradas
  n vezes na prefeitura" — decisão do usuário (podem ser escrituração em dobro). As linhas
  repetidas costumam diferir só nas deduções/desconto ("0,00" numa e vazio na outra).
- Situação "Cancelada" marca a linha como cancelada (mesma regra de Cidade Epsilon).
- Colunas localizadas pelo NOME do cabeçalho.
- Nunca levanta exceção: problema no arquivo vira `erro`, problema numa linha vira aviso.
  Toda linha do arquivo é mantida (mesmo com problema), para nada sumir do relatório.
"""

from __future__ import annotations

import csv
import io
import re
from collections import Counter
from pathlib import Path

from modulos.conferencia_iss.leitor_prefeitura import (
    LeituraPrefeitura,
    _aviso,
    _chave_coluna,
    _erro_pdf,
    _limpar,
)
from modulos.conferencia_iss.leitor_prefeitura_sj import NOMES_MESES
from modulos.conferencia_iss.modelos import LinhaPrefeitura
from modulos.conferencia_iss.normalizar import normalizar_documento, normalizar_numero, valor_prefeitura

NOME_RELATORIO = "relatório de notas tomadas"

# Nomes das colunas na prefeitura de Cidade Alfa
COL_NUMERO = "nfs"
COL_SITUACAO = "situacaonf"
COL_DOCUMENTO = "cnpjcpf"
COL_PRESTADOR = "nome"
COL_EMISSAO = "dtemissao"
COL_VALOR = "vlrservicos"
COL_ATIVIDADE = "descratividade"
COL_CFPS = "cfps"
COL_DEDUCOES = "vlrdeducoes"
COL_DESCONTO = "descontoincondicionado"
COL_BASE = "basecalculo"
COL_ALIQUOTA = "aliquota"
COL_RETIDO = "impretido"
COL_IMPOSTO = "vlrimposto"
COL_SIMPLES = "enquadradosn"

COLUNAS_OBRIGATORIAS = (COL_NUMERO, COL_DOCUMENTO, COL_VALOR)
COLUNAS_OPCIONAIS = (
    COL_SITUACAO, COL_PRESTADOR, COL_EMISSAO, COL_ATIVIDADE, COL_CFPS, COL_DEDUCOES,
    COL_DESCONTO, COL_BASE, COL_ALIQUOTA, COL_RETIDO, COL_IMPOSTO, COL_SIMPLES,
)

SITUACAO_NORMAL = "normal"
ERRO_E_DE_CIDADE_ALFA = ("Este é o relatório de notas tomadas de Cidade Alfa. "
                    "Para conferi-lo, use a aba Cidade Alfa da Conferência ISS.")

_REGEX_DATA = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})")


# ---------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------
def ler_relatorio_cidade_alfa(caminho: Path | str,
                         identificar_outras: bool = True) -> LeituraPrefeitura:
    """
    Lê o relatório de Cidade Alfa. Nunca levanta exceção: problemas vão para erro/avisos.

    identificar_outras: se o arquivo não for de Cidade Alfa, tenta reconhecer o relatório de
    outra cidade (ou um CSV do Tasy) para dizer o que fazer. Os leitores das outras
    cidades chamam com False (senão um leitor chamaria o outro sem fim).
    """
    caminho = Path(caminho)
    leitura = LeituraPrefeitura(caminho=caminho)

    try:
        conteudo = caminho.read_bytes()
    except OSError as erro:
        leitura.erro = f"Não foi possível abrir o arquivo: {erro.strerror or erro}"
        return leitura

    if not conteudo.strip():
        leitura.erro = "Arquivo vazio."
        return leitura

    if conteudo.lstrip().startswith(b"%PDF"):
        leitura.erro = _erro_pdf(caminho, NOME_RELATORIO) if identificar_outras else "PDF"
        return leitura

    texto = _decodificar(conteudo)
    if texto is None or texto.lstrip().startswith("<"):
        # planilha do Excel, HTML (Cidade Beta) ou outro formato
        leitura.erro = _erro_de_outra_cidade(caminho, identificar_outras) or (
            f"O arquivo não é o {NOME_RELATORIO} (CSV) baixado do site da Prefeitura de Cidade Alfa."
        )
        return leitura

    try:
        _ler_tabela(texto, leitura)
    except csv.Error as erro:
        leitura.erro = f"O arquivo não é um CSV válido: {erro}"
    if leitura.erro:
        leitura.linhas.clear()
        leitura.avisos.clear()
        leitura.erro = _erro_de_outra_cidade(caminho, identificar_outras) or leitura.erro
    return leitura


def _decodificar(conteudo: bytes) -> str | None:
    """Texto do CSV (UTF-8 ou Windows-1252); None se for binário ou UTF-16 (CSV do Tasy)."""
    if b"\x00" in conteudo[:4096]:
        return None
    try:
        return conteudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        return conteudo.decode("cp1252", errors="replace")


def _erro_de_outra_cidade(caminho: Path, identificar_outras: bool) -> str | None:
    """Se o arquivo for de outra cidade ou um CSV do Tasy, diz o que fazer."""
    if not identificar_outras:
        return None
    from modulos.conferencia_iss.leitor_prefeitura import ler_relatorio_prefeitura
    from modulos.conferencia_iss.leitor_prefeitura_cp import ERRO_E_DE_CIDADE_GAMA, eh_relatorio_de_cidade_gama
    from modulos.conferencia_iss.leitor_prefeitura_sj import ler_relatorio_cidade_epsilon
    from modulos.conferencia_iss.leitor_tasy import ler_csv_tasy

    if _leu_bem(ler_relatorio_prefeitura(caminho)):
        return ("Este é o Relatório de Serviços Contratados de Cidade Beta. "
                "Para conferi-lo, use a aba Cidade Beta da Conferência ISS.")
    if _leu_bem(ler_relatorio_cidade_epsilon(caminho)):
        return ("Este é o Relatório de Serviços Tomados de Cidade Epsilon. "
                "Para conferi-lo, use a aba Cidade Epsilon da Conferência ISS.")
    if eh_relatorio_de_cidade_gama(caminho):
        return ERRO_E_DE_CIDADE_GAMA
    tasy = ler_csv_tasy(caminho)
    if tasy.erro is None and tasy.notas:
        return ("Este é um CSV do Tasy. Escolha-o no cartão Relatórios do Tasy; aqui vai o "
                f"{NOME_RELATORIO} baixado do site da Prefeitura de Cidade Alfa.")
    return None


def _leu_bem(leitura: LeituraPrefeitura) -> bool:
    return leitura.erro is None and bool(leitura.linhas)


def eh_relatorio_de_cidade_alfa(caminho: Path) -> bool:
    """O arquivo escolhido (no item de outra cidade) é, na verdade, o relatório de Cidade Alfa?"""
    return _leu_bem(ler_relatorio_cidade_alfa(caminho, identificar_outras=False))


# ---------------------------------------------------------------------
# Tabela
# ---------------------------------------------------------------------
def _ler_tabela(texto: str, leitura: LeituraPrefeitura) -> None:
    leitor = csv.reader(io.StringIO(texto, newline=""), delimiter=";", quotechar='"')
    cabecalho = next(leitor, None) or []

    indices: dict[str, int] = {}
    for posicao, nome in enumerate(cabecalho):
        if nome.strip():
            indices.setdefault(_chave_coluna(nome), posicao)
    faltando = [c for c in COLUNAS_OBRIGATORIAS if _chave_coluna(c) not in indices]
    if faltando:
        leitura.erro = (
            "Coluna(s) obrigatória(s) não encontrada(s): " + ", ".join(faltando)
            + f". Confira se é o {NOME_RELATORIO} baixado do site da Prefeitura de Cidade Alfa."
        )
        return
    posicoes = {
        coluna: indices.get(_chave_coluna(coluna))
        for coluna in COLUNAS_OBRIGATORIAS + COLUNAS_OPCIONAIS
    }
    if posicoes[COL_SITUACAO] is None:
        leitura.avisos.append(_aviso(
            leitura, f"Coluna {COL_SITUACAO} não encontrada: nenhuma nota foi tratada como "
                     "cancelada na prefeitura.",
        ))

    numero_linha = 0
    for registro in leitor:
        if not any(campo.strip() for campo in registro):
            continue                       # linha em branco não é nota
        numero_linha += 1
        leitura.linhas.append(_montar_linha(registro, posicoes, numero_linha, leitura))

    _ler_competencia(leitura)


def _ler_competencia(leitura: LeituraPrefeitura) -> None:
    """O arquivo não traz a competência: vale o mês que mais aparece nas datas de emissão."""
    contagem = Counter()
    for linha in leitura.linhas:
        encontrado = _REGEX_DATA.match(linha.data_emissao)
        if encontrado and 1 <= int(encontrado.group(2)) <= 12:
            contagem[(encontrado.group(3), int(encontrado.group(2)))] += 1
    if not contagem:
        leitura.avisos.append(_aviso(
            leitura, "Competência não encontrada: o relatório da prefeitura não tem datas de "
                     "emissão válidas.",
        ))
        return
    (ano, mes), _ = contagem.most_common(1)[0]
    leitura.competencia = f"{ano}-{mes:02d}"
    leitura.competencia_texto = f"{NOMES_MESES[mes]}/{ano}"
    if len(contagem) > 1:
        outras = ", ".join(f"{m:02d}/{a}" for (a, m) in sorted(contagem) if (a, m) != (ano, mes))
        leitura.avisos.append(_aviso(
            leitura, f"O relatório tem notas emitidas em mais de um mês ({outras}). "
                     f"Foi usada a competência {mes:02d}/{ano}, a que mais aparece.",
        ))


def _montar_linha(registro: list[str], posicoes, numero_linha: int,
                  leitura: LeituraPrefeitura) -> LinhaPrefeitura:
    def campo(coluna: str) -> str:
        posicao = posicoes[coluna]
        if posicao is None or posicao >= len(registro):
            return ""
        return _limpar(registro[posicao])

    documento_original = campo(COL_DOCUMENTO)
    numero_doc = campo(COL_NUMERO)
    prestador = campo(COL_PRESTADOR)
    identificacao = (
        f"Linha {numero_linha} do arquivo, nota {numero_doc or '(sem número)'} "
        f"({prestador or documento_original or 'sem prestador'})"
    )

    def valor(coluna: str):
        try:
            return valor_prefeitura(campo(coluna))
        except ValueError:
            leitura.avisos.append(_aviso(
                leitura, f"{identificacao}: {coluna} inválido ({campo(coluna)!r}); "
                         "tratado como vazio.",
            ))
            return None

    valor_doc = valor(COL_VALOR)
    if valor_doc is None and not campo(COL_VALOR):
        leitura.avisos.append(_aviso(leitura, f"{identificacao}: {COL_VALOR} vazio."))

    documento = normalizar_documento(documento_original)
    if not documento:
        leitura.avisos.append(_aviso(leitura, f"{identificacao}: sem CPF/CNPJ do prestador."))
    numero = normalizar_numero(numero_doc)
    if not numero:
        leitura.avisos.append(_aviso(leitura, f"{identificacao}: sem número da nota."))

    situacao = campo(COL_SITUACAO)
    cancelada = situacao.casefold().startswith("cancel")
    if situacao and not cancelada and situacao.casefold() != SITUACAO_NORMAL:
        leitura.avisos.append(_aviso(
            leitura, f"{identificacao}: situação na prefeitura é {situacao!r} "
                     "(nem Normal nem Cancelada); foi conferida normalmente.",
        ))

    return LinhaPrefeitura(
        linha=numero_linha,
        documento=documento,
        documento_original=documento_original,
        prestador=prestador,
        numero_doc=numero_doc,
        numero=numero,
        valor_doc=valor_doc,
        aliquota=campo(COL_ALIQUOTA),
        imp_ret=campo(COL_RETIDO),
        sn_mei=campo(COL_SIMPLES),
        valor_tributavel=valor(COL_BASE),
        valor_imposto=valor(COL_IMPOSTO),
        cancelada=cancelada,
        situacao_nf=situacao,
        atividade=campo(COL_ATIVIDADE),
        data_emissao=campo(COL_EMISSAO)[:10],
        valor_deducoes=valor(COL_DEDUCOES),
        valor_desconto=valor(COL_DESCONTO),
        cfps=campo(COL_CFPS),
    )
