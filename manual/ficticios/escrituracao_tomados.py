"""Serviços Tomados: exportação de um lote do site da prefeitura (.csv) e o resultado do site com as
notas já escrituradas, gerando o .txt de importação (Layout V3).

Mostra: notas que entram no arquivo, uma já escriturada (fica fora), uma emitida em outro mês (lançar
à mão, V17) e uma cancelada (não incluída).

Sem internet: a cidade de cada prestador fictício é registrada antes no cadastro de prestadores (como
quando a cidade já foi aprendida). O registro vai para o %APPDATA% da vez — o script de prints e o teste
usam uma pasta temporária, nunca o cadastro de verdade.
"""

from __future__ import annotations

from pathlib import Path

from manual.ficticios import Exemplo
from manual.ficticios.tasy import numero_br

# CNPJ da Fundação (público): o módulo só aceita notas tomadas pela Fundação (raiz 98.765.432)
CNPJ_TOMADOR = "98.765.432/0001-98"
PRESTADORES = {                                  # CNPJ: (nome, cidade, UF)
    "00.111.000/0001-11": ("ALFA EXEMPLO SERVICOS MEDICOS LTDA", "Cidade Alfa", "SP"),
    "00.222.000/0001-22": ("BETA EXEMPLO LIMPEZA LTDA", "Cidade Alfa", "SP"),
    "00.333.000/0001-33": ("GAMA EXEMPLO MANUTENCAO LTDA", "Cidade Alfa", "SP"),
    "00.444.000/0001-44": ("DELTA EXEMPLO CONSULTORIA LTDA", "Cidade Alfa", "SP"),
}
NOTAS = [                                        # número, situação, CNPJ, emissão, valor, retido
    ("3101", "Normal", "00.111.000/0001-11", "05/09/2026", 15400.00, "NÃO"),
    ("3102", "Normal", "00.111.000/0001-11", "18/09/2026", 9800.00, "NÃO"),
    ("870", "Normal", "00.222.000/0001-22", "10/09/2026", 6250.00, "SIM"),
    ("451", "Normal", "00.333.000/0001-33", "22/09/2026", 2180.00, "NÃO"),      # já escriturada
    ("452", "Normal", "00.333.000/0001-33", "28/08/2026", 1340.00, "NÃO"),      # emitida em agosto
    ("96", "Cancelada", "00.444.000/0001-44", "12/09/2026", 3000.00, "NÃO"),
]
JA_ESCRITURADAS = ["451"]
CABECALHO = ("nfs;situacaonf;cnpjcpf;nome;dtemissao;vlrservicos;descratividade;cfps;vlrdeducoes;"
             "descontoincondicionado;basecalculo;aliquota;impretido;vlrimposto;enquadradosn")


def _linha(numero, situacao, cnpj, emissao, valor, retido) -> str:
    nome = PRESTADORES[cnpj][0]
    return (f"{numero};{situacao};{cnpj};{nome};{emissao};{numero_br(valor)};04.01.01  Medicina.;1;0,00;0,00;"
            f"{numero_br(valor)};2,00;{retido};{numero_br(round(valor * 0.02, 2))};N")


def _csv(caminho: Path, notas) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(("\r\n".join([CABECALHO] + [_linha(*n) for n in notas]) + "\r\n").encode("cp1252"))
    return caminho


def _preparar(tela) -> None:
    from modulos.escrituracao_tomados.cadastro_prestadores import CadastroPrestadores

    cadastro = CadastroPrestadores()
    for cnpj, (_nome, cidade, uf) in PRESTADORES.items():
        cadastro.registrar(cnpj, cidade, uf, "exemplo do manual")
    cadastro.salvar()
    tela.campo_tomador.definir(CNPJ_TOMADOR)
    tela.campo_competencia.definir("09/2026")
    tela.seletor_tipo.selecionar("Normal", avisar=True)
    tela.campo_data.definir("05/10/2026")


def gerar(pasta: Path) -> list[Exemplo]:
    lote = _csv(pasta / "exportacao_lote_09-2026.csv", NOTAS)
    resultado = _csv(pasta / "resultado_site_ja_escrituradas.csv", [n for n in NOTAS if n[0] in JA_ESCRITURADAS])
    saida = pasta / "saida"
    saida.mkdir(parents=True, exist_ok=True)
    return [Exemplo("escrituracao_tomados", "escrituracao_tomados", "Gerar arquivo", "gerar", {
        "cartao_exportacoes": [lote], "cartao_resultados": [resultado], "cartao_saida": [saida]},
        preparar=_preparar, pasta_saida=saida,
        numeros=("3", "1", "2"))]
