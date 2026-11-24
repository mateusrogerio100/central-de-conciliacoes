"""N2b: modelo do e-mail (seção 3.3)."""

from __future__ import annotations

import pytest

from modulos.notas_pendentes.leitor_modelo import (
    ORIGEM_FABRICA, caminho_modelo_fabrica, interpretar, ler_modelo, sugerir_modelo,
)
from modulos.notas_pendentes.modelos import ErroLeitura


def test_modelo_de_fabrica_e_o_texto_do_usuario():
    modelo = interpretar(caminho_modelo_fabrica().read_text(encoding="utf-8"), ORIGEM_FABRICA)
    assert modelo.assunto == "Notas fiscais pendentes de registro - Competência {competencia}"
    assert modelo.corpo.startswith("Prezados(as) Gerente e equipe\n\nSolicitamos o registro das notas fiscais")
    assert "competência de {competencia_extenso} que ainda não foram encaminhadas para registro." in modelo.corpo
    assert "registradas até o dia {prazo}, garantindo" in modelo.corpo
    assert modelo.corpo.endswith("Contamos com a colaboração de todos.\n\nNotas pendentes (anexas):\n"
                                 "{lista_notas}\n\nContabilidade")
    assert modelo.de_fabrica and modelo.avisos == []


def test_modelo_editado(tmp_path):
    caminho = tmp_path / "modelo_email.txt"
    caminho.write_text("\n\nASSUNTO:  Pendências {Competência}  \n\n\nTexto novo até {prazo}.   \n\n"
                       "{lista_notas}\n\n", encoding="utf-8-sig")
    modelo = ler_modelo(caminho)
    assert modelo.assunto == "Pendências {Competência}"
    assert modelo.corpo == "Texto novo até {prazo}.\n\n{lista_notas}"
    assert not modelo.de_fabrica and modelo.avisos == [] and modelo.origem == str(caminho)


def test_modelo_salvo_em_ansi_pelo_bloco_de_notas_antigo(tmp_path):
    caminho = tmp_path / "modelo_email.txt"
    caminho.write_bytes("Assunto: Competência {competencia}\n\nAté {prazo}: {lista_notas}".encode("cp1252"))
    assert ler_modelo(caminho).assunto == "Competência {competencia}"


@pytest.mark.parametrize("texto, mensagem", [
    ("Prezados\n\nTexto {prazo} {lista_notas}", "precisa começar com a linha \"Assunto: ...\""),
    ("Assunto:\n\nTexto", "assunto vazio"),
    ("Assunto: Notas {competencia}\n\n", "não tem texto depois do assunto"),
    ("Assunto: Notas {competencia}\n\nAté {prazoo} {lista_notas}", "{prazoo}"),
    ("Assunto: Notas {mes}\n\nAté {prazo} {lista_notas}", "{mes}"),
    ("", "precisa começar com a linha"),
])
def test_modelo_com_erro_nao_gera_nada(tmp_path, texto, mensagem):
    caminho = tmp_path / "modelo_email.txt"
    caminho.write_text(texto, encoding="utf-8")
    with pytest.raises(ErroLeitura) as erro:
        ler_modelo(caminho)
    assert mensagem in str(erro.value)
    if "{" in mensagem:
        assert "Os marcadores válidos são {competencia}, {competencia_extenso}, {prazo}, {lista_notas}" in \
            str(erro.value)


def test_marcador_faltando_vira_aviso(tmp_path):
    caminho = tmp_path / "modelo_email.txt"
    caminho.write_text("Assunto: Notas {competencia}\n\nFavor registrar.", encoding="utf-8")
    modelo = ler_modelo(caminho)
    assert modelo.corpo == "Favor registrar."
    assert [a.mensagem.split(":")[0] for a in modelo.avisos] == [
        "O modelo do e-mail não tem o marcador {prazo}", "O modelo do e-mail não tem o marcador {lista_notas}"]


def test_sem_modelo_usa_o_de_fabrica_com_aviso(tmp_path):
    for caminho, trecho in ((None, "não escolhido"), (tmp_path / "sumiu.txt", "não encontrado")):
        modelo = ler_modelo(caminho)
        assert modelo.de_fabrica and modelo.assunto.startswith("Notas fiscais pendentes de registro")
        assert trecho in modelo.avisos[0].mensagem and "modelo de fábrica" in modelo.avisos[0].mensagem


def test_sugerir_modelo_na_pasta_config_ao_lado_dos_meses(tmp_path):
    mes = tmp_path / "HOSPITAL EXEMPLO" / "102026"
    mes.mkdir(parents=True)
    assert sugerir_modelo(mes) is None
    config = tmp_path / "HOSPITAL EXEMPLO" / "config"
    config.mkdir()
    (config / "modelo_email.txt").write_text("Assunto: x\n\ny", encoding="utf-8")
    assert sugerir_modelo(mes) == config / "modelo_email.txt"
