"""
Testes da Conciliação Honorários (ESPECIFICACAO seção 18).

Os arquivos sintéticos imitam o Tasy: .xls que na verdade é texto separado por tabulação
(Windows-1252). O balancete é o mesmo da Conciliação Fornecedores (conta sintética com as contas
dos médicos/clínicas); o SCF – Repasse Sintético tem grupos, quebra de página com as colunas em outra
posição e linhas de total. Nomes inventados. O gabarito com os arquivos reais é pulado se
exemplos/ não existir.
"""

from datetime import date, datetime
from decimal import Decimal

import pytest
from openpyxl import load_workbook

from modulos.honorarios_medicos.ames import conferir_par, numeros_principais, previa_balancete, previa_repasse, processar_honorarios
from modulos.honorarios_medicos.ames.leitores import ler_balancete, ler_repasse
from modulos.honorarios_medicos.ames.modelos import (
    SITUACAO_DIVERGENTE,
    SITUACAO_OK,
    SITUACAO_SO_BALANCETE,
    SITUACAO_SO_REPASSE,
)
from modulos.honorarios_medicos.ames.relatorio_excel import ABA_COMPLETA, ABA_DETALHE, ABA_RESUMO

from testes.conftest import PASTA_EXEMPLOS
from testes.honorarios_medicos.apoio_fornecedores import _conta, _topo_balancete, planilha, texto_tasy

PASTA_HONORARIOS = PASTA_EXEMPLOS / "honorarios_medicos" / "Exemplos_Honorarios"
D = Decimal
UNIDADE = "AME - Cidade Teste (Fund. Hospital Exemplo)"
UNIDADE_REPASSE = "AME - Cidade Teste"


# ---------------------------------------------------------------------
# Arquivos sintéticos
# ---------------------------------------------------------------------
def linhas_balancete(contas, total=None, unidade=UNIDADE, mes="set/2026", codigo_total=2132,
                     classificacao="2.01.03.02", descricao="HONORARIOS MEDICOS A PAGAR - PJ"):
    """contas: (codigo, descricao, saldo). Total = soma, se não informado."""
    total = sum(c[2] for c in contas) if total is None else total
    linhas = _topo_balancete(unidade, mes)
    linhas.append(_conta(codigo_total, classificacao, descricao, total))
    for posicao, (codigo, nome, saldo) in enumerate(contas, start=1):
        linhas.append(_conta(codigo, f"{classificacao}.{posicao:04d}", nome, saldo))
    linhas.append([None, "Impresso em: 08/10/2026", None, None, None, None, None, "Página: 1", None,
                   None, None, "USUARIO", None, None, "WEXE001"])
    return linhas


def arquivo_balancete(pasta, contas, nome="Rel HM.xls", **opcoes):
    return texto_tasy(pasta, nome, linhas_balancete(contas, **opcoes))


def _topo_repasse(unidade, deslocado):
    """Topo de página; deslocado=True põe tudo uma coluna à esquerda (como a página 3 do Tasy)."""
    vazio = [] if deslocado else [None]
    return [
        ["SCF - Repasse Sintetico AME"],
        [None] * (3 if deslocado else 4) + [unidade],
        [None] + vazio + ["Terceiro", None, None, "Nr Repasse", "Dt Ref", "Status", "Vl repasse", "Vl. Líquido"],
    ]


def linhas_repasse(grupos, unidade=UNIDADE_REPASSE, dt_ref="01/09/2026", quebra_no_grupo=None,
                   total_geral=None):
    """grupos: [(nome, [(terceiro, nr, bruto, liquido)])]. quebra_no_grupo: quebra de página no meio dele."""
    linhas = _topo_repasse(unidade, False)
    deslocado = False
    soma_q, soma_b, soma_l = 0, 0.0, 0.0
    for nome, repasses in grupos:
        vazio = [] if deslocado else [None]
        linhas.append([None] + vazio + [f"{nome} - {unidade.title()}"])
        for posicao, (terceiro, numero, bruto, liquido) in enumerate(repasses):
            if quebra_no_grupo == nome and posicao == 1:
                linhas.append([None, None, "Impresso em:  08/10/2026", "Página   1", None, None, None,
                               "USUARIO", None, "CATE6095"])
                deslocado = True
                linhas += _topo_repasse(unidade, True)
                vazio = []
            linhas.append([None] + vazio + [terceiro, None, None, numero, dt_ref, "F", bruto, liquido])
        q, b, l = len(repasses), sum(r[2] for r in repasses), sum(r[3] for r in repasses)
        soma_q, soma_b, soma_l = soma_q + q, soma_b + b, soma_l + l
        linhas.append([None, f"Total - {nome} - {unidade.title()}({q})", None, None, None, None, None, None, b, l])
    q, b, l = total_geral or (soma_q, soma_b, soma_l)
    linhas.append([None, f"Total({q})", None, None, None, None, None, None, b, l])
    linhas.append([None, None, "Impresso em:  08/10/2026", "Página   2", None, None, None, "USUARIO", None,
                   "CATE6095"])
    return linhas


def arquivo_repasse(pasta, grupos, nome="Balancete (2).xls", **opcoes):
    return texto_tasy(pasta, nome, linhas_repasse(grupos, **opcoes))


CONTAS = [
    (40001, "Clínica Alfa Serviços Médicos Ltda", 1500.0),           # dois grupos → OK
    (40002, "Beta & Gama Médicos Associados S/S", 800.0),            # divergente (repasse 750)
    (40003, "Delta Saúde Ltda", 300.0),                              # sem repasse
    (40004, "Epsilon Clinica Medica", 0.0),                          # saldo zero sem repasse: fora
    (40005, "Zeta Oftalmologia Ltda", 920.0),                        # dois repasses no mesmo grupo
]
GRUPOS = [
    ("Deslocamento", [("Clinica Alfa Servicos Medicos Ltda", "500001", 200.0, 200.0)]),
    ("Produção Médica", [
        ("Clinica Alfa Servicos Medicos Ltda.", "500002", 1300.0, 1220.0),
        ("Beta E Gama Medicos Associados S/s", "500003", 750.0, 700.0),
        ("Zeta Oftalmologia Ltda", "500004", 600.0, 600.0),
        ("Zeta Oftalmologia Ltda", "500005", 320.0, 300.0),
        ("Omega Servicos Medicos Ltda", "500006", 90.0, 90.0),     # sem conta no balancete
    ]),
]


def _gerar(tmp_path, contas=CONTAS, grupos=GRUPOS, **opcoes):
    saida = tmp_path / "saida"
    saida.mkdir(exist_ok=True)
    return processar_honorarios(arquivo_balancete(tmp_path, contas), arquivo_repasse(tmp_path, grupos, **opcoes),
                                agora=datetime(2026, 10, 8, 9, 0), pasta_destino=saida)


# ---------------------------------------------------------------------
# Leitores
# ---------------------------------------------------------------------
def test_balancete_acha_a_conta_sintetica_e_as_contas_dos_medicos(tmp_path):
    leitura = ler_balancete(arquivo_balancete(tmp_path, CONTAS))
    assert leitura.erro is None
    assert leitura.unidade == UNIDADE
    assert leitura.mes == date(2026, 9, 1)
    assert (leitura.total.codigo, leitura.total.saldo_atual) == ("2132", D("3520.00"))
    assert [c.codigo for c in leitura.contas] == ["40001", "40002", "40003", "40004", "40005"]
    assert leitura.avisos == []


def test_balancete_com_outro_codigo_tambem_serve(tmp_path):
    """Hospital Exemplo: a conta de honorários pode ter outro código e classificação."""
    caminho = arquivo_balancete(tmp_path, CONTAS[:2], codigo_total=9999, classificacao="2.01.09.07",
                                descricao="HONORARIOS MEDICOS A PAGAR")
    leitura = ler_balancete(caminho)
    assert (leitura.total.codigo, len(leitura.contas)) == ("9999", 2)


def test_balancete_soma_que_nao_bate(tmp_path):
    leitura = ler_balancete(arquivo_balancete(tmp_path, CONTAS, total=1.0))
    assert any("ATENÇÃO" in a.mensagem for a in leitura.avisos)


def test_balancete_sem_contas_filhas_e_erro(tmp_path):
    caminho = texto_tasy(tmp_path, "b.xls", _topo_balancete(UNIDADE, "set/2026")
                         + [_conta(11111, "1.01.01", "Caixa", 10)] + [["WEXE001"]])
    assert "Honorários" in ler_balancete(caminho).erro


def test_repasse_le_grupos_quebra_de_pagina_e_totais(tmp_path):
    leitura = ler_repasse(arquivo_repasse(tmp_path, GRUPOS, quebra_no_grupo="Produção Médica"))
    assert leitura.erro is None
    assert leitura.unidade == UNIDADE_REPASSE
    assert leitura.mes == date(2026, 9, 1)
    assert leitura.grupos == ["Deslocamento", "Produção Médica"]
    assert [(r.grupo, r.terceiro, r.numero, r.bruto, r.liquido) for r in leitura.repasses][:3] == [
        ("Deslocamento", "Clinica Alfa Servicos Medicos Ltda", "500001", D("200.00"), D("200.00")),
        ("Produção Médica", "Clinica Alfa Servicos Medicos Ltda.", "500002", D("1300.00"), D("1220.00")),
        ("Produção Médica", "Beta E Gama Medicos Associados S/s", "500003", D("750.00"), D("700.00"))]
    assert len(leitura.repasses) == 6
    assert (leitura.total_bruto, leitura.total_liquido) == (D("3260.00"), D("3110.00"))
    assert leitura.repasses[0].data_referencia == date(2026, 9, 1)
    assert leitura.avisos == []


def test_repasse_total_que_nao_bate(tmp_path):
    leitura = ler_repasse(arquivo_repasse(tmp_path, GRUPOS, total_geral=(7, 9999.0, 9999.0)))
    assert any("ATENÇÃO" in a.mensagem and "total do relatório" in a.mensagem for a in leitura.avisos)


def test_repasse_salvo_como_xlsx_tambem_e_aceito(tmp_path):
    caminho = planilha(tmp_path, "repasse.xlsx", linhas_repasse(GRUPOS))
    leitura = ler_repasse(caminho)
    assert leitura.erro is None
    assert leitura.total_bruto == D("3260.00")


def test_arquivos_trocados_dizem_o_campo_certo(tmp_path):
    balancete = arquivo_balancete(tmp_path, CONTAS)
    repasse = arquivo_repasse(tmp_path, GRUPOS)
    assert "campo \"Repasse médico\"" in ler_balancete(repasse).erro
    assert "campo \"Balancete\"" in ler_repasse(balancete).erro
    assert "não parece ser" in ler_repasse(texto_tasy(tmp_path, "x.xls", [["qualquer coisa"]])).erro


# ---------------------------------------------------------------------
# Conciliação
# ---------------------------------------------------------------------
def _situacoes(resultado):
    return [(l.conta.codigo if l.conta else "—", l.nome_repasse, l.diferenca, l.situacao)
            for l in resultado.linhas]


def test_conciliacao_soma_os_grupos_e_classifica(tmp_path):
    resultado = _gerar(tmp_path)
    assert resultado.erro is None
    assert _situacoes(resultado) == [
        ("40001", "Clinica Alfa Servicos Medicos Ltda", D("0.00"), SITUACAO_OK),
        ("40002", "Beta E Gama Medicos Associados S/s", D("50.00"), SITUACAO_DIVERGENTE),
        ("40003", "", D("300.00"), SITUACAO_SO_BALANCETE),
        ("40005", "Zeta Oftalmologia Ltda", D("0.00"), SITUACAO_OK),
        ("—", "Omega Servicos Medicos Ltda", D("-90.00"), SITUACAO_SO_REPASSE),
    ]
    alfa = resultado.linhas[0]
    assert (alfa.bruto_do_grupo("Deslocamento"), alfa.bruto_do_grupo("Produção Médica")) == (D("200"), D("1300"))
    assert alfa.total_liquido == D("1420.00")
    numeros = numeros_principais(resultado)
    assert (numeros.linhas, numeros.ok, numeros.nao_ok) == (5, 2, 3)
    # prova: total balancete − total repasse = soma das diferenças
    assert resultado.total_balancete - resultado.total_repasse == sum(l.diferenca for l in resultado.linhas)
    assert not any("ATENÇÃO" in a.mensagem for a in resultado.avisos)


def test_notas_explicam_o_que_aconteceu(tmp_path):
    notas = " | ".join(_gerar(tmp_path).notas)
    assert "6 repasses de 4 terceiros, em 2 grupos (Deslocamento, Produção Médica)" in notas
    assert "Zeta Oftalmologia Ltda tem 2 repasses de Produção Médica" in notas
    assert "R$ 150,00, em Produção Médica" in notas                      # retenções
    assert "'Epsilon Clinica Medica'" in notas and "saldo zero" in notas
    assert "1 conta do Balancete não tem repasse" in notas
    assert "1 terceiro do Repasse não tem conta no Balancete" in notas


def test_planilha_tem_as_tres_abas_com_formulas(tmp_path):
    resultado = _gerar(tmp_path)
    caminho = resultado.caminho_relatorio
    assert caminho.name == "Conciliacao_HonorariosMedicos_CidadeTeste_set2026.xlsx"
    livro = load_workbook(caminho)
    assert livro.sheetnames == [ABA_RESUMO, ABA_COMPLETA, ABA_DETALHE]
    completa = livro[ABA_COMPLETA]
    assert [c.value for c in completa[3]] == [
        "Código (Balancete)", "Descrição (Balancete)", "Terceiro (Repasse SCF)", "Saldo Balancete",
        "Repasse Deslocamento", "Repasse Produção Médica", "Total Repasse (bruto)", "Diferença",
        "Confiança do Pareamento", "Situação", "Vl. Líquido (Repasse)"]
    assert [c.value for c in completa[4]][:8] == [
        "40001", "Clínica Alfa Serviços Médicos Ltda", "Clinica Alfa Servicos Medicos Ltda", 1500, 200, 1300,
        "=SUM(E4:F4)", "=D4-G4"]
    assert completa["J5"].value == SITUACAO_DIVERGENTE
    assert completa["D8"].value is None and completa["J8"].value == SITUACAO_SO_REPASSE
    assert completa["B10"].value == "TOTAL" and completa["G10"].value == "=SUM(G4:G8)"
    detalhe = livro[ABA_DETALHE]
    assert [c.value for c in detalhe[4]][:3] == ["Deslocamento", "Clinica Alfa Servicos Medicos Ltda", 500001]
    assert detalhe["H4"].value == "=F4-G4" and detalhe["I4"].value == "40001"
    assert detalhe["I9"].value == "—"                                    # Omega: sem conta
    resumo = livro[ABA_RESUMO]
    textos = [c.value for linha in resumo.iter_rows() for c in linha if isinstance(c.value, str)]
    assert "Divergências e Itens Sem Correspondência" in textos
    assert "Divergente" in textos and "Só no Balancete" in textos and "Só no Repasse" in textos
    assert any(t.startswith("=SUMIF('Repasses (detalhe)'!A4:A9,\"Produção Médica\"") for t in textos)


def test_tudo_ok_mostra_frase_de_nenhuma_divergencia(tmp_path):
    contas = [(40001, "Clínica Alfa Serviços Médicos Ltda", 200.0)]
    grupos = [("Administrativo", [("Clinica Alfa Servicos Medicos Ltda", "1", 200.0, 200.0)])]
    resultado = _gerar(tmp_path, contas, grupos)
    textos = [c.value for linha in load_workbook(resultado.caminho_relatorio)[ABA_RESUMO].iter_rows()
              for c in linha if isinstance(c.value, str)]
    assert any(t.startswith("Nenhuma divergência") for t in textos)


def test_unidades_diferentes_nao_gera(tmp_path):
    resultado = _gerar(tmp_path, unidade="AME - Outra Cidade")
    assert "unidades diferentes" in resultado.erro
    assert resultado.caminho_relatorio is None


def test_mesma_unidade_com_nome_mais_comprido_no_repasse(tmp_path):
    # o balancete diz "Ame - Cidade Epsilon" e o repasse "AME - Cidade Epsilon (SCF)"
    from modulos.honorarios_medicos.fornecedores.leitores import mesma_unidade_pelo_nome
    resultado = _gerar(tmp_path, unidade="AME - Cidade Teste do Norte (SCF)")
    assert resultado.erro is None and resultado.caminho_relatorio is not None
    assert conferir_par(tmp_path / "Rel HM.xls", tmp_path / "Balancete (2).xls").erro is None
    assert mesma_unidade_pelo_nome("Ame - Cidade Epsilon ( Fund. Hospital Exemplo )", "AME - Cidade Epsilon (SCF)")
    assert not mesma_unidade_pelo_nome("AME - Cidade Delta (Fund.)", "Ame - Cidade Epsilon ( Fund. )")


def test_meses_diferentes_avisa(tmp_path):
    resultado = _gerar(tmp_path, dt_ref="01/08/2026")
    assert resultado.erro is None
    assert any("ATENÇÃO" in a.mensagem and "ago/2026" in a.mensagem for a in resultado.avisos)
    assert "ago/2026" in conferir_par(tmp_path / "Rel HM.xls", tmp_path / "Balancete (2).xls").avisos[0]


def test_arquivo_trocado_nao_gera(tmp_path):
    balancete = arquivo_balancete(tmp_path, CONTAS)
    resultado = processar_honorarios(balancete, balancete, pasta_destino=tmp_path)
    assert "Relatório não gerado" in resultado.erro


def test_previas(tmp_path):
    assert previa_balancete(arquivo_balancete(tmp_path, CONTAS)).descricao == \
        "AME - Cidade Teste · set/2026 · conta 2132 · 5 contas · R$ 3.520,00"
    assert previa_repasse(arquivo_repasse(tmp_path, GRUPOS)).descricao == \
        "AME - Cidade Teste · set/2026 · 6 repasses · 4 terceiros · R$ 3.260,00"
    assert conferir_par(tmp_path / "Rel HM.xls", tmp_path / "Balancete (2).xls").erro is None


# ---------------------------------------------------------------------
# Gabarito (arquivos reais, fora do git) — ESPECIFICACAO 18.5
# ---------------------------------------------------------------------
def test_gabarito_cidade_delta_set2026(tmp_path):
    pasta = PASTA_HONORARIOS / "set2026_CidadeDelta"
    if not pasta.exists():
        pytest.skip("exemplos/Exemplos_Honorarios não existe")
    resultado = processar_honorarios(pasta / "Rel HM.xls", pasta / "Balancete (2).xls",
                                     agora=datetime(2026, 10, 8, 9, 0), pasta_destino=tmp_path)
    assert resultado.erro is None
    assert (resultado.total_balancete, resultado.total_repasse, resultado.total_liquido) == (
        D("366298.38"), D("366298.38"), D("355812.13"))
    assert len(resultado.repasses) == 70
    assert resultado.grupos == ["Administrativo", "Deslocamento", "Produção Médica"]
    numeros = numeros_principais(resultado)
    assert (numeros.linhas, numeros.ok, numeros.nao_ok) == (53, 53, 0)
    assert not any("ATENÇÃO" in a.mensagem for a in resultado.avisos)
    assert "17 terceiros têm mais de um repasse" in resultado.notas[2]
    assert resultado.caminho_relatorio.name == "Conciliacao_HonorariosMedicos_CidadeDelta_set2026.xlsx"
