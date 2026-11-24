"""EFD 5 — a tela do módulo EFD Contribuições (montada sem mostrar a janela).

O cadastro "da rede" é uma pasta temporária (conftest do módulo); a leitura dos PDFs é trocada por notas fictícias;
as perguntas e a janela do Código IBGE são respondidas pelos testes. %APPDATA% temporário.
"""

from __future__ import annotations

import ast
import json
from datetime import date
from decimal import Decimal

import pytest

from central import registro
from modulos.efd_contribuicoes import MODULO, processamento
from modulos.efd_contribuicoes.leitor_danfse import PF, PJ, NotaDanfse
from testes.conftest import RAIZ, esperar

CLIENTES = [{"cod_part": "1", "nome": "CLIENTE FICTICIO UM", "cnpj": "11111111000191", "codigo_ibge": "3516200"}]


@pytest.fixture(autouse=True)
def appdata_temporario(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))


def _nota(arquivo, numero, cnpj="11.111.111/0001-91", tipo=PJ, ibge="3516200", tomador="CLIENTE FICTICIO UM",
          valor="100.00", status="OK"):
    return NotaDanfse(arquivo=arquivo, numero_nfse=numero, competencia="08/2026", data_emissao=date(2026, 8, 10),
                      data_emissao_texto="10/08/2026 10:00:00", prestador="PRESTADOR", tomador=tomador,
                      doc_tomador=cnpj, tipo_pessoa=tipo, codigo_ibge_tomador=ibge, valor=Decimal(valor),
                      status=status)


@pytest.fixture
def ambiente(tmp_path, monkeypatch, sped_ficticio, cadastro_fora_da_rede):
    (cadastro_fora_da_rede / "clientes.json").write_text(json.dumps({"clientes": CLIENTES}), encoding="utf-8")
    pdfs = tmp_path / "pdfs"
    pdfs.mkdir()
    saida = tmp_path / "saida"
    saida.mkdir()
    notas = {}

    def colocar(*lista):
        for n in lista:
            notas[n.arquivo] = n
            (pdfs / n.arquivo).write_bytes(b"")

    monkeypatch.setattr(processamento, "ler_danfse", lambda caminho: notas[caminho.name])
    return {"pdfs": pdfs, "saida": saida, "sped": sped_ficticio, "colocar": colocar, "rede": cadastro_fora_da_rede}


def _tela(criar_painel):
    tela = criar_painel(MODULO).geracao
    tela.mensagens, tela.perguntas = [], []
    tela.avisar = tela.mensagens.append
    esperar(tela, lambda: not tela.lendo_cadastro)
    return tela


def _preencher(tela, ambiente):
    tela.cartao_pdfs.definir_caminhos([ambiente["pdfs"]])
    tela.cartao_sped.definir_caminhos([ambiente["sped"]])
    tela.cartao_cadastro.definir_caminhos([ambiente["rede"] / "clientes.json"])
    tela.cartao_saida.definir_caminhos([ambiente["saida"]])
    esperar(tela, lambda: not tela.lendo_cadastro)


def _textos(widget):
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

def test_modulo_no_menu_fiscal():
    assert registro.SECAO_DO_MODULO["efd_contribuicoes"] == "FISCAL"
    assert registro.NOMES_MODULOS.index("efd_contribuicoes") == registro.NOMES_MODULOS.index("conferencia_iss") + 1
    carregado = next(m for m in registro.carregar_modulos() if m.chave == "efd_contribuicoes")
    assert carregado.ok and carregado.info.nome == "EFD Contribuições"
    assert (RAIZ / "central" / "icones" / f"{carregado.info.icone}.png").exists()
    assert (RAIZ / "modulos" / "efd_contribuicoes" / "INSTRUCOES_DE_USO.md").exists()


def test_tela_so_usa_o_processamento_e_modulo_nao_importa_outro():
    arvore = ast.parse((RAIZ / "modulos" / "efd_contribuicoes" / "telas" / "geracao.py").read_text(encoding="utf-8"))
    do_modulo = {n.module for n in ast.walk(arvore) if isinstance(n, ast.ImportFrom) and n.module
                 and n.module.startswith("modulos.")}
    assert do_modulo == {"modulos.efd_contribuicoes"}
    for arquivo in (RAIZ / "modulos" / "efd_contribuicoes").rglob("*.py"):
        texto = arquivo.read_text(encoding="utf-8")
        for no in ast.walk(ast.parse(texto)):
            if isinstance(no, ast.ImportFrom) and no.module and no.module.startswith("modulos."):
                assert no.module.startswith("modulos.efd_contribuicoes"), (arquivo.name, no.module)
        if arquivo.parent.name != "telas" and arquivo.name != "painel.py":
            assert "customtkinter" not in texto, arquivo.name


# ---------------------------------------------------------------------------
# Cadastro de clientes (escolhido na tela; ajuste de 05/11/2026)
# ---------------------------------------------------------------------------

def test_abre_sem_cadastro_e_com_o_botao_apagado(criar_painel, ambiente):
    tela = _tela(criar_painel)
    assert not tela.cartao_cadastro.preenchido and tela.cadastro is None
    assert not tela.botao.habilitado


def test_cadastro_escolhido_e_lido_e_lembrado(criar_painel, ambiente):
    tela = _tela(criar_painel)
    tela.cartao_cadastro.definir_caminhos([ambiente["rede"] / "clientes.json"])
    esperar(tela, lambda: not tela.lendo_cadastro)
    assert tela.cartao_cadastro.texto_confirmacao == "1 clientes"
    outra = _tela(criar_painel)                                   # abre de novo: o mesmo arquivo, relido
    esperar(outra, lambda: not outra.lendo_cadastro)
    assert outra.cartao_cadastro.caminho == ambiente["rede"] / "clientes.json"
    assert outra.cadastro is not None and len(outra.cadastro.clientes) == 1


def test_cadastro_lembrado_que_sumiu(criar_painel, ambiente):
    tela = _tela(criar_painel)
    tela.cartao_cadastro.definir_caminhos([ambiente["rede"] / "clientes.json"])
    esperar(tela, lambda: not tela.lendo_cadastro)
    (ambiente["rede"] / "clientes.json").unlink()
    outra = _tela(criar_painel)
    esperar(outra, lambda: not outra.lendo_cadastro)
    assert outra.cartao_cadastro.status_confirmacao == "erro"
    assert "não foi encontrado" in outra.cartao_cadastro.texto_confirmacao
    assert outra.cadastro is None


def test_cadastro_ilegivel_fica_vermelho(criar_painel, ambiente):
    (ambiente["rede"] / "clientes.json").write_text("isto não é json", encoding="utf-8")
    tela = _tela(criar_painel)
    tela.cartao_cadastro.definir_caminhos([ambiente["rede"] / "clientes.json"])
    esperar(tela, lambda: not tela.lendo_cadastro)
    assert tela.cartao_cadastro.status_confirmacao == "erro"


def test_criar_cadastro_novo_pelo_sped(criar_painel, ambiente):
    tela = _tela(criar_painel)
    destino = ambiente["rede"] / "novo.json"
    tela.criar_cadastro_do_sped(destino)
    assert tela.mensagens and "Escolha primeiro o SPED" in tela.mensagens[0]
    tela.cartao_sped.definir_caminhos([ambiente["sped"]])
    tela.criar_cadastro_do_sped(destino)
    assert tela.cartao_cadastro.caminho == destino
    assert tela.cartao_cadastro.texto_confirmacao == "2 clientes (cadastro novo: o arquivo é criado ao gerar)"
    assert not destino.exists()                                   # só é gravado ao gerar
    tela.criar_cadastro_do_sped(ambiente["rede"] / "clientes.json")   # não pisa num cadastro que já existe
    assert "Já existe um cadastro" in tela.mensagens[-1]


# ---------------------------------------------------------------------------
# Cartões, competência e geração
# ---------------------------------------------------------------------------

def test_cartoes_e_competencia_sugerida(criar_painel, ambiente):
    ambiente["colocar"](_nota("a.pdf", "1"))
    tela = _tela(criar_painel)
    _preencher(tela, ambiente)
    assert tela.cartao_pdfs.texto_confirmacao == "1 PDF(s) na pasta"
    assert tela.cartao_sped.texto_confirmacao == "SPED de 07/2026 · 2 clientes · 2 notas"
    assert tela.campo_competencia.valor() == "08/2026"
    assert tela.botao.habilitado
    tela.campo_competencia.definir("8/2026")
    assert not tela.botao.habilitado


def test_gera_com_pergunta_e_codigo_ibge(criar_painel, ambiente):
    ambiente["colocar"](
        _nota("a.pdf", "11"),
        _nota("b.pdf", "12", cnpj="33.333.333/0001-91", tomador="CLIENTE NOVO", ibge=None, valor="50.00"),
        _nota("c.pdf", "13", tipo=PF, cnpj="111.111.111-11"),
        _nota("d.pdf", None, status="ERRO: valor total não encontrado"),
    )
    tela = _tela(criar_painel)
    tela.perguntar = lambda texto: tela.perguntas.append(texto) or True
    tela.pedir_codigos_ibge = lambda clientes: {c["cnpj"]: "3543600" for c in clientes}
    _preencher(tela, ambiente)
    tela.processar()
    esperar(tela, lambda: not tela.ocupado and tela.resultado_geracao is not None)
    esperar(tela, lambda: not tela.lendo_cadastro)

    assert len(tela.perguntas) == 1 and "d.pdf" in tela.perguntas[0]
    resultado = tela.resultado_geracao
    assert resultado.erro == "" and resultado.total_receita == Decimal("150.00")
    assert resultado.caminho_sped.name == "SpedEPC_gerado_08_2026.txt"
    assert tela.resultado.selo.cget("text") == "Concluído"
    assert "Cliente novo 2: CLIENTE NOVO (IBGE 3543600, digitado)" in _textos(tela.resultado)
    botoes = {b.cget("text"): b for b in tela.resultado.rodape.winfo_children()}
    assert list(botoes) == ["Abrir pasta", "Abrir Excel", "Ver avisos", "Novo"]
    botoes["Ver avisos"].invoke()
    assert "d.pdf: Fora: não lido" in tela.janela_avisos.texto
    tela.janela_avisos.destroy()
    # o cadastro foi relido: a próxima geração já conhece o cliente novo
    assert tela.cartao_cadastro.texto_confirmacao == "2 clientes"
    assert tela.mensagens == []


def test_responder_nao_cancela_sem_gravar(criar_painel, ambiente):
    ambiente["colocar"](_nota("a.pdf", "11"), _nota("d.pdf", None, status="ERRO: valor total não encontrado"))
    tela = _tela(criar_painel)
    tela.perguntar = lambda texto: False
    _preencher(tela, ambiente)
    tela.processar()
    esperar(tela, lambda: not tela.ocupado)
    assert tela.resultado.selo.cget("text") == "Erro"
    assert not list(ambiente["saida"].iterdir())


def test_cancelar_a_janela_do_ibge_nao_grava(criar_painel, ambiente):
    ambiente["colocar"](_nota("b.pdf", "12", cnpj="33.333.333/0001-91", tomador="CLIENTE NOVO", ibge=None))
    tela = _tela(criar_painel)
    tela.pedir_codigos_ibge = lambda clientes: None
    _preencher(tela, ambiente)
    tela.processar()
    esperar(tela, lambda: not tela.ocupado)
    assert tela.resultado.selo.cget("text") == "Erro"
    assert not list(ambiente["saida"].iterdir())
    assert json.loads((ambiente["rede"] / "clientes.json").read_text(encoding="utf-8")) == {"clientes": CLIENTES}


def test_janela_do_ibge_confere_os_7_numeros(raiz_tk):
    from modulos.efd_contribuicoes.telas.geracao import JanelaCodigosIbge
    janela = JanelaCodigosIbge(raiz_tk, [{"nome": "CLIENTE NOVO", "cnpj": "33333333000191"}])
    janela.campos["33333333000191"].definir("35436")
    janela.confirmar()
    assert janela.respostas is None and "7 números" in janela.mensagem.cget("text")
    janela.campos["33333333000191"].definir("3543600")
    janela.confirmar()
    assert janela.respostas == {"33333333000191": "3543600"}


def test_novo_mantem_o_cadastro_e_a_pasta(criar_painel, ambiente):
    tela = _tela(criar_painel)
    _preencher(tela, ambiente)
    tela.novo()
    assert not tela.cartao_pdfs.preenchido and not tela.cartao_sped.preenchido
    assert tela.cartao_cadastro.caminho == ambiente["rede"] / "clientes.json" and tela.cadastro is not None


def test_pasta_de_saida_lembrada(criar_painel, ambiente):
    tela = _tela(criar_painel)
    tela.cartao_saida.definir_caminhos([ambiente["saida"]])
    outra = _tela(criar_painel)
    assert outra.cartao_saida.caminho == ambiente["saida"]


# ---------------------------------------------------------------------------
# Ajuste de 05/11/2026: incluir à mão as notas fora pelas datas
# ---------------------------------------------------------------------------

def _nota_fora_pela_data(arquivo, numero):
    n = _nota(arquivo, numero)
    n.competencia = "07/2026"                       # competência diferente da emissão (10/08/2026)
    return n


def test_tela_oferece_incluir_as_notas_fora_pelas_datas(criar_painel, ambiente):
    ambiente["colocar"](_nota("a.pdf", "11"), _nota_fora_pela_data("b.pdf", "12"), _nota_fora_pela_data("c.pdf", "13"))
    tela = _tela(criar_painel)
    oferecidas = []
    tela.escolher_notas_para_incluir = lambda itens: oferecidas.extend(i.nota.arquivo for i in itens) or ["b.pdf"]
    _preencher(tela, ambiente)
    tela.processar()
    esperar(tela, lambda: not tela.ocupado and tela.resultado_geracao is not None)
    assert oferecidas == ["b.pdf", "c.pdf"]
    resultado = tela.resultado_geracao
    assert resultado.erro == "" and len(resultado.selecao.no_sped) == 2
    assert "Incluída à mão" in _textos(tela.resultado)


def test_cancelar_a_inclusao_nao_gera(criar_painel, ambiente):
    ambiente["colocar"](_nota("a.pdf", "11"), _nota_fora_pela_data("b.pdf", "12"))
    tela = _tela(criar_painel)
    tela.escolher_notas_para_incluir = lambda itens: None
    _preencher(tela, ambiente)
    tela.processar()
    esperar(tela, lambda: not tela.ocupado)
    assert tela.resultado.selo.cget("text") == "Erro" and not list(ambiente["saida"].iterdir())


def test_janela_de_incluir_notas(raiz_tk):
    from modulos.efd_contribuicoes.selecao import classificar
    from modulos.efd_contribuicoes.telas.geracao import JanelaIncluirNotas
    selecao = classificar([_nota_fora_pela_data("b.pdf", "12"), _nota_fora_pela_data("c.pdf", "13")], "08/2026")
    janela = JanelaIncluirNotas(raiz_tk, selecao.incluiveis)
    assert list(janela.variaveis) == ["b.pdf", "c.pdf"] and not any(v.get() for v in janela.variaveis.values())
    janela.variaveis["c.pdf"].set(True)
    janela.confirmar()
    assert janela.escolhidas == ["c.pdf"]
