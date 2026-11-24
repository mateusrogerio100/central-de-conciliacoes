"""Testes do leitor do balancete."""

from datetime import date, datetime
from decimal import Decimal

import openpyxl
import pytest

from modulos.bancos.balancete import interpretar_descricao, ler_balancete
from testes.bancos.conftest import ARQUIVO_BALANCETE


@pytest.fixture(scope="module")
def balancete():
    if not ARQUIVO_BALANCETE.is_file():
        pytest.skip("balancete de exemplo não encontrado")
    return ler_balancete(ARQUIVO_BALANCETE)


@pytest.fixture(scope="module")
def por_codigo(balancete):
    return {conta.codigo: conta for conta in balancete.contas}


# ---------------------------------------------------------------------------
# Balancete de exemplo (agosto/2026)
# ---------------------------------------------------------------------------

def test_competencia(balancete):
    assert balancete.competencia == date(2026, 8, 1)
    assert balancete.data_referencia == date(2026, 8, 31)


def test_nenhuma_conta_de_caixa(balancete):
    assert not [c for c in balancete.contas if c.classificacao.startswith("1.01.01.01")]


def test_so_contas_analiticas_bancarias(balancete):
    for conta in balancete.contas:
        assert conta.classificacao.startswith(("1.01.01.02.", "1.01.01.03.", "1.01.01.04."))
        assert len(conta.classificacao.split(".")) == 6


def test_soma_bate_com_totais_dos_grupos(balancete):
    # Totais das linhas sintéticas do próprio balancete:
    # 1.01.01.02 = 140.615,34; 1.01.01.03 = 39.630.168,02; 1.01.01.04 = 3.318.170,86
    total = sum(c.saldo_atual for c in balancete.contas)
    assert total == Decimal("140615.34") + Decimal("39630168.02") + Decimal("3318170.86")


def test_todas_as_descricoes_reconhecidas(balancete):
    assert [c.descricao for c in balancete.contas if not c.banco] == []


@pytest.mark.parametrize("codigo, banco, tipo, conta, saldo", [
    ("10007", "BB", "CC", "80365", "640.44"),
    ("190898", "CEF", "CC", "5686307039", "93.56"),
    ("11796", "SICOOB", "CC", "20048343", "4186.14"),
    ("190502", "BB", "APLICACAO", "11444", "8893.49"),
    ("190498", "BB", "CC", "11444", "300.25"),
    ("14421", "SANTANDER", "APLICACAO", "36369", "138.49"),
    ("190557", "BB", "POUPANCA", "11797", "223374.00"),
    ("190614", "BB", "APLICACAO", "400759X", "2728903.05"),
    ("11610", "BB", "CC", "57495", "200.00"),
])
def test_contas_conferidas(por_codigo, codigo, banco, tipo, conta, saldo):
    c = por_codigo[codigo]
    assert (c.banco, c.tipo, c.conta) == (banco, tipo, conta)
    assert isinstance(c.saldo_atual, Decimal)
    assert c.saldo_atual == Decimal(saldo)


def test_classificacao_repetida_vira_duas_contas(por_codigo):
    assert por_codigo["190502"].classificacao == por_codigo["190335"].classificacao
    assert por_codigo["190502"].conta != por_codigo["190335"].conta


def test_codigos_unicos(balancete):
    codigos = [c.codigo for c in balancete.contas]
    assert len(codigos) == len(set(codigos))


def test_descricao_sem_espacos_nas_pontas(balancete):
    for conta in balancete.contas:
        assert conta.descricao == conta.descricao.strip()


# ---------------------------------------------------------------------------
# Interpretação da descrição (todos os exemplos da especificação)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("descricao, esperado", [
    ("BB C/C 8036-5", ("BB", "CC", "80365")),
    ("Sicoob C/C 2024675-7", ("SICOOB", "CC", "20246757")),
    ("CEF C/C 568630703-9 - Empréstimo", ("CEF", "CC", "5686307039")),
    ("Santander Aplicação 3634-5", ("SANTANDER", "APLICACAO", "36345")),
    ("Santander Aplicação 13000305-3", ("SANTANDER", "APLICACAO", "130003053")),
    ("BB Aplicação 400759-x - Resolução 03 Cirurgias Eletivas", ("BB", "APLICACAO", "400759X")),
    ("BB Poupança 1179-7 - Termo de Convênio 989501/2025 - Samia", ("BB", "POUPANCA", "11797")),
    ("BB S/A 5749-5", ("BB", "CC", "57495")),            # S/A = conta corrente
    ("BB Investimento 1234-5", ("BB", "OUTRO", "12345")),   # tipo desconhecido
    ("   BB C/C 8036-5   ", ("BB", "CC", "80365")),
    # número seguido de texto sem o " - " (caso real do balancete)
    ("Santander Aplicação 13005133-1 RATEIOS", ("SANTANDER", "APLICACAO", "130051331")),
    ("BB Poupança 400727-1 Plano de Trabalho 10 Leitos UTI Estado", ("BB", "POUPANCA", "4007271")),
])
def test_interpretar_descricao(descricao, esperado):
    assert interpretar_descricao(descricao) == esperado


@pytest.mark.parametrize("descricao", [
    "BANCOS CONTA MOVIMENTO",
    "Itaú C/C 1234-5",           # banco não cadastrado
    "BB C/C sem número",
    "",
])
def test_descricao_nao_reconhecida(descricao):
    assert interpretar_descricao(descricao) == ("", "", "")


# ---------------------------------------------------------------------------
# Planilha sintética: "Mês Referência" como número serial e colunas deslocadas
# ---------------------------------------------------------------------------

def _criar_planilha(caminho, mes_referencia):
    pasta = openpyxl.Workbook()
    aba = pasta.active
    aba.append(["Fundação Hospital Exemplo"])
    aba.append(["Balancete"])
    aba.append([None, None, None, None, None, None, "Mês Referência:", None, None, mes_referencia])
    # Cabeçalho numa ordem/posição diferente da do relatório real
    aba.append(["Saldo Atual", None, "Descrição", None, "Código", "Classificação"])
    aba.append([1234.5, None, "  BB C/C 8036-5", None, 10007, "1.01.01.02.01.0003"])
    aba.append([10.0, None, "Caixa Cofre", None, 11816, "1.01.01.01.0013"])
    aba.append([99.0, None, "DEPOSITOS BANCARIOS", None, 1112, "1.01.01.02"])
    aba.append([5.0, None, "Conta Estranha", None, 555, "1.01.01.03.01.0099"])
    aba.append(["Impresso em: 22/09/2026", None, None, None, None, "Página: 1"])
    pasta.save(caminho)


def test_mes_referencia_como_numero_serial(tmp_path):
    caminho = tmp_path / "balancete.xlsx"
    _criar_planilha(caminho, 46235)   # 46235 = 01/08/2026
    resultado = ler_balancete(caminho)
    assert resultado.competencia == date(2026, 8, 1)


def test_colunas_localizadas_pelo_cabecalho(tmp_path):
    caminho = tmp_path / "balancete.xlsx"
    _criar_planilha(caminho, datetime(2026, 2, 1))
    resultado = ler_balancete(caminho)
    assert resultado.data_referencia == date(2026, 2, 28)
    assert [(c.codigo, c.banco, c.conta, c.saldo_atual) for c in resultado.contas] == [
        ("10007", "BB", "80365", Decimal("1234.50")),
        ("555", "", "", Decimal("5.00")),   # descrição não reconhecida, mas presente
    ]


# ---------------------------------------------------------------------------
# Balancete como sai do Tasy: ".xls" que é texto com tabulação (cp1252)
# ---------------------------------------------------------------------------

TEXTO_TASY = "\n".join("\t".join(linha) for linha in [
    ["Fundação Hospital Exemplo"],
    ["Balancete"],
    ["", "", "", "", "", "", "Mês Referência:", "", "", "set/2026"],
    ["", "Código", "", "Classificação", "", "Descrição", "", "", "Saldo Anterior", "", "Débitos", "",
     "Créditos", "Saldo Atual", ""],
    ["", "", "1112", "", "1.01.01.02", "   DEPOSITOS BANCARIOS", "", "", "1,00", "", "0,00", "", "0,00",
     "1.234.567,89", ""],
    ["", "", "10007", "", "1.01.01.02.01.0003", "      BB C/C 8036-5", "", "", "640,44", "", "0,00", "",
     "0,00", "1.234.567,89", ""],
    ["", "", "17677", "", "1.01.01.02.01.0029", "      Sicoob C/C 347-6", "", "", "0,00", "", "0,00", "",
     "0,00", "-6.569,00", ""],
    ["", "", "11816", "", "1.01.01.01.0013", "      Caixa Cofre", "", "", "0,00", "", "0,00", "", "0,00",
     "167,15", ""],
])


def test_balancete_em_texto_do_tasy(tmp_path):
    caminho = tmp_path / "balancete_09_caixas.xls"
    caminho.write_bytes(TEXTO_TASY.encode("cp1252"))
    resultado = ler_balancete(caminho)
    assert resultado.competencia == date(2026, 9, 1)
    assert [(c.codigo, c.descricao, c.banco, c.conta, c.saldo_atual) for c in resultado.contas] == [
        ("10007", "BB C/C 8036-5", "BB", "80365", Decimal("1234567.89")),
        ("17677", "Sicoob C/C 347-6", "SICOOB", "3476", Decimal("-6569.00")),
    ]


def test_xlsx_com_extensao_xls(tmp_path):
    """O usuário abriu o .xls do Tasy no Excel e salvou como .xlsx sem trocar o nome."""
    caminho = tmp_path / "balancete.xls"
    _criar_planilha(caminho, datetime(2026, 9, 1))
    assert ler_balancete(caminho).competencia == date(2026, 9, 1)


def test_excel_antigo_pede_para_salvar_como_xlsx(tmp_path):
    caminho = tmp_path / "balancete.xls"
    caminho.write_bytes(b"\xd0\xcf\x11\xe0" + b"\x00" * 100)
    with pytest.raises(ValueError, match="salve como .xlsx"):
        ler_balancete(caminho)


def test_balancete_de_setembro_do_tasy():
    from testes.conftest import PASTA_EXEMPLOS

    caminho = PASTA_EXEMPLOS / "bancos" / "2026-09" / "balancete_09_caixas.xls"
    if not caminho.is_file():
        pytest.skip("balancete de setembro (texto do Tasy) não encontrado")
    resultado = ler_balancete(caminho)
    assert resultado.competencia == date(2026, 9, 1)
    assert len(resultado.contas) == 109
    assert all(c.banco for c in resultado.contas)
    # Totais das linhas sintéticas do próprio balancete de setembro:
    # 1.01.01.02 = 747.073,58; 1.01.01.03 = 45.335.385,98; 1.01.01.04 = 2.888.342,12
    assert sum(c.saldo_atual for c in resultado.contas) == \
        Decimal("747073.58") + Decimal("45335385.98") + Decimal("2888342.12")
