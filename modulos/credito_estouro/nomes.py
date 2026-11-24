"""Quem é o colaborador de um lançamento do razão (ESPECIFICACAO_CREDITO_ESTOURO.md, seção 4).

O histórico do razão traz o nome da pessoa e, às vezes, o crachá (que é a matrícula do PDF de eventos):
"Recebimento de valores na tesouraria Fulano de Tal …", "… da colaboradora Fulana crachá 12345 …".

1. **Crachá** no histórico → a matrícula.
2. **Nome completo:** todas as palavras do nome (sem "de", "da", "dos"…) aparecem no histórico, sem acento e
   sem diferença de maiúsculas. Uma palavra de 4 letras ou mais pode ter **uma letra** trocada, a mais ou a
   menos (a folha e o financeiro escrevem "FALEIROS" × "Falleiros", "SOUZA" × "Sousa"). Se mais de uma pessoa
   servir, vale a de nome mais comprido (quem tem "CARLOS SILVA PEREIRA" no histórico não é confundido com
   "CARLOS SILVA"); empate → ninguém (ambíguo).
   O nome de um **pagador** da lista "quem paga por quem" (controle) conta como nome do colaborador.
3. Nada disso → ninguém: o lançamento vai para "a conferir". Um nome nunca é casado "mais ou menos".

Diferente do pareamento das Rescisões (que compara um nome com outro nome): aqui o nome está dentro de um texto
maior, então a regra é "todas as palavras do nome estão no histórico".
"""

from __future__ import annotations

import re

from modulos.credito_estouro.util import sem_acento

PARTICULAS = {"de", "da", "do", "das", "dos", "e"}
_REGEX_CRACHA = re.compile(r"cracha\s*:?\s*n?\.?\s*(\d+)")
_REGEX_PALAVRA = re.compile(r"[a-z0-9]+")


def palavras(texto: str) -> list[str]:
    return _REGEX_PALAVRA.findall(sem_acento(texto))


def palavras_do_nome(nome: str) -> frozenset[str]:
    return frozenset(p for p in palavras(nome) if p not in PARTICULAS and not p.isdigit())


def cracha_do_historico(historico: str) -> str | None:
    achado = _REGEX_CRACHA.search(sem_acento(historico))
    if not achado:
        return None
    return achado.group(1).lstrip("0") or "0"


def _uma_letra_de_diferenca(a: str, b: str) -> bool:
    """Distância de edição até 1 (troca, sobra ou falta de uma letra)."""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    curto, longo = (a, b) if len(a) < len(b) else (b, a)
    return any(longo[:i] + longo[i + 1:] == curto for i in range(len(longo)))


def _palavra_esta(palavra: str, texto: set[str]) -> bool:
    if palavra in texto:
        return True
    if len(palavra) < 4:
        return False
    return any(len(outra) >= 4 and _uma_letra_de_diferenca(palavra, outra) for outra in texto)


def nome_esta_no_texto(nome: frozenset[str], texto: set[str]) -> bool:
    return bool(nome) and all(_palavra_esta(p, texto) for p in nome)


class Pessoas:
    """As pessoas conhecidas no mês (matrícula → nome), para achar quem é o colaborador de um histórico."""

    def __init__(self, nomes_por_matricula: dict[str, str], pagadores: dict[str, str] | None = None):
        """`pagadores`: nome do pagador → matrícula do colaborador ("quem paga por quem")."""
        self.nomes = {m.lstrip("0") or "0": n for m, n in nomes_por_matricula.items() if n}
        # cada nome (do colaborador ou de um pagador dele) aponta para a matrícula
        self._palavras = [(palavras_do_nome(n), m) for m, n in self.nomes.items()]
        self._palavras += [(palavras_do_nome(p), m.lstrip("0") or "0") for p, m in (pagadores or {}).items()]

    def nome(self, matricula: str) -> str:
        return self.nomes.get(matricula, "")

    def do_historico(self, historico: str) -> tuple[str | None, str]:
        """(matrícula, como foi achada: "crachá", "nome", "ambíguo" ou "")."""
        cracha = cracha_do_historico(historico)
        if cracha:
            return cracha, "crachá"
        texto = set(palavras(historico))
        servem = [(len(p), m) for p, m in self._palavras if nome_esta_no_texto(p, texto)]
        if not servem:
            return None, ""
        maior = max(tamanho for tamanho, _ in servem)
        melhores = sorted({m for tamanho, m in servem if tamanho == maior})
        if len(melhores) > 1:
            return None, "ambíguo"
        return melhores[0], "nome"
