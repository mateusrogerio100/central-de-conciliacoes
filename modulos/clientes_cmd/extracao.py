"""Extracao e padronizacao dos relatorios de origem (contabil e financeiro).

Cada funcao le um relatorio Excel exportado por outro sistema (sem cabecalho fixo
em posicao conhecida, com linhas de titulo/rodape intercaladas) e devolve um
DataFrame padronizado com as colunas: codigo, nome, valor.

Aceita o relatorio salvo no Excel (.xlsx) ou o ".xls" como sai do Tasy (pedido do
Usuário, 12/11/2026), que na verdade e TEXTO separado por tabulacao (cp1252). O
formato e reconhecido pelo CONTEUDO; cada celula do texto passa pela mesma
conversao que o Excel faz ao abrir o arquivo, e por isso o resto da leitura (que
acha as colunas pelo titulo e pelo conteudo) nao muda.
"""

import csv
import io
import re
import unicodedata
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

_CLASSIFICACAO_RE = re.compile(r"^\d+(\.\d+)*$")

_ROTULOS_FINANCEIRO = {
    "vl titulo",
    "vl juros + multa",
    "vl baixa",
    "vl glosa",
    "vl diferenca",
    "vl saldo",
    "vl menor",
    "vl s/ret",
    "vl cancelad",
    "vl desc",
    "% inadimplenc",
    "vl liquido",
}


def _normalizar_texto(valor):
    """Remove acentos, colapsa espacos e converte para minusculas."""
    if valor is None:
        return ""
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.strip().lower().split())


def _eh_numero(valor):
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


# Texto do Tasy: tabulacao, cp1252, aspas como no CSV.
_SEPARADOR_TASY = "\t"
_CODIFICACAO_TASY = "cp1252"
_ASSINATURA_ZIP = b"PK"                              # .xlsx (mesmo com extensao .xls)
_ASSINATURA_XLS_BINARIO = bytes.fromhex("D0CF11E0")  # Excel 97-2003 de verdade
_PADRAO_INTEIRO = re.compile(r"-?\d+")
_PADRAO_NUMERO_BR = re.compile(r"-?\d{1,3}(?:\.\d{3})*,\d+|-?\d+,\d+")


def celula_do_texto(celula):
    """Celula do texto do Tasy convertida como o Excel faz ao abrir o arquivo:
    "" -> vazia; "14296" -> 14296; "2.419.888,77" -> 2419888.77; o resto fica texto."""
    limpo = celula.strip()
    if limpo == "":
        return None
    if _PADRAO_INTEIRO.fullmatch(limpo):
        return int(limpo)
    if _PADRAO_NUMERO_BR.fullmatch(limpo):
        return float(limpo.replace(".", "").replace(",", "."))
    return celula


def _ler_linhas(caminho_arquivo):
    conteudo = Path(caminho_arquivo).read_bytes()
    if conteudo.startswith(_ASSINATURA_XLS_BINARIO):
        raise ValueError(
            f"{Path(caminho_arquivo).name}: e um Excel antigo (.xls 97-2003), nao o arquivo como sai do Tasy. "
            "Use o arquivo exportado pelo Tasy ou abra no Excel e salve como .xlsx."
        )
    if conteudo.startswith(_ASSINATURA_ZIP):
        planilha = load_workbook(io.BytesIO(conteudo), data_only=True)
        aba = planilha.active
        return [list(linha) for linha in aba.iter_rows(values_only=True)]
    texto = conteudo.decode(_CODIFICACAO_TASY, errors="replace")
    leitor = csv.reader(io.StringIO(texto, newline=""), delimiter=_SEPARADOR_TASY, quotechar='"')
    return [[celula_do_texto(c) for c in linha] for linha in leitor]


def _encontrar_coluna_por_predicado(linhas, indices_amostra, coluna_referencia, predicado, janela=3):
    """Procura, ao redor de `coluna_referencia`, a coluna cujo conteudo mais bate com
    `predicado` nas linhas de `indices_amostra`. Testa primeiro o deslocamento 0
    (sem deslocamento), depois +1, -1, +2, -2... e fica com o melhor resultado.
    """
    if not indices_amostra:
        return coluna_referencia

    melhor_coluna = coluna_referencia
    melhor_pontuacao = -1.0
    deslocamentos = [0]
    for d in range(1, janela + 1):
        deslocamentos.extend([d, -d])

    for deslocamento in deslocamentos:
        coluna = coluna_referencia + deslocamento
        if coluna < 0:
            continue
        acertos = sum(
            1
            for i in indices_amostra
            if coluna < len(linhas[i]) and predicado(linhas[i][coluna])
        )
        pontuacao = acertos / len(indices_amostra)
        if pontuacao >= 0.9:
            return coluna
        if pontuacao > melhor_pontuacao:
            melhor_pontuacao = pontuacao
            melhor_coluna = coluna

    return melhor_coluna


def extrair_balancete(caminho_arquivo):
    """Le o balancete contabil e devolve um DataFrame com codigo, nome e valor.

    So sao mantidas as linhas de nivel mais profundo da hierarquia de
    Classificacao (as contas de cliente individuais), descartando totais de
    categoria e linhas de cabecalho/rodape de pagina.
    """
    linhas = _ler_linhas(caminho_arquivo)

    linha_cabecalho = next(
        (
            i
            for i, linha in enumerate(linhas)
            if "classificacao" in {_normalizar_texto(v) for v in linha}
            and "saldo atual" in {_normalizar_texto(v) for v in linha}
        ),
        None,
    )
    if linha_cabecalho is None:
        raise ValueError(
            "Cabecalho do balancete nao encontrado (colunas 'Classificacao' e 'Saldo Atual')."
        )

    cabecalho = linhas[linha_cabecalho]

    def _coluna_do_rotulo(rotulo):
        return next(
            (j for j, v in enumerate(cabecalho) if _normalizar_texto(v) == rotulo), None
        )

    col_classificacao_hdr = _coluna_do_rotulo("classificacao")
    col_codigo_hdr = _coluna_do_rotulo("codigo")
    col_descricao_hdr = _coluna_do_rotulo("descricao")
    col_saldo_hdr = _coluna_do_rotulo("saldo atual")

    def _eh_classificacao(valor):
        return isinstance(valor, str) and bool(_CLASSIFICACAO_RE.match(valor.strip()))

    linhas_apos_cabecalho = list(range(linha_cabecalho + 1, len(linhas)))

    col_classificacao = _encontrar_coluna_por_predicado(
        linhas, linhas_apos_cabecalho, col_classificacao_hdr, _eh_classificacao
    )

    indices_dados = [
        i
        for i in linhas_apos_cabecalho
        if col_classificacao < len(linhas[i]) and _eh_classificacao(linhas[i][col_classificacao])
    ]
    if not indices_dados:
        raise ValueError("Nenhuma linha com Classificacao valida foi encontrada no balancete.")

    def _eh_descricao(valor):
        return isinstance(valor, str) and valor.strip() != "" and not _eh_classificacao(valor)

    col_codigo = _encontrar_coluna_por_predicado(linhas, indices_dados, col_codigo_hdr, _eh_numero)
    col_descricao = _encontrar_coluna_por_predicado(
        linhas, indices_dados, col_descricao_hdr, _eh_descricao
    )
    col_saldo = _encontrar_coluna_por_predicado(linhas, indices_dados, col_saldo_hdr, _eh_numero)

    profundidade_maxima = max(
        linhas[i][col_classificacao].strip().count(".") for i in indices_dados
    ) + 1

    registros = []
    for i in indices_dados:
        linha = linhas[i]
        classificacao = linha[col_classificacao].strip()
        if classificacao.count(".") + 1 != profundidade_maxima:
            continue

        codigo = linha[col_codigo]
        if isinstance(codigo, float) and codigo.is_integer():
            codigo = int(codigo)

        registros.append(
            {
                "codigo": codigo,
                "nome": str(linha[col_descricao]).strip(),
                "valor": float(linha[col_saldo]),
            }
        )

    return pd.DataFrame(registros, columns=["codigo", "nome", "valor"])


def _detectar_coluna_valor_financeiro(linhas, indice_cabecalho, proximo_cabecalho):
    """Dado o indice de uma linha de cabecalho do relatorio financeiro, descobre
    a coluna real da 'Vl saldo' na linha de dados correspondente.

    O layout usa celulas mescladas no cabecalho, entao cada rotulo aparece
    deslocado em relacao ao valor da linha de dados. O deslocamento e sempre o
    mesmo para todos os rotulos "Vl ..." de um mesmo bloco, entao ele e
    calculado por consenso entre todos os rotulos encontrados naquela linha de
    cabecalho (evita confundir com colunas vizinhas que tambem sao numericas).
    """
    linha_cabecalho = linhas[indice_cabecalho]
    colunas_rotulos = [
        j
        for j, v in enumerate(linha_cabecalho)
        if _normalizar_texto(v) in _ROTULOS_FINANCEIRO
    ]
    col_saldo_hdr = next(
        j for j in colunas_rotulos if _normalizar_texto(linha_cabecalho[j]) == "vl saldo"
    )

    fim_bloco = proximo_cabecalho if proximo_cabecalho is not None else len(linhas)
    amostra = list(range(indice_cabecalho + 1, fim_bloco))

    melhor_deslocamento = 0
    melhor_pontuacao = -1.0
    for deslocamento in range(-3, 4):
        pontuacao = 0.0
        for col_rotulo in colunas_rotulos:
            coluna = col_rotulo + deslocamento
            if coluna < 0:
                continue
            acertos = sum(
                1
                for i in amostra
                if coluna < len(linhas[i]) and _eh_numero(linhas[i][coluna])
            )
            if amostra:
                pontuacao += acertos / len(amostra)
        if pontuacao > melhor_pontuacao:
            melhor_pontuacao = pontuacao
            melhor_deslocamento = deslocamento

    return col_saldo_hdr + melhor_deslocamento


def extrair_financeiro(caminho_arquivo):
    """Le o relatorio de titulos a receber e devolve um DataFrame com codigo,
    nome e valor (Vl saldo). A coluna codigo vem sempre vazia, pois esse
    relatorio nao traz um codigo de cliente, so o nome.
    """
    linhas = _ler_linhas(caminho_arquivo)

    indices_cabecalho = [
        i
        for i, linha in enumerate(linhas)
        if any(_normalizar_texto(v) == "vl saldo" for v in linha)
    ]
    if not indices_cabecalho:
        raise ValueError("Cabecalho 'Vl saldo' nao encontrado no relatorio financeiro.")

    registros = []
    for idx, indice_cabecalho in enumerate(indices_cabecalho):
        proximo_cabecalho = (
            indices_cabecalho[idx + 1] if idx + 1 < len(indices_cabecalho) else None
        )
        col_valor = _detectar_coluna_valor_financeiro(linhas, indice_cabecalho, proximo_cabecalho)

        fim_bloco = proximo_cabecalho if proximo_cabecalho is not None else len(linhas)
        col_nome = None

        for i in range(indice_cabecalho + 1, fim_bloco):
            linha = linhas[i]
            valor = linha[col_valor] if col_valor < len(linha) else None
            if not _eh_numero(valor):
                continue

            if col_nome is None:
                col_nome = next((j for j, v in enumerate(linha) if v is not None), None)
                if col_nome is None:
                    continue

            nome_bruto = linha[col_nome] if col_nome < len(linha) else None
            if not isinstance(nome_bruto, str) or not nome_bruto.strip():
                continue

            nome = nome_bruto.strip()
            if _normalizar_texto(nome) == "total geral":
                continue

            registros.append({"codigo": None, "nome": nome, "valor": float(valor)})

    return pd.DataFrame(registros, columns=["codigo", "nome", "valor"])
