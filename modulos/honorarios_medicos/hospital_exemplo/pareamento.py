"""
Pareamento da Conciliação Honorários Hospital Exemplo (ESPECIFICACAO seção 20.2).

1. Remoção/Deslocamento primeiro: as linhas dos PDFs são juntadas por terceiro (nome igual sem acento,
   maiúsculas, pontuação e "Ltda"...) e cada terceiro é procurado pelo nome em TODAS as contas do
   balancete, PF e PJ juntas (os PDFs misturam os dois): guloso da maior nota para a menor (nota ≥ 0,60),
   uma conta por terceiro; sobra com nota ≥ 0,85 numa conta já pareada é somada a ela (o mesmo médico
   escrito de dois jeitos em dois PDFs). Pelo valor não: o valor do PDF é só uma parte do saldo.
2. Depois o Senior: o HM PF só com as contas PF e o HM PJ só com as contas PJ, comparando com o saldo
   da conta já descontado da Remoção/Deslocamento. A nota de semelhança é a da Conciliação Fornecedores
   (fornecedores.pareamento.nota_semelhanca), mas a ORDEM é outra, porque os nomes da Hospital Exemplo têm
   muitas palavras comuns ("Serviços Médicos", "Clínica Médica") que dão nota alta a clínicas
   diferentes (na planilha de ago/2026 do usuário, pares certos tinham nota 0,73 com o mesmo valor, e
   pares errados chegavam a 0,86 com valor diferente):
   a) nome bem parecido (nota ≥ 0,85), da maior nota para a menor; empate: primeiro o de mesmo valor;
   b) cadastro duplicado no Senior (nota ≥ 0,85) somado a uma conta já pareada que ainda não bate;
   c) entre as sobras, mesmo valor e nota ≥ 0,40; depois mesmo valor ÚNICO dos dois lados, com qualquer
      nome (os dois pelo valor: confirmar);
   d) entre as sobras, nome parecido (nota ≥ 0,60).
   Conta que já bate só com a Remoção/Deslocamento (saldo descontado = 0) não recebe Senior.
3. Situação: OK (diferença zero), DIVERGENTE, SÓ NO BALANCETE (conta sem nada nos relatórios),
   SÓ NO SENIOR (pessoa do Senior sem conta).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal

from modulos.honorarios_medicos.fornecedores.pareamento import (
    NOTA_MINIMA_DUPLICADO,
    NOTA_MINIMA_NOME,
    NOTA_MINIMA_VALOR,
    normalizar_nome,
    nota_semelhanca,
)
from modulos.honorarios_medicos.ames.modelos import ContaHonorario, Terceiro
from modulos.honorarios_medicos.ames.pareamento import agrupar_terceiros
from modulos.honorarios_medicos.hospital_exemplo.modelos import (
    LADOS,
    PAREAMENTO_NOME,
    PAREAMENTO_VALOR,
    SITUACAO_DIVERGENTE,
    SITUACAO_OK,
    SITUACAO_SO_BALANCETE,
    SITUACAO_SO_SENIOR,
    LancamentoSenior,
    LinhaHospitalExemplo,
)

__all__ = ["agrupar_terceiros", "parear_hospital_exemplo", "PareamentoHospitalExemplo"]


@dataclass
class PareamentoHospitalExemplo:
    linhas: dict[str, list[LinhaHospitalExemplo]] = field(default_factory=dict)   # lado → linhas
    terceiros_sem_conta: list[Terceiro] = field(default_factory=list)
    nota_remocao: dict[int, float] = field(default_factory=dict)             # id(Terceiro) → nota
    duplicados: list[LinhaHospitalExemplo] = field(default_factory=list)          # 2+ cadastros no Senior
    por_valor: list[LinhaHospitalExemplo] = field(default_factory=list)


def _parear_remocao(contas: list[tuple[str, ContaHonorario]], terceiros: list[Terceiro]):
    """→ {índice da conta: [índices dos terceiros]}, {índice do terceiro: nota}."""
    pares: dict[int, list[int]] = {}
    notas: dict[int, float] = {}
    candidatos = sorted(((nota_semelhanca(conta.descricao, terceiro.nome), i, j)
                         for i, (_lado, conta) in enumerate(contas)
                         for j, terceiro in enumerate(terceiros)), reverse=True)
    for nota, i, j in candidatos:
        if nota < NOTA_MINIMA_NOME:
            break
        if i in pares or j in notas:
            continue
        pares[i] = [j]
        notas[j] = nota
    for j, terceiro in enumerate(terceiros):
        if j in notas:
            continue
        melhor = max(((nota_semelhanca(contas[i][1].descricao, terceiro.nome), i) for i in pares),
                     default=(0.0, None))
        if melhor[0] >= NOTA_MINIMA_DUPLICADO:
            pares[melhor[1]].append(j)
            notas[j] = melhor[0]
    return pares, notas


NOTA_NOME_FORTE = 0.85


def _parear_senior(contas: list[ContaHonorario], saldos: list[Decimal], fechadas: set[int],
                   lancamentos: list[LancamentoSenior]):
    """saldos: saldo de cada conta já sem a Remoção; fechadas: contas que já batem só com a Remoção.

    → {índice da conta: ([índices do Senior], nota, como)}.
    """
    pares: dict[int, tuple[list[int], float, str]] = {}
    usados: set[int] = set()
    abertas = [i for i in range(len(contas)) if i not in fechadas]
    notas: dict[tuple[int, int], float] = {}

    def nota(i: int, j: int) -> float:
        if (i, j) not in notas:
            notas[(i, j)] = nota_semelhanca(contas[i].descricao, lancamentos[j].nome)
        return notas[(i, j)]

    # a0) nome igual (sem acento, maiúsculas, "Ltda"...) e único dos dois lados: nota 1, o guloso o pegaria
    #     primeiro de qualquer jeito. Separar antes evita comparar todos com todos (321 × 312 no PJ).
    chaves_contas = Counter(normalizar_nome(contas[i].descricao) for i in abertas)
    chaves_senior = Counter(normalizar_nome(l.nome) for l in lancamentos)
    senior_da_chave = {normalizar_nome(l.nome): j for j, l in enumerate(lancamentos)}
    for i in abertas:
        chave = normalizar_nome(contas[i].descricao)
        if chave and chaves_contas[chave] == 1 and chaves_senior[chave] == 1:
            j = senior_da_chave[chave]
            pares[i] = ([j], 1.0, PAREAMENTO_NOME)
            usados.add(j)

    def guloso(minima: float) -> None:
        candidatos = sorted(((nota(i, j), lancamentos[j].saldo == saldos[i], i, j)
                             for i in abertas if i not in pares
                             for j in range(len(lancamentos)) if j not in usados), reverse=True)
        candidatos = [c for c in candidatos if c[0] >= minima]
        for semelhanca, _mesmo_valor, i, j in candidatos:
            if i in pares or j in usados:
                continue
            pares[i] = ([j], semelhanca, PAREAMENTO_NOME)
            usados.add(j)

    # a) nome bem parecido
    guloso(NOTA_NOME_FORTE)

    # b) cadastro duplicado no Senior, nunca numa conta que já bate
    def ja_bate(i: int) -> bool:
        return sum((lancamentos[k].saldo for k in pares[i][0]), Decimal(0)) == saldos[i]

    for j in range(len(lancamentos)):
        if j in usados:
            continue
        melhor = max(((nota(i, j), i) for i in pares if not ja_bate(i)), default=(0.0, None))
        if melhor[0] >= NOTA_MINIMA_DUPLICADO:
            pares[melhor[1]][0].append(j)
            usados.add(j)

    # c) mesmo valor + nome minimamente parecido
    for i in abertas:
        if i in pares:
            continue
        candidatos = sorted(((nota(i, j), j) for j in range(len(lancamentos))
                             if j not in usados and lancamentos[j].saldo == saldos[i]
                             and nota(i, j) >= NOTA_MINIMA_VALOR), reverse=True)
        if candidatos:
            semelhanca, j = candidatos[0]
            pares[i] = ([j], semelhanca, PAREAMENTO_VALOR)
            usados.add(j)

    # c2) mesmo valor, ÚNICO entre as sobras dos dois lados, qualquer nome: a clínica com as iniciais da médica
    #     ("A B C Clinica Medica" × "Dra Ana Exemplo") tem nota 0,23 — par feito pelo usuário em ago/2026
    sobra_contas = Counter(saldos[i] for i in abertas if i not in pares)
    sobra_senior = Counter(l.saldo for j, l in enumerate(lancamentos) if j not in usados)
    for i in abertas:
        if i in pares or sobra_contas[saldos[i]] != 1 or sobra_senior[saldos[i]] != 1 or saldos[i] == 0:
            continue
        j = next(j for j, l in enumerate(lancamentos) if j not in usados and l.saldo == saldos[i])
        pares[i] = ([j], nota(i, j), PAREAMENTO_VALOR)
        usados.add(j)

    # d) nome parecido, entre as sobras
    guloso(NOTA_MINIMA_NOME)
    return pares, usados


def parear_hospital_exemplo(contas: dict[str, list[ContaHonorario]],
                      senior: dict[str, list[LancamentoSenior]],
                      terceiros: list[Terceiro]) -> PareamentoHospitalExemplo:
    resultado = PareamentoHospitalExemplo()

    # 1) Remoção/Deslocamento × todas as contas
    todas = [(lado, conta) for lado in LADOS for conta in contas.get(lado, [])]
    pares_remocao, notas_remocao = _parear_remocao(todas, terceiros)
    remocao_da_conta = {id(todas[i][1]): [terceiros[j] for j in js] for i, js in pares_remocao.items()}
    resultado.nota_remocao = {id(terceiros[j]): nota for j, nota in notas_remocao.items()}
    resultado.terceiros_sem_conta = [t for j, t in enumerate(terceiros) if j not in notas_remocao]

    # 2) Senior × contas do mesmo lado, com o saldo já sem a Remoção/Deslocamento
    for lado in LADOS:
        if lado not in contas:
            continue
        do_lado = contas[lado]
        remocao = [remocao_da_conta.get(id(c), []) for c in do_lado]
        saldos = [c.saldo_atual - sum((t.bruto for t in r), Decimal(0)) for c, r in zip(do_lado, remocao)]
        fechadas = {i for i, (r, s) in enumerate(zip(remocao, saldos)) if r and s == 0}
        lancamentos = senior.get(lado, [])
        pares, usados = _parear_senior(do_lado, saldos, fechadas, lancamentos)

        linhas: list[LinhaHospitalExemplo] = []
        brutas = [LinhaHospitalExemplo(lado=lado, conta=c, remocao=remocao[i]) for i, c in enumerate(do_lado)]
        for i, linha in enumerate(brutas):
            if i in pares:
                indices, linha.nota, linha.pareamento = pares[i]
                linha.senior = [lancamentos[j] for j in indices]
        brutas += [LinhaHospitalExemplo(lado=lado, senior=[l]) for j, l in enumerate(lancamentos) if j not in usados]
        for linha in brutas:
            if linha.conta is None:
                linha.situacao = SITUACAO_SO_SENIOR
            elif not linha.senior and not linha.remocao:
                linha.situacao = SITUACAO_SO_BALANCETE
            else:
                linha.situacao = SITUACAO_OK if linha.diferenca == 0 else SITUACAO_DIVERGENTE
            if linha.nota is None and linha.remocao:
                linha.nota = max(resultado.nota_remocao[id(t)] for t in linha.remocao)
            if len(linha.senior) > 1:
                resultado.duplicados.append(linha)
            if linha.pareamento == PAREAMENTO_VALOR:
                resultado.por_valor.append(linha)
            linhas.append(linha)
        resultado.linhas[lado] = linhas
    return resultado
