"""Planilha de configuração da EST-02 (ESPECIFICACAO_ESTOQUE.md, seção 3.6).

TODA leitura da configuração passa por carregar_configuracao_estoque(): nenhum outro arquivo
lê a planilha. Motivo: na futura versão web, a configuração vai para um banco de dados e só
esta função deve mudar.

Onde fica:
- cópia de fábrica: modulos/conciliacao_estoque/recursos/ (dentro do .exe, com --add-data);
- versão do usuário: %APPDATA%\\CentralConciliacoes\\configuracoes\\. Se ela existir, é a que vale.
O botão "Editar configuração" usa preparar_configuracao_do_usuario(): copia a de fábrica para
a pasta do usuário (se ainda não houver) e devolve o caminho para a tela abrir no Excel.

Colunas localizadas pelo título, nunca pela letra.
"""

from __future__ import annotations

import io
import os
import shutil
import zipfile
from pathlib import Path

import openpyxl

from central.caminhos import caminho_interno
from modulos.conciliacao_estoque import configuracao
from modulos.conciliacao_estoque.modelos import (
    Aviso,
    ConfiguracaoEST02,
    ErroArquivo,
    GrupoSCF,
    Gravidade,
    ItemOperacao,
    ParIgual,
)
from modulos.conciliacao_estoque.utilitarios import normalizar_texto, texto_igual


def caminho_fabrica() -> Path:
    return caminho_interno(*configuracao.EST02_PASTA_FABRICA, configuracao.EST02_NOME_ARQUIVO)


def pasta_usuario() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / configuracao.PASTA_DADOS_USUARIO / configuracao.EST02_SUBPASTA_USUARIO


def caminho_usuario(pasta: Path | None = None) -> Path:
    return Path(pasta or pasta_usuario()) / configuracao.EST02_NOME_ARQUIVO


def preparar_configuracao_do_usuario(pasta: Path | None = None, fabrica: Path | None = None) -> Path:
    """Garante a versão do usuário (copiando a de fábrica, se não existir) e devolve o caminho dela."""
    destino = caminho_usuario(pasta)
    if not destino.exists():
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(fabrica or caminho_fabrica(), destino)
    return destino


def carregar_configuracao_estoque(pasta: Path | None = None, fabrica: Path | None = None) -> ConfiguracaoEST02:
    """Lê a configuração do usuário, ou a de fábrica se a do usuário não existir, e confere."""
    do_usuario = caminho_usuario(pasta)
    caminho = do_usuario if do_usuario.exists() else Path(fabrica or caminho_fabrica())
    config = ConfiguracaoEST02(caminho=str(caminho), de_fabrica=caminho != do_usuario)
    pasta_trabalho = _abrir(caminho)
    try:
        abas = {normalizar_texto(nome): pasta_trabalho[nome] for nome in pasta_trabalho.sheetnames}

        def aba(nome):
            encontrada = abas.get(normalizar_texto(nome))
            if encontrada is None:
                _avisar(config, Gravidade.ERRO, "aba não encontrada", f"Aba '{nome}' não encontrada.")
            return encontrada

        aba_grupos, aba_itens, aba_pares = (aba(configuracao.EST02_ABA_GRUPOS), aba(configuracao.EST02_ABA_ITENS),
                                            aba(configuracao.EST02_ABA_PARES))
        if aba_grupos is not None:
            _ler_grupos(config, aba_grupos)
        if aba_itens is not None:
            _ler_itens(config, aba_itens)
        if aba_pares is not None:
            _ler_pares(config, aba_pares)
    finally:
        pasta_trabalho.close()
    return config


def _abrir(caminho: Path):
    try:
        conteudo = io.BytesIO(caminho.read_bytes())
    except FileNotFoundError:
        raise ErroArquivo(f"{caminho.name}: arquivo de configuração não encontrado ({caminho}).")
    except PermissionError:
        raise ErroArquivo(f"{caminho.name}: o arquivo está aberto em outro programa (feche o Excel e tente de novo).")
    try:
        return openpyxl.load_workbook(conteudo, read_only=True, data_only=True)
    except (zipfile.BadZipFile, KeyError, OSError) as erro:
        raise ErroArquivo(f"{caminho.name}: não foi possível abrir a configuração ({erro}).")


def _avisar(config, gravidade, tipo, mensagem, linha=None, conta=""):
    config.avisos.append(Aviso(gravidade, tipo, mensagem, arquivo=Path(config.caminho).name, linha=linha, conta=conta))


def _linhas_com_titulos(config, aba, titulos: tuple[str, ...]):
    """Acha a linha de títulos e devolve (número da linha, {título: valor}) para cada linha preenchida."""
    linhas = list(aba.iter_rows(values_only=True))
    for indice, linha in enumerate(linhas):
        colunas = {}
        for titulo in titulos:
            colunas[titulo] = next((i for i, v in enumerate(linha) if texto_igual(v, titulo)), None)
        if all(c is not None for c in colunas.values()):
            for numero, dados in enumerate(linhas[indice + 1:], start=indice + 2):
                valores = {t: _limpar(dados[c] if c < len(dados) else None) for t, c in colunas.items()}
                if any(v is not None for v in valores.values()):
                    yield numero, valores
            return
    faltando = ", ".join(titulos)
    _avisar(config, Gravidade.ERRO, "títulos não encontrados",
            f"Aba '{aba.title}': linha de títulos ({faltando}) não encontrada.")


def _limpar(valor):
    if isinstance(valor, str):
        valor = valor.strip()
        return valor or None
    return valor


def _inteiro(valor) -> int | None:
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float) and valor.is_integer():
        return int(valor)
    if isinstance(valor, str) and valor.isdigit():
        return int(valor)
    return None


def _ler_grupos(config, aba):
    titulo_grupo, titulo_tipo, titulo_posicao = configuracao.EST02_TITULOS_GRUPOS
    tipos = (configuracao.EST02_TIPO_ENTRADA, configuracao.EST02_TIPO_SAIDA)
    for linha, valores in _linhas_com_titulos(config, aba, configuracao.EST02_TITULOS_GRUPOS):
        nome, tipo, posicao = valores[titulo_grupo], valores[titulo_tipo], _inteiro(valores[titulo_posicao])
        tipo = next((t for t in tipos if texto_igual(tipo, t)), None)
        if nome is None or tipo is None or posicao is None:
            _avisar(config, Gravidade.ERRO, "grupo inválido",
                    f"Aba Grupos, linha {linha}: preencha o grupo, o tipo (Entrada ou Saída) e a posição no SCF.", linha)
            continue
        if not 1 < posicao < len(configuracao.SCF_TITULOS) or posicao in configuracao.EST02_POSICOES_CALCULADAS:
            _avisar(config, Gravidade.ERRO, "grupo inválido",
                    f"Aba Grupos, linha {linha}: posição {posicao} do grupo {nome} não é uma coluna de grupo do SCF.",
                    linha)
            continue
        if config.grupo(str(nome)) is not None:
            _avisar(config, Gravidade.ERRO, "grupo repetido", f"Aba Grupos: grupo {nome} repetido (linha {linha}).", linha)
            continue
        config.grupos.append(GrupoSCF(nome=str(nome), tipo=tipo, posicao=posicao))


def _ler_itens(config, aba):
    titulo_codigo, titulo_nome, titulo_es, titulo_tipo, titulo_grupo = configuracao.EST02_TITULOS_ITENS
    for linha, valores in _linhas_com_titulos(config, aba, configuracao.EST02_TITULOS_ITENS):
        codigo = _inteiro(valores[titulo_codigo])
        nome = str(valores[titulo_nome] or "")
        if codigo is None:
            _avisar(config, Gravidade.ERRO, "código inválido",
                    f"Aba Itens, linha {linha}: código vazio ou não numérico ({valores[titulo_codigo]!r}).", linha)
            continue
        if codigo in config.itens:
            _avisar(config, Gravidade.ERRO, "código repetido",
                    f"Aba Itens: operação {codigo} aparece nas linhas {config.itens[codigo].linha} e {linha}. "
                    "Cada código só pode aparecer uma vez.", linha, str(codigo))
            continue
        grupo_nome = valores[titulo_grupo]
        grupo = config.grupo(str(grupo_nome)) if grupo_nome is not None else None
        if grupo is None:
            _avisar(config, Gravidade.ERRO, "grupo inexistente",
                    f"Aba Itens, linha {linha}: operação {codigo} com grupo {grupo_nome!r}, que não está na aba Grupos.",
                    linha, str(codigo))
            continue
        es = str(valores[titulo_es] or "").upper()
        item = ItemOperacao(codigo, nome, es, str(valores[titulo_tipo] or ""), grupo.nome, linha)
        config.itens[codigo] = item
        if es and es != configuracao.EST02_ES_DO_TIPO[grupo.tipo]:
            _avisar(config, Gravidade.INFO, "E/S diferente do grupo",
                    f"Operação {codigo} {nome}: marcada '{es}' no Tasy, mas está em {grupo.nome} "
                    f"({grupo.tipo.lower()}). Vale o grupo.", linha, str(codigo))


def _ler_pares(config, aba):
    titulo_a, titulo_nome_a, titulo_b, titulo_nome_b, titulo_obs = configuracao.EST02_TITULOS_PARES
    for linha, valores in _linhas_com_titulos(config, aba, configuracao.EST02_TITULOS_PARES):
        a, b = _inteiro(valores[titulo_a]), _inteiro(valores[titulo_b])
        if a is None or b is None:
            _avisar(config, Gravidade.ERRO, "par inválido",
                    f"Aba Pares iguais, linha {linha}: preencha as duas operações com o código numérico.", linha)
            continue
        if a == b:
            _avisar(config, Gravidade.ERRO, "par inválido",
                    f"Aba Pares iguais, linha {linha}: a mesma operação ({a}) dos dois lados.", linha)
            continue
        fora = [c for c in (a, b) if c not in config.itens]
        if fora:
            _avisar(config, Gravidade.ERRO, "par inválido",
                    f"Aba Pares iguais, linha {linha}: operação {', '.join(map(str, fora))} não está na aba Itens.", linha)
            continue
        config.pares.append(ParIgual(
            a, str(valores[titulo_nome_a] or config.itens[a].nome),
            b, str(valores[titulo_nome_b] or config.itens[b].nome),
            str(valores[titulo_obs] or ""), linha,
        ))
