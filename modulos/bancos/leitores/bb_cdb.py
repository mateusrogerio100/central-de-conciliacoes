"""Leitor: Banco do Brasil — extrato de CDB / RDB.

O "Saldo final / valor capital" NÃO serve: é só o capital, sem os juros.
O saldo usado é a coluna Liquid.proj. da tabela "SALDO NOS ULTIMOS 6
MESES", na última data do mês de competência:

    SALDO NOS ULTIMOS 6 MESES
    Data Capital em ser Juros IR proj. Liquid.proj.
    31/07/2026 8500,00 301,05 0,00 8801,05
    31/08/2026 8500,00 393,49 0,00 8893,49

A tabela pode continuar na página seguinte (com o cabeçalho da página no
meio), por isso as linhas são procuradas em todo o texto após o título.
"""

import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from ..modelos import SaldoExtraido
from ..util import PADRAO_VALOR, converter_valor, normalizar_conta
from .base import DATA, LeitorBase, LeituraError, buscar, conferir_periodo

_TITULO_TABELA = "SALDO NOS ULTIMOS 6 MESES"
_FIM_TABELA = "RESUMO DOS DEPOSITOS"
# Data, Capital em ser, Juros, IR proj., Liquid.proj.
_LINHA_TABELA = re.compile(
    rf"^(\d{{2}}/\d{{2}}/\d{{4}})\s+({PADRAO_VALOR})\s+({PADRAO_VALOR})"
    rf"\s+({PADRAO_VALOR})\s+({PADRAO_VALOR})\s*$",
    re.MULTILINE,
)
# Aplicação zerada: "31/08 Saldo final 0,00" (sem a linha "valor capital").
_SALDO_FINAL_ZERO = re.compile(r"Saldo final\s+0,00\s*$", re.MULTILINE)


class LeitorBBCDB(LeitorBase):
    nome = "BB - CDB"
    banco = "BB"

    def reconhece(self, texto: str) -> bool:
        return "Extratos - CDB / RDB" in texto

    def ler(self, texto: str, arquivo: Path, competencia: date) -> list[SaldoExtraido]:
        conferir_periodo(rf"Período\s+{DATA}\s+a\s+{DATA}", texto, competencia)
        conta = buscar(r"\bConta\s+(\d[\d.]*-[0-9Xx])\b", texto, "número da conta").group(1)

        saldo = Decimal("0")
        observacao = ""
        liquido = self._liquido_do_mes(texto, competencia)
        if liquido is not None:
            saldo = converter_valor(liquido)
        elif _SALDO_FINAL_ZERO.search(texto):
            # Aplicação zerada: o próprio extrato diz "Saldo final 0,00" e a
            # tabela não tem linha do mês (não há mais capital aplicado).
            observacao = "aplicação zerada: extrato com 'Saldo final 0,00'"
        elif texto.find(_TITULO_TABELA) < 0:
            # Caso real: o BB também gera um extrato "resumo" do CDB, só com o
            # capital (sem os juros). O saldo correto só está no extrato completo.
            raise LeituraError("extrato de CDB em formato resumo (sem a tabela de "
                               "saldos); use o extrato completo")
        else:
            raise LeituraError(
                f"tabela '{_TITULO_TABELA}' sem linha do mês de competência "
                f"({competencia:%m/%Y})"
            )

        return [SaldoExtraido(
            banco=self.banco,
            tipo="APLICACAO",
            conta=normalizar_conta(conta),
            conta_original=conta,
            saldo_total=saldo,
            arquivo=arquivo,
            modelo=self.nome,
            observacao=observacao,
        )]

    def _liquido_do_mes(self, texto: str, competencia: date) -> str | None:
        """Liquid.proj. da última linha do mês de competência (ou None)."""
        inicio = texto.find(_TITULO_TABELA)
        if inicio < 0:
            return None
        fim = texto.find(_FIM_TABELA, inicio)
        tabela = texto[inicio:fim if fim >= 0 else len(texto)]

        do_mes = []
        for linha in _LINHA_TABELA.finditer(tabela):
            data = datetime.strptime(linha.group(1), "%d/%m/%Y").date()
            if (data.year, data.month) == (competencia.year, competencia.month):
                do_mes.append((data, linha.group(5)))
        return max(do_mes)[1] if do_mes else None
