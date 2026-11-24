"""
Leitura do "Relatório de Serviços Tomados" da Prefeitura de Cidade Epsilon.

- O site entrega uma planilha do Excel de verdade (.xls antigo): lida com xlrd.
  Se alguém salvar como .xlsx, também funciona (openpyxl).
- Antes da tabela vêm o título, o nome do tomador e "Inscrição Municipal: 35882".
- A tabela começa na linha cujo cabeçalho tem as colunas obrigatórias.
- Colunas localizadas pelo NOME do cabeçalho.
- Números e valores chegam como número da planilha (ou texto "1.234,56"): viram Decimal.
- "Situação NF" = Cancelada marca a linha como cancelada (regra no comparador).
- Nunca levanta exceção: problema no arquivo vira `erro`, problema numa linha vira aviso.
  Toda linha da tabela é mantida (mesmo com problema), para nada sumir do relatório.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path

from modulos.conferencia_iss.leitor_prefeitura import (
    MESES,
    LeituraPrefeitura,
    _aviso,
    _chave_coluna,
    _erro_pdf,
    _limpar,
    ler_relatorio_prefeitura,
)
from modulos.conferencia_iss.modelos import LinhaPrefeitura
from modulos.conferencia_iss.normalizar import normalizar_documento, normalizar_numero, valor_prefeitura

NOME_RELATORIO = "Relatório de Serviços Tomados"

# Nomes das colunas na prefeitura de Cidade Epsilon
COL_COMPETENCIA = "Competência"
COL_NUMERO = "Nº Nota"
COL_ATIVIDADE = "Atividade"
COL_SITUACAO = "Situação NF"
COL_DOCUMENTO = "CNPJ/CPF"
COL_PRESTADOR = "Razão Social / Nome"
COL_VALOR = "Vlr. Nota"
COL_DEDUCOES = "Vlr. Deduções"
COL_BASE = "Base Cálculo"
COL_ALIQUOTA = "Alíquota"
COL_INCIDENCIA_FORA = "Incidência Fora"
COL_RETIDO = "Retido"
COL_IMPOSTO = "Imposto"
COL_DATA_EMISSAO = "Data Emissão"
COL_CHAVE = "Chave Acesso"

COLUNAS_OBRIGATORIAS = (COL_DOCUMENTO, COL_NUMERO, COL_VALOR)
COLUNAS_OPCIONAIS = (
    COL_COMPETENCIA, COL_ATIVIDADE, COL_SITUACAO, COL_PRESTADOR, COL_DEDUCOES, COL_BASE,
    COL_ALIQUOTA, COL_INCIDENCIA_FORA, COL_RETIDO, COL_IMPOSTO, COL_DATA_EMISSAO, COL_CHAVE,
)

SITUACAO_NORMAL = "normal"
NOMES_MESES = {numero: nome for nome, numero in MESES.items()}
NOMES_MESES[3] = "março"

_REGEX_INSCRICAO = re.compile(r"Inscri[çc][ãa]o\s*Municipal\s*:\s*([\w.\-/]+)", re.IGNORECASE)
_REGEX_COMPETENCIA = re.compile(r"^(\d{1,2})\s*/\s*(\d{4})$")


# ---------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------
def ler_relatorio_cidade_epsilon(caminho: Path | str) -> LeituraPrefeitura:
    """Lê o relatório de Cidade Epsilon. Nunca levanta exceção: problemas vão para erro/avisos."""
    caminho = Path(caminho)
    leitura = LeituraPrefeitura(caminho=caminho)

    try:
        conteudo = caminho.read_bytes()
    except OSError as erro:
        leitura.erro = f"Não foi possível abrir o arquivo: {erro.strerror or erro}"
        return leitura

    if not conteudo.strip():
        leitura.erro = "Arquivo vazio."
        return leitura

    try:
        if conteudo.startswith(b"\xd0\xcf\x11\xe0"):
            planilhas = _ler_xls(conteudo)
        elif conteudo.startswith(b"PK\x03\x04"):
            planilhas = _ler_xlsx(conteudo)
        elif conteudo.lstrip().startswith(b"%PDF"):
            leitura.erro = _erro_pdf(caminho, NOME_RELATORIO)
            return leitura
        else:
            from modulos.conferencia_iss.leitor_prefeitura_fr import (  # evita import circular
                ERRO_E_DE_CIDADE_ALFA,
                eh_relatorio_de_cidade_alfa,
            )
            if eh_relatorio_de_cidade_alfa(caminho):
                leitura.erro = ERRO_E_DE_CIDADE_ALFA
            elif _eh_relatorio_de_cidade_beta(caminho):
                leitura.erro = (
                    "Este é o Relatório de Serviços Contratados de Cidade Beta. "
                    "Para conferi-lo, use a aba Cidade Beta da Conferência ISS."
                )
            else:
                leitura.erro = (
                    f"O arquivo não é uma planilha do Excel. Confira se é o {NOME_RELATORIO} "
                    "baixado do site da Prefeitura de Cidade Epsilon."
                )
            return leitura
    except Exception as erro:  # planilha corrompida ou protegida
        leitura.erro = f"Não foi possível ler a planilha: {erro}"
        return leitura

    _ler_tabela(planilhas, leitura)
    if leitura.erro:
        leitura.linhas.clear()
        from modulos.conferencia_iss.leitor_prefeitura_cp import (  # evita import circular
            ERRO_E_DE_CIDADE_GAMA,
            eh_relatorio_de_cidade_gama,
        )
        if eh_relatorio_de_cidade_gama(caminho):
            leitura.erro = ERRO_E_DE_CIDADE_GAMA
    return leitura


def _eh_relatorio_de_cidade_beta(caminho: Path) -> bool:
    """O arquivo escolhido é, na verdade, o relatório de Cidade Beta?"""
    leitura = ler_relatorio_prefeitura(caminho)
    return leitura.erro is None and bool(leitura.linhas)


def _ler_xls(conteudo: bytes) -> list[list[list]]:
    """Todas as abas do .xls como listas de linhas (datas viram date)."""
    import xlrd

    livro = xlrd.open_workbook(file_contents=conteudo)
    planilhas = []
    for aba in livro.sheets():
        linhas = []
        for numero in range(aba.nrows):
            linha = []
            for celula in aba.row(numero):
                if celula.ctype == xlrd.XL_CELL_DATE:
                    try:
                        linha.append(xlrd.xldate_as_datetime(celula.value, livro.datemode).date())
                    except Exception:
                        linha.append(celula.value)
                elif celula.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                    linha.append("")
                else:
                    linha.append(celula.value)
            linhas.append(linha)
        planilhas.append(linhas)
    return planilhas


def _ler_xlsx(conteudo: bytes) -> list[list[list]]:
    import warnings

    from openpyxl import load_workbook

    with warnings.catch_warnings():
        # O .xlsx de Cidade Gama vem sem "estilo padrão"; o openpyxl avisa, mas lê normalmente.
        warnings.simplefilter("ignore", UserWarning)
        livro = load_workbook(BytesIO(conteudo), read_only=True, data_only=True)
    try:
        return [
            [["" if v is None else v for v in linha] for linha in aba.iter_rows(values_only=True)]
            for aba in livro.worksheets
        ]
    finally:
        livro.close()


# ---------------------------------------------------------------------
# Conversões de célula
# ---------------------------------------------------------------------
def _texto(valor) -> str:
    """Célula como texto: 634.0 → "634"; datas → "01/09/2026"."""
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "Sim" if valor else "Não"
    if isinstance(valor, float):
        return str(int(valor)) if valor.is_integer() else _limpar(repr(valor))
    if isinstance(valor, datetime):
        valor = valor.date()
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    return _limpar(str(valor))


def _valor(celula) -> Decimal | None:
    """Número da planilha ou texto "1.234,56" → Decimal com 2 casas. Inválido → ValueError."""
    if celula is None or celula == "":
        return None
    if isinstance(celula, bool):
        raise ValueError(f"Valor inválido: {celula!r}")
    if isinstance(celula, (int, float)):
        try:
            # repr dá o número "curto" (189.1 e não 189.0999...)
            return Decimal(repr(celula)).quantize(Decimal("0.01"))
        except InvalidOperation as erro:
            raise ValueError(f"Valor inválido: {celula!r}") from erro
    return valor_prefeitura(str(celula))


def _aliquota(celula) -> str:
    """2.01 → "2,01" (como texto, igual ao relatório de Cidade Beta)."""
    if isinstance(celula, (int, float)) and not isinstance(celula, bool):
        return f"{Decimal(repr(celula)).quantize(Decimal('0.01'))}".replace(".", ",")
    return _texto(celula)


# ---------------------------------------------------------------------
# Tabela
# ---------------------------------------------------------------------
def _ler_tabela(planilhas: list[list[list]], leitura: LeituraPrefeitura) -> None:
    obrigatorias = {_chave_coluna(c) for c in COLUNAS_OBRIGATORIAS}

    # A tabela certa começa na primeira linha que tem as colunas obrigatórias.
    encontrado = None
    for linhas in planilhas:
        for posicao, linha in enumerate(linhas):
            if obrigatorias <= {_chave_coluna(_texto(c)) for c in linha}:
                encontrado = (linhas, posicao)
                break
        if encontrado:
            break

    if encontrado is None:
        leitura.erro = (
            "Coluna(s) obrigatória(s) não encontrada(s): " + ", ".join(COLUNAS_OBRIGATORIAS)
            + f". Confira se é o {NOME_RELATORIO} da Prefeitura de Cidade Epsilon."
        )
        return

    linhas, posicao_cabecalho = encontrado
    _ler_inscricao(linhas[:posicao_cabecalho], leitura)

    cabecalho = [_texto(c) for c in linhas[posicao_cabecalho]]
    indices: dict[str, int] = {}
    for posicao, nome in enumerate(cabecalho):
        if nome:
            indices.setdefault(_chave_coluna(nome), posicao)
    posicoes = {
        coluna: indices.get(_chave_coluna(coluna))
        for coluna in COLUNAS_OBRIGATORIAS + COLUNAS_OPCIONAIS
    }
    if posicoes[COL_SITUACAO] is None:
        leitura.avisos.append(_aviso(
            leitura, f"Coluna {COL_SITUACAO} não encontrada: nenhuma nota foi tratada como "
                     "cancelada na prefeitura.",
        ))

    numero_linha = 0
    for celulas in linhas[posicao_cabecalho + 1:]:
        if not any(_texto(c) for c in celulas):
            continue                       # linha em branco não é nota
        numero_linha += 1
        leitura.linhas.append(_montar_linha(celulas, posicoes, numero_linha, leitura))

    _ler_competencia(leitura)


def _ler_inscricao(linhas_antes: list[list], leitura: LeituraPrefeitura) -> None:
    for linha in linhas_antes:
        for celula in linha:
            encontrado = _REGEX_INSCRICAO.search(_texto(celula))
            if encontrado:
                leitura.inscricao_municipal = encontrado.group(1)
                return
    leitura.avisos.append(_aviso(
        leitura, "Inscrição municipal não encontrada no cabeçalho do relatório da prefeitura."
    ))


def _ler_competencia(leitura: LeituraPrefeitura) -> None:
    """A competência vem em cada linha ("09/2026"); vale a que mais aparece."""
    contagem = Counter()
    for linha in leitura.linhas:
        encontrado = _REGEX_COMPETENCIA.match(linha.competencia)
        if encontrado and 1 <= int(encontrado.group(1)) <= 12:
            contagem[(encontrado.group(2), int(encontrado.group(1)))] += 1
    if not contagem:
        leitura.avisos.append(_aviso(
            leitura, "Competência não encontrada no relatório da prefeitura."
        ))
        return
    (ano, mes), _ = contagem.most_common(1)[0]
    leitura.competencia = f"{ano}-{mes:02d}"
    leitura.competencia_texto = f"{NOMES_MESES[mes]}/{ano}"
    if len(contagem) > 1:
        outras = ", ".join(f"{m:02d}/{a}" for (a, m) in sorted(contagem) if (a, m) != (ano, mes))
        leitura.avisos.append(_aviso(
            leitura, f"O relatório tem linhas de mais de uma competência ({outras}). "
                     f"Foi usada {mes:02d}/{ano}, a que mais aparece.",
        ))


def _montar_linha(celulas, posicoes, numero_linha: int,
                  leitura: LeituraPrefeitura) -> LinhaPrefeitura:
    def celula(coluna: str):
        posicao = posicoes[coluna]
        if posicao is None or posicao >= len(celulas):
            return ""
        return celulas[posicao]

    def campo(coluna: str) -> str:
        return _texto(celula(coluna))

    documento_original = campo(COL_DOCUMENTO)
    numero_doc = campo(COL_NUMERO)
    prestador = campo(COL_PRESTADOR)
    identificacao = (
        f"Linha {numero_linha} da tabela, nota {numero_doc or '(sem número)'} "
        f"({prestador or documento_original or 'sem prestador'})"
    )

    def valor(coluna: str):
        try:
            return _valor(celula(coluna))
        except ValueError:
            leitura.avisos.append(_aviso(
                leitura, f"{identificacao}: {coluna} inválido ({campo(coluna)!r}); "
                         "tratado como vazio.",
            ))
            return None

    valor_doc = valor(COL_VALOR)
    if valor_doc is None and not campo(COL_VALOR):
        leitura.avisos.append(_aviso(leitura, f"{identificacao}: {COL_VALOR} vazio."))

    documento = normalizar_documento(documento_original)
    if not documento:
        leitura.avisos.append(_aviso(leitura, f"{identificacao}: sem CPF/CNPJ do prestador."))
    numero = normalizar_numero(numero_doc)
    if not numero:
        leitura.avisos.append(_aviso(leitura, f"{identificacao}: sem número da nota."))

    situacao = campo(COL_SITUACAO)
    cancelada = situacao.casefold().startswith("cancel")
    if situacao and not cancelada and situacao.casefold() != SITUACAO_NORMAL:
        leitura.avisos.append(_aviso(
            leitura, f"{identificacao}: situação na prefeitura é {situacao!r} "
                     "(nem Normal nem Cancelada); foi conferida normalmente.",
        ))

    return LinhaPrefeitura(
        linha=numero_linha,
        documento=documento,
        documento_original=documento_original,
        prestador=prestador,
        numero_doc=numero_doc,
        numero=numero,
        valor_doc=valor_doc,
        aliquota=_aliquota(celula(COL_ALIQUOTA)),
        imp_ret=campo(COL_RETIDO),
        valor_tributavel=valor(COL_BASE),
        valor_imposto=valor(COL_IMPOSTO),
        cancelada=cancelada,
        situacao_nf=situacao,
        competencia=campo(COL_COMPETENCIA),
        atividade=campo(COL_ATIVIDADE),
        data_emissao=campo(COL_DATA_EMISSAO),
        incidencia_fora=campo(COL_INCIDENCIA_FORA),
        valor_deducoes=valor(COL_DEDUCOES),
        chave_acesso=campo(COL_CHAVE),
    )
