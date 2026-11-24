"""
Testes do comparador (Etapa 4).

- Casos sintéticos (dados inventados) da seção 8.3.
- Contagens do gabarito 8.1 e 8.2 com os exemplos reais (pula se exemplos/ não existir).
"""

from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import pytest

from modulos.conferencia_iss.comparador import (
    AVISO_PF_VARIOS_CANDIDATOS,
    AVISO_UNIDADES_MISTURADAS,
    comparar,
)
from modulos.conferencia_iss.leitor_prefeitura import ler_relatorio_prefeitura
from modulos.conferencia_iss.leitor_tasy import ler_csv_tasy
from modulos.conferencia_iss.modelos import (
    SITUACAO_CONFERIDA,
    SITUACAO_CONFERIDA_AJUSTADO,
    SITUACAO_CONFERIDA_SEM_CPF,
    SITUACAO_DIVERGENCIA,
    SITUACAO_SOMENTE_PREFEITURA,
    SITUACAO_SOMENTE_TASY,
    LinhaPrefeitura,
    NotaTasy,
    situacao_escriturada_varias_vezes,
)
from modulos.conferencia_iss.normalizar import (
    normalizar_documento,
    normalizar_numero,
    numero_ajustado,
)

ESCRITURADA_2 = situacao_escriturada_varias_vezes(2)


# ---------------------------------------------------------------------
# Fábricas de dados inventados
# ---------------------------------------------------------------------
def nota(numero, valor, documento="11222333000181", pf=False, arquivo="servico.csv",
         emitente="Fornecedor Teste", estabelecimento="Unidade A", codigo=None):
    return NotaTasy(
        arquivo=arquivo, linha=2, nota_fiscal=numero,
        numero=normalizar_numero(numero), numero_ajustado=numero_ajustado(numero),
        emitente=emitente, codigo_emitente=codigo or documento,
        documento="" if pf else normalizar_documento(documento),
        tipo_nota="Entrada por pessoa física" if pf else "Entrada",
        eh_pessoa_fisica=pf, valor_mercadoria=Decimal(valor),
        estabelecimento=estabelecimento,
    )


def linha(numero, valor, documento="11.222.333/0001-81", prestador="Prestador Teste"):
    return LinhaPrefeitura(
        linha=1, documento=normalizar_documento(documento), documento_original=documento,
        prestador=prestador, numero_doc=numero, numero=normalizar_numero(numero),
        valor_doc=None if valor is None else Decimal(valor),
    )


def situacoes(resultado):
    return [i.situacao for i in resultado.itens]


# ---------------------------------------------------------------------
# Regras básicas
# ---------------------------------------------------------------------
def test_conferida():
    r = comparar([nota("10", "100.00")], [linha("10", "100.00")])
    assert situacoes(r) == [SITUACAO_CONFERIDA]
    assert r.itens[0].diferenca == 0
    assert r.avisos == []


def test_diferenca_de_um_centavo_e_divergencia():                          # 8.3 caso 3
    r = comparar([nota("10", "100.01")], [linha("10", "100.00")])
    assert situacoes(r) == [SITUACAO_DIVERGENCIA]
    assert r.itens[0].diferenca == Decimal("0.01")


def test_valor_da_prefeitura_vazio_com_mesma_chave_e_divergencia():
    r = comparar([nota("10", "100.00")], [linha("10", None)])
    assert situacoes(r) == [SITUACAO_DIVERGENCIA]
    assert r.itens[0].diferenca is None


def test_numero_com_zeros_a_esquerda_casa():
    r = comparar([nota("000010", "5")], [linha("10", "5")])
    assert situacoes(r) == [SITUACAO_CONFERIDA]


def test_cpf_formatado_na_prefeitura_casa_com_documento_so_digitos():      # 8.3 caso 5
    r = comparar(
        [nota("7", "300", documento="12345678909")],
        [linha("7", "300", documento="123.456.789-09")],
    )
    assert situacoes(r) == [SITUACAO_CONFERIDA]


def test_mesmo_numero_documento_diferente_nao_casa():
    r = comparar([nota("10", "100")], [linha("10", "100", documento="99.888.777/0001-66")])
    assert situacoes(r) == [SITUACAO_SOMENTE_TASY, SITUACAO_SOMENTE_PREFEITURA]


def test_somente_tasy_e_somente_prefeitura():
    r = comparar([nota("1", "10")], [linha("2", "20")])
    assert situacoes(r) == [SITUACAO_SOMENTE_TASY, SITUACAO_SOMENTE_PREFEITURA]
    assert r.itens[0].linha_prefeitura is None
    assert r.itens[1].nota_tasy is None


# ---------------------------------------------------------------------
# Escriturada mais de uma vez
# ---------------------------------------------------------------------
def test_escriturada_duas_vezes_uma_linha_por_linha_da_prefeitura():
    r = comparar([nota("1", "7590.00")], [linha("1", "7590.00"), linha("1", "7123.21")])
    assert situacoes(r) == [ESCRITURADA_2, ESCRITURADA_2]
    assert [i.valor_confere for i in r.itens] == [True, False]
    assert r.itens[1].diferenca == Decimal("466.79")
    assert r.itens[0].nota_tasy is r.itens[1].nota_tasy


def test_escriturada_tres_vezes():
    r = comparar([nota("1", "5")], [linha("1", "5")] * 1 + [linha("1", "5"), linha("1", "6")])
    assert situacoes(r) == [situacao_escriturada_varias_vezes(3)] * 3


# ---------------------------------------------------------------------
# Número ajustado
# ---------------------------------------------------------------------
def test_numero_ajustado_com_mesmo_valor():
    r = comparar([nota("2026000000122", "6927.15")], [linha("122", "6927.15")])
    assert situacoes(r) == [SITUACAO_CONFERIDA_AJUSTADO]


def test_numero_ajustado_com_valor_diferente_nao_casa():                  # 8.3 caso 4
    r = comparar([nota("2026000000122", "6927.15")], [linha("122", "6927.16")])
    assert situacoes(r) == [SITUACAO_SOMENTE_TASY, SITUACAO_SOMENTE_PREFEITURA]


def test_numero_ajustado_exige_mesmo_documento():
    r = comparar(
        [nota("2026000000122", "10")],
        [linha("122", "10", documento="99.888.777/0001-66")],
    )
    assert situacoes(r) == [SITUACAO_SOMENTE_TASY, SITUACAO_SOMENTE_PREFEITURA]


def test_numero_ajustado_com_duas_linhas_iguais_nao_casa():
    r = comparar([nota("2026000000122", "10")], [linha("122", "10"), linha("122", "10")])
    assert situacoes(r) == [SITUACAO_SOMENTE_TASY] + [SITUACAO_SOMENTE_PREFEITURA] * 2


def test_numero_ajustado_nao_rouba_linha_de_nota_com_numero_exato():
    """A nota 2026000000122 vem antes no CSV, mas a linha 122 é da nota 122."""
    r = comparar(
        [nota("2026000000122", "10"), nota("122", "10")],
        [linha("122", "10")],
    )
    assert situacoes(r) == [SITUACAO_SOMENTE_TASY, SITUACAO_CONFERIDA]


# ---------------------------------------------------------------------
# Pessoa física
# ---------------------------------------------------------------------
def test_pf_com_um_candidato_conferida_sem_cpf():                           # 8.3 caso 1
    r = comparar(
        [nota("247", "1100", pf=True, codigo="1079616", emitente="Dra. Teste")],
        [linha("247", "1100", documento="123.456.789-09", prestador="TESTE MEDICA")],
    )
    assert situacoes(r) == [SITUACAO_CONFERIDA_SEM_CPF]
    item = r.itens[0]
    assert item.nota_tasy.emitente == "Dra. Teste"
    assert item.linha_prefeitura.prestador == "TESTE MEDICA"
    assert r.avisos == []


def test_pf_com_dois_candidatos_somente_tasy_e_aviso():                    # 8.3 caso 2
    r = comparar(
        [nota("247", "1100", pf=True, codigo="1079616")],
        [linha("247", "1100", documento="111.111.111-11"),
         linha("247", "1100", documento="222.222.222-22")],
    )
    assert situacoes(r) == [SITUACAO_SOMENTE_TASY] + [SITUACAO_SOMENTE_PREFEITURA] * 2
    assert len(r.avisos) == 1
    assert AVISO_PF_VARIOS_CANDIDATOS in r.avisos[0].mensagem


def test_pf_sem_candidato_somente_tasy():
    r = comparar([nota("247", "1100", pf=True)], [linha("247", "1000")])
    assert situacoes(r) == [SITUACAO_SOMENTE_TASY, SITUACAO_SOMENTE_PREFEITURA]
    assert r.avisos == []


def test_pf_nao_usa_linha_ja_casada_com_pj():
    r = comparar(
        [nota("247", "1100", pf=True), nota("247", "1100")],      # PF vem antes no CSV
        [linha("247", "1100")],
    )
    assert situacoes(r) == [SITUACAO_SOMENTE_TASY, SITUACAO_CONFERIDA]


def test_pf_ignora_codigo_do_tasy_como_documento():
    """O código interno (1079616) não pode ser usado como CPF na chave."""
    r = comparar(
        [nota("5", "10", pf=True, codigo="1079616")],
        [linha("5", "10", documento="1079616")],
    )
    assert situacoes(r) == [SITUACAO_CONFERIDA_SEM_CPF]


# ---------------------------------------------------------------------
# Avisos que juntam vários CSVs
# ---------------------------------------------------------------------
def test_nota_repetida_em_dois_csvs_avisa_e_ambas_aparecem():               # 8.3 caso 6
    r = comparar(
        [nota("10", "100", arquivo="servico.csv"), nota("10", "100", arquivo="honorario.csv")],
        [linha("10", "100")],
    )
    assert situacoes(r) == [SITUACAO_CONFERIDA, SITUACAO_CONFERIDA]
    assert len(r.avisos) == 1
    assert "mais de um CSV" in r.avisos[0].mensagem
    assert "servico.csv" in r.avisos[0].mensagem and "honorario.csv" in r.avisos[0].mensagem


def test_mesma_nota_repetida_no_mesmo_csv_nao_avisa_de_dois_csvs():
    r = comparar([nota("10", "1"), nota("10", "1")], [linha("10", "1")])
    assert r.avisos == []


def test_unidades_misturadas():
    r = comparar(
        [nota("1", "1", estabelecimento="Unidade A", arquivo="a.csv"),
         nota("2", "1", estabelecimento="Unidade B", arquivo="b.csv")],
        [],
    )
    assert len(r.avisos) == 1
    assert AVISO_UNIDADES_MISTURADAS in r.avisos[0].mensagem


# ---------------------------------------------------------------------
# Arquivos com problema não derrubam os outros (8.3 casos 7 e 8)
# O aviso por arquivo na aba Avisos é montado no processar() (Etapa 6).
# ---------------------------------------------------------------------
def _csv_tasy(pasta: Path, nome: str, cabecalho, linhas) -> Path:
    texto = "\r\n".join(
        ";".join(f'"{c}"' for c in registro) for registro in [cabecalho, *linhas]
    )
    caminho = pasta / nome
    caminho.write_bytes(texto.encode("utf-16-le"))
    return caminho


def test_csv_sem_codigo_emitente_nao_atrapalha_os_outros(tmp_path):         # 8.3 caso 7
    completo = ["Nota Fiscal", "Emitente", "Código emitente", "Tipo de nota", "Valor da mercadoria"]
    bom = _csv_tasy(tmp_path, "bom.csv", completo,
                    [["10", "Fornecedor", "11222333000181", "Entrada", "100,00"]])
    ruim = _csv_tasy(tmp_path, "ruim.csv", [c for c in completo if c != "Código emitente"],
                     [["20", "Outro", "Entrada", "50,00"]])
    leituras = [ler_csv_tasy(bom), ler_csv_tasy(ruim)]
    assert leituras[0].erro is None
    assert "Código emitente" in leituras[1].erro

    notas = [n for l in leituras for n in l.notas]
    r = comparar(notas, [linha("10", "100.00")])
    assert situacoes(r) == [SITUACAO_CONFERIDA]


def test_arquivos_invalidos_viram_erro_sem_excecao(tmp_path):              # 8.3 caso 8
    falso_csv = tmp_path / "foto.csv"
    falso_csv.write_bytes(bytes(range(256)) * 8)
    sem_tabela = tmp_path / "relatorio.xls"
    sem_tabela.write_text("<html>Nenhum registro</html>", encoding="utf-8")

    leitura_tasy = ler_csv_tasy(falso_csv)
    leitura_prefeitura = ler_relatorio_prefeitura(sem_tabela)
    assert leitura_tasy.erro and leitura_prefeitura.erro
    assert comparar(leitura_tasy.notas, leitura_prefeitura.linhas).itens == []


# ---------------------------------------------------------------------
# Gabarito 8.1 e 8.2 (exemplos reais) — contagens
# ---------------------------------------------------------------------
from testes.conferencia_iss.pastas_exemplos import PASTA_EXEMPLOS, PASTA_RB, caso_real  # noqa: E402
PASTA_2026_09 = PASTA_RB
CSV_PF = PASTA_EXEMPLOS / "pf" / "Notas_fiscais_PF_exemplo.csv"


def _rodar_exemplos(com_pf: bool):
    if not PASTA_EXEMPLOS.exists():
        pytest.skip("pasta exemplos/ não existe (dados reais ficam fora do git)")
    arquivos = [PASTA_2026_09 / "Servico_PJ_RB.csv", PASTA_2026_09 / "Honorario_PJ_RB.csv"]
    if com_pf:
        arquivos.append(CSV_PF)
    notas = [n for a in arquivos for n in ler_csv_tasy(a).notas]
    linhas = ler_relatorio_prefeitura(
        PASTA_2026_09 / "Relatorio_de_Servicos_Contratados.xls"
    ).linhas
    return notas, linhas, comparar(notas, linhas)


def _por_nota(resultado):
    """Situação → (quantidade de notas do Tasy, total mercadoria), contando cada nota uma vez."""
    vistas = defaultdict(dict)
    for item in resultado.itens:
        if item.nota_tasy is not None:
            vistas[item.situacao][id(item.nota_tasy)] = item.nota_tasy.valor_mercadoria
    return {s: (len(v), sum(v.values(), Decimal(0))) for s, v in vistas.items()}


def _itens(resultado, documento, numero):
    return [
        i for i in resultado.itens
        if (i.nota_tasy and i.nota_tasy.documento == documento and i.nota_tasy.numero == numero)
        or (i.nota_tasy is None and i.linha_prefeitura.documento == documento
            and i.linha_prefeitura.numero == numero)
    ]


def test_gabarito_8_1_contagens():
    notas, linhas, r = _rodar_exemplos(com_pf=False)
    assert len(notas) == 159
    contagem = _por_nota(r)
    assert contagem[SITUACAO_CONFERIDA] == (118, Decimal("1448484.54"))
    assert contagem[SITUACAO_CONFERIDA_AJUSTADO] == (1, Decimal("6927.15"))
    assert contagem[ESCRITURADA_2] == (4, Decimal("15412.39"))
    assert SITUACAO_DIVERGENCIA not in contagem
    assert contagem[SITUACAO_SOMENTE_TASY] == (36, Decimal("445180.46"))
    assert sum(q for q, _ in contagem.values()) == 159
    assert sum(t for _, t in contagem.values()) == Decimal("1916004.54")

    somente_pref = [i.linha_prefeitura for i in r.itens if i.situacao == SITUACAO_SOMENTE_PREFEITURA]
    assert len(somente_pref) == 3
    assert sum(l.valor_doc or 0 for l in somente_pref) == Decimal("9979.71")

    # Conservação: 118 + 1 + 8 + 3 = 130 linhas da prefeitura
    assert sum(1 for i in r.itens if i.situacao == ESCRITURADA_2) == 8
    linhas_no_relatorio = {id(i.linha_prefeitura) for i in r.itens if i.linha_prefeitura}
    assert len(linhas_no_relatorio) == len(linhas) == 130
    assert r.avisos == []


def test_gabarito_8_1_casos_especificos():
    _, _, r = _rodar_exemplos(com_pf=False)

    casos = caso_real("rb_8_1")

    ajustada = _itens(r, casos["numero_ajustado"], "2026000000122")
    assert [i.situacao for i in ajustada] == [SITUACAO_CONFERIDA_AJUSTADO]
    assert ajustada[0].linha_prefeitura.numero == "122"

    for documento, numero, valor in [
        (casos["escriturada_2_vezes_629"], "629", "667"),
        (casos["escriturada_2_vezes_12"], "12", "5308.39"),
        (casos["escriturada_2_vezes_6"], "6", "1847"),
    ]:
        itens = _itens(r, documento, numero)
        assert [i.situacao for i in itens] == [ESCRITURADA_2] * 2
        assert [i.valor_confere for i in itens] == [True, True]
        assert all(i.linha_prefeitura.valor_doc == Decimal(valor) for i in itens)
    assert [i.situacao for i in _itens(r, casos["escriturada_2_vezes_6"], "5")] == [SITUACAO_CONFERIDA]

    com_diferenca = _itens(r, casos["escriturada_2_vezes_com_diferenca"], "1")
    assert [i.situacao for i in com_diferenca] == [ESCRITURADA_2] * 2
    confere = {i.linha_prefeitura.valor_doc: (i.valor_confere, i.diferenca) for i in com_diferenca}
    assert confere[Decimal("7590")] == (True, Decimal("0"))
    assert confere[Decimal("7123.21")] == (False, Decimal("466.79"))

    assert [i.situacao for i in _itens(r, casos["somente_prefeitura_41"], "41")] == [SITUACAO_SOMENTE_PREFEITURA]
    assert [i.situacao for i in _itens(r, casos["somente_prefeitura_41"], "39")] == [SITUACAO_CONFERIDA]
    assert [i.situacao for i in _itens(r, casos["somente_prefeitura_5"], "5")] == [SITUACAO_SOMENTE_PREFEITURA]

    valor_vazio = _itens(r, casos["valor_vazio"], "8905486")
    assert [i.situacao for i in valor_vazio] == [SITUACAO_SOMENTE_PREFEITURA]
    assert valor_vazio[0].linha_prefeitura.valor_doc is None
    for numero in ("8804236", "8830033"):
        assert [i.situacao for i in _itens(r, casos["valor_vazio"], numero)] == [SITUACAO_SOMENTE_TASY]

    def somente_tasy_do_documento(documento):
        return sum(
            1 for i in r.itens
            if i.situacao == SITUACAO_SOMENTE_TASY and i.nota_tasy.documento == documento
        )

    # Hospital Exemplo tem outras 4 notas escrituradas na prefeitura (89669/70/71/74), que conferem.
    assert somente_tasy_do_documento("98765432000198") == 15
    assert somente_tasy_do_documento(casos["somente_tasy_5_notas"]) == 5

    nota_35048 = [i for i in r.itens if i.nota_tasy and i.nota_tasy.numero == "35048"]
    assert [(i.situacao, i.nota_tasy.valor_mercadoria) for i in nota_35048] == [
        (SITUACAO_SOMENTE_TASY, Decimal("24750"))
    ]
    do_prestador = {i.nota_tasy.numero: i for i in r.itens
                    if i.nota_tasy and i.nota_tasy.documento == casos["somente_tasy_96529"]}
    assert do_prestador["96529"].situacao == SITUACAO_SOMENTE_TASY
    assert do_prestador["96529"].nota_tasy.valor_mercadoria == Decimal("18157.06")
    assert do_prestador["96997"].situacao == SITUACAO_CONFERIDA


def test_gabarito_8_2_contagens_com_pessoa_fisica():
    notas, linhas, r = _rodar_exemplos(com_pf=True)
    assert len(notas) == 170
    contagem = _por_nota(r)
    assert contagem[SITUACAO_CONFERIDA][0] == 118
    assert contagem[SITUACAO_CONFERIDA_AJUSTADO][0] == 1
    assert contagem[ESCRITURADA_2][0] == 4
    assert SITUACAO_DIVERGENCIA not in contagem
    assert contagem[SITUACAO_SOMENTE_TASY][0] == 47
    assert sum(1 for i in r.itens if i.situacao == SITUACAO_SOMENTE_PREFEITURA) == 3

    mensagens = [a.mensagem for a in r.avisos]
    assert any(AVISO_UNIDADES_MISTURADAS in m for m in mensagens)
