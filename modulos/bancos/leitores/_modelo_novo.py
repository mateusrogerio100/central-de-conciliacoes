"""MOLDE para criar um leitor de um modelo novo de extrato.

Este arquivo NÃO é usado pelo programa (o "_" no início do nome indica
isso). Para criar um leitor novo:

  1. Rode:  python conciliar.py --mostrar-texto "<arquivo.pdf>"
     e observe o texto que o programa enxerga: o que identifica o modelo
     de forma única, onde está a conta e onde está o saldo.
  2. Copie este arquivo para  <banco>_<modelo>.py  (ex.: itau_conta_corrente.py)
     nesta mesma pasta.
  3. Preencha os pontos marcados com  >>>  abaixo.
  4. Registre o leitor em leitores/__init__.py (import + lista LEITORES).
  5. Acrescente o PDF de exemplo em tests/gabarito.py e rode  python -m pytest.

Dica sobre expressões regulares (o "re" do Python):
  \\s+        um ou mais espaços/quebras de linha
  \\d         um dígito;  [\\d.]* dígitos e pontos
  (...)      o trecho entre parênteses é o que se quer "capturar"
  PADRAO_VALOR     um valor em reais: "1.234,56" ou "1234,56"
  PADRAO_VALOR_CD  um valor seguido de C ou D: "1.234,56 C", "12,00D"
"""

from datetime import date
from pathlib import Path

from ..modelos import SaldoExtraido
from ..util import PADRAO_VALOR, PADRAO_VALOR_CD, converter_valor, normalizar_conta
from .base import (DATA, LeitorBase, LeituraError, buscar, buscar_ultimo,
                   conferir_mes_referencia, conferir_periodo)


class LeitorModeloNovo(LeitorBase):
    # >>> Nome que aparece no relatório, no formato "<Banco> - <Modelo>".
    nome = "Banco X - Modelo Y"
    # >>> Um de: "BB", "SICOOB", "CEF", "SANTANDER" (ou um banco novo).
    banco = "BANCOX"

    def reconhece(self, texto: str) -> bool:
        # >>> Frases que SÓ aparecem neste modelo de extrato. Use duas ou
        # mais, ligadas por "and", para não confundir com outro modelo do
        # mesmo banco. O teste "nenhum PDF reconhecido por dois leitores"
        # avisa se ficou genérico demais.
        return "Título que só existe neste extrato" in texto and "Nome do banco" in texto

    def ler(self, texto: str, arquivo: Path, competencia: date) -> list[SaldoExtraido]:
        # >>> 0. Período do extrato: TODO leitor confere, para um extrato de
        #     outro mês nunca entrar na soma. DATA casa "01/09/2026" (com ou
        #     sem espaços em volta das barras). Ajuste o texto em volta.
        conferir_periodo(rf"Período:\s*{DATA}\s+a\s+{DATA}", texto, competencia)
        #     Se o extrato traz o mês por extenso ("Mês: Setembro/2026"), use:
        #     conferir_mes_referencia(r"Mês:\s*(\w+)/(\d{4})", texto, competencia)

        # >>> 1. Número da conta. Ajuste o texto antes do número.
        #     buscar() levanta LeituraError sozinho se não achar.
        conta = buscar(r"Conta:\s+(\d[\d.]*-?[0-9Xx]?)", texto, "número da conta").group(1)

        # >>> 2. Saldo DO FIM DO MÊS. Cuidado com saldos parecidos que não
        #     são o do fim do mês (quadro-resumo com o saldo do dia em que o
        #     PDF foi baixado, valor só de capital sem juros etc.).
        #     Se a linha do saldo aparece várias vezes (ex.: uma por página),
        #     use buscar_ultimo() para pegar a última.
        #     Se o valor tem C/D no fim, use PADRAO_VALOR_CD: converter_valor()
        #     já transforma D em negativo.
        texto_saldo = buscar(r"Saldo final\s+(" + PADRAO_VALOR_CD + ")", texto,
                             "saldo final").group(1)
        saldo = converter_valor(texto_saldo)

        # >>> 3. (Opcional) Saldo bloqueado, se o extrato mostrar.
        bloqueado = converter_valor("0,00")

        # >>> 4. (Opcional) Conferências que devem PARAR a leitura com erro,
        #     em vez de devolver um valor errado. Exemplo:
        if "Sem lançamentos" in texto and "Saldo final" not in texto:
            raise LeituraError("extrato sem saldo impresso; conferir manualmente")

        return [SaldoExtraido(
            banco=self.banco,
            tipo="CC",                    # >>> "CC", "APLICACAO", "POUPANCA" ou "OUTRO"
            conta=normalizar_conta(conta),
            conta_original=conta,
            saldo_total=saldo,            # é este que é comparado com o balancete
            saldo_bloqueado=bloqueado,
            arquivo=arquivo,
            modelo=self.nome,
            observacao="",                # >>> algo que o usuário deva conferir
        )]


# Estes nomes são importados só para ficarem à mão ao copiar o molde.
_ = (PADRAO_VALOR, buscar_ultimo, conferir_mes_referencia)
