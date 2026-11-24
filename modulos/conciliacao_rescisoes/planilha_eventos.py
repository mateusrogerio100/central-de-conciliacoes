"""
Relatório de eventos da folha (FPRF404) exportado em Excel (.xlsx), no lugar do PDF (pedido do usuário, out/2026).

A planilha tem as mesmas linhas do PDF, uma célula por pedaço ("0264" | "-" | "Liquido Rescisao";
matrícula | nome | SIT | competência | pagamento | referência | valor). Cada linha vira o MESMO texto que o
pdfplumber tira do PDF, e a leitura do 0264 continua sendo uma só (leitores.ler_eventos_do_texto).

O .xlsx que o Tasy exporta tem a parte de estilos fora do padrão (o openpyxl não abre): por isso as células
são lidas direto do XML, só com os valores e o formato de número de cada uma (para saber o que é data).
"""

from __future__ import annotations

import re
import zipfile
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from xml.etree import ElementTree

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_NS_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
# formatos embutidos no Excel (não vêm escritos no arquivo): números e datas
_FORMATOS_EMBUTIDOS = {1: "0", 2: "0.00", 3: "#,##0", 4: "#,##0.00", 14: "dd/mm/yyyy", 15: "d-mmm-yy",
                       16: "d-mmm", 17: "mmm-yy", 22: "dd/mm/yyyy hh:mm"}
_REGEX_COMPETENCIA = re.compile(r"^\d{2}/\d{4}$")
_REGEX_PESSOA = re.compile(r"^\d+$")
_REGEX_PERIODO = re.compile(r"^(Per[íi]odo:)\s*(\d{2}/\d{4})\s+a\s+(\d{2}/\d{4})(.*)$")


class PlanilhaIlegivel(Exception):
    """O arquivo não é um .xlsx que dê para ler."""


def eh_xlsx(caminho: Path) -> bool:
    try:
        with open(caminho, "rb") as arquivo:
            return arquivo.read(2) == b"PK"
    except OSError:
        return False


def _ler_xml(pacote: zipfile.ZipFile, nome: str):
    try:
        return ElementTree.fromstring(pacote.read(nome))
    except KeyError:
        return None


def _formatos_por_estilo(pacote: zipfile.ZipFile) -> list[str]:
    """Para cada estilo de célula (atributo s), o código do formato de número ('' se for o geral)."""
    estilos = _ler_xml(pacote, "xl/styles.xml")
    if estilos is None:
        return []
    codigos = {int(n.get("numFmtId")): n.get("formatCode") or "" for n in estilos.iter(f"{_NS}numFmt")}
    celulas = estilos.find(f"{_NS}cellXfs")
    if celulas is None:
        return []
    formatos = []
    for xf in celulas.findall(f"{_NS}xf"):
        numero = int(xf.get("numFmtId", "0") or 0)
        formatos.append(codigos.get(numero, _FORMATOS_EMBUTIDOS.get(numero, "")))
    return formatos


def _primeira_aba(pacote: zipfile.ZipFile) -> str:
    livro = _ler_xml(pacote, "xl/workbook.xml")
    relacoes = _ler_xml(pacote, "xl/_rels/workbook.xml.rels")
    if livro is not None and relacoes is not None:
        aba = livro.find(f"{_NS}sheets/{_NS}sheet")
        if aba is not None:
            alvo = next((r.get("Target") for r in relacoes if r.get("Id") == aba.get(f"{_NS_REL}id")), None)
            if alvo:
                alvo = alvo.lstrip("/")
                return alvo if alvo.startswith("xl/") else f"xl/{alvo}"
    return "xl/worksheets/sheet1.xml"


def _coluna(referencia: str) -> int:
    numero = 0
    for letra in re.match(r"[A-Z]+", referencia).group(0):
        numero = numero * 26 + ord(letra) - 64
    return numero


def celulas_xlsx(caminho: Path) -> list[list[tuple[str, str]]]:
    """Linhas da primeira aba: [(valor como está no arquivo, formato de número)], na ordem das colunas.

    Células vazias ficam de fora (as posições não importam: a linha vira texto).
    """
    try:
        with zipfile.ZipFile(caminho) as pacote:
            formatos = _formatos_por_estilo(pacote)
            compartilhados = _ler_xml(pacote, "xl/sharedStrings.xml")
            textos = ["".join(t.text or "" for t in si.iter(f"{_NS}t")) for si in compartilhados] \
                if compartilhados is not None else []
            aba = _ler_xml(pacote, _primeira_aba(pacote))
    except (zipfile.BadZipFile, ElementTree.ParseError, OSError) as erro:
        raise PlanilhaIlegivel(f"Não foi possível abrir a planilha: {erro}") from erro
    if aba is None:
        raise PlanilhaIlegivel("A planilha não tem nenhuma aba.")
    linhas = []
    for linha in aba.iter(f"{_NS}row"):
        celulas = []
        for celula in linha.findall(f"{_NS}c"):
            tipo = celula.get("t")
            if tipo == "inlineStr":
                valor = "".join(t.text or "" for t in celula.iter(f"{_NS}t"))
            else:
                valor = celula.findtext(f"{_NS}v") or ""
                if tipo == "s" and valor.isdigit() and int(valor) < len(textos):
                    valor = textos[int(valor)]
            valor = valor.replace("\xa0", " ").strip()
            if valor == "":
                continue
            estilo = int(celula.get("s", "0") or 0)
            formato = formatos[estilo] if tipo not in ("s", "inlineStr", "str") and estilo < len(formatos) else ""
            celulas.append((_coluna(celula.get("r", "A")), valor, formato))
        linhas.append([(valor, formato) for _, valor, formato in sorted(celulas)])
    return linhas


def _eh_formato_de_data(formato: str) -> bool:
    limpo = re.sub(r'"[^"]*"|\[[^\]]*\]', "", formato).lower()
    return "y" in limpo or "d" in limpo


def _real(numero: Decimal) -> str:
    """1234.5 → "1.234,50" (como no PDF)."""
    texto = f"{numero:,.2f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


def _como_no_pdf(valor: str, formato: str) -> str:
    """Uma célula escrita como o PDF imprime (datas dd/mm/aaaa ou mm/aaaa; dinheiro 1.234,56)."""
    try:
        numero = Decimal(valor)
    except InvalidOperation:
        return valor                                  # texto
    if formato and _eh_formato_de_data(formato):
        dia = date(1899, 12, 30) + timedelta(days=int(numero))
        return f"{dia:%d/%m/%Y}" if "d" in formato.lower() else f"{dia:%m/%Y}"
    if re.fullmatch(r"[#0,.]+", formato or ""):
        decimais = len(formato.split(".")[1]) if "." in formato else 0
        if decimais:
            return _real(numero)
        return str(int(numero)).zfill(formato.count("0"))   # "000" → SIT 007; "####00" → 01
    if numero == numero.to_integral_value() and "." not in valor:
        return valor
    return _real(numero)


def _texto_da_linha(celulas: list[str]) -> str:
    """Junta as células como o PDF: "0264-Liquido Rescisao" (evento) e "0001 -FUNDAÇÃO ... Pág.: 1" (topo)."""
    if len(celulas) >= 3 and celulas[1] == "-" and re.fullmatch(r"\d{4}", celulas[0]):
        topo = any(c.lower().startswith("pág") or c.lower().startswith("pag") for c in celulas)
        juntas = f"{celulas[0]} -{celulas[2]}" if topo else f"{celulas[0]}-{celulas[2]}"
        return " ".join([juntas] + celulas[3:])
    return " ".join(celulas)


def paginas_da_planilha(caminho: Path) -> tuple[list[str], list[str]]:
    """O relatório de eventos em Excel → ([texto como o do PDF], avisos).

    O cabeçalho "Período" do Excel exportado pode vir errado (veio 09/2026 num relatório de 07/2026): quando
    a competência das linhas das pessoas é outra, vale a das linhas (com aviso).
    """
    linhas = [_texto_da_linha([_como_no_pdf(v, f) for v, f in celulas]) for celulas in celulas_xlsx(caminho)]
    linhas = [l for l in linhas if l]
    competencias = Counter()
    for linha in linhas:
        partes = linha.split()
        if len(partes) >= 6 and _REGEX_PESSOA.match(partes[0]) and _REGEX_COMPETENCIA.match(partes[-4]):
            competencias[partes[-4]] += 1
    avisos = []
    if competencias:
        da_maioria = competencias.most_common(1)[0][0]
        for posicao, linha in enumerate(linhas):
            periodo = _REGEX_PERIODO.match(linha)
            if periodo and periodo.group(2) != da_maioria:
                avisos.append(f"O \"Período\" do cabeçalho da planilha ({periodo.group(2)}) é diferente da "
                              f"competência das pessoas ({da_maioria}): foi usada a das pessoas.")
                linhas[posicao] = f"{periodo.group(1)} {da_maioria} a {da_maioria}{periodo.group(4)}"
                break
    return ["\n".join(linhas)], avisos
