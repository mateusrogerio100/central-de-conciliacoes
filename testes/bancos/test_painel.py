"""Testes da tela da Conciliação Bancária (adaptados de tests/test_interface.py do programa original).

A regra do "Salvar em" (pasta_saida_sugerida) e o ícone passaram a ser da Central e são testados em
testes/central/test_painel_base.py.
"""

from __future__ import annotations

import shutil

import pytest

from modulos.bancos import MODULO
from modulos.bancos import identificador as identificador_bancos
from modulos.bancos import leitores as leitores_bancos
from modulos.bancos.telas import conciliacao as painel_bancos
from modulos.bancos.telas.conciliacao import FormularioModeloNovo
from testes.bancos.conftest import ARQUIVO_BALANCETE, PASTA_EXTRATOS, caminho_exemplo
from testes.conftest import esperar


def _exige_exemplos():
    if not ARQUIVO_BALANCETE.is_file() or not PASTA_EXTRATOS.is_dir():
        pytest.skip("exemplos não encontrados")


def _preencher(painel, balancete, extratos, saida):
    painel.cartao_balancete.definir_caminhos(balancete, avisar=False)
    painel.cartao_extratos.definir_caminhos(extratos, avisar=False)
    painel.cartao_saida.definir_caminhos(saida, avisar=False)
    painel.atualizar_botoes()


def _conciliar(painel):
    painel.processar()
    esperar(painel, lambda: not painel.ocupado)


# ---------------------------------------------------------------------------
# Escolhas
# ---------------------------------------------------------------------------


def test_escolher_balancete_preenche_salvar_em_e_competencia(criar_painel):
    _exige_exemplos()
    painel = criar_painel(MODULO).conciliacao
    painel.cartao_balancete.definir_caminhos(ARQUIVO_BALANCETE)          # como se o usuário escolhesse
    esperar(painel, lambda: painel._competencia_de is not None)
    assert painel.pasta_saida == ARQUIVO_BALANCETE.parent
    assert painel.cartao_balancete.texto_confirmacao == "Competência 08/2026"
    assert painel.cartao_balancete.status_confirmacao == "ok"


def test_pasta_trocada_pelo_usuario_nao_e_sobrescrita(criar_painel, tmp_path):
    _exige_exemplos()
    painel = criar_painel(MODULO).conciliacao
    painel.cartao_saida.definir_caminhos(tmp_path)                       # o usuário escolhe a pasta antes
    painel.cartao_balancete.definir_caminhos(ARQUIVO_BALANCETE)
    esperar(painel, lambda: painel._competencia_de is not None)
    assert painel.pasta_saida == tmp_path


def test_pasta_de_extratos_mostra_quantos_pdfs(criar_painel):
    _exige_exemplos()
    painel = criar_painel(MODULO).conciliacao
    painel.cartao_extratos.definir_caminhos(PASTA_EXTRATOS)
    assert painel.cartao_extratos.texto_confirmacao == "12 arquivo(s) PDF encontrado(s)"


# ---------------------------------------------------------------------------
# Conciliar
# ---------------------------------------------------------------------------


def test_conciliar_sem_campos_avisa(criar_painel, dialogos):
    painel = criar_painel(MODULO).conciliacao
    assert not painel.botao.habilitado
    painel.processar()                         # mesmo chamando direto, nada começa
    assert dialogos.avisos and not painel.ocupado


def test_conciliar_gera_planilha_e_mostra_o_resultado(criar_painel, dialogos, tmp_path):
    _exige_exemplos()
    painel = criar_painel(MODULO).conciliacao
    _preencher(painel, ARQUIVO_BALANCETE, PASTA_EXTRATOS, tmp_path)

    painel.processar()
    assert painel.ocupado and not painel.botao.habilitado                # não deixa clicar de novo
    esperar(painel, lambda: not painel.ocupado)

    destino = tmp_path / "conciliacao_bancaria_2026-08.xlsx"
    assert destino.is_file()
    assert painel.execucao.caminho == destino.resolve()
    assert painel.botao.habilitado and painel.resultado.estado == "concluido"
    assert set(painel.botoes_resultado) == {"Abrir planilha", "Abrir pasta", "Novo"}   # nada sem modelo
    assert dialogos.perguntas == []


def test_arquivo_existente_pergunta_antes_de_substituir(criar_painel, dialogos, tmp_path):
    _exige_exemplos()
    existente = tmp_path / "conciliacao_bancaria_2026-08.xlsx"
    existente.write_bytes(b"planilha antiga")
    dialogos.resposta = False                                           # responde "Não"
    painel = criar_painel(MODULO).conciliacao
    _preencher(painel, ARQUIVO_BALANCETE, PASTA_EXTRATOS, tmp_path)

    painel.processar()

    assert len(dialogos.perguntas) == 1
    assert not painel.ocupado                                           # não começou
    assert existente.read_bytes() == b"planilha antiga"                 # não mexeu no arquivo


def test_balancete_ilegivel_avisa_e_nao_comeca(criar_painel, dialogos, tmp_path):
    balancete_ruim = tmp_path / "balancete.xlsx"
    balancete_ruim.write_bytes(b"nao e excel")
    painel = criar_painel(MODULO).conciliacao
    _preencher(painel, balancete_ruim, tmp_path, tmp_path)

    painel.processar()                         # a leitura da competência falha antes de começar

    assert not painel.ocupado
    assert dialogos.avisos
    assert "Não foi possível ler o balancete" in painel.cartao_balancete.texto_confirmacao
    assert painel.cartao_balancete.status_confirmacao == "erro"


# ---------------------------------------------------------------------------
# Botão "Modelo novo" (Etapa 10 do programa original)
# ---------------------------------------------------------------------------


class _LeitorQueNaoReconheceNada(leitores_bancos.LeitorBase):
    nome = "Nenhum"
    banco = "TESTE"

    def reconhece(self, texto):
        return False


@pytest.fixture
def conciliado_sem_modelo(criar_painel, dialogos, tmp_path, monkeypatch):
    """Concilia uma pasta com um PDF que nenhum leitor reconhece."""
    _exige_exemplos()
    monkeypatch.setattr(identificador_bancos, "LEITORES", [_LeitorQueNaoReconheceNada()])
    extratos = tmp_path / "extratos" / "Itaú"
    extratos.mkdir(parents=True)
    shutil.copyfile(caminho_exemplo("1179 7.pdf"), extratos / "extrato novo.pdf")
    (tmp_path / "saida").mkdir()
    painel = criar_painel(MODULO).conciliacao
    _preencher(painel, ARQUIVO_BALANCETE, tmp_path / "extratos", tmp_path / "saida")
    _conciliar(painel)
    return painel, tmp_path / "saida"


def test_sem_modelo_nao_reconhecido_nao_ha_botao(criar_painel, dialogos, tmp_path):
    _exige_exemplos()
    extratos = tmp_path / "extratos"
    extratos.mkdir()
    shutil.copyfile(caminho_exemplo("1179 7.pdf"), extratos / "1179 7.pdf")
    painel = criar_painel(MODULO).conciliacao
    _preencher(painel, ARQUIVO_BALANCETE, extratos, tmp_path)
    _conciliar(painel)
    assert "Modelo novo" not in painel.botoes_resultado
    assert painel.preparar_modelo_novo() is None


def test_botao_modelo_aparece_com_pdf_nao_reconhecido(conciliado_sem_modelo):
    painel, _ = conciliado_sem_modelo
    assert "Modelo novo" in painel.botoes_resultado
    assert len(painel.nao_reconhecidos()) == 1


def test_formulario_salva_pacote_e_mostra_o_comando(conciliado_sem_modelo):
    painel, saida = conciliado_sem_modelo
    formulario = painel.preparar_modelo_novo()
    formulario.withdraw()
    assert "extrato novo.pdf" in formulario.rotulo_arquivo.cget("text")
    assert "Página 1" in formulario.previa.get("1.0", "end")

    formulario.var_banco.set("Itau")
    formulario.var_conta.set("1234-5")
    formulario.var_saldo.set("1.500,00")
    formulario.salvar()

    pasta = saida / "modelos_novos" / "2026-08_extrato novo"
    assert (pasta / "dados.json").is_file()
    assert (pasta / "PEDIDO.md").is_file()
    assert not formulario.winfo_exists()          # era o único arquivo: fechou
    assert [p.resolve() for p in painel.pacotes_criados] == [pasta.resolve()]
    assert painel.clipboard_get() == f'/novo-modelo "{painel.pacotes_criados[0]}"'


def test_formulario_com_saldo_invalido_nao_salva(conciliado_sem_modelo, dialogos):
    painel, saida = conciliado_sem_modelo
    formulario = FormularioModeloNovo(painel, painel.nao_reconhecidos(), painel.execucao.competencia, saida)
    formulario.withdraw()
    formulario.var_banco.set("Itau")
    formulario.var_conta.set("1234-5")
    formulario.var_saldo.set("mil e quinhentos")
    formulario.salvar()
    assert dialogos.erros                          # mostrou o erro
    assert formulario.winfo_exists()               # continua aberto
    assert not (saida / "modelos_novos").exists()
    formulario.destroy()


def test_formulario_pular_nao_cria_pacote(conciliado_sem_modelo):
    painel, saida = conciliado_sem_modelo
    formulario = painel.preparar_modelo_novo()
    formulario.withdraw()
    formulario.pular()
    assert not formulario.winfo_exists()
    assert not (saida / "modelos_novos").exists()


def test_painel_nao_usa_messagebox_fora_do_formulario():
    """Os diálogos da tela passam pela base (perguntar/avisar); só o formulário usa messagebox direto."""
    import inspect

    fonte = inspect.getsource(painel_bancos.PainelBancos)
    assert "messagebox" not in fonte
