"""Testes do leitor do relatório da prefeitura (Etapa 3)."""

from decimal import Decimal
from pathlib import Path

import pytest

from modulos.conferencia_iss.leitor_prefeitura import ler_relatorio_prefeitura

from testes.conferencia_iss.pastas_exemplos import PASTA_EXEMPLOS, PASTA_RB, caso_real  # noqa: E402
PREFEITURA = PASTA_RB / "Relatorio_de_Servicos_Contratados.xls"


def _exige_exemplos():
    if not PASTA_EXEMPLOS.exists():
        pytest.skip("pasta exemplos/ não existe (dados reais ficam fora do git)")


# ---------------------------------------------------------------------
# Arquivo real (gabarito seção 8.1)
# ---------------------------------------------------------------------
def test_relatorio_real():
    _exige_exemplos()
    leitura = ler_relatorio_prefeitura(PREFEITURA)
    assert leitura.erro is None
    assert len(leitura.linhas) == 130
    assert leitura.competencia == "2026-09"
    assert leitura.competencia_texto == "setembro/2026"
    assert leitura.inscricao_municipal == "20164715"
    total = sum(l.valor_doc for l in leitura.linhas if l.valor_doc is not None)
    assert total == Decimal("1495749.39")


def test_relatorio_real_um_valor_vazio():
    _exige_exemplos()
    leitura = ler_relatorio_prefeitura(PREFEITURA)
    vazias = [l for l in leitura.linhas if l.valor_doc is None]
    assert len(vazias) == 1
    assert vazias[0].documento == caso_real("rb_8_1", "valor_vazio")
    assert vazias[0].numero == "8905486"
    assert len(leitura.avisos) == 1
    assert "Valor do Doc. vazio" in leitura.avisos[0].mensagem
    assert "8905486" in leitura.avisos[0].mensagem


def test_relatorio_real_campos_da_primeira_linha():
    _exige_exemplos()
    primeira = ler_relatorio_prefeitura(PREFEITURA).linhas[0]
    esperada = caso_real("rb_8_1", "primeira_linha")
    assert primeira.documento == esperada["documento"]
    assert primeira.documento_original == esperada["documento_original"]
    assert primeira.prestador == esperada["prestador"]
    assert primeira.numero == "76807"
    assert primeira.valor_doc == Decimal("1802.62")
    assert primeira.inscricao_prestador == ""          # &nbsp;
    assert primeira.aliquota == "5,00%"
    assert primeira.item_lc == "17.01 - Assessoria o..."
    assert primeira.dia == "1"
    assert primeira.valor_imposto == Decimal("0")


def test_relatorio_real_casos_do_gabarito():
    _exige_exemplos()
    linhas = ler_relatorio_prefeitura(PREFEITURA).linhas

    def procurar(documento, numero):
        return [l for l in linhas if l.documento == documento and l.numero == numero]

    casos = caso_real("rb_8_1")
    assert [l.valor_doc for l in procurar(casos["numero_ajustado"], "122")] == [Decimal("6927.15")]
    assert [l.valor_doc for l in procurar(casos["escriturada_2_vezes_629"], "629")] == [Decimal("667")] * 2
    assert sorted(l.valor_doc for l in procurar(casos["escriturada_2_vezes_com_diferenca"], "1")) == [
        Decimal("7123.21"), Decimal("7590"),
    ]
    assert [l.valor_doc for l in procurar(casos["somente_prefeitura_41"], "41")] == [Decimal("9699.71")]
    assert [l.valor_doc for l in procurar(casos["somente_prefeitura_5"], "5")] == [Decimal("280")]


# ---------------------------------------------------------------------
# Casos inventados
# ---------------------------------------------------------------------
CABECALHO = [
    "CPF / CNPJ Prestador", " Insc. Prestador", "Nome / Razão Social Prestador",
    "Modelo de Doc. Fiscal", "Nº Doc.", "Item LC", "Unidade Econômica", "Alíquota", "Dia",
    "Imp. Ret.", "SN/MEI", "Nat. Operação", " Valor do Doc. ", "Valor Tribut. ",
    "Valor do Imp. ",
]


def _linha(doc="11.222.333/0001-81", numero="10", valor="1.234,56", nome="Prestador Teste"):
    return [doc, "&nbsp;", nome, "NFS-e", numero, "04.01 - Medicina e b...", "Não",
            "2,00%", "5", "Não", "Optante SN", "Exigível", valor, valor, "0,0000"]


def _gravar(pasta: Path, linhas, cabecalho=CABECALHO,
            topo="Tomador Teste • Inscr. Municipal: 12345 • Competência: março/2026",
            codificacao="utf-8") -> Path:
    def tr(celulas):
        return "<tr>" + "".join(f"<td>{c}</td>" for c in celulas) + "</tr>"

    html = (
        f"Relatório de Serviços Contratados<br><br>{topo}<br><br>"
        f'<table border="1">{tr(cabecalho)}{"".join(tr(l) for l in linhas)}</table>'
    )
    caminho = pasta / "relatorio.xls"
    caminho.write_bytes(html.encode(codificacao))
    return caminho


def test_cabecalho_competencia_com_acento(tmp_path):
    leitura = ler_relatorio_prefeitura(_gravar(tmp_path, [_linha()]))
    assert leitura.erro is None
    assert leitura.competencia == "2026-03"
    assert leitura.competencia_texto == "março/2026"
    assert leitura.inscricao_municipal == "12345"
    assert leitura.avisos == []


def test_sem_competencia_vira_aviso(tmp_path):
    leitura = ler_relatorio_prefeitura(_gravar(tmp_path, [_linha()], topo="Tomador Teste"))
    assert leitura.erro is None
    assert len(leitura.linhas) == 1
    mensagens = " ".join(a.mensagem for a in leitura.avisos)
    assert "Competência" in mensagens and "Inscrição" in mensagens


def test_cpf_formatado(tmp_path):
    leitura = ler_relatorio_prefeitura(_gravar(tmp_path, [_linha(doc="123.456.789-09")]))
    assert leitura.linhas[0].documento == "12345678909"


def test_numero_e_valores_normalizados(tmp_path):
    leitura = ler_relatorio_prefeitura(_gravar(tmp_path, [_linha(numero="000077", valor="1.495.749,39")]))
    linha = leitura.linhas[0]
    assert linha.numero == "77" and linha.numero_doc == "000077"
    assert linha.valor_doc == Decimal("1495749.39")
    assert linha.valor_tributavel == Decimal("1495749.39")


def test_valor_vazio_mantem_linha_e_avisa(tmp_path):
    leitura = ler_relatorio_prefeitura(_gravar(tmp_path, [_linha(valor="&nbsp;"), _linha(numero="2")]))
    assert len(leitura.linhas) == 2
    assert leitura.linhas[0].valor_doc is None
    assert len(leitura.avisos) == 1
    assert "Valor do Doc. vazio" in leitura.avisos[0].mensagem


def test_valor_invalido_mantem_linha_e_avisa(tmp_path):
    leitura = ler_relatorio_prefeitura(_gravar(tmp_path, [_linha(valor="abc")]))
    assert len(leitura.linhas) == 1
    assert leitura.linhas[0].valor_doc is None
    assert any("inválido" in a.mensagem for a in leitura.avisos)


def test_colunas_em_outra_ordem(tmp_path):
    ordem = list(reversed(range(len(CABECALHO))))
    cabecalho = [CABECALHO[i] for i in ordem]
    linha = [_linha(numero="88", valor="10,00")[i] for i in ordem]
    leitura = ler_relatorio_prefeitura(_gravar(tmp_path, [linha], cabecalho=cabecalho))
    assert leitura.linhas[0].numero == "88"
    assert leitura.linhas[0].valor_doc == Decimal("10.00")


def test_celula_com_tags_dentro(tmp_path):
    linha = _linha(nome="<span>Clínica <b>Teste</b></span>")
    leitura = ler_relatorio_prefeitura(_gravar(tmp_path, [linha]))
    assert leitura.linhas[0].prestador == "Clínica Teste"


def test_linha_com_colunas_a_menos_mantem_e_avisa(tmp_path):
    leitura = ler_relatorio_prefeitura(_gravar(tmp_path, [_linha()[:5], _linha(numero="2")]))
    assert len(leitura.linhas) == 2
    assert any("Linha 1 da tabela" in a.mensagem for a in leitura.avisos)


def test_codificacao_cp1252(tmp_path):
    leitura = ler_relatorio_prefeitura(_gravar(tmp_path, [_linha(nome="Serviços Cidade Epsilon")],
                                               codificacao="cp1252"))
    assert leitura.linhas[0].prestador == "Serviços Cidade Epsilon"
    assert leitura.competencia == "2026-03"


def test_sem_tabela_vira_erro(tmp_path):
    caminho = tmp_path / "relatorio.xls"
    caminho.write_text("<html><body>Nenhum registro encontrado</body></html>", encoding="utf-8")
    leitura = ler_relatorio_prefeitura(caminho)
    assert "Nenhuma tabela" in leitura.erro
    assert leitura.linhas == []


def test_tabela_sem_coluna_obrigatoria_vira_erro(tmp_path):
    cabecalho = [c for c in CABECALHO if "Valor do Doc." not in c]
    leitura = ler_relatorio_prefeitura(_gravar(tmp_path, [_linha()[:-3]], cabecalho=cabecalho))
    assert "Valor do Doc." in leitura.erro
    assert leitura.linhas == []


def test_planilha_excel_de_verdade_vira_erro(tmp_path):
    caminho = tmp_path / "relatorio.xls"
    caminho.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + bytes(500))
    leitura = ler_relatorio_prefeitura(caminho)
    assert "planilha do Excel" in leitura.erro


def test_arquivo_inexistente_e_vazio_viram_erro(tmp_path):
    assert ler_relatorio_prefeitura(tmp_path / "nao_existe.xls").erro
    vazio = tmp_path / "vazio.xls"
    vazio.write_bytes(b"")
    assert ler_relatorio_prefeitura(vazio).erro == "Arquivo vazio."


def test_arquivo_binario_qualquer_nao_quebra(tmp_path):
    caminho = tmp_path / "lixo.xls"
    caminho.write_bytes(bytes(range(256)) * 10)
    leitura = ler_relatorio_prefeitura(caminho)
    assert leitura.erro is not None
    assert leitura.linhas == []
