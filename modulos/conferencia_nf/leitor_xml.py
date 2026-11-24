"""XML da nota (NF-e ou NFS-e do padrão nacional) -> NotaPdf. Seção 3.5 e regras X1 a X3.

X1a: o XML da Nota Paulistana (NFS-e de São Paulo) é lido por leitor_paulistana.py.

O XML é a própria nota fiscal autorizada: cada dado vem numa etiqueta com nome fixo, sem depender
do desenho da página como no PDF. As etiquetas são procuradas pelo nome, sem o "namespace" (o
endereço do padrão que vem antes do nome).

- NF-e (nota de compra): raiz `nfeProc` (a nota com o protocolo de autorização da Sefaz). O número
  e o CNPJ do emitente são conferidos contra a chave de acesso, como na DANFE (L4).
- NFS-e (nota de serviço): raiz `NFSe`, o mesmo padrão nacional da DANFSe v2.0. Lê também o que a
  DANFSe dá ao relatório (regime, atividade, ISS e retenções federais). Etiqueta que não vem no XML
  = valor zero (na DANFSe o campo aparece com "-").

O XML não diz se a nota foi cancelada depois (o cancelamento é outro arquivo): a situação da
NFS-e fica em branco e, se o PDF da mesma nota estiver na pasta, vem dele (leitor_pdfs.py, X2).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from modulos.conferencia_nf import configuracao as cfg
from modulos.conferencia_nf.leitor_danfe import cnpj_da_chave, numero_da_chave, so_digitos
from modulos.conferencia_nf.leitor_paulistana import e_paulistana_xml, ler_paulistana_xml
from modulos.conferencia_nf.modelos import ErroLeitura, NotaPdf


def _nome(elemento: ET.Element) -> str:
    """'{http://www.portalfiscal.inf.br/nfe}nNF' -> 'nNF'."""
    return elemento.tag.rsplit("}", 1)[-1]


def _achar(pai: ET.Element | None, *caminho: str) -> ET.Element | None:
    """Primeira etiqueta com cada nome, uma dentro da outra (em qualquer nível)."""
    atual = pai
    for nome in caminho:
        if atual is None:
            return None
        atual = next((e for e in atual.iter() if e is not atual and _nome(e) == nome), None)
    return atual


def _texto(pai: ET.Element | None, *caminho: str) -> str:
    elemento = _achar(pai, *caminho)
    return " ".join((elemento.text or "").split()) if elemento is not None else ""


def _obrigatorio(pai: ET.Element | None, nome_campo: str, *caminho: str) -> str:
    texto = _texto(pai, *caminho)
    if not texto:
        raise ErroLeitura(f"Campo \"{nome_campo}\" ({'/'.join(caminho)}) não encontrado no XML.")
    return texto


def _valor(texto: str, nome_campo: str) -> Decimal:
    """'1431.00', '0', '' -> Decimal com 2 casas. Vazio = 0,00 (etiqueta que não veio)."""
    if not texto:
        return Decimal("0.00")
    try:
        return Decimal(texto).quantize(Decimal("0.01"))
    except InvalidOperation:
        raise ErroLeitura(f"Valor \"{texto}\" do campo \"{nome_campo}\" não reconhecido no "
                          "XML.") from None


def _data(texto: str, nome_campo: str) -> date:
    """'2026-09-21T16:10:00-03:00' ou '2026-09-21' -> date."""
    try:
        return date.fromisoformat(texto[:10])
    except ValueError:
        raise ErroLeitura(f"Data \"{texto}\" do campo \"{nome_campo}\" não reconhecida no "
                          "XML.") from None


def _documento(pai: ET.Element | None) -> str:
    """CNPJ ou CPF (só dígitos) dentro do bloco; vazio se não houver."""
    return so_digitos(_texto(pai, "CNPJ") or _texto(pai, "CPF"))


def _chave(info: ET.Element, prefixo: str) -> str:
    identificacao = info.get("Id") or ""
    if not identificacao.startswith(prefixo) or not so_digitos(identificacao):
        raise ErroLeitura("Chave de acesso (atributo Id) não encontrada no XML.")
    return so_digitos(identificacao)


# ---------------------------------------------------------------------------
# NF-e (nota de compra)
# ---------------------------------------------------------------------------


def _ler_nfe(raiz: ET.Element, arquivo: str) -> NotaPdf:
    info = _achar(raiz, cfg.XML_NFE_INFO)
    if info is None:
        raise ErroLeitura("XML de NF-e sem o bloco infNFe.")
    protocolo = _achar(raiz, cfg.XML_NFE_PROTOCOLO)
    if protocolo is None:
        raise ErroLeitura("XML de NF-e sem o protocolo de autorização da Sefaz (protNFe): não é "
                          "a nota autorizada.")
    codigo = _texto(protocolo, "cStat")
    situacao = "" if codigo in cfg.XML_NFE_AUTORIZADA else \
        f"Não autorizada (código {codigo}: {_texto(protocolo, 'xMotivo')})"

    emitente = _achar(info, "emit")
    nota = NotaPdf(
        tipo=cfg.TIPO_NFE,
        numero=str(int(_obrigatorio(info, "número da nota", "ide", "nNF"))),
        emissao=_data(_obrigatorio(info, "data de emissão", "ide", "dhEmi"), "data de emissão"),
        valor=_valor(_obrigatorio(info, "valor total da nota", "total", "vNF"),
                     "valor total da nota"),
        emitente_nome=_texto(emitente, "xNome"),
        emitente_documento=_documento(emitente),
        situacao=situacao,
        chave=_chave(info, "NFe"),
        arquivo=arquivo,
        destinatario_documento=_documento(_achar(info, "dest")),
        xml=True,
    )
    # como na DANFE (L4): a chave traz o número e o CNPJ do emitente (CPF com zeros na frente)
    if len(nota.chave) != cfg.TAMANHO_CHAVE \
            or cnpj_da_chave(nota.chave) != nota.emitente_documento.zfill(14) \
            or numero_da_chave(nota.chave) != nota.numero:
        raise ErroLeitura("Número ou CNPJ do XML não conferem com a chave de acesso "
                          f"(nº {nota.numero}, CNPJ {nota.emitente_documento}; chave {nota.chave}).")
    return nota


# ---------------------------------------------------------------------------
# NFS-e (nota de serviço, padrão nacional)
# ---------------------------------------------------------------------------


def _atividade(info: ET.Element) -> str:
    """'040101' + 'Medicina.' -> '04.01.01 - Medicina.' (como na DANFSe)."""
    codigo = _texto(info, "cTribNac")
    if len(codigo) == 6 and codigo.isdigit():
        codigo = f"{codigo[:2]}.{codigo[2:4]}.{codigo[4:]}"
    descricao = _texto(info, "xTribNac")
    return f"{codigo} - {descricao}" if codigo and descricao else codigo


def _ler_nfse(raiz: ET.Element, arquivo: str) -> NotaPdf:
    info = raiz if _nome(raiz) == cfg.XML_NFSE_INFO else _achar(raiz, cfg.XML_NFSE_INFO)
    if info is None:
        raise ErroLeitura("XML de NFS-e sem o bloco infNFSe.")
    dps = _achar(info, cfg.XML_NFSE_DPS)
    emitente = _achar(info, "emit")
    tributos = _achar(dps, "trib")
    federais = _achar(tributos, "tribFed")
    valores_nota = next((e for e in info if _nome(e) == "valores"), None)   # os da NFS-e, não da DPS
    emissao = _texto(info, "dhProc") or _texto(dps, "dhEmi")
    if not emissao:
        raise ErroLeitura("Campo \"data de emissão\" (dhProc) não encontrado no XML.")
    # S16a: tipo de retenção do PIS/COFINS/CSLL; na DANFSe aparece como "Código 3"
    codigo = _texto(federais, "tpRetPisCofins")
    documento = _documento(emitente)
    if len(documento) not in (11, 14):
        raise ErroLeitura("CNPJ/CPF do prestador não encontrado no XML.")

    return NotaPdf(
        tipo=cfg.TIPO_NFSE,
        numero=str(int(_obrigatorio(info, "número da NFS-e", "nNFSe"))),
        emissao=_data(emissao, "data de emissão"),
        valor=_valor(_obrigatorio(dps, "valor do serviço", "vServPrest", "vServ"),
                     "valor do serviço"),
        emitente_nome=_obrigatorio(emitente, "nome do prestador", "xNome"),
        emitente_documento=documento,
        situacao="",                       # X2: o XML não diz se foi cancelada depois
        chave=_chave(info, "NFS"),
        arquivo=arquivo,
        destinatario_documento=_documento(_achar(dps, "toma")),
        xml=True,
        regime=cfg.XML_NFSE_REGIMES.get(_texto(dps, "prest", "opSimpNac"), ""),
        atividade=_atividade(info),
        aliquota_iss=_valor(_texto(valores_nota, "pAliqAplic"), "alíquota"),
        valor_iss=_valor(_texto(valores_nota, "vISSQN"), "ISSQN apurado"),
        retencao_iss=cfg.XML_NFSE_RETENCAO_ISS.get(_texto(tributos, "tpRetISSQN"), ""),
        irrf=_valor(_texto(federais, "vRetIRRF"), "IRRF"),
        previdencia_retida=_valor(_texto(federais, "vRetCP"), "contribuição previdenciária"),
        # no padrão nacional, vRetCSLL é o total retido de PIS/COFINS/CSLL ("Contribuições
        # Sociais - Retidas" da DANFSe); conferido com os PDFs do lote 72929
        contribuicoes_retidas=_valor(_texto(federais, "vRetCSLL"), "contribuições sociais"),
        descricao_contribuicoes=f"Código {codigo}" if codigo else "",
    )


# ---------------------------------------------------------------------------
# Um XML
# ---------------------------------------------------------------------------


def ler_xml(caminho: Path, arquivo: str) -> NotaPdf:
    """Lê um XML de NF-e ou NFS-e. Levanta ErroLeitura com a explicação para o usuário."""
    try:
        raiz = ET.parse(caminho).getroot()
    except ET.ParseError:
        raise ErroLeitura("O XML está estragado ou incompleto (não foi possível ler).") from None
    except OSError:
        raise ErroLeitura("Não foi possível abrir o arquivo XML.") from None
    tipo = _nome(raiz)
    if tipo in cfg.XML_NFE_RAIZES:
        return _ler_nfe(raiz, arquivo)
    if tipo in cfg.XML_NFSE_RAIZES:
        return _ler_nfse(raiz, arquivo)
    if e_paulistana_xml(raiz):                    # X1a: Nota Paulistana (NFS-e de São Paulo)
        return ler_paulistana_xml(raiz, arquivo)
    if tipo == "NFe":
        raise ErroLeitura("XML de NF-e sem o protocolo de autorização da Sefaz (procure o XML "
                          "\"autorizado\", com nfeProc).")
    raise ErroLeitura(f"XML não reconhecido (\"{tipo}\"): não é NF-e nem NFS-e. Um evento "
                      "(cancelamento, carta de correção) não é lido.")
