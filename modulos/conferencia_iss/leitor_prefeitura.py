"""
Leitura do "Relatório de Serviços Contratados" da Prefeitura de Cidade Beta
(seção 2.2 da especificação).

- Apesar da extensão .xls, o arquivo é um HTML com uma <table>: lido com html.parser.
- Antes da tabela vem a linha com a inscrição municipal e a competência.
- Colunas localizadas pelo NOME do cabeçalho (espaços sobrando são ignorados).
- &nbsp; = vazio. Valores no formato 1.234,56.
- Nunca levanta exceção: problema no arquivo vira `erro`, problema numa linha vira aviso.
  Toda linha da tabela é mantida (mesmo com problema), para nada sumir do relatório.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

from modulos.conferencia_iss.modelos import NIVEL_AVISO, Aviso, LinhaPrefeitura
from modulos.conferencia_iss.normalizar import normalizar_documento, normalizar_numero, valor_prefeitura

# Nomes das colunas na prefeitura
COL_DOCUMENTO = "CPF / CNPJ Prestador"
COL_INSCRICAO = "Insc. Prestador"
COL_PRESTADOR = "Nome / Razão Social Prestador"
COL_MODELO = "Modelo de Doc. Fiscal"
COL_NUMERO = "Nº Doc."
COL_ITEM_LC = "Item LC"
COL_UNIDADE_ECONOMICA = "Unidade Econômica"
COL_ALIQUOTA = "Alíquota"
COL_DIA = "Dia"
COL_IMP_RET = "Imp. Ret."
COL_SN_MEI = "SN/MEI"
COL_NAT_OPERACAO = "Nat. Operação"
COL_VALOR_DOC = "Valor do Doc."
COL_VALOR_TRIBUTAVEL = "Valor Tribut."
COL_VALOR_IMPOSTO = "Valor do Imp."

COLUNAS_OBRIGATORIAS = (COL_DOCUMENTO, COL_NUMERO, COL_VALOR_DOC)
COLUNAS_OPCIONAIS = (
    COL_INSCRICAO, COL_PRESTADOR, COL_MODELO, COL_ITEM_LC, COL_UNIDADE_ECONOMICA,
    COL_ALIQUOTA, COL_DIA, COL_IMP_RET, COL_SN_MEI, COL_NAT_OPERACAO,
    COL_VALOR_TRIBUTAVEL, COL_VALOR_IMPOSTO,
)

MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}

_REGEX_COMPETENCIA = re.compile(r"Compet[êe]ncia\s*:\s*([^\s/•]+)\s*/\s*(\d{4})", re.IGNORECASE)
_REGEX_INSCRICAO = re.compile(r"Inscr\.?\s*Municipal\s*:\s*([\w.\-/]+)", re.IGNORECASE)


@dataclass
class LeituraPrefeitura:
    """O que saiu da leitura do relatório da prefeitura."""

    caminho: Path
    linhas: list[LinhaPrefeitura] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)   # avisos de linha / cabeçalho
    erro: str | None = None                              # arquivo inteiro com problema
    competencia: str = ""                                # "2026-09"
    competencia_texto: str = ""                          # "setembro/2026"
    inscricao_municipal: str = ""
    documento_tomador: str = ""                          # CNPJ da unidade (só Cidade Gama)

    @property
    def arquivo(self) -> str:
        return self.caminho.name


# ---------------------------------------------------------------------
# Leitor de HTML: separa o texto antes da tabela e as células de cada linha
# ---------------------------------------------------------------------
class _LeitorHtml(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.texto_antes: list[str] = []
        self.tabelas: list[list[list[str]]] = []
        self._profundidade = 0           # tabelas abertas (só a de fora interessa)
        self._linha: list[str] | None = None
        self._celula: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._profundidade += 1
            if self._profundidade == 1:
                self.tabelas.append([])
        elif self._profundidade == 1 and tag == "tr":
            self._fechar_linha()
            self._linha = []
        elif self._profundidade == 1 and tag in ("td", "th"):
            self._fechar_celula()
            if self._linha is None:
                self._linha = []
            self._celula = []
        elif tag == "br":
            self._guardar("\n")

    def handle_endtag(self, tag):
        if tag == "table" and self._profundidade:
            if self._profundidade == 1:
                self._fechar_linha()
            self._profundidade -= 1
        elif self._profundidade == 1 and tag == "tr":
            self._fechar_linha()
        elif self._profundidade == 1 and tag in ("td", "th"):
            self._fechar_celula()

    def handle_data(self, data):
        self._guardar(data)

    def _guardar(self, texto):
        if self._celula is not None:
            self._celula.append(texto)
        elif self._profundidade == 0 and not self.tabelas:
            self.texto_antes.append(texto)

    def _fechar_celula(self):
        if self._celula is not None and self._linha is not None:
            self._linha.append("".join(self._celula))
        self._celula = None

    def _fechar_linha(self):
        self._fechar_celula()
        if self._linha is not None and self.tabelas:
            self.tabelas[-1].append(self._linha)
        self._linha = None


def _chave_coluna(nome: str) -> str:
    """Compara cabeçalhos sem ligar para espaços, &nbsp; ou maiúsculas (e "N°" = "Nº")."""
    nome = nome.replace("\xa0", " ").replace("°", "º")
    return " ".join(nome.split()).casefold()


def _limpar(texto: str) -> str:
    return " ".join(texto.replace("\xa0", " ").split())


def _sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


# ---------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------
def ler_relatorio_prefeitura(caminho: Path | str) -> LeituraPrefeitura:
    """Lê o relatório da prefeitura. Nunca levanta exceção: problemas vão para erro/avisos."""
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
    if conteudo.lstrip().startswith(b"%PDF"):
        leitura.erro = _erro_pdf(caminho, "Relatório de Serviços Contratados")
        return leitura
    if conteudo.startswith(b"\xd0\xcf\x11\xe0") or conteudo.startswith(b"PK\x03\x04"):
        if _eh_relatorio_de_cidade_epsilon(caminho):
            leitura.erro = (
                "Este é o Relatório de Serviços Tomados de Cidade Epsilon. "
                "Para conferi-lo, use a aba Cidade Epsilon da Conferência ISS."
            )
        elif _eh_relatorio_de_cidade_gama(caminho):
            from modulos.conferencia_iss.leitor_prefeitura_cp import ERRO_E_DE_CIDADE_GAMA
            leitura.erro = ERRO_E_DE_CIDADE_GAMA
        else:
            leitura.erro = (
                "O arquivo é uma planilha do Excel, não o relatório no formato do site. "
                "Baixe de novo o Relatório de Serviços Contratados no site da prefeitura "
                "e selecione o arquivo original, sem abrir e salvar no Excel."
            )
        return leitura

    try:
        texto = conteudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = conteudo.decode("cp1252", errors="replace")

    parser = _LeitorHtml()
    try:
        parser.feed(texto)
        parser.close()
    except Exception as erro:  # html.parser é tolerante; isto é só uma rede de segurança
        leitura.erro = f"Não foi possível ler o HTML do arquivo: {erro}"
        return leitura

    _ler_cabecalho("".join(parser.texto_antes), leitura)
    _ler_tabela(parser.tabelas, leitura)
    if leitura.erro:
        leitura.linhas.clear()
    return leitura


def _erro_pdf(caminho: Path, nome_relatorio: str) -> str:
    """Escolheram um PDF: se for o de Cidade Zeta, diz qual item usar."""
    from modulos.conferencia_iss.leitor_prefeitura_av import ler_relatorio_cidade_zeta  # evita import circular

    leitura = ler_relatorio_cidade_zeta(caminho)
    if leitura.erro is None and leitura.linhas:
        return ("Esta é a Declaração Completa de Tomador de Cidade Zeta. "
                "Para conferi-la, use a aba Cidade Zeta da Conferência ISS.")
    return f"O arquivo é um PDF, não o {nome_relatorio} baixado do site da prefeitura."


def _eh_relatorio_de_cidade_epsilon(caminho: Path) -> bool:
    """O arquivo escolhido é, na verdade, o relatório de Cidade Epsilon?"""
    from modulos.conferencia_iss.leitor_prefeitura_sj import ler_relatorio_cidade_epsilon  # evita import circular

    leitura = ler_relatorio_cidade_epsilon(caminho)
    return leitura.erro is None and bool(leitura.linhas)


def _eh_relatorio_de_cidade_gama(caminho: Path) -> bool:
    """O arquivo escolhido é, na verdade, o relatório de Cidade Gama?"""
    from modulos.conferencia_iss.leitor_prefeitura_cp import eh_relatorio_de_cidade_gama  # import circular

    return eh_relatorio_de_cidade_gama(caminho)


def _eh_relatorio_de_cidade_alfa(caminho: Path) -> bool:
    """O arquivo escolhido é, na verdade, o relatório de Cidade Alfa?"""
    from modulos.conferencia_iss.leitor_prefeitura_fr import eh_relatorio_de_cidade_alfa  # import circular

    return eh_relatorio_de_cidade_alfa(caminho)


def _ler_cabecalho(texto: str, leitura: LeituraPrefeitura) -> None:
    """Extrai competência e inscrição municipal da linha antes da tabela."""
    texto = _limpar(texto)

    encontrado = _REGEX_COMPETENCIA.search(texto)
    if encontrado:
        nome_mes, ano = encontrado.group(1), encontrado.group(2)
        mes = MESES.get(_sem_acento(nome_mes).casefold())
        if mes:
            leitura.competencia = f"{ano}-{mes:02d}"
            leitura.competencia_texto = f"{nome_mes.lower()}/{ano}"
    if not leitura.competencia:
        leitura.avisos.append(_aviso(
            leitura, "Competência não encontrada no cabeçalho do relatório da prefeitura."
        ))

    encontrado = _REGEX_INSCRICAO.search(texto)
    if encontrado:
        leitura.inscricao_municipal = encontrado.group(1)
    else:
        leitura.avisos.append(_aviso(
            leitura, "Inscrição municipal não encontrada no cabeçalho do relatório da prefeitura."
        ))


def _ler_tabela(tabelas: list[list[list[str]]], leitura: LeituraPrefeitura) -> None:
    obrigatorias = {_chave_coluna(c) for c in COLUNAS_OBRIGATORIAS}

    # A tabela certa é a primeira cujo cabeçalho tem as colunas obrigatórias.
    tabela = None
    for candidata in tabelas:
        if candidata and obrigatorias <= {_chave_coluna(c) for c in candidata[0]}:
            tabela = candidata
            break

    if tabela is None:
        if not any(tabelas) and _eh_relatorio_de_cidade_alfa(leitura.caminho):
            from modulos.conferencia_iss.leitor_prefeitura_fr import ERRO_E_DE_CIDADE_ALFA
            leitura.erro = ERRO_E_DE_CIDADE_ALFA
        elif not any(tabelas):
            leitura.erro = (
                "Nenhuma tabela encontrada. Confira se é o Relatório de Serviços "
                "Contratados baixado do site da prefeitura."
            )
        else:
            presentes = {_chave_coluna(c) for t in tabelas if t for c in t[0]}
            faltando = [c for c in COLUNAS_OBRIGATORIAS if _chave_coluna(c) not in presentes]
            leitura.erro = (
                "Coluna(s) obrigatória(s) não encontrada(s): " + ", ".join(faltando)
                + ". Confira se é o Relatório de Serviços Contratados."
            )
        return

    cabecalho = tabela[0]
    indices: dict[str, int] = {}
    for posicao, nome in enumerate(cabecalho):
        indices.setdefault(_chave_coluna(nome), posicao)
    posicoes = {
        coluna: indices.get(_chave_coluna(coluna))
        for coluna in COLUNAS_OBRIGATORIAS + COLUNAS_OPCIONAIS
    }

    numero_linha = 0
    for celulas in tabela[1:]:
        if not any(_limpar(c) for c in celulas):
            continue                       # linha em branco não é nota
        numero_linha += 1
        if len(celulas) != len(cabecalho):
            leitura.avisos.append(_aviso(
                leitura,
                f"Linha {numero_linha} da tabela: tem {len(celulas)} colunas e o cabeçalho "
                f"tem {len(cabecalho)}. Confira essa linha no relatório da prefeitura.",
            ))
        leitura.linhas.append(_montar_linha(celulas, posicoes, numero_linha, leitura))


def _montar_linha(celulas, posicoes, numero_linha: int,
                  leitura: LeituraPrefeitura) -> LinhaPrefeitura:
    def campo(coluna: str) -> str:
        posicao = posicoes[coluna]
        if posicao is None or posicao >= len(celulas):
            return ""
        return _limpar(celulas[posicao])

    documento_original = campo(COL_DOCUMENTO)
    numero_doc = campo(COL_NUMERO)
    prestador = campo(COL_PRESTADOR)
    identificacao = (
        f"Linha {numero_linha} da tabela, nota {numero_doc or '(sem número)'} "
        f"({prestador or documento_original or 'sem prestador'})"
    )

    def valor(coluna: str):
        texto = campo(coluna)
        try:
            return valor_prefeitura(texto)
        except ValueError:
            leitura.avisos.append(_aviso(
                leitura, f"{identificacao}: {coluna} inválido ({texto!r}); tratado como vazio."
            ))
            return None

    valor_doc = valor(COL_VALOR_DOC)
    if valor_doc is None and not campo(COL_VALOR_DOC):
        leitura.avisos.append(_aviso(leitura, f"{identificacao}: Valor do Doc. vazio."))

    documento = normalizar_documento(documento_original)
    if not documento:
        leitura.avisos.append(_aviso(leitura, f"{identificacao}: sem CPF/CNPJ do prestador."))
    numero = normalizar_numero(numero_doc)
    if not numero:
        leitura.avisos.append(_aviso(leitura, f"{identificacao}: sem número do documento."))

    return LinhaPrefeitura(
        linha=numero_linha,
        documento=documento,
        documento_original=documento_original,
        prestador=prestador,
        numero_doc=numero_doc,
        numero=numero,
        valor_doc=valor_doc,
        inscricao_prestador=campo(COL_INSCRICAO),
        modelo=campo(COL_MODELO),
        item_lc=campo(COL_ITEM_LC),
        unidade_economica=campo(COL_UNIDADE_ECONOMICA),
        aliquota=campo(COL_ALIQUOTA),
        dia=campo(COL_DIA),
        imp_ret=campo(COL_IMP_RET),
        sn_mei=campo(COL_SN_MEI),
        nat_operacao=campo(COL_NAT_OPERACAO),
        valor_tributavel=valor(COL_VALOR_TRIBUTAVEL),
        valor_imposto=valor(COL_VALOR_IMPOSTO),
    )


def _aviso(leitura: LeituraPrefeitura, mensagem: str) -> Aviso:
    return Aviso(arquivo=leitura.arquivo, mensagem=mensagem, nivel=NIVEL_AVISO)
