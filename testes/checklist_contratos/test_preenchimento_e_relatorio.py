"""T5 — cópia do Check list preenchida; T6 — relatório; e o processamento.conferir que junta tudo."""

from __future__ import annotations

import zipfile
from datetime import datetime
from decimal import Decimal

import openpyxl
import pytest
from openpyxl.styles import PatternFill

from modulos.checklist_contratos import configuracao as cfg
from modulos.checklist_contratos import processamento
from modulos.checklist_contratos.preenchimento import ValorParaGravar, gravar_copia
from testes.checklist_contratos.conftest import escrever_checklist, escrever_movimento, exemplos
from testes.conftest import diferencas_entre_planilhas, pasta_exemplos

AGORA = datetime(2026, 10, 23, 9, 30)


# ---------------------------------------------------------------------------
# T5 — cópia preenchida com o mês real (out/2026, configuração do gabarito)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def outubro(tmp_path_factory):
    """Gabarito de outubro: o Check list de 22/10 já tinha todas as linhas OK preenchidas (nada a gravar)."""
    pasta = exemplos("2026-10")
    saida = tmp_path_factory.mktemp("saida")
    resultado = processamento.conferir(pasta / "Movimentos_NF_10_SC.csv", pasta / "Movimentos_NF_10_CMD.csv",
                                       pasta / "Check list 2026.xlsx", exemplos("config_gabarito_22-10-2026"),
                                       saida, 2026, 10, agora=AGORA)
    return pasta / "Check list 2026.xlsx", resultado


@pytest.fixture(scope="module")
def rodada_23_10(tmp_path_factory):
    """O uso real de 23/10/2026: Check list da rede daquele dia + as pastas diárias do Movimento contábil."""
    checklist = exemplos("2026-10", "rodada_23-10") / "Check list 2026 (rede 23-10 0925).xlsx"
    diarios = pasta_exemplos("conferencias_notas_contratos", "Movimento_centro_custo")
    saida = tmp_path_factory.mktemp("saida_rodada")
    resultado = processamento.conferir(diarios / "Hospital Exemplo", diarios / "CMD", checklist, exemplos("config"),
                                       saida, 2026, 10, agora=AGORA)
    return checklist, resultado


def test_t5_so_as_celulas_ok_vazias_mudaram(rodada_23_10):
    original, resultado = rodada_23_10
    assert resultado.erro == "" and resultado.erro_copia == "" and resultado.avisos == []
    gravadas = {(resultado.checklist.abas[r.regra.aba].nome, r.linha.numero): r.valor
                for r in resultado.conferencia.resultados if r.gravar}
    assert gravadas and all(not r.celula_preenchida for r in resultado.conferencia.resultados if r.gravar)
    diferencas = diferencas_entre_planilhas(original, resultado.caminho_copia)
    assert {(aba, int(celula[1:])) for aba, celula, _, _ in diferencas} == set(gravadas)
    for aba, celula, antes, depois in diferencas:
        assert antes is None and Decimal(str(depois)) == gravadas[(aba, int(celula[1:]))]


def test_t5_o_resto_do_arquivo_fica_igual_byte_a_byte(rodada_23_10):
    original, resultado = rodada_23_10
    with zipfile.ZipFile(original) as antes, zipfile.ZipFile(resultado.caminho_copia) as depois:
        assert antes.namelist() == depois.namelist()                     # formas, comentários, suplementos
        mudaram = [n for n in antes.namelist() if antes.read(n) != depois.read(n)]
    assert "xl/workbook.xml" in mudaram and set(mudaram) <= {"xl/workbook.xml", "xl/worksheets/sheet2.xml",
                                                              "xl/worksheets/sheet3.xml"}     # só as duas abas


def test_t5_formato_da_celula_nova_igual_ao_do_mes_anterior(rodada_23_10):
    _, resultado = rodada_23_10
    livro = openpyxl.load_workbook(resultado.caminho_copia)
    for r in resultado.conferencia.resultados:
        if r.gravar:
            aba = resultado.checklist.abas[r.regra.aba]
            nova = livro[aba.nome].cell(r.linha.numero, aba.coluna_mes)
            modelo = livro[aba.nome].cell(r.linha.numero, aba.coluna_mes_anterior)
            assert nova.style_id == modelo.style_id                  # o mesmo estilo (formato, fonte, cor, borda)
            assert nova.number_format == modelo.number_format


def test_t5_recalcula_as_formulas_ao_abrir(rodada_23_10):
    _, resultado = rodada_23_10
    with zipfile.ZipFile(resultado.caminho_copia) as livro:
        assert 'fullCalcOnLoad="1"' in livro.read("xl/workbook.xml").decode("utf-8")


# ---------------------------------------------------------------------------
# T5 — casos montados: célula que não existe no arquivo, linha sem células, célula com conteúdo
# ---------------------------------------------------------------------------

def test_t5_celula_que_nao_existe_no_xml_entra_na_ordem_certa(tmp_path):
    caminho = escrever_checklist(tmp_path / "chk.xlsx", linhas_sc=[
        [30091, "Software", None, "Fornecedor Exemplo", None, "Licença", "Ana", 1, 2, 3, 4, 5, 6, 7, 8, 9, None, 99]])
    livro = openpyxl.load_workbook(caminho)
    livro["HOSPITAL EXEMPLO"].cell(2, 16).fill = PatternFill("solid", start_color="FFFF00")    # set/26 amarelo
    livro.save(caminho)
    destino = tmp_path / "copia.xlsx"
    avisos = gravar_copia(caminho, destino, [ValorParaGravar("HOSPITAL EXEMPLO", 2, 17, 16, Decimal("123.45"))])
    assert avisos == []
    aba = openpyxl.load_workbook(destino)["HOSPITAL EXEMPLO"]
    assert aba.cell(2, 17).value == 123.45 and aba.cell(2, 18).value == 99          # out/26 entre set e a seguinte
    assert aba.cell(2, 17).fill.start_color.rgb == aba.cell(2, 16).fill.start_color.rgb
    assert diferencas_entre_planilhas(caminho, destino) == [("HOSPITAL EXEMPLO", "Q2", None, 123.45)]


def test_t5_celula_com_conteudo_nunca_e_alterada(tmp_path):
    caminho = escrever_checklist(tmp_path / "chk.xlsx", linhas_sc=[
        [30091, "Software", None, "Fornecedor Exemplo", None, "Licença", "Ana", 1, 2, 3, 4, 5, 6, 7, 8, 9, "Provisão"]])
    destino = tmp_path / "copia.xlsx"
    avisos = gravar_copia(caminho, destino, [ValorParaGravar("HOSPITAL EXEMPLO", 2, 17, 16, Decimal("10"))])
    assert "já tem conteúdo" in avisos[0].mensagem
    assert openpyxl.load_workbook(destino)["HOSPITAL EXEMPLO"].cell(2, 17).value == "Provisão"


def test_t5_linha_inexistente_e_aba_inexistente_viram_aviso(tmp_path):
    caminho = escrever_checklist(tmp_path / "chk.xlsx")
    avisos = gravar_copia(caminho, tmp_path / "copia.xlsx", [ValorParaGravar("HOSPITAL EXEMPLO", 50, 17, 16, Decimal("1")),
                                                             ValorParaGravar("OUTRA", 2, 17, 16, Decimal("1"))])
    assert len(avisos) == 2 and "não existe" in avisos[0].mensagem and "Aba" in avisos[1].mensagem


# ---------------------------------------------------------------------------
# T6 — relatório
# ---------------------------------------------------------------------------

def test_t5_gabarito_de_outubro_ja_preenchido_nao_muda_nada(outubro):
    original, resultado = outubro
    assert not any(r.gravar for r in resultado.conferencia.resultados)          # R7: nunca sobrescreve
    assert diferencas_entre_planilhas(original, resultado.caminho_copia) == []


def test_t6_abas_na_ordem_e_uma_linha_por_regra(outubro):
    _, resultado = outubro
    livro = openpyxl.load_workbook(resultado.caminho_relatorio)
    assert livro.sheetnames == [cfg.ABA_RESUMO, cfg.ABA_CONFERENCIA, cfg.ABA_DIVERGENTE, cfg.ABA_MANUAIS,
                                cfg.ABA_NAO_VINCULADOS, cfg.ABA_ESTORNOS, cfg.ABA_AVISOS]
    conferencia = livro[cfg.ABA_CONFERENCIA]
    assert conferencia.max_row - 1 == 158
    assert livro[cfg.ABA_DIVERGENTE].max_row - 1 == 6                          # gabarito de outubro
    assert resultado.caminho_relatorio.name == "Conferencia_Contratos_2026-10_2026-10-23_093000.xlsx"
    for aba in livro.sheetnames[1:]:
        assert livro[aba].freeze_panes == "A2" and livro[aba].auto_filter.ref


def test_t6_cores_da_situacao_e_destaques(outubro):
    _, resultado = outubro
    aba = openpyxl.load_workbook(resultado.caminho_relatorio)[cfg.ABA_CONFERENCIA]
    for linha in range(2, aba.max_row + 1):
        situacao = aba.cell(linha, 6).value.split(" (")[0]
        assert aba.cell(linha, 6).fill.start_color.rgb.endswith(cfg.CORES_SITUACAO[situacao])
    destacadas = [r for r in resultado.conferencia.resultados if r.variacao_destacada]
    assert destacadas
    linha = 2 + resultado.conferencia.resultados.index(destacadas[0])
    assert aba.cell(linha, 10).fill.start_color.rgb.endswith(cfg.COR_DESTAQUE)


def test_t6_resumo_com_as_contagens(outubro):
    _, resultado = outubro
    resumo = dict(openpyxl.load_workbook(resultado.caminho_relatorio)[cfg.ABA_RESUMO].iter_rows(values_only=True))
    assert (resumo["OK"], resumo["CONTA DIVERGENTE"], resumo["NÃO ENCONTRADO"], resumo["MANUAL"],
            resumo["IGNORADO"]) == (80, 5, 52, 13, 8)
    assert resumo["Conferência das notas de contrato"] == "Outubro/2026"


# ---------------------------------------------------------------------------
# processamento.conferir
# ---------------------------------------------------------------------------

def _caso(tmp_path):
    escrever_movimento(tmp_path / "sc.csv", [{"Valor": "100", "Complemento": "Fornecedor Exemplo NF. 1"}])
    escrever_movimento(tmp_path / "cmd.csv", [{"Valor": "5", "Complemento": "Outro NF. 2"}])
    escrever_checklist(tmp_path / "Check list 2026.xlsx", linhas_sc=[
        [30091, "Software", None, "Fornecedor Exemplo", None, "Licença", "Ana"]])
    config = tmp_path / "config"
    config.mkdir()
    (config / "regras.csv").write_text(
        "Aba;Linha;Fornecedor_Planilha;Descricao_Planilha;Contas;Busca_Fornecedor;Busca_Descricao;Excluir;"
        "Selecao;Tipo;Obs\nSC;2;Fornecedor Exemplo;Licença;30091;fornecedor exemplo;;;;auto;\n", encoding="utf-8")
    return tmp_path / "sc.csv", tmp_path / "cmd.csv", tmp_path / "Check list 2026.xlsx", config


def test_r7a_provisao_aparece_no_relatorio_e_na_tela(tmp_path):
    sc, cmd, chk, config = _caso(tmp_path)
    escrever_checklist(chk, linhas_sc=[[30091, "Software", None, "Fornecedor Exemplo", None, "Licença", "Ana",
                                        1, 2, 3, 4, 5, 6, 7, 8, 100, "Provisão"]])
    resultado = processamento.conferir(sc, cmd, chk, config, tmp_path, 2026, 10, agora=AGORA)
    (r,) = resultado.conferencia.resultados
    assert r.provisao and not r.gravar                                   # a célula "Provisão" fica como está
    livro = openpyxl.load_workbook(resultado.caminho_relatorio)
    conferencia = livro[cfg.ABA_CONFERENCIA]
    assert conferencia["M2"].value == "Valor se refere ao mês anterior, pois ele foi provisionado."
    resumo = {l[0]: l[1] for l in livro[cfg.ABA_RESUMO].iter_rows(values_only=True)}
    assert resumo['"Provisão" na planilha e valor achado: se refere ao mês anterior (R7a)'] == 1
    linhas = [texto for texto, _ in processamento.resumir_conferencia(resultado).linhas]
    assert any("Valor se refere ao mês anterior, pois ele foi provisionado" in texto for texto in linhas)


def test_processamento_chamada_incompleta():
    with pytest.raises(ValueError):
        processamento.conferir(None, None, None, None, None, 2026, 10)


def test_processamento_nao_sobrescreve_sem_perguntar(tmp_path):
    sc, cmd, chk, config = _caso(tmp_path)
    saida = tmp_path / "saida"
    saida.mkdir()
    primeira = processamento.conferir(sc, cmd, chk, config, saida, 2026, 10, agora=AGORA)
    assert processamento.arquivos_que_seriam_substituidos(saida, 2026, 10) == [primeira.caminho_copia]
    segunda = processamento.conferir(sc, cmd, chk, config, saida, 2026, 10, agora=AGORA)
    assert segunda.caminho_copia.name == "Check list 2026 - 10 preenchido_2.xlsx"
    assert segunda.caminho_relatorio.name == "Conferencia_Contratos_2026-10_2026-10-23_093000_2.xlsx"
    terceira = processamento.conferir(sc, cmd, chk, config, saida, 2026, 10, substituir=True, agora=AGORA)
    assert terceira.caminho_copia == primeira.caminho_copia


def test_processamento_nunca_grava_por_cima_da_entrada(tmp_path):
    sc, cmd, chk, config = _caso(tmp_path)
    copia_como_entrada = tmp_path / processamento.nome_copia(2026, 10)
    chk.rename(copia_como_entrada)
    antes = copia_como_entrada.read_bytes()
    resultado = processamento.conferir(sc, cmd, copia_como_entrada, config, tmp_path, 2026, 10, substituir=True)
    assert resultado.caminho_copia.name == "Check list 2026 - 10 preenchido_2.xlsx"
    assert copia_como_entrada.read_bytes() == antes
    assert resultado.preenchidas == 1


def test_processamento_erro_de_leitura_vai_para_o_resultado(tmp_path):
    sc, cmd, chk, config = _caso(tmp_path)
    resultado = processamento.conferir(sc, cmd, chk, config, tmp_path, 2026, 7)     # CMD sem jul/26
    assert "jul/26" in resultado.erro and resultado.caminho_copia is None and resultado.caminho_relatorio is None


def test_processamento_relatorio_aberto_no_excel_nao_derruba(tmp_path, monkeypatch):
    sc, cmd, chk, config = _caso(tmp_path)

    def falhar(*_args, **_kwargs):
        raise PermissionError("arquivo em uso")

    monkeypatch.setattr(processamento, "gerar_relatorio", falhar)
    resultado = processamento.conferir(sc, cmd, chk, config, tmp_path, 2026, 10)
    assert "arquivo em uso" in resultado.erro_relatorio and resultado.caminho_copia.exists()
