"""Arquivos de configuração (.csv com ;) -> Configuracao. Seção 3.3 da especificação.

- regras.csv é obrigatório. destinatarios_extras.csv e redirecionamentos.csv foram aposentados em
  23/10/2026 (os destinatários vêm dos códigos do Check list): se ainda estiverem na pasta, só avisa.
- Coluna faltando = o arquivo inteiro vira erro. Linha com problema (aba desconhecida, linha que
  não é número, expressão inválida...) = só aquela linha é pulada, com aviso: as outras regras
  continuam valendo.
- As expressões (Busca_Fornecedor, Busca_Descricao, Excluir) são comparadas com o texto
  normalizado (M2), sem diferença entre maiúsculas e minúsculas. Centro_Custo (opcional) é comparada
  com o nome normalizado do centro de custo do lançamento.
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

from modulos.checklist_contratos import configuracao as cfg
from modulos.checklist_contratos.modelos import Aviso, Configuracao, ErroLeitura, Regra


class _LinhaInvalida(Exception):
    pass


def _ler_csv(caminho: Path, colunas: tuple[str, ...], opcionais: tuple[str, ...] = ()
             ) -> list[tuple[int, dict[str, str]]]:
    """Linhas do .csv como {coluna: texto}, com o número da linha. ErroLeitura se não der.

    Coluna opcional que não existe no arquivo vem vazia (arquivos de antes dela continuam valendo).
    """
    try:
        conteudo = caminho.read_bytes()
    except OSError as erro:
        raise ErroLeitura(f"Não foi possível abrir {caminho.name}: {erro}") from None
    for codificacao in cfg.CONFIG_CODIFICACOES:
        try:
            texto = conteudo.decode(codificacao)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ErroLeitura(f"{caminho.name}: codificação não reconhecida.")

    leitor = csv.reader(io.StringIO(texto, newline=""), delimiter=cfg.CONFIG_SEPARADOR)
    try:
        titulos = [t.strip() for t in next(leitor)]
    except StopIteration:
        raise ErroLeitura(f"{caminho.name} está vazio (falta a linha de títulos).") from None
    faltando = [c for c in colunas if c not in titulos]
    if faltando:
        raise ErroLeitura(f"{caminho.name}: colunas não encontradas: " + ", ".join(faltando) + ".")
    posicao = {c: titulos.index(c) for c in colunas + opcionais if c in titulos}
    linhas = []
    for valores in leitor:
        if not any(v.strip() for v in valores):
            continue
        linhas.append((leitor.line_num, {c: (valores[posicao[c]].strip()
                                             if c in posicao and posicao[c] < len(valores) else "")
                                         for c in colunas + opcionais}))
    return linhas


def _expressao(texto: str, coluna: str) -> re.Pattern:
    try:
        return re.compile(texto, re.IGNORECASE)
    except re.error as erro:
        raise _LinhaInvalida(f"{coluna} \"{texto}\" não é uma expressão válida ({erro})") from None


def _regra(numero: int, campos: dict[str, str]) -> Regra:
    aba = campos["Aba"].upper()
    if aba not in cfg.ESTABELECIMENTOS:
        raise _LinhaInvalida(f"Aba \"{campos['Aba']}\" (use SC ou CMD)")
    if not campos["Linha"].isdigit():
        raise _LinhaInvalida(f"Linha \"{campos['Linha']}\" não é um número")
    tipo = campos["Tipo"].lower()
    if tipo not in cfg.TIPOS:
        raise _LinhaInvalida(f"Tipo \"{campos['Tipo']}\" (use {', '.join(cfg.TIPOS)})")
    selecao = campos["Selecao"].lower()
    if selecao not in cfg.SELECOES:
        raise _LinhaInvalida(f"Selecao \"{campos['Selecao']}\" (use vazio, maior ou menor)")
    if not campos["Busca_Fornecedor"] and tipo != cfg.TIPO_IGNORAR:
        raise _LinhaInvalida("Busca_Fornecedor vazia")
    return Regra(
        aba=aba,
        linha=int(campos["Linha"]),
        fornecedor_planilha=campos["Fornecedor_Planilha"],
        descricao_planilha=campos["Descricao_Planilha"],
        contas=tuple(c for c in cfg.RE_SEPARADOR_CONTAS.split(campos["Contas"]) if c),
        busca_fornecedor=_expressao(campos["Busca_Fornecedor"], "Busca_Fornecedor"),
        busca_descricao=(_expressao(campos["Busca_Descricao"], "Busca_Descricao")
                         if campos["Busca_Descricao"] else None),
        excluir=_expressao(campos["Excluir"], "Excluir") if campos["Excluir"] else None,
        centro_custo=(_expressao(campos["Centro_Custo"], "Centro_Custo")
                      if campos["Centro_Custo"] else None),
        selecao=selecao,
        tipo=tipo,
        obs=campos["Obs"],
        linha_arquivo=numero,
    )


def ler_configuracao(pasta: Path) -> Configuracao:
    """Lê o regras.csv da pasta de configuração. ErroLeitura se o regras.csv não puder ser lido."""
    pasta = Path(pasta)
    configuracao = Configuracao()
    avisos = configuracao.avisos

    arquivo = pasta / cfg.ARQUIVO_REGRAS
    if not arquivo.is_file():
        raise ErroLeitura(f"A pasta de configuração não tem o {cfg.ARQUIVO_REGRAS}.")
    for numero, campos in _ler_csv(arquivo, cfg.REGRAS_COLUNAS, cfg.REGRAS_COLUNAS_OPCIONAIS):
        try:
            configuracao.regras.append(_regra(numero, campos))
        except _LinhaInvalida as erro:
            avisos.append(Aviso(f"{cfg.ARQUIVO_REGRAS} linha {numero}", f"{erro}: regra pulada."))

    for nome in cfg.ARQUIVOS_APOSENTADOS:
        if (pasta / nome).is_file():
            avisos.append(Aviso(nome, "Este arquivo não é mais usado: os destinatários dos e-mails vêm dos "
                                      "números da coluna Responsável e da aba Emails do Check list. "
                                      "Pode apagá-lo da pasta de configuração."))
    return configuracao
