"""Estruturas de dados do módulo Planilha HM."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

ZERO = Decimal("0.00")


class ErroLeitura(Exception):
    """Problema que impede ler uma entrada; a mensagem é para o usuário."""


@dataclass
class Aviso:
    """Algo que o usuário precisa saber e que não impede o resto (aba "Avisos" do relatório)."""

    origem: str            # arquivo e linha ("Eventos 09-2026.XLS linha 40")
    mensagem: str
    erro: bool = False     # True = a conferência não fecha (vermelho); False = atenção


# ---------------------------------------------------------------------------
# Eventos (2.1, R1, R2)
# ---------------------------------------------------------------------------

@dataclass
class SubtotalCC:
    """Linha de subtotal de um centro de custo dentro de um evento (R1): vira uma linha da aba Senior."""

    evento: int
    codigo: str            # código do centro de custo ("72")
    nome: str
    valor: Decimal
    linha: int             # linha do relatório Eventos


@dataclass
class Evento:
    """Um bloco "Evento:" do relatório, com os subtotais de CC e a linha "Total Evento"."""

    numero: int
    nome: str
    sinal: str             # "(+)" ou "(-)"
    linha: int
    subtotais: list[SubtotalCC] = field(default_factory=list)
    total: Decimal | None = None     # da linha "Total Evento"; None = linha não encontrada
    codigo_historico: str = ""       # o código do histórico do Movimento (seção 2.2)
    erro: str = ""                   # R2: preenchido = o evento não entra na planilha

    @property
    def soma_subtotais(self) -> Decimal:
        return sum((s.valor for s in self.subtotais), ZERO)

    @property
    def ok(self) -> bool:
        return not self.erro


@dataclass
class Eventos:
    """O relatório Eventos lido."""

    arquivo: str
    ano: int | None = None
    mes: int | None = None
    eventos: list[Evento] = field(default_factory=list)
    total_relatorio: Decimal | None = None   # a linha do total geral, no fim do relatório
    avisos: list[Aviso] = field(default_factory=list)

    @property
    def eventos_ok(self) -> list[Evento]:
        return [e for e in self.eventos if e.ok]

    @property
    def subtotais(self) -> list[SubtotalCC]:
        """R3: as linhas da aba Senior, na ordem do relatório (só os eventos sem erro)."""
        return [s for e in self.eventos_ok for s in e.subtotais]

    @property
    def total(self) -> Decimal:
        """Soma dos "Total Evento" de todos os eventos."""
        return sum((e.total for e in self.eventos if e.total is not None), ZERO)


# ---------------------------------------------------------------------------
# Planilha HM (2.3)
# ---------------------------------------------------------------------------

@dataclass
class LinhaCC:
    """Linha de centro de custo de um evento na aba do ano (D = código do CC)."""

    codigo: str
    nome: str
    linha: int


@dataclass
class LinhaEvento:
    """Linha de evento na aba do ano (D vazia), com as linhas de CC logo abaixo."""

    numero: int
    nome: str
    linha: int
    ccs: list[LinhaCC] = field(default_factory=list)

    @property
    def ultima_linha(self) -> int:
        """A última linha do evento (a do último CC, ou a própria linha do evento)."""
        return self.ccs[-1].linha if self.ccs else self.linha


@dataclass
class Secao:
    """Seção da aba do ano: abertura ("EVENTO" + nome), eventos e linha de total."""

    nome: str
    linha: int                         # linha de abertura
    eventos: list[LinhaEvento] = field(default_factory=list)
    linha_total: int | None = None     # None = seção sem linha de total (ex.: seção vazia)
    nome_total: str = ""
    linhas_no_total: list[int] = field(default_factory=list)   # linhas que a fórmula do total soma (algum mês)
    linhas_no_total_mes: dict[int, list[int]] = field(default_factory=dict)   # mês → linhas que o total soma

    @property
    def linhas_eventos(self) -> list[int]:
        return [e.linha for e in self.eventos]


@dataclass
class AbaSenior:
    """Uma aba "Senior MM AAAA": quantas linhas de dados tem e até onde vão as fórmulas F, G e H."""

    nome: str
    mes: int
    linhas_dados: int = 0                                  # linhas com o evento preenchido (da 2 em diante)
    ultima_formula: dict[str, int] = field(default_factory=dict)   # título da coluna → última linha com fórmula
    valores: dict[int, Decimal] = field(default_factory=dict)      # evento → soma do Valor (o SOMASE da linha do evento)
    valores_cc: dict[tuple[int, str], Decimal] = field(default_factory=dict)   # (evento, cód. do CC) → soma do Valor


@dataclass
class Planilha:
    """A Planilha HM lida (só a estrutura: o preenchimento é feito numa cópia)."""

    arquivo: str
    ano: int
    aba_ano: str
    linha_titulos: int
    colunas: dict[str, int]            # título → coluna (1 = A): EVENTO, nome, Concateno, Cód., Centros de Custos
    colunas_meses: dict[int, int]      # mês (1 a 12) → coluna
    secoes: list[Secao] = field(default_factory=list)
    linha_total_geral: int | None = None
    linhas_no_total_geral: list[int] = field(default_factory=list)
    linhas_no_total_geral_mes: dict[int, list[int]] = field(default_factory=dict)
    linha_lote: int | None = None
    linha_diferenca: int | None = None
    lote_por_mes: dict[int, object] = field(default_factory=dict)   # mês → valor digitado na linha LOTE REPASSE
    seniors: dict[int, AbaSenior] = field(default_factory=dict)     # mês → aba Senior
    avisos: list[Aviso] = field(default_factory=list)

    @property
    def eventos(self) -> list[LinhaEvento]:
        return [e for s in self.secoes for e in s.eventos]

    def secao_do_evento(self, numero: int) -> Secao | None:
        return next((s for s in self.secoes if any(e.numero == numero for e in s.eventos)), None)

    def evento(self, numero: int) -> LinhaEvento | None:
        return next((e for e in self.eventos if e.numero == numero), None)

    @property
    def ultima_competencia(self) -> int | None:
        """O último mês com a aba Senior preenchida (None = nenhum)."""
        return max((m for m, s in self.seniors.items() if s.linhas_dados), default=None)


# ---------------------------------------------------------------------------
# Movimento (2.2)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ContaContabil:
    """Conta de débito de um lançamento do Movimento."""

    codigo: str            # código reduzido ("30197")
    nome: str              # "Honorários Médicos Fixos PJ"
    classificacao: str     # "3.01.01.06.03.0002"


@dataclass
class LinhaMovimento:
    """Uma linha do .csv do Movimento."""

    linha: int             # linha do .csv (a 1 é a dos títulos)
    debito: str            # código reduzido da conta de débito ("" = sem débito)
    credito: str
    valor: Decimal
    codigo_historico: str  # 1ª coluna "Histórico" (o mesmo código da linha "Total Evento")
    historico: str         # 2ª coluna "Histórico" (o texto do lançamento)
    conta_debito: str      # nome da conta de débito
    classificacao_debito: str
    evento: int | None     # o número do evento, quando o histórico traz "Evento NNNN"

    @property
    def tem_debito(self) -> bool:
        return bool(self.debito)

    @property
    def conta(self) -> ContaContabil:
        return ContaContabil(self.debito, self.conta_debito, self.classificacao_debito)


@dataclass
class Movimento:
    """O Movimento do lote de Repasse a terceiros lido."""

    arquivo: str
    ano: int | None = None
    mes: int | None = None
    lote: str = ""
    linhas: list[LinhaMovimento] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        """Seção 2.2: soma do Valor das linhas com Débito preenchido (inclui as com débito e crédito)."""
        return sum((l.valor for l in self.linhas if l.tem_debito), ZERO)


# ---------------------------------------------------------------------------
# Tabela conta → seção (R5a)
# ---------------------------------------------------------------------------

@dataclass
class ItemTabela:
    classificacao: str     # "3.01.01.06.03.0002"
    conta: str             # "Honorários Médicos Fixos PJ"
    secao: str             # nome da seção na aba do ano


@dataclass
class TabelaSecoes:
    """O secoes_contas.csv: classificação da conta → seção."""

    arquivo: str
    itens: dict[str, ItemTabela] = field(default_factory=dict)   # classificação → item
    existia: bool = True                                         # False = montada agora (R5a, item 1)
    avisos: list[Aviso] = field(default_factory=list)

    def secao(self, classificacao: str) -> str | None:
        item = self.itens.get(classificacao)
        return item.secao if item else None


@dataclass
class Pergunta:
    """Pergunta da tela (R5 item 4, ou conta em mais de uma seção ao montar a tabela). A resposta é o nome de
    uma das `opcoes` ou cfg.RESPOSTA_SECAO_NOVA (só quando `permite_nova`)."""

    chave: str                      # classificação da conta; sem conta, "evento NNNN"
    motivo: str                     # o texto da pergunta
    contas: list[ContaContabil]
    eventos: list[int]
    opcoes: list[str]               # seções que podem ser escolhidas
    permite_nova: bool = True
    nome_secao_nova: str = ""       # o nome que a seção nova teria


@dataclass
class EventoNovo:
    """Evento do Eventos que não está na aba do ano (R5)."""

    evento: Evento
    contas: list[ContaContabil]
    como: str                       # como a conta foi achada no Movimento ("" = não achada)
    secao: str | None = None        # seção decidida (None = depende da pergunta)
    origem: str = ""                # de onde veio a seção (tabela, tabela montada agora, resposta na tela)
    chave_pergunta: str = ""


@dataclass
class Plano:
    """O que o preenchimento vai fazer, antes de gravar (a tela faz as perguntas entre um e outro)."""

    tabela: TabelaSecoes
    caminho_tabela: str
    novos: list[EventoNovo] = field(default_factory=list)
    perguntas: list[Pergunta] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)


@dataclass
class LinhaCriada:
    """Linha acrescentada à aba do ano (aba "Linhas criadas" do relatório)."""

    tipo: str                       # "evento novo", "CC novo", "seção nova", "total da seção nova"
    linha: int                      # linha na cópia gravada
    evento: int | None = None
    nome_evento: str = ""
    codigo_cc: str = ""
    nome_cc: str = ""
    secao: str = ""
    conta: str = ""
    origem: str = ""                # de onde veio a seção (evento novo)
    motivo: str = ""


@dataclass
class Preenchimento:
    """Resultado da gravação da cópia."""

    destino: str
    mes: int
    ano: int
    linhas_senior: int = 0
    lote: Decimal = ZERO
    criadas: list[LinhaCriada] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Conferência final (R9)
# ---------------------------------------------------------------------------

@dataclass
class TotalSecao:
    secao: str
    nome_total: str
    linha: int
    valor: Decimal


@dataclass
class ComparacaoEvento:
    """Evento identificado no Movimento ("Evento NNNN" no histórico): valor no Eventos × no Movimento."""

    evento: int
    nome: str
    valor_eventos: Decimal
    valor_movimento: Decimal

    @property
    def diferenca(self) -> Decimal:
        return self.valor_eventos - self.valor_movimento


@dataclass
class Conferencia:
    mes: int
    ano: int
    total_eventos: Decimal
    total_geral: Decimal
    total_movimento: Decimal
    totais: list[TotalSecao] = field(default_factory=list)
    eventos_fora: list[Evento] = field(default_factory=list)          # não entraram em nenhuma seção
    comparacao: list[ComparacaoEvento] = field(default_factory=list)
    linhas_sem_evento: list[LinhaMovimento] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)

    @property
    def diferenca(self) -> Decimal:
        return self.total_geral - self.total_movimento

    @property
    def ok(self) -> bool:
        return self.diferenca == 0
