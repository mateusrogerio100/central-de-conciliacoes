"""
Leitor do relatório "Patrimonio - Bens adquiridos no período por centro custo" (Tasy 555).

Formato (texto separado por tabulação, ver leitor_texto):
- "Bens adquiridos de:" 01/08/2026 "até:" 31/08/2026 → período.
- Cabeçalho: Centro, Conta, Código Bem, Descrição Bem, Dt. Aquisição, Dt. Início,
  Taxa Deprec, Vl original (lido de novo a cada página).
- Linha de centro ("1888  -  Central de Esterilização de Materiais") na coluna Centro,
  linha de conta ("11038 Aparelhos de informática AME") na coluna Conta e, embaixo,
  uma linha por bem.
- "Total(2) ... 6.689,00" no fim: a soma e a quantidade lidas são conferidas com ele.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from modulos.conciliacao_imobilizado.base_iss import Aviso
from modulos.conciliacao_imobilizado.leitor_texto import (
    RELATORIO_BENS_ADQUIRIDOS,
    ArquivoIlegivel,
    Cabecalho,
    data,
    depois_do_rotulo,
    eh_rodape,
    erro_relatorio_errado,
    identificar_relatorio,
    juntar_espacos,
    ler_linhas,
    preenchidas,
    reais,
    valor,
)
from modulos.conciliacao_imobilizado.modelos import BemAdquirido, LeituraBensAdquiridos

COL_CENTRO = "Centro"
COL_CONTA = "Conta"
COL_CODIGO_BEM = "Código Bem"
COL_DESCRICAO = "Descrição Bem"
COL_DATA_AQUISICAO = "Dt. Aquisição"
COL_VALOR = "Vl original"
COLUNAS_OBRIGATORIAS = (COL_CENTRO, COL_CONTA, COL_CODIGO_BEM, COL_DESCRICAO, COL_VALOR)

ROTULO_INICIO = "Bens adquiridos de:"
ROTULO_FIM = "até:"

_REGEX_CONTA = re.compile(r"^(\d+)\s*-?\s*(.*)$")
_REGEX_TOTAL = re.compile(r"^Total\s*\((\d+)\)", re.IGNORECASE)


def ler_bens_adquiridos(caminho: Path) -> LeituraBensAdquiridos:
    caminho = Path(caminho)
    leitura = LeituraBensAdquiridos(arquivo=caminho.name)
    try:
        linhas = ler_linhas(caminho)
    except ArquivoIlegivel as erro:
        leitura.erro = str(erro)
        return leitura

    erro = erro_relatorio_errado(RELATORIO_BENS_ADQUIRIDOS, identificar_relatorio(linhas))
    if erro:
        leitura.erro = erro
        return leitura

    cabecalho: Cabecalho | None = None
    centro = conta_codigo = conta_nome = ""
    total_impresso: tuple[int, Decimal] | None = None

    for numero, linha in enumerate(linhas, start=1):
        celulas = preenchidas(linha)
        if not celulas:
            continue
        if leitura.periodo_inicio is None:
            leitura.periodo_inicio = data(depois_do_rotulo(linha, ROTULO_INICIO))
            leitura.periodo_fim = data(depois_do_rotulo(linha, ROTULO_FIM))

        possivel = Cabecalho(linha)
        if possivel.tem(*COLUNAS_OBRIGATORIAS):
            cabecalho = possivel
            continue
        if cabecalho is None or eh_rodape(linha):
            continue

        total = _REGEX_TOTAL.match(celulas[0])
        if total:
            try:
                total_impresso = (int(total.group(1)), valor(celulas[-1]))
            except ValueError:
                pass
            continue

        codigo_bem = cabecalho.valor(linha, COL_CODIGO_BEM)
        if codigo_bem:
            texto_valor = cabecalho.valor(linha, COL_VALOR)
            try:
                valor_bem = valor(texto_valor)
            except ValueError:
                valor_bem = None
            if valor_bem is None:
                leitura.avisos.append(Aviso(
                    arquivo=leitura.arquivo,
                    mensagem=f"Linha {numero}: bem {codigo_bem} sem valor reconhecido "
                             f"({texto_valor!r}); ele não foi lido.",
                ))
                continue
            if not conta_codigo:
                leitura.avisos.append(Aviso(
                    arquivo=leitura.arquivo,
                    mensagem=f"Linha {numero}: bem {codigo_bem} sem conta antes; ele não foi lido.",
                ))
                continue
            leitura.bens.append(BemAdquirido(
                centro=centro, conta_codigo=conta_codigo, conta_nome=conta_nome,
                codigo_bem=codigo_bem,
                descricao=juntar_espacos(cabecalho.valor(linha, COL_DESCRICAO)),
                data_aquisicao=data(cabecalho.valor(linha, COL_DATA_AQUISICAO)),
                valor=valor_bem,
            ))
            continue

        texto_conta = cabecalho.valor(linha, COL_CONTA)
        if texto_conta:
            encontrado = _REGEX_CONTA.match(texto_conta)
            if encontrado:
                conta_codigo, conta_nome = encontrado.group(1), juntar_espacos(encontrado.group(2))
            continue
        texto_centro = cabecalho.valor(linha, COL_CENTRO)
        if texto_centro:
            centro = juntar_espacos(texto_centro)

    if cabecalho is None:
        leitura.erro = ("Cabeçalho do relatório de bens adquiridos não encontrado "
                        f"(colunas esperadas: {', '.join(COLUNAS_OBRIGATORIAS)}).")
        return leitura

    soma = sum((b.valor for b in leitura.bens), Decimal(0))
    if total_impresso is not None:
        quantidade, valor_total = total_impresso
        if quantidade != len(leitura.bens) or valor_total != soma:
            leitura.avisos.append(Aviso(
                arquivo=leitura.arquivo,
                mensagem=f"ATENÇÃO: foram lidos {len(leitura.bens)} bens somando {reais(soma)}, "
                         f"mas o total impresso no relatório é {quantidade} bens / "
                         f"{reais(valor_total)}. Algum bem pode não ter sido lido.",
            ))
    elif leitura.bens:
        leitura.avisos.append(Aviso(
            arquivo=leitura.arquivo,
            mensagem="Linha \"Total\" não encontrada no relatório de bens adquiridos; "
                     "não deu para conferir se todos os bens foram lidos.",
        ))
    return leitura
