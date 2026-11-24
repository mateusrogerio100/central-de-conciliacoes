"""Leitor: Banco do Brasil — Investimentos Fundos (extrato mensal).

O PDF traz vários fundos, cada um com seu bloco:

    RF Ref DI Plus Ágil - CNPJ: 5.943.661/0001-74      <- nome do fundo
    ...
    31/08/2026 Saldo Atual 101.343,70 ...              <- linha da tabela: NÃO usar
    Resumo do mês
    ...
    Saldo Atual = 101.343,70                           <- este (com "=")

O saldo da conta é a soma dos "Saldo Atual = ..." de todos os fundos.
"""

import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from ..modelos import SaldoExtraido
from ..util import PADRAO_VALOR, converter_valor, formatar_valor, normalizar_conta
from .base import LeitorBase, LeituraError, buscar, conferir_mes_referencia

_NOME_FUNDO = re.compile(r"^(.+?)\s+-\s+CNPJ:", re.MULTILINE)
_SALDO_FUNDO = re.compile(rf"Saldo Atual\s*=\s*({PADRAO_VALOR})")
_SEM_MOVIMENTO = "NÃO HOUVE MOVIMENTO NO PERÍODO SOLICITADO"


class LeitorBBFundos(LeitorBase):
    nome = "BB - Fundos"
    banco = "BB"

    def reconhece(self, texto: str) -> bool:
        return "Investimentos Fundos" in texto

    def ler(self, texto: str, arquivo: Path, competencia: date) -> list[SaldoExtraido]:
        # "Mês/ano referência AGOSTO/2026"
        conferir_mes_referencia(r"Mês/ano referência\s+(\w+)/(\d{4})", texto, competencia)
        conta = buscar(r"\bConta\s+(\d[\d.]*-[0-9Xx])\b", texto, "número da conta").group(1)

        nomes = [n.strip() for n in _NOME_FUNDO.findall(texto)]
        saldos = [converter_valor(v) for v in _SALDO_FUNDO.findall(texto)]
        if not saldos and not nomes and _SEM_MOVIMENTO in texto:
            # O banco não lista nenhum fundo. "Não houve movimento" não garante
            # que o saldo seja zero, por isso o usuário é avisado para conferir.
            return [SaldoExtraido(
                banco=self.banco,
                tipo="APLICACAO",
                conta=normalizar_conta(conta),
                conta_original=conta,
                saldo_total=Decimal("0"),
                arquivo=arquivo,
                modelo=self.nome,
                observacao="extrato sem movimento no período e sem fundos listados: "
                           "conferir se há saldo em fundos",
            )]
        if not saldos:
            raise LeituraError("nenhuma linha 'Saldo Atual = ...' encontrada")
        # Cada fundo tem um nome e um "Saldo Atual ="; se a contagem não
        # bater, algum bloco saiu diferente e é melhor parar do que somar errado.
        if len(nomes) != len(saldos):
            raise LeituraError(
                f"{len(nomes)} fundo(s) encontrado(s), mas {len(saldos)} "
                f"linha(s) 'Saldo Atual ='"
            )

        detalhe = "; ".join(f"{n}: {formatar_valor(s)}" for n, s in zip(nomes, saldos))
        return [SaldoExtraido(
            banco=self.banco,
            tipo="APLICACAO",
            conta=normalizar_conta(conta),
            conta_original=conta,
            saldo_total=sum(saldos, Decimal("0")),
            arquivo=arquivo,
            modelo=self.nome,
            observacao=detalhe,
        )]
