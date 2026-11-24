"""
Comparação Ativo x Passivo do Imobilizado – AME's (ESPECIFICACAO_IMOBILIZADO.md, seção 6).

Pedido do usuário (05/11/2026). Dois razões contábeis do Tasy (relatório "Razão", rodapé WEXE002),
um com as contas do Ativo (classificação 1.x) e outro com as do Passivo (2.x). Cada conta do Ativo
tem uma "irmã" no Passivo com o mesmo saldo; o nome é parecido, mas não igual:

    1.02.05.10.0001  Aparelhos de Informatica  - AME Cidade Gama
    2.02.12.01.0001  Gestão Imobilizado Publico AmeC Aparelhos de Informatica

e o número da conta nem sempre ajuda (1.02.06.10.0001 Direito de uso de software ↔ 2.02.12.01.0006).

Como o par é achado:
1. só dentro do mesmo grupo: o 2º nível da classificação (1.02 ↔ 2.02, 1.05 ↔ 2.05);
2. pelo "tipo do bem" que sobra no nome depois de tirar acentos, maiúsculas, plural e as palavras que
   não dizem o tipo (Gestão, Imobilizado, Público, Cessão, Uso, "AME", "AmeC", o nome da cidade do AME...);
3. o valor NUNCA é usado para achar o par (senão a conta com diferença ficaria sem par): só é comparado
   depois. Nome sem par claro (nenhum, ou mais de um) → "Sem par — verificar". O programa não chuta.

O saldo de cada conta é o da coluna "Saldo": o último da conta (sem lançamento, o "Saldo anterior").
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from modulos.conciliacao_imobilizado.base_iss import NIVEL_AVISO, NIVEL_ERRO, NIVEL_OK, Aviso
from modulos.conciliacao_imobilizado.leitor_texto import (
    ArquivoIlegivel,
    Cabecalho,
    NOMES_RELATORIOS,
    competencia_de_data,
    competencia_por_extenso,
    data,
    eh_rodape,
    identificar_relatorio,
    juntar_espacos,
    ler_linhas,
    nome_curto_ame,
    preenchidas,
    reais,
    valor,
)

LADO_ATIVO = "Ativo"
LADO_PASSIVO = "Passivo"

SITUACAO_AP_CONFERE = "Confere"
SITUACAO_AP_DIFERENCA = "Diferença — verificar"
SITUACAO_AP_SEM_PAR = "Sem par — verificar"
ORDEM_SITUACOES_AP = [SITUACAO_AP_CONFERE, SITUACAO_AP_DIFERENCA, SITUACAO_AP_SEM_PAR]

TIPO_ARQUIVO_RAZAO = "Razão contábil"
NOME_RAZAO_CONTABIL = "o Razão contábil do Tasy (relatório \"Razão\")"

# Palavras que não dizem o tipo do bem (comparadas já sem acento e em minúsculas)
PALAVRAS_IGNORADAS = {
    "de", "da", "do", "das", "dos", "e", "a", "o", "em",
    "gestao", "imobilizado", "publico", "cessao", "uso", "ame",
}
# "AmeC", "AmeRP", "AmeSJ"...: a sigla do AME colada no "Ame"
_REGEX_SIGLA_AME = re.compile(r"^ame[a-z]{1,3}$")
_REGEX_CONTA = re.compile(r"^(\d+)\s*-\s*(\d+(?:\.\d+)+)\s+(.+)$")
_REGEX_TOTAL = re.compile(r"^Total\s*\((\d+)\)", re.IGNORECASE)
_RODAPE_RAZAO = "wctb938"


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------


@dataclass
class ContaRazao:
    codigo: str                      # "12425"
    classificacao: str               # "1.02.05.10.0001"
    nome: str                        # "Aparelhos de Informatica - AME Cidade Gama"
    saldo: Decimal | None = None     # o último da coluna Saldo
    lancamentos: int = 0             # linhas com valor depois do saldo anterior

    @property
    def lado(self) -> str:
        return LADO_ATIVO if self.classificacao.startswith("1") else LADO_PASSIVO

    @property
    def grupo(self) -> str:
        """2º nível da classificação: "1.02.05.10.0001" → "02"."""
        partes = self.classificacao.split(".")
        return partes[1] if len(partes) > 1 else ""

    @property
    def descricao(self) -> str:
        return f"{self.classificacao} {self.nome}"


@dataclass
class LeituraRazaoContabil:
    arquivo: str
    ame: str = ""
    inicio: date | None = None
    fim: date | None = None
    contas: list[ContaRazao] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)      # ATENÇÃO de leitura (o arquivo foi lido)

    @property
    def competencia(self) -> str:
        return competencia_de_data(self.inicio)

    @property
    def lado(self) -> str:
        """Ativo, Passivo, "misturado" ou "" (sem contas)."""
        lados = {c.lado for c in self.contas}
        if len(lados) == 1:
            return lados.pop()
        return "misturado" if lados else ""


@dataclass
class ParAtivoPassivo:
    grupo: str
    ativo: ContaRazao | None
    passivo: ContaRazao | None
    situacao: str
    observacao: str = ""

    @property
    def saldo_ativo(self) -> Decimal | None:
        return None if self.ativo is None else self.ativo.saldo

    @property
    def saldo_passivo(self) -> Decimal | None:
        return None if self.passivo is None else self.passivo.saldo

    @property
    def diferenca(self) -> Decimal | None:
        """Ativo − Passivo (conta sem par: o lado que existe, com o sinal do lado)."""
        return (self.saldo_ativo or Decimal("0")) - (self.saldo_passivo or Decimal("0"))

    @property
    def nome_grupo(self) -> str:
        return f"1.{self.grupo} × 2.{self.grupo}" if self.grupo else ""


@dataclass
class ResultadoAtivoPassivo:
    ame: str = ""
    competencia: str = ""
    arquivo_ativo: str = ""
    arquivo_passivo: str = ""
    pares: list[ParAtivoPassivo] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)
    caminho_relatorio: Path | None = None
    erro: str = ""

    @property
    def competencia_texto(self) -> str:
        return competencia_por_extenso(self.competencia)

    def total(self, campo: str) -> Decimal:
        return sum((getattr(p, campo) or Decimal("0") for p in self.pares), Decimal("0"))

    def contar(self, situacao: str) -> int:
        return sum(1 for p in self.pares if p.situacao == situacao)


# ---------------------------------------------------------------------------
# Leitura do razão contábil
# ---------------------------------------------------------------------------


def eh_razao_contabil(linhas) -> bool:
    texto = " ".join(c for linha in linhas[:80] for c in linha if c).casefold()
    if _RODAPE_RAZAO in texto:
        return True
    tem_titulo = any(preenchidas(l)[:1] == ["Razão"] for l in linhas[:10])
    return tem_titulo and "saldo anterior" in texto


def ler_razao_contabil(caminho: Path) -> LeituraRazaoContabil:
    """Lê um razão contábil do Tasy. Arquivo ilegível ou de outro relatório → ArquivoIlegivel."""
    caminho = Path(caminho)
    linhas = ler_linhas(caminho)
    if not eh_razao_contabil(linhas):
        outro = identificar_relatorio(linhas)
        if outro is not None:
            raise ArquivoIlegivel(f"Este arquivo é {NOMES_RELATORIOS[outro]}, não {NOME_RAZAO_CONTABIL}. "
                                  "Ele é usado na aba \"Conciliação\".")
        raise ArquivoIlegivel(f"Este arquivo não parece ser {NOME_RAZAO_CONTABIL}. "
                              "Confira se escolheu o relatório certo do Tasy.")

    leitura = LeituraRazaoContabil(arquivo=caminho.name)
    cabecalho: Cabecalho | None = None
    conta: ContaRazao | None = None
    total_informado: int | None = None

    for linha in linhas:
        celulas = preenchidas(linha)
        if not celulas or eh_rodape(linha):
            continue
        if not leitura.ame and any(c.startswith("Livro:") for c in celulas[1:]):
            leitura.ame = juntar_espacos(celulas[0])
            continue
        if "Período:" in celulas:
            datas = [d for d in (data(c) for c in celulas) if d is not None]
            if datas:
                leitura.inicio, leitura.fim = datas[0], datas[-1]
            continue
        auxiliar = Cabecalho(linha)
        if auxiliar.tem("Saldo", "Débitos", "Créditos"):
            cabecalho = auxiliar         # repete a cada página (as colunas podem mudar de lugar)
            continue
        total = _REGEX_TOTAL.match(celulas[0])
        if total:
            total_informado = int(total.group(1))
            conta = None
            continue
        nova = _REGEX_CONTA.match(celulas[0])
        if nova and len(celulas) == 1:
            conta = ContaRazao(codigo=nova.group(1), classificacao=nova.group(2),
                               nome=juntar_espacos(nova.group(3)))
            leitura.contas.append(conta)
            continue
        if conta is None or cabecalho is None:
            continue
        texto_saldo = cabecalho.valor(linha, "Saldo")
        if not texto_saldo:
            continue
        try:
            saldo = valor(texto_saldo)
        except ValueError:
            leitura.avisos.append(f"conta {conta.classificacao}: saldo ilegível ({texto_saldo!r})")
            continue
        if saldo is None:
            continue
        if not any(c.casefold().startswith("saldo anterior") for c in celulas):
            conta.lancamentos += 1
        conta.saldo = saldo

    for sem_saldo in (c for c in leitura.contas if c.saldo is None):
        leitura.avisos.append(f"conta {sem_saldo.classificacao} sem saldo")
    if total_informado is not None and total_informado != len(leitura.contas):
        leitura.avisos.append(f"o relatório diz {total_informado} contas e foram lidas {len(leitura.contas)}")
    if not leitura.contas:
        raise ArquivoIlegivel("Nenhuma conta encontrada no razão. Confira se escolheu o relatório certo.")
    return leitura


# ---------------------------------------------------------------------------
# Casamento dos nomes
# ---------------------------------------------------------------------------


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def _singular(palavra: str) -> str:
    return palavra[:-1] if len(palavra) > 3 and palavra.endswith("s") else palavra


def palavras_da_cidade(ame: str) -> set[str]:
    """"AME - Cidade Gama (Fund. ...)" → {"cidade_gama"}; "Ame - São José do Rio Preto" → {"sao", "jose", "rio", "preto"}."""
    curto = _sem_acento(nome_curto_ame(ame)).casefold()
    return {p for p in re.findall(r"[a-z0-9]+", curto)} - PALAVRAS_IGNORADAS


def chave_do_nome(nome: str, cidade: set[str] = frozenset()) -> frozenset[str]:
    """O "tipo do bem" do nome: "Gestão Imobilizado Publico AmeC Aparelhos de Informatica" →
    {"aparelho", "informatica"}."""
    palavras = re.findall(r"[a-z0-9]+", _sem_acento(nome).casefold())
    return frozenset(
        _singular(p) for p in palavras
        if p not in PALAVRAS_IGNORADAS and p not in cidade and not _REGEX_SIGLA_AME.match(p)
    )


def casar_contas(ativo: list[ContaRazao], passivo: list[ContaRazao], ame: str = "") -> list[ParAtivoPassivo]:
    """Pares por grupo e pelo tipo do bem; na ordem do Ativo, e as contas sem par do Passivo no fim."""
    cidade = palavras_da_cidade(ame)

    def indice(contas):
        mapa: dict[tuple[str, frozenset], list[ContaRazao]] = {}
        for conta in contas:
            mapa.setdefault((conta.grupo, chave_do_nome(conta.nome, cidade)), []).append(conta)
        return mapa

    do_ativo, do_passivo = indice(ativo), indice(passivo)
    pares: list[ParAtivoPassivo] = []
    usadas_passivo: set[int] = set()

    for conta in ativo:
        chave = (conta.grupo, chave_do_nome(conta.nome, cidade))
        candidatas = do_passivo.get(chave, [])
        if not chave[1]:
            pares.append(ParAtivoPassivo(conta.grupo, conta, None, SITUACAO_AP_SEM_PAR,
                                         "o nome não tem o tipo do bem"))
        elif len(do_ativo[chave]) > 1 or len(candidatas) > 1:
            pares.append(ParAtivoPassivo(conta.grupo, conta, None, SITUACAO_AP_SEM_PAR,
                                         "mais de uma conta com o mesmo nome: confira à mão"))
        elif not candidatas:
            pares.append(ParAtivoPassivo(conta.grupo, conta, None, SITUACAO_AP_SEM_PAR,
                                         "nenhuma conta do Passivo com esse nome no mesmo grupo"))
        else:
            irma = candidatas[0]
            usadas_passivo.add(id(irma))
            igual = conta.saldo is not None and conta.saldo == irma.saldo
            pares.append(ParAtivoPassivo(conta.grupo, conta, irma,
                                         SITUACAO_AP_CONFERE if igual else SITUACAO_AP_DIFERENCA))

    for conta in passivo:
        if id(conta) in usadas_passivo:
            continue
        chave = (conta.grupo, chave_do_nome(conta.nome, cidade))
        if not chave[1]:
            motivo = "o nome não tem o tipo do bem"
        elif len(do_passivo[chave]) > 1 or len(do_ativo.get(chave, [])) > 1:
            motivo = "mais de uma conta com o mesmo nome: confira à mão"
        else:
            motivo = "nenhuma conta do Ativo com esse nome no mesmo grupo"
        pares.append(ParAtivoPassivo(conta.grupo, None, conta, SITUACAO_AP_SEM_PAR, motivo))
    return pares


# ---------------------------------------------------------------------------
# Prévia (cartão da tela) e processamento completo
# ---------------------------------------------------------------------------


@dataclass
class PreviaRazaoContabil:
    descricao: str = ""
    erro: str = ""
    avisos: list[str] = field(default_factory=list)


def previa_razao_contabil(caminho: Path, lado_esperado: str) -> PreviaRazaoContabil:
    """"AME - Cidade Gama · outubro/2026 · 10 contas"; razão do outro lado → erro."""
    try:
        leitura = ler_razao_contabil(caminho)
    except ArquivoIlegivel as erro:
        return PreviaRazaoContabil(erro=str(erro))
    erro = _erro_de_lado(leitura, lado_esperado)
    if erro:
        return PreviaRazaoContabil(erro=erro)
    partes = [nome_curto_ame(leitura.ame), competencia_por_extenso(leitura.competencia),
              f"{len(leitura.contas)} conta{'s' if len(leitura.contas) != 1 else ''}"]
    return PreviaRazaoContabil(descricao=" · ".join(p for p in partes if p), avisos=list(leitura.avisos))


def _erro_de_lado(leitura: LeituraRazaoContabil, esperado: str) -> str:
    if leitura.lado == esperado:
        return ""
    if leitura.lado == "misturado":
        return (f"Este razão tem contas do Ativo (1.x) e do Passivo (2.x) juntas. "
                f"Tire do Tasy um razão só com as contas do {esperado}.")
    outro = LADO_PASSIVO if esperado == LADO_ATIVO else LADO_ATIVO
    return f"Este razão é do {outro} (contas {'2' if outro == LADO_PASSIVO else '1'}.x). Escolha-o no cartão \"Razão do {outro}\"."


def comparar_ativo_passivo(arquivo_ativo: Path, arquivo_passivo: Path) -> ResultadoAtivoPassivo:
    """Lê os dois razões e casa as contas (não grava nada; nunca levanta exceção)."""
    resultado = ResultadoAtivoPassivo(arquivo_ativo=Path(arquivo_ativo).name,
                                      arquivo_passivo=Path(arquivo_passivo).name)
    leituras: dict[str, LeituraRazaoContabil] = {}
    for lado, caminho in ((LADO_ATIVO, arquivo_ativo), (LADO_PASSIVO, arquivo_passivo)):
        nome = Path(caminho).name
        try:
            leitura = ler_razao_contabil(caminho)
            erro = _erro_de_lado(leitura, lado)
            if erro:
                raise ArquivoIlegivel(erro)
        except ArquivoIlegivel as erro:
            resultado.avisos.append(Aviso(nome, str(erro), NIVEL_ERRO, TIPO_ARQUIVO_RAZAO))
            continue
        except Exception as erro:       # rede de segurança: um arquivo nunca derruba o processamento
            resultado.avisos.append(Aviso(nome, f"Erro inesperado ao ler o arquivo: {erro}", NIVEL_ERRO,
                                          TIPO_ARQUIVO_RAZAO))
            continue
        leituras[lado] = leitura
        resumo = f"OK · {len(leitura.contas)} contas do {lado}"
        resultado.avisos.append(Aviso(nome, resumo, NIVEL_OK, TIPO_ARQUIVO_RAZAO, unidades=leitura.ame))
        for texto in leitura.avisos:
            resultado.avisos.append(Aviso(nome, f"Atenção: {texto}.", NIVEL_AVISO))

    if len(leituras) < 2:
        resultado.erro = "Não foi possível comparar: um dos razões não pôde ser lido (veja os avisos)."
        return resultado

    ativo, passivo = leituras[LADO_ATIVO], leituras[LADO_PASSIVO]
    resultado.ame = nome_curto_ame(ativo.ame or passivo.ame)
    resultado.competencia = ativo.competencia or passivo.competencia
    if nome_curto_ame(ativo.ame).casefold() != nome_curto_ame(passivo.ame).casefold():
        resultado.avisos.append(Aviso(passivo.arquivo, f"Os razões são de AMEs diferentes: "
                                      f"{nome_curto_ame(ativo.ame)} (Ativo) e {nome_curto_ame(passivo.ame)} (Passivo).",
                                      NIVEL_AVISO))
    if (ativo.inicio, ativo.fim) != (passivo.inicio, passivo.fim):
        resultado.avisos.append(Aviso(passivo.arquivo, "Os razões são de períodos diferentes: "
                                      f"{_periodo(ativo)} (Ativo) e {_periodo(passivo)} (Passivo).", NIVEL_AVISO))
    resultado.pares = casar_contas(ativo.contas, passivo.contas, ativo.ame or passivo.ame)
    return resultado


def _periodo(leitura: LeituraRazaoContabil) -> str:
    if leitura.inicio is None:
        return "sem período"
    return f"{leitura.inicio:%d/%m/%Y} a {leitura.fim:%d/%m/%Y}"


def mensagem_do_par(par: ParAtivoPassivo) -> str:
    """Uma linha para a tela: "Equipamentos hospitalares: diferença de 69.500,00"."""
    conta = par.ativo or par.passivo
    nome = conta.nome if conta else ""
    if par.situacao == SITUACAO_AP_SEM_PAR:
        return f"{conta.descricao} ({conta.lado}): sem par — {par.observacao}"
    return f"{nome}: diferença de {reais(par.diferenca)} (Ativo {reais(par.saldo_ativo)} × Passivo {reais(par.saldo_passivo)})"

