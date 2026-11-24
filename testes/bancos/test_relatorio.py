"""Testes do relatório Excel e do modo principal da linha de comando."""

from datetime import date
from decimal import Decimal

import openpyxl
import pytest

from modulos.bancos import ferramentas as conciliar
from modulos.bancos.relatorio_excel import (
    CABECALHO_ARQUIVOS,
    CABECALHO_CONCILIACAO,
    CABECALHO_DETALHE,
    FORMATO_VALOR,
    nome_padrao,
)
from testes.bancos.conftest import ARQUIVO_BALANCETE, PASTA_EXTRATOS


@pytest.fixture(scope="module")
def planilha(tmp_path_factory):
    """Roda a conciliação completa dos exemplos e reabre a planilha gerada."""
    if not ARQUIVO_BALANCETE.is_file() or not PASTA_EXTRATOS.is_dir():
        pytest.skip("exemplos não encontrados")
    saida = tmp_path_factory.mktemp("saida")
    execucao = conciliar.executar(ARQUIVO_BALANCETE, PASTA_EXTRATOS, saida)
    assert execucao.caminho == saida / "conciliacao_bancaria_2026-08.xlsx"
    assert execucao.competencia == date(2026, 8, 1)
    assert len(execucao.arquivos) == 12
    return openpyxl.load_workbook(execucao.caminho)


def _linhas(aba):
    cabecalho = [c.value for c in aba[1]]
    return [dict(zip(cabecalho, (c.value for c in linha))) for linha in aba.iter_rows(min_row=2)]


def test_nome_padrao():
    assert nome_padrao(date(2026, 8, 1)) == "conciliacao_bancaria_2026-08.xlsx"


def test_abas(planilha):
    assert planilha.sheetnames == ["Resumo", "Conciliação", "Arquivos", "Detalhe"]


@pytest.mark.parametrize("aba, cabecalho", [
    ("Conciliação", CABECALHO_CONCILIACAO),
    ("Arquivos", CABECALHO_ARQUIVOS),
    ("Detalhe", CABECALHO_DETALHE),
])
def test_cabecalhos_negrito_congelados_e_com_filtro(planilha, aba, cabecalho):
    folha = planilha[aba]
    assert [c.value for c in folha[1]] == cabecalho
    assert all(c.font.bold for c in folha[1])
    assert folha.freeze_panes == "A2"
    assert folha.auto_filter.ref == folha.dimensions


def _calcular(planilha, formula):
    """Calcula as fórmulas do Resumo (COUNTIF/COUNTA/SUM) como o Excel faria."""
    import re
    def faixa(texto):
        aba, col, ini, fim = re.fullmatch(r"'(.+)'!\$([A-Z]+)\$(\d+):\$[A-Z]+\$(\d+)", texto).groups()
        return [planilha[aba][f"{col}{n}"].value for n in range(int(ini), int(fim) + 1)]
    resumo = planilha["Resumo"]
    if m := re.fullmatch(r"=COUNTIF\((.+),A(\d+)\)", formula):
        alvo = str(resumo[f"A{m.group(2)}"].value).casefold()
        return sum(1 for v in faixa(m.group(1)) if v is not None and str(v).casefold() == alvo)
    if m := re.fullmatch(r"=COUNTA\((.+?)\)(?:-SUM\(B(\d+):B(\d+)\))?", formula):
        total = sum(1 for v in faixa(m.group(1)) if v not in (None, ""))
        if m.group(2):
            total -= sum(_calcular(planilha, resumo[f"B{n}"].value) for n in range(int(m.group(2)), int(m.group(3)) + 1))
        return total
    raise AssertionError(formula)


def _resumo(planilha):
    valores = {}
    for linha in planilha["Resumo"].iter_rows(values_only=True):
        if linha[0] and linha[0] not in valores:
            valores[linha[0]] = linha[1]
    return valores


def test_resumo(planilha):
    valores = _resumo(planilha)
    assert valores["Competência"] == "08/2026"
    assert "Gerado em" in valores
    conta = {k: _calcular(planilha, v) for k, v in valores.items() if isinstance(v, str) and v.startswith("=")}
    assert (conta["OK"], conta["DIFERENÇA"], conta["NÃO ESTÁ NO BALANCETE"]) == (5, 3, 3)
    assert conta["SEM EXTRATO"] == 101
    assert conta["LIDO"] == 11
    assert conta["ESCANEADO – CONFERIR MANUALMENTE"] == 1
    assert conta["Outros (status digitado fora da lista)"] == 0


def test_resumo_sao_formulas_que_acompanham_a_troca_de_status(planilha, tmp_path):
    # Pedido do usuário (06/11/2026): trocou o status na aba Conciliação, o Resumo se ajusta sozinho
    valores = _resumo(planilha)
    assert valores["OK"].startswith("=COUNTIF('Conciliação'!$L$2:$L$")
    assert valores["LIDO"].startswith("=COUNTIF('Arquivos'!$D$2:$D$")
    folha = planilha["Conciliação"]
    diferenca = next(l for l in folha.iter_rows(min_row=2) if l[11].value == "DIFERENÇA")
    diferenca[11].value = "OK"
    assert (_calcular(planilha, valores["OK"]), _calcular(planilha, valores["DIFERENÇA"])) == (6, 2)
    diferenca[11].value = "resolvido"                      # digitado fora da lista: vai para "Outros"
    assert _calcular(planilha, valores["Outros (status digitado fora da lista)"]) == 1
    diferenca[11].value = "DIFERENÇA"


def test_status_com_lista_suspensa_e_cor_que_acompanha(planilha):
    folha = planilha["Conciliação"]
    (lista,) = folha.data_validations.dataValidation
    assert lista.formula1 == '"OK,DIFERENÇA,SEM EXTRATO,NÃO ESTÁ NO BALANCETE"'
    assert lista.errorStyle == "warning" and str(lista.sqref) == f"L2:L{folha.max_row}"
    regras = [r.formula[0] for faixa in folha.conditional_formatting for r in faixa.rules]
    assert '$L2="OK"' in regras and '$L2="DIFERENÇA"' in regras


def test_conciliacao_status_e_valores(planilha):
    linhas = _linhas(planilha["Conciliação"])
    assert len(linhas) == 109 + 3          # contas do balancete + NÃO ESTÁ NO BALANCETE

    por_codigo = {l["Código"]: l for l in linhas if l["Código"]}
    sicoob = por_codigo[11796]
    assert sicoob["Status"] == "OK"
    assert sicoob["Saldo Total (extrato)"] == pytest.approx(4186.14)
    assert sicoob["Saldo Bloqueado (extrato)"] == pytest.approx(50.00)
    assert sicoob["Saldo Disponível (extrato)"] == pytest.approx(4136.14)
    assert sicoob["Arquivos"] == "2004834 3ok.pdf"

    cdb = por_codigo[19408]                  # BB Aplicação 400585-6
    assert cdb["Status"] == "DIFERENÇA"
    assert cdb["Diferença"] == pytest.approx(-48.18)

    assert por_codigo[10007]["Status"] == "SEM EXTRATO"
    assert por_codigo[10007]["Saldo Total (extrato)"] is None

    fora = [l for l in linhas if not l["Código"]]
    assert [l["Status"] for l in fora] == ["NÃO ESTÁ NO BALANCETE"] * 3
    assert all(l["Observação"] == "saldo zero" for l in fora)


def test_formato_e_cores(planilha):
    folha = planilha["Conciliação"]
    cores = {"OK": "C6EFCE", "DIFERENÇA": "FFC7CE", "SEM EXTRATO": "FFEB9C",
             "NÃO ESTÁ NO BALANCETE": "FFEB9C"}
    for linha in folha.iter_rows(min_row=2):
        status = linha[11].value
        assert linha[0].fill.fgColor.rgb.endswith(cores[status])
        for celula in linha[6:11]:
            assert celula.number_format == FORMATO_VALOR
    arquivos = planilha["Arquivos"]
    escaneado = [l for l in arquivos.iter_rows(min_row=2) if l[3].value.startswith("ESCANEADO")]
    assert escaneado[0][0].fill.fgColor.rgb.endswith("D9D9D9")


def test_aba_arquivos(planilha):
    linhas = _linhas(planilha["Arquivos"])
    assert len(linhas) == 12
    santander = next(l for l in linhas if l["Arquivo"] == "13003634 5 Conta Corrente.pdf")
    assert santander["Subpasta"] == "Santander"
    assert santander["Modelo"] == "Santander - Conta corrente"
    assert santander["Contas extraídas"] == "CC 130036345"


def test_aba_detalhe(planilha):
    linhas = _linhas(planilha["Detalhe"])
    assert len(linhas) == 11               # um saldo por PDF lido
    cef = next(l for l in linhas if l["Modelo"] == "CEF - Conta corrente")
    assert (cef["Conta original"], cef["Conta normalizada"]) == ("000568630703-9", "5686307039")
    assert cef["Total"] == pytest.approx(93.56)
    assert all(l["Fonte secundária"] == "Não" for l in linhas)


# ---------------------------------------------------------------------------
# Linha de comando
# ---------------------------------------------------------------------------

def test_linha_de_comando_gera_planilha(tmp_path, capsys):
    if not ARQUIVO_BALANCETE.is_file():
        pytest.skip("exemplos não encontrados")
    destino = tmp_path / "minha_conciliacao.xlsx"
    codigo = conciliar.main(["--balancete", str(ARQUIVO_BALANCETE),
                             "--extratos", str(PASTA_EXTRATOS), "--saida", str(destino)])
    assert codigo == 0
    assert destino.is_file()
    saida = capsys.readouterr().out
    assert "Contas por status:" in saida
    assert "Planilha gerada" in saida


def test_linha_de_comando_balancete_inexistente(tmp_path, capsys):
    codigo = conciliar.main(["--balancete", str(tmp_path / "nao_existe.xlsx"),
                             "--extratos", str(tmp_path)])
    assert codigo == 1
    assert "balancete não encontrado" in capsys.readouterr().err


def test_linha_de_comando_sem_argumentos():
    with pytest.raises(SystemExit):
        conciliar.main([])


def test_valores_gravados_como_numero(planilha):
    # Decimal vira número no Excel (não texto), para somar e filtrar
    celula = planilha["Detalhe"]["I2"]
    assert isinstance(celula.value, (int, float, Decimal))
