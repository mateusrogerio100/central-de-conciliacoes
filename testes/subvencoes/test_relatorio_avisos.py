"""Testes do relatório Avisos_MM-AAAA.xlsx (seção 4.2 e R13)."""

from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest

from modulos.subvencoes.modelos import (
    ArquivoResumo,
    Aviso,
    Gravidade,
    MesReferencia,
    ResultadoProcessamento,
    StatusArquivo,
)
from modulos.subvencoes.processamento import processar
from modulos.subvencoes.relatorio_avisos import gerar_relatorio
from testes.subvencoes.conftest import MESES_EXEMPLO, arquivos_do_mes, ler_gabarito


@pytest.fixture(scope="module", params=MESES_EXEMPLO)
def relatorio(request, tmp_path_factory):
    mes_exemplo = request.param
    ano, mes = map(int, mes_exemplo.split("-"))
    arquivos = arquivos_do_mes(mes_exemplo)
    resultado = processar(arquivos.balancete, arquivos.patrimonio, [arquivos.subvencoes, arquivos.projetos],
                          tmp_path_factory.mktemp(f"rel_{mes_exemplo}"), MesReferencia(ano, mes))
    pasta = openpyxl.load_workbook(resultado.caminho_relatorio)
    return mes_exemplo, arquivos, resultado, pasta


def _linhas(aba):
    """Linhas da tabela (sem o título), como listas de valores."""
    return [list(l) for l in aba.iter_rows(min_row=2, values_only=True)]


def _titulos(aba):
    return [c.value for c in aba[1]]


def test_abas_e_titulos(relatorio):
    _, _, resultado, pasta = relatorio
    assert Path(resultado.caminho_relatorio).name == f"Avisos_{resultado.mes_referencia.para_nome_arquivo}.xlsx"
    assert pasta.sheetnames == ["Resumo", "Avisos", "Conferência", "Patrimônio"]
    assert _titulos(pasta["Avisos"]) == ["Gravidade", "Tipo", "Arquivo", "Aba", "Linha", "Conta", "Mensagem"]
    assert _titulos(pasta["Conferência"]) == [
        "Planilha", "Aba", "Linha", "Conta Contábil", "Convênio", "Descrição no balancete",
        "Saldo Patrimônio", "Saldo Contábil", "Patrimônio − Contábil", "Observação"]
    assert _titulos(pasta["Patrimônio"]) == [
        "Conta", "Soma dos bens", "Total do sistema", "Qtd itens lida", "Qtd do sistema", "Situação"]


def test_conferencia_tem_todas_as_linhas_com_valores_do_gabarito(relatorio):
    """R13: toda linha de conta de toda planilha aparece na aba Conferência."""
    _, arquivos, _, pasta = relatorio
    linhas = _linhas(pasta["Conferência"])
    gabarito = ler_gabarito(arquivos.gabarito)
    assert len(linhas) == len(gabarito) == 123
    for obtida, esperada in zip(linhas, gabarito):
        _, aba, linha, conta, convenio, _, sp, sc, dif, _ = obtida
        assert (aba, linha, conta, convenio) == \
               (esperada["aba"], esperada["linha"], esperada["conta_contabil"], esperada["convenio"])
        para_dec = lambda v: Decimal(repr(v)).quantize(Decimal("0.01"))
        assert para_dec(sp) == esperada["saldo_patrimonio"]
        assert para_dec(sc) == esperada["saldo_contabil"]
        assert para_dec(dif) == esperada["saldo_patrimonio"] - esperada["saldo_contabil"]
    assert pasta["Conferência"]["G2"].number_format == "#,##0.00;-#,##0.00"


def test_patrimonio_tem_todas_as_contas(relatorio):
    """R13: toda conta do patrimônio aparece, com situação (R8: não usadas sem aviso)."""
    mes_exemplo, _, resultado, pasta = relatorio
    linhas = _linhas(pasta["Patrimônio"])
    assert len(linhas) == 143
    situacoes = {l[0]: l[5] for l in linhas}
    assert situacoes["Bens em Comodato"] == "não usada"
    assert set(situacoes.values()) <= {"usada", "não usada", "total divergente", "cabeçalho ausente"}
    if mes_exemplo == "2026-07":
        assert situacoes["Convenio Federal 773672/2012"] == "cabeçalho ausente"
    else:
        assert situacoes["Convênio Federal 775214/2012"] == "total divergente"
    assert not any(a.conta == "Bens em Comodato" for a in resultado.avisos)


def test_avisos_todos_presentes(relatorio):
    _, _, resultado, pasta = relatorio
    linhas = _linhas(pasta["Avisos"])
    assert len(linhas) == len(resultado.avisos)
    assert {(l[1], l[3], l[4]) for l in linhas} == {(a.tipo, a.aba, a.linha) for a in resultado.avisos}


def test_resumo_lista_todos_os_arquivos(relatorio):
    """R13: todo arquivo de entrada aparece no Resumo com o que aconteceu."""
    _, arquivos, resultado, pasta = relatorio
    textos = [str(v) for l in pasta["Resumo"].iter_rows(values_only=True) for v in l if v is not None]
    for caminho in (arquivos.balancete, arquivos.patrimonio, arquivos.subvencoes, arquivos.projetos):
        assert caminho.name in textos
    assert str(resultado.mes_referencia) in textos
    for texto in ("Avisos por gravidade", "Arquivos de entrada", "Planilhas", "Total geral do patrimônio",
                  "Conferência por aba (soma do Saldo Contábil x conta sintética do balancete)"):
        assert texto in textos
    assert textos.count("sim") >= 5            # 4 abas (R9) + total geral do patrimônio


def test_avisos_ordenados_por_gravidade(tmp_path):
    resultado = ResultadoProcessamento(mes_referencia=MesReferencia(2026, 9), pasta_saida=str(tmp_path))
    resultado.arquivos.append(ArquivoResumo("c:/x/Balancete.xlsx", "Balancete", StatusArquivo.FALHOU,
                                            detalhe="Arquivo não encontrado"))
    resultado.avisos = [
        Aviso(Gravidade.INFO, "i1", "m"),
        Aviso(Gravidade.ATENCAO, "a1", "m"),
        Aviso(Gravidade.ERRO, "e1", "m"),
        Aviso(Gravidade.ATENCAO, "a2", "m"),
        Aviso(Gravidade.ERRO, "e2", "m"),
    ]
    caminho = gerar_relatorio(resultado, tmp_path / "Avisos_09-2026.xlsx")
    pasta = openpyxl.load_workbook(caminho)
    assert [l[1] for l in _linhas(pasta["Avisos"])] == ["e1", "e2", "a1", "a2", "i1"]
    # sem balancete/patrimônio: as abas existem, vazias, e o Resumo mostra a falha
    assert _linhas(pasta["Conferência"]) == [] and _linhas(pasta["Patrimônio"]) == []
    textos = [v for l in pasta["Resumo"].iter_rows(values_only=True) for v in l if v is not None]
    assert "falhou" in textos and "Arquivo não encontrado" in textos
