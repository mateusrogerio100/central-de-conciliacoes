"""
Geração do relatório em Excel (seção 6 da especificação), com openpyxl.

Abas: Resumo, Conferidas, Divergência de valor, [Nome diferente (verificar) — Cidade Gama],
Somente no Tasy, Somente na prefeitura, Escrituradas mais de uma vez,
[Canceladas na prefeitura — Cidade Epsilon, Cidade Zeta, Cidade Gama e Cidade Alfa] e Avisos.

As colunas do Tasy são as mesmas nas duas cidades; as da prefeitura mudam
(COLUNAS_PREFEITURA, uma lista por cidade).

- Valores gravados como número (Decimal) com formato #,##0.00.
- CNPJ/CPF formatado como texto; números de nota como texto (o Excel não "estraga").
- A coluna Observação do Tasy não existe aqui (nem no modelo de dados).
- Quem decide o nome e a pasta do arquivo é processar(); aqui só se grava no caminho dado.
  Erro ao gravar (pasta sem permissão, arquivo aberto) sobe como OSError para processar().
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Callable

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from modulos.conferencia_iss.modelos import (
    MUNICIPIO_AV,
    MUNICIPIO_CP,
    MUNICIPIO_FR,
    MUNICIPIO_RB,
    MUNICIPIO_SJ,
    SITUACAO_CANCELADA_COM_TASY,
    SITUACAO_CANCELADA_SEM_TASY,
    SITUACAO_DIVERGENCIA,
    SITUACAO_NOME_DIFERENTE,
    SITUACAO_SOMENTE_PREFEITURA,
    SITUACAO_SOMENTE_TASY,
    ItemResultado,
    LinhaPrefeitura,
    NotaTasy,
    Resultado,
)
from modulos.conferencia_iss.municipios import IDENTIFICACAO_NENHUMA
from modulos.conferencia_iss.municipios import municipio as cadastro_municipio
from modulos.conferencia_iss.normalizar import formatar_documento
from modulos.conferencia_iss.resumo import (
    SITUACOES_CONFERIDAS,
    conferencia_nada_sumiu,
    eh_escriturada_varias_vezes,
    linhas_do_resumo,
)

# ---------------------------------------------------------------------
# Cores (as mesmas de interface/tema.py, modo claro). A regra de negócio não importa
# a interface, por isso os valores estão copiados aqui.
# ---------------------------------------------------------------------
COR_GERAL = "0E3B3E"          # tema.COR_MENU_FUNDO  — Situação, Diferença, Resumo
COR_TASY = "0F5C63"           # tema.COR_PRINCIPAL   — colunas do Tasy
COR_PREFEITURA = "E7B75F"     # tema.COR_MARCA       — colunas da prefeitura
COR_TEXTO_CLARO = "FFFFFF"
COR_TEXTO_ESCURO = "1B2424"   # tema.COR_TEXTO
COR_OK = "1B6E45"             # tema.COR_OK
COR_ERRO = "B42318"           # tema.COR_ERRO

FORMATO_VALOR = "#,##0.00"
FORMATO_DATA = "DD/MM/YYYY"
FORMATO_TEXTO = "@"
LARGURA_MAXIMA = 50

# ---------------------------------------------------------------------
# Abas e colunas
# ---------------------------------------------------------------------
ABA_RESUMO = "Resumo"
ABA_CONFERIDAS = "Conferidas"
ABA_DIVERGENCIA = "Divergência de valor"
ABA_NOME_DIFERENTE = "Nome diferente (verificar)"   # só Cidade Gama
ABA_SOMENTE_TASY = "Somente no Tasy"
ABA_SOMENTE_PREFEITURA = "Somente na prefeitura"
ABA_ESCRITURADAS = "Escrituradas mais de uma vez"
ABA_CANCELADAS = "Canceladas na prefeitura"
ABA_AVISOS = "Avisos"

COLUNA_SITUACAO = "Situação"
COLUNA_CONFERE = "Valor confere?"


def titulo_diferenca(rotulo_valor: str) -> str:
    """"Diferença (mercadoria − Valor do Doc.)" — o nome do valor muda por cidade."""
    return f"Diferença (mercadoria − {rotulo_valor})"


COLUNA_DIFERENCA = titulo_diferenca("Valor do Doc.")      # Cidade Beta

# Grupo de cada coluna (define a cor do cabeçalho e a faixa "Tasy" / "Prefeitura")
GRUPO_GERAL = ""
GRUPO_TASY = "Tasy"
GRUPO_PREFEITURA = "Prefeitura"
GRUPO_TASY_OUTROS = "Tasy — outros dados"



@dataclass(frozen=True)
class Coluna:
    """Uma coluna das abas de detalhe: título, grupo (cor) e de onde vem o valor."""

    titulo: str
    grupo: str
    valor: Callable[[ItemResultado], object]
    formato: str = ""                # FORMATO_VALOR, FORMATO_TEXTO ou "" (datas: automático)


def _da_nota(funcao: Callable[[NotaTasy], object]) -> Callable[[ItemResultado], object]:
    return lambda item: None if item.nota_tasy is None else funcao(item.nota_tasy)


def _da_linha(funcao: Callable[[LinhaPrefeitura], object]) -> Callable[[ItemResultado], object]:
    return lambda item: None if item.linha_prefeitura is None else funcao(item.linha_prefeitura)


def _data(texto: str):
    """"15/09/2026" vira data do Excel; qualquer outra coisa fica como veio."""
    try:
        return datetime.strptime(texto.strip(), "%d/%m/%Y").date()
    except (ValueError, AttributeError):
        return texto or None


def _dia(texto: str):
    return int(texto) if texto and texto.isdigit() else (texto or None)


def _documento_prefeitura(linha: LinhaPrefeitura) -> str:
    return formatar_documento(linha.documento) or linha.documento_original


def _valor_ou_oculto(linha: LinhaPrefeitura, valor):
    """Cidade Gama: valor que a prefeitura mandou como "*****" aparece assim na planilha."""
    if valor is None and linha.valores_ocultos:
        return "*****"
    return valor


# Colunas da prefeitura que vêm depois dos valores lado a lado, por cidade
COLUNAS_PREFEITURA: dict[str, list[Coluna]] = {
    MUNICIPIO_RB: [
        Coluna("CPF/CNPJ", GRUPO_PREFEITURA, _da_linha(_documento_prefeitura), FORMATO_TEXTO),
        Coluna("Prestador", GRUPO_PREFEITURA, _da_linha(lambda l: l.prestador)),
        Coluna("Nº Doc.", GRUPO_PREFEITURA, _da_linha(lambda l: l.numero_doc), FORMATO_TEXTO),
        Coluna("Modelo", GRUPO_PREFEITURA, _da_linha(lambda l: l.modelo)),
        Coluna("Dia", GRUPO_PREFEITURA, _da_linha(lambda l: _dia(l.dia))),
        Coluna("Item LC", GRUPO_PREFEITURA, _da_linha(lambda l: l.item_lc)),
        Coluna("Alíquota", GRUPO_PREFEITURA, _da_linha(lambda l: l.aliquota)),
        Coluna("Imp. Ret.", GRUPO_PREFEITURA, _da_linha(lambda l: l.imp_ret)),
        Coluna("SN/MEI", GRUPO_PREFEITURA, _da_linha(lambda l: l.sn_mei)),
        Coluna("Nat. Operação", GRUPO_PREFEITURA, _da_linha(lambda l: l.nat_operacao)),
        Coluna("Valor Tribut.", GRUPO_PREFEITURA,
               _da_linha(lambda l: l.valor_tributavel), FORMATO_VALOR),
        Coluna("Valor do Imp.", GRUPO_PREFEITURA,
               _da_linha(lambda l: l.valor_imposto), FORMATO_VALOR),
    ],
    MUNICIPIO_SJ: [
        Coluna("CNPJ/CPF", GRUPO_PREFEITURA, _da_linha(_documento_prefeitura), FORMATO_TEXTO),
        Coluna("Razão Social / Nome", GRUPO_PREFEITURA, _da_linha(lambda l: l.prestador)),
        Coluna("Nº Nota", GRUPO_PREFEITURA, _da_linha(lambda l: l.numero_doc), FORMATO_TEXTO),
        Coluna("Situação NF", GRUPO_PREFEITURA, _da_linha(lambda l: l.situacao_nf)),
        Coluna("Data Emissão", GRUPO_PREFEITURA, _da_linha(lambda l: _data(l.data_emissao))),
        Coluna("Atividade", GRUPO_PREFEITURA, _da_linha(lambda l: l.atividade)),
        Coluna("Alíquota", GRUPO_PREFEITURA, _da_linha(lambda l: l.aliquota)),
        Coluna("Retido", GRUPO_PREFEITURA, _da_linha(lambda l: l.imp_ret)),
        Coluna("Incidência Fora", GRUPO_PREFEITURA, _da_linha(lambda l: l.incidencia_fora)),
        Coluna("Vlr. Deduções", GRUPO_PREFEITURA,
               _da_linha(lambda l: l.valor_deducoes), FORMATO_VALOR),
        Coluna("Base Cálculo", GRUPO_PREFEITURA,
               _da_linha(lambda l: l.valor_tributavel), FORMATO_VALOR),
        Coluna("Imposto", GRUPO_PREFEITURA, _da_linha(lambda l: l.valor_imposto), FORMATO_VALOR),
        Coluna("Chave Acesso", GRUPO_PREFEITURA, _da_linha(lambda l: l.chave_acesso),
               FORMATO_TEXTO),
    ],
    MUNICIPIO_AV: [
        Coluna("CNPJ/CPF", GRUPO_PREFEITURA, _da_linha(_documento_prefeitura), FORMATO_TEXTO),
        Coluna("Prestador", GRUPO_PREFEITURA, _da_linha(lambda l: l.prestador)),
        Coluna("Número", GRUPO_PREFEITURA, _da_linha(lambda l: l.numero_doc), FORMATO_TEXTO),
        Coluna("Situação da nota", GRUPO_PREFEITURA, _da_linha(lambda l: l.situacao_nf)),
        Coluna("Imposto Retido", GRUPO_PREFEITURA, _da_linha(lambda l: l.imp_ret)),
        Coluna("Competência", GRUPO_PREFEITURA, _da_linha(lambda l: _data(l.competencia))),
        Coluna("Data de emissão", GRUPO_PREFEITURA, _da_linha(lambda l: _data(l.data_emissao))),
        Coluna("Série", GRUPO_PREFEITURA, _da_linha(lambda l: l.serie)),
        Coluna("Alíquota", GRUPO_PREFEITURA, _da_linha(lambda l: l.aliquota)),
        Coluna("ISS", GRUPO_PREFEITURA, _da_linha(lambda l: l.valor_imposto), FORMATO_VALOR),
        Coluna("Dedução", GRUPO_PREFEITURA, _da_linha(lambda l: l.valor_deducoes), FORMATO_VALOR),
        Coluna("Desc. Incond.", GRUPO_PREFEITURA,
               _da_linha(lambda l: l.valor_desconto), FORMATO_VALOR),
        Coluna("Incidência", GRUPO_PREFEITURA, _da_linha(lambda l: l.incidencia)),
        Coluna("Optante", GRUPO_PREFEITURA, _da_linha(lambda l: l.optante)),
        Coluna("Regime", GRUPO_PREFEITURA, _da_linha(lambda l: l.regime)),
        Coluna("Exigibilidade", GRUPO_PREFEITURA, _da_linha(lambda l: l.exigibilidade)),
        Coluna("Cofins", GRUPO_PREFEITURA, _da_linha(lambda l: l.valor_cofins), FORMATO_VALOR),
        Coluna("CSLL", GRUPO_PREFEITURA, _da_linha(lambda l: l.valor_csll), FORMATO_VALOR),
        Coluna("INSS", GRUPO_PREFEITURA, _da_linha(lambda l: l.valor_inss), FORMATO_VALOR),
        Coluna("IRRF", GRUPO_PREFEITURA, _da_linha(lambda l: l.valor_irrf), FORMATO_VALOR),
        Coluna("PIS", GRUPO_PREFEITURA, _da_linha(lambda l: l.valor_pis), FORMATO_VALOR),
    ],
    # Sem CNPJ do prestador: o nome vem primeiro, para comparar com o Emitente do Tasy.
    MUNICIPIO_CP: [
        Coluna("Nome Empresarial", GRUPO_PREFEITURA, _da_linha(lambda l: l.prestador)),
        Coluna("Nr. NF", GRUPO_PREFEITURA, _da_linha(lambda l: l.numero_doc), FORMATO_TEXTO),
        Coluna("Nº Documento Escriturado", GRUPO_PREFEITURA,
               _da_linha(lambda l: l.numero_escriturado), FORMATO_TEXTO),
        Coluna("Nr. RPS", GRUPO_PREFEITURA, _da_linha(lambda l: l.numero_rps), FORMATO_TEXTO),
        Coluna("Situação da nota", GRUPO_PREFEITURA, _da_linha(lambda l: l.situacao_nf)),
        Coluna("Data de emissão", GRUPO_PREFEITURA, _da_linha(lambda l: _data(l.data_emissao))),
        Coluna("Compet.", GRUPO_PREFEITURA, _da_linha(lambda l: l.competencia)),
        Coluna("Pagamento", GRUPO_PREFEITURA, _da_linha(lambda l: _data(l.data_pagamento))),
        Coluna("CNAE", GRUPO_PREFEITURA, _da_linha(lambda l: l.cnae), FORMATO_TEXTO),
        Coluna("Base Cálculo", GRUPO_PREFEITURA,
               _da_linha(lambda l: _valor_ou_oculto(l, l.valor_tributavel)), FORMATO_VALOR),
        Coluna("Valor ISS", GRUPO_PREFEITURA,
               _da_linha(lambda l: _valor_ou_oculto(l, l.valor_imposto)), FORMATO_VALOR),
    ],
    MUNICIPIO_FR: [
        Coluna("CNPJ/CPF", GRUPO_PREFEITURA, _da_linha(_documento_prefeitura), FORMATO_TEXTO),
        Coluna("Nome", GRUPO_PREFEITURA, _da_linha(lambda l: l.prestador)),
        Coluna("NFS", GRUPO_PREFEITURA, _da_linha(lambda l: l.numero_doc), FORMATO_TEXTO),
        Coluna("Situação da nota", GRUPO_PREFEITURA, _da_linha(lambda l: l.situacao_nf)),
        Coluna("Data de emissão", GRUPO_PREFEITURA, _da_linha(lambda l: _data(l.data_emissao))),
        Coluna("Atividade", GRUPO_PREFEITURA, _da_linha(lambda l: l.atividade)),
        Coluna("CFPS", GRUPO_PREFEITURA, _da_linha(lambda l: l.cfps)),
        Coluna("Deduções", GRUPO_PREFEITURA, _da_linha(lambda l: l.valor_deducoes), FORMATO_VALOR),
        Coluna("Desconto incond.", GRUPO_PREFEITURA,
               _da_linha(lambda l: l.valor_desconto), FORMATO_VALOR),
        Coluna("Base de cálculo", GRUPO_PREFEITURA,
               _da_linha(lambda l: l.valor_tributavel), FORMATO_VALOR),
        Coluna("Alíquota", GRUPO_PREFEITURA, _da_linha(lambda l: l.aliquota)),
        Coluna("Imposto retido", GRUPO_PREFEITURA, _da_linha(lambda l: l.imp_ret)),
        Coluna("Valor do imposto", GRUPO_PREFEITURA,
               _da_linha(lambda l: l.valor_imposto), FORMATO_VALOR),
        Coluna("Simples Nacional", GRUPO_PREFEITURA, _da_linha(lambda l: l.sn_mei)),
    ],
}


def colunas_detalhe(codigo_municipio: str = MUNICIPIO_RB) -> list[Coluna]:
    """
    Ordem das colunas nas abas de detalhe (decisão do usuário): os dois valores comparados
    e a diferença lado a lado logo no começo; o resto da prefeitura depois; valor da nota,
    arquivo, tipo e datas do Tasy no final.
    """
    rotulo_valor = cadastro_municipio(codigo_municipio).rotulo_valor
    return [
        Coluna(COLUNA_SITUACAO, GRUPO_GERAL, lambda item: item.situacao),
        Coluna("CNPJ/CPF", GRUPO_TASY,
               _da_nota(lambda n: formatar_documento(n.documento)), FORMATO_TEXTO),
        Coluna("Emitente", GRUPO_TASY, _da_nota(lambda n: n.emitente)),
        Coluna("Nota Fiscal", GRUPO_TASY, _da_nota(lambda n: n.nota_fiscal), FORMATO_TEXTO),
        Coluna("Valor da mercadoria", GRUPO_TASY,
               _da_nota(lambda n: n.valor_mercadoria), FORMATO_VALOR),
        Coluna(rotulo_valor, GRUPO_PREFEITURA, _da_linha(lambda l: l.valor_doc), FORMATO_VALOR),
        Coluna(titulo_diferenca(rotulo_valor), GRUPO_GERAL,
               lambda item: item.diferenca, FORMATO_VALOR),
        *COLUNAS_PREFEITURA[codigo_municipio],
        Coluna("Valor da nota", GRUPO_TASY_OUTROS, _da_nota(lambda n: n.valor_nota), FORMATO_VALOR),
        Coluna("Arquivo", GRUPO_TASY_OUTROS, _da_nota(lambda n: n.arquivo)),
        Coluna("Tipo de nota", GRUPO_TASY_OUTROS, _da_nota(lambda n: n.tipo_nota)),
        Coluna("Emissão", GRUPO_TASY_OUTROS, _da_nota(lambda n: _data(n.data_emissao))),
        Coluna("Entrada", GRUPO_TASY_OUTROS, _da_nota(lambda n: _data(n.data_entrada))),
    ]


COLUNA_VALOR_CONFERE = Coluna(
    COLUNA_CONFERE, GRUPO_GERAL,
    lambda item: {True: "Sim", False: "Não"}.get(item.valor_confere, "Sem valor"),
)

# Nomes das colunas de Cidade Beta (usados nos testes e na documentação)
GRUPOS_DETALHE = [(c.titulo, c.grupo) for c in colunas_detalhe(MUNICIPIO_RB)]
COLUNAS_DETALHE = [nome for nome, _ in GRUPOS_DETALHE]
COLUNAS_TASY = [n for n, g in GRUPOS_DETALHE if g in (GRUPO_TASY, GRUPO_TASY_OUTROS)]
COLUNAS_PREFEITURA_RB = [n for n, g in GRUPOS_DETALHE if g == GRUPO_PREFEITURA]

COLUNAS_AVISOS = ["Arquivo", "Tipo", "Nível", "Linhas lidas", "Unidade(s)", "Mensagem"]

# ---------------------------------------------------------------------
# Entrada principal
# ---------------------------------------------------------------------
def gerar_relatorio(resultado: Resultado, caminho: Path | str,
                    gerado_em: datetime | None = None) -> Path:
    """Grava o .xlsx no caminho dado e devolve o caminho. Pode levantar OSError."""
    caminho = Path(caminho)
    gerado_em = gerado_em or datetime.now()

    cidade = cadastro_municipio(resultado.municipio)
    colunas = colunas_detalhe(cidade.codigo)

    livro = Workbook()
    _aba_resumo(livro.active, resultado, gerado_em)

    itens = resultado.itens

    def detalhe(titulo: str, itens_da_aba: list[ItemResultado], com_confere: bool = False):
        _aba_detalhe(livro, titulo, itens_da_aba, colunas, com_confere)

    detalhe(ABA_CONFERIDAS, [i for i in itens if i.situacao in SITUACOES_CONFERIDAS])
    detalhe(ABA_DIVERGENCIA, [i for i in itens if i.situacao == SITUACAO_DIVERGENCIA])
    if cidade.compara_por_nome:
        detalhe(ABA_NOME_DIFERENTE, [i for i in itens if i.situacao == SITUACAO_NOME_DIFERENTE])
    detalhe(ABA_SOMENTE_TASY, [i for i in itens if i.situacao == SITUACAO_SOMENTE_TASY])
    detalhe(ABA_SOMENTE_PREFEITURA, [i for i in itens if i.situacao == SITUACAO_SOMENTE_PREFEITURA])
    detalhe(ABA_ESCRITURADAS, [i for i in itens if eh_escriturada_varias_vezes(i.situacao)],
            com_confere=True)
    if cidade.tem_situacao_nf:
        # As lançadas no Tasy (precisam de análise) primeiro.
        detalhe(ABA_CANCELADAS,
                [i for i in itens if i.situacao == SITUACAO_CANCELADA_COM_TASY]
                + [i for i in itens if i.situacao == SITUACAO_CANCELADA_SEM_TASY])
    _aba_avisos(livro, resultado)

    livro.save(caminho)
    return caminho


# ---------------------------------------------------------------------
# Estilos
# ---------------------------------------------------------------------
def _estilo_cabecalho(celula, cor: str) -> None:
    texto = COR_TEXTO_ESCURO if cor == COR_PREFEITURA else COR_TEXTO_CLARO
    celula.font = Font(bold=True, color=texto)
    celula.fill = PatternFill("solid", start_color=cor, end_color=cor)
    celula.alignment = Alignment(vertical="center", wrap_text=True)


CORES_GRUPO = {
    GRUPO_GERAL: COR_GERAL,
    GRUPO_TASY: COR_TASY,
    GRUPO_TASY_OUTROS: COR_TASY,
    GRUPO_PREFEITURA: COR_PREFEITURA,
}


def _ajustar_larguras(aba, primeira_linha: int = 1) -> None:
    larguras: dict[int, int] = {}
    for linha in aba.iter_rows(min_row=primeira_linha):
        for celula in linha:
            if celula.value is None:
                continue
            if isinstance(celula.value, (int, float, Decimal)):
                tamanho = len(f"{celula.value:,.2f}")
            elif isinstance(celula.value, (date, datetime)):
                tamanho = 10
            else:
                tamanho = max(len(parte) for parte in str(celula.value).split("\n"))
            larguras[celula.column] = max(larguras.get(celula.column, 0), tamanho)
    for coluna, tamanho in larguras.items():
        aba.column_dimensions[get_column_letter(coluna)].width = min(tamanho + 2, LARGURA_MAXIMA)


# ---------------------------------------------------------------------
# Abas de detalhe
# ---------------------------------------------------------------------
def _colunas_da_aba(colunas: list[Coluna], com_confere: bool) -> list[Coluna]:
    """Colunas da aba; "Valor confere?" entra logo depois da Diferença."""
    colunas = list(colunas)
    if com_confere:
        posicao = next(i for i, c in enumerate(colunas) if c.titulo.startswith("Diferença"))
        colunas.insert(posicao + 1, COLUNA_VALOR_CONFERE)
    return colunas


def _aba_detalhe(livro: Workbook, titulo: str, itens: list[ItemResultado],
                 colunas: list[Coluna], com_confere: bool = False) -> None:
    aba = livro.create_sheet(titulo)
    colunas = _colunas_da_aba(colunas, com_confere)
    grupos = [(c.titulo, c.grupo) for c in colunas]

    # Linha 1: faixa com o grupo de colunas ("Tasy", "Prefeitura", "Tasy — outros dados")
    inicio = 0
    while inicio < len(grupos):
        grupo = grupos[inicio][1]
        fim = inicio
        while fim + 1 < len(grupos) and grupos[fim + 1][1] == grupo:
            fim += 1
        for posicao in range(inicio, fim + 1):
            _estilo_cabecalho(aba.cell(row=1, column=posicao + 1), CORES_GRUPO[grupo])
        if grupo:
            aba.cell(row=1, column=inicio + 1, value=grupo)
            if fim > inicio:
                aba.merge_cells(start_row=1, start_column=inicio + 1,
                                end_row=1, end_column=fim + 1)
        inicio = fim + 1

    # Linha 2: títulos das colunas
    for posicao, (nome, grupo) in enumerate(grupos):
        _estilo_cabecalho(aba.cell(row=2, column=posicao + 1, value=nome), CORES_GRUPO[grupo])

    for numero_linha, item in enumerate(itens, start=3):
        for posicao, coluna in enumerate(colunas):
            valor = coluna.valor(item)
            if valor == "":
                valor = None                 # lado sem dado fica em branco
            celula = aba.cell(row=numero_linha, column=posicao + 1, value=valor)
            if coluna.formato:
                celula.number_format = coluna.formato
            elif isinstance(valor, date):
                celula.number_format = FORMATO_DATA

    aba.freeze_panes = "B3"
    aba.auto_filter.ref = f"A2:{get_column_letter(len(colunas))}{max(2, len(itens) + 2)}"
    _ajustar_larguras(aba, primeira_linha=2)


# ---------------------------------------------------------------------
# Resumo
# ---------------------------------------------------------------------
def _aba_resumo(aba, resultado: Resultado, gerado_em: datetime) -> None:
    aba.title = ABA_RESUMO
    negrito = Font(bold=True)

    cidade = cadastro_municipio(resultado.municipio)
    aba.append([cidade.titulo])
    aba["A1"].font = Font(bold=True, size=14, color=COR_GERAL)
    aba.append([])

    arquivos = [a for a in resultado.avisos if a.tipo_arquivo]
    informacoes = [
        ("Unidade(s)", ", ".join(resultado.unidades) or "—"),
        ("Competência", resultado.competencia_texto or resultado.competencia or "—"),
        ("Inscrição municipal", resultado.inscricao_municipal or "—"),
        ("Gerado em", gerado_em.strftime("%d/%m/%Y %H:%M")),
    ]
    if cidade.identificacao == IDENTIFICACAO_NENHUMA:
        del informacoes[2]               # Cidade Alfa: o relatório não identifica a unidade
    elif resultado.documento_tomador:
        # Cidade Gama: o relatório não traz inscrição, e sim o CNPJ da unidade
        informacoes[2] = ("CNPJ da unidade", formatar_documento(resultado.documento_tomador))
    for rotulo, valor in informacoes:
        aba.append([rotulo, valor])
        aba.cell(row=aba.max_row, column=1).font = negrito

    aba.append(["Arquivos lidos"])
    aba.cell(row=aba.max_row, column=1).font = negrito
    for aviso in arquivos:
        linhas = "" if aviso.linhas_lidas is None else f" · {aviso.linhas_lidas} linhas"
        aba.append(["", f"{aviso.arquivo} ({aviso.tipo_arquivo}{linhas}) — {aviso.mensagem}"])
    aba.append([])

    # Tabela por situação
    cabecalho = ["Situação", "Notas do Tasy", "Linhas da prefeitura",
                 "Total Tasy (mercadoria)", f"Total prefeitura ({cidade.rotulo_valor})"]
    aba.append(cabecalho)
    linha_cabecalho = aba.max_row
    for posicao in range(1, len(cabecalho) + 1):
        _estilo_cabecalho(aba.cell(row=linha_cabecalho, column=posicao), COR_GERAL)

    linhas = linhas_do_resumo(resultado)
    for linha in linhas:
        aba.append(list(linha))
    aba.append([
        "Total",
        sum(l[1] for l in linhas), sum(l[2] for l in linhas),
        sum((l[3] for l in linhas), Decimal(0)), sum((l[4] for l in linhas), Decimal(0)),
    ])
    for celula in aba[aba.max_row]:
        celula.font = negrito
    for numero in range(linha_cabecalho + 1, aba.max_row + 1):
        aba.cell(row=numero, column=4).number_format = FORMATO_VALOR
        aba.cell(row=numero, column=5).number_format = FORMATO_VALOR
    aba.append([])

    # Conferência "nada sumiu"
    (notas_no_rel, notas_lidas), (linhas_no_rel, linhas_lidas) = conferencia_nada_sumiu(resultado)
    for texto, no_relatorio, lidas in [
        ("Todas as notas do Tasy aparecem no relatório", notas_no_rel, notas_lidas),
        ("Todas as linhas da prefeitura aparecem no relatório", linhas_no_rel, linhas_lidas),
    ]:
        ok = no_relatorio == lidas
        aba.append([f"{texto} ({no_relatorio} de {lidas})", "OK" if ok else "ATENÇÃO: confira"])
        aba.cell(row=aba.max_row, column=2).font = Font(bold=True, color=COR_OK if ok else COR_ERRO)

    _ajustar_larguras(aba, primeira_linha=3)
    aba.column_dimensions["A"].width = 45


# ---------------------------------------------------------------------
# Avisos
# ---------------------------------------------------------------------
def _aba_avisos(livro: Workbook, resultado: Resultado) -> None:
    aba = livro.create_sheet(ABA_AVISOS)
    aba.append(COLUNAS_AVISOS)
    for posicao in range(1, len(COLUNAS_AVISOS) + 1):
        _estilo_cabecalho(aba.cell(row=1, column=posicao), COR_GERAL)

    # Primeiro os registros de arquivo, depois os avisos de nota/linha.
    avisos = sorted(resultado.avisos, key=lambda a: 0 if a.tipo_arquivo else 1)
    for aviso in avisos:
        aba.append([
            aviso.arquivo, aviso.tipo_arquivo or None, aviso.nivel, aviso.linhas_lidas,
            aviso.unidades or None, aviso.mensagem,
        ])
        if aviso.eh_erro:
            aba.cell(row=aba.max_row, column=3).font = Font(bold=True, color=COR_ERRO)

    aba.freeze_panes = "A2"
    aba.auto_filter.ref = f"A1:{get_column_letter(len(COLUNAS_AVISOS))}{max(1, aba.max_row)}"
    _ajustar_larguras(aba)
