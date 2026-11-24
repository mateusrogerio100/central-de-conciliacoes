"""V1 — leitura do PDF de eventos da folha (ESPECIFICACAO_CREDITO_ESTOURO.md, seções 2.1, 3.1 e 8).

Os textos sintéticos usam nomes fictícios; os testes com os PDFs reais (exemplos\\credito_estouro\\, fora do git)
são pulados quando a pasta não existe.
"""

from decimal import Decimal as D
from pathlib import Path

import pytest

from modulos.credito_estouro.leitor_eventos import ERRO_NAO_EH_EVENTOS, ler_eventos, ler_eventos_do_texto
from modulos.credito_estouro.modelos import LeituraEventos

PASTA_EXEMPLOS = Path(__file__).resolve().parents[2] / "exemplos" / "credito_estouro"


def _topo(pagina, titulo="EVENTOS 05/2026 C/IDENT"):
    return (f"0001 -FUNDAÇÃO TESTE DE MISER. DE EXEMPLO Pág.: {pagina}\n{titulo}\n"
            "Período: 05/2026 a 05/2026 Tipo: Cálculo Mensal\n"
            "Evento Colaborador SIT Competência Pagamento Referência Valor\n")


PAGINAS = [
    _topo(1)
    + "0241-Reembolso Debito Afastado\n"
      "101 ANA PESSOA FICTICIA 003 05/2026 05/06/2026 0,00 300,00\n"
      "102BRUNO MODELO TESTE 003 05/2026 05/06/2026 0,00 150,50\n"
      "Total de Colaboradores: 02 0,00 450,50\n"
      "0256-Cred. Estouro do Mes\n"
      "101 ANA PESSOA FICTICIA 003 05/2026 05/06/2026 0,00 1.200,00\n"
      "103 CARLA EXEMPLO 008 05/2026 05/06/2026 0,00 80,00\n"
      "FPRF404.OPE - 08/06/2026 - 14:54:02 FUNDAÇÃO TESTE\n1",
    _topo(2)
    + "104 DANIEL QUALQUER 008 05/2026 05/06/2026 0,00 20,00\n"
      "Total de Colaboradores: 03 0,00 1.300,00\n"
      "0258-Deb. Estouro Mes Anterior\n"
      "103 CARLA EXEMPLO 008 05/2026 05/06/2026 0,00 75,00\n"
      "Total de Colaboradores: 01 0,00 75,00\n"
      "0264-Liquido Rescisao\n"
      "555 NAO ENTRA AQUI 007 05/2026 05/06/2026 0,00 999,00\n"
      "Total de Colaboradores: 01 0,00 999,00\n"
      "1204-Deb. Estouro Parcelado\n"
      "105 ELISA PARCELADA 008 05/2026 05/06/2026 0,00 140,02\n"
      "Total de Colaboradores: 01 0,00 140,02\n"
      "0775-Devolucao Credito Estouro\n"
      "106 FABIO DEVOLVIDO 008 05/2026 05/06/2026 0,00 33,00\n"
      "Total de Colaboradores: 01 0,00 33,00\n"
      "FPRF404.OPE - 08/06/2026 - 14:54:02 FUNDAÇÃO TESTE\n2",
]


def _ler(paginas):
    return ler_eventos_do_texto(list(paginas), LeituraEventos(arquivo="eventos.pdf"))


def test_le_os_cinco_eventos_e_ignora_os_outros():
    leitura = _ler(PAGINAS)
    assert leitura.erro is None
    assert leitura.avisos == []
    assert leitura.unidade == "FUNDAÇÃO TESTE DE MISER. DE EXEMPLO"
    assert (leitura.competencia.year, leitura.competencia.month) == (2026, 5)
    assert leitura.tipo == "Cálculo Mensal"
    assert {e: (leitura.quantidade(e), leitura.total(e)) for e in ("0241", "0256", "0258", "1204", "0775")} == {
        "0241": (2, D("450.50")), "0256": (3, D("1300.00")), "0258": (1, D("75.00")),
        "1204": (1, D("140.02")), "0775": (1, D("33.00"))}
    assert all(l.matricula != "555" for l in leitura.linhas)          # o 0264 não entra


def test_bloco_atravessa_pagina_e_matricula_grudada_no_nome():
    leitura = _ler(PAGINAS)
    assert [(l.matricula, l.nome, l.valor, l.pagina) for l in leitura.do_evento("0256")] == [
        ("101", "ANA PESSOA FICTICIA", D("1200.00"), 1), ("103", "CARLA EXEMPLO", D("80.00"), 1),
        ("104", "DANIEL QUALQUER", D("20.00"), 2)]
    assert leitura.do_evento("0241")[1].matricula == "102"
    assert leitura.do_evento("0241")[1].nome == "BRUNO MODELO TESTE"
    assert leitura.do_evento("0241")[0].data_pagamento.isoformat() == "2026-06-05"


def test_por_matricula_soma_quem_aparece_duas_vezes():
    paginas = [PAGINAS[0].replace("103 CARLA EXEMPLO 008", "101 ANA PESSOA FICTICIA 008"), PAGINAS[1]]
    assert _ler(paginas).por_matricula("0256") == {"101": D("1280.00"), "104": D("20.00")}


def test_titulo_no_singular():
    """Desde out/2026 o Tasy imprime "EVENTO 102026 C/IDENT 1676" (sem o S) no topo de cada página."""
    paginas = [p.replace("EVENTOS 05/2026 C/IDENT", "EVENTO 052026 C/IDENT 1676") for p in PAGINAS]
    leitura = _ler(paginas)
    assert leitura.erro is None
    assert leitura.avisos == []
    assert leitura.quantidade("0256") == 3


def test_total_que_nao_bate_vira_atencao():
    paginas = [PAGINAS[0], PAGINAS[1].replace("0,00 1.300,00", "0,00 1.399,00")]
    avisos = [a.mensagem for a in _ler(paginas).avisos]
    assert len(avisos) == 1 and avisos[0].startswith("ATENÇÃO") and "0256" in avisos[0]


def test_linha_nao_reconhecida_vira_aviso():
    paginas = [PAGINAS[0].replace("103 CARLA EXEMPLO 008 05/2026", "103 CARLA EXEMPLO 05/2026"), PAGINAS[1]]
    avisos = [a.mensagem for a in _ler(paginas).avisos]
    assert any("não reconhecida" in a for a in avisos)
    assert any("ATENÇÃO" in a for a in avisos)          # e a soma deixa de bater: nada some em silêncio


def test_nome_comprido_que_invade_a_coluna_sit():
    paginas = [_topo(1) + "0256-Cred. Estouro do Mes\n"
               "105 IRENE SOUZA CAMPOS FICTICIA MODELO TE0L08 05/2026 05/06/2026 0,00 10,00\n"
               "Total de Colaboradores: 01 0,00 10,00\n"]
    leitura = _ler(paginas)
    assert [(l.matricula, l.nome) for l in leitura.linhas] == [("105", "IRENE SOUZA CAMPOS FICTICIA MODELO TEL")]
    assert leitura.avisos == []


def test_pdf_sem_os_eventos_e_arquivo_que_nao_e_eventos():
    sem = _ler([_topo(1) + "0264-Liquido Rescisao\nTotal de Colaboradores: 00 0,00 0,00"])
    assert "nenhum dos eventos" in sem.erro
    assert _ler(["Razão\nPeríodo: 01/05/2026 até: 31/05/2026"]).erro == ERRO_NAO_EH_EVENTOS


def test_arquivo_que_nao_e_pdf(tmp_path):
    planilha = tmp_path / "eventos.xlsx"
    planilha.write_bytes(b"PK\x03\x04qualquer coisa")
    assert ler_eventos(planilha).erro == ERRO_NAO_EH_EVENTOS


# ---------------------------------------------------------------------
# PDFs reais (seção 2.1)
# ---------------------------------------------------------------------
REAIS = {
    "2026-04": {"0256": (128, D("95595.35")), "0258": (140, D("89798.31")), "0241": (20, D("10453.39")),
                "1204": (3, D("909.35")), "0775": (0, D("0.00"))},
    "2026-05": {"0256": (147, D("96906.08")), "0258": (120, D("89271.55")), "0241": (25, D("16440.61")),
                "1204": (3, D("909.35")), "0775": (0, D("0.00"))},
    "2026-06": {"0256": (164, D("111708.31")), "0258": (140, D("92446.15")), "0241": (22, D("13481.23")),
                "1204": (3, D("854.20")), "0775": (0, D("0.00"))},
}


@pytest.mark.skipif(not PASTA_EXEMPLOS.exists(), reason="exemplos reais fora do git")
@pytest.mark.parametrize("mes", sorted(REAIS))
def test_pdfs_reais_batem_com_o_total_de_cada_evento(mes):
    pdf = next((PASTA_EXEMPLOS / mes).glob("EVENTOS*"))
    leitura = ler_eventos(pdf)
    assert leitura.erro is None
    assert leitura.avisos == []
    assert leitura.unidade.startswith("FUNDAÇÃO HOSPITAL EXEMPLO")
    assert f"{leitura.competencia:%Y-%m}" == mes
    assert {e: (leitura.quantidade(e), leitura.total(e)) for e in REAIS[mes]} == REAIS[mes]


@pytest.mark.skipif(not PASTA_EXEMPLOS.exists(), reason="exemplos reais fora do git")
def test_varios_pdfs_do_mes_o_0775_vem_separado():
    from modulos.credito_estouro.leitor_eventos import ler_varios

    eventos = next((PASTA_EXEMPLOS / "2026-07").glob("EVENTOS*"))
    pdf_0775 = next((PASTA_EXEMPLOS / "2026-07").glob("EVENTO 775*"))
    junto = ler_varios([eventos, pdf_0775])
    assert junto.erro is None and junto.avisos == []
    assert (junto.quantidade("0256"), junto.quantidade("0775"), junto.total("0775")) == (206, 1, D("441.65"))
    repetido = ler_varios([eventos, pdf_0775, pdf_0775])
    assert repetido.quantidade("0775") == 1 and "repetido" in repetido.avisos[0].mensagem
    # decisão de 16/11/2026: o 0775 entra no mês em que foi lançado no razão; o PDF pode ser de um mês anterior
    junho_0775 = next((PASTA_EXEMPLOS / "2026-06").glob("EVENTO 775*"))
    com_junho = ler_varios([junho_0775, eventos])
    assert com_junho.erro is None and f"{com_junho.competencia:%Y-%m}" == "2026-07"
    assert (com_junho.quantidade("0256"), com_junho.total("0775")) == (206, D("810.50"))
    assert "PDF do 0775 de 06/2026" in com_junho.avisos[0].mensagem
    eventos_junho = next((PASTA_EXEMPLOS / "2026-06").glob("EVENTOS*"))
    assert "depois do mês do relatório" in ler_varios([eventos_junho, pdf_0775]).erro      # 0775 de um mês depois
    assert "meses diferentes" in ler_varios([eventos, eventos_junho]).erro                  # dois relatórios
    assert ler_varios(eventos).quantidade("0256") == 206                  # um só (sem lista) também vale
