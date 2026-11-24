"""Aba Emails do Check list de contratos -> Contatos. Seção 3.2 da especificação.

Copiado do checklist_contratos (leitor_checklist.py), porque um módulo nunca importa outro:
- o Check list pode estar aberto no Excel de alguém: é copiado para uma pasta temporária e a cópia é
  lida (o original nunca é aberto pelo openpyxl nem alterado);
- uma pessoa por célula, "Nome (Apelido) <email>", "<email>" ou só o e-mail; a célula à direita tem os
  números que ela recebe. Célula fora desses formatos vira aviso.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import openpyxl

from modulos.notas_pendentes import configuracao as cfg
from modulos.notas_pendentes.modelos import Aviso, Contato, Contatos, ErroLeitura
from modulos.notas_pendentes.normalizacao import normalizar


def texto_da_celula(valor) -> str:
    """Número 21 -> "21"; texto com espaço sobrando -> sem as pontas."""
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return str(valor).strip()


def _contato(texto: str) -> tuple[str, str] | None:
    """"Nome <email>", "<email>" ou só o e-mail -> (nome, e-mail); None se não for nenhum dos três."""
    achado = cfg.RE_CONTATO.match(texto)
    if achado:
        return achado.group(1).strip(), achado.group(2).strip().lower()
    achado = cfg.RE_EMAIL_SOZINHO.match(texto)
    if achado:
        return "", achado.group(1).strip().lower()
    return None


def codigos_da_celula(texto: str) -> tuple[list[str], list[str]]:
    """"11; 12; 13" / "Todos" / "6; Cópia" -> (códigos, partes não reconhecidas)."""
    codigos, invalidos = [], []
    for parte in cfg.RE_SEPARADOR_CODIGOS.split(texto.strip()):
        normalizada = normalizar(parte)
        if not normalizada:
            continue
        if normalizada.isdigit():
            codigos.append(str(int(normalizada)))
        elif normalizada in (cfg.CODIGO_TODOS, cfg.CODIGO_TODOS_CMD, cfg.CODIGO_COPIA, cfg.CODIGO_COPIA_CMD):
            codigos.append(normalizada)
        else:
            invalidos.append(parte.strip())
    return codigos, invalidos


def _ler_contatos(planilha, avisos: list[Aviso]) -> list[Contato]:
    """Uma pessoa por célula; a célula logo à direita tem os números que ela recebe."""
    contatos = []
    for linha in planilha[cfg.ABA_EMAILS].iter_rows():
        ao_lado = None
        for celula in linha:
            texto = texto_da_celula(celula.value)
            origem = f"{cfg.ABA_EMAILS} {celula.coordinate}"
            if (celula.row, celula.column) == ao_lado:
                codigos, invalidos = codigos_da_celula(texto)
                contatos[-1].codigos = tuple(codigos)
                if invalidos:
                    avisos.append(Aviso(origem, f"\"{', '.join(invalidos)}\" não é um número de responsável, "
                                                "\"Todos\", \"Todos CMD\", \"Cópia\" nem \"Cópia CMD\": ignorado."))
                continue
            if not texto:
                continue
            achado = _contato(texto)
            if not achado:
                avisos.append(Aviso(origem, f"\"{texto}\" não está no formato Nome <email>: célula ignorada."))
                continue
            nome, email = achado
            apelido = cfg.RE_APELIDO.search(nome)
            contatos.append(Contato(nome, email, apelido.group(1).strip() if apelido else "",
                                    celula=celula.coordinate))
            ao_lado = (celula.row, celula.column + 1)
    for contato in contatos:
        if not contato.codigos:
            avisos.append(Aviso(f"{cfg.ABA_EMAILS} {contato.celula}",
                                f"{contato.email} não tem número ao lado: não recebe nenhum e-mail."))
    return contatos


def copiar_para_ler(caminho: Path, pasta_temporaria: Path) -> Path:
    """Copia o Check list para ler sem prender o arquivo da rede (pode estar aberto no Excel)."""
    copia = Path(pasta_temporaria) / Path(caminho).name
    try:
        shutil.copyfile(caminho, copia)
    except FileNotFoundError:
        raise ErroLeitura(f"Arquivo não encontrado: {caminho}") from None
    except OSError as erro:
        raise ErroLeitura("Não foi possível ler o Check list: ele pode estar bloqueado por outro "
                          f"programa. Feche-o e tente de novo. ({erro})") from None
    return copia


def ler_contatos(caminho: Path) -> Contatos:
    """Lê a aba Emails do Check list. Levanta ErroLeitura com mensagem para o usuário."""
    caminho = Path(caminho)
    with tempfile.TemporaryDirectory(prefix="notas_pendentes_") as pasta:
        copia = copiar_para_ler(caminho, Path(pasta))
        try:
            planilha = openpyxl.load_workbook(copia, data_only=True)
        except Exception as erro:
            raise ErroLeitura(f"O arquivo não pôde ser aberto como planilha do Excel: {erro}") from None
        try:
            if cfg.ABA_EMAILS not in planilha.sheetnames:
                raise ErroLeitura(f"O Check list não tem a aba \"{cfg.ABA_EMAILS}\": sem ela os e-mails não "
                                  "têm destinatário.")
            avisos: list[Aviso] = []
            contatos = _ler_contatos(planilha, avisos)
        finally:
            planilha.close()
    return Contatos(caminho.name, contatos, avisos)
