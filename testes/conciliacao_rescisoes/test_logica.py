"""
Testes da Conciliação de Rescisões a pagar (ESPECIFICACAO seção 17).

Arquivos sintéticos com nomes inventados: razão imitando o Tasy (em .xlsx e no .xls de texto),
texto do PDF de eventos (o PDF é simulado: a leitura do texto das páginas é testada à parte) e a
planilha de controle do mês anterior. O gabarito com os arquivos reais é pulado se exemplos/ não existir.
"""

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook

import modulos.conciliacao_rescisoes.leitores as leitores
from modulos.conciliacao_rescisoes.processamento import (
    conferir_conjunto,
    numeros_principais,
    previa_controle,
    previa_eventos,
    previa_razao,
    processar_rescisoes,
)
from modulos.conciliacao_rescisoes.conciliador import nota_nome
from modulos.conciliacao_rescisoes.leitores import ler_controle, ler_eventos, ler_eventos_do_texto, ler_razao, nome_do_historico
from modulos.conciliacao_rescisoes.modelos import ORIGEM_NAO_ENCONTRADO, ORIGEM_PDF, ORIGEM_PENDENTE, LeituraEventos
from modulos.conciliacao_rescisoes.processar import unidade_para_arquivo
from modulos.conciliacao_rescisoes.relatorio_excel import (
    ABA_DIFERENTES,
    ABA_LISTA,
    ABA_NAO_ENCONTRADOS,
    ABA_PAGAMENTOS,
    ABA_RESUMO,
)

from testes.conciliacao_rescisoes.apoio_fornecedores import texto_tasy
from testes.conftest import PASTA_EXEMPLOS, pasta_exemplos

PASTA_RESCISOES = PASTA_EXEMPLOS / "conciliacao_rescisoes" / "Exemplos_Rescisoes"

D = Decimal
UNIDADE = "Fundação Teste de Misericórdia"


def planilha(pasta: Path, nome: str, linhas: list[list]) -> Path:
    livro = Workbook()
    for linha in linhas:
        livro.active.append(linha)
    caminho = pasta / nome
    livro.save(caminho)
    return caminho


# ---------------------------------------------------------------------
# Razão sintético
# ---------------------------------------------------------------------
JUDICIAL = ("Tribunal Regional Do Trabalho Da 15A. Região - Verbas rescisórias Bruno Souza Exemplo "
            "processo 00012345620265150001")
PAGAMENTOS = [
    ("Eduardo Lima Teste", 500.00),
    ("Ana Paula Teste", 100.00),
    ("Fernanda Costa Exemplo", 1000.00),          # PDF diz 300,00: valor diferente
    ("Gabriel Ribeiro Alves Modelo", 200.00),     # PDF abrevia: "GABRIEL R ALVES MODELO"
    (JUDICIAL, 50.00),                            # judicial: nome no meio do texto
    ("Daniel Rocha Barreto Modelo", 20.00),       # lista anterior: "BARRETTO"
    ("Igor Nunes Desconhecido", 33.00),           # em lugar nenhum
]
SALDO_ANTERIOR = 200.00
CREDITO = 1160.00                                 # PDF soma 1.150,00: diferença de 10,00


def _topo_razao(pagina):
    return [
        [None, UNIDADE] + [None] * 8 + ["Livro: 0", None, f"Página: {pagina}"],
        ["Razão"],
        [None, None, None, "Período:", datetime(2026, 6, 1), "até:", None, datetime(2026, 6, 30)],
        [None, "Data", "Histórico", None, None, None, "Lote", None, None, "Débitos", None, "Créditos", None,
         None, "Saldo"],
    ]


def _rodape_razao(pagina):
    return [[None, "Impresso em: 07/10/2026 16:12:40", None, f"Página: {pagina}", None, None, None, None, "USR",
             None, None, None, None, "WEXE002"]]


def linhas_razao(pagamentos=PAGAMENTOS, saldo_anterior=SALDO_ANTERIOR, credito=CREDITO, quebra_depois=None):
    saldo = saldo_anterior
    linhas = _topo_razao(1) + [[None, "20763 - 2.01.03.04.0002  Rescisões a pagar"],
                               [None, None, "Saldo anterior "] + [None] * 11 + [saldo]]
    for posicao, (nome, valor) in enumerate(pagamentos, start=1):
        saldo = round(saldo - valor, 2)
        historico = nome if nome.startswith("Tribunal") else \
            f"Pagamento de Rescisão conf. bordero n.  11154{posicao:02d} {nome}"
        linhas.append([None, datetime(2026, 6, 1 + posicao), historico, None, None, None, 70849, None, None,
                       valor, None, 0, None, None, saldo])
        if quebra_depois == posicao:
            # o Tasy repete o fim do nome no topo da página seguinte
            linhas += _rodape_razao(1) + _topo_razao(2) + [[None, None, " ".join(nome.split()[-2:])]]
    saldo = round(saldo + credito, 2)
    linhas.append([None, datetime(2026, 6, 30), "Líquido Rescisão 0626", None, None, None, 71112, None, None, 0,
                   None, credito, None, None, saldo])
    debitos = round(sum(v for _, v in pagamentos), 2)
    linhas.append([None, None, "Total - 20763 - 2.01.03.04.0002  Rescisões a pagar"] + [None] * 6
                  + [debitos, None, credito])
    linhas.append([None, f"Total ({len(pagamentos) + 1})"] + [None] * 7 + [debitos, None, credito])
    linhas += _rodape_razao(2)
    return linhas


# ---------------------------------------------------------------------
# PDF de eventos (texto das páginas)
# ---------------------------------------------------------------------
def _topo_pdf(pagina):
    return (f"0001 -FUNDAÇÃO TESTE DE MISER. Pág.: {pagina}\nEVENTOS 06/2026 C/IDENT\n"
            "Período: 06/2026 a 06/2026 Tipo: Cálculo Mensal\n"
            "Evento Colaborador SIT Competência Pagamento Referência Valor\n")


PAGINAS_PDF = [
    _topo_pdf(1)
    + "0256-Cred. Estouro do Mes\n"
      "26 OUTRA PESSOA QUALQUER 003 06/2026 06/07/2026 0,00 99,00\n"
      "Total de Colaboradores: 01 0,00 99,00\n"
      "0264-Liquido Rescisao\n"
      "101 EDUARDO LIMA TESTE 007 06/2026 06/07/2026 0,00 500,00\n"
      "102FERNANDA COSTA EXEMPLO 007 06/2026 06/07/2026 0,00 300,00\n"
      "FPRF404.OPE - 08/07/2026 - 14:54:02 FUNDAÇÃO TESTE\n1",
    _topo_pdf(2)
    + "103 GABRIEL R ALVES MODELO007 06/2026 06/07/2026 0,00 200,00\n"
      "104 HELENA DIAS FICTICIA 007 06/2026 06/07/2026 0,00 150,00\n"
      "Total de Colaboradores: 04 0,00 1.150,00\n"
      "0241-Reembolso Debito Afastado\n"
      "55 NAO ENTRA NA CONTA 002 06/2026 06/07/2026 0,00 10,00\n"
      "Total de Colaboradores: 01 0,00 10,00\n",
]


@pytest.fixture
def pdf_falso(tmp_path, monkeypatch):
    """Um arquivo que começa como PDF; o texto das páginas vem de PAGINAS_PDF."""
    caminho = tmp_path / "EVENTOS 062026.PDF"
    caminho.write_bytes(b"%PDF-1.4 teste")
    monkeypatch.setattr(leitores, "paginas_do_pdf", lambda _caminho: list(PAGINAS_PDF))
    return caminho


# ---------------------------------------------------------------------
# Lista do mês anterior (planilha de controle)
# ---------------------------------------------------------------------
PENDENTES = [
    (datetime(2026, 5, 1), "ANA PAULA TESTE", 100.00),
    (datetime(2026, 5, 1), "BRUNO SOUZA EXEMPLO", 50.00),
    ("  11/2022", "CARLA MENDES FICTICIA", 30.00),          # continua a pagar
    (datetime(2026, 4, 1), "DANIEL ROCHA BARRETTO MODELO", 20.00),
]


def arquivo_controle(pasta, pendentes=PENDENTES, nome="Rescisões a pagar.xlsx"):
    linhas = [[], ["Periodo", "Colaborador", "Valor"]] + [list(p) for p in pendentes]
    linhas += [[None, None, f"=SUM(C3:C{len(pendentes) + 2})"], [], [None, "COMPOSIÇÃO SALDOS"],
               [None, "Contabil", 999], [None, "ALGUEM - Falecido pago judicial mês 06", 5]]
    livro = Workbook()
    livro.active.title = "Planilha5"                       # aba extra antes da certa
    livro.active.append(["Periodo", "Colaborador", "Valor"])
    livro.active.append(["10/2025", "NAO E ESTA ABA", 1])
    aba = livro.create_sheet("Rescisões a pagar")
    for linha in linhas:
        aba.append(linha)
    caminho = pasta / nome
    livro.save(caminho)
    return caminho


# ---------------------------------------------------------------------
# Leitores
# ---------------------------------------------------------------------
def test_razao_xlsx_pagamentos_creditos_e_saldo(tmp_path):
    leitura = ler_razao(planilha(tmp_path, "Razão 062026.xlsx", linhas_razao(quebra_depois=6)))
    assert leitura.erro is None
    assert leitura.unidade == UNIDADE
    assert (leitura.inicio.month, leitura.fim.day) == (6, 30)
    assert leitura.saldo_anterior == D("200.00")
    assert [p.nome for p in leitura.pagamentos] == [
        "Eduardo Lima Teste", "Ana Paula Teste", "Fernanda Costa Exemplo", "Gabriel Ribeiro Alves Modelo",
        "Bruno Souza Exemplo", "Daniel Rocha Barreto Modelo", "Igor Nunes Desconhecido"]
    assert leitura.pagamentos[0].bordero == "1115401"
    assert leitura.total_pagamentos == D("1903.00")
    assert leitura.creditos == [("Líquido Rescisão 0626", D("1160.00"), date(2026, 6, 30))]
    assert leitura.saldo_final == D("-543.00")
    assert leitura.conta.startswith("20763")
    assert leitura.avisos == []


def test_razao_xls_de_texto_do_tasy(tmp_path):
    leitura = ler_razao(texto_tasy(tmp_path, "razao.xls", linhas_razao()))
    assert leitura.erro is None
    assert len(leitura.pagamentos) == 7
    assert leitura.saldo_final == D("-543.00")
    assert leitura.avisos == []


def test_razao_quebra_de_pagina_com_pedaco_novo_do_nome(tmp_path):
    linhas = linhas_razao(quebra_depois=1)
    linhas[linhas.index([None, None, "Lima Teste"])] = [None, None, "Sobrenome Cortado"]
    leitura = ler_razao(planilha(tmp_path, "r.xlsx", linhas))
    assert leitura.pagamentos[0].nome == "Eduardo Lima Teste Sobrenome Cortado"


def test_razao_que_nao_fecha_vira_atencao(tmp_path):
    linhas = linhas_razao()
    linhas[-4][14] = 1.0                              # último saldo impresso errado
    leitura = ler_razao(planilha(tmp_path, "r.xlsx", linhas))
    assert any("ATENÇÃO" in a.mensagem and "último saldo" in a.mensagem for a in leitura.avisos)


def test_nome_do_historico():
    assert nome_do_historico("Pagamento de Rescisão conf. bordero n.  1234567 Maria  Teste") == \
        ("Maria Teste", "1234567")
    assert nome_do_historico(JUDICIAL) == ("Bruno Souza Exemplo", "")
    assert nome_do_historico("Outro lançamento qualquer") == ("Outro lançamento qualquer", "")


def test_eventos_le_so_o_0264_atravessando_paginas():
    leitura = ler_eventos_do_texto(list(PAGINAS_PDF), LeituraEventos(arquivo="e.pdf"))
    assert leitura.erro is None
    assert (leitura.competencia.year, leitura.competencia.month) == (2026, 6)
    assert [(r.matricula, r.nome, r.valor) for r in leitura.rescisoes] == [
        ("101", "EDUARDO LIMA TESTE", D("500.00")), ("102", "FERNANDA COSTA EXEMPLO", D("300.00")),
        ("103", "GABRIEL R ALVES MODELO", D("200.00")), ("104", "HELENA DIAS FICTICIA", D("150.00"))]
    assert (leitura.quantidade_impressa, leitura.total_impresso) == (4, D("1150.00"))
    assert leitura.avisos == []


def test_eventos_titulo_no_singular():
    """Desde out/2026 o Tasy imprime "EVENTO 102026 C/IDENT 1676" (sem o S) no topo de cada página."""
    paginas = [p.replace("EVENTOS 06/2026 C/IDENT", "EVENTO 062026 C/IDENT 1676") for p in PAGINAS_PDF]
    leitura = ler_eventos_do_texto(paginas, LeituraEventos(arquivo="e.pdf"))
    assert leitura.erro is None
    assert len(leitura.rescisoes) == 4
    assert (leitura.quantidade_impressa, leitura.total_impresso) == (4, D("1150.00"))
    assert leitura.avisos == []      # o topo da página 2 não vira "linha do 0264 não reconhecida"


def test_eventos_nome_comprido_que_invade_a_coluna_sit():
    """O PDF mistura o fim do nome com o "007" ("MODELO TE0L07"): as letras voltam para o nome."""
    paginas = [_topo_pdf(1) + "0264-Liquido Rescisao\n"
               "105 IRENE SOUZA CAMPOS FICTICIA MODELO TE0L07 07/2026 06/08/2026 0,00 809,22\n"
               "106 JOAO TESTE 007 07/2026 06/08/2026 0,00 10,00\n"
               "Total de Colaboradores: 02 0,00 819,22\n"]
    leitura = ler_eventos_do_texto(paginas, LeituraEventos(arquivo="e.pdf"))
    assert [(r.matricula, r.nome, r.valor) for r in leitura.rescisoes] == [
        ("105", "IRENE SOUZA CAMPOS FICTICIA MODELO TEL", D("809.22")), ("106", "JOAO TESTE", D("10.00"))]
    assert leitura.avisos == []
    # pedaço sem exatamente 3 algarismos continua virando aviso (não inventa pessoa)
    ruim = [paginas[0].replace("TE0L07", "TE0L7")]
    assert any("não reconhecida" in a.mensagem
               for a in ler_eventos_do_texto(ruim, LeituraEventos(arquivo="e.pdf")).avisos)


def test_eventos_total_que_nao_bate_e_sem_0264():
    paginas = list(PAGINAS_PDF)
    paginas[1] = paginas[1].replace("1.150,00", "9.999,00")
    assert any("ATENÇÃO" in a.mensagem
               for a in ler_eventos_do_texto(paginas, LeituraEventos(arquivo="e.pdf")).avisos)
    sem = ler_eventos_do_texto([_topo_pdf(1) + "0256-Cred\nTotal de Colaboradores: 00 0,00 0,00"],
                               LeituraEventos(arquivo="e.pdf"))
    assert "0264" in sem.erro


def test_controle_acha_a_aba_certa_e_para_no_total(tmp_path):
    leitura = ler_controle(arquivo_controle(tmp_path))
    assert leitura.erro is None
    assert leitura.aba == "Rescisões a pagar"
    assert [(p.nome, p.valor) for p in leitura.pendentes] == [
        ("ANA PAULA TESTE", D("100.00")), ("BRUNO SOUZA EXEMPLO", D("50.00")),
        ("CARLA MENDES FICTICIA", D("30.00")), ("DANIEL ROCHA BARRETTO MODELO", D("20.00"))]
    assert leitura.pendentes[2].periodo == "  11/2022"
    assert leitura.total == D("200.00")


def test_arquivos_trocados(tmp_path, pdf_falso):
    razao = planilha(tmp_path, "r.xlsx", linhas_razao())
    controle = arquivo_controle(tmp_path)
    assert "Razão" in ler_controle(razao).erro
    assert "lista" in ler_razao(controle).erro.casefold() or "Rescisões a pagar" in ler_razao(controle).erro
    assert "PDF" in ler_razao(pdf_falso).erro
    assert "Razão" in ler_eventos(razao).erro


# ---------------------------------------------------------------------
# Nomes
# ---------------------------------------------------------------------
def test_nota_nome():
    assert nota_nome("Maria José Teste", "MARIA JOSE TESTE") == 1.0
    assert nota_nome("Marina Lopes de Castro Neves", "MARINA LOPES CASTRO DE NEVES") == 1.0   # "de" ignorado
    assert nota_nome("Clara Barretto Lima Modelo", "CLARA BARRETO LIMA MODELO") >= 0.85
    assert nota_nome("Olga Antunes Prado Modelo", "OLGA ANTUNES PRADO") >= 0.85        # sobrenome a mais
    assert nota_nome("Paulo Henrique Ramos Teixeira", "PAULO HENRIQUE R TEIXEIRA") >= 0.85   # letra no lugar
    assert nota_nome("Paula da Silva", "PAULA REGINA DE SOUZA SILVA") < 0.85            # comum demais
    assert nota_nome("Camila Exemplo", "CARLA EXEMPLO") == 0.0                             # outro primeiro nome


# ---------------------------------------------------------------------
# processar_rescisoes
# ---------------------------------------------------------------------
@pytest.fixture
def tres_arquivos(tmp_path, pdf_falso):
    return planilha(tmp_path, "Razão 062026.xlsx", linhas_razao()), pdf_falso, arquivo_controle(tmp_path)


def test_processar_sintetico(tres_arquivos, tmp_path):
    resultado = processar_rescisoes(*tres_arquivos)
    assert resultado.erro is None
    assert [(b.pagamento.nome, b.origem) for b in resultado.baixas] == [
        ("Eduardo Lima Teste", ORIGEM_PDF), ("Ana Paula Teste", ORIGEM_PENDENTE),
        ("Fernanda Costa Exemplo", ORIGEM_PDF), ("Gabriel Ribeiro Alves Modelo", ORIGEM_PDF),
        ("Bruno Souza Exemplo", ORIGEM_PENDENTE), ("Daniel Rocha Barreto Modelo", ORIGEM_PENDENTE),
        ("Igor Nunes Desconhecido", ORIGEM_NAO_ENCONTRADO)]
    assert [(b.pagamento.nome, b.diferenca) for b in resultado.valores_diferentes] == [
        ("Fernanda Costa Exemplo", D("-700.00"))]
    assert [(i.nome, i.valor, i.origem) for i in resultado.lista_nova] == [
        ("CARLA MENDES FICTICIA", D("30.00"), ORIGEM_PENDENTE), ("HELENA DIAS FICTICIA", D("150.00"), ORIGEM_PDF)]
    numeros = numeros_principais(resultado)
    assert (numeros.achados_pdf, numeros.achados_lista, numeros.nao_encontrados, numeros.valores_diferentes,
            numeros.lista_nova) == (3, 3, 1, 1, 2)
    assert resultado.saldo_final == D("-543.00")
    assert not any("ATENÇÃO" in a.mensagem for a in resultado.avisos)     # a prova fechou
    assert resultado.caminho_relatorio.name == "Conciliacao_Rescisoes_FundacaoTesteDeMisericordia_jun2026.xlsx"
    assert resultado.caminho_relatorio.parent == tmp_path


def test_planilha_abas_formulas_e_lista_nova_relida(tres_arquivos):
    resultado = processar_rescisoes(*tres_arquivos)
    livro = load_workbook(resultado.caminho_relatorio)
    assert livro.sheetnames == [ABA_RESUMO, ABA_PAGAMENTOS, ABA_DIFERENTES, ABA_NAO_ENCONTRADOS, ABA_LISTA]
    pagamentos = livro[ABA_PAGAMENTOS]
    assert pagamentos["A3"].value == "Data" and pagamentos["H4"].value == "=G4-D4"
    assert pagamentos["E10"].value == ORIGEM_NAO_ENCONTRADO and pagamentos["H10"].value == "—"
    assert pagamentos["D12"].value == "=SUM(D4:D10)"
    diferentes = livro[ABA_DIFERENTES]
    assert (diferentes["C4"].value, diferentes["H4"].value) == ("Fernanda Costa Exemplo", "=F4-G4")
    assert livro[ABA_NAO_ENCONTRADOS]["C4"].value == "Igor Nunes Desconhecido"
    lista = livro[ABA_LISTA]
    assert [c.value for c in lista[2]] == ["Periodo", "Colaborador", "Valor", "Origem"]
    assert lista["C5"].value == "=SUM(C3:C4)"
    resumo = livro[ABA_RESUMO]
    assert any(isinstance(c.value, str) and c.value == "Diferença sem explicação" for c in resumo["B"])
    # a lista nova serve de "lista do mês anterior" no mês seguinte
    relida = ler_controle(resultado.caminho_relatorio)
    assert (relida.aba, [(p.nome, p.valor) for p in relida.pendentes]) == (
        ABA_LISTA, [("CARLA MENDES FICTICIA", D("30.00")), ("HELENA DIAS FICTICIA", D("150.00"))])
    assert relida.pendentes[0].periodo == "  11/2022"


def test_lista_gerada_tem_composicao_da_diferenca_e_serve_no_mes_seguinte(tres_arquivos, tmp_path, pdf_falso):
    """A aba "Rescisões a pagar" sai com a composição de "saldo do razão − lista" abaixo do total; usada como
    lista do mês anterior, a composição é lida de volta, entra na conferência do saldo e continua valendo."""
    from modulos.conciliacao_rescisoes.modelos import ROTULO_COMPOSICAO
    from modulos.conciliacao_rescisoes.processar import composicao_da_diferenca
    junho = processar_rescisoes(*tres_arquivos)
    # saldo final −543,00 − lista nova 180,00 = −723,00 = 10,00 (créditos − PDF) − 700,00 (valor diferente) − 33,00
    assert [v for _, v in junho.composicao_nova] == [D("10.00"), D("-700.00"), D("-33.00")]
    assert junho.composicao_nova[1][0].startswith("Fernanda Costa Exemplo - pago R$ 1.000,00 em ")
    assert junho.composicao_nova[2][0].startswith("Igor Nunes Desconhecido - pago em ")
    aba = load_workbook(junho.caminho_relatorio)[ABA_LISTA]
    assert (aba["B7"].value, aba["B11"].value, aba["C11"].value) == (ROTULO_COMPOSICAO, "Total da composição",
                                                                     "=SUM(C8:C10)")
    assert aba["B12"].value.startswith("Saldo do razão em 30/06/2026") and aba["C12"].value == "=C5+C11"

    relida = ler_controle(junho.caminho_relatorio)
    assert (relida.total, relida.total_composicao) == (D("180.00"), D("-723.00"))
    assert [t for t, _ in relida.rodape] == [t for t, _ in junho.composicao_nova]   # só os itens (regra c)

    # mês seguinte: saldo anterior = saldo final de junho; paga a Carla (lista) e mais 5,00 ao Igor (composição)
    pasta = tmp_path / "julho"
    pasta.mkdir()
    razao = planilha(pasta, "Razão.xlsx", linhas_razao(
        [("Carla Mendes Ficticia", 30.00), ("Igor Nunes Desconhecido", 5.00)], saldo_anterior=-543.00,
        credito=1150.00))
    julho = processar_rescisoes(razao, pdf_falso, junho.caminho_relatorio, pasta_destino=pasta)
    assert julho.erro is None
    assert not any("ATENÇÃO" in a.mensagem for a in julho.avisos)    # saldo anterior = lista + composição
    igor = julho.baixas_de(ORIGEM_NAO_ENCONTRADO)
    assert [(b.pagamento.valor, b.regra) for b in igor] == [(D("5.00"), "c")]
    assert composicao_da_diferenca(julho).sem_explicacao == 0
    # os itens de junho continuam, e entra o pagamento novo do Igor
    assert [v for _, v in julho.composicao_nova] == [D("10.00"), D("-700.00"), D("-33.00"), D("-5.00")]
    assert sum((v for _, v in julho.composicao_nova), D(0)) == julho.saldo_final - julho.total_lista_nova
    resumo = [c.value for c in load_workbook(julho.caminho_relatorio)[ABA_RESUMO]["B"]]
    assert "(+) Composição da diferença da lista anterior (rodapé)" in resumo


def test_lista_anterior_com_composicao_que_nao_bate_avisa(tres_arquivos, tmp_path, pdf_falso):
    junho = processar_rescisoes(*tres_arquivos)
    razao = planilha(tmp_path, "Razão julho.xlsx", linhas_razao([("Carla Mendes Ficticia", 30.00)],
                                                               saldo_anterior=100.00, credito=1150.00))
    julho = processar_rescisoes(razao, pdf_falso, junho.caminho_relatorio)
    assert any("não bate com o total da lista do mês anterior com a composição da diferença "
               "(180,00 + -723,00 = -543,00)" in a.mensagem for a in julho.avisos)


def test_processar_avisa_mes_e_saldo_anterior(tmp_path, pdf_falso):
    linhas = linhas_razao(saldo_anterior=999.0)
    resultado = processar_rescisoes(planilha(tmp_path, "r.xlsx", linhas), pdf_falso, arquivo_controle(tmp_path))
    assert resultado.erro is None
    assert any("saldo anterior" in a.mensagem and "ATENÇÃO" in a.mensagem for a in resultado.avisos)
    assert any("saldo anterior" in nota for nota in resultado.notas)


def test_processar_arquivo_errado_e_pasta(tres_arquivos, tmp_path):
    razao, eventos, controle = tres_arquivos
    trocado = processar_rescisoes(controle, eventos, razao)
    assert trocado.erro and trocado.caminho_relatorio is None
    sumiu = processar_rescisoes(razao, eventos, controle, pasta_destino=tmp_path / "nao_existe")
    assert sumiu.erro and "não existe" in sumiu.erro
    destino = tmp_path / "saida"
    destino.mkdir()
    primeiro = processar_rescisoes(razao, eventos, controle, pasta_destino=destino)
    segundo = processar_rescisoes(razao, eventos, controle, pasta_destino=destino)
    assert primeiro.caminho_relatorio.parent == destino
    assert segundo.caminho_relatorio.name.endswith("_jun2026_2.xlsx")


def test_previas(tres_arquivos):
    razao, eventos, controle = tres_arquivos
    assert previa_razao(razao).descricao == \
        "Fundação Teste de Misericórdia · jun/2026 · 7 pagamentos · saldo final R$ -543,00"
    assert previa_eventos(eventos).descricao == "0264 · jun/2026 · 4 pessoas · R$ 1.150,00"
    assert previa_controle(controle).descricao == "aba \"Rescisões a pagar\" · 4 rescisões · R$ 200,00"
    assert conferir_conjunto(razao, eventos, controle).avisos == []


def test_nome_da_unidade_no_arquivo():
    assert unidade_para_arquivo("Fundação Hospital Exemplo") == "HospitalExemplo"
    assert unidade_para_arquivo("AME - Cidade Delta (Fund. Hospital Exemplo)") == "CidadeDelta"


# ---------------------------------------------------------------------
# Gabarito: Hospital Exemplo, junho/2026 (ESPECIFICACAO seção 17.5)
# ---------------------------------------------------------------------
@pytest.fixture
def arquivos_reais():
    pasta = PASTA_RESCISOES / "jun2026"
    if not pasta.exists():
        pytest.skip("exemplos/Exemplos_Rescisoes não existe")
    return (pasta / "Razão 062026.xlsx", pasta / "EVENTOS 062026 COM IDENT F010405.PDF",
            pasta / "Rescisões a pagar.xlsx")


def test_gabarito_hospital_exemplo_jun2026(arquivos_reais, tmp_path):
    """Só o PDF mensal. Regra corrigida (out/2026): os 10 que estavam na lista de maio com o valor exato pago
    casam com a lista (não com o novo cálculo do PDF de junho) — nenhum valor diferente."""
    resultado = processar_rescisoes(*arquivos_reais, pasta_destino=tmp_path)
    assert resultado.erro is None
    assert (resultado.saldo_anterior, resultado.total_creditos, resultado.total_pagamentos, resultado.saldo_final) == \
        (D("104350.71"), D("222585.59"), D("194853.32"), D("132082.98"))
    assert (resultado.total_pdf, resultado.total_controle) == (D("222394.99"), D("104350.71"))
    numeros = numeros_principais(resultado)
    assert (numeros.achados_pdf, numeros.achados_lista, numeros.nao_encontrados, numeros.valores_diferentes,
            numeros.lista_nova) == (40, 49, 3, 0, 135)
    assert sum(b.pagamento.valor for b in resultado.baixas_de(ORIGEM_NAO_ENCONTRADO)) == D("273.91")
    assert resultado.valores_diferentes == []
    assert resultado.total_lista_nova == D("132166.29")
    assert sum(1 for b in resultado.baixas if b.nota is not None and b.nota < 1) == 6
    assert not any("ATENÇÃO" in a.mensagem for a in resultado.avisos)
    assert resultado.caminho_relatorio.name == "Conciliacao_Rescisoes_HospitalExemplo_jun2026.xlsx"
    relida = ler_controle(resultado.caminho_relatorio)
    assert (len(relida.pendentes), relida.total) == (135, D("132166.29"))
    # composição da diferença no rodapé: lista + (−83,31) = saldo final de junho (o saldo anterior de julho)
    assert (relida.total_composicao, relida.total + relida.total_composicao) == (D("-83.31"), D("132082.98"))


# ---------------------------------------------------------------------
# Observação dos não encontrados (regras a, b, c, d)
# ---------------------------------------------------------------------
def _pagamento(nome, valor, dia=10, bordero="900"):
    from datetime import date

    from modulos.conciliacao_rescisoes.modelos import Pagamento
    return Pagamento(data=date(2026, 6, dia), historico=f"Pagamento de Rescisão conf. bordero n. {bordero} {nome}",
                     nome=nome, valor=D(valor), bordero=bordero)


def test_observacao_regras_a_b_c_d():
    from modulos.conciliacao_rescisoes.conciliador import conciliar
    from modulos.conciliacao_rescisoes.modelos import (REGRA_JA_BAIXADA, REGRA_PDF_FORA_DO_MES, REGRA_RODAPE, REGRA_SEM_RESCISAO,
                                   Pendente, RescisaoMes)
    from datetime import date
    pagamentos = [
        _pagamento("Paula Ramos Teste", "800.00", dia=5, bordero="111"),      # baixa a rescisão do PDF
        _pagamento("Paula Ramos Teste", "40.00", dia=28, bordero="222"),      # já baixada (PDF) → a
        _pagamento("Otavio Prado Exemplo", "60.00", dia=6, bordero="333"),    # baixa a pendente
        _pagamento("Otavio Prado Exemplo", "5.00", dia=29, bordero="444"),    # já baixada (lista) → a
        _pagamento("Vera Lucia Modelo", "25.00"),                             # só num PDF fora do mês → b
        _pagamento("Joana Lemos Ficticia", "12.00"),                          # rodapé → c
        _pagamento("Rui Sem Par Nenhum", "9.00"),                             # → d
    ]
    rescisoes = [RescisaoMes("1", "PAULA RAMOS TESTE", D("800.00"), pdf="PDF mensal")]
    pendentes = [Pendente("05/2026", "OTAVIO PRADO EXEMPLO", D("60.00"))]
    fora = [RescisaoMes("9", "VERA LUCIA MODELO", D("25.00"), data_pagamento=date(2026, 7, 15),
                        arquivo="RESC COMPL 1507.PDF", pdf="PDF complementar 15/07")]
    rodape = [("COMPOSIÇÃO DA DIFERENÇA", None), ("Contabil", D("999")),
              ("JOANA LEMOS FICTICIA - Calculo 1635 mês 06", D("-12.00"))]
    baixas = conciliar(pagamentos, rescisoes, pendentes, "06/2026", rodape, fora_do_mes=fora).baixas
    nao = [b for b in baixas if b.origem == ORIGEM_NAO_ENCONTRADO]
    assert [b.regra for b in nao] == [REGRA_JA_BAIXADA, REGRA_JA_BAIXADA, REGRA_PDF_FORA_DO_MES, REGRA_RODAPE,
                                      REGRA_SEM_RESCISAO]
    assert nao[0].observacao == "Rescisão de R$ 800,00 (PDF mensal) já baixada pelo pagamento de 05/06, borderô 111."
    assert nao[1].observacao == ("Rescisão de R$ 60,00 (lista anterior) já baixada pelo pagamento de 06/06, "
                                 "borderô 333.")
    assert nao[2].observacao == ("Consta no PDF RESC COMPL 1507.PDF (pagamento 15/07, R$ 25,00), não lançado no "
                                 "razão deste mês.")
    assert nao[3].observacao == ("Consta na composição da diferença da lista anterior: "
                                 "'JOANA LEMOS FICTICIA - Calculo 1635 mês 06' (R$ -12,00).")
    assert nao[4].observacao == "Sem rescisão correspondente."
    # as observações não mudam nenhum casamento
    assert [b.origem for b in baixas[:3:2]] == [ORIGEM_PDF, ORIGEM_PENDENTE]


def test_valor_exato_na_lista_anterior_vence_o_nome_no_pdf():
    """A pessoa está na lista de maio com o valor exato pago e no PDF de junho com outro valor (novo cálculo):
    baixa a de maio; a de junho vai para a lista nova e não há valor diferente."""
    from modulos.conciliacao_rescisoes.conciliador import conciliar
    from modulos.conciliacao_rescisoes.modelos import Pendente, RescisaoMes
    pagamentos = [_pagamento("Rosa Maria Teste", "3514.62")]
    rescisoes = [RescisaoMes("1", "ROSA MARIA TESTE", D("726.77"), pdf="PDF mensal")]
    pendentes = [Pendente("05/2026", "ROSA MARIA TESTE", D("3514.62"))]
    resultado = conciliar(pagamentos, rescisoes, pendentes, "06/2026")
    baixa = resultado.baixas[0]
    assert (baixa.origem, baixa.diferenca) == (ORIGEM_PENDENTE, D("0.00"))
    assert [(i.nome, i.valor, i.origem) for i in resultado.lista_nova] == [("ROSA MARIA TESTE", D("726.77"), ORIGEM_PDF)]
    # sem valor igual em lugar nenhum: continua PDF primeiro (e vira "valor diferente")
    resultado = conciliar([_pagamento("Rosa Maria Teste", "100.00")], rescisoes, pendentes, "06/2026")
    assert (resultado.baixas[0].origem, resultado.baixas[0].diferenca) == (ORIGEM_PDF, D("626.77"))
    # valor igual nos dois: a lista anterior (rescisão mais antiga) e tolerância de R$ 0,01
    iguais = [RescisaoMes("1", "ROSA MARIA TESTE", D("50.01"), pdf="PDF mensal")]
    resultado = conciliar([_pagamento("Rosa Maria Teste", "50.00")], iguais,
                          [Pendente("04/2026", "ROSA MARIA TESTE", D("50.00"))], "06/2026")
    assert resultado.baixas[0].origem == ORIGEM_PENDENTE


def test_nome_exato_vence_nome_parecido_mesmo_com_valor_igual():
    """"Clara da Silva" casa com CLARA DA SILVA (lista, nome exato), não com CLARA REGINA DE MOURA SILVA (PDF,
    nome parecido), mesmo o parecido tendo o valor igual."""
    from modulos.conciliacao_rescisoes.conciliador import conciliar
    from modulos.conciliacao_rescisoes.modelos import Pendente, RescisaoMes
    rescisoes = [RescisaoMes("1", "CLARA REGINA DE MOURA SILVA", D("107.05"), pdf="PDF mensal")]
    pendentes = [Pendente("05/2026", "CLARA DA SILVA", D("90.00"))]
    resultado = conciliar([_pagamento("Clara da Silva", "107.05")], rescisoes, pendentes, "06/2026")
    assert (resultado.baixas[0].origem, resultado.baixas[0].nome_encontrado) == (ORIGEM_PENDENTE, "CLARA DA SILVA")


def test_pagamento_sem_valor_igual_nao_rouba_a_rescisao_de_valor_exato():
    """Dois pagamentos da mesma pessoa: o de valor exato fica com a rescisão de mesmo valor, qualquer que seja a ordem."""
    from modulos.conciliacao_rescisoes.conciliador import conciliar
    from modulos.conciliacao_rescisoes.modelos import RescisaoMes
    rescisoes = [RescisaoMes("1", "TIAGO NERY TESTE", D("40.00"), pdf="PDF complementar 29/06"),
                 RescisaoMes("1", "TIAGO NERY TESTE", D("900.00"), pdf="PDF mensal")]
    pagamentos = [_pagamento("Tiago Nery Teste", "850.00", dia=3), _pagamento("Tiago Nery Teste", "40.00", dia=20)]
    baixas = conciliar(pagamentos, rescisoes, [], "06/2026").baixas
    assert [(b.pagamento.valor, b.rescisao.valor) for b in baixas] == [(D("850.00"), D("900.00")),
                                                                       (D("40.00"), D("40.00"))]


def test_controle_le_o_rodape_a_parte_e_nao_quebra_sem_ele(tmp_path):
    leitura = ler_controle(arquivo_controle(tmp_path))
    assert len(leitura.pendentes) == 4                                  # o rodapé não entra na lista
    assert ("ALGUEM - Falecido pago judicial mês 06", D("5.00")) in leitura.rodape
    assert ("COMPOSIÇÃO SALDOS", None) in leitura.rodape
    sem_rodape = tmp_path / "sem"
    sem_rodape.mkdir()
    caminho = planilha(sem_rodape, "lista.xlsx", [["Periodo", "Colaborador", "Valor"], ["05/2026", "X Y Z", 1]])
    leitura = ler_controle(caminho)
    assert (leitura.erro, leitura.rodape, len(leitura.pendentes)) == (None, [], 1)


def test_planilha_observacao_e_linhas_novas_do_resumo(tres_arquivos):
    resultado = processar_rescisoes(*tres_arquivos)
    livro = load_workbook(resultado.caminho_relatorio)
    nao = livro[ABA_NAO_ENCONTRADOS]
    assert nao["F3"].value == "Observação"
    assert (nao["C4"].value, nao["F4"].value) == ("Igor Nunes Desconhecido", "Sem rescisão correspondente.")
    rotulos = [c.value for c in livro[ABA_RESUMO]["B"] if isinstance(c.value, str)]
    assert "   soma dos pagamentos complementares (regra 1a)" in rotulos
    assert "   diferença restante" in rotulos


def test_gabarito_jun2026_observacoes(arquivos_reais, tmp_path):
    """Só o PDF mensal: os 3 não encontrados ganham a explicação certa (os complementares, regra a)."""
    from modulos.conciliacao_rescisoes.modelos import REGRA_COMPLEMENTAR_PDF, REGRA_RODAPE
    resultado = processar_rescisoes(*arquivos_reais, pasta_destino=tmp_path)
    numeros = numeros_principais(resultado)
    assert (numeros.achados_pdf, numeros.achados_lista, numeros.nao_encontrados, numeros.valores_diferentes,
            numeros.lista_nova, resultado.total_lista_nova) == (40, 49, 3, 0, 135, D("132166.29"))
    regras = {b.pagamento.valor: b for b in resultado.baixas_de(ORIGEM_NAO_ENCONTRADO)}
    assert {valor: b.regra for valor, b in regras.items()} == {
        D("66.96"): REGRA_COMPLEMENTAR_PDF, D("123.64"): REGRA_COMPLEMENTAR_PDF, D("83.31"): REGRA_RODAPE}
    assert regras[D("66.96")].observacao == \
        "Rescisão de R$ 2.065,19 (PDF mensal) já baixada pelo pagamento de 24/06, borderô 1118860."
    assert regras[D("123.64")].observacao == \
        "Rescisão de R$ 2.504,96 (PDF mensal) já baixada pelo pagamento de 10/06, borderô 1116650."
    assert regras[D("83.31")].observacao.endswith("(R$ -83,31).")
    complementares = sum(b.pagamento.valor for b in resultado.complementares)
    assert complementares == D("190.60") == resultado.total_creditos - resultado.total_pdf
    assert any("corresponde aos 2 pagamento(s) complementar(es)" in nota for nota in resultado.notas)


# ---------------------------------------------------------------------
# Vários PDFs de eventos: mensal + complementares (escolha pela soma × créditos do razão)
# ---------------------------------------------------------------------
def _topo_pdf_tipo(tipo):
    return ("0001 -FUNDAÇÃO TESTE DE MISER. Pág.: 1\nEVENTOS 06/2026 C/IDENT\n"
            f"Período: 06/2026 a 06/2026 Tipo: {tipo}\n"
            "Evento Colaborador SIT Competência Pagamento Referência Valor\n")


PAGINAS_COMPLEMENTAR_2906 = [_topo_pdf_tipo("Complementar Rescisão")
                             + "0264-Liquido Rescisao\n"
                               "101 EDUARDO LIMA TESTE 007 06/2026 29/06/2026 0,00 10,00\n"
                               "Total de Colaboradores: 01 0,00 10,00\n"]
PAGINAS_COMPLEMENTAR_1507 = [_topo_pdf_tipo("Complementar Rescisão")
                             + "0264-Liquido Rescisao\n"
                               "120 JULIA PRADO FICTICIA 007 06/2026 15/07/2026 0,00 40,00\n"
                               "Total de Colaboradores: 01 0,00 40,00\n"]
# o razão ganha o pagamento complementar do Eduardo (10,00); os créditos (1.160,00) = mensal + complementar 29/06
PAGAMENTOS_COM_COMPLEMENTAR = PAGAMENTOS + [("Eduardo Lima Teste", 10.00)]


@pytest.fixture
def pdfs_falsos(tmp_path, monkeypatch):
    """Três PDFs simulados (conteúdos diferentes) e uma cópia idêntica do complementar de 29/06."""
    paginas = {"EVENTOS 062026.PDF": PAGINAS_PDF, "RESC COMPL 2906.PDF": PAGINAS_COMPLEMENTAR_2906,
               "RESC COMPL 1507.PDF": PAGINAS_COMPLEMENTAR_1507,
               "copia RESC COMPL 2906.PDF": PAGINAS_COMPLEMENTAR_2906}
    caminhos = []
    for nome in paginas:
        caminho = tmp_path / nome
        conteudo = nome.replace("copia ", "")           # a cópia tem os mesmos bytes do original
        caminho.write_bytes(b"%PDF-1.4 " + conteudo.encode())
        caminhos.append(caminho)
    monkeypatch.setattr(leitores, "paginas_do_pdf", lambda caminho: list(paginas[Path(caminho).name]))
    return caminhos


def test_eventos_guarda_tipo_data_de_pagamento_e_rotulo():
    mensal = ler_eventos_do_texto(list(PAGINAS_PDF), LeituraEventos(arquivo="m.pdf"))
    complementar = ler_eventos_do_texto(list(PAGINAS_COMPLEMENTAR_2906), LeituraEventos(arquivo="c.pdf"))
    assert (mensal.tipo, mensal.rotulo, str(mensal.data_pagamento)) == ("Cálculo Mensal", "PDF mensal", "2026-07-06")
    assert (complementar.tipo, complementar.rotulo) == ("Complementar Rescisão", "PDF complementar 29/06")
    rescisao = complementar.rescisoes[0]
    assert (rescisao.nome, rescisao.valor, str(rescisao.data_pagamento), rescisao.tipo, rescisao.arquivo) == (
        "EDUARDO LIMA TESTE", D("10.00"), "2026-06-29", "Complementar Rescisão", "c.pdf")


def test_escolher_pdfs_uma_nenhuma_ou_varias_combinacoes():
    from modulos.conciliacao_rescisoes.modelos import ESCOLHA_COMBINACAO, ESCOLHA_NENHUMA, ESCOLHA_UNICO, ESCOLHA_VARIAS
    from modulos.conciliacao_rescisoes.processar import escolher_pdfs

    def pdf(nome, tipo, valor, dia):
        texto = (_topo_pdf_tipo(tipo) + "0264-Liquido Rescisao\n"
                 f"1 PESSOA TESTE {nome} 007 06/2026 {dia}/06/2026 0,00 {valor}\n"
                 f"Total de Colaboradores: 01 0,00 {valor}\n")
        return ler_eventos_do_texto([texto], LeituraEventos(arquivo=f"{nome}.pdf"))

    mensal, comp_a, comp_b = (pdf("M", "Cálculo Mensal", "100,00", "30"),
                              pdf("A", "Complementar Rescisão", "10,00", "20"),
                              pdf("B", "Complementar Rescisão", "7,00", "25"))
    escolha = escolher_pdfs([comp_b, comp_a, mensal], D("110.01"))       # tolerância de R$ 0,01
    assert escolha.situacao == ESCOLHA_COMBINACAO
    assert [l.arquivo for l in escolha.usados] == ["M.pdf", "A.pdf"]
    assert [l.arquivo for l in escolha.fora] == ["B.pdf"]
    assert escolher_pdfs([mensal, comp_a, comp_b], D("500.00")).situacao == ESCOLHA_NENHUMA
    comp_c = pdf("C", "Complementar Rescisão", "10,00", "21")             # mesmo valor do A: duas combinações
    escolha = escolher_pdfs([mensal, comp_a, comp_c], D("110.00"))
    assert escolha.situacao == ESCOLHA_VARIAS and len(escolha.usados) == 3 and escolha.fora == []
    assert escolher_pdfs([mensal], D("1.00")).situacao == ESCOLHA_UNICO


def test_processar_varios_pdfs_usa_so_os_que_batem_com_os_creditos(tmp_path, pdfs_falsos):
    razao = planilha(tmp_path, "Razão 062026.xlsx", linhas_razao(PAGAMENTOS_COM_COMPLEMENTAR))
    resultado = processar_rescisoes(razao, pdfs_falsos, arquivo_controle(tmp_path))
    assert resultado.erro is None
    assert [l.rotulo for l in resultado.pdfs_usados] == ["PDF mensal", "PDF complementar 29/06"]
    assert [l.rotulo for l in resultado.pdfs_fora] == ["PDF complementar 15/07"]
    assert resultado.total_pdf == resultado.total_creditos == D("1160.00")
    # o pagamento complementar do Eduardo é achado no PDF complementar; o grande, no mensal
    eduardo = [(b.pagamento.valor, b.onde_achado) for b in resultado.baixas if b.pagamento.nome == "Eduardo Lima Teste"]
    assert eduardo == [(D("500.00"), "PDF mensal"), (D("10.00"), "PDF complementar 29/06")]
    # o PDF de 15/07 não entra no casamento nem na lista nova
    assert all("JULIA" not in i.nome for i in resultado.lista_nova)
    assert [(i.nome, i.texto_origem) for i in resultado.lista_nova] == [
        ("CARLA MENDES FICTICIA", ORIGEM_PENDENTE), ("HELENA DIAS FICTICIA", "PDF mensal")]
    assert [b.pagamento.nome for b in resultado.baixas_de(ORIGEM_NAO_ENCONTRADO)] == ["Igor Nunes Desconhecido"]
    assert any("repetido, ignorado: copia RESC COMPL 2906.PDF" in a.mensagem for a in resultado.avisos)
    assert not any("ATENÇÃO" in a.mensagem for a in resultado.avisos)
    assert any("não foi lançado no razão deste mês" in nota for nota in resultado.notas)

    livro = load_workbook(resultado.caminho_relatorio)
    aba = livro[ABA_RESUMO]
    resumo = [(c.value, aba.cell(row=c.row, column=5).value) for c in aba["B"] if isinstance(c.value, str)]
    rotulos = [r for r, _ in resumo]
    usados = [(r, v) for r, v in resumo if r.startswith("PDF usado:")]
    assert usados == [("PDF usado: EVENTOS 062026.PDF — Cálculo Mensal — pagamento 06/07/2026", 1150),
                      ("PDF usado: RESC COMPL 2906.PDF — Complementar Rescisão — pagamento 29/06/2026", 10)]
    assert "Total dos PDFs usados (0264 – Líquido Rescisão)" in rotulos
    assert "Diferença: créditos do razão − PDFs" in rotulos
    assert "PDFs não lançados no razão deste mês (provavelmente do mês seguinte)" in rotulos
    assert "RESC COMPL 1507.PDF — Complementar Rescisão — pagamento 15/07/2026" in rotulos
    assert "PDF complementar 29/06" in rotulos                          # contagem por PDF em "Pagamentos do mês"
    assert "Total do 0264 – Líquido Rescisão (PDF)" not in rotulos
    origens = [livro[ABA_PAGAMENTOS].cell(row=r, column=5).value for r in range(4, 4 + len(resultado.baixas))]
    assert origens.count("PDF complementar 29/06") == 1 and origens.count("PDF mensal") == 3
    assert [livro[ABA_LISTA].cell(row=r, column=4).value for r in (3, 4)] == [ORIGEM_PENDENTE, "PDF mensal"]


def test_processar_varios_pdfs_sem_combinacao_que_bata_usa_todos_e_avisa(tmp_path, pdfs_falsos):
    from modulos.conciliacao_rescisoes.modelos import ESCOLHA_NENHUMA
    razao = planilha(tmp_path, "r.xlsx", linhas_razao(PAGAMENTOS_COM_COMPLEMENTAR, credito=2000.00))
    resultado = processar_rescisoes(razao, pdfs_falsos[:3], arquivo_controle(tmp_path))
    assert resultado.erro is None
    assert resultado.escolha_pdfs == ESCOLHA_NENHUMA
    assert len(resultado.pdfs_usados) == 3 and resultado.pdfs_fora == []
    assert resultado.total_pdf == D("1200.00")
    atencao = [a.mensagem for a in resultado.avisos if "nenhuma combinação" in a.mensagem]
    assert atencao and "Diferença créditos − PDFs: R$ 800,00" in atencao[0]
    assert any(i.nome == "JULIA PRADO FICTICIA" for i in resultado.lista_nova)   # usado: entra na lista


def test_previa_e_conjunto_com_varios_pdfs(tmp_path, pdfs_falsos):
    previa = previa_eventos(pdfs_falsos)
    assert previa.descricao == ("3 PDFs · 0264 · jun/2026 · PDF mensal R$ 1.150,00 + PDF complementar 29/06 "
                                "R$ 10,00 + PDF complementar 15/07 R$ 40,00 · total R$ 1.200,00")
    assert any("repetido, ignorado" in a for a in previa.avisos)
    razao = planilha(tmp_path, "r.xlsx", linhas_razao(PAGAMENTOS_COM_COMPLEMENTAR))
    conjunto = conferir_conjunto(razao, pdfs_falsos, arquivo_controle(tmp_path))
    assert conjunto.descricao == ("entram no mês: PDF mensal + PDF complementar 29/06 (= créditos do razão "
                                  "R$ 1.160,00); fora (provavelmente do mês seguinte): PDF complementar 15/07")


@pytest.fixture
def pdfs_reais_jun2026():
    pasta = PASTA_RESCISOES / "jun2026"
    nomes = ["EVENTOS 062026 COM IDENT F010405.PDF", "EVENTOS 062026 COM IDENT RESC COMPL.PDF",
             "EVENTOS COM IDENT 062026.PDF"]
    if not all((pasta / n).exists() for n in nomes):
        pytest.skip("PDFs complementares de jun/2026 não estão em exemplos/")
    return pasta, [pasta / n for n in nomes]


def test_gabarito_jun2026_com_os_pdfs_complementares(pdfs_reais_jun2026, tmp_path):
    """Mensal + complementar 29/06 = créditos do razão; o de 15/07 fica de fora; os 2 complementares são achados."""
    pasta, pdfs = pdfs_reais_jun2026
    resultado = processar_rescisoes(pasta / "Razão 062026.xlsx", pdfs, pasta / "Rescisões a pagar.xlsx",
                                    pasta_destino=tmp_path)
    assert resultado.erro is None
    assert [l.rotulo for l in resultado.pdfs_usados] == ["PDF mensal", "PDF complementar 29/06"]
    assert [(l.rotulo, l.total, len(l.rescisoes)) for l in resultado.pdfs_fora] == [
        ("PDF complementar 15/07", D("560.41"), 2)]
    assert resultado.total_pdf == resultado.total_creditos == D("222585.59")
    numeros = numeros_principais(resultado)
    assert (numeros.achados_pdf, numeros.achados_lista, numeros.nao_encontrados, numeros.valores_diferentes,
            numeros.lista_nova, resultado.total_lista_nova) == (42, 49, 1, 0, 135, D("132166.29"))
    no_complementar = sorted(b.pagamento.valor for b in resultado.baixas if b.onde_achado == "PDF complementar 29/06")
    assert no_complementar == [D("66.96"), D("123.64")]
    nao = resultado.baixas_de(ORIGEM_NAO_ENCONTRADO)
    assert [(b.pagamento.valor, b.regra) for b in nao] == [(D("83.31"), "c")]
    assert nao[0].observacao.startswith("Consta na composição da diferença da lista anterior: '")
    assert nao[0].observacao.endswith(" - Calculo 1635 mês 06' (R$ -83,31).")
    # saldo final − lista nova = −83,31, explicado só pelo não encontrado
    from modulos.conciliacao_rescisoes.processar import composicao_da_diferenca
    composicao = composicao_da_diferenca(resultado)
    assert (resultado.saldo_final, composicao.diferenca, composicao.sem_explicacao) == (
        D("132082.98"), D("-83.31"), D("0.00"))
    # o pagamento de 107,05 continua com o nome IDÊNTICO da lista anterior (não com o nome parecido do PDF)
    pagamento_107 = [b for b in resultado.baixas if b.pagamento.valor == D("107.05")]
    assert [(b.origem, b.nota) for b in pagamento_107] == [(ORIGEM_PENDENTE, 1.0)]
    assert not any("ATENÇÃO" in a.mensagem for a in resultado.avisos)


# ---------------------------------------------------------------------
# Eventos da folha exportado em Excel (.xlsx), no lugar do PDF
# ---------------------------------------------------------------------
# estilos como os do .xlsx do Tasy: bordas com atributos vazios e "builtInId" (o openpyxl não abre)
_ESTILOS_TASY = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    '<numFmts count="4"><numFmt numFmtId="168" formatCode="MM/YYYY"/><numFmt numFmtId="170" formatCode="000"/>'
    '<numFmt numFmtId="171" formatCode="###,###,##0.00"/><numFmt numFmtId="172" formatCode="####00"/></numFmts>'
    '<fonts count="1"><font><sz val="11"></sz></font></fonts><fills count="1"><fill></fill></fills>'
    '<borders count="1"><border left="" right="" top="" bottom="" diagonal=""></border></borders>'
    '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"></xf></cellStyleXfs>'
    '<cellXfs count="5"><xf numFmtId="0"/><xf numFmtId="168"/><xf numFmtId="170"/><xf numFmtId="171"/>'
    '<xf numFmtId="172"/></cellXfs>'
    '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtInId="0"></cellStyle></cellStyles>'
    '</styleSheet>')
_TEXTO, _MES, _SIT, _VALOR, _QUANTIDADE = 0, 1, 2, 3, 4      # estilos acima


def _celula(coluna, linha, valor, estilo=_TEXTO):
    if isinstance(valor, str):
        return f'<c r="{coluna}{linha}" t="inlineStr" s="{estilo}"><is><t><![CDATA[{valor}]]></t></is></c>'
    return f'<c r="{coluna}{linha}" s="{estilo}"><v>{valor}</v></c>'


def _pessoa(matricula, nome, valor, pagamento="06/08/2026", sit=7, competencia=46204):   # 46204 = jul/2026
    return [("A", matricula), ("B", nome), ("F", sit, _SIT), ("G", competencia, _MES), ("H", pagamento),
            ("J", 0, _VALOR), ("K", valor, _VALOR)]


LINHAS_EXCEL_TASY = [
    [("A", "0001"), ("B", "-"), ("C", "FUNDAÇÃO TESTE DE MISER."), ("L", "Pág.:"), ("M", 1)],
    [("E", "EVENTOS 072026 C/ IDENT")],
    [("A", "Período:"), ("B", 46266, _MES), ("C", "a"), ("D", 46266, _MES), ("E", "Tipo:"),   # 09/2026: errado
     ("F", "Cálculo Mensal")],
    [("A", "Evento"), ("B", "Colaborador"), ("F", "SIT"), ("G", "Competência"), ("H", "Pagamento"),
     ("J", "Referência"), ("L", "Valor")],
    [("A", "0256"), ("B", "-"), ("C", "Cred. Estouro do Mes")],
    _pessoa(26, "OUTRA PESSOA QUALQUER", 99, sit=3),
    [("D", "Total de Colaboradores:"), ("F", 1, _QUANTIDADE), ("I", 0, _VALOR), ("K", 99, _VALOR)],
    [("A", "0264"), ("B", "-"), ("C", "Liquido Rescisao")],
    _pessoa(201, "LUCIO PRADO FICTICIO", 1234.5),
    [("A", "0001"), ("B", "-"), ("C", "FUNDAÇÃO TESTE DE MISER."), ("L", "Pág.:"), ("M", 2)],   # topo da pág. 2
    _pessoa(202, "MARTA SOUZA EXEMPLO", 300),
    [("D", "Total de Colaboradores:"), ("F", 2, _QUANTIDADE), ("I", 0, _VALOR), ("K", 1534.5, _VALOR)],
]


def excel_de_eventos_tasy(pasta, linhas=LINHAS_EXCEL_TASY, nome="EVENTOS 072026 EXCEL.xlsx"):
    import zipfile
    corpo = "".join(
        f'<row r="{numero}">' + "".join(_celula(c[0], numero, *c[1:]) for c in celulas) + "</row>"
        for numero, celulas in enumerate(linhas, start=1))
    principal = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    caminho = pasta / nome
    with zipfile.ZipFile(caminho, "w") as pacote:
        pacote.writestr("[Content_Types].xml",
                        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        pacote.writestr("xl/workbook.xml",
                        f'<workbook xmlns="{principal}" xmlns:r="http://schemas.openxmlformats.org/'
                        'officeDocument/2006/relationships"><sheets><sheet name="Plan1" sheetId="1" r:id="rId1"/>'
                        '</sheets></workbook>')
        pacote.writestr("xl/_rels/workbook.xml.rels",
                        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                        '<Relationship Id="rId1" Target="sheet1.xml" Type="x"/></Relationships>')
        pacote.writestr("xl/styles.xml", _ESTILOS_TASY)
        pacote.writestr("xl/sheet1.xml", f'<worksheet xmlns="{principal}"><sheetData>{corpo}</sheetData></worksheet>')
    return caminho


def test_eventos_em_excel_do_tasy(tmp_path):
    caminho = excel_de_eventos_tasy(tmp_path)
    with pytest.raises(Exception):                   # o openpyxl não abre (estilos fora do padrão)
        load_workbook(caminho)
    leitura = ler_eventos(caminho)
    assert leitura.erro is None
    assert (leitura.tipo, leitura.competencia.month) == ("Cálculo Mensal", 7)
    assert [(r.matricula, r.nome, r.valor, r.data_pagamento.day) for r in leitura.rescisoes] == [
        ("201", "LUCIO PRADO FICTICIO", D("1234.50"), 6), ("202", "MARTA SOUZA EXEMPLO", D("300.00"), 6)]
    assert (leitura.quantidade_impressa, leitura.total_impresso) == (2, D("1534.50"))
    # o "Período" errado do cabeçalho (09/2026) dá lugar à competência das pessoas (07/2026), com aviso
    assert [a.mensagem for a in leitura.avisos] == [
        "O \"Período\" do cabeçalho da planilha (09/2026) é diferente da competência das pessoas (07/2026): "
        "foi usada a das pessoas."]
    assert previa_eventos(caminho).descricao == "0264 · jul/2026 · 2 pessoas · R$ 1.534,50"


def test_eventos_em_excel_salvo_pelo_excel(tmp_path):
    """Aberto e salvo de novo no Excel: textos compartilhados, números e datas de verdade."""
    livro = Workbook()
    aba = livro.active
    for linha in [["0001", "-", "FUNDAÇÃO TESTE DE MISER.", "Pág.:", 1], ["EVENTOS 072026 C/ IDENT"],
                  ["Período:", datetime(2026, 7, 1), "a", datetime(2026, 7, 1), "Tipo:", "Complementar Rescisão"],
                  ["Evento", "Colaborador", "SIT", "Competência", "Pagamento", "Referência", "Valor"],
                  ["0264", "-", "Liquido Rescisao"],
                  [203, "NINA ROCHA MODELO", 7, datetime(2026, 7, 1), datetime(2026, 7, 30), 0, 703.53],
                  [None, "Total de Colaboradores:", 1, 0, 703.53]]:
        aba.append(linha)
    for celula in ("B3", "D3", "D6"):
        aba[celula].number_format = "MM/YYYY"
    aba["E6"].number_format = "DD/MM/YYYY"
    aba["C6"].number_format = "000"
    for celula in ("F6", "G6", "D7", "E7"):
        aba[celula].number_format = "#,##0.00"
    caminho = tmp_path / "eventos.xlsx"
    livro.save(caminho)
    leitura = ler_eventos(caminho)
    assert leitura.erro is None and leitura.avisos == []
    assert leitura.tipo == "Complementar Rescisão"
    assert [(r.matricula, r.nome, r.valor, r.data_pagamento) for r in leitura.rescisoes] == [
        ("203", "NINA ROCHA MODELO", D("703.53"), datetime(2026, 7, 30).date())]


def test_eventos_em_excel_no_campo_errado_e_repetido_do_pdf(tmp_path, monkeypatch):
    caminho = excel_de_eventos_tasy(tmp_path)
    assert "Eventos da folha (PDF ou Excel)" in ler_razao(caminho).erro
    assert "Eventos da folha (PDF ou Excel)" in ler_controle(caminho).erro
    # o PDF e o Excel do mesmo relatório, escolhidos juntos: o segundo é ignorado (mesmo conteúdo)
    pdf = tmp_path / "EVENTOS 072026.PDF"
    pdf.write_bytes(b"%PDF-1.4 teste")
    texto = ("0001 -FUNDAÇÃO TESTE DE MISER. Pág.: 1\nEVENTOS 07/2026 C/IDENT\n"
             "Período: 07/2026 a 07/2026 Tipo: Cálculo Mensal\n0264-Liquido Rescisao\n"
             "201 LUCIO PRADO FICTICIO 007 07/2026 06/08/2026 0,00 1.234,50\n"
             "202 MARTA SOUZA EXEMPLO 007 07/2026 06/08/2026 0,00 300,00\n"
             "Total de Colaboradores: 02 0,00 1.534,50\n")
    monkeypatch.setattr(leitores, "paginas_do_pdf", lambda _caminho: [texto])
    from modulos.conciliacao_rescisoes.processar import ler_varios_eventos
    leituras, repetidos = ler_varios_eventos([pdf, caminho])
    assert [l.arquivo for l in leituras] == ["EVENTOS 072026.PDF"]
    assert repetidos == ["EVENTOS 072026 EXCEL.xlsx (igual a EVENTOS 072026.PDF)"]


def test_gabarito_eventos_jul2026_excel_igual_ao_pdf():
    pasta = PASTA_RESCISOES / "jul2026"
    excel = pasta / "EVENTOS 072026 COM IDENT F01_04_05 EXCEL.xlsx"
    pdf = pasta / "EVENTOS 072026 COM IDENT F01_04_05.PDF"
    if not (excel.exists() and pdf.exists()):
        pytest.skip("exemplos de jul/2026 não disponíveis")
    lido_excel, lido_pdf = ler_eventos(excel), ler_eventos(pdf)
    assert (len(lido_excel.rescisoes), lido_excel.total, lido_excel.competencia) == (
        105, D("324681.64"), lido_pdf.competencia)
    assert [(r.matricula, r.nome, r.valor, r.data_pagamento) for r in lido_excel.rescisoes] == \
        [(r.matricula, r.nome, r.valor, r.data_pagamento) for r in lido_pdf.rescisoes]
    assert lido_pdf.avisos == []


def test_rotulo_de_origem_diz_excel_quando_o_relatorio_e_excel(tmp_path):
    from modulos.conciliacao_rescisoes.processar import rotular_pdfs
    leitura = ler_eventos(excel_de_eventos_tasy(tmp_path))
    assert (leitura.formato, leitura.rotulo) == ("Excel", "Excel mensal")
    rotular_pdfs([leitura])
    assert {r.pdf for r in leitura.rescisoes} == {"Excel mensal"}
    complementar = LeituraEventos(arquivo="c.xlsx", tipo="Complementar Rescisão", formato="Excel")
    assert complementar.rotulo == "Excel complementar"
    assert LeituraEventos(arquivo="c.pdf", tipo="Cálculo Mensal").rotulo == "PDF mensal"


# ---------------------------------------------------------------------
# Pago a menor: o restante continua na lista nova; pago a maior: diferença na composição
# ---------------------------------------------------------------------
def test_pago_a_menor_deixa_o_restante_na_lista_nova(tmp_path, pdf_falso):
    from modulos.conciliacao_rescisoes.processar import composicao_da_diferenca
    # o Eduardo recebe 450,00 de uma rescisão de 500,00 (falta 50,00); a Fernanda, 1.000,00 de 300,00 (a maior)
    pagamentos = [("Eduardo Lima Teste", 450.00)] + PAGAMENTOS[1:]
    razao = planilha(tmp_path, "Razão 062026.xlsx", linhas_razao(pagamentos))
    resultado = processar_rescisoes(razao, pdf_falso, arquivo_controle(tmp_path))
    assert resultado.erro is None
    assert [(b.pagamento.nome, b.diferenca) for b in resultado.pagos_a_menor] == [("Eduardo Lima Teste", D("50.00"))]
    assert [(b.pagamento.nome, b.diferenca) for b in resultado.pagos_a_maior] == [
        ("Fernanda Costa Exemplo", D("-700.00"))]
    assert [(i.nome, i.valor, i.texto_origem) for i in resultado.lista_nova] == [
        ("CARLA MENDES FICTICIA", D("30.00"), ORIGEM_PENDENTE),
        ("EDUARDO LIMA TESTE", D("50.00"), "PDF mensal – restante (pago R$ 450,00 em 02/06/2026)"),
        ("HELENA DIAS FICTICIA", D("150.00"), "PDF mensal")]
    # o pago a menor não entra na composição (está na lista); o pago a maior entra
    assert [v for _, v in resultado.composicao_nova] == [D("10.00"), D("-700.00"), D("-33.00")]
    assert resultado.composicao_nova[1][0].endswith("(PDF mensal): pago a maior")
    assert composicao_da_diferenca(resultado).sem_explicacao == 0
    assert not any("ATENÇÃO" in a.mensagem for a in resultado.avisos)
    assert any("falta pagar R$ 50,00" in nota for nota in resultado.notas)

    livro = load_workbook(resultado.caminho_relatorio)
    diferentes = livro[ABA_DIFERENTES]
    assert [diferentes.cell(row=r, column=9).value for r in (4, 5)] == [
        "Pago a menor: o restante continua na lista nova",
        "Pago a maior: saiu da lista; diferença na composição (rodapé)"]
    aba = livro[ABA_RESUMO]
    explicacao = next(aba.cell(row=c.row, column=5).value for c in aba["B"]
                      if isinstance(c.value, str) and c.value.startswith("   explicada pelos pagamentos a maior"))
    assert explicacao == "=SUMIF('Valores diferentes'!H4:H5,\"<0\")"
    # no mês seguinte, o restante é a rescisão a pagar do Eduardo
    relida = ler_controle(resultado.caminho_relatorio)
    assert ("EDUARDO LIMA TESTE", D("50.00")) in [(p.nome, p.valor) for p in relida.pendentes]


def test_pago_a_menor_da_lista_anterior_guarda_o_periodo():
    from modulos.conciliacao_rescisoes.conciliador import conciliar
    from modulos.conciliacao_rescisoes.modelos import Pendente
    pendentes = [Pendente("  11/2022", "OTAVIO PRADO EXEMPLO", D("60.00")),
                 Pendente("05/2026", "OTAVIO PRADO EXEMPLO", D("60.00"))]       # duas iguais: baixa a primeira
    resultado = conciliar([_pagamento("Otavio Prado Exemplo", "45.00")], [], pendentes, "06/2026")
    assert [(i.periodo, i.valor, i.restante_de is not None) for i in resultado.lista_nova] == [
        ("  11/2022", D("15.00"), True), ("05/2026", D("60.00"), False)]
    assert resultado.lista_nova[0].texto_origem == "Pendente anterior – restante (pago R$ 45,00 em 10/06/2026)"


# ---------------------------------------------------------------------
# Crédito do razão que não é de PDF (reembolso): cada PDF casado com o seu lançamento de crédito
# ---------------------------------------------------------------------
REEMBOLSO = ("Reembolso de férias colaborador Igor Nunes Desconhecido CPF 123.456.789-00, foi desligado em "
             "01/06/2026 e teve a demissão cancelada por resultado do exame demissional. Banco: 0000-0")


def linhas_razao_com_reembolso(pagamentos, credito=1160.00, reembolso=33.50):
    """Razão com um crédito a mais (o reembolso, em 15/06) antes do "Líquido Rescisão" (mensal + complementar)."""
    linhas = linhas_razao(pagamentos, credito=credito)
    posicao = next(i for i, l in enumerate(linhas) if len(l) > 2 and l[2] == "Líquido Rescisão 0626")
    linhas.insert(posicao, [None, datetime(2026, 6, 15), REEMBOLSO, None, None, None, 71000, None, None, 0,
                            None, reembolso, None, None, None])
    linhas[posicao + 1][14] = round(linhas[posicao + 1][14] + reembolso, 2)       # saldo depois dos créditos
    for linha in linhas:
        if any(isinstance(c, str) and c.startswith("Total") for c in linha[:3]):
            linha[11] = round(credito + reembolso, 2)
    return linhas


def test_credito_sem_pdf_no_razao_e_pdf_nao_lancado(tmp_path, pdfs_falsos):
    from modulos.conciliacao_rescisoes.modelos import ESCOLHA_LANCAMENTOS
    from modulos.conciliacao_rescisoes.processar import composicao_da_diferenca
    razao = planilha(tmp_path, "Razão 062026.xlsx", linhas_razao_com_reembolso(PAGAMENTOS_COM_COMPLEMENTAR))
    resultado = processar_rescisoes(razao, pdfs_falsos[:3], arquivo_controle(tmp_path))
    assert resultado.erro is None
    # créditos 1.193,50: nenhuma soma de PDFs bate; o lançamento de 1.160,00 = mensal + complementar 29/06
    assert resultado.escolha_pdfs == ESCOLHA_LANCAMENTOS
    assert [l.rotulo for l in resultado.pdfs_usados] == ["PDF mensal", "PDF complementar 29/06"]
    assert [l.rotulo for l in resultado.pdfs_fora] == ["PDF complementar 15/07"]
    assert all("JULIA" not in i.nome for i in resultado.lista_nova)
    assert [c.valor for c in resultado.creditos_sem_pdf] == [D("33.50")] and resultado.pdfs_sem_credito == []
    # a composição mostra o crédito (sem o CPF) no lugar de "créditos do razão − PDFs"
    textos = [t for t, _ in resultado.composicao_nova]
    assert textos[0] == ("Crédito do razão sem PDF de eventos: 15/06/2026 – Reembolso de férias colaborador Igor "
                         "Nunes Desconhecido, foi desligado em 01/06/2026 e…")
    assert [v for _, v in resultado.composicao_nova] == [D("33.50"), D("-700.00"), D("-33.00")]
    assert not any("123.456" in t for t in textos)
    assert composicao_da_diferenca(resultado).sem_explicacao == 0
    # o pagamento do Igor (não encontrado) aponta o crédito com o nome dele
    igor = resultado.baixas_de(ORIGEM_NAO_ENCONTRADO)
    assert [b.pagamento.nome for b in igor] == ["Igor Nunes Desconhecido"]
    assert igor[0].observacao.startswith("Sem rescisão no PDF nem na lista anterior; o razão tem um crédito com "
                                         "este nome, sem PDF de eventos: 15/06/2026 – Reembolso")
    atencao = [a.mensagem for a in resultado.avisos if "ATENÇÃO" in a.mensagem]
    assert len(atencao) == 1 and atencao[0].startswith("ATENÇÃO: o razão tem um lançamento de crédito sem PDF")
    assert "não foram lançados" not in " ".join(resultado.notas)
    assert any("não foi lançado no razão deste mês" in nota for nota in resultado.notas)
    aba = load_workbook(resultado.caminho_relatorio)[ABA_RESUMO]
    assert any(isinstance(c.value, str) and c.value.startswith("      crédito do razão sem PDF de valor igual: 15/06")
               for c in aba["B"])
    # a prévia do conjunto diz o mesmo
    conjunto = conferir_conjunto(razao, pdfs_falsos[:3], arquivo_controle(tmp_path))
    assert conjunto.descricao == ("entram no mês: PDF mensal + PDF complementar 29/06 (cada um = um lançamento "
                                  "de crédito do razão); fora (provavelmente do mês seguinte): PDF complementar 15/07")


def test_parear_creditos_um_pdf_ou_varios_por_lancamento():
    from modulos.conciliacao_rescisoes.modelos import Credito
    from modulos.conciliacao_rescisoes.processar import parear_creditos

    def leitura(nome, total):
        return LeituraEventos(arquivo=nome, tipo="Complementar Rescisão", rescisoes=[
            leitores.RescisaoMes("1", "PESSOA", D(total))])

    a, b, c = leitura("a.pdf", "100.00"), leitura("b.pdf", "10.00"), leitura("c.pdf", "7.00")
    creditos = [Credito("Reembolso", D("5.00")), Credito("Líquido", D("110.00"))]
    pares, sem_pdf, sem_credito = parear_creditos(creditos, [c, b, a])
    assert [(cr.historico, [l.arquivo for l in grupo]) for cr, grupo in pares] == [("Líquido", ["a.pdf", "b.pdf"])]
    assert [cr.historico for cr in sem_pdf] == ["Reembolso"]
    assert [l.arquivo for l in sem_credito] == ["c.pdf"]
    assert Credito("x", D(1)).descricao == "x"


def test_gabarito_jul2026_com_a_lista_de_junho():
    """Julho real: crédito de reembolso sem PDF (1.295,70); os complementares 1654 e 1655 (pagos em agosto) não
    estão no razão e ficam de fora; a rescisão paga a menor deixa o restante na lista; a prova fecha."""
    pasta = PASTA_RESCISOES / "jul2026"
    lista_junho = PASTA_RESCISOES / "gerado_pelo_programa" / "Conciliacao_Rescisoes_HospitalExemplo_jun2026.xlsx"
    eventos = [pasta / "EVENTOS 072026 COM IDENT F01_04_05.PDF", pasta / "EVENTOS 072026 COM IDENT CÁLC 1650.PDF",
               pasta / "EVENTO COM IDENT RESC COMPL CÁLC 1654.PDF", pasta / "EVENTO COM IDENT RESC COMPL CÁLC 1655.PDF"]
    razao = pasta / "Razão Rescisão 072026.xlsx"
    if not all(p.exists() for p in eventos + [razao, lista_junho]):
        pytest.skip("exemplos de jul/2026 não disponíveis")
    from modulos.conciliacao_rescisoes.modelos import ESCOLHA_LANCAMENTOS
    from modulos.conciliacao_rescisoes.processar import composicao_da_diferenca
    import tempfile
    with tempfile.TemporaryDirectory() as pasta_saida:
        resultado = processar_rescisoes(razao, eventos, lista_junho, pasta_destino=Path(pasta_saida))
        assert resultado.erro is None
        assert resultado.escolha_pdfs == ESCOLHA_LANCAMENTOS
        assert [l.arquivo for l in resultado.pdfs_fora] == [eventos[2].name, eventos[3].name]
        assert [c.valor for c in resultado.creditos_sem_pdf] == [D("1295.70")]
        assert (resultado.saldo_final, len(resultado.lista_nova), resultado.total_lista_nova) == (
            D("96751.40"), 131, D("97282.83"))
        assert [i.valor for i in resultado.lista_nova if i.restante_de is not None] == [D("453.23")]
        assert [v for _, v in resultado.composicao_nova] == [D("-83.31"), D("1295.70"), D("-1295.44"), D("-448.38")]
        assert composicao_da_diferenca(resultado).sem_explicacao == 0


# ---------------------------------------------------------------------
# Lista nova × títulos a pagar do financeiro (opcional)
# ---------------------------------------------------------------------
def arquivo_financeiro(pasta, titulos, tipo="Recisões", nome="Titulos a pagar financeiro.xls"):
    """Relatório analítico de títulos a pagar do Tasy (WFIN 563). titulos: (pessoa, nr_titulo, saldo)."""
    from testes.conciliacao_rescisoes.apoio_fornecedores import CABECALHO_ANALITICO, OBSERVACAO_SECRETA
    linhas = [CABECALHO_ANALITICO]
    for pessoa, numero, saldo in titulos:
        linhas.append([pessoa, "1622", numero, tipo, "A", datetime(2026, 5, 26), datetime(2026, 5, 27),
                       datetime(2026, 5, 27), "", 0, 0, saldo, OBSERVACAO_SECRETA, 0, saldo, 0, 0, UNIDADE, "",
                       "", "", 0, "", ""])
    return texto_tasy(pasta, nome, linhas)


def test_lista_nova_comparada_com_o_financeiro(tres_arquivos, tmp_path):
    from modulos.conciliacao_rescisoes.financeiro import SITUACAO_DIVERGENTE, SITUACAO_OK, SITUACAO_SO_FINANCEIRO
    from modulos.conciliacao_rescisoes.relatorio_excel import ABA_FINANCEIRO
    from testes.conciliacao_rescisoes.apoio_fornecedores import OBSERVACAO_SECRETA
    # lista nova: CARLA MENDES FICTICIA 30,00 e HELENA DIAS FICTICIA 150,00
    financeiro = arquivo_financeiro(tmp_path, [("Carla Mendes Fictícia", "1318304", 20.00),
                                               ("Carla Mendes Fictícia", "1203972", 10.00),   # dois títulos
                                               ("Helena Dias Ficticia", "1318305", 140.00),
                                               ("Joana Prado Exemplo", "1318306", 25.00)])
    resultado = processar_rescisoes(*tres_arquivos, arquivo_financeiro=financeiro)
    assert resultado.erro is None
    comparacao = resultado.financeiro
    assert [(l.situacao, l.pessoa and l.pessoa.nome, l.valor_lista, l.valor_financeiro, l.diferenca)
            for l in comparacao.linhas] == [
        (SITUACAO_DIVERGENTE, "HELENA DIAS FICTICIA", D("150.00"), D("140.00"), D("10.00")),
        (SITUACAO_SO_FINANCEIRO, None, None, D("25.00"), D("-25.00")),
        (SITUACAO_OK, "CARLA MENDES FICTICIA", D("30.00"), D("30.00"), D("0"))]
    assert (comparacao.total_lista, comparacao.total_financeiro) == (D("180.00"), D("195.00"))
    atencao = [a.mensagem for a in resultado.avisos if "financeiro" in a.mensagem and "ATENÇÃO" in a.mensagem]
    assert len(atencao) == 1 and "1 com valor diferente, 1 só no financeiro (diferença R$ -15,00)" in atencao[0]
    assert any(a.tipo_arquivo == "Títulos a pagar (financeiro)" and a.linhas_lidas == 4 for a in resultado.avisos)

    livro = load_workbook(resultado.caminho_relatorio)
    assert livro.sheetnames[-1] == ABA_FINANCEIRO
    aba = livro[ABA_FINANCEIRO]
    assert [aba.cell(row=r, column=1).value for r in (4, 5, 6)] == [
        SITUACAO_DIVERGENTE, SITUACAO_SO_FINANCEIRO, SITUACAO_OK]
    assert aba["E6"].value == "1318304 – 26/05/2026 – 20,00; 1203972 – 26/05/2026 – 10,00"
    assert (aba["G4"].value, aba["C8"].value, aba["F8"].value) == ("=C4-F4", "=SUM(C4:C6)", "=SUM(F4:F6)")
    textos = [c.value for planilha_ in livro.worksheets for linha in planilha_.iter_rows() for c in linha
              if isinstance(c.value, str)]
    assert not any(OBSERVACAO_SECRETA in t for t in textos)            # a Observação nunca vai para o relatório
    resumo = livro[ABA_RESUMO]
    rotulos = {c.value: c.row for c in resumo["B"] if isinstance(c.value, str)}
    assert resumo.cell(row=rotulos["Lista nova × títulos a pagar do financeiro"] + 1, column=5).value == \
        f"='{ABA_FINANCEIRO}'!C8"
    assert resumo.cell(row=rotulos["   pessoas com o mesmo valor (OK)"], column=5).value == \
        f"=COUNTIF('{ABA_FINANCEIRO}'!A4:A6,\"OK\")"
    assert "títulos a pagar do financeiro" in resumo["B4"].value
    # a lista nova continua igual (o financeiro só é comparado)
    assert [(p.nome, p.valor) for p in ler_controle(resultado.caminho_relatorio).pendentes] == [
        ("CARLA MENDES FICTICIA", D("30.00")), ("HELENA DIAS FICTICIA", D("150.00"))]


def test_financeiro_que_bate_com_nome_escrito_diferente_e_sem_financeiro(tres_arquivos, tmp_path):
    financeiro = arquivo_financeiro(tmp_path, [("Carla Mendes Ficticia", "1", 30.00),
                                               ("Helena Diaz Ficticia", "2", 150.00)])
    resultado = processar_rescisoes(*tres_arquivos, arquivo_financeiro=financeiro)
    comparacao = resultado.financeiro
    assert comparacao.para_conferir == [] and comparacao.diferenca == 0
    assert [l.nome_financeiro for l in comparacao.nomes_parecidos] == ["Helena Diaz Ficticia"]
    assert not any("ATENÇÃO" in a.mensagem for a in resultado.avisos)
    assert any("1 delas com o nome escrito diferente" in n for n in resultado.notas)
    # sem o arquivo: nada muda (sem a aba)
    sem = processar_rescisoes(*tres_arquivos)
    assert sem.financeiro is None and "Financeiro × lista" not in load_workbook(sem.caminho_relatorio).sheetnames


def test_financeiro_ilegivel_ou_de_outro_tipo_vira_aviso(tres_arquivos, tmp_path):
    from modulos.conciliacao_rescisoes.processamento import previa_financeiro
    trocado = processar_rescisoes(*tres_arquivos, arquivo_financeiro=tres_arquivos[2])   # a lista no lugar
    assert trocado.erro is None and trocado.caminho_relatorio is not None and trocado.financeiro is None
    assert any(a.tipo_arquivo == "Títulos a pagar (financeiro)" and a.nivel == "Erro" for a in trocado.avisos)
    notas_fiscais = arquivo_financeiro(tmp_path, [("Carla Mendes Ficticia", "1", 30.00)], tipo="Nota Fiscal")
    resultado = processar_rescisoes(*tres_arquivos, arquivo_financeiro=notas_fiscais)
    assert any("não são de rescisão (Nota Fiscal: 1 título(s))" in a.mensagem for a in resultado.avisos)
    previa = previa_financeiro(arquivo_financeiro(tmp_path, [("Carla Mendes Ficticia", "1", 30.00),
                                                             ("Carla Mendes Ficticia", "2", 5.00)], nome="b.xls"))
    assert (previa.erro, previa.descricao, previa.avisos) == (None, "2 títulos · 1 pessoas · R$ 35,00", [])
    assert previa_financeiro(tres_arquivos[2]).erro


def test_gabarito_set2026_lista_x_financeiro():
    """Setembro real: a lista nova (98 rescisões, R$ 53.836,22) × títulos a pagar do financeiro (98 títulos de 90
    pessoas, o mesmo total): as 90 pessoas batem; 10 com o nome escrito diferente nos dois lados."""
    from modulos.conciliacao_rescisoes.fornecedores.leitores import ler_titulos
    from modulos.conciliacao_rescisoes.financeiro import comparar_com_financeiro
    from modulos.conciliacao_rescisoes.modelos import ItemLista
    pasta = PASTA_RESCISOES / "parte_final"
    lista, titulos = pasta / "Conciliacao_Rescisoes_HospitalExemplo_set2026.xlsx", pasta / "Titulos a pagar financeiro 30092026.xlsx"
    if not (lista.exists() and titulos.exists()):
        pytest.skip("exemplos de set/2026 não disponíveis")
    itens = [ItemLista(p.periodo, p.nome, p.valor, ORIGEM_PENDENTE) for p in ler_controle(lista).pendentes]
    comparacao = comparar_com_financeiro(itens, ler_titulos(titulos))
    assert (len(itens), comparacao.total_lista, comparacao.quantidade_titulos) == (98, D("53836.22"), 98)
    assert (len(comparacao.linhas), comparacao.para_conferir, comparacao.diferenca) == (90, [], 0)
    assert len(comparacao.nomes_parecidos) == 10


def test_financeiro_nome_so_parecido_com_valor_diferente_sao_duas_pessoas(tmp_path):
    from modulos.conciliacao_rescisoes.fornecedores.leitores import ler_titulos
    from modulos.conciliacao_rescisoes.financeiro import SITUACAO_OK, SITUACAO_SO_FINANCEIRO, SITUACAO_SO_LISTA, comparar_com_financeiro
    from modulos.conciliacao_rescisoes.modelos import ItemLista
    itens = [ItemLista("05/2026", "PAULA CRISTINA EXEMPLO DE MOURA", D("107.67"), ORIGEM_PENDENTE),
             ItemLista("05/2026", "CLARA FERNANDA LIMA FICTICIA", D("778.77"), ORIGEM_PENDENTE)]
    titulos = ler_titulos(arquivo_financeiro(tmp_path, [("Vanessa Cristiane Exemplo Matos", "1", 3615.23),
                                                        ("Clara Fernanda Barbosa Lima", "2", 778.77)]))
    comparacao = comparar_com_financeiro(itens, titulos)
    # nota 0,71 e valor diferente: não junta; nota 0,73 e valor igual: junta (confirmar)
    assert [(l.situacao, l.pessoa and l.pessoa.nome, l.nome_financeiro) for l in comparacao.linhas] == [
        (SITUACAO_SO_LISTA, "PAULA CRISTINA EXEMPLO DE MOURA", ""),
        (SITUACAO_SO_FINANCEIRO, None, "Vanessa Cristiane Exemplo Matos"),
        (SITUACAO_OK, "CLARA FERNANDA LIMA FICTICIA", "Clara Fernanda Barbosa Lima")]
    assert [l.pessoa.nome for l in comparacao.nomes_parecidos] == ["CLARA FERNANDA LIMA FICTICIA"]


def test_nota_nome_casos_reais():
    """O par de nomes reais que estava em test_nota_nome no Conciliações AMES (fora do git)."""
    import json

    casos = json.loads((pasta_exemplos("conciliacao_rescisoes") / "casos_reais.json").read_text(encoding="utf-8"))
    for pagamento, rescisao in casos["outro_primeiro_nome"]:
        assert nota_nome(pagamento, rescisao) == 0.0
