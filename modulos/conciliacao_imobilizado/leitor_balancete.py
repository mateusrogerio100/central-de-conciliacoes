"""
Leitor do Balancete (Tasy 865) — Intangível, Imobilizado ou Cessão, um arquivo cada.

Formato (texto separado por tabulação, ver leitor_texto):
- 1ª linha: o AME ("Ame - Cidade Alfa ( Fund. Hospital Exemplo )").
- "Mês Referência:" → "ago/2026".
- Cabeçalho: Código, Classificação, Descrição, Saldo Anterior, Débitos, Créditos, Saldo Atual.
- Cada conta numa linha. Nas linhas de conta as células ficam uma posição à direita do
  título da coluna, então os valores são lidos NA ORDEM do cabeçalho (todas as células de
  uma linha de conta vêm preenchidas, inclusive os 0,00).
- Conta-mãe (ex.: 1320 / 1.02.05.06) = conta cuja classificação é o começo da classificação
  de outra. Ela é a soma das filhas: não entra na comparação, mas a soma é conferida.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from modulos.conciliacao_imobilizado.base_iss import Aviso
from modulos.conciliacao_imobilizado.leitor_texto import (
    RELATORIO_BALANCETE,
    ArquivoIlegivel,
    competencia_de_mes_ano,
    depois_do_rotulo,
    erro_relatorio_errado,
    eh_rodape,
    identificar_relatorio,
    juntar_espacos,
    ler_linhas,
    preenchidas,
    reais,
    valor,
)
from modulos.conciliacao_imobilizado.modelos import ContaBalancete, LeituraBalancete

ROTULO_MES = "Mês Referência:"
TITULO_RELATORIO = "Balancete"
COLUNAS = ["Código", "Classificação", "Descrição", "Saldo Anterior", "Débitos", "Créditos",
           "Saldo Atual"]


def ler_balancete(caminho: Path) -> LeituraBalancete:
    caminho = Path(caminho)
    leitura = LeituraBalancete(arquivo=caminho.name)
    try:
        linhas = ler_linhas(caminho)
    except ArquivoIlegivel as erro:
        leitura.erro = str(erro)
        return leitura

    erro = erro_relatorio_errado(RELATORIO_BALANCETE, identificar_relatorio(linhas))
    if erro:
        leitura.erro = erro
        return leitura

    ordem_colunas: list[str] | None = None
    anterior: list[str] = []                 # última linha preenchida antes de "Balancete"
    for numero, linha in enumerate(linhas, start=1):
        celulas = preenchidas(linha)
        if not celulas:
            continue
        if not leitura.ame and celulas == [TITULO_RELATORIO] and anterior:
            leitura.ame = juntar_espacos(anterior[0])
        if not leitura.competencia:
            leitura.competencia = competencia_de_mes_ano(depois_do_rotulo(linha, ROTULO_MES))
        anterior = celulas

        if all(c in celulas for c in COLUNAS):
            ordem_colunas = celulas
            continue
        if ordem_colunas is None or eh_rodape(linha):
            continue
        if not celulas[0].isdigit():
            continue                         # "Ativo", títulos de grupo etc.
        if len(celulas) != len(ordem_colunas):
            leitura.avisos.append(Aviso(
                arquivo=leitura.arquivo,
                mensagem=f"Linha {numero}: conta {celulas[0]} em formato inesperado; "
                         "ela não foi lida.",
            ))
            continue
        campos = dict(zip(ordem_colunas, celulas))
        try:
            conta = ContaBalancete(
                codigo=campos["Código"],
                classificacao=campos["Classificação"],
                descricao=juntar_espacos(campos["Descrição"]),
                saldo_anterior=valor(campos["Saldo Anterior"]),
                debitos=valor(campos["Débitos"]),
                creditos=valor(campos["Créditos"]),
                saldo_atual=valor(campos["Saldo Atual"]),
                arquivo=leitura.arquivo,
            )
        except ValueError as erro_valor:
            leitura.avisos.append(Aviso(
                arquivo=leitura.arquivo,
                mensagem=f"Linha {numero}: conta {celulas[0]} com valor não reconhecido "
                         f"({erro_valor}); ela não foi lida.",
            ))
            continue
        leitura.contas.append(conta)

    if ordem_colunas is None:
        faltando = ", ".join(COLUNAS)
        leitura.erro = f"Cabeçalho do balancete não encontrado (colunas esperadas: {faltando})."
        return leitura
    if not leitura.contas:
        leitura.erro = "Nenhuma conta encontrada no balancete."
        return leitura

    _marcar_contas_maes(leitura)
    if not leitura.competencia:
        leitura.avisos.append(Aviso(
            arquivo=leitura.arquivo,
            mensagem="Mês de referência não encontrado no balancete.",
        ))
    return leitura


def _marcar_contas_maes(leitura: LeituraBalancete) -> None:
    """Marca as contas-mães e confere se cada uma é a soma das filhas diretas."""
    classificacoes = [c.classificacao for c in leitura.contas]
    for conta in leitura.contas:
        prefixo = conta.classificacao + "."
        filhas = [c for c in leitura.contas
                  if c.classificacao.startswith(prefixo)
                  and "." not in c.classificacao[len(prefixo):]]
        if not any(c.startswith(prefixo) for c in classificacoes):
            continue
        conta.sintetica = True
        soma = sum((f.saldo_atual for f in filhas), Decimal(0))
        if filhas and soma != conta.saldo_atual:
            leitura.avisos.append(Aviso(
                arquivo=leitura.arquivo,
                mensagem=f"ATENÇÃO: no balancete, a conta {conta.codigo} ({conta.descricao}) tem "
                         f"saldo atual {reais(conta.saldo_atual)} mas a soma das contas dela dá {reais(soma)}. "
                         "Alguma conta pode não ter sido lida.",
            ))
