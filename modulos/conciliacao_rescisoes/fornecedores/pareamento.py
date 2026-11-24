"""
Pareamento Balancete × financeiro pelo nome do fornecedor (ESPECIFICACAO seção 16.3).

O financeiro não tem código contábil e os nomes vêm escritos de jeitos diferentes
("Verano Com. Informática Ltda Epp" × "Veranno Comercio e Informatica Ltda - EPP"; nomes fictícios no lugar do exemplo real do Conciliações AMES).

Ordem (exatamente a do protótipo validado pelo usuário):
1. Contas "Fornecedores a reclassificar" nunca são pareadas.
2. Guloso por nome: todas as combinações, da maior nota para a menor, casando as de nota
   ≥ 0,60 sem reaproveitar nenhum dos lados. Nota empatada: primeiro o par de mesmo valor.
3. Cadastro duplicado no financeiro: sobra do financeiro com nota ≥ 0,85 com uma conta já
   pareada é SOMADA a ela (o mesmo fornecedor com 2 cadastros) — nunca a uma conta que já bate.
4. Por valor: entre as sobras, mesmo valor e nota ≥ 0,40 (confirmar).
5. O resto: SÓ NO BALANCETE / SÓ NO RELATÓRIO.

Nota de semelhança (0 a 1) = max(SequenceMatcher, 0,97 × palavras em comum / menor nº de palavras),
depois de tirar acentos, pontuação e palavras vazias (ltda, me, de, da...).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from difflib import SequenceMatcher

from modulos.conciliacao_rescisoes.fornecedores.modelos import (
    PAREAMENTO_NOME,
    PAREAMENTO_VALOR,
    SITUACAO_DIVERGENTE,
    SITUACAO_OK,
    SITUACAO_SO_BALANCETE,
    SITUACAO_SO_RELATORIO,
    ContaFornecedor,
    FornecedorFinanceiro,
    LinhaConciliacao,
)

NOTA_MINIMA_NOME = 0.60
NOTA_MINIMA_DUPLICADO = 0.85
NOTA_MINIMA_VALOR = 0.40
PESO_PALAVRAS = 0.97

PALAVRAS_VAZIAS = frozenset({
    "ltda", "me", "epp", "eireli", "eirelli", "sa", "s", "a", "de", "da", "do", "dos", "das",
    "e", "com", "cia",
})


def normalizar_nome(nome: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower()
    so_letras = re.sub(r"[^a-z0-9 ]", " ", sem_acento)
    return " ".join(p for p in so_letras.split() if p not in PALAVRAS_VAZIAS)


def nota_semelhanca(nome_a: str, nome_b: str) -> float:
    a, b = normalizar_nome(nome_a), normalizar_nome(nome_b)
    parecido = SequenceMatcher(None, a, b).ratio()
    palavras_a, palavras_b = set(a.split()), set(b.split())
    if not palavras_a or not palavras_b:
        return parecido
    em_comum = len(palavras_a & palavras_b) / min(len(palavras_a), len(palavras_b))
    return max(parecido, PESO_PALAVRAS * em_comum)


@dataclass
class Pareamento:
    linhas: list[LinhaConciliacao] = field(default_factory=list)
    duplicados: list[LinhaConciliacao] = field(default_factory=list)   # linhas com 2+ cadastros
    por_valor: list[LinhaConciliacao] = field(default_factory=list)


def parear(contas: list[ContaFornecedor], fornecedores: list[FornecedorFinanceiro]) -> Pareamento:
    # i → [índices do financeiro], nota, como
    pares: dict[int, tuple[list[int], float, str]] = {}
    usados: set[int] = set()

    # 2) guloso por nome. Empate de nota: primeiro o par de mesmo valor (duas filiais com o mesmo nome, cada
    #    uma com a sua conta); depois como no protótipo, ordem decrescente de i, j
    candidatos = sorted(
        ((nota_semelhanca(conta.descricao, fornecedor.nome), fornecedor.saldo == conta.saldo_atual, i, j)
         for i, conta in enumerate(contas) if not conta.a_reclassificar
         for j, fornecedor in enumerate(fornecedores)),
        reverse=True)
    for nota, _mesmo_valor, i, j in candidatos:
        if nota < NOTA_MINIMA_NOME:
            break
        if i in pares or j in usados:
            continue
        pares[i] = ([j], nota, PAREAMENTO_NOME)
        usados.add(j)

    # 3) cadastro duplicado no financeiro → somado à conta já pareada, menos às que já batem: somar estragaria
    #    a conta, e a sobra ainda pode casar pelo valor com outra (um "/MG" ia para o "/SP", set/2026)
    def ja_bate(i: int) -> bool:
        return sum((fornecedores[k].saldo for k in pares[i][0]), Decimal(0)) == contas[i].saldo_atual

    for j, fornecedor in enumerate(fornecedores):
        if j in usados:
            continue
        melhor = max(((nota_semelhanca(contas[i].descricao, fornecedor.nome), i) for i in pares if not ja_bate(i)),
                     default=(0.0, None))
        if melhor[0] >= NOTA_MINIMA_DUPLICADO:
            pares[melhor[1]][0].append(j)
            usados.add(j)

    # 4) por valor idêntico + nome minimamente parecido
    for i, conta in enumerate(contas):
        if i in pares or conta.a_reclassificar:
            continue
        for j, fornecedor in enumerate(fornecedores):
            if j in usados or fornecedor.saldo != conta.saldo_atual:
                continue
            nota = nota_semelhanca(conta.descricao, fornecedor.nome)
            if nota >= NOTA_MINIMA_VALOR:
                pares[i] = ([j], nota, PAREAMENTO_VALOR)
                usados.add(j)
                break

    # 5) linhas: na ordem do balancete, depois as sobras do financeiro
    resultado = Pareamento()
    for i, conta in enumerate(contas):
        if i not in pares:
            resultado.linhas.append(LinhaConciliacao(situacao=SITUACAO_SO_BALANCETE, conta=conta))
            continue
        indices, nota, como = pares[i]
        linha = LinhaConciliacao(situacao="", conta=conta,
                                 financeiros=[fornecedores[j] for j in indices],
                                 nota=nota, pareamento=como)
        linha.situacao = SITUACAO_OK if linha.diferenca == 0 else SITUACAO_DIVERGENTE
        resultado.linhas.append(linha)
        if len(indices) > 1:
            resultado.duplicados.append(linha)
        if como == PAREAMENTO_VALOR:
            resultado.por_valor.append(linha)
    for j, fornecedor in enumerate(fornecedores):
        if j not in usados:
            resultado.linhas.append(LinhaConciliacao(situacao=SITUACAO_SO_RELATORIO,
                                                     financeiros=[fornecedor]))
    return resultado
