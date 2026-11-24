"""Leitura do SPED do mês anterior (o molde) — ESPECIFICACAO_EFD_CONTRIBUICOES.md, seções 2.1, 3 e R10.

Copiado de `gerar_sped_mensal.py` da aplicação Automacao-Notas-Fiscais-EFD (ler_registros_sped, campos,
montar_linha e a classe SpedMensal). O que mudou: o arquivo que não é SPED vira ErroSped com mensagem para a tela;
o molde também guarda a competência (0000), os 0150 e os A100 (para a prévia e para o teste da regra de ouro);
registro fixo que falta no molde vira erro (na origem, ficava None e quebrava na hora de gravar).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from modulos.efd_contribuicoes import configuracao

FIXOS_BLOCO0 = ("0001", "0100", "0110", "0140", "0200")
FIXOS_BLOCOA = ("A001", "A010")
FIXOS_FECHAMENTO = (
    "C001", "C990", "D001", "D990", "F001", "F990", "I001", "I990",
    "M001", "M200", "M600", "M990", "P001", "P990", "1001", "1990", "9001",
)


class ErroSped(Exception):
    """O arquivo não pôde ser lido como SPED (mensagem para a tela)."""


def campos(linha: str) -> list[str]:
    """'|A|B|C|' -> ['A','B','C'] (remove a barra inicial/final vazias)."""
    partes = linha.split("|")
    return partes[1:-1]


def montar_linha(lista_campos) -> str:
    return "|" + "|".join(lista_campos) + "|"


def ler_registros_sped(caminho: Path) -> list[str]:
    """Linhas de |0000| até |9999| (inclusive); o que vem depois (a assinatura) é ignorado."""
    caminho = Path(caminho)
    try:
        with open(caminho, encoding=configuracao.CODIFICACAO_SPED, newline="") as f:
            conteudo = f.read()
    except OSError as erro:
        raise ErroSped(f"{caminho.name}: não foi possível abrir o arquivo ({erro.strerror or erro}).")
    todas = [l for l in conteudo.split(configuracao.QUEBRA_LINHA_SPED) if l]
    if not todas or not todas[0].startswith("|0000|"):
        raise ErroSped(f"{caminho.name}: não parece ser um arquivo SPED (a 1ª linha não é o registro 0000).")
    try:
        idx_9999 = next(i for i, l in enumerate(todas) if l.startswith("|9999|"))
    except StopIteration:
        raise ErroSped(f"{caminho.name}: arquivo SPED sem o registro 9999 (incompleto).")
    return todas[: idx_9999 + 1]


@dataclass
class MoldeSped:
    """O SPED do mês anterior: os registros fixos e o que serve para a prévia (era a SpedMensal da origem)."""
    arquivo: str
    linhas_originais: list[str]
    linha_0000: str = ""
    fixos: dict[str, str] = field(default_factory=dict)
    linhas_0150: list[str] = field(default_factory=list)
    linhas_a100: list[str] = field(default_factory=list)
    linhas_a170: list[str] = field(default_factory=list)
    ordem_9900: list[str] = field(default_factory=list)

    @property
    def inicio(self) -> date | None:
        """DT_INI do 0000 (campo 6, formato DDMMAAAA)."""
        return _data(campos(self.linha_0000)[5]) if self.linha_0000 else None

    @property
    def competencia(self) -> str:
        """"08/2026" (do DT_INI)."""
        inicio = self.inicio
        return "" if inicio is None else f"{inicio.month:02d}/{inicio.year}"

    @property
    def competencia_seguinte(self) -> str:
        inicio = self.inicio
        if inicio is None:
            return ""
        ano, mes = (inicio.year + 1, 1) if inicio.month == 12 else (inicio.year, inicio.month + 1)
        return f"{mes:02d}/{ano}"


def _data(texto: str) -> date | None:
    try:
        return date(int(texto[4:8]), int(texto[2:4]), int(texto[0:2]))
    except (ValueError, IndexError):
        return None


def ler_molde(caminho: Path) -> MoldeSped:
    """Lê o SPED do mês anterior. Arquivo inválido ou sem algum registro fixo → ErroSped."""
    caminho = Path(caminho)
    linhas = ler_registros_sped(caminho)
    molde = MoldeSped(arquivo=caminho.name, linhas_originais=linhas, linha_0000=linhas[0])
    if molde.inicio is None:
        raise ErroSped(f"{caminho.name}: o registro 0000 não tem uma data inicial válida.")
    for linha in linhas:
        tipo = campos(linha)[0]
        if tipo in FIXOS_BLOCO0 + FIXOS_BLOCOA + FIXOS_FECHAMENTO and tipo not in molde.fixos:
            molde.fixos[tipo] = linha           # como na origem: vale o primeiro de cada tipo
        elif tipo == "0150":
            molde.linhas_0150.append(linha)
        elif tipo == "A100":
            molde.linhas_a100.append(linha)
        elif tipo == "A170":
            molde.linhas_a170.append(linha)
        elif tipo == "9900":
            molde.ordem_9900.append(campos(linha)[1])
    faltando = [t for t in FIXOS_BLOCO0 + FIXOS_BLOCOA + FIXOS_FECHAMENTO if t not in molde.fixos]
    if faltando:
        raise ErroSped(f"{caminho.name}: faltam no SPED os registros {', '.join(faltando)}; "
                       "use o SPED completo do mês anterior.")
    return molde


@dataclass
class PreviaSped:
    descricao: str = ""
    erro: str = ""
    competencia_seguinte: str = ""


def previa_sped(caminho: Path) -> PreviaSped:
    """"SPED de 08/2026 · 44 clientes · 49 notas" (para o cartão da tela)."""
    try:
        molde = ler_molde(caminho)
    except ErroSped as erro:
        return PreviaSped(erro=str(erro))
    return PreviaSped(
        descricao=f"SPED de {molde.competencia} · {len(molde.linhas_0150)} clientes · {len(molde.linhas_a100)} notas",
        competencia_seguinte=molde.competencia_seguinte,
    )
