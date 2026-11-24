"""Relatório Excel Relatorio_Tomados_<data e hora>.xlsx (seção 6 da especificação).

Abas:
- Notas:            uma linha por nota / PDF / linha de exportação, com destino e motivo (R15);
- Lançar à mão:     só as notas para digitar no site, na ordem dos campos da tela do site;
- Falar com o fornecedor: prestador Não Optante sem imposto federal retido (R19);
- Corrigir número no site: notas que entraram com os 8 últimos dígitos do número (R8);
- Arquivos gerados: um .txt por tomador + competência, com quantidades e totais;
- Divergências:     PDF x exportação (R13) e ISS calculado x informado (R10);
- Avisos:           os demais pontos a conferir, as falhas de leitura e as conferências (R16).

Dinheiro sai de Decimal para número (2 casas) só na gravação.
"""

from __future__ import annotations

import os
import tempfile
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from modulos.escrituracao_tomados import configuracao as cfg
from modulos.escrituracao_tomados.gerador_txt import normalizar_texto
from modulos.escrituracao_tomados.modelos import Destino, NotaTomada

FORMATO_DINHEIRO = "#,##0.00"
_NEGRITO = Font(bold=True)
_FUNDO_TITULO = PatternFill("solid", fgColor="D9E1F2")
_FUNDO_ATENCAO = PatternFill("solid", fgColor="FFE699")
_FUNDO_ERRO = PatternFill("solid", fgColor="F8CBAD")
_FUNDO_DESTINO = {
    Destino.LANCAR_A_MAO: _FUNDO_ATENCAO,
    Destino.ERRO_LEITURA: _FUNDO_ERRO,
}

TIPOS_DIVERGENCIA = ("Divergência PDF x exportação", "ISS calculado diferente do informado",
                     "Base de cálculo diferente de serviço - deduções")


def gerar_relatorio(resultado, caminho) -> Path:
    caminho = Path(caminho)
    livro = Workbook()
    _aba_notas(livro.active, resultado)
    _aba_lancar_a_mao(livro.create_sheet("Lançar à mão"), resultado)
    _aba_falar_com_fornecedor(livro.create_sheet(cfg.ABA_FALAR_COM_FORNECEDOR), resultado)
    _aba_corrigir_numero(livro.create_sheet("Corrigir número no site"), resultado)
    _aba_arquivos(livro.create_sheet("Arquivos gerados"), resultado)
    _aba_divergencias(livro.create_sheet("Divergências"), resultado)
    _aba_avisos(livro.create_sheet("Avisos"), resultado)
    _salvar(livro, caminho)
    return caminho


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def _dinheiro(valor: Decimal | None):
    return None if valor is None else float(valor.quantize(Decimal("0.01")))


def _tabela(aba, titulos: list[str], linhas: list[list], colunas_dinheiro=(), larguras=(),
            fundos: list | None = None) -> None:
    for coluna, titulo in enumerate(titulos, 1):
        celula = aba.cell(1, coluna, titulo)
        celula.font, celula.fill = _NEGRITO, _FUNDO_TITULO
        celula.alignment = Alignment(wrap_text=True, vertical="center")
    nomes_dinheiro = {titulos.index(t) + 1 for t in colunas_dinheiro}
    for numero, valores in enumerate(linhas, 2):
        fundo = fundos[numero - 2] if fundos else None
        for coluna, valor in enumerate(valores, 1):
            celula = aba.cell(numero, coluna, valor)
            if coluna in nomes_dinheiro:
                celula.number_format = FORMATO_DINHEIRO
            if fundo is not None:
                celula.fill = fundo
    aba.auto_filter.ref = f"A1:{get_column_letter(len(titulos))}{max(len(linhas), 1) + 1}"
    aba.freeze_panes = "A2"
    for coluna, largura in enumerate(larguras, 1):
        aba.column_dimensions[get_column_letter(coluna)].width = largura


def _competencia(nota: NotaTomada) -> str:
    return nota.competencia.texto if nota.competencia else ""


def _atividade(codigo: str) -> str:
    """040101 -> 04.01.01"""
    return f"{codigo[:2]}.{codigo[2:4]}.{codigo[4:]}" if len(codigo) == 6 else codigo


def _atividade_com_texto(nota: NotaTomada) -> str:
    """040101 + "Medicina." -> 04.01.01 - Medicina."""
    codigo = _atividade(nota.codigo_atividade)
    return f"{codigo} - {nota.descricao_atividade}" if nota.descricao_atividade else codigo


def _retido(nota: NotaTomada) -> str:
    if nota.iss_retido is None:
        return ""
    return "Retido" if nota.iss_retido else "Não Retido"


def _federais(nota: NotaTomada) -> list:
    return [_dinheiro(nota.irrf), _dinheiro(nota.previdencia_retida),
            _dinheiro(nota.contribuicoes_retidas), nota.descricao_contribuicoes]


def _cidade_uf(nota: NotaTomada) -> str:
    if nota.prestador_cidade and nota.prestador_uf:
        return f"{nota.prestador_cidade}/{nota.prestador_uf}"
    return nota.prestador_cidade


# ---------------------------------------------------------------------------
# Abas
# ---------------------------------------------------------------------------


def _aba_notas(aba, resultado) -> None:
    aba.title = "Notas"
    titulos = ["Destino", "Motivo", "Origem", "Arquivo de origem", "CNPJ do tomador",
               "Tomador", "Competência", "Número", "Emissão", "Prestador", "CNPJ/CPF do prestador",
               "Cidade/UF do prestador", "Valor do serviço", "Deduções", "Alíquota (%)", "ISS",
               "Imposto retido", "CFPS", "Regime", "Arquivo .txt", "Base de cálculo (BC ISSQN)",
               "Atividade", "Retenção do ISS (nota)", "IRRF", "Previdência retida",
               "Contribuições Sociais retidas", "Descrição contrib. sociais",
               "Falar com o fornecedor"]
    linhas, fundos = [], []
    for nota in resultado.notas:
        linhas.append([
            nota.destino.value if nota.destino else "", nota.motivo, nota.origem, nota.arquivo,
            nota.tomador_documento, nota.tomador_nome, _competencia(nota), nota.numero,
            nota.data_emissao.strftime("%d/%m/%Y"), nota.prestador_nome,
            nota.prestador_documento, _cidade_uf(nota), _dinheiro(nota.valor_servico),
            _dinheiro(nota.deducoes), _dinheiro(nota.aliquota), _dinheiro(nota.valor_iss),
            nota.codigo_retido, nota.cfps, nota.regime,
            resultado.arquivo_txt_da_nota.get(id(nota), ""), _dinheiro(nota.base_calculo),
            _atividade_com_texto(nota) if nota.codigo_atividade else "", _retido(nota),
            *_federais(nota), "SIM" if nota.falar_com_fornecedor else "",
        ])
        fundos.append(_FUNDO_DESTINO.get(nota.destino))
    for falha in resultado.falhas:
        if falha.origem == "Resultado":
            continue                                     # vai para a aba Avisos
        linhas.append([Destino.ERRO_LEITURA.value, falha.motivo, falha.origem, falha.arquivo]
                      + [None] * (len(titulos) - 4))
        fundos.append(_FUNDO_ERRO)
    _tabela(aba, titulos, linhas,
            colunas_dinheiro=("Valor do serviço", "Deduções", "Alíquota (%)", "ISS",
                              "Base de cálculo (BC ISSQN)", "IRRF", "Previdência retida",
                              "Contribuições Sociais retidas"),
            larguras=(18, 45, 12, 40, 17, 35, 12, 15, 11, 40, 20, 24, 14, 11, 11, 11, 9, 7,
                      8, 34, 16, 30, 13, 11, 12, 14, 14, 12),
            fundos=fundos)


def _aba_lancar_a_mao(aba, resultado) -> None:
    """Na ordem dos campos da tela do site."""
    titulos = ["Motivo", "Número", "Data", "Local do serviço", "Atividade", "CNPJ/CPF", "Nome",
               "Cidade", "Estado", "Enquadramento", "Total dos serviços",
               "Desconto incondicionado", "% Imposto", "Imposto retido", "Valor do ISS",
               "Deduções", "Tomador (login)", "Competência", "Arquivo de origem",
               "Base de cálculo (BC ISSQN)"]
    linhas = []
    for nota in resultado.notas:
        if nota.destino is not Destino.LANCAR_A_MAO:
            continue
        linhas.append([
            nota.motivo, nota.numero, nota.data_emissao.strftime("%d/%m/%Y"),
            cfg.TEXTO_SITE_CFPS.get(nota.cfps, ""), _atividade(nota.codigo_atividade),
            nota.prestador_documento, nota.prestador_nome, nota.prestador_cidade,
            nota.prestador_uf, cfg.TEXTO_SITE_REGIME.get(nota.regime, nota.regime),
            _dinheiro(nota.valor_servico), _dinheiro(nota.desconto_incondicionado),
            _dinheiro(nota.aliquota),
            cfg.TEXTO_SITE_RETIDO.get(nota.codigo_retido,
                                      f"conferir (site: {nota.retido_site})"
                                      if nota.retido_site else "conferir"),
            _dinheiro(nota.valor_iss), _dinheiro(nota.deducoes), nota.tomador_documento,
            _competencia(nota), nota.arquivo, _dinheiro(nota.base_calculo),
        ])
    _tabela(aba, titulos, linhas,
            colunas_dinheiro=("Total dos serviços", "Desconto incondicionado", "% Imposto",
                              "Valor do ISS", "Deduções", "Base de cálculo (BC ISSQN)"),
            larguras=(45, 15, 11, 40, 10, 17, 40, 22, 7, 13, 14, 13, 10, 30, 11, 11, 17, 11, 40,
                      16))


def _aba_falar_com_fornecedor(aba, resultado) -> None:
    """R19: prestador Não Optante sem nenhum imposto federal retido na nota. Perguntar ao
    fornecedor; a coluna "Retorno do fornecedor" fica em branco para anotar."""
    titulos = ["Prestador", "CNPJ/CPF", "Número", "Emissão", "Competência", "Valor do serviço",
               "Atividade", "Alíquota ISS (%)", "ISS", "Retenção do ISS", "IRRF",
               "Previdência retida", "Contribuições Sociais retidas", "Descrição contrib. sociais",
               "Destino da nota", "Tomador", "Arquivo de origem", "Retorno do fornecedor"]
    notas = sorted(resultado.falar_com_fornecedor,
                   key=lambda n: (normalizar_texto(n.prestador_nome), n.numero.zfill(20)))
    linhas = [[nota.prestador_nome, nota.prestador_documento, nota.numero,
               nota.data_emissao.strftime("%d/%m/%Y"), _competencia(nota),
               _dinheiro(nota.valor_servico), _atividade_com_texto(nota), _dinheiro(nota.aliquota),
               _dinheiro(nota.valor_iss), _retido(nota), *_federais(nota),
               nota.destino.value if nota.destino else "", nota.tomador_documento, nota.arquivo,
               ""]
              for nota in notas]
    _tabela(aba, titulos, linhas,
            colunas_dinheiro=("Valor do serviço", "Alíquota ISS (%)", "ISS", "IRRF",
                              "Previdência retida", "Contribuições Sociais retidas"),
            larguras=(45, 17, 15, 11, 12, 14, 40, 11, 11, 13, 11, 12, 14, 14, 16, 17, 45, 40))


def _aba_corrigir_numero(aba, resultado) -> None:
    """Notas que entraram no .txt com os 8 últimos dígitos (R8): depois de importar, abrir cada uma
    no site e trocar só o número."""
    titulos = ["Número no arquivo (site)", "Número correto", "Prestador", "CNPJ/CPF", "Emissão",
               "Valor do serviço", "Competência", "Tomador (login)", "Arquivo .txt"]
    linhas = [[nota.numero_arquivo.lstrip("0") or "0", nota.numero, nota.prestador_nome,
               nota.prestador_documento, nota.data_emissao.strftime("%d/%m/%Y"),
               _dinheiro(nota.valor_servico), _competencia(nota), nota.tomador_documento,
               resultado.arquivo_txt_da_nota.get(id(nota), "")]
              for nota in resultado.notas_com_numero_ajustado]
    _tabela(aba, titulos, linhas, colunas_dinheiro=("Valor do serviço",),
            larguras=(16, 18, 45, 17, 11, 14, 12, 17, 34))


def _aba_arquivos(aba, resultado) -> None:
    titulos = ["CNPJ do tomador", "Tomador", "Competência", "Arquivo", "Situação", "Notas",
               "Total dos serviços", "Deduções", "ISS"]
    linhas = [[a.tomador_documento, a.tomador_nome, a.competencia.texto, a.caminho.name,
               "Gravado" if a.gravado else a.problema, a.quantidade,
               _dinheiro(a.total_servicos), _dinheiro(a.total_deducoes), _dinheiro(a.total_iss)]
              for a in resultado.arquivos]
    _tabela(aba, titulos, linhas, colunas_dinheiro=("Total dos serviços", "Deduções", "ISS"),
            larguras=(17, 40, 12, 42, 20, 7, 16, 12, 12),
            fundos=[None if a.gravado else _FUNDO_ERRO for a in resultado.arquivos])


def _aba_divergencias(aba, resultado) -> None:
    titulos = ["Tipo", "Nota", "Arquivo", "Divergência"]
    linhas = [[a.tipo, a.nota, a.arquivo, a.mensagem] for a in resultado.avisos
              if a.tipo in TIPOS_DIVERGENCIA]
    _tabela(aba, titulos, linhas, larguras=(32, 45, 40, 80))


def _aba_avisos(aba, resultado) -> None:
    titulos = ["Tipo", "Nota", "Arquivo", "Aviso"]
    linhas, fundos = [], []
    for conferencia in resultado.conferencias:
        linhas.append(["Conferência: " + ("OK" if conferencia.ok else "ATENÇÃO"), "", "",
                       f"{conferencia.descricao}"
                       + (f" — {conferencia.detalhe}" if conferencia.detalhe else "")])
        fundos.append(None if conferencia.ok else _FUNDO_ATENCAO)
    for falha in resultado.falhas:
        if falha.origem == "Resultado":
            linhas.append(["Resultado da prefeitura não lido", "", falha.arquivo, falha.motivo])
            fundos.append(_FUNDO_ERRO)
    for aviso in resultado.avisos:
        if aviso.tipo not in TIPOS_DIVERGENCIA:
            linhas.append([aviso.tipo, aviso.nota, aviso.arquivo, aviso.mensagem])
            fundos.append(None)
    _tabela(aba, titulos, linhas, larguras=(36, 45, 40, 90), fundos=fundos)


def _salvar(livro, caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    descritor, temporario = tempfile.mkstemp(suffix=".xlsx", prefix="~tmp_", dir=caminho.parent)
    os.close(descritor)
    try:
        livro.save(temporario)
        os.replace(temporario, caminho)
    except PermissionError:
        raise OSError(f"{caminho.name}: não foi possível gravar. Feche o arquivo no Excel e "
                      "tente de novo.") from None
    finally:
        if os.path.exists(temporario):
            os.remove(temporario)
