"""T8 — exportação "Movimento contábil" (com centro de custo), S11 e rateios (S12).

- O "Movimento contábil" do lote 72887 tem os mesmos lançamentos do lote antigo e dá a mesma
  conferência; o do AME Vale Zeta tem um rateio (INMETRO, 8 centros de custo).
- Centro de custo faltando e rateio errado com dados fictícios montados no teste.
Os testes com arquivos reais usam exemplos\\conferencia_nf\\ (fora do git) e são pulados sem ela.
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal

import openpyxl
import pytest

from modulos.conferencia_nf import leitor_pdfs
from modulos.conferencia_nf.conferencia import conferir, lancamentos_sem_centro_custo, rateios
from modulos.conferencia_nf.leitor_lote import ler_lote
from modulos.conferencia_nf.modelos import ErroLeitura, Fato, Lancamento, Situacao
from modulos.conferencia_nf.relatorio import gerar_relatorio
from testes.conferencia_nf.conftest import ler_pdfs_do_lote
from testes.conferencia_nf.test_conferencia import _como_gabarito, _gabarito, _nota
from testes.conftest import pasta_exemplos

COMPLEMENTO = "Cirurgica Exemplo Comercio de Produtos Medicos Ltda NF. 1851605 DT25/09/2026 O.C 811215"


def _movimento(nome: str):
    return pasta_exemplos("conferencia_nf", "movimento_contabil") / nome


def _por_fato(fatos: list[Fato]) -> dict[str, Counter]:
    return {f.fato: Counter((l.conta_debito, l.conta_credito, l.valor, l.complemento,
                             l.classificacao) for l in f.lancamentos) for f in fatos}


# ---------------------------------------------------------------------------
# Arquivos reais
# ---------------------------------------------------------------------------

def test_t8_movimento_contabil_tem_os_mesmos_lancamentos_do_lote():
    lote = pasta_exemplos("conferencia_nf", "lote_72887")
    antigo = ler_lote(next(lote.glob("Movimento*.csv")))
    novo = ler_lote(_movimento("lote_72887_movimento_contabil.csv"))
    assert [f.fato for f in novo] == [f.fato for f in antigo]
    assert _por_fato(novo) == _por_fato(antigo)
    assert all(f.com_centro_custo for f in novo) and not any(f.com_centro_custo for f in antigo)
    com_cc = [l for f in novo for l in f.lancamentos if l.centro_custo]
    assert len(com_cc) == 25 and all(l.classificacao.startswith("3") for l in com_cc)
    lancamento = next(l for f in novo for l in f.lancamentos if f.fato == "6598289")
    assert (lancamento.centro_custo, lancamento.nome_centro_custo) == (
        "366", "Áreas Comuns - Hospital do Coração")
    assert not any(lancamentos_sem_centro_custo(f) or rateios(f) for f in novo)


def test_t8_conferencia_com_o_movimento_contabil_igual_ao_gabarito():
    lote = pasta_exemplos("conferencia_nf", "lote_72887")
    notas, _, _ = ler_pdfs_do_lote("lote_72887")
    fatos = ler_lote(_movimento("lote_72887_movimento_contabil.csv"))
    resultados = conferir(fatos, notas, leitor_pdfs.ler_sem_pdf(lote))
    gabarito = _gabarito(lote)
    for r in resultados:
        esperado = dict(gabarito[r.fato.fato], arquivo_lote=r.fato.arquivo)
        assert dict(_como_gabarito(r), arquivo_lote=r.fato.arquivo) == esperado, r.fato.fato
    assert Counter(r.situacao.value for r in resultados) == {
        "OK": 40, "ESTORNO": 4, "CONFERIR": 2, "SEM PDF": 4, "SEM Nº DE NOTA": 5}


def test_t8_rateio_do_ame():
    fatos = {f.fato: f for f in ler_lote(_movimento("ame_zeta_rateio.csv"))}
    assert set(fatos) == {"6681142", "6681365", "6679925"}
    inmetro = rateios(fatos["6681142"])
    assert list(inmetro) == [("D", "30039")]
    (lancamentos,) = inmetro.values()
    assert len(lancamentos) == 8 and len({l.centro_custo for l in lancamentos}) == 7
    assert sum(l.valor for l in lancamentos) == Decimal("3247.60") == fatos["6681142"].total_credito
    assert not rateios(fatos["6681365"]) and not rateios(fatos["6679925"])
    assert not any(lancamentos_sem_centro_custo(f) for f in fatos.values())


def test_t8_aba_rateios_e_centro_de_custo_nos_lancamentos(tmp_path):
    fatos = ler_lote(_movimento("ame_zeta_rateio.csv"))
    resultados = conferir(fatos, [], [])
    caminho = gerar_relatorio(tmp_path / "r.xlsx", resultados, [], [], [], [], ["ame.csv"])
    livro = openpyxl.load_workbook(caminho)
    linhas = list(livro["Rateios"].iter_rows(min_row=2, values_only=True))
    assert len(linhas) == 8 and {l[0] for l in linhas} == {"6681142"}
    enfermagem = [l for l in linhas if l[8] == "9085 - Serviços de enfermagem"]
    assert [l[9] for l in enfermagem] == [2060.74, 156.54]
    assert {l[11] for l in linhas} == {3247.6}
    assert round(sum(l[10] for l in linhas), 6) == 1
    assert {l[12] for l in linhas} == {"Partidas OK (sem PDF)"}
    centros = {(l[1], l[4]): l[9] for l in livro["Lançamentos"].iter_rows(min_row=2,
                                                                          values_only=True)}
    assert centros[("6681365", "10")] == "9093 - Central de Esterilização de Materiais"
    assert centros[("6679925", "14")] is None                    # estoque: sem centro de custo
    resumo = {l[0]: l[1] for l in livro["Resumo"].iter_rows(values_only=True)}
    assert resumo["Centro de custo nas contas de resultado (3 e 4)"] == \
        "Conferido: todos com centro de custo"
    assert resumo["Fatos com rateio de centro de custo (aba Rateios)"] == 1


def test_t8_lote_antigo_avisa_que_o_centro_de_custo_nao_foi_conferido(tmp_path):
    lote = pasta_exemplos("conferencia_nf", "lote_72887")
    resultados = conferir(ler_lote(next(lote.glob("Movimento*.csv"))), [], [])
    caminho = gerar_relatorio(tmp_path / "r.xlsx", resultados, [], [], [], [], ["lote.csv"])
    resumo = {l[0]: l[1] for l in openpyxl.load_workbook(caminho)["Resumo"].iter_rows(
        values_only=True)}
    assert resumo["Centro de custo nas contas de resultado (3 e 4)"].startswith("NÃO CONFERIDO")


# ---------------------------------------------------------------------------
# Dados fictícios
# ---------------------------------------------------------------------------

def _l(seq, lado, conta, classificacao, valor, cc="", nome_cc="") -> Lancamento:
    return Lancamento(sequencia=seq, conta_debito=conta if lado == "D" else "",
                      conta_credito=conta if lado == "C" else "", nome_conta=f"Conta {conta}",
                      classificacao=classificacao, valor=Decimal(valor), complemento=COMPLEMENTO,
                      centro_custo=cc, nome_centro_custo=nome_cc)


def _fato(*lancamentos, numero="900", com_cc=True) -> Fato:
    return Fato("mov.csv", numero, "01/10/2026", list(lancamentos), com_centro_custo=com_cc)


def _despesa(cc_despesa="70", com_cc=True) -> Fato:
    return _fato(_l("1", "D", "30080", "3.01.02.07.0001", "29.80", cc_despesa, "Centro Cirúrgico"),
                 _l("2", "C", "201777", "2.01.01.01.1842", "29.80"), com_cc=com_cc)


def test_s11_conta_de_resultado_sem_centro_de_custo_fica_divergente():
    (ok,) = conferir([_despesa()], [_nota()])
    assert ok.situacao == Situacao.OK
    (sem,) = conferir([_despesa(cc_despesa="")], [_nota()])
    assert sem.situacao == Situacao.DIVERGENTE
    assert [l.sequencia for l in sem.sem_centro_custo] == ["1"]
    assert "Conta de resultado sem centro de custo: sequência 1, 3.01.02.07.0001" in \
        " ".join(sem.observacoes)


def test_s11_vale_sem_pdf_e_para_receita_mas_nao_para_estorno_nem_lote_antigo():
    (sem_pdf,) = conferir([_despesa(cc_despesa="")], [])
    assert sem_pdf.situacao == Situacao.DIVERGENTE                 # com ou sem PDF
    receita = _fato(_l("1", "D", "10010", "1.01.01.01.0001", "50.00"),
                    _l("2", "C", "40001", "4.01.01.01.0001", "50.00"))
    (r_receita,) = conferir([receita], [])
    assert r_receita.situacao == Situacao.DIVERGENTE               # conta 4 a crédito
    lote_antigo = _despesa(cc_despesa="", com_cc=False)
    (antigo,) = conferir([lote_antigo], [_nota()])
    assert antigo.situacao == Situacao.OK and antigo.sem_centro_custo == []
    lancamento = _despesa(cc_despesa="")
    estorno = _fato(_l("1", "C", "30080", "3.01.02.07.0001", "29.80"),
                    _l("2", "D", "201777", "2.01.01.01.1842", "29.80"), numero="901")
    assert {r.situacao for r in conferir([lancamento, estorno], [])} == {Situacao.ESTORNO}


def test_s11_motivo_e_destaque_no_relatorio(tmp_path):
    resultados = conferir([_despesa(cc_despesa="")], [_nota()])
    caminho = gerar_relatorio(tmp_path / "r.xlsx", resultados, [_nota()], [], [], [], ["mov.csv"])
    livro = openpyxl.load_workbook(caminho)
    (a_mao,) = livro["Conferir à mão"].iter_rows(min_row=2, values_only=True)
    assert a_mao[0] == "Conta de resultado sem centro de custo"
    aba = livro["Lançamentos"]
    assert aba["J2"].value == "CONTA DE RESULTADO SEM CENTRO DE CUSTO"
    assert aba["J2"].fill.fgColor.rgb.endswith("FFC7CE")
    resumo = {l[0]: l[1] for l in livro["Resumo"].iter_rows(values_only=True)}
    assert resumo["Centro de custo nas contas de resultado (3 e 4)"] == \
        "1 lançamento(s) SEM centro de custo, em 1 fato(s): DIVERGENTE"


def test_s12_rateio_que_nao_bate_com_a_nota_fica_divergente(tmp_path):
    rateado = _fato(_l("1", "D", "30080", "3.01.02.07.0001", "20.00", "70", "Centro Cirúrgico"),
                    _l("2", "D", "30080", "3.01.02.07.0001", "10.00", "57", "U.I. Maternidade"),
                    _l("3", "C", "201777", "2.01.01.01.1842", "30.00"))
    (r,) = conferir([rateado], [_nota()])                # nota de 29,80; rateio soma 30,00
    assert r.situacao == Situacao.DIVERGENTE
    caminho = gerar_relatorio(tmp_path / "r.xlsx", [r], [_nota()], [], [], [], ["mov.csv"])
    linhas = list(openpyxl.load_workbook(caminho)["Rateios"].iter_rows(min_row=2,
                                                                       values_only=True))
    assert [(l[9], round(l[10], 4), l[11]) for l in linhas] == [(20, 0.6667, 30), (10, 0.3333, 30)]
    assert {l[12] for l in linhas} == {"NÃO: ver as observações do fato"}
    (ok,) = conferir([_fato(_l("1", "D", "30080", "3.01.02.07.0001", "19.80", "70"),
                            _l("2", "D", "30080", "3.01.02.07.0001", "10.00", "57"),
                            _l("3", "C", "201777", "2.01.01.01.1842", "29.80"))], [_nota()])
    assert ok.situacao == Situacao.OK and rateios(ok.fato)       # rateio é só informativo


def test_movimento_contabil_com_as_duas_contas_na_linha_e_erro(tmp_path):
    titulos = ["Lançamento", "Sequência", "Fato contábil", "Data", "Valor", "Conta débito",
               "Conta crédito", "Centro custo", "Complemento", "Conta contábil", "Centro de custo",
               "Classificação da conta"]
    linha = ["1", "1", "900", "01/10/2026", "10,00", "30080", "201777", "0", COMPLEMENTO,
             "Conta", "", "3.01.02.07.0001"]
    arquivo = tmp_path / "mov.csv"
    arquivo.write_text(";".join(titulos) + "\n" + ";".join(linha) + "\n", encoding="utf-16")
    with pytest.raises(ErroLeitura, match="conta débito OU a conta crédito"):
        ler_lote(arquivo)


# ---------------------------------------------------------------------------
# S18 — centro de custo 539 - CMD: trocar pela conta do ativo (pedido do usuário, 28/10/2026)
# ---------------------------------------------------------------------------

def _despesa_cmd() -> Fato:
    return _fato(_l("1", "D", "30080", "3.01.02.07.0001", "29.80", "539", "Centro Multidisciplinar - Rateios"),
                 _l("2", "C", "201777", "2.01.01.01.1842", "29.80"))


def test_s18_centro_de_custo_539_avisa_para_trocar_pela_conta_do_ativo():
    (r,) = conferir([_despesa_cmd()], [_nota()])
    assert r.situacao == Situacao.CONFERIR                  # o fato que estaria OK fica laranja
    assert [l.sequencia for l in r.centro_custo_cmd] == ["1"]
    assert "Centro de custo 539 - CMD: trocar pela conta do ativo: sequência 1" in " ".join(r.observacoes)
    (sem_pdf,) = conferir([_despesa_cmd()], [])
    assert sem_pdf.situacao == Situacao.SEM_PDF and sem_pdf.centro_custo_cmd   # situação pior não muda
    (ok,) = conferir([_despesa()], [_nota()])
    assert ok.situacao == Situacao.OK and ok.centro_custo_cmd == []


def test_s18_motivo_e_destaque_no_relatorio(tmp_path):
    resultados = conferir([_despesa_cmd()], [_nota()])
    caminho = gerar_relatorio(tmp_path / "r.xlsx", resultados, [_nota()], [], [], [], ["mov.csv"])
    livro = openpyxl.load_workbook(caminho)
    (a_mao,) = livro["Conferir à mão"].iter_rows(min_row=2, values_only=True)
    assert a_mao[0] == "Centro de custo 539 - CMD: trocar pela conta do ativo"
    assert livro["Lançamentos"]["J2"].value == "539 - Centro Multidisciplinar - Rateios: TROCAR PELA CONTA DO ATIVO"
    resumo = {l[0]: l[1] for l in livro["Resumo"].iter_rows(values_only=True)}
    assert resumo["      centro de custo 539 - CMD: trocar pela conta do ativo"] == 1


# ---------------------------------------------------------------------------
# S19 — software, uniforme e enxoval acima de R$ 1.000,00: verificar a diluição (pedido do usuário, 28/10/2026)
# ---------------------------------------------------------------------------

def _conta_nome(fato: Fato, nome: str) -> Fato:
    fato.lancamentos[0].nome_conta = nome
    return fato


def _fato_valor(valor: str, nome: str, classificacao="3.01.02.08.0015") -> Fato:
    return _conta_nome(_fato(_l("1", "D", "30183", classificacao, valor, "70", "Centro Cirúrgico"),
                             _l("2", "C", "201777", "2.01.01.01.1842", valor)), nome)


def test_s19_software_uniforme_enxoval_acima_de_1000_avisa():
    for nome in ("Locação e manutenção de softwares licenciados", "Uniformes e similares", "Enxoval"):
        (r,) = conferir([_fato_valor("1000.01", nome)], [])
        assert r.diluicao and "Verificar se é possível a diluição do custo ou despesa" in " ".join(r.observacoes)
    (igual,) = conferir([_fato_valor("1000.00", "Uniformes e similares")], [])
    assert igual.diluicao == []                                          # "maior que" 1.000,00
    (outra,) = conferir([_fato_valor("5000.00", "Telefones")], [])
    assert outra.diluicao == []
    (ativo,) = conferir([_fato_valor("5000.00", "Software (intangível)", "1.02.03.01.0001")], [])
    assert ativo.diluicao == []                                          # só despesa e receita (3 e 4)


def test_s19_soma_do_rateio_e_situacao():
    rateado = _fato(_l("1", "D", "30183", "3.01.02.08.0015", "600.00", "70"),
                    _l("2", "D", "30183", "3.01.02.08.0015", "600.00", "57"),
                    _l("3", "C", "201777", "2.01.01.01.1842", "1200.00"))
    for l in rateado.lancamentos[:2]:
        l.nome_conta = "Locação e manutenção de softwares licenciados"
    (r,) = conferir([rateado], [])
    assert len(r.diluicao) == 2 and "R$ 1.200,00" in " ".join(r.observacoes)
    assert r.situacao == Situacao.SEM_PDF                                # situação pior não muda
    (ok,) = conferir([_conta_nome(_despesa(), "Uniformes e similares")], [_nota()])
    assert ok.situacao == Situacao.OK                                    # 29,80: abaixo do limite


# ---------------------------------------------------------------------------
# S20 — Fornecedores a reclassificar (pedido do usuário, 06/11/2026)
# ---------------------------------------------------------------------------

def _com_reclassificar(lado: str) -> Fato:
    fato = _despesa()
    l = next(l for l in fato.lancamentos if (l.conta_debito if lado == "D" else l.conta_credito))
    l.nome_conta = "FORNECEDORES A  RECLASSIFICAR"           # nome com maiúscula e espaço a mais
    return fato


def test_s20_fornecedores_a_reclassificar_no_credito_e_no_debito():
    (credito,) = conferir([_com_reclassificar("C")], [_nota()])
    assert credito.situacao == Situacao.CONFERIR and [l.sequencia for l in credito.reclassificar] == ["2"]
    texto = " ".join(credito.observacoes)
    assert "no crédito: conferir se precisa trocar para a conta do próprio fornecedor: sequência 2" in texto
    assert "débito" not in texto
    (debito,) = conferir([_com_reclassificar("D")], [_nota()])
    assert debito.situacao == Situacao.CONFERIR
    assert "Fornecedores a reclassificar no débito: conferir se foi provisionada: sequência 1" in " ".join(
        debito.observacoes)
    (sem_pdf,) = conferir([_com_reclassificar("C")], [])
    assert sem_pdf.situacao == Situacao.SEM_PDF and sem_pdf.reclassificar     # situação pior não muda
    (ok,) = conferir([_despesa()], [_nota()])
    assert ok.situacao == Situacao.OK and ok.reclassificar == []


def test_s20_motivo_e_resumo_no_relatorio(tmp_path):
    resultados = conferir([_com_reclassificar("C")], [_nota()])
    caminho = gerar_relatorio(tmp_path / "r.xlsx", resultados, [_nota()], [], [], [], ["mov.csv"])
    livro = openpyxl.load_workbook(caminho)
    (a_mao,) = livro["Conferir à mão"].iter_rows(min_row=2, values_only=True)
    assert a_mao[0] == ("Fornecedores a reclassificar no crédito: conferir se precisa trocar para a conta "
                        "do próprio fornecedor")
    resumo = {l[0]: l[1] for l in livro["Resumo"].iter_rows(values_only=True)}
    assert resumo["Fornecedores a reclassificar: no crédito, trocar pela conta do fornecedor?; no débito, "
                  "foi provisionada?"] == 1


# ---------------------------------------------------------------------------
# S19 e S20 na aba Lançamentos (pedido do usuário, 18/11/2026): o lançamento do aviso em destaque
# ---------------------------------------------------------------------------

def _linhas_lancamentos(tmp_path, fato, notas):
    resultados = conferir([fato], notas)
    caminho = gerar_relatorio(tmp_path / "r.xlsx", resultados, notas, [], [], [], ["mov.csv"])
    aba = openpyxl.load_workbook(caminho)["Lançamentos"]
    return [(aba.cell(row=n, column=9).value, aba.cell(row=n, column=9))
            for n in range(2, aba.max_row + 1)]


def test_s19_lancamento_da_diluicao_marcado_na_aba_lancamentos(tmp_path):
    (debito, credito) = _linhas_lancamentos(
        tmp_path, _fato_valor("2827.35", "Locação e manutenção de softwares licenciados"), [])
    assert debito[0] == "Locação e manutenção de softwares licenciados: VERIFICAR A DILUIÇÃO"
    assert debito[1].font.bold and debito[1].fill.fgColor.rgb.endswith("FFD966")
    assert ": " not in (credito[0] or "") and not credito[1].font.bold       # só o lançamento do aviso
    (abaixo, _) = _linhas_lancamentos(tmp_path, _fato_valor("1000.00", "Uniformes e similares"), [])
    assert abaixo[0] == "Uniformes e similares"                              # sem aviso, sem marca


def test_s20_lancamento_a_reclassificar_marcado_na_aba_lancamentos(tmp_path):
    linhas = _linhas_lancamentos(tmp_path, _com_reclassificar("C"), [_nota()])
    marcadas = [texto for texto, celula in linhas if celula.font.bold]
    assert marcadas == ["FORNECEDORES A  RECLASSIFICAR: TROCAR PELA CONTA DO FORNECEDOR?"]
    linhas = _linhas_lancamentos(tmp_path, _com_reclassificar("D"), [_nota()])
    assert [texto for texto, celula in linhas if celula.font.bold] == [
        "FORNECEDORES A  RECLASSIFICAR: FOI PROVISIONADA?"]
