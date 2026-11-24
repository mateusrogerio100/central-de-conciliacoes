"""Textos, títulos e formatos do módulo Planilha HM (o que muda quando o Tasy muda um relatório)."""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Eventos (seção 2.1): "Conferência Lançamentos Contábeis" do Tasy
# ---------------------------------------------------------------------------

EVENTOS_TITULO = "Conferência Lançamentos Contábeis"
EVENTOS_TEXTO_COMPETENCIA = "Competência"
EVENTOS_TEXTO_EVENTO = "Evento"
EVENTOS_TEXTO_TOTAL = "Total Evento"
# cabeçalho e rodapé de cada página: ignorados, não interrompem o bloco do evento (R1)
EVENTOS_TEXTOS_CABECALHO = ("Pág.", "Médico")
EVENTOS_INICIO_RODAPE = "FPTE"
# o .xlsx "tratado" de agosto (só para teste): a aba com o relatório como saiu do Tasy
EVENTOS_ABA_XLSX = "Plan1"
RE_COMPETENCIA_TEXTO = re.compile(r"^\s*(\d{1,2})/(\d{4})\s*$")
# valor em texto da aba Plan1: "15.854,34" ou "57,03-" (sinal no fim)
RE_VALOR_TEXTO = re.compile(r"^\s*(-)?\s*([\d.]+,\d{1,2})\s*(-)?\s*$")

# ---------------------------------------------------------------------------
# Planilha HM (seção 2.3)
# ---------------------------------------------------------------------------

RE_ABA_ANO = re.compile(r"^\s*(\d{4})\s*$")                       # a aba "2026"
RE_ABA_SENIOR = re.compile(r"^\s*senior\s+(\d{1,2})\s+(\d{4})\s*$", re.IGNORECASE)
NOME_ABA_SENIOR = "Senior {mes:02d} {ano:04d}"
# títulos da aba do ano (linha de abertura de cada seção); a coluna do nome é a que vem logo depois de "EVENTO"
PLANILHA_TITULO_EVENTO = "EVENTO"
PLANILHA_TITULO_CONCATENO = "Concateno"
PLANILHA_TITULO_CODIGO = "Cód."
PLANILHA_TITULO_CENTRO = "Centros de Custos"
NOMES_MESES = ("JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO", "SETEMBRO",
               "OUTUBRO", "NOVEMBRO", "DEZEMBRO")
PLANILHA_TEXTO_TOTAL_GERAL = "TOTAL GERAL"
PLANILHA_TEXTO_LOTE = "LOTE REPASSE"
# títulos da aba Senior (linha 1)
SENIOR_TITULOS = ("Evento", "Cód.", "Centro de custo", "Valor", "Concateno", "Conf.", "Conf.1")
# referência a uma célula numa fórmula ("N95", "$C7"); referência a coluna inteira ("$A:$A") não casa
RE_REFERENCIA = re.compile(r"(?<![A-Za-z0-9_!:'])\$?([A-Z]{1,3})\$?(\d+)(?![\d(:])")

# ---------------------------------------------------------------------------
# Movimento (seção 2.2): lote de Repasse a terceiros do Tasy (.csv)
# ---------------------------------------------------------------------------

MOVIMENTO_SEPARADOR = ";"
MOVIMENTO_CODIFICACOES = ("utf-8-sig", "cp1252")   # sem UTF-16 (reconhecido pelos bytes, em leitor_movimento)
MOVIMENTO_TITULO_LOTE = "Fato contábil"
MOVIMENTO_TITULO_DATA = "Data movimento"
MOVIMENTO_TITULO_DEBITO = "Débito"
MOVIMENTO_TITULO_CREDITO = "Crédito"
MOVIMENTO_TITULO_VALOR = "Valor"
# "Histórico" aparece duas vezes: a 1ª é o código do histórico, a 2ª é o texto do lançamento
MOVIMENTO_TITULO_HISTORICO = "Histórico"
MOVIMENTO_TITULO_CONTA_DEBITO = "Conta débito"
MOVIMENTO_TITULO_CLASSIFICACAO_DEBITO = "Classificação débito"
MOVIMENTO_TITULOS_OBRIGATORIOS = (MOVIMENTO_TITULO_LOTE, MOVIMENTO_TITULO_DATA, MOVIMENTO_TITULO_DEBITO,
                                  MOVIMENTO_TITULO_CREDITO, MOVIMENTO_TITULO_VALOR, MOVIMENTO_TITULO_CONTA_DEBITO,
                                  MOVIMENTO_TITULO_CLASSIFICACAO_DEBITO)
RE_DATA_TEXTO = re.compile(r"^\s*(\d{1,2})/(\d{1,2})/(\d{4})")
# o evento no texto do histórico: "HM Físico Médico (Evento 3171)" ou "Evento 3013 - HM Preceptoria"
RE_EVENTO_HISTORICO = re.compile(r"\(\s*evento\s+(\d+)\s*\)|^\s*evento\s+(\d+)\s*-", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Tabela conta → seção (R5a): secoes_contas.csv na pasta config ao lado da Planilha HM
# ---------------------------------------------------------------------------

PASTA_CONFIG = "config"
ARQUIVO_SECOES = "secoes_contas.csv"
SECOES_FABRICA = ("modulos", "planilha_hm", "modelos_configuracao", ARQUIVO_SECOES)
SECOES_TITULO_CLASSIFICACAO = "Classificacao"
SECOES_TITULO_CONTA = "Conta"
SECOES_TITULO_SECAO = "Secao"
SECOES_COLUNAS = (SECOES_TITULO_CLASSIFICACAO, SECOES_TITULO_CONTA, SECOES_TITULO_SECAO)
CSV_SEPARADOR = ";"
CSV_CODIFICACOES = ("utf-8-sig", "cp1252")
# o código do histórico "0" não identifica um evento (seção 2.2): não serve para achar a conta
CODIGOS_HISTORICO_SEM_EVENTO = ("", "0")

# ---------------------------------------------------------------------------
# Preenchimento (R3–R8)
# ---------------------------------------------------------------------------

RESPOSTA_SECAO_NOVA = "<seção nova>"          # resposta da pergunta da R5: criar uma seção com o nome da conta
TEXTO_TOTAL_SECAO_NOVA = "TOTAL {nome}"        # R6
ORIGEM_TABELA = "tabela conta → seção"
ORIGEM_TABELA_MONTADA = "tabela montada agora"
ORIGEM_RESPOSTA = "resposta na tela"

# ---------------------------------------------------------------------------
# Saídas (seção 5)
# ---------------------------------------------------------------------------

NOME_COPIA = "{mes:02d} Planilha HM {ano:04d} Atualizada em {data} COMPETENCIA {mes:02d}.xlsx"
FORMATO_DATA_NOME = "%d-%m-%Y"                  # "Atualizada em" = data do processamento
NOME_RELATORIO = "Conferencia_PlanilhaHM_{ano:04d}-{mes:02d}_{data_hora}.xlsx"
FORMATO_DATA_HORA_NOME = "%Y-%m-%d_%H%M%S"

ABA_RESUMO = "Resumo"
ABA_EVENTOS = "Eventos"
ABA_LINHAS_CRIADAS = "Linhas criadas"
ABA_SEM_EVENTO = "Movimento sem evento"         # só quando o TOTAL GERAL não bate com o Movimento (R9)
ABA_AVISOS = "Avisos"

SITUACAO_OK = "ok"
SITUACAO_NOVO = "evento novo (linhas criadas)"
SITUACAO_CC_NOVO = "ok (CC novo criado)"
SITUACAO_FORA = "fora da planilha"

COR_FUNDO_TITULO = "1F4E78"
COR_FONTE_TITULO = "FFFFFF"
COR_OK = "C6EFCE"              # verde: a conferência fecha
COR_PROBLEMA = "FFC7CE"        # rosa: diferença, evento com erro ou fora da planilha
COR_ATENCAO = "FFEB9C"         # amarelo: linha criada, aviso de atenção

# ---------------------------------------------------------------------------
# Tela (seção 7)
# ---------------------------------------------------------------------------

MESES_ABREVIADOS = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")
CHAVE_PREFERENCIAS = "planilha_hm"             # %APPDATA%\CentralConciliacoes\planilha_hm.json
PREFERENCIAS = ("saida",)                      # só a pasta de saída: as entradas mudam todo mês
TEXTO_OPCAO_SECAO_NOVA = "Criar seção nova: {nome}"
