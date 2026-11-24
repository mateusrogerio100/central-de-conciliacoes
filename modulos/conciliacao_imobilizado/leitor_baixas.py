"""
Leitor do relatório "Baixa de bens do ativo imobilizado" (Tasy 561).

Formato (texto separado por tabulação, ver leitor_texto):
- Logo acima do cabeçalho, o AME ("Ame - Cidade Alfa ( Fund. Hospital Exemplo ... )").
- Cabeçalho: CHAPA, IMOBILIZADO, TIPO, MOTIVO, VL. ORIGEM, VL. DEPREC., VL. ATUAL, DATA
  (repetido a cada página, às vezes deslocado: as colunas são relidas a cada página).
- Os bens vêm agrupados pelo NOME da conta ("Equipamentos hospitalares AME"), sem o código;
  a conciliação acha a conta pelo nome (decisão do usuário).
- "Total - <conta>(40)" e "Total(40)": a soma e a quantidade lidas são conferidas com eles.
- O valor que sai do saldo da conta é o VL. ORIGEM.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from modulos.conciliacao_imobilizado.base_iss import Aviso
from modulos.conciliacao_imobilizado.leitor_texto import (
    RELATORIO_BAIXAS,
    ArquivoIlegivel,
    Cabecalho,
    data,
    eh_rodape,
    erro_relatorio_errado,
    identificar_relatorio,
    juntar_espacos,
    ler_linhas,
    preenchidas,
    reais,
    valor,
)
from modulos.conciliacao_imobilizado.modelos import BemBaixado, LeituraBaixas

COL_CHAPA = "CHAPA"
COL_DESCRICAO = "IMOBILIZADO"
COL_TIPO = "TIPO"
COL_MOTIVO = "MOTIVO"
COL_ORIGEM = "VL. ORIGEM"
COL_DEPRECIACAO = "VL. DEPREC."
COL_ATUAL = "VL. ATUAL"
COL_DATA = "DATA"
COLUNAS_OBRIGATORIAS = (COL_CHAPA, COL_DESCRICAO, COL_ORIGEM)

_REGEX_TOTAL_CONTA = re.compile(r"^Total\s*-\s*(.+?)\s*\((\d+)\)\s*$", re.IGNORECASE)
_REGEX_TOTAL_GERAL = re.compile(r"^Total\s*\((\d+)\)\s*$", re.IGNORECASE)


def _valor_opcional(texto: str) -> Decimal | None:
    try:
        return valor(texto)
    except ValueError:
        return None


def ler_baixas(caminho: Path) -> LeituraBaixas:
    caminho = Path(caminho)
    leitura = LeituraBaixas(arquivo=caminho.name)
    try:
        linhas = ler_linhas(caminho)
    except ArquivoIlegivel as erro:
        leitura.erro = str(erro)
        return leitura

    erro = erro_relatorio_errado(RELATORIO_BAIXAS, identificar_relatorio(linhas))
    if erro:
        leitura.erro = erro
        return leitura

    cabecalho: Cabecalho | None = None
    conta_nome = ""
    entre_paginas = False
    anterior: list[str] = []
    totais_conta: list[tuple[str, int, Decimal | None]] = []
    total_geral: tuple[int, Decimal | None] | None = None

    for numero, linha in enumerate(linhas, start=1):
        celulas = preenchidas(linha)
        if not celulas:
            continue
        possivel = Cabecalho(linha)
        if possivel.tem(*COLUNAS_OBRIGATORIAS):
            cabecalho = possivel
            entre_paginas = False
            if not leitura.ame and len(anterior) == 1:
                leitura.ame = juntar_espacos(anterior[0])
            continue
        anterior = celulas
        if eh_rodape(linha):
            entre_paginas = True             # até o próximo cabeçalho: topo da página seguinte
            continue
        if cabecalho is None:
            continue
        if entre_paginas and len(celulas) == 1:
            continue                         # RESPONSÁVEL, título, AME... do topo da página

        total_conta = _REGEX_TOTAL_CONTA.match(celulas[0])
        if total_conta:
            totais_conta.append((juntar_espacos(total_conta.group(1)), int(total_conta.group(2)),
                                 _valor_opcional(cabecalho.valor(linha, COL_ORIGEM))))
            continue
        total = _REGEX_TOTAL_GERAL.match(celulas[0])
        if total:
            total_geral = (int(total.group(1)), _valor_opcional(cabecalho.valor(linha, COL_ORIGEM)))
            continue

        if len(celulas) == 1:
            conta_nome = juntar_espacos(celulas[0])     # título do grupo (nome da conta)
            continue

        chapa = cabecalho.valor(linha, COL_CHAPA)
        texto_origem = cabecalho.valor(linha, COL_ORIGEM)
        valor_origem = _valor_opcional(texto_origem)
        if not chapa or valor_origem is None:
            leitura.avisos.append(Aviso(
                arquivo=leitura.arquivo,
                mensagem=f"Linha {numero}: linha não reconhecida ({' | '.join(celulas)}); "
                         "ela não foi lida.",
            ))
            continue
        if not conta_nome:
            leitura.avisos.append(Aviso(
                arquivo=leitura.arquivo,
                mensagem=f"Linha {numero}: bem {chapa} sem conta antes; ele não foi lido.",
            ))
            continue
        leitura.bens.append(BemBaixado(
            conta_nome=conta_nome, chapa=chapa,
            descricao=juntar_espacos(cabecalho.valor(linha, COL_DESCRICAO)),
            tipo=cabecalho.valor(linha, COL_TIPO),
            motivo=cabecalho.valor(linha, COL_MOTIVO),
            valor_origem=valor_origem,
            valor_depreciacao=_valor_opcional(cabecalho.valor(linha, COL_DEPRECIACAO)),
            valor_atual=_valor_opcional(cabecalho.valor(linha, COL_ATUAL)),
            data=data(cabecalho.valor(linha, COL_DATA)),
        ))

    if cabecalho is None:
        leitura.erro = ("Cabeçalho do relatório de baixa de bens não encontrado "
                        f"(colunas esperadas: {', '.join(COLUNAS_OBRIGATORIAS)}).")
        return leitura

    _conferir_totais(leitura, totais_conta, total_geral)
    return leitura


def _conferir_totais(leitura: LeituraBaixas, totais_conta, total_geral) -> None:
    def conferir(rotulo: str, bens: list[BemBaixado], quantidade: int, total: Decimal | None):
        soma = sum((b.valor_origem for b in bens), Decimal(0))
        if quantidade != len(bens) or (total is not None and total != soma):
            leitura.avisos.append(Aviso(
                arquivo=leitura.arquivo,
                mensagem=f"ATENÇÃO: {rotulo}: foram lidos {len(bens)} bens somando {reais(soma)}, "
                         f"mas o total impresso é {quantidade} bens / {reais(total)}. "
                         "Algum bem pode não ter sido lido.",
            ))

    for nome, quantidade, total in totais_conta:
        bens = [b for b in leitura.bens if b.conta_nome.casefold() == nome.casefold()]
        conferir(f"conta {nome}", bens, quantidade, total)
    if total_geral is not None:
        conferir("total do relatório", leitura.bens, *total_geral)
    elif leitura.bens:
        leitura.avisos.append(Aviso(
            arquivo=leitura.arquivo,
            mensagem="Linha \"Total\" não encontrada no relatório de baixas; "
                     "não deu para conferir se todos os bens foram lidos.",
        ))
