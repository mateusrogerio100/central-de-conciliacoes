"""Tela do módulo Imprimir PDFs (montada sem mostrar a janela).

Refeitos a partir dos testes da tela antiga (test_interface_apoio.py do Conciliações AMES:
test_painel_impressao_conta_folhas_e_imprime_tudo_junto, test_config_lembra_impressora_e_pasta_dos_pdfs,
test_painel_impressao_escolhe_paginas_de_um_pdf; o da janela mínima está em test_janela_minima.py), com
as mesmas verificações, mais as regras da Central. Nenhum teste usa papel: a impressão e a fila são trocadas
por versões falsas. Todos usam um %APPDATA% temporário.
"""

from __future__ import annotations

import ast
import json
from functools import partial

import pytest

from central import registro
from modulos.imprimir_pdfs import MODULO, processamento
from modulos.imprimir_pdfs.fila import PAUSADO, TrabalhoNaFila
from modulos.imprimir_pdfs.telas import imprimir as tela_imprimir
from testes.conftest import RAIZ, esperar

PASTA_MODULO = RAIZ / "modulos" / "imprimir_pdfs"


@pytest.fixture(autouse=True)
def appdata_temporario(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))


@pytest.fixture
def tela(criar_painel):
    return criar_painel(MODULO).imprimir


def _criar_pdf(caminho, paginas):
    import pypdfium2

    documento = pypdfium2.PdfDocument.new()
    for _ in range(paginas):
        documento.new_page(595, 842)
    documento.save(str(caminho))
    documento.close()


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


# ---------------------------------------------------------------------------
# Módulo e arquitetura
# ---------------------------------------------------------------------------


def test_modulo_no_registro_na_secao_ferramentas():
    assert registro.SECAO_DO_MODULO["imprimir_pdfs"] == "FERRAMENTAS"
    carregado = next(m for m in registro.carregar_modulos() if m.chave == "imprimir_pdfs")
    assert carregado.ok and carregado.info.nome == "Imprimir PDFs"
    assert (RAIZ / "central" / "icones" / f"{carregado.info.icone}.png").exists()
    assert (PASTA_MODULO / "INSTRUCOES_DE_USO.md").exists()


def test_tela_so_usa_o_processamento():
    arvore = ast.parse((PASTA_MODULO / "telas" / "imprimir.py").read_text(encoding="utf-8"))
    do_modulo = {no.module for no in ast.walk(arvore) if isinstance(no, ast.ImportFrom)
                 and no.module and no.module.startswith("modulos.")}
    assert do_modulo == {"modulos.imprimir_pdfs", "modulos.imprimir_pdfs.processamento"}


def test_modulo_nao_importa_outro_modulo():
    for arquivo in PASTA_MODULO.rglob("*.py"):
        for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
            if isinstance(no, ast.ImportFrom) and no.module and no.module.startswith("modulos."):
                assert no.module.startswith("modulos.imprimir_pdfs"), (arquivo.name, no.module)


# ---------------------------------------------------------------------------
# Pasta e impressora lembradas (era test_config_lembra_impressora_e_pasta_dos_pdfs)
# ---------------------------------------------------------------------------


def test_pasta_e_impressora_lembradas(tmp_path):
    assert processamento.ler_pasta_lembrada(tmp_path) == "" and processamento.ler_impressora_lembrada(tmp_path) == ""
    assert processamento.salvar_pasta_lembrada("C:/pdfs", tmp_path)
    assert processamento.salvar_impressora_lembrada("Impressora X", tmp_path)
    assert (processamento.ler_pasta_lembrada(tmp_path), processamento.ler_impressora_lembrada(tmp_path)) == \
        ("C:/pdfs", "Impressora X")


def test_vem_do_conciliacoes_ames_so_enquanto_a_central_nao_guardou(tmp_path):
    antigo = tmp_path / "config.json"
    antigo.write_text(json.dumps({"pasta_pdfs": "C:/pdfs", "impressora": "Impressora X"}), encoding="utf-8")
    central = tmp_path / "central"
    assert processamento.ler_pasta_lembrada(central, antigo) == "C:/pdfs"
    assert processamento.ler_impressora_lembrada(central, antigo) == "Impressora X"
    processamento.salvar_impressora_lembrada("Impressora Y", central)
    assert processamento.ler_impressora_lembrada(central, antigo) == "Impressora Y"
    assert processamento.ler_pasta_lembrada(central, antigo) == "C:/pdfs"


def test_tela_abre_na_pasta_e_na_impressora_lembradas(criar_painel, tmp_path, monkeypatch):
    monkeypatch.setattr(processamento, "listar_impressoras", lambda: ["Impressora A", "Impressora B"])
    monkeypatch.setattr(processamento, "impressora_padrao", lambda: "Impressora A")
    assert criar_painel(MODULO).imprimir.impressora == "Impressora A"         # sem lembrança: a padrão
    processamento.salvar_impressora_lembrada("Impressora B")
    processamento.salvar_pasta_lembrada(str(tmp_path))
    tela = criar_painel(MODULO).imprimir
    esperar(tela, lambda: tela.pasta == str(tmp_path), 10)                # conferida em segundo plano
    assert tela.impressora == "Impressora B"
    processamento.salvar_impressora_lembrada("Impressora que saiu")         # não existe mais: a padrão
    assert criar_painel(MODULO).imprimir.impressora == "Impressora A"


def test_pasta_lembrada_num_servidor_fora_do_ar_nao_trava_a_abertura(criar_painel, monkeypatch):
    # o Windows leva ~21 s para dizer que \\servidor\pasta não existe; a tela abre sem esperar
    import time
    from pathlib import Path

    servidor = r"\\192.0.2.1\Arquivos\PDFs"
    original = Path.is_dir
    monkeypatch.setattr(Path, "is_dir", lambda p: time.sleep(3) or False if str(p) == servidor else original(p))
    processamento.salvar_pasta_lembrada(servidor)
    inicio = time.time()
    tela = criar_painel(MODULO).imprimir
    assert time.time() - inicio < 2.5
    assert tela.pasta == ""


# ---------------------------------------------------------------------------
# Conta as folhas e imprime tudo junto (era test_painel_impressao_conta_folhas_e_imprime_tudo_junto)
# ---------------------------------------------------------------------------


def test_conta_folhas_e_imprime_tudo_junto(tela, tmp_path, monkeypatch):
    pasta = tmp_path / "pdfs"
    pasta.mkdir()
    _criar_pdf(pasta / "12206.pdf", 1)
    _criar_pdf(pasta / "1546.pdf", 2)
    _criar_pdf(pasta / "Titulos Exemplo 13.10.pdf", 1)
    (pasta / "danificado.pdf").write_bytes(b"%PDF-1.4 quebrado")
    assert not tela.botao_imprimir.habilitado                       # nada escolhido ainda

    tela.definir_pasta(pasta)
    tela.update()
    assert [l.pdf.nome for l in tela.linhas] == ["1546.pdf", "12206.pdf", "danificado.pdf",
                                                  "Titulos Exemplo 13.10.pdf"]
    numeros = [b.rotulo_numero.cget("text") for b in tela.numeros.blocos]
    assert numeros == ["4", "3", "1"]                               # o danificado fica fora
    assert tela.numeros.blocos[1].rotulo_legenda.cget("text") == "PDFs marcados (de 3)"
    assert tela.botao_imprimir.cget("text") == "Imprimir 4 folhas"
    assert processamento.ler_pasta_lembrada() == str(pasta)

    tela.linhas[1].caixa.toggle()                                   # desmarca o 12206
    assert [b.rotulo_numero.cget("text") for b in tela.numeros.blocos][:2] == ["3", "2"]
    tela.marcar_todos(False)
    assert not tela.botao_imprimir.habilitado
    tela.marcar_todos(True)

    if not tela.impressoras:
        pytest.skip("nenhuma impressora neste computador")
    tela.campo_impressora.definir(tela.impressoras[-1])
    assert processamento.ler_impressora_lembrada() == tela.impressoras[-1]

    enviados = []

    def imprimir_falso(pdfs, impressora, ao_avancar=None, **_):
        enviados.append(([p.nome for p in pdfs], impressora))
        for folha in range(1, 5):
            ao_avancar(folha, 4)
        return processamento.Envio(4, "Central de Conciliações – 3 PDFs (4 folhas) – 10:42:05")

    monkeypatch.setattr(processamento, "imprimir", imprimir_falso)
    # a fila mostra o trabalho pausado (o caso visto no servidor da contabilidade); sem esperar de verdade
    pausado = TrabalhoNaFila("Central de Conciliações – 3 PDFs (4 folhas) – 10:42:05", "", status=PAUSADO)
    monkeypatch.setattr(processamento, "listar_trabalhos", lambda impressora: [pausado])
    monkeypatch.setattr(processamento, "acompanhar",
                        partial(processamento.acompanhar, espera=lambda s: None, limite=4))
    tela.iniciar_impressao(tela.marcados, tela.impressora)
    assert tela.ocupado and not tela.botao_imprimir.habilitado
    esperar(tela, lambda: not tela.ocupado, limite_segundos=10)
    assert enviados == [(["1546.pdf", "12206.pdf", "Titulos Exemplo 13.10.pdf"], tela.impressoras[-1])]
    esperar(tela, lambda: "continua na fila" in " ".join(_textos(tela.area_status)), limite_segundos=10)
    status = " ".join(_textos(tela.area_status))
    assert "4 folhas mandadas para" in status
    assert "continua na fila" in status and "PAUSADA" in status      # o acompanhamento avisa o problema
    assert tela.botao_fila.habilitado
    assert tela.botao_imprimir.habilitado                           # dá para imprimir de novo

    def imprimir_com_erro(*_, **__):
        raise processamento.ErroDeImpressao("A impressora parou de responder no meio da impressão.")

    monkeypatch.setattr(processamento, "imprimir", imprimir_com_erro)
    tela.iniciar_impressao(tela.marcados, tela.impressora)
    esperar(tela, lambda: not tela.ocupado, limite_segundos=10)
    assert "parou de responder" in " ".join(_textos(tela.area_status))

    tela.novo()
    assert not tela.linhas and tela.numeros.blocos[0].rotulo_numero.cget("text") == "0"
    assert tela_imprimir.TEXTO_SEM_PDFS in _textos(tela)


def test_imprimir_pede_confirmacao(tela, tmp_path, monkeypatch, dialogos):
    pasta = tmp_path / "pdfs"
    pasta.mkdir()
    _criar_pdf(pasta / "1546.pdf", 2)
    tela.definir_pasta(pasta)
    monkeypatch.setattr(tela.campo_impressora, "valor", lambda: "Impressora X")
    iniciadas = []
    monkeypatch.setattr(tela, "iniciar_impressao", lambda pdfs, impressora: iniciadas.append(impressora))
    dialogos.resposta = False
    tela.imprimir()
    assert iniciadas == [] and "Mandar 2 folhas (1 PDF) para a impressora" in dialogos.perguntas[0]
    assert "Confira se há pelo menos 2 folhas de papel" in dialogos.perguntas[0]
    dialogos.resposta = True
    tela.imprimir()
    assert iniciadas == ["Impressora X"]


def test_janela_pergunta_antes_de_fechar_no_meio_da_impressao(criar_painel):
    painel = criar_painel(MODULO)
    assert not painel.ocupado
    painel.imprimir.ocupado = True
    assert painel.ocupado                                           # a janela pergunta antes de fechar
    painel.imprimir.ocupado = False


# ---------------------------------------------------------------------------
# Só algumas páginas (era test_painel_impressao_escolhe_paginas_de_um_pdf)
# ---------------------------------------------------------------------------


def test_escolhe_paginas_de_um_pdf(tela, tmp_path, monkeypatch):
    pasta = tmp_path / "pdfs"
    pasta.mkdir()
    _criar_pdf(pasta / "1546.pdf", 3)
    _criar_pdf(pasta / "5078.pdf", 1)
    tela.definir_pasta(pasta)
    tres, um = tela.linhas
    assert [c.cget("text") for c in tres.caixas_paginas] == ["Pág. 1", "Pág. 2", "Pág. 3"]
    assert not um.caixas_paginas                                    # 1 página: sem caixinhas de página
    assert tres.rotulo_folhas.cget("text") == "3 folhas"
    assert tela.numeros.blocos[0].rotulo_numero.cget("text") == "4"

    tres.so_a_primeira()
    assert tres.rotulo_folhas.cget("text") == "1 de 3 folhas"
    assert tela.numeros.blocos[0].rotulo_numero.cget("text") == "2"
    assert tela.botao_imprimir.cget("text") == "Imprimir 2 folhas"
    assert tela.marcados[0].escolhidas == (1,) and tela.marcados[1].escolhidas is None

    tres.caixas_paginas[2].toggle()                                 # marca também a pág. 3
    assert tela.marcados[0].escolhidas == (1, 3)
    for caixa in tres.caixas_paginas:                               # desmarca todas: o arquivo sai
        if caixa.get():
            caixa.toggle()
    assert not tres.caixa.get() and [p.nome for p in tela.marcados] == ["5078.pdf"]
    tres.caixa.toggle()                                             # marcar o arquivo volta todas as páginas
    assert tres.paginas_marcadas == [1, 2, 3]
    assert tela.marcados[0].escolhidas is None

    tres.so_a_primeira()
    tela.marcar_todos(False)
    tela.marcar_todos(True)
    assert tres.paginas_marcadas == [1]                             # "Marcar todos" não mexe nas páginas
    enviados = []
    monkeypatch.setattr(processamento, "imprimir",
                        lambda pdfs, impressora, **_: enviados.append([(p.nome, p.escolhidas) for p in pdfs])
                        or processamento.Envio(2, "x"))
    monkeypatch.setattr(processamento, "acompanhar",
                        lambda *a, **k: processamento.EstadoNaFila("Saiu da fila.", "ok", True))
    tela.iniciar_impressao(tela.marcados, "Impressora X")
    assert all(c.cget("state") == "disabled" for c in tres.caixas_paginas)   # travado enquanto imprime
    esperar(tela, lambda: not tela.ocupado, limite_segundos=10)
    assert enviados == [[("1546.pdf", (1,)), ("5078.pdf", None)]]
    assert all(c.cget("state") == "normal" for c in tres.caixas_paginas)
