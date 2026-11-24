"""
Cruzamento das notas do Tasy com as linhas da prefeitura (seção 4 da especificação).

Recebe dados já lidos e normalizados (sem arquivos, sem tela) e devolve os itens
do relatório e os avisos. Valor comparado: só Valor da mercadoria (Tasy) ×
Valor do Doc. (prefeitura); a diferença tem que ser exatamente zero.

Ordem:
1. agrupa as linhas da prefeitura por (documento, número);
2. notas PJ com grupo de mesma chave: 1 linha → Conferida / Divergência de valor;
   n linhas → "Notas escrituradas n vezes na prefeitura" (uma linha por linha da prefeitura);
3. notas PJ sem grupo: número ajustado (só depois de todas as chaves exatas, para uma
   nota não "roubar" a linha de outra), exige 1 linha não usada com mesmo documento,
   número ajustado e valor;
4. notas PF: 1 linha não usada com mesmo número e valor → Conferida sem CPF;
5. o que sobrou da prefeitura → somente no site da prefeitura.

Linhas canceladas na prefeitura (só existem em Cidade Epsilon) ficam FORA dos passos 1 a 5:
uma nota cancelada não conta como escrituração. Depois, cada nota que ficou "somente
no Tasy" é procurada entre as canceladas (mesmas regras: chave exata, número ajustado,
PF por número e valor) → "Cancelada na prefeitura (lançada no Tasy)". As canceladas que
sobram → "Cancelada na prefeitura (sem nota no Tasy)".

Cidade Gama (comparar_por_nome): o relatório não traz o CNPJ do prestador, então a chave
(documento, número) vira (nome parecido, número) — decisão do usuário:
1. número + nome parecido: 1 linha → Conferida / Divergência de valor;
   n linhas → "Notas escrituradas n vezes na prefeitura";
2. sem linha: número ajustado + nome parecido + valor (1 linha não usada) → Conferida
   (número ajustado);
3. ainda sem linha: número + valor iguais com nome diferente (1 linha não usada) →
   "Número e valor iguais, nome diferente — verificar" (prestador com outro nome no cadastro);
4. canceladas e sobras como acima.
O número da linha é o "Nr. NF" ou, se preenchido, também o "Nº Documento Escriturado".
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from modulos.conferencia_iss.modelos import (
    NIVEL_AVISO,
    SITUACAO_CANCELADA_COM_TASY,
    SITUACAO_CANCELADA_SEM_TASY,
    SITUACAO_CONFERIDA,
    SITUACAO_CONFERIDA_AJUSTADO,
    SITUACAO_CONFERIDA_SEM_CPF,
    SITUACAO_DIVERGENCIA,
    SITUACAO_NOME_DIFERENTE,
    SITUACAO_SOMENTE_PREFEITURA,
    SITUACAO_SOMENTE_TASY,
    Aviso,
    ItemResultado,
    LinhaPrefeitura,
    NotaTasy,
    situacao_escriturada_varias_vezes,
)
from modulos.conferencia_iss.normalizar import formatar_documento, nomes_parecidos

AVISO_UNIDADES_MISTURADAS = "Arquivos de unidades diferentes misturados"
AVISO_PF_VARIOS_CANDIDATOS = "Mais de uma nota da prefeitura com mesmo número e valor"


@dataclass
class ResultadoComparacao:
    itens: list[ItemResultado] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)


def comparar(notas: list[NotaTasy], linhas: list[LinhaPrefeitura]) -> ResultadoComparacao:
    """Aplica as regras da seção 4 e devolve itens (na ordem das notas) e avisos."""
    resultado = ResultadoComparacao()
    resultado.avisos.extend(avisos_das_notas_tasy(notas))

    canceladas = [l for l in linhas if l.cancelada]
    linhas = [l for l in linhas if not l.cancelada]

    grupos = _agrupar(linhas)

    usadas: set[int] = set()                        # id() das linhas já casadas
    itens_por_nota: dict[int, list[ItemResultado]] = {}

    notas_pj = [n for n in notas if not n.eh_pessoa_fisica]
    notas_pf = [n for n in notas if n.eh_pessoa_fisica]

    # 1) PJ pela chave exata (documento, número)
    sem_grupo: list[NotaTasy] = []
    for nota in notas_pj:
        grupo = grupos.get((nota.documento, nota.numero))
        if not grupo:
            sem_grupo.append(nota)
            continue
        usadas.update(id(l) for l in grupo)
        if len(grupo) == 1:
            item = ItemResultado(SITUACAO_CONFERIDA, nota, grupo[0])
            if not item.valor_confere:
                item.situacao = SITUACAO_DIVERGENCIA
            itens_por_nota[id(nota)] = [item]
        else:
            situacao = situacao_escriturada_varias_vezes(len(grupo))
            itens_por_nota[id(nota)] = [ItemResultado(situacao, nota, l) for l in grupo]

    # 2) PJ pelo número ajustado (ano + zeros + número)
    for nota in sem_grupo:
        candidatas = []
        if nota.numero_ajustado:
            candidatas = [
                l for l in grupos.get((nota.documento, nota.numero_ajustado), [])
                if id(l) not in usadas and l.valor_doc == nota.valor_mercadoria
            ]
        if len(candidatas) == 1:
            usadas.add(id(candidatas[0]))
            itens_por_nota[id(nota)] = [
                ItemResultado(SITUACAO_CONFERIDA_AJUSTADO, nota, candidatas[0])
            ]
        else:
            itens_por_nota[id(nota)] = [ItemResultado(SITUACAO_SOMENTE_TASY, nota)]

    # 3) PF por número e valor, só contra linhas ainda não usadas
    for nota in notas_pf:
        candidatas = [
            l for l in linhas
            if id(l) not in usadas
            and l.numero == nota.numero
            and l.valor_doc == nota.valor_mercadoria
        ]
        if len(candidatas) == 1:
            usadas.add(id(candidatas[0]))
            itens_por_nota[id(nota)] = [
                ItemResultado(SITUACAO_CONFERIDA_SEM_CPF, nota, candidatas[0])
            ]
            continue
        itens_por_nota[id(nota)] = [ItemResultado(SITUACAO_SOMENTE_TASY, nota)]
        if len(candidatas) > 1:
            prestadores = "; ".join(
                f"{formatar_documento(l.documento)} {l.prestador}".strip() for l in candidatas
            )
            resultado.avisos.append(Aviso(
                arquivo=nota.arquivo,
                mensagem=(
                    f"{AVISO_PF_VARIOS_CANDIDATOS}: nota {nota.nota_fiscal} de "
                    f"{nota.emitente} (pessoa física). Candidatas na prefeitura: "
                    f"{prestadores}. A nota ficou em somente no Tasy."
                ),
                nivel=NIVEL_AVISO,
            ))

    # 4) Notas que sobraram, procuradas entre as canceladas na prefeitura
    if canceladas:
        grupos_canceladas = _agrupar(canceladas)
        _procurar_nas_canceladas(
            notas, itens_por_nota, usadas,
            lambda nota: _canceladas_da_nota(nota, canceladas, grupos_canceladas, usadas),
        )

    _fechar(resultado, notas, itens_por_nota, linhas, canceladas, usadas)
    return resultado


def _procurar_nas_canceladas(notas, itens_por_nota, usadas: set[int], achar) -> None:
    """Cada nota que ficou somente no Tasy, procurada entre as canceladas na prefeitura."""
    for nota in notas:
        itens = itens_por_nota[id(nota)]
        if itens[0].situacao != SITUACAO_SOMENTE_TASY:
            continue
        achadas = achar(nota)
        if achadas:
            usadas.update(id(l) for l in achadas)
            itens_por_nota[id(nota)] = [
                ItemResultado(SITUACAO_CANCELADA_COM_TASY, nota, l) for l in achadas
            ]


def _fechar(resultado: ResultadoComparacao, notas, itens_por_nota, linhas, canceladas,
            usadas: set[int]) -> None:
    """Itens na ordem das notas e, no fim, as linhas da prefeitura que ninguém usou."""
    for nota in notas:
        resultado.itens.extend(itens_por_nota[id(nota)])

    # 5) Linhas da prefeitura que ninguém usou
    for linha in linhas:
        if id(linha) not in usadas:
            resultado.itens.append(
                ItemResultado(SITUACAO_SOMENTE_PREFEITURA, linha_prefeitura=linha)
            )
    for linha in canceladas:
        if id(linha) not in usadas:
            resultado.itens.append(
                ItemResultado(SITUACAO_CANCELADA_SEM_TASY, linha_prefeitura=linha)
            )


def _agrupar(linhas: list[LinhaPrefeitura]) -> dict[tuple[str, str], list[LinhaPrefeitura]]:
    """Linhas da prefeitura agrupadas por (documento, número)."""
    grupos: dict[tuple[str, str], list[LinhaPrefeitura]] = defaultdict(list)
    for linha in linhas:
        grupos[(linha.documento, linha.numero)].append(linha)
    return grupos


def _canceladas_da_nota(nota: NotaTasy, canceladas: list[LinhaPrefeitura],
                        grupos: dict[tuple[str, str], list[LinhaPrefeitura]],
                        usadas: set[int]) -> list[LinhaPrefeitura]:
    """Linhas canceladas que correspondem à nota (mesmas regras da conferência)."""
    if nota.eh_pessoa_fisica:
        candidatas = [
            l for l in canceladas
            if id(l) not in usadas
            and l.numero == nota.numero
            and l.valor_doc == nota.valor_mercadoria
        ]
        return candidatas if len(candidatas) == 1 else []

    exatas = [l for l in grupos.get((nota.documento, nota.numero), []) if id(l) not in usadas]
    if exatas:
        return exatas                    # uma linha por cancelamento, como nas escrituradas
    if nota.numero_ajustado:
        candidatas = [
            l for l in grupos.get((nota.documento, nota.numero_ajustado), [])
            if id(l) not in usadas and l.valor_doc == nota.valor_mercadoria
        ]
        if len(candidatas) == 1:
            return candidatas
    return []


# ---------------------------------------------------------------------
# Cidade Gama: sem CNPJ do prestador na prefeitura
# ---------------------------------------------------------------------
def _numeros_da_linha(linha: LinhaPrefeitura) -> tuple[str, ...]:
    """Nr. NF e, se houver, o Nº Documento Escriturado (já normalizados)."""
    return tuple(n for n in (linha.numero, linha.numero_alternativo) if n)


def _do_mesmo_prestador(nota: NotaTasy, linha: LinhaPrefeitura, numero: str) -> bool:
    return numero in _numeros_da_linha(linha) and nomes_parecidos(nota.emitente, linha.prestador)


def comparar_por_nome(notas: list[NotaTasy],
                      linhas: list[LinhaPrefeitura]) -> ResultadoComparacao:
    """Regras de Cidade Gama (sem CNPJ do prestador): número, valor e nome parecido."""
    resultado = ResultadoComparacao()
    resultado.avisos.extend(avisos_das_notas_tasy(notas))

    canceladas = [l for l in linhas if l.cancelada]
    linhas = [l for l in linhas if not l.cancelada]

    usadas: set[int] = set()
    itens_por_nota: dict[int, list[ItemResultado]] = {}

    # 1) número + nome parecido (o equivalente à chave exata)
    sem_grupo: list[NotaTasy] = []
    for nota in notas:
        grupo = [l for l in linhas if _do_mesmo_prestador(nota, l, nota.numero)]
        if not grupo:
            sem_grupo.append(nota)
            continue
        usadas.update(id(l) for l in grupo)
        if len(grupo) == 1:
            item = ItemResultado(SITUACAO_CONFERIDA, nota, grupo[0])
            if not item.valor_confere:
                item.situacao = SITUACAO_DIVERGENCIA
            itens_por_nota[id(nota)] = [item]
        else:
            situacao = situacao_escriturada_varias_vezes(len(grupo))
            itens_por_nota[id(nota)] = [ItemResultado(situacao, nota, l) for l in grupo]

    # 2) número ajustado + nome parecido + valor
    sem_par: list[NotaTasy] = []
    for nota in sem_grupo:
        candidatas = []
        if nota.numero_ajustado:
            candidatas = [
                l for l in linhas
                if id(l) not in usadas
                and _do_mesmo_prestador(nota, l, nota.numero_ajustado)
                and l.valor_doc == nota.valor_mercadoria
            ]
        if len(candidatas) == 1:
            usadas.add(id(candidatas[0]))
            itens_por_nota[id(nota)] = [
                ItemResultado(SITUACAO_CONFERIDA_AJUSTADO, nota, candidatas[0])
            ]
        else:
            sem_par.append(nota)

    # 3) número + valor iguais, nome diferente: não confere sozinho, vai para análise
    for nota in sem_par:
        numeros = {nota.numero, nota.numero_ajustado} - {None}
        candidatas = [
            l for l in linhas
            if id(l) not in usadas
            and numeros & set(_numeros_da_linha(l))
            and l.valor_doc == nota.valor_mercadoria
        ]
        if len(candidatas) == 1:
            usadas.add(id(candidatas[0]))
            itens_por_nota[id(nota)] = [
                ItemResultado(SITUACAO_NOME_DIFERENTE, nota, candidatas[0])
            ]
            continue
        itens_por_nota[id(nota)] = [ItemResultado(SITUACAO_SOMENTE_TASY, nota)]
        if len(candidatas) > 1:
            prestadores = "; ".join(l.prestador for l in candidatas)
            resultado.avisos.append(Aviso(
                arquivo=nota.arquivo,
                mensagem=(
                    f"{AVISO_PF_VARIOS_CANDIDATOS}, com nome diferente: nota "
                    f"{nota.nota_fiscal} de {nota.emitente}. Candidatas na prefeitura: "
                    f"{prestadores}. A nota ficou em somente no Tasy."
                ),
                nivel=NIVEL_AVISO,
            ))

    # 4) Notas que sobraram, procuradas entre as canceladas (número + nome parecido)
    if canceladas:
        def achar(nota: NotaTasy) -> list[LinhaPrefeitura]:
            exatas = [l for l in canceladas
                      if id(l) not in usadas and _do_mesmo_prestador(nota, l, nota.numero)]
            if exatas or not nota.numero_ajustado:
                return exatas
            candidatas = [
                l for l in canceladas
                if id(l) not in usadas
                and _do_mesmo_prestador(nota, l, nota.numero_ajustado)
                and l.valor_doc == nota.valor_mercadoria
            ]
            return candidatas if len(candidatas) == 1 else []

        _procurar_nas_canceladas(notas, itens_por_nota, usadas, achar)

    _fechar(resultado, notas, itens_por_nota, linhas, canceladas, usadas)
    return resultado


def avisos_das_notas_tasy(notas: list[NotaTasy]) -> list[Aviso]:
    """Avisos que só aparecem juntando os CSVs: unidades misturadas e nota repetida."""
    avisos: list[Aviso] = []

    estabelecimentos: dict[str, list[str]] = {}
    for nota in notas:
        if nota.estabelecimento:
            arquivos = estabelecimentos.setdefault(nota.estabelecimento, [])
            if nota.arquivo not in arquivos:
                arquivos.append(nota.arquivo)
    if len(estabelecimentos) > 1:
        detalhe = "; ".join(
            f"{nome} ({', '.join(arquivos)})" for nome, arquivos in estabelecimentos.items()
        )
        avisos.append(Aviso(
            arquivo=", ".join(sorted({a for l in estabelecimentos.values() for a in l})),
            mensagem=f"{AVISO_UNIDADES_MISTURADAS}: {detalhe}.",
            nivel=NIVEL_AVISO,
        ))

    # Mesma nota em dois CSVs. Na PF o documento é vazio: usa o código do Tasy.
    por_chave: dict[tuple[str, str], list[NotaTasy]] = defaultdict(list)
    for nota in notas:
        emitente = nota.documento or f"PF:{nota.codigo_emitente}"
        por_chave[(emitente, nota.numero)].append(nota)
    for repetidas in por_chave.values():
        arquivos = sorted({n.arquivo for n in repetidas})
        if len(arquivos) < 2:
            continue
        nota = repetidas[0]
        avisos.append(Aviso(
            arquivo=", ".join(arquivos),
            mensagem=(
                f"Nota {nota.nota_fiscal} de {nota.emitente} aparece em mais de um CSV do "
                f"Tasy ({', '.join(arquivos)}). Todas aparecem no relatório."
            ),
            nivel=NIVEL_AVISO,
        ))

    return avisos
