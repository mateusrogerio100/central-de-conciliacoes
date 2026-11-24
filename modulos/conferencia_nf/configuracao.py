"""Valores fixos do módulo Conferência de Notas Fiscais.

Se o Tasy mudar um título de coluna, ou a Fundação mudar algum destes dados, basta alterar a
linha aqui. Seções citadas: ESPECIFICACAO_CONFERENCIA_NF.md.
"""

import re
from decimal import Decimal

# ---------------------------------------------------------------------------
# Lote do Tasy (.csv) — seção 3.1
# ---------------------------------------------------------------------------

# O Tasy exporta em UTF-16; as outras codificações ficam de reserva, nesta ordem.
LOTE_CODIFICACOES_RESERVA = ("utf-8-sig", "latin-1")
LOTE_SEPARADOR = ";"

# Títulos das colunas (as colunas são achadas pelo título, nunca pela letra).
LOTE_COLUNA_FATO = "Fato contábil"
LOTE_COLUNA_SEQUENCIA = "Sequência"
LOTE_COLUNA_DATA_MOVIMENTO = "Data movimento"
LOTE_COLUNA_DEBITO = "Débito"
LOTE_COLUNA_CREDITO = "Crédito"
LOTE_COLUNA_VALOR = "Valor"
LOTE_COLUNA_COMPLEMENTO = "Complemento"
LOTE_COLUNA_CONTA_DEBITO = "Conta débito"
LOTE_COLUNA_CONTA_CREDITO = "Conta crédito"
LOTE_COLUNA_CLASSIFICACAO_DEBITO = "Classificação débito"
LOTE_COLUNA_CLASSIFICACAO_CREDITO = "Classificação crédito"

LOTE_COLUNAS_OBRIGATORIAS = (
    LOTE_COLUNA_FATO, LOTE_COLUNA_SEQUENCIA, LOTE_COLUNA_DEBITO, LOTE_COLUNA_CREDITO,
    LOTE_COLUNA_VALOR, LOTE_COLUNA_COMPLEMENTO, LOTE_COLUNA_CONTA_DEBITO,
    LOTE_COLUNA_CONTA_CREDITO,
)
# Só aparecem no relatório; se faltarem, a coluna fica em branco.
# Exportação "Movimento contábil" do Tasy (16/10/2026): os mesmos lançamentos, uma conta por linha
# ("Conta débito"/"Conta crédito" com o código, "0" no lado vazio), mais o centro de custo.
# Reconhecida pelos títulos; os títulos iguais aos do lote ("Conta débito") mudam de sentido.
MOV_COLUNA_FATO = "Fato contábil"
MOV_COLUNA_SEQUENCIA = "Sequência"
MOV_COLUNA_DATA = "Data"
MOV_COLUNA_VALOR = "Valor"
MOV_COLUNA_DEBITO = "Conta débito"           # código reduzido
MOV_COLUNA_CREDITO = "Conta crédito"         # código reduzido
MOV_COLUNA_COMPLEMENTO = "Complemento"
MOV_COLUNA_NOME_CONTA = "Conta contábil"
MOV_COLUNA_CLASSIFICACAO = "Classificação da conta"
MOV_COLUNA_CENTRO_CUSTO = "Centro custo"     # código
MOV_COLUNA_NOME_CENTRO_CUSTO = "Centro de custo"
MOV_COLUNAS_OBRIGATORIAS = (
    MOV_COLUNA_FATO, MOV_COLUNA_SEQUENCIA, MOV_COLUNA_VALOR, MOV_COLUNA_DEBITO, MOV_COLUNA_CREDITO,
    MOV_COLUNA_COMPLEMENTO, MOV_COLUNA_NOME_CONTA, MOV_COLUNA_CLASSIFICACAO, MOV_COLUNA_CENTRO_CUSTO,
)
MOV_COLUNAS_IDENTIFICACAO = (MOV_COLUNA_CLASSIFICACAO, MOV_COLUNA_CENTRO_CUSTO)
MOV_CONTA_VAZIA = "0"                        # código no lado que não é usado; centro de custo vazio

# S11 (pedido do usuário e da chefia, 16/10/2026): conta de resultado (classificação começando por
# 3 ou 4) obrigatoriamente com centro de custo.
CLASSES_COM_CENTRO_CUSTO = ("3", "4")
MOTIVO_SEM_CENTRO_CUSTO = "Conta de resultado sem centro de custo"
# S18 (pedido do usuário, 28/10/2026): despesa do CMD não vai no centro de custo 539 - CMD, vai na conta do
# ativo. O lançamento com esse centro de custo ganha um aviso (o fato OK vira CONFERIR).
CENTROS_CUSTO_TROCAR_PELO_ATIVO = ("539",)
MOTIVO_CENTRO_CUSTO_CMD = "Centro de custo 539 - CMD: trocar pela conta do ativo"
# S19 (pedido do usuário, 28/10/2026): conta de despesa ou receita (3 ou 4) com uma destas palavras no nome
# (sem acento, minúsculo) e valor maior que o limite no fato: aviso (o fato OK vira CONFERIR).
PALAVRAS_DILUICAO = ("software", "uniforme", "enxoval")
LIMITE_DILUICAO = Decimal("1000.00")
MOTIVO_DILUICAO = "Verificar se é possível a diluição do custo ou despesa"
# S20 (pedido do usuário, 06/11/2026): lançamento na conta "Fornecedores a reclassificar" (pelo nome, sem
# acento, minúsculo) ganha um aviso conforme o lado; o fato OK vira CONFERIR.
NOME_FORNECEDORES_RECLASSIFICAR = "fornecedores a reclassificar"
MOTIVO_RECLASSIFICAR_CREDITO = ("Fornecedores a reclassificar no crédito: conferir se precisa trocar para a "
                                "conta do próprio fornecedor")
MOTIVO_RECLASSIFICAR_DEBITO = "Fornecedores a reclassificar no débito: conferir se foi provisionada"
# S19 e S20 na aba Lançamentos (pedido do usuário, 18/11/2026): a célula "Nome da conta" do lançamento do
# aviso ganha este texto depois do nome, em negrito, com o fundo COR_DESTAQUE_AVISO.
MARCA_DILUICAO = "VERIFICAR A DILUIÇÃO"
MARCA_RECLASSIFICAR_CREDITO = "TROCAR PELA CONTA DO FORNECEDOR?"
MARCA_RECLASSIFICAR_DEBITO = "FOI PROVISIONADA?"
COR_DESTAQUE_AVISO = "FFD966"          # amarelo forte: aparece em cima do amarelo claro do CONFERIR

LOTE_COLUNAS_OPCIONAIS = (
    LOTE_COLUNA_DATA_MOVIMENTO, LOTE_COLUNA_CLASSIFICACAO_DEBITO, LOTE_COLUNA_CLASSIFICACAO_CREDITO,
)

# Valor do lote: formato brasileiro sem casas fixas ("4887,2", "3420", "887,93"); o ponto de
# milhar, se vier, é aceito ("1.234,56").
RE_VALOR_LOTE = re.compile(r"-?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{1,2})?")

# ---------------------------------------------------------------------------
# Tipo do PDF — regra L2
# ---------------------------------------------------------------------------

PDF_TEXTO_DANFSE = "DANFSe"
PDF_TEXTOS_DANFE = ("DANFE", "CHAVE DE ACESSO")
TIPO_NFE = "NF-e"          # nota de compra (DANFE)
TIPO_NFSE = "NFS-e"        # nota de serviço (DANFSe)

# ---------------------------------------------------------------------------
# DANFE (nota de compra) — seção 3.2, regras L3 e L4
# ---------------------------------------------------------------------------

# Cada campo fica na linha logo abaixo do seu rótulo (texto da 1ª página).
RE_DANFE_NUMERO = re.compile(r"^Nº\s*([\d.]+)", re.MULTILINE)
RE_DANFE_EMITENTE = re.compile(r"RECEBEMOS DE (.+?) OS PRODUTOS", re.DOTALL)
DANFE_ROTULO_CNPJ_INICIO = "INSCRIÇÃO ESTADUAL"     # linha que começa com isto...
DANFE_ROTULO_CNPJ_FIM = "CNPJ / CPF"                # ...e termina com isto
DANFE_ROTULO_EMISSAO = "DATA DA EMISSÃO"            # linha que termina com isto
DANFE_ROTULO_VALOR_TOTAL = "VALOR TOTAL DA NOTA"    # linha que termina com isto
# L3: a chave vem em 11 grupos de 4 dígitos; um número de nota de 4 dígitos na frente dela vira
# um 12º grupo ("Nº 1090 2926 0950 ..."), por isso valem sempre os 44 últimos dígitos.
RE_DANFE_CHAVE = re.compile(r"(?<!\d)((?:\d{4} ){10,}\d{4})(?!\d)")
TAMANHO_CHAVE = 44
# Posições (começando em 0) do CNPJ do emitente e do número da nota dentro da chave de acesso.
CHAVE_POSICAO_CNPJ = slice(6, 20)
CHAVE_POSICAO_NUMERO = slice(25, 34)

RE_DATA = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
RE_DOCUMENTO = re.compile(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{3}\.\d{3}\.\d{3}-\d{2}")
# Valor no PDF: "7.900,00", "650,75" (sempre 2 casas).
RE_VALOR_PDF = re.compile(r"^(\d{1,3}(?:\.\d{3})*|\d+),(\d{2})$")

# ---------------------------------------------------------------------------
# DANFSe v2.0 (nota de serviço) — seção 3.3 (mesmas posições do módulo Serviços Tomados)
# ---------------------------------------------------------------------------

DANFSE_IDENTIFICACAO = "DANFSe v2.0"

# Posição horizontal (x) onde começa cada uma das 4 colunas da DANFSe. Cada dado fica na
# coluna do seu rótulo, na primeira linha abaixo dele.
DANFSE_COLUNAS_X = (11, 156, 300, 445)
DANFSE_TOLERANCIA_X = 3            # folga para a posição das palavras
DANFSE_TOLERANCIA_LINHA = 2.0      # palavras com "top" até esta distância estão na mesma linha
# Letras maiores que isto são a marca d'água "CANCELADA" / "SUBSTITUÍDA" e são ignoradas.
DANFSE_TAMANHO_MAXIMO_TEXTO = 20
DANFSE_DISTANCIA_MAXIMA_VALOR = 14  # o valor fica até esta distância abaixo do rótulo

# Blocos da nota (os rótulos "CNPJ / CPF / NIF" e "Nome / Nome Empresarial" se repetem).
DANFSE_BLOCO_PRESTADOR = "PRESTADOR / FORNECEDOR"
DANFSE_BLOCO_VALORES = "VALOR TOTAL DA NFS-E"
DANFSE_BLOCO_TOMADOR = "TOMADOR / ADQUIRENTE"     # S15: o CNPJ da unidade da Fundação

# Só estes campos são lidos; os demais (regime, atividade, tributação...) não importam aqui.
DANFSE_ROTULO_CHAVE = "CHAVE DE ACESSO DA NFS-E"
DANFSE_ROTULO_NUMERO = "NÚMERO DA NFS-E"
DANFSE_ROTULO_EMISSAO = "DATA E HORA DA EMISSÃO DA NFS-E"
DANFSE_ROTULO_SITUACAO = "SITUAÇÃO DA NFS-E"
DANFSE_ROTULO_DOCUMENTO = "CNPJ / CPF / NIF"
DANFSE_ROTULO_NOME = "Nome / Nome Empresarial"
DANFSE_ROTULO_VALOR_SERVICO = "VALOR DA OPERAÇÃO / SERVIÇO"

# S10: campos só para o relatório (nunca causam erro de leitura), como no Serviços Tomados.
DANFSE_ROTULO_REGIME = "Simples Nacional na Data de Competência"
DANFSE_ROTULO_ATIVIDADE = "Código de Tributação Nacional / Municipal"
DANFSE_ROTULO_DESCRICAO_SERVICO = "Descrição do Serviço"   # fim do texto da atividade
DANFSE_ROTULO_ALIQUOTA = "Alíquota Aplicada"
DANFSE_ROTULO_RETENCAO_ISS = "Retenção do ISSQN"
DANFSE_ROTULO_ISS = "ISSQN Apurado"
DANFSE_BLOCO_FEDERAL = "TRIBUTAÇÃO FEDERAL"
DANFSE_ROTULO_IRRF = "IRRF"
DANFSE_ROTULO_PREVIDENCIA = "Contribuição Previdenciária - Retida"
DANFSE_ROTULO_CONTRIBUICOES = "Contribuições Sociais - Retidas"
DANFSE_ROTULO_DESCRICAO_CONTRIBUICOES = "Descrição Contrib. Sociais - Retidas"
REGIME_TEXTO_NAO_OPTANTE = "NAO OPTANTE"     # comparação sem acento, maiúsculas

# Campo sem valor na DANFSe.
DANFSE_VAZIO = "-"

# ---------------------------------------------------------------------------
# XML das notas — seção 3.5 e regras X1 a X5 (pedido do usuário, 19/10/2026)
# ---------------------------------------------------------------------------

# Os campos são achados pelo nome da etiqueta, sem o "namespace" (o endereço do padrão).
# NF-e (nota de compra): raiz "nfeProc" (nota + protocolo de autorização da Sefaz).
XML_NFE_RAIZES = ("nfeProc",)
XML_NFE_INFO = "infNFe"              # o atributo Id = "NFe" + chave de acesso
XML_NFE_PROTOCOLO = "protNFe"
XML_NFE_AUTORIZADA = ("100", "150")  # cStat do protocolo: autorizado o uso (150: fora de prazo)
# NFS-e (nota de serviço, padrão nacional = DANFSe v2.0): raiz "NFSe".
XML_NFSE_RAIZES = ("NFSe",)
XML_NFSE_INFO = "infNFSe"            # o atributo Id = "NFS" + chave de acesso
XML_NFSE_DPS = "infDPS"
# "Simples Nacional na Data de Competência" (opSimpNac), escrito como na DANFSe.
XML_NFSE_REGIMES = {
    "1": "Não Optante",
    "2": "Optante - Microempreendedor Individual (MEI)",
    "3": "Optante - Microempresa ou Empresa de Pequeno Porte (ME/EPP)",
}
# "Retenção do ISSQN" (tpRetISSQN): 1 = não retido; 2 = retido pelo tomador; 3 = pelo intermediário.
XML_NFSE_RETENCAO_ISS = {"1": "Não Retido", "2": "Retido", "3": "Retido"}

# ---------------------------------------------------------------------------
# Nota Fiscal Paulistana (NFS-e da Prefeitura de São Paulo) — L2a e X1a (pedido do usuário, 18/11/2026)
# ---------------------------------------------------------------------------
PDF_TEXTOS_PAULISTANA = ("PREFEITURA DO MUNICÍPIO DE SÃO PAULO", "NOTA FISCAL ELETRÔNICA DE SERVIÇOS")
PAULISTANA_BLOCO_PRESTADOR = "PRESTADOR DE SERVIÇOS"
PAULISTANA_BLOCO_TOMADOR = "TOMADOR DE SERVIÇOS"
PAULISTANA_BLOCO_INTERMEDIARIO = "INTERMEDIÁRIO DE SERVIÇOS"
# linhas de títulos; os valores vêm na linha de baixo
PAULISTANA_TITULO_FEDERAIS = "Contribuição Previdenciária - Retida (R$) IRRF (R$)"
PAULISTANA_TITULO_CONTRIBUICOES = "Contribuições Sociais - Retidas (R$)"
PAULISTANA_TITULO_ISS = "Valor Total das Deduções (R$)"
# em "OUTRAS INFORMAÇÕES" (minúsculas): ISS retido pelo tomador x ISS com vencimento (o prestador paga)
PAULISTANA_TEXTO_ISS_RETIDO = "retido pelo tomador"
PAULISTANA_TEXTO_ISS_NAO_RETIDO = "vencimento do iss"
# Identificador Nacional (50 dígitos): CNPJ/CPF do prestador e número da nota (posições começando em 0)
PAULISTANA_TAMANHO_CHAVE = 50
PAULISTANA_CHAVE_POSICAO_DOCUMENTO = slice(9, 23)
PAULISTANA_CHAVE_POSICAO_NUMERO = slice(23, 36)
PAULISTANA_PREFIXO_CHAVE = "SP"      # nota sem Identificador Nacional: "SP" + CNPJ (14) + número (13)
XML_PAULISTANA_CHAVE = "ChaveNFe"
XML_PAULISTANA_SITUACOES = {"C": "Cancelada", "E": "Extraviada"}     # StatusNFe; N (normal) = em branco
XML_PAULISTANA_REGIMES = {"0": "Não Optante"}    # OpcaoSimples; os outros códigos ficam em branco

# ---------------------------------------------------------------------------
# Complemento do lançamento — regras F1 a F3
# ---------------------------------------------------------------------------

# F1: "NF. 35681", "NF 35681", "NF. nº 35681"
RE_NUMERO_NF = re.compile(r"\bNF\.?\s*(?:n[º°o]\.?\s*)?(\d+)", re.IGNORECASE)
# F2: "DT25/09/2026" ou "DT 25/09/2026"
RE_DATA_DT = re.compile(r"\bDT\s*(\d{2})/(\d{2})/(\d{4})")
# F3: sem "NF.", o fornecedor é o texto antes da palavra Recibo ou de um número de 3+ dígitos
RE_RECIBO = re.compile(r"\bRecibo\b", re.IGNORECASE)
RE_INICIO_DOCUMENTO = re.compile(r"\bRecibo\b|\b\d{3,}\b", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Conferência — regras C2 e S3a
# ---------------------------------------------------------------------------

# C2: abaixo disto o nome do emitente do PDF é considerado de outro fornecedor.
SEMELHANCA_MINIMA_NOME = 0.60
# S17 (pedido do usuário, 21/10/2026): se casar menos que esta fração dos PDFs lidos, a pasta dos PDFs
# provavelmente é de outro dia (13/10 conferido com os PDFs de 05/10: 0 de 78). Num dia certo, quase
# todos casam (13/10: 52 de 53); 25% e não 50% porque a pasta do lote 72648 tinha PDFs de outros dias
# junto e só 76 de 178 (43%) casaram. Só aviso, em vermelho: a conferência e a planilha saem normalmente.
MINIMO_PDFS_CASADOS = 0.25
AVISO_PASTA_DE_OUTRO_DIA = ("A pasta dos PDFs parece ser de outro dia: só {casados} de {lidos} PDFs "
                            "casaram com o lote. Confira a pasta escolhida.")
# C2: palavras que não contam na comparação de nomes ("S" e "A" vêm de "S/A", sem a barra).
PALAVRAS_IGNORADAS_NOME = frozenset({
    "LTDA", "ME", "EPP", "EIRELI", "SA", "S", "A", "CIA", "MEI",
    "DE", "DO", "DA", "DOS", "DAS", "E",
})
# S3a: conta de crédito com este texto no nome (sem acento, maiúsculas) = desconto lançado à parte.
TEXTO_CONTA_DESCONTO = "DESCONTO"
# S4: situação da DANFSe que não gera observação (sem acento, maiúsculas).
SITUACAO_NOTA_AUTORIZADA = "AUTORIZADA"

# ---------------------------------------------------------------------------
# Fundação e download das notas — seções 3.4 e 5
# ---------------------------------------------------------------------------

# Raiz (8 primeiros dígitos) do CNPJ da Fundação: nota emitida por ela não é compra.
RAIZ_CNPJ_FUNDACAO = "98765432"
# S15 (pedido do usuário, 19/10/2026): CNPJ de cada unidade da Fundação. A nota (DANFE ou DANFSe)
# tem que vir com o CNPJ da unidade escolhida na tela no destinatário / tomador; senão o fato
# fica DIVERGENTE.
# Unidade nova ou CNPJ novo: acrescentar a linha aqui.
UNIDADES_FUNDACAO = {
    "98765432000198": "Fundação Hospital Exemplo",
    "98765432000430": "AME Cidade Alfa",
    "98765432000783": "AME Cidade Eta",
    "98765432000864": "AME Cidade Gama",
    "98765432000945": "CMD",                    # pedido do usuário, 04/11/2026
    "98765432001089": "AME Vale Zeta / Cidade Zeta",
    "98765432001160": "AME Cidade Delta",
    "98765432001240": "AME Cidade Beta",
    "98765432001402": "AME Cidade Epsilon",
}
MOTIVO_DESTINATARIO = "CNPJ da nota não é o da unidade conferida"
# Arquivo do download em lote com as chaves das notas que vieram sem DANFE.
ARQUIVO_SEM_PDF = "_sem_pdf.txt"

# ---------------------------------------------------------------------------
# Relatório Excel — seção 5
# ---------------------------------------------------------------------------

# Data e hora no nome, para nunca substituir um relatório anterior.
NOME_RELATORIO = "Conferencia_NF_{data_hora}.xlsx"
FORMATO_DATA_HORA_NOME = "%Y-%m-%d_%H%M%S"

ABA_RESUMO = "Resumo"
ABA_A_MAO = "Conferir à mão"
ABA_PREFEITURA = "Escriturar na prefeitura"
ABA_LANCAMENTOS = "Lançamentos"
ABA_RATEIOS = "Rateios"
ABA_PDF_X_TASY = "PDF x Tasy"
ABA_SEM_LANCAMENTO = "PDFs sem lançamento"
ABA_ERROS = "Erros de leitura"

# Cor de cada situação (S5): verde OK, vermelho divergente, amarelo conferir e sem PDF, cinza sem
# nº de nota, azul estorno, roxo retenção (S13). Na aba "Lançamentos" os fatos alternam com o tom claro.
CORES_SITUACAO = {
    "OK": "C6EFCE",
    "DIVERGENTE": "FFC7CE",
    "CONFERIR": "FFEB9C",
    "SEM PDF": "FFEB9C",
    "SEM Nº DE NOTA": "D9D9D9",
    "ESTORNO": "BDD7EE",
    "CONFERIR RETENÇÃO": "D9C2EC",      # roxo (S13, escolha do usuário)
}
CORES_SITUACAO_CLARAS = {
    "OK": "E2F5E6",
    "DIVERGENTE": "FFE3E6",
    "CONFERIR": "FFF5CC",
    "SEM PDF": "FFF5CC",
    "SEM Nº DE NOTA": "EDEDED",
    "ESTORNO": "DDEBF7",
    "CONFERIR RETENÇÃO": "EDE2F6",
}
COR_FUNDO_TITULO = "1F4E78"
COR_FONTE_TITULO = "FFFFFF"
COR_BORDA = "7F7F7F"
FORMATO_VALOR_EXCEL = "#,##0.00"

# Ordem das abas "Conferir à mão" e "PDF x Tasy" (dentro de cada grupo, por fornecedor).
ORDEM_SITUACAO = ("DIVERGENTE", "ESTORNO", "CONFERIR RETENÇÃO", "CONFERIR", "SEM PDF",
                  "SEM Nº DE NOTA", "OK")

# Coluna "O que fazer" da aba "Lançamentos".
ACAO_OK = "Só conferir as contas contábeis"
ACAO_NOTA_IMPRESSA = "Conferir com a nota impressa"
ACAO_ESTORNO = "Estorno: verificar os lançamentos"

# S9: coluna das notas de serviço nas abas "Conferir à mão" e "Lançamentos".
COLUNA_PREFEITURA = "Escriturar na prefeitura"
MARCA_PREFEITURA = "SIM"

# S10 (pedido do usuário e da chefia, 16/10/2026): prestador "Não Optante" sem nenhum imposto
# federal retido -> "Falar com o fornecedor" na aba "Escriturar na prefeitura".
COLUNA_FALAR_FORNECEDOR = "Falar com o fornecedor"
MARCA_FALAR_FORNECEDOR = "SIM"
MARCA_FEDERAIS_NAO_LIDOS = "CONFERIR NO PDF (impostos federais não lidos)"

# S13 (pedido do usuário, 16/10/2026): retenções da DANFSe x crédito na conta de cada imposto
# (código reduzido). IRRF: P.J. ou P.F. pelo documento do prestador (CNPJ 14 ou CPF 11 dígitos).
CONTA_IRRF_PJ = "20776"
CONTA_IRRF_PF = "20775"
CONTA_INSS = "20769"
CONTA_PIS_COFINS_CSLL = "25206"
CONTA_ISS_RETIDO = "21996"
RETENCAO_ISS_RETIDO = "RETIDO"   # "Retenção do ISSQN" da nota, sem acento e maiúsculas (não "NÃO RETIDO")

# S16 (pedido do usuário, 19/10/2026): alíquota (em %) de cada retenção federal da nota de serviço
# sobre o valor do serviço. Só confere o imposto que veio retido; o IRRF de prestador pessoa física
# (CPF) não é conferido (tabela progressiva). INSS: vale qualquer uma das alíquotas da lista.
ALIQUOTA_IRRF = Decimal("1.5")
ALIQUOTAS_INSS = (Decimal("11"), Decimal("20"))
ALIQUOTA_PIS_COFINS_CSLL = Decimal("4.65")
# Diferença aceita entre o valor da nota e o calculado: cada fornecedor arredonda de um jeito
# (corta o centavo, ou calcula PIS, COFINS e CSLL separados e soma). Nos lotes de exemplo, até 0,01.
TOLERANCIA_ALIQUOTA = Decimal("0.01")
MOTIVO_ALIQUOTA = "Alíquota da retenção diferente da esperada"

# S16a (pedido do usuário, 19/10/2026): "Descrição Contrib. Sociais - Retidas" da DANFSe ("Código 3")
# = tpRetPisCofins do XML, tipo de retenção do PIS/COFINS/CSLL (NT SE/CGNFS-e 007/2026). O valor
# "Contribuições Sociais - Retidas" (vRetCSLL) é a SOMA do que foi retido dos três. Cada código dá as
# alíquotas aceitas (PIS 0,65% + COFINS 3% + CSLL 1%). Os códigos 1 e 2 são antigos (vão sumir) e
# não dizem nada da CSLL: aceitam com e sem ela. Nota sem código: ALIQUOTA_PIS_COFINS_CSLL.
RE_CODIGO_CONTRIBUICOES = re.compile(r"^(?:C[OÓ]DIGO\s*)?(\d)\b", re.IGNORECASE)
CODIGOS_CONTRIBUICOES = {
    "0": ("PIS/COFINS/CSLL não retidos", (Decimal("0"),)),
    "1": ("PIS/COFINS retidos (código antigo; não diz da CSLL)", (Decimal("3.65"), Decimal("4.65"))),
    "2": ("PIS/COFINS não retidos (código antigo; não diz da CSLL)", (Decimal("0"), Decimal("1"))),
    "3": ("PIS/COFINS/CSLL retidos", (Decimal("4.65"),)),
    "4": ("PIS/COFINS retidos, CSLL não retida", (Decimal("3.65"),)),
    "5": ("PIS retido, COFINS/CSLL não retidos", (Decimal("0.65"),)),
    "6": ("COFINS retido, PIS/CSLL não retidos", (Decimal("3"),)),
    "7": ("PIS não retido, COFINS/CSLL retidos", (Decimal("4"),)),
    "8": ("PIS/COFINS não retidos, CSLL retida", (Decimal("1"),)),
    "9": ("COFINS não retido, PIS/CSLL retidos", (Decimal("1.65"),)),
}
LEGENDA_CODIGOS_TITULO = ("Códigos da coluna \"Descrição contrib. sociais\" — tipo de retenção do "
                          "PIS/COFINS/CSLL (Nota Técnica SE/CGNFS-e nº 007/2026)")
LEGENDA_CODIGOS_NOTA = ("A coluna \"Contribuições Sociais retidas\" é a soma do que foi retido de "
                        "PIS (0,65%), COFINS (3%) e CSLL (1%), conforme o código. Nota sem código: "
                        "o programa espera os três (4,65%).")

# ---------------------------------------------------------------------------
# Gabarito de contas (S14) — gabarito.py
# ---------------------------------------------------------------------------

GABARITO_ARQUIVO = "Gabarito_contas.xlsx"
GABARITO_PASTA_COPIAS = "copias_de_seguranca"
GABARITO_COPIAS = 20                         # cópias de segurança guardadas
# O fornecedor é o crédito em conta de fornecedores; entram os débitos em estoque (1.01.04),
# imobilizado (1.02), custo/despesa (3) e receita (4).
CLASSIFICACAO_FORNECEDORES = "2.01.01.01"
CLASSIFICACOES_GABARITO = ("1.01.04", "1.02", "3", "4")
# Produto: o texto entre "NF. número -" e "DT", "PR" ou "O.C" do complemento.
RE_PRODUTO = re.compile(
    r"NF\.?\s*(?:n[ºo°]\.?\s*)?\d+\s*-\s*(.+?)(?=\s+DT\s?\d{2}/|\s+PR\s|\s+O\.?\s?C|$)",
    re.IGNORECASE)
GABARITO_TAMANHO_PRODUTO = 60
SEM_PRODUTO = "(sem produto no complemento)"
GABARITO_SUGESTAO = "<- mais usada"
GABARITO_ABA_PADRAO = "Padrão"
GABARITO_ABA_HISTORICO = "Histórico"
GABARITO_ABA_PADRONIZAR = "Para padronizar"
GABARITO_ABA_FATOS = "Fatos aprendidos"
GABARITO_ABAS = {
    GABARITO_ABA_PADRAO: ("Fornecedor (conta)", "Nome do fornecedor", "Produto",
                          "Conta padrão (código)", "Classificação e nome", "Decidido por", "Data",
                          "Observação"),
    GABARITO_ABA_HISTORICO: ("Fornecedor (conta)", "Nome do fornecedor", "Produto", "Conta",
                             "Classificação", "Nome da conta", "Vezes", "Primeira vez",
                             "Última vez", "Exemplo de complemento"),
    GABARITO_ABA_PADRONIZAR: ("Fornecedor (conta)", "Nome do fornecedor", "Produto", "Conta",
                              "Classificação", "Nome da conta", "Vezes", "% do produto",
                              "Última vez", "Sugestão", "Já padronizado"),
    GABARITO_ABA_FATOS: ("Fato contábil", "Data", "Arquivo", "Aprendido em"),
}
# Resultado de cada lançamento na conferência (só informativo).
GABARITO_IGUAL_PADRAO = "IGUAL AO PADRÃO"
GABARITO_FORA_PADRAO = "FORA DO PADRÃO"
GABARITO_IGUAL_HISTORICO = "IGUAL AO HISTÓRICO"
GABARITO_DIFERENTE = "DIFERENTE DO HABITUAL"
GABARITO_PRODUTO_NOVO = "PRODUTO NOVO"
GABARITO_FORNECEDOR_NOVO = "FORNECEDOR NOVO"
GABARITO_ORDEM = (GABARITO_FORA_PADRAO, GABARITO_DIFERENTE, GABARITO_PRODUTO_NOVO,
                  GABARITO_FORNECEDOR_NOVO, GABARITO_IGUAL_HISTORICO, GABARITO_IGUAL_PADRAO)
ABA_CONTAS = "Contas a conferir"
GABARITO_CORES = {
    GABARITO_FORA_PADRAO: "F8CBAD",          # laranja: diferente do que a chefia decidiu
    GABARITO_DIFERENTE: "FFEB9C",            # amarelo: diferente do habitual
    GABARITO_PRODUTO_NOVO: "EDEDED",         # cinza: ainda sem histórico
    GABARITO_FORNECEDOR_NOVO: "EDEDED",
}

# Coluna "Motivo" da aba "Conferir à mão" e linhas do resumo.
MOTIVOS = {
    "SEM PDF": "PDF da nota não veio",
    "SEM Nº DE NOTA": "Não é nota fiscal (recibo, doação, taxa...)",
    "DIVERGENTE": "PDF não bate com o lançamento",
    "CONFERIR": "Casou com o PDF, mas tem observação",
    "ESTORNO": "Lançamento e estorno que se anulam",
    "CONFERIR RETENÇÃO": "Retenção da nota não bate com o lançamento",
}
