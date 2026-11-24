"""Casamento das contas analíticas do balancete com os locais do SCF (ESPECIFICACAO_ESTOQUE.md, seção 4).

Cada conta é ligada a UM local, em até 3 níveis, nesta ordem (todas as contas passam pelo
nível 1 antes de qualquer uma ir para o nível 2). Um local casado sai da disputa: cada local
só casa uma vez.

1. Código do local: o número entre parênteses no fim das duas descrições é o mesmo.
2. Nome equivalente: os nomes padronizados (nome_padronizado) ficam iguais e as unidades
   (SC, HC, HCA) são compatíveis; com mais de um candidato, não casa.
3. Sem par: só sugere o local livre mais parecido (semelhança >= 50%), sem casar.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from modulos.conciliacao_estoque import configuracao
from modulos.conciliacao_estoque.modelos import (
    ComoCasou,
    ContaBalancete,
    LocalSCF,
    ParCasado,
    ResultadoCasamento,
)
from modulos.conciliacao_estoque.utilitarios import normalizar_texto

_PADRAO_CODIGO_NO_FIM = re.compile(r"\((\d+)\)\s*$")
_PADRAO_PONTUACAO = re.compile(r"[^a-z0-9]+")

OBSERVACAO_NOME_EQUIVALENTE = "Casada por nome equivalente — conferir"
OBSERVACAO_SEM_PAR = "Sem par no Mapa do Estoque"


@dataclass(frozen=True)
class NomePadronizado:
    resto: str                  # o nome sem unidade, abreviação nem palavras sem valor
    unidades: frozenset[str]    # {"SC"}, {"HC", "HCA"}, ...


def codigo_no_fim(descricao: str) -> int | None:
    """"Central de Kits - SC (23)" -> 23; sem número entre parênteses no fim -> None."""
    encontrado = _PADRAO_CODIGO_NO_FIM.search(descricao)
    return int(encontrado.group(1)) if encontrado else None


def nome_padronizado(descricao: str) -> NomePadronizado:
    """Passos 1 a 5 do nível 2 (seção 4).

    "Estoque SESMT - EPI - HC e H Central (118)" -> resto "sesmt epi", unidades {HC, HCA}
    """
    texto = _PADRAO_CODIGO_NO_FIM.sub("", descricao)                     # 1. tira o (número)
    texto = _PADRAO_PONTUACAO.sub(" ", normalizar_texto(texto))          # 2. acentos, minúsculas, pontuação
    palavras = []
    for palavra in texto.split():                                        # 3. abreviações
        palavras.extend(configuracao.CASAMENTO_ABREVIACOES.get(palavra, palavra).split())
    palavras = [p for p in palavras if p not in configuracao.CASAMENTO_PALAVRAS_SEM_VALOR]  # 4.
    unidades = set()                                                     # 5. separa as unidades
    for expressao, unidade in configuracao.CASAMENTO_UNIDADES.items():
        partes = expressao.split()
        i = 0
        while i <= len(palavras) - len(partes):
            if palavras[i:i + len(partes)] == partes:
                unidades.add(unidade)
                del palavras[i:i + len(partes)]
            else:
                i += 1
    return NomePadronizado(" ".join(palavras), frozenset(unidades))


def unidades_compativeis(a: NomePadronizado, b: NomePadronizado) -> bool:
    """Se os dois nomes têm unidade, precisam ser as mesmas; se só um tem, ou nenhum, é compatível."""
    if a.unidades and b.unidades:
        return a.unidades == b.unidades
    return True


def semelhanca(a: NomePadronizado, b: NomePadronizado) -> float:
    """Média de: proporção de palavras em comum (em comum / todas as palavras dos dois) e
    difflib.SequenceMatcher entre os nomes padronizados."""
    palavras_a, palavras_b = set(a.resto.split()), set(b.resto.split())
    todas = palavras_a | palavras_b
    proporcao = len(palavras_a & palavras_b) / len(todas) if todas else 0.0
    sequencia = difflib.SequenceMatcher(None, a.resto, b.resto).ratio()
    return (proporcao + sequencia) / 2


def casar(contas: list[ContaBalancete], locais: list[LocalSCF]) -> ResultadoCasamento:
    livres: list[LocalSCF] = list(locais)
    casados: dict[int, ParCasado] = {}          # por código da conta

    # Nível 1 — código do local
    for conta in contas:
        codigo = codigo_no_fim(conta.descricao)
        local = next((l for l in livres if l.codigo == codigo), None) if codigo is not None else None
        if local is not None:
            casados[conta.codigo] = ParCasado(conta, local, ComoCasou.CODIGO_LOCAL)
            livres.remove(local)

    # Nível 2 — nome equivalente (só um candidato)
    for conta in contas:
        if conta.codigo in casados:
            continue
        nome = nome_padronizado(conta.descricao)
        candidatos = [
            l for l in livres
            if (outro := nome_padronizado(l.descricao)).resto == nome.resto and unidades_compativeis(nome, outro)
        ]
        if len(candidatos) == 1:
            casados[conta.codigo] = ParCasado(
                conta, candidatos[0], ComoCasou.NOME_EQUIVALENTE, OBSERVACAO_NOME_EQUIVALENTE,
            )
            livres.remove(candidatos[0])

    # Nível 3 — sem par, com sugestão
    resultado = ResultadoCasamento(locais_sem_conta=livres)
    for conta in contas:
        if conta.codigo in casados:
            resultado.pares.append(casados[conta.codigo])
        else:
            resultado.pares.append(_sem_par(conta, livres))
    return resultado


def _sem_par(conta: ContaBalancete, livres: list[LocalSCF]) -> ParCasado:
    nome = nome_padronizado(conta.descricao)
    melhor, melhor_semelhanca = None, 0.0
    for local in livres:
        outro = nome_padronizado(local.descricao)
        if not unidades_compativeis(nome, outro):
            continue
        valor = semelhanca(nome, outro)
        if valor > melhor_semelhanca:
            melhor, melhor_semelhanca = local, valor
    if melhor is None or melhor_semelhanca < configuracao.CASAMENTO_SEMELHANCA_MINIMA:
        return ParCasado(conta, None, ComoCasou.SEM_PAR, OBSERVACAO_SEM_PAR)
    observacao = (f"{OBSERVACAO_SEM_PAR} — possível par: {melhor.descricao} "
                  f"(semelhança {round(melhor_semelhanca * 100)}%)")
    return ParCasado(conta, None, ComoCasou.SEM_PAR, observacao, melhor, melhor_semelhanca)
