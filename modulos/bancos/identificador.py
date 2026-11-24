"""Percorre a pasta de extratos e escolhe o leitor de cada arquivo.

Quem decide o banco/modelo é sempre o CONTEÚDO do arquivo (reconhece() de
cada leitor), nunca o nome do arquivo ou da pasta. O nome da pasta só é
usado para dar um aviso quando um extrato parece estar na pasta errada.
"""

import hashlib
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .leitores import LEITORES, LeitorBase
from .modelos import SaldoExtraido
from .util import (extrair_paginas_pdf, extrair_paginas_rapido, juntar_paginas, mensagem_pdf_sem_texto,
                   parece_escaneado)

# Situação de cada arquivo (aba "Arquivos" do relatório).
LIDO = "LIDO"
ESCANEADO = "ESCANEADO – CONFERIR MANUALMENTE"
MODELO_NAO_RECONHECIDO = "MODELO NÃO RECONHECIDO"
ERRO_DE_LEITURA = "ERRO DE LEITURA"
DUPLICADO = "DUPLICADO – IGNORADO"

# Palavras que identificam o banco pelo nome da pasta (só para o aviso
# de "pasta errada"). Escrever em minúsculas e sem acento.
# Para um banco novo, acrescente uma linha: "SIGLA": ["palavra 1", "palavra 2"].
# A sigla deve ser a mesma usada no atributo `banco` do leitor.
PALAVRAS_PASTA_POR_BANCO = {
    "BB": ["banco do brasil", "bb"],
    "CEF": ["cef", "caixa"],
    "SANTANDER": ["santander"],
    "SICOOB": ["sicoob"],
}


@dataclass
class ResumoArquivo:
    """O que aconteceu com um arquivo da pasta."""

    arquivo: Path
    subpasta: str                     # caminho relativo à pasta selecionada
    situacao: str
    modelo: str = ""
    mensagem: str = ""
    saldos: list[SaldoExtraido] = field(default_factory=list)


@dataclass
class ResultadoIdentificacao:
    saldos: list[SaldoExtraido] = field(default_factory=list)
    arquivos: list[ResumoArquivo] = field(default_factory=list)


def identificar_pasta(pasta: Path, competencia: date,
                      leitores: list[LeitorBase] | None = None,
                      progresso: Callable[[int, int, Path], None] | None = None,
                      ) -> ResultadoIdentificacao:
    """Lê todos os extratos da pasta e das subpastas.

    `progresso`, se informado, é chamado antes de cada arquivo com
    (número do arquivo, total de arquivos, caminho) — usado para mostrar
    o andamento no terminal ou na janela.
    """
    leitores = LEITORES if leitores is None else leitores
    pasta = Path(pasta)
    resultado = ResultadoIdentificacao()
    originais: dict[str, Path] = {}   # hash do conteúdo -> primeiro arquivo

    arquivos = listar_arquivos(pasta, leitores)
    for numero, arquivo in enumerate(arquivos, 1):
        if progresso:
            progresso(numero, len(arquivos), arquivo)
        subpasta = str(arquivo.parent.relative_to(pasta))
        subpasta = "" if subpasta == "." else subpasta

        codigo = _hash_arquivo(arquivo)
        if codigo in originais:
            original = originais[codigo]
            resultado.arquivos.append(ResumoArquivo(
                arquivo=arquivo, subpasta=subpasta, situacao=DUPLICADO,
                mensagem=f"cópia idêntica de {original.relative_to(pasta)}",
            ))
            continue
        originais[codigo] = arquivo

        resumo = processar_arquivo(arquivo, competencia, leitores)
        resumo.subpasta = subpasta
        if resumo.situacao == LIDO:
            aviso = aviso_pasta_errada(arquivo.parent.relative_to(pasta),
                                       _banco_do_modelo(resumo.modelo, leitores))
            if aviso:
                resumo.mensagem = _juntar(resumo.mensagem, aviso)
        resultado.arquivos.append(resumo)
        resultado.saldos.extend(resumo.saldos)

    return resultado


def listar_arquivos(pasta: Path, leitores: list[LeitorBase] | None = None) -> list[Path]:
    """Arquivos da pasta e subpastas com extensão que algum leitor aceita.

    Ignora temporários do Office ("~$...") e devolve em ordem alfabética
    do caminho, para o resultado ser sempre o mesmo.
    """
    leitores = LEITORES if leitores is None else leitores
    extensoes = {ext.lower() for leitor in leitores for ext in leitor.extensoes}
    encontrados = [
        arquivo for arquivo in Path(pasta).rglob("*")
        if arquivo.is_file()
        and arquivo.suffix.lower() in extensoes
        and not arquivo.name.startswith("~$")
    ]
    return sorted(encontrados, key=lambda a: str(a.relative_to(pasta)).lower())


def processar_arquivo(arquivo: Path, competencia: date,
                      leitores: list[LeitorBase] | None = None) -> ResumoArquivo:
    """Extrai o texto, escolhe o leitor e lê um único arquivo.

    Nunca levanta exceção: qualquer problema vira situação ERRO DE LEITURA,
    para não interromper o lote.
    """
    leitores = LEITORES if leitores is None else leitores
    resumo = ResumoArquivo(arquivo=arquivo, subpasta="", situacao=ERRO_DE_LEITURA)
    candidatos = [l for l in leitores if arquivo.suffix.lower() in l.extensoes]

    # Checagem rápida: PDF sem texto vira ESCANEADO sem passar pela leitura lenta do pdfplumber.
    # Se a checagem falhar ou achar texto, segue o caminho normal abaixo.
    try:
        previa = extrair_paginas_rapido(arquivo)
    except Exception:
        previa = None
    if previa is not None and parece_escaneado(previa):
        resumo.situacao = ESCANEADO
        resumo.mensagem = mensagem_pdf_sem_texto(arquivo, len(previa))
        return resumo

    try:
        paginas = extrair_paginas_pdf(arquivo)
    except Exception as erro:
        resumo.mensagem = f"não foi possível abrir o PDF: {erro}"
        return resumo

    if parece_escaneado(paginas):
        resumo.situacao = ESCANEADO
        resumo.mensagem = mensagem_pdf_sem_texto(arquivo, len(paginas))
        return resumo

    texto = juntar_paginas(paginas)
    try:
        reconhecidos = [l for l in candidatos if l.reconhece(texto)]
    except Exception as erro:
        resumo.mensagem = f"erro ao reconhecer o modelo: {erro}"
        return resumo

    if not reconhecidos:
        resumo.situacao = MODELO_NAO_RECONHECIDO
        return resumo
    if len(reconhecidos) > 1:
        nomes = ", ".join(l.nome for l in reconhecidos)
        resumo.mensagem = (f"reconhecido por mais de um modelo: {nomes}. O arquivo pode "
                           "conter vários extratos juntos ou ter sido gerado por OCR; "
                           "use um PDF por conta")
        return resumo

    leitor = reconhecidos[0]
    resumo.modelo = leitor.nome
    try:
        saldos = leitor.ler(texto, arquivo, competencia)
    except Exception as erro:
        resumo.mensagem = str(erro) or type(erro).__name__
        return resumo
    if not saldos:
        resumo.mensagem = "o leitor não devolveu nenhum saldo"
        return resumo

    for saldo in saldos:
        saldo.arquivo = saldo.arquivo or arquivo
        saldo.modelo = saldo.modelo or leitor.nome
    resumo.situacao = LIDO
    resumo.saldos = saldos
    return resumo


def bancos_no_nome_da_pasta(nome: str) -> set[str]:
    """Bancos cujas palavras-chave aparecem (como palavra inteira) no nome."""
    nome = _simplificar(nome)
    return {
        banco for banco, palavras in PALAVRAS_PASTA_POR_BANCO.items()
        if any(re.search(rf"\b{re.escape(p)}\b", nome) for p in palavras)
    }


def aviso_pasta_errada(caminho_relativo: Path, banco: str) -> str:
    """Aviso se alguma subpasta do caminho tem nome de OUTRO banco.

    Pasta cujo nome cita dois bancos diferentes não gera aviso (não dá
    para saber o que era esperado).
    """
    avisos = []
    for nome_pasta in Path(caminho_relativo).parts:
        bancos = bancos_no_nome_da_pasta(nome_pasta)
        if len(bancos) == 1 and banco not in bancos:
            avisos.append(f'Aviso: extrato do {banco} encontrado na pasta "{nome_pasta}"')
    return "; ".join(avisos)


def _banco_do_modelo(modelo: str, leitores: list[LeitorBase]) -> str:
    return next((l.banco for l in leitores if l.nome == modelo), "")


def _simplificar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c)).lower()


def _hash_arquivo(arquivo: Path) -> str:
    return hashlib.sha256(arquivo.read_bytes()).hexdigest()


def _juntar(*mensagens: str) -> str:
    return "; ".join(m for m in mensagens if m)
