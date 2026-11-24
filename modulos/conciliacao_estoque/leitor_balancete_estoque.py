"""Leitura do balancete do Tasy, grupo 1.01.04 ESTOQUES (ESPECIFICACAO_ESTOQUE.md, seção 3.2).

Como o arquivo é lido (nunca por letra de coluna):
- linha de conta = tem uma célula de classificação (1.01.04, 1.01.04.01, 1.01.04.01.0002);
- Código (reduzido) = célula preenchida mais próxima à esquerda da classificação;
- Descrição = primeira célula de texto à direita da classificação, sem os espaços das pontas;
- Saldo Anterior, Movimento e Saldo Atual = os três números à direita da descrição, nessa ordem;
  no balancete do CMD e dos AMES são quatro (Saldo Anterior, Débitos, Créditos, Saldo Atual) e o
  Movimento é Débitos − Créditos (a linha de títulos diz qual dos dois é);
- "Mês Referência:" -> primeira célula preenchida à direita ("set/2026").
Só entram as contas sob 1.01.04; as demais são contadas e ignoradas.
"""

from __future__ import annotations

import re
from pathlib import Path

from modulos.conciliacao_estoque import configuracao
from modulos.conciliacao_estoque.leitor_tasy_texto import ler_linhas
from modulos.conciliacao_estoque.modelos import (
    Aviso,
    BalanceteEstoque,
    ContaBalancete,
    ErroArquivo,
    Gravidade,
)
from modulos.conciliacao_estoque.utilitarios import (
    mes_de_texto,
    para_decimal,
    texto_comeca_com,
    texto_igual,
)

_PADRAO_CLASSIFICACAO = re.compile(configuracao.BALANCETE_PADRAO_CLASSIFICACAO)


def _eh_classificacao(texto: str) -> bool:
    return bool(_PADRAO_CLASSIFICACAO.match(texto.strip()))


def _dentro_do_prefixo(classificacao: str) -> bool:
    prefixo = configuracao.PREFIXO_ESTOQUE
    return classificacao == prefixo or classificacao.startswith(prefixo + ".")


def _tem_titulos(celulas: dict[int, str], titulos) -> bool:
    return all(any(texto_igual(v, titulo) for v in celulas.values()) for titulo in titulos)


def ler_balancete_estoque(caminho) -> BalanceteEstoque:
    caminho = Path(caminho)
    linhas = ler_linhas(caminho)
    balancete = BalanceteEstoque(arquivo=caminho.name)

    def avisar(gravidade, tipo, mensagem, linha=None, conta=""):
        balancete.avisos.append(Aviso(gravidade, tipo, mensagem, arquivo=caminho.name, linha=linha, conta=conta))

    achou_titulos = False
    com_debito_credito = False
    for numero_linha, linha in enumerate(linhas, start=1):
        celulas = {i: v.strip() for i, v in enumerate(linha) if v.strip()}
        if not celulas:
            continue
        if any(texto_comeca_com(celulas[min(celulas)], r) for r in configuracao.RODAPES):
            continue
        if _tem_titulos(celulas, configuracao.BALANCETE_TITULOS_VALORES):
            achou_titulos, com_debito_credito = True, False
            continue
        if _tem_titulos(celulas, configuracao.BALANCETE_TITULOS_DEBITO_CREDITO):
            achou_titulos, com_debito_credito = True, True
            continue

        coluna_mes = next(
            (i for i in sorted(celulas) if texto_igual(celulas[i], configuracao.BALANCETE_TITULO_MES_REFERENCIA)),
            None,
        )
        if coluna_mes is not None:
            _ler_mes(balancete, celulas, coluna_mes, numero_linha, avisar)
            continue

        coluna_classificacao = next((i for i in sorted(celulas) if _eh_classificacao(celulas[i])), None)
        if coluna_classificacao is None:
            continue
        if not _dentro_do_prefixo(celulas[coluna_classificacao]):
            balancete.contas_fora_do_prefixo += 1
            continue
        _ler_conta(balancete, celulas, coluna_classificacao, numero_linha, avisar, com_debito_credito)

    if not achou_titulos:
        raise ErroArquivo(
            f"{caminho.name}: não parece ser um balancete (linha de títulos "
            f"'{' / '.join(configuracao.BALANCETE_TITULOS_VALORES)}' ou "
            f"'{' / '.join(configuracao.BALANCETE_TITULOS_DEBITO_CREDITO)}' não encontrada)."
        )
    if balancete.mes_referencia is None:
        avisar(Gravidade.ATENCAO, "mês não encontrado",
               f"'{configuracao.BALANCETE_TITULO_MES_REFERENCIA}' não encontrado no balancete.")
    _avisar_classificacoes_repetidas(balancete, avisar)
    return balancete


def _ler_mes(balancete, celulas, coluna_mes, numero_linha, avisar):
    valor = next((celulas[i] for i in sorted(celulas) if i > coluna_mes), "")
    mes = mes_de_texto(valor)
    if mes is None:
        avisar(Gravidade.ATENCAO, "mês não reconhecido",
               f"Não foi possível ler o mês de referência: {valor!r}.", numero_linha)
    elif balancete.mes_referencia is None:
        balancete.mes_referencia = mes
    elif mes != balancete.mes_referencia:
        avisar(Gravidade.ATENCAO, "mês diferente entre páginas",
               f"Página com mês {mes}, diferente do mês {balancete.mes_referencia} "
               "da primeira página. Vale o da primeira página.", numero_linha)


def _ler_conta(balancete, celulas, coluna_classificacao, numero_linha, avisar, com_debito_credito=False):
    classificacao = celulas[coluna_classificacao]

    coluna_codigo = max((i for i in celulas if i < coluna_classificacao), default=None)
    texto_codigo = celulas.get(coluna_codigo, "")
    if not texto_codigo.isdigit():
        avisar(Gravidade.ERRO, "linha não reconhecida",
               f"Conta {classificacao} sem código numérico à esquerda da classificação; linha ignorada.",
               numero_linha, classificacao)
        return
    codigo = int(texto_codigo)

    depois = [i for i in sorted(celulas) if i > coluna_classificacao]
    coluna_descricao = next((i for i in depois if para_decimal(celulas[i]) is None), None)
    descricao = celulas[coluna_descricao] if coluna_descricao is not None else ""
    valores = [
        para_decimal(celulas[i]) for i in depois
        if coluna_descricao is None or i > coluna_descricao
    ]
    titulos = (configuracao.BALANCETE_TITULOS_DEBITO_CREDITO if com_debito_credito
               else configuracao.BALANCETE_TITULOS_VALORES)
    if len(valores) != len(titulos) or any(v is None for v in valores):
        avisar(Gravidade.ERRO, "linha não reconhecida",
               f"Conta {codigo} ({classificacao}): esperados {len(titulos)} números à direita da descrição "
               f"({', '.join(titulos)}), encontrados {len(valores)}; linha ignorada.",
               numero_linha, str(codigo))
        return
    if com_debito_credito:
        saldo_anterior, debitos, creditos, saldo_atual = valores
        movimento = debitos - creditos
    else:
        saldo_anterior, movimento, saldo_atual = valores

    if any(c.codigo == codigo for c in balancete.contas):
        avisar(Gravidade.ATENCAO, "código repetido no balancete",
               f"Código {codigo} aparece de novo; vale a primeira ocorrência.", numero_linha, str(codigo))
        return

    if saldo_anterior + movimento != saldo_atual:
        avisar(Gravidade.ERRO, "saldo não fecha",
               f"Conta {codigo} ({classificacao}): Saldo Anterior {saldo_anterior} + Movimento {movimento} "
               f"diferente do Saldo Atual {saldo_atual}. Confira a leitura do arquivo.",
               numero_linha, str(codigo))

    balancete.contas.append(ContaBalancete(
        codigo=codigo,
        classificacao=classificacao,
        descricao=descricao,
        saldo_anterior=saldo_anterior,
        movimento=movimento,
        saldo_atual=saldo_atual,
        linha=numero_linha,
    ))


def _avisar_classificacoes_repetidas(balancete, avisar):
    """Duas contas com a mesma classificação não são erro: a conta é identificada pelo código."""
    por_classificacao: dict[str, list[ContaBalancete]] = {}
    for conta in balancete.analiticas:
        por_classificacao.setdefault(conta.classificacao, []).append(conta)
    for classificacao, contas in por_classificacao.items():
        if len(contas) > 1:
            nomes = "; ".join(f"{c.codigo} {c.descricao}" for c in contas)
            avisar(Gravidade.INFO, "classificação repetida",
                   f"Classificação {classificacao} usada por {len(contas)} contas ({nomes}). "
                   "Não é erro: cada conta é identificada pelo código reduzido.",
                   contas[1].linha, classificacao)
