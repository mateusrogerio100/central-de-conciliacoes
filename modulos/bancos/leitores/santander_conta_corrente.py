"""Leitor: Santander — extrato de conta corrente (Internet Banking Empresarial).

    ... Agência: 3431 Conta: 130030239
    Período: 01/08/2026 a 31/08/2026 Data/Hora: 07/09/2026 às 20:51h
    Data Histórico Documento Valor Saldo
    06/08/2026 SALDO ANTERIOR 000000 0,00
    ...
    31/08/2026 025860 -61.804,00 17.641,34     <- último saldo do período: ESTE
    A - Saldo de Conta Corrente 23.627,15      <- NÃO usar
    B - Saldo Bloqueado 0,00
    D - Saldo em Investimentos com Resgate Automático 310,72   <- NÃO usar

ATENÇÃO: o quadro-resumo A–E do fim do extrato mostra o saldo na DATA DE
EMISSÃO do PDF, não no fim do período (conferido em julho e agosto/2026:
a linha A divergia do balancete; o último saldo da lista batia). Por isso:
  - o saldo da conta corrente é a coluna Saldo da última linha de lançamento
    que a tenha preenchida (ou a linha "SALDO ANTERIOR", se não houve
    movimento);
  - o item D (ContaMax) não é usado: o saldo da aplicação vem do extrato
    ContaMax, que traz o saldo mês a mês.
Valores negativos aparecem com sinal de menos ("-40,00").

Extrato que passa do fim do mês (ajuste de 04/11/2026; ex.: "01/10/2026 a 01/11/2026"):
como no BB, o saldo é o da última linha com data até o fim do mês; as linhas do mês seguinte
não contam. O início do período tem que ser no mês de competência.
"""

import calendar
import re
from datetime import date
from pathlib import Path

from ..modelos import SaldoExtraido
from ..util import PADRAO_VALOR, converter_valor, normalizar_conta
from .base import DATA, LeitorBase, LeituraError, buscar, ler_data

_VALOR = rf"(?:-\s?)?{PADRAO_VALOR}"
_LINHA_COM_DATA = re.compile(r"^(\d{2}/\d{2}/\d{4})\s.*$", re.MULTILINE)


class LeitorSantanderContaCorrente(LeitorBase):
    nome = "Santander - Conta corrente"
    banco = "SANTANDER"

    def reconhece(self, texto: str) -> bool:
        return "Conta Corrente > Extrato" in texto and "Internet Banking Empresarial" in texto

    def ler(self, texto: str, arquivo: Path, competencia: date) -> list[SaldoExtraido]:
        fim_do_mes = competencia.replace(
            day=calendar.monthrange(competencia.year, competencia.month)[1])
        fim_do_extrato = self._conferir_periodo(texto, competencia)
        conta = buscar(r"Conta:\s*(\d[\d.\-]*[0-9Xx])\b", texto, "número da conta").group(1)

        saldo = None
        for linha in _LINHA_COM_DATA.finditer(texto):
            if ler_data(linha.group(1)) > fim_do_mes:
                continue
            valores = re.findall(_VALOR, linha.group(0))
            # Linha com Valor e Saldo (dois valores), ou o SALDO ANTERIOR (só o saldo).
            if len(valores) >= 2 or ("SALDO ANTERIOR" in linha.group(0) and valores):
                saldo = valores[-1]
        if saldo is None:
            raise LeituraError("nenhuma linha de lançamento com a coluna Saldo preenchida")

        # O bloqueado só existe no quadro-resumo (data de emissão do PDF).
        observacoes = []
        if fim_do_extrato > fim_do_mes:
            observacoes.append(f"extrato vai até {fim_do_extrato:%d/%m/%Y}: usado o saldo "
                               f"da última linha até {fim_do_mes:%d/%m/%Y}")
        achado = re.search(rf"B - Saldo Bloqueado\s+({_VALOR})", texto)
        if achado and converter_valor(achado.group(1)):
            observacoes.append(f"quadro-resumo mostra saldo bloqueado de {achado.group(1)} "
                               "na data de emissão do extrato: conferir")
        observacao = "; ".join(observacoes)

        return [SaldoExtraido(
            banco=self.banco,
            tipo="CC",
            conta=normalizar_conta(conta),
            conta_original=conta,
            saldo_total=converter_valor(saldo),
            arquivo=arquivo,
            modelo=self.nome,
            observacao=observacao,
        )]

    def _conferir_periodo(self, texto: str, competencia: date) -> date:
        """Confere o período e devolve a data final do extrato.

        O início tem que ser no mês de competência; o fim pode passar do mês (aí o saldo é
        lido até o último dia do mês).
        """
        achado = buscar(rf"Período:\s*{DATA}\s+a\s+{DATA}", texto, "período do extrato")
        inicio, fim = ler_data(achado.group(1)), ler_data(achado.group(2))
        if (inicio.year, inicio.month) != (competencia.year, competencia.month) or fim < inicio:
            raise LeituraError(
                f"extrato de outro período ({inicio:%d/%m/%Y} a {fim:%d/%m/%Y}); "
                f"competência {competencia:%m/%Y}"
            )
        return fim
