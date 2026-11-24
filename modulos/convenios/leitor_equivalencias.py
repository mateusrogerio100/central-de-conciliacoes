"""Leitura do equivalencias.csv (nome no razão -> linha da planilha). Seção 3.3 da especificação.

- Fica na pasta `config` ao lado da planilha de receitas; o usuário edita (sem .exe novo).
- Sem o arquivo: vale o modelo de fábrica, que é vazio (o preenchido tem nomes reais e fica fora do git),
  com aviso em vermelho.
- Coluna faltando = o arquivo inteiro vira erro. Linha com problema = só ela é pulada, com aviso.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from central.caminhos import caminho_interno
from modulos.convenios import configuracao as cfg
from modulos.convenios.modelos import Aviso, Equivalencia, Equivalencias, ErroLeitura


def caminho_fabrica() -> Path:
    return caminho_interno(*cfg.EQUIVALENCIAS_FABRICA)


def pasta_sugerida(planilha: Path) -> Path | None:
    """A pasta `config` ao lado da planilha, se tiver o equivalencias.csv (a tela preenche sozinha)."""
    pasta = Path(planilha).parent / cfg.PASTA_CONFIG
    return pasta if (pasta / cfg.ARQUIVO_EQUIVALENCIAS).is_file() else None


def _texto(caminho: Path) -> str:
    try:
        conteudo = caminho.read_bytes()
    except OSError as erro:
        raise ErroLeitura(f"Não foi possível abrir {caminho.name}: {erro}") from None
    for codificacao in cfg.CSV_CODIFICACOES:
        try:
            return conteudo.decode(codificacao)
        except UnicodeDecodeError:
            continue
    raise ErroLeitura(f"{caminho.name}: codificação não reconhecida.")


def _interpretar(caminho: Path, de_fabrica: bool) -> Equivalencias:
    resultado = Equivalencias(str(caminho), de_fabrica)
    leitor = csv.reader(io.StringIO(_texto(caminho), newline=""), delimiter=cfg.CSV_SEPARADOR)
    try:
        titulos = [t.strip() for t in next(leitor)]
    except StopIteration:
        raise ErroLeitura(f"{caminho.name} está vazio (falta a linha de títulos).") from None
    faltando = [c for c in cfg.EQUIVALENCIAS_COLUNAS if c not in titulos]
    if faltando:
        raise ErroLeitura(f"{caminho.name}: colunas não encontradas: {', '.join(faltando)}.")
    posicao = {c: titulos.index(c) for c in cfg.EQUIVALENCIAS_COLUNAS}
    for valores in leitor:
        if not any(v.strip() for v in valores):
            continue
        campos = {c: valores[i].strip() if i < len(valores) else "" for c, i in posicao.items()}
        nome, linha = campos["Nome_no_razao"], campos["Linha_da_planilha"]
        if not nome or not linha:
            resultado.avisos.append(Aviso(f"{caminho.name} linha {leitor.line_num}",
                                          "Nome_no_razao ou Linha_da_planilha vazio: linha pulada."))
            continue
        resultado.itens.append(Equivalencia(nome, linha, campos["Obs"], leitor.line_num))
    return resultado


def ler_equivalencias(pasta: Path | None) -> Equivalencias:
    """O equivalencias.csv da pasta; sem pasta ou sem o arquivo, o de fábrica (com aviso)."""
    if pasta is not None:
        arquivo = Path(pasta) / cfg.ARQUIVO_EQUIVALENCIAS
        if arquivo.is_file():
            return _interpretar(arquivo, de_fabrica=False)
    resultado = _interpretar(caminho_fabrica(), de_fabrica=True)
    motivo = "nenhuma pasta escolhida" if pasta is None else f"a pasta {pasta} não tem o {cfg.ARQUIVO_EQUIVALENCIAS}"
    resultado.avisos.insert(0, Aviso(cfg.ARQUIVO_EQUIVALENCIAS, f"Sem o {cfg.ARQUIVO_EQUIVALENCIAS} ({motivo}): só os "
                                     "nomes iguais aos da planilha casam; os outros virariam linhas novas. Escolha a "
                                     "pasta config das equivalências.", erro=True))
    return resultado
