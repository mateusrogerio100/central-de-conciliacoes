"""Nota Fiscal Paulistana (NFS-e da Prefeitura de São Paulo) -> NotaPdf. Regras L2a e X1a.

Pedido do usuário (18/11/2026): prestador de São Paulo emite a nota no site da prefeitura de lá, que
não é a DANFSe do padrão nacional. O PDF e o XML têm outro desenho, mas trazem os mesmos dados que a
conferência usa (número, emissão, valor, prestador, tomador, ISS e retenções federais). Desde a reforma
tributária, a nota traz também o "Identificador Nacional" (a chave de 50 dígitos do padrão nacional):
é a chave usada para juntar o PDF e o XML da mesma nota (X2) e achar repetidas (L6).

- PDF: lido pelo texto da 1ª página (como a DANFE). O número e o CNPJ do prestador são conferidos
  contra o Identificador Nacional (como a L4 da DANFE): se não baterem, erro de leitura.
- XML: raiz `NFe` sem namespace, com `ChaveNFe` (a NF-e de compra tem `infNFe`).
- Retenções federais: só o layout novo (com "Contribuições Sociais - Retidas" no PDF e
  `RetencaoPisCofins` no XML). Os campos COFINS e PIS/PASEP do layout novo ficam ao lado do IPI e não
  são retenção (como a "apuração própria" da DANFSe): não entram. Sem o layout novo, as Contribuições
  Sociais ficam "não lidas" (None) e o relatório pede para conferir.
- O PDF não diz o regime (Simples): fica em branco. O XML diz (`OpcaoSimples` 0 = Não Optante).
- Situação: PDF com "CANCELADA" (em maiúsculas) = Cancelada; senão, em branco (como o XML nacional,
  X2). No XML, `StatusNFe` C = Cancelada, E = Extraviada; N (normal) fica em branco.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal, InvalidOperation

from modulos.conferencia_nf import configuracao as cfg
from modulos.conferencia_nf.leitor_danfe import converter_valor_pdf, so_digitos
from modulos.conferencia_nf.modelos import ErroLeitura, NotaPdf

RE_NUMERO = re.compile(r"^\s*(\d{8})\s*$", re.MULTILINE)
RE_EMISSAO = re.compile(r"(\d{2})/(\d{2})/(\d{4}) \d{2}:\d{2}:\d{2}")
RE_CHAVE = re.compile(r"Identificador Nacional:\s*(\d{50})")
RE_VALOR_TOTAL = re.compile(r"VALOR TOTAL DO SERVIÇO\s*=\s*R\$\s*([\d.,]+)")
RE_DOCUMENTO = re.compile(r"CPF/CNPJ:\s*([\d./-]+)")
RE_NOME = re.compile(r"Nome/Razão Social:\s*(.+)")
RE_VALOR = re.compile(r"\d{1,3}(?:\.\d{3})*,\d{2}%?|-")
RE_ATIVIDADE = re.compile(r"Código do Serviço\s*\n\s*(\d+ - .+)")
RE_DESCRICAO_CONTRIBUICOES = re.compile(r"Descrição Contribuições Sociais - Retidas\s*\n\s*[\d.,]+\s+(\d)\s*-")
RE_CANCELADA = re.compile(r"\bCANCELADA\b")


# ---------------------------------------------------------------------------
# Chave nacional (50 dígitos): município (7), ambiente (1), tipo de inscrição (1), CNPJ/CPF (14),
# número da NFS-e (13), ano e mês (4), código (9), dígito (1)
# ---------------------------------------------------------------------------

def _conferir_chave(nota: NotaPdf):
    """Como a L4 da DANFE: o número e o CNPJ/CPF lidos têm que ser os do Identificador Nacional."""
    chave = nota.chave
    if len(chave) != cfg.PAULISTANA_TAMANHO_CHAVE:
        return
    if chave[cfg.PAULISTANA_CHAVE_POSICAO_DOCUMENTO] != nota.emitente_documento.zfill(14) \
            or str(int(chave[cfg.PAULISTANA_CHAVE_POSICAO_NUMERO])) != nota.numero:
        raise ErroLeitura("Número ou CNPJ da Nota Paulistana não conferem com o Identificador Nacional "
                          f"(nº {nota.numero}, CNPJ {nota.emitente_documento}; chave {chave}).")


def _chave_sem_identificador(documento: str, numero: str) -> str:
    """Nota sem o Identificador Nacional (anterior à reforma): uma chave só para juntar PDF e XML."""
    return f"{cfg.PAULISTANA_PREFIXO_CHAVE}{documento.zfill(14)}{numero.zfill(13)}"


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def e_paulistana(texto: str) -> bool:
    """L2a: o PDF é uma Nota Paulistana."""
    return all(t in texto for t in cfg.PDF_TEXTOS_PAULISTANA)


def _bloco(texto: str, inicio: str, fim: str) -> str:
    """O texto entre dois títulos de bloco ("" se não achar o início)."""
    posicao = texto.find(inicio)
    if posicao < 0:
        return ""
    resto = texto[posicao + len(inicio):]
    final = resto.find(fim)
    return resto if final < 0 else resto[:final]


def _documento(bloco: str, nome: str, obrigatorio: bool = True) -> str:
    achado = RE_DOCUMENTO.search(bloco)
    digitos = so_digitos(achado.group(1)) if achado else ""
    if len(digitos) not in (11, 14):
        if obrigatorio:
            raise ErroLeitura(f"Campo \"{nome}\" não encontrado na Nota Paulistana.")
        return ""
    return digitos


def _valor_opcional(texto: str | None) -> Decimal | None:
    """Campo só do relatório: não achado = None; "-" = 0,00."""
    if texto is None:
        return None
    if texto.strip() == "-":
        return Decimal("0.00")
    try:
        return converter_valor_pdf(texto.replace("%", "").strip())
    except ErroLeitura:
        return None


def _linha_de_valores(linhas: list[str], titulo: str) -> list[str] | None:
    """Os valores da linha logo abaixo da linha de títulos que começa com `titulo`."""
    for posicao, linha in enumerate(linhas[:-1]):
        if linha.strip().startswith(titulo):
            return RE_VALOR.findall(linhas[posicao + 1])
    return None


def _retencao_iss_pdf(texto: str) -> str:
    """"RETIDO pelo Tomador" = Retido; "vencimento do ISS" (o prestador paga) = Não Retido;
    nenhum dos dois = "" (não lido: o relatório pede para conferir)."""
    if cfg.PAULISTANA_TEXTO_ISS_RETIDO in texto.lower():
        return "Retido"
    if cfg.PAULISTANA_TEXTO_ISS_NAO_RETIDO in texto.lower():
        return "Não Retido"
    return ""


def ler_paulistana_pdf(texto: str, arquivo: str) -> NotaPdf:
    """Texto da 1ª página da Nota Paulistana -> NotaPdf. Levanta ErroLeitura com a explicação."""
    numero = RE_NUMERO.search(texto)
    if not numero:
        raise ErroLeitura("Campo \"Número da Nota\" não encontrado na Nota Paulistana.")
    numero = str(int(numero.group(1)))
    emissao = RE_EMISSAO.search(texto)
    if not emissao:
        raise ErroLeitura("Campo \"Data e Hora de Emissão\" não encontrado na Nota Paulistana.")
    dia, mes, ano = emissao.groups()
    try:
        emissao = date(int(ano), int(mes), int(dia))
    except ValueError:
        raise ErroLeitura(f"Data de emissão \"{emissao.group(0)}\" inválida na Nota Paulistana.") from None
    valor = RE_VALOR_TOTAL.search(texto)
    if not valor:
        raise ErroLeitura("Campo \"VALOR TOTAL DO SERVIÇO\" não encontrado na Nota Paulistana.")
    valor = converter_valor_pdf(valor.group(1))

    prestador = _bloco(texto, cfg.PAULISTANA_BLOCO_PRESTADOR, cfg.PAULISTANA_BLOCO_TOMADOR)
    tomador = _bloco(texto, cfg.PAULISTANA_BLOCO_TOMADOR, cfg.PAULISTANA_BLOCO_INTERMEDIARIO)
    documento = _documento(prestador, "CPF/CNPJ do prestador")
    nome = RE_NOME.search(prestador)
    if not nome or not nome.group(1).strip():
        raise ErroLeitura("Campo \"Nome/Razão Social\" do prestador não encontrado na Nota Paulistana.")
    chave = RE_CHAVE.search(texto)
    chave = chave.group(1) if chave else _chave_sem_identificador(documento, numero)

    linhas = texto.split("\n")
    federais = _linha_de_valores(linhas, cfg.PAULISTANA_TITULO_FEDERAIS)
    sociais = _linha_de_valores(linhas, cfg.PAULISTANA_TITULO_CONTRIBUICOES)
    iss = _linha_de_valores(linhas, cfg.PAULISTANA_TITULO_ISS)
    # títulos: Contrib. Previdenciária - Retida, IRRF, COFINS, PIS/PASEP, IPI (os 3 últimos não são retenção)
    federais = federais if federais and len(federais) == 5 else None
    # títulos: Base de Cálculo... -> Valor Total das Deduções, Base de Cálculo, Alíquota, Valor do ISS, Crédito
    iss = iss if iss and len(iss) == 5 else None
    codigo = RE_DESCRICAO_CONTRIBUICOES.search(texto)
    atividade = RE_ATIVIDADE.search(texto)

    nota = NotaPdf(
        tipo=cfg.TIPO_NFSE,
        numero=numero,
        emissao=emissao,
        valor=valor,
        emitente_nome=" ".join(nome.group(1).split()),
        emitente_documento=documento,
        situacao="Cancelada" if RE_CANCELADA.search(texto) else "",
        chave=chave,
        arquivo=arquivo,
        destinatario_documento=_documento(tomador, "CPF/CNPJ do tomador", obrigatorio=False),
        regime="",                                     # o PDF não diz
        atividade=" ".join(atividade.group(1).split()) if atividade else "",
        aliquota_iss=_valor_opcional(iss[2]) if iss else None,
        valor_iss=_valor_opcional(iss[3]) if iss else None,
        retencao_iss=_retencao_iss_pdf(texto),
        irrf=_valor_opcional(federais[1]) if federais else None,
        previdencia_retida=_valor_opcional(federais[0]) if federais else None,
        contribuicoes_retidas=_valor_opcional(sociais[0]) if sociais else None,
        descricao_contribuicoes=f"Código {codigo.group(1)}" if codigo else "",
    )
    _conferir_chave(nota)
    return nota


# ---------------------------------------------------------------------------
# XML
# ---------------------------------------------------------------------------

def _nome(elemento: ET.Element) -> str:
    return elemento.tag.rsplit("}", 1)[-1]


def _filho(pai: ET.Element | None, nome: str) -> ET.Element | None:
    if pai is None:
        return None
    return next((e for e in pai.iter() if e is not pai and _nome(e) == nome), None)


def _texto(pai: ET.Element | None, nome: str) -> str:
    elemento = _filho(pai, nome)
    return " ".join((elemento.text or "").split()) if elemento is not None else ""


def _numero_xml(texto: str, nome_campo: str, obrigatorio: bool = False) -> Decimal | None:
    """'2827.35' -> Decimal com 2 casas. Etiqueta que não veio: 0,00 (como no XML nacional)."""
    if not texto:
        if obrigatorio:
            raise ErroLeitura(f"Campo \"{nome_campo}\" não encontrado no XML da Nota Paulistana.")
        return Decimal("0.00")
    try:
        return Decimal(texto).quantize(Decimal("0.01"))
    except InvalidOperation:
        raise ErroLeitura(f"Valor \"{texto}\" do campo \"{nome_campo}\" não reconhecido no XML.") from None


def _aliquota_xml(texto: str) -> Decimal | None:
    """'0.029' (fração) -> Decimal('2.90') (em %, como na DANFSe). Não veio ou inválida: None."""
    try:
        return (Decimal(texto) * 100).quantize(Decimal("0.01")) if texto else None
    except InvalidOperation:
        return None


def e_paulistana_xml(raiz: ET.Element) -> bool:
    """X1a: raiz NFe com ChaveNFe (a NF-e de compra tem infNFe)."""
    return _nome(raiz) == "NFe" and _filho(raiz, cfg.XML_PAULISTANA_CHAVE) is not None \
        and _filho(raiz, cfg.XML_NFE_INFO) is None


def ler_paulistana_xml(raiz: ET.Element, arquivo: str) -> NotaPdf:
    """XML da Nota Paulistana -> NotaPdf. Levanta ErroLeitura com a explicação."""
    numero = so_digitos(_texto(_filho(raiz, cfg.XML_PAULISTANA_CHAVE), "NumeroNFe"))
    if not numero:
        raise ErroLeitura("Campo \"NumeroNFe\" não encontrado no XML da Nota Paulistana.")
    numero = str(int(numero))
    emissao = _texto(raiz, "DataEmissaoNFe")
    try:
        emissao = date.fromisoformat(emissao[:10])
    except ValueError:
        raise ErroLeitura("Campo \"DataEmissaoNFe\" não encontrado ou inválido no XML da Nota "
                          "Paulistana.") from None
    prestador = _filho(raiz, "CPFCNPJPrestador")
    documento = so_digitos(_texto(prestador, "CNPJ") or _texto(prestador, "CPF"))
    if len(documento) not in (11, 14):
        raise ErroLeitura("CNPJ/CPF do prestador não encontrado no XML da Nota Paulistana.")
    nome = _texto(raiz, "RazaoSocialPrestador")
    if not nome:
        raise ErroLeitura("Campo \"RazaoSocialPrestador\" não encontrado no XML da Nota Paulistana.")
    tomador = _filho(raiz, "CPFCNPJTomador")
    chave = so_digitos(_texto(raiz, "ChaveNotaNacional")) or _chave_sem_identificador(documento, numero)
    codigo = _texto(raiz, "RetencaoPisCofins")              # só no layout novo
    aliquota = _texto(raiz, "AliquotaServicos")              # "0.029" = 2,90%
    iss_retido = _texto(raiz, "ISSRetido").lower()
    codigo_servico = so_digitos(_texto(raiz, "CodigoServico"))

    nota = NotaPdf(
        tipo=cfg.TIPO_NFSE,
        numero=numero,
        emissao=emissao,
        valor=_numero_xml(_texto(raiz, "ValorServicos"), "ValorServicos", obrigatorio=True),
        emitente_nome=nome,
        emitente_documento=documento,
        situacao=cfg.XML_PAULISTANA_SITUACOES.get(_texto(raiz, "StatusNFe"), ""),
        chave=chave,
        arquivo=arquivo,
        destinatario_documento=so_digitos(_texto(tomador, "CNPJ") or _texto(tomador, "CPF")),
        xml=True,
        regime=cfg.XML_PAULISTANA_REGIMES.get(_texto(raiz, "OpcaoSimples"), ""),
        atividade=codigo_servico.zfill(5) if codigo_servico else "",
        aliquota_iss=_aliquota_xml(aliquota),
        valor_iss=_numero_xml(_texto(raiz, "ValorISS"), "ValorISS"),
        retencao_iss={"true": "Retido", "false": "Não Retido"}.get(iss_retido, ""),
        irrf=_numero_xml(_texto(raiz, "ValorIR"), "ValorIR"),
        previdencia_retida=_numero_xml(_texto(raiz, "ValorINSS"), "ValorINSS"),
        # layout novo: ValorCSLL é o total retido de PIS/COFINS/CSLL (no PDF, "Contribuições
        # Sociais - Retidas"), como o vRetCSLL do XML nacional; sem o layout novo: não lido
        contribuicoes_retidas=_numero_xml(_texto(raiz, "ValorCSLL"), "ValorCSLL") if codigo else None,
        descricao_contribuicoes=f"Código {codigo}" if codigo else "",
    )
    _conferir_chave(nota)
    return nota
