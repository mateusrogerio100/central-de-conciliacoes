"""Etapa Tomados 3: regras (regras.py) e notas já escrituradas (conferencia.py).

- T1: só PDFs, sem resultado (Complementar, 28/09/2026) -> destinos do gabarito e arquivo
  teste1_..._08-2026.txt byte a byte. As notas 229/230 (emitidas em 08, competência 07) vai para
  "lançar à mão" pela V17 (07/10/2026); o gabarito e o teste1_..._07-2026.txt são de antes dela.
- T2: PDFs + todos os resultados_prefeitura (Complementar, 24/09/2026) -> já escrituradas e
  arquivo teste2_..._08-2026.txt byte a byte.
- Casos unitários com dados fictícios (rodam sempre).
"""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal

import pytest

from modulos.escrituracao_tomados import conferencia, gerador_txt, leitor_danfse, regras
from modulos.escrituracao_tomados.gerador_txt import normalizar_texto
from modulos.escrituracao_tomados.modelos import Competencia, Destino, NotaTomada
from testes.conftest import pasta_exemplos

AGOSTO = Competencia(2026, 8)
JULHO = Competencia(2026, 7)
MATRIZ = "98765432000198"


# ---------------------------------------------------------------------------
# Dados reais
# ---------------------------------------------------------------------------


def _ler_pdfs():
    notas, falhas = leitor_danfse.ler_pasta(
        pasta_exemplos("escrituracao_tomados", "2026-08", "pdfs"))
    assert falhas == []
    return notas


@pytest.fixture(scope="module")
def gabarito():
    arquivo = pasta_exemplos("escrituracao_tomados") / "gabarito_danfse.csv"
    with open(arquivo, encoding="utf-8-sig", newline="") as entrada:
        return {linha["arquivo_pdf"]: linha for linha in csv.DictReader(entrada, delimiter=";")}


@pytest.fixture(scope="module")
def t1():
    notas = _ler_pdfs()
    avisos = regras.classificar(notas)
    return notas, avisos


@pytest.fixture(scope="module")
def t2():
    pasta = pasta_exemplos("escrituracao_tomados", "2026-08", "resultados_prefeitura")
    escrituradas = conferencia.ler_resultados(sorted(pasta.glob("*.csv")))
    notas = _ler_pdfs()
    regras.classificar(notas, escrituradas)
    return notas, escrituradas


def _por_numero(notas, destino):
    return sorted((n.numero for n in notas if n.destino is destino), key=int)


def _conferir_arquivo(grupo, nome_esperado, data_lancamento):
    esperado = pasta_exemplos("escrituracao_tomados", "esperado") / nome_esperado
    conteudo = gerador_txt.gerar_conteudo(grupo.tomador_documento, grupo.competencia,
                                          data_lancamento, "C", grupo.notas)
    assert gerador_txt.conferir_conteudo(conteudo) == []
    assert nome_esperado.endswith(gerador_txt.nome_arquivo(grupo.tomador_documento,
                                                           grupo.competencia))
    assert conteudo.encode("latin-1") == esperado.read_bytes()


def test_t1_destinos(t1):
    notas, _ = t1
    assert _por_numero(notas, Destino.INCLUIDA) == [
        "95", "118", "215", "249", "337", "542",
        "29555", "29556", "29670", "29671", "45540", "2026000000090"]
    assert _por_numero(notas, Destino.LANCAR_A_MAO) == ["229", "230"]         # V17
    assert _por_numero(notas, Destino.NAO_INCLUIDA) == ["89504", "89509", "89525", "89554",
                                                        "89575"]
    coop = next(n for n in notas if n.numero == "2026000000090")         # R8: 8 últimos dígitos
    assert coop.numero_arquivo == "00000090"
    duplicadas = [n.arquivo for n in notas if n.destino is Destino.DUPLICADA]
    assert len(duplicadas) == 1 and duplicadas[0].startswith("copia_DANFSe-249")
    assert _por_numero(notas, Destino.JA_ESCRITURADA) == []
    assert all(n.destino is not None for n in notas)          # nada some em silêncio


MOTIVO_COMPETENCIA_07 = ("emitida em 08/2026, competência 07/2026 (o site só aceita no arquivo a nota "
                 "emitida no mês da competência)")


def test_t1_cada_nota_igual_ao_gabarito(t1, gabarito):
    """Destino, motivo e códigos. Nota que não será escriturada fica sem CFPS e sem código de
    retido (decisão de 28/09/2026: o gabarito traz 001/Z nessas linhas, que não são usadas)."""
    notas, _ = t1
    diferencas = []
    for nota in notas:
        linha = gabarito.get(nota.arquivo)
        if linha is None:
            continue
        escriturada = nota.destino in (Destino.INCLUIDA, Destino.LANCAR_A_MAO)
        destino, motivo = linha["destino_sem_resultado"], linha["motivo"]
        if nota.numero in ("229", "230"):          # V17: o gabarito é de antes da regra
            destino, motivo = "LANCAR_A_MAO", MOTIVO_COMPETENCIA_07
        esperado = {
            "destino": destino,
            "motivo": normalizar_texto(motivo),
            "cfps": linha["cfps"] if escriturada else "",
            "codigo_retido": linha["codigo_retencao"] if escriturada else "",
        }
        lido = {"destino": nota.destino.name, "motivo": normalizar_texto(nota.motivo),
                "cfps": nota.cfps, "codigo_retido": nota.codigo_retido}
        if lido != esperado:
            diferencas.append((nota.numero, esperado, lido))
    assert diferencas == []


def test_t1_arquivos_byte_a_byte(t1):
    notas, _ = t1
    grupos = regras.agrupar_para_arquivos(notas)
    assert [(g.tomador_documento, g.competencia, len(g.notas)) for g in grupos] == [
        (MATRIZ, AGOSTO, 12)]                     # julho só tinha as notas 229/230 (V17)
    (agosto,) = grupos
    _conferir_arquivo(agosto, "teste1_tomados_98765432000198_08-2026.txt", date(2026, 9, 28))
    assert normalizar_texto(agosto.tomador_nome).startswith("FUNDACAO HOSPITAL EXEMPLO")


def test_t1_avisos_so_dos_casos_esperados(t1):
    """Nas notas de agosto a incidência é sempre a cidade do prestador e o ISS confere."""
    _, avisos = t1
    assert [a for a in avisos if a.tipo != "ISS calculado diferente do informado"] == []
    assert avisos == []


def test_t2_ja_escrituradas(t2):
    notas, escrituradas = t2
    assert escrituradas.falhas == []
    ja = {n.numero: n.motivo for n in notas if n.destino is Destino.JA_ESCRITURADA}
    assert sorted(ja, key=int) == ["229", "230", "542", "29555", "29556", "29670", "29671",
                                   "45540"]
    assert "resultado07" in ja["229"] and "resultado07" in ja["230"]
    for numero in ("542", "29555", "29556", "29670", "29671", "45540"):
        assert "resultado08" in ja[numero], numero


def test_t2_demais_destinos_e_arquivo(t2):
    notas, _ = t2
    assert _por_numero(notas, Destino.INCLUIDA) == ["95", "118", "215", "249", "337",
                                                    "2026000000090"]
    assert _por_numero(notas, Destino.LANCAR_A_MAO) == []
    assert _por_numero(notas, Destino.NAO_INCLUIDA) == ["89504", "89509", "89525", "89554",
                                                        "89575"]
    grupos = regras.agrupar_para_arquivos(notas)
    assert [(g.competencia, len(g.notas)) for g in grupos] == [(AGOSTO, 6)]
    _conferir_arquivo(grupos[0], "teste2_tomados_98765432000198_08-2026.txt", date(2026, 9, 24))


def test_t2_a_215_usa_z_pela_incidencia(t2):
    notas, _ = t2
    nota = next(n for n in notas if n.numero == "215")
    assert (nota.codigo_retido, nota.cfps) == ("Z", "001")


# ---------------------------------------------------------------------------
# Regras com dados fictícios
# ---------------------------------------------------------------------------


def nota(**mudancas) -> NotaTomada:
    dados = dict(
        numero="100", data_emissao=date(2026, 8, 5), competencia=AGOSTO,
        prestador_documento="12345678000195", prestador_nome="Clinica Exemplo",
        prestador_cidade="Cidade Alfa", prestador_uf="SP", tomador_documento=MATRIZ,
        situacao="Autorizada", regime="N", codigo_atividade="040101",
        local_prestacao="Cidade Alfa", tipo_tributacao="Operação Tributável",
        municipio_incidencia="Cidade Alfa", valor_servico=Decimal("1000.00"),
        aliquota=Decimal("2.00"), valor_iss=Decimal("20.00"), iss_retido=False, origem="PDF",
        arquivo="nota.pdf",
    )
    dados.update(mudancas)
    return NotaTomada(**dados)


ZERO = Decimal("0.00")
SEM_FEDERAL = dict(irrf=ZERO, previdencia_retida=ZERO, contribuicoes_retidas=ZERO)


def falar(n) -> tuple[bool, list]:
    regras.classificar([n])
    avisos = regras.marcar_falar_com_fornecedor([n])
    return n.falar_com_fornecedor, avisos


def test_r19_nao_optante_sem_federal_retido_vai_para_falar_com_o_fornecedor():
    assert falar(nota(**SEM_FEDERAL)) == (True, [])
    # o ISS não entra na regra
    assert falar(nota(**SEM_FEDERAL, iss_retido=True, municipio_incidencia="Cidade Alfa"))[0]


@pytest.mark.parametrize("mudanca", [
    dict(irrf=Decimal("15.00")),
    dict(previdencia_retida=Decimal("110.00")),
    dict(contribuicoes_retidas=Decimal("46.50")),
])
def test_r19_qualquer_federal_retido_tira_da_lista(mudanca):
    assert falar(nota(**{**SEM_FEDERAL, **mudanca})) == (False, [])


@pytest.mark.parametrize("mudanca", [
    dict(regime="S"), dict(regime="M"),                         # optante do Simples, MEI
    dict(situacao="Cancelada"),
    dict(prestador_documento="98765432000198"),                 # serviço prestado pela Fundação
    dict(tomador_documento="11222333000181"),                   # tomador de fora
    dict(origem="Exportação"),                                  # o site não traz os federais
])
def test_r19_fora_da_lista(mudanca):
    assert falar(nota(**{**SEM_FEDERAL, **mudanca})) == (False, [])


def test_r19_duplicada_e_ja_escriturada():
    duplicada = nota(**SEM_FEDERAL, destino=Destino.DUPLICADA)
    assert regras.marcar_falar_com_fornecedor([duplicada]) == []
    assert not duplicada.falar_com_fornecedor
    escriturada = nota(**SEM_FEDERAL, destino=Destino.JA_ESCRITURADA)
    regras.marcar_falar_com_fornecedor([escriturada])
    assert escriturada.falar_com_fornecedor


def test_r19_federal_nao_lido_vira_aviso():
    marcada, avisos = falar(nota(irrf=ZERO, previdencia_retida=None, contribuicoes_retidas=ZERO))
    assert not marcada
    assert [a.tipo for a in avisos] == ["Impostos federais não lidos"]


def classificar_uma(n, escrituradas=None):
    avisos = regras.classificar([n], escrituradas)
    return n, avisos


@pytest.mark.parametrize("situacao, motivo", [
    ("Cancelada", "nota cancelada"), ("Substituída", "nota substituída"),
    ("Bloqueada", "situação não prevista: Bloqueada"),
])
def test_situacao_fora_de_autorizada(situacao, motivo):
    n, _ = classificar_uma(nota(situacao=situacao))
    assert (n.destino, n.motivo) == (Destino.NAO_INCLUIDA, motivo)
    assert (n.cfps, n.codigo_retido) == ("", "")


def test_tomador_que_nao_e_da_fundacao():
    n, _ = classificar_uma(nota(tomador_documento="11222333000181"))
    assert n.destino is Destino.NAO_INCLUIDA and "tomador" in n.motivo


def test_filial_da_fundacao_como_tomador_entra():
    n, _ = classificar_uma(nota(tomador_documento="98765432000945"))
    assert n.destino is Destino.INCLUIDA


def test_outro_cnpj_da_fundacao_de_outra_raiz():
    """R1 (Usuário, 01/10/2026): CNPJ de outra raiz informado na tela (ex.: um AME) entra, num
    arquivo próprio; como prestador, é serviço prestado."""
    ame = "11.222.333/0001-81"
    n, _ = classificar_uma(nota(tomador_documento="11222333000181"))
    assert n.destino is Destino.NAO_INCLUIDA                      # sem estar na lista: fora
    notas = [nota(numero="1"), nota(numero="2", tomador_documento="11222333000181")]
    regras.classificar(notas, outros_cnpjs=[ame])
    assert [x.destino for x in notas] == [Destino.INCLUIDA, Destino.INCLUIDA]
    assert sorted((g.tomador_documento, [x.numero for x in g.notas])
                  for g in regras.agrupar_para_arquivos(notas)) == [("11222333000181", ["2"]),
                                                                     (MATRIZ, ["1"])]
    n = nota(prestador_documento="11222333000181")
    regras.classificar([n], outros_cnpjs=[ame])
    assert n.destino is Destino.NAO_INCLUIDA and "serviço prestado" in n.motivo


def test_cpf_que_comeca_como_a_raiz_da_fundacao_nao_e_a_fundacao():
    n, _ = classificar_uma(nota(prestador_documento="98765432000"))    # CPF (11 dígitos)
    assert n.destino is Destino.INCLUIDA


@pytest.mark.parametrize("mudanca, trecho", [
    ({"desconto_incondicionado": Decimal("57.03")}, "R$ 57,03"),
    ({"tipo_tributacao": "Imune"}, "Imune"),
])
def test_lancar_a_mao(mudanca, trecho):
    n, _ = classificar_uma(nota(**mudanca))
    assert n.destino is Destino.LANCAR_A_MAO and trecho in n.motivo
    assert (n.cfps, n.codigo_retido) == ("001", "N")          # prontos para digitar


def test_varios_motivos_para_lancar_a_mao_aparecem_juntos():
    n, _ = classificar_uma(nota(tipo_tributacao="Isenta", desconto_incondicionado=Decimal("1.00")))
    assert "Isenta" in n.motivo and "R$ 1,00" in n.motivo


# ---------------------------------------------------------------------------
# R8: número com mais de 8 dígitos entra com os 8 últimos (decisão da chefia, 28/09/2026)
# ---------------------------------------------------------------------------


def test_numero_longo_entra_com_os_8_ultimos_digitos():
    n, _ = classificar_uma(nota(numero="2026000000090"))
    assert (n.destino, n.numero_arquivo) == (Destino.INCLUIDA, "00000090")
    assert n.motivo == "número ajustado para 00000090: corrigir no site para 2026000000090"
    assert gerador_txt.montar_detalhe(n)[178:186] == "00000090"


def test_numero_longo_com_outro_motivo_continua_em_lancar_a_mao():
    n, _ = classificar_uma(nota(numero="2026000000090", tipo_tributacao="Isenta"))
    assert n.destino is Destino.LANCAR_A_MAO and n.numero_arquivo == ""
    assert "Isenta" in n.motivo


def test_numero_ajustado_que_ja_existe_no_site_com_outro_valor_vai_para_lancar_a_mao(tmp_path):
    """O site recusaria o arquivo inteiro por nota repetida (V3)."""
    n, _ = classificar_uma(nota(numero="2026000000090"),
                           _resultado_com(tmp_path, "90;12.345.678/0001-95;5,00"))
    assert n.destino is Destino.LANCAR_A_MAO and n.numero_arquivo == ""
    assert "número ajustado (90) já existe no site" in n.motivo


def test_numero_ajustado_repetido_no_mesmo_arquivo_vai_para_lancar_a_mao():
    curta = nota(numero="90", arquivo="a.pdf")
    longa = nota(numero="2026000000090", arquivo="b.pdf")
    outra_longa = nota(numero="2025000000091", arquivo="c.pdf")
    regras.classificar([longa, curta, outra_longa])
    assert curta.destino is Destino.INCLUIDA                             # a nota 90 de verdade
    assert longa.destino is Destino.LANCAR_A_MAO and "repetiria outra nota" in longa.motivo
    assert outra_longa.numero_arquivo == "00000091"


def test_numero_ajustado_de_outro_prestador_ou_mes_nao_conflita():
    longa = nota(numero="2026000000090")
    outro_prestador = nota(numero="90", prestador_documento="99999999000191")
    outro_mes = nota(numero="90", competencia=JULHO)
    regras.classificar([longa, outro_prestador, outro_mes])
    assert longa.numero_arquivo == "00000090"


def test_ordem_no_arquivo_pelo_numero_ajustado():
    notas = [nota(numero="95"), nota(numero="2026000000090")]
    regras.classificar(notas)
    assert [n.numero for n in gerador_txt.ordenar_notas(notas)] == ["2026000000090", "95"]


def test_ja_escriturada_vence_lancar_a_mao(tmp_path):
    """Decisão de 28/09/2026: nota já digitada no site não volta para a lista de digitação."""
    resultado = tmp_path / "resultado.csv"
    resultado.write_text("cfps;nfs;cnpjcpf;\n1;2026000000090;12.345.678/0001-95;\n",
                         encoding="latin-1")
    escrituradas = conferencia.ler_resultados([resultado])
    n, _ = classificar_uma(nota(numero="2026000000090"), escrituradas)
    assert (n.destino, n.motivo) == (Destino.JA_ESCRITURADA, "já escriturada (resultado.csv)")


@pytest.mark.parametrize("longo, curto, equivale", [
    ("2026000003076", "3076", True), ("2600000000027", "27", True), ("2600000000027", "0027", True),
    ("2026000013076", "3076", False), ("2026000003076", "307", False), ("3076", "3076", False),
])
def test_numero_curto_equivale(longo, curto, equivale):
    assert conferencia.numero_curto_equivale(longo, curto) is equivale


def _resultado_com(tmp_path, *linhas):
    caminho = tmp_path / "resultado08.csv"
    caminho.write_text("nfs;cnpjcpf;vlrservicos\n" + "\n".join(linhas) + "\n", encoding="latin-1")
    return conferencia.ler_resultados([caminho])


def test_numero_longo_digitado_curto_no_site_e_ja_escriturada(tmp_path):
    """Decisão de 28/09/2026 (caso da nota 2026000003076, digitada no site como 3076)."""
    escrituradas = _resultado_com(tmp_path, "3076;12.345.678/0001-95;28.579,02")
    n, _ = classificar_uma(nota(numero="2026000003076", valor_servico=Decimal("28579.02")),
                           escrituradas)
    assert (n.destino, n.motivo) == (Destino.JA_ESCRITURADA,
                                     "já escriturada (resultado08.csv, digitada como 3076)")


@pytest.mark.parametrize("linha, destino", [
    # mesmo número com valor diferente: não é "já escriturada", e o ajuste repetiria o número
    ("3076;12.345.678/0001-95;28.579,01", Destino.LANCAR_A_MAO),
    ("3076;99.999.999/0001-91;28.579,02", Destino.INCLUIDA),      # outro prestador
    ("13076;12.345.678/0001-95;28.579,02", Destino.INCLUIDA),     # não é o final inteiro do número
])
def test_numero_curto_sem_todas_as_condicoes_nao_conta(tmp_path, linha, destino):
    n, _ = classificar_uma(nota(numero="2026000003076", valor_servico=Decimal("28579.02")),
                           _resultado_com(tmp_path, linha))
    assert n.destino is destino


def test_numero_curto_so_vale_para_nota_de_numero_longo(tmp_path):
    """Nota 76 (curta) não é confundida com uma 3076 do site."""
    n, _ = classificar_uma(nota(numero="76", valor_servico=Decimal("10.00")),
                           _resultado_com(tmp_path, "3076;12.345.678/0001-95;10,00"))
    assert n.destino is Destino.INCLUIDA


def test_cancelada_vence_ja_escriturada(tmp_path):
    resultado = tmp_path / "r.csv"
    resultado.write_text("nfs;cnpjcpf\n100;12345678000195\n", encoding="latin-1")
    n, _ = classificar_uma(nota(situacao="Cancelada"), conferencia.ler_resultados([resultado]))
    assert n.motivo == "nota cancelada"


def test_duplicada_da_leitura_fica_como_esta():
    n = nota(destino=Destino.DUPLICADA, motivo="duplicado na pasta")
    classificar_uma(n)
    assert (n.destino, n.motivo, n.cfps) == (Destino.DUPLICADA, "duplicado na pasta", "")


@pytest.mark.parametrize("retido, incidencia, cidade, codigo", [
    (False, "Cidade Alfa", "Cidade Alfa", "N"), (True, "Cidade Alfa", "Cidade Alfa", "S"),
    (False, "Cidade Beta", "Cidade Beta", "Z"), (True, "Uberaba", "Uberaba", "X"),
    (False, "", "Cidade Alfa", "N"), (False, "", "Indaiatuba", "Z"),
])
def test_codigo_de_retido(retido, incidencia, cidade, codigo):
    n, _ = classificar_uma(nota(iss_retido=retido, municipio_incidencia=incidencia,
                                prestador_cidade=cidade))
    assert n.codigo_retido == codigo


def test_prestacao_em_cidade_alfa_com_prestador_e_incidencia_fora_e_z_sem_aviso():
    """Caso da nota 337: local Cidade Alfa, prestador e incidência Cidade Beta."""
    n, avisos = classificar_uma(nota(prestador_cidade="Cidade Beta",
                                     municipio_incidencia="Cidade Beta"))
    assert (n.cfps, n.codigo_retido, avisos) == ("001", "Z", [])


def test_incidencia_diferente_da_cidade_do_prestador_avisa_e_vai_para_lancar_a_mao():
    """Caso da nota 144 (09/2026): o site recusou o N ("Esperado o valor S")."""
    n, avisos = classificar_uma(nota(prestador_cidade="São José da Bela Vista",
                                     municipio_incidencia="Cidade Alfa"))
    assert n.codigo_retido == "N"
    assert [a.tipo for a in avisos] == ["Incidência diferente da cidade do prestador"]
    assert n.destino is Destino.LANCAR_A_MAO
    assert n.motivo == ("ISS devido em CIDADE ALFA, prestador de SAO JOSE DA BELA VISTA, não retido (o "
                        "site recusa o imposto retido da nota)")


def test_incidencia_diferente_retida_continua_no_arquivo():
    """Caso da nota 3115 (09/2026): retida, código S, aceita pelo site (V16)."""
    n, avisos = classificar_uma(nota(prestador_cidade="Cidade Beta", municipio_incidencia="Cidade Alfa",
                                     iss_retido=True))
    assert (n.destino, n.motivo, n.codigo_retido) == (Destino.INCLUIDA, "", "S")
    assert [a.tipo for a in avisos] == ["Incidência diferente da cidade do prestador"]


def test_incidencia_diferente_junta_com_outro_motivo_de_lancar_a_mao():
    n, _ = classificar_uma(nota(prestador_cidade="Cidade Beta", municipio_incidencia="Cidade Alfa",
                                desconto_incondicionado=Decimal("10.00")))
    assert n.destino is Destino.LANCAR_A_MAO and n.codigo_retido == "N"
    assert "desconto incondicionado" in n.motivo and "prestador de CIDADE BETA" in n.motivo


def test_incidencia_vazia_avisa_e_usa_a_cidade():
    n, avisos = classificar_uma(nota(municipio_incidencia="", prestador_cidade="Uberaba"))
    assert n.codigo_retido == "Z"
    assert [a.tipo for a in avisos] == ["Incidência vazia"]


def test_sem_cidade_e_sem_incidencia_vai_para_lancar_a_mao():
    n, _ = classificar_uma(nota(municipio_incidencia="", prestador_cidade=""))
    assert n.destino is Destino.LANCAR_A_MAO and "cidade do prestador" in n.motivo
    assert n.codigo_retido == ""


def test_cfps_pelo_local_da_prestacao():
    assert classificar_uma(nota(local_prestacao="CIDADE ALFA"))[0].cfps == "001"
    assert classificar_uma(nota(local_prestacao="Indaiatuba"))[0].cfps == "002"


def test_iss_diferente_do_calculado_so_avisa():
    n, avisos = classificar_uma(nota(valor_iss=Decimal("25.00")))
    assert n.destino is Destino.INCLUIDA
    assert [a.tipo for a in avisos] == ["ISS calculado diferente do informado"]
    assert "R$ 5,00" in avisos[0].mensagem
    _, avisos = classificar_uma(nota(valor_iss=Decimal("20.01")))       # até 1 centavo: ok
    assert avisos == []


def test_iss_zerado_com_aliquota_vai_com_o_iss_calculado():
    """Caso da nota 69 (08/2026): o site recusou imposto 0 e exige 325,14.
    Decisão de 28/09/2026."""
    n, avisos = classificar_uma(nota(valor_servico=Decimal("16176.00"), aliquota=Decimal("2.01"),
                                     valor_iss=Decimal("0.00"), regime="S"))
    assert (n.destino, n.valor_iss, n.iss_calculado) == (Destino.INCLUIDA, Decimal("325.14"), True)
    assert [a.tipo for a in avisos] == ["ISS da nota zerado: usado o calculado"]
    assert "R$ 325,14" in avisos[0].mensagem
    assert gerador_txt.montar_detalhe(n)[227:241] == "00000000032514"


def test_iss_calculado_continua_avisando_na_segunda_classificacao():
    """O processamento classifica duas vezes (antes e depois de achar as cidades)."""
    n = nota(valor_servico=Decimal("360.00"), aliquota=Decimal("3.00"), valor_iss=Decimal("0.00"))
    regras.classificar([n])
    avisos = regras.classificar([n])
    assert n.valor_iss == Decimal("10.80")
    assert [a.tipo for a in avisos] == ["ISS da nota zerado: usado o calculado"]


@pytest.mark.parametrize("mudanca", [
    {"aliquota": Decimal("0.00")},                                   # sem alíquota: 0 está certo
    {"valor_iss": Decimal("20.00")},                                 # ISS informado: vale o da nota
])
def test_iss_nao_e_mexido_fora_do_caso(mudanca):
    dados = dict(valor_iss=Decimal("0.00"))
    dados.update(mudanca)
    n, _ = classificar_uma(nota(**dados))
    assert n.iss_calculado is False and n.valor_iss == dados["valor_iss"]


def test_iss_de_nota_nao_escriturada_nao_e_mexido():
    n, _ = classificar_uma(nota(situacao="Cancelada", valor_iss=Decimal("0.00")))
    assert n.valor_iss == Decimal("0.00") and not n.iss_calculado


@pytest.mark.parametrize("servico, iss, aliquota", [
    ("29.00", "0.94", "3.24"),          # nota 10418
    ("1000.00", "20.00", "2.00"),
    ("333.33", "10.00", "3.00"),        # 333,33 x 3% = 9,9999 -> 10,00
])
def test_aliquota_em_branco_e_calculada_pelo_iss(servico, iss, aliquota):
    n, avisos = classificar_uma(nota(valor_servico=Decimal(servico), valor_iss=Decimal(iss),
                                     aliquota=Decimal("0.00")))
    assert (n.destino, n.aliquota, n.aliquota_calculada) == (Destino.INCLUIDA, Decimal(aliquota), True)
    assert regras.iss_calculado(n) == Decimal(iss)                     # o site chega no mesmo ISS
    assert "Alíquota em branco: calculada" in [a.tipo for a in avisos]
    assert "ISS calculado diferente do informado" not in [a.tipo for a in avisos]


def test_aliquota_que_nao_leva_ao_iss_vai_para_lancar_a_mao():
    """R$ 10.000,00 com ISS de R$ 0,01: a menor alíquota de 2 casas (0,01%) já dá R$ 1,00."""
    n, _ = classificar_uma(nota(valor_servico=Decimal("10000.00"), valor_iss=Decimal("0.01"),
                                aliquota=Decimal("0.00")))
    assert n.destino is Destino.LANCAR_A_MAO and "alíquota em branco" in n.motivo
    assert n.aliquota == Decimal("0.00")


def test_aliquota_calculada_continua_avisando_na_segunda_classificacao():
    n = nota(valor_servico=Decimal("29.00"), valor_iss=Decimal("0.94"), aliquota=Decimal("0.00"))
    regras.classificar([n])
    avisos = regras.classificar([n])
    assert n.aliquota == Decimal("3.24")
    assert [a.tipo for a in avisos] == ["Alíquota em branco: calculada"]


def test_conferencia_do_iss_usa_a_base_da_nota():
    n, avisos = classificar_uma(nota(valor_servico=Decimal("3213.18"), base_calculo=Decimal("3156.15"),
                                     desconto_incondicionado=Decimal("57.03"), aliquota=Decimal("3.00"),
                                     valor_iss=Decimal("94.68")))
    assert "ISS calculado diferente do informado" not in [a.tipo for a in avisos]


def test_sem_bc_a_base_desconta_deducoes_e_desconto_incondicionado():
    n = nota(valor_servico=Decimal("3213.18"), desconto_incondicionado=Decimal("57.03"))
    assert regras.base_da_nota(n) == Decimal("3156.15")


def test_nota_no_arquivo_com_base_diferente_do_que_o_site_calcula_avisa():
    """Ex.: benefício municipal reduzindo a BC — o site recalcula sobre serviço - deduções."""
    n, avisos = classificar_uma(nota(valor_servico=Decimal("1000.00"), base_calculo=Decimal("800.00"),
                                     aliquota=Decimal("2.00"), valor_iss=Decimal("16.00")))
    assert n.destino is Destino.INCLUIDA
    assert [a.tipo for a in avisos] == ["Base de cálculo diferente de serviço - deduções"]


def test_agrupamento_por_tomador_e_competencia():
    notas = [nota(numero="1"), nota(numero="2", competencia=JULHO, data_emissao=date(2026, 7, 31)),
             nota(numero="3", tomador_documento="98765432000945"),
             nota(numero="4", situacao="Cancelada")]
    regras.classificar(notas)
    grupos = regras.agrupar_para_arquivos(notas)
    assert [(g.tomador_documento, g.competencia, [n.numero for n in g.notas])
            for g in grupos] == [
        (MATRIZ, JULHO, ["2"]), (MATRIZ, AGOSTO, ["1"]), ("98765432000945", AGOSTO, ["3"])]


@pytest.mark.parametrize("emissao", [date(2026, 9, 2), date(2026, 7, 31), date(2025, 8, 5)])
def test_emitida_fora_da_competencia_vai_para_lancar_a_mao(emissao):
    """V17: o site recusa a nota cuja emissão não está no mês de referência (caso das notas
    emitidas em 02/10/2026 com competência 09/2026)."""
    n, _ = classificar_uma(nota(data_emissao=emissao))
    assert n.destino is Destino.LANCAR_A_MAO
    assert n.motivo == (f"emitida em {emissao:%m/%Y}, competência 08/2026 (o site só aceita no "
                        "arquivo a nota emitida no mês da competência)")
    assert (n.cfps, n.codigo_retido) == ("001", "N")          # a pessoa digita com os códigos
    assert regras.agrupar_para_arquivos([n]) == []


def test_emitida_no_ultimo_dia_do_mes_da_competencia_entra():
    n, _ = classificar_uma(nota(data_emissao=date(2026, 8, 31)))
    assert n.destino is Destino.INCLUIDA


def test_emitida_fora_da_competencia_mas_ja_escriturada():
    """Já escriturada vem antes de lançar à mão: não volta para a lista de digitação."""
    escrituradas = conferencia.NotasEscrituradas()
    escrituradas.por_chave[conferencia.chave_nota("100", "12345678000195")] = "resultado.csv"
    n, _ = classificar_uma(nota(data_emissao=date(2026, 9, 2)), escrituradas)
    assert n.destino is Destino.JA_ESCRITURADA


# ---------------------------------------------------------------------------
# Conferência (resultados da prefeitura)
# ---------------------------------------------------------------------------


def test_chave_ignora_zeros_e_pontuacao():
    assert conferencia.chave_nota("000542", "33.444.555/0001-81") == ("542", "33444555000181")


def test_resultado_com_tabulacao_e_com_ponto_e_virgula(tmp_path):
    (tmp_path / "a.txt").write_text("cfps\tnfs\tcnpjcpf\t\n1\t0249\t44.555.666/0001-81\t\n",
                                    encoding="latin-1")
    (tmp_path / "b.csv").write_text("NFS;CnpjCpf;nome\n542;33444555000181;CLÍNICA ZÉLIA\n\n",
                                    encoding="latin-1")
    escrituradas = conferencia.ler_resultados([tmp_path / "a.txt", tmp_path / "b.csv"])
    assert escrituradas.arquivo_da_nota("249", "44555666000181") == "a.txt"
    assert escrituradas.arquivo_da_nota("542", "33.444.555/0001-81") == "b.csv"
    assert escrituradas.arquivo_da_nota("542", "99999999000199") is None   # outro prestador
    assert escrituradas.linhas_por_arquivo == {"a.txt": 1, "b.csv": 1}


def test_resultado_invalido_vira_falha_e_os_outros_continuam(tmp_path):
    (tmp_path / "planilha.csv").write_text("coluna;outra\n1;2\n", encoding="latin-1")
    (tmp_path / "bom.csv").write_text("nfs;cnpjcpf\n1;12345678000195\n", encoding="latin-1")
    escrituradas = conferencia.ler_resultados(
        [tmp_path / "planilha.csv", tmp_path / "nao_existe.csv", tmp_path / "bom.csv"])
    assert [f.arquivo for f in escrituradas.falhas] == ["planilha.csv", "nao_existe.csv"]
    assert "nfs" in escrituradas.falhas[0].motivo
    assert escrituradas.arquivo_da_nota("1", "12345678000195") == "bom.csv"


def test_sem_resultados():
    assert conferencia.ler_resultados(None).por_chave == {}
