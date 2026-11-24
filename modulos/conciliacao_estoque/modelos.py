"""Estruturas de dados do módulo de Estoque."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum


class ErroArquivo(Exception):
    """Arquivo que não pôde ser lido (inexistente, aberto no Excel, .xls binário, formato inesperado).

    A mensagem é escrita para o usuário final.
    """


class Gravidade(str, Enum):
    ERRO = "ERRO"
    ATENCAO = "ATENÇÃO"
    INFO = "INFO"


@dataclass
class Aviso:
    gravidade: Gravidade
    tipo: str
    mensagem: str
    arquivo: str = ""
    linha: int | None = None
    conta: str = ""


@dataclass(frozen=True, order=True)
class MesReferencia:
    ano: int
    mes: int

    def __post_init__(self):
        if not 1 <= self.mes <= 12:
            raise ValueError(f"Mês inválido: {self.mes}")

    def __str__(self) -> str:
        """Formato de tela: MM/AAAA."""
        return f"{self.mes:02d}/{self.ano}"

    @property
    def para_nome_arquivo(self) -> str:
        """Formato dos nomes de arquivo: MM-AAAA."""
        return f"{self.mes:02d}-{self.ano}"


# ---------------------------------------------------------------------------
# Balancete
# ---------------------------------------------------------------------------


@dataclass
class ContaBalancete:
    codigo: int                 # código reduzido (ex.: 10978)
    classificacao: str          # ex.: 1.01.04.01.0002
    descricao: str
    saldo_anterior: Decimal
    movimento: Decimal
    saldo_atual: Decimal
    linha: int                  # linha do arquivo (1 = primeira)

    @property
    def analitica(self) -> bool:
        """Conta analítica = último segmento da classificação com 4 dígitos."""
        return len(self.classificacao.rsplit(".", 1)[-1]) == 4


@dataclass
class BalanceteEstoque:
    arquivo: str
    mes_referencia: MesReferencia | None = None
    contas: list[ContaBalancete] = field(default_factory=list)   # na ordem do arquivo
    contas_fora_do_prefixo: int = 0                               # ignoradas (fora de 1.01.04)
    avisos: list[Aviso] = field(default_factory=list)

    @property
    def analiticas(self) -> list[ContaBalancete]:
        return [c for c in self.contas if c.analitica]

    @property
    def sinteticas(self) -> list[ContaBalancete]:
        return [c for c in self.contas if not c.analitica]

    def sintetica(self, classificacao: str) -> ContaBalancete | None:
        return next((c for c in self.sinteticas if c.classificacao == classificacao), None)


# ---------------------------------------------------------------------------
# SCF - Movimento Estoque (Contabilidade)
# ---------------------------------------------------------------------------


@dataclass
class LocalSCF:
    codigo: int                 # número entre parênteses no fim da descrição (ex.: 12)
    descricao: str              # como veio no relatório, sem os espaços das pontas
    valores: list[Decimal]      # os 13 valores, na ordem de configuracao.SCF_TITULOS
    linha: int

    def valor(self, posicao: int) -> Decimal:
        """Valor pela posição do título (1 = Saldo Anterior ... 13 = Saldo Atual)."""
        return self.valores[posicao - 1]

    @property
    def saldo_anterior(self) -> Decimal:
        return self.valor(1)

    @property
    def saldo_atual(self) -> Decimal:
        return self.valor(13)


@dataclass
class RelatorioSCF:
    arquivo: str
    mes_referencia: MesReferencia | None = None
    locais: list[LocalSCF] = field(default_factory=list)     # na ordem do arquivo
    total: list[Decimal] | None = None                       # os 13 valores da linha Total(...)
    quantidade_total: int | None = None                      # o NN de Total(NN)
    linhas_ignoradas: int = 0                                # linhas de local com problema
    avisos: list[Aviso] = field(default_factory=list)

    def total_na_posicao(self, posicao: int) -> Decimal | None:
        return self.total[posicao - 1] if self.total else None

    def local(self, codigo: int) -> LocalSCF | None:
        return next((l for l in self.locais if l.codigo == codigo), None)


# ---------------------------------------------------------------------------
# Casamento das contas do balancete com os locais do SCF
# ---------------------------------------------------------------------------


class ComoCasou(str, Enum):
    """Nível em que a conta casou (o valor é a chave usada no gabarito)."""

    CODIGO_LOCAL = "codigo_local"
    NOME_EQUIVALENTE = "nome_equivalente"
    SEM_PAR = "sem_par"

    @property
    def texto(self) -> str:
        """Texto da coluna "Como casou" no Excel."""
        return {
            ComoCasou.CODIGO_LOCAL: "Código do local",
            ComoCasou.NOME_EQUIVALENTE: "Nome equivalente — conferir",
            ComoCasou.SEM_PAR: "Sem par",
        }[self]


@dataclass
class ParCasado:
    conta: ContaBalancete
    local: LocalSCF | None          # None = sem par
    como: ComoCasou
    observacao: str = ""
    sugestao: LocalSCF | None = None        # nível 3: possível par
    semelhanca: float | None = None         # nível 3: 0 a 1


@dataclass
class ResultadoCasamento:
    pares: list[ParCasado] = field(default_factory=list)            # na ordem do balancete
    locais_sem_conta: list[LocalSCF] = field(default_factory=list)  # na ordem do SCF


# ---------------------------------------------------------------------------
# Comparação (EST-01 e EST-03)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Etapa:
    """Uma comparação "valor do balancete x coluna do SCF" (seção 6.4)."""

    id: str                     # "EST-01"
    titulo: str                 # nome oficial (menu e título do Excel)
    campo_balancete: str        # atributo de ContaBalancete: "saldo_anterior" ou "saldo_atual"
    campo_scf: str              # título da coluna do SCF: "Saldo Anterior" ou "Saldo Atual"


@dataclass
class LinhaComparacao:
    """Uma linha da conciliação: conta do balancete (com ou sem par) ou local do SCF sem conta."""

    grupo: str                      # classificação da sintética (1.01.04.01); "" para local sem conta
    classificacao: str
    codigo: int | None              # código reduzido da conta; None para local sem conta
    descricao_balancete: str
    descricao_scf: str
    local_scf: int | None
    saldo_balancete: Decimal
    saldo_scf: Decimal
    como: ComoCasou
    observacao: str = ""

    @property
    def diferenca(self) -> Decimal:
        return self.saldo_balancete - self.saldo_scf


@dataclass
class ConferenciaGrupo:
    """Saldo da conta sintética x subtotal das contas analíticas do grupo."""

    classificacao: str
    descricao: str
    saldo_sintetica: Decimal | None     # None = sintética não impressa no balancete
    subtotal: Decimal
    causa_provavel: str = ""

    @property
    def diferenca(self) -> Decimal:
        return (self.saldo_sintetica or Decimal("0.00")) - self.subtotal


@dataclass
class ResultadoComparacao:
    etapa: Etapa
    mes_referencia: MesReferencia | None
    arquivo_balancete: str
    arquivo_scf: str
    contas: list[LinhaComparacao] = field(default_factory=list)            # na ordem do balancete
    locais_sem_conta: list[LinhaComparacao] = field(default_factory=list)  # na ordem do SCF
    grupos: list[ConferenciaGrupo] = field(default_factory=list)
    saldo_sintetica_raiz: Decimal | None = None     # sintética 1.01.04 no balancete
    total_scf: Decimal | None = None                # linha Total(...) do SCF
    avisos: list[Aviso] = field(default_factory=list)

    @property
    def total_balancete(self) -> Decimal:
        """Soma das contas analíticas (TOTAL GERAL da aba Conciliação)."""
        return sum((l.saldo_balancete for l in self.contas), Decimal("0.00"))

    @property
    def total_scf_das_linhas(self) -> Decimal:
        """Contas casadas + locais sem conta (deve ser igual à linha Total do SCF)."""
        return sum((l.saldo_scf for l in self.contas + self.locais_sem_conta), Decimal("0.00"))

    @property
    def contas_conciliadas(self) -> int:
        return sum(1 for l in self.contas if l.diferenca == 0)

    @property
    def contas_com_diferenca(self) -> int:
        return sum(1 for l in self.contas if l.diferenca != 0)

    @property
    def grupos_conferidos(self) -> int:
        return sum(1 for g in self.grupos if g.diferenca == 0)


# ---------------------------------------------------------------------------
# EST-02: configuração e PDF "Movimento estoque"
# ---------------------------------------------------------------------------


@dataclass
class ItemOperacao:
    codigo: int
    nome: str
    es_tasy: str                # "E" / "S" (só informativo)
    tipo_operacao: str
    grupo: str                  # nome do grupo SCF
    linha: int


@dataclass
class GrupoSCF:
    nome: str
    tipo: str                   # "Entrada" / "Saída"
    posicao: int                # posição do valor na linha do SCF (2 a 11)


@dataclass
class ParIgual:
    operacao_a: int
    nome_a: str
    operacao_b: int
    nome_b: str
    observacao: str
    linha: int


@dataclass
class ConfiguracaoEST02:
    caminho: str
    de_fabrica: bool            # True = cópia de fábrica; False = versão do usuário
    itens: dict[int, ItemOperacao] = field(default_factory=dict)
    grupos: list[GrupoSCF] = field(default_factory=list)
    pares: list[ParIgual] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)

    @property
    def valida(self) -> bool:
        """Com algum ERRO, a EST-02 não roda até a planilha ser corrigida."""
        return not any(a.gravidade == Gravidade.ERRO for a in self.avisos)

    @property
    def descricao_origem(self) -> str:
        return "configuração de fábrica" if self.de_fabrica else "configuração do usuário"

    def grupo(self, nome: str) -> GrupoSCF | None:
        return next((g for g in self.grupos if g.nome == nome), None)

    def grupo_da_operacao(self, codigo: int) -> GrupoSCF | None:
        item = self.itens.get(codigo)
        return self.grupo(item.grupo) if item else None


@dataclass
class OperacaoPDF:
    codigo: int
    valor: Decimal              # último número da linha "Total" da operação
    pagina: int


@dataclass
class MovimentoEstoquePDF:
    arquivo: str
    mes_referencia: MesReferencia | None = None
    operacoes: list[OperacaoPDF] = field(default_factory=list)   # na ordem do PDF
    total_geral: Decimal | None = None
    avisos: list[Aviso] = field(default_factory=list)

    @property
    def soma_operacoes(self) -> Decimal:
        return sum((o.valor for o in self.operacoes), Decimal("0.00"))

    def valor(self, codigo: int) -> Decimal:
        """Valor da operação no PDF; operação ausente vale 0 (regra 6 da seção 6.3)."""
        return next((o.valor for o in self.operacoes if o.codigo == codigo), Decimal("0.00"))


@dataclass
class ConferenciaGrupoSCF:
    """Um grupo do SCF (ou o Total (E)/(S)): total no SCF x soma das operações do PDF."""

    nome: str
    tipo: str                       # "Entrada" / "Saída"
    total_scf: Decimal
    soma_pdf: Decimal
    operacoes: list[int] = field(default_factory=list)      # códigos somados, em ordem
    e_total: bool = False                                   # True = Total (E) ou Total (S)

    @property
    def diferenca(self) -> Decimal:
        return self.total_scf - self.soma_pdf


@dataclass
class ConferenciaPar:
    par: ParIgual
    nome_a: str                     # nome para exibir
    nome_b: str
    valor_a: Decimal
    valor_b: Decimal

    @property
    def diferenca(self) -> Decimal:
        return self.valor_a - self.valor_b

    @property
    def mensagem_atencao(self) -> str:
        return (f"ATENÇÃO: {self.nome_a} ({self.par.operacao_a}) diferente de "
                f"{self.nome_b} ({self.par.operacao_b}) — verificar")

    @property
    def mensagem_ok(self) -> str:
        return f"OK: {self.nome_a} ({self.par.operacao_a}) igual a {self.nome_b} ({self.par.operacao_b})"

    @property
    def mensagem(self) -> str:
        return self.mensagem_atencao if self.diferenca != 0 else self.mensagem_ok


@dataclass
class LinhaOperacao:
    """Uma operação do PDF na aba Operações."""

    codigo: int
    nome: str                       # nome da configuração (sem o prefixo "E - "/"S - ")
    valor: Decimal
    grupo: str                      # "" = sem grupo
    es_tabela: str
    observacao: str = ""

    @property
    def sem_grupo(self) -> bool:
        return not self.grupo


@dataclass
class ResultadoEST02:
    mes_referencia: MesReferencia | None
    arquivo_scf: str
    arquivo_pdf: str
    arquivo_configuracao: str
    origem_configuracao: str        # "configuração de fábrica" / "configuração do usuário"
    entradas: list[ConferenciaGrupoSCF] = field(default_factory=list)
    saidas: list[ConferenciaGrupoSCF] = field(default_factory=list)
    total_entradas: ConferenciaGrupoSCF | None = None
    total_saidas: ConferenciaGrupoSCF | None = None
    total_geral_pdf: Decimal | None = None
    soma_operacoes_pdf: Decimal = Decimal("0.00")
    saldo_anterior_scf: Decimal = Decimal("0.00")
    saldo_atual_scf: Decimal = Decimal("0.00")
    pares: list[ConferenciaPar] = field(default_factory=list)
    operacoes: list[LinhaOperacao] = field(default_factory=list)   # por código
    avisos: list[Aviso] = field(default_factory=list)

    @property
    def todas_as_linhas(self) -> list[ConferenciaGrupoSCF]:
        """Os 11 itens conferidos: grupos de entrada, Total (E), grupos de saída, Total (S)."""
        return [*self.entradas, self.total_entradas, *self.saidas, self.total_saidas]

    @property
    def grupos_conferidos(self) -> int:
        return sum(1 for g in self.todas_as_linhas if g.diferenca == 0)

    @property
    def grupos_com_diferenca(self) -> int:
        return sum(1 for g in self.todas_as_linhas if g.diferenca != 0)

    @property
    def diferenca_total_geral_pdf(self) -> Decimal | None:
        return None if self.total_geral_pdf is None else self.total_geral_pdf - self.soma_operacoes_pdf

    @property
    def fechamento_calculado(self) -> Decimal:
        """Saldo anterior + Total (E) − Total (S), com os totais do próprio SCF."""
        return self.saldo_anterior_scf + self.total_entradas.total_scf - self.total_saidas.total_scf

    @property
    def diferenca_fechamento(self) -> Decimal:
        return self.saldo_atual_scf - self.fechamento_calculado
