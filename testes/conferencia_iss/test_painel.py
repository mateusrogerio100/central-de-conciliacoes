"""Tela do módulo Conferência ISS (montada sem mostrar a janela).

Refeitos a partir dos testes da tela antiga (test_interface_apoio.py do Conciliações AMES:
test_previa_tasy, test_previa_tasy_misturadas_e_com_erro, test_previa_prefeitura,
test_numeros_principais_8_1, test_config_lembra_a_cidade, test_config_cidade_desconhecida_vira_cidade_beta,
test_config_lembra_cidade_gama, test_config_lembra_cidade_alfa, test_menu_cidades_dentro_do_grupo_ames e
test_so_a_tela_visivel_e_montada_na_abertura_e_as_outras_guardam_o_estado), com as mesmas verificações:
lá cada cidade era um item do menu; aqui é uma aba. Mais as regras da Central e a tela com os
arquivos reais. Todos usam um %APPDATA% temporário e nunca abrem o Excel.
"""

from __future__ import annotations

import ast
import json
import shutil
import time

import pytest

from central import registro
from central.painel_abas import ABA_INSTRUCOES
from modulos.conferencia_iss import MODULO, processamento
from modulos.conferencia_iss.processamento import (
    MUNICIPIO_AV,
    MUNICIPIO_CP,
    MUNICIPIO_FR,
    MUNICIPIO_RB,
    MUNICIPIO_SJ,
    numeros_principais,
    previa_prefeitura,
    previa_tasy,
)
from modulos.conferencia_iss.processar import processar
from testes.conferencia_iss.pastas_exemplos import PASTA_CP, PASTA_EXEMPLOS, PASTA_FR, PASTA_RB
from testes.conftest import RAIZ, esperar

CIDADES = ["Cidade Beta", "Cidade Epsilon", "Cidade Zeta", "Cidade Gama", "Cidade Alfa"]
PREFEITURA_RB = "Relatorio_de_Servicos_Contratados.xls"
CSVS_RB = ("Servico_PJ_RB.csv", "Honorario_PJ_RB.csv")


@pytest.fixture(autouse=True)
def appdata_temporario(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))


@pytest.fixture
def pasta(tmp_path):
    """Os arquivos de Cidade Beta (e o CSV de pessoa física) copiados para uma pasta temporária."""
    if not PASTA_EXEMPLOS.exists():
        pytest.skip("pasta exemplos/ não existe (dados reais ficam fora do git)")
    copia = tmp_path / "rb"
    copia.mkdir()
    for arquivo in PASTA_RB.glob("*.*"):
        if arquivo.suffix in (".csv", ".xls"):
            shutil.copy(arquivo, copia / arquivo.name)
    shutil.copy(PASTA_EXEMPLOS / "pf" / "Notas_fiscais_PF_exemplo.csv", copia)
    return copia


def _textos(widget):
    """Todos os textos de rótulos dentro de um widget (para conferir o que a tela mostra)."""
    textos = []
    for filho in widget.winfo_children():
        try:
            texto = filho.cget("text")
        except Exception:
            texto = None
        if isinstance(texto, str):
            textos.append(texto)
        textos.extend(_textos(filho))
    return textos


def _sem_abrir(aba, monkeypatch):
    aba.abertos = []
    monkeypatch.setattr(aba, "abrir", aba.abertos.append)       # nunca abre o Excel de verdade
    return aba


# ---------------------------------------------------------------------------
# Módulo e arquitetura (era test_menu_cidades_dentro_do_grupo_ames)
# ---------------------------------------------------------------------------


def test_modulo_no_registro_na_secao_fiscal():
    assert registro.SECAO_DO_MODULO["conferencia_iss"] == "FISCAL"
    carregado = next(m for m in registro.carregar_modulos() if m.chave == "conferencia_iss")
    assert carregado.ok and carregado.info.nome == "Conferência ISS"
    assert (RAIZ / "central" / "icones" / f"{carregado.info.icone}.png").exists()
    assert (RAIZ / "modulos" / "conferencia_iss" / "INSTRUCOES_DE_USO.md").exists()


def test_uma_aba_por_cidade_e_as_instrucoes(criar_painel):
    painel = criar_painel(MODULO)
    assert list(painel.abas.botoes) == CIDADES + [ABA_INSTRUCOES]
    assert [c.nome for c in processamento.MUNICIPIOS.values()] == CIDADES


def test_tela_so_usa_o_processamento():
    pasta = RAIZ / "modulos" / "conferencia_iss"
    for arquivo in [pasta / "painel.py", *(pasta / "telas").glob("*.py")]:
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        do_modulo = {no.module for no in ast.walk(arvore) if isinstance(no, ast.ImportFrom)
                     and no.module and no.module.startswith("modulos.")}
        assert do_modulo <= {"modulos.conferencia_iss", "modulos.conferencia_iss.processamento",
                             "modulos.conferencia_iss.telas.cidade"}, arquivo.name


def test_modulo_nao_importa_outro_modulo():
    for arquivo in (RAIZ / "modulos" / "conferencia_iss").rglob("*.py"):
        for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
            if isinstance(no, ast.ImportFrom) and no.module and no.module.startswith("modulos."):
                assert no.module.startswith("modulos.conferencia_iss"), (arquivo.name, no.module)


# ---------------------------------------------------------------------------
# Última cidade (eram test_config_lembra_a_cidade, _cidade_desconhecida_vira_cidade_beta,
# _lembra_cidade_gama e _lembra_cidade_alfa)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cidade", [MUNICIPIO_SJ, MUNICIPIO_AV, MUNICIPIO_CP, MUNICIPIO_FR])
def test_cidade_lembrada_salva_e_le(tmp_path, cidade):
    assert processamento.ler_cidade_lembrada(tmp_path) == MUNICIPIO_RB
    assert processamento.salvar_cidade_lembrada(cidade, tmp_path)
    assert processamento.ler_cidade_lembrada(tmp_path) == cidade


def test_cidade_desconhecida_vira_cidade_beta(tmp_path):
    (tmp_path / "conferencia_iss.json").write_text('{"cidade": "XX"}', encoding="utf-8")
    assert processamento.ler_cidade_lembrada(tmp_path) == MUNICIPIO_RB


def test_cidade_vem_do_conciliacoes_ames_so_enquanto_a_central_nao_guardou(tmp_path):
    antigo = tmp_path / "config.json"
    antigo.write_text(json.dumps({"modo": "escuro", "cidade": MUNICIPIO_CP}), encoding="utf-8")
    assert processamento.ler_cidade_lembrada(tmp_path / "central", antigo) == MUNICIPIO_CP
    processamento.salvar_cidade_lembrada(MUNICIPIO_FR, tmp_path / "central")
    assert processamento.ler_cidade_lembrada(tmp_path / "central", antigo) == MUNICIPIO_FR


def test_ultimo_item_do_programa_antigo_que_nao_e_cidade_vira_cidade_beta(tmp_path):
    antigo = tmp_path / "config.json"
    antigo.write_text(json.dumps({"cidade": "FORNECEDORES"}), encoding="utf-8")
    assert processamento.ler_cidade_lembrada(tmp_path / "central", antigo) == MUNICIPIO_RB


def test_abre_na_ultima_cidade_e_lembra_a_troca(criar_painel):
    painel = criar_painel(MODULO)
    assert painel.aba_atual == "Cidade Beta"
    painel.abas.selecionar("Cidade Gama", avisar=True)             # como se o usuário clicasse
    assert processamento.ler_cidade_lembrada() == MUNICIPIO_CP
    painel.abas.selecionar(ABA_INSTRUCOES, avisar=True)         # as instruções não são uma cidade
    assert processamento.ler_cidade_lembrada() == MUNICIPIO_CP

    outro = criar_painel(MODULO)                                # abre de novo: na cidade lembrada
    assert outro.aba_atual == "Cidade Gama"
    assert list(outro.paineis) == ["Cidade Gama"]                  # só ela foi montada
    assert processamento.ler_cidade_lembrada() == MUNICIPIO_CP  # abrir não regrava nada


# ---------------------------------------------------------------------------
# Abas montadas sob demanda (era test_so_a_tela_visivel_e_montada_na_abertura_e_as_outras_guardam_o_estado)
# ---------------------------------------------------------------------------


def test_so_a_aba_visivel_e_montada_e_as_outras_guardam_o_estado(criar_painel, tmp_path):
    painel = criar_painel(MODULO)
    assert list(painel.paineis) == ["Cidade Beta"]
    painel.abas.selecionar("Cidade Alfa", avisar=True)
    cidade_alfa = painel.cidade_alfa
    assert set(painel.paineis) == {"Cidade Beta", "Cidade Alfa"}
    csv = tmp_path / "Notas.csv"
    csv.write_bytes(b"")
    cidade_alfa.cartao_tasy.definir_caminhos([csv])                  # escolhe algo nesta aba
    painel.abas.selecionar("Cidade Epsilon", avisar=True)
    painel.abas.selecionar("Cidade Alfa", avisar=True)
    assert painel.cidade_alfa is cidade_alfa                              # a mesma aba, não uma nova
    assert cidade_alfa.cartao_tasy.caminhos == [csv]
    assert painel.cabecalho.rotulo_descricao.cget("text") == (
        "Compara as notas do Tasy com o relatório de notas tomadas da Prefeitura de Cidade Alfa.")


def test_cada_aba_com_o_cartao_da_sua_cidade(criar_painel):
    painel = criar_painel(MODULO)
    rotulos = {nome: painel.painel_da_aba(nome).cartao_prefeitura.rotulo for nome in CIDADES}
    assert rotulos == {
        "Cidade Beta": "Relatório da prefeitura (.xls)", "Cidade Epsilon": "Relatório da prefeitura (.xls)",
        "Cidade Zeta": "Relatório da prefeitura (.pdf)", "Cidade Gama": "Relatório da prefeitura (.xlsx)",
        "Cidade Alfa": "Relatório da prefeitura (.csv)",
    }
    assert not any(painel.painel_da_aba(nome).botao.habilitado for nome in CIDADES)


# ---------------------------------------------------------------------------
# Prévias e números (eram test_previa_tasy, ..._misturadas_e_com_erro, test_previa_prefeitura e
# test_numeros_principais_8_1)
# ---------------------------------------------------------------------------


def test_previa_tasy(pasta):
    previa = previa_tasy([pasta / "Servico_PJ_RB.csv", pasta / "Honorario_PJ_RB.csv"])
    assert previa.notas == 159
    assert previa.unidades == ["AME Cidade Beta"]
    assert not previa.unidades_misturadas
    assert previa.erros == []


def test_previa_tasy_misturadas_e_com_erro(pasta):
    ruim = pasta / "ruim.csv"
    ruim.write_bytes(b"")
    previa = previa_tasy([pasta / "Servico_PJ_RB.csv", pasta / "Notas_fiscais_PF_exemplo.csv", ruim])
    assert previa.notas == 86
    assert previa.unidades_misturadas
    assert len(previa.erros) == 1 and previa.erros[0].startswith("ruim.csv")


def test_previa_prefeitura(pasta):
    previa = previa_prefeitura(pasta / PREFEITURA_RB)
    assert (previa.linhas, previa.competencia_texto, previa.inscricao_municipal, previa.erro) == (
        130, "setembro/2026", "20164715", None
    )
    assert previa_prefeitura(pasta / "Servico_PJ_RB.csv").erro


def test_numeros_principais_8_1(pasta):
    resultado = processar([pasta / n for n in CSVS_RB], pasta / PREFEITURA_RB)
    numeros = numeros_principais(resultado)
    assert numeros.conferidas == 119              # 118 + 1 número ajustado
    assert numeros.somente_tasy == 36
    assert numeros.para_analisar == 7             # 0 divergências + 4 escrituradas + 3 só prefeitura
    assert (numeros.divergencias, numeros.escrituradas, numeros.somente_prefeitura) == (0, 4, 3)


# ---------------------------------------------------------------------------
# Tela com os arquivos reais
# ---------------------------------------------------------------------------


def test_tela_cidade_beta_com_arquivos_reais(criar_painel, pasta, monkeypatch):
    aba = _sem_abrir(criar_painel(MODULO).cidade_beta, monkeypatch)
    aba.cartao_tasy.definir_caminhos([pasta / n for n in CSVS_RB])
    assert aba.cartao_tasy.texto_confirmacao == "159 notas · unidade AME Cidade Beta"
    assert not aba.botao.habilitado                             # falta a prefeitura
    aba.cartao_prefeitura.definir_caminhos([pasta / PREFEITURA_RB])
    assert not aba.botao.habilitado                             # lendo em segundo plano
    esperar(aba, lambda: not aba.lendo_prefeitura)
    assert aba.cartao_prefeitura.texto_confirmacao == "Competência setembro/2026 · Inscr. 20164715 · 130 linhas"
    assert aba.botao.habilitado

    aba.processar()
    esperar(aba, lambda: not aba.ocupado)
    resultado = aba.resultado_conferencia
    assert resultado.erro is None and resultado.caminho_relatorio.parent == pasta
    assert resultado.caminho_relatorio.name.startswith("Conferencia_ISS_RB_2026-09_AME_Cidade_Beta_")
    assert aba.resultado.selo.cget("text") == "Concluído"
    textos = _textos(aba.resultado)
    assert "159 de 159" in textos and "130 de 130" in textos
    assert "Escrituradas 2 vezes" in textos and "Conferidas (número ajustado)" in textos

    botoes = {b.cget("text"): b for b in aba.resultado.rodape.winfo_children()}
    assert list(botoes) == ["Abrir pasta", "Ver avisos", "Novo"]
    botoes["Ver avisos"].invoke()
    assert aba.janela_avisos.texto.startswith("ARQUIVOS LIDOS\n•")
    assert "AVISOS (1)" in aba.janela_avisos.texto                # o valor vazio da prefeitura
    aba.janela_avisos.destroy()
    botoes["Novo"].invoke()
    assert not aba.cartao_tasy.preenchido and not aba.cartao_prefeitura.preenchido
    assert aba.resultado_conferencia is None and not aba.botao_limpar_tudo.habilitado


def test_relatorio_da_cidade_errada_bloqueia_o_botao(criar_painel, pasta):
    aba = criar_painel(MODULO).painel_da_aba("Cidade Epsilon")
    aba.cartao_tasy.definir_caminhos([pasta / CSVS_RB[0]])
    aba.cartao_prefeitura.definir_caminhos([pasta / PREFEITURA_RB])
    esperar(aba, lambda: not aba.lendo_prefeitura)
    assert aba.cartao_prefeitura.status_confirmacao == "erro"
    assert "use a aba Cidade Beta da Conferência ISS" in aba.cartao_prefeitura.texto_confirmacao
    assert not aba.botao.habilitado
    aba.cartao_prefeitura.limpar_pelo_usuario()
    assert not aba.cartao_prefeitura.preenchido and not aba.botao.habilitado


def test_previa_antiga_e_ignorada_se_o_arquivo_foi_limpo(criar_painel, pasta):
    aba = criar_painel(MODULO).cidade_beta
    aba.cartao_prefeitura.definir_caminhos([pasta / PREFEITURA_RB])
    aba.cartao_prefeitura.limpar_pelo_usuario()                 # antes de a leitura terminar
    assert not aba.lendo_prefeitura
    for _ in range(150):                                        # tempo de sobra para a leitura acabar
        aba.update()
        time.sleep(0.02)
    assert aba.cartao_prefeitura.texto_confirmacao == "Nenhum arquivo selecionado"


def test_previa_de_cidade_gama_mostra_o_cnpj_da_unidade(criar_painel):
    if not PASTA_CP.exists():
        pytest.skip("exemplos de Cidade Gama não existem")
    aba = criar_painel(MODULO).cidade_gama
    aba.cartao_prefeitura.definir_caminhos([PASTA_CP / "Nota Fiscal_Cidade_Gama.xlsx"])
    esperar(aba, lambda: not aba.lendo_prefeitura)
    assert aba.cartao_prefeitura.texto_confirmacao == (
        "Competência setembro/2026 · CNPJ 98.765.432/0008-64 · 64 linhas")
    assert aba.cartao_prefeitura.status_confirmacao == "ok"


def test_previa_de_cidade_alfa_sem_identificacao_da_unidade(criar_painel):
    if not PASTA_FR.exists():
        pytest.skip("exemplos de Cidade Alfa não existem")
    aba = criar_painel(MODULO).cidade_alfa
    aba.cartao_prefeitura.definir_caminhos([PASTA_FR / "resultado_Prefeitura_Cidade_Alfa.csv"])
    esperar(aba, lambda: not aba.lendo_prefeitura)
    assert aba.cartao_prefeitura.texto_confirmacao == "Competência setembro/2026 · 155 linhas"
    assert aba.cartao_prefeitura.status_confirmacao == "ok"
