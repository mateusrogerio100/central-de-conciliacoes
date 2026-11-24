"""T6 — relatório Excel e processamento completo.

Com os lotes reais (exemplos\\conferencia_nf\\, pulado sem a pasta), o relatório tem que ser igual
ao modelo aprovado Conferencia_NF_*.xlsx de cada lote, célula por célula (menos "Gerado em").
"""

from __future__ import annotations

import shutil
from datetime import datetime
from decimal import Decimal

import openpyxl
import pytest

from modulos.conferencia_nf import leitor_pdfs
from modulos.conferencia_nf.conferencia import conferir
from modulos.conferencia_nf.leitor_lote import ler_lote
from modulos.conferencia_nf.modelos import FalhaLeitura, Situacao
from modulos.conferencia_nf.processamento import caminho_novo_relatorio, processar
from modulos.conferencia_nf.relatorio import gerar_relatorio
from testes.conferencia_nf.conftest import ler_pdfs_do_lote
from testes.conferencia_nf.test_conferencia import (
    AME_CIDADE_ALFA, EMITENTE, FUNDACAO, _compra, _nota,
)
from testes.conftest import diferencas_entre_planilhas, pasta_exemplos

ABAS = ["Resumo", "Conferir à mão", "Escriturar na prefeitura", "Lançamentos", "Rateios",
        "Contas a conferir", "PDF x Tasy", "PDFs sem lançamento", "Erros de leitura"]


def _notas_da_prefeitura(aba) -> list[tuple]:
    """As linhas das notas da aba "Escriturar na prefeitura" (a legenda dos códigos vem depois de
    uma linha em branco, S16a)."""
    linhas = []
    for linha in aba.iter_rows(min_row=2, values_only=True):
        if not any(linha):
            break
        linhas.append(linha)
    return linhas


def _relatorio_do_lote(nome: str, saida):
    lote = pasta_exemplos("conferencia_nf", nome)
    arquivo_lote = next(lote.glob("Movimento*.csv"))
    fatos = ler_lote(arquivo_lote)
    notas, falhas, _ = ler_pdfs_do_lote(nome)
    sem_pdf = leitor_pdfs.ler_sem_pdf(lote)
    resultados = conferir(fatos, notas, sem_pdf, FUNDACAO)        # como a tela (S15)
    caminho = gerar_relatorio(saida / "relatorio.xlsx", resultados, notas, [], falhas, sem_pdf,
                              [arquivo_lote.name], unidade=FUNDACAO)
    return lote, fatos, resultados, caminho


@pytest.mark.parametrize("nome", ["lote_72648", "lote_72887"])
def test_t6_relatorio_igual_ao_modelo_aprovado(nome, tmp_path):
    lote, _, _, caminho = _relatorio_do_lote(nome, tmp_path)
    modelo = next(lote.glob("Conferencia_NF_*.xlsx"))
    diferencas = [d for d in diferencas_entre_planilhas(modelo, caminho)
                  if (d[0], d[1]) != ("Resumo", "B2")]          # "Gerado em"
    assert diferencas == []


@pytest.mark.parametrize("nome", ["lote_72648", "lote_72887"])
def test_t6_abas_e_linhas(nome, tmp_path):
    _, fatos, resultados, caminho = _relatorio_do_lote(nome, tmp_path)
    livro = openpyxl.load_workbook(caminho)
    assert livro.sheetnames == ABAS
    pdf_x_tasy = [linha[1] for linha in livro["PDF x Tasy"].iter_rows(min_row=2, values_only=True)]
    assert sorted(pdf_x_tasy) == sorted(f.fato for f in fatos)        # uma linha por fato
    a_mao = [linha[1] for linha in livro["Conferir à mão"].iter_rows(min_row=2, values_only=True)]
    assert sorted(a_mao) == sorted(r.fato.fato for r in resultados if r.situacao != Situacao.OK)
    lancamentos = [(linha[1], linha[4]) for linha in
                   livro["Lançamentos"].iter_rows(min_row=2, values_only=True)]
    assert lancamentos == [(f.fato, l.sequencia) for f in fatos for l in f.lancamentos]
    prefeitura = [linha[5] for linha in _notas_da_prefeitura(livro["Escriturar na prefeitura"])]
    servicos = [r.fato.fato for r in resultados if r.nota and r.nota.tipo == "NFS-e"]
    assert servicos and sorted(prefeitura) == sorted(servicos)     # S9: só os casados com DANFSe
    marcados = {linha[1] for linha in livro["Lançamentos"].iter_rows(min_row=2, values_only=True)
                if linha[14] == "SIM"}
    assert marcados == set(servicos)
    for aba in ABAS[1:]:
        assert livro[aba].freeze_panes == "A2"
    for aba in ABAS[1:8]:
        assert livro[aba].auto_filter.ref


# ---------------------------------------------------------------------------
# Relatório montado no teste (roda sem a pasta de exemplos)
# ---------------------------------------------------------------------------

def test_relatorio_montado(tmp_path):
    divergente = _compra("1", valor="29.80")
    sem_pdf = _compra("2", nf="999")
    ok = _compra("3", nf="1851606")
    notas = [_nota(valor="19.80"), _nota("1851606"), _nota("555", arquivo="sobra.pdf")]
    resultados = conferir([divergente, sem_pdf, ok], notas, [])
    caminho = gerar_relatorio(tmp_path / "r.xlsx", resultados, notas,
                              [FalhaLeitura("lote.csv", "Não foi possível ler o lote: x")],
                              [FalhaLeitura("ruim.pdf", "O PDF não tem texto.")], [], ["lote.csv"],
                              datetime(2026, 10, 13, 10, 0, 0))
    livro = openpyxl.load_workbook(caminho)
    assert livro.sheetnames == ABAS
    resumo = {linha[0]: linha[1] for linha in livro["Resumo"].iter_rows(values_only=True)}
    assert resumo["Gerado em"] == "13/10/2026 10:00:00"
    assert resumo["  VERDE — conferidos pelo programa: só olhar as contas e revisar"] == 1
    assert resumo["  CONFERIR À MÃO"] == 2
    assert resumo["PDFs com erro de leitura"] == 1
    a_mao = list(livro["Conferir à mão"].iter_rows(min_row=2, values_only=True))
    assert [(l[0], l[1]) for l in a_mao] == [("PDF não bate com o lançamento", "1"),
                                            ("PDF da nota não veio", "2")]
    assert "Valor: Tasy (total dos débitos) 29,80 x nota 19,80" in a_mao[0][7]
    assert a_mao[0][5] == 29.8
    sobras = list(livro["PDFs sem lançamento"].iter_rows(min_row=2, values_only=True))
    assert [(s[1], s[6]) for s in sobras] == [("555", "Nota não encontrada no lote.")]
    erros = list(livro["Erros de leitura"].iter_rows(min_row=2, values_only=True))
    assert erros == [("lote.csv", "Não foi possível ler o lote: x"),
                     ("ruim.pdf", "O PDF não tem texto.")]
    # cores: vermelho divergente, amarelo sem PDF; caixa "Conferido" com borda
    aba = livro["Conferir à mão"]
    assert aba["A2"].fill.fgColor.rgb.endswith("FFC7CE")
    assert aba["A3"].fill.fgColor.rgb.endswith("FFEB9C")
    assert aba["J2"].border.left.style == "thin"
    assert _notas_da_prefeitura(livro["Escriturar na prefeitura"]) == []   # nenhuma de serviço


def test_s9_notas_de_servico_para_escriturar_na_prefeitura(tmp_path):
    servico_ok = _compra("1", nf="1851606")
    servico_divergente = _compra("2", nf="77", valor="50.00")
    compra = _compra("3")
    servico_sem_pdf = _compra("4", nf="999")
    notas = [_nota("1851606", tipo="NFS-e"), _nota("77", valor="40.00", tipo="NFS-e"), _nota(),
             _nota("555", tipo="NFS-e", arquivo="solto.pdf")]       # DANFSe sem lançamento
    resultados = conferir([servico_ok, servico_divergente, compra, servico_sem_pdf], notas, [])
    caminho = gerar_relatorio(tmp_path / "r.xlsx", resultados, notas, [], [], [], [])
    livro = openpyxl.load_workbook(caminho)
    aba = livro["Escriturar na prefeitura"]
    linhas = _notas_da_prefeitura(aba)
    assert [(l[2], l[5], l[7]) for l in linhas] == [("77", "2", "DIVERGENTE"),   # por nº da nota
                                                    ("1851606", "1", "OK")]
    assert linhas[1][:5] == (EMITENTE, "00909901000109", "1851606", "25/09/2026", 29.8)
    assert linhas[0][21] is None and aba["V2"].border.left.style == "thin"   # "Escriturado"
    assert aba["A2"].fill.fgColor.rgb.endswith("FFC7CE")                   # cor da situação
    assert aba.auto_filter.ref
    marcas = {l[1]: l[14] for l in livro["Lançamentos"].iter_rows(min_row=2, values_only=True)}
    assert marcas == {"1": "SIM", "2": "SIM", "3": None, "4": None}
    a_mao = {l[1]: l[8] for l in livro["Conferir à mão"].iter_rows(min_row=2, values_only=True)}
    assert a_mao == {"2": "SIM", "4": None}                    # sem PDF: o tipo não é conhecido
    resumo = {l[0]: l[1] for l in livro["Resumo"].iter_rows(values_only=True)}
    assert resumo["Notas de serviço para escriturar na prefeitura (com PDF)"] == 2


def test_s10_falar_com_o_fornecedor_na_aba_da_prefeitura(tmp_path):
    sem_federal, com_irrf, nao_lido = _nota("10", tipo="NFS-e"), _nota("11", tipo="NFS-e"), \
        _nota("12", tipo="NFS-e")
    for nota, irrf in ((sem_federal, Decimal("0.00")), (com_irrf, Decimal("15.00")),
                       (nao_lido, None)):
        nota.regime, nota.atividade, nota.retencao_iss = "Não Optante", "04.01.01 - Medicina.", \
            "Não Retido"
        nota.aliquota_iss, nota.valor_iss = Decimal("2.00"), Decimal("0.60")
        nota.irrf, nota.previdencia_retida, nota.contribuicoes_retidas = irrf, Decimal("0.00"), \
            Decimal("0.00")
    fatos = [_compra("1", nf="10"), _compra("2", nf="11"), _compra("3", nf="12")]
    notas = [sem_federal, com_irrf, nao_lido]
    resultados = conferir(fatos, notas, [])
    caminho = gerar_relatorio(tmp_path / "r.xlsx", resultados, notas, [], [], [], [])
    livro = openpyxl.load_workbook(caminho)
    aba = livro["Escriturar na prefeitura"]
    titulos = [c.value for c in aba[1]]
    assert titulos[10:] == ["Regime (Simples)", "Atividade", "Alíquota ISS (%)", "ISS",
                            "Retenção do ISS", "IRRF", "Previdência retida",
                            "Contribuições Sociais retidas", "Descrição contrib. sociais",
                            "Falar com o fornecedor", "Retorno do fornecedor", "Escriturado"]
    linhas = {l[2]: l for l in aba.iter_rows(min_row=2, values_only=True)}
    assert linhas["10"][10:20] == ("Não Optante", "04.01.01 - Medicina.", 2, 0.6, "Não Retido",
                                   0, 0, 0, None, "SIM")
    assert linhas["11"][15] == 15 and linhas["11"][19] is None
    assert linhas["12"][19] == "CONFERIR NO PDF (impostos federais não lidos)"
    assert all(l[20] is None for l in linhas.values())            # "Retorno do fornecedor"
    resumo = {l[0]: l[1] for l in livro["Resumo"].iter_rows(values_only=True)}
    assert resumo["      Não Optante sem imposto federal retido: falar com o fornecedor"] == 1


def test_nota_da_propria_fundacao_e_repetida_em_pdfs_sem_lancamento(tmp_path):
    propria = _nota("89680", arquivo="a.pdf", tipo="NFS-e")
    propria.emitente_documento = "98765432000198"
    repetida = _nota("10", arquivo="c.pdf", situacao="Cancelada", tipo="NFS-e")
    repetida.repetida_de = "b.pdf"
    caminho = gerar_relatorio(tmp_path / "r.xlsx", [], [propria, repetida], [], [], [], [])
    sobras = {l[1]: l[6] for l in openpyxl.load_workbook(caminho)["PDFs sem lançamento"]
              .iter_rows(min_row=2, values_only=True)}
    assert sobras["89680"] == "Nota emitida pela própria Fundação (serviço prestado, não é compra)."
    assert sobras["10"] == "PDF repetido: mesma nota do arquivo b.pdf. Situação da nota: Cancelada."


# ---------------------------------------------------------------------------
# Processamento
# ---------------------------------------------------------------------------

def _pasta_pequena(tmp_path):
    """O lote 72887 com só 2 PDFs (1 DANFE e 1 DANFSe): processamento rápido."""
    lote = pasta_exemplos("conferencia_nf", "lote_72887")
    pdfs = tmp_path / "pdfs"
    for padrao in ("DANFE-935-*.pdf", "DANFSe-968-*.pdf"):
        origem = next(lote.rglob(padrao))
        (pdfs / origem.parent.name).mkdir(parents=True, exist_ok=True)
        shutil.copy(origem, pdfs / origem.parent.name / origem.name)
    return next(lote.glob("Movimento*.csv")), pdfs


def test_processar_grava_o_relatorio_e_informa_o_andamento(tmp_path):
    arquivo_lote, pdfs = _pasta_pequena(tmp_path)
    andamento = []
    r = processar(arquivo_lote, pdfs, tmp_path / "saida", lambda t, f: andamento.append((t, f)))
    assert r.erro_relatorio == "" and r.caminho_relatorio.exists()
    assert r.caminho_relatorio.parent == tmp_path / "saida"
    assert r.caminho_relatorio.name.startswith("Conferencia_NF_")
    assert len(r.resultados) == 55 and len(r.notas) == 2 and r.falhas_pdf == []
    assert r.conferidos == r.quantidade(Situacao.OK) == 2
    assert len(r.a_mao) == 53 and r.sem_lancamento == [] and r.repetidos == []
    assert ("Lendo PDFs... 1 de 2", 0.0) in andamento
    assert andamento[-1] == ("Pronto.", 1.0)


def test_lote_ilegivel_vira_erro_e_o_relatorio_sai_mesmo_assim(tmp_path):
    lote = tmp_path / "lote.csv"
    lote.write_text("isto não é o lote", encoding="utf-8")
    r = processar(lote, tmp_path, tmp_path)
    assert r.resultados == [] and r.caminho_relatorio.exists()
    assert len(r.falhas_lote) == 1
    assert r.falhas_lote[0].motivo.startswith("Não foi possível ler o lote: Colunas não "
                                              "encontradas")


def test_relatorio_que_nao_pode_ser_gravado_vira_erro(tmp_path):
    lote = tmp_path / "lote.csv"
    lote.write_text("x", encoding="utf-8")
    arquivo_no_lugar_da_pasta = tmp_path / "saida"
    arquivo_no_lugar_da_pasta.write_text("")
    r = processar(lote, tmp_path / "vazia", arquivo_no_lugar_da_pasta)
    assert r.caminho_relatorio is None
    assert r.erro_relatorio.startswith("Não foi possível gravar o relatório Conferencia_NF_")


def test_nome_do_relatorio_nunca_substitui_um_anterior(tmp_path):
    agora = datetime(2026, 10, 13, 10, 16, 58)
    primeiro = caminho_novo_relatorio(tmp_path, agora)
    assert primeiro.name == "Conferencia_NF_2026-10-13_101658.xlsx"
    primeiro.write_bytes(b"")
    assert caminho_novo_relatorio(tmp_path, agora).name == "Conferencia_NF_2026-10-13_101658_2.xlsx"


def test_processar_sem_os_caminhos_e_erro_da_chamada():
    with pytest.raises(ValueError):
        processar(None, None, None)


def test_valores_do_relatorio_sao_numeros(tmp_path):
    resultados = conferir([_compra(valor="1234.56")], [], [])
    caminho = gerar_relatorio(tmp_path / "r.xlsx", resultados, [], [], [], [], [])
    linha = next(openpyxl.load_workbook(caminho)["Lançamentos"].iter_rows(min_row=2,
                                                                         values_only=True))
    assert linha[10] == float(Decimal("1234.56")) and linha[11] is None


def test_s15_cnpj_errado_no_relatorio(tmp_path):
    """Nota de outra unidade: vermelha, com o motivo na aba "Conferir à mão", a coluna "Unidade"
    na "PDF x Tasy" e a contagem no Resumo."""
    resultados = conferir([_compra()], [_nota()], [], AME_CIDADE_ALFA)
    caminho = gerar_relatorio(tmp_path / "r.xlsx", resultados, [], [], [], [], ["lote.csv"],
                              unidade=AME_CIDADE_ALFA)
    livro = openpyxl.load_workbook(caminho)
    a_mao = livro["Conferir à mão"]
    assert a_mao["A2"].value == "CNPJ da nota não é o da unidade conferida"
    assert a_mao["A2"].fill.start_color.rgb.endswith("FFC7CE")             # vermelho
    titulos = [c.value for c in livro["PDF x Tasy"][1]]
    linha = dict(zip(titulos, [c.value for c in livro["PDF x Tasy"][2]]))
    assert linha["Unidade"] == "ERRADO"
    assert linha["Destinatário / tomador (nota)"] ==         "Fundação Hospital Exemplo (98.765.432/0001-98)"
    resumo = {l[0]: l[1] for l in livro["Resumo"].iter_rows(values_only=True)}     # pelo título da linha
    assert resumo["Unidade conferida (CNPJ do destinatário / tomador da nota)"] ==         "AME Cidade Alfa (98.765.432/0004-30): 1 nota(s) com CNPJ errado (vermelho)."
