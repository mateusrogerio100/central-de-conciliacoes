"""R18: NFS-e no modelo da Prefeitura de São Paulo (decisão do usuário, 08/10/2026).

O modelo não traz competência, regime nem retenção do ISS: a nota é lida só para ir a
"lançar à mão" com os dados que tem. Os testes com texto fictício rodam sempre; o PDF real
(exemplos\\escrituracao_tomados\\Notas_Novas\\) só quando a pasta existe.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from modulos.escrituracao_tomados import configuracao as cfg
from modulos.escrituracao_tomados import leitor_danfse, leitor_nfse_sp, regras
from modulos.escrituracao_tomados.modelos import Competencia, Destino, ErroLeitura, NotaTomada
from testes.conftest import caso_real, pasta_exemplos

PAGINA_1 = """Número da Nota
PREFEITURA DO MUNICÍPIO DE SÃO PAULO
00000077
SECRETARIA MUNICIPAL DA FAZENDA Data e Hora de Emissão
05/08/2026 10:00:00
NOTA FISCAL ELETRÔNICA DE SERVIÇOS - NFS-e
Identificador Nacional: 35503081212345678000195000000000007726080000000001
PRESTADOR DE SERVIÇOS
CPF/CNPJ: 12.345.678/0001-95 Inscrição Municipal:1.234.567-8
Nome/Razão Social: CLINICA EXEMPLO LTDA
Endereço: RUA EXEMPLO 10 - CENTRO - CEP: 01000-000
Município: São Paulo UF: SP
TOMADOR DE SERVIÇOS
Nome/Razão Social: FUNDAÇÃO HOSPITAL EXEMPLO
CPF/CNPJ: 98.765.432/0001-98 Inscrição Municipal:----
Município: Cidade Alfa UF: SP E-mail: exemplo@exemplo.com.br
INTERMEDIÁRIO DE SERVIÇOS
CPF/CNPJ: ---- Nome/Razão Social: ----
DISCRIMINAÇÃO DE SERVIÇOS
Serviços médicos.
VALOR TOTAL DO SERVIÇO = R$ 1.500,00
Código do Serviço
04030 - Medicina e biomedicina.
Valor Total das Deduções (R$) Base de Cálculo (R$) Alíquota (%) Valor do ISS (R$) Crédito Programa da NFP (R$)
0,00 1.500,00 2,00% 30,00 0,00
"""
PAGINA_2 = """SERVIÇO PRESTADO
Local de prestação: 3550308 - São Paulo - SP Código indicador da operação: 100301
Localidade de incidência: 3516200 - Cidade Alfa - SP
"""


def test_identifica_o_modelo():
    assert leitor_nfse_sp.e_nfse_sp(PAGINA_1)
    assert not leitor_nfse_sp.e_nfse_sp("DANFSe v2.0 Documento Auxiliar da NFS-e")


def test_le_os_campos():
    nota = leitor_nfse_sp.ler_pdf([PAGINA_1, PAGINA_2], "nota_sp.pdf")
    assert (nota.numero, nota.data_emissao, nota.competencia) == (
        "77", date(2026, 8, 5), Competencia(2026, 8))                 # sem competência: mês da emissão
    assert (nota.prestador_documento, nota.prestador_nome) == ("12345678000195", "CLINICA EXEMPLO LTDA")
    assert (nota.prestador_cidade, nota.prestador_uf, nota.local_prestacao) == ("São Paulo", "SP", "São Paulo")
    assert nota.tomador_documento == "98765432000198"
    assert (nota.valor_servico, nota.deducoes, nota.aliquota, nota.valor_iss, nota.base_calculo) == (
        Decimal("1500.00"), Decimal("0.00"), Decimal("2.00"), Decimal("30.00"), Decimal("1500.00"))
    assert nota.codigo_atividade == "04030 - Medicina e biomedicina (código de São Paulo)"
    assert nota.iss_retido is None and nota.regime == ""
    assert nota.chave_acesso == "35503081212345678000195000000000007726080000000001"
    assert nota.motivo_leitura == cfg.SP_MOTIVO_LANCAR_A_MAO


def test_campo_obrigatorio_faltando_e_erro_de_leitura():
    with pytest.raises(ErroLeitura, match="Valor total do serviço"):
        leitor_nfse_sp.ler_pdf([PAGINA_1.replace("VALOR TOTAL DO SERVIÇO", "TOTAL"), PAGINA_2], "x.pdf")


def test_vai_para_lancar_a_mao_sem_codigo_retido():
    nota = leitor_nfse_sp.ler_pdf([PAGINA_1, PAGINA_2], "nota_sp.pdf")
    regras.classificar([nota])
    assert (nota.destino, nota.motivo) == (Destino.LANCAR_A_MAO, cfg.SP_MOTIVO_LANCAR_A_MAO)
    assert (nota.cfps, nota.codigo_retido) == ("002", "")         # retido: a pessoa confere no PDF
    assert regras.agrupar_para_arquivos([nota]) == []


def test_ja_escriturada_continua_ja_escriturada():
    from modulos.escrituracao_tomados import conferencia

    escrituradas = conferencia.NotasEscrituradas()
    escrituradas.por_chave[conferencia.chave_nota("77", "12345678000195")] = "resultado.csv"
    nota = leitor_nfse_sp.ler_pdf([PAGINA_1, PAGINA_2], "nota_sp.pdf")
    regras.classificar([nota], escrituradas)
    assert nota.destino is Destino.JA_ESCRITURADA


def test_mesma_nota_em_danfse_e_no_modelo_de_sp_vale_a_danfse(monkeypatch, tmp_path):
    for nome in ("a_sp.pdf", "b_danfse.pdf"):
        (tmp_path / nome).write_bytes(b"")

    def ler(caminho, nome):
        nota = NotaTomada(numero="77", data_emissao=date(2026, 8, 5), competencia=Competencia(2026, 8),
                          prestador_documento="12345678000195", prestador_nome="X",
                          chave_acesso="CHAVE", arquivo=nome)
        if nome == "a_sp.pdf":
            nota.motivo_leitura = cfg.SP_MOTIVO_LANCAR_A_MAO
        return nota

    monkeypatch.setattr(leitor_danfse, "ler_pdf", ler)
    sp, danfse = leitor_danfse.ler_pasta(tmp_path)[0]
    assert sp.destino is Destino.DUPLICADA and "b_danfse.pdf" in sp.motivo
    assert danfse.destino is None


def test_pdf_real_de_sao_paulo():
    pasta = pasta_exemplos("escrituracao_tomados", "Notas_Novas")
    notas, falhas = leitor_danfse.ler_pasta(pasta)
    assert falhas == [] and len(notas) == 1
    (nota,) = notas
    assert (nota.numero, nota.data_emissao, nota.prestador_documento) == (
        "545", date(2026, 8, 18), caso_real("escrituracao_tomados", "prestador_nota_sao_paulo_545"))
    assert (nota.valor_servico, nota.aliquota, nota.valor_iss) == (
        Decimal("10000.00"), Decimal("2.00"), Decimal("200.00"))
    regras.classificar(notas)
    assert nota.destino is Destino.LANCAR_A_MAO
