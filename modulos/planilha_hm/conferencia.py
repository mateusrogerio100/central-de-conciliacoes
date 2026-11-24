"""Conferência final: TOTAL GERAL do mês × Movimento. Regra R9.

O openpyxl não calcula fórmulas: o próprio módulo faz a conta que o Excel vai fazer na cópia gravada.
- Linha de evento = SOMASE da aba Senior do mês pelo evento (a soma dos subtotais do evento).
- Linha de CC = a soma do evento + CC na aba Senior.
- Total da seção = as linhas que a fórmula do total soma naquele mês; TOTAL GERAL = os totais que a fórmula dele
  soma naquele mês.
Se o TOTAL GERAL não bater com o Movimento, a conferência lista: os eventos que não entraram em nenhuma seção;
a comparação Eventos × Movimento dos eventos que o Movimento identifica ("Evento NNNN" no histórico); e as
linhas do Movimento sem evento identificado (para conferência manual).
"""

from __future__ import annotations

from modulos.planilha_hm.modelos import (
    ZERO,
    Aviso,
    ComparacaoEvento,
    Conferencia,
    Eventos,
    Movimento,
    Planilha,
    TotalSecao,
)
from modulos.planilha_hm.normalizacao import formatar_valor


def totais_do_mes(planilha: Planilha, mes: int):
    """(totais de cada seção, TOTAL GERAL) do mês, como o Excel vai calcular a partir da aba Senior do mês."""
    senior = planilha.seniors.get(mes)
    valores = senior.valores if senior else {}
    valores_cc = senior.valores_cc if senior else {}
    valor_da_linha = {}
    for evento in planilha.eventos:
        valor_da_linha[evento.linha] = valores.get(evento.numero, ZERO)
        for cc in evento.ccs:
            valor_da_linha[cc.linha] = valores_cc.get((evento.numero, cc.codigo), ZERO) if cc.codigo else ZERO
    totais = []
    for secao in planilha.secoes:
        if secao.linha_total is None:
            continue
        valor = sum((valor_da_linha.get(l, ZERO) for l in secao.linhas_no_total_mes.get(mes, [])), ZERO)
        totais.append(TotalSecao(secao.nome, secao.nome_total, secao.linha_total, valor))
    valor_do_total = {t.linha: t.valor for t in totais}
    total_geral = sum((valor_do_total.get(l, ZERO) for l in planilha.linhas_no_total_geral_mes.get(mes, [])), ZERO)
    return totais, total_geral


def conferir(eventos: Eventos, movimento: Movimento, planilha: Planilha) -> Conferencia:
    """R9 sobre a cópia gravada (lida de novo com ler_planilha)."""
    mes = eventos.mes
    totais, total_geral = totais_do_mes(planilha, mes)
    conferencia = Conferencia(mes, planilha.ano, eventos.total, total_geral, movimento.total, totais)

    somados = {l for s in planilha.secoes for l in s.linhas_no_total_mes.get(mes, [])}
    for evento in eventos.eventos:
        linha = planilha.evento(evento.numero)
        if not evento.ok or linha is None or linha.linha not in somados:
            conferencia.eventos_fora.append(evento)

    por_evento: dict[int, object] = {}
    for linha in movimento.linhas:
        if linha.tem_debito and linha.evento is not None:
            por_evento[linha.evento] = por_evento.get(linha.evento, ZERO) + linha.valor
        elif linha.tem_debito:
            conferencia.linhas_sem_evento.append(linha)
    do_relatorio = {e.numero: e for e in eventos.eventos}
    for numero in sorted(por_evento):
        evento = do_relatorio.get(numero)
        valor_eventos = (evento.total if evento is not None and evento.total is not None else ZERO)
        conferencia.comparacao.append(ComparacaoEvento(numero, evento.nome if evento else "(não está no Eventos)",
                                                       valor_eventos, por_evento[numero]))

    origem = f"Conferência {mes:02d}/{planilha.ano}"
    if not conferencia.ok:
        partes = [f"TOTAL GERAL {formatar_valor(total_geral)} × Movimento {formatar_valor(movimento.total)}: "
                  f"diferença de {formatar_valor(conferencia.diferenca)}."]
        if conferencia.eventos_fora:
            partes.append("Eventos fora da planilha: " + ", ".join(
                f"{e.numero} ({formatar_valor(e.total or ZERO)})" for e in conferencia.eventos_fora) + ".")
        diferentes = [c for c in conferencia.comparacao if c.diferenca]
        if diferentes:
            partes.append("Eventos com valor diferente no Movimento: " + ", ".join(
                f"{c.evento} ({formatar_valor(c.diferenca)})" for c in diferentes) + ".")
        partes.append(f"{len(conferencia.linhas_sem_evento)} linha(s) do Movimento sem o evento no histórico ficam "
                      "para conferência manual (aba do relatório).")
        conferencia.avisos.append(Aviso(origem, " ".join(partes), erro=True))
    if eventos.total != total_geral and conferencia.ok:
        conferencia.avisos.append(Aviso(origem, f"O total do Eventos ({formatar_valor(eventos.total)}) é diferente do "
                                                f"TOTAL GERAL ({formatar_valor(total_geral)})."))
    return conferencia
