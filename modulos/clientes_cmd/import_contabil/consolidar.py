"""Consolidacao das planilhas fonte do Import Contabil em um unico Rel_Geral.

Funcionalidade independente da conciliacao de clientes: le todos os .xlsx de
uma pasta (a quantidade e os nomes mudam de mes a mes), empilha as linhas
numa tabela so e corrige os defeitos conhecidos de exportacao (espacos e
aspas duplicadas no Complemento, valores com varias virgulas).

Aceita tambem o ".xls" como sai do Tasy (pedido do usuário, 11/11/2026), que na
verdade e TEXTO separado por tabulacao (cp1252): cada celula passa pela mesma
conversao que o Excel fazia quando o relatorio era salvo como .xlsx, e o
Rel_Geral sai igual.
"""

import csv
import io
import re
from pathlib import Path

import pandas as pd

# Colunas de saida, na ordem. As planilhas fonte trazem antes delas uma
# coluna de contrato (descartada) e seguem sempre esta mesma ordem, mas os
# nomes do cabecalho variam entre arquivos (principalmente o da coluna de
# valor) - por isso as colunas sao identificadas pela posicao, nao pelo nome.
COLUNAS_SAIDA = [
    "Dia lançamento",
    "Conta debito",
    "Conta credito",
    "Vl parcela formatado",
    "Historico",
    "Complemento",
    "Centro custo",
    "Vl parcela formatado.1",
]
_COLUNAS_VALOR = ["Vl parcela formatado", "Vl parcela formatado.1"]

# Minimo de colunas para o arquivo ser reconhecido: contrato + ate o valor.
_MINIMO_COLUNAS = 5

_NOME_ABA = "Consolidado"

# Relatorios aceitos na pasta: o .xlsx salvo no Excel e o .xls como sai do Tasy.
EXTENSOES_RELATORIO = (".xlsx", ".xls")

# Texto do Tasy: tabulacao, cp1252, aspas como no CSV (o Excel le do mesmo jeito).
_SEPARADOR_TASY = "\t"
_CODIFICACAO_TASY = "cp1252"
_ASSINATURA_ZIP = b"PK"                              # .xlsx
_ASSINATURA_XLS_BINARIO = bytes.fromhex("D0CF11E0")  # Excel 97-2003 de verdade
_PADRAO_INTEIRO = re.compile(r"-?\d+")
_PADRAO_NUMERO_BR = re.compile(r"-?\d{1,3}(?:\.\d{3})*,\d+|-?\d+,\d+")


def converter_valor(valor):
    """Converte o valor para float. Em texto, o ULTIMO separador (virgula ou
    ponto) e o decimal e os anteriores sao de milhar e sao descartados - cobre
    exportacoes malformadas como "2,614,91" e "2.614.91" (ambos 2614.91)."""
    if pd.isna(valor):
        return float("nan")
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return float(valor)

    texto = str(valor).strip()
    if not texto:
        return float("nan")
    posicao_decimal = max(texto.rfind(","), texto.rfind("."))
    if posicao_decimal >= 0:
        inteiro = texto[:posicao_decimal].replace(",", "").replace(".", "")
        texto = inteiro + "." + texto[posicao_decimal + 1 :]
    return float(texto)


def _corrigir_complemento(valor):
    """Tira espacos das pontas e reduz aspas duplicadas ("") nas pontas a uma
    aspas so. Espacos, aspas, acentos e virgulas internos ficam como estao."""
    if pd.isna(valor):
        return valor
    texto = str(valor).strip()
    if texto.startswith('""'):
        texto = texto[1:]
    if texto.endswith('""'):
        texto = texto[:-1]
    return texto


def celula_do_texto(celula):
    """Celula do texto do Tasy convertida como o Excel fazia ao abrir o arquivo:
    "" -> vazio; "201749" -> 201749; " 0000000000159,80" -> 159.8; o resto
    (inclusive "79.90", que o Excel em portugues deixa como texto) fica como veio."""
    limpo = celula.strip()
    if limpo == "":
        return None
    if _PADRAO_INTEIRO.fullmatch(limpo):
        return int(limpo)
    if _PADRAO_NUMERO_BR.fullmatch(limpo):
        return float(limpo.replace(".", "").replace(",", "."))
    return celula


def _ler_texto_tasy(caminho_arquivo, conteudo):
    texto = conteudo.decode(_CODIFICACAO_TASY, errors="replace")
    linhas = list(csv.reader(io.StringIO(texto, newline=""), delimiter=_SEPARADOR_TASY, quotechar='"'))
    if not linhas:
        return pd.DataFrame()
    cabecalho, dados = linhas[0], linhas[1:]
    largura = len(cabecalho)
    dados = [[celula_do_texto(c) for c in (linha + [""] * largura)[:largura]] for linha in dados]
    # Mesmos nomes que o pandas daria lendo o .xlsx (o repetido ganha ".1").
    nomes, vistos = [], {}
    for nome in cabecalho:
        nome = nome.strip()
        nomes.append(f"{nome}.{vistos[nome]}" if nome in vistos else nome)
        vistos[nome] = vistos.get(nome, 0) + 1
    return pd.DataFrame(dados, columns=nomes, dtype=object)


def _abrir_relatorio(caminho_arquivo):
    """O formato e reconhecido pelo CONTEUDO: .xlsx (ou Excel antigo) pelo
    pandas; o .xls de texto do Tasy pelo leitor de texto."""
    conteudo = Path(caminho_arquivo).read_bytes()
    if conteudo.startswith(_ASSINATURA_ZIP) or conteudo.startswith(_ASSINATURA_XLS_BINARIO):
        # dtype=object preserva contas e centros de custo como vieram (sem virar
        # 1007.0 quando a coluna tem celulas vazias).
        return pd.read_excel(io.BytesIO(conteudo), sheet_name=0, header=0, dtype=object)
    return _ler_texto_tasy(caminho_arquivo, conteudo)


def _ler_relatorio(caminho_arquivo):
    df = _abrir_relatorio(caminho_arquivo)
    if df.shape[1] < _MINIMO_COLUNAS:
        raise ValueError(
            f"{Path(caminho_arquivo).name}: esperado ao menos {_MINIMO_COLUNAS} colunas "
            f"(contrato, dia, conta debito, conta credito, valor), encontradas {df.shape[1]}."
        )

    # Algumas exportacoes repetem a linha de cabecalho no meio dos dados (a
    # cada "pagina" do relatorio); essas linhas sao descartadas. Compara so as
    # primeiras colunas porque o pandas renomeia a de valor repetida ("X.1").
    cabecalho = [str(nome).strip() for nome in df.columns[:_MINIMO_COLUNAS]]
    eh_cabecalho_repetido = df.iloc[:, :_MINIMO_COLUNAS].apply(
        lambda linha: [str(v).strip() for v in linha] == cabecalho, axis=1
    )
    df = df[~eh_cabecalho_repetido]

    df = df.iloc[:, 1 : 1 + len(COLUNAS_SAIDA)]
    df.columns = COLUNAS_SAIDA[: df.shape[1]]
    df = df.reindex(columns=COLUNAS_SAIDA)
    return df.dropna(how="all")


def consolidar_relatorios(pasta_entrada):
    """Empilha todos os relatorios (.xlsx e .xls do Tasy) de pasta_entrada num
    DataFrame com COLUNAS_SAIDA.

    A quantidade de linhas que veio de cada arquivo fica em
    df.attrs["linhas_por_arquivo"] ({nome do arquivo: linhas}).
    """
    pasta = Path(pasta_entrada)
    # "~$" sao os arquivos temporarios que o Excel cria enquanto a planilha esta aberta.
    arquivos = listar_relatorios(pasta)
    if not arquivos:
        raise ValueError(f"Nenhum relatório .xlsx ou .xls encontrado em: {pasta}")
    repetidos = sorted({p.stem for p in arquivos if sum(1 for q in arquivos if q.stem == p.stem) > 1})
    if repetidos:
        raise ValueError(
            "O mesmo relatório está na pasta em .xls e em .xlsx e entraria duas vezes no Rel_Geral: "
            + "; ".join(repetidos) + ". Deixe só um dos dois arquivos de cada e gere de novo."
        )

    partes = []
    linhas_por_arquivo = {}
    for arquivo in arquivos:
        df = _ler_relatorio(arquivo)
        partes.append(df)
        linhas_por_arquivo[arquivo.name] = len(df)

    df_geral = pd.concat(partes, ignore_index=True)
    df_geral["Complemento"] = df_geral["Complemento"].map(_corrigir_complemento)
    for coluna in _COLUNAS_VALOR:
        df_geral[coluna] = df_geral[coluna].map(converter_valor)

    df_geral.attrs["linhas_por_arquivo"] = linhas_por_arquivo
    return df_geral


def listar_relatorios(pasta):
    """Relatorios da pasta (.xlsx e .xls), sem os temporarios "~$" do Excel."""
    return sorted(p for p in Path(pasta).iterdir()
                  if p.is_file() and p.suffix.lower() in EXTENSOES_RELATORIO and not p.name.startswith("~$"))


def salvar_rel_geral(df, caminho_saida):
    """Grava df num .xlsx com uma unica aba "Consolidado" (cabecalho + dados, sem total)."""
    Path(caminho_saida).parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(caminho_saida, sheet_name=_NOME_ABA, index=False)
