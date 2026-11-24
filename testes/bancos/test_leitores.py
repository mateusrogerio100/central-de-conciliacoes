"""Testes dos leitores de extrato e do identificador."""

import shutil
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from modulos.bancos import identificador
from modulos.bancos.identificador import (
    DUPLICADO,
    ERRO_DE_LEITURA,
    ESCANEADO,
    LIDO,
    MODELO_NAO_RECONHECIDO,
    aviso_pasta_errada,
    bancos_no_nome_da_pasta,
    identificar_pasta,
    processar_arquivo,
)
from modulos.bancos.leitores import LEITORES, LeitorBase, LeituraError
from modulos.bancos.leitores.bb_cdb import LeitorBBCDB
from modulos.bancos.leitores.bb_conta_corrente import LeitorBBContaCorrente
from modulos.bancos.leitores.bb_fundos import LeitorBBFundos
from modulos.bancos.leitores.bb_poupanca import LeitorBBPoupanca
from modulos.bancos.leitores.bb_rende_facil import LeitorBBRendeFacil
from modulos.bancos.leitores.cef_conta_corrente import LeitorCEFContaCorrente
from modulos.bancos.leitores.santander_conta_corrente import LeitorSantanderContaCorrente
from modulos.bancos.leitores.santander_contamax import saldo_do_mes
from modulos.bancos.leitores.sicoob_conta_corrente import LeitorSicoobContaCorrente
from modulos.bancos.util import extrair_texto_pdf
from testes.bancos.conftest import PASTA_EXTRATOS, PASTA_MODELOS, caminho_exemplo, caminho_modelo
from testes.bancos.gabarito import COMPETENCIA, ESCANEADO as GABARITO_ESCANEADO, GABARITO, GABARITO_MODELOS

# Modelos cujo leitor ainda não foi escrito: o teste do gabarito fica
# marcado como "falha esperada" (xfail) até a etapa correspondente.
MODELOS_PENDENTES: set[str] = set()


def _casos_gabarito():
    """Os PDFs de agosto (exemplos/2026-08) e os dos modelos novos (exemplos/modelos)."""
    casos = []
    for lista, localizar, prefixo in ((GABARITO, caminho_exemplo, ""),
                                      (GABARITO_MODELOS, caminho_modelo, "modelos/")):
        for esperado in lista:
            marcas = []
            if esperado.modelo in MODELOS_PENDENTES:
                marcas.append(pytest.mark.xfail(reason="leitor ainda não criado", strict=True))
            casos.append(pytest.param(esperado, localizar, id=prefixo + esperado.arquivo,
                                      marks=marcas))
    return casos


# ---------------------------------------------------------------------------
# Gabarito: cada PDF de exemplo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("esperado, localizar", _casos_gabarito())
def test_gabarito(esperado, localizar):
    arquivo = localizar(esperado.arquivo)
    resumo = processar_arquivo(arquivo, esperado.competencia)

    if esperado.modelo == GABARITO_ESCANEADO:
        assert resumo.situacao == ESCANEADO
        assert resumo.saldos == []
        return

    assert resumo.situacao == LIDO, resumo.mensagem
    assert resumo.modelo == esperado.modelo
    obtidos = [
        (s.banco, s.tipo, s.conta, s.saldo_total, s.saldo_bloqueado, s.fonte_secundaria)
        for s in resumo.saldos
    ]
    assert obtidos == [s.valores for s in esperado.saldos]
    for saldo in resumo.saldos:
        assert saldo.arquivo == arquivo
        assert saldo.modelo == esperado.modelo
        assert saldo.conta_original


def test_gabarito_cobre_todos_os_pdfs_de_exemplo():
    if not PASTA_EXTRATOS.is_dir():
        pytest.skip("pasta de exemplos não encontrada")
    nomes_pasta = sorted(a.name for a in PASTA_EXTRATOS.rglob("*.pdf"))
    assert nomes_pasta == sorted(e.arquivo for e in GABARITO)


def test_gabarito_cobre_todos_os_pdfs_de_modelos_novos():
    if not PASTA_MODELOS.is_dir():
        pytest.skip("pasta exemplos/modelos não encontrada")
    nomes_pasta = sorted(a.name for a in PASTA_MODELOS.rglob("*.pdf"))
    assert nomes_pasta == sorted(e.arquivo for e in GABARITO_MODELOS)


def test_nenhum_pdf_reconhecido_por_mais_de_um_leitor():
    pastas = [p for p in (PASTA_EXTRATOS, PASTA_MODELOS) if p.is_dir()]
    if not pastas:
        pytest.skip("pasta de exemplos não encontrada")
    for arquivo in (a for pasta in pastas for a in pasta.rglob("*.pdf")):
        texto = extrair_texto_pdf(arquivo)
        reconhecido_por = [l.nome for l in LEITORES if l.reconhece(texto)]
        assert len(reconhecido_por) <= 1, f"{arquivo.name}: {reconhecido_por}"


def test_leitores_com_nome_e_banco_unicos():
    nomes = [l.nome for l in LEITORES]
    assert len(nomes) == len(set(nomes))
    for leitor in LEITORES:
        assert leitor.nome and leitor.banco


# ---------------------------------------------------------------------------
# Regras dos leitores com textos sintéticos (casos que os PDFs não cobrem)
# ---------------------------------------------------------------------------

def _ler(classe, texto, competencia=COMPETENCIA):
    return classe().ler(texto, Path("teste.pdf"), competencia)


_TEXTO_CDB = """Extratos - CDB / RDB e BB Reaplic
Conta 1144-4 FUNDACAO
Período 01/08/2026 a 31/08/2026
31/08 Saldo final
valor capital 8.500,00
SALDO NOS ULTIMOS 6 MESES
Data Capital em ser Juros IR proj. Liquid.proj.
31/07/2026 8500,00 301,05 0,00 8801,05
https://autoatendimento.bb.com.br 1/2
06/09/26, 07:40 Banco do Brasil
28/08/2026 8500,00 390,00 0,00 8890,00
31/08/2026 8500,00 393,49 0,00 8893,49
RESUMO DOS DEPOSITOS EM SER
"""


def test_cdb_usa_liquido_projetado_da_ultima_data_do_mes():
    [saldo] = _ler(LeitorBBCDB, _TEXTO_CDB)
    assert saldo.saldo_total == Decimal("8893.49")     # não o capital 8.500,00


def test_cdb_sem_linha_do_mes_de_competencia_da_erro():
    with pytest.raises(LeituraError, match="09/2026"):
        _ler(LeitorBBCDB, _TEXTO_CDB, date(2026, 9, 1))


def test_cdb_zerado_com_saldo_final_zero():
    # Caso real (400706-9): resgatado antes do mês; tabela sem linha de agosto
    texto = """Extratos - CDB / RDB e BB Reaplic
Conta 400706-9 FUNDACAO
Período 01/08/2026 a 31/08/2026
31/08 Saldo final 0,00
SALDO NOS ULTIMOS 6 MESES
Data Capital em ser Juros IR proj. Liquid.proj.
30/06/2026 20500,00 0,00 0,00 20500,00
"""
    [saldo] = _ler(LeitorBBCDB, texto)
    assert saldo.saldo_total == 0
    assert "zerada" in saldo.observacao


def test_cdb_resumo_sem_tabela_continua_erro():
    # "Saldo final" seguido de "valor capital" não é aplicação zerada
    texto = """Extratos - CDB / RDB e BB Reaplic
Conta 400585-6 FUNDACAO
Período 01/08/2026 a 31/08/2026
31/08 Saldo final
valor capital 4.920.000,00
"""
    with pytest.raises(LeituraError, match="formato resumo.*use o extrato completo"):
        _ler(LeitorBBCDB, texto)


_RENDE_FACIL_SEM_DATA = """BB RENDE FÁCIL
Agência Conta
5113-6 400766-2
Resumo do mês - Agosto/2026
Saldo bruto em R$ 0,00
Aplicações no mês: R$ 0,00
Saldo bruto em : R$ {final}
31/08/2026 Saldo Final R$ 0,00 R$ 0,00 R$ 0,00 R$ 0,00 R$ 0,00
"""


def test_rende_facil_zerado():
    [saldo] = _ler(LeitorBBRendeFacil, _RENDE_FACIL_SEM_DATA.format(final="0,00"))
    assert saldo.saldo_total == 0
    assert "zerada" in saldo.observacao


def test_rende_facil_sem_data_com_valor_da_erro():
    with pytest.raises(LeituraError):
        _ler(LeitorBBRendeFacil, _RENDE_FACIL_SEM_DATA.format(final="10,00"))


def test_fundos_sem_movimento_vira_zero_com_aviso():
    texto = """Extratos - Investimentos Fundos - Mensal
Conta 1170-3 CONVENIO987996/2025
Mês/ano referência AGOSTO/2026
NÃO HOUVE MOVIMENTO NO PERÍODO SOLICITADO.
"""
    [saldo] = _ler(LeitorBBFundos, texto)
    assert saldo.saldo_total == 0
    assert "conferir" in saldo.observacao


def test_poupanca_com_bloqueado_tem_observacao():
    texto = """Extratos - Poupança
Agência / Conta 5113-6 / 1179-7
Período 01/08/2026 a 31/08/2026
Saldo atual 0,00 C
Saldo bloqueado 1.000,00 D
Saldo total 223.374,00 C
"""
    [saldo] = _ler(LeitorBBPoupanca, texto)
    assert saldo.saldo_total == Decimal("223374.00")
    assert saldo.saldo_bloqueado == Decimal("1000.00")
    assert "bloqueado" in saldo.observacao


def test_rende_facil_de_outro_mes_da_erro():
    texto = """BB RENDE FÁCIL
Agência Conta
5113-6 534-7
Resumo do mês - Agosto/2026
Saldo bruto em 31/07/2026 R$ 299,12
"""
    with pytest.raises(LeituraError, match="08/2026"):
        _ler(LeitorBBRendeFacil, texto)


def test_fundos_com_contagem_diferente_da_erro():
    texto = """Extratos - Investimentos Fundos - Mensal
Conta 400500-7 FUNDACAO
Mês/ano referência AGOSTO/2026
Fundo A - CNPJ: 1
Saldo Atual = 10,00
Fundo B - CNPJ: 2
"""
    with pytest.raises(LeituraError, match="2 fundo"):
        _ler(LeitorBBFundos, texto)


_POUPANCA_SETEMBRO = """Extratos - Poupança
Agência / Conta 5113-6 / 400755-7
Período 01/09/2026 a 07/09/2026
Saldo bloqueado 0,00 D
Saldo total 103.745,61 C
"""


def test_extrato_de_outro_periodo_da_erro():
    # Caso real: extrato de setembro na pasta de agosto (seria somado ao de agosto)
    with pytest.raises(LeituraError, match=r"outro período \(01/09/2026 a 07/09/2026\)"):
        _ler(LeitorBBPoupanca, _POUPANCA_SETEMBRO)


def test_poupanca_ate_o_dia_1_do_mes_seguinte_usa_o_saldo_total():
    # Decisão do usuário (06/11/2026): o BB tira a poupança "01/10 a 01/11"; o Saldo total bate com o balancete
    texto = _POUPANCA_SETEMBRO.replace("01/09/2026 a 07/09/2026", "01/08/2026 a 01/09/2026")
    [saldo] = _ler(LeitorBBPoupanca, texto, date(2026, 8, 1))
    assert saldo.saldo_total == Decimal("103745.61")
    assert saldo.observacao == "extrato vai até 01/09/2026: usado o Saldo total"
    for periodo in ("01/08/2026 a 02/09/2026", "01/07/2026 a 01/08/2026", "01/09/2026 a 01/10/2026"):
        with pytest.raises(LeituraError, match="outro período"):
            _ler(LeitorBBPoupanca, _POUPANCA_SETEMBRO.replace("01/09/2026 a 07/09/2026", periodo), date(2026, 8, 1))
    dezembro = _POUPANCA_SETEMBRO.replace("01/09/2026 a 07/09/2026", "01/12/2026 a 01/01/2027")
    assert _ler(LeitorBBPoupanca, dezembro, date(2026, 12, 1))[0].observacao.startswith("extrato vai até 01/01/2027")


def test_extrato_do_proprio_periodo_passa():
    [saldo] = _ler(LeitorBBPoupanca, _POUPANCA_SETEMBRO, date(2026, 9, 1))
    assert saldo.saldo_total == Decimal("103745.61")


@pytest.mark.parametrize("classe, texto", [
    (LeitorBBContaCorrente, "de 01 / 07 / 2026 até 31 / 07 / 2026"),
    (LeitorBBCDB, "Período 01/07/2026 a 31/07/2026"),
    (LeitorSantanderContaCorrente, "Período: 01/07/2026 a 31/07/2026 Data/Hora"),
    (LeitorSicoobContaCorrente, "Periodo: 01/07/2026 - 31/07/2026"),
    (LeitorBBRendeFacil, "Resumo do mês - Julho/2026"),
    (LeitorBBFundos, "Mês/ano referência JULHO/2026"),
    (LeitorCEFContaCorrente, "Mês: Julho/2026"),
])
def test_cada_leitor_confere_o_periodo(classe, texto):
    with pytest.raises(LeituraError, match="outro"):
        _ler(classe, texto)


def test_bb_conta_corrente_com_periodo_em_mes():
    texto = """BB Cash - Conta corrente - Extrato de conta corrente
Conta corrente 1144-4 FUNDACAO S C M CIDADE ALFA
Período do
{mes} / 2026
extrato
31/08/2026 0000 00000 S A L D O 300,25 C
"""
    [saldo] = _ler(LeitorBBContaCorrente, texto.format(mes="08"))
    assert saldo.saldo_total == Decimal("300.25")
    with pytest.raises(LeituraError, match=r"outro mês \(07/2026\)"):
        _ler(LeitorBBContaCorrente, texto.format(mes="07"))


_BB_ATE_01_09 = """BB Cash - Conta corrente - Extrato de conta corrente
Conta corrente 400585-6 FUNDACAO S C M CIDADE ALFA
Período do
de 01 / 08 / 2026 até 01 / 09 / 2026
extrato
29/07/2026 0000 00000 Saldo Anterior 0,00 C 0,00 C
31/08/2026 0000 00000 Resgate BB CDB DI 98 1.129.000,00 C
Cobrança referente 31/08/2026
31/08/2026 01/09/2026 0000 14060 Resgate BB CDB DI 1.411,92 C
31/08/2026 01/09/2026 0000 14060 Resgate BB CDB DI 2.012,50 C 3.424,42 C
01/09/2026 0000 00000 BB Rende Fácil 9.903 3.424,42 D
01/09/2026 0000 00000 S A L D O 0,00 C
"""


def test_bb_conta_corrente_extrato_ate_o_dia_seguinte_usa_saldo_do_fim_do_mes():
    # Caso real (400585-6): a linha S A L D O é de 01/09 e daria 0,00
    [saldo] = _ler(LeitorBBContaCorrente, _BB_ATE_01_09)
    assert saldo.saldo_total == Decimal("3424.42")
    assert "01/09/2026" in saldo.observacao


def test_bb_conta_corrente_sem_movimento_ate_o_dia_seguinte_usa_saldo_anterior():
    texto = """BB Cash - Conta corrente - Extrato de conta corrente
Conta corrente 400645-3 FUNDACAO S C M CIDADE ALFA
de 01 / 08 / 2026 até 01 / 09 / 2026
29/11/2023 0000 00000 Saldo Anterior 150,00 C 150,00 C
01/09/2026 0000 00000 S A L D O 150,00 C
"""
    [saldo] = _ler(LeitorBBContaCorrente, texto)
    assert saldo.saldo_total == Decimal("150.00")


def test_bb_conta_corrente_do_mes_seguinte_continua_erro():
    texto = _BB_ATE_01_09.replace("de 01 / 08 / 2026 até 01 / 09 / 2026",
                                  "de 01 / 09 / 2026 até 07 / 09 / 2026")
    with pytest.raises(LeituraError, match="outro período"):
        _ler(LeitorBBContaCorrente, texto)


def test_bb_conta_corrente_sem_lancamentos_e_sem_saldo_da_erro_claro():
    # Caso real (532-0, julho): o extrato não imprime saldo nenhum
    texto = """BB Cash - Conta corrente - Consulta autorizaveis - Extrato de conta corrente
Agência 5113-6
Conta 532-0
Período solicitado {mes} / 2026
Lançamentos
Sem lançamentos no período
"""
    with pytest.raises(LeituraError, match="sem saldo impresso.*conferir o saldo manualmente"):
        _ler(LeitorBBContaCorrente, texto.format(mes="08"))
    with pytest.raises(LeituraError, match=r"outro mês \(07/2026\)"):
        _ler(LeitorBBContaCorrente, texto.format(mes="07"))


_BB_TELA_CONSULTAS = """04/11/2026, 07:56 Banco do Brasil
Visualizar Pix agrupados
Consultas - Extrato de conta corrente 04/11/2026 07:56:12
Cliente - Conta atual
Agência 5113-6
Conta corrente 1192-4 FUNDACAO S C M CIDADE ALFA
Período do
de 01 / 10 / 2026 até 01 / 11 / 2026
extrato
02/09/2026 0000 00000 000 Saldo Anterior 0,00 C
02/10/2026 0000 13113 231 Tar Manuten Conta Ativa 812.750.700.102.861 73,00 D
02/10/2026 0000 00000 798 BB Rende Fácil 9.903 73,00 C 0,00 C
30/10/2026 31/10/2026 0000 14060 798 Resgate BB CDB DI 1.401.003.314.527 250,00 C 250,00 C
01/11/2026 0000 00000 351 BB Rende Fácil 9.903 250,00 D
01/11/2026 0000 00000 999 S A L D O 0,00 C
Transação efetuada com sucesso por: XX000000 PESSOA EXEMPLO.
https://autoatendimento.bb.com.br/apf-apj-autoatendimento/index.html 1/1
"""


def test_bb_conta_corrente_da_tela_consultas_do_autoatendimento():
    # Outubro/2026: extrato salvo da tela "Consultas", sem "BB Cash" no título
    assert LeitorBBContaCorrente().reconhece(_BB_TELA_CONSULTAS)
    [saldo] = _ler(LeitorBBContaCorrente, _BB_TELA_CONSULTAS, date(2026, 10, 1))
    assert saldo.conta == "11924"
    assert saldo.saldo_total == Decimal("250.00")       # saldo de 31/10, não o S A L D O de 01/11
    assert "01/11/2026" in saldo.observacao
    reconhecido_por = [l.nome for l in LEITORES if l.reconhece(_BB_TELA_CONSULTAS)]
    assert reconhecido_por == ["BB - Conta corrente"]


def test_bb_conta_corrente_sem_bb_cash_nem_tela_consultas_nao_e_reconhecido():
    texto = _BB_TELA_CONSULTAS.replace("Consultas - ", "")
    assert not LeitorBBContaCorrente().reconhece(texto)


def test_pdf_reconhecido_por_varios_modelos_explica_o_motivo():
    arquivo = caminho_exemplo("1179 7.pdf")
    leitores = [_LeitorQueReconheceTudo("Modelo X"), _LeitorQueReconheceTudo("Modelo Y")]
    resumo = processar_arquivo(arquivo, COMPETENCIA, leitores)
    assert "vários extratos juntos" in resumo.mensagem
    assert "OCR" in resumo.mensagem


def test_extrato_sem_periodo_da_erro():
    with pytest.raises(LeituraError, match="período"):
        _ler(LeitorBBPoupanca, "Extratos - Poupança\nSaldo total 1,00 C\n")


def test_cef_ultima_linha_sem_coluna_saldo_da_erro():
    texto = """Extrato por período
Conta: 4282 | 1292 | 000568630703-9
Mês: Agosto/2026
19/08/2026 191001 ENVIO TEV 539.300,00 D
SAC CAIXA: 0800 726 0101
"""
    with pytest.raises(LeituraError, match="Saldo"):
        _ler(LeitorCEFContaCorrente, texto)


_SANTANDER_CC = """Internet Banking Empresarial
FUNDACAO Agência: 3431 Conta: 130030239
Conta Corrente > Extrato
Período: 01/08/2026 a 31/08/2026 Data/Hora: 07/09/2026 às 20:51h
Data Histórico Documento Valor Saldo
06/08/2026 SALDO ANTERIOR 000000 1.000,00
{lancamentos}A - Saldo de Conta Corrente 23.627,15
B - Saldo Bloqueado {bloqueado}
C - Saldo Disponível Conta Corrente (A - B) 23.627,15
D - Saldo em Investimentos com Resgate Automático 310,72
"""


def test_santander_cc_usa_ultimo_saldo_da_lista_e_nao_o_quadro_resumo():
    # Caso real (13003023-9): a linha A (23.627,15) é o saldo na data de emissão
    lancamentos = """28/08/2026 PIX RECEBIDO 39053344705 000000 36,00 70.776,84
TED RECEBIDA TRANSFERENCIA EN
31/08/2026 000000 8.668,50
31/08/2026 025860 -61.804,00 17.641,34
"""
    [cc] = _ler(LeitorSantanderContaCorrente,
                _SANTANDER_CC.format(lancamentos=lancamentos, bloqueado="0,00"))
    assert (cc.tipo, cc.saldo_total, cc.fonte_secundaria) == ("CC", Decimal("17641.34"), False)


def test_santander_cc_nao_usa_mais_o_item_d():
    saldos = _ler(LeitorSantanderContaCorrente,
                  _SANTANDER_CC.format(lancamentos="", bloqueado="0,00"))
    assert [s.tipo for s in saldos] == ["CC"]


def test_santander_cc_sem_movimento_usa_saldo_anterior():
    [cc] = _ler(LeitorSantanderContaCorrente,
                _SANTANDER_CC.format(lancamentos="", bloqueado="0,00"))
    assert cc.saldo_total == Decimal("1000.00")


def test_santander_cc_com_saldo_negativo():
    lancamentos = "31/08/2026 010806 -2.040,00 - 1.040,00\n"
    [cc] = _ler(LeitorSantanderContaCorrente,
                _SANTANDER_CC.format(lancamentos=lancamentos, bloqueado="0,00"))
    assert cc.saldo_total == Decimal("-1040.00")


def test_santander_cc_bloqueado_no_quadro_vira_observacao():
    [cc] = _ler(LeitorSantanderContaCorrente,
                _SANTANDER_CC.format(lancamentos="", bloqueado="50,00"))
    assert cc.saldo_bloqueado == 0
    assert "bloqueado" in cc.observacao and "conferir" in cc.observacao


def test_santander_cc_extrato_ate_o_dia_seguinte_usa_saldo_do_fim_do_mes():
    # Caso real (outubro/2026): extratos de 01/10 a 01/11; a linha de 01/09 aqui não pode contar
    lancamentos = """31/08/2026 025860 -500,00 500,00
01/09/2026 PIX RECEBIDO 000000 300,00 800,00
"""
    texto = _SANTANDER_CC.format(lancamentos=lancamentos, bloqueado="0,00").replace(
        "01/08/2026 a 31/08/2026", "01/08/2026 a 01/09/2026")
    [cc] = _ler(LeitorSantanderContaCorrente, texto)
    assert cc.saldo_total == Decimal("500.00")
    assert "01/09/2026" in cc.observacao and "31/08/2026" in cc.observacao


def test_santander_cc_que_comeca_no_mes_seguinte_continua_erro():
    texto = _SANTANDER_CC.format(lancamentos="", bloqueado="0,00").replace(
        "01/08/2026 a 31/08/2026", "01/09/2026 a 07/09/2026")
    with pytest.raises(LeituraError, match="outro período"):
        _ler(LeitorSantanderContaCorrente, texto)


def _linhas_contamax(final_agosto="132,59", resgates_julho="314.517,99"):
    # Colunas já separadas, como saem da leitura por posição
    def linha(mes, anterior, aplicacoes, resgates, rendimento, final):
        return {"mes": mes, "anterior": anterior, "aplicacoes": aplicacoes,
                "resgates": resgates, "rendimento_total": rendimento, "final": final}
    return [
        linha("Julho 2026", "10,93", "314.517,99", resgates_julho, "1,65", "12,58"),
        linha("Agosto 202", "12,58", "160,00", "40,00", "0,01", final_agosto),
        linha("Setembro 2", "132,59", "385.871,39", "385.871,39", "1,99", "134,58"),
    ]


@pytest.mark.parametrize("competencia, esperado", [
    (date(2026, 7, 1), "12.58"),
    (date(2026, 8, 1), "132.59"),
    (date(2026, 9, 1), "134.58"),
])
def test_contamax_pega_a_linha_do_mes(competencia, esperado):
    assert saldo_do_mes(_linhas_contamax(), competencia) == Decimal(esperado)


def test_contamax_linha_que_nao_fecha_da_erro():
    with pytest.raises(LeituraError, match="não fecha"):
        saldo_do_mes(_linhas_contamax(final_agosto="999,99"), COMPETENCIA)


def test_contamax_valor_cortado_pelo_banco_da_erro():
    # Caso real (13000305-3, julho): "1.055.925,67" sai como "055.925,67"
    with pytest.raises(LeituraError, match="não fecha"):
        saldo_do_mes(_linhas_contamax(resgates_julho="014.517,99"), date(2026, 7, 1))


def _linhas_contamax_do_navegador():
    # Caso real (outubro/2026, PDF salvo pelo Chrome): o ano vaza para o Saldo Bruto Anterior
    def linha(mes, anterior, aplicacoes, resgates, final):
        return {"mes": mes, "anterior": anterior, "aplicacoes": aplicacoes,
                "resgates": resgates, "rendimento_total": "0,00", "final": final}
    return [
        linha("Setembro 2", "0,00", "0,00", "0,00", "0,00"),
        linha("Outubro 20", "2\xa00,00", "950,00", "950,00", "0,00"),
        linha("Novembro", "2\xa00,00", "100,00", "0,00", "100,00"),
    ]


def test_contamax_ano_que_vaza_para_a_coluna_de_valor_e_ignorado():
    assert saldo_do_mes(_linhas_contamax_do_navegador(), date(2026, 10, 1)) == Decimal("0.00")


def test_contamax_mes_com_o_ano_cortado_inteiro():
    assert saldo_do_mes(_linhas_contamax_do_navegador(), date(2026, 11, 1)) == Decimal("100.00")


def test_contamax_ano_que_vaza_continua_conferido_pela_conta_do_saldo():
    linhas = _linhas_contamax_do_navegador()
    linhas[1]["final"] = "2\xa0950,00"
    with pytest.raises(LeituraError, match="não fecha"):
        saldo_do_mes(linhas, date(2026, 10, 1))


def test_contamax_mes_ausente_da_erro():
    with pytest.raises(LeituraError, match="10/2026"):
        saldo_do_mes(_linhas_contamax(), date(2026, 10, 1))


def test_sicoob_bloqueado_judicial_soma_e_tem_observacao():
    texto = """EXTRATO DE CONTA CORRENTE
Cooperativa: 4321-4 / SICOOB 3 COLINAS
Conta: 2.004.834-3 / FUNDACAO
Periodo: 01/08/2026 - 31/08/2026
RESUMO
Saldo em conta: 1.000,00C
Saldo disponível: 1.000,00C
Saldo bloqueado (cheques): 50,00C*
Saldo bloqueado (judicial): 200,00C
"""
    [saldo] = _ler(LeitorSicoobContaCorrente, texto)
    assert saldo.saldo_total == Decimal("1250.00")
    assert saldo.saldo_bloqueado == Decimal("250.00")
    assert saldo.saldo_disponivel == Decimal("1000.00")
    assert "judicial" in saldo.observacao


# ---------------------------------------------------------------------------
# Identificador com pastas temporárias
# ---------------------------------------------------------------------------

def _copiar(origem: Path, destino: Path) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(origem, destino)
    return destino


def _por_nome(resultado):
    return {r.arquivo.name: r for r in resultado.arquivos}


def test_subpastas_encontradas_e_duplicado_ignorado(tmp_path):
    pdf = caminho_exemplo("1179 7.pdf")
    _copiar(pdf, tmp_path / "Banco do Brasil" / "Conta Corrente" / "1179 7.pdf")
    _copiar(pdf, tmp_path / "outra pasta" / "copia.pdf")
    (tmp_path / "anotacoes.txt").write_text("não é extrato")
    _copiar(pdf, tmp_path / "~$temporario.pdf")

    resultado = identificar_pasta(tmp_path, COMPETENCIA)
    arquivos = _por_nome(resultado)

    assert set(arquivos) == {"1179 7.pdf", "copia.pdf"}
    original = arquivos["1179 7.pdf"]
    assert original.situacao == LIDO
    assert original.subpasta == str(Path("Banco do Brasil", "Conta Corrente"))
    assert original.mensagem == ""          # subpasta dentro da pasta do BB: sem aviso
    copia = arquivos["copia.pdf"]
    assert copia.situacao == DUPLICADO
    assert "1179 7.pdf" in copia.mensagem
    assert copia.saldos == []
    assert len(resultado.saldos) == 1       # o saldo não é contado duas vezes


def test_pdf_do_bb_na_pasta_sicoob_tem_aviso(tmp_path):
    pdf = caminho_exemplo("1179 7.pdf")
    _copiar(pdf, tmp_path / "Sicoob" / "1179 7.pdf")

    resumo = identificar_pasta(tmp_path, COMPETENCIA).arquivos[0]

    assert resumo.situacao == LIDO
    assert resumo.modelo == "BB - Conta corrente"
    assert resumo.saldos[0].conta == "11797"
    assert resumo.saldos[0].saldo_total == 0
    assert resumo.mensagem == 'Aviso: extrato do BB encontrado na pasta "Sicoob"'


def test_pdf_do_bb_na_pasta_banco_do_brasil_sem_aviso(tmp_path):
    pdf = caminho_exemplo("1179 7.pdf")
    _copiar(pdf, tmp_path / "Banco do Brasil" / "1179 7.pdf")

    resumo = identificar_pasta(tmp_path, COMPETENCIA).arquivos[0]

    assert resumo.situacao == LIDO
    assert resumo.mensagem == ""


def test_progresso_avisado_a_cada_arquivo(tmp_path):
    pdf = caminho_exemplo("1179 7.pdf")
    _copiar(pdf, tmp_path / "a.pdf")
    (tmp_path / "b.pdf").write_bytes(b"quebrado")
    chamadas = []
    identificar_pasta(tmp_path, COMPETENCIA,
                      progresso=lambda n, total, arquivo: chamadas.append((n, total, arquivo.name)))
    assert chamadas == [(1, 2, "a.pdf"), (2, 2, "b.pdf")]


def test_pdf_direto_na_pasta_selecionada_sem_aviso(tmp_path):
    _copiar(caminho_exemplo("1179 7.pdf"), tmp_path / "1179 7.pdf")
    resumo = identificar_pasta(tmp_path, COMPETENCIA).arquivos[0]
    assert (resumo.situacao, resumo.subpasta, resumo.mensagem) == (LIDO, "", "")


def test_pdf_escaneado_e_pdf_quebrado_nao_interrompem_o_lote(tmp_path):
    _copiar(caminho_exemplo("Aplicações ok.pdf"), tmp_path / "Aplicações ok.pdf")
    (tmp_path / "quebrado.pdf").write_bytes(b"isto nao e um pdf")
    _copiar(caminho_exemplo("1179 7.pdf"), tmp_path / "zz 1179 7.pdf")

    arquivos = _por_nome(identificar_pasta(tmp_path, COMPETENCIA))

    assert arquivos["Aplicações ok.pdf"].situacao == ESCANEADO
    assert arquivos["quebrado.pdf"].situacao == ERRO_DE_LEITURA
    assert arquivos["quebrado.pdf"].mensagem
    assert arquivos["zz 1179 7.pdf"].situacao == LIDO


# ---------------------------------------------------------------------------
# Identificador com leitores de mentira (regras de reconhecimento)
# ---------------------------------------------------------------------------

class _LeitorQueReconheceTudo(LeitorBase):
    banco = "TESTE"

    def __init__(self, nome, erro=None, saldos=None):
        self.nome = nome
        self.erro = erro
        self.saldos = saldos or []

    def reconhece(self, texto):
        return True

    def ler(self, texto, arquivo, competencia):
        if self.erro:
            raise self.erro
        return self.saldos


def test_reconhecido_por_dois_leitores_vira_erro():
    arquivo = caminho_exemplo("1179 7.pdf")
    leitores = [_LeitorQueReconheceTudo("Modelo X"), _LeitorQueReconheceTudo("Modelo Y")]
    resumo = processar_arquivo(arquivo, COMPETENCIA, leitores)
    assert resumo.situacao == ERRO_DE_LEITURA
    assert resumo.mensagem.startswith("reconhecido por mais de um modelo: Modelo X, Modelo Y.")


def test_erro_do_leitor_vira_erro_de_leitura_com_mensagem():
    arquivo = caminho_exemplo("1179 7.pdf")
    leitor = _LeitorQueReconheceTudo("Modelo X", erro=LeituraError("saldo não encontrado"))
    resumo = processar_arquivo(arquivo, COMPETENCIA, [leitor])
    assert (resumo.situacao, resumo.modelo, resumo.mensagem) == (
        ERRO_DE_LEITURA, "Modelo X", "saldo não encontrado")


def test_leitor_sem_saldos_vira_erro():
    arquivo = caminho_exemplo("1179 7.pdf")
    resumo = processar_arquivo(arquivo, COMPETENCIA, [_LeitorQueReconheceTudo("Modelo X")])
    assert resumo.situacao == ERRO_DE_LEITURA


def test_nenhum_leitor_reconhece():
    arquivo = caminho_exemplo("1179 7.pdf")
    resumo = processar_arquivo(arquivo, COMPETENCIA, [])
    assert resumo.situacao == MODELO_NAO_RECONHECIDO


# ---------------------------------------------------------------------------
# Aviso de pasta errada (só pelo nome da pasta)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nome, esperado", [
    ("Banco do Brasil", {"BB"}),
    ("Extratos BB Agosto", {"BB"}),
    ("Caixa Econômica Federal - Extratos", {"CEF"}),
    ("CEF", {"CEF"}),
    ("SANTANDER", {"SANTANDER"}),
    ("sicoob", {"SICOOB"}),
    ("BB e Sicoob", {"BB", "SICOOB"}),
    ("agosto", set()),
    ("Aplicações", set()),
    ("Conta Corrente", set()),
    ("abbc", set()),                # "bb" dentro de outra palavra não conta
    ("caixinha", set()),
])
def test_bancos_no_nome_da_pasta(nome, esperado):
    assert bancos_no_nome_da_pasta(nome) == esperado


@pytest.mark.parametrize("caminho, banco, esperado", [
    ("Sicoob", "BB", 'Aviso: extrato do BB encontrado na pasta "Sicoob"'),
    ("Banco do Brasil/Aplicações", "BB", ""),
    ("Santander/Aplicações", "BB", 'Aviso: extrato do BB encontrado na pasta "Santander"'),
    ("BB e Sicoob", "CEF", ""),     # dois bancos no nome: sem aviso
    ("agosto", "CEF", ""),
    ("", "BB", ""),
])
def test_aviso_pasta_errada(caminho, banco, esperado):
    assert aviso_pasta_errada(Path(caminho), banco) == esperado


# ---------------------------------------------------------------------------
# Checagem rápida de PDF sem texto
# ---------------------------------------------------------------------------

def test_escaneado_nao_passa_pela_leitura_lenta(monkeypatch):
    """PDF sem texto vira ESCANEADO pela checagem rápida, sem chamar o pdfplumber."""
    arquivo = caminho_exemplo("Aplicações ok.pdf")

    def nao_deveria_chamar(_arquivo):
        raise AssertionError("leitura lenta chamada para PDF sem texto")

    monkeypatch.setattr(identificador, "extrair_paginas_pdf", nao_deveria_chamar)
    resumo = processar_arquivo(arquivo, COMPETENCIA)
    assert resumo.situacao == ESCANEADO
    assert resumo.mensagem.startswith("PDF sem texto (")


def _pdf_sem_texto(caminho: Path, produtor: str) -> Path:
    """PDF de uma página em branco (sem texto), com o "Producer" informado: fictício, montado à mão."""
    objetos = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >>",
        f"<< /Producer ({produtor}) >>",
    ]
    conteudo = b"%PDF-1.4\n"
    posicoes = []
    for numero, objeto in enumerate(objetos, 1):
        posicoes.append(len(conteudo))
        conteudo += f"{numero} 0 obj\n{objeto}\nendobj\n".encode("latin-1")
    inicio_xref = len(conteudo)
    conteudo += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    conteudo += b"".join(f"{p:010d} 00000 n \n".encode() for p in posicoes)
    conteudo += (f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R /Info 4 0 R >>\n"
                 f"startxref\n{inicio_xref}\n%%EOF\n").encode()
    caminho.write_bytes(conteudo)
    return caminho


def test_escaneado_do_microsoft_print_to_pdf_diz_como_salvar_de_novo(tmp_path):
    # Pedido do usuário (12/11/2026): o aviso diz por que o PDF não foi lido e como refazer
    arquivo = _pdf_sem_texto(tmp_path / "308-5 - Conta corrente.pdf", "Microsoft: Print To PDF")
    resumo = processar_arquivo(arquivo, COMPETENCIA)
    assert resumo.situacao == ESCANEADO
    assert resumo.mensagem.startswith("PDF sem texto (1 página(s)): foi salvo pelo \"Microsoft Print to PDF\"")
    assert "Salvar como PDF" in resumo.mensagem


def test_escaneado_de_outra_origem_mantem_a_mensagem(tmp_path):
    arquivo = _pdf_sem_texto(tmp_path / "scanner.pdf", "Scanner Qualquer 1.0")
    resumo = processar_arquivo(arquivo, COMPETENCIA)
    assert (resumo.situacao, resumo.mensagem) == (ESCANEADO, "PDF sem texto (1 página(s)); provavelmente escaneado")


def test_checagem_rapida_com_erro_segue_o_caminho_normal(monkeypatch):
    """Se a checagem rápida falhar, o arquivo é lido como antes (pdfplumber)."""
    arquivo = caminho_exemplo("1179 7.pdf")

    def falha(_arquivo):
        raise RuntimeError("pdfium indisponível")

    monkeypatch.setattr(identificador, "extrair_paginas_rapido", falha)
    resumo = processar_arquivo(arquivo, COMPETENCIA)
    assert resumo.situacao == LIDO
