"""Testes do contrato de módulo e do registro (ESPECIFICACAO, seção 4)."""

from __future__ import annotations

import itertools
import sys
import textwrap

import pytest

from central import registro
from central.modulo_base import ErroModulo, InfoModulo

_contador = itertools.count()


def _info(chave="teste", **mudancas) -> InfoModulo:
    dados = dict(
        chave=chave,
        nome="Módulo de teste",
        descricao="Faz uma conciliação de teste.",
        contexto="Conciliações / Teste",
        icone="teste",
        criar_painel=lambda frame: None,
    )
    dados.update(mudancas)
    return InfoModulo(**dados)


@pytest.fixture
def pacote_falso(tmp_path, monkeypatch):
    """Cria um pacote de módulos falso numa pasta temporária.

    Devolve (nome_do_pacote, criar), onde criar(nome_pasta, codigo_do___init__) monta um módulo.
    Cada teste usa um nome de pacote diferente para o Python não reaproveitar importações.
    """
    nome_pacote = f"modulos_falsos_{next(_contador)}"
    raiz = tmp_path / nome_pacote
    raiz.mkdir()
    (raiz / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    def criar(nome_pasta: str, codigo: str):
        pasta = raiz / nome_pasta
        pasta.mkdir()
        (pasta / "__init__.py").write_text(textwrap.dedent(codigo), encoding="utf-8")

    yield nome_pacote, criar
    for nome in [n for n in sys.modules if n == nome_pacote or n.startswith(nome_pacote + ".")]:
        del sys.modules[nome]


def _codigo_modulo(chave: str, nome: str = "Módulo") -> str:
    return f"""
        from central.modulo_base import InfoModulo
        MODULO = InfoModulo(
            chave={chave!r}, nome={nome!r}, descricao="Descrição.", contexto="Conciliações / Teste",
            icone="teste", criar_painel=lambda frame: None,
        )
    """


# ---------------------------------------------------------------------------
# InfoModulo
# ---------------------------------------------------------------------------


def test_info_modulo_valido():
    info = _info("clientes_cmd")
    assert info.chave == "clientes_cmd"


@pytest.mark.parametrize("chave", ["", "Subvencoes", "subvenções", "clientes cmd", "1bancos", "clientes-cmd"])
def test_info_modulo_recusa_chave_invalida(chave):
    with pytest.raises(ErroModulo):
        _info(chave)


@pytest.mark.parametrize("campo", ["nome", "descricao", "contexto", "icone"])
def test_info_modulo_recusa_campo_vazio(campo):
    with pytest.raises(ErroModulo, match=campo):
        _info(**{campo: "  "})


def test_info_modulo_exige_funcao_criar_painel():
    with pytest.raises(ErroModulo, match="criar_painel"):
        _info(criar_painel="não é função")


# ---------------------------------------------------------------------------
# carregar_modulos
# ---------------------------------------------------------------------------


def test_registro_da_primeira_etapa_carrega_sem_erro():
    carregados = registro.carregar_modulos()
    assert [m for m in carregados if not m.ok] == []


def test_carrega_modulos_na_ordem_do_registro(pacote_falso):
    pacote, criar = pacote_falso
    criar("bbb", _codigo_modulo("bbb", "Segundo nome"))
    criar("aaa", _codigo_modulo("aaa", "Primeiro nome"))

    carregados = registro.carregar_modulos(["bbb", "aaa"], pacote=pacote)

    assert [m.chave for m in carregados] == ["bbb", "aaa"]
    assert all(m.ok for m in carregados)
    assert carregados[0].nome == "Segundo nome"


def test_modulo_com_erro_nao_derruba_os_outros(pacote_falso):
    pacote, criar = pacote_falso
    criar("bom", _codigo_modulo("bom"))
    criar("quebrado", "import biblioteca_que_nao_existe\n")
    criar("outro_bom", _codigo_modulo("outro_bom"))

    carregados = registro.carregar_modulos(["bom", "quebrado", "outro_bom"], pacote=pacote)

    assert [m.ok for m in carregados] == [True, False, True]
    quebrado = carregados[1]
    assert "quebrado" in quebrado.erro
    assert "biblioteca_que_nao_existe" in quebrado.detalhe_tecnico
    assert quebrado.nome == "quebrado"  # aparece no menu pelo nome da pasta


def test_pasta_inexistente_vira_erro(pacote_falso):
    pacote, _ = pacote_falso
    carregados = registro.carregar_modulos(["nao_existe"], pacote=pacote)
    assert not carregados[0].ok
    assert "nao_existe" in carregados[0].erro


def test_modulo_sem_variavel_modulo(pacote_falso):
    pacote, criar = pacote_falso
    criar("sem_info", "X = 1\n")
    carregados = registro.carregar_modulos(["sem_info"], pacote=pacote)
    assert not carregados[0].ok
    assert "MODULO" in carregados[0].erro


def test_modulo_com_info_invalida(pacote_falso):
    pacote, criar = pacote_falso
    criar("chave_ruim", _codigo_modulo("Chave Ruim"))
    carregados = registro.carregar_modulos(["chave_ruim"], pacote=pacote)
    assert not carregados[0].ok
    assert "Chave de módulo inválida" in carregados[0].erro


def test_chave_repetida_vira_erro_no_segundo(pacote_falso):
    pacote, criar = pacote_falso
    criar("primeiro", _codigo_modulo("mesma_chave"))
    criar("segundo", _codigo_modulo("mesma_chave"))

    carregados = registro.carregar_modulos(["primeiro", "segundo"], pacote=pacote)

    assert carregados[0].ok
    assert not carregados[1].ok
    assert "mesma_chave" in carregados[1].erro


def test_nome_repetido_no_registro_vira_erro(pacote_falso):
    pacote, criar = pacote_falso
    criar("unico", _codigo_modulo("unico"))

    carregados = registro.carregar_modulos(["unico", "unico"], pacote=pacote)

    assert carregados[0].ok
    assert not carregados[1].ok
    assert "mais de uma vez" in carregados[1].erro


def test_registro_real_nao_tem_nomes_repetidos():
    assert len(registro.NOMES_MODULOS) == len(set(registro.NOMES_MODULOS))


# ---------------------------------------------------------------------------
# modulo_inicial (o preferido — registro.MODULO_INICIAL — ou o primeiro)
# ---------------------------------------------------------------------------


def _carregado(chave, ok=True):
    if ok:
        return registro.ModuloCarregado(nome_pasta=chave, info=_info(chave))
    return registro.ModuloCarregado(nome_pasta=chave, erro="quebrado")


def test_modulo_inicial_e_o_preferido():
    carregados = [_carregado("aaa"), _carregado("bbb")]
    assert registro.modulo_inicial(carregados, "bbb").chave == "bbb"


def test_modulo_inicial_sem_preferido_e_o_primeiro():
    carregados = [_carregado("aaa"), _carregado("bbb")]
    assert registro.modulo_inicial(carregados, "").chave == "aaa"


def test_modulo_inicial_preferido_que_nao_existe():
    carregados = [_carregado("aaa"), _carregado("bbb")]
    assert registro.modulo_inicial(carregados, "removido").chave == "aaa"


def test_modulo_inicial_pula_modulo_com_erro():
    carregados = [_carregado("quebrado", ok=False), _carregado("bom")]
    assert registro.modulo_inicial(carregados, "quebrado").chave == "bom"


def test_modulo_inicial_sem_modulos():
    assert registro.modulo_inicial([], "qualquer") is None


def test_modulo_inicial_do_registro_existe():
    assert registro.MODULO_INICIAL in registro.NOMES_MODULOS


def test_secoes_do_registro():
    # nenhum módulo em duas seções, e a seção de cada um chega ao item carregado
    assert set(registro.SECAO_DO_MODULO) == set(registro.NOMES_MODULOS)
    carregados = registro.carregar_modulos()
    assert [m.secao for m in carregados] == [registro.SECAO_DO_MODULO[m.nome_pasta] for m in carregados]


def test_modulo_fora_das_secoes_fica_na_secao_padrao(pacote_falso):
    pacote, criar = pacote_falso
    criar("avulso", _codigo_modulo("avulso"))
    assert registro.carregar_modulos(["avulso"], pacote=pacote)[0].secao == registro.SECAO_PADRAO
