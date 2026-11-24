"""
Leitores dos dois relatórios do Tasy da Conciliação Honorários.

Os dois saem do Tasy como .xls que na verdade é TEXTO separado por tabulação (Windows-1252);
.xlsx e .xls de verdade também são aceitos (fornecedores.leitores.ler_planilha). O programa
reconhece cada relatório pelo CONTEÚDO, não pelo nome do arquivo (no exemplo de set/2026 os nomes
vieram trocados: "Rel HM.xls" era o balancete e "Balancete (2).xls" o repasse).

Balancete (WEXE001), o mesmo da Conciliação Fornecedores:
- 1ª linha: a unidade; "Mês Referência:" → o mês; cabeçalho Código · Classificação · Descrição ·
  Saldo Anterior · Débitos · Créditos · Saldo Atual (valores lidos NA ORDEM do cabeçalho).
- A conta de total (sintética) é a que tem contas "filhas" (classificação dela + ".") no balancete:
  no AME, 2132 – 2.01.03.02 HONORARIOS MEDICOS A PAGAR - PJ. Serve também para a Hospital Exemplo, que
  pode ter outro código. Mais de uma conta com filhas → fica a que tem "honor" na descrição.
- Validação: soma do Saldo Atual das filhas = Saldo Atual da sintética (senão ATENÇÃO).

SCF – Repasse Sintético (CATE6095):
- Topo de cada página: título, unidade ("AME - Cidade Delta") e o cabeçalho Terceiro · Nr Repasse ·
  Dt Ref · Status · Vl repasse · Vl. Líquido (a posição das colunas muda de página para página, então
  os valores são lidos NA ORDEM do cabeçalho).
- Linha só com um texto depois do cabeçalho = começo de um grupo ("Produção Médica - Ame São
  Carlos" → "Produção Médica"); o grupo continua na página seguinte até aparecer outro.
- "Total - <grupo>(n)" e "Total(n)" → conferência da leitura (quantidade, bruto e líquido).
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path

from modulos.honorarios_medicos.fornecedores.avisos import Aviso
from modulos.honorarios_medicos.fornecedores.leitores import (
    COLUNAS_BALANCETE,
    ROTULO_MES,
    ArquivoIlegivel,
    _data,
    _eh_rodape,
    _identificador,
    _juntar_espacos,
    _mes,
    _preenchidas,
    dinheiro,
    ler_planilha,
    nome_curto_unidade,
    reais,
)
from modulos.honorarios_medicos.ames.modelos import ContaHonorario, LeituraBalancete, LeituraRepasse, Repasse, TotalGrupo

COLUNAS_REPASSE = ["Terceiro", "Nr Repasse", "Dt Ref", "Status", "Vl repasse", "Vl. Líquido"]

RELATORIO_BALANCETE = "balancete"
RELATORIO_REPASSE = "repasse"
NOMES = {
    RELATORIO_BALANCETE: "o Balancete (Tasy 865)",
    RELATORIO_REPASSE: "o relatório SCF – Repasse Sintético (repasse médico)",
}
CAMPOS = {
    RELATORIO_BALANCETE: "Balancete",
    RELATORIO_REPASSE: "Repasse médico",
}

_REGEX_TOTAL = re.compile(r"^Total(?:\s*-\s*(.*?))?\s*\((\d+)\)\s*$")

__all__ = ["ler_balancete", "ler_repasse", "identificar", "nome_curto_unidade", "reais",
           "ArquivoIlegivel"]


def _chave(texto: object) -> str:
    return re.sub(r"\s+", " ", str(texto)).strip().casefold()


def _eh_cabecalho_repasse(celulas: list[object]) -> bool:
    chaves = {_chave(c) for c in celulas if isinstance(c, str)}
    return all(_chave(nome) in chaves for nome in COLUNAS_REPASSE)


def identificar(linhas) -> str | None:
    if any(_eh_cabecalho_repasse(_preenchidas(linha)) for linha in linhas[:15]):
        return RELATORIO_REPASSE
    textos = " ".join(str(c) for linha in linhas[:40] for c in linha if isinstance(c, str)).casefold()
    if "wctb865" in textos or any(_preenchidas(l) == ["Balancete"] for l in linhas[:10]):
        return RELATORIO_BALANCETE
    return None


def _erro_relatorio_errado(esperado: str, encontrado: str | None) -> str | None:
    if encontrado == esperado:
        return None
    if encontrado is None:
        return f"Este arquivo não parece ser {NOMES[esperado]}. Confira se escolheu o relatório certo."
    return (f"Este arquivo é {NOMES[encontrado]}, não {NOMES[esperado]}. "
            f"Escolha-o no campo \"{CAMPOS[encontrado]}\".")


def _abrir(caminho: Path, esperado: str, leitura) -> list | None:
    try:
        linhas = ler_planilha(caminho)
    except ArquivoIlegivel as erro:
        leitura.erro = str(erro)
        return None
    erro = _erro_relatorio_errado(esperado, identificar(linhas))
    if erro:
        leitura.erro = erro
        return None
    return linhas


# ---------------------------------------------------------------------
# Balancete
# ---------------------------------------------------------------------
def ler_balancete(caminho: Path) -> LeituraBalancete:
    caminho = Path(caminho)
    leitura = LeituraBalancete(arquivo=caminho.name)
    todas = ler_todas_as_contas(caminho, leitura)
    if todas is None:
        return leitura

    def filhas(conta: ContaHonorario) -> list[ContaHonorario]:
        return [c for c in todas if c.classificacao.startswith(conta.classificacao + ".")]

    sinteticas = [c for c in todas if filhas(c)]
    if len(sinteticas) > 1:
        # contas sintéticas umas dentro das outras: fica a mais de dentro com "honor" (ou a mais de dentro)
        com_honor = [c for c in sinteticas if "honor" in c.descricao.casefold()] or sinteticas
        sinteticas = [max(com_honor, key=lambda c: c.classificacao.count("."))]
    if not sinteticas:
        leitura.erro = ("O balancete não traz a conta de Honorários médicos a pagar com as contas dos "
                        "médicos/clínicas (no AME, 2132 – 2.01.03.02). Confira se escolheu o balancete certo.")
        return leitura
    leitura.total = sinteticas[0]
    leitura.contas = filhas(leitura.total)
    fora = [c for c in todas if c is not leitura.total and c not in leitura.contas]
    if fora:
        leitura.avisos.append(Aviso(
            arquivo=leitura.arquivo,
            mensagem=f"{len(fora)} conta(s) do balancete fora da conta {leitura.total.codigo} – "
                     f"{leitura.total.descricao} não entraram na conciliação: "
                     + ", ".join(f"{c.codigo} {c.descricao}" for c in fora[:5])
                     + ("..." if len(fora) > 5 else "") + ".",
        ))
    conferir_soma_das_filhas(leitura, leitura.total, leitura.contas)
    if leitura.mes is None:
        leitura.avisos.append(Aviso(arquivo=leitura.arquivo,
                                    mensagem="Mês Referência não encontrado no balancete."))
    return leitura


def conferir_soma_das_filhas(leitura, total: ContaHonorario, contas: list[ContaHonorario]) -> None:
    soma = sum((c.saldo_atual for c in contas), Decimal(0))
    if soma != total.saldo_atual:
        leitura.avisos.append(Aviso(
            arquivo=leitura.arquivo,
            mensagem=f"ATENÇÃO: a soma das contas dos médicos/clínicas ({reais(soma)}) não bate com o "
                     f"total da conta {total.codigo} ({reais(total.saldo_atual)}). "
                     "A leitura pode estar incompleta.",
        ))


def ler_todas_as_contas(caminho: Path, leitura) -> list[ContaHonorario] | None:
    """Todas as contas do balancete, na ordem do arquivo (também usado pela Honorários Hospital Exemplo).

    Preenche leitura.unidade e leitura.mes; arquivo ilegível, trocado ou sem cabeçalho → leitura.erro e None.
    """
    linhas = _abrir(Path(caminho), RELATORIO_BALANCETE, leitura)
    if linhas is None:
        return None

    ordem: list[str] | None = None
    anterior: list[object] = []
    todas: list[ContaHonorario] = []
    for numero, linha in enumerate(linhas, start=1):
        celulas = _preenchidas(linha)
        if not celulas:
            continue
        if not leitura.unidade and celulas == ["Balancete"] and anterior and isinstance(anterior[0], str):
            leitura.unidade = _juntar_espacos(anterior[0])
        if leitura.mes is None and ROTULO_MES in celulas:
            depois = celulas[celulas.index(ROTULO_MES) + 1:]
            if depois:
                leitura.mes = _mes(depois[0])
        anterior = celulas

        if all(c in celulas for c in COLUNAS_BALANCETE):
            ordem = [c for c in celulas if isinstance(c, str)]
            continue
        if ordem is None or _eh_rodape(celulas) or len(celulas) != len(ordem):
            continue
        campos = dict(zip(ordem, celulas))
        try:
            todas.append(ContaHonorario(
                codigo=_identificador(campos["Código"]),
                classificacao=str(campos["Classificação"]).strip(),
                descricao=_juntar_espacos(campos["Descrição"]),
                saldo_anterior=dinheiro(campos["Saldo Anterior"]),
                debitos=dinheiro(campos["Débitos"]),
                creditos=dinheiro(campos["Créditos"]),
                saldo_atual=dinheiro(campos["Saldo Atual"]),
            ))
        except ValueError as erro_valor:
            leitura.avisos.append(Aviso(
                arquivo=leitura.arquivo,
                mensagem=f"Linha {numero}: conta {campos.get('Código')} com valor não reconhecido "
                         f"({erro_valor}); ela não foi lida.",
            ))

    if ordem is None:
        leitura.erro = ("Cabeçalho do balancete não encontrado (colunas esperadas: "
                        + ", ".join(COLUNAS_BALANCETE) + ").")
        return None
    return todas


# ---------------------------------------------------------------------
# SCF – Repasse Sintético
# ---------------------------------------------------------------------
def _nome_do_grupo(texto: str) -> str:
    """"Produção Médica - Ame Cidade Delta" → "Produção Médica".

    Corta no primeiro " - " seguido do nome da unidade ("Ame...", "Hospital Exemplo...", "Fund...");
    sem isso, no último " - ".
    """
    texto = _juntar_espacos(texto)
    partes = texto.split(" - ")
    for posicao in range(1, len(partes)):
        if partes[posicao].casefold().startswith(("ame", "hospital exemplo", "fund", "scm")):
            return " - ".join(partes[:posicao]).strip()
    return " - ".join(partes[:-1]).strip() if len(partes) > 1 else texto


def ler_repasse(caminho: Path) -> LeituraRepasse:
    caminho = Path(caminho)
    leitura = LeituraRepasse(arquivo=caminho.name)
    linhas = _abrir(caminho, RELATORIO_REPASSE, leitura)
    if linhas is None:
        return leitura

    ordem: list[str] | None = None
    no_topo = True                       # entre o título da página e o cabeçalho
    grupo = ""
    meses: Counter[date] = Counter()
    for numero, linha in enumerate(linhas, start=1):
        celulas = _preenchidas(linha)
        if not celulas:
            continue
        if _eh_rodape(celulas):
            no_topo = True
            continue
        if _eh_cabecalho_repasse(celulas):
            ordem = [_juntar_espacos(c) for c in celulas if isinstance(c, str)]
            no_topo = False
            continue
        if no_topo:
            # título ("SCF - Repasse Sintetico AME") e unidade ("AME - Cidade Delta")
            if len(celulas) == 1 and isinstance(celulas[0], str) and not leitura.unidade \
                    and "repasse" not in celulas[0].casefold():
                leitura.unidade = _juntar_espacos(celulas[0])
            continue

        primeiro = _juntar_espacos(celulas[0]) if isinstance(celulas[0], str) else ""
        total = _REGEX_TOTAL.match(primeiro)
        if total and len(celulas) == 3:
            try:
                conferencia = TotalGrupo(quantidade=int(total.group(2)), bruto=dinheiro(celulas[1]),
                                         liquido=dinheiro(celulas[2]))
            except ValueError:
                continue
            if total.group(1) is None:
                leitura.total_geral = conferencia
            else:
                leitura.totais_grupo[_nome_do_grupo(total.group(1))] = conferencia
            continue
        if len(celulas) == 1 and primeiro:
            grupo = _nome_do_grupo(primeiro)
            if grupo not in leitura.grupos:
                leitura.grupos.append(grupo)
            continue
        if ordem is None or len(celulas) != len(ordem):
            leitura.avisos.append(Aviso(
                arquivo=leitura.arquivo,
                mensagem=f"Linha {numero}: linha não reconhecida ({' | '.join(str(c) for c in celulas)}); "
                         "ela não foi lida.",
            ))
            continue
        campos = {_chave(nome): valor for nome, valor in zip(ordem, celulas)}
        try:
            repasse = Repasse(
                grupo=grupo or "Sem grupo",
                terceiro=_juntar_espacos(campos[_chave("Terceiro")]),
                numero=_identificador(campos[_chave("Nr Repasse")]),
                data_referencia=_data(campos[_chave("Dt Ref")]),
                status=str(campos[_chave("Status")]).strip(),
                bruto=dinheiro(campos[_chave("Vl repasse")]),
                liquido=dinheiro(campos[_chave("Vl. Líquido")]),
            )
        except ValueError as erro_valor:
            leitura.avisos.append(Aviso(
                arquivo=leitura.arquivo,
                mensagem=f"Linha {numero}: repasse de \"{campos.get(_chave('Terceiro'), '?')}\" com valor "
                         f"não reconhecido ({erro_valor}); ele não foi lido.",
            ))
            continue
        if not grupo and "Sem grupo" not in leitura.grupos:
            leitura.grupos.append("Sem grupo")
        leitura.repasses.append(repasse)
        if repasse.data_referencia:
            meses[date(repasse.data_referencia.year, repasse.data_referencia.month, 1)] += 1

    if ordem is None:
        leitura.erro = ("Cabeçalho do repasse não encontrado (colunas esperadas: "
                        + ", ".join(COLUNAS_REPASSE) + ").")
        return leitura
    if not leitura.repasses:
        leitura.erro = "Nenhum repasse encontrado no relatório."
        return leitura
    if meses:
        leitura.mes = meses.most_common(1)[0][0]
        if len(meses) > 1:
            leitura.avisos.append(Aviso(
                arquivo=leitura.arquivo,
                mensagem="O repasse tem datas de referência de mais de um mês: "
                         + ", ".join(f"{m:%m/%Y} ({n})" for m, n in sorted(meses.items())) + ".",
            ))
    _conferir_totais(leitura)
    return leitura


def _conferir_totais(leitura: LeituraRepasse) -> None:
    def conferir(rotulo: str, esperado: TotalGrupo, repasses: list[Repasse]) -> None:
        bruto = sum((r.bruto for r in repasses), Decimal(0))
        liquido = sum((r.liquido for r in repasses), Decimal(0))
        if (len(repasses), bruto, liquido) != (esperado.quantidade, esperado.bruto, esperado.liquido):
            leitura.avisos.append(Aviso(
                arquivo=leitura.arquivo,
                mensagem=f"ATENÇÃO: {rotulo}: foram lidos {len(repasses)} repasses (bruto {reais(bruto)}, "
                         f"líquido {reais(liquido)}), mas o relatório diz {esperado.quantidade} (bruto "
                         f"{reais(esperado.bruto)}, líquido {reais(esperado.liquido)}). A leitura pode "
                         "estar incompleta.",
            ))

    for grupo, esperado in leitura.totais_grupo.items():
        conferir(f"grupo {grupo}", esperado, [r for r in leitura.repasses if r.grupo == grupo])
    if leitura.total_geral is not None:
        conferir("total do relatório", leitura.total_geral, leitura.repasses)
    else:
        leitura.avisos.append(Aviso(
            arquivo=leitura.arquivo,
            mensagem="ATENÇÃO: a linha \"Total(n)\" do repasse não foi encontrada; não deu para conferir "
                     "se todos os repasses foram lidos.",
        ))
