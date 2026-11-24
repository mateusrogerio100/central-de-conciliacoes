"""Quem é o colaborador do histórico (nomes.py) e o controle de um mês para o outro (controle.py).

Nomes fictícios.
"""

from datetime import date
from decimal import Decimal as D

from openpyxl import Workbook

from modulos.credito_estouro.controle import ABA_CONTROLE, gravar_controle, ler_controle
from modulos.credito_estouro.modelos import (
    TIPO_0256,
    TIPO_DIFERENCA_0241,
    TIPO_PARCELAMENTO,
    TIPO_PENDENCIA,
    TIPO_VINCULO,
    ItemControle,
)
from modulos.credito_estouro.nomes import Pessoas, cracha_do_historico

PESSOAS = Pessoas({"101": "CARLOS MODELO PEREIRA", "102": "CARLOS MODELO", "103": "BEATRIZ EXEMPLO FALEIROS",
                   "104": "LIVIA DE SOUZA MOTA", "105": "ANA PAULA LIMA", "106": "ANA PAULA MODELO",
                   "0107": "JOSE DA COSTA"},
                  {"Marta Alves Duarte": "101"})


def test_cracha_vale_mais_que_o_nome():
    assert cracha_do_historico("Rescisão negativa da colaboradora Fulana crachá 012345 não lançado") == "12345"
    assert PESSOAS.do_historico("Referente Rescisão negativa do colaborador Jose da Costa crachá 999") == ("999",
                                                                                                         "crachá")


def test_nome_completo_e_o_mais_comprido_ganha():
    assert PESSOAS.do_historico("Recebimento de valores na tesouraria Carlos Modelo Pereira")[0] == "101"
    assert PESSOAS.do_historico("Recebimento de valores Carlos Modelo plano")[0] == "102"
    assert PESSOAS.do_historico("Desconto Plano de Saúde em folha Título 1 José da Costa")[0] == "107"


def test_uma_letra_de_diferenca_e_aceita_duas_nao():
    assert PESSOAS.do_historico("Desconto Plano de Saúde Título 9 Beatriz Exemplo Falleiros")[0] == "103"
    assert PESSOAS.do_historico("Desconto Plano de Saúde Título 9 Livia de Sousa Mota")[0] == "104"
    assert PESSOAS.do_historico("Desconto Plano de Saúde Título 9 Livia de Sauza Mutu")[0] is None


def test_ambiguo_e_ninguem():
    assert PESSOAS.do_historico("Desconto Ana Paula Lima Modelo") == (None, "ambíguo")
    assert PESSOAS.do_historico("Desconto de alguém que não está na folha") == (None, "")
    assert PESSOAS.do_historico("Desconto Plano de Saúde Título 1 Ana")[0] is None     # nome cortado no PDF


def test_pagador_da_lista_quem_paga_por_quem():
    assert PESSOAS.do_historico("Recebimento de valores na tesouraria Marta Alves Duarte Pereira "
                                "recebimento de plano de saude de Marta alves") == ("101", "nome")


ITENS = [
    ItemControle("101", "PESSOA UM", TIPO_0256, date(2026, 5, 1), D("100.50")),
    ItemControle("102", "PESSOA DOIS", TIPO_PARCELAMENTO, date(2026, 3, 1), D("373.21"), D("373.14"), "8 parcelas"),
    ItemControle("103", "PESSOA TRES", TIPO_DIFERENCA_0241, date(2026, 5, 1), D("-0.60")),
    ItemControle("104", "PESSOA QUATRO", TIPO_VINCULO, None, D("0"), pagador="Fulana Pagadora"),
]


def test_controle_gravado_e_lido_de_volta(tmp_path):
    caminho = gravar_controle(tmp_path / "controle.xlsx", date(2026, 5, 1), "Fundação Teste", D("473.11"), ITENS)
    leitura = ler_controle(caminho)
    assert leitura.erro is None and leitura.avisos == []
    assert (leitura.competencia, leitura.unidade, leitura.saldo_razao) == (date(2026, 5, 1), "Fundação Teste",
                                                                          D("473.11"))
    assert leitura.itens == ITENS
    assert leitura.total == D("473.11")


def _aba(tmp_path, linhas, nome=ABA_CONTROLE):
    livro = Workbook()
    livro.active.title = nome
    for linha in linhas:
        livro.active.append(linha)
    caminho = tmp_path / "controle.xlsx"
    livro.save(caminho)
    return caminho


CABECALHO = ["Matrícula", "Colaborador", "Tipo", "Mês de origem", "Valor", "Parcela", "Observação",
             "Pagador (nome no razão)"]


def test_linha_acrescentada_a_mao_tipo_desconhecido_e_valor_ruim(tmp_path):
    caminho = _aba(tmp_path, [["Crédito Estouro — controle de 05/2026"], [], [], [], CABECALHO,
                              [12, "MANUAL", "Parcelamento", "05/2026", 300, 100, "combinado com o DP"],
                              ["13", "OUTRO", "Coisa nova", "05/2026", 5],
                              ["14", "RUIM", "Pendência a conferir", "05/2026", "abc"],
                              ["15", "SEM PAGADOR", "Pagamento por outra pessoa", None, 0],
                              [None, "Total", None, None, 305]])
    leitura = ler_controle(caminho)
    assert [(i.matricula, i.tipo, i.valor, i.parcela) for i in leitura.itens] == [
        ("12", TIPO_PARCELAMENTO, D("300.00"), D("100.00")), ("13", TIPO_PENDENCIA, D("5.00"), None)]
    avisos = " | ".join(a.mensagem for a in leitura.avisos)
    assert "desconhecido" in avisos and "NÃO foi lida" in avisos and "nome do pagador" in avisos


def test_controle_sem_aba_sem_cabecalho_ou_sem_mes(tmp_path):
    assert "não tem a aba" in ler_controle(_aba(tmp_path, [["x"]], nome="Plan1")).erro
    assert "cabeçalho" in ler_controle(_aba(tmp_path, [["Crédito Estouro — controle de 05/2026"]])).erro
    assert "de que mês" in ler_controle(_aba(tmp_path, [CABECALHO])).erro
    nao_excel = tmp_path / "x.xlsx"
    nao_excel.write_bytes(b"isto nao e excel")
    assert "Não foi possível abrir" in ler_controle(nao_excel).erro
