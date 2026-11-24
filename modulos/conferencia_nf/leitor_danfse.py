"""DANFSe v2.0 (nota de serviço, NFS-e) -> NotaPdf. Seção 3.3 da especificação.

A base (palavras agrupadas em linhas pela posição vertical e separadas em colunas pela posição
horizontal, retirada da marca d'água) foi COPIADA de modulos\\escrituracao_tomados\\leitor_danfse.py,
nunca importada de lá: um módulo nunca importa outro, e mudar um não pode quebrar o outro.

Como cada dado é achado: a DANFSe tem 4 colunas que começam sempre na mesma posição
(configuracao.DANFSE_COLUNAS_X). O valor de um campo fica na coluna do seu rótulo, na primeira
linha logo abaixo dele. Rótulos que se repetem (CNPJ, Nome) são procurados a partir do bloco
PRESTADOR / FORNECEDOR.

Para a conferência só interessam número, emissão, prestador, valor do serviço, situação e chave.
Regime, atividade, ISS e impostos federais são lidos só para o relatório (S10): ficam em branco
quando não dá para ler e nunca causam erro de leitura. Os outros campos não são lidos.
"""

from __future__ import annotations

import unicodedata
from datetime import date
from decimal import Decimal

from modulos.conferencia_nf import configuracao as cfg
from modulos.conferencia_nf.leitor_danfe import converter_valor_pdf, so_digitos
from modulos.conferencia_nf.modelos import ErroLeitura, NotaPdf

_TROCAS_TIPOGRAFICAS = str.maketrans({
    "–": "-", "—": "-", "‘": "'", "’": "'", "“": '"', "”": '"',
})


def normalizar_texto(texto: str) -> str:
    """Maiúsculas, sem acento, espaços únicos. Ex.: 'Clínica  Exemplo' -> 'CLINICA EXEMPLO'."""
    texto = str(texto or "").translate(_TROCAS_TIPOGRAFICAS)
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    so_ascii = "".join(c if " " <= c <= "~" else " " for c in sem_acento)
    return " ".join(so_ascii.upper().split())


# ---------------------------------------------------------------------------
# Página: linhas, rótulos e colunas (copiado do módulo Serviços Tomados)
# ---------------------------------------------------------------------------


def _agrupar_por_linha(words, tolerancia=cfg.DANFSE_TOLERANCIA_LINHA):
    """Agrupa palavras (de extract_words) em linhas, pela coordenada 'top'."""
    linhas = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if linhas and abs(linhas[-1][0]["top"] - w["top"]) <= tolerancia:
            linhas[-1].append(w)
        else:
            linhas.append([w])
    return linhas


class _Pagina:
    def __init__(self, words):
        self.linhas = _agrupar_por_linha(words)
        self._textos = [[normalizar_texto(w["text"]) for w in linha] for linha in self.linhas]

    def achar_rotulo(self, rotulo: str, a_partir_de: int = 0) -> tuple[int, float] | None:
        """(índice da linha, posição x do rótulo) da primeira ocorrência a partir da linha dada."""
        procurado = normalizar_texto(rotulo).split()
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
        """A coluna vai até o próximo rótulo DA MESMA LINHA que comece numa coluna da grade."""
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


def _data(texto: str | None, nome: str) -> date:
    achado = cfg.RE_DATA.match(_obrigatorio(texto, nome))
    if not achado:
        raise ErroLeitura(f"Data \"{texto}\" do campo \"{nome}\" não reconhecida.")
    dia, mes, ano = achado.groups()
    try:
        return date(int(ano), int(mes), int(dia))
    except ValueError:
        raise ErroLeitura(f"Data \"{texto}\" do campo \"{nome}\" inválida.") from None


def _documento(texto: str | None, nome: str) -> str:
    digitos = so_digitos(_obrigatorio(texto, nome))
    if len(digitos) not in (11, 14):
        raise ErroLeitura(f"{nome} \"{texto}\" não tem 11 (CPF) nem 14 (CNPJ) dígitos.")
    return digitos


def _texto_opcional(texto: str | None) -> str:
    return "" if _vazio(texto) else " ".join(texto.split())


def valor_opcional(texto: str | None) -> Decimal | None:
    """Campo só do relatório (S10): sem rótulo ou fora do formato = None, "-" = 0,00."""
    if texto is None:
        return None
    if _vazio(texto):
        return Decimal("0.00")
    try:
        return converter_valor_pdf(texto.replace("%", "").strip())
    except ErroLeitura:
        return None


def _campos_do_relatorio(p: _Pagina, bloco_prestador: int) -> dict:
    """Regime, atividade, ISS e impostos federais (S10). Nada aqui levanta erro."""
    codigo = _texto_opcional(p.valor(cfg.DANFSE_ROTULO_ATIVIDADE))
    codigo = codigo.split()[0] if codigo else ""
    descricao = _texto_opcional(
        p.texto_entre(cfg.DANFSE_ROTULO_ATIVIDADE, cfg.DANFSE_ROTULO_DESCRICAO_SERVICO))
    campos = {
        "regime": _texto_opcional(p.valor(cfg.DANFSE_ROTULO_REGIME, bloco_prestador)),
        "atividade": f"{codigo} - {descricao}" if codigo and descricao else codigo,
        "aliquota_iss": valor_opcional(p.valor(cfg.DANFSE_ROTULO_ALIQUOTA)),
        "valor_iss": valor_opcional(p.valor(cfg.DANFSE_ROTULO_ISS)),
        "retencao_iss": _texto_opcional(p.valor(cfg.DANFSE_ROTULO_RETENCAO_ISS)),
    }
    bloco = p.linha_do_bloco(cfg.DANFSE_BLOCO_FEDERAL)
    if bloco is not None:
        campos.update(
            irrf=valor_opcional(p.valor(cfg.DANFSE_ROTULO_IRRF, bloco)),
            previdencia_retida=valor_opcional(p.valor(cfg.DANFSE_ROTULO_PREVIDENCIA, bloco)),
            contribuicoes_retidas=valor_opcional(p.valor(cfg.DANFSE_ROTULO_CONTRIBUICOES, bloco)),
            descricao_contribuicoes=_texto_opcional(
                p.valor(cfg.DANFSE_ROTULO_DESCRICAO_CONTRIBUICOES, bloco)),
        )
    return campos


# ---------------------------------------------------------------------------
# Uma DANFSe
# ---------------------------------------------------------------------------


def palavras_sem_marca_dagua(pagina) -> list[dict]:
    """Palavras da página do pdfplumber, sem as letras grandes da marca d'água
    ("CANCELADA", "SUBSTITUÍDA"): a situação vem do campo próprio."""
    sem_marca = pagina.filter(
        lambda obj: not (obj.get("object_type") == "char"
                         and obj.get("size", 0) > cfg.DANFSE_TAMANHO_MAXIMO_TEXTO))
    return sem_marca.extract_words()


def ler_danfse(words: list[dict], arquivo: str) -> NotaPdf:
    """Palavras da 1ª página de uma DANFSe v2.0 -> NotaPdf. Levanta ErroLeitura com a explicação."""
    if not words:
        raise ErroLeitura("O PDF não tem texto (escaneado?).")
    p = _Pagina(words)
    if p.achar_rotulo(cfg.DANFSE_IDENTIFICACAO) is None:
        raise ErroLeitura("O PDF é uma DANFSe, mas não do modelo v2.0 (o único lido).")

    bloco_prestador = p.linha_do_bloco(cfg.DANFSE_BLOCO_PRESTADOR)
    bloco_valores = p.linha_do_bloco(cfg.DANFSE_BLOCO_VALORES)
    for bloco, nome in ((bloco_prestador, cfg.DANFSE_BLOCO_PRESTADOR),
                        (bloco_valores, cfg.DANFSE_BLOCO_VALORES)):
        if bloco is None:
            raise ErroLeitura(f"Bloco \"{nome}\" não encontrado na DANFSe.")

    numero = so_digitos(_obrigatorio(p.valor(cfg.DANFSE_ROTULO_NUMERO), "Número da NFS-e"))
    if not numero:
        raise ErroLeitura("Número da NFS-e não reconhecido.")
    # "-" no valor = R$ 0,00 (como em Serviços Tomados); nada abaixo do rótulo = erro de leitura
    valor_servico = p.valor(cfg.DANFSE_ROTULO_VALOR_SERVICO, bloco_valores)
    if valor_servico is None or not valor_servico.strip():
        raise ErroLeitura("Campo \"Valor da operação / serviço\" não encontrado na DANFSe.")
    if _vazio(valor_servico):
        valor = Decimal("0.00")
    else:
        try:
            valor = converter_valor_pdf(valor_servico)
        except ErroLeitura:
            raise ErroLeitura(f"Valor \"{valor_servico}\" do campo \"Valor da operação / "
                              "serviço\" não reconhecido.") from None

    # S15: CNPJ do tomador (a unidade da Fundação). Não achado = "" (a conferência avisa)
    bloco_tomador = p.linha_do_bloco(cfg.DANFSE_BLOCO_TOMADOR)
    tomador = "" if bloco_tomador is None else so_digitos(
        _texto_opcional(p.valor(cfg.DANFSE_ROTULO_DOCUMENTO, bloco_tomador)))

    return NotaPdf(
        tipo=cfg.TIPO_NFSE,
        destinatario_documento=tomador,
        numero=str(int(numero)),
        emissao=_data(p.valor(cfg.DANFSE_ROTULO_EMISSAO), "Data de emissão"),
        valor=valor,
        emitente_nome=_obrigatorio(p.valor(cfg.DANFSE_ROTULO_NOME, bloco_prestador),
                                   "Nome do prestador"),
        emitente_documento=_documento(p.valor(cfg.DANFSE_ROTULO_DOCUMENTO, bloco_prestador),
                                      "CNPJ/CPF do prestador"),
        situacao=_obrigatorio(p.valor(cfg.DANFSE_ROTULO_SITUACAO), "Situação da NFS-e"),
        chave=so_digitos(_obrigatorio(p.valor(cfg.DANFSE_ROTULO_CHAVE), "Chave de acesso")),
        arquivo=arquivo,
        **_campos_do_relatorio(p, bloco_prestador),
    )
