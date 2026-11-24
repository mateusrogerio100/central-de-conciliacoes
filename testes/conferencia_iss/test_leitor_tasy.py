"""Testes do leitor dos CSVs do Tasy (Etapa 2)."""

from dataclasses import astuple
from decimal import Decimal
from pathlib import Path

import pytest

from modulos.conferencia_iss.leitor_tasy import detectar_codificacao, ler_csv_tasy

from testes.conferencia_iss.pastas_exemplos import PASTA_EXEMPLOS, PASTA_RB, caso_real  # noqa: E402
SERVICO = PASTA_RB / "Servico_PJ_RB.csv"
HONORARIO = PASTA_RB / "Honorario_PJ_RB.csv"
PF = PASTA_EXEMPLOS / "pf" / "Notas_fiscais_PF_exemplo.csv"


def _exige_exemplos():
    if not PASTA_EXEMPLOS.exists():
        pytest.skip("pasta exemplos/ não existe (dados reais ficam fora do git)")


# ---------------------------------------------------------------------
# Arquivos reais (gabarito seção 8)
# ---------------------------------------------------------------------
def test_servico_pj():
    _exige_exemplos()
    leitura = ler_csv_tasy(SERVICO)
    assert leitura.erro is None
    assert leitura.avisos == []
    assert len(leitura.notas) == 75
    assert sum(n.valor_mercadoria for n in leitura.notas) == Decimal("837034.43")
    assert all(not n.eh_pessoa_fisica for n in leitura.notas)


def test_honorario_pj():
    _exige_exemplos()
    leitura = ler_csv_tasy(HONORARIO)
    assert leitura.erro is None
    assert leitura.avisos == []
    assert len(leitura.notas) == 84
    assert sum(n.valor_mercadoria for n in leitura.notas) == Decimal("1078970.11")


def test_total_tasy_e_unidade_2026_09():
    _exige_exemplos()
    notas = ler_csv_tasy(SERVICO).notas + ler_csv_tasy(HONORARIO).notas
    assert len(notas) == 159
    assert sum(n.valor_mercadoria for n in notas) == Decimal("1916004.54")
    for arquivo in (SERVICO, HONORARIO):
        leitura = ler_csv_tasy(arquivo)
        assert leitura.estabelecimentos == [
            "AME - Cidade Beta (Fundação Hospital Exemplo)"
        ]
        assert leitura.unidades == ["AME Cidade Beta"]


def test_observacao_com_quebra_de_linha_lida_certo():
    """O arquivo tem mais linhas físicas que notas: as quebras estão dentro das aspas."""
    _exige_exemplos()
    texto = SERVICO.read_bytes().decode("utf-16-le")
    assert texto.count("\n") > 76            # 75 notas + cabeçalho
    leitura = ler_csv_tasy(SERVICO)
    assert len(leitura.notas) == 75
    # Se a quebra tivesse partido algum registro, valores e números estariam errados.
    assert all(n.numero.isdigit() for n in leitura.notas)
    assert all(len(n.documento) == 14 for n in leitura.notas)


def test_numero_ajustado_do_gabarito():
    _exige_exemplos()
    notas = ler_csv_tasy(HONORARIO).notas
    ajustada = [n for n in notas if n.nota_fiscal == "2026000000122"]
    assert len(ajustada) == 1
    assert ajustada[0].documento == caso_real("rb_8_1", "numero_ajustado")
    assert ajustada[0].numero_ajustado == "122"
    assert ajustada[0].valor_mercadoria == Decimal("6927.15")


def test_mercadoria_e_valor_da_nota_diferentes():
    _exige_exemplos()
    notas = ler_csv_tasy(HONORARIO).notas
    documento = caso_real("rb_8_1", "escriturada_2_vezes_com_diferenca")
    nota_1 = [n for n in notas if n.documento == documento and n.numero == "1"]
    assert len(nota_1) == 1
    assert nota_1[0].valor_mercadoria == Decimal("7590")
    assert nota_1[0].valor_nota == Decimal("7123.21")


def test_csv_pessoa_fisica():
    _exige_exemplos()
    leitura = ler_csv_tasy(PF)
    assert leitura.erro is None
    assert leitura.avisos == []
    assert len(leitura.notas) == 11

    pf = [n for n in leitura.notas if n.eh_pessoa_fisica]
    pj = [n for n in leitura.notas if not n.eh_pessoa_fisica]
    assert len(pf) == 9
    assert all(n.documento == "" for n in pf)          # código do Tasy não é CPF
    assert all(n.codigo_emitente for n in pf)          # mas continua guardado para exibição
    assert sorted(n.numero for n in pj) == ["828", "916"]   # as 2 notas PJ
    assert all(len(n.documento) == 14 for n in pj)

    assert leitura.estabelecimentos == ["Fundação Hospital Exemplo"]
    meses = {n.data_emissao[3:] for n in leitura.notas}
    assert meses == {f"{m:02d}/2026" for m in range(5, 10)}


def test_observacao_real_nao_vai_para_as_notas():
    """Nenhum texto da coluna Observação aparece em campo algum das notas (LGPD)."""
    _exige_exemplos()
    import csv
    import io

    texto = PF.read_bytes().decode("utf-16-le")
    registros = list(csv.reader(io.StringIO(texto, newline=""), delimiter=";"))
    posicao = registros[0].index("Observação")
    observacoes = {r[posicao].strip() for r in registros[1:] if len(r[posicao].strip()) > 10}
    assert observacoes, "o exemplo deveria ter observações preenchidas"

    campos = {str(v) for n in ler_csv_tasy(PF).notas for v in astuple(n)}
    assert not (observacoes & campos)


# ---------------------------------------------------------------------
# Casos inventados
# ---------------------------------------------------------------------
CABECALHO = [
    "Status", "Nota Fiscal", "Emitente", "Observação", "Série", "Data de emissão",
    "Data de entrada/saída", "Valor da nota", "Situação", "Valor da mercadoria",
    "Tipo de nota", "Estabelecimento", "Nome fantasia (Destinatário)", "Código emitente",
]


def _linha(nota="10", emitente="Fornecedor Teste Ltda", obs="", valor="100,5",
           liquido="90", situacao="Ativa", tipo="Entrada", codigo="11222333000181"):
    return ["Nota calculada", nota, emitente, obs, "1", "01/09/2026", "02/09/2026",
            liquido, situacao, valor, tipo, "Unidade Teste", "Teste", codigo]


def _gravar(pasta: Path, linhas, cabecalho=CABECALHO, codificacao="utf-16-le",
            nome="teste.csv") -> Path:
    def registro(campos):
        return ";".join('"' + c.replace('"', '""') + '"' for c in campos)

    texto = "\r\n".join(registro(r) for r in [cabecalho, *linhas]) + "\r\n"
    caminho = pasta / nome
    caminho.write_bytes(texto.encode(codificacao))
    return caminho


@pytest.mark.parametrize("codificacao", ["utf-16-le", "utf-16", "utf-8", "utf-8-sig", "cp1252"])
def test_detecta_codificacao_e_le_acentos(tmp_path, codificacao):
    caminho = _gravar(tmp_path, [_linha(emitente="Serviços Médicos Cidade Epsilon")],
                      codificacao=codificacao)
    leitura = ler_csv_tasy(caminho)
    assert leitura.erro is None
    assert leitura.notas[0].emitente == "Serviços Médicos Cidade Epsilon"
    assert leitura.notas[0].valor_mercadoria == Decimal("100.5")


def test_detectar_codificacao_direto():
    assert detectar_codificacao("ação".encode("utf-16")) == "utf-16"
    assert detectar_codificacao('"Nota"'.encode("utf-16-le")) == "utf-16-le"
    assert detectar_codificacao("ação".encode("utf-8")) == "utf-8-sig"
    assert detectar_codificacao("ação".encode("cp1252")) == "cp1252"


def test_colunas_em_outra_ordem(tmp_path):
    ordem = list(reversed(range(len(CABECALHO))))
    cabecalho = [CABECALHO[i] for i in ordem]
    linha = [_linha(nota="77", valor="12,34")[i] for i in ordem]
    leitura = ler_csv_tasy(_gravar(tmp_path, [linha], cabecalho=cabecalho))
    assert leitura.erro is None
    assert leitura.notas[0].numero == "77"
    assert leitura.notas[0].valor_mercadoria == Decimal("12.34")


def test_observacao_com_quebra_de_linha_e_aspas(tmp_path):
    obs = 'SEGREDO_LGPD primeira linha\r\nsegunda; com ponto e vírgula\n"aspas"'
    leitura = ler_csv_tasy(_gravar(tmp_path, [_linha(nota="1", obs=obs), _linha(nota="2")]))
    assert [n.numero for n in leitura.notas] == ["1", "2"]
    assert leitura.notas[1].linha == 5        # nota 1 ocupa as linhas 2 a 4
    campos = " ".join(str(v) for n in leitura.notas for v in astuple(n))
    assert "SEGREDO_LGPD" not in campos


def test_normaliza_numero_documento_e_pf(tmp_path):
    leitura = ler_csv_tasy(_gravar(tmp_path, [
        _linha(nota="000123", codigo="11.222.333/0001-81"),
        _linha(nota="55", tipo="Entrada por pessoa física", codigo="1079616"),
    ]))
    pj, pf = leitura.notas
    assert pj.numero == "123" and pj.nota_fiscal == "000123"
    assert pj.documento == "11222333000181"
    assert pf.eh_pessoa_fisica and pf.documento == "" and pf.codigo_emitente == "1079616"


def test_sem_coluna_obrigatoria_vira_erro(tmp_path):
    cabecalho = [c for c in CABECALHO if c != "Código emitente"]
    linha = _linha()[:-1]
    leitura = ler_csv_tasy(_gravar(tmp_path, [linha], cabecalho=cabecalho))
    assert leitura.notas == []
    assert "Código emitente" in leitura.erro


def test_arquivo_inexistente_vira_erro(tmp_path):
    leitura = ler_csv_tasy(tmp_path / "nao_existe.csv")
    assert leitura.erro and leitura.notas == []


def test_arquivo_vazio_vira_erro(tmp_path):
    caminho = tmp_path / "vazio.csv"
    caminho.write_bytes(b"")
    assert ler_csv_tasy(caminho).erro == "Arquivo vazio."


def test_arquivo_que_nao_e_csv_vira_erro(tmp_path):
    caminho = tmp_path / "planilha.csv"
    caminho.write_bytes(b"PK\x03\x04\x14\x00\x06\x00" + bytes(range(256)) * 4)
    leitura = ler_csv_tasy(caminho)
    assert leitura.erro is not None
    assert leitura.notas == []


def test_valor_invalido_vira_aviso_e_resto_continua(tmp_path):
    leitura = ler_csv_tasy(_gravar(tmp_path, [
        _linha(nota="1", valor="abc"),
        _linha(nota="2", valor=""),
        _linha(nota="3", valor="1.234,56"),
        _linha(nota="4", valor="50"),
    ]))
    assert leitura.erro is None
    assert [n.numero for n in leitura.notas] == ["4"]
    assert len(leitura.avisos) == 3
    assert all("não foi conferida" in a.mensagem for a in leitura.avisos)


def test_valor_da_nota_invalido_mantem_a_nota(tmp_path):
    leitura = ler_csv_tasy(_gravar(tmp_path, [_linha(liquido="xx")]))
    assert len(leitura.notas) == 1
    assert leitura.notas[0].valor_nota is None
    assert len(leitura.avisos) == 1


def test_sem_numero_vira_aviso(tmp_path):
    leitura = ler_csv_tasy(_gravar(tmp_path, [_linha(nota="")]))
    assert leitura.notas == []
    assert "sem número" in leitura.avisos[0].mensagem


def test_situacao_diferente_de_ativa_vira_aviso(tmp_path):
    leitura = ler_csv_tasy(_gravar(tmp_path, [_linha(situacao="Cancelada")]))
    assert len(leitura.notas) == 1
    assert "Cancelada" in leitura.avisos[0].mensagem


def test_linha_com_colunas_a_menos_vira_aviso(tmp_path):
    leitura = ler_csv_tasy(_gravar(tmp_path, [_linha(nota="1")[:5], _linha(nota="2")]))
    assert [n.numero for n in leitura.notas] == ["2"]
    assert "Linha 2" in leitura.avisos[0].mensagem


def test_linhas_em_branco_sao_ignoradas(tmp_path):
    leitura = ler_csv_tasy(_gravar(tmp_path, [_linha(nota="1"), [""] * len(CABECALHO)]))
    assert len(leitura.notas) == 1
    assert leitura.avisos == []
