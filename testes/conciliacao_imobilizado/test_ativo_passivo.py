"""
Testes da Comparação Ativo x Passivo (ESPECIFICACAO_IMOBILIZADO.md, seção 6).

Os razões sintéticos imitam o relatório "Razão" do Tasy (texto separado por tabulação, cp1252) com um
AME fictício. O teste com os arquivos reais (AME Cidade Gama, outubro/2026) é pulado se exemplos/ não existir.
"""

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import load_workbook

from modulos.conciliacao_imobilizado.ativo_passivo import (
    SITUACAO_AP_CONFERE,
    SITUACAO_AP_DIFERENCA,
    SITUACAO_AP_SEM_PAR,
    ContaRazao,
    casar_contas,
    chave_do_nome,
    comparar_ativo_passivo,
    ler_razao_contabil,
    previa_razao_contabil,
)
from modulos.conciliacao_imobilizado.leitor_texto import ArquivoIlegivel
from modulos.conciliacao_imobilizado.processamento import processar_ativo_passivo
from modulos.conciliacao_imobilizado.relatorio_ativo_passivo import ABA_ATIVO_PASSIVO, ABA_AVISOS_AP

from testes.conftest import PASTA_EXEMPLOS

D = Decimal
AME = "AME - Exemplo (Fund. Hospital Exemplo)"
PASTA_REAL = PASTA_EXEMPLOS / "conciliacao_imobilizado" / "ativo_passivo_2026-10_cidade_gama"

CABECALHO = ["", "Data", "Histórico", "", "", "", "Lote", "", "", "Débitos", "", "Créditos", "", "", "Saldo"]


def _topo(ame=AME, inicio="01/10/2026", fim="31/10/2026"):
    return [
        ["", ame, "", "", "", "", "", "", "", "", "Livro: 0", "", "Página: 1", "", ""],
        ["Razão"] + [""] * 14,
        ["", "", "", "Período:", inicio, "até:", "", fim] + [""] * 7,
        CABECALHO,
    ]


def _conta(codigo, classificacao, nome):
    return ["", f"{codigo} - {classificacao}  {nome}"] + [""] * 13


def _saldo_anterior(texto):
    return ["", "", "Saldo anterior "] + [""] * 11 + [texto]


def _rodape():
    return ["", "Impresso em: 04/11/2026 16:42:43", "", "Página: 1", "", "", "", "", "JHFASI", "", "", "", "",
            "", "WEXE002"]


def gravar(pasta: Path, nome: str, linhas: list[list[str]]) -> Path:
    caminho = pasta / nome
    caminho.write_bytes("\r\n".join("\t".join(l) for l in linhas).encode("cp1252"))
    return caminho


def razao(pasta, nome, contas, ame=AME, inicio="01/10/2026", fim="31/10/2026", total=None):
    """contas: [(código, classificação, nome, saldo)]."""
    linhas = _topo(ame, inicio, fim)
    for codigo, classificacao, descricao, saldo in contas:
        linhas += [_conta(codigo, classificacao, descricao), _saldo_anterior(saldo)]
    linhas += [["", f"Total ({len(contas) if total is None else total})"] + [""] * 13, _rodape()]
    return gravar(pasta, nome, linhas)


CONTAS_ATIVO = [
    ("1001", "1.02.05.10.0001", "Aparelhos de Informatica  - AME Exemplo", "1.000,00"),
    ("1002", "1.02.05.10.0002", "Equipamentos hospitalares - AME Exemplo", "3.394.572,63"),
    ("1003", "1.02.06.10.0001", "Direito de uso de software - AME Exemplo", "500,00"),
    ("1004", "1.05.01.07.0002", "Cessão Uso Imobilizado Equipamentos Hospitalares Ame Exemplo", "9.000,00"),
]
CONTAS_PASSIVO = [
    ("2001", "2.02.12.01.0001", "Gestão Imobilizado Publico AmeE Aparelhos de Informatica", "1.000,00"),
    ("2002", "2.02.12.01.0002", "Gestão Imobilizado Publico AmeE Equipamentos Hospitalares", "3.325.072,63"),
    ("2006", "2.02.12.01.0006", "Gestão Imobilizado Publico AmeE Direito de Uso de Softwares", "500,00"),
    ("2007", "2.05.01.07.0002", "Cessão Uso Imobilizado Equipamentos Hospitalares Ame Exemplo", "9.000,00"),
]


@pytest.fixture
def arquivos(tmp_path):
    return (razao(tmp_path, "ativo.xls", CONTAS_ATIVO), razao(tmp_path, "passivo.xls", CONTAS_PASSIVO))


# ---------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------


def test_le_ame_periodo_contas_e_saldos(tmp_path):
    leitura = ler_razao_contabil(razao(tmp_path, "ativo.xls", CONTAS_ATIVO))
    assert leitura.ame == AME
    assert leitura.competencia == "2026-10"
    assert leitura.lado == "Ativo"
    assert [(c.codigo, c.classificacao, c.saldo) for c in leitura.contas] == [
        ("1001", "1.02.05.10.0001", D("1000.00")), ("1002", "1.02.05.10.0002", D("3394572.63")),
        ("1003", "1.02.06.10.0001", D("500.00")), ("1004", "1.05.01.07.0002", D("9000.00")),
    ]
    assert leitura.contas[0].nome == "Aparelhos de Informatica - AME Exemplo"
    assert leitura.avisos == []


def test_conta_com_lancamentos_vale_o_ultimo_saldo_e_pagina_com_colunas_deslocadas(tmp_path):
    lancamento = ["", "15/10/2026", "Aquisição de bem", "", "", "", "77", "", "", "200,00", "", "", "", "", "1.200,00"]
    deslocado = [""] + CABECALHO                       # página 2: uma coluna vazia a mais no começo
    baixa = ["", "", "20/10/2026", "Baixa", "", "", "", "78", "", "", "", "", "50,00", "", "", "1.150,00"]
    linhas = _topo() + [
        _conta("1001", "1.02.05.10.0001", "Aparelhos de Informatica - AME Exemplo"),
        _saldo_anterior("1.000,00"), lancamento, _rodape(), deslocado, baixa,
        ["", "Total (1)"] + [""] * 13,
    ]
    leitura = ler_razao_contabil(gravar(tmp_path, "ativo.xls", linhas))
    assert leitura.contas[0].saldo == D("1150.00")
    assert leitura.contas[0].lancamentos == 2


def test_total_de_contas_diferente_avisa(tmp_path):
    leitura = ler_razao_contabil(razao(tmp_path, "ativo.xls", CONTAS_ATIVO, total=5))
    assert leitura.avisos == ["o relatório diz 5 contas e foram lidas 4"]


def test_outro_relatorio_do_tasy_diz_qual_e(tmp_path):
    balancete = gravar(tmp_path, "bal.xls", [["Ame - Exemplo"], ["Balancete"], ["Mês Referência:", "out/2026"]])
    with pytest.raises(ArquivoIlegivel, match="Balancete .* aba \"Conciliação\""):
        ler_razao_contabil(balancete)
    with pytest.raises(ArquivoIlegivel, match="não parece ser o Razão contábil"):
        ler_razao_contabil(gravar(tmp_path, "x.xls", [["qualquer coisa"]]))


def test_previa_e_razao_no_cartao_errado(arquivos):
    ativo, passivo = arquivos
    assert previa_razao_contabil(ativo, "Ativo").descricao == "AME - Exemplo · outubro/2026 · 4 contas"
    erro = previa_razao_contabil(passivo, "Ativo").erro
    assert "é do Passivo" in erro and "Razão do Passivo" in erro


def test_razao_com_ativo_e_passivo_misturados(tmp_path):
    caminho = razao(tmp_path, "misto.xls", CONTAS_ATIVO[:1] + CONTAS_PASSIVO[:1])
    assert "juntas" in previa_razao_contabil(caminho, "Ativo").erro


# ---------------------------------------------------------------------
# Casamento dos nomes
# ---------------------------------------------------------------------


@pytest.mark.parametrize("ativo, passivo", [
    ("Aparelhos de Informatica  - AME Cidade Gama", "Gestão Imobilizado Publico AmeC Aparelhos de Informatica"),
    ("Moveis e utensílios - AME Cidade Gama", "Gestão Imobilizado Publico AmeC Moveis e Utensilios"),
    ("Direito de uso de software - AME Cidade Gama", "Gestão Imobilizado Publico AmeC Direito de Uso de Softwares"),
    ("Cessão Uso Imobilizado Instrumentos Medicos Ame Cidade Gama", "Cessão Uso Imobilizado Instrumentos Medicos Ame Cidade Gama"),
    ("Equipamentos hospitalares - AME Cidade Beta", "Gestão Imobilizado Publico AmeRP Equipamentos Hospitalares"),
])
def test_nomes_parecidos_tem_a_mesma_chave(ativo, passivo):
    cidade = {"cidade", "gama", "beta"}
    assert chave_do_nome(ativo, cidade) == chave_do_nome(passivo, cidade)


def test_tipos_de_bem_diferentes_nao_casam():
    assert chave_do_nome("Maquinas e equipamentos") != chave_do_nome("Equipamentos hospitalares")
    assert chave_do_nome("Instrumentos medicos") != chave_do_nome("Equipamentos hospitalares")


def _c(classificacao, nome, saldo):
    return ContaRazao(codigo="1", classificacao=classificacao, nome=nome, saldo=D(saldo))


def test_so_casa_dentro_do_mesmo_grupo():
    ativo = [_c("1.02.05.10.0002", "Equipamentos hospitalares - AME Exemplo", "10")]
    passivo = [_c("2.05.01.07.0002", "Cessão Uso Imobilizado Equipamentos Hospitalares Ame Exemplo", "10")]
    pares = casar_contas(ativo, passivo, AME)
    assert [p.situacao for p in pares] == [SITUACAO_AP_SEM_PAR, SITUACAO_AP_SEM_PAR]
    assert pares[0].diferenca == D("10") and pares[1].diferenca == D("-10")


def test_valor_nao_acha_par_e_nome_repetido_nao_chuta():
    ativo = [_c("1.02.05.10.0001", "Aparelhos de informatica", "10"),
             _c("1.02.05.10.0009", "Aparelhos de informática", "20")]
    passivo = [_c("2.02.12.01.0001", "Gestão Imobilizado Publico AmeE Aparelhos de Informatica", "10")]
    pares = casar_contas(ativo, passivo, AME)
    assert all(p.situacao == SITUACAO_AP_SEM_PAR for p in pares)
    assert "mais de uma conta" in pares[0].observacao
    assert len(pares) == 3


# ---------------------------------------------------------------------
# Comparação completa e planilha
# ---------------------------------------------------------------------


def test_compara_e_acha_a_diferenca(arquivos):
    resultado = comparar_ativo_passivo(*arquivos)
    assert resultado.erro == ""
    assert resultado.ame == "AME - Exemplo" and resultado.competencia == "2026-10"
    assert [(p.ativo.classificacao, p.passivo.classificacao, p.situacao) for p in resultado.pares] == [
        ("1.02.05.10.0001", "2.02.12.01.0001", SITUACAO_AP_CONFERE),
        ("1.02.05.10.0002", "2.02.12.01.0002", SITUACAO_AP_DIFERENCA),
        ("1.02.06.10.0001", "2.02.12.01.0006", SITUACAO_AP_CONFERE),
        ("1.05.01.07.0002", "2.05.01.07.0002", SITUACAO_AP_CONFERE),
    ]
    assert resultado.pares[1].diferenca == D("69500.00")
    assert resultado.total("diferenca") == D("69500.00")


def test_conta_so_no_passivo_aparece_sem_par(tmp_path):
    extra = ("2009", "2.02.12.01.0009", "Gestão Imobilizado Publico AmeE Veiculos", "7,00")
    resultado = comparar_ativo_passivo(razao(tmp_path, "a.xls", CONTAS_ATIVO),
                                       razao(tmp_path, "p.xls", CONTAS_PASSIVO + [extra]))
    ultimo = resultado.pares[-1]
    assert (ultimo.ativo, ultimo.passivo.classificacao, ultimo.situacao) == (None, "2.02.12.01.0009", SITUACAO_AP_SEM_PAR)
    assert ultimo.diferenca == D("-7.00")


def test_ames_e_periodos_diferentes_avisam(tmp_path):
    resultado = comparar_ativo_passivo(
        razao(tmp_path, "a.xls", CONTAS_ATIVO),
        razao(tmp_path, "p.xls", CONTAS_PASSIVO, ame="AME - Outro (Fund. Hospital Exemplo)",
              inicio="01/09/2026", fim="30/09/2026"))
    mensagens = " ".join(a.mensagem for a in resultado.avisos)
    assert "AMEs diferentes" in mensagens and "períodos diferentes" in mensagens


def test_razoes_trocados_nao_comparam(arquivos):
    ativo, passivo = arquivos
    resultado = comparar_ativo_passivo(passivo, ativo)
    assert resultado.pares == [] and "não pôde ser lido" in resultado.erro


def test_planilha_gerada(arquivos, tmp_path):
    saida = tmp_path / "saida"
    saida.mkdir()
    resultado = processar_ativo_passivo(*arquivos, pasta_destino=saida, agora=datetime(2026, 11, 5, 15, 30))
    assert resultado.erro == ""
    assert resultado.caminho_relatorio.name == "Conciliacao_ativo_passivo_2026-10_AME_Exemplo_15h30.xlsx"
    livro = load_workbook(resultado.caminho_relatorio)
    assert livro.sheetnames == [ABA_ATIVO_PASSIVO, ABA_AVISOS_AP]
    linhas = list(livro[ABA_ATIVO_PASSIVO].iter_rows(values_only=True))
    titulos = linhas[7]
    assert titulos[:7] == ("Grupo", "Conta do Ativo", "Saldo Ativo", "Conta do Passivo", "Saldo Passivo",
                           "Diferença (Ativo − Passivo)", "Situação")
    assert linhas[9][5] == 69500 and linhas[9][6] == SITUACAO_AP_DIFERENCA
    assert linhas[-1][1] == "Total" and linhas[-1][5] == 69500


def test_pasta_que_nao_existe(arquivos, tmp_path):
    resultado = processar_ativo_passivo(*arquivos, pasta_destino=tmp_path / "sumiu")
    assert resultado.caminho_relatorio is None and "não existe mais" in resultado.erro
    assert len(resultado.pares) == 4


# ---------------------------------------------------------------------
# Gabarito real: AME Cidade Gama, outubro/2026
# ---------------------------------------------------------------------


def test_gabarito_cidade_gama_outubro():
    ativo, passivo = PASTA_REAL / "Imobilizado Ativo.xls", PASTA_REAL / "Imobilizado Passivo .xls"
    if not ativo.is_file() or not passivo.is_file():
        pytest.skip(f"Arquivos de exemplo não encontrados em {PASTA_REAL}")
    resultado = comparar_ativo_passivo(ativo, passivo)
    assert resultado.ame == "AME - Cidade Gama" and resultado.competencia == "2026-10"
    assert len(resultado.pares) == 10
    assert resultado.contar(SITUACAO_AP_CONFERE) == 9
    diferentes = [p for p in resultado.pares if p.situacao != SITUACAO_AP_CONFERE]
    assert [(p.ativo.classificacao, p.passivo.classificacao, p.diferenca) for p in diferentes] == [
        ("1.02.05.10.0002", "2.02.12.01.0002", D("69500.00"))]
    software = next(p for p in resultado.pares if p.ativo.classificacao == "1.02.06.10.0001")
    assert software.passivo.classificacao == "2.02.12.01.0006"
    assert resultado.total("saldo_ativo") == D("19054531.39")
    assert resultado.total("saldo_passivo") == D("18985031.39")
