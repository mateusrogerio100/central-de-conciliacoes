"""DANFE (nota de compra, NF-e) -> NotaPdf. Seção 3.2 e regras L3 e L4 da especificação.

Lê o texto da PRIMEIRA página (a nota pode ter 2 ou 3). Cada campo fica na linha logo abaixo do
seu rótulo. O número e o CNPJ lidos são conferidos contra a chave de acesso: se não baterem, a
leitura está errada e o PDF vira erro de leitura (nunca usar um dado lido errado).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from modulos.conferencia_nf import configuracao as cfg
from modulos.conferencia_nf.modelos import ErroLeitura, NotaPdf


def so_digitos(texto: str) -> str:
    return "".join(c for c in str(texto or "") if c.isdigit())


def converter_valor_pdf(texto: str) -> Decimal:
    """'7.900,00' -> Decimal('7900.00'). ErroLeitura se fora do formato."""
    achado = cfg.RE_VALOR_PDF.match(texto.replace("R$", "").strip())
    if not achado:
        raise ErroLeitura(f"Valor \"{texto}\" não reconhecido.")
    inteiro, centavos = achado.groups()
    return Decimal(f"{inteiro.replace('.', '')}.{centavos}")


def _linha_abaixo(linhas: list[str], termina_com: str) -> str | None:
    for indice, linha in enumerate(linhas[:-1]):
        if linha.strip().endswith(termina_com):
            return linhas[indice + 1]
    return None


def numero_da_chave(chave: str) -> str:
    """Número da nota que está dentro da chave de acesso (sem zeros à esquerda)."""
    return str(int(chave[cfg.CHAVE_POSICAO_NUMERO]))


def cnpj_da_chave(chave: str) -> str:
    return chave[cfg.CHAVE_POSICAO_CNPJ]


def ler_danfe(texto: str, arquivo: str) -> NotaPdf:
    """Texto da 1ª página da DANFE -> NotaPdf. Levanta ErroLeitura com a explicação."""
    linhas = texto.split("\n")
    numero = cfg.RE_DANFE_NUMERO.search(texto)
    chave = cfg.RE_DANFE_CHAVE.search(texto)
    emitente = cfg.RE_DANFE_EMITENTE.search(texto)
    linha_emissao = _linha_abaixo(linhas, cfg.DANFE_ROTULO_EMISSAO)
    linha_total = _linha_abaixo(linhas, cfg.DANFE_ROTULO_VALOR_TOTAL)
    linha_cnpj = next((linhas[i + 1] for i, linha in enumerate(linhas[:-1])
                       if linha.startswith(cfg.DANFE_ROTULO_CNPJ_INICIO)
                       and linha.strip().endswith(cfg.DANFE_ROTULO_CNPJ_FIM)), None)
    faltando = [nome for nome, achado in (
        ("número", numero), ("chave de acesso", chave), ("data da emissão", linha_emissao),
        ("valor total da nota", linha_total), ("CNPJ do emitente", linha_cnpj)) if not achado]
    if faltando:
        raise ErroLeitura("DANFE fora do modelo esperado: não foi encontrado o campo "
                          + ", ".join(faltando) + ".")

    datas = cfg.RE_DATA.findall(linha_emissao)
    documentos = cfg.RE_DOCUMENTO.findall(linha_cnpj)
    if not datas:
        raise ErroLeitura("Data de emissão não encontrada na DANFE.")
    if not documentos:
        raise ErroLeitura("CNPJ/CPF do emitente não encontrado na DANFE.")
    dia, mes, ano = datas[-1]
    try:
        emissao = date(int(ano), int(mes), int(dia))
    except ValueError:
        raise ErroLeitura(f"Data de emissão {dia}/{mes}/{ano} inválida na DANFE.") from None
    partes_total = linha_total.split()
    if not partes_total:
        raise ErroLeitura("Valor total da nota não encontrado na DANFE.")
    try:
        valor = converter_valor_pdf(partes_total[-1])
    except ErroLeitura:
        raise ErroLeitura(f"Valor total da nota \"{partes_total[-1]}\" não reconhecido na "
                          "DANFE.") from None
    # S15: a linha da data de emissão é a do destinatário (nome, CNPJ/CPF e data); não lido = ""
    destinatarios = cfg.RE_DOCUMENTO.findall(linha_emissao)
    digitos_numero = so_digitos(numero.group(1))
    if not digitos_numero:
        raise ErroLeitura("Número da nota não reconhecido na DANFE.")

    nota = NotaPdf(
        tipo=cfg.TIPO_NFE,
        numero=str(int(digitos_numero)),
        emissao=emissao,
        valor=valor,
        emitente_nome=" ".join(emitente.group(1).split()) if emitente else "",
        emitente_documento=so_digitos(documentos[-1]),
        situacao="",
        chave=so_digitos(chave.group(1))[-cfg.TAMANHO_CHAVE:],
        arquivo=arquivo,
        destinatario_documento=so_digitos(destinatarios[0]) if destinatarios else "",
    )
    # L4: a chave de acesso traz o CNPJ do emitente e o número; se não baterem, a leitura errou
    if cnpj_da_chave(nota.chave) != nota.emitente_documento \
            or numero_da_chave(nota.chave) != nota.numero:
        raise ErroLeitura("Número ou CNPJ lidos não conferem com a chave de acesso da DANFE "
                          f"(lido: nº {nota.numero}, CNPJ {nota.emitente_documento}; chave "
                          f"{nota.chave}).")
    return nota
