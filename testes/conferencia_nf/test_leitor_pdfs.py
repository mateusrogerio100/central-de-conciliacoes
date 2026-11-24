"""T1, T2 e T3 — leitura dos PDFs (DANFE e DANFSe), PDFs repetidos e _sem_pdf.txt.

Os testes com os PDFs reais usam exemplos\\conferencia_nf\\ (fora do git) e são pulados sem ela.
Cada lote é lido uma vez só por execução (conftest.py).
"""

from __future__ import annotations

import csv
import shutil
from datetime import date
from decimal import Decimal

import pytest

from modulos.conferencia_nf import leitor_pdfs
from modulos.conferencia_nf.leitor_danfe import converter_valor_pdf, ler_danfe
from modulos.conferencia_nf.modelos import ErroLeitura
from testes.conferencia_nf.conftest import ler_pdfs_do_lote as _leitura
from testes.conftest import caso_real, pasta_exemplos

LOTES = ("lote_72648", "lote_72887")


def _gabarito(lote: str) -> list[dict]:
    caminho = pasta_exemplos("conferencia_nf", lote, "gabarito") / "gabarito_pdfs.csv"
    with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
        return list(csv.DictReader(arquivo, delimiter=";"))


def _como_gabarito(nota) -> dict:
    return {
        "arquivo": nota.arquivo, "tipo": nota.tipo, "numero": nota.numero,
        "emissao": nota.emissao.strftime("%d/%m/%Y"), "valor": str(nota.valor),
        "emitente_documento": nota.emitente_documento, "emitente_nome": nota.emitente_nome,
        "situacao": nota.situacao, "chave": nota.chave, "repetida_de": nota.repetida_de,
    }


def _comparar_tipo(lote: str, tipo: str):
    notas, falhas, _ = _leitura(lote)
    assert falhas == []
    lidas = {n.arquivo: _como_gabarito(n) for n in notas if n.tipo == tipo}
    esperadas = {g["arquivo"]: g for g in _gabarito(lote) if g["tipo"] == tipo}
    assert set(lidas) == set(esperadas)
    for arquivo, esperada in esperadas.items():
        assert lidas[arquivo] == esperada, arquivo
    return lidas


# ---------------------------------------------------------------------------
# T1 — DANFE
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lote", LOTES)
def test_t1_danfes_iguais_ao_gabarito(lote):
    assert _comparar_tipo(lote, "NF-e")


def test_t1_numero_de_4_digitos_e_notas_de_mais_de_uma_pagina():
    lidas = _comparar_tipo("lote_72648", "NF-e")
    numeros = {n["numero"] for n in lidas.values()}
    assert {"1090", "4787", "7617"} <= numeros          # o número encosta na chave (L3)
    vcp = next(n for n in lidas.values() if n["numero"] == "1090")
    assert vcp["chave"] == caso_real("conferencia_nf", "chave_nota_1090")
    assert vcp["valor"] == "7900.00"
    # a 1851957 tem 3 páginas e a 1851958 tem 2 (mesmo fornecedor): vale a 1ª página
    cnpj = caso_real("conferencia_nf", "cnpj_nota_de_varias_paginas")
    do_fornecedor = {n["numero"]: n for n in lidas.values() if n["emitente_documento"] == cnpj}
    assert {"1851957", "1851958"} <= set(do_fornecedor)


# ---------------------------------------------------------------------------
# T2 — DANFSe
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lote", LOTES)
def test_t2_danfses_iguais_ao_gabarito(lote):
    assert _comparar_tipo(lote, "NFS-e")


def test_t2_danfse_cancelada():
    lidas = _comparar_tipo("lote_72648", "NFS-e")
    canceladas = [n for n in lidas.values() if n["situacao"] != "Autorizada"]
    assert {n["numero"] for n in canceladas} == {"967"}
    assert canceladas[0]["situacao"].upper().startswith("CANCELADA")


def test_s10_regime_atividade_iss_e_federais_da_danfse():
    notas, _, _ = _leitura("lote_72648")
    servicos = {n.numero: n for n in notas if n.tipo == "NFS-e" and not n.repetida_de}
    assert all(n.federais_lidos for n in servicos.values())
    pharmacia = servicos["32110"]                   # Não Optante, nenhum federal retido
    assert pharmacia.regime == "Não Optante"
    assert pharmacia.atividade == "04.07.01 - Serviços farmacêuticos."
    assert (pharmacia.aliquota_iss, pharmacia.retencao_iss) == (Decimal("2.50"), "Não Retido")
    assert (pharmacia.irrf, pharmacia.previdencia_retida, pharmacia.contribuicoes_retidas) == (
        Decimal("0.00"), Decimal("0.00"), Decimal("0.00"))
    nota_7463 = servicos["7463"]                      # Não Optante que retém IR e PIS/COFINS/CSLL
    assert (nota_7463.irrf, nota_7463.contribuicoes_retidas) == (Decimal("42.41"), Decimal("131.47"))
    assert servicos["1839"].regime.startswith("Optante")


def test_s10_campo_do_relatorio_fora_do_formato_nao_e_erro():
    from modulos.conferencia_nf.leitor_danfse import valor_opcional
    assert valor_opcional("-") == Decimal("0.00")
    assert valor_opcional("R$ 1.234,56") == Decimal("1234.56")
    assert valor_opcional("2,90 %") == Decimal("2.90")
    assert valor_opcional("ilegível") is None
    assert valor_opcional(None) is None


# ---------------------------------------------------------------------------
# T3 — PDFs repetidos, ordem, progresso e _sem_pdf.txt
# ---------------------------------------------------------------------------

def test_t3_lote_72648_com_as_quatro_pastas():
    notas, falhas, _ = _leitura("lote_72648")
    assert (len(notas), len(falhas)) == (185, 0)
    repetidas = [n for n in notas if n.repetida_de]
    assert len(repetidas) == 7
    por_arquivo = {n.arquivo: n for n in notas}
    for nota in repetidas:
        original = por_arquivo[nota.repetida_de]
        assert original.chave == nota.chave and not original.repetida_de
        # vale o primeiro na ordem do caminho (L1/L6)
        assert notas.index(original) < notas.index(nota)


def test_t3_lote_72887():
    notas, falhas, _ = _leitura("lote_72887")
    assert (len(notas), len(falhas)) == (42, 0)
    assert not any(n.repetida_de for n in notas)
    assert leitor_pdfs.ler_sem_pdf(pasta_exemplos("conferencia_nf", "lote_72887")) == []


def test_t3_so_as_duas_pastas_novas_nao_tem_repetidos(tmp_path):
    origem = pasta_exemplos("conferencia_nf", "lote_72648")
    for subpasta in ("Notas Fiscais/danfe-lote (2)", "Notas Fiscais de Serviço/danfse-lote (11)"):
        shutil.copytree(origem / subpasta, tmp_path / subpasta)
    notas, falhas = leitor_pdfs.ler_pasta(tmp_path)
    assert (len(notas), len(falhas)) == (84, 0)
    assert not any(n.repetida_de for n in notas)


def test_t3_progresso_vai_de_0_a_1():
    _, _, fracoes = _leitura("lote_72887")
    assert fracoes[0] == 0 and fracoes[-1] == 1.0 and fracoes == sorted(fracoes)
    assert len(fracoes) == 43


def test_t3_sem_pdf_do_lote_72648():
    sem_pdf = leitor_pdfs.ler_sem_pdf(pasta_exemplos("conferencia_nf", "lote_72648"))
    assert [[s.numero, s.emitente_documento] for s in sem_pdf] == caso_real("conferencia_nf", "sem_pdf_72648")
    assert {s.arquivo for s in sem_pdf} == {"Notas Fiscais/danfe-lote/_sem_pdf.txt"}


def test_sem_pdf_ignora_linhas_que_nao_sao_chave(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "_sem_pdf.txt").write_text(
        "Chaves sem DANFE\n\n 35260911444777000161550010006883891000000000 \n123\n", encoding="utf-8")
    sem_pdf = leitor_pdfs.ler_sem_pdf(tmp_path)
    assert [(s.chave[:6], s.numero, s.arquivo) for s in sem_pdf] == [
        ("352609", "688389", "sub/_sem_pdf.txt")]


def test_ordem_dos_pdfs_e_pasta_por_pasta(tmp_path):
    for caminho in ("b/x.pdf", "a (2)/y.pdf", "a/Z.pdf", "a/y.PDF", "a/nota.txt"):
        (tmp_path / caminho).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / caminho).write_bytes(b"")
    nomes = [p.relative_to(tmp_path).as_posix() for p in leitor_pdfs.listar_pdfs(tmp_path)]
    assert nomes == ["a/y.PDF", "a/Z.pdf", "a (2)/y.pdf", "b/x.pdf"]


# ---------------------------------------------------------------------------
# PDFs com problema (L5): erro de leitura, o resto continua
# ---------------------------------------------------------------------------

def test_pdf_estragado_e_de_outro_modelo_viram_falha_e_o_resto_continua(tmp_path):
    boa = next(pasta_exemplos("conferencia_nf", "lote_72887").rglob("DANFE-935-*.pdf"))
    shutil.copy(boa, tmp_path / boa.name)
    (tmp_path / "estragado.pdf").write_bytes(b"%PDF-1.4 quebrado")
    outro = pasta_exemplos("escrituracao_tomados", "layout") / "Declaracao_ServicosTomados_V3.0.pdf"
    (tmp_path / "sub").mkdir()
    shutil.copy(outro, tmp_path / "sub" / "outro.pdf")

    notas, falhas = leitor_pdfs.ler_pasta(tmp_path)
    assert [n.numero for n in notas] == ["935"]
    motivos = {f.arquivo: f.motivo for f in falhas}
    assert set(motivos) == {"estragado.pdf", "sub/outro.pdf"}
    assert "estragado" in motivos["estragado.pdf"]
    assert "Modelo não reconhecido" in motivos["sub/outro.pdf"]


# ---------------------------------------------------------------------------
# DANFE montada no teste (texto da 1ª página)
# ---------------------------------------------------------------------------

CHAVE = "3526 0911 4447 7700 0161 5500 1000 0103 4610 9790 9980"


def _texto_danfe(numero="10.346", chave=CHAVE, cnpj="11.444.777/0001-61", total="650,75",
                 emissao="28/09/2026", destinatario="98.765.432/0001-98"):
    return "\n".join([
        "RECEBEMOS DE DISTRIBUIDORA EXEMPLO LTDA OS PRODUTOS/SERVIÇOS CONSTANTES DA NF-E INDICADA AO LADO NF-e",
        f"Nº {numero}",
        "1 - SAÍDA CHAVE DE ACESSO",
        f"Nº {numero} {chave}",
        "INSCRIÇÃO ESTADUAL INSCRIÇÃO ESTADUAL DO SUBST. TRIBUTÁRIO CNPJ / CPF",
        f"206876092 {cnpj}",
        "NOME / RAZÃO SOCIAL CNPJ / CPF DATA DA EMISSÃO",
        f"FUNDACAO HOSPITAL EXEMPLO {destinatario} {emissao}".replace("  ", " "),
        "VALOR DO FRETE VALOR DO SEGURO DESCONTO OUTRAS DESPESAS VALOR DO IPI VALOR TOTAL DA NOTA",
        f"0,00 0,00 0,00 0,00 0,00 {total}",
    ])


def test_danfe_montada():
    nota = ler_danfe(_texto_danfe(), "x.pdf")
    assert (nota.numero, nota.emissao, nota.valor, nota.emitente_nome, nota.emitente_documento) \
        == ("10346", date(2026, 9, 28), Decimal("650.75"), "DISTRIBUIDORA EXEMPLO LTDA", "11444777000161")
    assert nota.chave == CHAVE.replace(" ", "")
    assert nota.destinatario_documento == "98765432000198"


def test_s15_danfe_destinatario_de_outra_unidade_ou_nao_lido():
    assert ler_danfe(_texto_danfe(destinatario="98.765.432/0004-30"), "x.pdf"
                     ).destinatario_documento == "98765432000430"
    assert ler_danfe(_texto_danfe(destinatario=""), "x.pdf").destinatario_documento == ""


@pytest.mark.parametrize("lote", LOTES)
def test_s15_destinatario_e_tomador_lidos_em_todos_os_pdfs(lote):
    """Todas as notas de compra e de serviço dos exemplos vieram para a Fundação (0001-89),
    menos duas notas de serviço emitidas pela própria Fundação (sem lançamento no lote)."""
    notas, _, _ = _leitura(lote)
    outras = {(n.numero, n.destinatario_documento) for n in notas
              if n.destinatario_documento != "98765432000198"}
    assert all(n.destinatario_documento for n in notas)
    assert outras == ({tuple(caso_real("conferencia_nf", "tomador_pessoa_fisica_72648")),
                       ("89683", "98765432000864")}
                      if lote == "lote_72648" else set())


def test_l3_numero_de_4_digitos_grudado_na_chave():
    chave = "2926 0900 5075 0600 0191 5500 1000 0010 9012 9150 0487"
    nota = ler_danfe(_texto_danfe(numero="1090", chave=chave, cnpj="00.507.506/0001-91"), "x.pdf")
    assert nota.chave == chave.replace(" ", "") and nota.numero == "1090"


@pytest.mark.parametrize("campo", [{"numero": "10.347"}, {"cnpj": "00.205.204/0001-68"}])
def test_l4_numero_ou_cnpj_diferente_da_chave_e_erro(campo):
    with pytest.raises(ErroLeitura, match="não conferem com a chave"):
        ler_danfe(_texto_danfe(**campo), "x.pdf")


def test_danfe_sem_campo_obrigatorio_e_erro():
    texto = _texto_danfe().replace("VALOR TOTAL DA NOTA", "VALOR TOTAL")
    with pytest.raises(ErroLeitura, match="valor total da nota"):
        ler_danfe(texto, "x.pdf")


@pytest.mark.parametrize("texto, esperado", [
    ("7.900,00", "7900.00"), ("650,75", "650.75"), ("R$ 1.117.461,33", "1117461.33"),
])
def test_converter_valor_pdf(texto, esperado):
    assert converter_valor_pdf(texto) == Decimal(esperado)


@pytest.mark.parametrize("texto", ["7900", "7,9", "abc", ""])
def test_converter_valor_pdf_recusa(texto):
    with pytest.raises(ErroLeitura):
        converter_valor_pdf(texto)
