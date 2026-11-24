"""Casa os saldos dos extratos com as contas do balancete e define o status.

Regras (seção 7 da especificação):
  - chave de casamento: (banco, tipo, conta normalizada);
  - casamento exato primeiro; depois, por sufixo (ex.: Santander 130036369
    no extrato x 3636-9 no balancete), só com um único candidato possível;
  - saldos com a mesma chave são somados (ex.: CDB + Rende Fácil da mesma
    conta);
  - fonte secundária (item D do Santander C/C) só é usada se não houver
    extrato principal da mesma chave; se houver, os dois são comparados.

O comparador só aponta diferenças; não tenta explicá-las.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from .modelos import ContaBalancete, SaldoExtraido
from .util import formatar_valor

OK = "OK"
DIFERENCA = "DIFERENÇA"
SEM_EXTRATO = "SEM EXTRATO"
NAO_ESTA_NO_BALANCETE = "NÃO ESTÁ NO BALANCETE"
STATUS = (OK, DIFERENCA, SEM_EXTRATO, NAO_ESTA_NO_BALANCETE)

# Tamanho mínimo da conta menor para aceitar casamento por sufixo.
MINIMO_SUFIXO = 5

_CENTAVO = Decimal("0.01")

Chave = tuple[str, str, str]   # (banco, tipo, conta normalizada)


@dataclass
class GrupoExtrato:
    """Todos os saldos de extrato de uma mesma chave, já somados."""

    chave: Chave
    saldos: list[SaldoExtraido]          # os que entram na soma
    saldo_total: Decimal
    saldo_bloqueado: Decimal
    observacoes: list[str] = field(default_factory=list)

    @property
    def saldo_disponivel(self) -> Decimal:
        return self.saldo_total - self.saldo_bloqueado

    @property
    def arquivos(self) -> list[str]:
        nomes = []
        for saldo in self.saldos:
            nome = saldo.arquivo.name if saldo.arquivo else ""
            if nome and nome not in nomes:
                nomes.append(nome)
        return nomes

    @property
    def conta_original(self) -> str:
        return self.saldos[0].conta_original


@dataclass
class LinhaConciliacao:
    """Uma linha da aba "Conciliação"."""

    status: str
    banco: str
    tipo: str
    conta: str                               # normalizada (a do balancete, se houver)
    conta_balancete: ContaBalancete | None = None
    grupo: GrupoExtrato | None = None
    observacoes: list[str] = field(default_factory=list)

    @property
    def saldo_balancete(self) -> Decimal | None:
        return self.conta_balancete.saldo_atual if self.conta_balancete else None

    @property
    def diferenca(self) -> Decimal | None:
        """Saldo do extrato − saldo do balancete (só quando há os dois)."""
        if self.grupo is None or self.conta_balancete is None:
            return None
        return (self.grupo.saldo_total - self.conta_balancete.saldo_atual).quantize(_CENTAVO)

    @property
    def arquivos(self) -> list[str]:
        return self.grupo.arquivos if self.grupo else []

    @property
    def observacao(self) -> str:
        return "; ".join(self.observacoes)


def conciliar(contas: list[ContaBalancete],
              saldos: list[SaldoExtraido]) -> list[LinhaConciliacao]:
    """Uma linha por conta do balancete (na ordem do balancete), seguidas
    das linhas NÃO ESTÁ NO BALANCETE (na ordem em que os extratos foram lidos)."""
    grupos = agrupar_saldos(saldos)
    casamentos = _casar(contas, grupos)

    linhas = []
    usados: set[Chave] = set()
    for conta in contas:
        linha = LinhaConciliacao(status=SEM_EXTRATO, banco=conta.banco, tipo=conta.tipo,
                                 conta=conta.conta, conta_balancete=conta)
        if not conta.banco:
            linha.observacoes.append("descrição não reconhecida")
        casamento = casamentos.get(conta.codigo)
        if isinstance(casamento, str):          # motivo para não casar
            linha.observacoes.append(casamento)
        elif casamento is not None:
            chave, por_sufixo = casamento
            grupo = grupos[chave]
            usados.add(chave)
            linha.grupo = grupo
            linha.status = OK if linha.diferenca == 0 else DIFERENCA
            if por_sufixo:
                linha.observacoes.append("conta casada por sufixo")
            linha.observacoes.extend(grupo.observacoes)
        linhas.append(linha)

    for chave, grupo in grupos.items():
        if chave in usados:
            continue
        linha = LinhaConciliacao(status=NAO_ESTA_NO_BALANCETE, banco=chave[0], tipo=chave[1],
                                 conta=chave[2], grupo=grupo)
        if grupo.saldo_total == 0:
            linha.observacoes.append("saldo zero")
        linha.observacoes.extend(grupo.observacoes)
        linhas.append(linha)
    return linhas


def contar_por_status(linhas: list[LinhaConciliacao]) -> dict[str, int]:
    contagem = {status: 0 for status in STATUS}
    for linha in linhas:
        contagem[linha.status] += 1
    return contagem


def agrupar_saldos(saldos: list[SaldoExtraido]) -> dict[Chave, GrupoExtrato]:
    """Junta os saldos por chave, somando e aplicando a regra da fonte secundária."""
    por_chave: dict[Chave, list[SaldoExtraido]] = {}
    for saldo in saldos:
        por_chave.setdefault((saldo.banco, saldo.tipo, saldo.conta), []).append(saldo)

    grupos = {}
    for chave, lista in por_chave.items():
        principais = [s for s in lista if not s.fonte_secundaria]
        secundarios = [s for s in lista if s.fonte_secundaria]
        usados = principais or secundarios
        grupo = GrupoExtrato(
            chave=chave,
            saldos=usados,
            saldo_total=sum((s.saldo_total for s in usados), Decimal("0")),
            saldo_bloqueado=sum((s.saldo_bloqueado for s in usados), Decimal("0")),
        )
        if principais and secundarios:
            total_secundario = sum((s.saldo_total for s in secundarios), Decimal("0"))
            if total_secundario != grupo.saldo_total:
                grupo.observacoes.append(
                    f"extratos divergentes: {formatar_valor(grupo.saldo_total)} "
                    f"({_nomes(principais)}) x {formatar_valor(total_secundario)} "
                    f"({_nomes(secundarios)}, fonte secundária)"
                )
        for saldo in usados:
            if saldo.observacao:
                prefixo = f"{saldo.arquivo.name}: " if len(usados) > 1 and saldo.arquivo else ""
                grupo.observacoes.append(prefixo + saldo.observacao)
        grupos[chave] = grupo
    return grupos


def _casar(contas: list[ContaBalancete], grupos: dict[Chave, GrupoExtrato]):
    """{código da conta: (chave do grupo, por_sufixo) ou texto com o motivo}."""
    casamentos: dict[str, tuple[Chave, bool] | str] = {}
    livres = set(grupos)

    # 1) Casamento exato. Se a mesma chave aparecer em duas linhas do
    #    balancete, o extrato vai só para a primeira (nunca é contado duas vezes).
    dono: dict[Chave, ContaBalancete] = {}
    for conta in contas:
        if not conta.banco:
            continue
        chave = (conta.banco, conta.tipo, conta.conta)
        if chave in dono:
            casamentos[conta.codigo] = (f"mesma conta da linha de código {dono[chave].codigo} "
                                        f"do balancete; extrato atribuído a ela")
            continue
        dono[chave] = conta
        if chave in grupos:
            casamentos[conta.codigo] = (chave, False)
            livres.discard(chave)

    # 2) Casamento por sufixo, só entre as contas e os extratos que sobraram.
    pendentes = [c for c in contas if c.banco and c.codigo not in casamentos]
    candidatos = {c.codigo: [k for k in livres if _casa_por_sufixo(c, k)] for c in pendentes}
    for conta in pendentes:
        opcoes = candidatos[conta.codigo]
        if len(opcoes) != 1:
            continue
        chave = opcoes[0]
        disputas = [codigo for codigo, lista in candidatos.items() if chave in lista]
        if len(disputas) == 1:
            casamentos[conta.codigo] = (chave, True)
    return casamentos


def _casa_por_sufixo(conta: ContaBalancete, chave: Chave) -> bool:
    banco, tipo, numero = chave
    if (banco, tipo) != (conta.banco, conta.tipo):
        return False
    menor, maior = sorted((conta.conta, numero), key=len)
    return len(menor) >= MINIMO_SUFIXO and maior.endswith(menor)


def _nomes(saldos: list[SaldoExtraido]) -> str:
    return ", ".join(s.arquivo.name if s.arquivo else s.modelo for s in saldos)
