"""
Leitores dos dois relatórios do Tasy da Conciliação Fornecedores.

Os dois saem do Tasy como .xls que na verdade é TEXTO separado por tabulação (Windows-1252):
a pessoa só baixa e escolhe o arquivo, sem abrir e salvar no Excel. Se alguém tiver salvado
como .xlsx (ou .xls de verdade), o arquivo também é aceito.

Balancete (WEXE001):
- 1ª linha: a unidade ("AME - Cidade Delta (Fund. Hospital Exemplo)").
- "Mês Referência:" → o mês ao lado ("set/2026"; no .xlsx, uma data).
- Cabeçalho Código · Classificação · Descrição · Saldo Anterior · Débitos · Créditos · Saldo Atual.
  Nas linhas de conta as células ficam uma coluna à direita do título, então os valores são
  lidos NA ORDEM do cabeçalho (todas as células de uma conta vêm preenchidas).
- Classificação exatamente "2.01.01.01" = total da conta 2111; começando com "2.01.01.01." =
  contas de fornecedor. Outras contas e o cabeçalho/rodapé repetidos são ignorados.
- Validação: soma do Saldo Atual das contas = total da 2111 (senão ATENÇÃO).

Relatório analítico de títulos a pagar (WFIN 563): uma tabela comum, com cabeçalho na 1ª linha
e uma linha por título. Colunas achadas pelo nome: "Pessoa Física/Jurídica" (fornecedor),
"Nr. Doc.", "Nr. Título", "TIpo Título", "Sit.", "Dt. Emissão", "Dt. Vencto. Atu.", "Vl. Saldo" e
"Estabelecimento" (a unidade). O saldo de cada fornecedor é a soma do Vl. Saldo dos seus títulos.
A coluna Observação NUNCA é lida (dados sensíveis).
O relatório antigo "Sintético por Fornecedor" (CorCpa) não é mais aceito: vira erro explicando.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from openpyxl import load_workbook

from modulos.conciliacao_rescisoes.fornecedores.avisos import Aviso
from modulos.conciliacao_rescisoes.fornecedores.modelos import (
    ContaFornecedor,
    FornecedorFinanceiro,
    LeituraBalancete,
    LeituraTitulos,
    TituloPagar,
)

CLASSIFICACAO_2111 = "2.01.01.01"

COLUNAS_BALANCETE = ["Código", "Classificação", "Descrição", "Saldo Anterior", "Débitos", "Créditos",
                     "Saldo Atual"]
ROTULO_MES = "Mês Referência:"

COLUNA_FORNECEDOR = "Pessoa Física/Jurídica"
COLUNA_DOCUMENTO = "Nr. Doc."
COLUNA_TITULO = "Nr. Título"
COLUNA_SALDO = "Vl. Saldo"
COLUNA_TIPO = "Tipo Título"              # no Tasy vem "TIpo Título": comparação sem maiúsculas
COLUNA_SITUACAO = "Sit."
COLUNA_EMISSAO = "Dt. Emissão"
COLUNA_VENCIMENTO = "Dt. Vencto. Atu."
COLUNA_ESTABELECIMENTO = "Estabelecimento"
COLUNA_CNPJ = "CNPJ"                      # opcional: separa as filiais com o mesmo nome
COLUNAS_TITULOS = [COLUNA_FORNECEDOR, COLUNA_DOCUMENTO, COLUNA_TITULO, COLUNA_SALDO]

RELATORIO_BALANCETE = "balancete"
RELATORIO_TITULOS = "titulos"
RELATORIO_TITULOS_SINTETICO = "titulos_sintetico"
NOMES = {
    RELATORIO_BALANCETE: "o Balancete (Tasy 865)",
    RELATORIO_TITULOS: "o Relatório analítico de títulos a pagar (Tasy)",
}
CAMPOS = {
    RELATORIO_BALANCETE: "Balancete",
    RELATORIO_TITULOS: "Títulos a pagar",
}
ERRO_SINTETICO = ("Este é o relatório de títulos a pagar \"Sintético por Fornecedor\". O programa agora usa "
                  "o relatório ANALÍTICO de títulos a pagar (uma linha por título, com Nr. Doc. e Nr. Título).")

_MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
_REGEX_MES_ANO = re.compile(r"^([a-zç]{3})/(\d{4})$", re.IGNORECASE)
_REGEX_DATA = re.compile(r"^(\d{2})/(\d{2})/(\d{4})")
_BYTES_XLSX = b"PK"
_BYTES_XLS_BINARIO = b"\xd0\xcf\x11\xe0"
_CENTAVO = Decimal("0.01")

Linhas = list[list[object]]


class ArquivoIlegivel(Exception):
    pass


# ---------------------------------------------------------------------
# Apoio
# ---------------------------------------------------------------------
def ler_planilha(caminho: Path) -> Linhas:
    """Arquivo do Tasy → linhas de células (textos sem espaços nas pontas).

    .xls de texto (o normal) → todas as células são texto; .xlsx ou .xls de verdade → números e
    datas vêm como número/data. Os leitores aceitam os dois jeitos.
    """
    caminho = Path(caminho)
    try:
        bruto = caminho.read_bytes()
    except OSError as erro:
        raise ArquivoIlegivel(f"Não foi possível abrir o arquivo: {erro.strerror or erro}.") from erro
    if bruto.startswith(_BYTES_XLSX):
        return _ler_xlsx(caminho)
    if bruto.startswith(_BYTES_XLS_BINARIO):
        return _ler_xls_binario(caminho)
    for codificacao in ("utf-8", "cp1252"):
        try:
            texto = bruto.decode(codificacao)
            break
        except UnicodeDecodeError:
            continue
    else:
        texto = bruto.decode("latin-1")
    texto = texto.lstrip("﻿")
    return [[celula.replace("\xa0", " ").strip() for celula in linha.split("\t")]
            for linha in texto.splitlines()]


def _ler_xlsx(caminho: Path) -> Linhas:
    try:
        livro = load_workbook(caminho, read_only=True, data_only=True)
    except Exception as erro:
        raise ArquivoIlegivel(f"Não foi possível abrir a planilha: {erro}") from erro
    try:
        aba = livro.worksheets[0]
        return [[c.strip() if isinstance(c, str) else c for c in linha]
                for linha in aba.iter_rows(values_only=True)]
    finally:
        livro.close()


def _ler_xls_binario(caminho: Path) -> Linhas:
    import xlrd

    try:
        livro = xlrd.open_workbook(str(caminho))
    except Exception as erro:
        raise ArquivoIlegivel(f"Não foi possível abrir a planilha: {erro}") from erro
    aba = livro.sheet_by_index(0)
    linhas: Linhas = []
    for indice in range(aba.nrows):
        linha: list[object] = []
        for celula in aba.row(indice):
            if celula.ctype == xlrd.XL_CELL_DATE:
                linha.append(xlrd.xldate.xldate_as_datetime(celula.value, livro.datemode))
            elif isinstance(celula.value, str):
                linha.append(celula.value.strip())
            else:
                linha.append(celula.value)
        linhas.append(linha)
    return linhas


def _preenchidas(linha: list[object]) -> list[object]:
    return [c for c in linha if c is not None and c != ""]


def _chave_coluna(texto: object) -> str:
    return re.sub(r"\s+", " ", str(texto)).strip().casefold()


def _posicoes_titulos(linha: list[object]) -> dict[str, int] | None:
    """Cabeçalho do relatório analítico → {nome da coluna (minúsculas): posição}; None se não for."""
    posicoes = {_chave_coluna(c): i for i, c in enumerate(linha) if isinstance(c, str) and c}
    if all(_chave_coluna(nome) in posicoes for nome in COLUNAS_TITULOS):
        return posicoes
    return None


def identificar(linhas: Linhas) -> str | None:
    if any(_posicoes_titulos(linha) for linha in linhas[:10]):
        return RELATORIO_TITULOS
    textos = " ".join(str(c) for linha in linhas[:40] for c in linha if isinstance(c, str)).casefold()
    if "corcpa" in textos or "títulos a pagar - sintético" in textos:
        return RELATORIO_TITULOS_SINTETICO
    if "wctb865" in textos or any(_preenchidas(l) == ["Balancete"] for l in linhas[:10]):
        return RELATORIO_BALANCETE
    return None


def _erro_relatorio_errado(esperado: str, encontrado: str | None) -> str | None:
    if encontrado == esperado:
        return None
    if encontrado == RELATORIO_TITULOS_SINTETICO:
        return ERRO_SINTETICO
    if encontrado is None:
        return f"Este arquivo não parece ser {NOMES[esperado]}. Confira se escolheu o relatório certo."
    return (f"Este arquivo é {NOMES[encontrado]}, não {NOMES[esperado]}. "
            f"Escolha-o no campo \"{CAMPOS[encontrado]}\".")


def dinheiro(valor: object) -> Decimal:
    """Número da planilha ou texto "1.234,56" → Decimal com 2 casas. Outro → ValueError."""
    if isinstance(valor, bool) or valor is None:
        raise ValueError(f"valor inválido: {valor!r}")
    if isinstance(valor, (int, float)):
        return Decimal(str(valor)).quantize(_CENTAVO)
    if isinstance(valor, str):
        texto = valor.strip().replace(".", "").replace(",", ".")
        try:
            return Decimal(texto).quantize(_CENTAVO)
        except InvalidOperation as erro:
            raise ValueError(f"valor inválido: {valor!r}") from erro
    raise ValueError(f"valor inválido: {valor!r}")


def _identificador(valor: object) -> str:
    """Nr. Doc. / Nr. Título → texto ("484025"); 484025.0 da planilha vira "484025"; vazio → ""."""
    if valor is None or isinstance(valor, bool):
        return ""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


def _data(valor: object) -> date | None:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        achado = _REGEX_DATA.match(valor.strip())
        if achado:
            dia, mes, ano = (int(p) for p in achado.groups())
            try:
                return date(ano, mes, dia)
            except ValueError:
                return None
    return None


def _mes(valor: object) -> date | None:
    """"set/2026" (texto) ou uma data → dia 1 do mês."""
    if isinstance(valor, (datetime, date)):
        return date(valor.year, valor.month, 1)
    if isinstance(valor, str):
        achado = _REGEX_MES_ANO.match(valor.strip())
        if achado and achado.group(1).lower() in _MESES:
            return date(int(achado.group(2)), _MESES.index(achado.group(1).lower()) + 1, 1)
        dia = _data(valor)
        if dia:
            return date(dia.year, dia.month, 1)
    return None


def _eh_rodape(celulas: list[object]) -> bool:
    return any(isinstance(c, str) and c.startswith("Impresso em") for c in celulas)


def _juntar_espacos(texto: object) -> str:
    return re.sub(r"\s+", " ", str(texto)).strip()


def reais(numero: Decimal | None) -> str:
    if numero is None:
        return "—"
    texto = f"{numero:,.2f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


def nome_curto_unidade(unidade: str) -> str:
    """"AME - Cidade Delta (Fund. Hospital Exemplo ...)" → "AME - Cidade Delta"."""
    return re.sub(r"\s+", " ", unidade.split("(")[0]).strip()


_PALAVRAS_FORA_DA_UNIDADE = frozenset({"ame", "de", "da", "do", "dos", "das", "e"})


def palavras_da_unidade(unidade: str) -> frozenset[str]:
    """"Ame - Cidade Epsilon ( Fund. ... )" → {"sao", "joao"} (sem acento, maiúsculas, "AME" e "de/da/do")."""
    sem_acento = unicodedata.normalize("NFKD", nome_curto_unidade(unidade)).encode("ascii", "ignore").decode()
    return frozenset(p for p in re.findall(r"[a-z0-9]+", sem_acento.casefold()) if p not in _PALAVRAS_FORA_DA_UNIDADE)


def mesma_unidade_pelo_nome(unidade_a: str, unidade_b: str) -> bool:
    """Mesma unidade se as palavras de um nome estão todas no outro: cada relatório do Tasy escreve o nome de um
    jeito ("Ame - Cidade Epsilon" no balancete, "AME - Cidade Epsilon" no repasse e no financeiro)."""
    a, b = palavras_da_unidade(unidade_a), palavras_da_unidade(unidade_b)
    if not a or not b:
        return a == b
    return a <= b or b <= a


# ---------------------------------------------------------------------
# Balancete
# ---------------------------------------------------------------------
def ler_balancete(caminho: Path) -> LeituraBalancete:
    caminho = Path(caminho)
    leitura = LeituraBalancete(arquivo=caminho.name)
    try:
        linhas = ler_planilha(caminho)
    except ArquivoIlegivel as erro:
        leitura.erro = str(erro)
        return leitura
    erro = _erro_relatorio_errado(RELATORIO_BALANCETE, identificar(linhas))
    if erro:
        leitura.erro = erro
        return leitura

    ordem: list[str] | None = None
    anterior: list[object] = []
    for numero, linha in enumerate(linhas, start=1):
        celulas = _preenchidas(linha)
        if not celulas:
            continue
        if not leitura.unidade and celulas == ["Balancete"] and anterior and isinstance(anterior[0], str):
            leitura.unidade = _juntar_espacos(anterior[0])
        if leitura.mes is None and ROTULO_MES in celulas:
            depois = celulas[celulas.index(ROTULO_MES) + 1:]
            if depois:
                leitura.mes = _mes(depois[0])
        anterior = celulas

        if all(c in celulas for c in COLUNAS_BALANCETE):
            ordem = [c for c in celulas if isinstance(c, str)]
            continue
        if ordem is None or _eh_rodape(celulas) or len(celulas) != len(ordem):
            continue
        campos = dict(zip(ordem, celulas))
        classificacao = str(campos.get("Classificação", ""))
        if classificacao != CLASSIFICACAO_2111 and not classificacao.startswith(CLASSIFICACAO_2111 + "."):
            continue                     # outra conta do balancete
        try:
            conta = ContaFornecedor(
                codigo=_identificador(campos["Código"]),
                classificacao=classificacao,
                descricao=_juntar_espacos(campos["Descrição"]),
                saldo_anterior=dinheiro(campos["Saldo Anterior"]),
                debitos=dinheiro(campos["Débitos"]),
                creditos=dinheiro(campos["Créditos"]),
                saldo_atual=dinheiro(campos["Saldo Atual"]),
            )
        except ValueError as erro_valor:
            leitura.avisos.append(Aviso(
                arquivo=leitura.arquivo,
                mensagem=f"Linha {numero}: conta {campos.get('Código')} com valor não reconhecido "
                         f"({erro_valor}); ela não foi lida.",
            ))
            continue
        if classificacao == CLASSIFICACAO_2111:
            leitura.total = conta
        else:
            leitura.contas.append(conta)

    if ordem is None:
        leitura.erro = ("Cabeçalho do balancete não encontrado (colunas esperadas: "
                        + ", ".join(COLUNAS_BALANCETE) + ").")
        return leitura
    if leitura.total is None:
        leitura.erro = ("O balancete não traz a conta 2111 – Fornecedores no País (classificação "
                        "2.01.01.01). Confira se escolheu o balancete certo.")
        return leitura

    soma = sum((c.saldo_atual for c in leitura.contas), Decimal(0))
    if soma != leitura.total.saldo_atual:
        leitura.avisos.append(Aviso(
            arquivo=leitura.arquivo,
            mensagem=f"ATENÇÃO: a soma das contas de fornecedor ({reais(soma)}) não bate com o total "
                     f"da conta 2111 ({reais(leitura.total.saldo_atual)}). A leitura pode estar "
                     "incompleta.",
        ))
    if leitura.mes is None:
        leitura.avisos.append(Aviso(arquivo=leitura.arquivo,
                                    mensagem="Mês Referência não encontrado no balancete."))
    return leitura


# ---------------------------------------------------------------------
# Relatório analítico de títulos a pagar
# ---------------------------------------------------------------------
def ler_titulos(caminho: Path) -> LeituraTitulos:
    caminho = Path(caminho)
    leitura = LeituraTitulos(arquivo=caminho.name)
    try:
        linhas = ler_planilha(caminho)
    except ArquivoIlegivel as erro:
        leitura.erro = str(erro)
        return leitura
    erro = _erro_relatorio_errado(RELATORIO_TITULOS, identificar(linhas))
    if erro:
        leitura.erro = erro
        return leitura

    posicoes: dict[str, int] | None = None
    por_nome: dict[tuple[str, str], FornecedorFinanceiro] = {}
    unidades: Counter[str] = Counter()

    def celula(linha: list[object], coluna: str) -> object:
        indice = posicoes.get(_chave_coluna(coluna)) if posicoes else None
        return linha[indice] if indice is not None and indice < len(linha) else None

    for numero, linha in enumerate(linhas, start=1):
        if not _preenchidas(linha):
            continue
        cabecalho = _posicoes_titulos(linha)
        if cabecalho:                    # cabeçalho (o primeiro ou um repetido)
            posicoes = cabecalho
            continue
        if posicoes is None:
            continue
        nome = _juntar_espacos(celula(linha, COLUNA_FORNECEDOR) or "")
        try:
            saldo = dinheiro(celula(linha, COLUNA_SALDO))
        except ValueError as erro_valor:
            leitura.avisos.append(Aviso(
                arquivo=leitura.arquivo,
                mensagem=f"Linha {numero}: título {_identificador(celula(linha, COLUNA_TITULO)) or '?'} "
                         f"de \"{nome or '?'}\" com saldo não reconhecido ({erro_valor}); ele não foi lido.",
            ))
            continue
        if not nome:
            leitura.avisos.append(Aviso(
                arquivo=leitura.arquivo,
                mensagem=f"Linha {numero}: título {_identificador(celula(linha, COLUNA_TITULO)) or '?'} "
                         f"(R$ {reais(saldo)}) sem fornecedor; ele não foi lido.",
            ))
            continue
        titulo = TituloPagar(
            documento=_identificador(celula(linha, COLUNA_DOCUMENTO)),
            numero=_identificador(celula(linha, COLUNA_TITULO)),
            tipo=_juntar_espacos(celula(linha, COLUNA_TIPO) or ""),
            situacao=_juntar_espacos(celula(linha, COLUNA_SITUACAO) or ""),
            emissao=_data(celula(linha, COLUNA_EMISSAO)),
            vencimento=_data(celula(linha, COLUNA_VENCIMENTO)),
            saldo=saldo,
        )
        # mesmo nome e mesmo CNPJ = um fornecedor; filiais (CNPJ diferente) têm contas separadas no balancete
        # (o mesmo nome, só com outra caixa, na filial 0001 e na 0004: visto em set/2026 na Hospital Exemplo)
        cnpj = _juntar_espacos(celula(linha, COLUNA_CNPJ) or "")
        chave = (nome.casefold(), cnpj)
        if chave not in por_nome:
            por_nome[chave] = FornecedorFinanceiro(nome=nome, saldo=Decimal(0), cnpj=cnpj)
        fornecedor = por_nome[chave]
        fornecedor.titulos.append(titulo)
        fornecedor.saldo += saldo
        leitura.quantidade_titulos += 1
        estabelecimento = _juntar_espacos(celula(linha, COLUNA_ESTABELECIMENTO) or "")
        if estabelecimento:
            unidades[estabelecimento] += 1

    if posicoes is None:
        leitura.erro = ("Cabeçalho do relatório de títulos a pagar não encontrado (colunas esperadas: "
                        + ", ".join(COLUNAS_TITULOS) + ").")
        return leitura
    leitura.fornecedores = list(por_nome.values())
    if not leitura.fornecedores:
        leitura.erro = "Nenhum título encontrado no relatório de títulos a pagar."
        return leitura

    if unidades:
        leitura.unidade = unidades.most_common(1)[0][0]
        curtos = sorted({nome_curto_unidade(u) for u in unidades}, key=str.casefold)
        if len({c.casefold() for c in curtos}) > 1:
            leitura.avisos.append(Aviso(
                arquivo=leitura.arquivo,
                mensagem="ATENÇÃO: o relatório de títulos a pagar tem títulos de mais de um estabelecimento ("
                         + "; ".join(curtos) + "). Todos foram somados.",
            ))
    return leitura
