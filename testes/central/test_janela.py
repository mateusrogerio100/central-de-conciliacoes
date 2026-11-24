"""Testes da janela principal com módulos de demonstração (sem mostrar a janela)."""

from __future__ import annotations

import json

import customtkinter as ctk
import pytest

from central import janela as modulo_janela
from central.janela import JanelaCentral, PainelModuloComErro
from central.modulo_base import InfoModulo
from central.preferencias import Preferencias, salvar_preferencias
from central.registro import ModuloCarregado
from testes.conftest import abrir_janela_ctk


class PainelDeTeste(ctk.CTkFrame):
    criados = 0

    def __init__(self, pai):
        super().__init__(pai, fg_color="transparent")
        PainelDeTeste.criados += 1
        self.escolha = ""


def _modulo(chave, criar_painel=PainelDeTeste) -> ModuloCarregado:
    info = InfoModulo(chave=chave, nome=f"Módulo {chave}", descricao="Teste.", contexto="Conciliações / Teste",
                      icone="banco", criar_painel=criar_painel)
    return ModuloCarregado(nome_pasta=chave, info=info)


def _painel_com_defeito(pai):
    raise RuntimeError("defeito na tela")


@pytest.fixture
def abrir(tmp_path):
    """abrir(modulos, preferencias=None) -> JanelaCentral escondida; fecha tudo no fim do teste."""
    abertas = []
    caminho = tmp_path / "preferencias.json"

    def _abrir(modulos, preferencias: Preferencias | None = None, chave_inicial: str | None = None):
        if preferencias:
            salvar_preferencias(preferencias, caminho)
        janela = abrir_janela_ctk(JanelaCentral, modulos=modulos, caminho_preferencias=caminho,
                                  chave_inicial=chave_inicial)
        abertas.append(janela)
        return janela

    _abrir.caminho = caminho
    yield _abrir
    for janela in abertas:
        janela.destroy()
    ctk.set_appearance_mode("light")


def _ler(caminho):
    return json.loads(caminho.read_text(encoding="utf-8"))


def test_menu_tem_um_item_por_modulo_na_ordem(abrir):
    janela = abrir([_modulo("aaa"), _modulo("bbb"), _modulo("ccc")])
    assert list(janela.menu.itens) == ["aaa", "bbb", "ccc"]
    assert janela.menu.itens["aaa"].cget("text") == "Módulo aaa"


def test_abre_no_primeiro_modulo_na_primeira_vez(abrir):
    janela = abrir([_modulo("aaa"), _modulo("bbb")])
    assert janela.modulo_atual == "aaa"
    assert janela.menu.itens["aaa"].ativo and not janela.menu.itens["bbb"].ativo


def test_abre_no_modulo_inicial_e_nao_no_ultimo_usado(abrir):
    # o "ultimo_modulo" das versões até a 1.3.8 fica no arquivo, mas não manda mais (decisão de 20/10/2026)
    abrir.caminho.write_text(json.dumps({"modo": "claro", "ultimo_modulo": "aaa"}), encoding="utf-8")
    janela = abrir([_modulo("aaa"), _modulo("bbb")], chave_inicial="bbb")
    assert janela.modulo_atual == "bbb"


def test_central_de_verdade_abre_no_modulo_inicial_do_registro(abrir, monkeypatch):
    from central import registro

    monkeypatch.setattr(registro, "carregar_modulos", lambda: [_modulo("aaa"), _modulo(registro.MODULO_INICIAL)])
    janela = abrir(None)
    assert janela.modulo_atual == registro.MODULO_INICIAL


def test_trocar_de_modulo_nao_grava_nada(abrir):
    janela = abrir([_modulo("aaa"), _modulo("bbb")])
    janela.selecionar("bbb")
    assert janela.modulo_atual == "bbb" and janela.menu.itens["bbb"].ativo
    assert not abrir.caminho.exists()


def test_menu_agrupa_os_itens_pelas_secoes(abrir):
    modulos = [_modulo("aaa"), _modulo("bbb"), _modulo("ccc")]
    modulos[0].secao = modulos[1].secao = "FISCAL"
    modulos[2].secao = "FERRAMENTAS"
    janela = abrir(modulos)
    assert janela.menu.secoes == ["FISCAL", "FERRAMENTAS"]
    assert list(janela.menu.itens) == ["aaa", "bbb", "ccc"]


def test_menu_rola_so_quando_nao_cabe(abrir):
    # 14 itens em 4 seções: na janela mínima (700 px) não cabem; em 1000 px cabem
    modulos = [_modulo(f"m{i:02d}") for i in range(14)]
    for indice, modulo in enumerate(modulos):
        modulo.secao = f"SEÇÃO {indice // 4}"
    janela = abrir(modulos)
    janela.deiconify()
    janela.geometry("1100x700")
    for _ in range(10):
        janela.update()
    assert janela.menu.area.precisa_rolar()
    janela.geometry("1100x1000")
    for _ in range(10):
        janela.update()
    assert not janela.menu.area.precisa_rolar()


def test_item_aberto_fica_a_vista_mesmo_se_a_janela_demora_a_aparecer(abrir):
    # No .exe a janela aparece depois do pedido de rolar (visto na Unificação 10, abrindo no
    # Imprimir PDFs, o último item): o menu guarda o pedido e rola quando a barra aparece.
    import time

    modulos = [_modulo(f"m{i:02d}") for i in range(14)]
    for indice, modulo in enumerate(modulos):
        modulo.secao = f"SEÇÃO {indice // 4}"
    janela = abrir(modulos, chave_inicial="m13")
    fim = time.time() + 0.3                       # passa o tempo do pedido com a janela escondida
    while time.time() < fim:
        janela.update()
    janela.geometry("1100x700")
    janela.deiconify()
    for _ in range(20):
        janela.update()
        time.sleep(0.01)
    area, item = janela.menu.area, janela.menu.itens["m13"]
    assert area.precisa_rolar()
    topo = item.winfo_rooty() - area.canvas.winfo_rooty()
    assert 0 <= topo and topo + item.winfo_height() <= area.canvas.winfo_height()


def test_painel_e_criado_uma_vez_e_mantem_o_estado(abrir):
    janela = abrir([_modulo("aaa"), _modulo("bbb")])
    antes = PainelDeTeste.criados
    painel = janela.paineis["aaa"]
    painel.escolha = "Balancete.xlsx"

    janela.selecionar("bbb")
    janela.selecionar("aaa")
    janela.selecionar("bbb")

    assert janela.paineis["aaa"] is painel and painel.escolha == "Balancete.xlsx"
    assert PainelDeTeste.criados == antes + 1                 # só o "bbb" foi criado agora
    assert not janela.paginas["aaa"].winfo_manager()           # o que não está aberto fica escondido


def test_modulo_que_nao_carregou_aparece_com_o_erro(abrir):
    quebrado = ModuloCarregado(nome_pasta="quebrado", erro="Não foi possível carregar o módulo 'quebrado': x",
                               detalhe_tecnico="Traceback...")
    janela = abrir([quebrado, _modulo("bom")])

    assert janela.modulo_atual == "bom"                       # abre no primeiro módulo que funciona
    janela.selecionar("quebrado")
    pagina = janela.paginas["quebrado"]
    assert _procurar(pagina, PainelModuloComErro)
    assert "quebrado" not in janela.paineis


def test_painel_com_defeito_nao_derruba_a_central(abrir):
    janela = abrir([_modulo("bom"), _modulo("defeito", _painel_com_defeito)])
    janela.selecionar("defeito")
    painel_erro = _procurar(janela.paginas["defeito"], PainelModuloComErro)
    assert painel_erro is not None
    janela.selecionar("bom")
    assert janela.modulo_atual == "bom"


def test_sem_modulos_mostra_orientacao(abrir):
    janela = abrir([])
    assert janela.modulo_atual is None and janela.menu.itens == {}


def test_alternar_modo_claro_escuro(abrir):
    janela = abrir([_modulo("aaa")])
    assert ctk.get_appearance_mode() == "Light"
    assert janela.menu.botao_modo.cget("text") == "Modo escuro"

    janela.alternar_modo()
    assert ctk.get_appearance_mode() == "Dark"
    assert janela.menu.botao_modo.cget("text") == "Modo claro"
    assert _ler(abrir.caminho)["modo"] == "escuro"

    janela.alternar_modo()
    assert ctk.get_appearance_mode() == "Light"
    assert _ler(abrir.caminho)["modo"] == "claro"


def test_abre_no_modo_escuro_salvo(abrir):
    janela = abrir([_modulo("aaa")], Preferencias(modo="escuro"))
    assert ctk.get_appearance_mode() == "Dark"
    assert janela.menu.botao_modo.cget("text") == "Modo claro"


def test_rodape_com_usuario_e_versao(abrir, monkeypatch):
    monkeypatch.setattr(modulo_janela, "usuario_do_windows", lambda: "usuario")
    janela = abrir([_modulo("aaa")])
    assert janela.menu.rotulo_rodape.cget("text") == f"usuario · versão {modulo_janela.VERSAO}"


def test_janela_titulo_e_tamanho_minimo(abrir):
    janela = abrir([_modulo("aaa")])
    assert janela.title() == "Central de Conciliações"
    assert (janela._min_width, janela._min_height) == (1100, 700)


def test_demonstracao_abre_todos_os_modulos(abrir):
    from central.demonstracao import modulos_de_demonstracao

    janela = abrir(modulos_de_demonstracao())
    for modulo in janela.modulos:
        janela.selecionar(modulo.chave)
    assert set(janela.paineis) == {"bancos", "clientes_cmd", "subvencoes"}


def _procurar(widget, classe):
    if isinstance(widget, classe):
        return widget
    for filho in widget.winfo_children():
        achado = _procurar(filho, classe)
        if achado is not None:
            return achado
    return None
