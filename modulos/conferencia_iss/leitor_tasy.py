"""
Leitura dos CSVs do Tasy (seção 2.1 da especificação).

- Detecta a codificação sozinho (os exemplos vêm em UTF-16 sem BOM).
- Separador ";" com campos entre aspas; a Observação pode ter quebras de linha
  dentro das aspas, por isso a leitura é sempre pelo módulo csv (nunca linha a linha).
- Colunas localizadas pelo NOME do cabeçalho (o CSV de pessoa física tem outra ordem).
- A coluna Observação nunca é lida (dados sensíveis — LGPD).
- Nunca levanta exceção: problema no arquivo vira `erro`, problema numa nota vira aviso.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path

from modulos.conferencia_iss.modelos import NIVEL_AVISO, Aviso, NotaTasy
from modulos.conferencia_iss.normalizar import (
    eh_pessoa_fisica,
    normalizar_documento,
    normalizar_numero,
    numero_ajustado,
    valor_tasy,
)

# Nomes das colunas no Tasy
COL_NOTA_FISCAL = "Nota Fiscal"
COL_EMITENTE = "Emitente"
COL_CODIGO_EMITENTE = "Código emitente"
COL_TIPO_NOTA = "Tipo de nota"
COL_VALOR_MERCADORIA = "Valor da mercadoria"
COL_VALOR_NOTA = "Valor da nota"
COL_DATA_EMISSAO = "Data de emissão"
COL_DATA_ENTRADA = "Data de entrada/saída"
COL_ESTABELECIMENTO = "Estabelecimento"
COL_NOME_FANTASIA = "Nome fantasia (Destinatário)"
COL_SITUACAO = "Situação"
COL_SERIE = "Série"
COL_CODIGO_DESTINATARIO = "Código destinatário"

COLUNAS_OBRIGATORIAS = (
    COL_NOTA_FISCAL,
    COL_EMITENTE,
    COL_CODIGO_EMITENTE,
    COL_TIPO_NOTA,
    COL_VALOR_MERCADORIA,
)
COLUNAS_OPCIONAIS = (
    COL_VALOR_NOTA,
    COL_DATA_EMISSAO,
    COL_DATA_ENTRADA,
    COL_ESTABELECIMENTO,
    COL_NOME_FANTASIA,
    COL_SITUACAO,
    COL_SERIE,
    COL_CODIGO_DESTINATARIO,
)

SITUACAO_ATIVA = "Ativa"


@dataclass
class LeituraTasy:
    """O que saiu da leitura de um CSV do Tasy."""

    caminho: Path
    notas: list[NotaTasy] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)   # avisos de nota/linha
    erro: str | None = None                              # arquivo inteiro com problema

    @property
    def arquivo(self) -> str:
        return self.caminho.name

    @property
    def estabelecimentos(self) -> list[str]:
        """Estabelecimentos distintos, na ordem em que aparecem."""
        return _distintos(n.estabelecimento for n in self.notas)

    @property
    def unidades(self) -> list[str]:
        """Nomes fantasia distintos (usados no nome do relatório)."""
        return _distintos(n.nome_fantasia for n in self.notas)


def _distintos(valores) -> list[str]:
    vistos: list[str] = []
    for valor in valores:
        if valor and valor not in vistos:
            vistos.append(valor)
    return vistos


# ---------------------------------------------------------------------
# Codificação
# ---------------------------------------------------------------------
def detectar_codificacao(conteudo: bytes) -> str:
    """
    BOM UTF-16 → "utf-16"; bytes nulos nas posições ímpares → "utf-16-le";
    senão "utf-8-sig" se decodificar; senão "cp1252".
    """
    if conteudo.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16"
    amostra = conteudo[:2000]
    impares = amostra[1::2]
    if impares and impares.count(0) >= len(impares) * 0.3:
        return "utf-16-le"
    try:
        conteudo.decode("utf-8-sig")
        return "utf-8-sig"
    except UnicodeDecodeError:
        return "cp1252"


def _chave_coluna(nome: str) -> str:
    """Compara cabeçalhos sem ligar para espaços sobrando ou maiúsculas."""
    return " ".join(nome.split()).casefold()


# ---------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------
def ler_csv_tasy(caminho: Path | str) -> LeituraTasy:
    """Lê um CSV do Tasy. Nunca levanta exceção: problemas vão para erro/avisos."""
    caminho = Path(caminho)
    leitura = LeituraTasy(caminho=caminho)

    try:
        conteudo = caminho.read_bytes()
    except OSError as erro:
        leitura.erro = f"Não foi possível abrir o arquivo: {erro.strerror or erro}"
        return leitura

    if not conteudo.strip():
        leitura.erro = "Arquivo vazio."
        return leitura

    codificacao = detectar_codificacao(conteudo)
    try:
        texto = conteudo.decode(codificacao)
    except UnicodeDecodeError:
        leitura.erro = f"Não foi possível ler o texto do arquivo (codificação {codificacao})."
        return leitura

    if "\x00" in texto:
        leitura.erro = "O arquivo não parece ser um CSV de texto."
        return leitura

    try:
        _ler_registros(texto, leitura)
    except csv.Error as erro:
        leitura.notas.clear()
        leitura.avisos.clear()
        leitura.erro = f"O arquivo não é um CSV válido: {erro}"
    return leitura


def _ler_registros(texto: str, leitura: LeituraTasy) -> None:
    leitor = csv.reader(io.StringIO(texto, newline=""), delimiter=";", quotechar='"')

    cabecalho = next(leitor, None)
    if not cabecalho or not any(c.strip() for c in cabecalho):
        leitura.erro = "Arquivo sem cabeçalho."
        return

    indices: dict[str, int] = {}
    for posicao, nome in enumerate(cabecalho):
        indices.setdefault(_chave_coluna(nome), posicao)

    faltando = [c for c in COLUNAS_OBRIGATORIAS if _chave_coluna(c) not in indices]
    if faltando and {"nfs", "cnpjcpf", "vlrservicos"} <= set(indices):
        leitura.erro = (
            "Este é o relatório da Prefeitura de Cidade Alfa, não um CSV do Tasy. Escolha-o no "
            "cartão Relatório da prefeitura (aba Cidade Alfa da Conferência ISS)."
        )
        return
    if faltando:
        leitura.erro = (
            "Coluna(s) obrigatória(s) não encontrada(s): " + ", ".join(faltando)
            + ". Confira se é o relatório de notas do Tasy."
        )
        return

    posicoes = {
        coluna: indices.get(_chave_coluna(coluna))
        for coluna in COLUNAS_OBRIGATORIAS + COLUNAS_OPCIONAIS
    }

    ultima_linha = leitor.line_num
    for registro in leitor:
        linha = ultima_linha + 1          # linha do arquivo onde o registro começa
        ultima_linha = leitor.line_num

        if not any(campo.strip() for campo in registro):
            continue                       # linha em branco não é nota
        if len(registro) != len(cabecalho):
            leitura.avisos.append(_aviso(
                leitura,
                f"Linha {linha}: tem {len(registro)} colunas e o cabeçalho tem "
                f"{len(cabecalho)}. A linha não foi lida.",
            ))
            continue

        nota = _montar_nota(registro, posicoes, linha, leitura)
        if nota is not None:
            leitura.notas.append(nota)


def _montar_nota(registro, posicoes, linha: int, leitura: LeituraTasy) -> NotaTasy | None:
    def campo(coluna: str) -> str:
        posicao = posicoes[coluna]
        return registro[posicao].strip() if posicao is not None else ""

    nota_fiscal = campo(COL_NOTA_FISCAL)
    emitente = campo(COL_EMITENTE)
    identificacao = f"Linha {linha}, nota {nota_fiscal or '(sem número)'} ({emitente})"

    numero = normalizar_numero(nota_fiscal)
    if not numero:
        leitura.avisos.append(_aviso(
            leitura, f"{identificacao}: sem número de nota. A nota não foi conferida."
        ))
        return None

    try:
        valor_mercadoria = valor_tasy(campo(COL_VALOR_MERCADORIA))
    except ValueError:
        valor_mercadoria = None
    if valor_mercadoria is None:
        leitura.avisos.append(_aviso(
            leitura,
            f"{identificacao}: Valor da mercadoria vazio ou inválido "
            f"({campo(COL_VALOR_MERCADORIA)!r}). A nota não foi conferida.",
        ))
        return None

    try:
        valor_nota = valor_tasy(campo(COL_VALOR_NOTA))
    except ValueError:
        valor_nota = None
        leitura.avisos.append(_aviso(
            leitura,
            f"{identificacao}: Valor da nota inválido ({campo(COL_VALOR_NOTA)!r}); "
            "a nota foi conferida normalmente (esse valor é só exibição).",
        ))

    tipo_nota = campo(COL_TIPO_NOTA)
    pessoa_fisica = eh_pessoa_fisica(tipo_nota)
    codigo_emitente = campo(COL_CODIGO_EMITENTE)
    situacao = campo(COL_SITUACAO)

    if situacao and situacao != SITUACAO_ATIVA:
        leitura.avisos.append(_aviso(
            leitura,
            f"{identificacao}: situação no Tasy é {situacao!r} (não Ativa). "
            "A nota foi conferida normalmente.",
        ))

    return NotaTasy(
        arquivo=leitura.arquivo,
        linha=linha,
        nota_fiscal=nota_fiscal,
        numero=numero,
        numero_ajustado=numero_ajustado(nota_fiscal),
        emitente=emitente,
        codigo_emitente=codigo_emitente,
        # Na PF o código é interno do Tasy (não é CPF): a nota fica sem documento.
        documento="" if pessoa_fisica else normalizar_documento(codigo_emitente),
        tipo_nota=tipo_nota,
        eh_pessoa_fisica=pessoa_fisica,
        valor_mercadoria=valor_mercadoria,
        valor_nota=valor_nota,
        data_emissao=campo(COL_DATA_EMISSAO),
        data_entrada=campo(COL_DATA_ENTRADA),
        estabelecimento=campo(COL_ESTABELECIMENTO),
        nome_fantasia=campo(COL_NOME_FANTASIA),
        situacao=situacao,
        serie=campo(COL_SERIE),
        documento_destinatario=normalizar_documento(campo(COL_CODIGO_DESTINATARIO)),
    )


def _aviso(leitura: LeituraTasy, mensagem: str) -> Aviso:
    return Aviso(arquivo=leitura.arquivo, mensagem=mensagem, nivel=NIVEL_AVISO)
