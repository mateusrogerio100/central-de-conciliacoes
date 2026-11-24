"""
Testes da Conciliação Fornecedores (ESPECIFICACAO seção 16).

Os arquivos sintéticos imitam o Tasy: .xls que na verdade é texto separado por tabulação
(Windows-1252), balancete com valores uma coluna à direita do cabeçalho e quebra de página, e o
relatório analítico de títulos a pagar (uma linha por título). Nomes inventados. O gabarito com
os arquivos reais é pulado se exemplos/ não existir.
"""

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook

from modulos.conciliacao_fornecedores.processar import conferir_par, numeros_principais, previa_balancete, previa_titulos, processar_fornecedores
from modulos.conciliacao_fornecedores.leitores import ERRO_SINTETICO, ler_balancete, ler_titulos
from modulos.conciliacao_fornecedores.modelos import (
    PAREAMENTO_VALOR,
    SITUACAO_DIVERGENTE,
    SITUACAO_OK,
    SITUACAO_SO_BALANCETE,
    SITUACAO_SO_RELATORIO,
    ContaFornecedor,
    FornecedorFinanceiro,
    LeituraTitulos,
    ResultadoFornecedores,
)
from modulos.conciliacao_fornecedores.pareamento import nota_semelhanca, parear
from modulos.conciliacao_fornecedores.processar import _notas, unidade_para_arquivo
from modulos.conciliacao_fornecedores.relatorio_excel import ABA_COMPLETA, ABA_RESUMO, ABA_TITULOS

from testes.conftest import PASTA_EXEMPLOS

PASTA_FORNECEDORES = PASTA_EXEMPLOS / "conciliacao_fornecedores" / "Exemplos_Fornecedores"

D = Decimal
UNIDADE = "AME - Cidade Teste (Fund. Hospital Exemplo)"
OBSERVACAO_SECRETA = "Obs. NF: texto sigiloso de teste"


def _texto_celula(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    if isinstance(valor, (datetime, date)):
        return f"{valor:%d/%m/%Y}"
    return str(valor)


def texto_tasy(pasta: Path, nome: str, linhas: list[list]) -> Path:
    """Como o Tasy salva: .xls que é texto separado por tabulação, em Windows-1252."""
    caminho = pasta / nome
    caminho.write_bytes("\r\n".join("\t".join(_texto_celula(c) for c in linha) for linha in linhas)
                        .encode("cp1252"))
    return caminho


def planilha(pasta: Path, nome: str, linhas: list[list]) -> Path:
    """O mesmo conteúdo salvo como .xlsx (quem abriu e salvou no Excel)."""
    livro = Workbook()
    aba = livro.active
    for linha in linhas:
        aba.append(linha)
    caminho = pasta / nome
    livro.save(caminho)
    return caminho


# ---------------------------------------------------------------------
# Arquivos sintéticos
# ---------------------------------------------------------------------
def _topo_balancete(unidade, mes):
    return [
        [unidade],
        ["Balancete"],
        [None] * 6 + ["Mês Referência:", None, None, mes],
        [None, "Código", None, "Classificação", None, "Descrição", None, None, "Saldo Anterior", None,
         "Débitos", None, "Créditos", "Saldo Atual"],
        [None, "Passivo"],
    ]


def _conta(codigo, classificacao, descricao, saldo):
    return [None, None, str(codigo), None, classificacao, "      " + descricao, None, None, 0, None, 0, None,
            saldo, saldo]


def linhas_balancete(contas, total=None, unidade=UNIDADE, mes="set/2026", quebra_depois=None):
    """contas: (codigo, descricao, saldo). Total = soma, se não informado."""
    total = sum(c[2] for c in contas) if total is None else total
    linhas = _topo_balancete(unidade, mes)
    linhas.append(_conta(2111, "2.01.01.01", "FORNECEDORES NO PAÍS", total))
    linhas.append(_conta(11111, "1.01.01", "Outra conta qualquer", 999))      # deve ser ignorada
    for posicao, (codigo, descricao, saldo) in enumerate(contas, start=1):
        linhas.append(_conta(codigo, f"2.01.01.01.{posicao:04d}", descricao, saldo))
        if quebra_depois == posicao:
            linhas.append([None, "Impresso em: 06/10/2026", None, None, None, None, None, "Página: 1"])
            linhas += _topo_balancete(unidade, mes)
    linhas.append([None, "Impresso em: 06/10/2026", None, None, None, None, None, "Página: 2", None,
                   None, None, "USUARIO", None, None, "WEXE001"])
    return linhas


def arquivo_balancete(pasta, contas, nome="balancete.xls", **opcoes):
    return texto_tasy(pasta, nome, linhas_balancete(contas, **opcoes))


CABECALHO_ANALITICO = ["Pessoa Física/Jurídica", "Nr. Doc.", "Nr. Título", "TIpo Título", "Sit.", "Dt. Emissão",
                       "Dt. Vencto. Atu.", "Dt. Vencto. Ori.", "Dt. Liquid.", "Vl. Juros", "Vl. Multa", "Vl. Saldo",
                       "Observação", "Vl classif", "Vl título", "Vl pago", "Cheque", "Estabelecimento", "CNPJ",
                       "Valor NF", "Ordem Compra", "Vl baixa", "Trans fin baixa", "Classificação"]


def linhas_titulos(titulos, unidade=UNIDADE):
    """titulos: (fornecedor, nr_doc, nr_titulo, saldo[, cnpj])."""
    linhas = [CABECALHO_ANALITICO]
    for fornecedor_, documento, numero, saldo, *cnpj in titulos:
        linhas.append([fornecedor_, documento, numero, "Nota Fiscal", "A", datetime(2026, 9, 24),
                       datetime(2026, 10, 15), datetime(2026, 10, 15), "                         ", 0, 0, saldo,
                       OBSERVACAO_SECRETA, 0, saldo, 0, 0, unidade, (cnpj or ["00.000.000/0001-00"])[0], saldo, 1, 0,
                       "                         ", "                         "])
    return linhas


def arquivo_titulos(pasta, titulos, nome="titulos_pagar.xls", **opcoes):
    return texto_tasy(pasta, nome, linhas_titulos(titulos, **opcoes))


CONTAS = [
    (30001, "Alfa Distribuidora Ltda", 100.0),
    (30002, "Beta Comércio de Materiais Hospitalares Ltda ME", 250.5),
    (30003, "Gama Serviços", 80.0),
]
TITULOS = [
    ("Alfa Distribuidora Ltda - EPP", "5001", "900001", 60.0),
    ("Alfa Distribuidora Ltda - EPP", "5002", "900002", 40.0),
    ("Beta Comercio de Materiais Hospitalares Ltda", "7001", "900003", 150.5),
    ("BETA COMERCIO DE MATERIAIS HOSPITALARES LTDA", "7002", "900004", 50.0),   # mesmo nome, outra caixa
    ("Gama Servicos Ltda", "", "900005", 80.0),                                  # boleto sem Nr. Doc.
    ("Zeta Transportes", "", "900006", 12.0),
    ("Omega Banco Teste SA", "", "900007", 0.0),                                 # saldo zero: ignorado
]


# ---------------------------------------------------------------------
# Leitores
# ---------------------------------------------------------------------
def test_balancete_xls_texto_le_2111_ignora_outras_contas_e_quebra_de_pagina(tmp_path):
    leitura = ler_balancete(arquivo_balancete(tmp_path, CONTAS, quebra_depois=1))
    assert leitura.erro is None
    assert leitura.unidade == UNIDADE
    assert leitura.mes == date(2026, 9, 1)
    assert leitura.total.saldo_atual == D("430.50")
    assert [(c.codigo, c.descricao, c.saldo_atual) for c in leitura.contas] == [
        ("30001", "Alfa Distribuidora Ltda", D("100.00")),
        ("30002", "Beta Comércio de Materiais Hospitalares Ltda ME", D("250.50")),
        ("30003", "Gama Serviços", D("80.00"))]
    assert leitura.avisos == []


def test_balancete_salvo_como_xlsx_tambem_e_aceito(tmp_path):
    linhas = linhas_balancete(CONTAS, mes=datetime(2026, 9, 1))
    leitura = ler_balancete(planilha(tmp_path, "Balancete.xlsx", linhas))
    assert leitura.erro is None
    assert leitura.mes == date(2026, 9, 1)
    assert leitura.total.saldo_atual == D("430.50")


def test_balancete_soma_que_nao_bate(tmp_path):
    leitura = ler_balancete(arquivo_balancete(tmp_path, CONTAS, total=999.0))
    assert any("ATENÇÃO" in a.mensagem for a in leitura.avisos)


def test_balancete_sem_a_conta_2111(tmp_path):
    caminho = texto_tasy(tmp_path, "b.xls", _topo_balancete(UNIDADE, "set/2026")
                         + [_conta(11111, "1.01.01", "Caixa", 10)] + [["WEXE001"]])
    assert "2111" in ler_balancete(caminho).erro


def test_titulos_analitico_soma_por_fornecedor_e_guarda_os_titulos(tmp_path):
    leitura = ler_titulos(arquivo_titulos(tmp_path, TITULOS))
    assert leitura.erro is None
    assert leitura.unidade == UNIDADE
    assert leitura.quantidade_titulos == 7
    assert [(f.nome, f.saldo) for f in leitura.fornecedores] == [
        ("Alfa Distribuidora Ltda - EPP", D("100.00")),
        ("Beta Comercio de Materiais Hospitalares Ltda", D("200.50")),
        ("Gama Servicos Ltda", D("80.00")),
        ("Zeta Transportes", D("12.00")),
        ("Omega Banco Teste SA", D("0.00"))]
    alfa = leitura.fornecedores[0].titulos
    assert [(t.documento, t.numero, t.tipo, t.situacao, t.saldo) for t in alfa] == [
        ("5001", "900001", "Nota Fiscal", "A", D("60.00")), ("5002", "900002", "Nota Fiscal", "A", D("40.00"))]
    assert (alfa[0].emissao, alfa[0].vencimento) == (date(2026, 9, 24), date(2026, 10, 15))
    assert leitura.fornecedores[2].titulos[0].documento == ""
    assert leitura.avisos == []


def test_titulos_analitico_salvo_como_xlsx_tambem_e_aceito(tmp_path):
    linhas = linhas_titulos([(f, int(d) if d else None, int(n), s) for f, d, n, s in TITULOS])
    leitura = ler_titulos(planilha(tmp_path, "titulos.xlsx", linhas))
    assert leitura.erro is None
    assert leitura.fornecedores[0].titulos[0].documento == "5001"
    assert leitura.fornecedores[0].titulos[0].numero == "900001"
    assert sum(f.saldo for f in leitura.fornecedores) == D("392.50")


def test_titulos_de_mais_de_um_estabelecimento_e_aviso(tmp_path):
    linhas = linhas_titulos(TITULOS[:2]) + linhas_titulos(TITULOS[2:3], unidade="AME - Outra (Fund.)")[1:]
    leitura = ler_titulos(texto_tasy(tmp_path, "t.xls", linhas))
    assert leitura.unidade == UNIDADE
    assert any("mais de um estabelecimento" in a.mensagem for a in leitura.avisos)


def test_titulo_com_saldo_ilegivel_vira_aviso(tmp_path):
    linhas = linhas_titulos(TITULOS)
    linhas[1][11] = "abc"
    leitura = ler_titulos(texto_tasy(tmp_path, "t.xls", linhas))
    assert leitura.quantidade_titulos == 6
    assert any("900001" in a.mensagem for a in leitura.avisos)


def test_relatorio_sintetico_antigo_explica_o_que_usar(tmp_path):
    caminho = texto_tasy(tmp_path, "sintetico.xls", [
        ["", "Relatório de títulos a pagar - Sintético"], ["", "Vl juros", "Vl multa", "Classif", "Vl saldo"],
        ["Impresso em", "06/10/2026", "Página 1", "CorCpa_R1"]])
    assert ler_titulos(caminho).erro == ERRO_SINTETICO
    assert ler_balancete(caminho).erro == ERRO_SINTETICO


def test_relatorios_trocados(tmp_path):
    balancete = arquivo_balancete(tmp_path, CONTAS)
    titulos = arquivo_titulos(tmp_path, TITULOS)
    assert "Títulos a pagar" in ler_balancete(titulos).erro
    assert "Balancete" in ler_titulos(balancete).erro


def test_arquivo_que_nao_e_relatorio(tmp_path):
    caminho = tmp_path / "qualquer.xls"
    caminho.write_text("texto\tsem\tsentido", encoding="utf-8")
    assert "não parece ser" in ler_balancete(caminho).erro
    assert "não parece ser" in ler_titulos(caminho).erro


# ---------------------------------------------------------------------
# Pareamento
# ---------------------------------------------------------------------
def conta(codigo, descricao, saldo):
    return ContaFornecedor(str(codigo), f"2.01.01.01.{codigo}", descricao, D(0), D(0), D(0), D(saldo))


def fornecedor(nome, saldo, cnpj=""):
    return FornecedorFinanceiro(nome, D(saldo), cnpj=cnpj)


def test_nota_de_semelhanca():
    # nomes fictícios com a mesma diferença do caso real (letra dobrada, "Com." × "Comercio"); o par real
    # fica fora do git, em test_nota_de_semelhanca_casos_reais (test_painel.py)
    assert nota_semelhanca("Verano Com. Informática Ltda Epp",
                           "Veranno Comercio e Informatica Ltda - EPP") >= 0.60
    assert nota_semelhanca("Alfa Distribuidora", "Zeta Transportes") < 0.40


def test_pareamento_ok_divergente_e_sobras():
    resultado = parear(
        [conta(1, "Alfa Distribuidora Ltda", "100"), conta(2, "Beta Hospitalar Ltda", "50"),
         conta(3, "Conta sem par Ltda", "7")],
        [fornecedor("Alfa Distribuidora", "100"), fornecedor("Beta Hospitalar", "40"),
         fornecedor("Zeta Transportes", "9")])
    assert [(l.conta.codigo if l.conta else l.nome_financeiro, l.situacao) for l in resultado.linhas] == [
        ("1", SITUACAO_OK), ("2", SITUACAO_DIVERGENTE), ("3", SITUACAO_SO_BALANCETE),
        ("Zeta Transportes", SITUACAO_SO_RELATORIO)]
    assert resultado.linhas[1].diferenca == D("10")


def test_a_reclassificar_nunca_e_pareada():
    resultado = parear([conta(1, "Fornecedores a reclassificar", "5")],
                       [fornecedor("Fornecedores a reclassificar", "5")])
    assert [l.situacao for l in resultado.linhas] == [SITUACAO_SO_BALANCETE, SITUACAO_SO_RELATORIO]


def test_cadastro_duplicado_e_somado():
    resultado = parear([conta(1, "Delta Comercio Varejista Ltda", "300")],
                       [fornecedor("Delta Comercio Varejista Ltda", "100"),
                        fornecedor("Delta Comervio Varejista Ltda", "200")])
    linha = resultado.linhas[0]
    assert len(resultado.linhas) == 1
    assert linha.situacao == SITUACAO_OK
    assert linha.nome_financeiro == "Delta Comercio Varejista Ltda + Delta Comervio Varejista Ltda"
    assert resultado.duplicados == [linha]


def test_filiais_com_o_mesmo_nome_ficam_separadas(tmp_path):
    """Caso visto em set/2026: o mesmo nome (só muda a caixa) em duas filiais, cada uma com a sua conta."""
    titulos = [("Kappa Diagnosticos Ltda", "1", "910001", 30.0, "11.111.111/0001-11"),
               ("KAPPA DIAGNOSTICOS LTDA", "2", "910002", 400.0, "11.111.111/0004-44"),
               ("Kappa Diagnosticos Ltda", "3", "910003", 5.0, "11.111.111/0001-11")]
    leitura = ler_titulos(arquivo_titulos(tmp_path, titulos))
    assert [(f.nome, f.saldo, f.cnpj) for f in leitura.fornecedores] == [
        ("Kappa Diagnosticos Ltda", D("35.00"), "11.111.111/0001-11"),
        ("KAPPA DIAGNOSTICOS LTDA", D("400.00"), "11.111.111/0004-44")]
    # cada filial casa com a conta de mesmo valor, nas duas ordens das contas
    for contas in ([conta(1, "Kappa Diagnosticos Ltda", "35"), conta(2, "Kappa Diagnosticos LTDA", "400")],
                   [conta(2, "Kappa Diagnosticos LTDA", "400"), conta(1, "Kappa Diagnosticos Ltda", "35")]):
        resultado = parear(contas, leitura.fornecedores)
        assert [l.situacao for l in resultado.linhas] == [SITUACAO_OK, SITUACAO_OK]
        assert resultado.duplicados == []


def test_mesmo_cnpj_com_nome_em_outra_caixa_continua_junto(tmp_path):
    titulos = [("Beta Comercio Ltda", "1", "910001", 30.0, "22.222.222/0001-22"),
               ("BETA COMERCIO LTDA", "2", "910002", 20.0, "22.222.222/0001-22")]
    assert [(f.nome, f.saldo) for f in ler_titulos(arquivo_titulos(tmp_path, titulos)).fornecedores] == [
        ("Beta Comercio Ltda", D("50.00"))]


def test_duplicado_nao_e_somado_a_conta_que_ja_bate():
    """Caso visto em set/2026: o "/MG" do financeiro é parecido com o "/SP", que já batia; o certo é a conta
    de outro nome e mesmo valor."""
    resultado = parear([conta(1, "Lambda/Exemplo Produtos Hospitalares Ltda", "3781.50"),
                        conta(2, "Lambda/MG - Material Cirurgico Ltda", "1428")],
                       [fornecedor("Lambda/Exemplo Produtos Hospitalares Ltda", "3781.50"),
                        fornecedor("Lambda/MG Produtos Hospitalares Ltda", "1428")])
    assert [(l.conta.codigo, l.situacao, l.nome_financeiro) for l in resultado.linhas] == [
        ("1", SITUACAO_OK, "Lambda/Exemplo Produtos Hospitalares Ltda"),
        ("2", SITUACAO_OK, "Lambda/MG Produtos Hospitalares Ltda")]
    assert resultado.duplicados == [] and resultado.por_valor == [resultado.linhas[1]]


def test_duplicado_com_mesmo_nome_mostra_o_cnpj_na_nota():
    resultado = parear([conta(1, "Kappa Diagnosticos Ltda", "435")],
                       [fornecedor("Kappa Diagnosticos Ltda", "35", "11.111.111/0001-11"),
                        fornecedor("Kappa Diagnosticos Ltda", "400", "11.111.111/0004-44")])
    linha = resultado.linhas[0]
    assert (linha.situacao, linha.nome_financeiro) == (SITUACAO_OK, "Kappa Diagnosticos Ltda")
    resumo = ResultadoFornecedores(linhas=resultado.linhas, total_financeiro=D("435"))
    notas = " ".join(_notas(resumo, resultado, LeituraTitulos(arquivo="t.xls")))
    assert "CNPJ 11.111.111/0001-11 (35,00)" in notas and "CNPJ 11.111.111/0004-44 (400,00)" in notas


def test_pareamento_por_valor():
    # nota 0,49: abaixo de 0,60 (não pareia por nome), acima de 0,40 (pareia pelo valor igual)
    resultado = parear([conta(1, "Epsilon Papeis Ltda", "806.40")],
                       [fornecedor("Epsilon Material Medico Hospitalar Ltda", "806.40")])
    linha = resultado.linhas[0]
    assert 0.40 <= linha.nota < 0.60
    assert (linha.situacao, linha.pareamento) == (SITUACAO_OK, PAREAMENTO_VALOR)
    assert resultado.por_valor == [linha]


# ---------------------------------------------------------------------
# processar_fornecedores
# ---------------------------------------------------------------------
def test_processar_sintetico(tmp_path):
    resultado = processar_fornecedores(arquivo_balancete(tmp_path, CONTAS), arquivo_titulos(tmp_path, TITULOS))
    assert resultado.erro is None
    numeros = numeros_principais(resultado)
    assert (numeros.linhas, numeros.ok, numeros.nao_ok) == (4, 2, 2)      # Beta divergente, Zeta só no relatório
    assert resultado.quantidade_titulos == 7
    assert not any(l.nome_financeiro == "Omega Banco Teste SA" for l in resultado.linhas)
    assert any("saldo zero" in nota and "Omega Banco Teste SA" in nota for nota in resultado.notas)
    assert resultado.caminho_relatorio.name == "Conciliacao_Fornecedores_CidadeTeste_set2026.xlsx"
    assert resultado.caminho_relatorio.parent == tmp_path


def test_previas(tmp_path):
    assert previa_balancete(arquivo_balancete(tmp_path, CONTAS)).descricao == \
        "AME - Cidade Teste · set/2026 · 3 contas · R$ 430,50"
    assert previa_titulos(arquivo_titulos(tmp_path, TITULOS)).descricao == \
        "AME - Cidade Teste · 7 títulos · 5 fornecedores · R$ 392,50"


def test_processar_unidades_diferentes_e_erro(tmp_path):
    balancete = arquivo_balancete(tmp_path, CONTAS)
    titulos = arquivo_titulos(tmp_path, TITULOS, unidade="AME - Outra Cidade (Fund. Hospital Exemplo)")
    resultado = processar_fornecedores(balancete, titulos)
    assert resultado.erro and "unidades diferentes" in resultado.erro
    assert resultado.caminho_relatorio is None
    assert "unidades diferentes" in conferir_par(balancete, titulos).erro
    assert conferir_par(balancete, arquivo_titulos(tmp_path, TITULOS, nome="t2.xls")).erro is None


def test_processar_pasta_escolhida_e_nome_repetido(tmp_path):
    destino = tmp_path / "saida"
    destino.mkdir()
    balancete, titulos = arquivo_balancete(tmp_path, CONTAS), arquivo_titulos(tmp_path, TITULOS)
    primeiro = processar_fornecedores(balancete, titulos, pasta_destino=destino)
    segundo = processar_fornecedores(balancete, titulos, pasta_destino=destino)
    assert primeiro.caminho_relatorio.parent == destino
    assert segundo.caminho_relatorio.name == "Conciliacao_Fornecedores_CidadeTeste_set2026_2.xlsx"
    sumiu = processar_fornecedores(balancete, titulos, pasta_destino=tmp_path / "nao_existe")
    assert sumiu.erro and "não existe" in sumiu.erro


def test_processar_relatorio_trocado(tmp_path):
    titulos = arquivo_titulos(tmp_path, TITULOS)
    resultado = processar_fornecedores(titulos, titulos)
    assert resultado.erro and "balancete" in resultado.erro


def test_planilha_formulas_e_formatacao(tmp_path):
    resultado = processar_fornecedores(arquivo_balancete(tmp_path, CONTAS), arquivo_titulos(tmp_path, TITULOS))
    livro = load_workbook(resultado.caminho_relatorio)
    assert livro.sheetnames == [ABA_RESUMO, ABA_COMPLETA, ABA_TITULOS]
    completa = livro[ABA_COMPLETA]
    assert completa["A3"].value == "Código (Balancete)"
    assert completa["F4"].value == "=D4-E4"
    assert completa["H5"].value == SITUACAO_DIVERGENTE
    assert completa["C7"].value == "Zeta Transportes" and completa["H7"].value == SITUACAO_SO_RELATORIO
    assert completa["B9"].value == "TOTAL" and completa["D9"].value == "=SUM(D4:D7)"
    assert completa.freeze_panes == "A4"
    assert len(completa.conditional_formatting) == 1
    resumo = livro[ABA_RESUMO]
    assert resumo["E6"].value == 430.5
    assert resumo["E9"].value == '=COUNTIF(\'Conciliação Completa\'!H4:H7,"OK")'
    assert resumo["G14"].value == "Divergente"
    assert resumo["B17"].value.startswith("Nota 1:")
    assert any(ABA_TITULOS in (c.value or "") for c in resumo["B"] if isinstance(c.value, str))


def test_aba_titulos_das_diferencas(tmp_path):
    """Uma linha por título dos fornecedores com diferença: Nr. Doc. na coluna B, Nr. Título na C."""
    resultado = processar_fornecedores(arquivo_balancete(tmp_path, CONTAS), arquivo_titulos(tmp_path, TITULOS))
    livro = load_workbook(resultado.caminho_relatorio)
    aba = livro[ABA_TITULOS]
    assert [c.value for c in aba[3]][:3] == ["Fornecedor (Rel. Financeiro)", "Nr. Doc.", "Nr. Título"]
    linhas = [tuple(r[:9]) for r in aba.iter_rows(min_row=4, max_row=6, values_only=True)]
    assert [(r[0], r[1], r[2], r[6], r[7], r[8]) for r in linhas] == [
        ("Beta Comercio de Materiais Hospitalares Ltda", 7001, 900003, 150.5, "30002", SITUACAO_DIVERGENTE),
        ("Beta Comercio de Materiais Hospitalares Ltda", 7002, 900004, 50, "30002", SITUACAO_DIVERGENTE),
        ("Zeta Transportes", "—", 900006, 12, "—", SITUACAO_SO_RELATORIO)]
    assert linhas[0][5] == datetime(2026, 10, 15)
    assert aba["A8"].value == "TOTAL" and aba["G8"].value == "=SUM(G4:G6)"
    # a Observação do Tasy nunca vai para a planilha
    for planilha_ in livro.worksheets:
        for linha in planilha_.iter_rows(values_only=True):
            assert not any(isinstance(c, str) and "sigiloso" in c for c in linha)


def test_aba_titulos_sem_diferencas(tmp_path):
    titulos = [("Alfa Distribuidora Ltda", "1", "2", 100.0)]
    resultado = processar_fornecedores(arquivo_balancete(tmp_path, CONTAS[:1]), arquivo_titulos(tmp_path, titulos))
    aba = load_workbook(resultado.caminho_relatorio)[ABA_TITULOS]
    assert aba["A4"].value.startswith("Nenhum fornecedor com diferença")
    assert not any(ABA_TITULOS in nota for nota in resultado.notas)


def test_nome_da_unidade_no_arquivo():
    assert unidade_para_arquivo("AME - Cidade Delta (Fund. Hospital Exemplo)") == "CidadeDelta"
    assert unidade_para_arquivo("Ame - Vale Zeta (fund. Hospital Exemplo)") == "ValeZeta"
    assert unidade_para_arquivo("Fundação Hospital Exemplo") == \
        "FundacaoHospitalExemplo"


# ---------------------------------------------------------------------
# Gabarito: Vale Zeta, Cidade Delta e Cidade Epsilon, set/2026 (ESPECIFICACAO seção 16.5)
# Arquivos .xls como saem do Tasy (balancete e relatório analítico de títulos a pagar).
# ---------------------------------------------------------------------
VALE = ("vale_zeta_set2026", "balancete_VJ.xls", "titulos_pagar_VJ.xls")
CIDADE_DELTA = ("cidade_delta_set2026", "balancete_SC.xls", "titulos_pagar_SC.xls")
CIDADE_EPSILON = ("cidade_epsilon_set_2026", "cidade_epsilon_Balancete.xls", "titulos_pagar_SJ_analitico.xls")


@pytest.fixture
def pasta_real(tmp_path):
    if not PASTA_FORNECEDORES.exists():
        pytest.skip("exemplos/Exemplos_Fornecedores não existe")
    return tmp_path


def _processar_real(unidade, saida):
    pasta, balancete, titulos = unidade
    return processar_fornecedores(PASTA_FORNECEDORES / pasta / balancete, PASTA_FORNECEDORES / pasta / titulos,
                                  agora=datetime(2026, 10, 7, 8, 0), pasta_destino=saida)


def _nao_ok(resultado):
    return [(l.conta.codigo if l.conta else "—", l.diferenca, l.situacao)
            for l in resultado.linhas if l.situacao != SITUACAO_OK]


def _titulos_nao_ok(resultado):
    return [(t.numero, t.saldo) for l in resultado.linhas if l.situacao != SITUACAO_OK
            for f in l.financeiros for t in f.titulos]


def test_gabarito_vale_zeta(pasta_real):
    resultado = _processar_real(VALE, pasta_real)
    assert resultado.erro is None
    assert (resultado.total_balancete, resultado.total_financeiro) == (D("336089.35"), D("333034.76"))
    assert resultado.quantidade_titulos == 88
    numeros = numeros_principais(resultado)
    assert (numeros.linhas, numeros.ok, numeros.nao_ok) == (54, 53, 1)
    assert _nao_ok(resultado) == [("293073", D("3054.59"), SITUACAO_SO_BALANCETE)]
    assert _titulos_nao_ok(resultado) == []
    assert any("saldo zero" in nota for nota in resultado.notas)
    duplicados = [l for l in resultado.linhas if len(l.financeiros) > 1]
    assert sorted(l.conta.codigo for l in duplicados) == ["25062", "292205"]
    assert all(l.situacao == SITUACAO_OK for l in duplicados)
    assert [l.conta.codigo for l in resultado.linhas if l.pareamento == PAREAMENTO_VALOR] == ["24836"]
    assert not any("ATENÇÃO" in a.mensagem for a in resultado.avisos)
    assert resultado.caminho_relatorio.name == "Conciliacao_Fornecedores_ValeZeta_set2026.xlsx"


def test_gabarito_cidade_delta(pasta_real):
    resultado = _processar_real(CIDADE_DELTA, pasta_real)
    assert resultado.erro is None
    assert (resultado.total_balancete, resultado.total_financeiro) == (D("181279.11"), D("149479.96"))
    numeros = numeros_principais(resultado)
    assert (numeros.linhas, numeros.ok, numeros.nao_ok) == (29, 23, 6)
    assert [(codigo, diferenca) for codigo, diferenca, _ in _nao_ok(resultado)] == [
        ("293073", D("4010.67")), ("293077", D("34095.00")),
        ("—", D("-1089.22")), ("—", D("-4851.00")), ("—", D("-43.10")), ("—", D("-323.20"))]
    assert _titulos_nao_ok(resultado) == [
        ("1345854", D("1089.22")), ("1348665", D("4851.00")), ("1349575", D("43.10")),
        ("1348664", D("323.20"))]
    assert sum(l.diferenca for l in resultado.linhas) == D("31799.15")
    assert "as 2 contas 'Fornecedores a reclassificar' somam R$ 38.105,67" in " ".join(resultado.notas)
    pasta, balancete, titulos = CIDADE_DELTA
    assert previa_balancete(PASTA_FORNECEDORES / pasta / balancete).descricao == \
        "AME - Cidade Delta · set/2026 · 25 contas · R$ 181.279,11"
    assert previa_titulos(PASTA_FORNECEDORES / pasta / titulos).descricao == \
        "AME - Cidade Delta · 33 títulos · 28 fornecedores · R$ 149.479,96"


def test_gabarito_cidade_epsilon(pasta_real):
    resultado = _processar_real(CIDADE_EPSILON, pasta_real)
    assert resultado.erro is None
    assert (resultado.total_balancete, resultado.total_financeiro) == (D("209533.04"), D("144930.03"))
    assert resultado.quantidade_titulos == 51
    numeros = numeros_principais(resultado)
    assert (numeros.linhas, numeros.ok, numeros.nao_ok) == (33, 30, 3)
    assert _nao_ok(resultado) == [
        ("293073", D("1887.23"), SITUACAO_SO_BALANCETE), ("293075", D("1253.00"), SITUACAO_SO_BALANCETE),
        ("293077", D("61462.78"), SITUACAO_SO_BALANCETE)]
    assert not any("ATENÇÃO" in a.mensagem for a in resultado.avisos)
    assert resultado.caminho_relatorio.name == "Conciliacao_Fornecedores_CidadeEpsilon_set2026.xlsx"
    aba = load_workbook(resultado.caminho_relatorio)[ABA_TITULOS]
    assert aba["A4"].value.startswith("Nenhum fornecedor com diferença")
