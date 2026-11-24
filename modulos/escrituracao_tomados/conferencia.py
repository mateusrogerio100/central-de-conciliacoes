"""Notas já escrituradas na prefeitura (R9), a partir dos "resultados" exportados do site.

O resultado tem o mesmo formato das exportações de lotes (seção 4.2 da especificação):
.csv separado por ';' ou .txt separado por tabulação, latin-1, colunas localizadas pelo título.
Aqui só interessam o número da nota e o CNPJ/CPF do prestador: a chave de comparação é
número (sem zeros à esquerda) + CNPJ/CPF (só dígitos) — nunca só o número, porque há números
repetidos entre prestadores (ex.: 542 do prestador A e 542 do prestador B).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from modulos.escrituracao_tomados import configuracao as cfg
from modulos.escrituracao_tomados.gerador_txt import so_digitos
from modulos.escrituracao_tomados.modelos import ErroLeitura, FalhaLeitura

Chave = tuple[str, str]


def chave_nota(numero: str, documento: str) -> Chave:
    """(número sem zeros à esquerda, CNPJ/CPF só dígitos)."""
    return so_digitos(numero).lstrip("0") or "0", so_digitos(documento)


# ---------------------------------------------------------------------------
# Tabela exportada pelo site (.csv com ';' ou .txt com tabulação)
# ---------------------------------------------------------------------------


def _titulo(texto: str) -> str:
    return texto.strip().lower()


def _ler_texto(caminho: Path) -> str:
    try:
        dados = caminho.read_bytes()
    except OSError:
        raise ErroLeitura("Não foi possível abrir o arquivo (está aberto em outro programa?).") \
            from None
    try:
        return dados.decode("utf-8-sig")
    except UnicodeDecodeError:
        return dados.decode(cfg.CODIFICACAO_SITE)


def ler_tabela_do_site(caminho: Path, obrigatorias=cfg.SITE_COLUNAS_OBRIGATORIAS
                       ) -> list[tuple[int, dict[str, str]]]:
    """Linhas do arquivo como (número da linha, {título da coluna em minúsculas: valor}).

    Linhas em branco são puladas. Levanta ErroLeitura se o arquivo não abrir ou não tiver as
    colunas obrigatórias.
    """
    linhas = [(numero, linha) for numero, linha in
              enumerate(_ler_texto(Path(caminho)).splitlines(), start=1) if linha.strip()]
    if not linhas:
        raise ErroLeitura("O arquivo está vazio.")
    cabecalho = linhas[0][1]
    separador = "\t" if "\t" in cabecalho else ";"
    titulos = [_titulo(t) for t in cabecalho.split(separador)]
    faltando = [c for c in obrigatorias if c not in titulos]
    if faltando:
        raise ErroLeitura("O arquivo não parece uma exportação do site da prefeitura: faltam as "
                          f"colunas {', '.join(faltando)}.")
    registros = []
    for numero, linha in linhas[1:]:
        valores = linha.split(separador)
        registros.append((numero, {t: (valores[i].strip() if i < len(valores) else "")
                                   for i, t in enumerate(titulos) if t}))
    return registros


# ---------------------------------------------------------------------------
# Resultados (notas já escrituradas)
# ---------------------------------------------------------------------------


def numero_curto_equivale(numero_longo: str, numero_curto: str) -> bool:
    """O número curto é o FINAL inteiro do número longo, depois dos zeros.

    2026000003076 x 3076 -> sim; 2026000013076 x 3076 -> não (ali o número seria 13076).
    """
    longo = so_digitos(numero_longo)
    curto = so_digitos(numero_curto).lstrip("0")
    if not curto or len(curto) >= len(longo) or not longo.endswith(curto):
        return False
    return longo[-len(curto) - 1] == "0"


@dataclass
class NotasEscrituradas:
    """Chave (número + prestador) -> nome do primeiro arquivo de resultado em que aparece."""

    por_chave: dict[Chave, str] = field(default_factory=dict)
    falhas: list[FalhaLeitura] = field(default_factory=list)
    linhas_por_arquivo: dict[str, int] = field(default_factory=dict)
    # CNPJ/CPF -> [(número, valor do serviço, arquivo)], para as notas de número longo (R9)
    por_documento: dict[str, list[tuple[str, Decimal, str]]] = field(default_factory=dict)

    def arquivo_da_nota(self, numero: str, documento: str) -> str | None:
        return self.por_chave.get(chave_nota(numero, documento))

    def digitada_com_numero_curto(self, numero: str, documento: str, valor: Decimal
                                  ) -> tuple[str, str] | None:
        """Nota de número longo (mais de 8 dígitos) que alguém digitou no site com o número curto.

        Mesmo CNPJ/CPF, número do site = final do número longo e MESMO valor do serviço
        (decisão do usuário, 28/09/2026). Devolve (arquivo, número digitado) ou None.
        """
        if len(so_digitos(numero).lstrip("0")) <= 8:
            return None
        for numero_site, valor_site, arquivo in self.por_documento.get(so_digitos(documento), []):
            if valor_site == valor and numero_curto_equivale(numero, numero_site):
                return arquivo, numero_site.lstrip("0")
        return None


def _valor_do_site(texto: str) -> Decimal | None:
    """'28.579,02' -> Decimal('28579.02'); vazio ou fora do formato -> None."""
    limpo = (texto or "").strip()
    if not re.fullmatch(r"\d{1,3}(\.\d{3})*,\d{2}|\d+,\d{2}", limpo):
        return None
    return Decimal(limpo.replace(".", "").replace(",", "."))


def ler_resultados(arquivos: list[Path] | None) -> NotasEscrituradas:
    """Lê os "resultados" da prefeitura (qualquer login ou mês). Basta a nota existir num deles.

    Um arquivo com problema vira falha de leitura e os demais continuam.
    """
    escrituradas = NotasEscrituradas()
    for caminho in arquivos or []:
        caminho = Path(caminho)
        try:
            registros = ler_tabela_do_site(caminho)
        except ErroLeitura as erro:
            escrituradas.falhas.append(FalhaLeitura(caminho.name, str(erro)))
            continue
        contadas = 0
        for _, registro in registros:
            numero = so_digitos(registro.get(cfg.SITE_COLUNA_NUMERO, ""))
            documento = so_digitos(registro.get(cfg.SITE_COLUNA_DOCUMENTO, ""))
            if not numero or not documento:
                continue
            escrituradas.por_chave.setdefault(chave_nota(numero, documento), caminho.name)
            valor = _valor_do_site(registro.get(cfg.SITE_COLUNA_SERVICOS, ""))
            if valor is not None and len(numero.lstrip("0")) <= 8:
                escrituradas.por_documento.setdefault(documento, []).append(
                    (numero, valor, caminho.name))
            contadas += 1
        escrituradas.linhas_por_arquivo[caminho.name] = contadas
    return escrituradas
