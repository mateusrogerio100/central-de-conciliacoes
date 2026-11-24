"""E7 — EST-02: conferência dos grupos e Excel (ESPECIFICACAO_ESTOQUE.md, seções 6.3 e 7.1)."""

from __future__ import annotations

import csv
from decimal import Decimal

import openpyxl
import pytest

from modulos.conciliacao_estoque.conferencia_grupos import conferir_grupos, nome_para_exibir
from modulos.conciliacao_estoque.configuracao_est02 import (
    carregar_configuracao_estoque,
    preparar_configuracao_do_usuario,
)
from modulos.conciliacao_estoque.leitor_pdf_movimento import ler_pdf_movimento
from modulos.conciliacao_estoque.leitor_scf import ler_scf
from modulos.conciliacao_estoque.modelos import ErroArquivo, Gravidade, MesReferencia
from modulos.conciliacao_estoque.relatorio_est02 import ABA_GRUPOS, ABA_OPERACOES, gerar_excel_est02
from testes.conciliacao_estoque.conftest import arquivo_exemplo, calcular, com_nome_antigo


def _gabarito() -> list[dict]:
    with open(arquivo_exemplo("gabarito_est02_2026-09.csv"), encoding="utf-8-sig", newline="") as arquivo:
        return list(csv.DictReader(arquivo, delimiter=";"))


@pytest.fixture
def pdf():
    return ler_pdf_movimento(arquivo_exemplo("Movimento_estoque_PDF.pdf"))


@pytest.fixture
def config(tmp_path):
    return carregar_configuracao_estoque(pasta=tmp_path)      # pasta vazia: configuração de fábrica


@pytest.fixture
def resultado(caminho_scf, pdf, config):
    return conferir_grupos(ler_scf(caminho_scf), pdf, config)


# ---------------------------------------------------------------------------
# Conferência contra o gabarito de setembro/2026
# ---------------------------------------------------------------------------


def test_grupos_iguais_ao_gabarito(resultado):
    gerado = {
        linha.nome.split(" — ")[0]: (linha.total_scf, linha.soma_pdf, linha.diferenca, linha.operacoes)
        for linha in resultado.todas_as_linhas
    }
    esperado = {
        g["item"]: (Decimal(g["valor_scf_ou_a"]), Decimal(g["valor_pdf_ou_b"]), Decimal(g["diferenca"]),
                    [int(c) for c in g["operacoes_ou_obs"].split()])
        for g in _gabarito() if g["tipo"] == "grupo"
    }
    assert gerado == esperado
    assert resultado.grupos_conferidos == 11 and resultado.grupos_com_diferenca == 0


def test_conferencias_e_par_iguais_ao_gabarito(resultado):
    gabarito = {g["item"]: g for g in _gabarito() if g["tipo"] in ("conferencia", "par")}
    total_geral = gabarito["Total geral do PDF"]
    assert resultado.total_geral_pdf == Decimal(total_geral["valor_scf_ou_a"])
    assert resultado.soma_operacoes_pdf == Decimal(total_geral["valor_pdf_ou_b"])
    fechamento = gabarito["Fechamento do total geral"]
    assert resultado.saldo_atual_scf == Decimal(fechamento["valor_scf_ou_a"])
    assert resultado.fechamento_calculado == Decimal(fechamento["valor_pdf_ou_b"])
    assert resultado.diferenca_fechamento == 0

    par = resultado.pares[0]
    assert f"{par.par.operacao_a} x {par.par.operacao_b}" == "15 x 16"
    assert (par.valor_a, par.valor_b, par.diferenca) == (
        Decimal(gabarito["15 x 16"]["valor_scf_ou_a"]), Decimal(gabarito["15 x 16"]["valor_pdf_ou_b"]),
        Decimal(gabarito["15 x 16"]["diferenca"]),
    )
    assert par.mensagem == "ATENÇÃO: Produção (15) diferente de Consumo na Produção (16) — verificar"


def test_avisos_de_setembro(resultado):
    """Só o par 15 x 16 gera aviso (a 82 não está no PDF de setembro)."""
    assert resultado.mes_referencia == MesReferencia(2026, 9)
    assert [(a.gravidade, a.tipo) for a in resultado.avisos] == [(Gravidade.ATENCAO, "par diferente")]
    assert "157,19" in resultado.avisos[0].mensagem


def test_mapa_movimentacao_da_o_mesmo_resultado(caminho_scf, caminho_mapa, pdf, config):
    do_scf = conferir_grupos(ler_scf(caminho_scf), pdf, config)
    do_mapa = conferir_grupos(ler_scf(caminho_mapa), pdf, config)
    assert [(l.nome, l.total_scf, l.soma_pdf, l.operacoes) for l in do_mapa.todas_as_linhas] == [
        (l.nome, l.total_scf, l.soma_pdf, l.operacoes) for l in do_scf.todas_as_linhas
    ]
    assert do_mapa.diferenca_fechamento == do_scf.diferenca_fechamento == 0


def test_operacoes_da_aba(resultado):
    assert [o.codigo for o in resultado.operacoes] == sorted(o.codigo for o in resultado.operacoes)
    por_codigo = {o.codigo: o for o in resultado.operacoes}
    assert (por_codigo[11].nome, por_codigo[11].grupo, por_codigo[11].es_tabela) == (
        "Nota Fiscal de Compra", "Notas Fiscais", "E")
    assert por_codigo[15].observacao == por_codigo[16].observacao == (
        "Produção (15) diferente de Consumo na Produção (16): diferença de 157,19 — ver aba Grupos")
    assert por_codigo[1].observacao == ""


def test_nome_para_exibir():
    assert nome_para_exibir("E - Produção") == "Produção"
    assert nome_para_exibir("S - Consumo na Produção") == "Consumo na Produção"
    assert nome_para_exibir("Sem prefixo - X") == "Sem prefixo - X"


# ---------------------------------------------------------------------------
# Configuração alterada (seção 7.1, testes extras)
# ---------------------------------------------------------------------------


def _alterar_itens(tmp_path, alterar):
    destino = preparar_configuracao_do_usuario(pasta=tmp_path)
    pasta = openpyxl.load_workbook(destino)
    alterar(pasta["Itens"])
    pasta.save(destino)
    return carregar_configuracao_estoque(pasta=tmp_path)


def test_codigo_repetido_nao_roda(caminho_scf, pdf, tmp_path):
    config = _alterar_itens(tmp_path, lambda aba: aba.append([1, "S - Consumo", "S", "", "Consumo"]))
    with pytest.raises(ErroArquivo, match="código repetido|aparece nas linhas"):
        conferir_grupos(ler_scf(caminho_scf), pdf, config)


def test_operacao_removida_vira_sem_grupo_e_a_diferenca_aparece_no_grupo(caminho_scf, pdf, tmp_path):
    def remover_87(aba):
        aba.delete_rows(next(c.row for c in aba["A"] if c.value == 87))
    resultado = conferir_grupos(ler_scf(caminho_scf), pdf, _alterar_itens(tmp_path, remover_87))
    consumo = next(l for l in resultado.saidas if l.nome == "Consumo")
    assert consumo.operacoes == [1, 91, 92]
    assert consumo.diferenca == Decimal("1028.06")
    assert resultado.total_saidas.diferenca == Decimal("1028.06")
    assert resultado.grupos_com_diferenca == 2
    tipos = [a.tipo for a in resultado.avisos]
    assert "operação sem grupo" in tipos and "grupo com diferença" in tipos
    linha_87 = next(o for o in resultado.operacoes if o.codigo == 87)
    assert linha_87.sem_grupo and linha_87.observacao.startswith("Operação sem grupo")


# ---------------------------------------------------------------------------
# Excel
# ---------------------------------------------------------------------------


def test_excel_est02(resultado, tmp_path):
    caminho = gerar_excel_est02(resultado, tmp_path)
    assert caminho.name == "EST-02 Conciliação contas estoque 09-2026.xlsx"
    pasta = openpyxl.load_workbook(caminho)
    assert pasta.sheetnames == [ABA_GRUPOS, ABA_OPERACOES]
    grupos, operacoes = pasta[ABA_GRUPOS], pasta[ABA_OPERACOES]

    assert grupos["A1"].value == "EST-02 · Conciliação contas estoque · 09/2026"
    assert "configuração de fábrica" in grupos["A2"].value
    esperado = {g["item"]: g for g in _gabarito()}
    for linha in range(5, 16):
        nome = grupos[f"A{linha}"].value.split(" — ")[0]
        assert calcular(grupos, f"B{linha}") == Decimal(esperado[nome]["valor_scf_ou_a"]), nome
        assert calcular(grupos, f"C{linha}") == Decimal(esperado[nome]["valor_pdf_ou_b"]), nome
        assert calcular(grupos, f"D{linha}") == 0, nome
    assert grupos["E5"].value == "11, 12, 14, 112, 120" and grupos["E6"].value == "—"
    assert grupos["C9"].value == "=SUM(C5:C8)" and grupos["C15"].value == "=SUM(C10:C14)"

    assert grupos["A17"].value == "Conferências"
    assert grupos["A18"].value == "Total geral do PDF" and calcular(grupos, "D18") == 0
    assert calcular(grupos, "C18") == Decimal("12085173.07")
    assert grupos["A19"].value == "Fechamento do total geral (Mapa do Estoque)" and calcular(grupos, "D19") == 0
    assert grupos["A20"].value == "Produção (op. 15) x Consumo na Produção (op. 16)"
    assert calcular(grupos, "D20") == Decimal("157.19")
    assert grupos["E20"].value == (
        '=IF(ROUND(D20,2)<>0,"ATENÇÃO: Produção (15) diferente de Consumo na Produção (16) — verificar",'
        '"OK: Produção (15) igual a Consumo na Produção (16)")'
    )
    regras = {str(i.sqref): [r.formula for r in i.rules] for i in grupos.conditional_formatting}
    assert regras == {"D5:D20": [["AND(ISNUMBER(D5),ROUND(D5,2)<>0)"]], "E20": [["ROUND(D20,2)<>0"]]}
    assert grupos.freeze_panes == "A5"

    assert [operacoes.cell(3, c).value for c in range(1, 7)] == [
        "Código", "Operação", "Valor (PDF)", "Grupo do Mapa do Estoque", "E/S na tabela", "Observação"]
    assert [operacoes[f"A{n}"].value for n in range(4, 22)] == sorted(o.codigo for o in resultado.operacoes)
    assert operacoes["B22"].value == "TOTAL" and operacoes["C22"].value == "=SUM(C4:C21)"
    assert operacoes.auto_filter.ref == "A3:F21" and operacoes.freeze_panes == "A4"


def test_excel_igual_ao_exemplo_aprovado_nos_valores(resultado, tmp_path):
    """Mesmos valores e fórmulas do exemplo, menos as mudanças explicadas abaixo."""
    gerada = openpyxl.load_workbook(gerar_excel_est02(resultado, tmp_path))
    exemplo = openpyxl.load_workbook(arquivo_exemplo("Exemplo_EST-02_Grupos_SCF_09-2026.xlsx"))
    mudancas_aprovadas = {
        (ABA_GRUPOS, "A1"),     # nome da etapa: "Conciliação contas estoque" (decisão de 06/10/2026)
        (ABA_GRUPOS, "A2"),     # nomes dos arquivos e configuração usada
        (ABA_GRUPOS, "C18"),    # especificação: soma de TODAS as operações lidas (exemplo: C9+C15)
        (ABA_GRUPOS, "E18"),
        (ABA_OPERACOES, "B10"),  # nome vem da configuração ("Doação - Materiais"; exemplo com 2 espaços)
    }
    diferencas = [
        (nome, c.coordinate, c.value, gerada[nome][c.coordinate].value)
        for nome in exemplo.sheetnames for linha in exemplo[nome].iter_rows() for c in linha
        if c.value != com_nome_antigo(gerada[nome][c.coordinate].value)
        and (nome, c.coordinate) not in mudancas_aprovadas
    ]
    assert diferencas == []


def test_excel_com_operacao_sem_grupo_destacada(caminho_scf, pdf, tmp_path):
    def remover_87(aba):
        aba.delete_rows(next(c.row for c in aba["A"] if c.value == 87))
    resultado = conferir_grupos(ler_scf(caminho_scf), pdf, _alterar_itens(tmp_path, remover_87))
    operacoes = openpyxl.load_workbook(gerar_excel_est02(resultado, tmp_path))[ABA_OPERACOES]
    linha = next(c.row for c in operacoes["A"] if c.value == 87)
    assert operacoes[f"D{linha}"].value == "Sem grupo"
    assert operacoes[f"A{linha}"].fill.fgColor.rgb.endswith("FBEEDD")
    assert operacoes[f"A{linha}"].font.bold
