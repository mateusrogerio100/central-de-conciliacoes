"""Conferência de NF: o lote do Tasy (.csv em UTF-16, como o Tasy grava) e a pasta das notas com os XMLs das
NF-e (o programa lê o XML direto; os PDFs de DANFE e DANFSe entram do mesmo jeito).

Mostra: notas conferidas (verde), uma com valor diferente do lançamento, uma sem nota na pasta e uma nota
da pasta sem lançamento no lote. Unidade conferida: a Fundação (CNPJ público, o único que o módulo aceita
como destinatário dessas notas).
"""

from __future__ import annotations

import csv
from pathlib import Path

from manual.ficticios import Exemplo

CNPJ_FUNDACAO = "98765432000198"
TITULOS = ["Status", "Fato contábil", "Sequência", "Data movimento", "Débito", "Crédito", "Valor",
           "Histórico", "Complemento", "Conta débito", "Conta crédito", "Histórico",
           "Classificação débito", "Classificação crédito"]
# fato, número da nota, fornecedor, CNPJ, valor lançado, valor do XML (None = sem nota na pasta)
NOTAS = [
    ("7101", "1001", "Alfa Exemplo Distribuidora Ltda", "00111222000133", 3369.10, 3369.10),
    ("7102", "2002", "Beta Exemplo Materiais Hospitalares Ltda", "00222333000144", 1250.00, 1205.00),
    ("7103", "3003", "Gama Exemplo Farmacêutica Ltda", "00333444000155", 980.00, None),
    ("7104", "4004", "Delta Exemplo Comércio Ltda", "00444555000166", 540.00, 540.00),
]
SEM_LANCAMENTO = ("5005", "Epsilon Exemplo Suprimentos Ltda", "00555666000177", 215.00)


def _linha(fato, sequencia, debito, credito, valor, complemento, conta, classificacao):
    valor_texto = f"{valor:.2f}".replace(".", ",")
    return ["Não revisado", fato, sequencia, "01/10/2026", debito, credito, valor_texto, "577", complemento,
            conta if debito else "", conta if credito else "", "Ref. nota fiscal",
            classificacao if debito else "", classificacao if credito else ""]


def _lote(caminho: Path) -> Path:
    linhas = []
    for fato, numero, fornecedor, _cnpj, valor, _ in NOTAS:
        complemento = f"{fornecedor} NF. {numero} DT21/09/2026"
        linhas.append(_linha(fato, "1", "30080", "", valor, complemento, "Material médico hospitalar",
                             "1.01.04.01.0002"))
        linhas.append(_linha(fato, "2", "", "201777", valor, complemento, fornecedor, "2.01.01.01.0001"))
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-16-le", newline="") as arquivo:   # como o Tasy: UTF-16 sem BOM
        escritor = csv.writer(arquivo, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\r\n")
        escritor.writerow(TITULOS)
        escritor.writerows(linhas)
    return caminho


def _digito_chave(chave43: str) -> str:
    """Dígito verificador da chave de acesso (módulo 11, pesos 2 a 9 da direita para a esquerda)."""
    soma = sum(int(d) * (2 + i % 8) for i, d in enumerate(reversed(chave43)))
    resto = soma % 11
    return "0" if resto < 2 else str(11 - resto)


def _xml_nfe(pasta: Path, numero: str, fornecedor: str, cnpj: str, valor: float) -> Path:
    chave43 = "35" + "2609" + cnpj + "55" + "001" + numero.zfill(9) + "1" + numero.zfill(8)
    chave = chave43 + _digito_chave(chave43)
    xml = (f'<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe Id="NFe{chave}">'
           f"<ide><nNF>{numero}</nNF><dhEmi>2026-09-21T10:00:00-03:00</dhEmi></ide>"
           f"<emit><CNPJ>{cnpj}</CNPJ><xNome>{fornecedor.upper()}</xNome></emit>"
           f"<dest><CNPJ>{CNPJ_FUNDACAO}</CNPJ><xNome>FUNDACAO EXEMPLO</xNome></dest>"
           f"<total><ICMSTot><vProd>{valor:.2f}</vProd><vNF>{valor:.2f}</vNF></ICMSTot></total>"
           f"</infNFe></NFe><protNFe><infProt><cStat>100</cStat><xMotivo>Autorizado o uso da NF-e</xMotivo>"
           f"</infProt></protNFe></nfeProc>")
    caminho = pasta / f"NFe {numero} {fornecedor}.xml"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(xml, encoding="utf-8")
    return caminho


def _preparar(tela) -> None:
    from modulos.conferencia_nf import processamento

    tela.campo_unidade.definir(processamento.opcao_do_cnpj(CNPJ_FUNDACAO))
    tela.atualizar_botoes()


def gerar(pasta: Path) -> list[Exemplo]:
    lote = _lote(pasta / "Lote 7100 - movimento.csv")
    notas = pasta / "notas do lote"
    for _fato, numero, fornecedor, cnpj, _valor, valor_xml in NOTAS:
        if valor_xml is not None:
            _xml_nfe(notas, numero, fornecedor, cnpj, valor_xml)
    _xml_nfe(notas, *SEM_LANCAMENTO)
    saida = pasta / "saida"
    saida.mkdir(parents=True, exist_ok=True)
    return [Exemplo("conferencia_nf", "conferencia_nf", "Conferir lote", "conferencia", {
        "cartao_lote": [lote], "cartao_pdfs": [notas], "cartao_saida": [saida]},
        preparar=_preparar, pasta_saida=saida,
        numeros=("2", "2", "1"))]
