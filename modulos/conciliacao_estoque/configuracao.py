"""Constantes do módulo de Estoque (ESPECIFICACAO_ESTOQUE.md).

Tudo o que pode mudar de um mês para outro, ou de uma versão do Tasy para outra, fica aqui.
"""

from __future__ import annotations

from modulos.conciliacao_estoque.modelos import Etapa

# ---------------------------------------------------------------------------
# Etapas do tipo "valor do balancete x coluna do SCF" (seção 6.4)
# ---------------------------------------------------------------------------
# Uma etapa nova do mesmo tipo é só uma linha nova nesta lista. A EST-02 é de outro tipo.
# Nomes dos botões e dos títulos do Excel: decisão do usuário (06/10/2026).

ETAPAS = [
    Etapa(id="EST-01", titulo="Conciliação saldo anterior estoque",
          campo_balancete="saldo_anterior", campo_scf="Saldo Anterior"),
    Etapa(id="EST-03", titulo="Conciliação saldo atual estoque",
          campo_balancete="saldo_atual", campo_scf="Saldo Atual"),
]

# EST-02: Conferência dos Grupos SCF x Movimento Estoque (PDF)
ID_EST02 = "EST-02"
TITULO_EST02 = "Conciliação contas estoque"

# ---------------------------------------------------------------------------
# Arquivos do Tasy (seção 3.1)
# ---------------------------------------------------------------------------

# Os ".xls" do Tasy são texto separado por tabulação, nesta codificação.
CODIFICACAO_TASY = "cp1252"
SEPARADOR_TASY = "\t"

# Número no formato brasileiro: 1.234.567,89 / -523.694,13 / 0 / 660 / 59,7
PADRAO_NUMERO = r"^-?(\d{1,3}(\.\d{3})+|\d+)(,\d+)?$"

# Início de rodapé de página (linha ignorada).
RODAPES = ("Impresso em", "Página")

# ---------------------------------------------------------------------------
# Balancete (seção 3.2)
# ---------------------------------------------------------------------------

# Classificação de conta: 1.01.04 / 1.01.04.01 / 1.01.04.01.0002
BALANCETE_PADRAO_CLASSIFICACAO = r"^\d+(\.\d{2})+(\.\d{4})?$"

# Só entram as contas sob este prefixo (grupo ESTOQUES).
PREFIXO_ESTOQUE = "1.01.04"

BALANCETE_TITULO_MES_REFERENCIA = "Mês Referência"
# Títulos que identificam o arquivo como balancete (linha de títulos).
BALANCETE_TITULOS_VALORES = ("Saldo Anterior", "Movimento", "Saldo Atual")
# O balancete do CMD e dos AMES traz Débitos e Créditos no lugar do Movimento (Movimento = D − C).
BALANCETE_TITULOS_DEBITO_CREDITO = ("Saldo Anterior", "Débitos", "Créditos", "Saldo Atual")

# ---------------------------------------------------------------------------
# SCF - Movimento Estoque (Contabilidade) (seção 3.3)
# ---------------------------------------------------------------------------

# Os 13 valores de cada linha, NA ORDEM em que aparecem (a posição 1 é o Saldo Anterior,
# a 13 é o Saldo Atual). O programa lê pela posição do número na linha, nunca pela coluna.
SCF_TITULOS = (
    "Saldo Anterior", "Notas Fiscais", "Emprestimo", "Inventário", "Out.Entradas", "Total (E)",
    "Consumo", "Inventário", "Pacientes", "Subvenção", "Out.Saídas", "Total (S)", "Saldo Atual",
)
# Títulos que podem faltar: o SCF do CMD e dos AMES não tem a coluna Subvenção; o valor
# dela fica 0,00 e as posições dos demais não mudam (a configuração da EST-02 usa a posição).
SCF_TITULOS_OPCIONAIS = ("Subvenção",)
SCF_TITULO_DESCRICAO = "Descrição"
SCF_TITULO_MES_COMPETENCIA = "Mês competência"
# Linha de local: o primeiro texto termina com o código do local entre parênteses.
SCF_PADRAO_CODIGO_LOCAL = r"\((\d+)\)\s*$"
# Linha de total: "Total(40)".
SCF_PADRAO_TOTAL = r"^Total\s*\((\d+)\)$"

# ---------------------------------------------------------------------------
# Casamento das contas com os locais do SCF (seção 4)
# ---------------------------------------------------------------------------

# Nível 2: abreviações trocadas palavra por palavra (depois de tirar acentos e pontuação).
CASAMENTO_ABREVIACOES = {
    "sc": "hospital exemplo",
    "scf": "hospital exemplo",
    "hc": "hospital coracao",
    "hosp": "hospital",
    "h": "hospital",
}
# Nível 2: palavras sem valor para a comparação.
CASAMENTO_PALAVRAS_SEM_VALOR = {"estoque", "de", "do", "da", "e"}
# Nível 2: unidades separadas do nome (um nome pode ter mais de uma).
CASAMENTO_UNIDADES = {
    "hospital exemplo": "SC",
    "hospital coracao": "HC",
    "hospital central": "HCA",
}
# Nível 3: semelhança mínima para sugerir um possível par.
CASAMENTO_SEMELHANCA_MINIMA = 0.5

# "set/2026" -> 9
MESES_ABREVIADOS = {
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
}

# ---------------------------------------------------------------------------
# EST-02: planilha de configuração (seção 3.6)
# ---------------------------------------------------------------------------

EST02_NOME_ARQUIVO = "Configuracao_EST-02_Itens_mapa_estoque.xlsx"
# cópia de fábrica, dentro do programa (e do .exe, com --add-data)
EST02_PASTA_FABRICA = ("modulos", "conciliacao_estoque", "recursos")
# cópia do usuário: %APPDATA%\CentralConciliacoes\configuracoes\
PASTA_DADOS_USUARIO = "CentralConciliacoes"
EST02_SUBPASTA_USUARIO = "configuracoes"

EST02_ABA_ITENS = "Itens"
EST02_ABA_GRUPOS = "Grupos"
EST02_ABA_PARES = "Pares iguais"
EST02_TITULOS_ITENS = ("Código", "Operação", "E/S no Tasy", "Tipo de operação", "Grupo SCF")
EST02_TITULOS_GRUPOS = ("Grupo SCF", "Tipo", "Posição no SCF")
EST02_TITULOS_PARES = ("Operação A", "Nome A", "Operação B", "Nome B", "Observação")
EST02_TIPO_ENTRADA = "Entrada"
EST02_TIPO_SAIDA = "Saída"
# "E/S no Tasy" que combina com cada tipo de grupo (diferente -> aviso INFO)
EST02_ES_DO_TIPO = {EST02_TIPO_ENTRADA: "E", EST02_TIPO_SAIDA: "S"}
# posições do SCF calculadas (Total (E) e Total (S)): nenhum grupo pode usá-las
EST02_POSICOES_CALCULADAS = (6, 12)

# ---------------------------------------------------------------------------
# EST-02: PDF "Movimento estoque" (seção 3.5)
# ---------------------------------------------------------------------------

PDF_TITULO = "Movimento estoque"
PDF_ROTULO_MES = "Data de Referência"
PDF_RODAPES = ("Impresso em", "Página")
