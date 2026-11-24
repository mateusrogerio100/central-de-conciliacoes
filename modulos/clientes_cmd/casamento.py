"""Casamento (matching) dos lancamentos do contabil (balancete) com o financeiro
(titulos a receber), pelo nome do cliente, tolerando ruido entre os dois sistemas
(truncamento, erros de digitacao, pontuacao/espacamento diferentes).
"""

import re
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher

import pandas as pd

_LIMIAR_SIMILARIDADE = 0.80


def _normalizar_nome(nome):
    """Maiusculas, sem acento, espacos colapsados."""
    if nome is None:
        return ""
    texto = unicodedata.normalize("NFKD", str(nome))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.strip().upper().split())


def _apenas_alfanumerico(nome_normalizado):
    """So letras e numeros (remove pontuacao e espacos)."""
    return re.sub(r"[^A-Z0-9]", "", nome_normalizado)


def _valor_bate(a, b):
    return round(a, 2) == round(b, 2)


def _agrupar_por_chave(indices, serie):
    grupos = defaultdict(list)
    for i in indices:
        chave = serie.at[i]
        if chave:
            grupos[chave].append(i)
    return grupos


def casar(df_balancete, df_financeiro):
    """Casa os lancamentos de df_balancete e df_financeiro (colunas: codigo,
    nome, valor) pelo nome do cliente, usando uma cascata de criterios do mais
    para o menos confiavel. Devolve um DataFrame com uma linha por cliente
    (casado ou nao), colunas: codigo, contabil, valor_contabil, financeiro,
    valor_financeiro, situacao.
    """
    contabil = df_balancete.reset_index(drop=True).copy()
    financeiro = df_financeiro.reset_index(drop=True).copy()

    contabil["_norm"] = contabil["nome"].map(_normalizar_nome)
    financeiro["_norm"] = financeiro["nome"].map(_normalizar_nome)
    contabil["_alnum"] = contabil["_norm"].map(_apenas_alfanumerico)
    financeiro["_alnum"] = financeiro["_norm"].map(_apenas_alfanumerico)

    pendentes_contabil = set(contabil.index)
    pendentes_financeiro = set(financeiro.index)
    pares = []

    def _casar_por_criterio(candidatos):
        """candidatos: lista de (prioridade, lista_ic, lista_jf). Ordena pela
        prioridade (menor = melhor) e casa greedy, pulando quem ja foi casado
        por um candidato de prioridade melhor nesta mesma leva. Listas com
        mais de um indice sao usadas na etapa 0 (agregacao N-para-1)."""
        for _, lista_ic, lista_jf in sorted(candidatos, key=lambda t: t[0]):
            if all(i in pendentes_contabil for i in lista_ic) and all(
                j in pendentes_financeiro for j in lista_jf
            ):
                pares.append((lista_ic, lista_jf))
                for i in lista_ic:
                    pendentes_contabil.discard(i)
                for j in lista_jf:
                    pendentes_financeiro.discard(j)

    def _eh_relacionado(nome, chave):
        return bool(nome) and (nome == chave or nome.startswith(chave) or chave.startswith(nome))

    # --- Etapa 0: agregacao inequivoca - varios lancamentos com o MESMO nome
    #     exato (mesmo _norm) de um lado que, juntos, so podem pertencer a UM
    #     unico cliente do outro lado (nenhum outro registro tem nome
    #     relacionado a essa chave). So agrega quando o alvo e unico, nunca
    #     por aproximacao de valor - isso evita juntar clientes diferentes que
    #     por coincidencia tem nomes identicos (nesse caso, ambos teriam alvos
    #     proprios e cairiam nas etapas seguintes, individualmente). Roda
    #     antes de tudo porque, quando o alvo e mesmo unico, um casamento
    #     individual nas etapas seguintes so pegaria uma das linhas e deixaria
    #     a(s) outra(s) sem ninguem para casar.
    def _agregacao_inequivoca_financeiro_para_contabil():
        """Grupos de nome identico do lado financeiro cuja soma so pode ir
        para um unico cliente do contabil."""
        candidatos = []
        for chave, membros in _agrupar_por_chave(pendentes_financeiro, financeiro["_norm"]).items():
            if len(membros) < 2:
                continue
            alvos = [ic for ic in pendentes_contabil if _eh_relacionado(contabil.at[ic, "_norm"], chave)]
            if len(alvos) == 1:
                soma = sum(financeiro.at[j, "valor"] for j in membros)
                dif = abs(soma - contabil.at[alvos[0], "valor"])
                candidatos.append((dif, alvos, list(membros)))
        return candidatos

    def _agregacao_inequivoca_contabil_para_financeiro():
        """Espelho da funcao acima, para grupos de nome identico do lado
        contabil cuja soma so pode ir para um unico cliente do financeiro."""
        candidatos = []
        for chave, membros in _agrupar_por_chave(pendentes_contabil, contabil["_norm"]).items():
            if len(membros) < 2:
                continue
            alvos = [jf for jf in pendentes_financeiro if _eh_relacionado(financeiro.at[jf, "_norm"], chave)]
            if len(alvos) == 1:
                soma = sum(contabil.at[i, "valor"] for i in membros)
                dif = abs(soma - financeiro.at[alvos[0], "valor"])
                candidatos.append((dif, list(membros), alvos))
        return candidatos

    _casar_por_criterio(_agregacao_inequivoca_financeiro_para_contabil())
    _casar_por_criterio(_agregacao_inequivoca_contabil_para_financeiro())

    # --- Etapa 1: nome normalizado identico; empate desempatado por valor mais proximo ---
    grupos_c = _agrupar_por_chave(pendentes_contabil, contabil["_norm"])
    grupos_f = _agrupar_por_chave(pendentes_financeiro, financeiro["_norm"])
    candidatos = []
    for chave, lista_c in grupos_c.items():
        lista_f = grupos_f.get(chave)
        if not lista_f:
            continue
        for ic in lista_c:
            for jf in lista_f:
                dif = abs(contabil.at[ic, "valor"] - financeiro.at[jf, "valor"])
                candidatos.append((dif, [ic], [jf]))
    _casar_por_criterio(candidatos)

    # --- Etapa 2: prefixo (nome truncado) num sentido ou no outro, sobre o nome normalizado ---
    def _eh_prefixo(a, b):
        return a != "" and b != "" and (a.startswith(b) or b.startswith(a))

    def _candidatos_prefixo(coluna):
        candidatos = []
        for ic in pendentes_contabil:
            valor_c = contabil.at[ic, "valor"]
            texto_c = contabil.at[ic, coluna]
            if not texto_c:
                continue
            for jf in pendentes_financeiro:
                texto_f = financeiro.at[jf, coluna]
                if not texto_f or not _eh_prefixo(texto_c, texto_f):
                    continue
                sobreposicao = min(len(texto_c), len(texto_f)) / max(len(texto_c), len(texto_f))
                dif_valor = abs(valor_c - financeiro.at[jf, "valor"])
                candidatos.append(((-sobreposicao, dif_valor), [ic], [jf]))
        return candidatos

    _casar_por_criterio(_candidatos_prefixo("_norm"))

    # --- Etapa 3: so letras/numeros (remove pontuacao/espacos), igualdade exata ---
    grupos_c = _agrupar_por_chave(pendentes_contabil, contabil["_alnum"])
    grupos_f = _agrupar_por_chave(pendentes_financeiro, financeiro["_alnum"])
    candidatos = []
    for chave, lista_c in grupos_c.items():
        lista_f = grupos_f.get(chave)
        if not lista_f:
            continue
        for ic in lista_c:
            for jf in lista_f:
                dif = abs(contabil.at[ic, "valor"] - financeiro.at[jf, "valor"])
                candidatos.append((dif, [ic], [jf]))
    _casar_por_criterio(candidatos)

    # --- Etapa 4: igual a etapa 3, mas com prefixo nos dois sentidos ---
    _casar_por_criterio(_candidatos_prefixo("_alnum"))

    # --- Etapa 5: similaridade de texto (so letras/numeros), limiar 80%,
    #     priorizando pares cujo valor tambem bate exatamente ---
    candidatos = []
    for ic in pendentes_contabil:
        alnum_c = contabil.at[ic, "_alnum"]
        if not alnum_c:
            continue
        valor_c = contabil.at[ic, "valor"]
        for jf in pendentes_financeiro:
            alnum_f = financeiro.at[jf, "_alnum"]
            if not alnum_f:
                continue
            similaridade = SequenceMatcher(None, alnum_c, alnum_f).ratio()
            if similaridade < _LIMIAR_SIMILARIDADE:
                continue
            valor_f = financeiro.at[jf, "valor"]
            prioridade = (0 if _valor_bate(valor_c, valor_f) else 1, -similaridade)
            candidatos.append((prioridade, [ic], [jf]))
    _casar_por_criterio(candidatos)

    # --- Etapa 6: ultimo recurso - valor identico e unico dos dois lados entre os restantes ---
    contagem_c = Counter(round(contabil.at[i, "valor"], 2) for i in pendentes_contabil)
    contagem_f = Counter(round(financeiro.at[j, "valor"], 2) for j in pendentes_financeiro)
    candidatos = []
    for ic in pendentes_contabil:
        vc = round(contabil.at[ic, "valor"], 2)
        if contagem_c[vc] != 1:
            continue
        for jf in pendentes_financeiro:
            vf = round(financeiro.at[jf, "valor"], 2)
            if vf == vc and contagem_f[vf] == 1:
                candidatos.append((0, [ic], [jf]))
    _casar_por_criterio(candidatos)

    # --- Monta o resultado final ---
    registros = []
    for lista_ic, lista_jf in pares:
        codigo = (
            contabil.at[lista_ic[0], "codigo"]
            if len(lista_ic) == 1
            else " + ".join(str(contabil.at[i, "codigo"]) for i in lista_ic)
        )
        registros.append(
            {
                "codigo": codigo,
                "contabil": " + ".join(contabil.at[i, "nome"] for i in lista_ic),
                "valor_contabil": sum(contabil.at[i, "valor"] for i in lista_ic),
                "financeiro": " + ".join(financeiro.at[j, "nome"] for j in lista_jf),
                "valor_financeiro": sum(financeiro.at[j, "valor"] for j in lista_jf),
                "situacao": "CASADO",
            }
        )
    for ic in pendentes_contabil:
        registros.append(
            {
                "codigo": contabil.at[ic, "codigo"],
                "contabil": contabil.at[ic, "nome"],
                "valor_contabil": contabil.at[ic, "valor"],
                "financeiro": None,
                "valor_financeiro": None,
                "situacao": "SO_CONTABIL",
            }
        )
    for jf in pendentes_financeiro:
        registros.append(
            {
                "codigo": None,
                "contabil": None,
                "valor_contabil": None,
                "financeiro": financeiro.at[jf, "nome"],
                "valor_financeiro": financeiro.at[jf, "valor"],
                "situacao": "SO_FINANCEIRO",
            }
        )

    colunas = ["codigo", "contabil", "valor_contabil", "financeiro", "valor_financeiro", "situacao"]
    return pd.DataFrame(registros, columns=colunas)
