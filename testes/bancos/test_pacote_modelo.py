"""Testes do pacote de modelo novo (Etapa 10)."""

import json
from datetime import date

import pytest

from modulos.bancos.pacote_modelo import (
    PASTA_PACOTES,
    DadosModeloNovo,
    caminho_do_pacote,
    criar_pacote,
    texto_inicial,
    validar,
)
from testes.bancos.conftest import caminho_exemplo

COMPETENCIA = date(2026, 9, 1)


def _dados(**mudancas):
    base = dict(banco="itau", tipo="cc", conta="1234-5", saldo_total="1.500,00",
                saldo_bloqueado="", observacao="  saldo na última linha  ")
    base.update(mudancas)
    return DadosModeloNovo(**base)


# ---------------------------------------------------------------------------
# Validação do formulário
# ---------------------------------------------------------------------------

def test_validar_arruma_os_dados():
    dados = validar(_dados(saldo_total="1500,50"))   # sem ponto de milhar
    assert (dados.banco, dados.tipo, dados.conta) == ("ITAU", "CC", "1234-5")
    assert dados.saldo_total == "1.500,50"
    assert dados.saldo_bloqueado == "0,00"          # vazio vira zero
    assert dados.observacao == "saldo na última linha"


@pytest.mark.parametrize("mudanca, mensagem", [
    ({"banco": "  "}, "banco"),
    ({"tipo": "CORRENTE"}, "Tipo inválido"),
    ({"conta": "abc"}, "número da conta"),
    ({"saldo_total": ""}, "Saldo total inválido"),
    ({"saldo_total": "1500"}, "Saldo total inválido"),         # sem centavos
    ({"saldo_bloqueado": "cinco"}, "Saldo bloqueado inválido"),
])
def test_validar_rejeita_dados_invalidos(mudanca, mensagem):
    with pytest.raises(ValueError, match=mensagem):
        validar(_dados(**mudanca))


def test_validar_junta_todos_os_problemas():
    with pytest.raises(ValueError) as erro:
        validar(_dados(banco="", saldo_total="x"))
    assert len(str(erro.value).splitlines()) == 2


# ---------------------------------------------------------------------------
# Criação do pacote
# ---------------------------------------------------------------------------

def test_caminho_do_pacote(tmp_path):
    caminho = caminho_do_pacote(tmp_path, tmp_path / "extrato itau.pdf", COMPETENCIA)
    assert caminho == tmp_path / PASTA_PACOTES / "2026-09_extrato itau"


def test_criar_pacote(tmp_path):
    pdf = caminho_exemplo("1179 7.pdf")
    pasta = criar_pacote(tmp_path, pdf, COMPETENCIA, _dados(), subpasta="Itaú")

    assert pasta == (tmp_path / PASTA_PACOTES / "2026-09_1179 7").resolve()
    assert (pasta / "1179 7.pdf").read_bytes() == pdf.read_bytes()
    texto = (pasta / "texto_extraido.txt").read_text(encoding="utf-8")
    assert texto.startswith("===== Página 1 de 1 =====")
    assert "Extrato de conta corrente" in texto

    info = json.loads((pasta / "dados.json").read_text(encoding="utf-8"))
    assert info["competencia"] == "2026-09"
    assert info["banco"] == "ITAU" and info["tipo"] == "CC"
    assert info["conta"] == "1234-5" and info["conta_normalizada"] == "12345"
    assert info["saldo_total"] == "1.500,00"
    assert info["saldo_total_decimal"] == "1500.00"
    assert info["saldo_bloqueado_decimal"] == "0.00"
    assert info["subpasta_de_origem"] == "Itaú"

    pedido = (pasta / "PEDIDO.md").read_text(encoding="utf-8")
    assert "R$ 1.500,00" in pedido
    assert "(banco novo)" in pedido
    assert f'/novo-modelo "{pasta}"' in pedido


def test_banco_conhecido_nao_e_marcado_como_novo(tmp_path):
    pasta = criar_pacote(tmp_path, caminho_exemplo("1179 7.pdf"), COMPETENCIA,
                         _dados(banco="bb"))
    assert "(banco novo)" not in (pasta / "PEDIDO.md").read_text(encoding="utf-8")


def test_criar_pacote_substitui_o_anterior(tmp_path):
    pdf = caminho_exemplo("1179 7.pdf")
    pasta = criar_pacote(tmp_path, pdf, COMPETENCIA, _dados())
    (pasta / "sobra.txt").write_text("de uma versão antiga")
    criar_pacote(tmp_path, pdf, COMPETENCIA, _dados(saldo_total="2,00"))
    assert not (pasta / "sobra.txt").exists()
    assert json.loads((pasta / "dados.json").read_text(encoding="utf-8"))["saldo_total"] == "2,00"


def test_dados_invalidos_nao_criam_pacote(tmp_path):
    with pytest.raises(ValueError):
        criar_pacote(tmp_path, caminho_exemplo("1179 7.pdf"), COMPETENCIA,
                     _dados(saldo_total="abc"))
    assert not (tmp_path / PASTA_PACOTES).exists()


def test_texto_inicial_limita_as_linhas():
    previa = texto_inicial(caminho_exemplo("1179 7.pdf"), linhas=5)
    assert len(previa.splitlines()) == 5
    assert previa.startswith("===== Página 1 de 1 =====")
