"""Leitura da estrutura da Planilha HM. Seção 2.3.

- A aba do ano ("2026") e as abas "Senior MM 2026" são achadas pelo nome.
- Na aba do ano, tudo é achado pelo texto, nunca pela letra: a linha de títulos é a primeira linha de abertura
  ("EVENTO" + nome da seção + os meses); a coluna do nome é a que vem logo depois de "EVENTO"; as colunas
  Concateno, Cód. e Centros de Custos e a de cada mês, pelo título.
- Seções: linha de abertura (col. EVENTO = "EVENTO"); linha de evento (número do evento, Cód. vazio); linha de
  CC (número do evento e Cód. preenchido), logo abaixo do evento — a linha com o mesmo número e o Cód. vazio
  logo abaixo do evento também é de CC, sem código (ex.: "A Classificar"); linha de total (EVENTO vazio, nome
  preenchido: "TOTAL ..." ou outro texto, ex.: "HONORÁRIOS PROCEDIMENTOS"). Uma seção pode não ter nada.
- Depois das seções: "TOTAL GERAL"; "LOTE REPASSE" (na col. EVENTO); na linha de baixo, a diferença.
- Conferência da estrutura (para a R5 acrescentar um evento ao total sem errar): a fórmula do total de cada
  seção soma exatamente as linhas de evento da seção, e a do TOTAL GERAL, as linhas de total das seções.
  Diferença vira aviso.
"""

from __future__ import annotations

import io
import warnings
import zipfile
from pathlib import Path

import openpyxl

from modulos.planilha_hm import configuracao as cfg
from modulos.planilha_hm.modelos import (
    AbaSenior,
    Aviso,
    ErroLeitura,
    LinhaCC,
    LinhaEvento,
    Planilha,
    Secao,
    ZERO,
)
from modulos.planilha_hm.normalizacao import para_decimal, para_inteiro, texto_igual

COLUNA_NOME = "nome"


def abrir_planilha(caminho: Path, somente_leitura: bool = True):
    """Abre o .xlsx pelo conteúdo (o arquivo pode estar aberto no Excel), com as fórmulas (não os valores)."""
    caminho = Path(caminho)
    try:
        conteudo = caminho.read_bytes()
    except FileNotFoundError:
        raise ErroLeitura(f"Arquivo não encontrado: {caminho}") from None
    except PermissionError:
        raise ErroLeitura(f"{caminho.name}: o arquivo está bloqueado por outro programa. Feche e tente de novo.") from None
    try:
        with warnings.catch_warnings():
            # a planilha real tem uma área de impressão quebrada (#N/A) desde antes: o openpyxl só avisa e segue
            warnings.filterwarnings("ignore", message="Print area cannot be set", category=UserWarning)
            return openpyxl.load_workbook(io.BytesIO(conteudo), read_only=somente_leitura, data_only=False)
    except (zipfile.BadZipFile, KeyError, OSError, ValueError) as erro:
        raise ErroLeitura(f"{caminho.name}: não foi possível abrir como planilha .xlsx ({erro}).") from None


def _texto(valor) -> str:
    return " ".join(str(valor).split()) if valor is not None else ""


def _vazio(valor) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip())


def linhas_da_formula(formula, coluna: str) -> list[int]:
    """As linhas da coluna `coluna` que uma fórmula cita ("=SUM(N95+N93)" na coluna N -> [95, 93])."""
    if not isinstance(formula, str) or not formula.startswith("="):
        return []
    return [int(linha) for letra, linha in cfg.RE_REFERENCIA.findall(formula) if letra == coluna]


def _aba_do_ano(livro, nome_arquivo: str) -> tuple[str, int]:
    candidatas = [(n, int(cfg.RE_ABA_ANO.match(n).group(1))) for n in livro.sheetnames if cfg.RE_ABA_ANO.match(n)]
    com_senior = [(n, ano) for n, ano in candidatas
                  if any((m := cfg.RE_ABA_SENIOR.match(s)) and int(m.group(2)) == ano for s in livro.sheetnames)]
    if not com_senior:
        raise ErroLeitura(f"{nome_arquivo}: não parece ser a Planilha HM (falta a aba do ano, ex.: \"2026\", com as "
                          "abas \"Senior MM AAAA\").")
    if len(com_senior) > 1:
        raise ErroLeitura(f"{nome_arquivo}: há mais de uma aba de ano ({', '.join(n for n, _ in com_senior)}); deixe "
                          "só a do ano que será preenchido.")
    return com_senior[0]


def _colunas_dos_titulos(valores: tuple) -> tuple[dict[str, int], dict[int, int]] | None:
    """Colunas pela linha de abertura com os títulos; None se a linha não for essa."""
    indice_evento = next((i for i, v in enumerate(valores) if texto_igual(v, cfg.PLANILHA_TITULO_EVENTO)), None)
    if indice_evento is None:
        return None
    colunas = {cfg.PLANILHA_TITULO_EVENTO: indice_evento + 1, COLUNA_NOME: indice_evento + 2}
    for titulo in (cfg.PLANILHA_TITULO_CONCATENO, cfg.PLANILHA_TITULO_CODIGO, cfg.PLANILHA_TITULO_CENTRO):
        indice = next((i for i, v in enumerate(valores) if texto_igual(v, titulo)), None)
        if indice is None:
            return None
        colunas[titulo] = indice + 1
    meses = {}
    for numero, nome in enumerate(cfg.NOMES_MESES, start=1):
        indice = next((i for i, v in enumerate(valores) if texto_igual(v, nome)), None)
        if indice is None:
            return None
        meses[numero] = indice + 1
    return colunas, meses


def ler_planilha(caminho: Path) -> Planilha:
    """Lê a estrutura da Planilha HM. ErroLeitura se não for a Planilha HM."""
    caminho = Path(caminho)
    livro = abrir_planilha(caminho)
    try:
        aba_ano, ano = _aba_do_ano(livro, caminho.name)
        linhas = [tuple(v) for v in livro[aba_ano].iter_rows(values_only=True)]
        planilha = _ler_aba_do_ano(caminho.name, aba_ano, ano, linhas)
        for nome in livro.sheetnames:
            achado = cfg.RE_ABA_SENIOR.match(nome)
            if achado and int(achado.group(2)) == ano and 1 <= int(achado.group(1)) <= 12:
                planilha.seniors[int(achado.group(1))] = _ler_senior(nome, int(achado.group(1)), livro[nome],
                                                                     planilha.avisos)
    finally:
        livro.close()
    faltam = [cfg.NOME_ABA_SENIOR.format(mes=m, ano=ano) for m in range(1, 13) if m not in planilha.seniors]
    if faltam:
        planilha.avisos.append(Aviso(caminho.name, f"Faltam as abas: {', '.join(faltam)}.", erro=True))
    return planilha


def _ler_aba_do_ano(arquivo: str, aba: str, ano: int, linhas: list[tuple]) -> Planilha:
    titulos = None
    for numero, valores in enumerate(linhas, start=1):
        titulos = _colunas_dos_titulos(valores)
        if titulos:
            linha_titulos = numero
            break
    if titulos is None:
        raise ErroLeitura(f"{arquivo}: na aba \"{aba}\", não foi encontrada a linha de títulos (EVENTO, Concateno, "
                          "Cód., Centros de Custos e os meses).")
    colunas, meses = titulos
    planilha = Planilha(arquivo, ano, aba, linha_titulos, colunas, meses)

    def avisar(numero, mensagem, erro=False):
        planilha.avisos.append(Aviso(f"{arquivo} aba {aba} linha {numero}", mensagem, erro))

    def celula(valores, coluna):
        return valores[coluna - 1] if coluna - 1 < len(valores) else None

    secao: Secao | None = None
    evento: LinhaEvento | None = None
    vistos: dict[int, int] = {}
    for numero in range(linha_titulos, len(linhas) + 1):
        valores = linhas[numero - 1]
        col_evento = celula(valores, colunas[cfg.PLANILHA_TITULO_EVENTO])
        nome = _texto(celula(valores, colunas[COLUNA_NOME]))
        codigo = celula(valores, colunas[cfg.PLANILHA_TITULO_CODIGO])

        if texto_igual(col_evento, cfg.PLANILHA_TITULO_EVENTO):
            secao, evento = Secao(nome, numero), None
            planilha.secoes.append(secao)
            continue
        if texto_igual(col_evento, cfg.PLANILHA_TEXTO_LOTE):
            planilha.linha_lote = numero
            planilha.lote_por_mes = {m: celula(valores, c) for m, c in meses.items()
                                     if not _vazio(celula(valores, c))}
            secao = evento = None
            continue
        numero_evento = para_inteiro(col_evento)
        if numero_evento is not None:
            if secao is None:
                avisar(numero, f"Evento {numero_evento} fora de uma seção: ignorado.", erro=True)
                continue
            if _vazio(codigo) and evento is not None and evento.numero == numero_evento:
                # logo abaixo do evento, com o Cód. vazio: linha de CC sem código (ex.: "A Classificar")
                evento.ccs.append(LinhaCC("", _texto(celula(valores, colunas[cfg.PLANILHA_TITULO_CENTRO])), numero))
            elif _vazio(codigo):
                if numero_evento in vistos:
                    avisar(numero, f"O evento {numero_evento} já aparece na linha {vistos[numero_evento]}.", erro=True)
                vistos.setdefault(numero_evento, numero)
                evento = LinhaEvento(numero_evento, nome, numero)
                secao.eventos.append(evento)
            elif evento is not None and evento.numero == numero_evento:
                evento.ccs.append(LinhaCC(str(para_inteiro(codigo) if para_inteiro(codigo) is not None else
                                              _texto(codigo)),
                                          _texto(celula(valores, colunas[cfg.PLANILHA_TITULO_CENTRO])), numero))
            else:
                avisar(numero, f"Centro de custo {_texto(codigo)} do evento {numero_evento} fora da linha do evento: "
                               "ignorado.", erro=True)
            continue
        if _vazio(col_evento) and nome:
            if texto_igual(nome, cfg.PLANILHA_TEXTO_TOTAL_GERAL):
                planilha.linha_total_geral = numero
                planilha.linhas_no_total_geral_mes = _linhas_citadas_por_mes(valores, meses)
                planilha.linhas_no_total_geral = _uniao(planilha.linhas_no_total_geral_mes)
                secao = evento = None
            elif secao is not None and secao.linha_total is None:
                secao.linha_total, secao.nome_total = numero, nome
                secao.linhas_no_total_mes = _linhas_citadas_por_mes(valores, meses)
                secao.linhas_no_total = _uniao(secao.linhas_no_total_mes)
                secao, evento = None, None
            elif numero > linha_titulos and planilha.linha_total_geral is None:
                avisar(numero, f"Linha \"{nome}\" fora de uma seção: ignorada.")
            continue
        if not _vazio(col_evento):
            avisar(numero, f"Linha não reconhecida (\"{_texto(col_evento)}\"): ignorada.")

    if planilha.linha_lote is not None:
        diferenca = planilha.linha_lote + 1
        if diferenca <= len(linhas) and linhas_da_formula(
                celula(linhas[diferenca - 1], meses[1]), openpyxl.utils.get_column_letter(meses[1])) == [
                planilha.linha_total_geral, planilha.linha_lote]:
            planilha.linha_diferenca = diferenca
    _conferir_estrutura(planilha, avisar, arquivo, aba)
    return planilha


def _linhas_citadas_por_mes(valores: tuple, meses: dict[int, int]) -> dict[int, list[int]]:
    """As linhas que a fórmula de um total soma, mês a mês. Um evento que começou no meio do ano pode faltar
    nos meses anteriores (ex.: o total dos FIXOS de janeiro/2026 não tem a linha 255): é normal."""
    return {mes: linhas_da_formula(valores[coluna - 1] if coluna - 1 < len(valores) else None,
                                   openpyxl.utils.get_column_letter(coluna))
            for mes, coluna in meses.items()}


def _uniao(por_mes: dict[int, list[int]]) -> list[int]:
    return sorted({linha for linhas in por_mes.values() for linha in linhas})


def _conferir_estrutura(planilha: Planilha, avisar, arquivo: str, aba: str) -> None:
    if planilha.linha_total_geral is None:
        planilha.avisos.append(Aviso(f"{arquivo} aba {aba}", "Linha \"TOTAL GERAL\" não encontrada.", erro=True))
    if planilha.linha_lote is None:
        planilha.avisos.append(Aviso(f"{arquivo} aba {aba}", "Linha \"LOTE REPASSE\" não encontrada.", erro=True))
    elif planilha.linha_diferenca is None:
        avisar(planilha.linha_lote + 1, "A linha abaixo do LOTE REPASSE não é \"TOTAL GERAL − LOTE REPASSE\".")
    for secao in planilha.secoes:
        if secao.linha_total is None:
            if secao.eventos:
                avisar(secao.linha, f"Seção \"{secao.nome}\" sem linha de total.", erro=True)
            continue
        if sorted(secao.linhas_no_total) != sorted(secao.linhas_eventos):
            fora = sorted(set(secao.linhas_eventos) - set(secao.linhas_no_total))
            sobra = sorted(set(secao.linhas_no_total) - set(secao.linhas_eventos))
            avisar(secao.linha_total, f"O total da seção \"{secao.nome}\" não soma exatamente as linhas de evento"
                                      + (f"; faltam as linhas {fora}" if fora else "")
                                      + (f"; soma linhas que não são de evento: {sobra}" if sobra else "") + ".",
                   erro=True)
    totais = [s.linha_total for s in planilha.secoes if s.linha_total is not None]
    if planilha.linha_total_geral is not None and sorted(planilha.linhas_no_total_geral) != sorted(totais):
        avisar(planilha.linha_total_geral, "O TOTAL GERAL não soma exatamente as linhas de total das seções.",
               erro=True)


def _ler_senior(nome: str, mes: int, aba, avisos: list[Aviso]) -> AbaSenior:
    senior = AbaSenior(nome, mes)
    linhas = list(aba.iter_rows(values_only=True))
    titulos = linhas[0] if linhas else ()
    colunas = {t: next((i for i, v in enumerate(titulos) if texto_igual(v, t)), None) for t in cfg.SENIOR_TITULOS}
    if any(c is None for c in colunas.values()):
        faltam = [t for t, c in colunas.items() if c is None]
        avisos.append(Aviso(f"aba {nome}", f"Títulos não encontrados na linha 1: {', '.join(faltam)}.", erro=True))
        return senior
    def celula(valores, titulo):
        indice = colunas[titulo]
        return valores[indice] if indice < len(valores) else None

    for numero, valores in enumerate(linhas[1:], start=2):
        if not _vazio(celula(valores, cfg.SENIOR_TITULOS[0])):
            senior.linhas_dados += 1
            evento = para_inteiro(celula(valores, cfg.SENIOR_TITULOS[0]))
            valor = para_decimal(celula(valores, cfg.SENIOR_TITULOS[3]))
            if evento is not None and valor is not None:
                codigo = celula(valores, cfg.SENIOR_TITULOS[1])
                codigo = str(para_inteiro(codigo)) if para_inteiro(codigo) is not None else _texto(codigo)
                senior.valores[evento] = senior.valores.get(evento, ZERO) + valor
                senior.valores_cc[(evento, codigo)] = senior.valores_cc.get((evento, codigo), ZERO) + valor
        for titulo in cfg.SENIOR_TITULOS[4:]:            # Concateno, Conf., Conf.1
            valor = celula(valores, titulo)
            if isinstance(valor, str) and valor.startswith("="):
                senior.ultima_formula[titulo] = numero
    return senior
