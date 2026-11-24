"""V2 — leitura do razão da conta nos três formatos (ESPECIFICACAO_CREDITO_ESTOURO.md, seções 2.2, 3.2 e 8).

Os arquivos sintéticos usam nomes fictícios e imitam o Tasy (o `.xls` é texto separado por tabulação, com as
células deslocadas como no original); os testes com os razões reais são pulados sem a pasta de exemplos.
"""

from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest
from openpyxl import Workbook

from modulos.credito_estouro.leitor_razao import (
    ERRO_EH_EVENTOS,
    ERRO_NAO_EH_RAZAO,
    conferir_periodo,
    ler_razao,
    ler_razao_do_texto,
)
from modulos.credito_estouro.modelos import LeituraRazao

PASTA_EXEMPLOS = Path(__file__).resolve().parents[2] / "exemplos" / "credito_estouro"
UNIDADE = "Fundação Teste de Exemplo"
CONTA = "10652 - 1.01.03.02.0002 Credito Complemento Salario"

# linhas do .xls do Tasy (as posições imitam o real: Data na coluna 1, Histórico na 2, Lote na 6…)
LINHAS_TASY = [
    ["", UNIDADE, "", "", "", "", "", "", "", "", "Livro: 0", "", "Página: 1", "", ""],
    ["Razão"],
    ["", "", "", "Período:", "01/06/2026", "até:", "", "30/06/2026"],
    ["", "Data", "Histórico", "", "", "", "Lote", "", "", "Débitos", "", "Créditos", "", "", "Saldo"],
    ["", CONTA.replace(" Credito", "  Credito")],
    ["", "", "Saldo anterior ", "", "", "", "", "", "", "", "", "", "", "", "1.000,00"],
    ["", "02/06/2026", "Desconto Plano de Saúde em folha  Título 1 Ana Pessoa Ficticia", "", "", "", "70882", "",
     "", "0,00", "", "300,00", "", "", "700,00"],
    ["", "05/06/2026", "Recebimento de valores na tesouraria Bruno Modelo", "", "", "", "70907", "", "",
     "0,00", "", "50,00", "", "", "650,00"],
    ["", "", "Plano de saude do funcionario afastado"],
    ["", "30/06/2026", "Credito complemento salário no mês 0626", "", "", "", "71112", "", "",
     "1.250,00", "", "0,00", "", "", "1.900,00"],
    ["", "30/06/2026", "Desconto crédito complemento salário no mês 0626", "", "", "", "71112", "", "",
     "0,00", "", "400,00", "", "", "1.500,00"],
    ["", "", "Total - " + CONTA, "", "", "", "", "", "", "1.250,00", "", "750,00", "", "", ""],
    ["", "Total (5)", "", "", "", "", "", "", "", "1.250,00", "", "750,00", "", "", ""],
    ["", "Impresso em: 13/11/2026 15:56:15", "", "Página: 1", "", "", "", "", "Usuario", "", "", "WEXE002"],
]


def _xls_tasy(pasta, linhas=LINHAS_TASY, nome="razao.xls"):
    caminho = pasta / nome
    caminho.write_bytes("\r\n".join("\t".join(l) for l in linhas).encode("cp1252"))
    return caminho


def _confere_sintetico(leitura):
    assert leitura.erro is None, leitura.erro
    assert leitura.avisos == []
    assert leitura.unidade == UNIDADE
    assert leitura.conta == CONTA
    assert (leitura.inicio, leitura.fim) == (date(2026, 6, 1), date(2026, 6, 30))
    assert leitura.saldo_anterior == D("1000.00")
    assert (leitura.total_debitos, leitura.total_creditos, leitura.saldo_final) == (
        D("1250.00"), D("750.00"), D("1500.00"))
    assert [(l.data.day, l.lote, l.debito, l.credito) for l in leitura.lancamentos] == [
        (2, "70882", D("0.00"), D("300.00")), (5, "70907", D("0.00"), D("50.00")),
        (30, "71112", D("1250.00"), D("0.00")), (30, "71112", D("0.00"), D("400.00"))]
    assert leitura.lancamentos[1].historico == ("Recebimento de valores na tesouraria Bruno Modelo "
                                                "Plano de saude do funcionario afastado")


def test_xls_de_texto_do_tasy(tmp_path):
    leitura = ler_razao(_xls_tasy(tmp_path))
    assert leitura.formato == "Excel"
    _confere_sintetico(leitura)


def test_xlsx(tmp_path):
    livro = Workbook()
    for linha in LINHAS_TASY:
        livro.active.append([c if c != "" else None for c in linha])
    caminho = tmp_path / "razao.xlsx"
    livro.save(caminho)
    _confere_sintetico(ler_razao(caminho))


def test_campo_entre_aspas_com_quebra_de_linha_fica_numa_celula(tmp_path):
    linhas = [list(l) for l in LINHAS_TASY]
    linhas[6][2] = '"Desconto Plano de Saúde em folha\nTítulo 1 Ana Pessoa Ficticia"'
    leitura = ler_razao(_xls_tasy(tmp_path, linhas))
    assert leitura.avisos == []
    assert leitura.lancamentos[0].historico == "Desconto Plano de Saúde em folha Título 1 Ana Pessoa Ficticia"


def test_saldo_e_total_que_nao_batem_viram_atencao(tmp_path):
    linhas = [list(l) for l in LINHAS_TASY]
    linhas[10][14] = "1.499,00"
    linhas[11][9] = "1.251,00"
    avisos = [a.mensagem for a in ler_razao(_xls_tasy(tmp_path, linhas)).avisos]
    assert len(avisos) == 2 and all(a.startswith("ATENÇÃO") for a in avisos)


def test_sem_saldo_anterior_e_arquivo_que_nao_e_razao(tmp_path):
    sem_saldo = [l for l in LINHAS_TASY if "Saldo anterior " not in l]
    assert "Saldo anterior" in ler_razao(_xls_tasy(tmp_path, sem_saldo)).erro
    outro = tmp_path / "outro.xls"
    outro.write_bytes("Balancete\tqualquer\r\nConta\tSaldo\r\n".encode("cp1252"))
    assert ler_razao(outro).erro == ERRO_NAO_EH_RAZAO


# ---------------------------------------------------------------------
# PDF (texto das páginas)
# ---------------------------------------------------------------------
PAGINAS_PDF = [
    f"{UNIDADE} Livro: 0 Página: 1\nRazão\nPeríodo: 01/06/2026até: 30/06/2026\n"
    "Data Histórico Lote Débitos Créditos Saldo\n"
    f"{CONTA}\n"
    "Saldo anterior 1.000,00\n"
    "02/06/2026 Desconto Plano de Saúde em folha Título 1 Ana 70882 0,00 300,00 700,00\n"
    "Pessoa Ficticia\n"
    "05/06/2026 Recebimento de valores na tesouraria Bruno Modelo 70907 0,00 50,00 650,00\n"
    "Impresso em: 13/11/2026 15:56:15 Página: 1 Usuario WEXE002",
    f"{UNIDADE} Livro: 0 Página: 2\nRazão\nPeríodo: 01/06/2026até: 30/06/2026\n"
    "Data Histórico Lote Débitos Créditos Saldo\n"
    "Plano de saude do funcionario afastado\n"
    "30/06/2026 Credito complemento salário no mês 0626 71112 1.250,00 0,00 1.900,00\n"
    "30/06/2026 Desconto crédito complemento salário no mês 0626 71112 0,00 400,00 1.500,00\n"
    f"Total - {CONTA} 1.250,00 750,00\n"
    "Total (5) 1.250,00 750,00\n"
    "Impresso em: 13/11/2026 15:56:15 Página: 2 Usuario WEXE002",
]


def test_pdf_junta_o_historico_quebrado_ate_na_pagina_seguinte():
    leitura = ler_razao_do_texto(list(PAGINAS_PDF), LeituraRazao(arquivo="razao.pdf"))
    assert leitura.formato == "PDF"
    _confere_sintetico(leitura)
    assert leitura.lancamentos[0].historico == "Desconto Plano de Saúde em folha Título 1 Ana Pessoa Ficticia"


def test_pdf_de_eventos_escolhido_no_lugar_do_razao():
    texto = ("0001 -FUNDAÇÃO TESTE Pág.: 1\nEVENTOS 05/2026\n0256-Cred. Estouro do Mes\n"
             "Total de Colaboradores: 00 0,00 0,00")
    assert ler_razao_do_texto([texto], LeituraRazao(arquivo="x.pdf")).erro == ERRO_EH_EVENTOS


def test_periodo_do_razao_tem_de_ser_o_mes_dos_eventos(tmp_path):
    leitura = ler_razao(_xls_tasy(tmp_path))
    assert conferir_periodo(leitura, date(2026, 6, 1)) is None
    mensagem = conferir_periodo(leitura, date(2026, 5, 1))
    assert "01/06/2026 até 30/06/2026" in mensagem and "05/2026" in mensagem
    linhas = [list(l) for l in LINHAS_TASY]
    linhas[2][7] = "31/10/2026"                        # o primeiro razão de junho ia até outubro
    assert "até 31/10/2026" in conferir_periodo(ler_razao(_xls_tasy(tmp_path, linhas)), date(2026, 6, 1))


# ---------------------------------------------------------------------
# Razões reais (seção 2.2)
# ---------------------------------------------------------------------
pula_sem_exemplos = pytest.mark.skipif(not PASTA_EXEMPLOS.exists(), reason="exemplos reais fora do git")


@pula_sem_exemplos
def test_razao_real_de_maio_em_pdf():
    leitura = ler_razao(PASTA_EXEMPLOS / "2026-05" / "Razão.pdf")
    assert leitura.erro is None and leitura.avisos == []
    assert leitura.conta == "10652 - 1.01.03.02.0002 Credito Complemento Salario"
    assert (leitura.saldo_anterior, leitura.saldo_final) == (D("97075.60"), D("98853.35"))
    assert (leitura.total_debitos, leitura.total_creditos) == (D("113346.69"), D("111568.94"))
    assert len(leitura.lancamentos) == 38
    assert conferir_periodo(leitura, date(2026, 5, 1)) is None


@pula_sem_exemplos
def test_razao_real_de_junho_pdf_igual_ao_xls():
    pdf = ler_razao(PASTA_EXEMPLOS / "2026-06" / "razao_06_credito_suplemento.pdf")
    xls = ler_razao(PASTA_EXEMPLOS / "2026-06" / "razao_06_credito_suplemento.xls")
    for leitura in (pdf, xls):
        assert leitura.erro is None and leitura.avisos == []
        assert (leitura.saldo_anterior, leitura.saldo_final) == (D("98853.35"), D("116027.92"))
        assert (leitura.total_debitos, leitura.total_creditos) == (D("125189.54"), D("108014.97"))
    assert [(l.data, l.lote, l.debito, l.credito, l.saldo) for l in pdf.lancamentos] == [
        (l.data, l.lote, l.debito, l.credito, l.saldo) for l in xls.lancamentos]
    # o PDF do Tasy às vezes corta o fim do nome (o texto não está no arquivo): o .xls traz o histórico inteiro
    for no_pdf, no_xls in zip(pdf.lancamentos, xls.lancamentos):
        assert " ".join(no_xls.historico.split()).startswith(no_pdf.historico.strip())
