"""EFD Contribuições: uma pasta com 4 DANFSe de setembro, o SPED fictício de agosto e o cadastro de clientes.

Mostra: 3 notas de pessoa jurídica no SPED (uma de um cliente novo, que ganha o próximo código), 1 nota de pessoa
física fora do SPED, e a receita do mês.

As DANFSe aqui são arquivos vazios: a leitura do PDF é trocada pelas notas abaixo (substituições), e o cadastro
de clientes é um clientes.json do exemplo — o print nunca toca a rede nem precisa de um PDF de verdade.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from manual.ficticios import Exemplo

EMPRESA = "|0000|006|0|||01082026|31082026|FUNDACAO EXEMPLO|00000000000191|SP|3516200||00|9|"
FIXOS = [
    "|0001|0|", "|0100|CONTADOR EXEMPLO|00000000000|1SP000000|||||||||||", "|0110|1|1||1|",
    "|0140||FUNDACAO EXEMPLO|00000000000191|SP||3516200|||",
]
CLIENTES = [
    {"cod_part": "1", "nome": "PREFEITURA MUNICIPAL DE CIDADE EXEMPLO", "cnpj": "11111111000191", "codigo_ibge": "3516200"},
    {"cod_part": "2", "nome": "CLINICA EXEMPLO LTDA", "cnpj": "22222222000191", "codigo_ibge": "3509502"},
]
NOTAS = [  # (arquivo, número, tomador, documento, PJ/PF, IBGE, valor)
    ("DANFSe-1001.pdf", "1001", "PREFEITURA MUNICIPAL DE CIDADE EXEMPLO", "11.111.111/0001-91", "PJ", "3516200", "12500.00"),
    ("DANFSe-1002.pdf", "1002", "CLINICA EXEMPLO LTDA", "22.222.222/0001-91", "PJ", "3509502", "3420.75"),
    ("DANFSe-1003.pdf", "1003", "HOSPITAL TESTE SA", "33.333.333/0001-91", "PJ", "3543600", "8100.00"),
    ("DANFSe-1004.pdf", "1004", "PACIENTE EXEMPLO", "111.111.111-11", "PF", "3516200", "30.00"),
]


def _sped(caminho: Path) -> Path:
    linhas = [EMPRESA] + FIXOS
    linhas += [f"|0150|{c['cod_part']}|{c['nome']}|1058|{c['cnpj']}|||{c['codigo_ibge']}||||||" for c in CLIENTES]
    linhas += ["|0200|1|SERVICOS||||||||||", f"|0990|{len(linhas) + 2}|", "|A001|0|", "|A010|00000000000191|",
               "|A100|1|0|1|00|||900||10082026|10082026|12000|0||12000|0|12000|0||||",
               "|A170|1|1||12000||||07|12000|||07|12000|||||", "|A990|5|"]
    for bloco in "CDFI":
        linhas += [f"|{bloco}001|1|", f"|{bloco}990|2|"]
    linhas += ["|M001|0|", "|M200|0|0|0|0|0|0|0|0|0|0|0|0|", "|M400|07|12000|||", "|M410|202|12000|||",
               "|M600|0|0|0|0|0|0|0|0|0|0|0|0|", "|M800|07|12000|||", "|M810|202|12000|||", "|M990|8|",
               "|P001|1|", "|P990|2|", "|1001|1|", "|1990|2|", "|9001|0|"]
    tipos = [l.split("|")[1] for l in linhas] + ["9990", "9999"]
    ordem = list(dict.fromkeys(tipos))
    linhas += [f"|9900|{t}|{tipos.count(t)}|" for t in ordem] + [f"|9900|9900|{len(ordem) + 1}|"]
    linhas += [f"|9990|{sum(1 for l in linhas if l.startswith('|9')) + 2}|", f"|9999|{len(linhas) + 2}|"]
    caminho.write_bytes(("\r\n".join(linhas) + "\r\n").encode("iso-8859-1"))
    return caminho


def gerar(pasta: Path) -> list[Exemplo]:
    from modulos.efd_contribuicoes.leitor_danfse import NotaDanfse

    pasta.mkdir(parents=True, exist_ok=True)
    pdfs = pasta / "DANFSe setembro"
    pdfs.mkdir(exist_ok=True)
    notas = {}
    for arquivo, numero, tomador, documento, tipo, ibge, valor in NOTAS:
        (pdfs / arquivo).write_bytes(b"")
        notas[arquivo] = NotaDanfse(arquivo=arquivo, numero_nfse=numero, competencia="09/2026",
                                    data_emissao=date(2026, 9, 15), data_emissao_texto="15/09/2026 10:00:00",
                                    prestador="FUNDACAO EXEMPLO", tomador=tomador, doc_tomador=documento,
                                    tipo_pessoa=tipo, codigo_ibge_tomador=ibge, valor=Decimal(valor),
                                    valor_texto=valor.replace(".", ","))
    sped = _sped(pasta / "SpedEPC_agosto_2026.txt")
    cadastro = pasta / "cadastro_rede"
    cadastro.mkdir(exist_ok=True)
    (cadastro / "clientes.json").write_text(json.dumps({"clientes": CLIENTES}, ensure_ascii=False, indent=2),
                                            encoding="utf-8")
    saida = pasta / "saida"
    saida.mkdir(exist_ok=True)
    return [Exemplo("efd_contribuicoes", "efd_contribuicoes", "Geração do SPED", "geracao",
                    {"cartao_pdfs": [pdfs], "cartao_sped": [sped], "cartao_cadastro": [cadastro / "clientes.json"],
                     "cartao_saida": [saida]},
                    pasta_saida=saida, numeros=("3", "1", "1"),
                    substituicoes={
                        "modulos.efd_contribuicoes.processamento.ler_danfse": lambda caminho: notas[Path(caminho).name],
                    })]
