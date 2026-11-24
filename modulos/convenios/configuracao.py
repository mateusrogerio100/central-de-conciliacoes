"""Constantes do módulo Convênios: o que muda de tempos em tempos fica aqui, não no meio do código."""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Razão Convênios (exportado do Tasy: .xlsx ou o ".xls" que é texto com tabulação) — seção 3.1
# ---------------------------------------------------------------------------

# Linha de títulos de cada página (as colunas são achadas por estes textos, nunca pela letra).
RAZAO_TITULO_DATA = "Data"
RAZAO_TITULO_HISTORICO = "Histórico"
RAZAO_TITULO_LOTE = "Lote"
RAZAO_TITULO_DEBITOS = "Débitos"
RAZAO_TITULO_CREDITOS = "Créditos"
RAZAO_TITULOS = (RAZAO_TITULO_DATA, RAZAO_TITULO_HISTORICO, RAZAO_TITULO_LOTE, RAZAO_TITULO_DEBITOS,
                 RAZAO_TITULO_CREDITOS)

RAZAO_TEXTO_PERIODO = "Período"
RAZAO_TEXTO_SALDO_ANTERIOR = "Saldo anterior"
# "40075 - 4.01.05.01.0001  Convênio Prefeitura Ambulatório"
RE_CONTA = re.compile(r"^\s*(\d+)\s*-\s*(\d+(?:\.\d+)+)\s+(.+?)\s*$")
# "Total - 40075 - 4.01.05.01.0001  Convênio Prefeitura Ambulatório"
RE_TOTAL_CONTA = re.compile(r"^\s*Total\s*-\s*(\d+)\s*-")

# O "Excel" do Tasy (.xls) é um texto com uma linha por linha do relatório e as células separadas por tabulação.
# Codificação do Windows; as datas vêm como texto "31/08/2026" (os valores "1.234,56" o para_decimal já lê).
RAZAO_TEXTO_SEPARADOR = "\t"
RAZAO_TEXTO_CODIFICACOES = ("utf-8", "cp1252")       # na ordem; a primeira que servir
RE_DATA_TEXTO = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")

# ---------------------------------------------------------------------------
# Planilha RECEITAS DE CONVÊNIOS (.xlsx) — seção 3.2
# ---------------------------------------------------------------------------

PLANILHA_PREFIXO_ABA = "Receita de Convênios"     # a aba do ano termina com o ano ("... 2026")
PLANILHA_TITULO_CONVENIO = "CONVÊNIO"
PLANILHA_TITULO_ACUMULADO = "Acumulado"
PLANILHA_TOTAL = "TOTAL RECEITAS"
PLANILHA_SALDO_CONTABIL = "Saldo Contábil"
PLANILHA_DIFERENCA = "Diferença"

ASSINATURA_XLS_ANTIGO = b"\xd0\xcf\x11\xe0"
MENSAGEM_XLS_ANTIGO = ("{nome}: é um Excel antigo (.xls 97-2003). Abra no Excel e salve como .xlsx "
                       "(Pasta de Trabalho do Excel).")

# ---------------------------------------------------------------------------
# Equivalências (equivalencias.csv, editável) — seção 3.3
# ---------------------------------------------------------------------------

ARQUIVO_EQUIVALENCIAS = "equivalencias.csv"
PASTA_CONFIG = "config"                          # ao lado da planilha de receitas
EQUIVALENCIAS_COLUNAS = ("Nome_no_razao", "Linha_da_planilha", "Obs")
EQUIVALENCIAS_FABRICA = ("modulos", "convenios", "modelos_configuracao", ARQUIVO_EQUIVALENCIAS)
CSV_SEPARADOR = ";"
CSV_CODIFICACOES = ("utf-8-sig", "cp1252")

# Linha_da_planilha especial: o valor não entra em linha nenhuma, vai para "Não identificado" com aviso
# (ex.: IAMSPE, enquanto não há regra para separar SC de HC; decisão do usuário, 29/10/2026).
LINHA_NAO_IDENTIFICADO = "NÃO IDENTIFICADO"

# ---------------------------------------------------------------------------
# Nome do convênio no histórico — regras C1 a C3
# ---------------------------------------------------------------------------

_MESES = "Jan|Fev|Mar|Abr|Mai|Jun|Jul|Ago|Set|Out|Nov|Dez"
# C1: "Faturamento Mês  NF 299141 PM de Cidade Teta Set/2026  Protocolo 152516"
RE_FATURAMENTO = re.compile(rf"^Faturamento\s+M[eê]s\s+(?:NF\.?\s*\d+\s+)?(.+?)\s+(?:{_MESES})/\d{{4}}\b",
                            re.IGNORECASE)
# C2: "Referente Fundação do ABC NF. 89592 Nota Fiscal Avulsa"
RE_REFERENTE = re.compile(r"^Referente\s+(.+?)\s+NF\.\s*\d+", re.IGNORECASE)
# C2 que não é nome: "Referente NFSE 89617 Faturamento convênio ..." (vai para a C3)
RE_NOME_QUE_E_DOCUMENTO = re.compile(r"^NFS?E?\b", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Comparação de nomes — regra C4
# ---------------------------------------------------------------------------

PALAVRAS_IGNORADAS = {"de", "da", "do", "das", "dos"}

# ---------------------------------------------------------------------------
# Preenchimento da cópia (P1 a P5) e saídas — seções 4 e 5
# ---------------------------------------------------------------------------

# O que aconteceu com cada linha da planilha no mês (coluna "Situação" do relatório)
SITUACAO_PREENCHIDA = "preenchida"
SITUACAO_SUBSTITUIDA = "substituída"
SITUACAO_NOVA = "linha nova (convênio novo)"
SITUACAO_MANTIDA = "mantida: sem lançamento no razão"       # mês substituído; decisão do usuário, 29/10/2026
SITUACAO_SEM_MOVIMENTO = "sem lançamento no mês"             # P2: fica vazia
SITUACAO_NAO_IDENTIFICADO = "não identificado: preencher à mão"

# a fórmula do TOTAL RECEITAS do mês: "=SUM(K5:K56)"
RE_FORMULA_SOMA = re.compile(r"^=\s*SUM\(\s*\$?([A-Z]{1,3})\$?(\d+)\s*:\s*\$?([A-Z]{1,3})\$?(\d+)\s*\)$", re.IGNORECASE)

NOMES_MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
               "outubro", "novembro", "dezembro")

NOME_COPIA ="RECEITAS DE CONVÊNIOS {mes:02d}{ano:04d}.xlsx"
NOME_RELATORIO = "Conferencia_Convenios_{ano:04d}-{mes:02d}_{data_hora}.xlsx"
FORMATO_DATA_HORA_NOME = "%Y-%m-%d_%H%M%S"

ABA_RESUMO = "Resumo"
ABA_POR_CONVENIO = "Por convênio"
ABA_LANCAMENTOS = "Lançamentos"
ABA_AVISOS = "Avisos"

COR_FUNDO_TITULO = "1F4E78"
COR_FONTE_TITULO = "FFFFFF"
COR_OK = "C6EFCE"              # verde: a conferência fecha
COR_PROBLEMA = "FFC7CE"        # rosa: não identificado, diferença
COR_ATENCAO = "FFEB9C"         # amarelo: linha nova, nome achado dentro do histórico, valor mantido
COR_CINZA = "D9D9D9"           # sem lançamento no mês
