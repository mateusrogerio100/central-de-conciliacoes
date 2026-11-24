"""Leitor: Banco do Brasil — extrato de conta corrente (BB Cash).

O mesmo extrato também é salvo da tela "Consultas - Extrato de conta corrente" do
autoatendimento (outubro/2026): o título não tem "BB Cash", mas as linhas e os saldos são
iguais, então os dois são lidos por este leitor.

Trecho do texto extraído:
    Conta corrente 1179-7 CONVENIO989501-2025
    ...
    31/08/2026 0000 00000 S A L D O 640,44 C

O período vem de três formas:
    "de 01 / 08 / 2026 até 31 / 08 / 2026"   (intervalo de datas)
    "Período do\\n08 / 2026\\nextrato"         (mês inteiro)
    "Período solicitado 07 / 2026"            (mês inteiro)

Conta sem movimento às vezes vem só com "Sem lançamentos no período" e
nenhum saldo impresso. Sem movimento não quer dizer saldo zero, então a
leitura para com uma mensagem pedindo conferência manual.

Extrato que passa do fim do mês (ex.: "de 01/08/2026 até 01/09/2026"):
a última linha "S A L D O" é do dia seguinte e NÃO serve. O saldo é o da
última linha com data de balancete (a 1ª data da linha) até o fim do mês
que tenha a coluna Saldo preenchida. Se a conta não teve movimento, essa
linha é a do "Saldo Anterior":

    31/08/2026 01/09/2026 ... Resgate BB CDB DI 2.012,50 C 3.424,42 C   <- saldo em 31/08
    01/09/2026 ... BB Rende Fácil 3.424,42 D
    01/09/2026 ... S A L D O 0,00 C                                     <- NÃO usar
"""

import calendar
import re
from datetime import date
from pathlib import Path

from ..modelos import SaldoExtraido
from ..util import PADRAO_VALOR_CD, converter_valor, normalizar_conta
from .base import DATA, LeitorBase, LeituraError, buscar, buscar_ultimo, ler_data

_LINHA_COM_DATA = re.compile(r"^(\d{2}/\d{2}/\d{4})\s.*$", re.MULTILINE)
_TELA_CONSULTAS = re.compile(r"Consultas\s*[-–]\s*Extrato de conta corrente")


class LeitorBBContaCorrente(LeitorBase):
    nome = "BB - Conta corrente"
    banco = "BB"

    def reconhece(self, texto: str) -> bool:
        if "Extrato de conta corrente" not in texto:
            return False
        return "BB Cash" in texto or bool(_TELA_CONSULTAS.search(texto))

    def ler(self, texto: str, arquivo: Path, competencia: date) -> list[SaldoExtraido]:
        fim_do_mes = competencia.replace(
            day=calendar.monthrange(competencia.year, competencia.month)[1])
        fim_do_extrato = self._conferir_periodo(texto, competencia)
        if "Sem lançamentos no período" in texto and "S A L D O" not in texto:
            raise LeituraError("extrato sem saldo impresso (sem lançamentos no período); "
                               "conferir o saldo manualmente")
        conta = buscar(r"Conta corrente\s+(\d[\d.]*-[0-9Xx])\b", texto,
                       "número da conta").group(1)

        observacao = ""
        if fim_do_extrato > fim_do_mes:
            saldo = self._saldo_ate(texto, fim_do_mes)
            observacao = (f"extrato vai até {fim_do_extrato:%d/%m/%Y}: usado o saldo "
                          f"da última linha até {fim_do_mes:%d/%m/%Y}")
        else:
            # Saldo final: último valor com C/D da última linha "S A L D O".
            linha_saldo = buscar_ultimo(r"S A L D O.*", texto, "linha 'S A L D O'").group(0)
            saldo = converter_valor(
                buscar_ultimo(PADRAO_VALOR_CD, linha_saldo, "valor do saldo final").group(0))

        return [SaldoExtraido(
            banco=self.banco,
            tipo="CC",
            conta=normalizar_conta(conta),
            conta_original=conta,
            saldo_total=saldo,
            arquivo=arquivo,
            modelo=self.nome,
            observacao=observacao,
        )]

    def _conferir_periodo(self, texto: str, competencia: date) -> date:
        """Confere o período e devolve a data final do extrato.

        O início tem que ser no mês de competência; o fim pode passar do
        mês (aí o saldo é lido até o último dia do mês).
        """
        mes_inteiro = re.search(r"Período (?:do|solicitado)\s+(\d{2})\s*/\s*(\d{4})\s", texto)
        if mes_inteiro:
            mes, ano = int(mes_inteiro.group(1)), int(mes_inteiro.group(2))
            if (ano, mes) != (competencia.year, competencia.month):
                raise LeituraError(f"extrato de outro mês ({mes:02d}/{ano}); "
                                   f"competência {competencia:%m/%Y}")
            return date(ano, mes, calendar.monthrange(ano, mes)[1])

        achado = buscar(rf"de\s+{DATA}\s+até\s+{DATA}", texto, "período do extrato")
        inicio, fim = ler_data(achado.group(1)), ler_data(achado.group(2))
        if (inicio.year, inicio.month) != (competencia.year, competencia.month) or fim < inicio:
            raise LeituraError(
                f"extrato de outro período ({inicio:%d/%m/%Y} a {fim:%d/%m/%Y}); "
                f"competência {competencia:%m/%Y}"
            )
        return fim

    def _saldo_ate(self, texto: str, limite: date):
        """Saldo da última linha com data de balancete até `limite`.

        Só contam linhas com a coluna Saldo preenchida: a linha "S A L D O"
        ou linhas com dois valores C/D (Valor e Saldo), como o "Saldo Anterior".
        """
        saldo = None
        for linha in _LINHA_COM_DATA.finditer(texto):
            if ler_data(linha.group(1)) > limite:
                continue
            valores = re.findall(PADRAO_VALOR_CD, linha.group(0))
            if valores and ("S A L D O" in linha.group(0) or len(valores) >= 2):
                saldo = converter_valor(valores[-1])
        if saldo is None:
            raise LeituraError(f"nenhuma linha com saldo até {limite:%d/%m/%Y}")
        return saldo
