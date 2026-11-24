"""Etapa Tomados 6: tela do módulo Serviços Tomados (montada sem mostrar a janela).

A parte visual é conferida pelo usuário ao usar a Central; aqui ficam as regras da tela: botão
habilitado só com o necessário, validação, confirmações dos cartões, campos das exportações,
geração completa pela tela, perguntas (cidade e substituição) e "Novo".
"""

from __future__ import annotations

import ast
import threading
from datetime import date

import pytest

from modulos.escrituracao_tomados import MODULO, processamento
from modulos.escrituracao_tomados.telas import outros_cnpjs, pergunta_cidade
from modulos.escrituracao_tomados.telas.gerar_arquivo import PerguntasDaTarefa
from testes.conftest import RAIZ, esperar, pasta_exemplos

MATRIZ = "98765432000198"


def _pdfs():
    return pasta_exemplos("escrituracao_tomados", "2026-08", "pdfs")


def _esperado(nome):
    return (pasta_exemplos("escrituracao_tomados", "esperado") / nome).read_bytes()


@pytest.fixture
def tela(criar_painel):
    return criar_painel(MODULO).gerar


def _preparar_pdfs(tela, saida, tipo="Complementar", data="28/09/2026"):
    tela.cartao_pdfs.definir_caminhos(_pdfs(), avisar=False)
    tela.seletor_tipo.selecionar(tipo)
    tela.campo_data.definir(data)
    tela.cartao_saida.definir_caminhos(saida, avisar=False)
    tela.atualizar_botoes()


def _gerar_e_esperar(tela):
    tela.processar()
    esperar(tela, lambda: not tela.ocupado)
    return tela.ultimo_resultado


def test_tela_so_usa_o_processamento():
    """A tela não tem regra de negócio: só conversa com processamento.py (e a janela da cidade)."""
    arvore = ast.parse((RAIZ / "modulos" / "escrituracao_tomados" / "telas" / "gerar_arquivo.py")
                       .read_text(encoding="utf-8"))
    usados = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.ImportFrom) and no.module and no.module.startswith("modulos"):
            usados.update(f"{no.module}.{n.name}" for n in no.names)
    assert usados <= {"modulos.escrituracao_tomados.processamento",
                      "modulos.escrituracao_tomados.telas.outros_cnpjs",
                      "modulos.escrituracao_tomados.telas.pergunta_cidade"}


def test_modulo_no_menu():
    from central import registro

    carregados = {m.chave: m for m in registro.carregar_modulos()}
    modulo = carregados["escrituracao_tomados"]
    assert modulo.ok and modulo.info.nome == "Serviços Tomados"
    assert modulo.info.contexto == "Escrituração / ISS"


def test_botao_so_habilita_com_o_necessario(tela, tmp_path):
    assert not tela.botao.habilitado
    assert tela.seletor_tipo.valor is None                      # R14: escolhido a cada geração
    assert tela.campo_data.valor() == date.today().strftime("%d/%m/%Y")
    tela.cartao_pdfs.definir_caminhos(tmp_path, avisar=False)
    tela.cartao_saida.definir_caminhos(tmp_path, avisar=False)
    tela.atualizar_botoes()
    assert not tela.botao.habilitado                           # falta o tipo
    tela.seletor_tipo.botoes["Normal"].invoke()
    assert tela.botao.habilitado
    tela.campo_data.definir("31/02/2026")
    assert not tela.botao.habilitado                           # data inválida
    tela.campo_data.definir("30/09/2026")
    assert tela.botao.habilitado


def test_validacao_das_exportacoes(tela, tmp_path, dialogos):
    tela.cartao_exportacoes.definir_caminhos([tmp_path / "lote.csv"], avisar=False)
    tela.seletor_tipo.selecionar("Normal")
    tela.cartao_saida.definir_caminhos(tmp_path, avisar=False)
    assert "CNPJ do tomador" in tela.validar()
    tela.campo_tomador.definir("98.765.432/0001-98")
    assert "competência" in tela.validar()
    tela.campo_competencia.definir("08/2026")
    assert tela.validar() is None
    tela.processar()                                           # validar() None -> gera; aqui só a mensagem
    esperar(tela, lambda: not tela.ocupado)


def test_falta_escolher_mostra_mensagem(tela, dialogos):
    tela.processar()
    assert len(dialogos.avisos) == 1
    for trecho in ("PDFs ou as exportações", "tipo da declaração", "pasta de saída"):
        assert trecho in dialogos.avisos[0]


def test_escolher_pdfs_conta_e_sugere_a_saida(tela):
    tela.cartao_pdfs.definir_caminhos(_pdfs())                 # como se o usuário escolhesse
    esperar(tela, lambda: "encontrado" in tela.cartao_pdfs.texto_confirmacao)
    assert tela.cartao_pdfs.texto_confirmacao == "20 PDFs encontrados"
    assert tela.cartao_pdfs.status_confirmacao == "ok"
    assert tela.pasta_saida == _pdfs() / "saida"


def test_escolher_exportacoes_mostra_os_campos_e_conta(tela):
    lotes = pasta_exemplos("escrituracao_tomados", "2026-08", "exportacoes_lotes")
    assert tela.area_exportacao.winfo_manager() == ""
    tela.cartao_exportacoes.definir_caminhos([lotes / "lote_249.txt", lotes / "lote_337_118.txt"])
    esperar(tela, lambda: "arquivo" in tela.cartao_exportacoes.texto_confirmacao)
    assert tela.cartao_exportacoes.texto_confirmacao == "3 notas em 2 arquivos"
    assert tela.area_exportacao.winfo_manager() == "pack"
    tela.novo()
    assert tela.area_exportacao.winfo_manager() == ""


def test_limpar_exportacoes_esconde_os_campos_e_apaga_o_botao(tela, tmp_path):
    tela.cartao_exportacoes.definir_caminhos([tmp_path / "lote.csv"])
    tela.cartao_resultados.definir_caminhos([tmp_path / "resultado08.csv"])
    tela.seletor_tipo.selecionar("Normal")
    tela.cartao_saida.definir_caminhos(tmp_path, avisar=False)
    tela.atualizar_botoes()
    assert tela.area_exportacao.winfo_manager() == "pack" and tela.botao.habilitado
    assert tela.cartao_resultados.status_confirmacao == "atencao"

    tela.cartao_exportacoes.botao_limpar.invoke()
    assert tela.area_exportacao.winfo_manager() == ""                # campos somem
    assert not tela.botao.habilitado                                  # sem PDFs nem exportações
    assert tela.cartao_resultados.status_confirmacao == "ok"          # aviso da R9 sai


def test_aviso_da_r9_so_quando_unifica(tela, tmp_path):
    resultado = [tmp_path / "resultado08.csv"]
    tela.cartao_resultados.definir_caminhos(resultado)
    assert tela.cartao_resultados.texto_confirmacao == "1 resultado da prefeitura"
    assert tela.cartao_resultados.status_confirmacao == "ok"
    tela.cartao_exportacoes.definir_caminhos([tmp_path / "lote.csv"])   # agora vai unificar
    assert "lotes que serão substituídos" in tela.cartao_resultados.texto_confirmacao
    assert tela.cartao_resultados.status_confirmacao == "atencao"


def test_legenda_das_nao_incluidas():
    from types import SimpleNamespace

    from modulos.escrituracao_tomados.telas.gerar_arquivo import legenda_nao_incluidas

    r = SimpleNamespace(ja_escrituradas=8, canceladas=0, duplicadas=1, erros_de_leitura=0,
                        nao_incluidas=14)
    assert legenda_nao_incluidas(r) == ("não incluídas: 8 já escrituradas · 1 duplicada · "
                                        "5 por outro motivo")
    vazio = SimpleNamespace(ja_escrituradas=0, canceladas=0, duplicadas=0, erros_de_leitura=0,
                            nao_incluidas=0)
    assert legenda_nao_incluidas(vazio) == "não incluídas"


def test_gerar_pela_tela_t1(tela, tmp_path, dialogos):
    _preparar_pdfs(tela, tmp_path)
    tela.processar()
    assert tela.ocupado and not tela.botao.habilitado
    esperar(tela, lambda: not tela.ocupado)

    r = tela.ultimo_resultado
    assert (tmp_path / "tomados_98765432000198_08-2026.txt").read_bytes() == \
        _esperado("teste1_tomados_98765432000198_08-2026.txt")
    assert not (tmp_path / "tomados_98765432000198_07-2026.txt").exists()   # 229/230: V17
    assert tela.resultado.estado == "concluido" and tela.botao.habilitado
    # "com avisos": o lembrete de corrigir o número da 2026000000090 no site (R8)
    assert tela.resultado.selo.cget("text") == "Concluído com avisos"
    assert (r.notas_no_arquivo, r.lancar_a_mao, r.nao_incluidas) == (12, 2, 6)
    assert dialogos.perguntas == [] and dialogos.avisos == []
    assert tela.botoes_resultado["Ver avisos"].habilitado


def test_substituir_pergunta_e_nao_grava_se_responder_nao(tela, tmp_path, dialogos):
    existente = tmp_path / "tomados_98765432000198_08-2026.txt"
    existente.write_bytes(b"antigo")
    _preparar_pdfs(tela, tmp_path)
    dialogos.resposta = False

    r = _gerar_e_esperar(tela)
    assert r.cancelado and existente.read_bytes() == b"antigo"
    assert len(dialogos.perguntas) == 1 and existente.name in dialogos.perguntas[0]
    assert "Nada foi gravado" in dialogos.informacoes[0]
    assert tela.resultado.estado == "vazio"


def test_cidade_perguntada_pela_tela(tela, tmp_path, dialogos, monkeypatch):
    lote = tmp_path / "lote.csv"
    lote.write_bytes(("cfps;nfs;situacaonf;cnpjcpf;nome;dtemissao;descratividade;vlrservicos;"
                      "vlrdeducoes;descontoincondicionado;basecalculo;aliquota;impretido;"
                      "vlrimposto;enquadradosn;\r\n1;77;Normal;33.333.333/0001-91;PRESTADOR NOVO;"
                      "05/08/2026;04.01.01  Medicina.;100,00;0,00;;100,00;2,00;NÃO;2,00;N;\r\n"
                      ).encode("latin-1"))
    perguntas = []

    def responder(pai, documento, nome):
        perguntas.append((documento, nome, threading.current_thread() is threading.main_thread()))
        return "Uberaba", "MG"

    monkeypatch.setattr(pergunta_cidade, "perguntar_cidade", responder)
    tela.cartao_exportacoes.definir_caminhos([lote], avisar=False)
    tela.campo_tomador.definir(MATRIZ)
    tela.campo_competencia.definir("08/2026")
    tela.seletor_tipo.selecionar("Normal")
    tela.cartao_saida.definir_caminhos(tmp_path / "saida", avisar=False)

    r = _gerar_e_esperar(tela)
    assert perguntas == [("33333333000191", "PRESTADOR NOVO", True)]     # na thread da janela
    (nota,) = r.notas
    assert (nota.prestador_cidade, nota.codigo_retido) == ("UBERABA", "Z")
    assert r.notas_no_arquivo == 1
    assert MATRIZ in tela.campo_tomador.opcoes                          # R12: lembrado
    assert processamento.tomadores_usados() == [MATRIZ]


def test_novo_limpa_as_escolhas(tela, tmp_path):
    _preparar_pdfs(tela, tmp_path, data="01/01/2026")
    tela.novo()
    assert not tela.cartao_pdfs.preenchido and tela.seletor_tipo.valor is None
    assert tela.campo_data.valor() == date.today().strftime("%d/%m/%Y")
    assert tela.pasta_saida == tmp_path                                 # a pasta de saída fica
    assert not tela.botao.habilitado


# ---------------------------------------------------------------------------
# Peças da tela
# ---------------------------------------------------------------------------


def test_janela_da_cidade(raiz_tk):
    janela = pergunta_cidade.JanelaCidade(raiz_tk, "33333333000191", "PRESTADOR NOVO")
    janela.withdraw()
    janela.confirmar()
    assert janela.winfo_exists() and "cidade" in janela.rotulo_erro.cget("text")
    janela.campo_cidade.definir("Uberaba")
    janela.campo_uf.definir("Minas")
    janela.confirmar()
    assert "UF" in janela.rotulo_erro.cget("text")
    janela.campo_uf.definir("mg")
    janela.confirmar()
    assert janela.resposta == ("Uberaba", "MG")

    outra = pergunta_cidade.JanelaCidade(raiz_tk, "12345678909", "FULANO")
    outra.withdraw()
    outra.nao_sei()
    assert outra.resposta is None


def test_outros_cnpjs_pela_tela(tela, monkeypatch):
    assert tela.rotulo_outros_cnpjs.cget("text") == "só os CNPJs com a raiz 98.765.432"
    recebidos = []

    def editar(pai, cnpjs, interpretar):
        recebidos.append(cnpjs)
        return interpretar("11.222.333/0001-81")[0]

    monkeypatch.setattr(outros_cnpjs, "editar_outros_cnpjs", editar)
    tela.botao_outros_cnpjs.invoke()
    assert recebidos == [[]]
    assert processamento.outros_cnpjs_fundacao() == ["11222333000181"]
    assert tela.rotulo_outros_cnpjs.cget("text") == "além da raiz 98.765.432, 1 CNPJ de outra raiz"

    monkeypatch.setattr(outros_cnpjs, "editar_outros_cnpjs", lambda *_: None)    # cancelou
    tela.botao_outros_cnpjs.invoke()
    assert processamento.outros_cnpjs_fundacao() == ["11222333000181"]


def test_janela_dos_outros_cnpjs(raiz_tk):
    janela = outros_cnpjs.JanelaOutrosCnpjs(raiz_tk, ["11222333000181"],
                                            processamento.interpretar_outros_cnpjs)
    janela.withdraw()
    assert janela.texto().strip() == "11.222.333/0001-81"
    janela.definir_texto("11.222.333/0001-81\n11.222.333/0001-82")
    janela.salvar()
    assert janela.winfo_exists() and "0001-82" in janela.rotulo_erro.cget("text")
    janela.definir_texto("11.222.333/0001-81\n98.765.432/0001-98")
    janela.salvar()
    assert janela.resposta == ["11222333000181", "98765432000198"]

    outra = outros_cnpjs.JanelaOutrosCnpjs(raiz_tk, [], processamento.interpretar_outros_cnpjs)
    outra.withdraw()
    outra.cancelar()
    assert outra.resposta is None


def test_formatar_documento():
    assert pergunta_cidade.formatar_documento("33333333000191") == "33.333.333/0001-91"
    assert pergunta_cidade.formatar_documento("12345678909") == "123.456.789-09"


def test_perguntas_da_tarefa_levam_a_pergunta_para_a_janela(raiz_tk):
    ponte = PerguntasDaTarefa(raiz_tk)
    ponte.iniciar()
    respostas = []

    def trabalho():
        respostas.append(ponte.perguntar(lambda a, b: (a + b, threading.current_thread().name), 1, 2))

    thread = threading.Thread(target=trabalho, name="trabalho")
    thread.start()
    esperar(raiz_tk, lambda: respostas, limite_segundos=10)
    ponte.parar()
    assert respostas == [(3, threading.main_thread().name)]


def test_erro_na_pergunta_volta_para_a_tarefa(raiz_tk):
    ponte = PerguntasDaTarefa(raiz_tk)
    ponte.iniciar()
    erros = []

    def falha():
        raise ValueError("problema")

    def trabalho():
        try:
            ponte.perguntar(falha)
        except ValueError as erro:
            erros.append(str(erro))

    threading.Thread(target=trabalho).start()
    esperar(raiz_tk, lambda: erros, limite_segundos=10)
    ponte.parar()
    assert erros == ["problema"]
