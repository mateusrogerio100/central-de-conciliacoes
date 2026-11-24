"""Testes da aba Conciliação de clientes do módulo Clientes CMD (o original não tinha testes de interface)."""

from __future__ import annotations

from modulos.clientes_cmd import MODULO
from modulos.clientes_cmd.processamento import NOME_PADRAO_SAIDA, ResumoClientes
from testes.clientes_cmd.test_clientes_cmd import ARQUIVO_BALANCETE, ARQUIVO_FINANCEIRO, ARQUIVO_REFERENCIA
from testes.conftest import diferencas_entre_planilhas, esperar, pasta_exemplos


def _preencher(painel, exemplos, saida):
    painel.cartao_balancete.definir_caminhos(exemplos / ARQUIVO_BALANCETE)
    painel.cartao_financeiro.definir_caminhos(exemplos / ARQUIVO_FINANCEIRO)
    painel.cartao_saida.definir_caminhos(saida)


def test_botao_so_habilita_com_tudo_escolhido(criar_painel, tmp_path):
    exemplos = pasta_exemplos("clientes_cmd")
    painel = criar_painel(MODULO).conciliacao
    assert not painel.botao.habilitado
    painel.cartao_balancete.definir_caminhos(exemplos / ARQUIVO_BALANCETE)
    assert painel.pasta_saida == exemplos                  # pasta de saída sugerida
    assert painel.botao.habilitado is False                # falta o financeiro
    painel.cartao_financeiro.definir_caminhos(exemplos / ARQUIVO_FINANCEIRO)
    assert painel.botao.habilitado


def test_gerar_conciliacao_pela_tela(criar_painel, dialogos, tmp_path):
    exemplos = pasta_exemplos("clientes_cmd")
    painel = criar_painel(MODULO).conciliacao
    _preencher(painel, exemplos, tmp_path)

    painel.processar()
    assert painel.ocupado
    esperar(painel, lambda: not painel.ocupado)

    destino = tmp_path / NOME_PADRAO_SAIDA
    assert painel.resultado.estado == "concluido"
    assert painel.ultimo_resultado.resumo == ResumoClientes(total=1214, ok=1173, divergente=15, sem_contabil=8,
                                                            sem_financeiro=18)
    assert diferencas_entre_planilhas(exemplos / ARQUIVO_REFERENCIA, destino) == []
    assert set(painel.botoes_resultado) == {"Abrir planilha", "Abrir pasta", "Novo"}


def test_arquivo_existente_pergunta_antes_de_substituir(criar_painel, dialogos, tmp_path):
    exemplos = pasta_exemplos("clientes_cmd")
    existente = tmp_path / NOME_PADRAO_SAIDA
    existente.write_bytes(b"planilha antiga")
    dialogos.resposta = False
    painel = criar_painel(MODULO).conciliacao
    _preencher(painel, exemplos, tmp_path)

    painel.processar()

    assert len(dialogos.perguntas) == 1 and NOME_PADRAO_SAIDA in dialogos.perguntas[0]
    assert not painel.ocupado and existente.read_bytes() == b"planilha antiga"


def test_relatorio_que_nao_e_planilha_mostra_erro(criar_painel, dialogos, tmp_path):
    ruim = tmp_path / "balancete.xlsx"
    ruim.write_bytes(b"nao e excel")
    painel = criar_painel(MODULO).conciliacao
    painel.cartao_balancete.definir_caminhos(ruim)
    painel.cartao_financeiro.definir_caminhos(ruim)
    painel.cartao_saida.definir_caminhos(tmp_path / "saida")

    painel.processar()
    esperar(painel, lambda: not painel.ocupado)

    assert painel.resultado.selo.cget("text") == "Erro"
    assert painel.botao.habilitado                          # dá para corrigir e tentar de novo
