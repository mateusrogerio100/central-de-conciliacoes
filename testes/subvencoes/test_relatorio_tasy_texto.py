"""Balancete e patrimônio no .xls como sai do Tasy (texto separado por tabulação, cp1252).

Pedido do usuário (09/11/2026): aceitar o arquivo direto do Tasy, sem precisar abrir no Excel e salvar
como .xlsx. O teste principal monta o MESMO relatório nos dois formatos e confere que a leitura é igual.
Dados fictícios; os reais de outubro/2026 (exemplos/, fora do git) só conferem os totais.
"""

import datetime
from decimal import Decimal

import openpyxl
import pytest

from modulos.subvencoes.leitor_balancete import ler_balancete
from modulos.subvencoes.leitor_patrimonio import ler_patrimonio
from modulos.subvencoes.modelos import ErroArquivo, Gravidade, MesReferencia
from modulos.subvencoes.utilitarios import abrir_relatorio_tasy, celula_do_texto
from testes.subvencoes.conftest import PASTA_EXEMPLOS

# Como o Tasy grava: tudo texto, números no formato brasileiro, código do bem com zero à esquerda.
BALANCETE_TEXTO = [
    ["Fundação Exemplo", "", "", "", "", ""],
    ["Balancete"],
    ["", "", "", "", "", "", "Mês Referência:", "", "out/2026", ""],
    ["", "Código", "", "Classificação", "", "Descrição", "", "", "", "Saldo Anterior", "", "Movimento",
     "Saldo Atual", ""],
    ["", "Passivo"],
    ["", "", "25546", "", "2.02.06", "      SUBVENÇÕES / PROJETOS", "", "", "", "1.234.567,89", "", "-1.000,00",
     "1.233.567,89", ""],
    ["", "", "24876", "", "2.02.06.01.0020", "              Convênio Federal 111111/2012", "", "", "", "444,95",
     "", "-62,31", "382,64", ""],
    ["", "", "Impresso em: 09/11/2026 10:00:00", "", "", "Página: 1"],
]

PATRIMONIO_TEXTO = [
    ["Patrimônio - Bens Subvenção"],
    ["", "", "", "", "", "", "", "", "", "Data: 01/10/26 à 31/10/26", ""],
    ["", "", "Conta Subvenção", "Cód Bem", "Descrição", "", "Valor Contábil", "", "Deprec Mês", "", ""],
    ["", "", "Convênio Federal 111111/2012"],
    ["", "", "", "017161", "Foco de Luz", "", "1.000,50", "", "10,00", "", ""],
    # descrição com quebra de linha, entre aspas: o Excel junta numa célula só
    ["", "", "", "11535252", '"Lentes Objetivas\n"', "", "20.572,30", "", "203,02", "", ""],
    ["", "Total - Convênio Federal 111111/2012(2)", "", "", "", "", "21.572,80", "", "213,02", "", ""],
    ["", "Total(2)", "", "", "", "", "21.572,80", "", "213,02", "", ""],
    ["", "", "Impresso em:  09/11/2026 10:46:22", "", "", "Página   1"],
]


def _gravar_texto(caminho, linhas):
    caminho.write_bytes("\r\n".join("\t".join(l) for l in linhas).encode("cp1252"))
    return caminho


def _gravar_como_excel(caminho, linhas):
    """O que o usuário fazia antes: abrir no Excel e salvar como .xlsx (o Excel converte os números)."""
    pasta = openpyxl.Workbook()
    for linha in linhas:
        pasta.active.append([_como_excel(c) for c in linha])
    pasta.save(caminho)
    return caminho


def _como_excel(celula):
    valor = celula_do_texto(celula.strip('"') if celula.startswith('"') else celula)
    return float(valor) if isinstance(valor, Decimal) else valor


@pytest.mark.parametrize("texto, esperado", [
    ("", None),
    ("   ", None),
    ("017161", 17161),
    ("-5", -5),
    ("30.712.933,62", Decimal("30712933.62")),
    ("-1.666,68", Decimal("-1666.68")),
    ("0,00", Decimal("0.00")),
    ("out/2026", datetime.datetime(2026, 10, 1)),
    ("Set/2026", datetime.datetime(2026, 9, 1)),
    ("2.02.06.01.0020", "2.02.06.01.0020"),
    ("      SUBVENÇÕES", "      SUBVENÇÕES"),
    ("Data: 01/10/26 à 31/10/26", "Data: 01/10/26 à 31/10/26"),
    ("abc/2026", "abc/2026"),
])
def test_celula_convertida_como_o_excel(texto, esperado):
    assert celula_do_texto(texto) == esperado


def test_balancete_do_tasy_le_igual_ao_xlsx(tmp_path):
    texto = ler_balancete(_gravar_texto(tmp_path / "balancete_10-2026.xls", BALANCETE_TEXTO))
    excel = ler_balancete(_gravar_como_excel(tmp_path / "balancete.xlsx", BALANCETE_TEXTO))
    assert texto.mes_referencia == excel.mes_referencia == MesReferencia(2026, 10)
    assert texto.contas == excel.contas
    assert texto.contas[24876].saldo_atual == Decimal("382.64")
    assert texto.contas[24876].descricao == "Convênio Federal 111111/2012"
    assert texto.avisos == []


def test_patrimonio_do_tasy_le_igual_ao_xlsx(tmp_path):
    texto = ler_patrimonio(_gravar_texto(tmp_path / "patrimonio_10-2026.xls", PATRIMONIO_TEXTO))
    excel = ler_patrimonio(_gravar_como_excel(tmp_path / "patrimonio.xlsx", PATRIMONIO_TEXTO))
    assert texto.mes_referencia == excel.mes_referencia == MesReferencia(2026, 10)
    assert [(c.nome, c.soma_itens, len(c.itens)) for c in texto.contas] == \
           [(c.nome, c.soma_itens, len(c.itens)) for c in excel.contas] == \
           [("Convênio Federal 111111/2012", Decimal("21572.80"), 2)]
    assert [i.codigo_bem for i in texto.contas[0].itens] == ["17161", "11535252"]
    assert texto.total_geral_confere and texto.linhas_nao_reconhecidas == []
    assert texto.avisos == []


def test_xlsx_com_extensao_xls_tambem_abre(tmp_path):
    caminho = _gravar_como_excel(tmp_path / "balancete.xls", BALANCETE_TEXTO)   # reconhecido pelo conteúdo
    assert len(ler_balancete(caminho).contas) == 2


def test_excel_antigo_de_verdade_tem_mensagem_clara(tmp_path):
    antigo = tmp_path / "antigo.xls"
    antigo.write_bytes(bytes.fromhex("D0CF11E0") + b"\x00" * 100)
    with pytest.raises(ErroArquivo, match="Excel antigo"):
        abrir_relatorio_tasy(antigo)
    with pytest.raises(ErroArquivo, match="não encontrado"):
        abrir_relatorio_tasy(tmp_path / "nao_existe.xls")


def test_balancete_so_com_cabecalho_para_com_aviso(tmp_path):
    # Pedido do usuário (09/11/2026): balancete exportado vazio para tudo, sem gerar planilhas zeradas
    vazio = _gravar_texto(tmp_path / "balancete_09.xls", BALANCETE_TEXTO[:4] + BALANCETE_TEXTO[-1:])
    with pytest.raises(ErroArquivo, match="não tem nenhuma conta"):
        ler_balancete(vazio)


def test_balancete_vazio_nao_gera_planilha(tmp_path, monkeypatch):
    from modulos.subvencoes import processamento
    from modulos.subvencoes.modelos import StatusArquivo
    vazio = _gravar_texto(tmp_path / "balancete_09.xls", BALANCETE_TEXTO[:4] + BALANCETE_TEXTO[-1:])
    patrimonio = _gravar_texto(tmp_path / "patrimonio.xls", PATRIMONIO_TEXTO)
    planilha = tmp_path / "Projetos 09-2026.xlsx"
    openpyxl.Workbook().save(planilha)
    saida = tmp_path / "saida"
    saida.mkdir()
    resultado = processamento.processar(vazio, patrimonio, [planilha], saida, MesReferencia(2026, 10))
    balancete = next(a for a in resultado.arquivos if a.nome == "balancete_09.xls")
    assert balancete.status == StatusArquivo.FALHOU and "não tem nenhuma conta" in balancete.detalhe
    assert not any(a.status == StatusArquivo.GERADO for a in resultado.arquivos)


def test_exemplo_real_de_outubro_fecha_com_os_totais_do_tasy():
    pasta = PASTA_EXEMPLOS / "2026-10"
    if not pasta.is_dir():
        pytest.skip("exemplos de outubro/2026 não encontrados")
    balancete = ler_balancete(pasta / "balancete_10-2026.xls")
    assert balancete.mes_referencia == MesReferencia(2026, 10)
    assert len(balancete.contas) == 129 and balancete.avisos == []
    patrimonio = ler_patrimonio(pasta / "patrimonio_10-2026.xls")
    assert patrimonio.mes_referencia == MesReferencia(2026, 10)
    assert patrimonio.quantidade_itens == patrimonio.quantidade_geral_sistema == 4828
    assert patrimonio.soma_itens == patrimonio.total_geral_sistema == Decimal("28916216.39")
    assert not any(a.gravidade == Gravidade.ERRO for a in patrimonio.avisos)
