"""V6 (Excel) — o Excel de saída e o processar() da tela (ESPECIFICACAO_CREDITO_ESTOURO.md, seções 5 e 8).

A primeira parte usa o mês fictício do test_conciliador; a segunda faz o caminho inteiro com os arquivos reais
(abril → maio → junho, o Excel de um mês entrando como controle do seguinte), pulada sem a pasta de exemplos.
"""

import re
from datetime import date, datetime
from decimal import Decimal as D

import pytest
from openpyxl import load_workbook

from modulos.credito_estouro import conciliador as c
from modulos.credito_estouro import relatorio_excel as r
from modulos.credito_estouro.controle import ABA_CONTROLE, LeituraControle, gravar_controle, ler_controle
from modulos.credito_estouro.modelos import TIPO_ACERTO, TIPO_PENDENCIA, TIPOS_COM_VALOR, Aviso
from modulos.credito_estouro.processamento import (
    conferir_conjunto,
    ler_pasta_lembrada,
    previa_controle,
    previa_eventos,
    previa_razao,
    processar,
    salvar_pasta_lembrada,
)
from testes.credito_estouro.test_conciliador import _controle, _eventos, _razao
from testes.credito_estouro.test_maio_real import PASTA, controle_inicial

AGORA = datetime(2026, 11, 16, 9, 30)


# ---------------------------------------------------------------------
# Calcula as fórmulas do Resumo como o Excel (o openpyxl não calcula)
# ---------------------------------------------------------------------
def _faixa(livro, texto):
    aba, coluna, inicio, fim = re.fullmatch(r"'(.+)'!\$([A-Z]+)\$(\d+):\$[A-Z]+\$(\d+)", texto).groups()
    return [livro[aba][f"{coluna}{n}"].value for n in range(int(inicio), int(fim) + 1)]


def _calcular(livro, formula):
    resumo = livro[r.ABA_RESUMO]

    def b(n):
        valor = resumo[f"B{n}"].value
        return _calcular(livro, valor) if isinstance(valor, str) and valor.startswith("=") else valor or 0

    if m := re.fullmatch(r"=COUNTIF\((.+),A(\d+)\)", formula):
        alvo = str(resumo[f"A{m.group(2)}"].value).casefold()
        return sum(1 for v in _faixa(livro, m.group(1)) if v is not None and str(v).casefold() == alvo)
    if m := re.fullmatch(r"=COUNTA\((.+?)\)(?:-SUM\(B(\d+):B(\d+)\))?", formula):
        total = sum(1 for v in _faixa(livro, m.group(1)) if v not in (None, ""))
        if m.group(2):
            total -= sum(b(n) for n in range(int(m.group(2)), int(m.group(3)) + 1))
        return total
    if m := re.fullmatch(r"=SUMIF\((.+),A(\d+),(.+)\)", formula):
        alvo = str(resumo[f"A{m.group(2)}"].value).casefold()
        tipos, valores = _faixa(livro, m.group(1)), _faixa(livro, m.group(3))
        return round(sum(v or 0 for t, v in zip(tipos, valores) if t is not None and str(t).casefold() == alvo), 2)
    if m := re.fullmatch(r"=SUM\(B(\d+):B(\d+)\)", formula):
        return round(sum(b(n) for n in range(int(m.group(1)), int(m.group(2)) + 1)), 2)
    if m := re.fullmatch(r"=ROUND\(B(\d+)-B(\d+),2\)", formula):
        return round(b(m.group(1)) - b(m.group(2)), 2)
    raise AssertionError(formula)


def _resumo(livro):
    """{rótulo: valor calculado}; o mesmo rótulo em dois blocos vira "bloco › rótulo"."""
    valores, bloco = {}, ""
    for linha in livro[r.ABA_RESUMO].iter_rows(values_only=True):
        rotulo, valor = linha[0], linha[1] if len(linha) > 1 else None
        if rotulo and valor in ("Quantidade", "Valor", "Razão"):
            bloco = rotulo
            continue
        if not rotulo:
            continue
        if isinstance(valor, str) and valor.startswith("="):
            valor = _calcular(livro, valor)
        valores[rotulo if rotulo not in valores else f"{bloco} › {rotulo}"] = valor
        valores[f"{bloco} › {rotulo}"] = valor
    return valores


# ---------------------------------------------------------------------
# Mês fictício
# ---------------------------------------------------------------------
@pytest.fixture(scope="module")
def conciliacao():
    eventos = _eventos()
    controle = _controle()
    return c.conciliar(eventos, _razao(eventos, controle.total), controle)


@pytest.fixture
def planilha(tmp_path, conciliacao):
    caminho = r.gravar_relatorio(tmp_path / "saida.xlsx", conciliacao, [Aviso("razao.xls", "ATENÇÃO: teste")],
                                 {"Eventos da folha": "eventos.pdf"}, AGORA)
    return caminho


def test_abas_e_nome_do_arquivo(planilha, tmp_path):
    livro = load_workbook(planilha)
    assert livro.sheetnames == [r.ABA_RESUMO, r.ABA_COBRANCAS, r.ABA_AFASTADOS, r.ABA_PARCELAMENTOS,
                                r.ABA_DEVOLUCOES, r.ABA_A_CONFERIR, ABA_CONTROLE, r.ABA_AVISOS, r.ABA_LISTAS]
    assert livro[r.ABA_LISTAS].sheet_state == "hidden"
    assert r.unidade_para_arquivo("FUNDAÇÃO HOSPITAL EXEMPLO DE MISER. DE CIDADE ALFA") == "HospitalExemplo"
    assert r.unidade_para_arquivo("AME - Cidade Delta (Fund. Hospital Exemplo)") == "CidadeDelta"
    primeiro = r.caminho_do_relatorio(tmp_path, "FUNDAÇÃO HOSPITAL EXEMPLO", date(2026, 6, 1))
    assert primeiro.name == "CreditoEstouro_jun2026.xlsx"
    primeiro.write_bytes(b"")
    assert r.caminho_do_relatorio(tmp_path, "FUNDAÇÃO HOSPITAL EXEMPLO", date(2026, 6, 1)).name.endswith("jun2026_2.xlsx")


def test_resumo_composicao_e_contagens(planilha, conciliacao):
    livro = load_workbook(planilha)
    valores = _resumo(livro)
    for tipo in TIPOS_COM_VALOR:
        assert valores[f"Composição do saldo (aba Controle) › {tipo}"] == pytest.approx(
            float(conciliacao.composicao[tipo]))
    assert valores["Total do controle"] == pytest.approx(float(conciliacao.saldo_final_razao))
    assert valores["Diferença sem explicação (saldo final do razão − total do controle; deve ser zero)"] == 0
    assert valores[f"0256 do mês anterior › {c.COBRADO}"] == 1
    assert valores[f"0256 do mês anterior › {c.NAO_COBRADO}"] == 1
    assert valores["0256 do mês anterior › Total"] == len(conciliacao.cobrancas)
    assert valores[f"0241 – afastados › {c.PAGOU_CERTO}"] == 4
    assert valores["Parcelamentos › Total"] == len(conciliacao.parcelamentos)
    assert all(valores[f"{bloco} › Outros (situação digitada fora da lista)"] == 0
               for bloco in ("0256 do mês anterior", "0241 – afastados", "Parcelamentos"))
    assert valores["Lançamentos que nenhuma regra explicou (entram como acerto manual)"] == 2
    assert valores[f"0775 – devoluções › {c.DEVOLUCAO_ZEROU}"] == 1
    assert valores[f"0775 – devoluções › {c.DEVOLUCAO_CONFERIR}"] == 1


def test_resumo_acompanha_a_planilha(planilha, tmp_path):
    """Trocou a situação ou apagou do controle uma linha acertada: o Resumo se ajusta sozinho."""
    livro = load_workbook(planilha)
    cobrancas = livro[r.ABA_COBRANCAS]
    linha = next(l for l in range(2, cobrancas.max_row + 1) if cobrancas.cell(l, 7).value == c.NAO_COBRADO)
    cobrancas.cell(linha, 7).value = c.BAIXADO
    controle = livro[ABA_CONTROLE]
    linha_pendencia = next(l for l in range(6, controle.max_row + 1)
                           if controle.cell(l, 3).value == TIPO_PENDENCIA and controle.cell(l, 5).value == 12.34)
    controle.cell(linha_pendencia, 5).value = 0
    livro.save(tmp_path / "editada.xlsx")
    valores = _resumo(load_workbook(tmp_path / "editada.xlsx"))
    assert valores[f"0256 do mês anterior › {c.NAO_COBRADO}"] == 0
    assert valores[f"0256 do mês anterior › {c.BAIXADO}"] == 2
    assert valores["Diferença sem explicação (saldo final do razão − total do controle; deve ser zero)"] == 12.34


def test_aba_controle_volta_como_entrada_do_mes_seguinte(planilha, conciliacao):
    leitura = ler_controle(planilha)
    assert leitura.erro is None and leitura.avisos == []
    assert leitura.competencia == date(2026, 5, 1)
    assert leitura.saldo_razao == conciliacao.saldo_final_razao
    assert leitura.itens == conciliacao.controle_novo


def test_abas_de_detalhe(planilha):
    livro = load_workbook(planilha)
    a_conferir = livro[r.ABA_A_CONFERIR]
    assert [c.value for c in a_conferir[1]] == r.COLUNAS_A_CONFERIR
    assert {a_conferir.cell(l, 2).value for l in range(2, a_conferir.max_row + 1)} == {
        "Ajuste qualquer sem nome",
        "Recebimento de valores na tesouraria Quiteria Desconhecida Ramos plano de saude"}
    cobrancas = livro[r.ABA_COBRANCAS]
    assert cobrancas.cell(2, 7).value != c.COBRADO          # o que precisa de atenção vem primeiro
    assert livro[r.ABA_AVISOS].cell(2, 2).value == "ATENÇÃO: teste"
    # lista suspensa na Situação apontando para a aba Listas: o Excel recusa (e "repara") uma lista escrita direto
    # na regra com mais de 255 letras, e as frases do 0256 e dos parcelamentos passam disso
    for aba, opcoes, coluna in ((r.ABA_COBRANCAS, r.SITUACOES_COBRANCA, "A"), (r.ABA_AFASTADOS, r.SITUACOES_AFASTADO, "B"),
                                (r.ABA_PARCELAMENTOS, r.SITUACOES_PARCELAMENTO, "C"),
                                (r.ABA_DEVOLUCOES, r.SITUACOES_DEVOLUCAO, "D")):
        validacao = livro[aba].data_validations.dataValidation[0]
        assert validacao.formula1 == f"'{r.ABA_LISTAS}'!${coluna}$1:${coluna}${len(opcoes)}"
        assert len(validacao.formula1) <= 255
        assert [livro[r.ABA_LISTAS][f"{coluna}{n}"].value for n in range(1, len(opcoes) + 1)] == opcoes


def test_conferir_conjunto_meses_trocados():
    eventos = _eventos()
    razao = _razao(eventos, D("0"))
    controle = LeituraControle("c.xlsx", competencia=date(2026, 4, 1))
    assert conferir_conjunto(eventos, razao, controle) == ""
    controle.competencia = date(2026, 3, 1)
    assert "03/2026" in conferir_conjunto(eventos, razao, controle)
    assert "04/2026 (o mês anterior)" in conferir_conjunto(eventos, razao, controle)
    razao.fim = date(2026, 10, 31)
    assert "31/10/2026" in conferir_conjunto(eventos, razao, LeituraControle("c", competencia=date(2026, 4, 1)))


def test_pasta_lembrada(tmp_path):
    assert ler_pasta_lembrada(tmp_path) == ""
    assert salvar_pasta_lembrada(r"C:\Saida", tmp_path)
    assert ler_pasta_lembrada(tmp_path) == r"C:\Saida"


# ---------------------------------------------------------------------
# Caminho inteiro com os arquivos reais: abril → maio → junho
# ---------------------------------------------------------------------
reais = pytest.mark.skipif(not (PASTA / "casos_reais.json").exists(), reason="exemplos reais fora do git")


def _eventos_real(mes):
    return next((PASTA / mes).glob("EVENTOS*"))


@reais
def test_maio_e_junho_pela_porta_da_tela(tmp_path):
    abril = controle_inicial("2026-04")
    controle_abril = gravar_controle(tmp_path / "controle_abril.xlsx", abril.competencia,
                                     "FUNDAÇÃO HOSPITAL EXEMPLO DE MISER. DE CIDADE ALFA", D("97075.60"), abril.itens)
    maio = processar(_eventos_real("2026-05"), PASTA / "2026-05" / "Razão.pdf", controle_abril, tmp_path,
                     agora=AGORA)
    assert maio.erro == "" and maio.erro_saida == ""
    assert maio.caminho_planilha.name == "CreditoEstouro_mai2026.xlsx"
    assert maio.conciliacao.diferenca_sem_explicacao == 0

    # o Excel de maio entra como controle de junho
    junho = processar(_eventos_real("2026-06"), PASTA / "2026-06" / "razao_06_credito_suplemento.xls",
                      maio.caminho_planilha, tmp_path, agora=AGORA)
    assert junho.erro == "" and junho.erro_saida == ""
    assert junho.conciliacao.diferenca_sem_explicacao == 0
    assert junho.conciliacao.a_conferir == []
    assert junho.conciliacao.composicao[TIPO_PENDENCIA] == D("4039.86")
    valores = _resumo(load_workbook(junho.caminho_planilha))
    assert valores["Diferença sem explicação (saldo final do razão − total do controle; deve ser zero)"] == 0
    assert valores["Total do controle"] == pytest.approx(116027.92)
    assert valores[f"0256 do mês anterior › {c.NAO_COBRADO}"] == 6


@reais
def test_processar_para_com_arquivo_ou_mes_errado(tmp_path):
    abril = controle_inicial("2026-04")
    controle_abril = gravar_controle(tmp_path / "controle_abril.xlsx", abril.competencia, "", D("0"), abril.itens)
    trocado = processar(_eventos_real("2026-05"), _eventos_real("2026-05"), controle_abril, tmp_path)
    assert trocado.erro.startswith("Razão") and "PDF de eventos" in trocado.erro
    mes_errado = processar(_eventos_real("2026-06"), PASTA / "2026-06" / "razao_06_credito_suplemento.xls",
                           controle_abril, tmp_path)
    assert "04/2026" in mes_errado.erro and "05/2026 (o mês anterior)" in mes_errado.erro
    razao_errada = processar(_eventos_real("2026-05"), PASTA / "2026-06" / "razao_06_credito_suplemento.xls",
                             controle_abril, tmp_path)
    assert "01/06/2026" in razao_errada.erro
    assert list(tmp_path.glob("Conciliacao_*")) == []        # nada gravado quando para


@reais
def test_previas():
    assert previa_eventos(_eventos_real("2026-06")).texto == (
        "FUNDAÇÃO HOSPITAL EXEMPLO DE MISER. DE CIDADE ALFA · jun/2026 · 0256: 164 · 0258: 140 · 0241: 22 · 1204: 3")
    xls = previa_razao(PASTA / "2026-06" / "razao_06_credito_suplemento.xls")
    assert xls.texto == "Excel · jun/2026 · 27 lançamentos · saldo final R$ 116.027,92" and xls.avisos == []
    pdf = previa_razao(PASTA / "2026-06" / "razao_06_credito_suplemento.pdf")
    assert pdf.texto.startswith("PDF") and "Excel" in pdf.avisos[-1]
    assert previa_controle(PASTA / "2026-05" / "05-2026.xlsx").erro       # a planilha à mão não é o controle
