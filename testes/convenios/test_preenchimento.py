"""V4 e V5 — cópia da planilha com o mês preenchido (P1 a P5) e relatório de conferência (seção 5)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import openpyxl
import pytest

from modulos.convenios import configuracao as cfg
from modulos.convenios.leitor_planilha import ler_planilha
from modulos.convenios.preenchimento import _deslocar_formula
from modulos.convenios.processamento import processar
from testes.convenios.conftest import conta, escrever_planilha, escrever_razao, exemplos, lancamento, total

C1 = ("40075", "4.01.05.01.0001", "Convênio Prefeitura Exemplo")
AGORA = datetime(2026, 10, 29, 10, 0, 0)
ABA = "Receita de Convênios 2026"


def _fat(nome: str) -> str:
    return f"Faturamento Mês NF 1 {nome} Set/2026 Protocolo 1"


def _razao(caminho, *nomes_valores):
    linhas = [lancamento(_fat(nome), credito=max(valor, 0), debito=max(-valor, 0)) for nome, valor in nomes_valores]
    creditos = sum(max(v, 0) for _, v in nomes_valores)
    debitos = sum(max(-v, 0) for _, v in nomes_valores)
    return escrever_razao(caminho, conta(*C1), *linhas, total(*C1, credito=creditos, debito=debitos))


def _aba(caminho):
    return openpyxl.load_workbook(caminho)[ABA]


# ---------------------------------------------------------------------------
# V4 — casos montados
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("formula, antes, esperado", [
    ("=SUM(C5:C56)", 30, "=SUM(C5:C57)"),
    ("=SUM(C5:C56)", 57, "=SUM(C5:C56)"),
    ("=$C$40-C10+SUM(A1:B2)", 20, "=$C$41-C10+SUM(A1:B2)"),
    ("=K59-K61", 60, "=K59-K62"),
    ("=2384371.86-40", 1, "=2384371.86-40"),        # números não são referências
])
def test_v4_formulas_descem_como_no_excel(formula, antes, esperado):
    assert _deslocar_formula(formula, antes) == esperado


def test_v4_mes_preenchido_linha_nova_e_formulas(tmp_path):
    planilha = escrever_planilha(tmp_path / "p.xlsx", [("Alfa", {8: 1}), ("Charlie", {}), ("Delta", {})])
    original = planilha.read_bytes()
    razao = _razao(tmp_path / "r.xlsx", ("Alfa", 10), ("Bravo", 5), ("Delta", -2), ("Delta", 3))
    saida = tmp_path / "saida"
    saida.mkdir()
    config = tmp_path / "config"
    config.mkdir()
    (config / cfg.ARQUIVO_EQUIVALENCIAS).write_text("Nome_no_razao;Linha_da_planilha;Obs\n", encoding="utf-8")
    r = processar(razao, planilha, saida, config, agora=AGORA)
    assert (r.erro, r.erro_saida, r.mes_ja_preenchido) == ("", "", [])
    assert r.caminho_planilha.name == "RECEITAS DE CONVÊNIOS 092026.xlsx"
    assert r.caminho_relatorio.name == "Conferencia_Convenios_2026-09_2026-10-29_100000.xlsx"
    assert planilha.read_bytes() == original                        # o original nunca muda

    aba = _aba(r.caminho_planilha)
    assert [aba.cell(n, 2).value for n in range(5, 9)] == ["Alfa", "Bravo", "Charlie", "Delta"]   # C6: alfabética
    assert [aba.cell(n, 11).value for n in range(5, 9)] == [10, 5, None, 1]                       # P1, P2, C7
    assert aba.cell(5, 10).value == 1                                                             # agosto intacto
    assert [aba.cell(n, 15).value for n in range(5, 9)] == [f"=SUM(C{n}:N{n})" for n in range(5, 9)]   # P4
    assert aba.cell(10, 2).value.strip() == cfg.PLANILHA_TOTAL and aba.cell(10, 11).value == "=SUM(K5:K8)"
    assert aba.cell(12, 2).value == cfg.PLANILHA_SALDO_CONTABIL and aba.cell(12, 11).value == 16   # P3

    p = r.preenchimento
    assert (p.total_preenchido, p.saldo_contabil, p.diferenca) == (Decimal("16"), Decimal("16"), Decimal("0"))
    assert [l.situacao for l in p.linhas] == [cfg.SITUACAO_PREENCHIDA, cfg.SITUACAO_NOVA,
                                              cfg.SITUACAO_SEM_MOVIMENTO, cfg.SITUACAO_PREENCHIDA]
    assert not any(a.erro for a in r.avisos)

    relatorio = openpyxl.load_workbook(r.caminho_relatorio)
    assert relatorio.sheetnames == [cfg.ABA_RESUMO, cfg.ABA_POR_CONVENIO, cfg.ABA_LANCAMENTOS, cfg.ABA_AVISOS]
    assert relatorio[cfg.ABA_LANCAMENTOS].max_row == 1 + 4                                       # P6: nada some


def test_v4_mes_ja_preenchido_pergunta_e_substitui_mantendo_o_que_nao_veio(tmp_path):
    planilha = escrever_planilha(tmp_path / "p.xlsx", [("Alfa", {9: 99}), ("Charlie", {9: 7}), ("Delta", {})])
    razao = _razao(tmp_path / "r.xlsx", ("Alfa", 10))
    saida = tmp_path / "saida"
    saida.mkdir()
    r = processar(razao, planilha, saida, agora=AGORA)
    assert r.mes_ja_preenchido == ["Alfa", "Charlie"] and r.caminho_planilha is None
    assert list(saida.iterdir()) == []                              # nada gravado antes de confirmar

    r = processar(razao, planilha, saida, substituir=True, agora=AGORA)
    aba = _aba(r.caminho_planilha)
    assert [aba.cell(n, 11).value for n in range(5, 8)] == [10, 7, None]
    p = r.preenchimento
    assert [(l.situacao, l.anterior, l.novo) for l in p.linhas] == [
        (cfg.SITUACAO_SUBSTITUIDA, Decimal("99.00"), Decimal("10")),
        (cfg.SITUACAO_MANTIDA, Decimal("7.00"), Decimal("7.00")),
        (cfg.SITUACAO_SEM_MOVIMENTO, None, None)]
    assert p.diferenca == Decimal("7.00")
    assert r.avisos[-1].erro and "Valores mantidos" in r.avisos[-1].mensagem


def test_v4_nada_e_substituido_na_pasta_de_saida(tmp_path):
    planilha = escrever_planilha(tmp_path / "p.xlsx", [("Alfa", {})])
    razao = _razao(tmp_path / "r.xlsx", ("Alfa", 1))
    primeiro = processar(razao, planilha, tmp_path, agora=AGORA)
    segundo = processar(razao, planilha, tmp_path, agora=AGORA)
    assert segundo.caminho_planilha.name == "RECEITAS DE CONVÊNIOS 092026_2.xlsx"
    assert segundo.caminho_relatorio.stem == primeiro.caminho_relatorio.stem + "_2"


def test_v4_total_que_nao_pega_a_linha_nova_avisa(tmp_path):
    planilha = escrever_planilha(tmp_path / "p.xlsx", [("Alfa", {}), ("Bravo", {})])
    livro = openpyxl.load_workbook(planilha)
    livro[ABA]["K8"] = "=SUM(K5:K6)"                                # termina na última linha de convênio
    livro.save(planilha)
    r = processar(_razao(tmp_path / "r.xlsx", ("Zulu", 3)), planilha, tmp_path, agora=AGORA)
    assert _aba(r.caminho_planilha).cell(7, 2).value == "Zulu"
    assert any(a.erro and "não soma todas as linhas" in a.mensagem for a in r.avisos)


def test_v4_erros_de_leitura_vao_para_o_resultado(tmp_path):
    planilha = escrever_planilha(tmp_path / "p.xlsx", [("Alfa", {})], ano=2025, abas_antigas=())
    r = processar(_razao(tmp_path / "r.xlsx", ("Alfa", 1)), planilha, tmp_path)
    assert "não tem a aba" in r.erro and r.caminho_planilha is None
    with pytest.raises(ValueError):
        processar(None, planilha, tmp_path)


# ---------------------------------------------------------------------------
# V5 — arquivos reais (só totais e números de linha: nenhum nome real no teste)
# ---------------------------------------------------------------------------

def test_v5_agosto_refeito_pelo_programa_e_igual_a_planilha_da_contabilidade(tmp_path):
    pasta = exemplos("2026-09")
    planilha = pasta / "RECEITAS DE CONVÊNIOS 082026.xlsx"
    r = processar(pasta / "razao_08_2026.xls", planilha, tmp_path, exemplos("config"), substituir=True, agora=AGORA)
    assert r.erro == r.erro_saida == ""
    p = r.preenchimento
    assert p.diferenca == 0 and p.saldo_contabil == Decimal("3074546.13") and p.linhas_novas == []
    assert sum(l.situacao == cfg.SITUACAO_MANTIDA for l in p.linhas) == 2          # IAMSPE HC e SC, à mão
    original = ler_planilha(planilha, 2026)
    copia = ler_planilha(r.caminho_planilha, 2026)
    coluna = original.colunas_mes[8]
    aba = _aba(r.caminho_planilha)
    for c in original.convenios:
        valor = original.valores.get((c.linha, 8))
        assert aba.cell(c.linha, coluna).value == pytest.approx(valor) if valor is not None else \
            aba.cell(c.linha, coluna).value is None, c.linha
    assert [c.linha for c in copia.convenios] == [c.linha for c in original.convenios]


def test_v5_setembro_preenchido(tmp_path):
    pasta = exemplos("2026-09")
    r = processar(pasta / "Razao Convenios 092026.xlsx", pasta / "RECEITAS DE CONVÊNIOS 082026.xlsx", tmp_path,
                  exemplos("config"), agora=AGORA)
    p = r.preenchimento
    assert [(l.linha, l.novo) for l in p.linhas_novas] == [(24, Decimal("40652.27"))]
    assert p.total_preenchido == Decimal("1994626.13") and p.diferenca == Decimal("-1140564.00")   # o IAMSPE
    copia = ler_planilha(r.caminho_planilha, 2026)
    assert len(copia.convenios) == 52 and copia.linha_total == 60 and copia.linha_saldo == 62
    aba = _aba(r.caminho_planilha)
    assert aba.cell(60, 11).value == "=SUM(K5:K57)" and aba.cell(62, 11).value == pytest.approx(3135190.13)
    assert aba.cell(63, 11).value == "=K60-K62"
    assert openpyxl.load_workbook(r.caminho_relatorio)[cfg.ABA_LANCAMENTOS].max_row == 1 + 189
