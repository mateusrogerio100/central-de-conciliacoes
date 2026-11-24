"""Leitor: Caixa Econômica Federal — extrato de conta corrente por período.

    Conta: 4282 | 1292 | 000568630703-9
    ...
    Data Mov. Nr. Doc. Histórico Valor Saldo
    19/08/2026 191001 ENVIO TEV 539.300,00 D 93,56 C
    19/08/2026 000000 SALDO DIA 0,00 C 93,56 C      <- última linha: saldo 93,56 C

O logo "GERENCIADOR CAIXA" é imagem e sai embaralhado no texto, por isso o
reconhecimento usa o rodapé ("SAC CAIXA" ou o endereço gerenciador.caixa).
"""

import re
from datetime import date
from pathlib import Path

from ..modelos import SaldoExtraido
from ..util import PADRAO_VALOR_CD, converter_valor, normalizar_conta
from .base import (LeitorBase, LeituraError, buscar, buscar_ultimo,
                   conferir_mes_referencia)


class LeitorCEFContaCorrente(LeitorBase):
    nome = "CEF - Conta corrente"
    banco = "CEF"

    def reconhece(self, texto: str) -> bool:
        return "Extrato por período" in texto and (
            "SAC CAIXA" in texto or "gerenciador.caixa" in texto)

    def ler(self, texto: str, arquivo: Path, competencia: date) -> list[SaldoExtraido]:
        # "Mês: Agosto/2026"
        conferir_mes_referencia(r"Mês:\s*(\w+)/(\d{4})", texto, competencia)
        conta = buscar(r"Conta:\s*[\d\s|]*?\|\s*(\d[\d.]*-[0-9Xx])\b", texto,
                       "número da conta").group(1)

        # Linha de lançamento: começa com data. Cada uma traz Valor e Saldo,
        # ambos com C/D; o saldo é o último valor da linha.
        ultima = buscar_ultimo(r"^\d{2}/\d{2}/\d{4}\s.*$", texto,
                               "linha de lançamento", re.MULTILINE).group(0)
        valores = re.findall(PADRAO_VALOR_CD, ultima)
        if len(valores) < 2:
            raise LeituraError(f"coluna Saldo não encontrada na última linha: {ultima!r}")

        return [SaldoExtraido(
            banco=self.banco,
            tipo="CC",
            conta=normalizar_conta(conta),
            conta_original=conta,
            saldo_total=converter_valor(valores[-1]),
            arquivo=arquivo,
            modelo=self.nome,
        )]
