"""Testes de ponta a ponta: processamento.processar com os exemplos reais e casos de falha (R13, R14)."""

import hashlib
import shutil
from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest

from modulos.subvencoes.modelos import Gravidade, MesReferencia, StatusArquivo
from modulos.subvencoes.processamento import (
    arquivos_de_saida,
    caminho_relatorio,
    mes_do_balancete,
    mes_do_patrimonio,
    processar,
)
from testes.subvencoes.conftest import MESES_EXEMPLO, arquivos_do_mes, ler_gabarito

NOMES_GABARITO = {"Subvenções_Investimento": "subvencoes", "Projetos": "projetos"}


def _mes(mes_exemplo: str) -> MesReferencia:
    ano, mes = map(int, mes_exemplo.split("-"))
    return MesReferencia(ano, mes)


def _hash(caminho):
    return hashlib.sha256(Path(caminho).read_bytes()).hexdigest()


def _processar_exemplo(mes_exemplo, pasta_saida, mes=None):
    arquivos = arquivos_do_mes(mes_exemplo)
    return processar(arquivos.balancete, arquivos.patrimonio, [arquivos.subvencoes, arquivos.projetos],
                     pasta_saida, mes or _mes(mes_exemplo))


@pytest.fixture(scope="module", params=MESES_EXEMPLO)
def processado(request, tmp_path_factory):
    """Processa o mês uma vez só (é o passo mais demorado) e reaproveita nos testes."""
    mes_exemplo = request.param
    arquivos = arquivos_do_mes(mes_exemplo)
    entradas = [arquivos.balancete, arquivos.patrimonio, arquivos.subvencoes, arquivos.projetos]
    hashes = {p: _hash(p) for p in entradas}
    pasta = tmp_path_factory.mktemp(f"saida_{mes_exemplo}")
    resultado = _processar_exemplo(mes_exemplo, pasta)
    return mes_exemplo, arquivos, pasta, resultado, hashes


# ---------------------------------------------------------------------------
# Exemplos reais
# ---------------------------------------------------------------------------


def test_todos_os_arquivos_processados(processado):
    mes_exemplo, arquivos, pasta, resultado, _ = processado
    assert [(a.tipo, a.status) for a in resultado.arquivos] == [
        ("Balancete", StatusArquivo.LIDO), ("Patrimônio", StatusArquivo.LIDO),
        ("Planilha", StatusArquivo.GERADO), ("Planilha", StatusArquivo.GERADO),
    ]
    assert resultado.arquivos[0].mes_lido == resultado.arquivos[1].mes_lido == _mes(mes_exemplo)
    assert [a.linhas_preenchidas for a in resultado.planilhas] == [108, 15]
    assert resultado.erro_relatorio == ""
    gerados = sorted(p.name for p in pasta.iterdir())
    assert gerados == sorted([arquivos.subvencoes.name, arquivos.projetos.name,
                              f"Avisos_{_mes(mes_exemplo).para_nome_arquivo}.xlsx"])


def test_sem_erros_nos_exemplos(processado):
    _, _, _, resultado, _ = processado
    assert resultado.quantidade_por_gravidade()[Gravidade.ERRO] == 0


def test_entradas_nao_alteradas(processado):
    _, _, _, _, hashes = processado
    for caminho, valor in hashes.items():
        assert _hash(caminho) == valor, caminho


def test_planilhas_geradas_iguais_ao_gabarito(processado):
    _, arquivos, _, resultado, _ = processado
    pastas = {Path(p.caminho).name: openpyxl.load_workbook(p.destino) for p in resultado.planilhas}
    nomes = {"subvencoes": arquivos.subvencoes.name, "projetos": arquivos.projetos.name}
    for linha in ler_gabarito(arquivos.gabarito):
        aba = pastas[nomes[NOMES_GABARITO[linha["planilha"]]]][linha["aba"]]
        for coluna, campo in ((4, "saldo_patrimonio"), (5, "saldo_contabil")):
            valor = Decimal(repr(aba.cell(linha["linha"], coluna).value)).quantize(Decimal("0.01"))
            assert valor == linha[campo], f"{linha['aba']} linha {linha['linha']} {campo}"


def test_avisos_esperados(processado):
    mes_exemplo, _, _, resultado, _ = processado
    tipos = {a.tipo for a in resultado.avisos}
    assert "vínculo externo" in tipos and "fórmula de total corrigida" in tipos
    especial = "cabeçalho ausente" if mes_exemplo == "2026-07" else "total do sistema divergente"
    assert especial in tipos
    assert "meses diferentes" not in tipos
    assert "conta nova no balancete" not in tipos


# ---------------------------------------------------------------------------
# Mês de referência (R10) e arquivos de saída (R11)
# ---------------------------------------------------------------------------


def test_meses_para_a_interface(arquivos, mes_exemplo):
    assert mes_do_balancete(arquivos.balancete) == _mes(mes_exemplo)
    assert mes_do_patrimonio(arquivos.patrimonio) == _mes(mes_exemplo)
    assert mes_do_balancete(arquivos.patrimonio) is None          # arquivo errado -> None, sem exceção


def test_arquivos_de_saida(tmp_path):
    saidas = arquivos_de_saida([Path("x/Projetos_08-2026.xlsx"), Path("x/Subvenções.xlsx")], tmp_path,
                               MesReferencia(2026, 9))
    assert [p.name for p in saidas] == ["Projetos_09-2026.xlsx", "Subvenções_09-2026.xlsx", "Avisos_09-2026.xlsx"]
    assert caminho_relatorio(tmp_path, MesReferencia(2026, 9)) == tmp_path / "Avisos_09-2026.xlsx"


def test_mes_informado_diferente(tmp_path):
    """O mês digitado na tela vale para os nomes; a diferença para o balancete vira aviso."""
    resultado = _processar_exemplo("2026-08", tmp_path, MesReferencia(2026, 9))
    assert {Path(p.destino).name for p in resultado.planilhas_geradas} == {
        "Subvenções Investimento 09-2026.xlsx", "Projetos 09-2026.xlsx"}
    assert (tmp_path / "Avisos_09-2026.xlsx").exists()
    avisos = [a for a in resultado.avisos if a.tipo == "meses diferentes"]
    assert len(avisos) == 1 and avisos[0].gravidade == Gravidade.ATENCAO


def test_patrimonio_de_outro_mes(tmp_path):
    julho, agosto = arquivos_do_mes("2026-07"), arquivos_do_mes("2026-08")
    resultado = processar(agosto.balancete, julho.patrimonio, [agosto.projetos], tmp_path, MesReferencia(2026, 8))
    avisos = [a for a in resultado.avisos if a.tipo == "meses diferentes"]
    assert len(avisos) == 1 and "07/2026" in avisos[0].mensagem and "08/2026" in avisos[0].mensagem
    assert resultado.planilhas[0].status == StatusArquivo.GERADO     # não bloqueia


def test_mes_obrigatorio(tmp_path):
    arquivos = arquivos_do_mes("2026-08")
    with pytest.raises(ValueError):
        processar(arquivos.balancete, arquivos.patrimonio, [], tmp_path, None)


# ---------------------------------------------------------------------------
# Um arquivo com problema não derruba os outros (R14)
# ---------------------------------------------------------------------------


def _erros(resultado, tipo):
    return [a for a in resultado.avisos if a.gravidade == Gravidade.ERRO and a.tipo == tipo]


def test_planilha_corrompida_nao_derruba_a_outra(tmp_path):
    arquivos = arquivos_do_mes("2026-08")
    corrompida = tmp_path / "entrada" / "Corrompida_08-2026.xlsx"
    corrompida.parent.mkdir()
    corrompida.write_bytes(b"isto nao e um xlsx")
    saida = tmp_path / "saida"
    resultado = processar(arquivos.balancete, arquivos.patrimonio, [corrompida, arquivos.projetos],
                          saida, MesReferencia(2026, 8))
    ruim, boa = resultado.planilhas
    assert ruim.status == StatusArquivo.FALHOU and "Corrompida" in ruim.detalhe
    assert boa.status == StatusArquivo.GERADO and Path(boa.destino).exists()
    assert len(_erros(resultado, "planilha não gerada")) == 1
    assert resultado.caminho_relatorio and Path(resultado.caminho_relatorio).exists()


def test_saida_aberta_no_excel(tmp_path):
    """Planilha de saída "aberta" (bloqueada): mensagem clara, as demais são geradas."""
    arquivos = arquivos_do_mes("2026-08")
    bloqueado = tmp_path / arquivos.projetos.name
    shutil.copy(arquivos.projetos, bloqueado)
    with open(bloqueado, "rb"):
        resultado = _processar_exemplo("2026-08", tmp_path)
    subvencoes, projetos = resultado.planilhas
    assert subvencoes.status == StatusArquivo.GERADO
    assert projetos.status == StatusArquivo.FALHOU and "Feche o arquivo" in projetos.detalhe
    assert len(_erros(resultado, "planilha não gerada")) == 1


def test_relatorio_aberto_no_excel(tmp_path):
    arquivos = arquivos_do_mes("2026-08")
    relatorio = caminho_relatorio(tmp_path, MesReferencia(2026, 8))
    openpyxl.Workbook().save(relatorio)
    with open(relatorio, "rb"):
        resultado = processar(arquivos.balancete, arquivos.patrimonio, [arquivos.projetos], tmp_path,
                              MesReferencia(2026, 8))
    assert "Feche o arquivo" in resultado.erro_relatorio
    assert resultado.caminho_relatorio == ""
    assert resultado.planilhas[0].status == StatusArquivo.GERADO


def test_balancete_ilegivel_nao_gera_planilhas(tmp_path):
    """Sem balancete não há Saldo Contábil nem descrição para achar o patrimônio: nenhuma planilha é
    gerada (seriam só zeros), mas o relatório sai explicando."""
    arquivos = arquivos_do_mes("2026-08")
    resultado = processar(tmp_path / "nao_existe.xlsx", arquivos.patrimonio, [arquivos.projetos],
                          tmp_path / "saida", MesReferencia(2026, 8))
    assert resultado.arquivos[0].status == StatusArquivo.FALHOU
    assert resultado.arquivos[1].status == StatusArquivo.LIDO
    assert resultado.planilhas[0].status == StatusArquivo.NAO_PROCESSADO
    assert _erros(resultado, "arquivo não lido") and _erros(resultado, "planilha não gerada")
    assert not (tmp_path / "saida" / arquivos.projetos.name).exists()
    assert Path(resultado.caminho_relatorio).exists()


def test_patrimonio_ilegivel_nao_gera_planilhas(tmp_path):
    arquivos = arquivos_do_mes("2026-08")
    resultado = processar(arquivos.balancete, arquivos.projetos, [arquivos.projetos],   # arquivo errado
                          tmp_path / "saida", MesReferencia(2026, 8))
    assert resultado.arquivos[1].status == StatusArquivo.FALHOU
    assert "Valor Contábil" in resultado.arquivos[1].detalhe
    assert resultado.planilhas[0].status == StatusArquivo.NAO_PROCESSADO


def test_dois_arquivos_com_mesmo_nome_de_saida(tmp_path):
    arquivos = arquivos_do_mes("2026-08")
    copia = tmp_path / "outra_pasta" / arquivos.projetos.name
    copia.parent.mkdir()
    shutil.copy(arquivos.projetos, copia)
    resultado = processar(arquivos.balancete, arquivos.patrimonio, [arquivos.projetos, copia],
                          tmp_path / "saida", MesReferencia(2026, 8))
    primeira, segunda = resultado.planilhas
    assert primeira.status == StatusArquivo.GERADO
    assert segunda.status == StatusArquivo.FALHOU and "mesmo" in segunda.detalhe


def test_saida_na_mesma_pasta_e_mes_nao_sobrescreve_a_entrada(tmp_path):
    arquivos = arquivos_do_mes("2026-08")
    entrada = tmp_path / arquivos.projetos.name
    shutil.copy(arquivos.projetos, entrada)
    antes = _hash(entrada)
    resultado = processar(arquivos.balancete, arquivos.patrimonio, [entrada], tmp_path, MesReferencia(2026, 8))
    assert resultado.planilhas[0].status == StatusArquivo.FALHOU
    assert "próprio arquivo de entrada" in resultado.planilhas[0].detalhe
    assert _hash(entrada) == antes


def test_aba_sem_contas_vira_info(tmp_path):
    arquivos = arquivos_do_mes("2026-08")
    pasta = openpyxl.load_workbook(arquivos.projetos)
    pasta.create_sheet("Anotações")["A1"] = "rascunho"
    entrada = tmp_path / "Projetos_08-2026.xlsx"
    pasta.save(entrada)
    resultado = processar(arquivos.balancete, arquivos.patrimonio, [entrada], tmp_path / "saida",
                          MesReferencia(2026, 8))
    assert resultado.planilhas[0].abas_sem_contas == ["Anotações"]
    info = [a for a in resultado.avisos if a.tipo == "aba sem contas"]
    assert len(info) == 1 and info[0].gravidade == Gravidade.INFO and info[0].aba == "Anotações"
