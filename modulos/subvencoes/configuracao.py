"""Textos e padrões que o programa procura nos arquivos.

Se o sistema mudar o título de uma coluna ou o texto de um relatório,
basta alterar a linha correspondente aqui. As comparações são feitas
depois de normalizar o texto (sem acentos, minúsculas, espaços únicos),
então não importa se o título vem com ou sem acento, em maiúsculas etc.
"""

# ---------------------------------------------------------------------------
# Balancete
# ---------------------------------------------------------------------------

# Título da coluna com o saldo que vai para "Saldo Contábil".
BALANCETE_TITULO_SALDO_ATUAL = "Saldo Atual"

# Rótulo da data de referência (o valor fica numa célula à direita).
BALANCETE_TITULO_MES_REFERENCIA = "Mês Referência"

# Classificação contábil: 2.02.06 / 2.02.06.01 / 2.02.06.01.0020
BALANCETE_PADRAO_CLASSIFICACAO = r"^\d+(\.\d{2})+(\.\d{4})?$"

# Quantidade de dígitos do último segmento de uma conta analítica.
BALANCETE_DIGITOS_ANALITICA = 4

# Contas analíticas que não fazem parte das planilhas (R7): Doações.
PREFIXOS_CLASSIFICACAO_IGNORADOS = ("2.02.06.08",)

# ---------------------------------------------------------------------------
# Rodapés (balancete e patrimônio) — linhas ignoradas
# ---------------------------------------------------------------------------

RODAPE_IMPRESSO_EM = "Impresso em"
RODAPE_PAGINA = "Página"

# ---------------------------------------------------------------------------
# Patrimônio - Bens Subvenção
# ---------------------------------------------------------------------------

PATRIMONIO_TITULO_RELATORIO = "Patrimônio - Bens Subvenção"
PATRIMONIO_ROTULO_DATA = "Data:"
PATRIMONIO_TITULO_CONTA = "Conta Subvenção"
PATRIMONIO_TITULO_COD_BEM = "Cód Bem"
PATRIMONIO_TITULO_DESCRICAO = "Descrição"
PATRIMONIO_TITULO_VALOR_CONTABIL = "Valor Contábil"
PATRIMONIO_TITULO_DEPRECIACAO = "Deprec Mês"
PATRIMONIO_PREFIXO_TOTAL_CONTA = "Total - "
PATRIMONIO_PREFIXO_TOTAL_GERAL = "Total("

# ---------------------------------------------------------------------------
# Planilhas a preencher (Subvenções_Investimento e Projetos)
# ---------------------------------------------------------------------------

PLANILHA_TITULO_CONTA_CONTABIL = "Conta Contábil"
PLANILHA_TITULO_CONVENIO = "Convênio"
PLANILHA_TITULO_SALDO_PATRIMONIO = "Saldo Patrimônio"
PLANILHA_TITULO_SALDO_CONTABIL = "Saldo Contábil"

# ---------------------------------------------------------------------------
# Arquivos gerados
# ---------------------------------------------------------------------------

# Padrão MM-AAAA no nome dos arquivos (ex.: Projetos_08-2026.xlsx).
PADRAO_MES_ANO_NOME_ARQUIVO = r"(0[1-9]|1[0-2])-(\d{4})"

# Nome do relatório de avisos; {mes_ano} vira MM-AAAA.
NOME_RELATORIO_AVISOS = "Avisos_{mes_ano}.xlsx"

# Extensões aceitas.
EXTENSOES_ACEITAS = (".xlsx", ".xlsm")
