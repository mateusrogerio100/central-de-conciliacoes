"""
Testes da Conciliação do Imobilizado – AME's (ESPECIFICACAO seção 15).

Os arquivos sintéticos imitam o formato do Tasy (texto separado por tabulação, Windows-1252,
colunas deslocadas entre páginas). Os testes com os arquivos reais (gabarito) são pulados
se exemplos/ não existir.
"""

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import load_workbook

from modulos.conciliacao_imobilizado.processamento import numeros_principais, previa_balancetes, processar_bens
from modulos.conciliacao_imobilizado.conciliador import conciliar, ligar_baixas_as_contas
from modulos.conciliacao_imobilizado.leitor_baixas import ler_baixas
from modulos.conciliacao_imobilizado.leitor_balancete import ler_balancete
from modulos.conciliacao_imobilizado.leitor_bens_adquiridos import ler_bens_adquiridos
from modulos.conciliacao_imobilizado.leitor_razao import ler_razao
from modulos.conciliacao_imobilizado.modelos import (
    SITUACAO_CONFERE,
    SITUACAO_DIFERENCA,
    SITUACAO_DIFERENCA_EXPLICADA,
    SITUACAO_DIFERENCA_SEM_EXPLICACAO,
    SITUACAO_SOMENTE_BALANCETE,
    SITUACAO_SOMENTE_PATRIMONIO,
    BemAdquirido,
    BemBaixado,
    ContaBalancete,
    ContaPatrimonio,
)
from modulos.conciliacao_imobilizado.relatorio_excel import (
    ABA_AVISOS,
    ABA_BAIXAS,
    ABA_BENS_ADQUIRIDOS,
    ABA_CONTAS,
    ABA_DIFERENCAS,
    ABA_RESUMO,
)

from testes.conftest import PASTA_EXEMPLOS

PASTA_PATRIMONIO = PASTA_EXEMPLOS / "conciliacao_imobilizado" / "Exemplos_Patrimonio_AME"

D = Decimal
AME_CIDADE_ALFA = "Ame - Cidade Alfa ( Fund. Hospital Exemplo )"
AME_OUTRO = "Ame - Outro ( Fund. Hospital Exemplo )"


def gravar(pasta: Path, nome: str, linhas: list[list[str]]) -> Path:
    caminho = pasta / nome
    caminho.write_bytes("\r\n".join("\t".join(l) for l in linhas).encode("cp1252"))
    return caminho


# ---------------------------------------------------------------------
# Arquivos sintéticos
# ---------------------------------------------------------------------
def bloco_razao(codigo, nome, anterior, entradas, baixas, atual, recuo=1):
    vazio = [""] * recuo
    return [
        vazio + [f"{codigo} - {nome}", "", ""],
        vazio + ["Saldo anterior", anterior, "", "", "", "Deprec mes anterior", "", "", "0,00"],
        vazio + ["Entradas", entradas, "", "", "", "Deprec mes", "", "", "0,00"],
        vazio + ["Baixas", baixas, "", "", "", "Baixa deprec", "", "", "0,00"],
        vazio + ["Transf bem (entrada)", "0,00"],
        vazio + ["Transf bem (saída)", "0,00"],
        vazio + ["Saldo atual", atual, "", "", "", "Deprec acum mes", "", "", "0,00"],
        vazio + ["Valor contábil liquido", atual, "", "", "", "Situação", "", "", "", "", "ATIVO"],
    ]


def arquivo_razao(pasta, contas=None, data="01/08/2026", nome="razao.xls"):
    contas = contas if contas is not None else [
        ("11038", "Aparelhos de informática AME", "100,00", "50,00", "0,00", "150,00"),
        ("11047", "Máquinas e Equipamentos AME", "1.000,00", "0,00", "0,00", "1.000,00"),
    ]
    linhas = [
        ["", "", ""],
        ["Patrimônio - Razão auxiliar (NOVO)", "", ""],
        ["", "", "", "Data referência", "", data],
    ]
    for conta in contas:
        linhas += bloco_razao(*conta)
    linhas += [["", "  Total Geral"]] + bloco_razao("0", "x", "0,00", "0,00", "0,00", "0,00")[1:]
    linhas += [["", "Impresso em:  06/10/2026 14:32:59", "", "Página   1", "", "CATE6051"]]
    return gravar(pasta, nome, linhas)


def arquivo_balancete(pasta, contas, nome="imobilizado.xls", ame=AME_CIDADE_ALFA, mes="ago/2026",
                      mae=("1320", "1.02.05.06", "IMOBILIZADO AMBULATÓRIO", None)):
    """contas: (codigo, classificacao, descricao, saldo_atual). A mãe soma as filhas se None."""
    linhas = [
        [ame, "", ""],
        ["Balancete", "", ""],
        ["", "", "", "", "", "", "Mês Referência:", "", "", mes],
        ["", "Código", "", "Classificação", "", "Descrição", "", "", "Saldo Anterior", "",
         "Débitos", "", "Créditos", "Saldo Atual", ""],
        ["", "Ativo"],
    ]
    if mae is not None:
        codigo, classificacao, descricao, saldo = mae
        if saldo is None:
            soma = sum(D(c[3].replace(".", "").replace(",", ".")) for c in contas)
            saldo = f"{soma:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
        linhas.append(["", "", codigo, "", classificacao, "", "   " + descricao, "", "",
                       saldo, "", "0,00", "", "0,00", saldo, ""])
    for codigo, classificacao, descricao, saldo in contas:
        linhas.append(["", "", codigo, "", classificacao, "", "      " + descricao, "", "",
                       saldo, "", "0,00", "", "0,00", saldo, ""])
    linhas.append(["", "Impresso em: 06/10/2026 14:37:41", "", "", "", "", "", "Página: 1", "",
                   "", "", "UsuarioRS", "", "", "WEXE001"])
    return gravar(pasta, nome, linhas)


CONTAS_IMOBILIZADO = [
    ("11038", "1.02.05.06.0001", "Aparelhos de informática AME", "150,00"),
    ("11047", "1.02.05.06.0010", "Máquinas e Equipamentos AME", "999,97"),
]


def arquivo_bens(pasta, bens, total=None, nome="bens.xls", periodo=("01/08/2026", "31/08/2026")):
    """bens: (centro, conta, codigo_bem, descricao, valor)."""
    linhas = [
        ["Patrimonio - Bens adquiridos no período por centro custo", ""],
        ["", "", "", "", "", "Bens adquiridos de:", "", periodo[0], "até:  ", "", periodo[1]],
        ["", "Centro", "Conta", "Código Bem", "Descrição Bem", "", "", "", "", "", "",
         "Dt. Aquisição", "Dt. Início ", "", "Taxa Deprec", "Vl original"],
    ]
    for centro, conta, codigo, descricao, valor in bens:
        linhas.append(["", centro])
        linhas.append(["", "", conta])
        linhas.append(["", "", "", codigo, descricao, "", "", "", "", "", "", "18/08/2026",
                       "18/08/2026", "", "0,00", valor])
    if total is not None:
        linhas.append([f"Total({total[0]})"] + [""] * 14 + [total[1]])
    linhas.append(["", "Impresso em:  06/10/2026 14:42:10", "", "", "", "", "Página   1", "",
                   "", "UsuarioRS", "", "", "", "UEXE001"])
    return gravar(pasta, nome, linhas)


def _cabecalho_baixas(recuo, ame):
    vazio = [""] * recuo
    return [
        vazio + [""] * 10 + ["RESPONSÁVEL: ________"],
        vazio + [""] * 10 + ["PATRIMÔNIO:________"],
        vazio + ["", "", "", "", "BAIXA DE BENS DO ATIVO IMOBILIZADO"],
        vazio + ["", "", ame],
        vazio + ["CHAPA", "IMOBILIZADO", "", "", "", "", "TIPO", "MOTIVO", "", "VL. ORIGEM", "",
                 "VL. DEPREC.", "", "VL. ATUAL", "DATA"],
    ]


def _linha_baixa(recuo, chapa, descricao, valor, data="01/08/2026"):
    return [""] * recuo + [chapa, "", "", descricao, "", "", "Baixa", "Processo: 1", "", valor,
                           "", "0,00", "", valor, data]


def arquivo_baixas(pasta, conta_nome, pagina1, pagina2=(), total=None, ame=AME_CIDADE_ALFA,
                   nome="baixas.xls"):
    """pagina1/pagina2: (chapa, descricao, valor). Página 2 com uma coluna a mais no começo."""
    linhas = _cabecalho_baixas(0, ame) + [[conta_nome]]
    linhas += [_linha_baixa(0, *b) for b in pagina1]
    linhas.append(["Impresso em:  06/10/2026 16:12:21", "", "", "", "", "Página   1", "", "", "",
                   "", "", "", "UEXE002"])
    if pagina2:
        linhas += _cabecalho_baixas(1, ame)
        linhas += [_linha_baixa(1, *b) for b in pagina2]
    if total is not None:
        quantidade, valor = total
        linhas.append([f"Total - {conta_nome}({quantidade})"] + [""] * 9 + [valor])
        linhas.append([f"Total({quantidade})"] + [""] * 9 + [valor])
    linhas.append(["", "Impresso em:  06/10/2026 16:12:33", "", "", "", "", "Página   2"])
    return gravar(pasta, nome, linhas)


# ---------------------------------------------------------------------
# Leitores
# ---------------------------------------------------------------------
def test_razao_le_contas_e_data(tmp_path):
    leitura = ler_razao(arquivo_razao(tmp_path))
    assert leitura.erro is None
    assert leitura.data_referencia.month == 8
    assert [(c.codigo, c.saldo_atual) for c in leitura.contas] == [
        ("11038", D("150.00")), ("11047", D("1000.00"))]
    assert leitura.contas[0].entradas == D("50.00")
    assert leitura.avisos == []


def test_razao_conta_quebrada_entre_paginas(tmp_path):
    """Título no fim da página 1; valores na página 2, uma coluna mais à direita."""
    linhas = [
        ["Patrimônio - Razão auxiliar (NOVO)"],
        ["", "", "", "Data referência", "", "01/08/2026"],
        ["", "11048 - Móveis e utensílios AME"],
        ["", "Impresso em:  06/10/2026 14:32:59", "", "", "Página   1", "", "CATE6051"],
        ["Patrimônio - Razão auxiliar (NOVO)"],
        ["", "", "", "", "Data referência", "", "01/08/2026"],
    ] + [[""] + l for l in bloco_razao("x", "x", "907.854,53", "0,00", "0,00", "907.854,53")[1:]]
    leitura = ler_razao(gravar(tmp_path, "r.xls", linhas))
    assert [(c.codigo, c.nome, c.saldo_atual) for c in leitura.contas] == [
        ("11048", "Móveis e utensílios AME", D("907854.53"))]


def test_razao_movimento_que_nao_fecha():
    conta = ContaPatrimonio("11042", "Equip", D("6277503.92"), D(0), D(0), D(0), D(0),
                            D("5148746.06"))
    assert conta.diferenca_movimento == D("-1128757.86")


def test_balancete_marca_conta_mae_e_le_ame(tmp_path):
    leitura = ler_balancete(arquivo_balancete(tmp_path, CONTAS_IMOBILIZADO))
    assert leitura.erro is None
    assert leitura.ame == AME_CIDADE_ALFA
    assert leitura.competencia == "2026-08"
    assert [(c.codigo, c.sintetica) for c in leitura.contas] == [
        ("1320", True), ("11038", False), ("11047", False)]
    assert leitura.contas[2].descricao == "Máquinas e Equipamentos AME"
    assert leitura.avisos == []


def test_balancete_conta_mae_que_nao_soma(tmp_path):
    caminho = arquivo_balancete(tmp_path, CONTAS_IMOBILIZADO,
                                mae=("1320", "1.02.05.06", "IMOBILIZADO", "5,00"))
    leitura = ler_balancete(caminho)
    assert any("ATENÇÃO" in a.mensagem and "1320" in a.mensagem for a in leitura.avisos)


def test_bens_adquiridos_e_total(tmp_path):
    caminho = arquivo_bens(tmp_path, [
        ("1888  -  Central", "11038 Aparelhos de informática AME", "AME1", "Nobreak 1", "3.989,00"),
        ("1990  -  Centro Cirúrgico", "11038 Aparelhos de informática AME", "AME2", "Nobreak 2",
         "2.700,00"),
    ], total=(2, "6.689,00"))
    leitura = ler_bens_adquiridos(caminho)
    assert leitura.erro is None
    assert [(b.centro, b.conta_codigo, b.codigo_bem, b.valor) for b in leitura.bens] == [
        ("1888 - Central", "11038", "AME1", D("3989.00")),
        ("1990 - Centro Cirúrgico", "11038", "AME2", D("2700.00"))]
    assert leitura.periodo_inicio.day == 1 and leitura.periodo_fim.day == 31
    assert leitura.avisos == []


def test_bens_adquiridos_total_que_nao_bate(tmp_path):
    caminho = arquivo_bens(tmp_path, [("1 - C", "11038 Ap", "AME1", "X", "10,00")],
                           total=(2, "20,00"))
    assert any("ATENÇÃO" in a.mensagem for a in ler_bens_adquiridos(caminho).avisos)


def test_baixas_com_quebra_de_pagina(tmp_path):
    """O topo da página 2 (RESPONSÁVEL, AME...) não pode virar nome de conta."""
    caminho = arquivo_baixas(tmp_path, "Equipamentos hospitalares AME",
                             [("AME1", "Aparelho 1", "57.407,41")],
                             [("AME2", "Aparelho 2", "482,08")], total=(2, "57.889,49"))
    leitura = ler_baixas(caminho)
    assert leitura.erro is None
    assert leitura.ame == AME_CIDADE_ALFA
    assert [(b.chapa, b.descricao, b.conta_nome, b.valor_origem) for b in leitura.bens] == [
        ("AME1", "Aparelho 1", "Equipamentos hospitalares AME", D("57407.41")),
        ("AME2", "Aparelho 2", "Equipamentos hospitalares AME", D("482.08"))]
    assert leitura.avisos == []


def test_baixas_total_que_nao_bate(tmp_path):
    caminho = arquivo_baixas(tmp_path, "Equip", [("AME1", "A", "10,00")], total=(1, "99,00"))
    assert any("ATENÇÃO" in a.mensagem for a in ler_baixas(caminho).avisos)


@pytest.mark.parametrize("leitor, esperado", [
    (ler_razao, "Bens adquiridos (555)"),
    (ler_balancete, "Bens adquiridos (555)"),
    (ler_baixas, "Bens adquiridos (555)"),
])
def test_arquivo_no_campo_errado(tmp_path, leitor, esperado):
    caminho = arquivo_bens(tmp_path, [("1 - C", "11038 Ap", "AME1", "X", "10,00")])
    leitura = leitor(caminho)
    assert leitura.erro and esperado in leitura.erro


def test_balancete_no_campo_do_razao(tmp_path):
    erro = ler_razao(arquivo_balancete(tmp_path, CONTAS_IMOBILIZADO)).erro
    assert "Balancete" in erro and "Balancetes (865)" in erro


def test_arquivo_salvo_de_novo_no_excel(tmp_path):
    caminho = tmp_path / "razao.xls"
    caminho.write_bytes(b"\xd0\xcf\x11\xe0" + b"\0" * 100)
    assert "salvo de novo no Excel" in ler_razao(caminho).erro


# ---------------------------------------------------------------------
# Conciliação
# ---------------------------------------------------------------------
def conta_p(codigo, saldo, nome=None):
    return ContaPatrimonio(codigo, nome or f"Conta {codigo}", D(0), D(0), D(0), D(0), D(0),
                           D(saldo))


def conta_b(codigo, saldo, descricao=None, sintetica=False):
    return ContaBalancete(codigo, f"1.{codigo}", descricao or f"Conta {codigo}", D(0), D(0), D(0),
                          D(saldo), arquivo="bal.xls", sintetica=sintetica)


def bem(conta, valor):
    return BemAdquirido("C", conta, "x", "AME", "bem", None, D(valor))


def baixa(conta, valor, nome="x"):
    return BemBaixado(nome, "AME", "bem", "Baixa", "", D(valor), None, None, None,
                      conta_codigo=conta)


def situacoes(conciliacao):
    return {i.codigo: i.situacao for i in conciliacao.itens}


def test_confere_somente_de_um_lado_e_conta_mae_fora():
    resultado = conciliar(
        [conta_p("1", "10"), conta_p("2", "5")],
        [conta_b("1", "10"), conta_b("3", "7"), conta_b("99", "17", sintetica=True)],
    )
    assert situacoes(resultado) == {
        "1": SITUACAO_CONFERE, "2": SITUACAO_SOMENTE_PATRIMONIO, "3": SITUACAO_SOMENTE_BALANCETE}


def test_diferenca_de_centavos_sem_opcionais():
    item = conciliar([conta_p("11047", "499400.00")], [conta_b("11047", "499399.97")]).itens[0]
    assert item.situacao == SITUACAO_DIFERENCA
    assert item.diferenca == D("0.03")
    assert "Selecione" in item.explicacao


@pytest.mark.parametrize("patrimonio, balancete, entradas, baixas, explica", [
    ("150", "100", ["50"], [], "entradas da conta"),         # entrou só no patrimônio
    ("100", "150", ["50"], [], "entradas da conta"),         # entrou só na contabilidade
    ("100", "130", [], ["30"], "baixas da conta"),           # baixou só no patrimônio
    ("130", "100", [], ["30"], "baixas da conta"),           # baixou só na contabilidade
    ("120", "100", ["50"], ["30"], "entradas menos baixas"),
])
def test_diferenca_explicada_para_mais_ou_para_menos(patrimonio, balancete, entradas, baixas,
                                                       explica):
    item = conciliar([conta_p("1", patrimonio)], [conta_b("1", balancete)],
                     [bem("1", v) for v in entradas], [baixa("1", v) for v in baixas]).itens[0]
    assert item.situacao == SITUACAO_DIFERENCA_EXPLICADA
    assert explica in item.explicacao
    assert ("maior" in item.explicacao) == (D(patrimonio) > D(balancete))


def test_diferenca_sem_explicacao_com_opcionais():
    item = conciliar([conta_p("1", "100")], [conta_b("1", "90")], [bem("1", "7")], []).itens[0]
    assert item.situacao == SITUACAO_DIFERENCA_SEM_EXPLICACAO
    assert "entradas 7,00" in item.explicacao


def test_so_um_opcional_informado_ja_tenta_explicar():
    item = conciliar([conta_p("1", "100")], [conta_b("1", "90")], None, [baixa("1", "10")]).itens[0]
    assert item.situacao == SITUACAO_DIFERENCA_EXPLICADA


def test_ligar_baixas_pelo_nome():
    contas_p = [conta_p("11042", "1", nome="Equipamentos hospitalares AME")]
    contas_b = [conta_b("12011", "1", descricao="Cessão Uso Equipamentos Hospitalares Ame"),
                conta_b("1", "1", descricao="Duplicada"), conta_b("2", "1", descricao="Duplicada")]
    baixas = [BemBaixado("Equipamentos  hospitalares AME", "A", "", "", "", D(1), None, None, None),
              BemBaixado("Não existe", "B", "", "", "", D(1), None, None, None),
              BemBaixado("Duplicada", "C", "", "", "", D(1), None, None, None)]
    avisos = ligar_baixas_as_contas(baixas, contas_p, contas_b)
    assert [b.conta_codigo for b in baixas] == ["11042", "", ""]
    assert len(avisos) == 2
    assert "nenhuma conta" in avisos[0].mensagem and "mais de uma" in avisos[1].mensagem


# ---------------------------------------------------------------------
# processar_bens
# ---------------------------------------------------------------------
AGORA = datetime(2026, 10, 6, 15, 30)


def test_processar_sintetico_com_opcionais(tmp_path):
    razao = arquivo_razao(tmp_path, contas=[
        ("11038", "Aparelhos de informática AME", "100,00", "50,00", "0,00", "150,00"),
        ("11047", "Máquinas e Equipamentos AME", "1.000,00", "0,00", "0,00", "1.000,00"),
        ("11042", "Equipamentos hospitalares AME", "500,00", "0,00", "0,00", "500,00"),
    ])
    balancete = arquivo_balancete(tmp_path, [
        ("11038", "1.02.05.06.0001", "Aparelhos de informática AME", "100,00"),
        ("11042", "1.02.05.06.0005", "Equipamentos hospitalares AME", "530,00"),
        ("11047", "1.02.05.06.0010", "Máquinas e Equipamentos AME", "1.000,00"),
    ])
    bens = arquivo_bens(tmp_path, [("1 - C", "11038 Aparelhos de informática AME", "AME1",
                                    "Nobreak", "50,00")], total=(1, "50,00"))
    baixas = arquivo_baixas(tmp_path, "Equipamentos hospitalares AME", [("AME9", "X", "30,00")],
                            total=(1, "30,00"))
    resultado = processar_bens(razao, [balancete], bens, baixas, agora=AGORA)
    assert resultado.erro is None
    assert situacoes(resultado) == {
        "11038": SITUACAO_DIFERENCA_EXPLICADA, "11042": SITUACAO_DIFERENCA_EXPLICADA,
        "11047": SITUACAO_CONFERE}
    assert resultado.ame == "Ame - Cidade Alfa"
    assert resultado.competencia_texto == "agosto/2026"
    assert resultado.caminho_relatorio.name == "Conciliacao_imobilizado_2026-08_Ame_Cidade_Alfa_15h30.xlsx"
    assert numeros_principais(resultado).explicadas == 2


def test_processar_avisa_ame_e_mes_diferentes(tmp_path):
    razao = arquivo_razao(tmp_path, data="01/07/2026")
    bal1 = arquivo_balancete(tmp_path, CONTAS_IMOBILIZADO[:1], nome="b1.xls",
                             mae=("1", "1.02.05.06", "M", None))
    bal2 = arquivo_balancete(tmp_path, CONTAS_IMOBILIZADO[1:], nome="b2.xls", ame=AME_OUTRO,
                             mes="set/2026", mae=("2", "1.02.05.06", "M", None))
    baixas = arquivo_baixas(tmp_path, "Equip", [("A", "X", "1,00")], total=(1, "1,00"),
                            ame=AME_OUTRO)
    mensagens = " | ".join(a.mensagem for a in
                           processar_bens(razao, [bal1, bal2], None, baixas, agora=AGORA).avisos)
    assert "AMEs diferentes" in mensagens
    assert "meses diferentes" in mensagens
    assert "o patrimônio é de julho/2026" in mensagens
    assert "o relatório de baixas é do Ame - Outro" in mensagens


def test_processar_sem_opcionais_sugere_selecionar(tmp_path):
    resultado = processar_bens(arquivo_razao(tmp_path),
                               [arquivo_balancete(tmp_path, CONTAS_IMOBILIZADO)], agora=AGORA)
    assert situacoes(resultado)["11047"] == SITUACAO_DIFERENCA
    assert any("selecione Bens adquiridos (555) e Baixa de bens (561)" in a.mensagem
               for a in resultado.avisos)


def test_processar_balancete_repetido(tmp_path):
    balancete = arquivo_balancete(tmp_path, CONTAS_IMOBILIZADO)
    resultado = processar_bens(arquivo_razao(tmp_path), [balancete, balancete], agora=AGORA)
    assert any("mais de uma vez" in a.mensagem for a in resultado.avisos)
    assert len(resultado.itens) == 2


def test_processar_sem_razao_nao_gera(tmp_path):
    balancete = arquivo_balancete(tmp_path, CONTAS_IMOBILIZADO)
    resultado = processar_bens(balancete, [balancete], agora=AGORA)
    assert resultado.erro and "Razão auxiliar" in resultado.erro
    assert resultado.caminho_relatorio is None


def test_processar_opcional_com_erro_continua(tmp_path):
    razao = arquivo_razao(tmp_path)
    balancete = arquivo_balancete(tmp_path, CONTAS_IMOBILIZADO)
    resultado = processar_bens(razao, [balancete], arquivo_bens_adquiridos=balancete, agora=AGORA)
    assert resultado.erro is None
    assert not resultado.leu_bens_adquiridos
    assert any(a.eh_erro for a in resultado.avisos)


# ---------------------------------------------------------------------
# Gabarito: AME Cidade Alfa, agosto/2026 (ESPECIFICACAO seção 15.5)
# ---------------------------------------------------------------------
RAZAO = "Patrimonio_razao_ame_cidade_alfa.xls"
BALANCETES = ["intangivel_ame_cidade_alfa.xls", "imobilizado_ame_cidade_alfa.xls", "cessao_ame_cidade_alfa.xls"]
BENS = "Bens_adquiridos.xls"
BAIXAS = "Baixa de Bens do Ativo Imobilizado.xls"


@pytest.fixture
def pasta_real(tmp_path):
    if not PASTA_PATRIMONIO.exists():
        pytest.skip("exemplos/Exemplos_Patrimonio_AME não existe")
    for nome in [RAZAO, BENS, BAIXAS, *BALANCETES]:
        (tmp_path / nome).write_bytes((PASTA_PATRIMONIO / nome).read_bytes())
    return tmp_path


def _processar_real(pasta, com_opcionais):
    return processar_bens(pasta / RAZAO, [pasta / n for n in BALANCETES],
                          pasta / BENS if com_opcionais else None,
                          pasta / BAIXAS if com_opcionais else None, agora=AGORA)


def test_gabarito_sem_opcionais(pasta_real):
    resultado = _processar_real(pasta_real, com_opcionais=False)
    assert resultado.erro is None
    assert (resultado.ame, resultado.competencia) == ("Ame - Cidade Alfa", "2026-08")
    assert [i.codigo for i in resultado.itens] == [
        "11038", "11040", "11042", "11045", "11047", "11048", "12011", "12012", "12014"]
    numeros = numeros_principais(resultado)
    assert (numeros.contas, numeros.conferem, numeros.para_analisar) == (9, 8, 1)
    item = next(i for i in resultado.itens if i.codigo == "11047")
    assert item.situacao == SITUACAO_DIFERENCA
    assert (item.saldo_patrimonio, item.saldo_balancete, item.diferenca) == (
        D("499400.00"), D("499399.97"), D("0.03"))
    assert [c.codigo for c in resultado.contas_maes] == ["152", "1320", "1515"]
    mensagens = [a.mensagem for a in resultado.avisos]
    assert any("11042" in m and "não fecha" in m and "-1.128.757,86" in m for m in mensagens)
    assert any("11047" in m and "selecione" in m for m in mensagens)
    assert not any("ATENÇÃO" in m for m in mensagens)


def test_gabarito_com_opcionais(pasta_real):
    resultado = _processar_real(pasta_real, com_opcionais=True)
    assert resultado.erro is None
    assert situacoes(resultado)["11047"] == SITUACAO_DIFERENCA_SEM_EXPLICACAO
    assert len(resultado.bens_adquiridos) == 2
    assert sum(b.valor for b in resultado.bens_adquiridos) == D("6689.00")
    assert len(resultado.bens_baixados) == 40
    assert {b.conta_codigo for b in resultado.bens_baixados} == {"11042"}
    assert sum(b.valor_origem for b in resultado.bens_baixados) == D("1128757.86")
    itens = {i.codigo: i for i in resultado.itens}
    assert itens["11038"].entradas == D("6689.00")
    assert itens["11042"].baixas == D("1128757.86")
    mensagens = [a.mensagem for a in resultado.avisos]
    assert any("11042" in m and "igual às baixas" in m for m in mensagens)
    assert not any("ATENÇÃO" in m for m in mensagens)
    assert not any("selecione" in m for m in mensagens)


def test_gabarito_planilha(pasta_real):
    resultado = _processar_real(pasta_real, com_opcionais=True)
    livro = load_workbook(resultado.caminho_relatorio)
    assert livro.sheetnames == [ABA_RESUMO, ABA_CONTAS, ABA_DIFERENCAS, ABA_BENS_ADQUIRIDOS,
                                ABA_BAIXAS, ABA_AVISOS]
    contas = list(livro[ABA_CONTAS].iter_rows(min_row=2, values_only=True))
    assert len(contas) == 9
    assert contas[4][:6] == ("11047", "Máquinas e Equipamentos AME", 499400, 499399.97, 0.03,
                             SITUACAO_DIFERENCA_SEM_EXPLICACAO)
    assert livro[ABA_BAIXAS].max_row == 41
    resumo = [l for l in livro[ABA_RESUMO].iter_rows(values_only=True)]
    assert ("AME", "Ame - Cidade Alfa", None, None, None) in resumo
    assert any(l[0] and str(l[0]).startswith("Todas as contas aparecem") and l[1] == "OK"
               for l in resumo)


def test_gabarito_planilha_sem_opcionais_nao_tem_abas_de_bens(pasta_real):
    livro = load_workbook(_processar_real(pasta_real, com_opcionais=False).caminho_relatorio)
    assert livro.sheetnames == [ABA_RESUMO, ABA_CONTAS, ABA_DIFERENCAS, ABA_AVISOS]


def test_gabarito_previa_balancetes(pasta_real):
    previa = previa_balancetes([pasta_real / n for n in BALANCETES])
    assert previa.erro is None
    assert previa.descricao == "Ame - Cidade Alfa · agosto/2026 · 9 contas"


def test_processar_salva_na_pasta_escolhida(tmp_path):
    destino = tmp_path / "planilhas"
    destino.mkdir()
    resultado = processar_bens(arquivo_razao(tmp_path),
                               [arquivo_balancete(tmp_path, CONTAS_IMOBILIZADO)],
                               agora=AGORA, pasta_destino=destino)
    assert resultado.erro is None
    assert resultado.caminho_relatorio.parent == destino
    assert resultado.caminho_relatorio.name == "Conciliacao_imobilizado_2026-08_Ame_Cidade_Alfa_15h30.xlsx"


def test_processar_pasta_escolhida_que_nao_existe(tmp_path):
    resultado = processar_bens(arquivo_razao(tmp_path),
                               [arquivo_balancete(tmp_path, CONTAS_IMOBILIZADO)],
                               agora=AGORA, pasta_destino=tmp_path / "sumiu")
    assert resultado.erro and "não existe" in resultado.erro
    assert resultado.caminho_relatorio is None
    assert len(resultado.itens) == 2          # a conciliação foi feita; só não salvou
