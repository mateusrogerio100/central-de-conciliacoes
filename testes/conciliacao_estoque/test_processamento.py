"""E8 — processamento de cada etapa (um botão por etapa) e o resumo da tela."""

from __future__ import annotations

import openpyxl
import pytest

from modulos.conciliacao_estoque import processamento
from modulos.conciliacao_estoque.configuracao_est02 import preparar_configuracao_do_usuario
from modulos.conciliacao_estoque.modelos import Gravidade, MesReferencia
from modulos.conciliacao_estoque.resumo_tela import resumir
from testes.conciliacao_estoque.conftest import arquivo_exemplo

SETEMBRO = MesReferencia(2026, 9)
NOMES = {
    "EST-01": "EST-01 Conciliação saldo anterior estoque 09-2026.xlsx",
    "EST-02": "EST-02 Conciliação contas estoque 09-2026.xlsx",
    "EST-03": "EST-03 Conciliação saldo atual estoque 09-2026.xlsx",
}


@pytest.fixture
def entradas():
    return {"balancete": arquivo_exemplo("Balancete_estoque_completo.xls"),
            "scf": arquivo_exemplo("SCF - Movimento Estoque (Contabilidade).xls"),
            "pdf": arquivo_exemplo("Movimento_estoque_PDF.pdf")}


def _processar(id_etapa, entradas, tmp_path, mes=SETEMBRO, **trocas):
    saida = tmp_path / "saida"
    saida.mkdir(exist_ok=True)
    arquivos = {**entradas, **trocas}
    usados = {c: arquivos[c] for c in processamento.etapa_da_tela(id_etapa).arquivos}
    return processamento.processar(id_etapa, saida, mes, pasta_configuracao=tmp_path / "configuracao", **usados)


def test_etapas_da_tela():
    assert [(e.id, e.texto_botao, e.arquivos) for e in processamento.ETAPAS_DA_TELA] == [
        ("EST-01", "EST-01 · Conciliação saldo anterior estoque", ("balancete", "scf")),
        ("EST-02", "EST-02 · Conciliação contas estoque", ("scf", "pdf")),
        ("EST-03", "EST-03 · Conciliação saldo atual estoque", ("balancete", "scf")),
    ]


def test_interpretar_mes():
    assert processamento.interpretar_mes("09/2026") == SETEMBRO
    assert processamento.interpretar_mes(" 9/2026 ") == SETEMBRO
    assert processamento.interpretar_mes("set/2026") == SETEMBRO      # também aceito
    for invalido in ("", "13/2026", "01/09/2026", "abc"):
        assert processamento.interpretar_mes(invalido) is None


def test_meses_lidos_dos_arquivos(entradas):
    assert [processamento.mes_do_balancete(entradas["balancete"]), processamento.mes_do_scf(entradas["scf"]),
            processamento.mes_do_pdf(entradas["pdf"])] == [SETEMBRO] * 3
    assert processamento.mes_do_scf(entradas["balancete"]) is None   # arquivo errado: sem mês, sem erro


def test_arquivo_de_saida(tmp_path):
    for id_etapa, nome in NOMES.items():
        assert processamento.arquivo_de_saida(id_etapa, tmp_path, SETEMBRO) == tmp_path / nome


@pytest.mark.parametrize("id_etapa", list(NOMES))
def test_cada_etapa_gera_so_o_seu_excel(entradas, tmp_path, id_etapa):
    progresso = []
    saida = tmp_path / "saida"
    saida.mkdir()
    usados = {c: entradas[c] for c in processamento.etapa_da_tela(id_etapa).arquivos}
    resultado = processamento.processar(id_etapa, saida, SETEMBRO, pasta_configuracao=tmp_path / "configuracao",
                                        progresso=lambda texto, fracao: progresso.append(fracao), **usados)
    assert resultado.falha == "" and resultado.erros == 0
    assert [p.name for p in saida.glob("*.xlsx")] == [NOMES[id_etapa]]
    assert resultado.caminho_excel == saida / NOMES[id_etapa]
    assert progresso[0] == 0.0 and progresso[-1] == 1.0
    assert all(a.ok for a in resultado.arquivos)


def test_titulos_novos_no_excel(entradas, tmp_path):
    for id_etapa, aba, titulo in (("EST-01", "Conciliação", "EST-01 · Conciliação saldo anterior estoque · 09/2026"),
                                  ("EST-02", "Grupos", "EST-02 · Conciliação contas estoque · 09/2026"),
                                  ("EST-03", "Conciliação", "EST-03 · Conciliação saldo atual estoque · 09/2026")):
        resultado = _processar(id_etapa, entradas, tmp_path)
        assert openpyxl.load_workbook(resultado.caminho_excel)[aba]["A1"].value == titulo


def test_resumo_est01(entradas, tmp_path):
    resumo = resumir(_processar("EST-01", entradas, tmp_path))
    assert resumo.titulo == "EST-01 · Conciliação saldo anterior estoque"
    assert [(n.valor, n.legenda, n.tom) for n in resumo.numeros] == [
        (23, "contas conciliadas", "ok"), (0, "contas com diferença", "ok"), (3, "avisos · 0 erros", "principal")]
    assert resumo.colunas == ("Grupo", "Contas", "Com diferença")
    assert resumo.linhas == [("ESTOQUE HOSPITAL EXEMPLO", 18, 0), ("ESTOQUE HOSPITAL CORAÇÃO", 4, 0),
                             ("ESTOQUE HOSPITAL CÂNCER", 1, 0)]
    assert [(c.texto, c.status, c.valor) for c in resumo.conferencias] == [
        ("Total do balancete = total do Mapa do Estoque", "ok", "6.558.659,62"),
        ("Grupos conferidos (2 de 3)", "atencao", None),
        ("Grupo 1.01.04.01: provável conta zerada", "atencao", "41.038,00"),
        ("1 local do Mapa do Estoque com saldo e sem conta no balancete", "atencao", None),
    ]
    assert [a.status for a in resumo.avisos] == ["atencao", "atencao", "ok"]
    assert resumo.selo == ("Concluído", "ok")


def test_resumo_est03(entradas, tmp_path):
    resumo = resumir(_processar("EST-03", entradas, tmp_path))
    assert [n.valor for n in resumo.numeros] == [23, 0, 1]            # 1 aviso: classificação repetida (INFO)
    assert [(c.texto, c.status) for c in resumo.conferencias] == [
        ("Total do balancete = total do Mapa do Estoque", "ok"), ("Grupos conferidos (3 de 3)", "ok")]


def test_resumo_est02(entradas, tmp_path):
    resumo = resumir(_processar("EST-02", entradas, tmp_path))
    assert [(n.valor, n.legenda) for n in resumo.numeros] == [
        (11, "de 11 grupos conferidos"), (0, "grupos com diferença"), (2, "avisos · 0 erros")]
    assert resumo.colunas == ("Grupo do Mapa do Estoque", "Operações", "Diferença")
    assert resumo.linhas[0] == ("Notas Fiscais", 5, "0,00") and resumo.linhas[4][0] == "Total (E)"
    assert [(c.texto, c.status, c.valor) for c in resumo.conferencias] == [
        ("Total geral do PDF conferido", "ok", "12.085.173,07"),
        ("Fechamento do total geral", "ok", "6.034.965,49"),
        ("Produção (15) x Consumo na Produção (16)", "atencao", "157,19"),
    ]


def test_pdf_com_problema(entradas, tmp_path):
    falso = tmp_path / "falso.pdf"
    falso.write_bytes(b"nao e pdf")
    resultado = _processar("EST-02", entradas, tmp_path, pdf=falso)
    assert resultado.caminho_excel is None
    assert "o PDF Movimento estoque" in resultado.falha
    resumo = resumir(resultado)
    assert resumo.selo == ("Concluído com erros", "erro")
    assert resumo.conferencias[-1].texto.startswith("Excel não gerado")
    assert resumo.avisos[0].status == "erro"


def test_balancete_errado(entradas, tmp_path):
    resultado = _processar("EST-01", entradas, tmp_path, balancete=entradas["scf"])
    assert resultado.caminho_excel is None and "o balancete" in resultado.falha


def test_configuracao_com_problema_nao_gera_a_est02(entradas, tmp_path):
    destino = preparar_configuracao_do_usuario(pasta=tmp_path / "configuracao")
    pasta = openpyxl.load_workbook(destino)
    pasta["Itens"].append([1, "S - Consumo", "S", "", "Consumo"])
    pasta.save(destino)
    assert processamento.situacao_configuracao(tmp_path / "configuracao")[1] == "erro"

    resultado = _processar("EST-02", entradas, tmp_path)
    assert resultado.caminho_excel is None and "Editar configuração" in resultado.falha
    assert any(a.tipo == "código repetido" and a.gravidade == Gravidade.ERRO for a in resultado.avisos)
    assert _processar("EST-01", entradas, tmp_path).caminho_excel is not None   # não afeta as outras


def test_excel_aberto_vira_falha(entradas, tmp_path):
    (tmp_path / "saida").mkdir()
    (tmp_path / "saida" / NOMES["EST-03"]).mkdir()       # simula o arquivo travado: não dá para gravar
    resultado = _processar("EST-03", entradas, tmp_path)
    assert resultado.caminho_excel is None and resultado.falha
    assert any(a.tipo == "etapa não gerada" for a in resultado.avisos)


def test_mes_informado_diferente_dos_arquivos(entradas, tmp_path):
    resultado = _processar("EST-02", entradas, tmp_path, mes=MesReferencia(2026, 10))
    assert sum(1 for a in resultado.avisos if a.tipo == "mês diferente") == 2     # SCF e PDF
    assert resultado.caminho_excel.name.endswith("10-2026.xlsx")


def test_situacao_e_edicao_da_configuracao(tmp_path):
    texto, status = processamento.situacao_configuracao(tmp_path)
    assert status == "ok" and "de fábrica, 62 operações" in texto
    caminho = processamento.preparar_configuracao(tmp_path)
    assert caminho.is_file()
    assert "sua (editada)" in processamento.situacao_configuracao(tmp_path)[0]
