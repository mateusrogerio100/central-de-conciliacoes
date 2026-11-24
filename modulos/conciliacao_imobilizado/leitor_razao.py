"""
Leitor do Razão auxiliar do patrimônio (Tasy 6051, "Patrimônio - Razão auxiliar (NOVO)").

Formato (texto separado por tabulação, ver leitor_texto):
- "Data referência" → a data ao lado (01/08/2026) dá o mês.
- Cada conta começa com uma linha "11038 - Aparelhos de informática AME" e segue com os
  rótulos "Saldo anterior", "Entradas", "Baixas", "Transf bem (entrada)",
  "Transf bem (saída)" e "Saldo atual", cada um com o valor na próxima célula preenchida.
- O título de uma conta pode ficar no fim de uma página e os valores no começo da seguinte
  (com as colunas deslocadas): por isso os valores são achados pelo rótulo.
- "Total Geral" encerra as contas (os valores dele são ignorados).
"""

from __future__ import annotations

import re
from pathlib import Path

from modulos.conciliacao_imobilizado.base_iss import Aviso
from modulos.conciliacao_imobilizado.leitor_texto import (
    RELATORIO_RAZAO,
    ArquivoIlegivel,
    data,
    depois_do_rotulo,
    erro_relatorio_errado,
    identificar_relatorio,
    juntar_espacos,
    ler_linhas,
    preenchidas,
    valor,
)
from modulos.conciliacao_imobilizado.modelos import ContaPatrimonio, LeituraRazao

ROTULO_DATA_REFERENCIA = "Data referência"
ROTULO_TOTAL_GERAL = "Total Geral"

# rótulo no relatório → campo de ContaPatrimonio
ROTULOS_VALORES = {
    "saldo anterior": "saldo_anterior",
    "entradas": "entradas",
    "baixas": "baixas",
    "transf bem (entrada)": "transf_entrada",
    "transf bem (saída)": "transf_saida",
    "saldo atual": "saldo_atual",
}
CAMPOS_OBRIGATORIOS = ("saldo_atual",)

_REGEX_CONTA = re.compile(r"^(\d+)\s+-\s+(.+)$")


def ler_razao(caminho: Path) -> LeituraRazao:
    caminho = Path(caminho)
    leitura = LeituraRazao(arquivo=caminho.name)
    try:
        linhas = ler_linhas(caminho)
    except ArquivoIlegivel as erro:
        leitura.erro = str(erro)
        return leitura

    erro = erro_relatorio_errado(RELATORIO_RAZAO, identificar_relatorio(linhas))
    if erro:
        leitura.erro = erro
        return leitura

    atual: ContaPatrimonio | None = None
    no_total_geral = False
    vistas: dict[str, ContaPatrimonio] = {}

    for numero, linha in enumerate(linhas, start=1):
        celulas = preenchidas(linha)
        if not celulas:
            continue

        if leitura.data_referencia is None:
            texto_data = depois_do_rotulo(linha, ROTULO_DATA_REFERENCIA)
            if texto_data:
                leitura.data_referencia = data(texto_data)

        if len(celulas) == 1:
            if celulas[0].casefold() == ROTULO_TOTAL_GERAL.casefold():
                atual, no_total_geral = None, True
                continue
            encontrado = _REGEX_CONTA.match(celulas[0])
            if encontrado:
                codigo, nome = encontrado.group(1), juntar_espacos(encontrado.group(2))
                atual = ContaPatrimonio(codigo=codigo, nome=nome, linha=numero)
                no_total_geral = False
                if codigo in vistas:
                    leitura.avisos.append(Aviso(
                        arquivo=leitura.arquivo,
                        mensagem=f"A conta {codigo} aparece mais de uma vez no patrimônio; "
                                 "foi usada só a primeira.",
                    ))
                    atual = None
                    continue
                vistas[codigo] = atual
                leitura.contas.append(atual)
                continue

        for posicao, celula in enumerate(linha):
            campo = ROTULOS_VALORES.get(juntar_espacos(celula).casefold())
            if campo is None:
                continue
            texto = next((c for c in linha[posicao + 1:] if c), "")
            if no_total_geral:
                continue
            if atual is None:
                leitura.avisos.append(Aviso(
                    arquivo=leitura.arquivo,
                    mensagem=f"Linha {numero}: \"{celula}\" sem conta antes; valor ignorado.",
                ))
                continue
            try:
                setattr(atual, campo, valor(texto))
            except ValueError:
                leitura.avisos.append(Aviso(
                    arquivo=leitura.arquivo,
                    mensagem=f"Linha {numero}: valor de \"{celula}\" da conta {atual.codigo} "
                             f"não reconhecido ({texto!r}).",
                ))

    # Conta sem Saldo atual não tem o que comparar: sai da lista com aviso.
    completas = []
    for conta in leitura.contas:
        faltando = [c for c in CAMPOS_OBRIGATORIOS if getattr(conta, c) is None]
        if faltando:
            leitura.avisos.append(Aviso(
                arquivo=leitura.arquivo,
                mensagem=f"A conta {conta.codigo} - {conta.nome} está sem \"Saldo atual\" no "
                         "patrimônio; ela não foi comparada.",
            ))
        else:
            completas.append(conta)
    leitura.contas = completas

    if not leitura.contas:
        leitura.erro = "Nenhuma conta encontrada no Razão auxiliar do patrimônio."
    return leitura
