"""Conferência ISS, aba Cidade Alfa: o CSV de notas de serviço do Tasy e o relatório de serviços tomados da
Prefeitura de Cidade Alfa (CSV). As outras cidades funcionam do mesmo jeito, com o relatório de cada prefeitura.

Mostra: notas conferidas, uma com valor diferente, uma só no Tasy, uma só na prefeitura, uma cancelada na
prefeitura e uma escriturada duas vezes.
"""

from __future__ import annotations

from pathlib import Path

from manual.ficticios import Exemplo
from manual.ficticios.tasy import numero_br

ESTABELECIMENTO = "AME Cidade Exemplo"
NOME_FANTASIA = "Ambulatório Exemplo de Especialidades"
CNPJ_UNIDADE = "00.900.800/0001-70"

PRESTADORES = {
    "alfa": ("Alfa Exemplo Serviços Médicos Ltda", "00.101.202/0001-10"),
    "beta": ("Beta Exemplo Laboratório Ltda", "00.202.303/0001-20"),
    "gama": ("Gama Exemplo Limpeza e Conservação Ltda", "00.303.404/0001-30"),
    "delta": ("Delta Exemplo Manutenção Ltda", "00.404.505/0001-40"),
    "epsilon": ("Epsilon Exemplo Informática Ltda", "00.505.606/0001-50"),
}
NOTAS_TASY = [                                   # número, prestador, valor
    ("1201", "alfa", 12800.00),
    ("1202", "alfa", 9350.00),
    ("845", "beta", 4120.50),
    ("3310", "gama", 18760.00),
    ("77", "delta", 1500.00),                    # a prefeitura tem 1.450,00
    ("78", "delta", 980.00),                     # não está na prefeitura
    ("2026000000415", "epsilon", 2300.00),       # número "ano + zeros + número" do Tasy
]
NOTAS_PREFEITURA = [                             # número, prestador, valor, situação
    ("1201", "alfa", 12800.00, "Normal"),
    ("1202", "alfa", 9350.00, "Normal"),
    ("845", "beta", 4120.50, "Normal"),
    ("3310", "gama", 18760.00, "Normal"),
    ("3310", "gama", 18760.00, "Normal"),        # escriturada duas vezes
    ("77", "delta", 1450.00, "Normal"),
    ("415", "epsilon", 2300.00, "Normal"),
    ("91", "epsilon", 640.00, "Normal"),         # não está no Tasy
    ("92", "epsilon", 210.00, "Cancelada"),
]

COLUNAS_TASY = ["Nota Fiscal", "Série", "Emitente", "Código emitente", "Tipo de nota", "Data de emissão",
                "Data de entrada/saída", "Valor da mercadoria", "Valor da nota", "Estabelecimento",
                "Nome fantasia (Destinatário)", "Situação", "Código destinatário", "Observação"]
CABECALHO_CIDADE_ALFA = ("nfs;situacaonf;cnpjcpf;nome;dtemissao;vlrservicos;descratividade;cfps;vlrdeducoes;"
                    "descontoincondicionado;basecalculo;aliquota;impretido;vlrimposto;enquadradosn;")


def _valor_tasy(valor) -> str:
    """No CSV o Tasy escreve sem o ponto de milhar: 12800,00."""
    return f"{valor:.2f}".replace(".", ",")


def _csv_tasy(caminho: Path) -> Path:
    def aspas(campos):
        return ";".join('"' + str(c).replace('"', '""') + '"' for c in campos)

    linhas = [aspas(COLUNAS_TASY)]
    for numero, chave, valor in NOTAS_TASY:
        nome, cnpj = PRESTADORES[chave]
        linhas.append(aspas([numero, "1", nome, cnpj, "Nota Fiscal de Serviço", "10/09/2026", "15/09/2026",
                             _valor_tasy(valor), _valor_tasy(valor), ESTABELECIMENTO, NOME_FANTASIA, "Ativa",
                             CNPJ_UNIDADE, ""]))
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(("\r\n".join(linhas) + "\r\n").encode("utf-16-le"))      # como o Tasy: UTF-16 sem BOM
    return caminho


def _csv_cidade_alfa(caminho: Path) -> Path:
    linhas = [CABECALHO_CIDADE_ALFA]
    for numero, chave, valor, situacao in NOTAS_PREFEITURA:
        nome, cnpj = PRESTADORES[chave]
        imposto = numero_br(round(valor * 0.02, 2))
        linhas.append(f"{numero};{situacao};{cnpj};{nome.upper()};10/09/2026;{numero_br(valor)};04.01.01  Medicina.;1;"
                      f"0,00;0,00;{numero_br(valor)};2,00;NÃO;{imposto};N;")
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(("\r\n".join(linhas) + "\r\n").encode("cp1252"))
    return caminho


def gerar(pasta: Path) -> list[Exemplo]:
    tasy = _csv_tasy(pasta / "Servicos_PJ_set2026.csv")
    prefeitura = _csv_cidade_alfa(pasta / "resultado_Prefeitura_Cidade_Alfa_set2026.csv")
    return [Exemplo("conferencia_iss", "conferencia_iss", "Cidade Alfa", "cidade_alfa",
                    {"cartao_tasy": [tasy], "cartao_prefeitura": [prefeitura]},
        numeros=("4", "1", "3"))]
