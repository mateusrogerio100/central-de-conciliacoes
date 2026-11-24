"""Leitura da planilha RECEITAS DE CONVÊNIOS (.xlsx). Seção 3.2 da especificação.

- Aba do ano: o nome começa com "Receita de Convênios" e termina com o ano.
- Linha de títulos = a que tem "CONVÊNIO"; colunas dos meses = as células com data do ano nessa linha.
- Convênios = da linha seguinte aos títulos até antes de "TOTAL RECEITAS" (linha sem nome é ignorada).
- "TOTAL RECEITAS", "Saldo Contábil" e "Diferença" achadas pelo texto da coluna dos nomes.
Só lê: a cópia preenchida é gravada por preenchimento.py (etapa Convênios 3).
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from modulos.convenios import configuracao as cfg
from modulos.convenios.leitor_razao import abrir_xlsx
from modulos.convenios.modelos import Aviso, ErroLeitura, LinhaConvenio, Planilha
from modulos.convenios.normalizacao import chave_nome, normalizar, texto_igual


def _aba_do_ano(livro, ano: int):
    prefixo = normalizar(cfg.PLANILHA_PREFIXO_ABA)
    for aba in livro.worksheets:
        nome = normalizar(aba.title)
        if nome.startswith(prefixo) and nome.endswith(str(ano)):
            return aba
    return None


def ler_planilha(caminho: Path, ano: int) -> Planilha:
    """Lê a aba do ano. Levanta ErroLeitura se a aba ou a estrutura (títulos, TOTAL RECEITAS) faltarem."""
    caminho = Path(caminho)
    livro = abrir_xlsx(caminho)
    try:
        aba = _aba_do_ano(livro, ano)
        if aba is None:
            raise ErroLeitura(f"{caminho.name}: não tem a aba \"{cfg.PLANILHA_PREFIXO_ABA} {ano}\". Crie a aba do "
                              "ano (copiando a do ano anterior) e tente de novo.")
        linhas = [tuple(v) for v in aba.iter_rows(values_only=True)]
        nome_aba = aba.title
    finally:
        livro.close()

    linha_titulos = coluna_nome = None
    for numero, valores in enumerate(linhas, start=1):
        indice = next((i for i, v in enumerate(valores) if texto_igual(v, cfg.PLANILHA_TITULO_CONVENIO)), None)
        if indice is not None:
            linha_titulos, coluna_nome = numero, indice + 1
            break
    if linha_titulos is None:
        raise ErroLeitura(f"{caminho.name}, aba {nome_aba}: linha de títulos com "
                          f"\"{cfg.PLANILHA_TITULO_CONVENIO}\" não encontrada.")

    titulos = linhas[linha_titulos - 1]
    colunas_mes, coluna_acumulado = {}, None
    for indice, valor in enumerate(titulos):
        if isinstance(valor, (datetime, date)) and valor.year == ano:
            colunas_mes.setdefault(valor.month, indice + 1)
        elif isinstance(valor, str) and normalizar(valor).startswith(normalizar(cfg.PLANILHA_TITULO_ACUMULADO)):
            coluna_acumulado = indice + 1

    def nome_da(numero: int) -> str:
        valores = linhas[numero - 1]
        valor = valores[coluna_nome - 1] if coluna_nome - 1 < len(valores) else None
        return " ".join(str(valor).split()) if valor is not None else ""

    convenios, linha_total = [], None
    for numero in range(linha_titulos + 1, len(linhas) + 1):
        nome = nome_da(numero)
        if texto_igual(nome, cfg.PLANILHA_TOTAL):
            linha_total = numero
            break
        if nome:
            convenios.append(LinhaConvenio(nome, numero))
    if linha_total is None:
        raise ErroLeitura(f"{caminho.name}, aba {nome_aba}: linha \"{cfg.PLANILHA_TOTAL}\" não encontrada.")

    abaixo = {chave_nome(nome_da(n)): n for n in range(linha_total + 1, len(linhas) + 1) if nome_da(n)}
    planilha = Planilha(
        arquivo=caminho.name, aba=nome_aba, ano=ano, linha_titulos=linha_titulos, coluna_nome=coluna_nome,
        colunas_mes=colunas_mes, coluna_acumulado=coluna_acumulado, convenios=convenios, linha_total=linha_total,
        linha_saldo=abaixo.get(chave_nome(cfg.PLANILHA_SALDO_CONTABIL)),
        linha_diferenca=abaixo.get(chave_nome(cfg.PLANILHA_DIFERENCA)),
    )
    for convenio in convenios:
        valores = linhas[convenio.linha - 1]
        for mes, coluna in colunas_mes.items():
            if coluna - 1 < len(valores):
                planilha.valores[(convenio.linha, mes)] = valores[coluna - 1]

    origem = f"{caminho.name}, aba {nome_aba}"
    faltando = [m for m in range(1, 13) if m not in colunas_mes]
    if faltando:
        planilha.avisos.append(Aviso(origem, "Meses sem coluna na linha de títulos: "
                                             + ", ".join(f"{m:02d}" for m in faltando) + "."))
    for titulo, linha in ((cfg.PLANILHA_SALDO_CONTABIL, planilha.linha_saldo),
                          (cfg.PLANILHA_DIFERENCA, planilha.linha_diferenca)):
        if linha is None:
            planilha.avisos.append(Aviso(origem, f"Linha \"{titulo}\" não encontrada abaixo do TOTAL."))
    vistos: dict[str, LinhaConvenio] = {}
    for convenio in convenios:
        chave = chave_nome(convenio.nome)
        if chave in vistos:
            planilha.avisos.append(Aviso(f"{origem} linha {convenio.linha}",
                                         f"\"{convenio.nome}\" repete a linha {vistos[chave].linha} "
                                         f"(\"{vistos[chave].nome}\"): vale a primeira."))
        else:
            vistos[chave] = convenio
    return planilha
