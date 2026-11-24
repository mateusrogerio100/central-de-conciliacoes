"""Pasta das notas do mês -> PastaNotas. Seção 3.1 e regras L1 a L5 da especificação.

- Só os arquivos da própria pasta; subpasta vira aviso (não é lida).
- Só .pdf entram nos e-mails; outro tipo vira aviso; temporário do Office (~$...) é ignorado sem aviso.
- O número do responsável e os dados da nota vêm do NOME do arquivo: o PDF não é aberto.
- A pasta nunca é alterada.
"""

from __future__ import annotations

from pathlib import Path

from modulos.notas_pendentes import configuracao as cfg
from modulos.notas_pendentes.modelos import ArquivoIgnorado, ArquivoNota, Aviso, ErroLeitura, PastaNotas


def dados_do_nome(nome_sem_extensao: str) -> tuple[str, str, str]:
    """L1 e L3: "13.DANFSe-22-Fornecedor-3553...": ("13", "22", "Fornecedor"); sem número: ("", "", "")."""
    achado = cfg.RE_NUMERO_ARQUIVO.match(nome_sem_extensao)
    if not achado:
        return "", "", ""
    numero = str(int(achado.group(1)))
    nota = cfg.RE_NOME_NOTA.match(achado.group(2))
    if not nota:
        return numero, "", ""
    return numero, nota.group(1), nota.group(2)


def ler_pasta(pasta: Path) -> PastaNotas:
    """Lê a pasta do mês. Levanta ErroLeitura se a pasta não existe ou não pode ser lida."""
    pasta = Path(pasta)
    if not pasta.is_dir():
        raise ErroLeitura(f"Pasta não encontrada: {pasta}")
    try:
        itens = sorted(pasta.iterdir(), key=lambda p: p.name.casefold())
    except OSError as erro:
        raise ErroLeitura(f"Não foi possível ler a pasta {pasta}: {erro}") from None

    resultado = PastaNotas(pasta)
    for item in itens:
        if item.is_dir():
            resultado.avisos.append(Aviso(item.name, "Subpasta: os arquivos dela não são lidos."))
            continue
        if item.name.startswith(cfg.PREFIXO_TEMPORARIO):
            continue
        if item.suffix.lower() != cfg.EXTENSAO_PDF:
            motivo = "Não é PDF: não vai em e-mail nenhum."
            resultado.ignorados.append(ArquivoIgnorado(item.name, motivo))
            resultado.avisos.append(Aviso(item.name, motivo))
            continue
        numero, nota, fornecedor = dados_do_nome(item.stem)
        try:
            tamanho = item.stat().st_size
        except OSError as erro:
            tamanho = 0
            resultado.avisos.append(Aviso(item.name, f"Não foi possível ver o tamanho do arquivo: {erro}"))
        resultado.notas.append(ArquivoNota(item, numero, nota, fornecedor, tamanho))
        if not numero:
            resultado.avisos.append(Aviso(item.name, "O nome não começa com o número do responsável: "
                                                     "a nota não vai em e-mail nenhum."))
    return resultado
