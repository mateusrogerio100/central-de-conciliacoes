"""
Testes da conferência de Cidade Zeta: leitor do PDF "Declaração Completa de Tomador",
conferência com os totais impressos, planilha e processar() de ponta a ponta.

- Casos sintéticos: linhas de texto montadas no teste (como o pdfplumber entrega),
  sem precisar gerar um PDF.
- Exemplos reais (exemplos/Exemplo_Cidade_Zeta, competência 09/2026): pula se não existirem.
"""

import shutil
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import load_workbook

from modulos.conferencia_iss.processamento import (
    MUNICIPIO_AV,
    MUNICIPIO_RB,
    MUNICIPIO_SJ,
    numeros_principais,
    previa_prefeitura,
)
from modulos.conferencia_iss.processar import processar
from modulos.conferencia_iss.leitor_prefeitura import LeituraPrefeitura
from modulos.conferencia_iss.leitor_prefeitura_av import _ler_linhas, _Linha, ler_relatorio_cidade_zeta
from modulos.conferencia_iss.modelos import (
    SITUACAO_CANCELADA_COM_TASY,
    SITUACAO_CANCELADA_SEM_TASY,
    SITUACAO_CONFERIDA,
    SITUACAO_DIVERGENCIA,
    SITUACAO_SOMENTE_PREFEITURA,
    SITUACAO_SOMENTE_TASY,
)
from modulos.conferencia_iss.relatorio_excel import ABA_CANCELADAS, ABA_CONFERIDAS, ABA_RESUMO
from modulos.conferencia_iss.resumo import linhas_do_resumo
from testes.conferencia_iss.pastas_exemplos import PASTA_EXEMPLOS, PASTA_RB, PASTA_SJ, caso_real

PASTA_AV = PASTA_EXEMPLOS / "Exemplo_Cidade_Zeta"
PDF_AV = "ISS Cidade Zeta.pdf"
CSVS_AV = ["Notas fiscais_HN_PJ.csv", "Notas fiscais_PJ.csv"]
AGORA = datetime(2026, 10, 2, 10, 50)


# ---------------------------------------------------------------------
# Linhas sintéticas (como saem do PDF)
# ---------------------------------------------------------------------
def _linha(texto: str, pagina: int = 1) -> _Linha:
    """Texto com campos separados por dois espaços → uma linha com palavras posicionadas."""
    palavras = [{"text": parte, "x0": 20.0 + 60 * i} for i, parte in enumerate(texto.split("  "))]
    return _Linha(pagina, 0.0, palavras)


def _nota(numero, cnpj, valor, prestador="PRESTADOR TESTE LTDA", pagina=1, quebra=False):
    """As 3 linhas de uma nota; com quebra=True, um rodapé de página no meio dela."""
    linhas = [
        _linha(f"Número:  {numero}  Competência:01/09/2026  {prestador}  Serviço:  R$ {valor}  "
               "Alíquota:  2,00%  Cofins:3,00 %  R$ 30,00  CSLL:  1,00 %  R$ 10,00", pagina),
        _linha(f"Emissão:05/09/2026  Espécie:  Prestação de Serviço  CNPJ/CPF:  {cnpj}  "
               "Optante?Não  Dedução:  R$ 0,00  Desc. Incond:  R$ 0,00  INSS:  0,00 %  R$ 0,00  "
               "IRRF:  1,50 %  R$ 15,00", pagina),
    ]
    if quebra:
        pagina += 1
        linhas.append(_linha("Usuário Logado: FUNDACAO  Impresso em: 02/10/2026 09:12:03", pagina - 1))
    linhas.append(_linha("Série:  NFSe Nacional  Exigibilidade:Exigível  Regime:  Não Possui  "
                         "ISS:  R$ 20,00  Incidência:  CIDADE ZETA-SP  PIS:  0,65 %  R$ 6,50", pagina))
    return linhas


CABECALHO = [
    _linha("PREFEITURA DA ESTANCIA TURISTICA DE CIDADE ZETA  Movimento"),
    _linha("DECLARAÇÃO COMPLETA DE TOMADOR"),
    _linha("Ano:  2026"),
    _linha("Mês:  9"),
    _linha("CPF/CNPJ  RG/Inscrição Estadual  Inscrição Municipal  Cadastro  Nome/Razão Social"),
    _linha("98.765.432/0010-89  ISENTO  000035604  000035604  FUNDACAO HOSPITAL EXEMPLO"),
    _linha("RELAÇÃO DAS NOTAS FISCAIS DO MOVIMENTO"),
]


def _ler(linhas) -> LeituraPrefeitura:
    leitura = LeituraPrefeitura(caminho=Path("teste.pdf"))
    _ler_linhas(linhas, leitura)
    return leitura


def _total(qtde, valor, situacao=""):
    nome = f"Qtde Notas {situacao}:" if situacao else "Qtde Notas:"
    return _linha(f"{nome}  {qtde}  Base Cálculo:R$ {valor}  Valor Nota:R$ {valor}  "
                  "Dedução:  R$ 0,00  Desc. Incond:  R$ 0,00  ISS:  R$ 0,00")


def _relatorio_basico():
    return (CABECALHO + [_linha("Normal"), _linha("Imposto Retido:  Não"),
                         _linha("Identificação  Prestador  Valores  Tributos Federais")]
            + _nota("10", "11.222.333/0001-81", "1.000,00")
            + _nota("11", "11.222.333/0001-81", "500,50")
            + [_total(2, "1.500,50"), _linha("Imposto Retido:  Sim")]
            + _nota("12", "44.555.666/0001-77", "99,90")
            + [_total(1, "99,90"), _total(3, "1.600,40", "Normais")])


# ---------------------------------------------------------------------
# Leitor — casos sintéticos
# ---------------------------------------------------------------------
def test_le_notas_sinteticas():
    leitura = _ler(_relatorio_basico())
    assert leitura.erro is None
    assert leitura.avisos == []
    assert leitura.competencia == "2026-09"
    assert leitura.competencia_texto == "setembro/2026"
    assert leitura.inscricao_municipal == "000035604"         # pela coluna, não pela ordem
    assert [l.numero for l in leitura.linhas] == ["10", "11", "12"]
    assert [l.imp_ret for l in leitura.linhas] == ["Não", "Não", "Sim"]

    nota = leitura.linhas[0]
    assert nota.documento == "11222333000181"
    assert nota.prestador == "PRESTADOR TESTE LTDA"
    assert nota.valor_doc == Decimal("1000.00")
    assert nota.valor_imposto == Decimal("20.00")
    assert nota.aliquota == "2,00%"
    assert nota.competencia == "01/09/2026"
    assert nota.data_emissao == "05/09/2026"
    assert nota.serie == "NFSe Nacional"
    assert nota.incidencia == "CIDADE ZETA-SP"
    assert (nota.valor_cofins, nota.valor_csll, nota.valor_irrf, nota.valor_pis) == (
        Decimal("30.00"), Decimal("10.00"), Decimal("15.00"), Decimal("6.50"))
    assert not nota.cancelada


def test_total_que_nao_bate_vira_aviso():
    linhas = _relatorio_basico()
    linhas[linhas.index(next(l for l in linhas if l.texto.startswith("Qtde Notas:  2")))] = (
        _total(3, "1.600,00"))
    leitura = _ler(linhas)
    assert any("não bate com o total impresso" in a.mensagem and "Imposto Retido: Não" in a.mensagem
               for a in leitura.avisos)


def test_sem_totais_avisa():
    linhas = [l for l in _relatorio_basico() if not l.texto.startswith("Qtde")]
    leitura = _ler(linhas)
    assert any("totais do PDF não foram encontrados" in a.mensagem for a in leitura.avisos)


def test_nota_que_continua_na_pagina_seguinte():
    linhas = (CABECALHO + [_linha("Normal"), _linha("Imposto Retido:  Não")]
              + _nota("10", "11.222.333/0001-81", "1.000,00", quebra=True)
              + _nota("11", "11.222.333/0001-81", "2,00", pagina=2)
              + [_total(2, "1.002,00")])
    leitura = _ler(linhas)
    assert leitura.avisos == []
    assert leitura.linhas[0].valor_imposto == Decimal("20.00")   # veio da página 2
    assert len(leitura.linhas) == 2


def test_secao_de_canceladas():
    linhas = (CABECALHO + [_linha("Normal"), _linha("Imposto Retido:  Não")]
              + _nota("10", "11.222.333/0001-81", "1.000,00")
              + [_total(1, "1.000,00"), _total(1, "1.000,00", "Normais"),
                 _linha("Cancelada"), _linha("Imposto Retido:  Não")]
              + _nota("11", "11.222.333/0001-81", "7,00")
              + [_total(1, "7,00"), _total(1, "7,00", "Canceladas")])
    leitura = _ler(linhas)
    assert leitura.avisos == []
    assert [l.cancelada for l in leitura.linhas] == [False, True]
    assert leitura.linhas[1].situacao_nf == "Cancelada"


def test_situacao_desconhecida_e_conferida_com_aviso():
    linhas = (CABECALHO + [_linha("Substituída"), _linha("Imposto Retido:  Não")]
              + _nota("10", "11.222.333/0001-81", "1,00") + [_total(1, "1,00")])
    leitura = _ler(linhas)
    assert not leitura.linhas[0].cancelada
    assert any("Substituída" in a.mensagem for a in leitura.avisos)


def test_linha_desconhecida_no_meio_das_notas_avisa():
    linhas = (CABECALHO + [_linha("Normal"), _linha("Imposto Retido:  Não")]
              + _nota("10", "11.222.333/0001-81", "1,00")
              + [_linha("Texto estranho 123 que ninguém espera")]
              + _nota("11", "11.222.333/0001-81", "1,00") + [_total(2, "2,00")])
    leitura = _ler(linhas)
    assert len(leitura.linhas) == 2
    assert any("linha não reconhecida" in a.mensagem for a in leitura.avisos)


def test_nota_com_numero_zero_avisa():
    linhas = (CABECALHO + [_linha("Normal"), _linha("Imposto Retido:  Não")]
              + _nota("0", "11.222.333/0001-81", "1,00") + [_total(1, "1,00")])
    leitura = _ler(linhas)
    assert any("número 0" in a.mensagem for a in leitura.avisos)


def test_sem_notas_e_erro():
    leitura = _ler(CABECALHO + [_total(0, "0,00")])
    assert "Nenhuma nota encontrada" in leitura.erro
    assert leitura.linhas == []


def test_arquivo_vazio_inexistente_e_nao_pdf(tmp_path):
    vazio = tmp_path / "vazio.pdf"
    vazio.write_bytes(b"")
    assert ler_relatorio_cidade_zeta(vazio).erro == "Arquivo vazio."
    assert "Não foi possível abrir" in ler_relatorio_cidade_zeta(tmp_path / "nao_existe.pdf").erro
    texto = tmp_path / "outro.pdf"
    texto.write_text("isto não é um pdf", encoding="utf-8")
    assert "não é um PDF" in ler_relatorio_cidade_zeta(texto).erro


def test_pdf_corrompido_vira_erro(tmp_path):
    ruim = tmp_path / "ruim.pdf"
    ruim.write_bytes(b"%PDF-1.5\n" + b"\x00" * 200)
    assert ler_relatorio_cidade_zeta(ruim).erro is not None


# ---------------------------------------------------------------------
# Leitor — arquivo real
# ---------------------------------------------------------------------
def _exige_exemplos_av():
    if not (PASTA_AV / PDF_AV).exists():
        pytest.skip("exemplos de Cidade Zeta não existem (dados reais ficam fora do git)")


def test_pdf_real_de_cidade_zeta():
    _exige_exemplos_av()
    leitura = ler_relatorio_cidade_zeta(PASTA_AV / PDF_AV)
    assert leitura.erro is None
    assert len(leitura.linhas) == 119
    assert leitura.competencia == "2026-09"
    assert leitura.inscricao_municipal == "000035604"
    assert sum(l.valor_doc for l in leitura.linhas) == Decimal("1118048.09")
    retidas = [l for l in leitura.linhas if l.imp_ret == "Sim"]
    assert len(retidas) == 25
    assert sum(l.valor_doc for l in retidas) == Decimal("468516.73")
    assert sum(l.valor_imposto for l in leitura.linhas) == Decimal("25625.01")
    # único aviso: a nota com número 0 (os totais do PDF bateram)
    assert len(leitura.avisos) == 1 and "número 0" in leitura.avisos[0].mensagem

    primeira = leitura.linhas[0]
    assert primeira.prestador == caso_real("av_8_5", "primeira_linha_prestador")
    assert primeira.valor_doc == Decimal("17489.10")
    # tributos federais lidos pelo rótulo (o texto simples do PDF vem embaralhado)
    assert (primeira.valor_cofins, primeira.valor_csll, primeira.valor_irrf,
            primeira.valor_pis) == (Decimal("524.67"), Decimal("174.89"),
                                    Decimal("262.34"), Decimal("113.68"))


# ---------------------------------------------------------------------
# processar() de ponta a ponta (gabarito Cidade Zeta)
# ---------------------------------------------------------------------
@pytest.fixture
def pasta_av(tmp_path):
    _exige_exemplos_av()
    for nome in CSVS_AV + [PDF_AV]:
        shutil.copy(PASTA_AV / nome, tmp_path / nome)
    return tmp_path


def test_cidade_zeta_ponta_a_ponta(pasta_av):
    resultado = processar([pasta_av / n for n in CSVS_AV], pasta_av / PDF_AV,
                          agora=AGORA, municipio=MUNICIPIO_AV)
    assert resultado.erro is None
    assert resultado.caminho_relatorio.name == (
        "Conferencia_ISS_AV_2026-09_Ame_-_Vale_do_Zeta_10h50.xlsx")

    contagens = {s: (n, l) for s, n, l, _, _ in linhas_do_resumo(resultado)}
    assert contagens[SITUACAO_CONFERIDA] == (115, 115)
    assert contagens[SITUACAO_DIVERGENCIA] == (1, 1)               # nº 8804027
    assert contagens[SITUACAO_SOMENTE_TASY] == (32, 0)
    assert contagens[SITUACAO_SOMENTE_PREFEITURA] == (0, 3)
    assert SITUACAO_CANCELADA_COM_TASY not in contagens
    assert SITUACAO_CANCELADA_SEM_TASY not in contagens
    assert numeros_principais(resultado).para_analisar == 4

    divergencia = next(i for i in resultado.itens if i.situacao == SITUACAO_DIVERGENCIA)
    assert divergencia.nota_tasy.nota_fiscal == "8804027"
    assert divergencia.diferenca == Decimal("48550.00")

    livro = load_workbook(resultado.caminho_relatorio)
    assert livro[ABA_RESUMO]["A1"].value == "Conferência ISS Cidade Zeta"
    assert ABA_CANCELADAS in livro.sheetnames
    titulos = [c.value for c in livro[ABA_CONFERIDAS][2]]
    assert titulos[5:7] == ["Valor do Serviço", "Diferença (mercadoria − Valor do Serviço)"]
    assert len(titulos) == len(set(titulos)) + 1        # só "CNPJ/CPF" repete (Tasy e prefeitura)
    textos = [str(l[0]) for l in livro[ABA_RESUMO].iter_rows(values_only=True) if l[0]]
    assert any("(148 de 148)" in t for t in textos)
    assert any("(119 de 119)" in t for t in textos)


def test_previa_cidade_zeta_e_pdf_nas_outras_cidades(pasta_av):
    previa = previa_prefeitura(pasta_av / PDF_AV, MUNICIPIO_AV)
    assert (previa.erro, previa.linhas, previa.competencia_texto) == (None, 119, "setembro/2026")
    for cidade in (MUNICIPIO_RB, MUNICIPIO_SJ):
        assert "aba Cidade Zeta" in previa_prefeitura(pasta_av / PDF_AV, cidade).erro


def test_relatorios_das_outras_cidades_no_item_cidade_zeta(tmp_path):
    if not PASTA_EXEMPLOS.exists():
        pytest.skip("pasta exemplos/ não existe (dados reais ficam fora do git)")
    rb = PASTA_RB / "Relatorio_de_Servicos_Contratados.xls"
    sj = PASTA_SJ / "nfe SJ.xls"
    for origem, item in ((rb, "aba Cidade Beta"), (sj, "aba Cidade Epsilon")):
        if not origem.exists():
            continue
        shutil.copy(origem, tmp_path / origem.name)
        assert item in previa_prefeitura(tmp_path / origem.name, MUNICIPIO_AV).erro

