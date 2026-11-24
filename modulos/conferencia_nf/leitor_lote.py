"""Lote do Tasy (.csv) -> lista de Fato. Seção 3.1 da especificação.

Dois formatos, reconhecidos pelos títulos: o lote da tela de movimento (seção 3.1) e a exportação
"Movimento contábil" (seção 3.1a), que traz os mesmos lançamentos mais o centro de custo.

- Codificação UTF-16 (como o Tasy exporta); UTF-8 e latin-1 de reserva.
- Lido com o módulo csv: o complemento pode ter quebra de linha dentro das aspas.
- Colunas achadas pelo título. Coluna obrigatória faltando = o arquivo inteiro vira erro.
- Linha com problema (colunas a menos, valor ilegível) = o arquivo inteiro vira erro, dizendo a
  linha: pular a linha deixaria um fato pela metade e as partidas não fechariam por engano.
"""

from __future__ import annotations

import csv
import html
import io
from decimal import Decimal
from pathlib import Path

from modulos.conferencia_nf import configuracao as cfg
from modulos.conferencia_nf.modelos import ErroLeitura, Fato, Lancamento


def decodificar(conteudo: bytes) -> str:
    """Bytes do .csv -> texto. UTF-16 quando tem marca (BOM) ou bytes nulos entre as letras."""
    if conteudo[:2] in (b"\xff\xfe", b"\xfe\xff") or b"\x00" in conteudo[:200]:
        try:
            return conteudo.decode("utf-16")
        except UnicodeDecodeError:
            raise ErroLeitura("O arquivo parece UTF-16, mas não pôde ser lido assim.") from None
    for codificacao in cfg.LOTE_CODIFICACOES_RESERVA:
        try:
            return conteudo.decode(codificacao)
        except UnicodeDecodeError:
            continue
    raise ErroLeitura("Codificação do arquivo não reconhecida.")


def converter_valor(texto: str) -> Decimal:
    """'4887,2' -> 4887.20; '3420' -> 3420.00; '1.234,56' -> 1234.56. ErroLeitura se ilegível."""
    limpo = texto.strip()
    if not cfg.RE_VALOR_LOTE.fullmatch(limpo):
        raise ErroLeitura(f"valor \"{texto}\" não reconhecido")
    return Decimal(limpo.replace(".", "").replace(",", ".")).quantize(Decimal("0.01"))


def limpar_complemento(texto: str) -> str:
    """Converte entidades HTML (&#x2013; -> –) e junta espaços e quebras de linha repetidos."""
    return " ".join(html.unescape(texto).split())


def ler_lote(caminho: Path) -> list[Fato]:
    """Lê o .csv do lote. Devolve os fatos na ordem em que aparecem no lote.

    Levanta ErroLeitura (mensagem para o usuário) se o arquivo não puder ser lido.
    """
    caminho = Path(caminho)
    try:
        conteudo = caminho.read_bytes()
    except OSError as erro:
        raise ErroLeitura(f"Não foi possível abrir o arquivo: {erro}") from None

    leitor = csv.reader(io.StringIO(decodificar(conteudo), newline=""),
                        delimiter=cfg.LOTE_SEPARADOR)
    try:
        titulos = [t.strip() for t in next(leitor)]
    except StopIteration:
        raise ErroLeitura("Arquivo vazio.") from None
    except csv.Error as erro:
        raise ErroLeitura(f"Arquivo fora do formato .csv esperado: {erro}") from None

    if all(c in titulos for c in cfg.MOV_COLUNAS_IDENTIFICACAO):
        return _ler_movimento_contabil(caminho.name, leitor, titulos)

    faltando = [c for c in cfg.LOTE_COLUNAS_OBRIGATORIAS if c not in titulos]
    if faltando:
        raise ErroLeitura("Colunas não encontradas: " + ", ".join(faltando)
                          + ". Confira se é a exportação do movimento do Tasy, tipo Notas Fiscais.")
    posicao = {c: titulos.index(c) for c in cfg.LOTE_COLUNAS_OBRIGATORIAS + cfg.LOTE_COLUNAS_OPCIONAIS
               if c in titulos}

    fatos: dict[str, Fato] = {}
    try:
        for linha in leitor:
            if not any(campo.strip() for campo in linha):
                continue                       # linha em branco (ex.: no fim do arquivo)
            numero_linha = leitor.line_num
            if len(linha) < len(titulos):
                raise ErroLeitura(f"Linha {numero_linha}: tem {len(linha)} colunas, o título tem "
                                  f"{len(titulos)}.")

            def campo(coluna: str) -> str:
                return linha[posicao[coluna]].strip() if coluna in posicao else ""

            numero_fato = campo(cfg.LOTE_COLUNA_FATO)
            if not numero_fato:
                raise ErroLeitura(f"Linha {numero_linha}: \"{cfg.LOTE_COLUNA_FATO}\" vazio.")
            debito = campo(cfg.LOTE_COLUNA_DEBITO)
            credito = campo(cfg.LOTE_COLUNA_CREDITO)
            try:
                valor = converter_valor(campo(cfg.LOTE_COLUNA_VALOR))
            except ErroLeitura as erro:
                raise ErroLeitura(f"Linha {numero_linha}: {erro}.") from None

            fato = fatos.get(numero_fato)
            if fato is None:
                fato = fatos[numero_fato] = Fato(caminho.name, numero_fato,
                                                 campo(cfg.LOTE_COLUNA_DATA_MOVIMENTO))
            fato.lancamentos.append(Lancamento(
                sequencia=campo(cfg.LOTE_COLUNA_SEQUENCIA),
                conta_debito=debito,
                conta_credito=credito,
                nome_conta=campo(cfg.LOTE_COLUNA_CONTA_DEBITO)
                or campo(cfg.LOTE_COLUNA_CONTA_CREDITO),
                classificacao=campo(cfg.LOTE_COLUNA_CLASSIFICACAO_DEBITO)
                or campo(cfg.LOTE_COLUNA_CLASSIFICACAO_CREDITO),
                valor=valor,
                complemento=limpar_complemento(linha[posicao[cfg.LOTE_COLUNA_COMPLEMENTO]]),
            ))
    except csv.Error as erro:
        raise ErroLeitura(f"Linha {leitor.line_num}: fora do formato .csv esperado ({erro}).") \
            from None
    return list(fatos.values())


def _codigo(texto: str) -> str:
    """Conta ou centro de custo: "0" (lado não usado) = vazio."""
    texto = texto.strip()
    return "" if texto in ("", cfg.MOV_CONTA_VAZIA) else texto


def _ler_movimento_contabil(nome_arquivo: str, leitor, titulos: list[str]) -> list[Fato]:
    """Seção 3.1a: exportação "Movimento contábil", uma conta por linha, com o centro de custo."""
    faltando = [c for c in cfg.MOV_COLUNAS_OBRIGATORIAS if c not in titulos]
    if faltando:
        raise ErroLeitura("Colunas não encontradas: " + ", ".join(faltando)
                          + ". Confira se é a exportação \"Movimento contábil\" do Tasy.")
    posicao = {c: titulos.index(c) for c in titulos}
    fatos: dict[str, Fato] = {}
    try:
        for linha in leitor:
            if not any(campo.strip() for campo in linha):
                continue
            numero_linha = leitor.line_num
            if len(linha) < len(titulos):
                raise ErroLeitura(f"Linha {numero_linha}: tem {len(linha)} colunas, o título tem "
                                  f"{len(titulos)}.")

            def campo(coluna: str) -> str:
                return linha[posicao[coluna]].strip() if coluna in posicao else ""

            numero_fato = campo(cfg.MOV_COLUNA_FATO)
            if not numero_fato:
                raise ErroLeitura(f"Linha {numero_linha}: \"{cfg.MOV_COLUNA_FATO}\" vazio.")
            debito, credito = _codigo(campo(cfg.MOV_COLUNA_DEBITO)), \
                _codigo(campo(cfg.MOV_COLUNA_CREDITO))
            if bool(debito) == bool(credito):
                raise ErroLeitura(f"Linha {numero_linha}: a linha tem que ter a conta débito OU a "
                                  "conta crédito.")
            try:
                valor = converter_valor(campo(cfg.MOV_COLUNA_VALOR))
            except ErroLeitura as erro:
                raise ErroLeitura(f"Linha {numero_linha}: {erro}.") from None
            centro_custo = _codigo(campo(cfg.MOV_COLUNA_CENTRO_CUSTO))

            fato = fatos.get(numero_fato)
            if fato is None:
                fato = fatos[numero_fato] = Fato(nome_arquivo, numero_fato,
                                                 campo(cfg.MOV_COLUNA_DATA), com_centro_custo=True)
            fato.lancamentos.append(Lancamento(
                sequencia=campo(cfg.MOV_COLUNA_SEQUENCIA),
                conta_debito=debito,
                conta_credito=credito,
                nome_conta=campo(cfg.MOV_COLUNA_NOME_CONTA),
                classificacao=campo(cfg.MOV_COLUNA_CLASSIFICACAO),
                valor=valor,
                complemento=limpar_complemento(linha[posicao[cfg.MOV_COLUNA_COMPLEMENTO]]),
                centro_custo=centro_custo,
                nome_centro_custo=campo(cfg.MOV_COLUNA_NOME_CENTRO_CUSTO) if centro_custo else "",
            ))
    except csv.Error as erro:
        raise ErroLeitura(f"Linha {leitor.line_num}: fora do formato .csv esperado ({erro}).") \
            from None
    return list(fatos.values())
