"""T4 — conferência com casos montados no próprio teste (R1 a R10)."""

from __future__ import annotations

import re
from decimal import Decimal

from modulos.checklist_contratos.conferencia import conferir
from modulos.checklist_contratos.modelos import (
    AbaChecklist,
    Checklist,
    Configuracao,
    Lancamento,
    LinhaChecklist,
    Movimento,
    Regra,
    Situacao,
)
from modulos.checklist_contratos.normalizacao import normalizar


def lanc(conta, valor, complemento, lancamento="1", estabelecimento="SC", lote="70000"):
    return Lancamento(estabelecimento, conta, "Conta Exemplo", Decimal(valor), lote, lancamento, "05/10/2026",
                      complemento, normalizar(complemento), 2, documento=f"{lote}/{lancamento}")


def regra(linha, contas, busca, descricao=None, excluir=None, selecao="", tipo="auto", aba="SC"):
    return Regra(aba, linha, "", "", tuple(contas.split("/")), re.compile(busca), re.compile(descricao) if descricao else None,
                 re.compile(excluir) if excluir else None, selecao, tipo, "", linha)


def linha(numero, mes=None, anterior=None, fornecedor="Fornecedor Exemplo"):
    return LinhaChecklist(numero, "30091", "Conta", fornecedor, "Descrição", "Ana", mes, anterior)


def conferir_caso(regras, lancamentos, linhas, cmd=None):
    checklist = Checklist("chk.xlsx", 2026, 10, {
        "SC": AbaChecklist("SC", "HOSPITAL EXEMPLO", 19, 18, linhas),
        "CMD": AbaChecklist("CMD", "CENTRO MULTIDISCIPLINAR", 19, 18, cmd or []),
    })
    movimentos = {"SC": Movimento(lancamentos), "CMD": Movimento([])}
    return conferir(movimentos, checklist, Configuracao(regras=regras))


def test_r4_soma_das_contas_do_mesmo_endereco():
    # água: custo e despesa do mesmo endereço somam
    c = conferir_caso([regra(2, "30037/30081", "agua exemplo")],
                      [lanc("30037", "100", "Agua Exemplo NF. 1 - Rua A"), lanc("30081", "50,5".replace(",", "."), "Agua Exemplo NF. 1 - Rua A")],
                      [linha(2)])
    [r] = c.resultados
    assert (r.situacao, r.valor, r.gravar) == (Situacao.OK, Decimal("150.50"), True)
    assert r.lote_lancamento == "70000/1, 70000/1"


def test_r3_maior_e_menor_ficam_com_uma_nf_so():
    lancs = [lanc("30091", "10", "Fornecedor Exemplo NF. 1", "1"), lanc("30091", "30", "Fornecedor Exemplo NF. 2", "2")]
    c = conferir_caso([regra(2, "30091", "fornecedor exemplo", selecao="maior"),
                       regra(3, "30091", "fornecedor exemplo", selecao="menor")], lancs, [linha(2), linha(3)])
    assert [r.valor for r in c.resultados] == [Decimal("30.00"), Decimal("10.00")]
    assert [r.lote_lancamento for r in c.resultados] == ["70000/2", "70000/1"]


def test_r1_busca_descricao_e_excluir():
    lancs = [lanc("30044", "10", "Gases Exemplo NF. 1 - Locacao de Cilindro"),
             lanc("30044", "20", "Gases Exemplo NF. 2 - Locacao de Misturador"),
             lanc("30044", "40", "Gases Exemplo NF. 3 - Assistencia")]
    c = conferir_caso([regra(2, "30044", "gases exemplo", descricao="locac", excluir="misturador")], lancs, [linha(2)])
    assert c.resultados[0].valor == Decimal("10.00")


def test_r2_r5_conta_divergente_e_divergencia_que_nao_e_divergencia():
    # o telefone aparece numa NF de vários números (linha 2) e na própria linha (3), em outra conta:
    # como a linha 3 achou o lançamento na conta certa, ele não é divergência da linha 2 (R5)
    lancs = [lanc("30130", "100", "Telefonia Exemplo NF. 1 - 3333-0001, 3333-0002", "1"),
             lanc("14000", "40", "Telefonia Exemplo NF. 2 - 3333-0002", "2"),
             lanc("30099", "70", "Telefonia Exemplo NF. 3 - 3333-0001", "3")]
    c = conferir_caso([regra(2, "30130", "telefonia exemplo", descricao="3333-0001"),
                       regra(3, "14000", "telefonia exemplo", descricao="3333-0002")], lancs, [linha(2), linha(3)])
    linha2, linha3 = c.resultados
    assert linha2.situacao == Situacao.CONTA_DIVERGENTE and [l.lancamento for l in linha2.divergentes] == ["3"]
    assert linha2.valor == Decimal("100.00") and not linha2.gravar         # divergente nunca grava
    assert (linha3.situacao, linha3.valor) == (Situacao.OK, Decimal("40.00"))


def test_r6_manual_ignorado_e_nao_encontrado():
    lancs = [lanc("30091", "10", "Fornecedor Exemplo NF. 1")]
    c = conferir_caso([regra(2, "30091", "fornecedor exemplo", tipo="manual"),
                       regra(3, "30091", "fornecedor exemplo", tipo="ignorar"),
                       regra(4, "30091", "outro fornecedor")], lancs, [linha(2), linha(3), linha(4)])
    assert [r.situacao for r in c.resultados] == [Situacao.MANUAL, Situacao.IGNORADO, Situacao.NAO_ENCONTRADO]
    assert len(c.resultados[0].candidatos) == 1                            # manual lista os candidatos
    assert not any(r.gravar for r in c.resultados)


def test_r7_celula_ja_preenchida_nunca_e_sobrescrita():
    lancs = [lanc("30091", "100", "Fornecedor Exemplo NF. 1")]
    c = conferir_caso([regra(2, "30091", "fornecedor exemplo"), regra(3, "30091", "fornecedor exemplo"),
                       regra(4, "30091", "fornecedor exemplo")],
                      lancs, [linha(2, mes=100), linha(3, mes=80.5), linha(4, mes="Provisão")])
    iguais, diferente, texto = c.resultados
    assert all(r.situacao == Situacao.OK and r.celula_preenchida and not r.gravar for r in c.resultados)
    assert (iguais.valor_diferente, diferente.valor_diferente, texto.valor_diferente) == (False, True, False)


def test_r7a_provisao_na_celula_e_valor_achado_avisa_que_e_do_mes_anterior():
    lancs = [lanc("30091", "100", "Fornecedor Exemplo NF. 1")]
    c = conferir_caso([regra(n, "30091", "fornecedor exemplo") for n in (2, 3, 4, 5)] + [regra(6, "30091", "outro")],
                      lancs, [linha(2, mes="Provisão"), linha(3, mes="fazer PROVISAO manual"), linha(4, mes=100),
                              linha(5, mes="virá no lote programado"), linha(6, mes="Provisão")])
    provisao, texto, numero, outro_texto, nao_achou = c.resultados
    assert provisao.provisao and texto.provisao                     # sem ligar para acento e maiúscula
    assert provisao.situacao == Situacao.OK and not provisao.gravar  # a célula continua como está (R7)
    assert not numero.provisao and not outro_texto.provisao
    assert nao_achou.situacao == Situacao.NAO_ENCONTRADO and not nao_achou.provisao   # sem valor achado, sem aviso


def test_r8_variacao_de_10_por_cento_ou_mais_fica_destacada():
    lancs = [lanc("30091", "110", "Fornecedor Exemplo NF. 1")]
    c = conferir_caso([regra(2, "30091", "fornecedor exemplo"), regra(3, "30091", "fornecedor exemplo"),
                       regra(4, "30091", "fornecedor exemplo"), regra(5, "30091", "fornecedor exemplo")],
                      lancs, [linha(2, anterior=100), linha(3, anterior=101), linha(4, anterior="encerrado"),
                              linha(5, anterior=0)])
    a, b, texto, zero = c.resultados
    assert (a.variacao, a.variacao_destacada) == (Decimal("10.00"), True)
    assert (b.variacao, b.variacao_destacada) == (Decimal("8.91"), False)
    assert texto.variacao is None and zero.variacao is None


def test_r9_nao_vinculados_conta_23334_e_estoque_fora():
    lancs = [lanc("30091", "10", "Fornecedor Exemplo NF. 1 - Licenca", "1"),
             lanc("30091", "20", "Fornecedor Exemplo NF. 2 - Outro produto", "2"),   # mesmo fornecedor, outra NF
             lanc("23334", "30", "Quem Sabe Ltda NF. 3", "3"),                         # fornecedores a reclassificar
             lanc("10131", "40", "Fornecedor Exemplo NF. 4", "4"),                    # estoque: fica de fora
             lanc("30091", "50", "Sem Contrato Ltda NF. 5", "5")]                     # fornecedor fora do Check list
    c = conferir_caso([regra(2, "30091", "fornecedor exemplo", descricao="licenca"),
                       regra(3, "30091", "encerrado ltda", tipo="ignorar")], lancs, [linha(2), linha(3)])
    assert [(n.lancamento.lancamento, n.motivo) for n in c.nao_vinculados] == [
        ("2", "Fornecedor do Check list sem linha correspondente"),
        ("3", "Conta 23334 - fornecedores a reclassificar")]


def test_r9_lancamento_descartado_pela_selecao_vira_nao_vinculado():
    lancs = [lanc("30091", "10", "Fornecedor Exemplo NF. 1", "1"), lanc("30091", "30", "Fornecedor Exemplo NF. 2", "2")]
    c = conferir_caso([regra(2, "30091", "fornecedor exemplo", selecao="maior")], lancs, [linha(2)])
    assert [n.lancamento.lancamento for n in c.nao_vinculados] == ["1"]


def test_r9_devolucao_aparece_nos_nao_vinculados():
    devolucao = lanc("20240", "99", "Fornecedor Exemplo NF. 9 - Devolucao NF 1 devido ao erro", "9")
    checklist = Checklist("chk.xlsx", 2026, 10, {"SC": AbaChecklist("SC", "HOSPITAL EXEMPLO", 19, 18, [linha(2)]),
                                                 "CMD": AbaChecklist("CMD", "CMD", 19, 18, [])})
    c = conferir({"SC": Movimento([], [devolucao]), "CMD": Movimento()}, checklist,
                 Configuracao(regras=[regra(2, "30091", "fornecedor exemplo")]))
    assert c.resultados[0].situacao == Situacao.NAO_ENCONTRADO              # a devolução não é candidata
    assert [n.motivo for n in c.nao_vinculados] == ["Devolução de NF (não é nota a conferir)"]


def test_r10_regra_cuja_linha_sumiu_vira_aviso():
    pulada = regra(2, "30091", "fornecedor exemplo")
    pulada.fornecedor_planilha, pulada.descricao_planilha = "Fornecedor Que Saiu", "Descrição"
    c = conferir_caso([pulada, regra(3, "30091", "fornecedor exemplo")], [], [linha(2), linha(3)])
    assert len(c.resultados) == 1 and "regra pulada" in c.avisos[0].mensagem


def test_cada_estabelecimento_so_ve_o_proprio_movimento():
    cmd = lanc("30091", "10", "Fornecedor Exemplo NF. 1", estabelecimento="CMD")
    checklist = Checklist("chk.xlsx", 2026, 10, {"SC": AbaChecklist("SC", "HOSPITAL EXEMPLO", 19, 18, [linha(2)]),
                                                 "CMD": AbaChecklist("CMD", "CMD", 19, 18, [linha(2)])})
    c = conferir({"SC": Movimento([]), "CMD": Movimento([cmd])}, checklist,
                 Configuracao(regras=[regra(2, "30091", "fornecedor exemplo"),
                                      regra(2, "30091", "fornecedor exemplo", aba="CMD")]))
    assert [r.situacao for r in c.resultados] == [Situacao.NAO_ENCONTRADO, Situacao.OK]


# ---------------------------------------------------------------------------
# Centro_Custo (ponto 13; regra dos dois contratos de locação de veículos, 28/10/2026)
# ---------------------------------------------------------------------------

def _com_centro(lancamento, *centros):
    lancamento.centros_custo = tuple((nome, lancamento.valor) for nome in centros)
    return lancamento


def _regras_veiculos():
    engenharia = regra(2, "30223", "locadora exemplo")
    engenharia.centro_custo = re.compile("engenharia clinica")
    argo = regra(3, "30223", "locadora exemplo")
    argo.centro_custo = re.compile("laboratorio|gerencia")
    return [engenharia, argo]


def test_centro_de_custo_separa_as_nfs_entre_as_linhas():
    lancs = [_com_centro(lanc("30223", "700", "Locadora Exemplo NF. 1 - Locacao de Veiculos", "1"), "Engenharia Clínica"),
             _com_centro(lanc("30223", "500", "Locadora Exemplo NF. 2 - Locacao de Veiculos", "2"),
                         "Laboratório de Análises Clínicas - Hospital Exemplo"),
             _com_centro(lanc("30223", "300", "Locadora Exemplo NF. 3 - Locacao de Veiculos", "3"), "Gerência"),
             _com_centro(lanc("30223", "900", "Locadora Exemplo NF. 4 - Locacao de Veiculos", "4"), "Transporte")]
    c = conferir_caso(_regras_veiculos(), lancs, [linha(2), linha(3)])
    assert [(r.situacao, r.valor) for r in c.resultados] == [
        (Situacao.OK, Decimal("700.00")), (Situacao.OK, Decimal("800.00"))]
    # a NF de outro centro de custo não some: vira não vinculada
    assert [(n.lancamento.lancamento, n.motivo) for n in c.nao_vinculados] == [
        ("4", "Centro de custo sem linha no Check list (Transporte)")]
    assert c.avisos == []


def test_centro_de_custo_sem_a_coluna_no_movimento_vira_manual():
    lancs = [lanc("30223", "700", "Locadora Exemplo NF. 1 - Locacao de Veiculos", "1"),
             lanc("30223", "500", "Locadora Exemplo NF. 2 - Locacao de Veiculos", "2")]
    c = conferir_caso(_regras_veiculos(), lancs, [linha(2), linha(3)])
    assert [r.situacao for r in c.resultados] == [Situacao.MANUAL, Situacao.MANUAL]
    assert all(len(r.candidatos) == 2 for r in c.resultados) and not any(r.gravar for r in c.resultados)
    assert len(c.avisos) == 2 and "centro de custo" in c.avisos[0].mensagem
