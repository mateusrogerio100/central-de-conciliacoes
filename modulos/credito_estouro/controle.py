"""Controle do crédito estouro: leitura e gravação da aba "Controle" (ESPECIFICACAO_CREDITO_ESTOURO.md, seção 3.3).

A aba é gravada pelo próprio módulo no Excel de saída de cada mês e escolhida como entrada no mês seguinte.
O usuário pode acrescentar à mão um parcelamento combinado com o DP, ou apagar uma linha já acertada.

    A1  Crédito Estouro — controle de 05/2026
    A2  Unidade: <unidade>
    A3  Saldo do razão em 31/05/2026: 98853.35
    A5  Matrícula | Colaborador | Tipo | Mês de origem | Valor | Parcela | Observação | Pagador (nome no razão)
    A6… uma linha por valor em aberto (até a primeira linha sem Tipo)

Linha "Pagamento por outra pessoa" (valor zero): os pagamentos no razão em nome do Pagador contam para o
colaborador da linha. É carregada de um mês para o outro como as outras.

Colunas achadas pelo título. Só openpyxl, nunca o Excel.
"""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook, load_workbook

from modulos.credito_estouro.modelos import (
    TIPO_PARCELAMENTO,
    TIPO_PENDENCIA,
    TIPO_VINCULO,
    TIPOS_CONTROLE,
    ZERO,
    Aviso,
    ItemControle,
)
from modulos.credito_estouro.util import dinheiro, juntar_espacos, sem_acento

ABA_CONTROLE = "Controle"
COLUNAS = ["Matrícula", "Colaborador", "Tipo", "Mês de origem", "Valor", "Parcela", "Observação",
           "Pagador (nome no razão)"]
_REGEX_COMPETENCIA = re.compile(r"controle de (\d{2})/(\d{4})", re.IGNORECASE)
_REGEX_MES = re.compile(r"^(\d{2})/(\d{4})$")


@dataclass
class LeituraControle:
    arquivo: str
    competencia: date | None = None
    unidade: str = ""
    saldo_razao: Decimal | None = None
    itens: list[ItemControle] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)
    erro: str | None = None

    @property
    def total(self) -> Decimal:
        return sum((item.valor for item in self.itens), ZERO)


def _mes(valor: object) -> date | None:
    if isinstance(valor, datetime):
        return valor.date().replace(day=1)
    if isinstance(valor, date):
        return valor.replace(day=1)
    if isinstance(valor, str):
        achado = _REGEX_MES.match(valor.strip())
        if achado:
            return date(int(achado.group(2)), int(achado.group(1)), 1)
    return None


def _texto(valor: object) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return juntar_espacos(valor)


# ---------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------
def ler_controle(caminho: Path) -> LeituraControle:
    caminho = Path(caminho)
    leitura = LeituraControle(arquivo=caminho.name)
    try:
        with warnings.catch_warnings():
            # o Excel regrava a lista suspensa da Situação num formato que o openpyxl não lê (e avisa): só a lista,
            # os dados são lidos normalmente
            warnings.simplefilter("ignore", UserWarning)
            livro = load_workbook(caminho, data_only=True)
    except Exception as erro:
        leitura.erro = (f"Não foi possível abrir o controle do mês anterior ({erro}). Escolha o Excel que o "
                        "Crédito Estouro gravou no mês anterior (.xlsx).")
        return leitura
    try:
        if ABA_CONTROLE not in livro.sheetnames:
            leitura.erro = (f"O arquivo não tem a aba \"{ABA_CONTROLE}\". Escolha o Excel que o Crédito Estouro "
                            "gravou no mês anterior.")
            return leitura
        linhas = [list(l) for l in livro[ABA_CONTROLE].iter_rows(values_only=True)]
    finally:
        livro.close()
    return ler_controle_das_linhas(linhas, leitura)


def ler_controle_das_linhas(linhas: list[list[object]], leitura: LeituraControle) -> LeituraControle:
    posicoes: dict[str, int] | None = None
    for numero, linha in enumerate(linhas, start=1):
        textos = [c for c in linha if isinstance(c, str)]
        if posicoes is None:
            for texto in textos:
                competencia = _REGEX_COMPETENCIA.search(texto)
                if competencia:
                    leitura.competencia = date(int(competencia.group(2)), int(competencia.group(1)), 1)
                if texto.startswith("Unidade:"):
                    leitura.unidade = juntar_espacos(texto.split(":", 1)[1])
                if texto.startswith("Saldo do razão"):
                    numeros = [c for c in linha if isinstance(c, (int, float))]
                    if numeros:
                        leitura.saldo_razao = dinheiro(numeros[0])
            titulos = {sem_acento(_texto(c)): i for i, c in enumerate(linha) if _texto(c)}
            if all(sem_acento(c) in titulos for c in COLUNAS[:5]):
                posicoes = {c: titulos.get(sem_acento(c)) for c in COLUNAS}
            continue

        def celula(coluna: str) -> object:
            indice = posicoes.get(coluna)
            return linha[indice] if indice is not None and indice < len(linha) else None

        tipo = _texto(celula("Tipo"))
        if not tipo:
            break                                   # fim da lista (a linha do total ou uma linha vazia)
        tipo_certo = next((t for t in TIPOS_CONTROLE if sem_acento(t) == sem_acento(tipo)), None)
        if tipo_certo is None:
            leitura.avisos.append(Aviso(leitura.arquivo, f"Controle, linha {numero}: tipo \"{tipo}\" desconhecido; "
                                                         f"a linha entrou como \"{TIPO_PENDENCIA}\"."))
            tipo_certo = TIPO_PENDENCIA
        try:
            valor = dinheiro(celula("Valor"))
            parcela_celula = celula("Parcela")
            parcela = dinheiro(parcela_celula) if parcela_celula not in (None, "") else None
        except ValueError:
            leitura.avisos.append(Aviso(leitura.arquivo, f"Controle, linha {numero}: valor não reconhecido; "
                                                         "a linha NÃO foi lida (a prova do saldo vai mostrar a "
                                                         "diferença)."))
            continue
        pagador = _texto(celula("Pagador (nome no razão)"))
        if tipo_certo == TIPO_VINCULO and (not pagador or not _texto(celula("Matrícula"))):
            leitura.avisos.append(Aviso(leitura.arquivo, f"Controle, linha {numero}: \"{TIPO_VINCULO}\" precisa da "
                                                         "matrícula do colaborador e do nome do pagador; a linha "
                                                         "não foi usada."))
            continue
        if tipo_certo == TIPO_PARCELAMENTO and not parcela:
            leitura.avisos.append(Aviso(leitura.arquivo, f"Controle, linha {numero}: parcelamento sem o valor da "
                                                         "parcela; a parcela do 1204 vai ser usada como veio."))
        leitura.itens.append(ItemControle(matricula=_texto(celula("Matrícula")).lstrip("0") or "",
                                          nome=_texto(celula("Colaborador")), tipo=tipo_certo,
                                          origem=_mes(celula("Mês de origem")), valor=valor, parcela=parcela,
                                          observacao=_texto(celula("Observação")), pagador=pagador))
    if posicoes is None:
        leitura.erro = ("A aba \"Controle\" não tem o cabeçalho esperado (" + ", ".join(COLUNAS[:5]) + ").")
    elif leitura.competencia is None:
        leitura.erro = "A aba \"Controle\" não diz de que mês é (\"Crédito Estouro — controle de MM/AAAA\")."
    return leitura


# ---------------------------------------------------------------------
# Gravação
# ---------------------------------------------------------------------
def escrever_aba_controle(aba, competencia: date, unidade: str, saldo_razao: Decimal | None,
                          itens: list[ItemControle], fim_do_mes: date | None = None) -> None:
    """Escreve a aba no formato que `ler_controle` lê (o relatório da etapa 4 também usa)."""
    aba["A1"] = f"Crédito Estouro — controle de {competencia:%m/%Y}"
    aba["A2"] = f"Unidade: {unidade}"
    fim = f" em {fim_do_mes:%d/%m/%Y}" if fim_do_mes else ""
    aba["A3"] = f"Saldo do razão{fim}:"
    aba["C3"] = float(saldo_razao) if saldo_razao is not None else None
    for coluna, titulo in enumerate(COLUNAS, start=1):
        aba.cell(row=5, column=coluna, value=titulo)
    for linha, item in enumerate(itens, start=6):
        valores = [item.matricula, item.nome, item.tipo, f"{item.origem:%m/%Y}" if item.origem else "",
                   float(item.valor), float(item.parcela) if item.parcela is not None else None, item.observacao,
                   item.pagador]
        for coluna, valor in enumerate(valores, start=1):
            aba.cell(row=linha, column=coluna, value=valor)


def gravar_controle(caminho: Path, competencia: date, unidade: str, saldo_razao: Decimal | None,
                    itens: list[ItemControle]) -> Path:
    livro = Workbook()
    aba = livro.active
    aba.title = ABA_CONTROLE
    escrever_aba_controle(aba, competencia, unidade, saldo_razao, itens)
    livro.save(caminho)
    return Path(caminho)
