"""E1 — leitura do balancete de estoque (ESPECIFICACAO_ESTOQUE.md, seções 3.2 e 7.1)."""

from __future__ import annotations

from decimal import Decimal

import openpyxl
import pytest

from modulos.conciliacao_estoque.leitor_balancete_estoque import ler_balancete_estoque
from modulos.conciliacao_estoque.leitor_tasy_texto import ler_linhas
from modulos.conciliacao_estoque.modelos import ErroArquivo, Gravidade, MesReferencia
from testes.conciliacao_estoque.conftest import ler_gabarito_estoque
from testes.conftest import pasta_exemplos

# ---------------------------------------------------------------------------
# Arquivo real de setembro/2026
# ---------------------------------------------------------------------------


def test_setembro_contas_e_mes(caminho_balancete):
    balancete = ler_balancete_estoque(caminho_balancete)
    assert balancete.mes_referencia == MesReferencia(2026, 9)
    assert len(balancete.analiticas) == 23
    assert [c.classificacao for c in balancete.sinteticas] == [
        "1.01.04", "1.01.04.01", "1.01.04.02", "1.01.04.03",
    ]
    assert balancete.contas_fora_do_prefixo == 0


def test_setembro_saldo_anterior_mais_movimento_igual_saldo_atual(caminho_balancete):
    balancete = ler_balancete_estoque(caminho_balancete)
    for conta in balancete.contas:
        assert conta.saldo_anterior + conta.movimento == conta.saldo_atual, conta.codigo
    assert [a for a in balancete.avisos if a.gravidade == Gravidade.ERRO] == []


def test_setembro_valores_e_totais(caminho_balancete):
    balancete = ler_balancete_estoque(caminho_balancete)
    primeira = balancete.analiticas[0]
    assert (primeira.codigo, primeira.classificacao, primeira.descricao) == (
        10978, "1.01.04.01.0002", "Estoque SESMT - EPI - SC (31)",
    )
    assert (primeira.saldo_anterior, primeira.movimento, primeira.saldo_atual) == (
        Decimal("26237.75"), Decimal("-7065.98"), Decimal("19171.77"),
    )
    estoques = balancete.sintetica("1.01.04")
    assert estoques.codigo == 114
    assert estoques.saldo_anterior == Decimal("6558659.62")
    assert estoques.saldo_atual == Decimal("6034965.49")
    assert sum(c.saldo_atual for c in balancete.analiticas) == Decimal("6034965.49")
    # seção 7.2: a conta do Enxoval (67), com saldo atual zero, não foi impressa
    assert sum(c.saldo_anterior for c in balancete.analiticas) == Decimal("6517621.62")
    assert balancete.sintetica("1.01.04.01").saldo_anterior == Decimal("4675745.59")


def test_setembro_classificacao_repetida_e_so_info(caminho_balancete):
    balancete = ler_balancete_estoque(caminho_balancete)
    repetidas = [a for a in balancete.avisos if a.tipo == "classificação repetida"]
    assert len(repetidas) == 1
    assert repetidas[0].gravidade == Gravidade.INFO
    assert repetidas[0].conta == "1.01.04.01.0017"
    assert {c.codigo for c in balancete.analiticas if c.classificacao == "1.01.04.01.0017"} == {11895, 11899}


def test_setembro_igual_ao_gabarito(caminho_balancete):
    """Código, classificação, descrição e saldos de cada conta iguais ao gabarito da EST-01/03."""
    balancete = ler_balancete_estoque(caminho_balancete)
    contas = {c.codigo: c for c in balancete.analiticas}
    campo = {"saldo_anterior": "saldo_anterior", "saldo_atual": "saldo_atual"}
    linhas_com_conta = [g for g in ler_gabarito_estoque() if g["codigo"]]
    assert len(linhas_com_conta) == 46     # 23 contas x 2 etapas
    for linha in linhas_com_conta:
        conta = contas[int(linha["codigo"])]
        assert conta.classificacao == linha["classificacao"]
        assert conta.descricao == linha["descricao_balancete"]
        assert getattr(conta, campo[linha["parte"]]) == linha["saldo_balancete"], linha["codigo"]


def test_setembro_salvo_como_xlsx_da_o_mesmo_resultado(caminho_balancete, tmp_path):
    """O usuário abre o .xls no Excel e salva como .xlsx: os números viram float na planilha."""
    convertido = tmp_path / "Balancete.xlsx"
    pasta = openpyxl.Workbook()
    aba = pasta.active
    for linha in ler_linhas(caminho_balancete):
        aba.append([_como_o_excel_gravaria(v) for v in linha])
    pasta.save(convertido)

    original = ler_balancete_estoque(caminho_balancete)
    do_xlsx = ler_balancete_estoque(convertido)
    assert do_xlsx.mes_referencia == original.mes_referencia
    assert [(c.codigo, c.descricao, c.saldo_anterior, c.movimento, c.saldo_atual) for c in do_xlsx.contas] == [
        (c.codigo, c.descricao, c.saldo_anterior, c.movimento, c.saldo_atual) for c in original.contas
    ]


def _como_o_excel_gravaria(texto: str):
    """Número brasileiro vira float (como o Excel faz ao abrir o texto); o resto fica texto."""
    texto = texto.strip()
    if not texto:
        return None
    try:
        if "," in texto or texto.replace(".", "").lstrip("-").isdigit() and "." not in texto:
            return float(texto.replace(".", "").replace(",", "."))
    except ValueError:
        pass
    return texto


# ---------------------------------------------------------------------------
# Casos construídos
# ---------------------------------------------------------------------------

CABECALHO = [
    "Fundação Hospital Exemplo\t\t",
    "\t\t\t\t\t\tMês Referência:\t\tset/2026",
    "\tCódigo\t\tClassificação\t\tDescrição\t\t\t\tSaldo Anterior\t\tMovimento\tSaldo Atual",
]


def _balancete(tmp_path, *linhas_conta: str, cabecalho=CABECALHO):
    arquivo = tmp_path / "balancete.xls"
    arquivo.write_bytes("\n".join([*cabecalho, *linhas_conta]).encode("cp1252"))
    return ler_balancete_estoque(arquivo)


def test_contas_fora_de_1_01_04_sao_ignoradas_e_contadas(tmp_path):
    balancete = _balancete(
        tmp_path,
        "\t\t114\t\t1.01.04\t  ESTOQUES\t\t\t\t10,00\t\t5,00\t15,00",
        "\t\t200\t\t1.01.05\t  OUTRA\t\t\t\t1,00\t\t0,00\t1,00",
        "\t\t201\t\t1.01.05.01.0001\t  OUTRA ANALÍTICA\t\t\t\t1,00\t\t0,00\t1,00",
    )
    assert [c.codigo for c in balancete.contas] == [114]
    assert balancete.contas_fora_do_prefixo == 2


def test_saldo_que_nao_fecha_gera_erro_mas_conta_continua(tmp_path):
    balancete = _balancete(tmp_path, "\t\t10978\t\t1.01.04.01.0002\t  Estoque X (31)\t\t\t\t10,00\t\t5,00\t16,00")
    assert len(balancete.analiticas) == 1
    erros = [a for a in balancete.avisos if a.gravidade == Gravidade.ERRO]
    assert [e.tipo for e in erros] == ["saldo não fecha"]
    assert erros[0].conta == "10978"


def test_linha_sem_os_tres_numeros_gera_erro_e_e_ignorada(tmp_path):
    balancete = _balancete(tmp_path, "\t\t10978\t\t1.01.04.01.0002\t  Estoque X (31)\t\t\t\t10,00\t\t5,00\t")
    assert balancete.contas == []
    assert [a.tipo for a in balancete.avisos if a.gravidade == Gravidade.ERRO] == ["linha não reconhecida"]


def test_conta_sem_codigo_gera_erro(tmp_path):
    balancete = _balancete(tmp_path, "\t\t\t\t1.01.04.01.0002\t  Estoque X (31)\t\t\t\t10,00\t\t5,00\t15,00")
    assert balancete.contas == []
    assert balancete.avisos[0].gravidade == Gravidade.ERRO


def test_rodape_e_ignorado(tmp_path):
    balancete = _balancete(
        tmp_path,
        "\t\t10978\t\t1.01.04.01.0002\t  Estoque X (31)\t\t\t\t10,00\t\t5,00\t15,00",
        "\tImpresso em: 05/10/2026 15:00:09\t\t\t\t\t\tPágina: 1\t\t\tUsuarioRS",
    )
    assert len(balancete.contas) == 1
    assert balancete.avisos == []


def test_mes_nao_encontrado_gera_atencao(tmp_path):
    balancete = _balancete(
        tmp_path, "\t\t10978\t\t1.01.04.01.0002\t  Estoque X (31)\t\t\t\t10,00\t\t5,00\t15,00",
        cabecalho=[CABECALHO[0], CABECALHO[2]],
    )
    assert balancete.mes_referencia is None
    assert [a.tipo for a in balancete.avisos] == ["mês não encontrado"]


def test_arquivo_que_nao_e_balancete(tmp_path):
    arquivo = tmp_path / "outro.xls"
    arquivo.write_bytes("SCF - Movimento Estoque\nqualquer coisa\t1,00\n".encode("cp1252"))
    with pytest.raises(ErroArquivo, match="não parece ser um balancete"):
        ler_balancete_estoque(arquivo)


# ---------------------------------------------------------------------------
# Balancete do CMD e dos AMES: Débitos e Créditos no lugar do Movimento
# ---------------------------------------------------------------------------

CABECALHO_DEBITO_CREDITO = [
    "CMD - Fundação\t\t",
    "Balancete",
    "\t\t\t\t\t\tMês Referência:\t\t\tset/2026",
    "\tCódigo\t\tClassificação\t\tDescrição\t\t\tSaldo Anterior\t\tDébitos\t\tCréditos\tSaldo Atual",
]


def test_debitos_e_creditos_viram_movimento(tmp_path):
    balancete = _balancete(
        tmp_path,
        "\t\t114\t\t1.01.04\t  ESTOQUES\t\t\t100,00\t\t50,00\t\t30,00\t120,00",
        "\t\t500\t\t1.01.04.13.0001\t  Estoque X\t\t\t100,00\t\t50,00\t\t30,00\t120,00",
        cabecalho=CABECALHO_DEBITO_CREDITO,
    )
    conta = balancete.analiticas[0]
    assert (conta.codigo, conta.saldo_anterior, conta.movimento, conta.saldo_atual) == (
        500, Decimal("100.00"), Decimal("20.00"), Decimal("120.00"))
    assert balancete.mes_referencia == MesReferencia(2026, 9)
    assert balancete.avisos == []


def test_debitos_e_creditos_com_tres_numeros_gera_erro(tmp_path):
    balancete = _balancete(
        tmp_path,
        "\t\t500\t\t1.01.04.13.0001\t  Estoque X\t\t\t100,00\t\t20,00\t120,00",
        cabecalho=CABECALHO_DEBITO_CREDITO,
    )
    assert balancete.contas == []
    assert balancete.avisos[0].tipo == "linha não reconhecida"


def test_balancete_real_do_cmd():
    caminho = pasta_exemplos("conciliacao_estoque") / "balancete 09 cmd.xls"
    if not caminho.is_file():
        pytest.skip(f"Arquivo de exemplo {caminho} não encontrado")
    balancete = ler_balancete_estoque(caminho)
    assert balancete.mes_referencia == MesReferencia(2026, 9)
    assert len(balancete.analiticas) == 4
    assert balancete.avisos == []
    assert sum(c.saldo_atual for c in balancete.analiticas) == Decimal("20516.71")
