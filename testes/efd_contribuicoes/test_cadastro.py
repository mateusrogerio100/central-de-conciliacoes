"""EFD 3 — cadastro de clientes na rede (ESPECIFICACAO_EFD_CONTRIBUICOES.md, seção 4.4).

Tudo numa pasta temporária, com clientes fictícios: nenhum teste toca a rede de verdade.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from modulos.efd_contribuicoes import configuracao
from modulos.efd_contribuicoes.cadastro_clientes import (
    ORIGEM_DIGITADO,
    ORIGEM_PDF,
    CadastroMudou,
    ErroCadastro,
    carregar_cadastro,
    criar_a_partir_do_sped,
    gravar_cadastro,
    novo_cadastro,
)
from modulos.efd_contribuicoes.leitor_sped import ler_molde

CLIENTES = [
    {"cod_part": "1", "nome": "CLIENTE FICTICIO UM", "cnpj": "11111111000191", "codigo_ibge": "3516200"},
    {"cod_part": "2", "nome": "CLIENTE FICTICIO DOIS", "cnpj": "22222222000191", "codigo_ibge": "3509502"},
]
AGORA = datetime(2026, 11, 5, 15, 30)


def _gravar(pasta, clientes=CLIENTES, nome=configuracao.NOME_CADASTRO):
    caminho = pasta / nome
    caminho.write_text(json.dumps({"clientes": clientes}, ensure_ascii=False, indent=2), encoding="utf-8")
    return caminho


@pytest.fixture
def rede(tmp_path):
    pasta = tmp_path / "rede" / "EFD Contribuições"
    pasta.mkdir(parents=True)
    return pasta


def test_sem_acesso_a_pasta_ou_arquivo_sumido_nao_gera(tmp_path):
    with pytest.raises(ErroCadastro, match="Sem acesso à pasta do cadastro"):
        carregar_cadastro(tmp_path / "nao_existe" / "clientes.json")
    with pytest.raises(ErroCadastro, match="não foi encontrado"):
        carregar_cadastro(tmp_path / "clientes.json")


def test_le_cadastro_e_reaproveita_codigo(rede):
    _gravar(rede)
    cadastro = carregar_cadastro(rede / "clientes.json")
    assert cadastro.existe and len(cadastro.clientes) == 2
    assert cadastro.obter_cod_part("22222222000191", "CLIENTE FICTICIO DOIS", "3509502") == "2"
    assert cadastro.novos == {} and cadastro.avisos == []


def test_cliente_novo_ganha_o_proximo_codigo(rede):
    _gravar(rede, CLIENTES + [{"cod_part": "7", "nome": "X", "cnpj": "77777777000191", "codigo_ibge": "3516200"}])
    cadastro = carregar_cadastro(rede / "clientes.json")
    assert cadastro.obter_cod_part("33333333000191", "CLIENTE NOVO", "3543600") == "8"
    assert cadastro.obter_cod_part("33333333000191", "CLIENTE NOVO", "3543600") == "8"       # 2ª nota: mesmo código
    assert cadastro.obter_cod_part("44444444000191", "OUTRO NOVO", None) == "9"
    assert cadastro.novos == {"33333333000191": ORIGEM_PDF, "44444444000191": ""}
    assert [c["cod_part"] for c in cadastro.novos_sem_ibge()] == ["9"]


def test_ibge_digitado_para_cliente_novo(rede):
    _gravar(rede)
    cadastro = carregar_cadastro(rede / "clientes.json")
    cadastro.obter_cod_part("33333333000191", "CLIENTE NOVO", None)
    with pytest.raises(ErroCadastro, match="7 números"):
        cadastro.definir_ibge("33333333000191", "35162")
    with pytest.raises(ErroCadastro, match="cliente novo"):
        cadastro.definir_ibge("11111111000191", "3516200")
    cadastro.definir_ibge("33333333000191", " 3543600 ")
    assert cadastro.novos_sem_ibge() == []
    assert cadastro.novos["33333333000191"] == ORIGEM_DIGITADO
    assert cadastro.clientes["33333333000191"]["codigo_ibge"] == "3543600"


def test_cliente_conhecido_com_nome_ou_ibge_diferente_fica_o_do_cadastro(rede):
    _gravar(rede)
    cadastro = carregar_cadastro(rede / "clientes.json")
    assert cadastro.obter_cod_part("11111111000191", "CLIENTE FICTICIO UM LTDA", "3509502") == "1"
    assert cadastro.clientes["11111111000191"]["nome"] == "CLIENTE FICTICIO UM"
    assert len(cadastro.avisos) == 2
    assert "ficou o do cadastro" in cadastro.avisos[0] and "3509502" in cadastro.avisos[1]


def test_gravar_faz_copia_e_mantem_o_formato(rede):
    _gravar(rede)
    cadastro = carregar_cadastro(rede / "clientes.json")
    cadastro.obter_cod_part("33333333000191", "CLIENTE NOVO", "3543600")
    copia = gravar_cadastro(cadastro, AGORA)
    assert copia == rede / "copias" / "clientes_2026-11-05_15h30.json"
    assert json.loads(copia.read_text(encoding="utf-8")) == {"clientes": CLIENTES}           # o anterior, intacto
    gravado = json.loads((rede / "clientes.json").read_text(encoding="utf-8"))
    assert [c["cod_part"] for c in gravado["clientes"]] == ["1", "2", "3"]
    assert gravado["clientes"][2] == {"cod_part": "3", "nome": "CLIENTE NOVO", "cnpj": "33333333000191",
                                      "codigo_ibge": "3543600"}
    assert not list(rede.glob("*.gravando"))
    # gravar de novo no mesmo minuto não apaga a primeira cópia
    assert gravar_cadastro(cadastro, AGORA).name == "clientes_2026-11-05_15h30_2.json"


def test_outra_pessoa_gravou_no_meio_nada_e_sobrescrito(rede):
    _gravar(rede)
    minha = carregar_cadastro(rede / "clientes.json")
    minha.obter_cod_part("33333333000191", "MEU CLIENTE NOVO", "3543600")
    outra = carregar_cadastro(rede / "clientes.json")
    outra.obter_cod_part("44444444000191", "CLIENTE NOVO DA OUTRA PESSOA", "3516200")
    gravar_cadastro(outra, AGORA)
    antes = (rede / "clientes.json").read_text(encoding="utf-8")
    with pytest.raises(CadastroMudou, match="Nada foi sobrescrito"):
        gravar_cadastro(minha, AGORA)
    assert (rede / "clientes.json").read_text(encoding="utf-8") == antes


def test_cadastro_novo_a_partir_dos_0150_do_sped(rede, sped_ficticio):
    cadastro = novo_cadastro(rede / "clientes.json", ler_molde(sped_ficticio))
    assert not cadastro.existe and len(cadastro.clientes) == 2
    assert cadastro.clientes["22222222000191"] == {"cod_part": "2", "nome": "CLIENTE FICTICIO DOIS",
                                                   "cnpj": "22222222000191", "codigo_ibge": "3509502"}
    assert gravar_cadastro(cadastro, AGORA) is None                    # não havia arquivo: sem cópia
    assert carregar_cadastro(rede / "clientes.json").clientes.keys() == {"11111111000191", "22222222000191"}


def test_cadastro_novo_nao_pisa_num_que_ja_existe(rede, sped_ficticio):
    _gravar(rede)
    with pytest.raises(ErroCadastro, match="Já existe um cadastro"):
        novo_cadastro(rede / "clientes.json", ler_molde(sped_ficticio))


def test_cadastro_novo_e_outra_pessoa_criou_antes(rede, sped_ficticio):
    cadastro = novo_cadastro(rede / "clientes.json", ler_molde(sped_ficticio))
    _gravar(rede)                                                      # outra pessoa criou nesse meio-tempo
    with pytest.raises(CadastroMudou):
        gravar_cadastro(cadastro, AGORA)


@pytest.mark.parametrize("conteudo, mensagem", [
    ("isto não é json", "não é um cadastro válido"),
    ('{"outra": []}', 'não tem a lista "clientes"'),
    ('{"clientes": [{"cod_part": "1"}]}', "cliente nº 1 está incompleto"),
    (json.dumps({"clientes": CLIENTES + [dict(CLIENTES[0], cod_part="3")]}), "repetido"),
])
def test_cadastro_ilegivel(rede, conteudo, mensagem):
    (rede / "clientes.json").write_text(conteudo, encoding="utf-8")
    with pytest.raises(ErroCadastro, match=mensagem):
        carregar_cadastro(rede / "clientes.json")


def test_clientes_para_o_sped_em_ordem_de_codigo(rede):
    _gravar(rede, list(reversed(CLIENTES)))
    assert [c.cod_part for c in carregar_cadastro(rede / "clientes.json").para_sped()] == ["1", "2"]


def test_cadastro_real_da_aplicacao_antiga_e_lido():
    from testes.efd_contribuicoes.conftest import exemplo_efd
    cadastro = carregar_cadastro(exemplo_efd("clientes.json"))
    assert len(cadastro.clientes) == 44 and cadastro.max_cod_part == 44


def test_nome_diferente_so_na_escrita_nao_e_aviso_e_aviso_sai_uma_vez(rede):
    _gravar(rede, [{"cod_part": "1", "nome": "PREFEITURA MUNICIPAL DE RESTINGA", "cnpj": "11111111000191",
                    "codigo_ibge": "3516200"},
                   {"cod_part": "2", "nome": "CMD Fundacao Exemplo de Cidade Alfa", "cnpj": "22222222000191",
                    "codigo_ibge": "3516200"}])
    cadastro = carregar_cadastro(rede / "clientes.json")
    cadastro.obter_cod_part("11111111000191", "Prefeitura Municipal de Restinga", "3516200")
    cadastro.obter_cod_part("22222222000191", "CMD - Fundação Exemplo de Cidade Alfa.", "3516200")
    assert cadastro.avisos == []
    for _ in range(3):                                            # 3 notas do mesmo cliente com nome diferente
        cadastro.obter_cod_part("11111111000191", "Prefeitura de Restinga", "3509502")
    assert cadastro.avisos == [
        'Cliente 1: no PDF o nome é "Prefeitura de Restinga"; ficou o do cadastro, "PREFEITURA MUNICIPAL DE RESTINGA".',
        "Cliente 1 (PREFEITURA MUNICIPAL DE RESTINGA): no PDF o Código IBGE é 3509502; ficou o do cadastro, 3516200.",
    ]
