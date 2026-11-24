"""Imprimir PDFs na janela de verdade (era test_painel_impressao_paginas_cabem_na_janela_minima do
Conciliações AMES). Fica num arquivo só dele: a janela do programa não pode ser aberta junto com a janela
escondida que os outros testes da tela usam (testes/conftest.py)."""

from __future__ import annotations

import pytest

from central import tema


@pytest.fixture(autouse=True)
def appdata_temporario(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))


def _criar_pdf(caminho, paginas):
    import pypdfium2

    documento = pypdfium2.PdfDocument.new()
    for _ in range(paginas):
        documento.new_page(595, 842)
    documento.save(str(caminho))
    documento.close()


def test_paginas_cabem_na_janela_minima(tmp_path):
    """PDF de 15 páginas: nenhuma caixinha de página sai da linha, na janela mínima e na grande."""
    from central.janela import JanelaCentral

    pasta = tmp_path / "pdfs"
    pasta.mkdir()
    _criar_pdf(pasta / "Relatorio 15 paginas.pdf", 15)
    try:
        janela = JanelaCentral(caminho_preferencias=tmp_path / "pref.json", chave_inicial="imprimir_pdfs")
    except Exception as erro:  # sem tela disponível (ex.: servidor)
        pytest.skip(f"não deu para abrir a janela: {erro}")
    try:
        tela = janela.paineis["imprimir_pdfs"].imprimir
        tela.definir_pasta(pasta)
        linha = tela.linhas[0]
        por_linha = {}
        for tamanho in (f"{tema.LARGURA_MINIMA_JANELA}x{tema.ALTURA_MINIMA_JANELA}", "1600x900"):
            janela.geometry(tamanho)
            for _ in range(10):
                janela.update()
            limite = linha.winfo_rootx() + linha.winfo_width()
            assert all(c.winfo_ismapped() and c.winfo_rootx() + c.winfo_width() <= limite
                       for c in linha.caixas_paginas), tamanho
            por_linha[tamanho] = linha.paginas_por_linha
        assert len(set(por_linha.values())) == 2                    # na grande cabem mais por linha
    finally:
        janela.destroy()
