"""Leitor: Banco do Brasil — BB Rende Fácil.

    Agência Conta
    5113-6 534-7                                <- rótulo e número em linhas diferentes
    ...
    Saldo bruto em 31/07/2026 R$ 299,12         <- mês anterior
    Saldo bruto em 31/08/2026: R$ 228,18        <- mês de competência: este é o saldo
"""

import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from ..modelos import SaldoExtraido
from ..util import PADRAO_VALOR, converter_valor, normalizar_conta
from .base import LeitorBase, LeituraError, buscar, conferir_mes_referencia

_SALDO_BRUTO = re.compile(
    rf"Saldo bruto em\s+(\d{{2}}/\d{{2}}/\d{{4}}):?\s*R\$\s*({PADRAO_VALOR})"
)
# Aplicação zerada: "Saldo bruto em : R$ 0,00" (o banco não imprime a data).
_SALDO_BRUTO_SEM_DATA = re.compile(r"Saldo bruto em\s*:\s*R\$\s*0,00")


class LeitorBBRendeFacil(LeitorBase):
    nome = "BB - Rende Fácil"
    banco = "BB"

    def reconhece(self, texto: str) -> bool:
        return "BB RENDE FÁCIL" in texto

    def ler(self, texto: str, arquivo: Path, competencia: date) -> list[SaldoExtraido]:
        # "Resumo do mês - Agosto/2026"
        conferir_mes_referencia(r"Resumo do mês\s*-\s*(\w+)/(\d{4})", texto, competencia)
        # "Agência" e "Conta" como rótulos; os números (agência e conta) vêm
        # em seguida, na mesma linha ou na de baixo. A conta é o segundo.
        conta = buscar(
            r"Agência\s+Conta\s+\d[\d.]*-[0-9Xx]\s+(\d[\d.]*-[0-9Xx])\b",
            texto, "número da conta",
        ).group(1)

        do_mes = []
        for achado in _SALDO_BRUTO.finditer(texto):
            data = datetime.strptime(achado.group(1), "%d/%m/%Y").date()
            if (data.year, data.month) == (competencia.year, competencia.month):
                do_mes.append((data, achado.group(2)))
        observacao = ""
        if do_mes:
            saldo = converter_valor(max(do_mes)[1])
        elif self._tudo_zerado(texto):
            # Aplicação zerada: o banco omite a data ("Saldo bruto em : R$ 0,00")
            # e todos os valores do extrato são R$ 0,00.
            saldo = Decimal("0")
            observacao = "aplicação zerada: todos os valores do extrato são R$ 0,00"
        else:
            raise LeituraError(
                f"'Saldo bruto em' do mês de competência ({competencia:%m/%Y}) não encontrado"
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

    def _tudo_zerado(self, texto: str) -> bool:
        valores = [converter_valor(v) for v in re.findall(rf"R\$\s*({PADRAO_VALOR})", texto)]
        return bool(_SALDO_BRUTO_SEM_DATA.search(texto)) and bool(valores) and not any(valores)
