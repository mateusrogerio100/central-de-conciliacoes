"""Geracao do .txt de importacao contabil a partir da planilha Rel_Geral.

Cada lancamento da aba "Consolidado" vira duas linhas no arquivo:
    {data},{conta debito},{conta credito},{valor},{historico},{complemento}
    {centro custo},{valor}
gravado em ISO-8859-1 com quebras de linha CRLF, no layout que o sistema
contabil importa.
"""

import calendar

import pandas as pd

from .consolidar import converter_valor

_NOME_ABA = "Consolidado"
# Colunas da aba, na ordem. Lidas pela posicao porque um Rel_Geral montado a
# mao pode repetir o nome "Vl parcela formatado" nas duas colunas de valor.
_COLUNAS = ["dia", "conta_debito", "conta_credito", "valor", "historico",
            "complemento", "centro_custo", "valor_2"]

# Lancamentos de provisao (contas de ativo/passivo) podem vir sem centro de
# custo, mas o layout exige a segunda linha mesmo assim.
_CENTRO_CUSTO_PADRAO = "1007"

_LARGURA_VALOR = 14
_LARGURA_CENTRO_CUSTO = 6


def _data_fixa(mes, ano):
    """Ultimo dia do mes em DDMMAA (mes=8, ano=2026 -> "310826")."""
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    return f"{ultimo_dia:02d}{mes:02d}{ano % 100:02d}"


def _texto_codigo(valor):
    """Conta, historico ou centro de custo como texto, sem o ".0" que o Excel
    coloca em numeros inteiros."""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return str(valor).strip()


def _formatar_valor(valor):
    return f"{converter_valor(valor):0{_LARGURA_VALOR}.2f}"


def _formatar_complemento(valor):
    """Complemento sempre entre um unico par de aspas, sem espacos do lado de
    dentro, e com as virgulas trocadas por pontos (a virgula separa os campos
    do layout). Cobre as variacoes que vem das exportacoes: espacos antes ou
    depois das aspas, aspas duplicadas nas pontas e aspas de fechamento
    faltando."""
    texto = "" if pd.isna(valor) else str(valor)
    miolo = texto.strip().strip('"').strip()
    return '"' + miolo.replace(",", ".") + '"'


def _ler_lancamentos(caminho_rel_geral):
    df = pd.read_excel(caminho_rel_geral, sheet_name=_NOME_ABA, header=0, dtype=object)
    if df.shape[1] < len(_COLUNAS):
        raise ValueError(
            f'A aba "{_NOME_ABA}" deveria ter {len(_COLUNAS)} colunas, encontradas {df.shape[1]}.'
        )
    df = df.iloc[:, : len(_COLUNAS)]
    df.columns = _COLUNAS

    df = df.dropna(how="all")
    # A linha de total (quando existe) nao tem conta de debito numerica.
    conta_numerica = pd.to_numeric(df["conta_debito"], errors="coerce").notna()
    return df[conta_numerica]


def gerar_import(caminho_rel_geral, mes, ano, caminho_saida):
    """Gera o .txt de importacao em caminho_saida e devolve quantos
    lancamentos foram gravados."""
    df = _ler_lancamentos(caminho_rel_geral)
    data = _data_fixa(mes, ano)

    linhas = []
    for lanc in df.itertuples(index=False):
        valor = _formatar_valor(lanc.valor)
        centro_custo = _CENTRO_CUSTO_PADRAO if pd.isna(lanc.centro_custo) else _texto_codigo(lanc.centro_custo)
        valor_2 = valor if pd.isna(lanc.valor_2) else _formatar_valor(lanc.valor_2)

        linhas.append(",".join([
            data,
            _texto_codigo(lanc.conta_debito),
            _texto_codigo(lanc.conta_credito),
            valor,
            _texto_codigo(lanc.historico),
            _formatar_complemento(lanc.complemento),
        ]))
        linhas.append(f"{centro_custo:<{_LARGURA_CENTRO_CUSTO}},{valor_2}")

    conteudo = "".join(linha + "\r\n" for linha in linhas)
    try:
        dados = conteudo.encode("iso-8859-1")
    except UnicodeEncodeError as erro:
        numero_linha = conteudo[: erro.start].count("\r\n") + 1
        raise ValueError(
            f"O caractere {conteudo[erro.start]!r} (linha {numero_linha} do txt) "
            "nao existe na codificacao ISO-8859-1 exigida pelo import. "
            "Corrija o texto no Rel_Geral e gere novamente."
        ) from erro

    with open(caminho_saida, "wb") as arquivo:
        arquivo.write(dados)
    return len(df)
