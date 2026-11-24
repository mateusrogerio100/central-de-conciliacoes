"""Testes dos ícones, do processamento em segundo plano e das regras visuais do GUIA_VISUAL."""

from __future__ import annotations

import re
import time

import customtkinter as ctk
import pytest
from PIL import Image

from central import gerar_icones, icones
from central.segundo_plano import TarefaEmSegundoPlano
from testes.conftest import RAIZ, abrir_janela_ctk


@pytest.fixture(scope="module")
def raiz():
    janela = abrir_janela_ctk()
    yield janela
    janela.destroy()


# ---------------------------------------------------------------------------
# Ícones
# ---------------------------------------------------------------------------


def _icones_usados_no_codigo() -> set[str]:
    """Nomes de ícones citados em central/ e modulos/ (icone="x", icone("x", ...), icone=x no InfoModulo)."""
    padroes = [r'icone\(\s*"([a-z_]+)"', r'icone\s*=\s*"([a-z_]+)"', r'"(?:icone)"\s*:\s*"([a-z_]+)"']
    nomes = set()
    for arquivo in list((RAIZ / "central").glob("*.py")) + list((RAIZ / "modulos").rglob("*.py")):
        texto = arquivo.read_text(encoding="utf-8")
        for padrao in padroes:
            nomes.update(re.findall(padrao, texto))
    nomes.update({"check", "alerta", "erro", "sol", "lua", "mais"})  # usados por variável
    return nomes


def test_todo_icone_usado_existe():
    faltando = sorted(n for n in _icones_usados_no_codigo() if not icones.existe(n))
    assert faltando == []


def test_icones_gravados_sao_os_do_gerador():
    gravados = {p.stem for p in icones.pasta_icones().glob("*.png")} - {"logo"}
    assert gravados == {f.__name__ for f in gerar_icones.ICONES}


def test_gerador_reproduz_os_icones(tmp_path):
    for caminho in gerar_icones.gerar_todos(tmp_path):
        with Image.open(caminho) as novo, Image.open(icones.pasta_icones() / caminho.name) as gravado:
            assert novo.size == gravado.size == (gerar_icones.TAMANHO_FINAL, gerar_icones.TAMANHO_FINAL)
            assert novo.getchannel("A").tobytes() == gravado.getchannel("A").tobytes(), caminho.name


def test_icone_pintado_nas_duas_cores(raiz):
    imagem = icones.icone("banco", ("#0f5c63", "#5bbab4"), 18)
    assert imagem.cget("size") == (18, 18)
    claro, escuro = imagem.cget("light_image"), imagem.cget("dark_image")
    pixel_claro = _primeiro_pixel_opaco(claro)
    pixel_escuro = _primeiro_pixel_opaco(escuro)
    assert pixel_claro[:3] == (0x0f, 0x5c, 0x63) and pixel_escuro[:3] == (0x5b, 0xba, 0xb4)


def _primeiro_pixel_opaco(imagem):
    largura, altura = imagem.size
    return next(p for y in range(altura) for x in range(largura) if (p := imagem.getpixel((x, y)))[3] == 255)


def test_icone_inexistente_nao_quebra(raiz):
    assert icones.icone("nao_existe", ("#000000", "#ffffff"), 18) is None


def test_logo_da_hospital_exemplo_no_menu(raiz):
    """A marca do menu é o símbolo do logo (central/gerar_icones.py, gerar_logo_e_icone)."""
    assert (icones.pasta_icones() / "logo.png").is_file()
    assert icones.logo(32) is not None


def test_sem_logo_usa_o_mais(raiz, monkeypatch, tmp_path):
    monkeypatch.setattr(icones, "pasta_icones", lambda: tmp_path)       # uma pasta sem logo.png
    assert icones.logo(32) is None


# ---------------------------------------------------------------------------
# Segundo plano
# ---------------------------------------------------------------------------


def _esperar(raiz, tarefa, limite=10):
    fim = time.time() + limite
    while tarefa.em_andamento and time.time() < fim:
        raiz.update()
        time.sleep(0.01)
    raiz.update()


def test_tarefa_informa_andamento_e_resultado(raiz):
    andamento, resultados = [], []

    def trabalho(progresso):
        progresso("Lendo...", 0.0)
        progresso("Gravando...", 0.5)
        return 42

    tarefa = TarefaEmSegundoPlano(raiz, trabalho, ao_progresso=lambda t, f: andamento.append((t, f)),
                                  ao_concluir=resultados.append).iniciar()
    _esperar(raiz, tarefa)

    # só o último andamento de cada leitura da fila é mostrado (ajuste de 05/11/2026): o último sempre aparece
    assert andamento[-1] == ("Gravando...", 0.5)
    assert all(a in [("Lendo...", 0.0), ("Gravando...", 0.5)] for a in andamento)
    assert resultados == [42] and tarefa.terminou


def test_andamento_muito_seguido_nao_congela_a_janela(raiz):
    """Andamento chegando mais rápido do que a janela consegue desenhar (o EFD Contribuições lendo PDFs): antes, a
    janela ficava presa redesenhando a barra a cada mensagem e congelava até o fim. Agora cada leitura da fila
    mostra só o último andamento e devolve a janela, que continua respondendo."""
    import time
    andamento, batidas = [], []

    def trabalho(progresso):
        for numero in range(60):
            progresso(f"Lendo {numero}...", numero / 60)
            time.sleep(0.005)
        return "ok"

    def desenhar_devagar(texto, fracao):
        andamento.append(texto)
        time.sleep(0.02)                     # desenhar demora mais que a próxima mensagem chegar

    def batida():
        batidas.append(time.time())
        if not tarefa.terminou:
            raiz.after(10, batida)

    tarefa = TarefaEmSegundoPlano(raiz, trabalho, ao_progresso=desenhar_devagar, ao_concluir=lambda r: None)
    raiz.after(10, batida)
    tarefa.iniciar()
    _esperar(raiz, tarefa)
    assert andamento[-1] == "Lendo 59..." and len(andamento) < 60
    pausas = [b - a for a, b in zip(batidas, batidas[1:])]
    assert len(batidas) > 3 and max(pausas) < 0.25


def test_tarefa_com_erro_vira_mensagem(raiz):
    falhas = []

    def trabalho(progresso):
        raise PermissionError("A planilha está aberta no Excel.")

    tarefa = TarefaEmSegundoPlano(raiz, trabalho, ao_concluir=lambda r: pytest.fail("não devia concluir"),
                                  ao_falhar=lambda erro, detalhe: falhas.append((erro, detalhe))).iniciar()
    _esperar(raiz, tarefa)

    [(erro, detalhe)] = falhas
    assert isinstance(erro, PermissionError) and "PermissionError" in detalhe


# ---------------------------------------------------------------------------
# Regras visuais (GUIA_VISUAL, seção 6): cor e fonte só em tema.py
# ---------------------------------------------------------------------------

ARQUIVOS_DE_TELA = sorted(
    [p for p in (RAIZ / "central").glob("*.py") if p.name not in {"tema.py", "gerar_icones.py"}]
    + list((RAIZ / "modulos").rglob("painel.py"))
    + [p for p in (RAIZ / "modulos").rglob("*.py") if "telas" in p.parts]
)


@pytest.mark.parametrize("arquivo", ARQUIVOS_DE_TELA, ids=lambda p: str(p.relative_to(RAIZ)))
def test_tela_nao_escreve_cor_nem_fonte(arquivo):
    texto = arquivo.read_text(encoding="utf-8")
    assert re.findall(r"#[0-9a-fA-F]{6}\b", texto) == [], "cor escrita direto: use central/tema.py"
    assert "CTkFont(" not in texto, "fonte criada direto: use as funções fonte_* de central/tema.py"


# ---------------------------------------------------------------------------
# Marca e ícone do .exe (Etapa 9 da unificação)
# ---------------------------------------------------------------------------


def test_logo_e_icone_feitos_do_simbolo(tmp_path):
    if not gerar_icones.LOGO_ORIGINAL.is_file():
        pytest.skip("recursos/logo_hospital_exemplo_256.png não encontrado")
    marca, icone = gerar_icones.gerar_logo_e_icone(pasta_icones=tmp_path, pasta_recursos=tmp_path)
    with Image.open(marca) as imagem:
        assert imagem.size == (gerar_icones.TAMANHO_LOGO,) * 2 and imagem.mode == "RGBA"
        assert imagem.getpixel((0, 0))[3] == 0                          # fundo transparente
    with Image.open(icone) as imagem:
        assert set(gerar_icones.TAMANHOS_ICO) <= imagem.info["sizes"]
    # o símbolo é só a parte colorida: o texto cinza "GRUPO HOSPITAL EXEMPLO" fica de fora
    simbolo = gerar_icones.simbolo_do_logo(Image.open(gerar_icones.LOGO_ORIGINAL))
    cinzas = sum(1 for r, g, b, a in simbolo.convert("RGBA").get_flattened_data() if a > 200 and max(r, g, b) - min(r, g, b) < 15)
    assert cinzas < simbolo.width * simbolo.height * 0.01
    # os arquivos da Central são os gerados agora
    assert (icones.pasta_icones() / "logo.png").read_bytes() == marca.read_bytes()


def test_cada_modulo_tem_o_seu_icone():
    from central import registro

    modulos = [m for m in registro.carregar_modulos() if m.ok]
    icones_usados = [m.info.icone for m in modulos]
    repetidos = {i for i in icones_usados if icones_usados.count(i) > 1}
    assert not repetidos, repetidos
    for nome in icones_usados:
        assert (icones.pasta_icones() / f"{nome}.png").is_file(), nome
