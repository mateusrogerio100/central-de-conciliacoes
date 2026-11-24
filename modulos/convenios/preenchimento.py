"""Grava a cópia da planilha de receitas com o mês preenchido. Regras P1 a P5 da especificação.

- P1: coluna do mês do razão. Mês já preenchido só é gravado com substituir=True (a tela pergunta antes);
  na substituição, a linha sem lançamento no razão mantém o valor que já tinha (decisão do usuário,
  29/10/2026: protege o que foi digitado à mão, ex.: IAMSPE).
- P2: convênio sem lançamento no mês: a célula fica como está (vazia).
- P3: linha Saldo Contábil do mês = total do razão.
- P4: TOTAL RECEITAS, Acumulado e Diferença continuam fórmulas. A linha nova (C6) entra na ordem alfabética;
  as fórmulas da aba são ajustadas como o Excel faz ao inserir uma linha, e a linha nova ganha a fórmula do
  Acumulado da vizinha.
- P5: conferência: total do mês das linhas de convênio (calculado aqui) − Saldo Contábil.
O original nunca é alterado: o openpyxl lê o arquivo e grava outro.
"""

from __future__ import annotations

import io
import re
from copy import copy
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

import openpyxl
from openpyxl.formula.translate import Translator
from openpyxl.utils import get_column_letter

from modulos.convenios import configuracao as cfg
from modulos.convenios.classificacao import Classificacao, TotalLinha
from modulos.convenios.modelos import ZERO, Aviso, ErroLeitura, Planilha, Razao
from modulos.convenios.normalizacao import chave_nome, formatar_valor, para_decimal

# referência a uma célula numa fórmula: C5, $C$5 (não pega nomes de função nem números)
_RE_REFERENCIA = re.compile(r"(?<![A-Za-z0-9_.!'\"])(\$?)([A-Z]{1,3})(\$?)(\d+)(?![\d(A-Za-z_])")


@dataclass
class LinhaPreenchida:
    """O que aconteceu com uma linha da planilha no mês (aba "Por convênio" do relatório)."""

    nome: str
    linha: int                         # linha na cópia (depois das linhas novas)
    linha_original: int | None         # linha na planilha escolhida; None = linha nova
    situacao: str
    anterior: Decimal | None = None    # o que havia na célula do mês (valor calculado pelo Excel)
    novo: Decimal | None = None        # o que ficou na célula do mês
    total: TotalLinha | None = None    # os lançamentos que caíram nela


@dataclass
class Preenchimento:
    mes: int
    ano: int
    linhas: list[LinhaPreenchida] = field(default_factory=list)
    saldo_contabil: Decimal = ZERO
    saldo_anterior: Decimal | None = None
    linha_saldo: int | None = None
    avisos: list[Aviso] = field(default_factory=list)

    @property
    def total_preenchido(self) -> Decimal:
        """TOTAL RECEITAS do mês como ficou na cópia (soma das linhas de convênio)."""
        return sum((l.novo for l in self.linhas if l.novo is not None), ZERO)

    @property
    def diferenca(self) -> Decimal:
        return self.total_preenchido - self.saldo_contabil

    @property
    def linhas_novas(self) -> list[LinhaPreenchida]:
        return [l for l in self.linhas if l.linha_original is None]


def mes_ja_preenchido(planilha: Planilha, mes: int) -> list[str]:
    """P1: os convênios que já têm valor no mês (a tela pergunta antes de substituir)."""
    return [c.nome for c in planilha.preenchidas_no_mes(mes)]


# ---------------------------------------------------------------------------
# Inserir uma linha (C6) mantendo as fórmulas, como o Excel faz
# ---------------------------------------------------------------------------

def _deslocar_formula(formula: str, antes: int) -> str:
    """Toda referência a uma linha >= antes desce uma linha (C5:C56 com antes=30 -> C5:C57)."""
    def trocar(achado):
        coluna_fixa, coluna, linha_fixa, linha = achado.groups()
        linha = int(linha)
        return f"{coluna_fixa}{coluna}{linha_fixa}{linha + 1 if linha >= antes else linha}"
    return _RE_REFERENCIA.sub(trocar, formula)


def _inserir_linha(aba, antes: int, modelo: int, coluna_acumulado: int | None):
    """Insere uma linha vazia em `antes`, com a formatação da linha `modelo` (número antes da inserção)."""
    for linha in aba.iter_rows():
        for celula in linha:
            if isinstance(celula.value, str) and celula.value.startswith("="):
                celula.value = _deslocar_formula(celula.value, antes)
    alturas = {n: d.height for n, d in aba.row_dimensions.items() if n >= antes}
    mescladas = [m for m in aba.merged_cells.ranges if m.min_row >= antes]
    for m in mescladas:
        aba.merged_cells.remove(m)
    aba.insert_rows(antes)
    for m in mescladas:
        m.shift(0, 1)
        aba.merged_cells.add(m)
    for numero in sorted(alturas, reverse=True):
        aba.row_dimensions[numero + 1].height = alturas[numero]
    modelo = modelo + 1 if modelo >= antes else modelo
    aba.row_dimensions[antes].height = aba.row_dimensions[modelo].height
    for coluna in range(1, aba.max_column + 1):
        origem, nova = aba.cell(modelo, coluna), aba.cell(antes, coluna)
        if origem.has_style:
            nova._style = copy(origem._style)
    if coluna_acumulado:
        formula = aba.cell(modelo, coluna_acumulado).value
        if isinstance(formula, str) and formula.startswith("="):
            letra = get_column_letter(coluna_acumulado)
            aba.cell(antes, coluna_acumulado).value = Translator(formula, f"{letra}{modelo}").translate_formula(
                f"{letra}{antes}")


def _posicao_alfabetica(nome: str, linhas: dict[str, int]) -> int:
    """C6: a linha antes da qual o convênio novo entra (ordem alfabética, comparando como em C4)."""
    chave = chave_nome(nome)
    for nome_linha, numero in sorted(linhas.items(), key=lambda item: item[1]):
        if chave_nome(nome_linha) > chave:
            return numero
    return max(linhas.values()) + 1


# ---------------------------------------------------------------------------
# Preencher
# ---------------------------------------------------------------------------

def preencher(origem: Path, planilha: Planilha, razao: Razao, classificacao: Classificacao, destino: Path,
              substituir: bool = False) -> Preenchimento:
    """Grava em `destino` a cópia de `origem` com o mês do razão preenchido.

    ErroLeitura se não der para abrir a planilha; ValueError se o mês já estiver preenchido e substituir=False;
    OSError se não der para gravar (ex.: destino aberto no Excel).
    """
    mes, ano = razao.mes, planilha.ano
    if mes is None:
        raise ValueError("O mês do razão não foi identificado: não dá para saber que coluna preencher.")
    if mes not in planilha.colunas_mes:
        raise ValueError(f"A aba {planilha.aba} não tem a coluna do mês {mes:02d}/{ano}.")
    ja = mes_ja_preenchido(planilha, mes)
    if ja and not substituir:
        raise ValueError(f"O mês {mes:02d}/{ano} já está preenchido em {len(ja)} linha(s): confirme a substituição.")
    try:
        livro = openpyxl.load_workbook(io.BytesIO(Path(origem).read_bytes()))
    except OSError as erro:
        raise ErroLeitura(f"Não foi possível abrir {Path(origem).name}: {erro}") from None
    aba = livro[planilha.aba]
    coluna = planilha.colunas_mes[mes]
    resultado = Preenchimento(mes, ano, saldo_contabil=razao.total)

    # linhas novas primeiro (C6): mudam a numeração das de baixo. Cada linha: [nome, linha na cópia, total]
    totais_planilha = {t.linha_planilha: t for t in classificacao.linhas if t.linha_planilha}
    linhas = {c.linha: [c.nome, c.linha, totais_planilha.get(c.linha)] for c in planilha.convenios}
    especiais = {"total": planilha.linha_total, "saldo": planilha.linha_saldo, "diferenca": planilha.linha_diferenca}
    for numero_nova, nova in enumerate(classificacao.linhas_novas, start=1):
        atuais = {nome: numero for nome, numero, _ in linhas.values()}
        antes = _posicao_alfabetica(nova.nome, atuais)
        modelo = antes - 1 if antes - 1 in atuais.values() else antes
        _inserir_linha(aba, antes, modelo, planilha.coluna_acumulado)
        for item in linhas.values():
            item[1] += item[1] >= antes
        especiais = {chave: n + 1 if n and n >= antes else n for chave, n in especiais.items()}
        aba.cell(antes, planilha.coluna_nome).value = nova.nome
        linhas[-numero_nova] = [nova.nome, antes, nova]        # chave negativa = não existia na planilha

    # P1/P2: a coluna do mês
    for original, (nome, numero, total) in sorted(linhas.items(), key=lambda item: item[1][1]):
        original = original if original > 0 else None
        anterior = para_decimal(planilha.valores.get((original, mes))) if original else None
        celula = aba.cell(numero, coluna)
        if total is not None and total.destinos:
            celula.value = float(total.valor)
            situacao = (cfg.SITUACAO_NOVA if original is None else
                        cfg.SITUACAO_SUBSTITUIDA if anterior is not None else cfg.SITUACAO_PREENCHIDA)
            novo = total.valor
        else:
            situacao = cfg.SITUACAO_MANTIDA if anterior is not None else cfg.SITUACAO_SEM_MOVIMENTO
            novo = anterior
        resultado.linhas.append(LinhaPreenchida(nome, numero, original, situacao, anterior, novo, total))

    # P3: Saldo Contábil
    if especiais["saldo"]:
        celula = aba.cell(especiais["saldo"], coluna)
        resultado.saldo_anterior = para_decimal(celula.value) if not str(celula.value or "").startswith("=") else None
        celula.value = float(razao.total)
        resultado.linha_saldo = especiais["saldo"]
    else:
        resultado.avisos.append(Aviso(planilha.aba, f"Linha \"{cfg.PLANILHA_SALDO_CONTABIL}\" não encontrada: o "
                                                    "total do razão não foi gravado na planilha.", erro=True))

    _conferir_total(aba, especiais["total"], coluna, [numero for _, numero, _ in linhas.values()], planilha.aba,
                    resultado)
    _avisar_diferenca(resultado, classificacao)
    livro.calculation.fullCalcOnLoad = True          # o Excel recalcula TOTAL, Acumulado e Diferença ao abrir
    livro.save(destino)
    return resultado


def _conferir_total(aba, linha_total: int, coluna: int, linhas: list[int], nome_aba: str,
                    resultado: Preenchimento):
    """P4: a fórmula do TOTAL RECEITAS do mês precisa somar todas as linhas de convênio (inclusive as novas)."""
    formula = aba.cell(linha_total, coluna).value
    achado = cfg.RE_FORMULA_SOMA.match(formula) if isinstance(formula, str) else None
    primeira, ultima = min(linhas), max(linhas)
    if achado and int(achado.group(2)) <= primeira and int(achado.group(4)) >= ultima:
        return
    resultado.avisos.append(Aviso(f"{nome_aba} linha {linha_total}",
                                  f"A fórmula do {cfg.PLANILHA_TOTAL} do mês ({formula!r}) não soma todas as linhas de "
                                  f"convênio ({primeira} a {ultima}): confira a fórmula na cópia.", erro=True))


def _avisar_diferenca(resultado: Preenchimento, classificacao: Classificacao):
    """P5: o total preenchido tem de bater com o Saldo Contábil."""
    if resultado.diferenca == ZERO:
        return
    partes = [f"{cfg.PLANILHA_TOTAL} do mês {formatar_valor(resultado.total_preenchido)} − "
              f"{cfg.PLANILHA_SALDO_CONTABIL} {formatar_valor(resultado.saldo_contabil)} = "
              f"{formatar_valor(resultado.diferenca)}."]
    if classificacao.nao_identificados:
        partes.append(f"Não identificado: {formatar_valor(classificacao.total_nao_identificado)} (preencha à mão).")
    mantidas = [l for l in resultado.linhas if l.situacao == cfg.SITUACAO_MANTIDA]
    if mantidas:
        partes.append(f"Valores mantidos sem lançamento no razão: "
                      f"{formatar_valor(sum((l.novo for l in mantidas), ZERO))}.")
    resultado.avisos.append(Aviso(cfg.PLANILHA_DIFERENCA, " ".join(partes), erro=True))
