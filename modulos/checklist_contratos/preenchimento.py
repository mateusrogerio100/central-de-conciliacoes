"""Cópia do Check list com a coluna do mês preenchida nas linhas OK (R6, R7). Seção 5 da especificação.

O valor é escrito direto no XML de cada aba, dentro do .xlsx copiado: o resto do arquivo (fórmulas,
comentários, formas, suplementos do Office, configurações de impressão, as outras abas) fica igual
byte a byte. Abrir e salvar com o openpyxl apagaria as formas e os suplementos (rodada de 23/10/2026).

- A célula nova recebe o formato da célula do mês anterior na mesma linha (se houver).
- Uma célula que já tem algo nunca é alterada (R7): a conferência já não manda gravá-la, e aqui
  ela é conferida de novo no próprio XML.
- O Excel recalcula as fórmulas (diferença, variação) ao abrir a cópia (fullCalcOnLoad).
"""

from __future__ import annotations

import re
import shutil
import zipfile
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path, PurePosixPath

from openpyxl.utils import column_index_from_string, get_column_letter

from modulos.checklist_contratos.modelos import Aviso, Checklist, ResultadoLinha


@dataclass
class ValorParaGravar:
    aba: str                   # nome da aba
    linha: int
    coluna: int                # 1 = A
    coluna_modelo: int | None  # mês anterior: de onde vem o formato
    valor: Decimal


def valores_para_gravar(resultados: list[ResultadoLinha], checklist: Checklist) -> list[ValorParaGravar]:
    saida = []
    for r in resultados:
        if r.gravar and r.valor is not None:
            aba = checklist.abas[r.regra.aba]
            saida.append(ValorParaGravar(aba.nome, r.linha.numero, aba.coluna_mes, aba.coluna_mes_anterior, r.valor))
    return saida


def _arquivo_da_aba(livro_zip: zipfile.ZipFile, nome_aba: str) -> str:
    workbook = livro_zip.read("xl/workbook.xml").decode("utf-8")
    rels = livro_zip.read("xl/_rels/workbook.xml.rels").decode("utf-8")
    for atributos in re.findall(r"<sheet\b([^>]*)/?>", workbook):
        nome = re.search(r'\bname="([^"]*)"', atributos)
        if nome and _xml_texto(nome.group(1)) == nome_aba:
            rid = re.search(r'\br:id="([^"]+)"', atributos).group(1)
            break
    else:
        raise KeyError(nome_aba)
    for atributos in re.findall(r"<Relationship\b([^>]*)/?>", rels):
        if re.search(rf'\bId="{re.escape(rid)}"', atributos):
            alvo = re.search(r'\bTarget="([^"]+)"', atributos).group(1)
            return alvo.lstrip("/") if alvo.startswith("/") else str(PurePosixPath("xl") / alvo)
    raise KeyError(nome_aba)


def _xml_texto(texto: str) -> str:
    return (texto.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
            .replace("&apos;", "'").replace("&amp;", "&"))


def _estilo(xml: str, referencia: str) -> str | None:
    celula = re.search(rf'<c r="{referencia}"(?=[\s/>])([^>]*?)/?>', xml)
    if not celula:
        return None
    estilo = re.search(r'\bs="(\d+)"', celula.group(1))
    return estilo.group(1) if estilo else None


def _gravar_na_aba(xml: str, item: ValorParaGravar) -> tuple[str, str]:
    """Devolve (xml novo, "" ou o motivo de não ter gravado)."""
    referencia = f"{get_column_letter(item.coluna)}{item.linha}"
    estilo_modelo = _estilo(xml, f"{get_column_letter(item.coluna_modelo)}{item.linha}") if item.coluna_modelo else None
    existente = re.search(rf'<c r="{referencia}"(?=[\s/>])([^>]*?)(/>|>(.*?)</c>)', xml, re.S)
    if existente:
        conteudo = existente.group(3) or ""
        if re.search(r"<(v|is|f)\b", conteudo):
            return xml, f"a célula {referencia} já tem conteúdo"
        estilo = estilo_modelo or (re.search(r'\bs="(\d+)"', existente.group(1)) or [None, None])[1]
        nova = f'<c r="{referencia}"' + (f' s="{estilo}"' if estilo else "") + f"><v>{item.valor}</v></c>"
        return xml[:existente.start()] + nova + xml[existente.end():], ""

    linha = re.search(rf'<row r="{item.linha}"(?=[\s>])[^>]*?(/>|>(.*?)</row>)', xml, re.S)
    if not linha:
        return xml, f"a linha {item.linha} não existe na aba"
    nova = f'<c r="{referencia}"' + (f' s="{estilo_modelo}"' if estilo_modelo else "") + f"><v>{item.valor}</v></c>"
    if linha.group(1) == "/>":                                    # <row r="5" .../> sem células
        abertura = linha.group(0)[:-2] + ">"
        return xml[:linha.start()] + abertura + nova + "</row>" + xml[linha.end():], ""
    # entra antes da primeira célula de coluna maior (as células ficam em ordem de coluna)
    inicio_conteudo = linha.start(2)
    for celula in re.finditer(r'<c r="([A-Z]+)\d+"', linha.group(2)):
        if column_index_from_string(celula.group(1)) > item.coluna:
            posicao = inicio_conteudo + celula.start()
            return xml[:posicao] + nova + xml[posicao:], ""
    posicao = linha.end(2)
    return xml[:posicao] + nova + xml[posicao:], ""


def _recalcular_ao_abrir(workbook: str) -> str:
    if re.search(r"<calcPr\b", workbook):
        return re.sub(r"<calcPr\b([^>]*?)\s*/>",
                      lambda m: "<calcPr" + re.sub(r'\s+fullCalcOnLoad="[^"]*"', "", m.group(1)) + ' fullCalcOnLoad="1"/>',
                      workbook, count=1)
    return workbook.replace("</workbook>", '<calcPr fullCalcOnLoad="1"/></workbook>', 1)


def gravar_copia(original: Path, destino: Path, valores: list[ValorParaGravar]) -> list[Aviso]:
    """Copia o Check list para `destino` e grava os valores. Devolve avisos das células não gravadas.

    Levanta OSError se não puder ler o original ou gravar o destino.
    """
    original, destino = Path(original), Path(destino)
    avisos: list[Aviso] = []
    temporario = destino.with_name(destino.name + ".tmp")
    with zipfile.ZipFile(original) as entrada:
        novos: dict[str, str] = {}
        for item in valores:
            try:
                parte = _arquivo_da_aba(entrada, item.aba)
            except KeyError:
                avisos.append(Aviso(item.aba, "Aba não encontrada no arquivo: valor não gravado."))
                continue
            xml = novos.get(parte) or entrada.read(parte).decode("utf-8")
            novos[parte], motivo = _gravar_na_aba(xml, item)
            if motivo:
                avisos.append(Aviso(f"{item.aba} linha {item.linha}", f"Valor {item.valor} não gravado: {motivo}."))
        if novos:
            novos["xl/workbook.xml"] = _recalcular_ao_abrir(entrada.read("xl/workbook.xml").decode("utf-8"))
        with zipfile.ZipFile(temporario, "w") as saida:
            for info in entrada.infolist():
                dados = novos[info.filename].encode("utf-8") if info.filename in novos else entrada.read(info.filename)
                saida.writestr(info, dados)
    shutil.move(temporario, destino)
    return avisos
