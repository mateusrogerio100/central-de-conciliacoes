"""T10 — S14: gabarito de contas (ensinar com o Movimento contábil revisado e conferir).

- Ensinar com o Movimento contábil de 09/2026 (exemplos, fora do git) e conferir o lote de 01/10.
- Regras com dados fictícios: padrão x histórico, produto do complemento, não contar em dobro,
  estorno não aprendido, aba "Padrão" (e a senha dela) nunca alterada pelo programa.
- A aba "Gabarito de contas" da tela. Tudo com %APPDATA% temporário; nada vai para a rede.
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal

import openpyxl
import pytest

from modulos.conferencia_nf import MODULO, gabarito, processamento
from modulos.conferencia_nf import configuracao as cfg
from modulos.conferencia_nf.conferencia import conferir
from modulos.conferencia_nf.leitor_lote import ler_lote
from modulos.conferencia_nf.modelos import Fato, Lancamento
from modulos.conferencia_nf.relatorio import gerar_relatorio
from testes.conftest import caso_real, esperar, pasta_exemplos

FORNECEDOR, FILTRO, OLEO = "4577", "30080", "30075"


@pytest.fixture(autouse=True)
def appdata_temporario(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))


def _setembro():
    return pasta_exemplos("conferencia_nf") / "Movimento contábil_09-2026.csv"


def _movimento(nome):
    return pasta_exemplos("conferencia_nf", "movimento_contabil") / nome


# ---------------------------------------------------------------------------
# Arquivos reais
# ---------------------------------------------------------------------------

def test_t10_ensinar_setembro_e_conferir_01_10(tmp_path):
    ensino = gabarito.ensinar(tmp_path, [_setembro()])
    assert ensino.erro == "" and ensino.falhas == []
    assert (ensino.fatos_novos, ensino.fatos_sem_fornecedor, ensino.lancamentos) == (1672, 24, 2654)
    de_novo = gabarito.ensinar(tmp_path, [_setembro()])
    assert (de_novo.fatos_novos, de_novo.fatos_ja_aprendidos) == (0, 1672)       # não dobra
    memoria = gabarito.abrir_gabarito(tmp_path)
    assert len(memoria.historico) == 962 and len(memoria.fatos_aprendidos) == 1672
    assert sum(i.vezes for i in memoria.historico.values()) == 2654

    resultados = conferir(ler_lote(_movimento("lote_72887_movimento_contabil.csv")), [], [])
    gabarito.conferir_contas(resultados, memoria)
    assert Counter(a.resultado for r in resultados for a in r.contas) == {
        cfg.GABARITO_IGUAL_HISTORICO: 35, cfg.GABARITO_PRODUTO_NOVO: 8,
        cfg.GABARITO_DIFERENTE: 6, cfg.GABARITO_FORNECEDOR_NOVO: 4}
    do_fato = [a for r in resultados if r.fato.fato == "6599410" for a in r.contas]
    assert {a.resultado for a in do_fato} == {cfg.GABARITO_DIFERENTE}
    assert "1.01.04.02.0009 Estoque Órtese e Prótese - HC" in do_fato[0].detalhe


def test_t10_planilha_para_padronizar(tmp_path):
    gabarito.ensinar(tmp_path, [_setembro()])
    livro = openpyxl.load_workbook(gabarito.caminho_gabarito(tmp_path))
    assert livro.sheetnames == list(cfg.GABARITO_ABAS)
    linhas = list(livro[cfg.GABARITO_ABA_PADRONIZAR].iter_rows(min_row=2, values_only=True))
    grupos = {(l[0], l[2]) for l in linhas}
    assert len(grupos) == 57                                     # fornecedor + produto
    fornecedor = caso_real("conferencia_nf", "fornecedor_planilha_padronizar")
    do_fornecedor = [l for l in linhas if l[1].startswith(fornecedor)][:2]
    assert [(l[4], l[6], l[9]) for l in do_fornecedor] == [
        ("3.01.01.07.0006", 96, cfg.GABARITO_SUGESTAO), ("1.01.04.01.0012", 4, None)]
    assert round(do_fornecedor[0][7], 2) == 0.96


# ---------------------------------------------------------------------------
# Dados fictícios
# ---------------------------------------------------------------------------

def _l(lado, conta, classificacao, valor, complemento) -> Lancamento:
    return Lancamento(sequencia=conta, conta_debito=conta if lado == "D" else "",
                      conta_credito=conta if lado == "C" else "", nome_conta=f"Conta {conta}",
                      classificacao=classificacao, valor=Decimal(valor), complemento=complemento,
                      centro_custo="366" if classificacao.startswith("3") else "")


def _compra(numero, conta=FILTRO, produto="Filtro de Agua", invertido=False, nf=None) -> Fato:
    complemento = f"Engenharia Exemplo NF. {nf or numero} - {produto}  DT 01/10/2026 O.C. 801894"
    classificacao = {FILTRO: "3.01.02.07.0001", OLEO: "3.01.02.06.0001"}[conta]
    debito, credito = ("C", "D") if invertido else ("D", "C")
    return Fato("mov.csv", numero, "01/10/2026", [
        _l(debito, conta, classificacao, "10.00", complemento),
        _l(credito, FORNECEDOR, "2.01.01.01.4577", "10.00", complemento)], com_centro_custo=True)


def _gravar_csv(caminho, fatos):
    titulos = ["Lançamento", "Sequência", "Fato contábil", "Data", "Valor", "Conta débito",
               "Conta crédito", "Centro custo", "Complemento", "Conta contábil", "Centro de custo",
               "Classificação da conta"]
    linhas = [";".join(titulos)]
    for f in fatos:
        for l in f.lancamentos:
            linhas.append(";".join([
                "1", l.sequencia, f.fato, f.data_movimento, str(l.valor).replace(".", ","),
                l.conta_debito or "0", l.conta_credito or "0", l.centro_custo or "0",
                l.complemento, l.nome_conta, "", l.classificacao]))
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-16")
    return caminho


def test_produto_do_complemento():
    assert gabarito.produto_do_complemento(
        "Engenharia Exemplo & Geradores Ltda NF. 935 - Filtro de Agua  DT 01/10/2026 PR MATERIAIS"
    ) == "FILTRO DE AGUA"
    assert gabarito.produto_do_complemento(
        "Softhouse Exemplo Ltda NF. 2511 - Licenca Software PACS DT 01/09/2026 O.C0 ") == \
        "LICENCA SOFTWARE PACS"
    assert gabarito.produto_do_complemento("Cirurgica Exemplo NF. 6403 DT28/08/2026 O.C 803080") == ""


def test_ensinar_nao_aprende_estorno_e_arquivo_ruim_nao_derruba(tmp_path):
    arquivo = _gravar_csv(tmp_path / "mov.csv", [
        _compra("1"), _compra("2"), _compra("3", invertido=True, nf="2"), _compra("4", conta=OLEO,
                                                                         produto="Oleo")])
    ruim = tmp_path / "ruim.csv"
    ruim.write_text("isto não é um movimento", encoding="utf-8")
    ensino = gabarito.ensinar(tmp_path / "gabarito", [arquivo, ruim])
    assert [f.arquivo for f in ensino.falhas] == ["ruim.csv"]
    assert ensino.fatos_novos == 2                     # o 3 estorna o 2: os dois ficam de fora
    memoria = gabarito.abrir_gabarito(tmp_path / "gabarito")
    assert {(p, c): i.vezes for (_, p, c), i in memoria.historico.items()} == {
        ("FILTRO DE AGUA", FILTRO): 1, ("OLEO", OLEO): 1}


def test_conferir_padrao_vale_mais_que_o_historico(tmp_path):
    pasta = tmp_path / "gabarito"
    gabarito.ensinar(pasta, [_gravar_csv(tmp_path / "mov.csv", [_compra("1"), _compra("2")])])
    # a chefia decide no Excel: filtro deste fornecedor vai em óleo (só para o teste)
    livro = openpyxl.load_workbook(gabarito.caminho_gabarito(pasta))
    padrao = livro[cfg.GABARITO_ABA_PADRAO]
    padrao.append([FORNECEDOR, "Engenharia Exemplo", "filtro de água", OLEO, "3.01.02.06.0001 Combustíveis",
                   "Chefe", "20/10/2026", ""])
    padrao.protection.set_password("chefe")
    padrao.protection.sheet = True
    livro.save(gabarito.caminho_gabarito(pasta))
    memoria = gabarito.abrir_gabarito(pasta)
    resultados = conferir([_compra("10"), _compra("11", conta=OLEO),
                           _compra("12", conta=OLEO, produto="Oleo")], [], [])
    gabarito.conferir_contas(resultados, memoria)
    assert [r.contas[0].resultado for r in resultados] == [
        cfg.GABARITO_FORA_PADRAO, cfg.GABARITO_IGUAL_PADRAO, cfg.GABARITO_PRODUTO_NOVO]
    assert "Padrão: 3.01.02.06.0001 Combustíveis (decidido por Chefe)" == \
        resultados[0].contas[0].detalhe
    assert "o fornecedor nunca usou" in resultados[2].contas[0].detalhe

    # ensinar de novo não mexe na aba Padrão nem na senha dela
    gabarito.ensinar(pasta, [_gravar_csv(tmp_path / "mov2.csv", [_compra("20")])])
    livro = openpyxl.load_workbook(gabarito.caminho_gabarito(pasta))
    assert livro[cfg.GABARITO_ABA_PADRAO].protection.sheet
    assert [l[3] for l in livro[cfg.GABARITO_ABA_PADRAO].iter_rows(min_row=2, values_only=True)] \
        == [OLEO]
    assert len(list((pasta / cfg.GABARITO_PASTA_COPIAS).glob("*.xlsx"))) == 1   # antes de gravar


def test_conferir_diferente_do_habitual_e_fornecedor_novo(tmp_path):
    pasta = tmp_path / "gabarito"
    gabarito.ensinar(pasta, [_gravar_csv(tmp_path / "mov.csv", [_compra("1"), _compra("2")])])
    memoria = gabarito.abrir_gabarito(pasta)
    outro = _compra("30")
    outro.lancamentos[1].conta_credito = "9999"                    # outro fornecedor
    resultados = conferir([_compra("10"), _compra("11", conta=OLEO), outro], [], [])
    situacoes = [r.situacao for r in resultados]
    gabarito.conferir_contas(resultados, memoria)
    assert [r.contas[0].resultado for r in resultados] == [
        cfg.GABARITO_IGUAL_HISTORICO, cfg.GABARITO_DIFERENTE, cfg.GABARITO_FORNECEDOR_NOVO]
    assert resultados[0].contas[0].detalhe == "2 de 2 vezes nesta conta"
    assert [r.situacao for r in resultados] == situacoes             # só aviso: a cor não muda


def test_copia_de_seguranca_no_mesmo_segundo_nao_substitui_a_outra(tmp_path):
    from datetime import datetime
    agora = datetime(2026, 10, 20, 9, 0, 0)
    arquivo = _gravar_csv(tmp_path / "mov.csv", [_compra("1")])
    for _ in range(3):
        gabarito.ensinar(tmp_path / "g", [arquivo], agora=agora)
    assert len(list((tmp_path / "g" / cfg.GABARITO_PASTA_COPIAS).glob("*.xlsx"))) == 2


def test_planilha_com_senha_para_abrir_ou_estragada_vira_erro(tmp_path):
    caminho = gabarito.caminho_gabarito(tmp_path)
    caminho.write_bytes(b"nao e uma planilha")
    with pytest.raises(gabarito.ErroLeitura, match="Proteger Planilha"):
        gabarito.abrir_gabarito(tmp_path)
    assert gabarito.ensinar(tmp_path, []).erro


def test_relatorio_com_e_sem_gabarito(tmp_path):
    pasta = tmp_path / "gabarito"
    gabarito.ensinar(pasta, [_gravar_csv(tmp_path / "mov.csv", [_compra("1")])])
    resultados = conferir([_compra("10"), _compra("11", conta=OLEO)], [], [])
    gabarito.conferir_contas(resultados, gabarito.abrir_gabarito(pasta))
    caminho = gerar_relatorio(tmp_path / "r.xlsx", resultados, [], [], [], [], ["mov.csv"],
                              gabarito=str(pasta))
    livro = openpyxl.load_workbook(caminho)
    (linha,) = livro[cfg.ABA_CONTAS].iter_rows(min_row=2, values_only=True)
    assert (linha[0], linha[1], linha[6]) == (cfg.GABARITO_DIFERENTE, "11", "FILTRO DE AGUA")
    lancamentos = {(l[1], l[4]): l[13] for l in livro["Lançamentos"].iter_rows(min_row=2,
                                                                               values_only=True)}
    assert lancamentos[("10", FILTRO)] == cfg.GABARITO_IGUAL_HISTORICO
    assert lancamentos[("11", OLEO)].startswith(cfg.GABARITO_DIFERENTE + ": Habitual:")
    resumo = {l[0]: l[1] for l in livro["Resumo"].iter_rows(values_only=True)}
    assert resumo["Gabarito de contas (só aviso)"].startswith(
        "1 iguais; 0 fora do padrão; 1 diferentes do habitual; 0 sem histórico")
    sem = gerar_relatorio(tmp_path / "s.xlsx", conferir([_compra("10")], [], []), [], [], [], [],
                          ["mov.csv"])
    resumo = {l[0]: l[1] for l in openpyxl.load_workbook(sem)["Resumo"].iter_rows(values_only=True)}
    assert resumo["Gabarito de contas (só aviso)"].startswith("NÃO CONFERIDO")


def test_processar_com_gabarito_vazio_avisa_e_confere_o_resto(tmp_path):
    lote = _gravar_csv(tmp_path / "mov.csv", [_compra("10")])
    (tmp_path / "pdfs").mkdir()
    resultado = processamento.processar(lote, tmp_path / "pdfs", tmp_path / "saida",
                                         pasta_gabarito=tmp_path / "gabarito_vazio")
    assert "ainda está vazio" in resultado.erro_gabarito
    assert resultado.caminho_relatorio.exists()
    textos = [l.texto for l in processamento.resumir(resultado).conferencias]
    assert any(t.startswith("Gabarito de contas:") for t in textos)


# ---------------------------------------------------------------------------
# Tela
# ---------------------------------------------------------------------------

@pytest.fixture
def tela(criar_painel, monkeypatch):
    painel = criar_painel(MODULO).gabarito
    painel.abertos = []
    monkeypatch.setattr(painel, "abrir", painel.abertos.append)
    return painel


def test_tela_ensinar_e_lembrar_a_pasta(tela, tmp_path):
    assert tela.botao.cget("text") == "Ensinar" and tela.botao.cget("state") == "disabled"
    arquivo = _gravar_csv(tmp_path / "mov.csv", [_compra("1"), _compra("2")])
    tela.cartao_gabarito.definir_caminhos([tmp_path / "gabarito"])
    tela.cartao_movimentos.definir_caminhos([arquivo])
    esperar(tela, lambda: tela.cartao_movimentos.status_confirmacao is not None)
    assert tela.cartao_movimentos.texto_confirmacao == "1 arquivo(s), 2 fatos contábeis"
    assert tela.botao.cget("state") == "normal"
    tela.processar()
    esperar(tela, lambda: tela.ultimo_resultado is not None)
    assert tela.ultimo_resultado.fatos_novos == 2
    assert gabarito.caminho_gabarito(tmp_path / "gabarito").exists()
    assert processamento.ler_pastas_usadas()["gabarito"] == tmp_path / "gabarito"
    tela.botoes_resultado = None
    tela.novo()
    assert tela.cartao_gabarito.caminho == tmp_path / "gabarito"    # continua escolhida
    assert tela.cartao_movimentos.caminho is None
