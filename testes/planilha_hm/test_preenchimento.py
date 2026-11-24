"""PlanilhaHM 4: tabela conta → seção (R5a), preenchimento da cópia (R3–R6, R8) e conferência final (R9).

Testes obrigatórios 4, 6, 7 e 8 da seção 8. A pergunta da tela é sempre simulada (um dicionário de respostas).
"""

from __future__ import annotations

import csv
import hashlib
from collections import Counter
from decimal import Decimal as D

import openpyxl
import pytest

from modulos.planilha_hm import configuracao as cfg
from modulos.planilha_hm.conferencia import conferir, totais_do_mes
from modulos.planilha_hm.leitor_eventos import ler_eventos
from modulos.planilha_hm.leitor_movimento import ler_movimento
from modulos.planilha_hm.leitor_planilha import ler_planilha
from modulos.planilha_hm.modelos import ErroLeitura
from modulos.planilha_hm.normalizacao import normalizar, para_decimal
from modulos.planilha_hm.preenchimento import planejar, preencher
from modulos.planilha_hm.secoes_contas import ler_tabela
from testes.planilha_hm.conftest import (
    CONTA_FIXOS,
    escrever_caso_ficticio,
    escrever_planilha,
    exemplos,
    gabarito_senior,
    planilha_real,
)

pytestmark = pytest.mark.filterwarnings("ignore:Print area cannot be set")


def _md5(caminho) -> str:
    return hashlib.md5(caminho.read_bytes()).hexdigest()


def _numero(valor):
    return round(valor, 6) if isinstance(valor, float) else valor


def _gabarito_totais_com_valor(mes: str) -> dict[str, D]:
    with open(exemplos(mes, "gabarito") / f"gabarito_totais_{mes}.csv", encoding="utf-8-sig") as arquivo:
        return {l["total"]: D(l["valor"].replace(",", ".")) for l in csv.DictReader(arquivo, delimiter=";")}


# ---------------------------------------------------------------------------
# Testes obrigatórios com os arquivos reais (setembro a partir da planilha de agosto)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def setembro(tmp_path_factory):
    pasta = tmp_path_factory.mktemp("setembro")
    entradas = [planilha_real("2026-08"), exemplos("2026-09") / "Eventos 09-2026.XLS",
                next(exemplos("2026-09").glob("Movimento*.csv"))]
    hashes = [_md5(c) for c in entradas]
    planilha, eventos, movimento = ler_planilha(entradas[0]), ler_eventos(entradas[1]), ler_movimento(entradas[2])
    plano = planejar(eventos, movimento, planilha, pasta / "config")
    perguntas = list(plano.perguntas)
    novos = [(n.evento.numero, n.secao, n.origem) for n in plano.novos]
    destino = pasta / "09 Planilha HM.xlsx"
    resultado = preencher(entradas[0], planilha, eventos, movimento, plano,
                          {p.chave: cfg.RESPOSTA_SECAO_NOVA for p in perguntas}, destino)
    final = ler_planilha(destino)
    return {"pasta": pasta, "entradas": entradas, "hashes": hashes, "eventos": eventos, "movimento": movimento,
            "planilha": planilha, "plano": plano, "perguntas": perguntas, "novos": novos, "resultado": resultado,
            "destino": destino, "final": final, "conferencia": conferir(eventos, movimento, final)}


def test_4_aba_do_ano_igual_ao_gabarito_de_setembro(setembro):
    """A aba 2026 inteira (valores e fórmulas) = a do gabarito feito à mão. Única diferença aceita: o nome do
    evento 3171, que o Tasy manda sem acento ("HM Fisico Medico") e o gabarito tem com acento."""
    nossa = openpyxl.load_workbook(setembro["destino"])["2026"]
    gabarito = openpyxl.load_workbook(planilha_real("2026-09"))["2026"]
    assert (nossa.max_row, nossa.max_column) == (gabarito.max_row, gabarito.max_column)
    diferencas = [(c.coordinate, c.value, gabarito[c.coordinate].value)
                  for linha in nossa.iter_rows() for c in linha
                  if _numero(c.value) != _numero(gabarito[c.coordinate].value)]
    assert [d[0] for d in diferencas] == ["B260", "B261"]
    assert all(normalizar(nosso) == normalizar(esperado) for _, nosso, esperado in diferencas)
    [tabela], [esperada] = nossa.tables.values(), gabarito.tables.values()
    assert (tabela.ref, tabela.autoFilter.ref) == (esperada.ref, esperada.autoFilter.ref)


def test_4_linhas_criadas_sao_as_do_gabarito(setembro):
    criadas = {(c.tipo, c.evento, c.codigo_cc, c.linha) for c in setembro["resultado"].criadas}
    assert criadas == {
        ("CC novo", 2721, "180", 955), ("CC novo", 2736, "78", 1182), ("CC novo", 3106, "18", 1368),
        ("CC novo", 3118, "70", 163), ("CC novo", 3118, "584", 164), ("CC novo", 3157, "53", 602),
        ("evento novo", 3171, "", 260), ("CC novo", 3171, "78", 261),
        ("seção nova", None, "", 1653), ("evento novo", 3172, "", 1654), ("CC novo", 3172, "72", 1655),
        ("total da seção nova", None, "", 1656)}
    secoes = {c.evento: (c.secao, c.origem) for c in setembro["resultado"].criadas if c.tipo == "evento novo"}
    assert secoes == {3171: ("HONORÁRIOS MÉDICOS - FIXOS", cfg.ORIGEM_TABELA_MONTADA),
                      3172: ("HM CATARATA - AGLUTINADA PJ", cfg.ORIGEM_RESPOSTA)}
    # o openpyxl não copia as duas setas desenhadas abaixo do LOTE nem o "ignorar erro": vira aviso de atenção
    avisos = setembro["resultado"].avisos
    assert len(avisos) == 2 and not any(a.erro for a in avisos)
    assert "2 desenho(s)" in avisos[0].mensagem and "ignorar erro" in avisos[1].mensagem


def test_4_totais_iguais_ao_gabarito_e_lote(setembro):
    final, esperado = setembro["final"], _gabarito_totais_com_valor("2026-09")
    totais, total_geral = totais_do_mes(final, 9)
    assert {t.nome_total: t.valor for t in totais} == {k: v for k, v in esperado.items()
                                                       if k not in ("TOTAL GERAL", "LOTE REPASSE")}
    assert total_geral == esperado["TOTAL GERAL"] == D("5794120.73")
    assert para_decimal(final.lote_por_mes[9]) == esperado["LOTE REPASSE"] == D("5794120.73")
    assert final.avisos == []                    # a estrutura continua fechando (totais = linhas de evento)


def test_4_agosto_continua_igual(setembro):
    esperado = _gabarito_totais_com_valor("2026-08")
    totais, total_geral = totais_do_mes(setembro["final"], 8)
    assert {t.nome_total: t.valor for t in totais if t.nome_total in esperado} == {
        k: v for k, v in esperado.items() if k not in ("TOTAL GERAL", "LOTE REPASSE")}
    assert total_geral == esperado["TOTAL GERAL"] == D("5737714.53")


def test_4_aba_senior_do_mes(setembro):
    """R3: o conteúdo da aba Senior 09 = gabarito (sem depender da ordem) e as fórmulas vão até a última linha."""
    aba = openpyxl.load_workbook(setembro["destino"])["Senior 09 2026"]
    linhas = Counter((l[0], str(l[1]), l[2], D(repr(l[3])).quantize(D("0.01")))
                     for l in aba.iter_rows(min_row=2, max_col=4, values_only=True) if l[0] is not None)
    assert linhas == gabarito_senior("2026-09")
    assert setembro["resultado"].linhas_senior == 264
    for linha in range(2, 266):
        assert aba.cell(linha, 6).value == (f"=A{linha}&B{linha}" if linha > 2 else '=CONCATENATE("",A2,B2)')
        assert aba.cell(linha, 7).value == f"=VLOOKUP(F{linha},'2026'!C:C,1,0)"
        assert aba.cell(linha, 8).value == f"=F{linha}=G{linha}"


def test_9_conferencia_fecha_com_o_movimento(setembro):
    conferencia = setembro["conferencia"]
    assert conferencia.total_geral == conferencia.total_movimento == conferencia.total_eventos == D("5794120.73")
    assert conferencia.ok and conferencia.avisos == [] and conferencia.eventos_fora == []
    comparacao = {c.evento: c for c in conferencia.comparacao}
    assert comparacao[3171].diferenca == comparacao[3172].diferenca == 0


def test_6_arquivos_de_entrada_nao_mudam(setembro):
    assert [_md5(c) for c in setembro["entradas"]] == setembro["hashes"]
    assert not (setembro["entradas"][0].parent / cfg.PASTA_CONFIG).exists()      # a tabela vai para a pasta pedida


def test_8_tabela_montada_e_pergunta_da_conta_nova(setembro):
    assert setembro["novos"] == [(3171, "HONORÁRIOS MÉDICOS - FIXOS", cfg.ORIGEM_TABELA_MONTADA),
                                 (3172, None, "")]
    [pergunta] = setembro["perguntas"]
    assert (pergunta.chave, pergunta.eventos, pergunta.permite_nova) == ("3.01.01.06.28.0005", [3172], True)
    assert pergunta.nome_secao_nova == "HM CATARATA - AGLUTINADA PJ"
    tabela = ler_tabela(setembro["pasta"] / "config" / cfg.ARQUIVO_SECOES)
    assert tabela.secao("3.01.01.06.28.0005") == "HM CATARATA - AGLUTINADA PJ"
    assert tabela.secao("3.01.01.06.03.0002") == tabela.secao("3.01.01.06.03.0001") == "HONORÁRIOS MÉDICOS - FIXOS"
    assert tabela.secao("3.01.01.06.04.0001") == tabela.secao("3.01.01.06.26.0002") == "HONORÁRIOS MÉDICOS - PLANTÕES"
    assert tabela.avisos == []


def test_8_meses_seguintes_usam_a_tabela(setembro):
    """Com a tabela gravada: a planilha de setembro pronta não tem nada novo; a de agosto põe o 3171 em FIXOS
    pela tabela, e o 3172 vai para a seção da tabela, que só existe depois de criada (então pergunta)."""
    pasta = setembro["pasta"] / "config"
    plano = planejar(setembro["eventos"], setembro["movimento"], setembro["final"], pasta)
    assert plano.novos == [] and plano.perguntas == []
    plano = planejar(setembro["eventos"], setembro["movimento"], setembro["planilha"], pasta)
    assert [(n.evento.numero, n.secao, n.origem) for n in plano.novos] == [
        (3171, "HONORÁRIOS MÉDICOS - FIXOS", cfg.ORIGEM_TABELA), (3172, None, "")]
    assert [p.chave for p in plano.perguntas] == ["3.01.01.06.28.0005"]


# ---------------------------------------------------------------------------
# Casos fictícios
# ---------------------------------------------------------------------------
# Planilha (conftest.SECOES_FICTICIAS): FIXOS = 1001 (CCs 10, 20) e 1002 (CC 10); seção VAZIA; DESCONTOS = 2001
# (CC sem código e CC 30). Eventos de set/2026: 1001 ganha o CC 40 (R4); 1003 é novo e a conta dele já é de FIXOS;
# 1004 é novo e a conta dele não está em nenhuma seção (pergunta).

def _ficticio(tmp_path, **opcoes):
    planilha, eventos, movimento = escrever_caso_ficticio(tmp_path, **opcoes)
    return planilha, ler_eventos(eventos), ler_movimento(movimento)


def _processar(tmp_path, respostas=None, substituir=False, **opcoes):
    caminho, eventos, movimento = _ficticio(tmp_path, **opcoes)
    planilha = ler_planilha(caminho)
    plano = planejar(eventos, movimento, planilha, tmp_path / "config")
    if respostas is None:
        respostas = {p.chave: cfg.RESPOSTA_SECAO_NOVA for p in plano.perguntas}
    destino = tmp_path / "saida.xlsx"
    resultado = preencher(caminho, planilha, eventos, movimento, plano, respostas, destino, substituir=substituir)
    final = ler_planilha(destino)
    return plano, resultado, final, conferir(eventos, movimento, final), destino


def test_ficticio_completo(tmp_path):
    plano, resultado, final, conferencia, destino = _processar(tmp_path)
    assert [(p.chave, p.nome_secao_nova) for p in plano.perguntas] == [("3.9.02.0001", "CONTA EXEMPLO NOVA PJ")]
    assert "HONORÁRIOS MÉDICOS - VAZIA" not in plano.perguntas[0].opcoes      # seção sem linha de total
    fixos, vazia, descontos, nova = final.secoes
    assert [e.numero for e in fixos.eventos] == [1001, 1002, 1003]
    assert [c.codigo for c in fixos.eventos[0].ccs] == ["10", "20", "40"]
    assert [c.codigo for c in fixos.eventos[2].ccs] == ["10"]
    assert (nova.nome, nova.nome_total, [e.numero for e in nova.eventos]) == (
        "CONTA EXEMPLO NOVA PJ", "TOTAL CONTA EXEMPLO NOVA PJ", [1004])
    for secao in (fixos, nova):                  # R5/R6: o evento novo entra no total em todos os meses
        assert all(linhas == secao.linhas_eventos for linhas in secao.linhas_no_total_mes.values())
    assert all(linhas == [fixos.linha_total, descontos.linha_total, nova.linha_total]
               for linhas in final.linhas_no_total_geral_mes.values())
    assert final.avisos == []
    assert para_decimal(final.lote_por_mes[9]) == D("505.00")                  # R8
    assert final.linha_diferenca == final.linha_lote + 1
    assert conferencia.ok and conferencia.total_geral == D("505.00")
    assert {t.nome_total: t.valor for t in conferencia.totais} == {
        "TOTAL HM FIXOS": D("435.00"), "TOTAL DESCONTOS": D("30.00"), "TOTAL CONTA EXEMPLO NOVA PJ": D("40.00")}
    aba = openpyxl.load_workbook(destino)["2026"]
    linha_cc = fixos.eventos[0].ccs[2].linha
    assert [aba.cell(linha_cc, c).value for c in range(1, 6)] == [1001, "HM Exemplo A", f"=A{linha_cc}&D{linha_cc}",
                                                                 40, "Centro Delta"]
    assert aba.cell(linha_cc, 14).value == f"=SUMIF('Senior 09 2026'!$G:$G,$C{linha_cc},'Senior 09 2026'!$D:$D)"
    assert aba.cell(linha_cc, 1).font.b == aba.cell(fixos.eventos[0].ccs[0].linha, 1).font.b
    assert not [c.coordinate for linha in aba.iter_rows() for c in linha
                if isinstance(c.value, str) and "#REF" in c.value]
    senior = openpyxl.load_workbook(destino)["Senior 09 2026"]
    assert [senior.cell(8, c).value for c in range(6, 9)] == ["=A8&B8", "=VLOOKUP(F8,'2026'!C:C,1,0)", "=F8=G8"]
    assert senior.cell(9, 6).value is None                        # R3: as fórmulas vão até a última linha de dados
    assert openpyxl.load_workbook(destino).calculation.fullCalcOnLoad
    assert resultado.avisos == []                 # planilha fictícia sem desenhos: nada a avisar
    tabela = ler_tabela(tmp_path / "config" / cfg.ARQUIVO_SECOES)
    assert {k: i.secao for k, i in tabela.itens.items()} == {
        "3.9.01.0001": "HONORÁRIOS MÉDICOS - FIXOS", "2.9.01.0001": "HM DESCONTOS",
        "3.9.02.0001": "CONTA EXEMPLO NOVA PJ"}


def test_ficticio_resposta_secao_existente(tmp_path):
    plano, resultado, final, conferencia, _ = _processar(tmp_path, respostas={"3.9.02.0001": "HM DESCONTOS"})
    assert [s.nome for s in final.secoes] == ["HONORÁRIOS MÉDICOS - FIXOS", "HONORÁRIOS MÉDICOS - VAZIA",
                                              "HM DESCONTOS"]
    assert [e.numero for e in final.secoes[2].eventos] == [2001, 1004]
    assert conferencia.ok and final.avisos == []
    assert ler_tabela(tmp_path / "config" / cfg.ARQUIVO_SECOES).secao("3.9.02.0001") == "HM DESCONTOS"
    criado = next(c for c in resultado.criadas if c.evento == 1004 and c.tipo == "evento novo")
    assert (criado.secao, criado.origem) == ("HM DESCONTOS", cfg.ORIGEM_RESPOSTA)


def test_ficticio_tabela_existente_e_corrigida_a_mao(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / cfg.ARQUIVO_SECOES).write_text(
        "Classificacao;Conta;Secao\n3.9.02.0001;Conta Exemplo Nova PJ;HONORÁRIOS MÉDICOS - FIXOS\n;sem;linha\n",
        encoding="utf-8-sig")
    caminho, eventos, movimento = _ficticio(tmp_path)
    plano = planejar(eventos, movimento, ler_planilha(caminho), tmp_path / "config")
    assert [(n.evento.numero, n.secao) for n in plano.novos] == [(1003, None), (1004, "HONORÁRIOS MÉDICOS - FIXOS")]
    assert [p.chave for p in plano.perguntas] == ["3.9.01.0001"]       # a conta do 1003 não está na tabela
    assert len(plano.avisos) == 1                                        # a linha sem classificação


def test_ficticio_evento_sem_conta_no_movimento(tmp_path):
    caminho, eventos, movimento = _ficticio(tmp_path)
    movimento.linhas = [l for l in movimento.linhas if l.evento != 1004]
    plano = planejar(eventos, movimento, ler_planilha(caminho), tmp_path / "config")
    pergunta = next(p for p in plano.perguntas if p.eventos == [1004])
    assert (pergunta.chave, pergunta.contas, pergunta.nome_secao_nova) == ("evento 1004", [],
                                                                            "HM EXEMPLO OUTRA CONTA")


def test_7_eventos_com_total_diferente_fica_fora_e_aparece_na_conferencia(tmp_path):
    _, resultado, final, conferencia, destino = _processar(tmp_path, total_1002=210)
    assert final.evento(1002) is not None                           # a linha já existia; o evento não entra
    aba = openpyxl.load_workbook(destino)["Senior 09 2026"]
    assert 1002 not in [l[0] for l in aba.iter_rows(min_row=2, max_col=1, values_only=True)]
    assert [e.numero for e in conferencia.eventos_fora] == [1002]
    assert conferencia.diferenca == D("-200.00") and not conferencia.ok
    assert "1002" in conferencia.avisos[0].mensagem and conferencia.avisos[0].erro


def test_7_movimento_de_outro_mes(tmp_path):
    caminho, eventos, movimento = _ficticio(tmp_path, data="31/08/2026")
    with pytest.raises(ValueError, match="mesmo mês"):
        planejar(eventos, movimento, ler_planilha(caminho), tmp_path / "config")


def test_7_planilha_sem_a_aba_do_mes(tmp_path):
    caminho, eventos, movimento = _ficticio(tmp_path, abas_senior=range(1, 9))
    with pytest.raises(ValueError, match="Senior 09 2026"):
        planejar(eventos, movimento, ler_planilha(caminho), tmp_path / "config")


def test_aba_senior_ja_preenchida_pergunta_antes(tmp_path):
    with pytest.raises(ValueError, match="confirme a substituição"):
        _processar(tmp_path, senior_com_dados={9: 8})
    assert not (tmp_path / "saida.xlsx").exists() and not (tmp_path / "config").exists()


def test_substituir_apaga_as_linhas_antigas_da_aba_senior(tmp_path):
    _, resultado, final, conferencia, destino = _processar(tmp_path, substituir=True, senior_com_dados={9: 8})
    aba = openpyxl.load_workbook(destino)["Senior 09 2026"]
    dados = [l for l in aba.iter_rows(min_row=2, max_col=4, values_only=True) if any(v is not None for v in l)]
    assert len(dados) == resultado.linhas_senior == 7 and conferencia.ok          # as 8 antigas saíram


def test_falta_resposta_ou_resposta_invalida(tmp_path):
    caminho, eventos, movimento = _ficticio(tmp_path)
    planilha = ler_planilha(caminho)
    plano = planejar(eventos, movimento, planilha, tmp_path / "config")
    with pytest.raises(ValueError, match="Faltam respostas"):
        preencher(caminho, planilha, eventos, movimento, plano, {}, tmp_path / "saida.xlsx")
    with pytest.raises(ValueError, match="não é uma das opções"):
        preencher(caminho, planilha, eventos, movimento, plano, {"3.9.02.0001": "SEÇÃO QUE NÃO EXISTE"},
                  tmp_path / "saida.xlsx")
    with pytest.raises(ValueError, match="nunca é alterada"):
        preencher(caminho, planilha, eventos, movimento, plano, {"3.9.02.0001": cfg.RESPOSTA_SECAO_NOVA}, caminho)


def test_montar_tabela_conta_em_duas_secoes_vira_pergunta(tmp_path):
    caminho, eventos, movimento = _ficticio(tmp_path)
    for linha in movimento.linhas:               # o desconto passa a debitar a conta dos FIXOS
        if linha.codigo_historico == "903":
            linha.debito, linha.conta_debito, linha.classificacao_debito = (
                CONTA_FIXOS["debito"], CONTA_FIXOS["conta_debito"], CONTA_FIXOS["classificacao_debito"])
    planilha = ler_planilha(caminho)
    plano = planejar(eventos, movimento, planilha, tmp_path / "config")
    conflito = next(p for p in plano.perguntas if p.chave == "3.9.01.0001")
    assert not conflito.permite_nova
    assert conflito.opcoes == ["HONORÁRIOS MÉDICOS - FIXOS", "HM DESCONTOS"]
    assert conflito.eventos == [1001, 1002, 2001, 1003]
    assert plano.novos[0].evento.numero == 1003 and plano.novos[0].chave_pergunta == "3.9.01.0001"
    respostas = {"3.9.01.0001": "HONORÁRIOS MÉDICOS - FIXOS", "3.9.02.0001": cfg.RESPOSTA_SECAO_NOVA}
    with pytest.raises(ValueError, match="uma das seções"):
        preencher(caminho, planilha, eventos, movimento, plano,
                  {**respostas, "3.9.01.0001": cfg.RESPOSTA_SECAO_NOVA}, tmp_path / "saida.xlsx")
    preencher(caminho, planilha, eventos, movimento, plano, respostas, tmp_path / "saida.xlsx")
    assert ler_tabela(tmp_path / "config" / cfg.ARQUIVO_SECOES).secao("3.9.01.0001") == "HONORÁRIOS MÉDICOS - FIXOS"
    assert [e.numero for e in ler_planilha(tmp_path / "saida.xlsx").secoes[0].eventos] == [1001, 1002, 1003]


def test_tabela_sem_coluna_e_erro(tmp_path):
    (tmp_path / cfg.ARQUIVO_SECOES).write_text("Conta;Secao\nx;y\n", encoding="utf-8")
    with pytest.raises(ErroLeitura, match="Classificacao"):
        ler_tabela(tmp_path / cfg.ARQUIVO_SECOES)
    assert ler_tabela(tmp_path / "nao_existe.csv") is None


@pytest.mark.parametrize("formula, esperado", [
    ("=SUM(N7+N9)", "=SUM(N7+N9+N20)"),
    ("=SUM(N7,N9)", "=SUM(N7,N9,N20)"),
    ("=N7+N9", "=N7+N9+N20"),
    ("=N7", "=N7+N20"),
    (None, "=N20"),
])
def test_acrescentar_ao_total_nos_formatos_da_planilha(tmp_path, formula, esperado):
    from modulos.planilha_hm.preenchimento import _Aba

    caminho = escrever_planilha(tmp_path / "planilha.xlsx")
    planilha = ler_planilha(caminho)
    livro = openpyxl.load_workbook(caminho)
    linha = planilha.secoes[0].linha_total
    for coluna in planilha.colunas_meses.values():
        livro["2026"].cell(linha, coluna).value = formula.replace("N", openpyxl.utils.get_column_letter(coluna)) \
            if formula else None
    _Aba(livro, planilha).acrescentar_ao_total(linha, 20, "teste")
    assert livro["2026"].cell(linha, planilha.colunas_meses[9]).value == esperado
