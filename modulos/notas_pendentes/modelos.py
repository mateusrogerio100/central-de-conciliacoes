"""Estruturas de dados do módulo Notas Pendentes."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


class ErroLeitura(Exception):
    """Problema que impede ler uma entrada; a mensagem é para o usuário."""


@dataclass
class Aviso:
    """Algo que o usuário precisa saber e que não impede o resto (aba "Avisos" do relatório)."""

    origem: str            # arquivo ou "Emails A5"
    mensagem: str


@dataclass
class ArquivoNota:
    """Um PDF da pasta do mês (L1 a L4)."""

    caminho: Path
    numero: str            # número do responsável ("13"); "" = sem número (L2)
    nota: str = ""         # nº da nota, tirado do nome (L3); "" = nome fora do padrão
    fornecedor: str = ""
    tamanho: int = 0       # bytes

    @property
    def nome(self) -> str:
        return self.caminho.name

    @property
    def descricao(self) -> str:
        """"NF 4615 – Fornecedor Exemplo Ltda" (L3); fora do padrão, o nome do arquivo."""
        if self.nota:
            return f"NF {self.nota} – {self.fornecedor}"
        return self.nome


@dataclass
class ArquivoIgnorado:
    """Arquivo da pasta que não entra em e-mail nenhum por não ser PDF (L5)."""

    nome: str
    motivo: str


@dataclass
class PastaNotas:
    """A pasta do mês lida: os PDFs (com e sem número), os outros arquivos e os avisos."""

    pasta: Path
    notas: list[ArquivoNota] = field(default_factory=list)
    ignorados: list[ArquivoIgnorado] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)

    def por_numero(self) -> dict[str, list[ArquivoNota]]:
        """Os PDFs com número, agrupados por ele, na ordem numérica."""
        grupos: dict[str, list[ArquivoNota]] = {}
        for nota in self.notas:
            if nota.numero:
                grupos.setdefault(nota.numero, []).append(nota)
        return dict(sorted(grupos.items(), key=lambda item: int(item[0])))

    @property
    def sem_numero(self) -> list[ArquivoNota]:
        return [n for n in self.notas if not n.numero]


@dataclass
class Contato:
    """Uma pessoa da aba Emails: "Nome (Apelido) <email>" e, ao lado, os números que ela recebe."""

    nome: str                  # como está, com o apelido entre parênteses ("" = só o e-mail)
    email: str                 # minúsculo
    apelido: str = ""          # o que estava entre parênteses
    codigos: tuple[str, ...] = ()   # "13", "todos", "todos cmd"
    celula: str = ""           # "A5", para os avisos


@dataclass
class Contatos:
    """A aba Emails lida."""

    arquivo: str
    contatos: list[Contato] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)


@dataclass
class Email:
    """Um e-mail pronto: um por número de responsável (E1)."""

    numero: str
    para: list[str]
    assunto: str
    corpo: str                 # texto, já com os marcadores trocados
    anexos: list[ArquivoNota]
    copia: list[str] = field(default_factory=list)   # E2: os contatos com "Cópia" (Cc)

    @property
    def tamanho(self) -> int:
        return sum(a.tamanho for a in self.anexos)


@dataclass
class SemEmail:
    """Notas que não vão em e-mail nenhum, com o motivo (E2, E5, L2)."""

    numero: str                # "" = sem número
    notas: list[ArquivoNota]
    motivo: str
    situacao: str              # texto da coluna Situação do relatório


@dataclass
class EmailsDoMes:
    """Os e-mails montados, as notas sem e-mail e os avisos de todas as entradas."""

    emails: list[Email] = field(default_factory=list)
    sem_email: list[SemEmail] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)


@dataclass
class ModeloEmail:
    """O modelo do e-mail (3.3): assunto e corpo ainda com os marcadores."""

    assunto: str
    corpo: str
    origem: str                # caminho do arquivo lido, ou "modelo de fábrica"
    de_fabrica: bool = False
    avisos: list[Aviso] = field(default_factory=list)
