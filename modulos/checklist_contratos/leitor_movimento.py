"""Movimento do Tasy (.csv) -> lista de Lancamento. Seção 3.1 e regras M1, M3 e M4 da especificação.

- Codificação UTF-16 (como o Tasy exporta, sem marca no início); UTF-8 e latin-1 de reserva.
- Lido com o módulo csv: o complemento pode ter quebra de linha dentro das aspas.
- Dois formatos, reconhecidos pelos títulos:
  - "Movimentos_NF" (o do protótipo): uma linha por conta, com a coluna Débito/Crédito;
  - "Movimento contábil" (o que o Tasy baixa um dia por vez): Conta débito / Conta crédito com "0" no
    lado vazio e o centro de custo; uma nota rateada vem em várias linhas, que são juntadas de volta
    (mesmo fato, conta e complemento) com os centros de custo guardados.
- Colunas achadas pelo título. Coluna obrigatória faltando = o arquivo inteiro vira erro.
- Linha com problema (colunas a menos, valor ilegível) = o arquivo inteiro vira erro, dizendo a
  linha: pular a linha esconderia uma nota da conferência.
- Débitos e créditos são lidos (os créditos servem para reconhecer estornos e devoluções, M4); a
  conferência usa só os débitos (M1).
- M3: o movimento pode ser um arquivo ou uma pasta (um .csv por dia, ou o mês inteiro). Na pasta,
  um arquivo com erro vira aviso e os outros continuam; um dia que aparece em dois arquivos é lido
  só do mais recente, com aviso (as notas daquele dia contariam em dobro).
"""

from __future__ import annotations

import csv
import html
import io
from decimal import Decimal
from pathlib import Path

from modulos.checklist_contratos import configuracao as cfg
from modulos.checklist_contratos.estornos import anular_estornos_e_devolucoes
from modulos.checklist_contratos.modelos import Aviso, ErroLeitura, Lancamento, Movimento
from modulos.checklist_contratos.normalizacao import normalizar


def decodificar(conteudo: bytes) -> str:
    """Bytes do .csv -> texto. UTF-16 quando tem marca (BOM) ou bytes nulos entre as letras."""
    if conteudo[:2] in (b"\xff\xfe", b"\xfe\xff"):
        codificacao = "utf-16"
    elif b"\x00" in conteudo[:200]:
        # sem marca: o lado do byte nulo diz a ordem ('"\x00' = little-endian, como o Tasy grava)
        codificacao = "utf-16-le" if conteudo[1:2] == b"\x00" else "utf-16-be"
    else:
        codificacao = None
    if codificacao:
        try:
            return conteudo.decode(codificacao)
        except UnicodeDecodeError:
            raise ErroLeitura("O arquivo parece UTF-16, mas não pôde ser lido assim.") from None
    for reserva in cfg.MOV_CODIFICACOES_RESERVA:
        try:
            return conteudo.decode(reserva)
        except UnicodeDecodeError:
            continue
    raise ErroLeitura("Codificação do arquivo não reconhecida.")


def converter_valor(texto: str) -> Decimal:
    """'21585,5' -> 21585.50; '3420' -> 3420.00; '1.234,56' -> 1234.56. ErroLeitura se ilegível."""
    limpo = texto.strip()
    if not cfg.RE_VALOR.fullmatch(limpo):
        raise ErroLeitura(f"valor \"{texto}\" não reconhecido")
    return Decimal(limpo.replace(".", "").replace(",", ".")).quantize(Decimal("0.01"))


def limpar_complemento(texto: str) -> str:
    """Converte entidades HTML (&#x2013; -> –) e junta espaços e quebras de linha repetidos."""
    return " ".join(html.unescape(texto).split())


def _linhas_do_csv(caminho: Path, obrigatorias: tuple[str, ...], titulos: list[str], leitor):
    """(número da linha, {título: texto}) de cada linha com conteúdo; ErroLeitura na linha com problema."""
    posicao = {c: titulos.index(c) for c in titulos if c}
    ultima = max(titulos.index(c) for c in obrigatorias)
    try:
        for linha in leitor:
            numero = leitor.line_num
            if not any(c.strip() for c in linha):
                continue
            if len(linha) <= ultima:
                raise ErroLeitura(f"Linha {numero}: tem {len(linha)} colunas, esperava pelo menos "
                                  f"{ultima + 1}.")
            yield numero, {c: (linha[i] if i < len(linha) else "") for c, i in posicao.items()}
    except csv.Error as erro:
        raise ErroLeitura(f"Linha {leitor.line_num}: fora do formato .csv esperado: {erro}") from None


def _valor(texto: str, numero: int) -> Decimal:
    try:
        return converter_valor(texto)
    except ErroLeitura as erro:
        raise ErroLeitura(f"Linha {numero}: {erro}.") from None


def _formato_nf(caminho: Path, titulos: list[str], leitor, estabelecimento: str) -> list[Lancamento]:
    """Movimentos_NF: uma linha por conta, Débito/Crédito; o lançamento é lote + lançamento."""
    lancamentos = []
    for numero, campos in _linhas_do_csv(caminho, cfg.MOV_COLUNAS_OBRIGATORIAS, titulos, leitor):
        natureza = campos[cfg.MOV_COLUNA_DEBITO_CREDITO].strip().upper()
        if natureza not in (cfg.MOV_DEBITO, cfg.MOV_CREDITO):
            continue
        complemento = limpar_complemento(campos[cfg.MOV_COLUNA_COMPLEMENTO])
        lote = campos[cfg.MOV_COLUNA_LOTE].strip()
        lancamento = campos[cfg.MOV_COLUNA_LANCAMENTO].strip()
        lancamentos.append(Lancamento(
            estabelecimento=estabelecimento,
            conta=campos[cfg.MOV_COLUNA_CONTA].strip(),
            nome_conta=campos[cfg.MOV_COLUNA_NOME_CONTA].strip(),
            valor=_valor(campos[cfg.MOV_COLUNA_VALOR], numero),
            lote=lote,
            lancamento=lancamento,
            data=campos[cfg.MOV_COLUNA_DATA].strip(),
            complemento=complemento,
            complemento_normalizado=normalizar(complemento),
            linha_arquivo=numero,
            arquivo=caminho.name,
            natureza=natureza,
            documento=f"{lote}/{lancamento}",
        ))
    return lancamentos


def _formato_contabil(caminho: Path, titulos: list[str], leitor, estabelecimento: str) -> list[Lancamento]:
    """Movimento contábil: as linhas rateadas por centro de custo voltam a ser uma por conta do fato."""
    juntos: dict[tuple, Lancamento] = {}
    for numero, campos in _linhas_do_csv(caminho, cfg.MOVC_COLUNAS_OBRIGATORIAS, titulos, leitor):
        debito = campos[cfg.MOVC_COLUNA_DEBITO].strip()
        credito = campos[cfg.MOVC_COLUNA_CREDITO].strip()
        if debito not in ("", cfg.MOVC_CONTA_VAZIA):
            natureza, conta = cfg.MOV_DEBITO, debito
        elif credito not in ("", cfg.MOVC_CONTA_VAZIA):
            natureza, conta = cfg.MOV_CREDITO, credito
        else:
            continue
        valor = _valor(campos[cfg.MOVC_COLUNA_VALOR], numero)
        complemento = limpar_complemento(campos[cfg.MOVC_COLUNA_COMPLEMENTO])
        fato = campos[cfg.MOVC_COLUNA_FATO].strip()
        centro = campos.get(cfg.MOVC_COLUNA_CENTRO_CUSTO, "").strip()
        chave = (fato, natureza, conta, complemento)
        if chave in juntos:
            atual = juntos[chave]
            atual.valor += valor
            atual.centros_custo += ((centro, valor),)
            continue
        juntos[chave] = Lancamento(
            estabelecimento=estabelecimento,
            conta=conta,
            nome_conta=campos[cfg.MOVC_COLUNA_NOME_CONTA].strip(),
            valor=valor,
            lote="",
            lancamento=campos[cfg.MOVC_COLUNA_LANCAMENTO].strip(),
            data=campos[cfg.MOVC_COLUNA_DATA].strip(),
            complemento=complemento,
            complemento_normalizado=normalizar(complemento),
            linha_arquivo=numero,
            arquivo=caminho.name,
            natureza=natureza,
            documento=f"fato {fato}",
            centros_custo=((centro, valor),),
        )
    return list(juntos.values())


def ler_linhas(caminho: Path, estabelecimento: str) -> list[Lancamento]:
    """Lê um .csv do movimento (os dois formatos). Devolve débitos e créditos, na ordem do arquivo.

    Levanta ErroLeitura (mensagem para o usuário) se o arquivo não puder ser lido.
    """
    caminho = Path(caminho)
    try:
        conteudo = caminho.read_bytes()
    except OSError as erro:
        raise ErroLeitura(f"Não foi possível abrir o arquivo: {erro}") from None

    leitor = csv.reader(io.StringIO(decodificar(conteudo), newline=""), delimiter=cfg.MOV_SEPARADOR)
    try:
        titulos = [t.strip() for t in next(leitor)]
    except StopIteration:
        raise ErroLeitura("Arquivo vazio.") from None
    except csv.Error as erro:
        raise ErroLeitura(f"Arquivo fora do formato .csv esperado: {erro}") from None

    if cfg.MOV_COLUNA_DEBITO_CREDITO not in titulos and all(c in titulos for c in cfg.MOVC_COLUNAS_IDENTIFICACAO):
        faltando = [c for c in cfg.MOVC_COLUNAS_OBRIGATORIAS if c not in titulos]
        if faltando:
            raise ErroLeitura("Colunas não encontradas: " + ", ".join(faltando)
                              + ". Confira se é a exportação \"Movimento contábil\" do Tasy.")
        return _formato_contabil(caminho, titulos, leitor, estabelecimento)
    faltando = [c for c in cfg.MOV_COLUNAS_OBRIGATORIAS if c not in titulos]
    if faltando:
        raise ErroLeitura("Colunas não encontradas: " + ", ".join(faltando)
                          + ". Confira se é a exportação do movimento do Tasy (Movimentos_NF ou "
                            "Movimento contábil).")
    return _formato_nf(caminho, titulos, leitor, estabelecimento)


def ler_movimento(caminho: Path, estabelecimento: str) -> list[Lancamento]:
    """M1: os débitos de um .csv do movimento, na ordem (sem tratar estornos)."""
    return [l for l in ler_linhas(caminho, estabelecimento) if l.natureza == cfg.MOV_DEBITO]


def arquivos_do_movimento(caminho: Path) -> list[Path]:
    """O próprio arquivo, ou os .csv da pasta (sem subpastas), em ordem de nome."""
    caminho = Path(caminho)
    if caminho.is_dir():
        return sorted((p for p in caminho.glob("*.csv") if p.is_file() and not p.name.startswith("~$")),
                      key=lambda p: p.name.lower())
    return [caminho]


def ler_movimentos(caminho: Path, estabelecimento: str) -> Movimento:
    """M3 e M4: lê o arquivo ou todos os .csv da pasta e anula estornos e notas devolvidas.

    Levanta ErroLeitura se nenhum arquivo pôde ser lido.
    """
    arquivos = arquivos_do_movimento(caminho)
    if not arquivos:
        raise ErroLeitura(f"A pasta {Path(caminho).name} não tem nenhum arquivo .csv.")
    avisos: list[Aviso] = []
    por_arquivo: dict[Path, list[Lancamento]] = {}
    for arquivo in arquivos:
        try:
            por_arquivo[arquivo] = ler_linhas(arquivo, estabelecimento)
        except ErroLeitura as erro:
            if len(arquivos) == 1:
                raise
            avisos.append(Aviso(arquivo.name, f"{erro} Arquivo deixado de fora."))
    if not por_arquivo:
        raise ErroLeitura("Nenhum arquivo da pasta pôde ser lido (veja os avisos).")

    # dia repetido: vale o arquivo mais recente (data de gravação), os outros perdem aquele dia
    arquivos_por_dia: dict[str, list[Path]] = {}
    for arquivo, lancamentos in por_arquivo.items():
        for dia in dict.fromkeys(l.data for l in lancamentos):
            arquivos_por_dia.setdefault(dia, []).append(arquivo)
    escolhido: dict[str, Path] = {}
    for dia, lista in arquivos_por_dia.items():
        escolhido[dia] = max(lista, key=lambda p: (p.stat().st_mtime, p.name))
        if len(lista) > 1:
            nomes = ", ".join(p.name for p in lista)
            avisos.append(Aviso(escolhido[dia].name,
                                f"O dia {dia} está em {len(lista)} arquivos ({nomes}): usei só o mais "
                                f"recente, {escolhido[dia].name}."))
    linhas = [l for arquivo, lista in por_arquivo.items() for l in lista if escolhido[l.data] == arquivo]
    movimento = anular_estornos_e_devolucoes(linhas)
    movimento.avisos[:0] = avisos
    return movimento
