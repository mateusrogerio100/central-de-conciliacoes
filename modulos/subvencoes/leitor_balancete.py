"""Leitura do Balancete exportado do sistema.

Como o arquivo é lido:
- A cada página há uma linha de títulos; dela só se usa a coluna "Saldo Atual".
  Tudo que estiver à direita dessa coluna (colunas de conferência do usuário) é ignorado.
- Uma linha é conta quando tem uma célula de classificação (2.02.06.01.0020).
  Código = primeira célula preenchida à esquerda; Descrição = primeiro texto à direita;
  Saldo Atual = número na coluna "Saldo Atual" da página.
- "Mês Referência:" define o mês; o valor é a primeira célula preenchida à direita do rótulo.
"""

from __future__ import annotations

import re
from pathlib import Path

from modulos.subvencoes import configuracao
from modulos.subvencoes.modelos import Aviso, Balancete, ContaBalancete, ErroArquivo, Gravidade
from modulos.subvencoes.utilitarios import (
    abrir_relatorio_tasy,
    mes_de_valor,
    para_decimal,
    para_inteiro,
    texto_comeca_com,
    texto_igual,
)

_PADRAO_CLASSIFICACAO = re.compile(configuracao.BALANCETE_PADRAO_CLASSIFICACAO)


def _eh_classificacao(valor) -> bool:
    return isinstance(valor, str) and bool(_PADRAO_CLASSIFICACAO.match(valor.strip()))


def _eh_rodape(celulas: dict[int, object]) -> bool:
    primeira = celulas[min(celulas)]
    return texto_comeca_com(primeira, configuracao.RODAPE_IMPRESSO_EM)


def _coluna_do_titulo(celulas: dict[int, object], titulo: str) -> int | None:
    """Coluna mais à esquerda com o título, desde que a linha não seja uma linha de conta
    (um "Saldo Atual" digitado numa coluna de conferência não conta como título)."""
    for coluna in sorted(celulas):
        if texto_igual(celulas[coluna], titulo):
            if any(_eh_classificacao(celulas[c]) for c in celulas if c < coluna):
                return None
            return coluna
    return None


def _localizar_aba(pasta_trabalho):
    """Primeira aba que tem a linha de títulos com "Saldo Atual"."""
    for aba in pasta_trabalho.worksheets:
        for linha in aba.iter_rows(values_only=True):
            if any(texto_igual(v, configuracao.BALANCETE_TITULO_SALDO_ATUAL) for v in linha):
                return aba
    return None


def ler_balancete(caminho) -> Balancete:
    caminho = Path(caminho)
    nome = caminho.name
    pasta_trabalho = abrir_relatorio_tasy(caminho)
    try:
        aba = _localizar_aba(pasta_trabalho)
        if aba is None:
            raise ErroArquivo(
                f"{nome}: não parece ser um balancete "
                f"(título '{configuracao.BALANCETE_TITULO_SALDO_ATUAL}' não encontrado)."
            )
        balancete = _ler_aba(aba, nome)
    finally:
        pasta_trabalho.close()
    if not balancete.contas:
        # Pedido do usuário (09/11/2026): balancete exportado vazio (só o cabeçalho) para tudo, em vez de
        # gerar as planilhas com todas as contas zeradas.
        raise ErroArquivo(
            f"{nome}: o balancete não tem nenhuma conta (só o cabeçalho). "
            "Tire o balancete de novo no Tasy, conferindo se as contas aparecem, e processe outra vez."
        )
    return balancete


def _ler_aba(aba, nome_arquivo: str) -> Balancete:
    balancete = Balancete(arquivo=nome_arquivo, mes_referencia=None)

    def avisar(gravidade, tipo, mensagem, linha=None, conta=""):
        balancete.avisos.append(
            Aviso(gravidade, tipo, mensagem, arquivo=nome_arquivo, aba=aba.title, linha=linha, conta=conta)
        )

    coluna_saldo: int | None = None

    for linha_celulas in aba.iter_rows():
        celulas = {c.column: c.value for c in linha_celulas if c.value is not None and c.value != ""}
        if not celulas:
            continue
        numero_linha = linha_celulas[0].row

        if _eh_rodape(celulas):
            continue

        # Linha de títulos da página: atualiza a coluna "Saldo Atual".
        coluna_titulo = _coluna_do_titulo(celulas, configuracao.BALANCETE_TITULO_SALDO_ATUAL)
        if coluna_titulo is not None:
            coluna_saldo = coluna_titulo
            continue

        # "Mês Referência:" -> primeira célula preenchida à direita.
        coluna_mes = _coluna_do_titulo(celulas, configuracao.BALANCETE_TITULO_MES_REFERENCIA)
        if coluna_mes is not None:
            _ler_mes(balancete, celulas, coluna_mes, numero_linha, avisar)
            continue

        if coluna_saldo is None:
            if any(_eh_classificacao(v) for v in celulas.values()):
                avisar(Gravidade.ERRO, "linha não reconhecida",
                       f"Conta antes da linha de títulos ('{configuracao.BALANCETE_TITULO_SALDO_ATUAL}' "
                       "ainda não encontrado); linha ignorada.", numero_linha)
            continue

        # Só interessa o que está até a coluna "Saldo Atual".
        uteis = {col: v for col, v in celulas.items() if col <= coluna_saldo}
        coluna_classificacao = next((col for col in sorted(uteis) if _eh_classificacao(uteis[col])), None)
        if coluna_classificacao is None:
            continue

        _ler_conta(balancete, uteis, coluna_classificacao, coluna_saldo, numero_linha, avisar)

    if balancete.mes_referencia is None:
        avisar(Gravidade.ATENCAO, "mês não encontrado",
               f"'{configuracao.BALANCETE_TITULO_MES_REFERENCIA}' não encontrado no balancete.")
    return balancete


def _ler_mes(balancete, celulas, coluna_mes, numero_linha, avisar):
    valor = next((celulas[c] for c in sorted(celulas) if c > coluna_mes), None)
    mes = mes_de_valor(valor)
    if mes is None:
        avisar(Gravidade.ATENCAO, "mês não reconhecido",
               f"Não foi possível ler o mês de referência: {valor!r}.", numero_linha)
    elif balancete.mes_referencia is None:
        balancete.mes_referencia = mes
    elif mes != balancete.mes_referencia:
        avisar(Gravidade.ATENCAO, "mês diferente entre páginas",
               f"Página com mês {mes}, diferente do mês {balancete.mes_referencia} "
               "da primeira página. Vale o da primeira página.", numero_linha)


def _ler_conta(balancete, uteis, coluna_classificacao, coluna_saldo, numero_linha, avisar):
    classificacao = uteis[coluna_classificacao].strip()

    # Código = primeira célula preenchida à esquerda da classificação
    # (no arquivo real há uma coluna vazia entre as duas: código em C, classificação em E).
    coluna_codigo = max((col for col in uteis if col < coluna_classificacao), default=None)
    codigo = para_inteiro(uteis.get(coluna_codigo))
    if codigo is None:
        avisar(Gravidade.ERRO, "linha não reconhecida",
               f"Conta {classificacao} sem código numérico à esquerda da classificação; linha ignorada.",
               numero_linha, classificacao)
        return

    descricao = next(
        (uteis[col].strip() for col in sorted(uteis)
         if coluna_classificacao < col < coluna_saldo and isinstance(uteis[col], str)),
        "",
    )

    saldo = para_decimal(uteis.get(coluna_saldo))
    if saldo is None:
        avisar(Gravidade.ERRO, "linha não reconhecida",
               f"Conta {codigo} ({classificacao}) sem número na coluna "
               f"'{configuracao.BALANCETE_TITULO_SALDO_ATUAL}'; linha ignorada.",
               numero_linha, str(codigo))
        return

    if codigo in balancete.contas:
        anterior = balancete.contas[codigo]
        avisar(Gravidade.ATENCAO, "código repetido no balancete",
               f"Código {codigo} aparece de novo (já lido na linha {anterior.linha}); "
               "vale a primeira ocorrência.", numero_linha, str(codigo))
        return

    balancete.contas[codigo] = ContaBalancete(
        codigo=codigo,
        classificacao=classificacao,
        descricao=descricao,
        saldo_atual=saldo,
        linha=numero_linha,
    )
