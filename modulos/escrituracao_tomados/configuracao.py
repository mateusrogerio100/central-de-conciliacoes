"""Valores fixos do módulo Escrituração de Serviços Tomados.

Se a Fundação, o município ou o site mudarem algum destes dados, basta alterar a linha aqui.
As posições do arquivo .txt ficam em layout_v3.py.
"""

# ---------------------------------------------------------------------------
# Fundação e município
# ---------------------------------------------------------------------------

# Raiz (8 primeiros dígitos) do CNPJ da Fundação: tomador com esta raiz = estabelecimento da
# Fundação; prestador com esta raiz = nota de serviço PRESTADO, fica de fora (R1).
RAIZ_CNPJ_FUNDACAO = "98765432"

# Município do site da prefeitura: define CFPS (R5) e o código de imposto retido (R6).
MUNICIPIO_SEDE = "CIDADE ALFA"

# ---------------------------------------------------------------------------
# Consulta pública de CNPJ (R11) — usada só quando a cidade não está no PDF nem no cadastro
# ---------------------------------------------------------------------------

URL_CONSULTA_CNPJ = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
URL_CONSULTA_CNPJ_RESERVA = "https://publica.cnpj.ws/cnpj/{cnpj}"
TEMPO_LIMITE_CONSULTA_SEGUNDOS = 5

# ---------------------------------------------------------------------------
# PDF da nota (DANFSe v2.0) — seção 4.1 da especificação
# ---------------------------------------------------------------------------

# Texto que identifica o modelo aceito. PDF sem ele = erro de leitura.
DANFSE_IDENTIFICACAO = "DANFSe v2.0"

# NFS-e no modelo da Prefeitura de São Paulo (leitor_nfse_sp.py, decisão do usuário, 08/2026): os
# dois textos juntos identificam o modelo. A nota é lida só para ir a "lançar à mão" (R18).
SP_IDENTIFICACAO = ("PREFEITURA DO MUNICIPIO DE SAO PAULO", "NOTA FISCAL ELETRONICA DE SERVICOS")
SP_MOTIVO_LANCAR_A_MAO = (
    "NFS-e no modelo da Prefeitura de São Paulo: não traz competência, regime (Simples) nem "
    "retenção do ISS; conferir no PDF e lançar à mão (ou baixar a DANFSe nacional pela chave)")

# Posição horizontal (x) onde começa cada uma das 4 colunas da DANFSe. Cada dado fica na
# coluna do seu rótulo, na primeira linha abaixo dele.
DANFSE_COLUNAS_X = (11, 156, 300, 445)
DANFSE_TOLERANCIA_X = 3            # folga para a posição das palavras
DANFSE_TOLERANCIA_LINHA = 2.0      # palavras com "top" até esta distância estão na mesma linha
# Letras maiores que isto são a marca d'água "CANCELADA" / "SUBSTITUÍDA" (tamanho 45 a 61; o
# texto da nota vai de 6 a 9) e são ignoradas: grudadas nos valores, estragavam a leitura (07/2026).
DANFSE_TAMANHO_MAXIMO_TEXTO = 20
DANFSE_DISTANCIA_MAXIMA_VALOR = 14  # o valor fica até esta distância abaixo do rótulo

# Blocos da nota (os rótulos "CNPJ / CPF / NIF" e "Nome / Nome Empresarial" se repetem).
DANFSE_BLOCO_PRESTADOR = "PRESTADOR / FORNECEDOR"
DANFSE_BLOCO_TOMADOR = "TOMADOR / ADQUIRENTE"
DANFSE_BLOCO_VALORES = "VALOR TOTAL DA NFS-E"
# Nota sem tomador (caso da nota 585, 08/2026): fica NÃO INCLUÍDA (decisão do usuário, 28/09/2026)
DANFSE_TOMADOR_NAO_IDENTIFICADO = "TOMADOR/ADQUIRENTE DA OPERAÇÃO NÃO IDENTIFICADO"
DANFSE_BLOCO_INTERMEDIARIO = "INTERMEDIÁRIO DA OPERAÇÃO"

# Rótulos dos campos, como aparecem na DANFSe.
DANFSE_ROTULO_CHAVE = "CHAVE DE ACESSO DA NFS-E"
DANFSE_ROTULO_NUMERO = "NÚMERO DA NFS-E"
DANFSE_ROTULO_COMPETENCIA = "COMPETÊNCIA DA NFS-E"
DANFSE_ROTULO_EMISSAO = "DATA E HORA DA EMISSÃO DA NFS-E"
DANFSE_ROTULO_SITUACAO = "SITUAÇÃO DA NFS-E"
DANFSE_ROTULO_DOCUMENTO = "CNPJ / CPF / NIF"
DANFSE_ROTULO_NOME = "Nome / Nome Empresarial"
DANFSE_ROTULO_MUNICIPIO = "Município / Sigla UF"
DANFSE_ROTULO_REGIME = "Simples Nacional na Data de Competência"
DANFSE_ROTULO_ATIVIDADE = "Código de Tributação Nacional / Municipal"
DANFSE_ROTULO_LOCAL_PRESTACAO = "Local da Prestação / Sigla UF / País"
DANFSE_ROTULO_TIPO_TRIBUTACAO = "Tipo de Tributação do ISSQN"
DANFSE_ROTULO_INCIDENCIA = "Município / Sigla UF / País da Incidência do ISSQN"
DANFSE_ROTULO_DEDUCOES = "Total Deduções/Reduções"
DANFSE_ROTULO_DESCONTO_INCONDICIONADO = "Desconto Incondicionado"
DANFSE_ROTULO_ALIQUOTA = "Alíquota Aplicada"
DANFSE_ROTULO_BASE_CALCULO = "BC ISSQN"
DANFSE_ROTULO_RETENCAO = "Retenção do ISSQN"
DANFSE_ROTULO_ISS = "ISSQN Apurado"
DANFSE_ROTULO_VALOR_SERVICO = "VALOR DA OPERAÇÃO / SERVIÇO"
# Texto do código de atividade (ex.: "Medicina."): nas linhas entre o código e este rótulo.
DANFSE_ROTULO_DESCRICAO_SERVICO = "Descrição do Serviço"

# Quadro "TRIBUTAÇÃO FEDERAL (EXCETO CBS)" (R19). Só informativo: nunca causa erro de leitura.
DANFSE_BLOCO_FEDERAL = "TRIBUTAÇÃO FEDERAL"
DANFSE_ROTULO_IRRF = "IRRF"
DANFSE_ROTULO_PREVIDENCIA = "Contribuição Previdenciária - Retida"
DANFSE_ROTULO_CONTRIBUICOES = "Contribuições Sociais - Retidas"
DANFSE_ROTULO_DESCRICAO_CONTRIBUICOES = "Descrição Contrib. Sociais - Retidas"

# Modelo em que o quadro "TRIBUTAÇÃO MUNICIPAL (ISSQN)" vem reduzido a esta frase (sem alíquota,
# ISS, retenção nem incidência). A nota vai para "lançar à mão" pela R10 (caso da nota 140, 08/2026).
DANFSE_TEXTO_NAO_SUJEITA = "OPERAÇÃO NÃO SUJEITA AO ISSQN"
TRIBUTACAO_NAO_SUJEITA = "Operação não sujeita ao ISSQN"

# Campo sem valor na DANFSe.
DANFSE_VAZIO = "-"

# Regime do prestador (R7), pelo texto de "Simples Nacional na Data de Competência".
# Comparação sem acento e sem diferença de maiúsculas; MEI é conferido antes de "Optante".
REGIME_TEXTOS_MEI = ("MEI", "MICROEMPREENDEDOR")
REGIME_TEXTO_NAO_OPTANTE = "NAO OPTANTE"
REGIME_TEXTO_OPTANTE = "OPTANTE"

# Retenção do ISSQN, pelo texto da DANFSe (comparação sem acento, maiúsculas).
RETENCAO_TEXTO_NAO_RETIDO = "NAO RETIDO"
RETENCAO_TEXTO_RETIDO = "RETIDO"

# ---------------------------------------------------------------------------
# Exportações e "resultados" do site (seções 4.2 e 4.3) — colunas pelo título
# ---------------------------------------------------------------------------

# O site grava latin-1, mas alguns .txt exportados vêm em UTF-8 (com "N�O" no lugar de "NÃO"):
# tenta UTF-8 e, se não der, latin-1.
CODIFICACAO_SITE = "latin-1"
SITE_COLUNA_NUMERO = "nfs"
SITE_COLUNA_DOCUMENTO = "cnpjcpf"
SITE_COLUNAS_OBRIGATORIAS = (SITE_COLUNA_NUMERO, SITE_COLUNA_DOCUMENTO)

# Colunas usadas para unificar lotes (todas obrigatórias nas exportações).
SITE_COLUNA_CFPS = "cfps"
SITE_COLUNA_SITUACAO = "situacaonf"
SITE_COLUNA_NOME = "nome"
SITE_COLUNA_EMISSAO = "dtemissao"
SITE_COLUNA_ATIVIDADE = "descratividade"
SITE_COLUNA_SERVICOS = "vlrservicos"
SITE_COLUNA_DEDUCOES = "vlrdeducoes"
SITE_COLUNA_DESCONTO_INCONDICIONADO = "descontoincondicionado"
SITE_COLUNA_ALIQUOTA = "aliquota"
SITE_COLUNA_BASE_CALCULO = "basecalculo"      # opcional: só para a conferência do ISS
SITE_COLUNA_RETIDO = "impretido"
SITE_COLUNA_IMPOSTO = "vlrimposto"
SITE_COLUNA_REGIME = "enquadradosn"
SITE_COLUNAS_EXPORTACAO = (
    SITE_COLUNA_CFPS, SITE_COLUNA_NUMERO, SITE_COLUNA_SITUACAO, SITE_COLUNA_DOCUMENTO,
    SITE_COLUNA_NOME, SITE_COLUNA_EMISSAO, SITE_COLUNA_ATIVIDADE, SITE_COLUNA_SERVICOS,
    SITE_COLUNA_DEDUCOES, SITE_COLUNA_DESCONTO_INCONDICIONADO, SITE_COLUNA_ALIQUOTA,
    SITE_COLUNA_RETIDO, SITE_COLUNA_IMPOSTO, SITE_COLUNA_REGIME,
)

# cfps do site -> código do arquivo (V4).
SITE_CFPS = {"1": "001", "2": "002"}

# Situação "Normal" do site = nota autorizada.
SITUACOES_AUTORIZADAS = ("AUTORIZADA", "NORMAL")

# R19 (pedido do usuário e da chefia, 16/10/2026): prestador "Não Optante" sem nenhum imposto
# federal retido na nota -> aba do relatório para falar com o fornecedor.
ABA_FALAR_COM_FORNECEDOR = "Falar com o fornecedor"

# ---------------------------------------------------------------------------
# Cadastro de prestadores (R11) e consulta pública de CNPJ
# ---------------------------------------------------------------------------

PASTA_DADOS_USUARIO = "CentralConciliacoes"      # dentro de %APPDATA%
SUBPASTA_MODULO = "escrituracao_tomados"
NOME_CADASTRO_PRESTADORES = "prestadores.json"
NOME_TOMADORES_USADOS = "tomadores.json"      # CNPJs de tomador já usados nas exportações (R12)
NOME_OUTROS_CNPJS_FUNDACAO = "outros_cnpjs_fundacao.json"   # CNPJs da Fundação de outra raiz (R1)

ORIGEM_CIDADE_PDF = "PDF"
ORIGEM_CIDADE_CONSULTA = "consulta CNPJ"
ORIGEM_CIDADE_INFORMADA = "informada na tela"

# ---------------------------------------------------------------------------
# Regras (R1, R2, R10)
# ---------------------------------------------------------------------------

# Situações de nota que fica fora (comparação sem acento, maiúsculas).
SITUACAO_CANCELADA = "CANCELADA"
SITUACAO_SUBSTITUIDA = "SUBSTITUIDA"

# Tipo de tributação do ISSQN que entra no arquivo; qualquer outro vai para "lançar à mão".
TRIBUTACAO_TRIBUTAVEL = "OPERACAO TRIBUTAVEL"

# Diferença tolerada entre o ISS da nota e (serviço - deduções) x alíquota, antes de avisar.
TOLERANCIA_ISS = "0.01"

# ---------------------------------------------------------------------------
# Arquivo .txt de importação (V1)
# ---------------------------------------------------------------------------

CODIFICACAO_TXT = "latin-1"
QUEBRA_DE_LINHA = "\r\n"

# Um arquivo por CNPJ do tomador + competência (R4).
MODELO_NOME_ARQUIVO = "tomados_{cnpj_tomador}_{competencia}.txt"

# Relatório (seção 6): data e hora no nome, para nunca substituir um relatório anterior.
MODELO_NOME_RELATORIO = "Relatorio_Tomados_{data_hora}.xlsx"
FORMATO_DATA_HORA_RELATORIO = "%Y-%m-%d_%H%M%S"

# Textos da tela do site, para a aba "Lançar à mão" (V4, V5, V6).
TEXTO_SITE_CFPS = {
    "001": "Serviço prestado no município de Cidade Alfa",
    "002": "Serviço prestado fora do município de Cidade Alfa",
}
TEXTO_SITE_RETIDO = {
    "N": "NÃO",
    "S": "SIM",
    "Z": "NÃO (devido FORA do município)",
    "X": "SIM (devido FORA do município)",
}
TEXTO_SITE_REGIME = {"N": "Não", "S": "SINAC", "M": "MEI"}

# Tipo de referência do header (R14): Normal ou Complementar.
TIPO_REFERENCIA_NORMAL = "N"
TIPO_REFERENCIA_COMPLEMENTAR = "C"
TIPOS_REFERENCIA = (TIPO_REFERENCIA_NORMAL, TIPO_REFERENCIA_COMPLEMENTAR)

# Tipo de identificação do prestador, pela quantidade de dígitos do documento (R3).
TIPO_IDENTIFICACAO_POR_DIGITOS = {14: "1", 11: "2"}   # CNPJ / CPF

# Códigos aceitos nos campos de uma letra (seção 3 da especificação).
CODIGOS_IMPOSTO_RETIDO = ("N", "S", "Z", "X")
CODIGOS_REGIME = ("N", "S", "M")
CODIGOS_CFPS = ("001", "002")
