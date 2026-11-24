"""
Teste ponta a ponta (Etapa 6): roda processar() como a interface vai rodar e confere
o gabarito da seção 8 no Resultado e no .xlsx gerado.

Os exemplos são copiados para uma pasta temporária (o relatório é salvo na pasta do
arquivo da prefeitura e não deve cair dentro de exemplos/).
"""

import importlib
import shutil
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import load_workbook

from modulos.conferencia_iss.processar import processar
from modulos.conferencia_iss.modelos import (
    NIVEL_ERRO,
    NIVEL_OK,
    SITUACAO_CONFERIDA,
    SITUACAO_CONFERIDA_AJUSTADO,
    SITUACAO_DIVERGENCIA,
    SITUACAO_SOMENTE_PREFEITURA,
    SITUACAO_SOMENTE_TASY,
    situacao_escriturada_varias_vezes,
)
from modulos.conferencia_iss.processar import nome_do_relatorio, nome_para_arquivo
from modulos.conferencia_iss.relatorio_excel import (
    ABA_AVISOS,
    ABA_CONFERIDAS,
    ABA_DIVERGENCIA,
    ABA_ESCRITURADAS,
    ABA_RESUMO,
    ABA_SOMENTE_PREFEITURA,
    ABA_SOMENTE_TASY,
)

from testes.conferencia_iss.pastas_exemplos import PASTA_EXEMPLOS, PASTA_RB  # noqa: E402
SERVICO = "Servico_PJ_RB.csv"
HONORARIO = "Honorario_PJ_RB.csv"
PREFEITURA = "Relatorio_de_Servicos_Contratados.xls"
PF = "Notas_fiscais_PF_exemplo.csv"
AGORA = datetime(2026, 10, 1, 14, 5)
ESCRITURADA_2 = situacao_escriturada_varias_vezes(2)
# O módulo (não a função de mesmo nome exposta em conferencia/__init__.py)
MODULO_PROCESSAR = importlib.import_module("modulos.conferencia_iss.processar")


@pytest.fixture
def pasta(tmp_path):
    if not PASTA_EXEMPLOS.exists():
        pytest.skip("pasta exemplos/ não existe (dados reais ficam fora do git)")
    for nome in (SERVICO, HONORARIO, PREFEITURA):
        shutil.copy(PASTA_RB / nome, tmp_path / nome)
    shutil.copy(PASTA_EXEMPLOS / "pf" / PF, tmp_path / PF)
    return tmp_path


def _por_nota(resultado):
    vistas = {}
    for item in resultado.itens:
        if item.nota_tasy is not None:
            vistas.setdefault(item.situacao, {})[id(item.nota_tasy)] = item.nota_tasy.valor_mercadoria
    return {s: (len(v), sum(v.values(), Decimal(0))) for s, v in vistas.items()}


def _linhas_dados(aba):
    return [l for l in aba.iter_rows(min_row=3, values_only=True) if any(l)]


# ---------------------------------------------------------------------
# 8.1 — Serviço + Honorário + prefeitura
# ---------------------------------------------------------------------
def test_gabarito_8_1_ponta_a_ponta(pasta):
    progresso = []
    resultado = processar(
        [pasta / SERVICO, pasta / HONORARIO], pasta / PREFEITURA,
        ao_progredir=lambda p, m: progresso.append((p, m)), agora=AGORA,
    )
    assert resultado.erro is None

    # Leitura
    assert len(resultado.notas_tasy) == 159
    assert sum(n.valor_mercadoria for n in resultado.notas_tasy) == Decimal("1916004.54")
    assert resultado.unidades == ["AME Cidade Beta"]
    assert len(resultado.linhas_prefeitura) == 130
    assert resultado.competencia == "2026-09"
    assert resultado.inscricao_municipal == "20164715"

    # Resultado por situação
    contagem = _por_nota(resultado)
    assert contagem[SITUACAO_CONFERIDA] == (118, Decimal("1448484.54"))
    assert contagem[SITUACAO_CONFERIDA_AJUSTADO] == (1, Decimal("6927.15"))
    assert contagem[ESCRITURADA_2] == (4, Decimal("15412.39"))
    assert SITUACAO_DIVERGENCIA not in contagem
    assert contagem[SITUACAO_SOMENTE_TASY] == (36, Decimal("445180.46"))
    somente_pref = [i for i in resultado.itens if i.situacao == SITUACAO_SOMENTE_PREFEITURA]
    assert len(somente_pref) == 3
    assert sum(i.linha_prefeitura.valor_doc or 0 for i in somente_pref) == Decimal("9979.71")

    # Avisos: nenhum erro; 3 registros de arquivo "OK"; 1 aviso de valor vazio
    assert not any(a.nivel == NIVEL_ERRO for a in resultado.avisos)
    arquivos = [a for a in resultado.avisos if a.tipo_arquivo]
    assert [(a.arquivo, a.nivel, a.linhas_lidas) for a in arquivos] == [
        (SERVICO, NIVEL_OK, 75), (HONORARIO, NIVEL_OK, 84), (PREFEITURA, NIVEL_OK, 130),
    ]
    outros = [a for a in resultado.avisos if not a.tipo_arquivo]
    assert len(outros) == 1 and "Valor do Doc. vazio" in outros[0].mensagem

    # Arquivo gerado: nome e pasta
    caminho = resultado.caminho_relatorio
    assert caminho.parent == pasta
    assert caminho.name == "Conferencia_ISS_RB_2026-09_AME_Cidade_Beta_14h05.xlsx"
    assert caminho.exists()

    # Progresso chega a 100
    assert progresso[-1][0] == 100
    assert [p for p, _ in progresso] == sorted(p for p, _ in progresso)


def test_gabarito_8_1_planilha(pasta):
    resultado = processar([pasta / SERVICO, pasta / HONORARIO], pasta / PREFEITURA, agora=AGORA)
    livro = load_workbook(resultado.caminho_relatorio)
    assert len(_linhas_dados(livro[ABA_CONFERIDAS])) == 119
    assert len(_linhas_dados(livro[ABA_DIVERGENCIA])) == 0
    assert len(_linhas_dados(livro[ABA_SOMENTE_TASY])) == 36
    assert len(_linhas_dados(livro[ABA_SOMENTE_PREFEITURA])) == 3
    assert len(_linhas_dados(livro[ABA_ESCRITURADAS])) == 8

    textos = [str(l[0]) for l in livro[ABA_RESUMO].iter_rows(values_only=True) if l[0]]
    assert "Todas as notas do Tasy aparecem no relatório (159 de 159)" in textos
    assert "Todas as linhas da prefeitura aparecem no relatório (130 de 130)" in textos

    avisos = list(livro[ABA_AVISOS].iter_rows(min_row=2, values_only=True))
    assert [l[2] for l in avisos if l[1]] == ["OK", "OK", "OK"]


# ---------------------------------------------------------------------
# 8.2 — com o CSV de pessoa física
# ---------------------------------------------------------------------
def test_gabarito_8_2_com_pessoa_fisica(pasta):
    resultado = processar(
        [pasta / SERVICO, pasta / HONORARIO, pasta / PF], pasta / PREFEITURA, agora=AGORA
    )
    assert resultado.erro is None
    assert len(resultado.notas_tasy) == 170

    contagem = _por_nota(resultado)
    assert contagem[SITUACAO_CONFERIDA][0] == 118
    assert contagem[SITUACAO_CONFERIDA_AJUSTADO][0] == 1
    assert contagem[ESCRITURADA_2][0] == 4
    assert SITUACAO_DIVERGENCIA not in contagem
    assert contagem[SITUACAO_SOMENTE_TASY][0] == 47
    assert sum(1 for i in resultado.itens if i.situacao == SITUACAO_SOMENTE_PREFEITURA) == 3

    assert any("unidades diferentes misturados" in a.mensagem for a in resultado.avisos)
    assert "Varias_unidades" in resultado.caminho_relatorio.name
    pf = [a for a in resultado.avisos if a.arquivo == PF and a.tipo_arquivo]
    assert pf[0].linhas_lidas == 11 and pf[0].unidades == "Hospital Exemplo"

    livro = load_workbook(resultado.caminho_relatorio)
    textos = {
        str(c) for aba in livro.worksheets
        for linha in aba.iter_rows(values_only=True) for c in linha if c is not None
    }
    assert not any("observa" in t.casefold() for t in textos)


# ---------------------------------------------------------------------
# Nome do arquivo e erros isolados
# ---------------------------------------------------------------------
def test_mesmo_minuto_nao_sobrescreve(pasta):
    primeiro = processar([pasta / SERVICO], pasta / PREFEITURA, agora=AGORA).caminho_relatorio
    segundo = processar([pasta / SERVICO], pasta / PREFEITURA, agora=AGORA).caminho_relatorio
    terceiro = processar([pasta / SERVICO], pasta / PREFEITURA, agora=AGORA).caminho_relatorio
    assert segundo.name == primeiro.stem + "_2.xlsx"
    assert terceiro.name == primeiro.stem + "_3.xlsx"


def test_csv_com_erro_vira_aviso_e_os_outros_processam(pasta):
    ruim = pasta / "ruim.csv"
    ruim.write_bytes('"Nota Fiscal";"Emitente"\r\n"1";"X"\r\n'.encode("utf-16-le"))
    resultado = processar([pasta / SERVICO, ruim, pasta / HONORARIO], pasta / PREFEITURA, agora=AGORA)
    assert resultado.erro is None
    assert len(resultado.notas_tasy) == 159
    erro = [a for a in resultado.avisos if a.arquivo == "ruim.csv"]
    assert erro[0].nivel == NIVEL_ERRO and "Código emitente" in erro[0].mensagem
    assert resultado.caminho_relatorio.exists()


def test_arquivo_selecionado_duas_vezes_nao_duplica_notas(pasta):
    resultado = processar([pasta / SERVICO, pasta / SERVICO], pasta / PREFEITURA, agora=AGORA)
    assert len(resultado.notas_tasy) == 75
    assert any("mais de uma vez" in a.mensagem for a in resultado.avisos)


def test_prefeitura_ilegivel_nao_gera_relatorio(pasta):
    falsa = pasta / "falsa.xls"
    falsa.write_text("<html>Nenhum registro</html>", encoding="utf-8")
    resultado = processar([pasta / SERVICO], falsa, agora=AGORA)
    assert resultado.erro and "prefeitura" in resultado.erro
    assert resultado.caminho_relatorio is None
    assert any(a.arquivo == "falsa.xls" and a.nivel == NIVEL_ERRO for a in resultado.avisos)
    assert list(pasta.glob("*.xlsx")) == []


def test_nenhum_csv_lido_nao_gera_relatorio(pasta):
    resultado = processar([pasta / "nao_existe.csv"], pasta / PREFEITURA, agora=AGORA)
    assert resultado.erro and "Tasy" in resultado.erro
    assert resultado.caminho_relatorio is None


def test_sem_permissao_para_salvar_da_mensagem_clara(pasta, monkeypatch):
    def falhar(*args, **kwargs):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(MODULO_PROCESSAR, "gerar_relatorio", falhar)
    resultado = processar([pasta / SERVICO], pasta / PREFEITURA, agora=AGORA)
    assert "permissão" in resultado.erro
    assert resultado.caminho_relatorio is None
    assert len(resultado.itens) > 0           # a conferência foi feita; só não salvou


def test_erro_inesperado_nao_vira_excecao(pasta, monkeypatch):
    def quebrar(*args, **kwargs):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(MODULO_PROCESSAR, "comparar", quebrar)
    resultado = processar([pasta / SERVICO], pasta / PREFEITURA, agora=AGORA)
    assert "falha simulada" in resultado.erro


# ---------------------------------------------------------------------
# Funções de nome (não precisam dos exemplos)
# ---------------------------------------------------------------------
@pytest.mark.parametrize("entrada, esperado", [
    ("AME Cidade Beta", "AME_Cidade_Beta"),
    ("Hospital Exemplo", "Hospital_Exemplo"),
    ("AME - Cidade Beta (Fundação)", "AME_-_Cidade_Beta_Fundacao"),
    ("Unidade: São José/SP", "Unidade_Sao_Jose_SP"),
])
def test_nome_para_arquivo(entrada, esperado):
    assert nome_para_arquivo(entrada) == esperado


def test_nome_do_relatorio():
    assert nome_do_relatorio("2026-09", ["AME Cidade Beta"], AGORA) == (
        "Conferencia_ISS_RB_2026-09_AME_Cidade_Beta_14h05.xlsx"
    )
    assert nome_do_relatorio("2026-09", ["A", "B"], AGORA) == (
        "Conferencia_ISS_RB_2026-09_Varias_unidades_14h05.xlsx"
    )
    assert nome_do_relatorio("", [], AGORA) == (
        "Conferencia_ISS_RB_sem_competencia_Sem_unidade_14h05.xlsx"
    )
