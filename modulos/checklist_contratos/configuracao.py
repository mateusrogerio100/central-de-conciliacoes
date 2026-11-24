"""Valores fixos do módulo Notas de Contrato (checklist mensal).

Se o Tasy mudar um título de coluna, ou a Fundação mudar algum destes dados, basta alterar a
linha aqui. Seções citadas: ESPECIFICACAO_CHECKLIST_CONTRATOS.md.
"""

import re
from decimal import Decimal

# ---------------------------------------------------------------------------
# Estabelecimentos e abas do Check list — seção 3.2
# ---------------------------------------------------------------------------

SC = "SC"
CMD = "CMD"
ESTABELECIMENTOS = (SC, CMD)
ABAS = {SC: "HOSPITAL EXEMPLO", CMD: "CENTRO MULTIDISCIPLINAR"}
NOMES_ESTABELECIMENTOS = {SC: "Hospital Exemplo", CMD: "CMD - Centro Multidisciplinar"}
ABA_EMAILS = "Emails"

# ---------------------------------------------------------------------------
# Movimento do Tasy (.csv) — seção 3.1 e regra M1
# ---------------------------------------------------------------------------

# O Tasy exporta em UTF-16 (sem marca no início); as outras codificações ficam de reserva.
MOV_CODIFICACOES_RESERVA = ("utf-8-sig", "latin-1")
MOV_SEPARADOR = ";"

# Títulos das colunas (achadas pelo título, nunca pela letra).
MOV_COLUNA_DEBITO_CREDITO = "Débito/Crédito"
MOV_COLUNA_CONTA = "Conta contábil"           # código reduzido
MOV_COLUNA_NOME_CONTA = "Conta"
MOV_COLUNA_VALOR = "Valor"
MOV_COLUNA_COMPLEMENTO = "Complemento"
MOV_COLUNA_LOTE = "Lote contábil"
MOV_COLUNA_LANCAMENTO = "Lançamento"
MOV_COLUNA_DATA = "Data movimento"
MOV_COLUNA_ESTABELECIMENTO = "Estabelecimento"
MOV_COLUNAS_OBRIGATORIAS = (
    MOV_COLUNA_DEBITO_CREDITO, MOV_COLUNA_CONTA, MOV_COLUNA_NOME_CONTA, MOV_COLUNA_VALOR,
    MOV_COLUNA_COMPLEMENTO, MOV_COLUNA_LOTE, MOV_COLUNA_LANCAMENTO, MOV_COLUNA_DATA,
    MOV_COLUNA_ESTABELECIMENTO,
)
MOV_DEBITO = "D"                              # só as linhas de débito entram na conferência
MOV_CREDITO = "C"                             # os créditos servem para reconhecer estornos (M4)

# Exportação "Movimento contábil" (baixada um dia por vez, com o centro de custo): reconhecida pelos
# títulos. Aqui "Conta contábil" é o NOME da conta; o código vem em Conta débito / Conta crédito.
MOVC_COLUNA_FATO = "Fato contábil"
MOVC_COLUNA_LANCAMENTO = "Lançamento"
MOVC_COLUNA_DATA = "Data"
MOVC_COLUNA_VALOR = "Valor"
MOVC_COLUNA_DEBITO = "Conta débito"
MOVC_COLUNA_CREDITO = "Conta crédito"
MOVC_COLUNA_COMPLEMENTO = "Complemento"
MOVC_COLUNA_NOME_CONTA = "Conta contábil"
MOVC_COLUNA_CENTRO_CUSTO = "Centro de custo"   # opcional
MOVC_COLUNAS_IDENTIFICACAO = (MOVC_COLUNA_FATO, MOVC_COLUNA_DEBITO, MOVC_COLUNA_CREDITO)
MOVC_COLUNAS_OBRIGATORIAS = (
    MOVC_COLUNA_FATO, MOVC_COLUNA_LANCAMENTO, MOVC_COLUNA_DATA, MOVC_COLUNA_VALOR, MOVC_COLUNA_DEBITO,
    MOVC_COLUNA_CREDITO, MOVC_COLUNA_COMPLEMENTO, MOVC_COLUNA_NOME_CONTA,
)
MOVC_CONTA_VAZIA = "0"                         # código no lado que não é usado

# ---------------------------------------------------------------------------
# Estornos e devoluções — regra M4 (decisão do usuário, 23/10/2026)
# ---------------------------------------------------------------------------

# Complemento normalizado (M2) de uma devolução: "manutencao exemplo ltda nf. 299689 - devolucao nf 2591 devido ..."
RE_DEVOLUCAO = re.compile(r"\bdevolu")
RE_NF_DEVOLVIDA = re.compile(r"\bdevolu\w*\s+(?:da\s+|de\s+)?(?:nf|nota fiscal)\b\.?\s*(?:n[o.º°]*\s*)?(\d+)")
# Fornecedor e número da nota no começo do complemento: "manutencao exemplo ltda nf. 2591 - ..."
RE_FORNECEDOR_E_NF = re.compile(r"^(.*?)\s+nf\b\.?\s*(\d+)")

# Valor em formato brasileiro sem casas fixas ("21585,5", "3420"); ponto de milhar aceito.
RE_VALOR = re.compile(r"-?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{1,2})?")

# ---------------------------------------------------------------------------
# Check list (.xlsx) — seção 3.2 e regra K1
# ---------------------------------------------------------------------------

# Títulos já normalizados (M2). A conta aparece como "Conta Contábil" na Hospital Exemplo e "Conta" no CMD.
CHK_TITULOS_CONTA = ("conta contabil", "conta")
CHK_TITULO_DESCRICAO_CONTA = "descricao conta"
CHK_TITULO_FORNECEDOR = "fornecedor"
CHK_TITULO_DESCRICAO_DESPESA = "descricao da despesa"      # começa com (o protótipo aceitava sufixo)
CHK_TITULO_RESPONSAVEL = "responsavel"

RE_MES_DIGITADO = re.compile(r"^\s*(\d{1,2})\s*/\s*(\d{4})\s*$")   # "10/2026", na tela
MESES_ABREVIADOS = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")
MESES_POR_EXTENSO = ("Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto",
                     "Setembro", "Outubro", "Novembro", "Dezembro")

# Aba Emails: "Nome <email>", "<email>" ou só o e-mail (pode vir com vírgula ou espaço sobrando).
RE_CONTATO = re.compile(r"^\s*(.*?)\s*<\s*([^<>\s]+@[^<>\s]+?)\s*>\s*[,;]?\s*$")
RE_EMAIL_SOZINHO = re.compile(r"^\s*([^<>\s,;]+@[^<>\s,;]+)\s*[,;]?\s*$")
RE_APELIDO = re.compile(r"\((.+?)\)")

# Códigos dos responsáveis (decisão do usuário, 23/10/2026): a coluna Responsável começa com o número
# ("13 - Carlos manutenção") e a célula ao lado do contato, na aba Emails, diz de quais números ele
# recebe os e-mails ("11; 12; 13"), ou "Todos" (todo e-mail) / "Todos CMD" (todo e-mail com notas do CMD).
RE_CODIGO_RESPONSAVEL = re.compile(r"^\s*(\d+)\s*[-–—.]\s*(.*)$")
RE_SEPARADOR_CODIGOS = re.compile(r"\s*[;,/]\s*")
CODIGO_TODOS = "todos"
CODIGO_TODOS_CMD = "todos cmd"
# "Cópia": vai em cópia (Cc) de todos os e-mails, a não ser que já esteja no Para (28/10/2026)
CODIGO_COPIA = "copia"
# "Cópia CMD": em cópia (Cc) só dos e-mails que têm notas do CMD
CODIGO_COPIA_CMD = "copia cmd"

# ---------------------------------------------------------------------------
# Arquivos de configuração (.csv com ;) — seção 3.3
# ---------------------------------------------------------------------------

CONFIG_SEPARADOR = ";"
CONFIG_CODIFICACOES = ("utf-8-sig", "latin-1")

ARQUIVO_REGRAS = "regras.csv"
# A pasta de configuração fica ao lado do Check list (decisão do usuário, 23/10/2026): ao escolher o Check
# list, a tela procura o regras.csv nestas pastas (relativas à do Check list) e preenche sozinha.
PASTAS_CONFIGURACAO_SUGERIDAS = ("config", ".")
# Aposentados em 23/10/2026 (os destinatários vêm dos códigos da aba Emails): se ainda estiverem na
# pasta, o módulo avisa que não são mais usados.
ARQUIVOS_APOSENTADOS = ("destinatarios_extras.csv", "redirecionamentos.csv")

REGRAS_COLUNAS = ("Aba", "Linha", "Fornecedor_Planilha", "Descricao_Planilha", "Contas",
                  "Busca_Fornecedor", "Busca_Descricao", "Excluir", "Selecao", "Tipo", "Obs")
# Opcional (ponto 13, 28/10/2026): expressão sobre o nome do centro de custo, só nas linhas que precisam
# (ex.: os dois contratos de locação de veículos). Arquivo sem a coluna continua valendo.
REGRAS_COLUNAS_OPCIONAIS = ("Centro_Custo",)

TIPO_AUTO = "auto"
TIPO_MANUAL = "manual"
TIPO_IGNORAR = "ignorar"
TIPOS = (TIPO_AUTO, TIPO_MANUAL, TIPO_IGNORAR)
SELECOES = ("", "maior", "menor")          # vazio = soma tudo (R3)
RE_SEPARADOR_CONTAS = re.compile(r"[/;, ]+")

# ---------------------------------------------------------------------------
# Conferência — regras R8 e R9
# ---------------------------------------------------------------------------

LIMITE_VARIACAO_PERCENTUAL = Decimal("10")    # R8: variação de 10% ou mais fica destacada
CONTA_RECLASSIFICAR = "23334"                 # R9: Fornecedores a reclassificar
CONTAS_ESTOQUE = ("30027", "10131", "10132", "10133", "10134", "10137", "10144", "10146", "10305",
                  "11677", "11895", "11899", "12699", "14320", "14321")     # R9: fora dos não vinculados

# ---------------------------------------------------------------------------
# Pendências — regra P2
# ---------------------------------------------------------------------------

# Mês anterior com um destes trechos (texto normalizado) = contrato encerrado: fora das pendências.
TEXTOS_ENCERRADO = ("finaliz", "rescin", "reinscin", "encerr", "rescis", "nao assinou")
SEM_RESPONSAVEL = "Sem responsável"           # P3

# P2: a linha CONTA DIVERGENTE vem do relatório da conferência (aba e títulos achados pelo texto
# normalizado; vale também o relatório do protótipo, aba "Conferencia").
REL_ABA_CONFERENCIA = "conferencia"
REL_TITULO_ABA = "aba"
REL_TITULO_LINHA = "linha"
REL_TITULOS_SITUACAO = ("situacao", "status")      # "Status" no relatório do protótipo
RE_MES_DO_RELATORIO = re.compile(r"_(\d{4})-(\d{2})(?:_|\.|\s|$)")

# ---------------------------------------------------------------------------
# E-mails — regras E1 a E7 (texto igual ao do protótipo, gerar_emails.ps1)
# ---------------------------------------------------------------------------

NOMES_CURTOS = {SC: "Hospital Exemplo", CMD: "CMD"}          # assunto e nome do arquivo
ASSUNTO_EMAIL = "Notas fiscais pendentes - {estabelecimentos} - {mes}"
ESTILO_TABELA_EMAIL = "border-collapse:collapse;font-family:Calibri,Arial,sans-serif;font-size:13px"
COR_TITULOS_TABELA_EMAIL = "#D9E3EF"
COLUNAS_TABELA_EMAIL = ("Conta", "Fornecedor", "Descrição da despesa")
# Prévia: notas fora dos e-mails por CONTA DIVERGENTE (P2)
COLUNAS_TABELA_CONTA_DIVERGENTE = ("Aba", "Linha", "Conta esperada", "Fornecedor", "Descrição da despesa",
                                   "Responsável")

# ---------------------------------------------------------------------------
# Gmail — regras G2 e G3
# ---------------------------------------------------------------------------

REMETENTE_PADRAO = "contabilidade@hospitalexemplo.com.br"
GMAIL_ESCOPOS = ("https://www.googleapis.com/auth/gmail.compose",)
GMAIL_URL_PERFIL = "https://gmail.googleapis.com/gmail/v1/users/me/profile"
GMAIL_URL_RASCUNHOS = "https://gmail.googleapis.com/gmail/v1/users/me/drafts"
GMAIL_TEMPO_LIMITE = 60                        # segundos por chamada
# Token da autorização (3.4): %APPDATA%\CentralConciliacoes\checklist_contratos\gmail_token.json.
# Nunca vai para o git nem para dentro do .exe (como o credentials.json, escolhido na tela).
PASTA_DADOS_USUARIO = "CentralConciliacoes"
SUBPASTA_DADOS_MODULO = "checklist_contratos"
NOME_TOKEN_GMAIL = "gmail_token.json"
TIPO_REGISTRO_RASCUNHO = "rascunho"            # G5 (o envio direto entra depois, G1)
REGISTRO_GMAIL_COLUNAS = ("Data e hora", "Tipo", "Responsável", "Para", "Assunto", "Notas", "Id no Gmail", "Erro")

# ---------------------------------------------------------------------------
# Saídas — seção 5
# ---------------------------------------------------------------------------

NOME_RELATORIO = "Conferencia_Contratos_{ano:04d}-{mes:02d}_{data_hora}.xlsx"
NOME_COPIA_CHECKLIST = "Check list {ano:04d} - {mes:02d} preenchido.xlsx"
NOME_PREVIA_EMAILS = "Previa_emails_{ano:04d}-{mes:02d}_{data_hora}.html"    # E7
NOME_TEXTO_CLAUDE_DESKTOP = "Emails_para_Claude_Desktop_{ano:04d}-{mes:02d}_{data_hora}.txt"   # E8
NOME_REGISTRO_GMAIL = "Envio_Gmail_{data_hora}.csv"                           # G5
FORMATO_DATA_HORA_NOME = "%Y-%m-%d_%H%M%S"

ABA_RESUMO = "Resumo"
ABA_CONFERENCIA = "Conferência"
ABA_DIVERGENTE = "Conta divergente"
ABA_MANUAIS = "Manuais"
ABA_NAO_VINCULADOS = "Não vinculados"
ABA_ESTORNOS = "Estornos e devoluções"
ABA_AVISOS = "Avisos"

# verde OK, laranja divergente, rosa não encontrado, amarelo manual (seção 5); cinza ignorado
CORES_SITUACAO = {
    "OK": "C6EFCE",
    "CONTA DIVERGENTE": "F8CBAD",
    "NÃO ENCONTRADO": "FFC7CE",
    "MANUAL": "FFEB9C",
    "IGNORADO": "D9D9D9",
}
COR_DESTAQUE = "F4B084"            # R7 (valor diferente na célula preenchida) e R8 (variação >= 10%)
COR_FUNDO_TITULO = "1F4E78"
COR_FONTE_TITULO = "FFFFFF"
FORMATO_VALOR_EXCEL = "#,##0.00"
FORMATO_PERCENTUAL_EXCEL = "0.00"

# R7a (pedido do usuário, 06/11/2026): célula do mês com "Provisão" (ou "provisionar"...) e valor achado no
# movimento: a nota achada se refere ao mês anterior, que foi provisionado. Só aviso (a célula não muda).
TEXTO_PROVISAO = "provis"
AVISO_PROVISAO = "Valor se refere ao mês anterior, pois ele foi provisionado"
