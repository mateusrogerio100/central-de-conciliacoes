"""Check list (.xlsx) -> Checklist. Seção 3.2 e regra K1 da especificação.

- O arquivo pode estar aberto no Excel de alguém: é copiado para uma pasta temporária e a cópia é
  lida (o original nunca é aberto pelo openpyxl).
- Colunas achadas pelo título. A coluna do mês é a que tem a data do dia 1 do mês escolhido; a do
  mês anterior, do mesmo jeito (pode não existir: a aba do CMD não tem todos os meses).
- Aba Emails: uma pessoa por célula, "Nome (Apelido) <email>", "<email>" ou só o e-mail; a célula à
  direita tem os códigos dos responsáveis que ela recebe. Célula fora desses formatos vira aviso.
"""

from __future__ import annotations

import shutil
import tempfile
from datetime import date, datetime
from pathlib import Path

import openpyxl

from modulos.checklist_contratos import configuracao as cfg
from modulos.checklist_contratos.modelos import AbaChecklist, Aviso, Checklist, Contato, ErroLeitura, LinhaChecklist
from modulos.checklist_contratos.normalizacao import normalizar


def nome_do_mes(ano: int, mes: int) -> str:
    """(2026, 10) -> "out/26", como nas mensagens."""
    return f"{cfg.MESES_ABREVIADOS[mes - 1]}/{ano % 100:02d}"


def mes_anterior(ano: int, mes: int) -> tuple[int, int]:
    return (ano - 1, 12) if mes == 1 else (ano, mes - 1)


def texto_da_celula(valor) -> str:
    """Conta 30091 (número) -> "30091"; texto com espaço sobrando -> sem as pontas."""
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return str(valor).strip()


def _data_do_titulo(valor) -> date | None:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return None


def _coluna_pelo_titulo(titulos: dict[int, str], aceitos: tuple[str, ...], prefixo: bool = False) -> int | None:
    for aceito in aceitos:
        for coluna, titulo in titulos.items():
            if titulo == aceito or (prefixo and titulo.startswith(aceito)):
                return coluna
    return None


def _ler_aba(planilha, estabelecimento: str, ano: int, mes: int) -> AbaChecklist:
    nome = cfg.ABAS[estabelecimento]
    if nome not in planilha.sheetnames:
        raise ErroLeitura(f"O Check list não tem a aba \"{nome}\".")
    aba = planilha[nome]
    linhas = list(aba.iter_rows(values_only=True))
    if not linhas:
        raise ErroLeitura(f"A aba \"{nome}\" está vazia.")

    cabecalho = linhas[0]
    titulos = {i + 1: normalizar(v) for i, v in enumerate(cabecalho)
               if v is not None and _data_do_titulo(v) is None}
    datas = {i + 1: _data_do_titulo(v) for i, v in enumerate(cabecalho) if _data_do_titulo(v)}

    colunas = {
        "conta": _coluna_pelo_titulo(titulos, cfg.CHK_TITULOS_CONTA),
        "descricao_conta": _coluna_pelo_titulo(titulos, (cfg.CHK_TITULO_DESCRICAO_CONTA,)),
        "fornecedor": _coluna_pelo_titulo(titulos, (cfg.CHK_TITULO_FORNECEDOR,)),
        "descricao_despesa": _coluna_pelo_titulo(titulos, (cfg.CHK_TITULO_DESCRICAO_DESPESA,), prefixo=True),
        "responsavel": _coluna_pelo_titulo(titulos, (cfg.CHK_TITULO_RESPONSAVEL,)),
    }
    nomes_colunas = {"conta": "Conta", "descricao_conta": "Descrição Conta", "fornecedor": "Fornecedor",
                     "descricao_despesa": "Descrição da despesa", "responsavel": "Responsável"}
    faltando = [nomes_colunas[c] for c, posicao in colunas.items() if posicao is None]
    if faltando:
        raise ErroLeitura(f"A aba \"{nome}\" não tem a(s) coluna(s): " + ", ".join(faltando) + ".")

    alvo = date(ano, mes, 1)
    anterior = date(*mes_anterior(ano, mes), 1)
    coluna_mes = next((c for c, d in datas.items() if d == alvo), None)
    if coluna_mes is None:
        raise ErroLeitura(f"A aba {nome} não tem a coluna de {nome_do_mes(ano, mes)}.")
    coluna_anterior = next((c for c, d in datas.items() if d == anterior), None)

    resultado = AbaChecklist(estabelecimento, nome, coluna_mes, coluna_anterior)
    for numero, valores in enumerate(linhas[1:], start=2):
        def celula(coluna: int | None):
            return valores[coluna - 1] if coluna and coluna <= len(valores) else None

        textos = {c: texto_da_celula(celula(p)) for c, p in colunas.items()}
        if not any(textos.values()):
            continue
        resultado.linhas.append(LinhaChecklist(
            numero=numero,
            valor_mes=celula(coluna_mes),
            valor_mes_anterior=celula(coluna_anterior),
            **textos,
        ))
    return resultado


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
    """Uma pessoa por célula; a célula logo à direita tem os códigos que ela recebe."""
    if cfg.ABA_EMAILS not in planilha.sheetnames:
        avisos.append(Aviso(cfg.ABA_EMAILS, f"O Check list não tem a aba \"{cfg.ABA_EMAILS}\": "
                                            "os e-mails não terão destinatário."))
        return []
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


def ler_checklist(caminho: Path, ano: int, mes: int) -> Checklist:
    """Lê o Check list para o mês (K1). Levanta ErroLeitura com mensagem para o usuário."""
    caminho = Path(caminho)
    with tempfile.TemporaryDirectory(prefix="checklist_") as pasta:
        copia = copiar_para_ler(caminho, Path(pasta))
        try:
            planilha = openpyxl.load_workbook(copia, data_only=True)
        except Exception as erro:
            raise ErroLeitura(f"O arquivo não pôde ser aberto como planilha do Excel: {erro}") from None
        try:
            avisos: list[Aviso] = []
            abas = {e: _ler_aba(planilha, e, ano, mes) for e in cfg.ESTABELECIMENTOS}
            contatos = _ler_contatos(planilha, avisos)
        finally:
            planilha.close()
    return Checklist(caminho.name, ano, mes, abas, contatos, avisos)
