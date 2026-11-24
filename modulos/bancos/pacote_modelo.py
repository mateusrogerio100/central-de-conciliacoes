"""Monta o "pacote" de um modelo novo de extrato (Etapa 10).

Quando um PDF fica como MODELO NÃO RECONHECIDO, o autor confere o saldo à
mão e preenche um formulário na janela. Este módulo valida esses dados e
cria uma pasta com tudo o que o Claude Code precisa para criar o leitor
novo (comando /novo-modelo):

    <Salvar em>/modelos_novos/<AAAA-MM>_<nome do PDF>/
        <o PDF>                 cópia do extrato
        texto_extraido.txt      o texto que o programa lê do PDF
        dados.json              os dados conferidos (lido pelo Claude Code)
        PEDIDO.md               os mesmos dados para leitura + o comando pronto
"""

import json
import shutil
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from .modelos import TIPOS
from .util import (converter_valor, extrair_paginas_pdf, formatar_valor,
                   normalizar_conta, texto_com_paginas)

PASTA_PACOTES = "modelos_novos"
BANCOS_CONHECIDOS = ("BB", "CEF", "SANTANDER", "SICOOB")
DESCRICAO_TIPOS = {
    "CC": "conta corrente",
    "APLICACAO": "aplicação",
    "POUPANCA": "poupança",
    "OUTRO": "outro",
}


@dataclass
class DadosModeloNovo:
    """O que o autor preenche no formulário (como texto, do jeito que digitou)."""

    banco: str
    tipo: str
    conta: str
    saldo_total: str
    saldo_bloqueado: str = "0,00"
    observacao: str = ""


def validar(dados: DadosModeloNovo) -> DadosModeloNovo:
    """Confere os dados do formulário e devolve uma cópia arrumada.

    Levanta ValueError com todos os problemas encontrados, um por linha,
    para a janela mostrar de uma vez.
    """
    problemas = []
    banco = dados.banco.strip().upper()
    tipo = dados.tipo.strip().upper()
    conta = dados.conta.strip()
    total = dados.saldo_total.strip()
    bloqueado = dados.saldo_bloqueado.strip() or "0,00"

    if not banco:
        problemas.append("Informe o banco.")
    if tipo not in TIPOS:
        problemas.append(f"Tipo inválido: escolha um de {', '.join(TIPOS)}.")
    if not normalizar_conta(conta):
        problemas.append("Informe o número da conta como aparece no extrato.")
    for rotulo, valor in (("Saldo total", total), ("Saldo bloqueado", bloqueado)):
        try:
            converter_valor(valor)
        except ValueError:
            problemas.append(f"{rotulo} inválido: use o formato 1.234,56.")
    if problemas:
        raise ValueError("\n".join(problemas))

    return DadosModeloNovo(
        banco=banco, tipo=tipo, conta=conta,
        saldo_total=formatar_valor(converter_valor(total)),
        saldo_bloqueado=formatar_valor(converter_valor(bloqueado)),
        observacao=dados.observacao.strip(),
    )


def caminho_do_pacote(pasta_saida: Path, pdf: Path, competencia: date) -> Path:
    """Pasta onde o pacote de um PDF fica: modelos_novos/<AAAA-MM>_<nome do PDF>."""
    return Path(pasta_saida) / PASTA_PACOTES / f"{competencia:%Y-%m}_{Path(pdf).stem.strip()}"


def texto_inicial(pdf: Path, linhas: int = 25) -> str:
    """Primeiras linhas do texto do PDF, para mostrar no formulário."""
    texto = texto_com_paginas(extrair_paginas_pdf(pdf))
    return "\n".join(texto.splitlines()[:linhas])


def criar_pacote(pasta_saida: Path, pdf: Path, competencia: date,
                 dados: DadosModeloNovo, subpasta: str = "") -> Path:
    """Valida os dados, cria (ou substitui) o pacote e devolve a pasta dele.

    Quem chama decide se pode substituir um pacote que já existe (a janela
    pergunta antes).
    """
    dados = validar(dados)
    pdf = Path(pdf)
    pasta = caminho_do_pacote(pasta_saida, pdf, competencia).resolve()
    if pasta.exists():
        shutil.rmtree(pasta)
    pasta.mkdir(parents=True)

    shutil.copy2(pdf, pasta / pdf.name)
    (pasta / "texto_extraido.txt").write_text(
        texto_com_paginas(extrair_paginas_pdf(pdf)), encoding="utf-8")

    informacoes = {
        "versao": 1,
        "competencia": f"{competencia:%Y-%m}",
        "arquivo": pdf.name,
        "subpasta_de_origem": subpasta,
        "banco": dados.banco,
        "tipo": dados.tipo,
        "conta": dados.conta,
        "conta_normalizada": normalizar_conta(dados.conta),
        "saldo_total": dados.saldo_total,
        "saldo_bloqueado": dados.saldo_bloqueado,
        # Também como número com ponto decimal, sem perder centavos (texto, não float).
        "saldo_total_decimal": str(converter_valor(dados.saldo_total)),
        "saldo_bloqueado_decimal": str(converter_valor(dados.saldo_bloqueado)),
        "observacao": dados.observacao,
        "criado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }
    (pasta / "dados.json").write_text(
        json.dumps(informacoes, ensure_ascii=False, indent=2), encoding="utf-8")
    (pasta / "PEDIDO.md").write_text(_texto_pedido(pasta, informacoes), encoding="utf-8")
    return pasta


def _texto_pedido(pasta: Path, info: dict) -> str:
    banco_novo = "" if info["banco"] in BANCOS_CONHECIDOS else " (banco novo)"
    linhas = [
        f"# Modelo novo de extrato: {info['arquivo']}",
        "",
        "Dados conferidos manualmente pelo autor:",
        "",
        f"- **Competência:** {info['competencia'][5:]}/{info['competencia'][:4]}",
        f"- **Banco:** {info['banco']}{banco_novo}",
        f"- **Tipo:** {info['tipo']} ({DESCRICAO_TIPOS.get(info['tipo'], '')})",
        f"- **Conta (como no extrato):** {info['conta']}",
        f"- **Saldo total no fim do mês:** R$ {info['saldo_total']}",
        f"- **Saldo bloqueado:** R$ {info['saldo_bloqueado']}",
    ]
    if info["subpasta_de_origem"]:
        linhas.append(f"- **Subpasta de origem:** {info['subpasta_de_origem']}")
    if info["observacao"]:
        linhas.append(f"- **Observação:** {info['observacao']}")
    linhas += [
        "",
        "## Para criar o leitor",
        "",
        "No Claude Code, dentro da pasta do projeto, digite:",
        "",
        "```",
        f'/novo-modelo "{pasta}"',
        "```",
        "",
        "O texto que o programa lê do PDF está em `texto_extraido.txt`.",
        "",
    ]
    return "\n".join(linhas)


def descrever(dados: DadosModeloNovo) -> str:
    """Resumo de uma linha dos dados (para o log da janela)."""
    return (f"{dados.banco} {dados.tipo} conta {dados.conta}: "
            f"saldo R$ {dados.saldo_total}")
