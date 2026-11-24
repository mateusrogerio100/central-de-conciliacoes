"""Tabela conta → seção (secoes_contas.csv). Regra R5a.

- Fica na pasta `config` ao lado da Planilha HM escolhida (o módulo cria a pasta, se faltar). O usuário pode abrir
  e corrigir. Tem nomes de pessoas em algumas contas: fica fora do git e do .exe; no git, só o modelo vazio de
  `modelos_configuracao\\`.
- Na primeira vez (sem o arquivo), é montada sozinha: para cada seção da aba do ano, as contas de débito, no
  Movimento do mês, dos eventos que já estão nela. O lançamento do Movimento é ligado ao evento pelo
  "Evento NNNN" do histórico e pelo código do histórico (o mesmo da linha "Total Evento" do relatório Eventos,
  seção 2.2; o código 0 não identifica evento). Conta que cair em mais de uma seção não é decidida: vira pergunta.
- Linha com problema no arquivo: só ela é pulada, com aviso. Coluna faltando: o arquivo inteiro vira erro.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from modulos.planilha_hm import configuracao as cfg
from modulos.planilha_hm.modelos import (
    Aviso,
    ContaContabil,
    ErroLeitura,
    Eventos,
    ItemTabela,
    Movimento,
    Pergunta,
    Planilha,
    TabelaSecoes,
)


def pasta_config(planilha: Path) -> Path:
    """A pasta `config` ao lado da Planilha HM."""
    return Path(planilha).parent / cfg.PASTA_CONFIG


def _texto(caminho: Path) -> str:
    try:
        conteudo = caminho.read_bytes()
    except OSError as erro:
        raise ErroLeitura(f"Não foi possível abrir {caminho.name}: {erro}") from None
    for codificacao in cfg.CSV_CODIFICACOES:
        try:
            return conteudo.decode(codificacao)
        except UnicodeDecodeError:
            continue
    raise ErroLeitura(f"{caminho.name}: codificação não reconhecida.")


def ler_tabela(caminho: Path) -> TabelaSecoes | None:
    """O secoes_contas.csv; None se o arquivo não existir (a tabela será montada)."""
    caminho = Path(caminho)
    if not caminho.is_file():
        return None
    tabela = TabelaSecoes(str(caminho))
    leitor = csv.reader(io.StringIO(_texto(caminho), newline=""), delimiter=cfg.CSV_SEPARADOR)
    try:
        titulos = [t.strip() for t in next(leitor)]
    except StopIteration:
        raise ErroLeitura(f"{caminho.name} está vazio (falta a linha de títulos).") from None
    faltando = [c for c in cfg.SECOES_COLUNAS if c not in titulos]
    if faltando:
        raise ErroLeitura(f"{caminho.name}: colunas não encontradas: {', '.join(faltando)}.")
    posicao = {c: titulos.index(c) for c in cfg.SECOES_COLUNAS}
    for valores in leitor:
        if not any(v.strip() for v in valores):
            continue
        campos = {c: valores[i].strip() if i < len(valores) else "" for c, i in posicao.items()}
        classificacao, secao = campos[cfg.SECOES_TITULO_CLASSIFICACAO], campos[cfg.SECOES_TITULO_SECAO]
        origem = f"{caminho.name} linha {leitor.line_num}"
        if not classificacao or not secao:
            tabela.avisos.append(Aviso(origem, f"{cfg.SECOES_TITULO_CLASSIFICACAO} ou {cfg.SECOES_TITULO_SECAO} "
                                               "vazio: linha pulada."))
            continue
        if classificacao in tabela.itens and tabela.itens[classificacao].secao != secao:
            tabela.avisos.append(Aviso(origem, f"A conta {classificacao} já está na seção "
                                               f"\"{tabela.itens[classificacao].secao}\": linha pulada.", erro=True))
            continue
        tabela.itens[classificacao] = ItemTabela(classificacao, campos[cfg.SECOES_TITULO_CONTA], secao)
    return tabela


def gravar_tabela(tabela: TabelaSecoes, caminho: Path) -> None:
    """Grava a tabela (cria a pasta config, se faltar). OSError se não der para gravar."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8-sig", newline="") as arquivo:
        escritor = csv.writer(arquivo, delimiter=cfg.CSV_SEPARADOR)
        escritor.writerow(cfg.SECOES_COLUNAS)
        for item in sorted(tabela.itens.values(), key=lambda i: (i.secao, i.classificacao)):
            escritor.writerow([item.classificacao, item.conta, item.secao])


def montar_tabela(planilha: Planilha, eventos: Eventos, movimento: Movimento,
                  caminho: Path) -> tuple[TabelaSecoes, list[Pergunta]]:
    """R5a, item 1: a tabela montada a partir das seções da aba do ano e do Movimento do mês. As contas que
    aparecem em mais de uma seção ficam fora da tabela e voltam como perguntas."""
    secao_do_evento = {e.numero: s.nome for s in planilha.secoes for e in s.eventos}
    eventos_do_codigo: dict[str, set[int]] = {}
    for evento in eventos.eventos:
        if evento.codigo_historico not in cfg.CODIGOS_HISTORICO_SEM_EVENTO:
            eventos_do_codigo.setdefault(evento.codigo_historico, set()).add(evento.numero)

    contas: dict[str, ContaContabil] = {}
    secoes_da_conta: dict[str, dict[str, set[int]]] = {}    # classificação → seção → eventos
    for linha in movimento.linhas:
        if not linha.tem_debito or not linha.classificacao_debito:
            continue
        ligados = set(eventos_do_codigo.get(linha.codigo_historico, ()))
        if linha.evento is not None:
            ligados.add(linha.evento)
        for numero in ligados:
            if numero in secao_do_evento:
                contas.setdefault(linha.classificacao_debito, linha.conta)
                secoes_da_conta.setdefault(linha.classificacao_debito, {}).setdefault(
                    secao_do_evento[numero], set()).add(numero)

    tabela = TabelaSecoes(str(caminho), existia=False)
    perguntas = []
    for classificacao, secoes in secoes_da_conta.items():
        conta = contas[classificacao]
        if len(secoes) == 1:
            tabela.itens[classificacao] = ItemTabela(classificacao, conta.nome, next(iter(secoes)))
        else:
            perguntas.append(Pergunta(
                classificacao,
                f"A conta {classificacao} {conta.nome} aparece em mais de uma seção da planilha "
                f"({', '.join(secoes)}). Em qual seção ela fica na tabela conta → seção?",
                [conta], sorted(set().union(*secoes.values())), list(secoes), permite_nova=False))
    return tabela, perguntas
