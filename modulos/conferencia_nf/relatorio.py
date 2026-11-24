"""Relatório Excel da conferência (seção 5 da especificação).

Abas, nesta ordem: Resumo, Conferir à mão, Escriturar na prefeitura, Lançamentos, Rateios, Contas a
conferir, PDF x Tasy, PDFs sem lançamento e Erros de leitura. O modelo visual aprovado é o Conferencia_NF_*.xlsx de cada pasta de exemplo.
Dinheiro vira float só aqui, ao gravar na célula.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from modulos.conferencia_nf import configuracao as cfg
from modulos.conferencia_nf.conferencia import (
    aviso_pasta_de_outro_dia, codigo_contribuicoes,
    escriturar_na_prefeitura, falar_com_fornecedor, formatar_data, nao_optante, nome_unidade, rateios,
    sem_acento,
)
from modulos.conferencia_nf.modelos import FalhaLeitura, NotaPdf, NotaSemPdf, Resultado, Situacao

NEGRITO = Font(bold=True)
FONTE_TITULO = Font(bold=True, color=cfg.COR_FONTE_TITULO)
FUNDO_TITULO = PatternFill("solid", start_color=cfg.COR_FUNDO_TITULO)
_TRACO = Side(style="thin", color=cfg.COR_BORDA)
CAIXA = Border(left=_TRACO, right=_TRACO, top=_TRACO, bottom=_TRACO)     # onde se marca à mão
LINHA_ENTRE_FATOS = Border(top=_TRACO)
QUEBRA_NO_TOPO = Alignment(wrap_text=True, vertical="top")


def _fundo(cor: str) -> PatternFill:
    return PatternFill("solid", start_color=cor)


def _ordem(r: Resultado) -> tuple[int, str]:
    """Divergentes, estornos, conferir, sem PDF, sem nº e OK; dentro de cada um, por fornecedor."""
    return cfg.ORDEM_SITUACAO.index(r.situacao.value), r.fornecedor.upper()


def _aba(livro: Workbook, nome: str, titulos: list[str], larguras: list[int]):
    aba = livro.create_sheet(nome)
    aba.append(titulos)
    for coluna, largura in enumerate(larguras, start=1):
        celula = aba.cell(row=1, column=coluna)
        celula.font, celula.fill = FONTE_TITULO, FUNDO_TITULO
        celula.alignment = Alignment(vertical="center", wrap_text=True)
        aba.column_dimensions[get_column_letter(coluna)].width = largura
    aba.freeze_panes = "A2"
    return aba


def _pintar(aba, linha: int, situacao: Situacao, colunas: int):
    fundo = _fundo(cfg.CORES_SITUACAO[situacao.value])
    for coluna in range(1, colunas + 1):
        aba.cell(row=linha, column=coluna).fill = fundo


def _valor(valor) -> float | None:
    return float(valor) if valor is not None else None


def _motivo(r: Resultado) -> str:
    if r.confere_destinatario == "ERRADO":
        return cfg.MOTIVO_DESTINATARIO
    if r.sem_centro_custo:
        return cfg.MOTIVO_SEM_CENTRO_CUSTO
    if r.motivo_aviso and r.situacao == Situacao.CONFERIR:      # S18/S19/S20
        return r.motivo_aviso
    if r.situacao == Situacao.RETENCAO and r.aliquotas_erradas \
            and all(x.confere for x in r.retencoes):
        return cfg.MOTIVO_ALIQUOTA            # S16: só a alíquota está errada
    return cfg.MOTIVOS[r.situacao.value]


def _gabarito(r: Resultado, lancamento) -> str:
    """S14: o que o gabarito de contas diz do lançamento (vazio se não foi avaliado)."""
    avaliacao = next((a for a in r.contas if a.lancamento is lancamento), None)
    if avaliacao is None:
        return ""
    return avaliacao.resultado if avaliacao.confere else \
        f"{avaliacao.resultado}: {avaliacao.detalhe}"


def _sem_cc(r: Resultado, lancamento) -> bool:
    return any(lancamento is l for l in r.sem_centro_custo)


def _centro_custo(l) -> str:
    return f"{l.centro_custo} - {l.nome_centro_custo}" if l.centro_custo else ""


def _centro_custo_da_linha(r: Resultado, l) -> str | None:
    """Coluna Centro de custo da aba Lançamentos, com o destaque da S11 (falta) e da S18 (539 - CMD)."""
    if any(l is x for x in r.centro_custo_cmd):
        return f"{_centro_custo(l)}: TROCAR PELA CONTA DO ATIVO"
    return _centro_custo(l) or (cfg.MOTIVO_SEM_CENTRO_CUSTO.upper() if _sem_cc(r, l) else None)


def _marca_da_conta(r: Resultado, l) -> str:
    """S19/S20: o aviso que vai na célula "Nome da conta" da aba Lançamentos ("" = nenhum)."""
    marcas = []
    if any(l is x for x in r.diluicao):
        marcas.append(cfg.MARCA_DILUICAO)
    if any(l is x for x in r.reclassificar):
        marcas.append(cfg.MARCA_RECLASSIFICAR_DEBITO if l.conta_debito else cfg.MARCA_RECLASSIFICAR_CREDITO)
    return "; ".join(marcas)


def _arquivo(n: NotaPdf) -> str:
    """O PDF da nota, para abrir e olhar; nota só em XML: o XML (X2)."""
    return n.arquivo_pdf or n.arquivo


def _prefeitura(r: Resultado) -> str:
    return cfg.MARCA_PREFEITURA if escriturar_na_prefeitura(r) else ""


# ---------------------------------------------------------------------------
# Abas
# ---------------------------------------------------------------------------


def _aba_a_mao(livro: Workbook, resultados: list[Resultado]):
    """Os fatos em que é preciso pegar a nota impressa, com o motivo."""
    titulos = ["Motivo", "Fato contábil", "Fornecedor", "Nº NF", "Emissão (DT)", "Valor (débitos)",
               "Partidas x contrapartidas", "O que aconteceu", cfg.COLUNA_PREFEITURA, "Conferido"]
    aba = _aba(livro, cfg.ABA_A_MAO, titulos, [38, 12, 48, 15, 13, 15, 16, 90, 14, 12])
    a_mao = [r for r in resultados if r.situacao != Situacao.OK]
    for r in sorted(a_mao, key=_ordem):
        aba.append([_motivo(r), r.fato.fato, r.fornecedor, ", ".join(r.numeros),
                    ", ".join(formatar_data(d) for d in r.datas), _valor(r.fato.total_debito),
                    "OK" if r.partidas_ok else "NÃO FECHA", " ".join(r.observacoes),
                    _prefeitura(r), ""])
        linha = aba.max_row
        _pintar(aba, linha, r.situacao, len(titulos) - 1)
        aba.cell(row=linha, column=6).number_format = cfg.FORMATO_VALOR_EXCEL
        aba.cell(row=linha, column=8).alignment = QUEBRA_NO_TOPO
        aba.cell(row=linha, column=len(titulos)).border = CAIXA
    aba.auto_filter.ref = aba.dimensions


def _falar(r: Resultado) -> str:
    """S10: "SIM", "conferir no PDF" (Não Optante com federal não lido) ou vazio."""
    if falar_com_fornecedor(r):
        return cfg.MARCA_FALAR_FORNECEDOR
    if nao_optante(r) and not r.nota.federais_lidos:
        return cfg.MARCA_FEDERAIS_NAO_LIDOS
    return ""


def _aba_prefeitura(livro: Workbook, resultados: list[Resultado]):
    """S9: as notas de serviço do lote, para escriturar no site da prefeitura. S10: regime,
    atividade, ISS e impostos federais, e "Falar com o fornecedor" nos Não Optante sem federal
    retido (com a coluna "Retorno do fornecedor" para anotar)."""
    titulos = ["Prestador (nota)", "CNPJ/CPF", "Nº NF", "Emissão", "Valor (nota)",
               "Fato contábil", "Fornecedor (Tasy)", "Situação", "Observações", "Arquivo PDF",
               "Regime (Simples)", "Atividade", "Alíquota ISS (%)", "ISS", "Retenção do ISS",
               "IRRF", "Previdência retida", "Contribuições Sociais retidas",
               "Descrição contrib. sociais", cfg.COLUNA_FALAR_FORNECEDOR,
               "Retorno do fornecedor", "Escriturado"]
    aba = _aba(livro, cfg.ABA_PREFEITURA, titulos,
               [45, 17, 12, 12, 14, 12, 42, 15, 70, 60, 16, 40, 11, 11, 13, 11, 12, 14, 30, 16,
                40, 12])
    servicos = [r for r in resultados if escriturar_na_prefeitura(r)]
    for r in sorted(servicos, key=lambda r: (r.nota.emitente_nome.upper(), int(r.nota.numero))):
        n = r.nota
        aba.append([n.emitente_nome, n.emitente_documento, n.numero, formatar_data(n.emissao),
                    _valor(n.valor), r.fato.fato, r.fornecedor, r.situacao.value,
                    " ".join(r.observacoes), _arquivo(n), n.regime, n.atividade,
                    _valor(n.aliquota_iss), _valor(n.valor_iss), n.retencao_iss, _valor(n.irrf),
                    _valor(n.previdencia_retida), _valor(n.contribuicoes_retidas),
                    _descricao_contribuicoes(n), _falar(r), "", ""])
        linha = aba.max_row
        _pintar(aba, linha, r.situacao, len(titulos) - 1)
        for coluna in (5, 13, 14, 16, 17, 18):
            aba.cell(row=linha, column=coluna).number_format = cfg.FORMATO_VALOR_EXCEL
        aba.cell(row=linha, column=9).alignment = QUEBRA_NO_TOPO
        aba.cell(row=linha, column=len(titulos)).border = CAIXA
    aba.auto_filter.ref = aba.dimensions
    _legenda_codigos(aba)


def _descricao_contribuicoes(n: NotaPdf) -> str:
    """S16a: 'Código 3' -> 'Código 3 - PIS/COFINS/CSLL retidos'; código desconhecido: como veio."""
    codigo = codigo_contribuicoes(n)
    if codigo is None:
        return n.descricao_contribuicoes
    return f"Código {codigo} - {cfg.CODIGOS_CONTRIBUICOES[codigo][0]}"


def _aliquotas(aliquotas) -> str:
    return " ou ".join(f"{a.normalize():f}".replace(".", ",") + "%" for a in aliquotas)


def _legenda_codigos(aba):
    """S16a: embaixo das notas (fora do filtro), o que quer dizer cada código da coluna
    "Descrição contrib. sociais" e a alíquota que o programa espera."""
    aba.append([])
    aba.append([cfg.LEGENDA_CODIGOS_TITULO])
    aba.cell(row=aba.max_row, column=1).font = NEGRITO
    for codigo, (descricao, aliquotas) in cfg.CODIGOS_CONTRIBUICOES.items():
        aba.append([f"Código {codigo} - {descricao}: {_aliquotas(aliquotas)} do serviço"])
    aba.append([cfg.LEGENDA_CODIGOS_NOTA])


def _aba_lancamentos(livro: Workbook, resultados: list[Resultado]):
    """O lote inteiro, na ordem do Tasy, com o que fazer em cada fato."""
    titulos = ["O que fazer", "Fato contábil", "Fornecedor", "Nº NF", "Sequência",
               "Conta débito", "Conta crédito", "Classificação", "Nome da conta",
               "Centro de custo", "Valor débito", "Valor crédito", "Complemento",
               "Gabarito de contas", cfg.COLUNA_PREFEITURA, "Revisado"]
    aba = _aba(livro, cfg.ABA_LANCAMENTOS, titulos,
               [32, 12, 40, 13, 11, 9, 9, 16, 46, 36, 14, 14, 110, 50, 14, 11])
    acoes = {Situacao.OK: cfg.ACAO_OK, Situacao.ESTORNO: cfg.ACAO_ESTORNO}
    for posicao, r in enumerate(resultados):
        cores = cfg.CORES_SITUACAO if posicao % 2 == 0 else cfg.CORES_SITUACAO_CLARAS
        fundo = _fundo(cores[r.situacao.value])
        acao = acoes.get(r.situacao, cfg.ACAO_NOTA_IMPRESSA)
        for indice, l in enumerate(r.fato.lancamentos):
            marca = _marca_da_conta(r, l)
            aba.append([acao, r.fato.fato, r.fornecedor, ", ".join(r.numeros), l.sequencia,
                        l.conta_debito, l.conta_credito, l.classificacao,
                        f"{l.nome_conta}: {marca}" if marca else l.nome_conta,
                        _centro_custo_da_linha(r, l),
                        _valor(l.valor) if l.conta_debito else None,
                        _valor(l.valor) if l.conta_credito else None,
                        l.complemento, _gabarito(r, l) or None, _prefeitura(r), ""])
            linha = aba.max_row
            for coluna in range(1, len(titulos)):
                celula = aba.cell(row=linha, column=coluna)
                celula.fill = fundo
                if indice == 0:
                    celula.border = LINHA_ENTRE_FATOS
            for coluna in (11, 12):
                aba.cell(row=linha, column=coluna).number_format = cfg.FORMATO_VALOR_EXCEL
            if _sem_cc(r, l):           # S11: a célula que falta em destaque
                aba.cell(row=linha, column=10).fill = _fundo(cfg.CORES_SITUACAO["DIVERGENTE"])
                aba.cell(row=linha, column=10).font = NEGRITO
            if marca:                   # S19/S20: o lançamento do aviso em destaque
                aba.cell(row=linha, column=9).fill = _fundo(cfg.COR_DESTAQUE_AVISO)
                aba.cell(row=linha, column=9).font = NEGRITO
            if indice == 0:          # um "Revisado" por fato, na primeira linha dele
                aba.cell(row=linha, column=len(titulos)).border = CAIXA
    aba.auto_filter.ref = aba.dimensions


def _aba_rateios(livro: Workbook, resultados: list[Resultado]):
    """S12: conta de resultado dividida entre centros de custo. Uma linha por lançamento, com o %
    dele na conta e o total da conta, e se o total confere com a nota e com as partidas."""
    titulos = ["Fato contábil", "Fornecedor", "Nº NF", "Situação", "Sequência", "Conta",
               "Classificação", "Nome da conta", "Centro de custo", "Valor", "% da conta",
               "Total da conta no fato", "Total confere", "Complemento"]
    aba = _aba(livro, cfg.ABA_RATEIOS, titulos,
               [12, 40, 13, 15, 11, 9, 16, 40, 40, 14, 11, 16, 34, 110])
    for r in resultados:
        for (_, conta), lancamentos in rateios(r.fato).items():
            total = sum((l.valor for l in lancamentos), Decimal("0.00"))
            if r.nota is None:
                confere = "Partidas OK (sem PDF)" if r.partidas_ok else "Partidas NÃO FECHAM"
            elif r.partidas_ok and r.confere_valor.startswith("OK"):
                confere = "OK (nota e partidas)"
            else:
                confere = "NÃO: ver as observações do fato"
            for l in lancamentos:
                aba.append([r.fato.fato, r.fornecedor, ", ".join(r.numeros), r.situacao.value,
                            l.sequencia, conta, l.classificacao, l.nome_conta, _centro_custo(l),
                            _valor(l.valor), float(l.valor / total) if total else None,
                            _valor(total), confere, l.complemento])
                linha = aba.max_row
                _pintar(aba, linha, r.situacao, len(titulos))
                for coluna in (10, 12):
                    aba.cell(row=linha, column=coluna).number_format = cfg.FORMATO_VALOR_EXCEL
                aba.cell(row=linha, column=11).number_format = "0.00%"
    aba.auto_filter.ref = aba.dimensions


def _aba_contas(livro: Workbook, resultados: list[Resultado]):
    """S14: os débitos em que a conta não é a do Padrão nem a habitual, ou ainda sem histórico.
    Só informativo: a situação do fato não muda."""
    titulos = ["Resultado", "Fato contábil", "Fornecedor", "Nº NF", "Situação do fato",
               "Sequência", "Produto", "Conta lançada", "Valor", "O que o gabarito diz",
               "Complemento"]
    aba = _aba(livro, cfg.ABA_CONTAS, titulos, [24, 12, 40, 13, 16, 11, 40, 50, 14, 70, 110])
    linhas = [(a, r) for r in resultados for a in r.contas if not a.confere]
    for a, r in sorted(linhas, key=lambda x: (cfg.GABARITO_ORDEM.index(x[0].resultado),
                                              x[1].fornecedor.upper())):
        l = a.lancamento
        aba.append([a.resultado, r.fato.fato, r.fornecedor, ", ".join(r.numeros),
                    r.situacao.value, l.sequencia, a.produto or cfg.SEM_PRODUTO,
                    f"{l.classificacao} {l.nome_conta} ({l.conta_debito})", _valor(l.valor),
                    a.detalhe, l.complemento])
        linha = aba.max_row
        fundo = _fundo(cfg.GABARITO_CORES[a.resultado])
        for coluna in range(1, len(titulos) + 1):
            aba.cell(row=linha, column=coluna).fill = fundo
        aba.cell(row=linha, column=9).number_format = cfg.FORMATO_VALOR_EXCEL
    aba.auto_filter.ref = aba.dimensions


def _texto_gabarito(resultados: list[Resultado], gabarito: str | None) -> str:
    if not gabarito:
        return ("NÃO CONFERIDO: escolha a pasta do gabarito de contas na tela (aba \"Gabarito de "
                "contas\" do módulo)")
    contagem = {s: sum(1 for r in resultados for a in r.contas if a.resultado == s)
                for s in cfg.GABARITO_ORDEM}
    return (f"{contagem[cfg.GABARITO_IGUAL_PADRAO] + contagem[cfg.GABARITO_IGUAL_HISTORICO]} "
            f"iguais; {contagem[cfg.GABARITO_FORA_PADRAO]} fora do padrão; "
            f"{contagem[cfg.GABARITO_DIFERENTE]} diferentes do habitual; "
            f"{contagem[cfg.GABARITO_PRODUTO_NOVO] + contagem[cfg.GABARITO_FORNECEDOR_NOVO]} "
            f"sem histórico ({gabarito})")


def _aba_pdf_x_tasy(livro: Workbook, resultados: list[Resultado]):
    """Uma linha por fato, com o que foi lido do PDF ao lado."""
    titulos = ["Situação", "Fato contábil", "Fornecedor (Tasy)", "Nº NF (Tasy)", "DT (Tasy)",
               "Total débitos", "Total créditos", "Partidas x contrapartidas", "Tipo",
               "Nº (nota)", "Emissão (nota)", "Valor (nota)", "Emitente (nota)", "CNPJ/CPF",
               "Destinatário / tomador (nota)", "Número", "Data", "Valor", "Unidade", "Observações",
               "Arquivo PDF", "Lote (.csv)"]
    aba = _aba(livro, cfg.ABA_PDF_X_TASY, titulos,
               [15, 12, 42, 13, 12, 14, 14, 16, 8, 12, 13, 14, 42, 17, 40, 10, 10, 10, 10, 90, 60,
                40])
    for r in sorted(resultados, key=_ordem):
        n = r.nota
        aba.append([
            r.situacao.value, r.fato.fato, r.fornecedor, ", ".join(r.numeros),
            ", ".join(formatar_data(d) for d in r.datas),
            _valor(r.fato.total_debito), _valor(r.fato.total_credito),
            "OK" if r.partidas_ok else "NÃO FECHA",
            n.tipo if n else "", n.numero if n else "", formatar_data(n.emissao) if n else "",
            _valor(n.valor) if n else None, n.emitente_nome if n else "",
            n.emitente_documento if n else "",
            nome_unidade(n.destinatario_documento) if n and n.destinatario_documento else "",
            r.confere_numero, r.confere_data, r.confere_valor, r.confere_destinatario,
            " ".join(r.observacoes), _arquivo(n) if n else "", r.fato.arquivo,
        ])
        linha = aba.max_row
        _pintar(aba, linha, r.situacao, len(titulos))
        for coluna in (6, 7, 12):
            aba.cell(row=linha, column=coluna).number_format = cfg.FORMATO_VALOR_EXCEL
        aba.cell(row=linha, column=20).alignment = QUEBRA_NO_TOPO
    aba.auto_filter.ref = aba.dimensions


def _situacao_nao_autorizada(nota: NotaPdf) -> bool:
    return bool(nota.situacao) and \
        sem_acento(nota.situacao).upper() != cfg.SITUACAO_NOTA_AUTORIZADA


def _aba_sem_lancamento(livro: Workbook, notas: list[NotaPdf], sem_pdf: list[NotaSemPdf]):
    """PDFs que não casaram com nenhum fato, e as notas do _sem_pdf.txt."""
    titulos = ["Tipo", "Nº", "Emissão", "Valor", "Emitente", "CNPJ/CPF", "Observações",
               "Arquivo PDF"]
    aba = _aba(livro, cfg.ABA_SEM_LANCAMENTO, titulos, [8, 12, 12, 14, 45, 17, 70, 70])
    sobras = [n for n in notas if not n.usada]
    for n in sorted(sobras, key=lambda n: (n.emitente_nome.upper(), int(n.numero))):
        observacoes = ["Nota não encontrada no lote."]
        if n.repetida_de:
            observacoes = [f"PDF repetido: mesma nota do arquivo {n.repetida_de}."]
        elif n.emitente_documento.startswith(cfg.RAIZ_CNPJ_FUNDACAO):
            observacoes = ["Nota emitida pela própria Fundação (serviço prestado, não é compra)."]
        if _situacao_nao_autorizada(n):
            observacoes.append(f"Situação da nota: {n.situacao}.")
        aba.append([n.tipo, n.numero, formatar_data(n.emissao), _valor(n.valor), n.emitente_nome,
                    n.emitente_documento, " ".join(observacoes), _arquivo(n)])
        aba.cell(row=aba.max_row, column=4).number_format = cfg.FORMATO_VALOR_EXCEL
    for s in sem_pdf:
        aba.append([cfg.TIPO_NFE, s.numero, "", None, "", s.emitente_documento,
                    f"Listada em {cfg.ARQUIVO_SEM_PDF}: sem DANFE disponível (precisa do XML "
                    f"completo). Chave {s.chave}.", ""])
    aba.auto_filter.ref = aba.dimensions


def _aba_erros(livro: Workbook, falhas: list[FalhaLeitura]):
    aba = _aba(livro, cfg.ABA_ERROS, ["Arquivo", "O que aconteceu"], [80, 100])
    for falha in falhas:
        aba.append([falha.arquivo, falha.motivo])


def _texto_centro_custo(resultados: list[Resultado]) -> str:
    """S11 no Resumo: conferido (quantos sem) ou não conferido (o arquivo não traz)."""
    if not resultados or not all(r.fato.com_centro_custo for r in resultados):
        return ("NÃO CONFERIDO: o arquivo do lote não traz o centro de custo (use a exportação "
                "\"Movimento contábil\" do Tasy)")
    faltando = sum(len(r.sem_centro_custo) for r in resultados)
    if not faltando:
        return "Conferido: todos com centro de custo"
    fatos = sum(1 for r in resultados if r.sem_centro_custo)
    return f"{faltando} lançamento(s) SEM centro de custo, em {fatos} fato(s): DIVERGENTE"


def _texto_unidade(resultados: list[Resultado], unidade: str | None) -> str:
    """S15: a unidade escolhida na tela e quantas notas vieram com outro CNPJ."""
    if not unidade:
        return "Não conferido (nenhuma unidade escolhida)."
    erradas = sum(1 for r in resultados if r.confere_destinatario == "ERRADO")
    nao_lidas = sum(1 for r in resultados if r.confere_destinatario == "NÃO LIDO")
    texto = f"{nome_unidade(unidade)}: " + (
        f"{erradas} nota(s) com CNPJ errado (vermelho)" if erradas else "todas as notas casadas "
        "com o CNPJ certo")
    return texto + (f"; {nao_lidas} sem o CNPJ lido no PDF (conferir)." if nao_lidas else ".")


def _linhas_xml(notas: list[NotaPdf]) -> list[tuple]:
    """Contagem das notas lidas. Sem nenhum XML, a linha de sempre ("PDFs lidos")."""
    xmls = [n for n in notas if n.xml]
    if not xmls:
        return [("PDFs lidos", len(notas))]
    return [("Notas lidas (XML e PDF da mesma nota contam uma vez)", len(notas)),
            ("  pelo XML (com o PDF junto)", sum(1 for n in xmls if n.arquivo_pdf)),
            ("  pelo XML (sem o PDF: situação não conferida)", sum(1 for n in xmls
                                                               if not n.arquivo_pdf)),
            ("  pelo PDF (sem o XML)", len(notas) - len(xmls))]


def _aba_resumo(aba, resultados: list[Resultado], notas: list[NotaPdf],
                falhas_pdf: list[FalhaLeitura], sem_pdf: list[NotaSemPdf],
                arquivos_lote: list[str], gerado_em: datetime, gabarito: str | None = None,
                unidade: str | None = None):
    contagem = {s: sum(1 for r in resultados if r.situacao == s) for s in Situacao}
    a_mao = sum(1 for r in resultados if r.situacao != Situacao.OK)
    sobras = [n for n in notas if not n.usada]
    outro_dia = aviso_pasta_de_outro_dia(notas)          # S17: ocupa a linha em branco (linha 4)
    linhas = [
        ("Conferência de Notas Fiscais — lote do Tasy x PDFs das notas", None),
        ("Gerado em", gerado_em.strftime("%d/%m/%Y %H:%M:%S")),
        ("Arquivo(s) do lote", "; ".join(arquivos_lote)),
        ("ATENÇÃO: pasta dos PDFs", outro_dia) if outro_dia else (None, None),
        ("Fatos contábeis no lote", len(resultados)),
        ("  VERDE — conferidos pelo programa: só olhar as contas e revisar",
         contagem[Situacao.OK]),
        ("  CONFERIR À MÃO", a_mao),
        ("      PDF da nota não veio", contagem[Situacao.SEM_PDF]),
        ("      não é nota fiscal (recibo, doação, taxa...)", contagem[Situacao.SEM_NUMERO]),
        ("      PDF não bate com o lançamento", contagem[Situacao.DIVERGENTE]),
        ("      casou com o PDF, mas tem observação", contagem[Situacao.CONFERIR]),
        ("      lançamento e estorno que se anulam", contagem[Situacao.ESTORNO]),
        ("      retenção da nota não bate com o lançamento (roxo)", contagem[Situacao.RETENCAO]),
        ("Notas de serviço para escriturar na prefeitura (com PDF)",
         sum(1 for r in resultados if escriturar_na_prefeitura(r))),
        ("      Não Optante sem imposto federal retido: falar com o fornecedor",
         sum(1 for r in resultados if falar_com_fornecedor(r))),
        ("Centro de custo nas contas de resultado (3 e 4)",
         _texto_centro_custo(resultados)),
        ("      centro de custo 539 - CMD: trocar pela conta do ativo",
         sum(1 for r in resultados if r.centro_custo_cmd)),
        ("Software, uniforme ou enxoval acima de R$ 1.000,00: verificar a diluição",
         sum(1 for r in resultados if r.diluicao)),
        ("Fornecedores a reclassificar: no crédito, trocar pela conta do fornecedor?; no débito, foi "
         "provisionada?", sum(1 for r in resultados if r.reclassificar)),
        ("Fatos com rateio de centro de custo (aba Rateios)",
         sum(1 for r in resultados if rateios(r.fato))),
        ("Gabarito de contas (só aviso)", _texto_gabarito(resultados, gabarito)),
        ("Unidade conferida (CNPJ do destinatário / tomador da nota)",
         _texto_unidade(resultados, unidade)),
        (None, None),
        ("Como usar", None),
        (f"  Aba {cfg.ABA_A_MAO}", "A lista das notas para separar no papel e conferir à mão, com "
                                  "o motivo de cada uma."),
        (f"  Aba {cfg.ABA_PREFEITURA}", "As notas de serviço do lote (PDF de DANFSe), para "
                                       "escriturar no site da prefeitura. Nota de serviço sem PDF "
                                       "não aparece: confira as do motivo \"PDF da nota não veio\". "
                                       "\"Falar com o fornecedor\" = SIM: prestador Não Optante sem "
                                       "nenhum imposto federal retido (pergunte ao fornecedor e anote "
                                       "em \"Retorno do fornecedor\")."),
        (f"  Aba {cfg.ABA_LANCAMENTOS}", "O lote inteiro, na ordem do Tasy. Verde: número, data, "
                                        "valor e partidas já conferidos; falta só olhar as contas."),
        (f"  Aba {cfg.ABA_RATEIOS}", "Contas de resultado divididas entre centros de custo: "
                                    "valor e % de cada um e o total da conta. Só informativo; se "
                                    "o total não bater com a nota ou as partidas, o fato fica "
                                    "DIVERGENTE."),
        (f"  Aba {cfg.ABA_CONTAS}", "Débitos em conta diferente do Padrão (laranja) ou da "
                                   "habitual (amarelo), e os ainda sem histórico (cinza), pelo "
                                   "gabarito de contas. Só aviso: a cor do fato não muda."),
        (f"  Aba {cfg.ABA_PDF_X_TASY}", "O que o programa leu de cada PDF ao lado do lançamento."),
        (None, None),
        *_linhas_xml(notas),
        ("  casados com um fato contábil", sum(1 for n in notas if n.usada)),
        ("  repetidos (mesma nota em dois arquivos)", sum(1 for n in notas if n.repetida_de)),
        ("  sem lançamento neste lote", sum(1 for n in sobras if not n.repetida_de)),
        ("PDFs com erro de leitura", len(falhas_pdf)),
        (f"Notas sem DANFE ({cfg.ARQUIVO_SEM_PDF})", len(sem_pdf)),
        (None, None),
        ("Como o valor é conferido", "Valor total da nota (PDF) x soma dos débitos do fato."),
        ("Como as retenções são conferidas",
         f"Nota de serviço: IRRF (conta {cfg.CONTA_IRRF_PJ}, ou {cfg.CONTA_IRRF_PF} se o prestador "
         f"tem CPF), INSS ({cfg.CONTA_INSS}), PIS/COFINS/CSLL ({cfg.CONTA_PIS_COFINS_CSLL}) e ISS "
         f"retido ({cfg.CONTA_ISS_RETIDO}) da nota x créditos do fato nessas contas. Não bate: "
         "roxo."),
        ("Como a nota é casada", "Pelo número; o fornecedor (nome parecido) ou o valor confirmam."),
    ]
    for texto, valor in linhas:
        aba.append([texto, valor])
    aba["A1"].font = Font(bold=True, size=14)
    for linha in aba.iter_rows(min_row=2):
        if linha[0].value and not str(linha[0].value).startswith("  "):
            linha[0].font = NEGRITO
        linha[1].alignment = Alignment(horizontal="left")
    aba.column_dimensions["A"].width = 66
    aba.column_dimensions["B"].width = 100
    # as duas pilhas de trabalho em destaque: verde e "conferir à mão"
    for numero_linha, situacao in ((6, "OK"), (7, "SEM PDF")):
        for celula in aba[numero_linha]:
            celula.fill = _fundo(cfg.CORES_SITUACAO[situacao])
            celula.font = NEGRITO
    if outro_dia:
        for celula in aba[4]:
            celula.fill = _fundo(cfg.CORES_SITUACAO["DIVERGENTE"])
            celula.font = NEGRITO


# ---------------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------------


def gerar_relatorio(caminho: Path, resultados: list[Resultado], notas: list[NotaPdf],
                    falhas_lote: list[FalhaLeitura], falhas_pdf: list[FalhaLeitura],
                    sem_pdf: list[NotaSemPdf], arquivos_lote: list[str],
                    gerado_em: datetime | None = None, gabarito: str | None = None,
                    unidade: str | None = None) -> Path:
    """Grava o relatório. Levanta OSError se não conseguir gravar (ex.: arquivo aberto).
    unidade: CNPJ da unidade escolhida na tela (S15)."""
    livro = Workbook()
    resumo = livro.active
    resumo.title = cfg.ABA_RESUMO
    _aba_a_mao(livro, resultados)
    _aba_prefeitura(livro, resultados)
    _aba_lancamentos(livro, resultados)
    _aba_rateios(livro, resultados)
    _aba_contas(livro, resultados)
    _aba_pdf_x_tasy(livro, resultados)
    _aba_sem_lancamento(livro, notas, sem_pdf)
    _aba_erros(livro, falhas_lote + falhas_pdf)
    _aba_resumo(resumo, resultados, notas, falhas_pdf, sem_pdf, arquivos_lote,
                gerado_em or datetime.now(), gabarito, unidade)
    caminho = Path(caminho)
    livro.save(caminho)
    return caminho
