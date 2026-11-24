"""Conferência do Check list com o movimento. Regras K2, K3 e R1 a R10 da especificação.

- K2: cada regra aponta para Aba + Linha do Check list.
- K3: se o Fornecedor e a Descrição normalizados daquela linha não forem os da regra, procura na aba
  a linha que tem os dois. Achou = usa essa linha e avisa; não achou = a regra é pulada, com aviso.
- R1 a R8: candidatos, conta, seleção, valor, divergência de verdade, situação, nunca sobrescrever e
  variação, uma linha do Check list por vez.
- Centro_Custo (opcional): a regra só fica com as NFs que têm um centro de custo que casa. Se o
  movimento do estabelecimento não tem centro de custo (o .csv do "Movimentos NF"), não dá para
  separar: a regra vira MANUAL, com todos os candidatos e um aviso.
- R9: lançamentos de fornecedores do Check list que nenhuma regra usou, mais as devoluções (M4).
- R10: toda regra aparece no resultado ou nos avisos (as puladas pela K3).
"""

from __future__ import annotations

from decimal import Decimal

from modulos.checklist_contratos import configuracao as cfg
from modulos.checklist_contratos.modelos import (
    AbaChecklist,
    Aviso,
    Checklist,
    Conferencia,
    Configuracao,
    Lancamento,
    Movimento,
    NaoVinculado,
    Regra,
    ResultadoLinha,
    Situacao,
)
from modulos.checklist_contratos.normalizacao import normalizar


def _identidade(fornecedor: str, descricao: str) -> tuple[str, str]:
    return normalizar(fornecedor), normalizar(descricao)


def localizar_linha(regra: Regra, aba: AbaChecklist) -> tuple[int | None, Aviso | None]:
    """K2/K3: a linha da planilha que a regra confere (None = regra pulada) e o aviso, se houver."""
    origem = f"regra {regra.aba} linha {regra.linha}"
    if not regra.fornecedor_planilha:          # sem o texto da planilha não há como relocalizar
        return regra.linha, None
    esperado = _identidade(regra.fornecedor_planilha, regra.descricao_planilha)
    linha = aba.linha(regra.linha)
    if linha and _identidade(linha.fornecedor, linha.descricao_despesa) == esperado:
        return regra.linha, None
    nova = next((l for l in aba.linhas
                 if _identidade(l.fornecedor, l.descricao_despesa) == esperado), None)
    if nova is None:
        return None, Aviso(origem, f"\"{regra.fornecedor_planilha} – {regra.descricao_planilha}\" "
                                   f"não foi encontrado na aba {aba.nome}: regra pulada. Atualize o "
                                   "regras.csv.")
    return nova.numero, Aviso(origem, f"A regra da linha {regra.linha} agora está na linha "
                                      f"{nova.numero}. Atualize o regras.csv.")


def candidatos(regra: Regra, lancamentos: list[Lancamento], usar_centro_custo: bool = True) -> list[Lancamento]:
    """R1: o complemento casa com Busca_Fornecedor (e Busca_Descricao) e não casa com Excluir; com
    Centro_Custo, algum centro de custo da NF também precisa casar."""
    return [l for l in lancamentos
            if regra.busca_fornecedor.search(l.complemento_normalizado)
            and (regra.busca_descricao is None or regra.busca_descricao.search(l.complemento_normalizado))
            and (regra.excluir is None or not regra.excluir.search(l.complemento_normalizado))
            and (regra.centro_custo is None or not usar_centro_custo or _casa_centro_custo(regra, l))]


def _casa_centro_custo(regra: Regra, lancamento: Lancamento) -> bool:
    return any(nome and regra.centro_custo.search(normalizar(nome)) for nome, _ in lancamento.centros_custo)


def _tem_centro_custo(lancamentos: list[Lancamento]) -> bool:
    """O movimento traz o centro de custo? (só o "Movimento contábil" traz)"""
    return any(nome for l in lancamentos for nome, _ in l.centros_custo)


def _numero(valor) -> Decimal | None:
    """Célula com número -> Decimal; texto, vazia ou booleano -> None."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float, Decimal)):
        return None
    return Decimal(str(valor)).quantize(Decimal("0.01"))


def _diz_provisao(valor) -> bool:
    """R7a: célula do mês com texto de provisão ("Provisão", "provisionar", "fazer provisão"...)."""
    return isinstance(valor, str) and cfg.TEXTO_PROVISAO in normalizar(valor)


def _celula_preenchida(valor) -> bool:
    return valor is not None and str(valor).strip() != ""


def conferir(movimentos: dict[str, Movimento], checklist: Checklist, configuracao: Configuracao) -> Conferencia:
    """Confere cada regra do regras.csv com o movimento do estabelecimento dela."""
    conferencia = Conferencia()
    lancamentos = {e: (m.lancamentos if m else []) for e, m in movimentos.items()}
    com_centro_custo = {e: _tem_centro_custo(l) for e, l in lancamentos.items()}

    # 1ª passada (R1-R3): candidatos de cada regra; marca os achados na conta certa das regras auto (R5)
    preparadas = []
    usados_na_conta_certa: set[int] = set()
    for regra in configuracao.regras:
        aba = checklist.abas[regra.aba]
        numero, aviso = localizar_linha(regra, aba)
        if aviso:
            conferencia.avisos.append(aviso)
        if numero is None:
            continue
        sem_centro = regra.centro_custo is not None and not com_centro_custo.get(regra.aba, False)
        if sem_centro:
            conferencia.avisos.append(Aviso(
                f"regra {regra.aba} linha {regra.linha}", "A regra separa as NFs pelo centro de custo, mas o "
                "movimento não tem essa coluna: a linha ficou MANUAL. Use o \"Movimento contábil\" do Tasy."))
        todos = candidatos(regra, lancamentos.get(regra.aba, []), usar_centro_custo=not sem_centro)
        achados = [l for l in todos if l.conta in regra.contas]
        suspeitos = [l for l in todos if l.conta not in regra.contas]
        if len(achados) > 1 and regra.selecao == "maior":
            achados = [max(achados, key=lambda l: l.valor)]
        elif len(achados) > 1 and regra.selecao == "menor":
            achados = [min(achados, key=lambda l: l.valor)]
        if regra.tipo == cfg.TIPO_AUTO and not sem_centro:
            usados_na_conta_certa.update(id(l) for l in achados)
        preparadas.append((regra, aba.linha(numero), todos, achados, suspeitos, sem_centro))

    # 2ª passada (R4-R8): situação de cada linha
    for regra, linha, todos, achados, suspeitos, sem_centro in preparadas:
        divergentes = [l for l in suspeitos if id(l) not in usados_na_conta_certa]
        soma = sum((l.valor for l in achados), Decimal("0"))
        resultado = ResultadoLinha(regra, linha, Situacao.NAO_ENCONTRADO, achados=achados,
                                   divergentes=divergentes, candidatos=todos)
        if regra.tipo == cfg.TIPO_IGNORAR:
            resultado.situacao = Situacao.IGNORADO
        elif regra.tipo == cfg.TIPO_MANUAL or sem_centro:
            resultado.situacao = Situacao.MANUAL
        elif divergentes:
            resultado.situacao = Situacao.CONTA_DIVERGENTE
            resultado.valor = soma if achados else None
        elif achados:
            resultado.situacao = Situacao.OK
            resultado.valor = soma
            resultado.celula_preenchida = _celula_preenchida(linha.valor_mes)
            resultado.gravar = not resultado.celula_preenchida
            na_celula = _numero(linha.valor_mes)
            resultado.valor_diferente = na_celula is not None and na_celula != soma
        resultado.provisao = resultado.valor is not None and _diz_provisao(linha.valor_mes)
        anterior = _numero(linha.valor_mes_anterior)
        if resultado.valor is not None and anterior:
            resultado.variacao = ((resultado.valor - anterior) / anterior * 100).quantize(Decimal("0.01"))
            resultado.variacao_destacada = abs(resultado.variacao) >= cfg.LIMITE_VARIACAO_PERCENTUAL
        conferencia.resultados.append(resultado)

    conferencia.nao_vinculados = _nao_vinculados(movimentos, preparadas, configuracao)
    return conferencia


def _nao_vinculados(movimentos: dict[str, Movimento], preparadas, configuracao: Configuracao) -> list[NaoVinculado]:
    """R9: lançamentos de fornecedor do Check list que nenhuma regra usou, mais as devoluções (M4)."""
    saida = []
    for estabelecimento, movimento in movimentos.items():
        if not movimento:
            continue
        regras = [r for r in configuracao.regras if r.aba == estabelecimento and r.tipo != cfg.TIPO_IGNORAR]
        expressoes = [r.busca_fornecedor for r in regras]
        # fornecedor de regra que separa pelo centro de custo: o motivo diz qual centro ficou sem linha
        por_centro = [r.busca_fornecedor for r in regras if r.centro_custo is not None]
        usados = {id(l) for regra, _, _, achados, suspeitos, _ in preparadas if regra.aba == estabelecimento
                  for l in achados + suspeitos}
        for lancamento in movimento.lancamentos:
            if id(lancamento) in usados or lancamento.conta in cfg.CONTAS_ESTOQUE:
                continue
            if lancamento.conta == cfg.CONTA_RECLASSIFICAR:
                saida.append(NaoVinculado(lancamento, "Conta 23334 - fornecedores a reclassificar"))
            elif any(e.search(lancamento.complemento_normalizado) for e in por_centro):
                centros = ", ".join(nome for nome, _ in lancamento.centros_custo if nome) or "sem centro de custo"
                saida.append(NaoVinculado(lancamento, f"Centro de custo sem linha no Check list ({centros})"))
            elif any(e.search(lancamento.complemento_normalizado) for e in expressoes):
                saida.append(NaoVinculado(lancamento, "Fornecedor do Check list sem linha correspondente"))
        for lancamento in movimento.devolucoes:
            if lancamento.conta not in cfg.CONTAS_ESTOQUE and (
                    lancamento.conta == cfg.CONTA_RECLASSIFICAR
                    or any(e.search(lancamento.complemento_normalizado) for e in expressoes)):
                saida.append(NaoVinculado(lancamento, "Devolução de NF (não é nota a conferir)"))
    return saida
