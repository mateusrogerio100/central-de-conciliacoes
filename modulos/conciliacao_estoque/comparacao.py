"""Comparação conta a conta da EST-01 e da EST-03 (ESPECIFICACAO_ESTOQUE.md, seções 4 a 7).

As duas etapas são a mesma comparação: só muda o valor comparado, que vem da Etapa
(configuracao.ETAPAS). Diferença = saldo do balancete − saldo do SCF.

Conferências:
- cada conta sintética de grupo (1.01.04.01, .02, .03) x subtotal das analíticas do grupo;
- sintética 1.01.04 x total das analíticas;
- linha Total(...) do SCF x contas casadas + locais sem conta.
Causa provável (seção 7.2): se a diferença de um grupo é igual à soma dos locais do SCF sem
conta que têm saldo, é provável uma conta com saldo atual zero que o balancete não imprimiu.
"""

from __future__ import annotations

from decimal import Decimal

from modulos.conciliacao_estoque import configuracao
from modulos.conciliacao_estoque.casamento import casar
from modulos.conciliacao_estoque.leitor_scf import posicao_do_titulo
from modulos.conciliacao_estoque.modelos import (
    Aviso,
    BalanceteEstoque,
    ComoCasou,
    ConferenciaGrupo,
    Etapa,
    Gravidade,
    LinhaComparacao,
    RelatorioSCF,
    ResultadoCasamento,
    ResultadoComparacao,
)
from modulos.conciliacao_estoque.utilitarios import formatar_valor

ZERO = Decimal("0.00")
OBSERVACAO_LOCAL_SALDO_ZERO = "Local do Mapa do Estoque sem conta no balancete — saldo zero"
OBSERVACAO_LOCAL_COM_SALDO = "Local do Mapa do Estoque sem conta no balancete — COM SALDO"
# decisão do usuário (06/10/2026): o programa só explica; a solução é gerar o balancete com as contas zeradas
RECOMENDACAO_CONTAS_ZERADAS = (
    "Recomendação: gere o balancete no Tasy com a opção de trazer as contas zeradas, "
    "para o programa identificar a conta"
)


def grupo_da_classificacao(classificacao: str) -> str:
    """1.01.04.01.0002 -> 1.01.04.01 (a conta sintética logo acima)."""
    return classificacao.rsplit(".", 1)[0]


def comparar(
    etapa: Etapa,
    balancete: BalanceteEstoque,
    scf: RelatorioSCF,
    casamento: ResultadoCasamento | None = None,
) -> ResultadoComparacao:
    if casamento is None:
        casamento = casar(balancete.analiticas, scf.locais)
    posicao = posicao_do_titulo(etapa.campo_scf)
    resultado = ResultadoComparacao(
        etapa=etapa,
        mes_referencia=balancete.mes_referencia,
        arquivo_balancete=balancete.arquivo,
        arquivo_scf=scf.arquivo,
        total_scf=scf.total_na_posicao(posicao),
    )

    def avisar(gravidade, tipo, mensagem, conta=""):
        resultado.avisos.append(Aviso(gravidade, tipo, f"{etapa.id}: {mensagem}", conta=conta))

    if balancete.mes_referencia and scf.mes_referencia and balancete.mes_referencia != scf.mes_referencia:
        avisar(Gravidade.ATENCAO, "mês diferente",
               f"Balancete de {balancete.mes_referencia} e Mapa do Estoque de {scf.mes_referencia}.")

    for par in casamento.pares:
        conta = par.conta
        resultado.contas.append(LinhaComparacao(
            grupo=grupo_da_classificacao(conta.classificacao),
            classificacao=conta.classificacao,
            codigo=conta.codigo,
            descricao_balancete=conta.descricao,
            descricao_scf=par.local.descricao if par.local else "",
            local_scf=par.local.codigo if par.local else None,
            saldo_balancete=getattr(conta, etapa.campo_balancete),
            saldo_scf=par.local.valor(posicao) if par.local else ZERO,
            como=par.como,
            observacao=par.observacao,
        ))
        if par.como == ComoCasou.SEM_PAR:
            avisar(Gravidade.ATENCAO, "conta sem par", f"Conta {conta.codigo} {conta.descricao}: {par.observacao}.",
                   str(conta.codigo))
        elif par.como == ComoCasou.NOME_EQUIVALENTE:
            avisar(Gravidade.INFO, "casada por nome",
                   f"Conta {conta.codigo} {conta.descricao} casada por nome com {par.local.descricao}: conferir.",
                   str(conta.codigo))

    for local in casamento.locais_sem_conta:
        saldo = local.valor(posicao)
        resultado.locais_sem_conta.append(LinhaComparacao(
            grupo="",
            classificacao="",
            codigo=None,
            descricao_balancete="",
            descricao_scf=local.descricao,
            local_scf=local.codigo,
            saldo_balancete=ZERO,
            saldo_scf=saldo,
            como=ComoCasou.SEM_PAR,
            observacao=OBSERVACAO_LOCAL_COM_SALDO if saldo != 0 else OBSERVACAO_LOCAL_SALDO_ZERO,
        ))
        if saldo != 0:
            avisar(Gravidade.ATENCAO, "local com saldo sem conta",
                   f"{local.descricao}: {etapa.campo_scf} {formatar_valor(saldo)} no Mapa do Estoque e nenhuma conta "
                   "no balancete.", str(local.codigo))

    _conferir_grupos(resultado, balancete, etapa, avisar)
    _conferir_totais(resultado, balancete, etapa, avisar)
    return resultado


def _conferir_grupos(resultado, balancete, etapa, avisar):
    raiz = configuracao.PREFIXO_ESTOQUE
    classificacoes = {c.classificacao for c in balancete.sinteticas if c.classificacao != raiz}
    classificacoes |= {l.grupo for l in resultado.contas}
    sem_conta_com_saldo = sum((l.saldo_scf for l in resultado.locais_sem_conta if l.saldo_scf != 0), ZERO)

    for classificacao in sorted(classificacoes):
        sintetica = balancete.sintetica(classificacao)
        grupo = ConferenciaGrupo(
            classificacao=classificacao,
            descricao=sintetica.descricao if sintetica else "",
            saldo_sintetica=getattr(sintetica, etapa.campo_balancete) if sintetica else None,
            subtotal=sum((l.saldo_balancete for l in resultado.contas if l.grupo == classificacao), ZERO),
        )
        resultado.grupos.append(grupo)
        if grupo.diferenca == 0:
            continue
        if sintetica is None:
            mensagem = f"Grupo {classificacao}: conta sintética não encontrada no balancete."
        else:
            mensagem = (f"Grupo {classificacao} {grupo.descricao}: saldo da sintética "
                        f"{formatar_valor(grupo.saldo_sintetica)} diferente do subtotal das contas "
                        f"{formatar_valor(grupo.subtotal)} (diferença {formatar_valor(grupo.diferenca)}).")
        if sem_conta_com_saldo != 0 and grupo.diferenca == sem_conta_com_saldo:
            grupo.causa_provavel = (
                f"Diferença no grupo {classificacao} igual ao saldo de local(is) do Mapa do Estoque sem conta: "
                "provável conta com saldo atual zero que o balancete não imprime"
            )
            mensagem += f" {grupo.causa_provavel}. {RECOMENDACAO_CONTAS_ZERADAS}."
        avisar(Gravidade.ATENCAO, "grupo com diferença", mensagem, classificacao)


def _conferir_totais(resultado, balancete, etapa, avisar):
    raiz = balancete.sintetica(configuracao.PREFIXO_ESTOQUE)
    if raiz is None:
        avisar(Gravidade.ATENCAO, "sintética não encontrada",
               f"Conta sintética {configuracao.PREFIXO_ESTOQUE} não encontrada no balancete.")
    else:
        resultado.saldo_sintetica_raiz = getattr(raiz, etapa.campo_balancete)
        diferenca = resultado.saldo_sintetica_raiz - resultado.total_balancete
        # a diferença de um grupo já foi avisada; aqui só a que os grupos não explicam
        if diferenca != sum((g.diferenca for g in resultado.grupos), ZERO):
            avisar(Gravidade.ATENCAO, "total do balancete",
                   f"Sintética {configuracao.PREFIXO_ESTOQUE} {formatar_valor(resultado.saldo_sintetica_raiz)} "
                   f"diferente do total das contas {formatar_valor(resultado.total_balancete)}.")

    if resultado.total_scf is None:
        avisar(Gravidade.ERRO, "total do Mapa do Estoque", "Linha Total(...) do Mapa do Estoque não lida; total do Mapa do Estoque não conferido.")
    elif resultado.total_scf != resultado.total_scf_das_linhas:
        avisar(Gravidade.ERRO, "total do Mapa do Estoque",
               f"Linha Total do Mapa do Estoque {formatar_valor(resultado.total_scf)} diferente da soma dos locais "
               f"lidos {formatar_valor(resultado.total_scf_das_linhas)} (algum local não foi lido).")
