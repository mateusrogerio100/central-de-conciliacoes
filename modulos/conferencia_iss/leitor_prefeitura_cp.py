"""
Leitura do "Relatório de Nota Fiscal" da Prefeitura de Cidade Gama.

- O site entrega uma planilha do Excel (.xlsx), lida com openpyxl. Todas as células
  chegam como texto: valores "1.500,00", datas "29/09/2026 09:16:35", competência "09/2026".
- Antes da tabela vêm o título e "Usuário: 98.765.432/0008-64 - FUNDACAO ...": o CNPJ da
  unidade que tirou o relatório (usado para avisar se é de outra unidade). Não há inscrição.
- O relatório NÃO traz o CNPJ do prestador, só o nome ("Nome Empresarial"): o comparador
  de Cidade Gama casa por número, valor e nome parecido (comparador.comparar_por_nome).
- "Nº Documento Escriturado" ("2543 / 1") é o número do documento lançado à mão
  (prestador de outra cidade); quando vem preenchido, também serve para achar a nota.
- Situação "Cancelada" marca a linha como cancelada (mesma regra de Cidade Epsilon).
- Base Cálculo / Valor ISS às vezes vêm como "*****": ficam vazios e a planilha mostra "*****".
- Colunas localizadas pelo NOME do cabeçalho.
- Nunca levanta exceção: problema no arquivo vira `erro`, problema numa linha vira aviso.
  Toda linha da tabela é mantida (mesmo com problema), para nada sumir do relatório.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from modulos.conferencia_iss.leitor_prefeitura import (
    LeituraPrefeitura,
    _aviso,
    _chave_coluna,
    _erro_pdf,
    ler_relatorio_prefeitura,
)
from modulos.conferencia_iss.leitor_prefeitura_sj import (
    NOMES_MESES,
    _ler_xls,
    _ler_xlsx,
    _texto,
    _valor,
    ler_relatorio_cidade_epsilon,
)
from modulos.conferencia_iss.modelos import LinhaPrefeitura
from modulos.conferencia_iss.normalizar import normalizar_documento, normalizar_numero

NOME_RELATORIO = "Relatório de Nota Fiscal"

# Nomes das colunas na prefeitura de Cidade Gama
COL_SITUACAO = "Situação"
COL_NUMERO = "Nr. NF"
COL_RPS = "Nr. RPS"
COL_ESCRITURADO = "Nº Documento Escriturado"
COL_EMISSAO = "Emissão"
COL_COMPETENCIA = "Compet."
COL_PAGAMENTO = "Pagamento"
COL_PRESTADOR = "Nome Empresarial"
COL_CNAE = "CNAE"
COL_VALOR = "Valor Serviço"
COL_BASE = "Base Cálculo"
COL_ISS = "Valor ISS"

COLUNAS_OBRIGATORIAS = (COL_NUMERO, COL_PRESTADOR, COL_VALOR)
COLUNAS_OPCIONAIS = (
    COL_SITUACAO, COL_RPS, COL_ESCRITURADO, COL_EMISSAO, COL_COMPETENCIA, COL_PAGAMENTO,
    COL_CNAE, COL_BASE, COL_ISS,
)

SITUACAO_ATIVA = "ativa"
VALOR_OCULTO = "*****"

_REGEX_CNPJ = re.compile(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}")
_REGEX_COMPETENCIA = re.compile(r"^(\d{1,2})\s*/\s*(\d{4})$")


# ---------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------
def ler_relatorio_cidade_gama(caminho: Path | str,
                           identificar_outras: bool = True) -> LeituraPrefeitura:
    """
    Lê o relatório de Cidade Gama. Nunca levanta exceção: problemas vão para erro/avisos.

    identificar_outras: se o arquivo não for de Cidade Gama, tenta reconhecer o relatório de
    outra cidade para dizer qual item usar. Os leitores das outras cidades chamam com False
    (senão um leitor chamaria o outro sem fim).
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

    try:
        if conteudo.startswith(b"PK\x03\x04"):
            planilhas = _ler_xlsx(conteudo)
        elif conteudo.startswith(b"\xd0\xcf\x11\xe0"):
            planilhas = _ler_xls(conteudo)
        else:
            leitura.erro = _erro_de_outra_cidade(caminho, identificar_outras) or (
                f"O arquivo não é uma planilha do Excel. Confira se é o {NOME_RELATORIO} "
                "baixado do site da Prefeitura de Cidade Gama."
            )
            return leitura
    except Exception as erro:  # planilha corrompida ou protegida
        leitura.erro = f"Não foi possível ler a planilha: {erro}"
        return leitura

    _ler_tabela(planilhas, leitura)
    if leitura.erro:
        leitura.linhas.clear()
        leitura.erro = _erro_de_outra_cidade(caminho, identificar_outras) or leitura.erro
    return leitura


def _erro_de_outra_cidade(caminho: Path, identificar_outras: bool) -> str | None:
    """Se o arquivo for o relatório de Cidade Beta, Cidade Epsilon ou Cidade Alfa, diz qual item usar."""
    if not identificar_outras:
        return None
    from modulos.conferencia_iss.leitor_prefeitura_fr import ERRO_E_DE_CIDADE_ALFA, eh_relatorio_de_cidade_alfa
    if eh_relatorio_de_cidade_alfa(caminho):
        return ERRO_E_DE_CIDADE_ALFA
    leitura = ler_relatorio_prefeitura(caminho)
    if leitura.erro is None and leitura.linhas:
        return ("Este é o Relatório de Serviços Contratados de Cidade Beta. "
                "Para conferi-lo, use a aba Cidade Beta da Conferência ISS.")
    leitura = ler_relatorio_cidade_epsilon(caminho)
    if leitura.erro is None and leitura.linhas:
        return ("Este é o Relatório de Serviços Tomados de Cidade Epsilon. "
                "Para conferi-lo, use a aba Cidade Epsilon da Conferência ISS.")
    return None


def eh_relatorio_de_cidade_gama(caminho: Path) -> bool:
    """O arquivo escolhido (no item de outra cidade) é, na verdade, o relatório de Cidade Gama?"""
    leitura = ler_relatorio_cidade_gama(caminho, identificar_outras=False)
    return leitura.erro is None and bool(leitura.linhas)


ERRO_E_DE_CIDADE_GAMA = ("Este é o Relatório de Nota Fiscal de Cidade Gama. "
                      "Para conferi-lo, use a aba Cidade Gama da Conferência ISS.")


# ---------------------------------------------------------------------
# Tabela
# ---------------------------------------------------------------------
def _ler_tabela(planilhas: list[list[list]], leitura: LeituraPrefeitura) -> None:
    obrigatorias = {_chave_coluna(c) for c in COLUNAS_OBRIGATORIAS}

    # A tabela certa começa na primeira linha que tem as colunas obrigatórias.
    encontrado = None
    for linhas in planilhas:
        for posicao, linha in enumerate(linhas):
            if obrigatorias <= {_chave_coluna(_texto(c)) for c in linha}:
                encontrado = (linhas, posicao)
                break
        if encontrado:
            break

    if encontrado is None:
        leitura.erro = (
            "Coluna(s) obrigatória(s) não encontrada(s): " + ", ".join(COLUNAS_OBRIGATORIAS)
            + f". Confira se é o {NOME_RELATORIO} da Prefeitura de Cidade Gama."
        )
        return

    linhas, posicao_cabecalho = encontrado
    _ler_tomador(linhas[:posicao_cabecalho], leitura)

    cabecalho = [_texto(c) for c in linhas[posicao_cabecalho]]
    indices: dict[str, int] = {}
    for posicao, nome in enumerate(cabecalho):
        if nome:
            indices.setdefault(_chave_coluna(nome), posicao)
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
    for celulas in linhas[posicao_cabecalho + 1:]:
        if not any(_texto(c) for c in celulas):
            continue                       # linha em branco não é nota
        numero_linha += 1
        leitura.linhas.append(_montar_linha(celulas, posicoes, numero_linha, leitura))

    _ler_competencia(leitura)


def _ler_tomador(linhas_antes: list[list], leitura: LeituraPrefeitura) -> None:
    """CNPJ da unidade que tirou o relatório ("Usuário: 98.765.432/0008-64 - FUNDACAO ...")."""
    for linha in linhas_antes:
        for celula in linha:
            encontrado = _REGEX_CNPJ.search(_texto(celula))
            if encontrado:
                leitura.documento_tomador = normalizar_documento(encontrado.group(0))
                return
    leitura.avisos.append(_aviso(
        leitura, "CNPJ da unidade (Usuário) não encontrado no cabeçalho do relatório da "
                 "prefeitura: não foi possível conferir se o relatório é da mesma unidade "
                 "dos CSVs do Tasy.",
    ))


def _ler_competencia(leitura: LeituraPrefeitura) -> None:
    """A competência vem em cada linha ("09/2026"); vale a que mais aparece."""
    contagem = Counter()
    for linha in leitura.linhas:
        encontrado = _REGEX_COMPETENCIA.match(linha.competencia)
        if encontrado and 1 <= int(encontrado.group(1)) <= 12:
            contagem[(encontrado.group(2), int(encontrado.group(1)))] += 1
    if not contagem:
        leitura.avisos.append(_aviso(
            leitura, "Competência não encontrada no relatório da prefeitura."
        ))
        return
    (ano, mes), _ = contagem.most_common(1)[0]
    leitura.competencia = f"{ano}-{mes:02d}"
    leitura.competencia_texto = f"{NOMES_MESES[mes]}/{ano}"
    if len(contagem) > 1:
        outras = ", ".join(f"{m:02d}/{a}" for (a, m) in sorted(contagem) if (a, m) != (ano, mes))
        leitura.avisos.append(_aviso(
            leitura, f"O relatório tem linhas de mais de uma competência ({outras}). "
                     f"Foi usada {mes:02d}/{ano}, a que mais aparece.",
        ))


def _montar_linha(celulas, posicoes, numero_linha: int,
                  leitura: LeituraPrefeitura) -> LinhaPrefeitura:
    def celula(coluna: str):
        posicao = posicoes[coluna]
        if posicao is None or posicao >= len(celulas):
            return ""
        return celulas[posicao]

    def campo(coluna: str) -> str:
        return _texto(celula(coluna))

    numero_doc = campo(COL_NUMERO)
    prestador = campo(COL_PRESTADOR)
    identificacao = (
        f"Linha {numero_linha} da tabela, nota {numero_doc or '(sem número)'} "
        f"({prestador or 'sem prestador'})"
    )
    ocultos = False

    def valor(coluna: str):
        nonlocal ocultos
        if campo(coluna) == VALOR_OCULTO:
            ocultos = True                 # a prefeitura não mostrou o valor
            return None
        try:
            return _valor(celula(coluna))
        except ValueError:
            leitura.avisos.append(_aviso(
                leitura, f"{identificacao}: {coluna} inválido ({campo(coluna)!r}); "
                         "tratado como vazio.",
            ))
            return None

    valor_doc = valor(COL_VALOR)
    if valor_doc is None and not campo(COL_VALOR):
        leitura.avisos.append(_aviso(leitura, f"{identificacao}: {COL_VALOR} vazio."))
    elif valor_doc is None and campo(COL_VALOR) == VALOR_OCULTO:
        leitura.avisos.append(_aviso(
            leitura, f"{identificacao}: {COL_VALOR} veio como {VALOR_OCULTO}.",
        ))

    if not prestador:
        leitura.avisos.append(_aviso(leitura, f"{identificacao}: sem nome do prestador."))
    numero = normalizar_numero(numero_doc)
    if not numero:
        leitura.avisos.append(_aviso(leitura, f"{identificacao}: sem número da nota."))

    # "2543 / 1" → número "2543" (o que vem depois da barra é a série)
    escriturado = campo(COL_ESCRITURADO)
    alternativo = normalizar_numero(escriturado.split("/")[0])

    situacao = campo(COL_SITUACAO)
    cancelada = situacao.casefold().startswith("cancel")
    if situacao and not cancelada and situacao.casefold() != SITUACAO_ATIVA:
        leitura.avisos.append(_aviso(
            leitura, f"{identificacao}: situação na prefeitura é {situacao!r} "
                     "(nem Ativa nem Cancelada); foi conferida normalmente.",
        ))

    linha = LinhaPrefeitura(
        linha=numero_linha,
        documento="",                      # o relatório de Cidade Gama não traz o CNPJ
        documento_original="",
        prestador=prestador,
        numero_doc=numero_doc,
        numero=numero,
        valor_doc=valor_doc,
        valor_tributavel=valor(COL_BASE),
        valor_imposto=valor(COL_ISS),
        cancelada=cancelada,
        situacao_nf=situacao,
        competencia=campo(COL_COMPETENCIA),
        data_emissao=campo(COL_EMISSAO)[:10],   # "29/09/2026 09:16:35" → só a data
        numero_rps=campo(COL_RPS),
        numero_escriturado=escriturado,
        numero_alternativo=alternativo if alternativo != numero else "",
        cnae=campo(COL_CNAE),
        data_pagamento=campo(COL_PAGAMENTO)[:10],
    )
    linha.valores_ocultos = ocultos
    return linha
