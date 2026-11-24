"""Inserir linhas numa aba sem o Excel, mantendo as fórmulas certas. Regra R7.

O openpyxl empurra as células para baixo, mas não corrige nenhuma fórmula. Aqui se faz o que o Excel faz:
- toda referência a uma linha >= a do ponto de inserção, na própria aba, desce o número de linhas inseridas,
  em TODAS as abas do arquivo (na própria aba, a referência sem nome de aba; nas outras, com "'2026'!");
- intervalo que atravessa o ponto de inserção cresce (N5:N10 com inserção na 8 -> N5:N11);
- referência a coluna inteira ($A:$A, '2026'!C:C) e a outras abas não muda;
- texto entre aspas dentro da fórmula não é mexido;
- também descem: células mescladas, alturas das linhas, painel congelado, formatação condicional, validação
  de dados, filtro, área de impressão e nomes definidos que apontem para a aba.
"""

from __future__ import annotations

import re
from copy import copy

from openpyxl.formatting.formatting import ConditionalFormattingList
from openpyxl.utils.cell import coordinate_from_string, range_boundaries
from openpyxl.worksheet.cell_range import CellRange, MultiCellRange

# [aba!]célula[:célula]: a aba entre aspas ('Senior 09 2026'!) ou sem aspas (Plan1!)
_RE_REFERENCIA = re.compile(
    r"(?P<aba>'(?:[^']|'')+'!|[A-Za-z_][\w.]*!)?"
    r"(?P<c1>\$?[A-Z]{1,3})(?P<r1>\$?)(?P<l1>\d+)"
    r"(?::(?P<c2>\$?[A-Z]{1,3})(?P<r2>\$?)(?P<l2>\d+))?"
    r"(?![\w(])")
_ANTES_PROIBIDO = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.$:")


def _nome_da_aba(prefixo: str) -> str:
    nome = prefixo[:-1]                                   # sem o "!"
    if nome.startswith("'"):
        nome = nome[1:-1].replace("''", "'")
    return nome


def deslocar_referencias(texto: str, aba_alvo: str, aba_da_formula: str, antes: int, quantidade: int = 1) -> str:
    """Desce as referências a linhas >= antes da aba `aba_alvo` num texto de fórmula escrito em `aba_da_formula`."""
    if not isinstance(texto, str):
        return texto
    partes = texto.split('"')
    for i in range(0, len(partes), 2):                    # as partes ímpares estão entre aspas
        partes[i] = _deslocar_trecho(partes[i], aba_alvo, aba_da_formula, antes, quantidade)
    return '"'.join(partes)


def _deslocar_trecho(trecho: str, aba_alvo: str, aba_da_formula: str, antes: int, quantidade: int) -> str:
    def trocar(achado):
        if achado.group("aba") is None:
            inicio = achado.start()
            if inicio > 0 and trecho[inicio - 1] in _ANTES_PROIBIDO:
                return achado.group(0)                    # pedaço de um nome (ex.: LOG10), não uma referência
            aba = aba_da_formula
        else:
            aba = _nome_da_aba(achado.group("aba"))
        if aba != aba_alvo:
            return achado.group(0)
        texto = (achado.group("aba") or "") + achado.group("c1") + achado.group("r1") + str(
            _nova_linha(int(achado.group("l1")), antes, quantidade))
        if achado.group("c2"):
            texto += ":" + achado.group("c2") + achado.group("r2") + str(
                _nova_linha(int(achado.group("l2")), antes, quantidade))
        return texto
    return _RE_REFERENCIA.sub(trocar, trecho)


def _nova_linha(linha: int, antes: int, quantidade: int) -> int:
    return linha + quantidade if linha >= antes else linha


def copiar_formula(texto, deslocamento: int):
    """A fórmula como fica ao copiar a célula `deslocamento` linhas para baixo, como o Excel faz: toda referência
    de linha relativa (sem $ antes do número) muda; $C$5, coluna inteira e texto entre aspas não mudam."""
    if not isinstance(texto, str) or not texto.startswith("=") or not deslocamento:
        return texto

    def trocar(achado):
        if achado.group("aba") is None and achado.start() > 0 and trecho[achado.start() - 1] in _ANTES_PROIBIDO:
            return achado.group(0)
        texto_novo = (achado.group("aba") or "") + achado.group("c1") + achado.group("r1") + str(
            int(achado.group("l1")) + (0 if achado.group("r1") else deslocamento))
        if achado.group("c2"):
            texto_novo += ":" + achado.group("c2") + achado.group("r2") + str(
                int(achado.group("l2")) + (0 if achado.group("r2") else deslocamento))
        return texto_novo

    partes = texto.split('"')
    for i in range(0, len(partes), 2):
        trecho = partes[i]
        partes[i] = _RE_REFERENCIA.sub(trocar, trecho)
    return '"'.join(partes)


def copiar_linha(aba, origem: int, destino: int) -> None:
    """A linha `destino` fica igual à `origem` (valores, fórmulas ajustadas à linha nova, formatação e altura)."""
    copiar_formatacao(aba, origem, destino)
    for coluna in range(1, aba.max_column + 1):
        aba.cell(destino, coluna).value = copiar_formula(aba.cell(origem, coluna).value, destino - origem)


def _deslocar_intervalo(intervalo: str, antes: int, quantidade: int) -> str:
    """"A5:C10" (sem nome de aba) com inserção na 8 -> "A5:C11"; coluna inteira não muda."""
    try:
        min_col, min_row, max_col, max_row = range_boundaries(intervalo)
    except (ValueError, TypeError):
        return intervalo
    if min_row is None:                                  # coluna inteira
        return intervalo
    novo = CellRange(min_col=min_col, min_row=_nova_linha(min_row, antes, quantidade),
                     max_col=max_col, max_row=_nova_linha(max_row, antes, quantidade))
    return novo.coord


def inserir_linhas(livro, nome_aba: str, antes: int, quantidade: int = 1, modelo: int | None = None) -> None:
    """Insere `quantidade` linhas vazias na aba, a partir da linha `antes` (que desce).

    modelo: linha (numeração de antes da inserção) cuja formatação e altura as linhas novas copiam.
    """
    aba = livro[nome_aba]
    for outra in livro.worksheets:
        for linha in outra.iter_rows():
            for celula in linha:
                valor = celula.value
                if isinstance(valor, str) and valor.startswith("=") and (outra is aba or nome_aba in valor):
                    celula.value = deslocar_referencias(valor, nome_aba, outra.title, antes, quantidade)

    # configuração das linhas que descem (altura, oculta, agrupamento): sai do lugar antigo e vai para o novo
    dimensoes = {n: d for n, d in aba.row_dimensions.items() if n >= antes}
    for numero in dimensoes:
        del aba.row_dimensions[numero]
    mescladas = list(aba.merged_cells.ranges)
    for m in mescladas:
        aba.merged_cells.remove(m)

    aba.insert_rows(antes, quantidade)

    for m in mescladas:
        aba.merged_cells.add(_deslocar_intervalo(m.coord, antes, quantidade))
    for numero, dimensao in dimensoes.items():
        nova = copy(dimensao)
        nova.index = numero + quantidade
        aba.row_dimensions[numero + quantidade] = nova
    _deslocar_painel(aba, antes, quantidade)
    _deslocar_formatacao_condicional(aba, antes, quantidade)
    _deslocar_validacoes(aba, antes, quantidade)
    if aba.auto_filter and aba.auto_filter.ref:
        aba.auto_filter.ref = _deslocar_intervalo(aba.auto_filter.ref, antes, quantidade)
    if aba.print_area:
        aba.print_area = [_deslocar_intervalo(p.split("!")[-1].replace("$", ""), antes, quantidade)
                          for p in str(aba.print_area).split(",")]
    _deslocar_nomes_definidos(livro, nome_aba, antes, quantidade)
    _deslocar_tabelas(aba, antes, quantidade)

    if modelo is not None:
        origem = modelo + quantidade if modelo >= antes else modelo
        for numero in range(antes, antes + quantidade):
            copiar_formatacao(aba, origem, numero)


def copiar_formatacao(aba, origem: int, destino: int) -> None:
    """A linha `destino` fica com a formatação e a altura da linha `origem` (sem copiar valores)."""
    aba.row_dimensions[destino].height = aba.row_dimensions[origem].height
    for coluna in range(1, aba.max_column + 1):
        celula = aba.cell(origem, coluna)
        if celula.has_style:
            aba.cell(destino, coluna)._style = copy(celula._style)


def _deslocar_painel(aba, antes: int, quantidade: int) -> None:
    painel = aba.freeze_panes
    if not painel:
        return
    coluna, linha = coordinate_from_string(painel)
    if linha >= antes:
        aba.freeze_panes = f"{coluna}{linha + quantidade}"


def _deslocar_formatacao_condicional(aba, antes: int, quantidade: int) -> None:
    regras = list(aba.conditional_formatting)
    if not regras:
        return
    nova = ConditionalFormattingList()
    for formatacao in regras:
        intervalo = " ".join(_deslocar_intervalo(r.coord, antes, quantidade) for r in formatacao.sqref.ranges)
        for regra in formatacao.rules:
            regra.formula = [deslocar_referencias(f, aba.title, aba.title, antes, quantidade) for f in regra.formula]
            nova.add(intervalo, regra)
    aba.conditional_formatting = nova


def _deslocar_validacoes(aba, antes: int, quantidade: int) -> None:
    for validacao in aba.data_validations.dataValidation:
        validacao.sqref = MultiCellRange(" ".join(_deslocar_intervalo(r.coord, antes, quantidade)
                                                  for r in validacao.sqref.ranges))
        validacao.formula1 = deslocar_referencias(validacao.formula1, aba.title, aba.title, antes, quantidade)
        validacao.formula2 = deslocar_referencias(validacao.formula2, aba.title, aba.title, antes, quantidade)


def _deslocar_tabelas(aba, antes: int, quantidade: int) -> None:
    """Tabela do Excel (Inserir > Tabela): o intervalo, o filtro e as fórmulas da linha de totais acompanham as
    linhas. Sem isso o Excel acusa "problema no conteúdo" ao abrir (a aba 2026 tem uma tabela da linha 6 ao fim)."""
    for tabela in aba.tables.values():
        tabela.ref = _deslocar_intervalo(tabela.ref, antes, quantidade)
        if tabela.autoFilter is not None and tabela.autoFilter.ref:
            tabela.autoFilter.ref = _deslocar_intervalo(tabela.autoFilter.ref, antes, quantidade)
        for coluna in tabela.tableColumns:
            for atributo in ("totalsRowFormula", "calculatedColumnFormula"):
                formula = getattr(coluna, atributo)
                if formula is not None and formula.attr_text:
                    formula.attr_text = deslocar_referencias(formula.attr_text, aba.title, aba.title, antes,
                                                             quantidade)


def _deslocar_nomes_definidos(livro, nome_aba: str, antes: int, quantidade: int) -> None:
    for nome in list(livro.defined_names.values()):
        if nome.value and nome_aba in nome.value:
            nome.value = deslocar_referencias(nome.value, nome_aba, "", antes, quantidade)
