"""EFD 2 — montagem do SPED (R10–R16) e a REGRA DE OURO: refazer agosto/2026 a partir do original."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from modulos.efd_contribuicoes.leitor_sped import campos, ler_molde
from modulos.efd_contribuicoes.montagem_sped import (
    ClienteSped,
    NotaSped,
    conferir_sped,
    formatar_valor_sped,
    montar_sped,
)
from testes.efd_contribuicoes.conftest import exemplo_efd

D = Decimal


def _clientes_e_notas_do_sped(molde):
    """O cadastro (dos 0150) e as notas (dos A100) que estão num SPED pronto."""
    clientes = []
    for linha in molde.linhas_0150:
        f = campos(linha)
        clientes.append(ClienteSped(cod_part=f[1], nome=f[2], cnpj=f[4], codigo_ibge=f[7]))
    notas = []
    for linha in molde.linhas_a100:
        f = campos(linha)
        dia = date(int(f[9][4:]), int(f[9][2:4]), int(f[9][:2]))
        notas.append(NotaSped(cod_part=f[3], numero_nfse=f[7], data_emissao=dia, valor=D(f[11].replace(",", "."))))
    return clientes, notas


# ---------------------------------------------------------------------------
# Regra de ouro (CONTEXTO da origem; ESPECIFICACAO, seção 8, teste 2)
# ---------------------------------------------------------------------------

def test_regra_de_ouro_agosto_2026_linha_por_linha():
    molde = ler_molde(exemplo_efd("sped_original_2026-08.txt"))
    clientes, notas = _clientes_e_notas_do_sped(molde)
    montado = montar_sped(molde, "08/2026", clientes, notas)
    assert montado.erros == []
    # O original traz as notas na ordem em que foram digitadas no programa da Receita; a montagem (como a
    # aplicação de origem) põe em ordem do número da NFS-e. Por isso o bloco das notas é comparado sem a ordem
    # — cada par A100+A170 igual a um par do original — e todo o resto, linha por linha.
    def sem_notas(linhas):
        return ["(nota)" if l.startswith(("|A100|", "|A170|")) else l for l in linhas]

    # Decisão do usuário (05/11/2026): campos zerados saem vazios, como na origem (aceito pelo programa da Receita).
    # No original de agosto, lançado à mão, 17 das 49 notas trazem "0" no VL_DESC do A100 (campo 13) e 1 nota traz
    # "0" na ALIQ_COFINS do A170 (campo 14) — o mesmo que vazio. Só nesses dois campos "0" e vazio contam como iguais.
    campos_zero_igual_vazio = {"A100": 13, "A170": 14}

    def zero_como_vazio(linha):
        f = campos(linha)
        posicao = campos_zero_igual_vazio.get(f[0])
        if posicao is not None and f[posicao] == "0":
            f[posicao] = ""
            return "|" + "|".join(f) + "|"
        return linha

    def pares_de_notas(linhas):
        return sorted((zero_como_vazio(a), zero_como_vazio(b))
                      for a, b in zip(linhas, linhas[1:]) if a.startswith("|A100|"))

    diferentes = [(n, original, gerada) for n, (original, gerada)
                  in enumerate(zip(sem_notas(molde.linhas_originais), sem_notas(montado.linhas)), start=1)
                  if original != gerada]
    assert diferentes == []
    assert pares_de_notas(montado.linhas) == pares_de_notas(molde.linhas_originais)
    assert all(b.startswith("|A170|") for _, b in pares_de_notas(montado.linhas))
    assert len(montado.linhas) == len(molde.linhas_originais) == 212
    assert montado.total_receita == D("3418347.48")
    assert (montado.quantidade_notas, montado.quantidade_clientes) == (49, 44)
    assert conferir_sped(molde.linhas_originais) == []          # o original também passa na conferência R16


def test_mes_seguinte_muda_so_as_datas_do_0000(sped_ficticio):
    molde = ler_molde(sped_ficticio)
    clientes, notas = _clientes_e_notas_do_sped(molde)
    montado = montar_sped(molde, "02/2028", clientes, notas)                 # fevereiro bissexto
    assert montado.erros == []
    assert campos(montado.linhas[0])[5:7] == ["01022028", "29022028"]
    assert montado.linhas[1:] == molde.linhas_originais[1:]                          # resto igual ao molde


# ---------------------------------------------------------------------------
# Montagem com dados fictícios
# ---------------------------------------------------------------------------

CLIENTES = [
    ClienteSped("2", "CLIENTE FICTICIO DOIS", "22222222000191", "3509502"),
    ClienteSped("1", "CLIENTE FICTICIO UM", "11111111000191", "3516200"),
    ClienteSped("3", "CLIENTE FICTICIO TRES", "33333333000191", "3543600"),
]


def test_monta_notas_clientes_e_contadores(sped_ficticio):
    notas = [
        NotaSped("3", "205", date(2026, 9, 10), D("0.10")),
        NotaSped("1", "201", date(2026, 9, 1), D("1850.61")),
        NotaSped("1", "203", date(2026, 9, 5), D("0.20")),
        NotaSped("2", "202", date(2026, 9, 2), D("30000.00")),
    ]
    montado = montar_sped(ler_molde(sped_ficticio), "09/2026", CLIENTES, notas)
    assert montado.erros == []
    tipos = [campos(l)[0] for l in montado.linhas]
    assert [campos(l)[1] for l in montado.linhas if l.startswith("|0150|")] == ["1", "2", "3"]   # ordem do código
    a100 = [campos(l) for l in montado.linhas if l.startswith("|A100|")]
    assert [f[7] for f in a100] == ["201", "202", "203", "205"]                                   # ordem do número
    assert a100[0][3:12] == ["1", "00", "", "", "201", "", "01092026", "01092026", "1850,61"]
    assert tipos.index("A170") == tipos.index("A100") + 1                                         # par A100/A170
    assert "|M400|07|31850,91|||" in montado.linhas and "|M810|202|31850,91|||" in montado.linhas
    assert montado.total_receita == D("31850.91")        # 0,10 + 0,20 somados exatos (em float, 0.30000000000000004)
    assert "|0990|10|" in montado.linhas and "|A990|11|" in montado.linhas


@pytest.mark.parametrize("valor, texto", [
    (D("1850.61"), "1850,61"), (D("30000.00"), "30000"), (D("50.50"), "50,5"), (D("0.05"), "0,05"), (D("7"), "7"),
])
def test_formato_do_valor_igual_ao_original(valor, texto):
    assert formatar_valor_sped(valor) == texto


# ---------------------------------------------------------------------------
# R16: conferência final pega arquivo inconsistente
# ---------------------------------------------------------------------------

@pytest.fixture
def montado(sped_ficticio):
    return montar_sped(ler_molde(sped_ficticio), "09/2026", CLIENTES,
                       [NotaSped("1", "201", date(2026, 9, 1), D("100.00"))])


def _trocar(linhas, inicio, nova):
    return [nova if l.startswith(inicio) else l for l in linhas]


@pytest.mark.parametrize("inicio, nova, trecho", [
    ("|0990|", "|0990|99|", "0990 (linhas do bloco 0): o arquivo diz 99"),
    ("|A990|", "|A990|4|", "A990 (linhas do bloco A): o arquivo diz 4, mas há 5"),
    ("|9999|", "|9999|1|", "9999 (linhas do arquivo)"),
    ("|M400|", "|M400|07|99,99|||", "M400: o arquivo diz 99,99, mas a soma das notas (A100) é 100"),
    ("|9900|A100|", "|9900|A100|2|", "9900 do registro A100: o arquivo diz 2, mas há 1"),
])
def test_conferencia_pega_contador_errado(montado, inicio, nova, trecho):
    assert montado.erros == []
    erros = conferir_sped(_trocar(montado.linhas, inicio, nova))
    assert any(trecho in e for e in erros), erros


def test_conferencia_pega_a170_faltando(montado):
    erros = conferir_sped([l for l in montado.linhas if not l.startswith("|A170|")])
    assert any("um A170 para cada A100" in e for e in erros)
