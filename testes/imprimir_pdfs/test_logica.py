"""
Testes do Imprimir PDFs (ESPECIFICACAO_IMPRIMIR_PDFS.md), copiados do Conciliações AMES
(tests/test_impressao.py). Mudaram só os import, o nome do trabalho na fila ("Central de Conciliações",
aprovado pelo usuário em 20/10/2026) e o usuário da fila nos exemplos (fictício).

- PDFs montados no próprio teste (pypdfium2), sem arquivo real.
- A impressão usa um dispositivo falso, que só anota as folhas; um teste imprime de verdade na
  "Microsoft Print to PDF" gravando num arquivo (sem papel) e é pulado se ela não existir.
"""

import faulthandler
import re
import sys
import time
from pathlib import Path

import pytest

from modulos.imprimir_pdfs.processamento import (
    ErroDeImpressao,
    PdfParaImprimir,
    imprimir,
    ler_pdf,
    ler_pdfs,
    listar_impressoras,
    nome_do_trabalho,
    ordenar_como_no_windows,
    pdfs_da_pasta,
    resumo,
    total_de_folhas,
)
from modulos.imprimir_pdfs.impressora import AreaDaFolha, posicao_na_folha

A4 = (595, 842)                    # em pontos (1/72 de polegada)
A4_DEITADA = (842, 595)


def criar_pdf(caminho: Path, *tamanhos) -> Path:
    import pypdfium2

    documento = pypdfium2.PdfDocument.new()
    for largura, altura in tamanhos:
        documento.new_page(largura, altura)
    documento.save(str(caminho))
    documento.close()
    return caminho


class DispositivoFalso:
    """Anota o que seria mandado para a impressora."""

    def __init__(self, falhar_na_folha: int | None = None):
        self.nome = None
        self.folhas = []                 # (paisagem, x, y, largura, altura)
        self.terminou = self.cancelou = False
        self._falhar_na_folha = falhar_na_folha

    def iniciar(self, nome):
        self.nome = nome

    def nova_folha(self, paisagem):
        if self._falhar_na_folha == len(self.folhas) + 1:
            raise ErroDeImpressao("A impressora parou de responder no meio da impressão.")
        self._paisagem = paisagem
        return AreaDaFolha(4760, 6779, 600, 600) if not paisagem else AreaDaFolha(6779, 4760, 600, 600)

    def desenhar(self, pagina, x, y, largura, altura, opcoes):
        self.folhas.append((self._paisagem, x, y, largura, altura))

    def fechar_folha(self):
        pass

    def terminar(self):
        self.terminou = True

    def cancelar(self):
        self.cancelou = True


@pytest.fixture
def pasta_pdfs(tmp_path):
    criar_pdf(tmp_path / "12206.pdf", A4)
    criar_pdf(tmp_path / "1546.pdf", A4)
    criar_pdf(tmp_path / "Relatorio 13.10.pdf", A4, A4_DEITADA)
    criar_pdf(tmp_path / "Titulos Exemplo 13.10.pdf", A4)
    (tmp_path / "anotacoes.txt").write_text("não é PDF", encoding="utf-8")
    return tmp_path


# --- lista e contagem --------------------------------------------------------------------------

def test_ordem_igual_ao_explorador_do_windows():
    nomes = ["12206.pdf", "1546.pdf", "8102026.pdf", "157177.pdf", "Saerp 09.2026.pdf", "5078.pdf",
             "Relatorio 13.10.pdf", "Titulos b 13.10.pdf", "Titulos A 13.10.pdf"]
    assert [p.name for p in ordenar_como_no_windows(nomes)] == [
        "1546.pdf", "5078.pdf", "12206.pdf", "157177.pdf", "8102026.pdf",
        "Relatorio 13.10.pdf", "Saerp 09.2026.pdf", "Titulos A 13.10.pdf", "Titulos b 13.10.pdf"]


def test_pasta_conta_folhas_e_ignora_o_que_nao_e_pdf(pasta_pdfs):
    pdfs = pdfs_da_pasta(pasta_pdfs)
    assert [(p.nome, p.paginas) for p in pdfs] == [
        ("1546.pdf", 1), ("12206.pdf", 1), ("Relatorio 13.10.pdf", 2), ("Titulos Exemplo 13.10.pdf", 1)]
    assert total_de_folhas(pdfs) == 5
    assert resumo(pdfs) == "4 PDFs · 5 folhas"


def test_pdf_danificado_fica_com_erro_e_fora_da_conta(pasta_pdfs):
    ruim = pasta_pdfs / "danificado.pdf"
    ruim.write_bytes(b"%PDF-1.4 isto nao e um pdf de verdade")
    pdfs = ler_pdfs([pasta_pdfs / "1546.pdf", ruim, pasta_pdfs / "sumiu.pdf"])
    por_nome = {p.nome: p for p in pdfs}
    assert por_nome["1546.pdf"].pode_imprimir
    assert not por_nome["danificado.pdf"].pode_imprimir
    assert "danificado" in por_nome["danificado.pdf"].erro
    assert por_nome["sumiu.pdf"].erro == "arquivo não encontrado"
    assert total_de_folhas(pdfs) == 1
    assert resumo(pdfs) == "1 PDF · 1 folha · 2 com problema"


def test_mesmo_arquivo_escolhido_duas_vezes_entra_uma_vez(pasta_pdfs):
    arquivo = pasta_pdfs / "1546.pdf"
    assert len(ler_pdfs([arquivo, Path(str(arquivo).upper())])) == 1


# --- impressão (dispositivo falso) -------------------------------------------------------------

def test_tudo_numa_impressao_so_na_ordem_da_lista(pasta_pdfs):
    pdfs = pdfs_da_pasta(pasta_pdfs)
    falso, andamento = DispositivoFalso(), []
    envio = imprimir(pdfs, "Impressora X", dispositivo=falso, ao_avancar=lambda f, t: andamento.append((f, t)))
    assert envio.folhas == 5
    assert re.fullmatch(r"Central de Conciliações – 4 PDFs \(5 folhas\) – \d\d:\d\d:\d\d", falso.nome)
    assert envio.nome_trabalho == falso.nome                       # o nome com o horário: é por ele que a fila é lida
    assert falso.terminou and not falso.cancelou
    assert [f[0] for f in falso.folhas] == [False, False, False, True, False]   # a página deitada em paisagem
    assert andamento == [(1, 5), (2, 5), (3, 5), (4, 5), (5, 5)]


def test_pdf_com_problema_nao_e_impresso(pasta_pdfs):
    pdfs = [ler_pdf(pasta_pdfs / "1546.pdf"), PdfParaImprimir(pasta_pdfs / "x.pdf", erro="arquivo não encontrado")]
    falso = DispositivoFalso()
    assert imprimir(pdfs, "Impressora X", dispositivo=falso).folhas == 1
    assert falso.nome.startswith("Central de Conciliações – 1 PDF (1 folha) – ")


def test_sem_pdf_valido_nao_manda_nada():
    with pytest.raises(ErroDeImpressao, match="Nenhum PDF"):
        imprimir([PdfParaImprimir(Path("x.pdf"), erro="arquivo não encontrado")], "X", dispositivo=DispositivoFalso())


def test_erro_no_meio_cancela_a_impressao(pasta_pdfs):
    falso = DispositivoFalso(falhar_na_folha=3)
    with pytest.raises(ErroDeImpressao, match="parou de responder"):
        imprimir(pdfs_da_pasta(pasta_pdfs), "Impressora X", dispositivo=falso)
    assert falso.cancelou and not falso.terminou


def test_pdf_apagado_depois_da_lista_nao_manda_nada(pasta_pdfs):
    pdfs = pdfs_da_pasta(pasta_pdfs)
    (pasta_pdfs / "Titulos Exemplo 13.10.pdf").unlink()
    falso = DispositivoFalso()
    with pytest.raises(ErroDeImpressao, match="Titulos Exemplo"):
        imprimir(pdfs, "Impressora X", dispositivo=falso)
    assert falso.nome is None                      # nada foi para a fila


def test_pagina_em_tamanho_real_centralizada():
    area = AreaDaFolha(4760, 6779, 600, 600)       # A4 a 600 dpi, sem as margens da impressora
    x, y, largura, altura = posicao_na_folha(*A4, area)
    assert (largura, altura) == (4760, 6736)       # reduzida só o necessário para caber na largura
    assert x == 0 and y == (6779 - 6736) // 2


def test_pagina_pequena_nao_e_ampliada():
    x, y, largura, altura = posicao_na_folha(288, 144, AreaDaFolha(4760, 6779, 600, 600))   # 4 × 2 polegadas
    assert (largura, altura) == (2400, 1200)
    assert (x, y) == ((4760 - 2400) // 2, (6779 - 1200) // 2)


def test_nome_do_trabalho():
    pdfs = [PdfParaImprimir(Path("a.pdf"), 2), PdfParaImprimir(Path("b.pdf"), 1)]
    assert nome_do_trabalho(pdfs) == "Central de Conciliações – 2 PDFs (3 folhas)"


# --- impressão de verdade, num arquivo ---------------------------------------------------------

IMPRESSORA_PDF = "Microsoft Print to PDF"


@pytest.mark.skipif(sys.platform != "win32", reason="só no Windows")
def test_imprime_de_verdade_na_microsoft_print_to_pdf(pasta_pdfs, tmp_path):
    import pypdfium2

    if IMPRESSORA_PDF not in listar_impressoras():
        pytest.skip("Microsoft Print to PDF não instalada")
    saida = tmp_path / "saida" / "impresso.pdf"
    saida.parent.mkdir()
    # o driver da Microsoft Print to PDF levanta e trata sozinho um erro interno (COM), que o
    # faulthandler do pytest mostraria como "Windows fatal exception" sem ser falha
    ligado = faulthandler.is_enabled()
    faulthandler.disable()
    try:
        assert imprimir(pdfs_da_pasta(pasta_pdfs), IMPRESSORA_PDF, arquivo_saida=saida).folhas == 5
    finally:
        if ligado:
            faulthandler.enable()
    for _ in range(50):                            # o spooler grava o arquivo logo depois
        if saida.exists() and saida.stat().st_size:
            break
        time.sleep(0.2)
    documento = pypdfium2.PdfDocument(str(saida))
    try:
        tamanhos = [documento[i].get_size() for i in range(len(documento))]
    finally:
        documento.close()
    assert len(tamanhos) == 5
    deitadas = [largura > altura for largura, altura in tamanhos]
    assert deitadas == [False, False, False, True, False]


def test_impressora_inexistente(pasta_pdfs):
    if sys.platform != "win32":
        pytest.skip("só no Windows")
    with pytest.raises(ErroDeImpressao, match="não encontrada|Não foi possível usar"):
        imprimir(pdfs_da_pasta(pasta_pdfs), "Impressora Que Nao Existe 123")


# --- só algumas páginas de um PDF (pedido do usuário, out/2026) ---------------------------------

def test_paginas_escolhidas_contam_so_elas(tmp_path):
    from dataclasses import replace

    pdf = ler_pdf(criar_pdf(tmp_path / "17273.pdf", A4, A4, A4))
    assert pdf.folhas == 3 and pdf.paginas_para_imprimir() == [1, 2, 3]
    so_a_primeira = replace(pdf, escolhidas=(1,))
    assert so_a_primeira.folhas == 1
    assert replace(pdf, escolhidas=(3, 1, 3)).paginas_para_imprimir() == [1, 3]
    assert total_de_folhas([so_a_primeira, ler_pdf(criar_pdf(tmp_path / "1546.pdf", A4))]) == 2


def test_imprime_so_as_paginas_escolhidas_na_ordem(tmp_path):
    from dataclasses import replace

    tres = ler_pdf(criar_pdf(tmp_path / "a.pdf", A4, A4_DEITADA, A4))
    um = ler_pdf(criar_pdf(tmp_path / "b.pdf", A4))
    falso = DispositivoFalso()
    assert imprimir([replace(tres, escolhidas=(3, 2)), um], "Impressora X", dispositivo=falso).folhas == 3
    assert falso.nome.startswith("Central de Conciliações – 2 PDFs (3 folhas) – ")
    assert [f[0] for f in falso.folhas] == [True, False, False]       # pág. 2 (deitada), pág. 3, depois o b.pdf


def test_pdf_sem_nenhuma_pagina_escolhida_nao_entra(tmp_path):
    from dataclasses import replace

    tres = ler_pdf(criar_pdf(tmp_path / "a.pdf", A4, A4))
    um = ler_pdf(criar_pdf(tmp_path / "b.pdf", A4))
    falso = DispositivoFalso()
    assert imprimir([replace(tres, escolhidas=()), um], "Impressora X", dispositivo=falso).folhas == 1
    assert falso.nome.startswith("Central de Conciliações – 1 PDF (1 folha) – ")


def test_pagina_escolhida_que_sumiu_do_arquivo_nao_manda_nada(tmp_path):
    from dataclasses import replace

    caminho = criar_pdf(tmp_path / "a.pdf", A4, A4, A4)
    pdf = replace(ler_pdf(caminho), escolhidas=(3,))
    criar_pdf(caminho, A4)                                           # o arquivo foi trocado por um de 1 página
    falso = DispositivoFalso()
    with pytest.raises(ErroDeImpressao, match="mudou depois de escolhido"):
        imprimir([pdf], "Impressora X", dispositivo=falso)
    assert falso.nome is None


# --- fila da impressora (pedido do usuário, out/2026: trabalho parado como "Pausado" e a impressora "aguardando") ---

from modulos.imprimir_pdfs.fila import (  # noqa: E402
    ERRO,
    IMPRIMINDO,
    NO_SPOOL,
    PAUSADO,
    SEM_PAPEL,
    TrabalhoNaFila,
    acompanhar,
    interpretar,
    procurar,
)

NOME = "Central de Conciliações – 2 PDFs (3 folhas) – 10:42:05"


@pytest.fixture(autouse=True)
def usuario_do_windows_ficticio(monkeypatch):
    """O acompanhamento acha o trabalho pelo usuário do Windows de quem imprime. Os testes de lá usavam o
    login real do usuário e só passavam no computador dele: aqui o usuário atual é simulado."""
    import modulos.imprimir_pdfs.fila as fila

    monkeypatch.setattr(fila, "usuario_atual", lambda: "usuario.teste")


def trabalho(status=0, posicao=1, **outros):
    return TrabalhoNaFila(documento=NOME, usuario="usuario.teste", status=status, posicao=posicao, **outros)


def test_pausado_no_spool_e_problema():
    """O caso visto na fila do servidor: "Pausado, Colocando no spool", 0 bytes."""
    estado = interpretar(trabalho(PAUSADO | NO_SPOOL), ja_visto=True)
    assert estado.nivel == "erro" and "PAUSADA" in estado.texto and "Continuar" in estado.texto
    assert "limite de impressões da sua conta (cota)" in estado.texto   # a causa achada pelo usuário
    assert not estado.final                                         # a pessoa pode clicar em Continuar


def test_estados_da_fila():
    assert "SEM PAPEL" in interpretar(trabalho(SEM_PAPEL), True).texto
    assert interpretar(trabalho(ERRO), True).nivel == "erro"
    imprimindo = interpretar(trabalho(IMPRIMINDO, paginas=3, paginas_impressas=1), True)
    assert imprimindo.nivel == "ok" and "página 1 de 3" in imprimindo.texto
    vez = interpretar(trabalho(0, posicao=3), True)
    assert vez.nivel == "atencao" and "2 impressão(ões) na frente" in vez.texto
    assert interpretar(None, ja_visto=True).final                  # saiu da fila: foi para a impressora
    assert not interpretar(None, ja_visto=False).final              # ainda pode estar chegando no servidor


def test_procura_pelo_nome_e_pelo_usuario():
    fila = [TrabalhoNaFila(NOME, "outra.pessoa"), trabalho(NO_SPOOL), TrabalhoNaFila("Planilha.xlsx", "usuario.teste")]
    assert procurar(fila, NOME, "Usuario.Teste").status == NO_SPOOL
    assert procurar(fila, NOME, "ninguem") is None


def test_acompanha_ate_sair_da_fila():
    respostas = iter([[], [trabalho(NO_SPOOL)], [trabalho(PAUSADO)], [trabalho(PAUSADO)], [trabalho(IMPRIMINDO)], []])
    vistos = []
    final = acompanhar(NOME, lambda: next(respostas), vistos.append, espera=lambda s: None)
    assert final.final and final.nivel == "ok"
    textos = [e.texto for e in vistos]
    assert len(textos) == 5                                         # o "pausado" repetido aparece uma vez só
    assert "Procurando" in textos[0] and "PAUSADA" in textos[2] and "Saiu da fila" in textos[-1]


def test_acompanhamento_tem_limite_e_avisa_quem_continua_pausado():
    vistos = []
    final = acompanhar(NOME, lambda: [trabalho(PAUSADO)], vistos.append, intervalo=10, limite=60,
                       espera=lambda s: None)
    assert final.final and final.nivel == "erro" and "continua na fila" in final.texto


def test_impressao_que_nunca_aparece_na_fila():
    final = acompanhar(NOME, lambda: [], lambda e: None, intervalo=2, espera=lambda s: None)
    assert final.final and final.nivel == "ok" and "já não está na fila" in final.texto


def test_erro_ao_ler_a_fila_vira_aviso():
    def falha():
        raise ErroDeImpressao("servidor fora do ar")
    final = acompanhar(NOME, falha, lambda e: None, espera=lambda s: None)
    assert final.final and final.nivel == "atencao" and "servidor fora do ar" in final.texto


@pytest.mark.skipif(sys.platform != "win32", reason="só no Windows")
def test_le_a_fila_de_verdade():
    from modulos.imprimir_pdfs.processamento import listar_trabalhos

    if IMPRESSORA_PDF not in listar_impressoras():
        pytest.skip("Microsoft Print to PDF não instalada")
    assert isinstance(listar_trabalhos(IMPRESSORA_PDF), list)
    with pytest.raises(ErroDeImpressao):
        listar_trabalhos("Impressora Que Nao Existe 123")


# --- gabarito com a pasta de exemplo (fora do git; ESPECIFICACAO_IMPRIMIR_PDFS.md, seção 4) -----------

def test_gabarito_pasta_de_exemplo():
    from testes.conftest import pasta_exemplos

    pdfs = pdfs_da_pasta(pasta_exemplos("imprimir_pdfs", "PDF's_imprimir"))
    assert resumo(pdfs) == "16 PDFs · 18 folhas"
    assert [p.nome for p in pdfs if p.paginas == 2] == ["17273.pdf", "Relatorio 13.10.pdf"]
