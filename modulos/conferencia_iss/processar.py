"""
Orquestração da conferência: lê os arquivos, compara, gera o Excel e devolve o Resultado.

processar() é a ÚNICA porta de entrada para a interface. Ela nunca levanta exceção:
- arquivo com problema → registro de erro na aba Avisos e o resto continua;
- nada para comparar (prefeitura ilegível ou nenhum CSV do Tasy lido) → Resultado.erro;
- não conseguiu salvar o .xlsx → Resultado.erro com mensagem clara.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from modulos.conferencia_iss.comparador import comparar, comparar_por_nome
from modulos.conferencia_iss.leitor_tasy import ler_csv_tasy
from modulos.conferencia_iss.modelos import (
    MUNICIPIO_RB,
    NIVEL_AVISO,
    NIVEL_ERRO,
    NIVEL_OK,
    TIPO_ARQUIVO_PREFEITURA,
    TIPO_ARQUIVO_TASY,
    Aviso,
    Resultado,
)
from modulos.conferencia_iss.municipios import municipio as cadastro_municipio
from modulos.conferencia_iss.normalizar import formatar_documento
from modulos.conferencia_iss.relatorio_excel import gerar_relatorio

PREFIXO_ARQUIVO = "Conferencia_ISS_RB"        # padrão (Cidade Beta)
NOME_VARIAS_UNIDADES = "Varias_unidades"
NOME_SEM_UNIDADE = "Sem_unidade"
NOME_SEM_COMPETENCIA = "sem_competencia"

# ao_progredir(percentual de 0 a 100, mensagem para a tela)
FuncaoProgresso = Callable[[int, str], None]


def processar(arquivos_tasy: list[Path], arquivo_prefeitura: Path,
              ao_progredir: FuncaoProgresso | None = None,
              agora: datetime | None = None,
              municipio: str = MUNICIPIO_RB) -> Resultado:
    """
    Faz a conferência completa e devolve o Resultado (nunca levanta exceção).

    municipio: MUNICIPIO_RB, MUNICIPIO_SJ, MUNICIPIO_AV ou MUNICIPIO_CP — define qual
    relatório da prefeitura é esperado (e, em Cidade Gama, a comparação por nome).
    """
    resultado = Resultado(municipio=municipio)
    try:
        _processar(resultado, arquivos_tasy, arquivo_prefeitura,
                   ao_progredir, agora or datetime.now())
    except Exception as erro:  # rede de segurança: a interface nunca recebe exceção
        resultado.erro = f"Erro inesperado durante a conferência: {erro}"
    return resultado


def _processar(resultado: Resultado, arquivos_tasy, arquivo_prefeitura,
               ao_progredir, agora: datetime) -> None:
    def progresso(percentual: int, mensagem: str) -> None:
        if ao_progredir is not None:
            ao_progredir(percentual, mensagem)

    cidade = cadastro_municipio(resultado.municipio)

    # 1) CSVs do Tasy
    vistos: set[Path] = set()
    tasy_lidos = 0
    total = max(len(arquivos_tasy), 1)
    for posicao, arquivo in enumerate(arquivos_tasy):
        arquivo = Path(arquivo)
        progresso(5 + 40 * posicao // total, f"Lendo {arquivo.name}...")
        chave = _chave_caminho(arquivo)
        if chave in vistos:
            resultado.avisos.append(Aviso(
                arquivo=arquivo.name, tipo_arquivo=TIPO_ARQUIVO_TASY, nivel=NIVEL_AVISO,
                mensagem="Arquivo selecionado mais de uma vez; a cópia repetida foi ignorada.",
            ))
            continue
        vistos.add(chave)

        leitura = ler_csv_tasy(arquivo)
        if leitura.erro:
            resultado.avisos.append(Aviso(
                arquivo=leitura.arquivo, tipo_arquivo=TIPO_ARQUIVO_TASY, nivel=NIVEL_ERRO,
                mensagem=leitura.erro, linhas_lidas=0,
            ))
            continue
        tasy_lidos += 1
        resultado.notas_tasy.extend(leitura.notas)
        resultado.avisos.append(Aviso(
            arquivo=leitura.arquivo, tipo_arquivo=TIPO_ARQUIVO_TASY, nivel=NIVEL_OK,
            mensagem="OK", linhas_lidas=len(leitura.notas),
            unidades=", ".join(leitura.unidades or leitura.estabelecimentos),
        ))
        resultado.avisos.extend(leitura.avisos)
        for unidade in leitura.unidades or leitura.estabelecimentos:
            if unidade not in resultado.unidades:
                resultado.unidades.append(unidade)

    # 2) Relatório da prefeitura
    arquivo_prefeitura = Path(arquivo_prefeitura)
    progresso(50, f"Lendo {arquivo_prefeitura.name}...")
    prefeitura = cidade.ler_relatorio(arquivo_prefeitura)
    if prefeitura.erro:
        resultado.avisos.append(Aviso(
            arquivo=prefeitura.arquivo, tipo_arquivo=TIPO_ARQUIVO_PREFEITURA, nivel=NIVEL_ERRO,
            mensagem=prefeitura.erro, linhas_lidas=0,
        ))
    else:
        resultado.linhas_prefeitura = prefeitura.linhas
        resultado.competencia = prefeitura.competencia
        resultado.competencia_texto = prefeitura.competencia_texto
        resultado.inscricao_municipal = prefeitura.inscricao_municipal
        resultado.documento_tomador = prefeitura.documento_tomador
        resultado.avisos.append(Aviso(
            arquivo=prefeitura.arquivo, tipo_arquivo=TIPO_ARQUIVO_PREFEITURA, nivel=NIVEL_OK,
            mensagem="OK", linhas_lidas=len(prefeitura.linhas),
        ))
        resultado.avisos.extend(prefeitura.avisos)
        aviso_unidade = _aviso_unidade_diferente(resultado, prefeitura.arquivo)
        if aviso_unidade:
            resultado.avisos.append(aviso_unidade)

    # Sem os dois lados não há conferência: o relatório sairia enganoso.
    problemas = []
    if prefeitura.erro:
        problemas.append(f"o relatório da prefeitura não pôde ser lido ({prefeitura.erro})")
    if tasy_lidos == 0:
        problemas.append("nenhum CSV do Tasy pôde ser lido (veja os avisos)")
    if problemas:
        resultado.erro = "Relatório não gerado: " + "; ".join(problemas) + "."
        progresso(100, "Não foi possível fazer a conferência.")
        return

    # 3) Comparação
    progresso(65, "Comparando as notas...")
    comparar_notas = comparar_por_nome if cidade.compara_por_nome else comparar
    comparacao = comparar_notas(resultado.notas_tasy, resultado.linhas_prefeitura)
    resultado.itens = comparacao.itens
    resultado.avisos.extend(comparacao.avisos)

    # 4) Excel
    progresso(85, "Gerando o relatório em Excel...")
    caminho = caminho_do_relatorio(
        arquivo_prefeitura.parent, resultado.competencia, resultado.unidades, agora,
        prefixo=cidade.prefixo_arquivo,
    )
    try:
        resultado.caminho_relatorio = gerar_relatorio(resultado, caminho, gerado_em=agora)
    except PermissionError:
        resultado.erro = (
            f"Não foi possível salvar o relatório na pasta {caminho.parent}. "
            "Verifique se você tem permissão para gravar nessa pasta "
            "(ou mova o arquivo da prefeitura para outra pasta) e tente de novo."
        )
    except OSError as erro:
        resultado.erro = (
            f"Não foi possível salvar o relatório em {caminho}: {erro.strerror or erro}."
        )
    progresso(100, "Concluído." if resultado.erro is None else "Relatório não salvo.")


def _aviso_unidade_diferente(resultado: Resultado, arquivo: str) -> Aviso | None:
    """
    O relatório da prefeitura traz o CNPJ da unidade (Cidade Gama): se nenhum CSV do Tasy é
    dessa unidade, provavelmente escolheram o relatório (ou os CSVs) de outra unidade.
    """
    if not resultado.documento_tomador:
        return None
    do_tasy = {n.documento_destinatario for n in resultado.notas_tasy if n.documento_destinatario}
    if not do_tasy or resultado.documento_tomador in do_tasy:
        return None
    return Aviso(
        arquivo=arquivo, tipo_arquivo="", nivel=NIVEL_AVISO,
        mensagem=(
            f"ATENÇÃO: o relatório da prefeitura é do CNPJ "
            f"{formatar_documento(resultado.documento_tomador)}, mas os CSVs do Tasy são do "
            f"CNPJ {', '.join(formatar_documento(d) for d in sorted(do_tasy))}. "
            "Confira se os arquivos são da mesma unidade."
        ),
    )


# ---------------------------------------------------------------------
# Prévia (confirmação na tela logo depois de escolher os arquivos)
# ---------------------------------------------------------------------
@dataclass
class PreviaTasy:
    notas: int = 0
    unidades: list[str] = field(default_factory=list)          # nomes fantasia
    estabelecimentos: list[str] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)              # "arquivo.csv: motivo"

    @property
    def unidades_misturadas(self) -> bool:
        return len(self.estabelecimentos) > 1


@dataclass
class PreviaPrefeitura:
    linhas: int = 0
    competencia_texto: str = ""
    inscricao_municipal: str = ""
    documento_tomador: str = ""      # CNPJ da unidade já formatado (Cidade Gama)
    erro: str | None = None


def previa_tasy(arquivos: list[Path]) -> PreviaTasy:
    """Lê os CSVs só para contar notas e unidades (não compara nada)."""
    previa = PreviaTasy()
    vistos: set[Path] = set()
    for arquivo in arquivos:
        arquivo = Path(arquivo)
        chave = _chave_caminho(arquivo)
        if chave in vistos:
            continue
        vistos.add(chave)
        leitura = ler_csv_tasy(arquivo)
        if leitura.erro:
            previa.erros.append(f"{leitura.arquivo}: {leitura.erro}")
            continue
        previa.notas += len(leitura.notas)
        for unidade in leitura.unidades or leitura.estabelecimentos:
            if unidade not in previa.unidades:
                previa.unidades.append(unidade)
        for estabelecimento in leitura.estabelecimentos:
            if estabelecimento not in previa.estabelecimentos:
                previa.estabelecimentos.append(estabelecimento)
    return previa


def previa_prefeitura(arquivo: Path, municipio: str = MUNICIPIO_RB) -> PreviaPrefeitura:
    """Lê o relatório da prefeitura só para mostrar competência, inscrição e linhas."""
    try:
        leitura = cadastro_municipio(municipio).ler_relatorio(arquivo)
    except Exception as erro:  # rede de segurança: os leitores não levantam exceção
        return PreviaPrefeitura(erro=f"Erro inesperado ao ler o arquivo: {erro}")
    return PreviaPrefeitura(
        linhas=len(leitura.linhas),
        competencia_texto=leitura.competencia_texto,
        inscricao_municipal=leitura.inscricao_municipal,
        documento_tomador=formatar_documento(leitura.documento_tomador),
        erro=leitura.erro,
    )


def _chave_caminho(caminho: Path) -> Path:
    try:
        return caminho.resolve()
    except OSError:
        return caminho.absolute()


# ---------------------------------------------------------------------
# Nome do arquivo
# ---------------------------------------------------------------------
def nome_para_arquivo(texto: str) -> str:
    """"AME Cidade Beta" → "AME_Cidade_Beta" (sem acentos; espaços → _)."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    limpo = re.sub(r"[^A-Za-z0-9._-]+", "_", sem_acento.strip())
    return re.sub(r"_+", "_", limpo).strip("_.")


def nome_do_relatorio(competencia: str, unidades: list[str], agora: datetime,
                      prefixo: str = PREFIXO_ARQUIVO) -> str:
    """Conferencia_ISS_RB_<AAAA-MM>_<Unidade>_<HHhMM>.xlsx (ou Conferencia_ISS_SJ_...)"""
    if len(unidades) > 1:
        unidade = NOME_VARIAS_UNIDADES
    elif unidades:
        unidade = nome_para_arquivo(unidades[0]) or NOME_SEM_UNIDADE
    else:
        unidade = NOME_SEM_UNIDADE
    return f"{prefixo}_{competencia or NOME_SEM_COMPETENCIA}_{unidade}_{agora:%Hh%M}.xlsx"


def caminho_do_relatorio(pasta: Path, competencia: str, unidades: list[str],
                         agora: datetime, prefixo: str = PREFIXO_ARQUIVO) -> Path:
    """Caminho livre na pasta: se o nome já existe, acrescenta _2, _3..."""
    original = Path(pasta) / nome_do_relatorio(competencia, unidades, agora, prefixo)
    caminho = original
    contador = 2
    while caminho.exists():
        caminho = original.with_name(f"{original.stem}_{contador}{original.suffix}")
        contador += 1
    return caminho
