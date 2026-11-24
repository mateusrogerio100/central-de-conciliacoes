"""Leitura do Razão Convênios exportado do Tasy. Seção 3.1 da especificação.

- Aceita o .xlsx e o ".xls" do Tasy, que na verdade é um texto com as células separadas por tabulação
  (decisão do usuário, 29/10/2026). Os dois viram a mesma lista de linhas e seguem pelo mesmo caminho.

- Cada página repete o cabeçalho; as colunas são achadas pela linha de títulos (Data, Histórico, Lote,
  Débitos, Créditos) da própria página, nunca pela letra.
- Linha de conta "40075 - 4.01.05.01.0001  Nome"; lançamentos até "Total - 40075 - ...".
- Lançamento = linha com data na coluna Data. "Saldo anterior" e a continuação de um histórico que quebrou
  na virada da página (linha sem data e sem valor) não são lançamentos.
- Conferência de leitura: a soma dos lançamentos de cada conta = a linha "Total" dela.
"""

from __future__ import annotations

import io
import zipfile
from datetime import date, datetime
from pathlib import Path

import openpyxl

from modulos.convenios import configuracao as cfg
from modulos.convenios.modelos import ZERO, Aviso, ContaRazao, ErroLeitura, Lancamento, Razao
from modulos.convenios.normalizacao import para_decimal, texto_igual


def abrir_xlsx(caminho: Path):
    """Abre o .xlsx pelo conteúdo (o arquivo pode estar aberto no Excel). ErroLeitura com mensagem clara."""
    caminho = Path(caminho)
    try:
        conteudo = caminho.read_bytes()
    except FileNotFoundError:
        raise ErroLeitura(f"Arquivo não encontrado: {caminho}") from None
    except PermissionError:
        raise ErroLeitura(f"{caminho.name}: o arquivo está bloqueado por outro programa. Feche e tente de novo.") from None
    if conteudo.startswith(cfg.ASSINATURA_XLS_ANTIGO):
        raise ErroLeitura(cfg.MENSAGEM_XLS_ANTIGO.format(nome=caminho.name))
    try:
        return openpyxl.load_workbook(io.BytesIO(conteudo), read_only=True, data_only=True)
    except (zipfile.BadZipFile, KeyError, OSError, ValueError) as erro:
        raise ErroLeitura(f"{caminho.name}: não foi possível abrir como planilha .xlsx ({erro}).") from None


def _linhas_do_texto(nome: str, conteudo: bytes) -> list[tuple]:
    """O ".xls" do Tasy: uma linha por linha do relatório, células separadas por tabulação."""
    for codificacao in cfg.RAZAO_TEXTO_CODIFICACOES:
        try:
            texto = conteudo.decode(codificacao)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ErroLeitura(f"{nome}: não foi possível ler o arquivo como texto.")
    if cfg.RAZAO_TEXTO_SEPARADOR not in texto:
        raise ErroLeitura(f"{nome}: não é uma planilha .xlsx nem o texto exportado pelo Tasy.")
    return [tuple(celula if celula.strip() else None for celula in linha.split(cfg.RAZAO_TEXTO_SEPARADOR))
            for linha in texto.splitlines()]


def _linhas_do_razao(caminho: Path) -> list[tuple]:
    """As linhas da primeira aba do .xlsx ou do texto do Tasy."""
    try:
        conteudo = caminho.read_bytes()
    except FileNotFoundError:
        raise ErroLeitura(f"Arquivo não encontrado: {caminho}") from None
    except PermissionError:
        raise ErroLeitura(f"{caminho.name}: o arquivo está bloqueado por outro programa. Feche e tente de novo.") from None
    if not conteudo.startswith(b"PK") and not conteudo.startswith(cfg.ASSINATURA_XLS_ANTIGO):
        return _linhas_do_texto(caminho.name, conteudo)
    livro = abrir_xlsx(caminho)
    try:
        return [tuple(v) for v in livro.worksheets[0].iter_rows(values_only=True)]
    finally:
        livro.close()


def _data(valor) -> date | None:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        achada = cfg.RE_DATA_TEXTO.match(valor.strip())
        if achada:
            try:
                return date(int(achada.group(3)), int(achada.group(2)), int(achada.group(1)))
            except ValueError:
                return None
    return None


def _colunas_dos_titulos(valores: tuple) -> dict[str, int] | None:
    """Índices das colunas pela linha de títulos; None se a linha não for a de títulos."""
    colunas = {}
    for titulo in cfg.RAZAO_TITULOS:
        indice = next((i for i, v in enumerate(valores) if texto_igual(v, titulo)), None)
        if indice is None:
            return None
        colunas[titulo] = indice
    return colunas


def _celula(valores: tuple, indice: int):
    return valores[indice] if indice < len(valores) else None


def _textos(valores: tuple) -> list[str]:
    return [v.strip() for v in valores if isinstance(v, str) and v.strip()]


def ler_razao(caminho: Path) -> Razao:
    """Lê o razão. Levanta ErroLeitura se o arquivo não for um razão (sem títulos ou sem nenhuma conta)."""
    caminho = Path(caminho)
    razao = Razao(arquivo=caminho.name)
    linhas = _linhas_do_razao(caminho)

    def avisar(numero, mensagem, erro=False):
        razao.avisos.append(Aviso(f"{caminho.name} linha {numero}", mensagem, erro))

    colunas = None
    conta: ContaRazao | None = None
    for numero, valores in enumerate(linhas, start=1):
        valores = tuple(valores)
        textos = _textos(valores)
        if not textos and not any(_data(v) for v in valores):
            continue

        if any(texto_igual(t, cfg.RAZAO_TEXTO_PERIODO) for t in textos):
            datas = [d for d in (_data(v) for v in valores) if d]
            if datas and razao.mes is None:
                razao.ano, razao.mes = datas[0].year, datas[0].month
                if len(datas) > 1 and (datas[-1].year, datas[-1].month) != (razao.ano, razao.mes):
                    avisar(numero, f"O período do razão vai de {datas[0]:%d/%m/%Y} até {datas[-1]:%d/%m/%Y}: "
                                   "mais de um mês. Vale o mês do início.", erro=True)
            continue

        novas = _colunas_dos_titulos(valores)
        if novas:
            colunas = novas
            continue
        if colunas is None:
            continue

        data = _data(_celula(valores, colunas[cfg.RAZAO_TITULO_DATA]))
        historico = _celula(valores, colunas[cfg.RAZAO_TITULO_HISTORICO])
        historico = " ".join(str(historico).split()) if historico is not None else ""

        if data is None:
            achada = next((cfg.RE_CONTA.match(t) for t in textos if cfg.RE_CONTA.match(t)), None)
            total = cfg.RE_TOTAL_CONTA.match(historico)
            if achada and not total:
                conta = ContaRazao(achada.group(1), achada.group(2), " ".join(achada.group(3).split()))
                if any(c.codigo == conta.codigo for c in razao.contas):
                    avisar(numero, f"A conta {conta.codigo} aparece de novo no razão: os lançamentos somam na mesma.")
                    conta = next(c for c in razao.contas if c.codigo == conta.codigo)
                else:
                    razao.contas.append(conta)
            elif total:
                _ler_total(conta, total.group(1), valores, colunas, numero, avisar)
            # "Saldo anterior", continuação de histórico, cabeçalho e rodapé: não são lançamentos
            continue

        if conta is None:
            avisar(numero, f"Lançamento antes de qualquer conta ({historico!r}): ignorado.", erro=True)
            continue
        debito = para_decimal(_celula(valores, colunas[cfg.RAZAO_TITULO_DEBITOS])) or ZERO
        credito = para_decimal(_celula(valores, colunas[cfg.RAZAO_TITULO_CREDITOS])) or ZERO
        lote = _celula(valores, colunas[cfg.RAZAO_TITULO_LOTE])
        conta.lancamentos.append(Lancamento(conta.codigo, data, historico, "" if lote is None else str(lote),
                                            debito, credito, numero))

    if colunas is None:
        raise ErroLeitura(f"{caminho.name}: não parece ser um razão (linha de títulos "
                          f"'{' / '.join(cfg.RAZAO_TITULOS)}' não encontrada).")
    if not razao.contas:
        raise ErroLeitura(f"{caminho.name}: nenhuma conta encontrada no razão.")
    if razao.mes is None:
        razao.avisos.append(Aviso(caminho.name, f"'{cfg.RAZAO_TEXTO_PERIODO}' não encontrado: mês do razão "
                                                "desconhecido.", erro=True))
    for c in razao.contas:
        _conferir_total(c, caminho.name, razao.avisos)
    return razao


def _ler_total(conta, codigo, valores, colunas, numero, avisar):
    if conta is None or conta.codigo != codigo:
        avisar(numero, f"Linha \"Total\" da conta {codigo} fora do lugar: ignorada.", erro=True)
        return
    conta.total_debito = para_decimal(_celula(valores, colunas[cfg.RAZAO_TITULO_DEBITOS])) or ZERO
    conta.total_credito = para_decimal(_celula(valores, colunas[cfg.RAZAO_TITULO_CREDITOS])) or ZERO


def _conferir_total(conta: ContaRazao, arquivo: str, avisos: list[Aviso]):
    origem = f"{arquivo} conta {conta.codigo}"
    if conta.total_credito is None:
        avisos.append(Aviso(origem, "Linha \"Total\" da conta não encontrada: não dá para conferir se a leitura "
                                    "está completa.", erro=True))
        return
    if (conta.soma_debitos, conta.soma_creditos) != (conta.total_debito, conta.total_credito):
        avisos.append(Aviso(origem, f"Soma dos lançamentos lidos (débitos {conta.soma_debitos}, créditos "
                                    f"{conta.soma_creditos}) diferente da linha Total (débitos {conta.total_debito}, "
                                    f"créditos {conta.total_credito}): algum lançamento não foi lido.", erro=True))
