"""Leitor: Sicoob — extrato de conta corrente (Sicoobnet).

Seção RESUMO, na última página:

    RESUMO
    Saldo em conta: 4.136,14C                 <- disponível
    ...
    Saldo disponível: 4.136,14C               <- NÃO usar (a regra é "Saldo em conta")
    Saldo bloqueado (cheques): 50,00C*
    Saldo bloqueado (judicial): 0,00C

Regra de negócio confirmada pelo autor: o bloqueado de cheques entra no
saldo contábil. Saldo total = em conta + bloqueado (cheques + judicial).
"""

from datetime import date
from pathlib import Path

from ..modelos import SaldoExtraido
from ..util import PADRAO_VALOR_CD, converter_valor, normalizar_conta
from .base import DATA, LeitorBase, LeituraError, buscar, conferir_periodo

_VALOR = rf"({PADRAO_VALOR_CD}\*?)"


class LeitorSicoobContaCorrente(LeitorBase):
    nome = "Sicoob - Conta corrente"
    banco = "SICOOB"

    def reconhece(self, texto: str) -> bool:
        return "EXTRATO DE CONTA CORRENTE" in texto and "SICOOB" in texto

    def ler(self, texto: str, arquivo: Path, competencia: date) -> list[SaldoExtraido]:
        # "Periodo: 01/08/2026 - 31/08/2026" (sem acento no Sicoob)
        conferir_periodo(rf"Per[ií]odo:\s*{DATA}\s*-\s*{DATA}", texto, competencia)
        conta = buscar(r"Conta:\s*(\d[\d.]*-[0-9Xx])\b", texto, "número da conta").group(1)

        inicio = texto.rfind("RESUMO")
        if inicio < 0:
            raise LeituraError("seção RESUMO não encontrada")
        resumo = texto[inicio:]

        em_conta = converter_valor(
            buscar(rf"Saldo em conta:\s*{_VALOR}", resumo, "'Saldo em conta'").group(1))
        cheques = converter_valor(
            buscar(rf"Saldo bloqueado \(cheques\):\s*{_VALOR}", resumo,
                   "'Saldo bloqueado (cheques)'").group(1))
        judicial = converter_valor(
            buscar(rf"Saldo bloqueado \(judicial\):\s*{_VALOR}", resumo,
                   "'Saldo bloqueado (judicial)'").group(1))

        bloqueado = cheques + judicial
        observacao = ""
        if judicial:
            observacao = "há saldo bloqueado judicial: conferir"

        return [SaldoExtraido(
            banco=self.banco,
            tipo="CC",
            conta=normalizar_conta(conta),
            conta_original=conta,
            saldo_total=em_conta + bloqueado,
            saldo_bloqueado=bloqueado,
            arquivo=arquivo,
            modelo=self.nome,
            observacao=observacao,
        )]
