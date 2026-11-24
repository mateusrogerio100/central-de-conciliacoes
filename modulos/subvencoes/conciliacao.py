"""Regras de negócio R1–R9: decide o Saldo Patrimônio e o Saldo Contábil de cada linha.

Este módulo não abre nem grava arquivos; recebe tudo já lido.

- R1  planilha -> balancete: pelo código (coluna "Conta Contábil" = Código do balancete).
- R2  balancete -> patrimônio: pela descrição da conta = nome da conta no patrimônio (normalizados).
- R3  Saldo Contábil = Saldo Atual do balancete.
- R4  Saldo Patrimônio = soma dos bens da conta.
- R5  sem valor -> 0 (fora do balancete: os dois; sem conta no patrimônio: Saldo Patrimônio).
- R7  conta analítica do balancete sem linha em nenhuma planilha -> aviso (exceto Doações).
- R8  contas do patrimônio não usadas -> só aparecem como "não usada".
- R9  soma do Saldo Contábil de cada aba = Saldo Atual da sintética que agrupa as contas.

Casos decididos pelo usuário (fora da especificação original):
- nome de conta repetido no patrimônio -> Saldo Patrimônio = soma dos blocos (+ aviso do leitor
  com as linhas de cada bloco);
- mesmo código em mais de uma linha das planilhas -> todas as linhas são preenchidas + aviso.
"""

from __future__ import annotations

from decimal import Decimal

from modulos.subvencoes import configuracao
from modulos.subvencoes.modelos import (
    Aviso,
    Balancete,
    ConferenciaAba,
    ContaPatrimonio,
    Gravidade,
    PlanilhaLida,
    RelatorioPatrimonio,
    ResultadoConciliacao,
    ResultadoLinha,
)
from modulos.subvencoes.utilitarios import normalizar_texto

ZERO = Decimal("0.00")

SITUACAO_USADA = "usada"
SITUACAO_NAO_USADA = "não usada"
SITUACAO_TOTAL_DIVERGENTE = "total divergente"
SITUACAO_CABECALHO_AUSENTE = "cabeçalho ausente"


def conciliar(
    balancete: Balancete,
    patrimonio: RelatorioPatrimonio,
    planilhas_lidas: list[PlanilhaLida],
) -> ResultadoConciliacao:
    resultado = ResultadoConciliacao()
    contas_patrimonio = _indexar_patrimonio(patrimonio)
    codigos_repetidos = _avisar_codigos_repetidos(planilhas_lidas, resultado)

    for planilha in planilhas_lidas:
        for aba in planilha.abas:
            linhas_aba = []
            for linha in aba.linhas:
                resultado_linha = _conciliar_linha(
                    planilha.arquivo, aba.nome, linha, balancete, contas_patrimonio, resultado
                )
                if linha.conta_contabil in codigos_repetidos:
                    resultado_linha.observacoes.append("código repetido em outra linha das planilhas")
                linhas_aba.append(resultado_linha)
                resultado.linhas.append(resultado_linha)
            _conferir_aba(planilha.arquivo, aba.nome, linhas_aba, balancete, resultado)

    _avisar_contas_novas(balancete, planilhas_lidas, resultado)
    return resultado


def situacao_conta_patrimonio(conta: ContaPatrimonio, resultado: ResultadoConciliacao) -> str:
    """Situação para a aba "Patrimônio" do relatório. Divergências têm prioridade sobre "usada"."""
    if conta.cabecalho_ausente:
        return SITUACAO_CABECALHO_AUSENTE
    if conta.total_divergente or conta.quantidade_divergente:
        return SITUACAO_TOTAL_DIVERGENTE
    if normalizar_texto(conta.nome) in resultado.contas_patrimonio_usadas:
        return SITUACAO_USADA
    return SITUACAO_NAO_USADA


# ---------------------------------------------------------------------------


def _indexar_patrimonio(patrimonio: RelatorioPatrimonio) -> dict[str, list[ContaPatrimonio]]:
    """Nome normalizado -> blocos com esse nome.

    Nome repetido no relatório (decisão do usuário): o Saldo Patrimônio é a soma dos blocos.
    O leitor do patrimônio já avisa a repetição, com as linhas de cada bloco.
    """
    indice: dict[str, list[ContaPatrimonio]] = {}
    for conta in patrimonio.contas:
        indice.setdefault(normalizar_texto(conta.nome), []).append(conta)
    return indice


def _avisar_codigos_repetidos(planilhas_lidas, resultado):
    """Mesmo código em mais de uma linha (decisão do usuário): todas são preenchidas, com aviso."""
    ocorrencias: dict[int, list[tuple[str, str, int]]] = {}
    for planilha in planilhas_lidas:
        for aba in planilha.abas:
            for linha in aba.linhas:
                ocorrencias.setdefault(linha.conta_contabil, []).append((planilha.arquivo, aba.nome, linha.linha))
    repetidos = {codigo: locais for codigo, locais in ocorrencias.items() if len(locais) > 1}
    for codigo, locais in repetidos.items():
        onde = "; ".join(f"{arquivo} / {aba} / linha {linha}" for arquivo, aba, linha in locais)
        arquivo, aba, linha = locais[0]
        resultado.avisos.append(Aviso(
            Gravidade.ATENCAO, "código repetido nas planilhas",
            f"O código {codigo} aparece em {len(locais)} linhas: {onde}. Todas foram preenchidas com os "
            "mesmos saldos; a conferência da aba (R9) pode acusar diferença por isso.",
            arquivo=arquivo, aba=aba, linha=linha, conta=str(codigo),
        ))
    return set(repetidos)


def _conciliar_linha(arquivo, nome_aba, linha, balancete, contas_patrimonio, resultado) -> ResultadoLinha:
    def avisar(gravidade, tipo, mensagem):
        resultado.avisos.append(Aviso(gravidade, tipo, mensagem, arquivo=arquivo, aba=nome_aba,
                                      linha=linha.linha, conta=str(linha.conta_contabil)))

    resultado_linha = ResultadoLinha(
        planilha=arquivo, aba=nome_aba, linha=linha.linha, conta_contabil=linha.conta_contabil,
        convenio=linha.convenio, descricao_balancete="", saldo_patrimonio=ZERO, saldo_contabil=ZERO,
    )

    # R1 + R3
    conta_balancete = balancete.contas.get(linha.conta_contabil)
    if conta_balancete is None:
        # R5: sem descrição não dá para achar no patrimônio -> os dois saldos ficam 0.
        resultado_linha.observacoes.append("conta fora do balancete -> 0")
        avisar(Gravidade.ATENCAO, "conta fora do balancete",
               f"Código {linha.conta_contabil} ({linha.convenio}) não está no balancete; "
               "Saldo Contábil e Saldo Patrimônio = 0.")
        return resultado_linha

    resultado_linha.descricao_balancete = conta_balancete.descricao
    resultado_linha.saldo_contabil = conta_balancete.saldo_atual

    # R2 + R4
    nome = normalizar_texto(conta_balancete.descricao)
    blocos = contas_patrimonio.get(nome)
    if not blocos:
        # R5: conta no balancete sem conta no patrimônio -> Saldo Patrimônio 0.
        resultado_linha.observacoes.append("sem bens no patrimonio -> 0")
        avisar(Gravidade.ATENCAO, "conta sem bens no patrimônio",
               f"'{conta_balancete.descricao}' não tem conta com esse nome no patrimônio; "
               "Saldo Patrimônio = 0.")
        return resultado_linha

    resultado.contas_patrimonio_usadas.add(nome)
    resultado_linha.saldo_patrimonio = sum((b.soma_itens for b in blocos), ZERO)
    if len(blocos) > 1:
        resultado_linha.observacoes.append(
            f"conta repetida no patrimônio: {len(blocos)} blocos somados")
    for bloco in blocos:
        if bloco.cabecalho_ausente:
            resultado_linha.observacoes.append(
                "cabeçalho da conta ausente no patrimônio; identificada pela linha Total")
        if bloco.total_divergente:
            resultado_linha.observacoes.append(
                f"Total do sistema = {bloco.total_sistema}, mas soma dos bens = "
                f"{bloco.soma_itens} (usada a soma)")
    return resultado_linha


def _conferir_aba(arquivo, nome_aba, linhas_aba, balancete, resultado):
    """R9: as contas da aba devem pertencer a uma única sintética, cuja soma deve bater."""
    if not linhas_aba:
        return

    sinteticas = sorted({
        balancete.contas[l.conta_contabil].classificacao_pai
        for l in linhas_aba if l.conta_contabil in balancete.contas
    })
    soma = sum((l.saldo_contabil for l in linhas_aba), ZERO)
    conferencia = ConferenciaAba(planilha=arquivo, aba=nome_aba, soma_saldo_contabil=soma,
                                 classificacoes_sinteticas=sinteticas)
    resultado.conferencias_aba.append(conferencia)

    def avisar(mensagem):
        resultado.avisos.append(Aviso(Gravidade.ATENCAO, "conferência da aba não bate", mensagem,
                                      arquivo=arquivo, aba=nome_aba))

    if len(sinteticas) != 1:
        if sinteticas:
            avisar(f"As contas da aba pertencem a mais de uma conta sintética ({', '.join(sinteticas)}); "
                   "não foi possível conferir o total.")
        else:
            avisar("Nenhuma conta da aba está no balancete; não foi possível conferir o total.")
        return

    conferencia.sintetica = balancete.por_classificacao(sinteticas[0])
    if conferencia.sintetica is None:
        avisar(f"A conta sintética {sinteticas[0]} não está no balancete; não foi possível conferir o total.")
    elif not conferencia.confere:
        avisar(f"Soma do Saldo Contábil da aba = {soma}, mas o Saldo Atual de {sinteticas[0]} "
               f"({conferencia.sintetica.descricao}) é {conferencia.sintetica.saldo_atual}. "
               f"Diferença: {soma - conferencia.sintetica.saldo_atual}.")


def _avisar_contas_novas(balancete, planilhas_lidas, resultado):
    """R7: conta analítica do balancete sem linha em nenhuma planilha (exceto prefixos ignorados)."""
    codigos_planilhas = {l.conta_contabil for p in planilhas_lidas for a in p.abas for l in a.linhas}
    for conta in balancete.analiticas():
        if conta.codigo in codigos_planilhas:
            continue
        if conta.classificacao.startswith(configuracao.PREFIXOS_CLASSIFICACAO_IGNORADOS):
            continue
        resultado.avisos.append(Aviso(
            Gravidade.ATENCAO, "conta nova no balancete",
            f"A conta {conta.codigo} ({conta.classificacao} - {conta.descricao}), saldo {conta.saldo_atual}, "
            "está no balancete mas não tem linha em nenhuma planilha. Nenhuma linha foi criada.",
            arquivo=balancete.arquivo, linha=conta.linha, conta=str(conta.codigo),
        ))
