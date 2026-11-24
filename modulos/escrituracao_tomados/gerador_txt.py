"""Monta o .txt de importação (header, detalhes, trailler) a partir das tabelas de layout_v3.py.

O gerador não decide nada de regra de negócio: recebe as notas que JÁ vão entrar no arquivo,
com os códigos (retido, CFPS, regime) prontos, e só formata. Um valor que não cabe no layout
(ex.: número com mais de 8 dígitos, V2) gera ErroLayout — nunca é cortado em silêncio.
"""

from __future__ import annotations

import unicodedata
from datetime import date
from decimal import Decimal
from pathlib import Path

from modulos.escrituracao_tomados import configuracao, layout_v3
from modulos.escrituracao_tomados.layout_v3 import Campo, Tipo
from modulos.escrituracao_tomados.modelos import Competencia, ErroLayout, NotaTomada

CENTAVO = Decimal("0.01")

# Caracteres comuns em nomes copiados de documentos, trocados pelo equivalente simples.
_TROCAS_TIPOGRAFICAS = str.maketrans({
    "–": "-", "—": "-", "‘": "'", "’": "'", "“": '"', "”": '"',
})


# ---------------------------------------------------------------------------
# Formatação de um campo
# ---------------------------------------------------------------------------


def so_digitos(texto: str) -> str:
    return "".join(c for c in str(texto) if c.isdigit())


def normalizar_texto(texto: str) -> str:
    """Maiúsculas, sem acento, espaços únicos (V8). Ex.: 'Clínica  Exemplo' -> 'CLINICA EXEMPLO'.

    O que sobrar fora do ASCII (símbolo raro) vira espaço, para o arquivo continuar válido.
    """
    texto = str(texto or "").translate(_TROCAS_TIPOGRAFICAS)
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    so_ascii = "".join(c if " " <= c <= "~" else " " for c in sem_acento)
    return " ".join(so_ascii.upper().split())


def _centavos(valor: Decimal, campo: Campo) -> int:
    if not isinstance(valor, Decimal):
        raise ErroLayout(f"Campo {campo.nome}: valor {valor!r} não é Decimal.")
    if valor < 0:
        raise ErroLayout(f"Campo {campo.nome}: valor negativo ({valor}).")
    if valor != valor.quantize(CENTAVO):
        raise ErroLayout(f"Campo {campo.nome}: valor {valor} tem mais de 2 casas decimais.")
    return int(valor.quantize(CENTAVO) * 100)


def formatar_campo(campo: Campo, valor) -> str:
    """Devolve o valor com exatamente campo.tamanho caracteres, conforme o tipo."""
    if campo.tipo is Tipo.FINANCEIRO:
        texto = str(_centavos(valor, campo)).zfill(campo.tamanho)
    elif campo.tipo is Tipo.NUMERICO:
        texto = str(valor)
        if not texto.isdigit():
            raise ErroLayout(f"Campo {campo.nome}: '{texto}' não é numérico.")
        texto = texto.zfill(campo.tamanho)
    else:
        texto = normalizar_texto(valor)[: campo.tamanho].ljust(campo.tamanho)
    if len(texto) > campo.tamanho:
        raise ErroLayout(
            f"Campo {campo.nome}: '{valor}' tem {len(texto)} posições; o layout aceita "
            f"{campo.tamanho}."
        )
    return texto


def montar_registro(campos: tuple[Campo, ...], valores: dict, tamanho: int) -> str:
    """Junta os campos na ordem da tabela, conferindo posições e tamanho final da linha."""
    partes = []
    posicao = 1
    for campo in campos:
        if campo.inicio != posicao:
            raise ErroLayout(f"Tabela de layout: {campo.nome} começa em {campo.inicio}, "
                             f"esperado {posicao}.")
        valor = campo.fixo if campo.fixo is not None else valores[campo.nome]
        partes.append(formatar_campo(campo, valor))
        posicao = campo.fim + 1
    linha = "".join(partes)
    if len(linha) != tamanho:
        raise ErroLayout(f"Registro com {len(linha)} posições; o layout exige {tamanho}.")
    return linha


def ler_campo(linha: str, campo: Campo) -> str:
    return linha[campo.inicio - 1: campo.fim]


# ---------------------------------------------------------------------------
# Registros
# ---------------------------------------------------------------------------


def _data(valor: date) -> str:
    return valor.strftime("%d%m%Y")


def montar_header(cnpj_tomador: str, competencia: Competencia, data_lancamento: date,
                  tipo_referencia: str) -> str:
    if tipo_referencia not in configuracao.TIPOS_REFERENCIA:
        raise ErroLayout(f"Tipo de referência '{tipo_referencia}' inválido (use N ou C).")
    cnpj = so_digitos(cnpj_tomador)
    if len(cnpj) != 14:
        raise ErroLayout(f"CNPJ do tomador '{cnpj_tomador}' não tem 14 dígitos.")
    return montar_registro(layout_v3.HEADER, {
        "cnpj_tomador": cnpj,
        "mes_referencia": f"{competencia.mes:02d}",
        "ano_referencia": f"{competencia.ano:04d}",
        "data_lancamento": _data(data_lancamento),
        "tipo_referencia": tipo_referencia,
    }, layout_v3.TAMANHO_HEADER)


def _conferir_codigo(nome: str, valor: str, aceitos: tuple[str, ...], nota: NotaTomada) -> str:
    if valor not in aceitos:
        raise ErroLayout(f"Nota {nota.numero}: {nome} '{valor}' inválido "
                         f"(aceitos: {', '.join(aceitos)}).")
    return valor


def montar_detalhe(nota: NotaTomada) -> str:
    documento = so_digitos(nota.prestador_documento)
    tipo_identificacao = configuracao.TIPO_IDENTIFICACAO_POR_DIGITOS.get(len(documento))
    if tipo_identificacao is None:
        raise ErroLayout(f"Nota {nota.numero}: CNPJ/CPF do prestador '{nota.prestador_documento}' "
                         "não tem 14 nem 11 dígitos.")
    numero = numero_no_arquivo(nota)
    if len(numero) > 8:
        raise ErroLayout(f"Nota {nota.numero}: número com mais de 8 dígitos não cabe no layout "
                         "(lançar à mão).")
    if not normalizar_texto(nota.prestador_cidade):
        raise ErroLayout(f"Nota {nota.numero}: cidade do prestador não informada.")
    uf = normalizar_texto(nota.prestador_uf)
    if len(uf) != 2 or not uf.isalpha():
        raise ErroLayout(f"Nota {nota.numero}: UF do prestador '{nota.prestador_uf}' inválida.")
    atividade = so_digitos(nota.codigo_atividade)
    if len(atividade) != 6:
        raise ErroLayout(f"Nota {nota.numero}: código de atividade '{nota.codigo_atividade}' "
                         "não tem 6 dígitos.")
    return montar_registro(layout_v3.DETALHE, {
        "tipo_identificacao": tipo_identificacao,
        "documento_prestador": documento,
        "nome_prestador": nota.prestador_nome,
        "cidade_prestador": nota.prestador_cidade,
        "uf_prestador": uf,
        "numero_nf": numero,
        "data_emissao": _data(nota.data_emissao),
        "valor_servicos": nota.valor_servico,
        "valor_deducoes": nota.deducoes,
        "aliquota": nota.aliquota,
        "valor_imposto": nota.valor_iss,
        "imposto_retido": _conferir_codigo("código de imposto retido", nota.codigo_retido,
                                           configuracao.CODIGOS_IMPOSTO_RETIDO, nota),
        "codigo_atividade": atividade,
        "cfps": _conferir_codigo("CFPS", nota.cfps, configuracao.CODIGOS_CFPS, nota),
        "regime_prestador": _conferir_codigo("regime", nota.regime,
                                             configuracao.CODIGOS_REGIME, nota),
    }, layout_v3.TAMANHO_DETALHE)


def montar_trailler(notas: list[NotaTomada]) -> str:
    return montar_registro(layout_v3.TRAILLER, {
        "quantidade_detalhes": str(len(notas)),
        "total_servicos": sum((n.valor_servico for n in notas), Decimal("0.00")),
        "total_deducoes": sum((n.deducoes for n in notas), Decimal("0.00")),
        "total_impostos": sum((n.valor_iss for n in notas), Decimal("0.00")),
    }, layout_v3.TAMANHO_TRAILLER)


# ---------------------------------------------------------------------------
# Arquivo
# ---------------------------------------------------------------------------


def numero_no_arquivo(nota: NotaTomada) -> str:
    """O número que vai no .txt, sem zeros à esquerda: o ajustado (8 últimos dígitos, R8) ou o da nota."""
    return so_digitos(nota.numero_arquivo or nota.numero).lstrip("0") or "0"


def ordenar_notas(notas: list[NotaTomada]) -> list[NotaTomada]:
    """Número no arquivo (inteiro) crescente, depois CNPJ/CPF do prestador (seção 9)."""
    return sorted(notas, key=lambda n: (int(numero_no_arquivo(n)), so_digitos(n.prestador_documento)))


def gerar_conteudo(cnpj_tomador: str, competencia: Competencia, data_lancamento: date,
                   tipo_referencia: str, notas: list[NotaTomada]) -> str:
    """Texto completo do arquivo: header, um detalhe por nota, trailler; CRLF no fim de cada linha."""
    if not notas:
        raise ErroLayout("Nenhuma nota para gerar o arquivo.")
    ordenadas = ordenar_notas(notas)
    linhas = [montar_header(cnpj_tomador, competencia, data_lancamento, tipo_referencia)]
    linhas += [montar_detalhe(nota) for nota in ordenadas]
    linhas.append(montar_trailler(ordenadas))
    quebra = configuracao.QUEBRA_DE_LINHA
    return quebra.join(linhas) + quebra


def nome_arquivo(cnpj_tomador: str, competencia: Competencia) -> str:
    return configuracao.MODELO_NOME_ARQUIVO.format(
        cnpj_tomador=so_digitos(cnpj_tomador), competencia=competencia.texto_arquivo)


def gravar_arquivo(caminho: Path, conteudo: str) -> Path:
    """Grava em latin-1 exatamente como está (sem o Python trocar as quebras de linha)."""
    caminho = Path(caminho)
    caminho.write_bytes(conteudo.encode(configuracao.CODIFICACAO_TXT))
    return caminho


# ---------------------------------------------------------------------------
# Conferências do arquivo pronto (R16)
# ---------------------------------------------------------------------------


def _valor_financeiro(linha: str, campo: Campo) -> Decimal:
    return Decimal(int(ler_campo(linha, campo))) / 100


def conferir_conteudo(conteudo: str) -> list[str]:
    """Confere o arquivo montado. Devolve a lista de problemas (vazia = tudo certo).

    - header e trailler com 100 posições, cada detalhe com 350;
    - trailler = soma dos detalhes (quantidade, serviços, deduções, impostos);
    - nenhuma nota (número + prestador) repetida no arquivo.
    """
    quebra = configuracao.QUEBRA_DE_LINHA
    if not conteudo.endswith(quebra):
        return ["O arquivo não termina com quebra de linha depois do trailler."]
    linhas = conteudo[: -len(quebra)].split(quebra)
    if len(linhas) < 3:
        return ["O arquivo precisa ter header, ao menos um detalhe e trailler."]
    problemas = []
    header, detalhes, trailler = linhas[0], linhas[1:-1], linhas[-1]

    if len(header) != layout_v3.TAMANHO_HEADER or not header.startswith("0"):
        problemas.append(f"Header com {len(header)} posições (esperado {layout_v3.TAMANHO_HEADER}).")
    if len(trailler) != layout_v3.TAMANHO_TRAILLER or not trailler.startswith("9"):
        problemas.append(f"Trailler com {len(trailler)} posições "
                         f"(esperado {layout_v3.TAMANHO_TRAILLER}).")
        return problemas

    campos = {c.nome: c for c in layout_v3.DETALHE}
    totais = {"total_servicos": Decimal(0), "total_deducoes": Decimal(0),
              "total_impostos": Decimal(0)}
    chaves_vistas = set()
    for posicao, linha in enumerate(detalhes, start=2):
        if len(linha) != layout_v3.TAMANHO_DETALHE or not linha.startswith("1"):
            problemas.append(f"Linha {posicao}: detalhe com {len(linha)} posições "
                             f"(esperado {layout_v3.TAMANHO_DETALHE}).")
            continue
        numero = int(ler_campo(linha, campos["numero_nf"]))
        documento = ler_campo(linha, campos["documento_prestador"])
        if (numero, documento) in chaves_vistas:
            problemas.append(f"Linha {posicao}: nota {numero} do prestador {documento} repetida.")
        chaves_vistas.add((numero, documento))
        totais["total_servicos"] += _valor_financeiro(linha, campos["valor_servicos"])
        totais["total_deducoes"] += _valor_financeiro(linha, campos["valor_deducoes"])
        totais["total_impostos"] += _valor_financeiro(linha, campos["valor_imposto"])

    campos_trailler = {c.nome: c for c in layout_v3.TRAILLER}
    quantidade = int(ler_campo(trailler, campos_trailler["quantidade_detalhes"]))
    if quantidade != len(detalhes):
        problemas.append(f"Trailler informa {quantidade} notas; o arquivo tem {len(detalhes)}.")
    for nome, soma in totais.items():
        informado = _valor_financeiro(trailler, campos_trailler[nome])
        if informado != soma:
            problemas.append(f"Trailler: {nome} = {informado}; soma dos detalhes = {soma}.")
    return problemas
