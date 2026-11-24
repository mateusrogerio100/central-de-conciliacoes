"""PlanilhaHM 5: processamento em duas passadas e relatório de conferência (seção 5)."""

from __future__ import annotations

from datetime import datetime

import openpyxl
import pytest

from modulos.planilha_hm import configuracao as cfg
from modulos.planilha_hm.processamento import analisar, processar
from testes.planilha_hm.conftest import escrever_caso_ficticio, exemplos, planilha_real

pytestmark = pytest.mark.filterwarnings("ignore:Print area cannot be set")

AGORA = datetime(2026, 10, 30, 14, 5, 9)
NOME_COPIA = "09 Planilha HM 2026 Atualizada em 30-10-2026 COMPETENCIA 09.xlsx"
NOME_RELATORIO = "Conferencia_PlanilhaHM_2026-09_2026-10-30_140509.xlsx"


def _valores_resumo(caminho) -> dict:
    aba = openpyxl.load_workbook(caminho)[cfg.ABA_RESUMO]
    return {l[0]: l[1] for l in aba.iter_rows(values_only=True) if l and l[0]}


def _analisar_ficticio(tmp_path, **opcoes):
    planilha, eventos, movimento = escrever_caso_ficticio(tmp_path, **opcoes)
    return analisar(eventos, movimento, planilha, tmp_path / "config")


def test_duas_passadas_gravam_copia_relatorio_e_tabela(tmp_path):
    analise = _analisar_ficticio(tmp_path)
    assert analise.erro == "" and [p.chave for p in analise.plano.perguntas] == ["3.9.02.0001"]
    assert not (tmp_path / "config").exists()                       # a 1ª passada não grava nada
    saida = tmp_path / "saida"
    saida.mkdir()
    resultado = processar(analise, saida, {"3.9.02.0001": cfg.RESPOSTA_SECAO_NOVA}, agora=AGORA)
    assert resultado.erro == resultado.erro_saida == ""
    assert resultado.caminho_planilha == saida / NOME_COPIA
    assert resultado.caminho_relatorio == saida / NOME_RELATORIO
    assert (tmp_path / "config" / cfg.ARQUIVO_SECOES).is_file()
    assert resultado.conferencia.ok

    livro = openpyxl.load_workbook(resultado.caminho_relatorio)
    assert livro.sheetnames == [cfg.ABA_RESUMO, cfg.ABA_EVENTOS, cfg.ABA_LINHAS_CRIADAS, cfg.ABA_AVISOS]
    resumo = _valores_resumo(resultado.caminho_relatorio)
    assert resumo["TOTAL GERAL do mês na cópia"] == resumo["Movimento (lote 70001)"] == 505
    assert resumo["Diferença (TOTAL GERAL − Movimento)"] == 0
    assert resumo["LOTE REPASSE gravado"] == 505
    assert resumo["Linhas criadas na aba do ano"] == 7
    eventos = list(livro[cfg.ABA_EVENTOS].iter_rows(min_row=2, values_only=True))
    assert [(l[0], l[7], l[10]) for l in eventos] == [
        (1001, "HONORÁRIOS MÉDICOS - FIXOS", cfg.SITUACAO_CC_NOVO),
        (1002, "HONORÁRIOS MÉDICOS - FIXOS", cfg.SITUACAO_OK),
        (2001, "HM DESCONTOS", cfg.SITUACAO_OK),
        (1003, "HONORÁRIOS MÉDICOS - FIXOS", cfg.SITUACAO_NOVO),
        (1004, "CONTA EXEMPLO NOVA PJ", cfg.SITUACAO_NOVO)]
    criadas = list(livro[cfg.ABA_LINHAS_CRIADAS].iter_rows(min_row=2, values_only=True))
    assert [l[1] for l in criadas] == ["CC novo", "evento novo", "CC novo", "seção nova", "evento novo", "CC novo",
                                       "total da seção nova"]
    assert [l[0] for l in criadas] == sorted(l[0] for l in criadas)


def test_relatorio_anterior_nunca_e_apagado(tmp_path):
    analise = _analisar_ficticio(tmp_path)
    respostas = {"3.9.02.0001": cfg.RESPOSTA_SECAO_NOVA}
    primeiro = processar(analise, tmp_path, respostas, agora=AGORA)
    segundo = processar(_analisar_ficticio(tmp_path), tmp_path, respostas, substituir_copia=True, agora=AGORA)
    assert primeiro.caminho_relatorio.is_file()
    assert segundo.caminho_relatorio.name == NOME_RELATORIO.replace(".xlsx", "_2.xlsx")


def test_copia_existente_pergunta_antes_de_substituir(tmp_path):
    (tmp_path / NOME_COPIA).write_bytes(b"antiga")
    resultado = processar(_analisar_ficticio(tmp_path), tmp_path, {"3.9.02.0001": "HM DESCONTOS"}, agora=AGORA)
    assert resultado.copia_existente == tmp_path / NOME_COPIA and resultado.caminho_planilha is None
    assert (tmp_path / NOME_COPIA).read_bytes() == b"antiga" and not (tmp_path / "config").exists()


def test_aba_senior_preenchida_pergunta_antes_de_substituir(tmp_path):
    analise = _analisar_ficticio(tmp_path, senior_com_dados={9: 4})
    assert analise.linhas_senior_preenchidas == 4
    resultado = processar(analise, tmp_path, {"3.9.02.0001": "HM DESCONTOS"}, agora=AGORA)
    assert resultado.senior_preenchida == 4 and not (tmp_path / NOME_COPIA).exists()
    resultado = processar(analise, tmp_path, {"3.9.02.0001": "HM DESCONTOS"}, substituir_senior=True, agora=AGORA)
    assert resultado.conferencia.ok and resultado.caminho_planilha.is_file()


def test_diferenca_traz_a_aba_do_movimento_sem_evento(tmp_path):
    analise = _analisar_ficticio(tmp_path, total_1002=210)
    resultado = processar(analise, tmp_path, {"3.9.02.0001": cfg.RESPOSTA_SECAO_NOVA}, agora=AGORA)
    livro = openpyxl.load_workbook(resultado.caminho_relatorio)
    assert cfg.ABA_SEM_EVENTO in livro.sheetnames
    assert [l[4] for l in livro[cfg.ABA_SEM_EVENTO].iter_rows(min_row=2, values_only=True)] == [175, 30]
    resumo = _valores_resumo(resultado.caminho_relatorio)
    assert resumo["Diferença (TOTAL GERAL − Movimento)"] == -200
    assert resumo["Eventos com erro (fora da planilha)"] == 1
    situacao = {l[0]: l[10] for l in livro[cfg.ABA_EVENTOS].iter_rows(min_row=2, values_only=True)}
    assert situacao[1002].startswith("erro:")
    avisos = list(livro[cfg.ABA_AVISOS].iter_rows(min_row=2, values_only=True))
    assert any("1002" in l[1] and l[2] == "erro" for l in avisos)


def test_erro_de_leitura_nao_derruba(tmp_path):
    analise = _analisar_ficticio(tmp_path, data="31/08/2026")
    assert "mesmo mês" in analise.erro and analise.plano is None
    with pytest.raises(ValueError):
        processar(analise, tmp_path)
    planilha, eventos, _ = escrever_caso_ficticio(tmp_path)
    analise = analisar(eventos, tmp_path / "nao_existe.csv", planilha, tmp_path / "config")
    assert "não encontrado" in analise.erro


def test_relatorio_bloqueado_vira_erro_de_saida(tmp_path, monkeypatch):
    import modulos.planilha_hm.processamento as processamento

    def bloqueado(*args, **kwargs):
        raise PermissionError("aberto no Excel")

    monkeypatch.setattr(processamento, "gerar_relatorio", bloqueado)
    resultado = processar(_analisar_ficticio(tmp_path), tmp_path, {"3.9.02.0001": "HM DESCONTOS"}, agora=AGORA)
    assert resultado.caminho_planilha.is_file() and "aberto no Excel" in resultado.erro_saida


def test_setembro_real_relatorio(tmp_path):
    pasta = exemplos("2026-09")
    analise = analisar(pasta / "Eventos 09-2026.XLS", next(pasta.glob("Movimento*.csv")), planilha_real("2026-08"),
                       tmp_path / "config")
    respostas = {p.chave: cfg.RESPOSTA_SECAO_NOVA for p in analise.plano.perguntas}
    resultado = processar(analise, tmp_path, respostas, agora=AGORA)
    assert resultado.erro == resultado.erro_saida == "" and resultado.conferencia.ok
    resumo = _valores_resumo(resultado.caminho_relatorio)
    assert resumo["Total Eventos (136 eventos)"] == resumo["TOTAL GERAL do mês na cópia"] == 5794120.73
    assert resumo["Movimento (lote 72959)"] == 5794120.73
    assert resumo["Linhas criadas na aba do ano"] == 12
    assert resumo["Linhas na aba Senior 09 2026"] == 264
    livro = openpyxl.load_workbook(resultado.caminho_relatorio)
    assert livro[cfg.ABA_EVENTOS].max_row == 137
    assert cfg.ABA_SEM_EVENTO not in livro.sheetnames
