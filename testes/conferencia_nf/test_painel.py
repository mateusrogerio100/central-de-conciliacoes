"""T7 — tela do módulo Conferência de NF (montada sem mostrar a janela).

A parte visual é conferida pelo usuário ao usar a Central; aqui ficam as regras da tela: módulo no
registro, botão habilitado só com a unidade e os três caminhos, confirmação dos cartões, conferência completa
pela tela, últimas pastas lembradas e "Novo". Todos os testes usam um %APPDATA% temporário e
nunca abrem o Excel.
"""

from __future__ import annotations

import ast
import shutil

import pytest

from central import registro
from modulos.conferencia_nf import MODULO, processamento
from modulos.conferencia_nf.modelos import FalhaLeitura
from testes.conftest import RAIZ, esperar, pasta_exemplos

UNIDADE_PRINCIPAL = "Fundação Hospital Exemplo (98.765.432/0001-98)"


@pytest.fixture(autouse=True)
def appdata_temporario(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))


@pytest.fixture
def tela(criar_painel, monkeypatch):
    painel = criar_painel(MODULO).conferencia
    painel.abertos = []
    monkeypatch.setattr(painel, "abrir", painel.abertos.append)   # nunca abre o Excel de verdade
    return painel


def _lote_pequeno(tmp_path):
    """O lote 72887 com só 2 PDFs (1 DANFE e 1 DANFSe)."""
    lote = pasta_exemplos("conferencia_nf", "lote_72887")
    pdfs = tmp_path / "pdfs"
    for padrao in ("DANFE-935-*.pdf", "DANFSe-968-*.pdf"):
        origem = next(lote.rglob(padrao))
        (pdfs / origem.parent.name).mkdir(parents=True, exist_ok=True)
        shutil.copy(origem, pdfs / origem.parent.name / origem.name)
    return next(lote.glob("Movimento*.csv")), pdfs


def _confirmacao(tela, cartao):
    esperar(tela, lambda: cartao.status_confirmacao is not None)
    return cartao.texto_confirmacao, cartao.status_confirmacao


# ---------------------------------------------------------------------------
# Módulo e arquitetura
# ---------------------------------------------------------------------------

def test_t7_modulo_no_registro_na_secao_fiscal():
    assert registro.SECAO_DO_MODULO["conferencia_nf"] == "FISCAL"
    carregado = next(m for m in registro.carregar_modulos() if m.chave == "conferencia_nf")
    assert carregado.ok and carregado.info.nome == "Conferência de NF"
    assert carregado.info.icone == "check"
    assert (RAIZ / "central" / "icones" / "check.png").exists()
    assert (RAIZ / "modulos" / "conferencia_nf" / "INSTRUCOES_DE_USO.md").exists()


def test_t7_tela_so_usa_o_processamento():
    """A tela não tem regra de negócio: só conversa com processamento.py."""
    arvore = ast.parse((RAIZ / "modulos" / "conferencia_nf" / "telas" / "conferencia.py")
                       .read_text(encoding="utf-8"))
    usados = {no.module + "." + n.name for no in ast.walk(arvore)
              if isinstance(no, ast.ImportFrom) and no.module and no.module.startswith("modulos")
              for n in no.names}
    assert usados == {"modulos.conferencia_nf.processamento"}


def test_t7_logica_nao_importa_customtkinter_nem_outro_modulo():
    pasta = RAIZ / "modulos" / "conferencia_nf"
    for arquivo in pasta.glob("*.py"):
        if arquivo.name == "painel.py":
            continue
        for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
            nomes = [a.name for a in no.names] if isinstance(no, ast.Import) else \
                [no.module or ""] if isinstance(no, ast.ImportFrom) else []
            for nome in nomes:
                assert not nome.startswith("customtkinter"), arquivo.name
                assert not nome.startswith("modulos.") or nome.startswith("modulos.conferencia_nf"), \
                    (arquivo.name, nome)


# ---------------------------------------------------------------------------
# Tela
# ---------------------------------------------------------------------------

def test_t7_tela_criada_vazia_e_botao_desabilitado(tela):
    assert tela.resultado.estado == "vazio"
    assert tela.botao.cget("text") == "Conferir lote"
    assert tela.botao.cget("state") == "disabled"
    assert [c.rotulo for c in tela.cartoes] == [
        "Lote do Tasy (.csv: Movimento contábil ou movimento do lote)",
        "Pasta das notas: PDFs e XMLs (DANFE e DANFSe, com as subpastas)",
        "Pasta do gabarito de contas (opcional)", "Pasta de saída"]


def test_escolher_o_lote_confere_e_sugere_a_pasta_de_saida(tela):
    lote = next(pasta_exemplos("conferencia_nf", "lote_72887").glob("Movimento*.csv"))
    tela.cartao_lote.definir_caminhos(lote)
    assert _confirmacao(tela, tela.cartao_lote) == ("55 fatos contábeis, 122 lançamentos", "ok")
    assert tela.pasta_saida == lote.parent
    assert tela.botao.cget("state") == "disabled"          # falta a pasta dos PDFs


def test_lote_errado_fica_vermelho(tela, tmp_path):
    errado = tmp_path / "outro.csv"
    errado.write_text("a;b\n1;2\n", encoding="utf-8")
    tela.cartao_lote.definir_caminhos(errado)
    texto, status = _confirmacao(tela, tela.cartao_lote)
    assert status == "erro" and texto.startswith("Não é o lote esperado: Colunas não encontradas")


def test_pasta_dos_pdfs_mostra_quantos_ha(tela, tmp_path):
    tela.cartao_pdfs.definir_caminhos(tmp_path)
    assert _confirmacao(tela, tela.cartao_pdfs) == (
        "Nenhum PDF nem XML nesta pasta nem nas subpastas", "atencao")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.pdf").write_bytes(b"")
    (tmp_path / "b.PDF").write_bytes(b"")
    tela.cartao_pdfs.definir_caminhos(tmp_path)
    assert _confirmacao(tela, tela.cartao_pdfs) == ("2 PDFs (com as subpastas)", "ok")


def test_conferir_pela_tela(tela, tmp_path):
    lote, pdfs = _lote_pequeno(tmp_path)
    saida = tmp_path / "saida"
    saida.mkdir()
    tela.cartao_lote.definir_caminhos(lote)
    tela.cartao_pdfs.definir_caminhos(pdfs)
    tela.cartao_saida.definir_caminhos(saida)
    assert tela.botao.cget("state") == "disabled"          # falta a unidade (S15)
    assert tela.campo_unidade.opcoes[0] == "Fundação Hospital Exemplo (98.765.432/0001-98)"
    assert len(tela.campo_unidade.opcoes) == 9                # 9 com o CMD (04/11/2026)
    tela.campo_unidade.definir(UNIDADE_PRINCIPAL)
    assert tela.botao.cget("state") == "normal"

    tela.processar()
    esperar(tela, lambda: not tela.ocupado)
    resultado = tela.ultimo_resultado
    assert resultado.caminho_relatorio.parent == saida
    assert tela.resultado.estado == "concluido"
    assert tela.resultado.selo.cget("text") == "Concluído"
    assert resultado.cnpj_unidade == "98765432000198"
    assert set(tela.botoes_resultado) == {"Abrir relatório", "Abrir pasta", "Novo"}
    tela.botoes_resultado["Abrir relatório"].invoke()
    assert tela.abertos == [resultado.caminho_relatorio]

    # as pastas ficam guardadas para a próxima vez
    assert processamento.ler_pastas_usadas() == {"lote": lote.parent, "pdfs": pdfs, "saida": saida}
    assert tela.cartao_pdfs.pasta_inicial == pdfs

    tela.botoes_resultado["Novo"].invoke()
    assert tela.resultado.estado == "vazio" and tela.ultimo_resultado is None
    assert not tela.cartao_lote.preenchido and not tela.cartao_pdfs.preenchido
    assert tela.cartao_saida.preenchido                     # a pasta de saída fica
    assert tela.campo_unidade.valor() == UNIDADE_PRINCIPAL             # a unidade também


def test_unidade_errada_fica_vermelha_pela_tela(tela, tmp_path):
    """S15: as 2 notas do lote pequeno são da Fundação (0001-89); conferindo como AME Cidade Alfa,
    as duas ficam DIVERGENTE e a tela avisa."""
    lote, pdfs = _lote_pequeno(tmp_path)
    tela.campo_unidade.definir("AME Cidade Alfa (98.765.432/0004-30)")
    for cartao, caminho in ((tela.cartao_lote, lote), (tela.cartao_pdfs, pdfs),
                            (tela.cartao_saida, tmp_path)):
        cartao.definir_caminhos(caminho)
    tela.processar()
    esperar(tela, lambda: not tela.ocupado)
    casados = [r for r in tela.ultimo_resultado.resultados if r.nota]
    assert len(casados) == 2
    assert all(r.confere_destinatario == "ERRADO" and r.situacao.value == "DIVERGENTE"
               for r in casados)
    textos = [l.texto for l in processamento.resumir(tela.ultimo_resultado).conferencias]
    assert "Notas com CNPJ diferente do da unidade AME Cidade Alfa" in textos
    assert processamento.ler_unidade_usada() == "98765432000430"


def test_tela_nova_abre_com_a_ultima_unidade(criar_painel, tmp_path):
    processamento.salvar_pastas_usadas(cnpj_unidade="98765432001160")
    processamento.salvar_pastas_usadas(tmp_path / "lotes" / "x.csv")    # não apaga a unidade
    tela = criar_painel(MODULO).conferencia
    assert tela.campo_unidade.valor() == "AME Cidade Delta (98.765.432/0011-60)"
    assert tela.cnpj_unidade == "98765432001160"


def test_tela_nova_abre_os_seletores_nas_ultimas_pastas(criar_painel, tmp_path):
    processamento.salvar_pastas_usadas(tmp_path / "lotes" / "x.csv", tmp_path / "pdfs",
                                       tmp_path / "saida")
    tela = criar_painel(MODULO).conferencia
    assert tela.cartao_lote.pasta_inicial == tmp_path / "lotes"
    assert tela.cartao_pdfs.pasta_inicial == tmp_path / "pdfs"
    assert tela.cartao_saida.pasta_inicial == tmp_path / "saida"


def test_relatorio_que_nao_pode_ser_gravado_mostra_o_erro(tela, tmp_path):
    lote = tmp_path / "lote.csv"
    lote.write_text("x", encoding="utf-8")
    arquivo_no_lugar_da_pasta = tmp_path / "saida"
    arquivo_no_lugar_da_pasta.write_text("")
    for cartao, caminho in ((tela.cartao_lote, lote), (tela.cartao_pdfs, tmp_path),
                            (tela.cartao_saida, arquivo_no_lugar_da_pasta)):
        cartao.definir_caminhos(caminho, avisar=False)
    tela.campo_unidade.definir(UNIDADE_PRINCIPAL)
    tela.atualizar_botoes()
    tela.processar()
    esperar(tela, lambda: not tela.ocupado)
    assert tela.resultado.selo.cget("text") == "Erro"
    assert processamento.ler_pastas_usadas() == {}           # nada guardado


# ---------------------------------------------------------------------------
# O que a tela mostra (sem janela)
# ---------------------------------------------------------------------------

def _resultado_montado(tmp_path):
    from testes.conferencia_nf.test_conferencia import _compra, _nota
    from modulos.conferencia_nf.conferencia import conferir

    notas = [_nota(valor="19.80"), _nota("2"), _nota("3", arquivo="sobra.pdf")]
    repetida = _nota("4", arquivo="copia.pdf")
    repetida.repetida_de = "orig.pdf"
    resultado = processamento.ResultadoConferencia(tmp_path / "lote.csv", tmp_path, tmp_path)
    resultado.notas = notas + [repetida]
    resultado.resultados = conferir([_compra("1"), _compra("2", nf="2"), _compra("3", nf="99")],
                                    resultado.notas, [])
    return resultado


def test_resumir(tmp_path):
    resultado = _resultado_montado(tmp_path)
    resumo = processamento.resumir(resultado)
    assert resumo.numeros == [
        (1, "conferidos pelo programa: só olhar as contas", "ok"),
        (2, "conferir com a nota impressa", "atencao"),
        (1, "PDFs sem lançamento neste lote", "principal")]
    assert resumo.motivos == [("PDF não bate com o lançamento", 1),
                              ("Lançamento e estorno que se anulam", 0),
                              ("Retenção da nota não bate com o lançamento", 0),
                              ("Casou com o PDF, mas tem observação", 0),
                              ("PDF da nota não veio", 1),
                              ("Não é nota fiscal (recibo, doação, taxa...)", 0)]
    textos = [(l.texto, l.status, l.valor) for l in resumo.conferencias]
    assert textos == [
        ("Todos os 4 PDFs foram lidos", "ok", None),
        ("PDFs repetidos (mesma nota em duas pastas): o segundo é ignorado", "atencao", "1"),
        ("Partidas x contrapartidas fecham em todos os fatos", "ok", None)]
    assert resumo.selo == ("Concluído com alertas", "atencao")      # há um divergente
    assert resumo.erro == ""


def _pasta_de_outro_dia(tmp_path, casam: int, sobram: int):
    """Lote com 1 fato por PDF que casa; os PDFs que sobram são de números que o lote não tem."""
    from testes.conferencia_nf.test_conferencia import _compra, _nota
    from modulos.conferencia_nf.conferencia import conferir

    resultado = processamento.ResultadoConferencia(tmp_path / "lote.csv", tmp_path, tmp_path)
    resultado.notas = ([_nota(str(n), arquivo=f"{n}.pdf") for n in range(1, casam + 1)]
                       + [_nota(str(900 + n), arquivo=f"outro-{n}.pdf") for n in range(sobram)])
    resultado.resultados = conferir([_compra(str(n), nf=str(n)) for n in range(1, casam + 1)]
                                    + [_compra("50", nf="50")], resultado.notas, [])
    return resultado


def test_s17_pasta_de_outro_dia_fica_vermelha(tmp_path):
    """13/10/2026: o lote do dia 13 conferido com os PDFs do dia 05 (0 de 78 casaram)."""
    resumo = processamento.resumir(_pasta_de_outro_dia(tmp_path, casam=0, sobram=3))
    assert (resumo.conferencias[0].texto, resumo.conferencias[0].status) == (
        "A pasta dos PDFs parece ser de outro dia: só 0 de 3 PDFs casaram com o lote. Confira a "
        "pasta escolhida.", "erro")
    assert resumo.selo == ("Confira a pasta dos PDFs", "erro")
    resumo = processamento.resumir(_pasta_de_outro_dia(tmp_path, casam=1, sobram=4))    # 20%
    assert "só 1 de 5 PDFs" in resumo.conferencias[0].texto


def test_s17_um_quarto_ou_mais_dos_pdfs_casados_nao_avisa(tmp_path):
    """O lote 72648 tinha PDFs de outros dias na pasta: 76 de 178 (43%) casaram, sem erro."""
    resumo = processamento.resumir(_pasta_de_outro_dia(tmp_path, casam=1, sobram=3))    # 25%
    assert not any("outro dia" in l.texto for l in resumo.conferencias)
    assert resumo.selo[1] != "erro"
    resumo = processamento.resumir(_pasta_de_outro_dia(tmp_path, casam=0, sobram=0))   # sem PDFs
    assert not any("outro dia" in l.texto for l in resumo.conferencias)


def test_s17_pasta_de_outro_dia_no_resumo_da_planilha(tmp_path):
    import openpyxl

    from modulos.conferencia_nf.relatorio import gerar_relatorio

    for casam, aviso in ((0, True), (1, False)):
        r = _pasta_de_outro_dia(tmp_path, casam=casam, sobram=2)
        caminho = gerar_relatorio(tmp_path / f"r{casam}.xlsx", r.resultados, r.notas, [], [], [],
                                  ["lote.csv"])
        aba = openpyxl.load_workbook(caminho)["Resumo"]
        if aviso:
            assert aba["A4"].value == "ATENÇÃO: pasta dos PDFs"
            assert aba["B4"].value.startswith("A pasta dos PDFs parece ser de outro dia: só 0 de 2")
            assert aba["A4"].fill.fgColor.rgb.endswith("FFC7CE")
        else:
            assert aba["A4"].value is None and aba["B4"].value is None
        assert aba["A5"].value == "Fatos contábeis no lote"       # as outras linhas não mudam


def test_resumir_com_erros_de_leitura_e_partidas(tmp_path):
    from testes.conferencia_nf.test_conferencia import _fato, _lanc, ESTOQUE

    resultado = processamento.ResultadoConferencia(tmp_path / "lote.csv", tmp_path, tmp_path)
    resultado.falhas_lote = [FalhaLeitura("lote.csv", "Não foi possível ler o lote: x")]
    resultado.falhas_pdf = [FalhaLeitura("a.pdf", "x"), FalhaLeitura("b.pdf", "y")]
    from modulos.conferencia_nf.conferencia import conferir
    resultado.resultados = conferir([_fato("1", _lanc("D", ESTOQUE, "10.00", "A NF. 1 DT01/01/2026"))],
                                    [], [])
    textos = [(l.texto, l.status, l.valor) for l in processamento.resumir(resultado).conferencias]
    assert textos == [
        ("Não foi possível ler o lote: x", "erro", None),
        ("2 PDFs com erro de leitura (aba \"Erros de leitura\")", "erro", None),
        ("Fatos com partidas e contrapartidas que não fecham", "erro", "1")]


def test_confirmacoes_sem_janela(tmp_path):
    vazio = tmp_path / "vazio.csv"
    vazio.write_bytes(b"")
    assert processamento.confirmar_lote(vazio) == ("Não é o lote esperado: Arquivo vazio.", "erro")
    (tmp_path / "x.pdf").write_bytes(b"")
    assert processamento.confirmar_pasta_pdfs(tmp_path) == ("1 PDF (com as subpastas)", "ok")


def test_pastas_usadas_com_arquivo_estragado(tmp_path):
    caminho = processamento.caminho_pastas_usadas()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("{estragado", encoding="utf-8")
    assert processamento.ler_pastas_usadas() == {}
    caminho.write_text('{"lote": "C:/x", "outra": "y", "pdfs": 3}', encoding="utf-8")
    assert {k: str(v) for k, v in processamento.ler_pastas_usadas().items()} == {"lote": "C:\\x"}
