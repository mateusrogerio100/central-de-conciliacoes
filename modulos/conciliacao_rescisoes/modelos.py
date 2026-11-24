"""
Estruturas de dados da Conciliação de Rescisões a pagar (ESPECIFICACAO seção 17).

Para cada pagamento do mês no Razão da conta Rescisões a pagar, procura a pessoa:
1. nos PDFs de eventos da folha (item 0264 – Líquido Rescisão: rescisões calculadas no mês). Pode haver
   mais de um: o "Cálculo Mensal" e os "Complementar Rescisão". Entram os PDFs cuja soma bate com os
   créditos do razão (ver processar.escolher_pdfs); os outros são do mês seguinte;
2. se não achar, na lista de rescisões pendentes do mês anterior (planilha "Rescisões a pagar").
O que sobra nos dois (sem pagamento) ainda vai ser pago e forma a lista nova de "Rescisões a pagar".

Dinheiro sempre em Decimal. A nota de semelhança dos nomes (0 a 1) é float: não é dinheiro.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from modulos.conciliacao_rescisoes.fornecedores.avisos import Aviso
from modulos.conciliacao_rescisoes.fornecedores.leitores import reais

if TYPE_CHECKING:
    from modulos.conciliacao_rescisoes.financeiro import ComparacaoFinanceiro

# Explicação de um pagamento não encontrado (coluna "Observação")
REGRA_JA_BAIXADA = "a"                  # a rescisão (PDF ou lista anterior) já foi baixada por outro pagamento
REGRA_PDF_FORA_DO_MES = "b"             # a pessoa está num PDF que não entrou no mês (ex.: complementar do mês seguinte)
REGRA_RODAPE = "c"                      # o nome está no rodapé da lista anterior
REGRA_SEM_RESCISAO = "d"
REGRA_COMPLEMENTAR_PDF = REGRA_JA_BAIXADA   # nome antigo (regra 1a do Resumo: complementar de rescisão do PDF)

# Onde o pagamento foi achado
ORIGEM_PDF = "Rescisão do mês (PDF)"
ORIGEM_PENDENTE = "Pendente anterior"
ORIGEM_NAO_ENCONTRADO = "Não encontrado"

# Como os PDFs de eventos foram escolhidos (processar.escolher_pdfs)
ESCOLHA_UNICO = "único"                 # só um PDF: usado como sempre
ESCOLHA_COMBINACAO = "combinação"       # uma única combinação de PDFs bate com os créditos do razão
ESCOLHA_NENHUMA = "nenhuma"             # nenhuma combinação bate: usados todos
ESCOLHA_VARIAS = "várias"               # mais de uma combinação bate: usados todos
ESCOLHA_LANCAMENTOS = "lançamentos"     # nenhuma combinação bate, mas cada PDF usado é igual a um lançamento
                                        # de crédito do razão (os outros PDFs ficam de fora)

# Rodapé que o programa grava abaixo do total da lista nova (aba "Rescisões a pagar"): o que explica
# "saldo do razão − lista". No mês seguinte é lido de volta (os itens continuam valendo até serem apagados).
ROTULO_COMPOSICAO = "COMPOSIÇÃO DA DIFERENÇA: SALDO DO RAZÃO − LISTA"
ROTULO_TOTAL_COMPOSICAO = "Total da composição"
ROTULO_SALDO_RAZAO = "Saldo do razão em"
TEXTO_SEM_COMPOSICAO = "Nenhuma diferença: a lista bate com o saldo do razão."
TEXTO_AVISO_COMPOSICAO = ("Estes itens continuam valendo no mês seguinte: apague ou corrija os que já foram "
                          "resolvidos antes de usar esta planilha como lista do mês anterior.")

TIPO_RAZAO = "Razão"
TIPO_EVENTOS = "Eventos (0264)"
TIPO_CONTROLE = "Rescisões a pagar"
TIPO_FINANCEIRO = "Títulos a pagar (financeiro)"


class Credito(NamedTuple):
    """Uma linha de crédito do Razão ("Líquido Rescisão 0726", ou um estorno/reembolso lançado à mão)."""

    historico: str
    valor: Decimal
    data: date | None = None

    @property
    def descricao(self) -> str:
        """"10/07/2026 – Reembolso de férias colaboradora FULANA…" (sem CPF; histórico longo é cortado)."""
        historico = re.sub(r"\s*\bCPF\b[:\s]*[\d.\-/]+", "", self.historico, flags=re.IGNORECASE)
        historico = " ".join(historico.split())
        if len(historico) > 90:
            historico = historico[:90].rsplit(" ", 1)[0].rstrip(",;.") + "…"
        return f"{self.data:%d/%m/%Y} – {historico}" if self.data else historico


@dataclass
class Pagamento:
    """Uma linha de débito do Razão ("Pagamento de Rescisão conf. bordero n. ... NOME")."""

    data: date | None
    historico: str
    nome: str                            # nome tirado do histórico
    valor: Decimal
    bordero: str = ""
    linha: int = 0


TIPO_CALCULO_MENSAL = "Cálculo Mensal"
TIPO_COMPLEMENTAR = "Complementar Rescisão"


@dataclass
class RescisaoMes:
    """Uma pessoa do item 0264 – Líquido Rescisão do PDF de eventos."""

    matricula: str
    nome: str
    valor: Decimal
    data_pagamento: date | None = None
    tipo: str = ""                       # do cabeçalho do PDF: "Cálculo Mensal", "Complementar Rescisão"
    arquivo: str = ""                    # nome do PDF de onde veio
    pdf: str = ""                        # rótulo do PDF na planilha: "PDF mensal", "PDF complementar 29/06"


@dataclass
class Pendente:
    """Uma rescisão ainda não paga, da planilha "Rescisões a pagar" do mês anterior."""

    periodo: object                      # como veio (data ou texto "  11/2022"); volta igual na lista nova
    nome: str
    valor: Decimal
    linha: int = 0


@dataclass
class LeituraRazao:
    arquivo: str
    unidade: str = ""
    inicio: date | None = None
    fim: date | None = None
    conta: str = ""                      # "20763 - 2.01.03.04.0002  Rescisões a pagar"
    saldo_anterior: Decimal | None = None
    pagamentos: list[Pagamento] = field(default_factory=list)
    creditos: list[Credito] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)
    erro: str | None = None

    @property
    def total_pagamentos(self) -> Decimal:
        return sum((p.valor for p in self.pagamentos), Decimal(0))

    @property
    def total_creditos(self) -> Decimal:
        return sum((c.valor for c in self.creditos), Decimal(0))

    @property
    def saldo_final(self) -> Decimal | None:
        if self.saldo_anterior is None:
            return None
        return self.saldo_anterior + self.total_creditos - self.total_pagamentos


@dataclass
class LeituraEventos:
    arquivo: str
    competencia: date | None = None      # dia 1 do mês ("Período: 06/2026")
    tipo: str = ""                       # "Tipo: Cálculo Mensal" / "Tipo: Complementar Rescisão"
    assinatura: str = ""                 # resumo do conteúdo do arquivo: PDFs repetidos são ignorados
    formato: str = "PDF"                 # "PDF" ou "Excel" (o mesmo relatório exportado em .xlsx)
    rescisoes: list[RescisaoMes] = field(default_factory=list)
    total_impresso: Decimal | None = None
    quantidade_impressa: int | None = None
    avisos: list[Aviso] = field(default_factory=list)
    erro: str | None = None

    @property
    def total(self) -> Decimal:
        return sum((r.valor for r in self.rescisoes), Decimal(0))

    @property
    def data_pagamento(self) -> date | None:
        """A data de pagamento mais comum entre as pessoas do 0264."""
        datas = [r.data_pagamento for r in self.rescisoes if r.data_pagamento]
        return max(set(datas), key=datas.count) if datas else None

    @property
    def complementar(self) -> bool:
        return "complementar" in self.tipo.casefold()

    @property
    def rotulo(self) -> str:
        """"PDF mensal", "PDF complementar 29/06" — ou "Excel mensal"... (o que aparece nas colunas de origem)."""
        if "mensal" in self.tipo.casefold():
            return f"{self.formato} mensal"
        if self.complementar:
            data = self.data_pagamento
            return f"{self.formato} complementar {data:%d/%m}" if data else f"{self.formato} complementar"
        return f"{self.formato} {self.tipo}".strip()


@dataclass
class LeituraControle:
    arquivo: str
    aba: str = ""
    pendentes: list[Pendente] = field(default_factory=list)
    # linhas abaixo do total (composição da diferença etc.): só para as observações, nunca para a lista
    rodape: list[tuple[str, Decimal | None]] = field(default_factory=list)
    # itens da composição da diferença gravada pelo programa (ROTULO_COMPOSICAO): lista + itens = saldo do razão
    composicao: list[tuple[str, Decimal]] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)
    erro: str | None = None

    @property
    def total(self) -> Decimal:
        return sum((p.valor for p in self.pendentes), Decimal(0))

    @property
    def total_composicao(self) -> Decimal:
        return sum((v for _, v in self.composicao), Decimal(0))


@dataclass
class Baixa:
    """O que aconteceu com um pagamento do Razão."""

    pagamento: Pagamento
    origem: str
    rescisao: RescisaoMes | None = None
    pendente: Pendente | None = None
    nota: float | None = None            # confiança do casamento dos nomes (1 = idêntico)
    regra: str = ""                      # só nos não encontrados: REGRA_JA_BAIXADA...
    observacao: str = ""                 # só nos não encontrados: explicação provável
    ja_baixada_por: Baixa | None = None  # regra a: o pagamento que já tinha baixado a rescisão da pessoa

    @property
    def nome_encontrado(self) -> str:
        if self.rescisao is not None:
            return self.rescisao.nome
        if self.pendente is not None:
            return self.pendente.nome
        return ""

    @property
    def onde_achado(self) -> str:
        """Texto da coluna "Onde foi achado": de qual PDF veio a rescisão ("PDF mensal"...)."""
        if self.origem == ORIGEM_PDF and self.rescisao is not None and self.rescisao.pdf:
            return self.rescisao.pdf
        return self.origem

    @property
    def valor_referencia(self) -> Decimal | None:
        """Valor da rescisão achada (PDF ou lista de pendentes)."""
        if self.rescisao is not None:
            return self.rescisao.valor
        if self.pendente is not None:
            return self.pendente.valor
        return None

    @property
    def diferenca(self) -> Decimal | None:
        """Valor da rescisão − valor pago (None se não foi achada)."""
        referencia = self.valor_referencia
        return None if referencia is None else referencia - self.pagamento.valor


@dataclass
class ItemLista:
    """Uma linha da lista nova de "Rescisões a pagar"."""

    periodo: object
    nome: str
    valor: Decimal
    origem: str                          # ORIGEM_PENDENTE ou ORIGEM_PDF
    pdf: str = ""                        # só nas do PDF: de qual PDF veio ("PDF mensal"...)
    restante_de: Baixa | None = None     # paga a menor: o que faltou pagar (valor = rescisão − pago)

    @property
    def texto_origem(self) -> str:
        """Texto da coluna "Origem" da lista nova."""
        origem = self.pdf if self.origem == ORIGEM_PDF and self.pdf else self.origem
        if self.restante_de is not None:
            pagamento = self.restante_de.pagamento
            data = f" em {pagamento.data:%d/%m/%Y}" if pagamento.data else ""
            origem += f" – restante (pago R$ {reais(pagamento.valor)}{data})"
        return origem


@dataclass
class ResultadoRescisoes:
    """Tudo o que processar_rescisoes() devolve para a interface."""

    baixas: list[Baixa] = field(default_factory=list)
    lista_nova: list[ItemLista] = field(default_factory=list)
    notas: list[str] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)
    unidade: str = ""
    competencia: date | None = None
    data_final: date | None = None       # fim do período do razão (posição da lista nova)
    saldo_anterior: Decimal | None = None
    total_creditos: Decimal | None = None
    total_pagamentos: Decimal | None = None
    saldo_final: Decimal | None = None
    total_pdf: Decimal | None = None     # soma do 0264 dos PDFs usados
    total_controle: Decimal | None = None
    composicao_anterior: list[tuple[str, Decimal]] = field(default_factory=list)   # rodapé da lista anterior
    composicao_nova: list[tuple[str, Decimal]] = field(default_factory=list)       # rodapé da lista nova
    pdfs_usados: list[LeituraEventos] = field(default_factory=list)
    pdfs_fora: list[LeituraEventos] = field(default_factory=list)   # não lançados no razão deste mês
    creditos: list[Credito] = field(default_factory=list)           # lançamentos de crédito do razão
    creditos_sem_pdf: list[Credito] = field(default_factory=list)   # créditos sem PDF de valor igual
    pdfs_sem_credito: list[LeituraEventos] = field(default_factory=list)   # PDFs usados sem crédito igual
    escolha_pdfs: str = ""               # ESCOLHA_UNICO, ESCOLHA_COMBINACAO, ESCOLHA_NENHUMA, ESCOLHA_VARIAS
    arquivo_razao: str = ""
    arquivo_eventos: str = ""
    arquivo_controle: str = ""
    arquivo_financeiro: str = ""         # opcional: títulos a pagar do financeiro
    financeiro: ComparacaoFinanceiro | None = None   # lista nova × financeiro (None = sem o arquivo)
    caminho_relatorio: Path | None = None
    erro: str | None = None

    def baixas_de(self, origem: str) -> list[Baixa]:
        return [b for b in self.baixas if b.origem == origem]

    @property
    def complementares(self) -> list[Baixa]:
        """Não encontrados cuja rescisão de um PDF usado já tinha sido baixada (regra a com rescisão do PDF)."""
        return [b for b in self.baixas if b.regra == REGRA_JA_BAIXADA and b.ja_baixada_por is not None
                and b.ja_baixada_por.origem == ORIGEM_PDF]

    @property
    def valores_diferentes(self) -> list[Baixa]:
        return [b for b in self.baixas if b.diferenca not in (None, Decimal(0))]

    @property
    def pagos_a_menor(self) -> list[Baixa]:
        """Pago menos que a rescisão: o que faltou pagar continua na lista nova."""
        return [b for b in self.valores_diferentes if b.diferenca > 0]

    @property
    def pagos_a_maior(self) -> list[Baixa]:
        """Pago mais que a rescisão: a diferença vai para a composição da diferença (rodapé)."""
        return [b for b in self.valores_diferentes if b.diferenca < 0]

    @property
    def total_lista_nova(self) -> Decimal:
        return sum((i.valor for i in self.lista_nova), Decimal(0))
