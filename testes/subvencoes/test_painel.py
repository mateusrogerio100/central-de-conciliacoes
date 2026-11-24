"""Testes da tela de Subvenções e Projetos (adaptados de testes/test_interface.py do programa original).

A parte visual é conferida pelo usuário ao usar a Central; aqui ficam as regras da tela:
validação dos campos, mês lido do balancete (R10), perguntas antes de seguir (R10, R11) e o
processamento completo de agosto pela tela.
"""

from __future__ import annotations

import ast
import shutil

from modulos.subvencoes import MODULO
from modulos.subvencoes.modelos import (
    ArquivoResumo,
    Aviso,
    Gravidade,
    MesReferencia,
    ResultadoProcessamento,
    StatusArquivo,
)
from modulos.subvencoes.resumo_tela import formatar_reais, resumir
from testes.conftest import RAIZ, esperar
from testes.subvencoes.conftest import arquivos_do_mes


def test_painel_so_usa_processamento_e_resumo():
    """A tela não tem regra de negócio: não importa leitores, conciliação nem preenchedor."""
    arvore = ast.parse((RAIZ / "modulos" / "subvencoes" / "telas" / "preenchimento.py").read_text(encoding="utf-8"))
    usados = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.ImportFrom) and no.module and no.module.startswith("modulos"):
            if no.module == "modulos.subvencoes":          # from modulos.subvencoes import processamento
                usados.update(f"{no.module}.{n.name}" for n in no.names)
            else:
                usados.add(no.module)
    assert usados <= {"modulos.subvencoes.processamento", "modulos.subvencoes.resumo_tela"}


def test_validacao_dos_campos(criar_painel, tmp_path):
    painel = criar_painel(MODULO).preenchimento
    erro, mes = painel.validar()
    assert mes is None
    for trecho in ("Balancete", "Patrimônio", "planilha", "pasta de saída"):
        assert trecho in erro
    assert not painel.botao.habilitado

    painel.cartao_balancete.definir_caminhos(tmp_path / "Balancete.xlsx", avisar=False)
    painel.cartao_patrimonio.definir_caminhos(tmp_path / "patrimonio.xlsx", avisar=False)
    painel.cartao_planilhas.definir_caminhos([tmp_path / "Projetos_08-2026.xlsx"], avisar=False)
    painel.cartao_saida.definir_caminhos(tmp_path, avisar=False)
    painel.atualizar_botoes()
    assert painel.botao.habilitado

    painel.campo_mes.definir("13/2026")
    erro, mes = painel.validar()
    assert "MM/AAAA" in erro and mes is None

    painel.campo_mes.definir("09/2026")
    assert painel.validar() == (None, MesReferencia(2026, 9))


def test_mes_lido_do_balancete_vai_para_o_campo(criar_painel):
    arquivos = arquivos_do_mes("2026-08")
    painel = criar_painel(MODULO).preenchimento

    painel.cartao_balancete.definir_caminhos(arquivos.balancete)          # como se o usuário escolhesse
    esperar(painel, lambda: painel._mes_balancete is not None)

    assert painel.campo_mes.valor() == "08/2026"                          # R10: editável
    assert painel.campo_mes.entrada.cget("state") == "normal"
    assert painel.cartao_balancete.texto_confirmacao == "Mês de referência 08/2026"
    assert painel.cartao_balancete.status_confirmacao == "ok"
    assert painel.pasta_saida == arquivos.balancete.parent                # pasta de saída sugerida


def test_patrimonio_de_outro_mes_fica_em_atencao(criar_painel):
    agosto, julho = arquivos_do_mes("2026-08"), arquivos_do_mes("2026-07")
    painel = criar_painel(MODULO).preenchimento
    painel.cartao_balancete.definir_caminhos(agosto.balancete)
    painel.cartao_patrimonio.definir_caminhos(julho.patrimonio)
    esperar(painel, lambda: painel._mes_balancete is not None and painel._mes_patrimonio is not None)

    assert painel.cartao_patrimonio.status_confirmacao == "atencao"
    assert "diferente do balancete (08/2026)" in painel.cartao_patrimonio.texto_confirmacao


def _preparar(painel, arquivos, saida, patrimonio=None):
    painel.cartao_balancete.definir_caminhos(arquivos.balancete, avisar=False)
    painel.cartao_patrimonio.definir_caminhos(patrimonio or arquivos.patrimonio, avisar=False)
    painel.cartao_planilhas.definir_caminhos([arquivos.subvencoes, arquivos.projetos], avisar=False)
    painel.cartao_saida.definir_caminhos(saida, avisar=False)
    painel.campo_mes.definir("08/2026")
    painel.atualizar_botoes()


def test_preencher_agosto_pela_tela(criar_painel, dialogos, tmp_path):
    arquivos = arquivos_do_mes("2026-08")
    painel = criar_painel(MODULO).preenchimento
    _preparar(painel, arquivos, tmp_path)

    painel.processar()
    assert painel.ocupado and not painel.botao.habilitado                # não deixa clicar de novo
    esperar(painel, lambda: painel.ultimo_resultado is not None)

    resultado = painel.ultimo_resultado
    assert painel.resultado.estado == "concluido" and painel.botao.habilitado
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(
        [arquivos.subvencoes.name, arquivos.projetos.name, "Avisos_08-2026.xlsx"])
    resumo = resumir(resultado)
    assert resumo.contas_preenchidas == 123 and resumo.erros == 0
    assert sorted(a.aba for a in resumo.abas) == sorted(["PROJETOS 1", "Federal Investimento", "Estadual Investimento",
                                                         "Municipal Investimento"])
    assert [c.status for c in resumo.conferencias] == ["ok", "ok"]
    assert painel.resultado.selo.cget("text") == "Concluído"
    assert dialogos.perguntas == []                                       # nada a perguntar


def test_meses_diferentes_pergunta_e_nao_segue_se_responder_nao(criar_painel, dialogos, tmp_path):
    agosto, julho = arquivos_do_mes("2026-08"), arquivos_do_mes("2026-07")
    painel = criar_painel(MODULO).preenchimento
    _preparar(painel, agosto, tmp_path, patrimonio=julho.patrimonio)
    dialogos.resposta = False

    painel.processar()
    esperar(painel, lambda: not painel.ocupado and painel.resultado.estado == "vazio")

    assert len(dialogos.perguntas) == 1 and "08/2026" in dialogos.perguntas[0]
    assert list(tmp_path.iterdir()) == []                                 # nada foi gravado


def test_arquivo_existente_pergunta_antes_de_substituir(criar_painel, dialogos, tmp_path):
    arquivos = arquivos_do_mes("2026-08")
    existente = tmp_path / "Avisos_08-2026.xlsx"
    existente.write_bytes(b"relatorio antigo")
    painel = criar_painel(MODULO).preenchimento
    _preparar(painel, arquivos, tmp_path)
    dialogos.resposta = False

    painel.processar()
    esperar(painel, lambda: not painel.ocupado and painel.resultado.estado == "vazio")

    assert len(dialogos.perguntas) == 1 and "Avisos_08-2026.xlsx" in dialogos.perguntas[0]
    assert existente.read_bytes() == b"relatorio antigo"


def test_novo_limpa_as_escolhas(criar_painel, tmp_path):
    arquivos = arquivos_do_mes("2026-08")
    painel = criar_painel(MODULO).preenchimento
    _preparar(painel, arquivos, tmp_path)
    painel.novo()
    assert not painel.cartao_balancete.preenchido and not painel.cartao_planilhas.preenchido
    assert painel.pasta_saida == tmp_path                                 # a pasta de saída fica
    assert painel.campo_mes.valor() == "" and not painel.botao.habilitado


def test_resumo_tela_com_problemas():
    """Adaptado de test_montar_resumo: arquivo que falhou e relatório não gravado aparecem como erro."""
    resultado = ResultadoProcessamento(mes_referencia=MesReferencia(2026, 8), pasta_saida="c:/saida")
    resultado.arquivos = [
        ArquivoResumo("c:/e/Balancete.xlsx", "Balancete", StatusArquivo.LIDO, MesReferencia(2026, 8)),
        ArquivoResumo("c:/e/Projetos_08-2026.xlsx", "Planilha", StatusArquivo.GERADO,
                      destino="c:/saida/Projetos_08-2026.xlsx", linhas_preenchidas=15, linhas_com_diferenca=9),
        ArquivoResumo("c:/e/Outra.xlsx", "Planilha", StatusArquivo.FALHOU, detalhe="Feche o arquivo no Excel."),
    ]
    resultado.avisos = [Aviso(Gravidade.ERRO, "planilha não gerada", "Feche o arquivo no Excel.", arquivo="Outra.xlsx"),
                        Aviso(Gravidade.ATENCAO, "vínculo externo", "x")]
    resultado.erro_relatorio = "Avisos_08-2026.xlsx: não foi possível gravar."

    resumo = resumir(resultado)

    assert (resumo.contas_preenchidas, resumo.contas_com_diferenca) == (15, 9)
    assert (resumo.avisos, resumo.erros, resumo.atencoes) == (2, 1, 1)
    assert resumo.legenda_avisos == "avisos · 1 erro"
    assert resumo.selo == ("Concluído com erros", "erro")
    textos = [c.texto for c in resumo.conferencias]
    assert "Planilha Outra.xlsx: falhou — Feche o arquivo no Excel." in textos
    assert "Relatório de avisos NÃO gravado: Avisos_08-2026.xlsx: não foi possível gravar." in textos


def test_formatar_reais():
    from decimal import Decimal

    assert formatar_reais(Decimal("29469866.53")) == "29.469.866,53"
    assert formatar_reais(Decimal("-0.5")) == "-0,50"


def test_entradas_nao_sao_alteradas_pela_tela(criar_painel, dialogos, tmp_path):
    """As planilhas de entrada continuam idênticas depois de preencher pela tela."""
    arquivos = arquivos_do_mes("2026-08")
    copia = tmp_path / "entrada"
    shutil.copytree(arquivos.pasta, copia)
    antes = {p.name: p.read_bytes() for p in copia.iterdir()}
    painel = criar_painel(MODULO).preenchimento
    painel.cartao_balancete.definir_caminhos(copia / arquivos.balancete.name, avisar=False)
    painel.cartao_patrimonio.definir_caminhos(copia / arquivos.patrimonio.name, avisar=False)
    painel.cartao_planilhas.definir_caminhos([copia / arquivos.subvencoes.name, copia / arquivos.projetos.name],
                                             avisar=False)
    painel.cartao_saida.definir_caminhos(tmp_path / "saida", avisar=False)
    (tmp_path / "saida").mkdir()
    painel.campo_mes.definir("08/2026")

    painel.processar()
    esperar(painel, lambda: painel.ultimo_resultado is not None)

    assert {p.name: p.read_bytes() for p in copia.iterdir()} == antes


def test_nunca_grava_por_cima_das_planilhas_de_entrada(criar_painel, dialogos, tmp_path):
    """Pasta de saída = pasta das planilhas, com o mesmo mês: a cópia teria o nome da entrada."""
    arquivos = arquivos_do_mes("2026-08")
    copia = tmp_path / "entrada"
    shutil.copytree(arquivos.pasta, copia)
    antes = {p.name: p.read_bytes() for p in copia.iterdir()}
    painel = criar_painel(MODULO).preenchimento
    painel.cartao_balancete.definir_caminhos(copia / arquivos.balancete.name, avisar=False)
    painel.cartao_patrimonio.definir_caminhos(copia / arquivos.patrimonio.name, avisar=False)
    painel.cartao_planilhas.definir_caminhos([copia / arquivos.subvencoes.name, copia / arquivos.projetos.name],
                                             avisar=False)
    painel.cartao_saida.definir_caminhos(copia, avisar=False)
    painel.campo_mes.definir("08/2026")

    painel.processar()
    esperar(painel, lambda: not painel.ocupado)

    assert len(dialogos.avisos) == 1 and "nunca são alterados" in dialogos.avisos[0]
    assert dialogos.perguntas == []                     # nem pergunta se pode substituir
    assert {p.name: p.read_bytes() for p in copia.iterdir()} == antes
