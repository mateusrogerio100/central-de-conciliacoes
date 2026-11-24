"""EFD 4 — quais notas entram (4.2), bloqueios e perguntas (4.3), processamento completo e Excel (seção 5).

As notas são fictícias: os PDFs da pasta são arquivos vazios e a leitura é trocada por notas montadas aqui.
O teste com as DANFSe reais (exemplos fora do git) é pulado se elas não existirem.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal

import pytest
from openpyxl import load_workbook

from modulos.efd_contribuicoes import configuracao as cfg
from modulos.efd_contribuicoes import processamento
from modulos.efd_contribuicoes.leitor_danfse import PF, PJ, NotaDanfse
from modulos.efd_contribuicoes.leitor_sped import campos, ler_registros_sped
from modulos.efd_contribuicoes.montagem_sped import conferir_sped
from modulos.efd_contribuicoes.relatorio_excel import ABA_AVISOS, ABA_CLIENTES_NOVOS, ABA_NOTAS
from modulos.efd_contribuicoes.selecao import classificar

D = Decimal
AGORA = datetime(2026, 11, 5, 15, 30)
CLIENTES = [
    {"cod_part": "1", "nome": "CLIENTE FICTICIO UM", "cnpj": "11111111000191", "codigo_ibge": "3516200"},
    {"cod_part": "2", "nome": "CLIENTE FICTICIO DOIS", "cnpj": "22222222000191", "codigo_ibge": "3509502"},
]


def nota(arquivo, numero, valor="100,00", cnpj="11.111.111/0001-91", emissao=date(2026, 9, 10), competencia="09/2026",
         tipo=PJ, ibge="3516200", tomador="CLIENTE FICTICIO UM", status="OK"):
    return NotaDanfse(arquivo=arquivo, numero_nfse=numero, competencia=competencia, data_emissao=emissao,
                      data_emissao_texto=f"{emissao:%d/%m/%Y} 10:00:00", prestador="PRESTADOR FICTICIO",
                      tomador=tomador, doc_tomador=cnpj, tipo_pessoa=tipo, codigo_ibge_tomador=ibge,
                      valor=D(valor.replace(".", "").replace(",", ".")), valor_texto=valor, status=status)


# ---------------------------------------------------------------------------
# Seleção (4.2)
# ---------------------------------------------------------------------------

def test_cada_regra_da_selecao():
    notas = [
        nota("a.pdf", "201"),
        nota("b.pdf", "202", tipo=PF, cnpj="111.111.111-11"),
        nota("c.pdf", "203", competencia="08/2026", emissao=date(2026, 9, 2)),
        nota("d.pdf", "204", competencia="08/2026", emissao=date(2026, 8, 31)),
        nota("e.pdf", None, status="ERRO: número/data não encontrados"),
        nota("f.pdf", "201"),                                             # cópia igual da a.pdf
    ]
    selecao = classificar(notas, "09/2026")
    assert [(n.nota.arquivo, n.situacao) for n in selecao.notas] == [
        ("a.pdf", cfg.SITUACAO_NO_SPED), ("b.pdf", cfg.SITUACAO_PF), ("c.pdf", cfg.SITUACAO_COMPETENCIA),
        ("d.pdf", cfg.SITUACAO_EMISSAO), ("e.pdf", cfg.SITUACAO_NAO_LIDO), ("f.pdf", cfg.SITUACAO_REPETIDA),
    ]
    assert selecao.conflitos == []
    observacoes = {n.nota.arquivo: n.observacao for n in selecao.notas}
    assert observacoes["c.pdf"] == "competência 08/2026, emitida em 02/09/2026"
    assert observacoes["d.pdf"] == "emitida em 31/08/2026, fora de 09/2026"
    assert observacoes["e.pdf"] == "número/data não encontrados"
    assert observacoes["f.pdf"] == "NFS-e 201 repetida: entrou o arquivo a.pdf"


def test_emissao_fora_do_mes_vale_mesmo_com_competencia_igual_a_emissao():
    selecao = classificar([nota("a.pdf", "1", competencia="10/2026", emissao=date(2026, 10, 1))], "09/2026")
    assert selecao.notas[0].situacao == cfg.SITUACAO_EMISSAO


@pytest.mark.parametrize("diferente", [{"valor": "100,01"}, {"cnpj": "22.222.222/0001-91"}])
def test_numero_repetido_com_tomador_ou_valor_diferente_bloqueia(diferente):
    selecao = classificar([nota("a.pdf", "201"), nota("b.pdf", "201", **diferente)], "09/2026")
    assert [n.situacao for n in selecao.notas] == [cfg.SITUACAO_CONFLITO] * 2
    assert selecao.conflitos == ["NFS-e 201 aparece em mais de um PDF com tomador ou valor diferente: a.pdf, b.pdf. "
                                 "Deixe só o PDF certo na pasta e gere de novo."]
    assert selecao.no_sped == []


# ---------------------------------------------------------------------------
# Processamento completo (com leitura trocada por notas fictícias)
# ---------------------------------------------------------------------------

@pytest.fixture
def ambiente(tmp_path, monkeypatch, sped_ficticio, cadastro_fora_da_rede):
    pdfs = tmp_path / "pdfs"
    pdfs.mkdir()
    saida = tmp_path / "saida"
    saida.mkdir()
    (cadastro_fora_da_rede / "clientes.json").write_text(json.dumps({"clientes": CLIENTES}), encoding="utf-8")
    notas: dict[str, NotaDanfse] = {}

    def colocar(*lista):
        for n in lista:
            notas[n.arquivo] = n
            (pdfs / n.arquivo).write_bytes(b"")

    monkeypatch.setattr(processamento, "ler_danfse", lambda caminho: notas[caminho.name])

    def preparar(competencia="09/2026"):
        cadastro = processamento.carregar_cadastro(cadastro_fora_da_rede / "clientes.json")
        return processamento.preparar(pdfs, sped_ficticio, competencia, cadastro)

    return {"pdfs": pdfs, "saida": saida, "colocar": colocar, "preparar": preparar, "rede": cadastro_fora_da_rede}


def test_gera_sped_excel_e_cadastro(ambiente):
    ambiente["colocar"](
        nota("a.pdf", "301", valor="1.000,10"),
        nota("b.pdf", "302", valor="0,20", cnpj="33.333.333/0001-91", tomador="CLIENTE NOVO", ibge="3543600"),
        nota("c.pdf", "303", valor="50,00", tipo=PF, cnpj="111.111.111-11"),
    )
    preparacao = ambiente["preparar"]()
    assert preparacao.bloqueios == [] and preparacao.nao_lidas == [] and preparacao.novos_sem_ibge() == []
    progresso = []
    resultado = processamento.gerar(preparacao, ambiente["saida"], progresso=lambda t, f: progresso.append(t),
                                    agora=AGORA)
    assert resultado.erro == ""
    assert resultado.total_receita == D("1000.30")
    assert resultado.caminho_sped.name == "SpedEPC_gerado_09_2026.txt"
    linhas = ler_registros_sped(resultado.caminho_sped)
    assert conferir_sped(linhas) == []
    assert [campos(l)[1:3] for l in linhas if l.startswith("|0150|")][-1] == ["3", "CLIENTE NOVO"]
    assert "|M400|07|1000,3|||" in linhas
    assert resultado.caminho_sped.read_bytes().endswith(b"|9999|" + str(len(linhas)).encode() + b"|\r\n")

    # cadastro na rede: cliente novo gravado, cópia do anterior
    gravado = json.loads((ambiente["rede"] / "clientes.json").read_text(encoding="utf-8"))["clientes"]
    assert [c["cod_part"] for c in gravado] == ["1", "2", "3"]
    assert resultado.caminho_copia_cadastro == ambiente["rede"] / "copias" / "clientes_2026-11-05_15h30.json"

    # Excel de conferência
    assert resultado.caminho_excel.name == "Conferencia_EFD_09_2026_15h30.xlsx"
    livro = load_workbook(resultado.caminho_excel)
    assert livro.sheetnames == [ABA_NOTAS, ABA_CLIENTES_NOVOS, ABA_AVISOS]
    notas = list(livro[ABA_NOTAS].iter_rows(min_row=2, max_row=4, values_only=True))
    assert [(n[0], n[8]) for n in notas] == [("301", cfg.SITUACAO_NO_SPED), ("302", cfg.SITUACAO_NO_SPED),
                                             ("303", cfg.SITUACAO_PF)]
    assert livro[ABA_NOTAS]["D6"].value == "No SPED (2)" and livro[ABA_NOTAS]["H6"].value == pytest.approx(1000.30)
    assert livro[ABA_NOTAS]["D7"].value == "PF (1)"
    assert list(livro[ABA_CLIENTES_NOVOS].iter_rows(min_row=2, values_only=True)) == [
        ("3", "CLIENTE NOVO", "33333333000191", "3543600", "PDF")]
    assert progresso[-1] == "Concluído."


def test_sem_cliente_novo_o_cadastro_nao_e_regravado(ambiente):
    ambiente["colocar"](nota("a.pdf", "301"))
    resultado = processamento.gerar(ambiente["preparar"](), ambiente["saida"], agora=AGORA)
    assert resultado.erro == "" and resultado.caminho_copia_cadastro is None
    assert not (ambiente["rede"] / "copias").exists()


def test_pdf_nao_lido_precisa_de_resposta(ambiente):
    ambiente["colocar"](nota("a.pdf", "301"), nota("b.pdf", None, status="ERRO: valor total não encontrado"))
    preparacao = ambiente["preparar"]()
    assert [n.nota.arquivo for n in preparacao.nao_lidas] == ["b.pdf"]
    nao = processamento.gerar(preparacao, ambiente["saida"], aceitar_nao_lidas=False, agora=AGORA)
    assert nao.erro.startswith("Geração cancelada") and not list(ambiente["saida"].iterdir())
    sim = processamento.gerar(preparacao, ambiente["saida"], aceitar_nao_lidas=True, agora=AGORA)
    assert sim.erro == "" and sim.caminho_sped is not None


def test_cliente_novo_sem_ibge_bloqueia_ate_digitar(ambiente):
    ambiente["colocar"](nota("a.pdf", "301", cnpj="33.333.333/0001-91", tomador="CLIENTE NOVO", ibge=None))
    preparacao = ambiente["preparar"]()
    assert [c["cod_part"] for c in preparacao.novos_sem_ibge()] == ["3"]
    sem = processamento.gerar(preparacao, ambiente["saida"], agora=AGORA)
    assert "sem Código IBGE" in sem.erro and not list(ambiente["saida"].iterdir())
    assert "3" not in [c["cod_part"] for c in processamento.carregar_cadastro(ambiente["rede"] / "clientes.json").clientes.values()]  # rede intacta
    preparacao.cadastro.definir_ibge("33333333000191", "3543600")
    com = processamento.gerar(preparacao, ambiente["saida"], agora=AGORA)
    assert com.erro == "" and com.clientes_novos[0][1] == "digitado"


def test_conflito_e_nenhuma_nota_bloqueiam(ambiente):
    ambiente["colocar"](nota("a.pdf", "301"), nota("b.pdf", "301", valor="5,00"))
    preparacao = ambiente["preparar"]()
    resultado = processamento.gerar(preparacao, ambiente["saida"], agora=AGORA)
    assert "aparece em mais de um PDF" in resultado.erro and not list(ambiente["saida"].iterdir())


def test_so_pf_nao_gera(ambiente):
    ambiente["colocar"](nota("a.pdf", "301", tipo=PF, cnpj="111.111.111-11"))
    assert processamento.gerar(ambiente["preparar"](), ambiente["saida"]).erro.startswith("Nenhuma nota para o SPED")


def test_outra_pessoa_gravou_o_cadastro_no_meio(ambiente):
    ambiente["colocar"](nota("a.pdf", "301", cnpj="33.333.333/0001-91", tomador="CLIENTE NOVO", ibge="3543600"))
    preparacao = ambiente["preparar"]()
    (ambiente["rede"] / "clientes.json").write_text(json.dumps({"clientes": CLIENTES[:1]}), encoding="utf-8")
    resultado = processamento.gerar(preparacao, ambiente["saida"], agora=AGORA)
    assert "outra pessoa" in resultado.erro and not list(ambiente["saida"].iterdir())


def test_sped_existente_nao_e_sobrescrito(ambiente):
    ambiente["colocar"](nota("a.pdf", "301"))
    (ambiente["saida"] / "SpedEPC_gerado_09_2026.txt").write_text("anterior")
    resultado = processamento.gerar(ambiente["preparar"](), ambiente["saida"], agora=AGORA)
    assert resultado.caminho_sped.name == "SpedEPC_gerado_09_2026_2.txt"
    assert (ambiente["saida"] / "SpedEPC_gerado_09_2026.txt").read_text() == "anterior"


@pytest.mark.parametrize("competencia", ["9/2026", "13/2026", "09-2026", ""])
def test_competencia_invalida(ambiente, competencia):
    assert ambiente["preparar"](competencia).bloqueios == ["Competência inválida: use MM/AAAA (ex.: 09/2026)."]


def test_cadastro_vazio(ambiente):
    (ambiente["rede"] / "clientes.json").write_text('{"clientes": []}', encoding="utf-8")
    preparacao = ambiente["preparar"]()
    assert "está vazio" in preparacao.bloqueios[0]


# ---------------------------------------------------------------------------
# Com as DANFSe reais de agosto (exemplos fora do git)
# ---------------------------------------------------------------------------

def test_danfse_reais_de_agosto(tmp_path, cadastro_fora_da_rede):
    from testes.efd_contribuicoes.conftest import exemplo_efd
    pdfs = exemplo_efd("danfse")
    (cadastro_fora_da_rede / "clientes.json").write_bytes(exemplo_efd("clientes.json").read_bytes())
    cadastro = processamento.carregar_cadastro(cadastro_fora_da_rede / "clientes.json")
    preparacao = processamento.preparar(pdfs, exemplo_efd("sped_original_2026-08.txt"), "08/2026", cadastro)
    assert preparacao.bloqueios == [] and preparacao.nao_lidas == []
    assert [n.situacao for n in preparacao.selecao.notas] == [cfg.SITUACAO_NO_SPED] * 3 + [cfg.SITUACAO_PF] * 2
    resultado = processamento.gerar(preparacao, tmp_path, agora=AGORA)
    assert resultado.erro == ""
    assert resultado.total_receita == D("1850.61") + D("30017.71") + D("2462.29")
    assert conferir_sped(ler_registros_sped(resultado.caminho_sped)) == []


# ---------------------------------------------------------------------------
# Ajustes de 05/11/2026: incluir à mão as notas fora pelas datas; prestador com CNPJ diferente
# ---------------------------------------------------------------------------

def test_so_as_notas_fora_pelas_datas_podem_ser_incluidas():
    from modulos.efd_contribuicoes.selecao import incluir
    notas = [
        nota("a.pdf", "201"),
        nota("b.pdf", "202", tipo=PF, cnpj="111.111.111-11"),
        nota("c.pdf", "203", competencia="08/2026", emissao=date(2026, 9, 2)),
        nota("d.pdf", "204", competencia="08/2026", emissao=date(2026, 8, 31)),
        nota("f.pdf", "201"),
    ]
    selecao = classificar(notas, "09/2026")
    assert [n.nota.arquivo for n in selecao.incluiveis] == ["c.pdf", "d.pdf"]
    incluidas = incluir(selecao, ["b.pdf", "c.pdf", "f.pdf"])          # PF e repetida não entram
    assert [n.nota.arquivo for n in incluidas] == ["c.pdf"]
    c = next(n for n in selecao.notas if n.nota.arquivo == "c.pdf")
    assert c.situacao == cfg.SITUACAO_INCLUIDA and c.no_sped
    assert c.observacao == "competência ≠ emissão: competência 08/2026, emitida em 02/09/2026 — incluída à mão"
    assert [n.nota.arquivo for n in selecao.no_sped] == ["a.pdf", "c.pdf"]


def test_incluir_notas_entra_no_sped_e_no_excel(ambiente):
    ambiente["colocar"](
        nota("a.pdf", "301"),
        nota("c.pdf", "303", valor="40,00", competencia="08/2026", emissao=date(2026, 9, 2)),
        nota("d.pdf", "304", valor="7,00", cnpj="33.333.333/0001-91", tomador="CLIENTE NOVO", ibge="3543600",
             competencia="08/2026", emissao=date(2026, 8, 31)),
    )
    preparacao = ambiente["preparar"]()
    assert [n.nota.arquivo for n in preparacao.incluiveis] == ["c.pdf", "d.pdf"]
    assert processamento.incluir_notas(preparacao, ["c.pdf", "d.pdf"]) == 2
    resultado = processamento.gerar(preparacao, ambiente["saida"], agora=AGORA)
    assert resultado.erro == "" and resultado.total_receita == D("147.00")
    assert [c["cod_part"] for c, _ in resultado.clientes_novos] == ["3"]
    linhas = ler_registros_sped(resultado.caminho_sped)
    assert "|A100|1|0|3|00|||304||31082026|31082026|7|0||7|0|7|0||||" in linhas     # data como está na nota
    assert any("c.pdf: No SPED (incluída à mão)" in a for a in resultado.avisos)
    livro = load_workbook(resultado.caminho_excel)
    situacoes = [r[8] for r in livro[ABA_NOTAS].iter_rows(min_row=2, max_row=4, values_only=True)]
    assert situacoes == [cfg.SITUACAO_NO_SPED, cfg.SITUACAO_INCLUIDA, cfg.SITUACAO_INCLUIDA]
    assert livro[ABA_NOTAS]["D6"].value == "No SPED (3)"


def test_todas_fora_pelas_datas_e_incluidas_gera(ambiente):
    ambiente["colocar"](nota("c.pdf", "303", competencia="08/2026", emissao=date(2026, 9, 2)))
    preparacao = ambiente["preparar"]()
    assert preparacao.bloqueios == []
    assert processamento.gerar(preparacao, ambiente["saida"]).erro.startswith("Nenhuma nota para o SPED")
    processamento.incluir_notas(preparacao, ["c.pdf"])
    assert processamento.gerar(preparacao, ambiente["saida"], agora=AGORA).erro == ""


def test_prestador_com_cnpj_diferente_vira_aviso(ambiente):
    ambiente["colocar"](nota("a.pdf", "301"), nota("b.pdf", "302"), nota("z.pdf", "309"))
    ambiente["colocar"](NotaDanfse(**{**nota("z.pdf", "309").__dict__, "doc_prestador": "99.999.999/0001-91",
                                      "prestador": "OUTRO PRESTADOR"}))
    for arquivo in ("a.pdf", "b.pdf"):
        n = nota(arquivo, "301" if arquivo == "a.pdf" else "302")
        n.doc_prestador = "00.000.000/0001-91"
        ambiente["colocar"](n)
    preparacao = ambiente["preparar"]()
    assert preparacao.avisos_prestador == [
        "z.pdf: prestador com CNPJ 99.999.999/0001-91 (OUTRO PRESTADOR), diferente do CNPJ 00.000.000/0001-91 dos "
        "outros 2 PDF(s). Confira se a nota é mesmo da Fundação."]
    resultado = processamento.gerar(preparacao, ambiente["saida"], agora=AGORA)
    assert resultado.erro == "" and resultado.avisos[0] == preparacao.avisos_prestador[0]
    assert len(resultado.selecao.no_sped) == 3                        # é só aviso: a nota continua no SPED
    linha_z = list(load_workbook(resultado.caminho_excel)[ABA_NOTAS].iter_rows(min_row=4, max_row=4, values_only=True))[0]
    assert linha_z[10] == "99.999.999/0001-91"
