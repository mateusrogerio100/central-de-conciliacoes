"""EFD 1 — leitura da DANFSe (R1–R4) e do SPED do mês anterior (ESPECIFICACAO_EFD_CONTRIBUICOES.md)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from modulos.efd_contribuicoes.leitor_danfse import PF, PJ, interpretar_danfse, ler_danfse, valor_para_decimal
from modulos.efd_contribuicoes.leitor_sped import ErroSped, ler_molde, previa_sped
from testes.efd_contribuicoes.conftest import LINHAS_SPED_FICTICIO, exemplo_efd, gravar_sped

D = Decimal

# ---------------------------------------------------------------------------
# DANFSe reais (exemplos fora do git): os valores esperados são os que a aplicação original já extraía
# ---------------------------------------------------------------------------

ESPERADO_DANFSE = {
    # número: (competência, data de emissão, PJ/PF, dígitos do documento, Código IBGE, valor)
    "89504": ("08/2026", date(2026, 8, 3), PJ, 14, "3516200", D("1850.61")),
    "89509": ("08/2026", date(2026, 8, 4), PJ, 14, "3509502", D("30017.71")),
    "89525": ("08/2026", date(2026, 8, 6), PJ, 14, "3516200", D("2462.29")),
    "89554": ("08/2026", date(2026, 8, 19), PF, 11, "3516200", D("30.00")),
    "89575": ("08/2026", date(2026, 8, 26), PF, 11, "3516200", D("27.50")),
}


@pytest.mark.parametrize("numero", sorted(ESPERADO_DANFSE))
def test_danfse_reais(numero):
    nota = ler_danfse(exemplo_efd("danfse", f"danfse_{numero}.pdf"))
    competencia, emissao, tipo, digitos, ibge, valor = ESPERADO_DANFSE[numero]
    assert nota.lida, nota.status
    assert nota.numero_nfse == numero
    assert (nota.competencia, nota.data_emissao, nota.tipo_pessoa) == (competencia, emissao, tipo)
    assert len(nota.cnpj_digitos) == digitos
    assert (nota.codigo_ibge_tomador, nota.valor) == (ibge, valor)
    assert nota.prestador and nota.tomador
    assert nota.mes_competencia == nota.mes_emissao == (2026, 8)


# ---------------------------------------------------------------------------
# DANFSe montada à mão (texto e palavras como o pdfplumber devolve; dados fictícios)
# ---------------------------------------------------------------------------

def _palavras(linhas):
    """[(top, [(x0, texto), ...]), ...] -> palavras no formato do extract_words."""
    return [{"top": top, "x0": x0, "text": texto} for top, itens in linhas for x0, texto in itens]


def _danfse(numero="101", competencia="01/09/2026", emissao="02/09/2026 10:00:00",
            doc_tomador="11.111.111/0001-91", ibge="3516200 / 14400-000", valor="1.234,56"):
    texto = (
        "NÚMERO DA NFS-E COMPETÊNCIA DA NFS-E DATA E HORA DA EMISSÃO DA NFS-E\n"
        f"{numero} {competencia} {emissao}\n"
        "VALOR TOTAL DA NFS-E VALOR DA OPERAÇÃO / SERVIÇO\n"
        f"R$ {valor}\n"
    )
    palavras = _palavras([
        (100, [(10, "CNPJ"), (40, "/"), (50, "CPF"), (80, "/"), (90, "NIF")]),
        (110, [(10, "00.000.000/0001-91")]),
        (120, [(10, "Nome"), (40, "/"), (50, "Nome"), (90, "Empresarial")]),
        (130, [(10, "PRESTADOR"), (60, "FICTICIO"), (450, "3516200 / 14400-000")]),
        (200, [(10, "CNPJ"), (40, "/"), (50, "CPF"), (80, "/"), (90, "NIF")]),
        (210, [(10, doc_tomador)]),
        (220, [(10, "Nome"), (40, "/"), (50, "Nome"), (90, "Empresarial")]),
        (230, [(10, "CLIENTE"), (60, "FICTICIO"), (450, ibge)]),
    ])
    return texto, palavras


def test_danfse_montada_le_todos_os_campos():
    nota = interpretar_danfse("x.pdf", *_danfse())
    assert nota.lida
    assert (nota.numero_nfse, nota.competencia, nota.data_emissao) == ("101", "09/2026", date(2026, 9, 2))
    assert (nota.prestador, nota.tomador) == ("PRESTADOR FICTICIO", "CLIENTE FICTICIO")
    assert (nota.tipo_pessoa, nota.cnpj_digitos, nota.codigo_ibge_tomador) == (PJ, "11111111000191", "3516200")
    assert nota.valor == D("1234.56")


def test_competencia_diferente_da_emissao_e_lida_como_esta():
    nota = interpretar_danfse("x.pdf", *_danfse(competencia="01/08/2026", emissao="02/09/2026 10:00:00"))
    assert nota.mes_competencia == (2026, 8) and nota.mes_emissao == (2026, 9)


def test_cpf_e_cnpj_com_digitos_errados():
    pf = interpretar_danfse("x.pdf", *_danfse(doc_tomador="111.111.111-1"))
    assert pf.tipo_pessoa == PF and pf.status.startswith("ERRO: CNPJ/CPF do tomador com 10 dígito(s)")
    pj = interpretar_danfse("x.pdf", *_danfse(doc_tomador="11.111.111/0001-9"))
    assert not pj.lida and "esperado 14 para PJ" in pj.status


def test_ibge_ausente_fica_vazio_sem_erro():
    nota = interpretar_danfse("x.pdf", *_danfse(ibge="SEM CODIGO"))
    assert nota.lida and nota.codigo_ibge_tomador is None


def test_sem_numero_ou_sem_valor():
    texto, palavras = _danfse()
    assert interpretar_danfse("x.pdf", "qualquer texto", palavras).status == "ERRO: número/data não encontrados"
    sem_valor = texto.split("VALOR TOTAL")[0]
    assert interpretar_danfse("x.pdf", sem_valor, palavras).status == "ERRO: valor total não encontrado"


def test_pdf_invalido_nao_derruba(tmp_path):
    falso = tmp_path / "falso.pdf"
    falso.write_bytes(b"isto nao e um pdf")
    nota = ler_danfse(falso)
    assert not nota.lida and nota.status.startswith("ERRO: não foi possível abrir o PDF")


@pytest.mark.parametrize("texto, esperado", [
    ("1.850,61", D("1850.61")), ("30.000,00", D("30000.00")), ("27,5", D("27.50")), ("", None), ("abc", None),
])
def test_valor_para_decimal(texto, esperado):
    assert valor_para_decimal(texto) == esperado


# ---------------------------------------------------------------------------
# SPED do mês anterior (molde)
# ---------------------------------------------------------------------------

def test_molde_ficticio(sped_ficticio):
    molde = ler_molde(sped_ficticio)
    assert (molde.competencia, molde.competencia_seguinte) == ("07/2026", "08/2026")
    assert len(molde.linhas_0150) == 2 and len(molde.linhas_a100) == 2 and len(molde.linhas_a170) == 2
    assert molde.ordem_9900[:3] == ["0000", "0001", "0100"] and molde.ordem_9900[-1] == "9900"
    assert molde.fixos["0200"] == "|0200|1|SERVICOS||||||||||"
    assert molde.linhas_originais[-1] == "|9999|76|"        # a assinatura depois do 9999 é ignorada


def test_previa_e_competencia_seguinte_em_dezembro(tmp_path):
    linhas = [LINHAS_SPED_FICTICIO[0].replace("01072026|31072026", "01122026|31122026")] + LINHAS_SPED_FICTICIO[1:]
    previa = previa_sped(gravar_sped(tmp_path, linhas + ["|9999|1|"]))
    assert previa.descricao == "SPED de 12/2026 · 2 clientes · 2 notas"
    assert previa.competencia_seguinte == "01/2027"


@pytest.mark.parametrize("linhas, mensagem", [
    (["qualquer coisa"], "não parece ser um arquivo SPED"),
    (LINHAS_SPED_FICTICIO, "sem o registro 9999"),
    ([l for l in LINHAS_SPED_FICTICIO if not l.startswith("|0200|")] + ["|9999|1|"], "faltam no SPED os registros 0200"),
])
def test_sped_invalido(tmp_path, linhas, mensagem):
    with pytest.raises(ErroSped, match=mensagem):
        ler_molde(gravar_sped(tmp_path, linhas))
    assert mensagem in previa_sped(gravar_sped(tmp_path, linhas)).erro


def test_sped_real_de_agosto():
    molde = ler_molde(exemplo_efd("sped_original_2026-08.txt"))
    assert (molde.competencia, molde.competencia_seguinte) == ("08/2026", "09/2026")
    assert (len(molde.linhas_0150), len(molde.linhas_a100), len(molde.linhas_a170), len(molde.ordem_9900)) == (44, 49, 49, 37)
    assert molde.linhas_originais[-1] == "|9999|212|"


def test_cnpj_do_prestador_e_guardado():
    nota = interpretar_danfse("x.pdf", *_danfse())
    assert nota.doc_prestador == "00.000.000/0001-91" and nota.cnpj_prestador_digitos == "00000000000191"


def test_danfse_reais_sao_todas_do_mesmo_prestador():
    cnpjs = {ler_danfse(exemplo_efd("danfse", f"danfse_{n}.pdf")).cnpj_prestador_digitos for n in ESPERADO_DANFSE}
    assert len(cnpjs) == 1 and len(cnpjs.pop()) == 14
