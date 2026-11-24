"""
Pareamento Balancete × repasse pelo nome do terceiro (ESPECIFICACAO seção 18.2).

1. Os repasses do mesmo terceiro (nome igual sem acento, maiúsculas, pontuação e "Ltda", "S/S"...)
   são juntados num só, somando todos os grupos (Administrativo + Deslocamento + Produção Médica).
2. Os terceiros são pareados com as contas do balancete com a MESMA regra da Conciliação Fornecedores
   (fornecedores.pareamento.parear): guloso por nome (nota ≥ 0,60), cadastro duplicado somado
   (nota ≥ 0,85) e, entre as sobras, mesmo valor + nome minimamente parecido (nota ≥ 0,40).
3. Situação: OK (diferença zero), DIVERGENTE, SÓ NO BALANCETE, SÓ NO REPASSE.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from modulos.honorarios_medicos.fornecedores.modelos import FornecedorFinanceiro
from modulos.honorarios_medicos.fornecedores.modelos import PAREAMENTO_VALOR as PAREAMENTO_VALOR_FORNECEDORES
from modulos.honorarios_medicos.fornecedores.pareamento import normalizar_nome, parear
from modulos.honorarios_medicos.ames.modelos import (
    PAREAMENTO_NOME,
    PAREAMENTO_VALOR,
    SITUACAO_DIVERGENTE,
    SITUACAO_OK,
    SITUACAO_SO_BALANCETE,
    SITUACAO_SO_REPASSE,
    ContaHonorario,
    LinhaHonorario,
    Repasse,
    Terceiro,
)


def agrupar_terceiros(repasses: list[Repasse]) -> list[Terceiro]:
    por_chave: dict[str, Terceiro] = {}
    for repasse in repasses:
        chave = normalizar_nome(repasse.terceiro) or repasse.terceiro.casefold()
        if chave not in por_chave:
            por_chave[chave] = Terceiro(nome=repasse.terceiro)
        por_chave[chave].repasses.append(repasse)
    return list(por_chave.values())


@dataclass
class PareamentoHonorarios:
    linhas: list[LinhaHonorario] = field(default_factory=list)
    duplicados: list[LinhaHonorario] = field(default_factory=list)
    por_valor: list[LinhaHonorario] = field(default_factory=list)


def parear_honorarios(contas: list[ContaHonorario], terceiros: list[Terceiro]) -> PareamentoHonorarios:
    # adaptador: cada terceiro vira um "fornecedor" com saldo = repasse bruto
    adaptados = [FornecedorFinanceiro(nome=t.nome, saldo=t.bruto) for t in terceiros]
    terceiro_de = {id(a): t for a, t in zip(adaptados, terceiros)}
    resultado = PareamentoHonorarios()
    for linha in parear(contas, adaptados).linhas:
        nova = LinhaHonorario(
            situacao="", conta=linha.conta,
            terceiros=[terceiro_de[id(f)] for f in linha.financeiros],
            nota=linha.nota,
            pareamento=(PAREAMENTO_VALOR if linha.pareamento == PAREAMENTO_VALOR_FORNECEDORES
                        else PAREAMENTO_NOME if linha.pareamento else ""),
        )
        if nova.conta is None:
            nova.situacao = SITUACAO_SO_REPASSE
        elif not nova.terceiros:
            nova.situacao = SITUACAO_SO_BALANCETE
        else:
            nova.situacao = SITUACAO_OK if nova.diferenca == 0 else SITUACAO_DIVERGENTE
            if len(nova.terceiros) > 1:
                resultado.duplicados.append(nova)
            if nova.pareamento == PAREAMENTO_VALOR:
                resultado.por_valor.append(nova)
        resultado.linhas.append(nova)
    return resultado
