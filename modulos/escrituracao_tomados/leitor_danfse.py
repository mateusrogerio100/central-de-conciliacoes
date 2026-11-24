"""Leitura dos PDFs das notas tomadas (DANFSe v2.0) -> NotaTomada (seção 4.1 da especificação).

A base (pdfplumber, palavras agrupadas em linhas pela posição vertical e separadas em colunas
pela posição horizontal) foi COPIADA do extrair_nfse.py do projeto do SPED
(origem\\Automacao-Notas-Fiscais-EFD\\), nunca importada de lá: aquele extrator lê o lado do
tomador e é validado pelas regras dele; mudar um não pode quebrar o outro.

Como cada dado é achado: a DANFSe tem 4 colunas que começam sempre na mesma posição
(configuracao.DANFSE_COLUNAS_X). O valor de um campo fica na coluna do seu rótulo, na primeira
linha logo abaixo dele. Rótulos que se repetem (CNPJ, Nome, Município) são procurados a partir
do bloco certo (PRESTADOR / FORNECEDOR ou TOMADOR / ADQUIRENTE).

PDF que não for DANFSe v2.0, estragado ou com campo obrigatório vazio: ErroLeitura (o
processamento registra e continua com os demais).
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Callable

import pdfplumber

from modulos.escrituracao_tomados import configuracao as cfg
from modulos.escrituracao_tomados import leitor_nfse_sp
from modulos.escrituracao_tomados.gerador_txt import normalizar_texto, so_digitos
from modulos.escrituracao_tomados.modelos import (
    Competencia, Destino, ErroLeitura, FalhaLeitura, NotaTomada,
)

Progresso = Callable[[str, float | None], None]

RE_DATA = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
RE_VALOR = re.compile(r"^(\d{1,3}(?:\.\d{3})*|\d+),(\d{2})$")


# ---------------------------------------------------------------------------
# Página: linhas, rótulos e colunas
# ---------------------------------------------------------------------------


def _agrupar_por_linha(words, tolerancia=cfg.DANFSE_TOLERANCIA_LINHA):
    """Agrupa palavras (de extract_words) em linhas, pela coordenada 'top'.

    (Copiado do extrair_nfse.py do projeto do SPED.)
    """
    linhas = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if linhas and abs(linhas[-1][0]["top"] - w["top"]) <= tolerancia:
            linhas[-1].append(w)
        else:
            linhas.append([w])
    return linhas


def _chave(texto: str) -> str:
    """Texto para comparar rótulos: maiúsculas, sem acento, espaços únicos."""
    return normalizar_texto(texto)


class _Pagina:
    def __init__(self, words):
        self.linhas = _agrupar_por_linha(words)
        self._textos = [[_chave(w["text"]) for w in linha] for linha in self.linhas]

    def achar_rotulo(self, rotulo: str, a_partir_de: int = 0) -> tuple[int, float] | None:
        """(índice da linha, posição x do rótulo) da primeira ocorrência a partir da linha dada."""
        procurado = _chave(rotulo).split()
        tamanho = len(procurado)
        for indice in range(a_partir_de, len(self.linhas)):
            textos = self._textos[indice]
            for inicio in range(len(textos) - tamanho + 1):
                if textos[inicio: inicio + tamanho] == procurado:
                    return indice, self.linhas[indice][inicio]["x0"]
        return None

    def linha_do_bloco(self, rotulo_bloco: str) -> int | None:
        achado = self.achar_rotulo(rotulo_bloco)
        return achado[0] if achado else None

    def _fim_da_coluna(self, indice: int, x_rotulo: float) -> float:
        """A coluna vai até o próximo rótulo DA MESMA LINHA que comece numa coluna da grade.

        (Nem toda linha usa as 4 colunas: em "Nome / Nome Empresarial" o nome ocupa as duas
        primeiras e pode passar da posição da 2ª.)
        """
        tolerancia = cfg.DANFSE_TOLERANCIA_X
        for w in sorted(self.linhas[indice], key=lambda w: w["x0"]):
            if w["x0"] > x_rotulo + tolerancia and any(
                    abs(w["x0"] - x) <= tolerancia for x in cfg.DANFSE_COLUNAS_X):
                return w["x0"] - tolerancia
        return float("inf")

    def valor(self, rotulo: str, a_partir_de: int = 0) -> str | None:
        """Texto da coluna do rótulo, na primeira linha abaixo dele que tenha algo nessa coluna.

        None = rótulo não encontrado ou nada abaixo dele (até DANFSE_DISTANCIA_MAXIMA_VALOR).
        """
        achado = self.achar_rotulo(rotulo, a_partir_de)
        if achado is None:
            return None
        indice, x_rotulo = achado
        inicio = x_rotulo - cfg.DANFSE_TOLERANCIA_X
        fim = self._fim_da_coluna(indice, x_rotulo)
        topo_rotulo = self.linhas[indice][0]["top"]
        for linha in self.linhas[indice + 1:]:
            if linha[0]["top"] - topo_rotulo > cfg.DANFSE_DISTANCIA_MAXIMA_VALOR:
                break
            palavras = [w["text"] for w in sorted(linha, key=lambda w: w["x0"])
                        if inicio <= w["x0"] < fim]
            if palavras:
                return " ".join(palavras).strip()
        return None

    def texto_entre(self, rotulo: str, rotulo_fim: str) -> str:
        """Linhas inteiras entre a 2ª linha abaixo do rótulo (a 1ª é a do valor) e o rótulo do fim.
        Vazio se algum dos dois não for achado."""
        inicio, fim = self.achar_rotulo(rotulo), self.achar_rotulo(rotulo_fim)
        if inicio is None or fim is None or fim[0] <= inicio[0] + 2:
            return ""
        linhas = self.linhas[inicio[0] + 2: fim[0]]
        return " ".join(w["text"] for linha in linhas for w in sorted(linha, key=lambda w: w["x0"]))


# ---------------------------------------------------------------------------
# Conversões
# ---------------------------------------------------------------------------


def _vazio(texto: str | None) -> bool:
    return texto is None or texto.strip() in ("", cfg.DANFSE_VAZIO)


def _obrigatorio(texto: str | None, nome: str) -> str:
    if _vazio(texto):
        raise ErroLeitura(f"Campo \"{nome}\" não encontrado ou vazio na DANFSe.")
    return texto.strip()


def converter_valor(texto: str | None, nome: str) -> Decimal:
    """'R$ 13.943,28' -> Decimal('13943.28'); '2,01 %' -> Decimal('2.01'); '-' -> 0,00."""
    if _vazio(texto):
        return Decimal("0.00")
    limpo = texto.replace("R$", "").replace("%", "").strip()
    achado = RE_VALOR.match(limpo)
    if not achado:
        raise ErroLeitura(f"Valor \"{texto}\" do campo \"{nome}\" não reconhecido.")
    inteiro, centavos = achado.groups()
    return Decimal(f"{inteiro.replace('.', '')}.{centavos}")


def converter_base(texto: str | None) -> Decimal | None:
    """Base de cálculo: vazia ("-") = None (não informada); valor fora do formato também vira None,
    porque ela só serve para conferir o ISS e não pode derrubar a leitura da nota."""
    if _vazio(texto):
        return None
    try:
        return converter_valor(texto, "BC ISSQN")
    except ErroLeitura:
        return None


def converter_data(texto: str | None, nome: str) -> date:
    achado = RE_DATA.match(_obrigatorio(texto, nome))
    if not achado:
        raise ErroLeitura(f"Data \"{texto}\" do campo \"{nome}\" não reconhecida.")
    dia, mes, ano = achado.groups()
    try:
        return date(int(ano), int(mes), int(dia))
    except ValueError:
        raise ErroLeitura(f"Data \"{texto}\" do campo \"{nome}\" inválida.") from None


def converter_documento(texto: str | None, nome: str) -> str:
    digitos = so_digitos(_obrigatorio(texto, nome))
    if len(digitos) not in (11, 14):
        raise ErroLeitura(f"{nome} \"{texto}\" não tem 11 (CPF) nem 14 (CNPJ) dígitos.")
    return digitos


def separar_municipio(texto: str | None) -> tuple[str, str]:
    """'Cidade Beta / SP' -> ('Cidade Beta', 'SP'). Sem UF -> (texto, '')."""
    if _vazio(texto):
        return "", ""
    if "/" in texto:
        cidade, uf = texto.rsplit("/", 1)
        uf = uf.strip()
        if len(uf) == 2 and uf.isalpha():
            return cidade.strip(), uf.upper()
    return texto.strip(), ""


def converter_regime(texto: str | None) -> str:
    """R7: 'Não Optante' -> N; 'Optante - ...' -> S; MEI/Microempreendedor -> M."""
    chave = _chave(_obrigatorio(texto, "Simples Nacional na Data de Competência"))
    palavras = chave.replace("(", " ").replace(")", " ").split()
    if any(t in palavras or (len(t) > 3 and t in chave) for t in cfg.REGIME_TEXTOS_MEI):
        return "M"
    if chave.startswith(cfg.REGIME_TEXTO_NAO_OPTANTE):
        return "N"
    if chave.startswith(cfg.REGIME_TEXTO_OPTANTE):
        return "S"
    raise ErroLeitura(f"Regime do prestador \"{texto}\" não reconhecido (esperado Não Optante, "
                      "Optante ou MEI).")


def converter_retencao(texto: str | None) -> bool:
    chave = _chave(_obrigatorio(texto, "Retenção do ISSQN"))
    if chave.startswith(cfg.RETENCAO_TEXTO_NAO_RETIDO):
        return False
    if chave.startswith(cfg.RETENCAO_TEXTO_RETIDO):
        return True
    raise ErroLeitura(f"Retenção do ISSQN \"{texto}\" não reconhecida.")


def converter_atividade(texto: str | None) -> str:
    codigo = _obrigatorio(texto, "Código de Tributação Nacional").split()[0]
    digitos = so_digitos(codigo)
    if len(digitos) != 6:
        raise ErroLeitura(f"Código de atividade \"{codigo}\" não tem 6 dígitos.")
    return digitos


def _texto_opcional(texto: str | None) -> str:
    return "" if _vazio(texto) else " ".join(texto.split())


def converter_opcional(texto: str | None, nome: str) -> Decimal | None:
    """Campo só informativo (R19): sem rótulo ou fora do formato = None (não lido), "-" = 0,00.
    Nunca derruba a leitura da nota."""
    if texto is None:
        return None
    try:
        return converter_valor(texto, nome)
    except ErroLeitura:
        return None


def _federais(p: "_Pagina") -> dict:
    """Quadro "TRIBUTAÇÃO FEDERAL" (R19). Sem o quadro: tudo None."""
    bloco = p.linha_do_bloco(cfg.DANFSE_BLOCO_FEDERAL)
    if bloco is None:
        return {}
    return {
        "irrf": converter_opcional(p.valor(cfg.DANFSE_ROTULO_IRRF, bloco), "IRRF"),
        "previdencia_retida": converter_opcional(
            p.valor(cfg.DANFSE_ROTULO_PREVIDENCIA, bloco), "Contribuição Previdenciária"),
        "contribuicoes_retidas": converter_opcional(
            p.valor(cfg.DANFSE_ROTULO_CONTRIBUICOES, bloco), "Contribuições Sociais"),
        "descricao_contribuicoes": _texto_opcional(
            p.valor(cfg.DANFSE_ROTULO_DESCRICAO_CONTRIBUICOES, bloco)),
    }


# ---------------------------------------------------------------------------
# Um PDF
# ---------------------------------------------------------------------------


def _abrir(caminho: Path) -> _Pagina:
    try:
        with pdfplumber.open(caminho) as pdf:
            if not pdf.pages:
                raise ErroLeitura("O PDF não tem páginas.")
            # sem as letras da marca d'água ("CANCELADA", "SUBSTITUÍDA"): a situação vem do campo
            pagina_sem_marca = pdf.pages[0].filter(
                lambda obj: not (obj.get("object_type") == "char"
                                 and obj.get("size", 0) > cfg.DANFSE_TAMANHO_MAXIMO_TEXTO))
            words = pagina_sem_marca.extract_words()
    except ErroLeitura:
        raise
    except Exception:
        raise ErroLeitura("Não foi possível abrir o PDF (arquivo estragado ou protegido).") from None
    if not words:
        raise ErroLeitura("O PDF não tem texto (escaneado?). Só a DANFSe v2.0 original é lida.")
    pagina = _Pagina(words)
    if pagina.achar_rotulo(cfg.DANFSE_IDENTIFICACAO) is None:
        raise ErroLeitura("O PDF não é uma DANFSe v2.0 (modelo de outra prefeitura ou outro "
                          "documento).")
    return pagina


def _documento_do_intermediario(p: _Pagina) -> str:
    """CNPJ/CPF do intermediário, se o quadro dele estiver preenchido (o rótulo "CNPJ / CPF / NIF"
    fica na mesma linha do título "INTERMEDIÁRIO DA OPERAÇÃO"). Senão, vazio."""
    bloco = p.linha_do_bloco(cfg.DANFSE_BLOCO_INTERMEDIARIO)
    if bloco is None:
        return ""
    rotulo = p.achar_rotulo(cfg.DANFSE_ROTULO_DOCUMENTO, bloco)
    if rotulo is None or rotulo[0] != bloco:
        return ""
    documento = so_digitos(p.valor(cfg.DANFSE_ROTULO_DOCUMENTO, bloco) or "")
    return documento if len(documento) in (11, 14) else ""


def ler_pdf(caminho: Path, nome_arquivo: str | None = None) -> NotaTomada:
    """Lê uma DANFSe v2.0 (ou uma NFS-e no modelo de São Paulo, R18). Levanta ErroLeitura com a
    explicação para o usuário."""
    caminho = Path(caminho)
    try:
        p = _abrir(caminho)
    except ErroLeitura:
        paginas = leitor_nfse_sp.ler_textos(caminho)
        if paginas and leitor_nfse_sp.e_nfse_sp(paginas[0]):
            return leitor_nfse_sp.ler_pdf(paginas, nome_arquivo or caminho.name)
        raise

    bloco_prestador = p.linha_do_bloco(cfg.DANFSE_BLOCO_PRESTADOR)
    bloco_tomador = p.linha_do_bloco(cfg.DANFSE_BLOCO_TOMADOR)
    bloco_valores = p.linha_do_bloco(cfg.DANFSE_BLOCO_VALORES)
    sem_tomador = bloco_tomador is None and \
        p.achar_rotulo(cfg.DANFSE_TOMADOR_NAO_IDENTIFICADO) is not None
    for bloco, nome in ((bloco_prestador, cfg.DANFSE_BLOCO_PRESTADOR),
                        (bloco_tomador, cfg.DANFSE_BLOCO_TOMADOR),
                        (bloco_valores, cfg.DANFSE_BLOCO_VALORES)):
        if bloco is None and not (sem_tomador and nome == cfg.DANFSE_BLOCO_TOMADOR):
            raise ErroLeitura(f"Bloco \"{nome}\" não encontrado na DANFSe.")
    if sem_tomador:
        tomador_documento = tomador_nome = ""
        intermediario = _documento_do_intermediario(p)
    else:
        tomador_documento = converter_documento(
            p.valor(cfg.DANFSE_ROTULO_DOCUMENTO, bloco_tomador), "CNPJ/CPF do tomador")
        tomador_nome = _texto_opcional(p.valor(cfg.DANFSE_ROTULO_NOME, bloco_tomador))
        intermediario = ""

    chave = so_digitos(_obrigatorio(p.valor(cfg.DANFSE_ROTULO_CHAVE), "Chave de acesso"))
    numero = so_digitos(_obrigatorio(p.valor(cfg.DANFSE_ROTULO_NUMERO), "Número da NFS-e"))
    if not numero:
        raise ErroLeitura("Número da NFS-e não reconhecido.")
    data_competencia = converter_data(p.valor(cfg.DANFSE_ROTULO_COMPETENCIA), "Competência")
    emissao = converter_data(p.valor(cfg.DANFSE_ROTULO_EMISSAO), "Data de emissão")

    cidade, uf = separar_municipio(p.valor(cfg.DANFSE_ROTULO_MUNICIPIO, bloco_prestador))

    # "-" no valor = R$ 0,00 (notas 8592262 e 8592280, 08/2026: a regra manda a nota para NÃO INCLUÍDA);
    # sem nada abaixo do rótulo continua sendo erro de leitura
    valor_servico = p.valor(cfg.DANFSE_ROTULO_VALOR_SERVICO, bloco_valores)
    if valor_servico is None or not valor_servico.strip():
        raise ErroLeitura("Campo \"Valor da operação / serviço\" não encontrado na DANFSe.")

    # "OPERAÇÃO NÃO SUJEITA AO ISSQN": o quadro municipal não traz tipo, retenção nem valores
    nao_sujeita = p.achar_rotulo(cfg.DANFSE_TEXTO_NAO_SUJEITA) is not None
    if nao_sujeita:
        tipo_tributacao, iss_retido = cfg.TRIBUTACAO_NAO_SUJEITA, False
    else:
        tipo_tributacao = _obrigatorio(p.valor(cfg.DANFSE_ROTULO_TIPO_TRIBUTACAO),
                                       "Tipo de Tributação do ISSQN")
        iss_retido = converter_retencao(p.valor(cfg.DANFSE_ROTULO_RETENCAO))

    # "Desconto Incondicionado" aparece duas vezes (tributação municipal e totais): lê as duas
    desconto_tributacao = converter_valor(
        p.valor(cfg.DANFSE_ROTULO_DESCONTO_INCONDICIONADO), "Desconto Incondicionado")
    desconto_totais = converter_valor(
        p.valor(cfg.DANFSE_ROTULO_DESCONTO_INCONDICIONADO, bloco_valores),
        "Desconto Incondicionado")
    if desconto_tributacao != desconto_totais:
        raise ErroLeitura(f"Desconto incondicionado diferente em dois lugares da nota "
                          f"({desconto_tributacao} e {desconto_totais}).")

    return NotaTomada(
        numero=numero,
        data_emissao=emissao,
        competencia=Competencia(data_competencia.year, data_competencia.month),
        prestador_documento=converter_documento(
            p.valor(cfg.DANFSE_ROTULO_DOCUMENTO, bloco_prestador), "CNPJ/CPF do prestador"),
        prestador_nome=_obrigatorio(p.valor(cfg.DANFSE_ROTULO_NOME, bloco_prestador),
                                    "Nome do prestador"),
        prestador_cidade=cidade,
        prestador_uf=uf,
        tomador_documento=tomador_documento,
        tomador_nome=tomador_nome,
        intermediario_documento=intermediario,
        situacao=_obrigatorio(p.valor(cfg.DANFSE_ROTULO_SITUACAO), "Situação da NFS-e"),
        regime=converter_regime(p.valor(cfg.DANFSE_ROTULO_REGIME, bloco_prestador)),
        codigo_atividade=converter_atividade(p.valor(cfg.DANFSE_ROTULO_ATIVIDADE)),
        local_prestacao=_obrigatorio(p.valor(cfg.DANFSE_ROTULO_LOCAL_PRESTACAO),
                                     "Local da Prestação"),
        tipo_tributacao=tipo_tributacao,
        municipio_incidencia=_texto_opcional(p.valor(cfg.DANFSE_ROTULO_INCIDENCIA)),
        valor_servico=converter_valor(valor_servico, "Valor da operação / serviço"),
        deducoes=converter_valor(p.valor(cfg.DANFSE_ROTULO_DEDUCOES), "Total Deduções/Reduções"),
        desconto_incondicionado=desconto_totais,
        aliquota=converter_valor(p.valor(cfg.DANFSE_ROTULO_ALIQUOTA), "Alíquota Aplicada"),
        valor_iss=converter_valor(p.valor(cfg.DANFSE_ROTULO_ISS), "ISSQN Apurado"),
        base_calculo=converter_base(p.valor(cfg.DANFSE_ROTULO_BASE_CALCULO)),
        iss_retido=iss_retido,
        descricao_atividade=_texto_opcional(
            p.texto_entre(cfg.DANFSE_ROTULO_ATIVIDADE, cfg.DANFSE_ROTULO_DESCRICAO_SERVICO)),
        **_federais(p),
        chave_acesso=chave,
        origem="PDF",
        arquivo=nome_arquivo or caminho.name,
    )


# ---------------------------------------------------------------------------
# Pasta de PDFs
# ---------------------------------------------------------------------------


def listar_pdfs(pasta: Path) -> list[Path]:
    """PDFs da pasta e das subpastas, em ordem do caminho (a mesma a cada execução)."""
    pasta = Path(pasta)
    return sorted((p for p in pasta.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf"),
                  key=lambda p: p.relative_to(pasta).as_posix())


def ler_pasta(pasta: Path, progresso: Progresso | None = None
              ) -> tuple[list[NotaTomada], list[FalhaLeitura]]:
    """Lê todos os PDFs. Devolve (notas lidas, falhas de leitura).

    Um PDF com problema vira FalhaLeitura e o resto continua. O mesmo PDF duas vezes (mesma
    chave de acesso) fica com destino DUPLICADA (R13), apontando o primeiro.
    """
    pasta = Path(pasta)
    pdfs = listar_pdfs(pasta)
    notas: list[NotaTomada] = []
    falhas: list[FalhaLeitura] = []
    primeiro_por_chave: dict[str, NotaTomada] = {}
    for posicao, caminho in enumerate(pdfs, start=1):
        if progresso:
            progresso(f"Lendo PDFs... {posicao} de {len(pdfs)}", (posicao - 1) / len(pdfs))
        nome = caminho.relative_to(pasta).as_posix()
        try:
            nota = ler_pdf(caminho, nome)
        except ErroLeitura as erro:
            falhas.append(FalhaLeitura(nome, str(erro)))
            continue
        except Exception as erro:          # nada derruba o processamento inteiro
            falhas.append(FalhaLeitura(nome, f"Erro inesperado ao ler o PDF: {erro}"))
            continue
        primeiro = primeiro_por_chave.setdefault(nota.chave_acesso, nota)
        if primeiro is not nota and primeiro.motivo_leitura and not nota.motivo_leitura:
            # a mesma nota em DANFSe e no modelo de São Paulo: vale a DANFSe (entra no arquivo)
            primeiro_por_chave[nota.chave_acesso] = nota
            primeiro.destino = Destino.DUPLICADA
            primeiro.motivo = f"duplicado na pasta (mesma nota do arquivo {nota.arquivo})"
        elif primeiro is not nota:
            nota.destino = Destino.DUPLICADA
            nota.motivo = f"duplicado na pasta (mesma nota do arquivo {primeiro.arquivo})"
        notas.append(nota)
    if progresso:
        progresso(f"PDFs lidos: {len(pdfs)}", 1.0)
    return notas, falhas
