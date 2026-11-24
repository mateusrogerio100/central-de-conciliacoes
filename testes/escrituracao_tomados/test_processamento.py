"""Etapa Tomados 5: processamento completo (processamento.gerar) e relatório Excel.

- T1, T2 e T3 pelo caminho completo: arquivos byte a byte, números do resumo e relatório.
- T6: um lote fictício com todos os casos especiais, do começo ao fim.
- Andamento, pergunta antes de substituir, arquivo que não pode ser gravado.
A consulta de CNPJ é sempre simulada e o %APPDATA% é temporário (conftest.py).
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import openpyxl
import pytest

from modulos.escrituracao_tomados import gerador_txt, layout_v3, processamento
from modulos.escrituracao_tomados.modelos import Competencia, Destino
from testes.conftest import caso_real, pasta_exemplos

MATRIZ = "98765432000198"
AGOSTO = Competencia(2026, 8)
ABAS = ["Notas", "Lançar à mão", "Falar com o fornecedor", "Corrigir número no site",
        "Arquivos gerados", "Divergências", "Avisos"]


def sem_consulta(cnpj):
    raise AssertionError(f"não devia consultar o CNPJ {cnpj}")


def _esperado(nome) -> bytes:
    return (pasta_exemplos("escrituracao_tomados", "esperado") / nome).read_bytes()


def _pdfs():
    return pasta_exemplos("escrituracao_tomados", "2026-08", "pdfs")


def _linhas_da_aba(caminho, aba):
    livro = openpyxl.load_workbook(caminho)
    return [list(linha) for linha in livro[aba].iter_rows(min_row=2, values_only=True)]


# ---------------------------------------------------------------------------
# T1, T2, T3 pelo caminho completo
# ---------------------------------------------------------------------------


def test_t1_so_pdfs(tmp_path):
    saida = tmp_path / "saida"
    r = processamento.gerar(pasta_pdfs=_pdfs(), tipo_referencia="C",
                            data_lancamento=date(2026, 9, 28), pasta_saida=saida,
                            consultar_cnpj=sem_consulta)
    assert (saida / "tomados_98765432000198_08-2026.txt").read_bytes() == \
        _esperado("teste1_tomados_98765432000198_08-2026.txt")
    # as notas 229/230 (emitidas em 08, competência 07) vai para "lançar à mão" (V17)
    assert not (saida / "tomados_98765432000198_07-2026.txt").exists()
    assert (r.notas_no_arquivo, r.lancar_a_mao, r.nao_incluidas) == (12, 2, 6)
    assert (r.ja_escrituradas, r.canceladas, r.erros_de_leitura) == (0, 0, 0)
    assert not r.cancelado and r.erro_relatorio == ""
    # a única conferência em laranja é o lembrete de corrigir o número no site (R8)
    assert [c.descricao for c in r.conferencias if not c.ok] == [
        "1 nota(s) com número ajustado aos 8 últimos dígitos: depois de importar, corrigir o "
        "número no site"]

    livro = openpyxl.load_workbook(r.caminho_relatorio)
    assert livro.sheetnames == ABAS
    notas = _linhas_da_aba(r.caminho_relatorio, "Notas")
    assert len(notas) == 20                                  # todo PDF aparece
    incluidas = [l for l in notas if l[0] == "INCLUÍDA"]
    assert {l[19] for l in incluidas} == {"tomados_98765432000198_08-2026.txt"}
    nota_337 = next(l for l in notas if l[7] == "337")
    assert (nota_337[12], nota_337[15], nota_337[16], nota_337[17]) == (13943.28, 278.87, "Z", "001")

    a_mao = _linhas_da_aba(r.caminho_relatorio, "Lançar à mão")
    assert sorted(l[1] for l in a_mao) == ["229", "230"]
    assert all("competência 07/2026" in l[0] for l in a_mao)
    (coop,) = _linhas_da_aba(r.caminho_relatorio, "Corrigir número no site")
    assert coop[:3] == ["90", "2026000000090",
                        caso_real("escrituracao_tomados", "prestador_nota_2026000000090")]
    assert (coop[5], coop[6], coop[8]) == (5369.58, "08/2026", "tomados_98765432000198_08-2026.txt")
    coop_notas = next(l for l in notas if l[7] == "2026000000090")
    assert coop_notas[0] == "INCLUÍDA" and "corrigir no site para 2026000000090" in coop_notas[1]
    arquivos = _linhas_da_aba(r.caminho_relatorio, "Arquivos gerados")
    assert [(a[2], a[5], a[6], a[8]) for a in arquivos] == [("08/2026", 12, 26757.53, 595.26)]

    # R19: Não Optante sem federal retido (a cooperativa da 2026000000090 retém PIS/COFINS/CSLL; as notas em que
    # a Fundação é a prestadora e a cópia duplicada da 249 ficam de fora)
    falar = _linhas_da_aba(r.caminho_relatorio, "Falar com o fornecedor")
    assert [l[2] for l in falar] == ["337", "542", "29555", "29556", "29670", "29671", "249"]
    assert falar[0][:7] == [*caso_real("escrituracao_tomados", "prestador_nota_337"), "337", "13/08/2026",
                            "08/2026", 13943.28, "04.01.01 - Medicina."]
    assert falar[0][9:15] == ["Não Retido", 0, 0, 0, "Código 0", "INCLUÍDA"]
    assert falar[0][17] is None                                  # "Retorno do fornecedor"
    marcadas = {l[7] for l in notas if l[27] == "SIM"}
    assert marcadas == {l[2] for l in falar}
    coop_notas = next(l for l in notas if l[7] == "2026000000090")
    assert (coop_notas[23:27], coop_notas[27]) == ([0, 0, 195.99, "Código 4"], None)


def test_t2_pdfs_com_resultados(tmp_path):
    resultados = sorted(pasta_exemplos("escrituracao_tomados", "2026-08",
                                       "resultados_prefeitura").glob("*.csv"))
    r = processamento.gerar(pasta_pdfs=_pdfs(), resultados=resultados, tipo_referencia="C",
                            data_lancamento=date(2026, 9, 24), pasta_saida=tmp_path,
                            consultar_cnpj=sem_consulta)
    assert [a.caminho.name for a in r.arquivos] == ["tomados_98765432000198_08-2026.txt"]
    assert r.arquivos[0].caminho.read_bytes() == \
        _esperado("teste2_tomados_98765432000198_08-2026.txt")
    assert (r.notas_no_arquivo, r.lancar_a_mao, r.ja_escrituradas) == (6, 0, 8)
    assert r.nao_incluidas == 8 + 5 + 1
    assert any(c.descricao == "Resultados da prefeitura lidos" and c.ok for c in r.conferencias)


def test_t3_unificar_exportacoes(tmp_path):
    lotes = pasta_exemplos("escrituracao_tomados", "2026-08", "exportacoes_lotes")
    cadastro = tmp_path / "prestadores.json"
    shutil.copy(pasta_exemplos("escrituracao_tomados", "esperado")
                / "cadastro_prestadores_teste.json", cadastro)
    r = processamento.gerar(exportacoes=[lotes / "lote_249.txt", lotes / "lote_337_118.txt"],
                            cnpj_tomador="98.765.432/0001-98", competencia=AGOSTO,
                            tipo_referencia="N", data_lancamento=date(2026, 9, 30),
                            pasta_saida=tmp_path / "saida", consultar_cnpj=sem_consulta,
                            caminho_cadastro=cadastro)
    assert r.arquivos[0].caminho.read_bytes() == \
        _esperado("teste3_unificado_98765432000198_08-2026.txt")
    unificacao = next(c for c in r.conferencias if c.descricao.startswith("Unificação"))
    assert unificacao.ok, unificacao.detalhe
    assert r.tudo_certo


# ---------------------------------------------------------------------------
# T6: casos especiais, do começo ao fim (lote fictício)
# ---------------------------------------------------------------------------

CABECALHO = ("cfps;nfs;situacaonf;cnpjcpf;nome;dtemissao;descratividade;vlrservicos;"
             "vlrdeducoes;descontoincondicionado;basecalculo;aliquota;impretido;vlrimposto;"
             "enquadradosn;")
NOME_LONGO = "Clínica Médica São José & Irmãos " * 4          # mais de 100 caracteres


def _linha(numero, documento="11.111.111/0001-91", nome="PRESTADOR UM", cfps="1",
           situacao="Normal", servico="1.000,00", desconto="", retido="NÃO", iss="20,00",
           regime="N"):
    return (f"{cfps};{numero};{situacao};{documento};{nome};05/08/2026;04.01.01  Medicina.;"
            f"{servico};0,00;{desconto};{servico};2,00;{retido};{iss};{regime};")


def _lote_t6(tmp_path) -> Path:
    linhas = [
        _linha("10"),                                                   # normal, Cidade Alfa
        _linha("11", documento="123.456.789-09", nome="JOSÉ DA SILVA"),  # CPF
        _linha("12", regime="M"),                                       # MEI
        _linha("13", desconto="57,03"),                                 # desconto -> à mão
        _linha("14", retido="M", iss="0,00"),                           # retido M -> à mão
        _linha("2026000000090"),                                        # > 8 dígitos
        _linha("15", situacao="Cancelada"),                             # fora
        _linha("16", documento="22.222.222/0001-91", nome=NOME_LONGO),  # nome longo, acentos, &
        _linha("17", documento="33.333.333/0001-91", nome="SEM CIDADE", cfps="2"),
    ]
    caminho = tmp_path / "lote_t6.csv"
    caminho.write_bytes(("\r\n".join([CABECALHO] + linhas) + "\r\n").encode("latin-1"))
    return caminho


def _cadastro_t6(tmp_path) -> Path:
    caminho = tmp_path / "prestadores.json"
    caminho.write_text('{"11111111000191": {"cidade": "CIDADE ALFA", "uf": "SP"},'
                       ' "12345678909": {"cidade": "CIDADE ALFA", "uf": "SP"},'
                       ' "22222222000191": {"cidade": "CIDADE BETA", "uf": "SP"}}',
                       encoding="utf-8")
    return caminho


def _gerar_t6(tmp_path, cnpj_tomador=MATRIZ, perguntas=None):
    perguntas = [] if perguntas is None else perguntas

    def perguntar(documento, nome):
        perguntas.append(documento)
        return "Uberaba", "MG"

    def consulta_falha(cnpj):
        raise OSError("sem internet (simulado)")

    return processamento.gerar(exportacoes=[_lote_t6(tmp_path)], cnpj_tomador=cnpj_tomador,
                               competencia=AGOSTO, tipo_referencia="N",
                               data_lancamento=date(2026, 9, 30),
                               pasta_saida=tmp_path / "saida", perguntar_cidade=perguntar,
                               consultar_cnpj=consulta_falha,
                               caminho_cadastro=_cadastro_t6(tmp_path))


def test_t6_casos_especiais(tmp_path):
    perguntas = []
    r = _gerar_t6(tmp_path, perguntas=perguntas)
    destino = {n.numero: n for n in r.notas}
    assert {k for k, n in destino.items() if n.destino is Destino.INCLUIDA} == \
        {"10", "11", "12", "16", "17", "2026000000090"}
    assert {k for k, n in destino.items() if n.destino is Destino.LANCAR_A_MAO} == {"13", "14"}
    assert destino["15"].motivo == "nota cancelada"
    assert destino["2026000000090"].numero_arquivo == "00000090"        # R8
    assert destino["14"].codigo_retido == ""                    # a pessoa decide ao digitar
    assert perguntas == ["33333333000191"]                      # só quem não tinha cidade
    assert (destino["17"].prestador_cidade, destino["17"].codigo_retido) == ("UBERABA", "Z")

    (arquivo,) = r.arquivos
    conteudo = arquivo.caminho.read_bytes().decode("latin-1")
    assert gerador_txt.conferir_conteudo(conteudo) == []
    detalhes = conteudo.split("\r\n")[1:-2]
    assert len(detalhes) == 6 and all(len(l) == 350 for l in detalhes)
    assert [l[178:186].lstrip("0") for l in detalhes] == ["10", "11", "12", "16", "17", "90"]
    tipo_id = {l[178:186].lstrip("0"): l[1] for l in detalhes}
    assert tipo_id["11"] == "2" and tipo_id["10"] == "1"         # CPF = tipo 2
    regime = {l[178:186].lstrip("0"): l[254] for l in detalhes}
    assert regime["12"] == "M"
    longo = next(l for l in detalhes if l[178:186].lstrip("0") == "16")
    assert longo[16:116] == gerador_txt.normalizar_texto(NOME_LONGO)[:100]
    assert "&" in longo[16:116] and "SAO JOSE" in longo[16:116]
    trailler = conteudo.split("\r\n")[-2]
    assert trailler[1:5] == "0006" and trailler[5:19] == "00000000600000"

    lancar = _linhas_da_aba(r.caminho_relatorio, "Lançar à mão")
    assert sorted(l[1] for l in lancar) == ["13", "14"]
    retido_14 = next(l for l in lancar if l[1] == "14")[13]
    assert retido_14 == "conferir (site: M)"
    nota_13 = next(l for l in lancar if l[1] == "13")                 # textos da tela do site
    assert (nota_13[3], nota_13[4], nota_13[9], nota_13[11], nota_13[13]) == (
        "Serviço prestado no município de Cidade Alfa", "04.01.01", "Não", 57.03, "NÃO")
    (corrigir,) = _linhas_da_aba(r.caminho_relatorio, "Corrigir número no site")
    assert corrigir[:2] == ["90", "2026000000090"]
    avisos = [l[0] for l in _linhas_da_aba(r.caminho_relatorio, "Avisos")]
    assert "Cidade informada à mão" in avisos and "Consulta de CNPJ falhou" in avisos
    unificacao = next(c for c in r.conferencias if c.descricao.startswith("Unificação"))
    assert unificacao.ok, unificacao.detalhe


def test_t6_tomador_que_nao_e_da_fundacao(tmp_path):
    r = _gerar_t6(tmp_path, cnpj_tomador="11222333000181")
    assert r.arquivos == [] and r.notas_no_arquivo == 0
    assert all(n.destino is Destino.NAO_INCLUIDA for n in r.notas)


def test_t6_tomador_de_outra_raiz_na_lista_da_tela(tmp_path):
    """R1 (Usuário, 01/10/2026): a lista gravada pela tela vale na geração."""
    assert processamento.outros_cnpjs_fundacao() == []
    assert processamento.salvar_outros_cnpjs_fundacao(["11.222.333/0001-81"]) == ""
    assert processamento.outros_cnpjs_fundacao() == ["11222333000181"]
    r = _gerar_t6(tmp_path, cnpj_tomador="11222333000181")
    assert [a.caminho.name for a in r.arquivos] == ["tomados_11222333000181_08-2026.txt"]
    assert r.notas_no_arquivo > 0


def test_cnpj_valido():
    assert processamento.cnpj_valido("98.765.432/0001-98")
    assert processamento.cnpj_valido("11222333000181")
    assert not processamento.cnpj_valido("11222333000182")        # dígito errado
    assert not processamento.cnpj_valido("1122233300018")         # 13 dígitos
    assert not processamento.cnpj_valido("11111111111111")


def test_interpretar_outros_cnpjs():
    texto = "11.222.333/0001-81\n\n  11222333000181 \n12.345.678/0001-00\n"
    assert processamento.interpretar_outros_cnpjs(texto) == (["11222333000181"],
                                                             ["12.345.678/0001-00"])
    assert processamento.interpretar_outros_cnpjs("") == ([], [])


def test_lista_de_outros_cnpjs_estragada_vale_vazia():
    caminho = processamento._caminho_outros_cnpjs()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("{não é json", encoding="utf-8")
    assert processamento.outros_cnpjs_fundacao() == []


# ---------------------------------------------------------------------------
# Andamento, substituição, falhas de gravação, validação
# ---------------------------------------------------------------------------


def test_andamento_informado_em_ordem(tmp_path):
    passos = []
    processamento.gerar(pasta_pdfs=_pdfs(), tipo_referencia="C",
                        data_lancamento=date(2026, 9, 28), pasta_saida=tmp_path,
                        consultar_cnpj=sem_consulta,
                        progresso=lambda texto, fracao: passos.append((texto, fracao)))
    fracoes = [f for _, f in passos if f is not None]
    assert fracoes == sorted(fracoes) and fracoes[-1] == 1.0
    textos = [t for t, _ in passos]
    assert "Lendo PDFs... 1 de 20" in textos and textos[-1] == "Concluído."


def test_pergunta_antes_de_substituir(tmp_path):
    parametros = dict(pasta_pdfs=_pdfs(), tipo_referencia="C", data_lancamento=date(2026, 9, 28),
                      pasta_saida=tmp_path, consultar_cnpj=sem_consulta)
    processamento.gerar(**parametros)
    arquivo = tmp_path / "tomados_98765432000198_08-2026.txt"
    arquivo.write_bytes(b"conteudo antigo")

    perguntados = []
    r = processamento.gerar(**parametros, perguntar_substituir=lambda c: perguntados.extend(c)
                            or False)
    assert r.cancelado and arquivo.read_bytes() == b"conteudo antigo"
    assert {c.name for c in perguntados} == {"tomados_98765432000198_08-2026.txt"}
    assert processamento.gerar(**parametros).cancelado             # sem quem responda: não troca

    r = processamento.gerar(**parametros, perguntar_substituir=lambda c: True)
    assert not r.cancelado
    assert arquivo.read_bytes() == _esperado("teste1_tomados_98765432000198_08-2026.txt")


def test_arquivo_que_nao_pode_ser_gravado_nao_derruba_o_resto(tmp_path):
    (tmp_path / "tomados_98765432000198_08-2026.txt").mkdir()      # uma pasta no lugar
    r = processamento.gerar(pasta_pdfs=_pdfs(), tipo_referencia="C",
                            data_lancamento=date(2026, 9, 28), pasta_saida=tmp_path,
                            consultar_cnpj=sem_consulta, perguntar_substituir=lambda c: True)
    (agosto,) = r.arquivos
    assert not agosto.gravado
    assert r.notas_no_arquivo == 0 and r.nao_incluidas == 6 + 12
    assert not r.tudo_certo
    assert r.caminho_relatorio.exists()                       # o relatório sai mesmo assim
    arquivos = _linhas_da_aba(r.caminho_relatorio, "Arquivos gerados")
    assert "não foi gravado" in arquivos[0][4]
    bruno = [l for l in _linhas_da_aba(r.caminho_relatorio, "Notas") if l[7] == "337"]
    assert bruno and all("não foi gravado" in l[1] and not l[19] for l in bruno)


def test_pdf_com_problema_aparece_como_erro_de_leitura(tmp_path):
    pasta = tmp_path / "pdfs"
    pasta.mkdir()
    shutil.copy(next(_pdfs().glob("DANFSe-95-*.pdf")), pasta)
    (pasta / "quebrado.pdf").write_bytes(b"nada")
    r = processamento.gerar(pasta_pdfs=pasta, tipo_referencia="C",
                            data_lancamento=date(2026, 9, 28), pasta_saida=tmp_path / "s",
                            consultar_cnpj=sem_consulta)
    assert (r.notas_no_arquivo, r.erros_de_leitura, r.nao_incluidas) == (1, 1, 1)
    notas = _linhas_da_aba(r.caminho_relatorio, "Notas")
    assert ["ERRO DE LEITURA", "quebrado.pdf"] == [notas[1][0], notas[1][3]]


def test_resultado_que_nao_abre_vira_aviso(tmp_path):
    r = processamento.gerar(pasta_pdfs=_pdfs(), resultados=[tmp_path / "nao_existe.csv"],
                            tipo_referencia="C", data_lancamento=date(2026, 9, 28),
                            pasta_saida=tmp_path / "s", consultar_cnpj=sem_consulta)
    conferencia = next(c for c in r.conferencias if c.descricao.startswith("Resultados"))
    assert not conferencia.ok
    avisos = _linhas_da_aba(r.caminho_relatorio, "Avisos")
    assert any(l[0] == "Resultado da prefeitura não lido" for l in avisos)


@pytest.mark.parametrize("mudanca, trecho", [
    ({"pasta_pdfs": None}, "PDFs ou as exportações"),
    ({"pasta_pdfs": None, "exportacoes": ["x.csv"]}, "CNPJ do tomador"),
    ({"pasta_pdfs": None, "exportacoes": ["x.csv"], "cnpj_tomador": MATRIZ}, "competência"),
    ({"tipo_referencia": "X"}, "tipo da declaração"),
    ({"data_lancamento": None}, "data de lançamento"),
    ({"pasta_saida": None}, "pasta de saída"),
])
def test_chamada_incompleta(tmp_path, mudanca, trecho):
    parametros = dict(pasta_pdfs=tmp_path, tipo_referencia="C", data_lancamento=date(2026, 9, 28),
                      pasta_saida=tmp_path)
    parametros.update(mudanca)
    with pytest.raises(ValueError, match=trecho):
        processamento.gerar(**parametros)


def test_consultas_para_a_tela(tmp_path):
    assert processamento.interpretar_data("28/09/2026") == date(2026, 9, 28)
    assert processamento.interpretar_data("31/02/2026") is None
    assert processamento.interpretar_competencia("08/2026") == AGOSTO
    assert processamento.interpretar_competencia("abc") is None
    assert processamento.contar_pdfs(_pdfs()) == 20
    assert processamento.contar_pdfs(tmp_path / "nao_existe") == 0
    nome = processamento.caminho_relatorio(tmp_path).name
    assert nome.startswith("Relatorio_Tomados_") and nome.endswith(".xlsx")


def test_layout_do_detalhe_bate_com_o_teste(tmp_path):
    """As posições usadas nos testes acima (número, tipo, regime) conferem com a tabela."""
    campos = {c.nome: c for c in layout_v3.DETALHE}
    assert (campos["numero_nf"].inicio - 1, campos["numero_nf"].fim) == (178, 186)
    assert campos["regime_prestador"].inicio - 1 == 254
