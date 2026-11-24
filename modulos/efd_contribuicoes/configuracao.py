"""Constantes do módulo EFD Contribuições (ESPECIFICACAO_EFD_CONTRIBUICOES.md)."""

from __future__ import annotations

# --- SPED (seção 2.1) ---
CODIFICACAO_SPED = "ISO-8859-1"
QUEBRA_LINHA_SPED = "\r\n"
CST = "07"                       # R13: fixo no regime da Fundação
CODIGO_RECEITA_M410_M810 = "202"
CODIGO_PAIS_BRASIL = "1058"      # 0150

# --- DANFSe (R1): posições horizontais das colunas na página (layout nacional v2.0, copiadas da origem) ---
LIMITE_X_COLUNA1 = 250           # 1ª coluna (nome / documento)
LIMITE_X_COLUNA3 = 400           # 3ª coluna (Código IBGE / CEP)
TOLERANCIA_LINHA = 2.0           # palavras com "top" a até 2 pontos ficam na mesma linha

# --- Cadastro de clientes (seção 4.4): o arquivo é escolhido na tela (ajuste de 05/11/2026) ---
NOME_CADASTRO = "clientes.json"          # nome sugerido ao criar um cadastro novo
PASTA_COPIAS = "copias"

# --- Situação de cada PDF (seção 4.2) ---
SITUACAO_NO_SPED = "No SPED"
SITUACAO_PF = "Fora: PF"
SITUACAO_COMPETENCIA = "Fora: competência ≠ emissão"
SITUACAO_EMISSAO = "Fora: emissão fora do mês"
SITUACAO_REPETIDA = "Fora: repetida"
SITUACAO_NAO_LIDO = "Fora: não lido"
SITUACAO_CONFLITO = "Número repetido com tomador ou valor diferente"   # R5: bloqueia
SITUACAO_INCLUIDA = "No SPED (incluída à mão)"     # ajuste de 05/11/2026: nota fora pela data, incluída na tela
SITUACOES_INCLUIVEIS = (SITUACAO_COMPETENCIA, SITUACAO_EMISSAO)   # só as que ficaram fora por causa das datas

# --- Excel de conferência (seção 5) ---
COR_FUNDO_TITULO = "1F4E78"
COR_FONTE_TITULO = "FFFFFF"
COR_OK = "C6EFCE"              # verde: no SPED
COR_PROBLEMA = "FFC7CE"        # rosa: não lido, conflito
COR_ATENCAO = "FFEB9C"         # amarelo: fora do SPED (PF, data, repetida)
