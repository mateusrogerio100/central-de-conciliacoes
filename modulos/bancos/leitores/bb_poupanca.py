"""Leitor: Banco do Brasil — extrato de Poupança.

    Agência / Conta 5113-6 / 1179-7
    ...
    Saldo atual 0,00 C          <- NÃO usar (vem zerado)
    Saldo bloqueado 0,00 D
    Saldo total 223.374,00 C    <- este é o saldo

Período: começa no mês de competência e termina no último dia dele ou no dia 1 do mês seguinte
(decisão do usuário, 06/11/2026: o BB tira a poupança "01/10 a 01/11"; o Saldo total, com os juros
do aniversário lançados no começo de novembro, é o que bate com o balancete). Outro fim: erro.
"""

from datetime import date, timedelta
from pathlib import Path

from ..modelos import SaldoExtraido
from ..util import PADRAO_VALOR_CD, converter_valor, normalizar_conta
from .base import DATA, LeitorBase, LeituraError, buscar, buscar_ultimo, ler_data


class LeitorBBPoupanca(LeitorBase):
    nome = "BB - Poupança"
    banco = "BB"

    def reconhece(self, texto: str) -> bool:
        return "Extratos - Poupança" in texto

    def ler(self, texto: str, arquivo: Path, competencia: date) -> list[SaldoExtraido]:
        fim = _conferir_periodo(texto, competencia)
        conta = buscar(r"Agência\s*/\s*Conta\s+\S+\s*/\s*(\d[\d.]*-[0-9Xx])\b", texto,
                       "número da conta").group(1)
        total = buscar_ultimo(rf"Saldo total\s+({PADRAO_VALOR_CD})", texto,
                              "linha 'Saldo total'").group(1)
        bloqueado = buscar_ultimo(rf"Saldo bloqueado\s+({PADRAO_VALOR_CD})", texto,
                                  "linha 'Saldo bloqueado'").group(1)

        # O extrato mostra o bloqueado com "D"; o que interessa é o valor.
        valor_bloqueado = abs(converter_valor(bloqueado))
        observacoes = []
        if fim.month != competencia.month:
            observacoes.append(f"extrato vai até {fim:%d/%m/%Y}: usado o Saldo total")
        if valor_bloqueado:
            observacoes.append("verificar se o saldo total já inclui o bloqueado")
        observacao = "; ".join(observacoes)

        return [SaldoExtraido(
            banco=self.banco,
            tipo="POUPANCA",
            conta=normalizar_conta(conta),
            conta_original=conta,
            saldo_total=converter_valor(total),
            saldo_bloqueado=valor_bloqueado,
            arquivo=arquivo,
            modelo=self.nome,
            observacao=observacao,
        )]


def _conferir_periodo(texto: str, competencia: date) -> date:
    """Início no mês de competência; fim no mesmo mês ou no dia 1 do mês seguinte. Devolve o fim."""
    achado = buscar(rf"Período\s+{DATA}\s+a\s+{DATA}", texto, "período do extrato")
    inicio, fim = ler_data(achado.group(1)), ler_data(achado.group(2))
    mes = (competencia.year, competencia.month)
    primeiro_do_seguinte = (date(*mes, 28) + timedelta(days=4)).replace(day=1)
    if (inicio.year, inicio.month) != mes or ((fim.year, fim.month) != mes and fim != primeiro_do_seguinte):
        raise LeituraError(
            f"extrato de outro período ({inicio:%d/%m/%Y} a {fim:%d/%m/%Y}); "
            f"competência {competencia:%m/%Y}"
        )
    return fim
