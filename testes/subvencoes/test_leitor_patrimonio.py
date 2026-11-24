from decimal import Decimal

import openpyxl
import pytest

from modulos.subvencoes.leitor_patrimonio import ler_patrimonio
from modulos.subvencoes.modelos import ErroArquivo, Gravidade, MesReferencia
from modulos.subvencoes.utilitarios import normalizar_texto
from testes.subvencoes.conftest import arquivos_do_mes


def _conta(relatorio, nome):
    encontradas = [c for c in relatorio.contas if normalizar_texto(c.nome) == normalizar_texto(nome)]
    assert len(encontradas) == 1, f"conta {nome}: {len(encontradas)} encontradas"
    return encontradas[0]


def _tipos(relatorio):
    return [a.tipo for a in relatorio.avisos]


# ---------------------------------------------------------------------------
# Exemplos reais
# ---------------------------------------------------------------------------


def test_exemplos_estrutura_geral(arquivos, mes_exemplo):
    relatorio = ler_patrimonio(arquivos.patrimonio)
    ano, mes = map(int, mes_exemplo.split("-"))
    assert relatorio.mes_referencia == MesReferencia(ano, mes)
    assert len(relatorio.contas) == 143
    assert sum(1 for c in relatorio.contas if c.total_sistema is None) == 19      # P2
    assert relatorio.linhas_nao_reconhecidas == []
    assert relatorio.itens_sem_conta == []
    assert relatorio.total_geral_sistema is not None
    assert relatorio.soma_itens == relatorio.total_geral_sistema                 # conferência obrigatória
    assert relatorio.quantidade_itens == relatorio.quantidade_geral_sistema
    assert not any(a.gravidade == Gravidade.ERRO for a in relatorio.avisos)


def test_exemplos_contas_de_um_bem_sem_total(arquivos):
    """P2: contas sem linha Total têm saldo = soma dos itens (um item só)."""
    relatorio = ler_patrimonio(arquivos.patrimonio)
    sem_total = [c for c in relatorio.contas if c.total_sistema is None]
    assert all(len(c.itens) == 1 for c in sem_total)
    nomes = {normalizar_texto(c.nome) for c in sem_total}
    for nome in ["Convênio Federal 826059/2015", "Convenio Federal 848574/2017",
                 "Convênio Federal 961621/2024", "Convênio Estadual 347/2020"]:
        assert normalizar_texto(nome) in nomes


def test_julho_cabecalho_ausente():
    """P4: os 11 bens sem cabeçalho vão para 773672/2012, não para 773671/2012."""
    relatorio = ler_patrimonio(arquivos_do_mes("2026-07").patrimonio)
    conta = _conta(relatorio, "Convenio Federal 773672/2012")
    assert conta.cabecalho_ausente
    assert len(conta.itens) == 11
    assert conta.soma_itens == Decimal("569.57")

    anterior = _conta(relatorio, "Convênio Federal 773671/2012")
    assert not anterior.cabecalho_ausente
    assert len(anterior.itens) == 2
    assert anterior.soma_itens == Decimal("11823.66")

    assert _tipos(relatorio) == ["cabeçalho ausente"]
    assert relatorio.avisos[0].conta == "Convenio Federal 773672/2012"


def test_agosto_total_do_sistema_divergente():
    """P3: a linha Total mostra 0,00 mas o Detector Fetal Portátil vale 154,70."""
    relatorio = ler_patrimonio(arquivos_do_mes("2026-08").patrimonio)
    conta = _conta(relatorio, "Convênio Federal 775214/2012")
    assert conta.soma_itens == Decimal("154.70")
    assert conta.total_sistema == Decimal("0.00")
    assert conta.total_divergente
    assert _tipos(relatorio) == ["total do sistema divergente"]
    assert relatorio.avisos[0].conta == "Convênio Federal 775214/2012"


def test_colunas_deslocadas_por_pagina(arquivos):
    """P1: o relatório tem páginas com 'Valor Contábil' em G e outras em F; as duas são lidas."""
    relatorio = ler_patrimonio(arquivos.patrimonio)
    pasta = openpyxl.load_workbook(arquivos.patrimonio, data_only=True)
    aba = pasta.worksheets[0]
    colunas = {c.column_letter for linha in aba.iter_rows() for c in linha if c.value == "Valor Contábil"}
    assert colunas == {"F", "G"}
    # cada bem lido guarda o valor da coluna "Valor Contábil" da sua página
    colunas_por_linha = {}
    coluna_atual = None
    for linha in aba.iter_rows():
        for c in linha:
            if c.value == "Valor Contábil":
                coluna_atual = c.column
        colunas_por_linha[linha[0].row] = coluna_atual
    for conta in relatorio.contas:
        for item in conta.itens:
            valor = aba.cell(item.linha, colunas_por_linha[item.linha]).value
            assert Decimal(repr(valor)).quantize(Decimal("0.01")) == item.valor


# ---------------------------------------------------------------------------
# Casos construídos
# ---------------------------------------------------------------------------

TITULOS_G = {3: "Conta Subvenção", 4: "Cód Bem", 5: "Descrição", 7: "Valor Contábil", 9: "Deprec Mês"}
TITULOS_F = {2: "Conta Subvenção", 3: "Cód Bem", 4: "Descrição", 6: "Valor Contábil", 8: "Deprec Mês"}


def cabecalho_pagina(titulos=TITULOS_G, data="Data: 01/09/26 à 30/09/26"):
    return [{1: "Patrimônio - Bens Subvenção"}, {10: data}, titulos]


def item(codigo, descricao, valor, deslocado=False):
    if deslocado:
        return {3: codigo, 4: descricao, 6: valor, 8: 0}
    return {4: codigo, 5: descricao, 7: valor, 9: 0}


def conta(nome, deslocado=False):
    return {2 if deslocado else 3: nome}


def total(nome, quantidade, valor):
    return {2: f"Total - {nome}({quantidade})", 7: valor, 9: 0}


def rodape(pagina):
    return {3: "Impresso em:  01/10/2026 08:00:00", 6: f"Página   {pagina}", 8: "Usuario", 11: "CPAT2271"}


def gravar(caminho, linhas):
    pasta = openpyxl.Workbook()
    aba = pasta.active
    for numero, linha in enumerate(linhas, start=1):
        for coluna, valor in (linha or {}).items():
            aba.cell(numero, coluna, valor)
    pasta.save(caminho)
    return caminho


def test_relatorio_construido_com_p1_p2_p3_p4(tmp_path):
    linhas = [
        *cabecalho_pagina(),
        conta("Conta A"),
        item(1, "Bem A1", 100.10),
        item(2, "Bem A2", 200.20),
        total("Conta A", 2, 300.30),
        conta("Conta B"),                          # P2: um bem, sem Total
        item(3, "Bem B1", 50),
        rodape(1),
        *cabecalho_pagina(TITULOS_F),              # P1: página deslocada
        conta("Conta C", deslocado=True),
        item(4, "Bem C1", 10.5, deslocado=True),
        item(5, "Bem C2", 0, deslocado=True),
        total("Conta C", 2, 0),                    # P3: total do sistema errado
        None,                                      # P4: cabeçalho ausente
        item(6, "Bem D1", 7.25, deslocado=True),
        total("Conta D", 1, 7.25),
        {2: "Total(6)", 7: 368.05, 9: 0},
        rodape(2),
    ]
    relatorio = ler_patrimonio(gravar(tmp_path / "p.xlsx", linhas))

    assert relatorio.mes_referencia == MesReferencia(2026, 9)
    assert [c.nome for c in relatorio.contas] == ["Conta A", "Conta B", "Conta C", "Conta D"]
    a, b, c, d = relatorio.contas
    assert a.soma_itens == Decimal("300.30") and not a.total_divergente
    assert b.soma_itens == Decimal("50.00") and b.total_sistema is None
    assert c.soma_itens == Decimal("10.50") and c.total_sistema == Decimal("0.00") and c.total_divergente
    assert d.cabecalho_ausente and d.soma_itens == Decimal("7.25")
    assert relatorio.total_geral_confere
    assert relatorio.linhas_nao_reconhecidas == []
    assert sorted(_tipos(relatorio)) == ["cabeçalho ausente", "total do sistema divergente"]


def test_bem_sem_valor_nao_e_adivinhado(tmp_path):
    linhas = [
        *cabecalho_pagina(),
        conta("Conta A"),
        item(1, "Bem A1", 100),
        {4: 2, 5: "Bem A2", 8: 55.0},             # valor fora da coluna "Valor Contábil"
        total("Conta A", 2, 155),
        {2: "Total(2)", 7: 155, 9: 0},
    ]
    relatorio = ler_patrimonio(gravar(tmp_path / "p.xlsx", linhas))
    assert relatorio.linhas_nao_reconhecidas == [6]
    conta_a = relatorio.contas[0]
    assert conta_a.soma_itens == Decimal("100.00")
    tipos = _tipos(relatorio)
    assert "linha não reconhecida" in tipos
    assert "total do sistema divergente" in tipos
    assert "quantidade divergente" in tipos
    erros = [a for a in relatorio.avisos if a.gravidade == Gravidade.ERRO]
    assert {a.tipo for a in erros} == {"linha não reconhecida", "total geral não confere"}


def test_linha_de_formato_desconhecido_e_erro(tmp_path):
    linhas = [
        *cabecalho_pagina(),
        conta("Conta A"),
        item(1, "Bem A1", 100),
        {3: "texto solto", 5: "outro texto"},
        total("Conta A", 1, 100),
        {2: "Total(1)", 7: 100, 9: 0},
    ]
    relatorio = ler_patrimonio(gravar(tmp_path / "p.xlsx", linhas))
    assert relatorio.linhas_nao_reconhecidas == [6]
    assert relatorio.total_geral_confere


def test_itens_sem_conta(tmp_path):
    """Itens depois de um Total e antes de um novo cabeçalho não têm conta: aviso, e o total geral denuncia."""
    linhas = [
        *cabecalho_pagina(),
        conta("Conta A"),
        item(1, "Bem A1", 100),
        total("Conta A", 1, 100),
        item(2, "Bem perdido", 30),
        conta("Conta B"),
        item(3, "Bem B1", 20),
        total("Conta B", 1, 20),
        {2: "Total(3)", 7: 150, 9: 0},
    ]
    relatorio = ler_patrimonio(gravar(tmp_path / "p.xlsx", linhas))
    assert [i.descricao for i in relatorio.itens_sem_conta] == ["Bem perdido"]
    assert [c.soma_itens for c in relatorio.contas] == [Decimal("100.00"), Decimal("20.00")]
    assert "itens sem conta" in _tipos(relatorio)
    assert not relatorio.total_geral_confere
    assert any(a.gravidade == Gravidade.ERRO and a.tipo == "total geral não confere" for a in relatorio.avisos)


def test_conta_aberta_sem_total_seguida_de_itens_sem_cabecalho(tmp_path):
    """Regra 1: Total com nome diferente da conta aberta -> os pendentes vão para a conta do Total."""
    linhas = [
        *cabecalho_pagina(),
        conta("Conta A"),
        item(1, "Bem X", 10),
        item(2, "Bem Y", 20),
        total("Conta B", 2, 30),
        {2: "Total(2)", 7: 30, 9: 0},
    ]
    relatorio = ler_patrimonio(gravar(tmp_path / "p.xlsx", linhas))
    a, b = relatorio.contas
    assert a.nome == "Conta A" and a.itens == []
    assert b.nome == "Conta B" and b.cabecalho_ausente and b.soma_itens == Decimal("30.00")
    assert _tipos(relatorio).count("cabeçalho ausente") == 2


def test_nomes_comparados_normalizados_e_conta_repetida(tmp_path):
    linhas = [
        *cabecalho_pagina(),
        conta("Convênio Federal 1/2020 "),
        item(1, "Bem", 10),
        total("Convenio  Federal 1/2020", 1, 10),   # mesmo nome, sem acento e com espaço duplo
        conta("Conta Z"),
        item(2, "Bem", 5),
        total("Conta Z", 1, 5),
        conta("Conta Z"),
        item(3, "Bem", 1),
        total("Conta Z", 1, 1),
        {2: "Total(3)", 7: 16, 9: 0},
    ]
    relatorio = ler_patrimonio(gravar(tmp_path / "p.xlsx", linhas))
    assert not relatorio.contas[0].cabecalho_ausente
    assert len(relatorio.contas) == 3                  # os dois blocos são mantidos
    assert _tipos(relatorio) == ["conta repetida no patrimônio"]
    aviso = relatorio.avisos[0]
    assert aviso.conta == "Conta Z" and aviso.linha == 7
    # linhas de cada bloco, para o usuário conferir
    assert "linhas 7 a 9 (5.00)" in aviso.mensagem
    assert "linhas 10 a 12 (1.00)" in aviso.mensagem


def test_sem_total_geral_e_erro(tmp_path):
    linhas = [*cabecalho_pagina(), conta("Conta A"), item(1, "Bem", 10), total("Conta A", 1, 10)]
    relatorio = ler_patrimonio(gravar(tmp_path / "p.xlsx", linhas))
    assert relatorio.total_geral_sistema is None
    assert [(a.gravidade, a.tipo) for a in relatorio.avisos] == [(Gravidade.ERRO, "total geral não confere")]


def test_arquivo_que_nao_e_patrimonio(tmp_path):
    with pytest.raises(ErroArquivo, match="Valor Contábil"):
        ler_patrimonio(gravar(tmp_path / "p.xlsx", [{1: "qualquer coisa"}]))
