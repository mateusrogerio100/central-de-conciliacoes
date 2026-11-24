"""V3 — regras R1 a R6 com um mês fictício que tem um caso de cada situação (ESPECIFICACAO, seção 4)."""

from datetime import date
from decimal import Decimal as D

import pytest

from modulos.credito_estouro import conciliador as c
from modulos.credito_estouro.controle import LeituraControle
from modulos.credito_estouro.modelos import (
    TIPO_0256,
    TIPO_ACERTO,
    TIPO_DIFERENCA_0241,
    TIPO_PARCELAMENTO,
    TIPO_PENDENCIA,
    TIPO_VINCULO,
    LancamentoRazao,
    LeituraEventos,
    LeituraRazao,
    LinhaEvento,
    ItemControle,
)

ABRIL, MAIO = date(2026, 4, 1), date(2026, 5, 1)

CONTROLE_ANTERIOR = [
    # R1
    ItemControle("101", "ANA COBRADA", TIPO_0256, ABRIL, D("100.00")),
    ItemControle("102", "BRUNO DIFERENTE", TIPO_0256, ABRIL, D("20.00")),
    ItemControle("103", "CARLA PARCELADA", TIPO_0256, ABRIL, D("420.07")),
    ItemControle("104", "DANIEL DESLIGADO", TIPO_0256, ABRIL, D("500.00")),
    ItemControle("105", "EVA RESCISAO TESTE", TIPO_0256, ABRIL, D("300.00")),
    ItemControle("106", "FABIO SUMIDO", TIPO_0256, ABRIL, D("70.00")),
    # R2
    ItemControle("206", "MARIO ANTERIOR", TIPO_DIFERENCA_0241, ABRIL, D("-30.00")),
    ItemControle("207", "NAIR VINCULO", TIPO_VINCULO, None, D("0"), pagador="Otavia Pagadora Exemplo"),
    # R3
    ItemControle("301", "RITA PARCELA", TIPO_PARCELAMENTO, ABRIL, D("300.00"), D("100.00")),
    ItemControle("302", "SERGIO ULTIMA", TIPO_PARCELAMENTO, ABRIL, D("50.00"), D("100.00")),
    ItemControle("303", "TANIA QUITOU TESTE", TIPO_PARCELAMENTO, ABRIL, D("635.56"), D("717.36")),
    ItemControle("304", "URSULA ESQUECIDA", TIPO_PARCELAMENTO, ABRIL, D("90.00"), D("45.00")),
    ItemControle("305", "VALTER PARCELA DIF", TIPO_PARCELAMENTO, ABRIL, D("300.00"), D("100.00")),
    # carregados sem mudança
    ItemControle("401", "XAVIER PENDENTE", TIPO_PENDENCIA, ABRIL, D("12.34"), observacao="de antes"),
]

EVENTOS_MAIO = {
    "0256": [("101", "ANA COBRADA", "110.00"), ("201", "HELENA AFASTADA EXEMPLO", "300.00")],
    "0258": [("101", "ANA COBRADA", "100.00"), ("102", "BRUNO DIFERENTE", "830.50"),
             ("107", "GUSTAVO SEM ANTERIOR", "40.00")],
    "1204": [("103", "CARLA PARCELADA", "140.02"), ("301", "RITA PARCELA", "100.00"),
             ("302", "SERGIO ULTIMA", "50.00"), ("305", "VALTER PARCELA DIF", "90.00"),
             ("306", "WILSON SEM CONTROLE", "25.00")],
    "0241": [("201", "HELENA AFASTADA EXEMPLO", "300.00"), ("202", "IGOR MENOS TESTE", "200.00"),
             ("203", "JULIA MAIS TESTE", "100.00"), ("204", "KLEBER NAOPAGOU", "80.00"),
             ("205", "LUCIA SOUZA", "60.00"), ("206", "MARIO ANTERIOR", "30.00"),
             ("207", "NAIR VINCULO", "90.00"), ("208", "PEDRO ALVES RAMOS", "45.00")],
    # R4: o 0775 do 102 zera a pendência de "cobrado a mais" (830,50 − 20,00); o do 501 não acha pendência
    "0775": [("102", "BRUNO DIFERENTE", "810.50"), ("501", "ZECA DEVOLVIDO", "15.00")],
}

# lançamentos manuais do razão de maio: (histórico, débito, crédito)
MANUAIS = [
    ("Referente Rescisão negativa do colaborador Daniel Desligado crachá 104", "0", "500.00"),
    ("Referente Rescisão negativa da colaboradora Eva Rescisao Teste", "0", "250.00"),
    ("Desconto Plano de Saúde em folha Título 1 Helena Afastada Exemplo", "0", "300.00"),
    ("Recebimento de valores na tesouraria Igor Menos Teste", "0", "150.00"),
    ("Recebimento de valores na tesouraria Julia Mais Teste", "0", "120.00"),
    ("Desconto Plano de Saúde em folha Título 2 Lucia Sousa", "0", "60.00"),
    ("Recebimento de valores na tesouraria Otavia Pagadora Exemplo plano de saude", "0", "90.00"),
    ("Recebimento de valores na tesouraria Quiteria Desconhecida Ramos plano de saude", "0", "45.00"),
    ("Referente Credito de estouro Tania Quitou Teste", "0", "635.56"),
    ("Ajuste qualquer sem nome", "10.00", "0"),
]


def _eventos(blocos=EVENTOS_MAIO) -> LeituraEventos:
    leitura = LeituraEventos(arquivo="eventos.pdf", unidade="FUNDAÇÃO TESTE", competencia=MAIO)
    for evento, pessoas in blocos.items():
        for matricula, nome, valor in pessoas:
            leitura.linhas.append(LinhaEvento(evento, matricula, nome, D(valor)))
    return leitura


def _razao(eventos: LeituraEventos, saldo_anterior: D, manuais=MANUAIS, ajuste_folha=D("0"),
           com_devolucao: bool = True) -> LeituraRazao:
    razao = LeituraRazao(arquivo="razao.xls", saldo_anterior=saldo_anterior, inicio=MAIO, fim=date(2026, 5, 31))
    folha_credito = eventos.total("0256") + eventos.total("0241") + ajuste_folha
    folha_desconto = eventos.total("0258") + eventos.total("1204")
    razao.lancamentos.append(LancamentoRazao(date(2026, 5, 31), "Credito complemento salário no mês 0526", "1",
                                             folha_credito, D("0")))
    razao.lancamentos.append(LancamentoRazao(date(2026, 5, 31), "Desconto crédito complemento salário no mês 0526",
                                             "1", D("0"), folha_desconto))
    if com_devolucao and eventos.total("0775"):
        razao.lancamentos.append(LancamentoRazao(date(2026, 5, 31), "Devolução desconto credito complemento salário "
                                                 "no mês 0526", "1", eventos.total("0775"), D("0")))
    for historico, debito, credito in manuais:
        razao.lancamentos.append(LancamentoRazao(date(2026, 5, 20), historico, "2", D(debito), D(credito)))
    return razao


def _controle(itens=CONTROLE_ANTERIOR) -> LeituraControle:
    return LeituraControle(arquivo="controle.xlsx", competencia=ABRIL, itens=list(itens))


@pytest.fixture(scope="module")
def resultado():
    eventos = _eventos()
    controle = _controle()
    return c.conciliar(eventos, _razao(eventos, controle.total), controle)


def _por_matricula(linhas):
    return {l.matricula: l for l in linhas}


def test_prova_fecha_e_a_folha_bate_com_o_razao(resultado):
    assert resultado.diferenca_sem_explicacao == 0
    assert all(conferencia.diferenca == 0 for conferencia in resultado.conferencias_folha)
    assert resultado.total_controle_novo == resultado.saldo_final_razao


def test_r1_cada_frase(resultado):
    linhas = _por_matricula(resultado.cobrancas)
    assert {m: (l.situacao, l.diferenca) for m, l in linhas.items()} == {
        "101": (c.COBRADO, D("0")),
        "102": (c.COBRADO_DIFERENTE, D("-810.50")),
        "103": (c.PARCELAMENTO_NOVO, D("0")),
        "104": (c.BAIXADO, D("0")),
        "105": (c.BAIXADO_DIFERENTE, D("50.00")),
        "106": (c.NAO_COBRADO, D("70.00")),
        "107": (c.COBRADO_SEM_0256, D("-40.00")),
    }


def test_r2_afastados(resultado):
    linhas = _por_matricula(resultado.afastados)
    assert {m: (l.situacao, l.pago, l.diferenca_nova) for m, l in linhas.items()} == {
        "201": (c.PAGOU_CERTO, D("300.00"), D("0")),
        "202": (c.PAGOU_A_MENOS, D("150.00"), D("50.00")),
        "203": (c.PAGOU_A_MAIS, D("120.00"), D("-20.00")),
        "204": (c.NAO_PAGOU, D("0"), D("80.00")),
        "205": (c.PAGOU_CERTO, D("60.00"), D("0")),          # "Sousa" no razão × "SOUZA" na folha
        "206": (c.PAGOU_CERTO, D("0"), D("0")),              # a diferença anterior (−30) cobriu o 0241
        "207": (c.PAGOU_CERTO, D("90.00"), D("0")),          # pago pela pessoa da lista "quem paga por quem"
        "208": (c.NAO_PAGOU, D("0"), D("45.00")),
    }


def test_r3_parcelamentos(resultado):
    linhas = _por_matricula(resultado.parcelamentos)
    novo = c.PARCELAMENTO_NOVO
    assert {m: (novo if l.situacao.startswith(novo) else l.situacao, l.saldo_novo) for m, l in linhas.items()} == {
        "301": (c.PARCELA_DESCONTADA, D("200.00")),
        "302": (c.QUITADO_1204, D("0")),
        "303": (c.QUITADO_RAZAO, D("0")),
        "304": (c.PARCELA_NAO_DESCONTADA, D("90.00")),
        "305": (c.PARCELA_DIFERENTE, D("210.00")),
        "103": (c.PARCELAMENTO_NOVO, D("280.05")),
        "306": (c.PARCELA_SEM_CONTROLE, D("-25.00")),
    }


def test_r5_lancamentos_a_conferir(resultado):
    motivos = {a.lancamento.historico: a.motivo for a in resultado.a_conferir}
    assert set(motivos) == {"Ajuste qualquer sem nome",
                            "Recebimento de valores na tesouraria Quiteria Desconhecida Ramos plano de saude"}
    sugestao = motivos["Recebimento de valores na tesouraria Quiteria Desconhecida Ramos plano de saude"]
    assert "PEDRO ALVES RAMOS (matrícula 208)" in sugestao and c.TIPO_VINCULO in sugestao


def test_r4_0775(resultado):
    """Regra do usuário (16/11/2026): o 0775 zera a pendência de cobrado a mais do mesmo valor; senão, conferir."""
    assert [(l.matricula, l.valor, l.situacao, l.pendencia) for l in resultado.devolucoes] == [
        ("102", D("810.50"), c.DEVOLUCAO_ZEROU, D("-810.50")),
        ("501", D("15.00"), c.DEVOLUCAO_CONFERIR, D("0"))]
    devolucao = [x for x in resultado.conferencias_folha if "0775" in x.descricao]
    assert len(devolucao) == 1 and devolucao[0].razao == devolucao[0].folha == D("825.50")


def test_controle_novo(resultado):
    novo = resultado.controle_novo
    assert {(i.matricula, i.valor) for i in novo if i.tipo == TIPO_0256} == {("101", D("110.00")),
                                                                            ("201", D("300.00"))}
    assert {(i.matricula, i.valor) for i in novo if i.tipo == TIPO_PARCELAMENTO} == {
        ("301", D("200.00")), ("304", D("90.00")), ("305", D("210.00")), ("103", D("280.05"))}
    assert {(i.matricula, i.valor) for i in novo if i.tipo == TIPO_DIFERENCA_0241} == {
        ("202", D("50.00")), ("203", D("-20.00")), ("204", D("80.00")), ("208", D("45.00"))}
    assert {(i.matricula, i.valor) for i in novo if i.tipo == TIPO_PENDENCIA} == {
        ("105", D("50.00")), ("106", D("70.00")), ("107", D("-40.00")), ("306", D("-25.00")), ("401", D("12.34")),
        ("501", D("15.00"))}                       # a do 102 (−810,50) o 0775 zerou
    assert sorted(i.valor for i in novo if i.tipo == TIPO_ACERTO) == [D("-45.00"), D("10.00")]
    assert [(i.matricula, i.pagador) for i in novo if i.tipo == TIPO_VINCULO] == [("207", "Otavia Pagadora Exemplo")]
    assert resultado.composicao[TIPO_ACERTO] == D("-35.00")
    assert TIPO_VINCULO not in resultado.composicao


def test_avisos_folha_e_controle():
    eventos = _eventos()
    controle = _controle()
    resultado = c.conciliar(eventos, _razao(eventos, controle.total + D("1.00"), ajuste_folha=D("5.00")), controle)
    avisos = " | ".join(a.mensagem for a in resultado.avisos)
    assert "0256 + 0241" in avisos and "controle do mês anterior soma" in avisos
    assert resultado.diferenca_sem_explicacao == D("6.00")      # a diferença aparece na prova, nada some


def test_devolucao_no_razao_sem_o_pdf_do_0775_e_0775_sem_lancamento():
    sem_0775 = {k: v for k, v in EVENTOS_MAIO.items() if k != "0775"}
    controle = _controle()
    razao = _razao(_eventos(), controle.total)                     # o razão tem a devolução de 825,50
    resultado = c.conciliar(_eventos(sem_0775), razao, controle)
    avisos = " | ".join(a.mensagem for a in resultado.avisos)
    assert "nenhum PDF escolhido tem o evento 0775" in avisos
    assert resultado.diferenca_sem_explicacao == D("825.50")       # devolução no razão sem o 0775 que a explica
    # o 0775 de junho de verdade: na folha complementar, mas ainda não lançado no razão do mês
    resultado = c.conciliar(_eventos(), _razao(_eventos(), controle.total, com_devolucao=False), controle)
    assert any("ATENÇÃO" in a.mensagem and "0775" in a.mensagem and "mês em que ela for lançada" in a.mensagem
               for a in resultado.avisos)
    assert resultado.diferenca_sem_explicacao == D("-825.50")


def test_controle_inicial():
    eventos = _eventos()
    extras = [ItemControle("301", "RITA PARCELA", TIPO_PARCELAMENTO, MAIO, D("300.00"), D("100.00"))]
    itens = c.montar_controle_inicial(eventos, extras)
    assert [(i.matricula, i.nome, i.tipo, i.valor) for i in itens] == [
        ("101", "ANA COBRADA", TIPO_0256, D("110.00")), ("201", "HELENA AFASTADA EXEMPLO", TIPO_0256, D("300.00")),
        ("301", "RITA PARCELA", TIPO_PARCELAMENTO, D("300.00"))]
