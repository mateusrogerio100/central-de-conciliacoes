"""Constantes do módulo Notas Pendentes: o que muda de tempos em tempos fica aqui, não no meio do código."""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Pasta das notas do mês — seção 3.1 e regras L1 a L5
# ---------------------------------------------------------------------------

EXTENSAO_PDF = ".pdf"
PREFIXO_TEMPORARIO = "~$"          # arquivo temporário do Office: ignorado sem aviso
# A pasta de cada mês se chama MMAAAA ("102026"): ao mudar a competência, a tela troca para a irmã do mês novo.
RE_NOME_PASTA_MES = re.compile(r"^\d{6}$")
NOME_PASTA_MES = "{mes:02d}{ano:04d}"

# L1: número do responsável no começo do nome, seguido de um separador ("13.DANFSe", "13+DANFSe",
# "15-DANFSe", "4 - DANFSe", "7_DANFSe"). Aplicado ao nome SEM a extensão.
RE_NUMERO_ARQUIVO = re.compile(r"^\s*(\d+)\s*[.\-+_ ]\s*(.*)$")

# L3: o resto do nome no padrão do emissor: "DANFSe-<nº da nota>-<fornecedor>-<chave>" (ou "DANFE-...").
RE_NOME_NOTA = re.compile(r"^\s*DANFS?E?\s*-\s*(\d+)\s*-\s*(.+?)\s*-\s*(\d{30,})\s*$", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Check list de contratos: só a aba Emails — seção 3.2 (copiado do checklist_contratos)
# ---------------------------------------------------------------------------

ABA_EMAILS = "Emails"

# "Nome <email>", "<email>" ou só o e-mail (pode vir com vírgula ou espaço sobrando).
RE_CONTATO = re.compile(r"^\s*(.*?)\s*<\s*([^<>\s]+@[^<>\s]+?)\s*>\s*[,;]?\s*$")
RE_EMAIL_SOZINHO = re.compile(r"^\s*([^<>\s,;]+@[^<>\s,;]+)\s*[,;]?\s*$")
RE_APELIDO = re.compile(r"\((.+?)\)")

# Célula ao lado do contato: os números que ele recebe ("11; 12; 13"), "Todos" ou "Todos CMD".
RE_SEPARADOR_CODIGOS = re.compile(r"\s*[;,/]\s*")
CODIGO_TODOS = "todos"
CODIGO_TODOS_CMD = "todos cmd"     # lido para não virar aviso, mas não usado: a pasta é da Hospital Exemplo (E2)
# "Cópia": vai em cópia (Cc) de todos os e-mails, a não ser que já esteja no Para (28/10/2026)
CODIGO_COPIA = "copia"
CODIGO_COPIA_CMD = "copia cmd"     # lido para não virar aviso, mas não usado: a pasta é da Hospital Exemplo (E2)

# ---------------------------------------------------------------------------
# Modelo do e-mail (modelo_email.txt) — seção 3.3
# ---------------------------------------------------------------------------

ARQUIVO_MODELO = "modelo_email.txt"
# A tela procura o modelo nesta pasta, ao lado das pastas dos meses (decisão do usuário, 26/10/2026).
PASTA_MODELO_SUGERIDA = "config"
# Cópia de fábrica, dentro do programa (no .exe, com --add-data).
MODELO_FABRICA = ("modulos", "notas_pendentes", "modelos_configuracao", ARQUIVO_MODELO)
MODELO_CODIFICACOES = ("utf-8-sig", "cp1252")

PREFIXO_ASSUNTO = "assunto:"       # 1ª linha do modelo, comparada sem acento e em minúsculas
RE_MARCADOR = re.compile(r"\{([^{}]*)\}")
MARCADOR_COMPETENCIA = "competencia"                    # 10/2026
MARCADOR_COMPETENCIA_EXTENSO = "competencia_extenso"    # outubro/2026
MARCADOR_PRAZO = "prazo"                                # 29/10/2026
MARCADOR_LISTA_NOTAS = "lista_notas"                    # a lista das notas anexas (E3)
MARCADORES = (MARCADOR_COMPETENCIA, MARCADOR_COMPETENCIA_EXTENSO, MARCADOR_PRAZO, MARCADOR_LISTA_NOTAS)
# Faltando no modelo = aviso (pode ter sido de propósito); os e-mails saem do mesmo jeito.
MARCADORES_ESPERADOS = (MARCADOR_PRAZO, MARCADOR_LISTA_NOTAS)

# ---------------------------------------------------------------------------
# Competência e prazo — seção 3.4
# ---------------------------------------------------------------------------

RE_MES_DIGITADO = re.compile(r"^\s*(\d{1,2})\s*/\s*(\d{4})\s*$")   # "10/2026", na tela
MESES_POR_EXTENSO = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
                     "setembro", "outubro", "novembro", "dezembro")

# ---------------------------------------------------------------------------
# E-mails — E5
# ---------------------------------------------------------------------------

LIMITE_ANEXOS_BYTES = 20 * 1024 * 1024     # o Gmail aceita 25 MB; acima de 20 MB o e-mail fica de fora
MARCADOR_ITEM_LISTA = "- "                 # cada nota do {lista_notas}: "- NF 4615 – Fornecedor"

# Por que as notas ficaram sem e-mail (prévia e relatório)
MOTIVO_SEM_NUMERO = "O nome do arquivo não começa com o número do responsável."
MOTIVO_SEM_CONTATO = "Nenhum contato da aba Emails tem o número {numero}."
MOTIVO_LIMITE = "Os anexos somam {tamanho} e passam do limite de {limite} por e-mail."

# ---------------------------------------------------------------------------
# Saídas — seção 5
# ---------------------------------------------------------------------------

NOME_PREVIA = "Previa_notas_pendentes_{ano:04d}-{mes:02d}_{data_hora}.html"
NOME_RELATORIO = "Notas_pendentes_{ano:04d}-{mes:02d}_{data_hora}.xlsx"
# E7: os e-mails para o Claude Desktop criar os rascunhos, sem anexos (decisão do usuário, 26/10/2026)
NOME_TEXTO_CLAUDE = "Emails_para_Claude_Desktop_{ano:04d}-{mes:02d}_{data_hora}.txt"
FORMATO_DATA_HORA_NOME = "%Y-%m-%d_%H%M%S"

ABA_RESUMO = "Resumo"
ABA_ARQUIVOS = "Arquivos"
ABA_AVISOS = "Avisos"

SITUACAO_ANEXADA = "Anexada"
SITUACAO_SEM_NUMERO = "Sem número"
SITUACAO_SEM_CONTATO = "Número sem contato"
SITUACAO_LIMITE = "Anexos acima do limite"
SITUACAO_IGNORADO = "Ignorado (não é PDF)"

COR_FUNDO_TITULO = "1F4E78"
COR_FONTE_TITULO = "FFFFFF"
COR_ANEXADA = "C6EFCE"          # verde
COR_PROBLEMA = "FFC7CE"         # rosa: a nota não vai em e-mail nenhum
COR_IGNORADO = "D9D9D9"         # cinza
