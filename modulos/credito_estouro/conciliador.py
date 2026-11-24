"""Regras da conciliação do crédito estouro — ESPECIFICACAO_CREDITO_ESTOURO.md, seção 4 (R1 a R6).

Entrada: os eventos da folha do mês, o razão da conta do mês e o controle do mês anterior.
Saída: o que aconteceu com cada colaborador, os lançamentos do razão a conferir, a prova do saldo e o controle novo
(a entrada do mês seguinte).

Por que a prova fecha: o controle do mês anterior soma o saldo anterior do razão; cada regra tira do controle o
mesmo valor que o razão baixou (0258, 1204, pagamento, rescisão) e põe o que o razão acrescentou (0256 e 0241 do
mês). O que sobra de diferença é o que nenhuma regra explicou ("diferença sem explicação", que deve ser zero).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from modulos.credito_estouro.controle import LeituraControle
from modulos.credito_estouro.modelos import (
    EVENTO_CREDITO_ESTOURO,
    EVENTO_DEBITO_ESTOURO,
    EVENTO_DEVOLUCAO,
    EVENTO_PARCELADO,
    EVENTO_REEMBOLSO_AFASTADO,
    TIPO_0256,
    TIPO_ACERTO,
    TIPO_DIFERENCA_0241,
    TIPO_PARCELAMENTO,
    TIPO_PENDENCIA,
    TIPO_VINCULO,
    TIPOS_COM_VALOR,
    ZERO,
    Aviso,
    ItemControle,
    LancamentoRazao,
    LeituraEventos,
    LeituraRazao,
)
from modulos.credito_estouro.nomes import PARTICULAS, Pessoas, palavras
from modulos.credito_estouro.util import reais, sem_acento

# R1 — frases escolhidas pelo usuário (13/11/2026)
COBRADO = "Cobrado na folha do mês seguinte – colaborador continua na folha (trabalhando ou afastado)"
COBRADO_DIFERENTE = "Cobrado na folha com valor diferente – conferir"
PARCELAMENTO_NOVO = "Parcelamento novo"
BAIXADO = "Baixado na rescisão do razão – colaborador desligado"
BAIXADO_DIFERENTE = "Baixado na rescisão do razão com valor diferente – conferir a diferença"
NAO_COBRADO = "Não cobrado na folha e não encontrado na rescisão negativa – conferir"
COBRADO_SEM_0256 = "0258 sem 0256 no mês anterior – conferir"

# R2
PAGOU_CERTO = "Pagou certo"
PAGOU_A_MAIS = "Pagou a mais"
PAGOU_A_MENOS = "Pagou a menos"
NAO_PAGOU = "Não pagou"
SEM_MOVIMENTO = "Sem movimento no mês (diferença continua)"

# R3
PARCELA_DESCONTADA = "Parcela descontada no 1204"
QUITADO_1204 = "Quitado (última parcela no 1204)"
PARCELA_DIFERENTE = "Parcela diferente – conferir"
PARCELA_MAIOR = "Parcela maior que o saldo – conferir"
QUITADO_RAZAO = "Quitado no razão"
PAGO_RAZAO_DIFERENTE = "Pago no razão com valor diferente do saldo – conferir"
PARCELA_NAO_DESCONTADA = "Parcela não descontada – conferir"
PARCELA_SEM_CONTROLE = "1204 sem parcelamento no controle – conferir"

# R4 — 0775 (regra aprovada pelo usuário, 16/11/2026)
DEVOLUCAO_ZEROU = "Devolução zerou a pendência de cobrado a mais"
DEVOLUCAO_CONFERIR = "Devolução 0775 – conferir"

# Tipos de lançamento do razão
_FOLHA_CREDITO = "folha_credito"         # 0256 + 0241
_FOLHA_DESCONTO = "folha_desconto"       # 0258 + 1204
_DEVOLUCAO = "devolucao"                 # 0775
_RESCISAO = "rescisao"
_PAGAMENTO = "pagamento"
_QUITACAO = "quitacao"
_OUTRO = "outro"


def tipo_do_lancamento(lancamento: LancamentoRazao) -> str:
    texto = sem_acento(lancamento.historico)
    if texto.startswith("devolucao desconto credito complemento"):
        return _DEVOLUCAO
    if "desconto credito complemento salario" in texto:
        return _FOLHA_DESCONTO
    if "credito complemento salario no mes" in texto and lancamento.debito:
        return _FOLHA_CREDITO
    if "rescisao negativa" in texto:
        return _RESCISAO
    if "plano de saude" in texto or "recebimento de valores" in texto:
        return _PAGAMENTO
    if "referente credito de estouro" in texto:
        return _QUITACAO
    return _OUTRO


# ---------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------
@dataclass
class LinhaCobranca:
    """R1: o 0256 do mês anterior de um colaborador."""

    matricula: str
    nome: str
    valor_0256: Decimal
    valor_0258: Decimal = ZERO
    valor_1204: Decimal = ZERO
    valor_rescisao: Decimal = ZERO
    situacao: str = ""
    diferenca: Decimal = ZERO          # o que ficou no controle como pendência


@dataclass
class LinhaAfastado:
    """R2: o 0241 do mês × os pagamentos no razão."""

    matricula: str
    nome: str
    devido: Decimal
    pago: Decimal
    diferenca_anterior: Decimal
    diferenca_nova: Decimal
    situacao: str
    pagamentos: list[LancamentoRazao] = field(default_factory=list)


@dataclass
class LinhaParcelamento:
    """R3."""

    matricula: str
    nome: str
    saldo_anterior: Decimal
    parcela: Decimal | None
    descontado_1204: Decimal
    pago_razao: Decimal
    saldo_novo: Decimal
    situacao: str


@dataclass
class LancamentoAConferir:
    """R5."""

    lancamento: LancamentoRazao
    motivo: str
    matricula: str = ""
    nome: str = ""

    @property
    def efeito(self) -> Decimal:
        return self.lancamento.debito - self.lancamento.credito


@dataclass
class LinhaDevolucao:
    """R4: o 0775 de um colaborador."""

    matricula: str
    nome: str
    valor: Decimal
    situacao: str
    pendencia: Decimal = ZERO          # a pendência de "cobrado a mais" que o 0775 zerou (negativa)


@dataclass
class ConferenciaFolha:
    """R6: um lançamento que a folha gera no razão × a soma dos eventos."""

    descricao: str
    razao: Decimal
    folha: Decimal

    @property
    def diferenca(self) -> Decimal:
        return self.razao - self.folha


@dataclass
class Conciliacao:
    competencia: date | None
    unidade: str
    saldo_anterior_razao: Decimal
    saldo_final_razao: Decimal
    total_controle_anterior: Decimal
    cobrancas: list[LinhaCobranca] = field(default_factory=list)
    afastados: list[LinhaAfastado] = field(default_factory=list)
    parcelamentos: list[LinhaParcelamento] = field(default_factory=list)
    devolucoes: list[LinhaDevolucao] = field(default_factory=list)
    a_conferir: list[LancamentoAConferir] = field(default_factory=list)
    conferencias_folha: list[ConferenciaFolha] = field(default_factory=list)
    controle_novo: list[ItemControle] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)

    @property
    def composicao(self) -> dict[str, Decimal]:
        somas = {tipo: ZERO for tipo in TIPOS_COM_VALOR}
        for item in self.controle_novo:
            if item.tipo in somas:
                somas[item.tipo] += item.valor
        return somas

    @property
    def total_controle_novo(self) -> Decimal:
        return sum((item.valor for item in self.controle_novo), ZERO)

    @property
    def diferenca_sem_explicacao(self) -> Decimal:
        return self.saldo_final_razao - self.total_controle_novo


# ---------------------------------------------------------------------
# Conciliação
# ---------------------------------------------------------------------
def _mes(competencia: date | None) -> str:
    return f"{competencia:%m/%Y}" if competencia else ""


def conciliar(eventos: LeituraEventos, razao: LeituraRazao, controle: LeituraControle) -> Conciliacao:
    competencia = eventos.competencia
    resultado = Conciliacao(competencia=competencia, unidade=eventos.unidade,
                            saldo_anterior_razao=razao.saldo_anterior or ZERO,
                            saldo_final_razao=razao.saldo_final or ZERO,
                            total_controle_anterior=controle.total)
    arquivo_razao = razao.arquivo

    # quem é quem: os nomes dos eventos do mês e do controle
    nomes: dict[str, str] = {}
    for item in controle.itens:
        if item.matricula:
            nomes.setdefault(item.matricula, item.nome)
    for linha in eventos.linhas:
        nomes[linha.matricula] = linha.nome
    vinculos = [i for i in controle.itens if i.tipo == TIPO_VINCULO]
    pessoas = Pessoas(nomes, {v.pagador: v.matricula for v in vinculos})

    # lançamentos do razão por tipo, com o colaborador de cada um
    por_tipo: dict[str, list[LancamentoRazao]] = defaultdict(list)
    colaborador: dict[int, str | None] = {}
    usados: set[int] = set()
    for lancamento in razao.lancamentos:
        tipo = tipo_do_lancamento(lancamento)
        por_tipo[tipo].append(lancamento)
        if tipo in (_RESCISAO, _PAGAMENTO, _QUITACAO, _OUTRO):
            colaborador[id(lancamento)] = pessoas.do_historico(lancamento.historico)[0]

    def do_colaborador(tipo: str, matricula: str) -> list[LancamentoRazao]:
        return [l for l in por_tipo[tipo] if id(l) not in usados and colaborador.get(id(l)) == matricula]

    # R6 (parte 1): o que a folha lançou no razão = os eventos
    resultado.conferencias_folha = [
        ConferenciaFolha("\"Crédito complemento salário no mês\" = 0256 + 0241",
                         sum((l.debito for l in por_tipo[_FOLHA_CREDITO]), ZERO),
                         eventos.total(EVENTO_CREDITO_ESTOURO) + eventos.total(EVENTO_REEMBOLSO_AFASTADO)),
        ConferenciaFolha("\"Desconto crédito complemento salário\" = 0258 + 1204",
                         sum((l.credito for l in por_tipo[_FOLHA_DESCONTO]), ZERO),
                         eventos.total(EVENTO_DEBITO_ESTOURO) + eventos.total(EVENTO_PARCELADO)),
    ]
    if por_tipo[_DEVOLUCAO] or eventos.quantidade(EVENTO_DEVOLUCAO):
        resultado.conferencias_folha.append(ConferenciaFolha(
            "\"Devolução desconto crédito complemento salário\" = 0775",
            sum((l.debito - l.credito for l in por_tipo[_DEVOLUCAO]), ZERO), eventos.total(EVENTO_DEVOLUCAO)))
    for lancamento in por_tipo[_FOLHA_CREDITO] + por_tipo[_FOLHA_DESCONTO] + por_tipo[_DEVOLUCAO]:
        usados.add(id(lancamento))
    for conferencia in resultado.conferencias_folha:
        if conferencia.diferenca:
            dica = ""
            if "0775" in conferencia.descricao and conferencia.folha > conferencia.razao:
                dica = (" Se a devolução ainda não foi lançada no razão, escolha esse PDF do 0775 na conciliação do "
                        "mês em que ela for lançada (o PDF pode ser de um mês anterior).")
            resultado.avisos.append(Aviso(arquivo_razao, f"ATENÇÃO: {conferencia.descricao}: razão R$ "
                                                         f"{reais(conferencia.razao)}, eventos R$ "
                                                         f"{reais(conferencia.folha)}.{dica}"))
    if razao.saldo_anterior is not None and controle.total != razao.saldo_anterior:
        resultado.avisos.append(Aviso(controle.arquivo,
                                      f"ATENÇÃO: o controle do mês anterior soma R$ {reais(controle.total)}, mas o "
                                      f"saldo anterior do razão é R$ {reais(razao.saldo_anterior)}. A diferença "
                                      "aparece na prova do saldo."))
    if por_tipo[_DEVOLUCAO] and not eventos.quantidade(EVENTO_DEVOLUCAO):
        resultado.avisos.append(Aviso(arquivo_razao,
                                      "O razão tem \"Devolução desconto crédito complemento salário\", mas nenhum PDF "
                                      "escolhido tem o evento 0775: escolha também o PDF do 0775 do mês (ele vem "
                                      "separado do relatório de eventos)."))

    saldo_1204 = eventos.por_matricula(EVENTO_PARCELADO)
    saldo_0258 = eventos.por_matricula(EVENTO_DEBITO_ESTOURO)
    novo: list[ItemControle] = []

    # R3 — parcelamentos do controle
    for item in [i for i in controle.itens if i.tipo == TIPO_PARCELAMENTO]:
        parcela_mes = saldo_1204.pop(item.matricula, ZERO)
        pago_razao = ZERO
        saldo_novo = item.valor - parcela_mes
        if parcela_mes:
            if item.parcela and parcela_mes != item.parcela and saldo_novo != 0:
                situacao = PARCELA_DIFERENTE
            elif saldo_novo == 0:
                situacao = QUITADO_1204
            elif saldo_novo < 0:
                situacao = PARCELA_MAIOR
            else:
                situacao = PARCELA_DESCONTADA
        else:
            quitacoes = do_colaborador(_QUITACAO, item.matricula)
            if quitacoes:
                usados.update(id(l) for l in quitacoes)
                pago_razao = sum((l.credito - l.debito for l in quitacoes), ZERO)
                saldo_novo = item.valor - pago_razao
                situacao = QUITADO_RAZAO if saldo_novo == 0 else PAGO_RAZAO_DIFERENTE
            else:
                situacao = PARCELA_NAO_DESCONTADA
        resultado.parcelamentos.append(LinhaParcelamento(item.matricula, item.nome, item.valor, item.parcela,
                                                         parcela_mes, pago_razao, saldo_novo, situacao))
        if saldo_novo:
            novo.append(ItemControle(item.matricula, item.nome, TIPO_PARCELAMENTO, item.origem, saldo_novo,
                                     item.parcela, item.observacao))

    # R1 — o 0256 do mês anterior
    anteriores: dict[str, Decimal] = defaultdict(lambda: ZERO)
    origem_0256: dict[str, date | None] = {}
    for item in controle.itens:
        if item.tipo == TIPO_0256:
            anteriores[item.matricula] += item.valor
            origem_0256.setdefault(item.matricula, item.origem)
    for matricula, valor in anteriores.items():
        nome = pessoas.nome(matricula)
        linha = LinhaCobranca(matricula, nome, valor)
        mes_origem = _mes(origem_0256.get(matricula))
        cobrado = saldo_0258.pop(matricula, ZERO)
        if cobrado:
            linha.valor_0258 = cobrado
            linha.situacao = COBRADO if cobrado == valor else COBRADO_DIFERENTE
            linha.diferenca = valor - cobrado
        elif saldo_1204.get(matricula):
            parcela = saldo_1204.pop(matricula)
            linha.valor_1204 = parcela
            linha.situacao = PARCELAMENTO_NOVO
            saldo_parcelamento = valor - parcela
            resultado.parcelamentos.append(LinhaParcelamento(
                matricula, nome, valor, parcela, parcela, ZERO, saldo_parcelamento,
                f"{PARCELAMENTO_NOVO} (0256 de {mes_origem}): 1ª parcela no 1204"))
            if saldo_parcelamento:
                novo.append(ItemControle(matricula, nome, TIPO_PARCELAMENTO, origem_0256.get(matricula),
                                         saldo_parcelamento, parcela,
                                         f"0256 de {mes_origem} (R$ {reais(valor)}) parcelado no 1204"))
        else:
            rescisoes = do_colaborador(_RESCISAO, matricula)
            if rescisoes:
                usados.update(id(l) for l in rescisoes)
                linha.valor_rescisao = sum((l.credito - l.debito for l in rescisoes), ZERO)
                linha.situacao = BAIXADO if linha.valor_rescisao == valor else BAIXADO_DIFERENTE
                linha.diferenca = valor - linha.valor_rescisao
            else:
                linha.situacao = NAO_COBRADO
                linha.diferenca = valor
        if linha.diferenca:
            novo.append(ItemControle(matricula, nome, TIPO_PENDENCIA, origem_0256.get(matricula), linha.diferenca,
                                     observacao=f"{linha.situacao} (0256 de {mes_origem}: R$ {reais(valor)})"))
        resultado.cobrancas.append(linha)
    for matricula, cobrado in saldo_0258.items():          # 0258 de quem não tinha 0256 no controle
        nome = pessoas.nome(matricula)
        resultado.cobrancas.append(LinhaCobranca(matricula, nome, ZERO, valor_0258=cobrado,
                                                 situacao=COBRADO_SEM_0256, diferenca=-cobrado))
        novo.append(ItemControle(matricula, nome, TIPO_PENDENCIA, competencia, -cobrado,
                                 observacao=f"{COBRADO_SEM_0256} (0258 de {_mes(competencia)})"))
    for matricula, parcela in saldo_1204.items():          # 1204 de quem não tinha parcelamento nem 0256
        nome = pessoas.nome(matricula)
        resultado.parcelamentos.append(LinhaParcelamento(matricula, nome, ZERO, None, parcela, ZERO, -parcela,
                                                         PARCELA_SEM_CONTROLE))
        novo.append(ItemControle(matricula, nome, TIPO_PENDENCIA, competencia, -parcela,
                                 observacao=f"{PARCELA_SEM_CONTROLE} (1204 de {_mes(competencia)})"))

    # R2 — afastados: 0241 do mês × pagamentos no razão
    devidos = eventos.por_matricula(EVENTO_REEMBOLSO_AFASTADO)
    diferencas: dict[str, Decimal] = defaultdict(lambda: ZERO)
    origem_diferenca: dict[str, date | None] = {}
    for item in controle.itens:
        if item.tipo == TIPO_DIFERENCA_0241:
            diferencas[item.matricula] += item.valor
            origem_diferenca.setdefault(item.matricula, item.origem)
    pagamentos: dict[str, list[LancamentoRazao]] = defaultdict(list)
    # pagamento do afastado: plano de saúde / tesouraria e, se não quitou parcelamento, "Referente crédito de
    # estouro … não lançado na folha" no nome de quem tem 0241 ou diferença
    for lancamento in por_tipo[_PAGAMENTO] + por_tipo[_QUITACAO]:
        if id(lancamento) in usados:
            continue
        matricula = colaborador.get(id(lancamento))
        if matricula and (matricula in devidos or matricula in diferencas):
            pagamentos[matricula].append(lancamento)
            usados.add(id(lancamento))
    for matricula in list(devidos) + [m for m in diferencas if m not in devidos]:
        devido = devidos.get(matricula, ZERO)
        anterior = diferencas.get(matricula, ZERO)
        pagos = pagamentos.get(matricula, [])
        pago = sum((l.credito - l.debito for l in pagos), ZERO)
        if not devido and not pagos:
            situacao = SEM_MOVIMENTO
        elif pago == devido + anterior:
            situacao = PAGOU_CERTO
        elif not pago:
            situacao = NAO_PAGOU
        elif pago > devido + anterior:
            situacao = PAGOU_A_MAIS
        else:
            situacao = PAGOU_A_MENOS
        diferenca_nova = anterior + devido - pago
        nome = pessoas.nome(matricula)
        resultado.afastados.append(LinhaAfastado(matricula, nome, devido, pago, anterior, diferenca_nova, situacao,
                                                 pagos))
        if diferenca_nova:
            novo.append(ItemControle(matricula, nome, TIPO_DIFERENCA_0241,
                                     origem_diferenca.get(matricula, competencia) if not devido else competencia,
                                     diferenca_nova, observacao=f"{situacao} em {_mes(competencia)}"))

    # pendências, acertos e "quem paga por quem" continuam até alguém apagar a linha
    novo.extend(i for i in controle.itens if i.tipo in (TIPO_PENDENCIA, TIPO_ACERTO, TIPO_VINCULO))

    # R4 — 0775: zera a pendência de "cobrado a mais" do mesmo valor; senão, "Devolução 0775 – conferir"
    for matricula, valor in eventos.por_matricula(EVENTO_DEVOLUCAO).items():
        nome = pessoas.nome(matricula)
        pendencia = next((i for i in novo if i.tipo == TIPO_PENDENCIA and i.matricula == matricula
                          and i.valor == -valor), None)
        if pendencia is not None:
            novo.remove(pendencia)
            resultado.devolucoes.append(LinhaDevolucao(matricula, nome, valor, DEVOLUCAO_ZEROU, pendencia.valor))
        else:
            resultado.devolucoes.append(LinhaDevolucao(matricula, nome, valor, DEVOLUCAO_CONFERIR))
            novo.append(ItemControle(matricula, nome, TIPO_PENDENCIA, competencia, valor,
                                     observacao=f"{DEVOLUCAO_CONFERIR} (0775 de {_mes(competencia)}: R$ "
                                                f"{reais(valor)}, sem pendência de cobrado a mais nesse valor)"))

    # R5 — o que o razão tem e nenhuma regra explicou
    motivos = {_RESCISAO: "Rescisão negativa de quem não tinha 0256 no controle",
               _PAGAMENTO: "Pagamento de quem não tem 0241 no mês nem diferença no controle",
               _QUITACAO: "\"Referente crédito de estouro\" de quem não tem parcelamento no controle",
               _OUTRO: "Lançamento manual que não se encaixa em nenhuma regra"}
    for lancamento in razao.lancamentos:
        if id(lancamento) in usados:
            continue
        tipo = tipo_do_lancamento(lancamento)
        matricula = colaborador.get(id(lancamento)) or ""
        nome = pessoas.nome(matricula)
        motivo = motivos[tipo]
        if tipo == _PAGAMENTO and not matricula:
            motivo = "Pagamento sem colaborador identificado no histórico" + _sugestao(lancamento, devidos,
                                                                                      diferencas, pessoas)
        resultado.a_conferir.append(LancamentoAConferir(lancamento, motivo, matricula, nome))
        data = f"{lancamento.data:%d/%m/%Y} " if lancamento.data else ""
        novo.append(ItemControle(matricula, nome, TIPO_ACERTO, competencia, lancamento.debito - lancamento.credito,
                                 observacao=f"{data}{lancamento.historico}"))

    # o 0256 do mês: a cobrar no mês seguinte
    for matricula, valor in eventos.por_matricula(EVENTO_CREDITO_ESTOURO).items():
        novo.append(ItemControle(matricula, pessoas.nome(matricula), TIPO_0256, competencia, valor))

    resultado.controle_novo = novo
    return resultado


def _sugestao(lancamento: LancamentoRazao, devidos: dict[str, Decimal], diferencas: dict[str, Decimal],
              pessoas: Pessoas) -> str:
    """Pagamento em nome de outra pessoa: sugere o afastado com o mesmo sobrenome (0241 ou diferença no mês)."""
    texto = set(palavras(lancamento.historico))
    candidatos = sorted(m for m in set(devidos) | set(diferencas)
                        if (sobrenome := _sobrenome(pessoas.nome(m))) and sobrenome in texto)
    if len(candidatos) != 1:
        return ""
    matricula = candidatos[0]
    return (f". Se for pagamento por {pessoas.nome(matricula)} (matrícula {matricula}), acrescente no controle uma "
            f"linha \"{TIPO_VINCULO}\" com a matrícula dele e o nome do pagador como aparece no histórico")


def _sobrenome(nome: str) -> str:
    partes = [p for p in palavras(nome) if p not in PARTICULAS]
    return partes[-1] if len(partes) > 1 else ""


def montar_controle_inicial(eventos: LeituraEventos, outros: list[ItemControle]) -> list[ItemControle]:
    """Primeira vez (seção 3.3): o 0256 de cada colaborador no PDF do mês + os parcelamentos e diferenças da
    planilha feita à mão."""
    itens = [ItemControle(matricula, next(l.nome for l in eventos.do_evento(EVENTO_CREDITO_ESTOURO)
                                          if l.matricula == matricula),
                          TIPO_0256, eventos.competencia, valor)
             for matricula, valor in eventos.por_matricula(EVENTO_CREDITO_ESTOURO).items()]
    return itens + list(outros)
