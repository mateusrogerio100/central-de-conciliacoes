"""Leitura do relatório SCF - Movimento Estoque (Contabilidade) (ESPECIFICACAO_ESTOQUE.md, seção 3.3).

As colunas mudam de lugar entre as páginas (na página 2 a linha começa uma coluna à direita),
por isso o programa NUNCA usa a letra da coluna:
- descrição = primeiro texto não vazio da linha;
- os números da linha, na ordem em que aparecem, são os 13 valores de configuracao.SCF_TITULOS
  (o 1º é o Saldo Anterior, o 13º é o Saldo Atual).
O SCF do CMD e dos AMES vem sem a coluna Subvenção (12 títulos), com "Empréstimo" e
"Out. Entradas" escritos de outro jeito e um número a mais, sem título e zerado, depois do Saldo
Atual. A linha de títulos diz quais colunas existem: a que falta fica 0,00 e o número a mais é
deixado de lado (se não for zero, a linha não é usada). Os valores continuam nas 13 posições.
Linha de local: a descrição termina com "(código)". Linha de total: "Total(40)".
O fechamento por local (anterior + entradas − saídas = atual) NÃO é conferido aqui: por decisão
do usuário, ele é conferido só no total geral, na EST-02.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from modulos.conciliacao_estoque import configuracao
from modulos.conciliacao_estoque.leitor_tasy_texto import ler_linhas
from modulos.conciliacao_estoque.modelos import Aviso, ErroArquivo, Gravidade, LocalSCF, RelatorioSCF
from modulos.conciliacao_estoque.utilitarios import (
    mes_de_texto,
    normalizar_texto,
    para_decimal,
    texto_comeca_com,
    texto_igual,
)

_PADRAO_CODIGO_LOCAL = re.compile(configuracao.SCF_PADRAO_CODIGO_LOCAL)
_PADRAO_TOTAL = re.compile(configuracao.SCF_PADRAO_TOTAL, re.IGNORECASE)
_QUANTIDADE_VALORES = len(configuracao.SCF_TITULOS)
_ZERO = Decimal("0.00")


def posicao_do_titulo(titulo: str) -> int:
    """Posição (1 a 13) do primeiro título com esse nome em configuracao.SCF_TITULOS."""
    for posicao, nome in enumerate(configuracao.SCF_TITULOS, start=1):
        if texto_igual(nome, titulo):
            return posicao
    raise ValueError(f"Título do SCF desconhecido: {titulo!r}")


def ler_scf(caminho) -> RelatorioSCF:
    caminho = Path(caminho)
    relatorio = RelatorioSCF(arquivo=caminho.name)

    def avisar(gravidade, tipo, mensagem, linha=None, conta=""):
        relatorio.avisos.append(Aviso(gravidade, tipo, mensagem, arquivo=caminho.name, linha=linha, conta=conta))

    achou_titulos = False
    # para cada uma das 13 posições, o índice do número na linha (None = coluna ausente no arquivo)
    disposicao = list(range(_QUANTIDADE_VALORES))
    avisou = set()

    def avisar_uma_vez(tipo, mensagem):
        if tipo not in avisou:
            avisou.add(tipo)
            avisar(Gravidade.INFO, tipo, mensagem)

    def valores_da_linha(numeros):
        """Os 13 valores da linha, ou None se a quantidade de números não bate com os títulos."""
        esperados = sum(1 for i in disposicao if i is not None)
        if len(numeros) == esperados + 1 and numeros[-1] == 0:
            avisar_uma_vez("coluna sem título",
                           "Número a mais, sem título e zerado, depois do Saldo Atual: deixado de lado.")
            numeros = numeros[:-1]
        if len(numeros) != esperados:
            return None
        return [numeros[i] if i is not None else _ZERO for i in disposicao]
    for numero_linha, linha in enumerate(ler_linhas(caminho), start=1):
        textos = [v.strip() for v in linha if v.strip()]
        if not textos:
            continue
        primeiro = textos[0]
        if any(texto_comeca_com(primeiro, r) for r in configuracao.RODAPES):
            continue

        if texto_igual(primeiro, configuracao.SCF_TITULO_DESCRICAO):
            disposicao = _conferir_titulos(caminho.name, textos[1:])
            for posicao, indice in enumerate(disposicao):
                if indice is None:
                    titulo = configuracao.SCF_TITULOS[posicao]
                    avisar_uma_vez("coluna ausente no Mapa do Estoque",
                                   f"O Mapa do Estoque não tem a coluna {titulo}: considerada 0,00 em todos os locais.")
            achou_titulos = True
            continue

        posicao_mes = next(
            (i for i, t in enumerate(textos) if texto_igual(t, configuracao.SCF_TITULO_MES_COMPETENCIA)), None
        )
        if posicao_mes is not None:
            _ler_mes(relatorio, textos[posicao_mes + 1:], numero_linha, avisar)
            continue

        numeros = [para_decimal(t) for t in textos[1:] if para_decimal(t) is not None]

        total = _PADRAO_TOTAL.match(primeiro)
        if total:
            _ler_total(relatorio, int(total.group(1)), numeros, valores_da_linha(numeros), numero_linha, avisar)
            continue

        codigo = _PADRAO_CODIGO_LOCAL.search(primeiro)
        if codigo is None:
            if numeros:
                relatorio.linhas_ignoradas += 1
                avisar(Gravidade.ERRO, "linha não reconhecida",
                       f"Linha com valores mas sem o código do local entre parênteses ({primeiro!r}); "
                       "linha ignorada.", numero_linha)
            continue
        _ler_local(relatorio, int(codigo.group(1)), primeiro, numeros, valores_da_linha(numeros), numero_linha,
                   avisar)

    if not achou_titulos:
        raise ErroArquivo(
            f"{caminho.name}: não parece ser o relatório SCF - Movimento Estoque "
            f"(linha de títulos começando por '{configuracao.SCF_TITULO_DESCRICAO}' não encontrada)."
        )
    if relatorio.mes_referencia is None:
        avisar(Gravidade.ATENCAO, "mês não encontrado",
               f"'{configuracao.SCF_TITULO_MES_COMPETENCIA}' não encontrado no Mapa do Estoque.")
    _conferir_total(relatorio, avisar)
    return relatorio


def _chave_titulo(titulo: str) -> str:
    """Título sem acento, caixa, espaço e pontuação: "Out. Entradas" = "Out.Entradas"."""
    return re.sub(r"[^a-z0-9]", "", normalizar_texto(titulo))


def _conferir_titulos(nome_arquivo: str, titulos: list[str]) -> list[int | None]:
    """Os títulos precisam ser os esperados, na mesma ordem (só os opcionais podem faltar): a leitura
    é pela posição. Devolve, para cada uma das 13 posições, o índice do número na linha (ou None)."""
    disposicao = []
    indice = 0
    for esperado in configuracao.SCF_TITULOS:
        if indice < len(titulos) and _chave_titulo(titulos[indice]) == _chave_titulo(esperado):
            disposicao.append(indice)
            indice += 1
        elif any(texto_igual(esperado, t) for t in configuracao.SCF_TITULOS_OPCIONAIS):
            disposicao.append(None)
        else:
            break
    else:
        if indice == len(titulos):
            return disposicao
    raise ErroArquivo(
            f"{nome_arquivo}: os títulos das colunas do Mapa do Estoque (SCF - Movimento Estoque) mudaram. Esperado: "
            f"{', '.join(configuracao.SCF_TITULOS)}. Encontrado: {', '.join(titulos)}. "
            "O programa lê os valores pela ordem dos títulos e precisa ser ajustado."
        )


def _ler_mes(relatorio, depois_do_rotulo, numero_linha, avisar):
    valor = depois_do_rotulo[0] if depois_do_rotulo else ""
    mes = mes_de_texto(valor)
    if mes is None:
        avisar(Gravidade.ATENCAO, "mês não reconhecido",
               f"Não foi possível ler o mês de competência: {valor!r}.", numero_linha)
    elif relatorio.mes_referencia is None:
        relatorio.mes_referencia = mes


def _ler_local(relatorio, codigo, descricao, numeros, valores, numero_linha, avisar):
    if valores is None:
        relatorio.linhas_ignoradas += 1
        avisar(Gravidade.ERRO, "linha não reconhecida",
               f"Local {descricao}: a quantidade de números ({len(numeros)}) não bate com os títulos do Mapa do Estoque; "
               "linha ignorada.", numero_linha, str(codigo))
        return
    repetido = relatorio.local(codigo)
    if repetido is not None:
        relatorio.linhas_ignoradas += 1
        avisar(Gravidade.ERRO, "local repetido no Mapa do Estoque",
               f"Código de local {codigo} aparece de novo ({descricao}; já lido: {repetido.descricao}); "
               "vale a primeira ocorrência.", numero_linha, str(codigo))
        return
    relatorio.locais.append(LocalSCF(codigo=codigo, descricao=descricao, valores=valores, linha=numero_linha))


def _ler_total(relatorio, quantidade, numeros, valores, numero_linha, avisar):
    if valores is None:
        avisar(Gravidade.ERRO, "linha não reconhecida",
               f"Linha Total({quantidade}): a quantidade de números ({len(numeros)}) não bate com os "
               "títulos do Mapa do Estoque; total não lido.", numero_linha)
        return
    relatorio.total = valores
    relatorio.quantidade_total = quantidade


def _conferir_total(relatorio, avisar):
    """Conferência de leitura: a soma dos locais lidos deve ser a linha Total(...)."""
    if relatorio.total is None:
        avisar(Gravidade.ERRO, "total não encontrado",
               "Linha 'Total(...)' não encontrada no Mapa do Estoque; não dá para conferir se a leitura está completa.")
        return
    if relatorio.quantidade_total != len(relatorio.locais):
        avisar(Gravidade.ERRO, "quantidade de locais",
               f"O Mapa do Estoque informa Total({relatorio.quantidade_total}), mas foram lidos "
               f"{len(relatorio.locais)} locais.")
    for posicao, titulo in enumerate(configuracao.SCF_TITULOS, start=1):
        soma = sum((l.valor(posicao) for l in relatorio.locais), Decimal("0.00"))
        if soma != relatorio.total_na_posicao(posicao):
            avisar(Gravidade.ERRO, "soma dos locais diferente do total",
                   f"Coluna {posicao} ({titulo}): soma dos locais {soma} diferente da linha "
                   f"Total {relatorio.total_na_posicao(posicao)}.")
