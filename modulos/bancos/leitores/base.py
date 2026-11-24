"""O contrato que todo leitor de extrato segue.

Cada modelo de extrato (ex.: "BB - Poupança") tem um leitor próprio, que
herda de LeitorBase e preenche reconhece() e ler().
"""

import re
from datetime import date, datetime
from pathlib import Path

from ..modelos import SaldoExtraido
from ..util import numero_do_mes

# Uma data dd/mm/aaaa, aceitando espaços em volta das barras ("01 / 08 / 2026").
DATA = r"(\d{2}\s*/\s*\d{2}\s*/\s*\d{4})"


class LeituraError(Exception):
    """Erro de leitura com mensagem clara (ex.: "saldo não encontrado")."""


class LeitorBase:
    nome: str = ""        # ex.: "BB - Poupança" (aparece no relatório)
    banco: str = ""       # ex.: "BB"
    extensoes: tuple[str, ...] = (".pdf",)

    def reconhece(self, texto: str) -> bool:
        """True se o texto é deste modelo. Deve ser específico o bastante
        para NUNCA reconhecer o PDF de outro modelo."""
        raise NotImplementedError

    def ler(self, texto: str, arquivo: Path, competencia: date) -> list[SaldoExtraido]:
        """Extrai os saldos. Pode devolver mais de um (ex.: Santander C/C
        devolve C/C e Aplicação). Deve levantar LeituraError com mensagem
        clara se um campo obrigatório não for encontrado — nunca devolver
        zero por não ter achado o valor."""
        raise NotImplementedError


def buscar(padrao: str, texto: str, o_que: str, flags: int = 0) -> re.Match:
    """Procura o padrão no texto; se não achar, levanta LeituraError.

    `o_que` descreve o campo procurado e aparece na mensagem de erro
    (ex.: "número da conta").
    """
    achado = re.search(padrao, texto, flags)
    if achado is None:
        raise LeituraError(f"{o_que} não encontrado(a) no extrato")
    return achado


def ler_data(texto: str) -> date:
    """"31/08/2026" ou "31 / 08 / 2026" -> date(2026, 8, 31)."""
    return datetime.strptime(re.sub(r"\s", "", texto), "%d/%m/%Y").date()


def conferir_periodo(padrao: str, texto: str, competencia: date, flags: int = 0) -> None:
    """Confere se o período do extrato é do mês de competência.

    `padrao` deve ter dois grupos com as datas de início e fim (use DATA).
    Se alguma das datas for de outro mês, levanta LeituraError: um extrato
    de outro mês nunca pode entrar na soma como se fosse da competência.
    """
    achado = buscar(padrao, texto, "período do extrato", flags)
    inicio, fim = ler_data(achado.group(1)), ler_data(achado.group(2))
    for data in (inicio, fim):
        if (data.year, data.month) != (competencia.year, competencia.month):
            raise LeituraError(
                f"extrato de outro período ({inicio:%d/%m/%Y} a {fim:%d/%m/%Y}); "
                f"competência {competencia:%m/%Y}"
            )


def conferir_mes_referencia(padrao: str, texto: str, competencia: date,
                            flags: int = 0) -> None:
    """Como conferir_periodo(), para extratos que trazem o mês por extenso.

    `padrao` deve ter dois grupos: nome do mês ("Agosto", "AGOSTO") e ano.
    """
    achado = buscar(padrao, texto, "mês de referência do extrato", flags)
    mes, ano = numero_do_mes(achado.group(1)), int(achado.group(2))
    if (ano, mes) != (competencia.year, competencia.month):
        raise LeituraError(
            f"extrato de outro mês ({achado.group(1)}/{ano}); "
            f"competência {competencia:%m/%Y}"
        )


def buscar_ultimo(padrao: str, texto: str, o_que: str, flags: int = 0) -> re.Match:
    """Igual a buscar(), mas devolve a ÚLTIMA ocorrência do padrão."""
    achados = list(re.finditer(padrao, texto, flags))
    if not achados:
        raise LeituraError(f"{o_que} não encontrado(a) no extrato")
    return achados[-1]
