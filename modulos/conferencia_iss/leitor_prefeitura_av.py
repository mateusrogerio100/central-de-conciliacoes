"""
Leitura da "Declaração Completa de Tomador" da Prefeitura de Cidade Zeta (PDF).

- O site entrega um PDF (gerado pelo JasperReports). Lido com pdfplumber, que dá a
  POSIÇÃO de cada texto na página: a extração de texto simples embaralha os campos.
- Cada nota ocupa 3 linhas, sempre com os mesmos rótulos:
      Número: N  Competência:dd/mm/aaaa  PRESTADOR  Serviço: R$  Alíquota: %  Cofins: % R$  CSLL: % R$
      Emissão:dd/mm/aaaa  Espécie: ...  CNPJ/CPF: ...  Optante?X  Dedução: R$  Desc. Incond: R$  INSS: ...  IRRF: ...
      Série: ...  Exigibilidade:...  Regime: ...  ISS: R$  Incidência: CIDADE  PIS: % R$
  Os campos são separados pelos rótulos (nunca pela ordem do texto).
- Seções: uma linha só com a situação ("Normal"; "Cancelada" → nota cancelada) e
  "Imposto Retido: Sim/Não". Cabeçalho: "Ano: 2026", "Mês: 9" e a inscrição municipal.
- O PDF imprime totais (quantidade e valor) por grupo e no fim. A leitura é conferida
  contra eles: se não bater, vira aviso — é a garantia de que nenhuma nota ficou para trás.
- Nunca levanta exceção: problema no arquivo vira `erro`, problema numa nota vira aviso.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from modulos.conferencia_iss.leitor_prefeitura import MESES, LeituraPrefeitura, _aviso, ler_relatorio_prefeitura
from modulos.conferencia_iss.leitor_prefeitura_cp import ERRO_E_DE_CIDADE_GAMA, eh_relatorio_de_cidade_gama
from modulos.conferencia_iss.leitor_prefeitura_sj import ler_relatorio_cidade_epsilon
from modulos.conferencia_iss.modelos import LinhaPrefeitura
from modulos.conferencia_iss.normalizar import normalizar_documento, normalizar_numero, valor_prefeitura

NOME_RELATORIO = "Declaração Completa de Tomador"

# Rótulos das 3 linhas de cada nota (como aparecem no PDF)
ROT_NUMERO = "Número:"
ROT_COMPETENCIA = "Competência:"
ROT_SERVICO = "Serviço:"
ROT_ALIQUOTA = "Alíquota:"
ROT_COFINS = "Cofins:"
ROT_CSLL = "CSLL:"
ROT_EMISSAO = "Emissão:"
ROT_ESPECIE = "Espécie:"
ROT_DOCUMENTO = "CNPJ/CPF:"
ROT_OPTANTE = "Optante?"
ROT_DEDUCAO = "Dedução:"
ROT_DESCONTO = "Desc. Incond:"
ROT_INSS = "INSS:"
ROT_IRRF = "IRRF:"
ROT_SERIE = "Série:"
ROT_EXIGIBILIDADE = "Exigibilidade:"
ROT_REGIME = "Regime:"
ROT_ISS = "ISS:"
ROT_INCIDENCIA = "Incidência:"
ROT_PIS = "PIS:"

ROTULOS_NOTA = (
    ROT_NUMERO, ROT_COMPETENCIA, ROT_SERVICO, ROT_ALIQUOTA, ROT_COFINS, ROT_CSLL,
    ROT_EMISSAO, ROT_ESPECIE, ROT_DOCUMENTO, ROT_OPTANTE, ROT_DEDUCAO, ROT_DESCONTO,
    ROT_INSS, ROT_IRRF, ROT_SERIE, ROT_EXIGIBILIDADE, ROT_REGIME, ROT_ISS, ROT_INCIDENCIA,
    ROT_PIS,
)
ROTULOS_OBRIGATORIOS = (ROT_NUMERO, ROT_DOCUMENTO, ROT_SERVICO)

_REGEX_ROTULOS = re.compile("(" + "|".join(re.escape(r) for r in ROTULOS_NOTA) + ")")
_REGEX_REAIS = re.compile(r"R\$\s*(-?[\d.]+,\d{2})")
_REGEX_PERCENTUAL = re.compile(r"(-?[\d.]+,\d+)\s*%")
_REGEX_RETIDO = re.compile(r"Imposto Retido:\s*(\S+)", re.IGNORECASE)
_REGEX_TOTAL_GRUPO = re.compile(r"^Qtde Notas:\s*(\d+)")
_REGEX_TOTAL_SITUACAO = re.compile(r"^Qtde Notas\s+(\w+):\s*(\d+)")
_REGEX_VALOR_NOTA = re.compile(r"Valor Nota:\s*R\$\s*([\d.]+,\d{2})")
_REGEX_ANO = re.compile(r"^Ano:\s*(\d{4})$")
_REGEX_MES = re.compile(r"^Mês:\s*(\d{1,2})$")
_REGEX_TOTAL_FINAL = re.compile(r"^(\d+)\s+R\$\s*([\d.]+,\d{2})")

# Linhas que não são nota e não precisam de aviso
_INICIO_NOTAS = "RELAÇÃO DAS NOTAS FISCAIS DO MOVIMENTO"
_FIM_NOTAS = ("NOTAS FISCAIS COM RETENÇÃO DE ISS", "NOTAS FISCAIS SEM RETENÇÃO DE ISS",
              "TOTAL DECLARADO NO MOVIMENTO")
_LINHAS_IGNORADAS = ("Identificação", "Usuário Logado:", "Impresso em:")

NOMES_MESES = {numero: nome for nome, numero in MESES.items()}
NOMES_MESES[3] = "março"

TOLERANCIA_LINHA = 2.5          # pontos: palavras com "top" mais perto que isso estão na mesma linha
TOLERANCIA_COLUNA = 20          # pontos: valor abaixo do título da coluna (cabeçalho do tomador)


@dataclass
class _Linha:
    pagina: int
    topo: float
    palavras: list[dict]

    @property
    def texto(self) -> str:
        return "  ".join(p["text"].strip() for p in self.palavras if p["text"].strip())


@dataclass
class _Grupo:
    """Notas lidas desde o último total impresso (para conferir com ele)."""

    nome: str = ""
    linhas: list[LinhaPrefeitura] = field(default_factory=list)

    def soma(self) -> Decimal:
        return sum((l.valor_doc for l in self.linhas if l.valor_doc is not None), Decimal(0))


# ---------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------
def ler_relatorio_cidade_zeta(caminho: Path | str) -> LeituraPrefeitura:
    """Lê o PDF de Cidade Zeta. Nunca levanta exceção: problemas vão para erro/avisos."""
    caminho = Path(caminho)
    leitura = LeituraPrefeitura(caminho=caminho)

    try:
        conteudo = caminho.read_bytes()
    except OSError as erro:
        leitura.erro = f"Não foi possível abrir o arquivo: {erro.strerror or erro}"
        return leitura

    if not conteudo.strip():
        leitura.erro = "Arquivo vazio."
        return leitura
    if not conteudo.lstrip().startswith(b"%PDF"):
        leitura.erro = _erro_nao_e_pdf(caminho)
        return leitura

    try:
        linhas = _linhas_do_pdf(caminho)
    except Exception as erro:  # PDF corrompido, protegido por senha...
        leitura.erro = f"Não foi possível ler o PDF: {erro}"
        return leitura

    _ler_linhas(linhas, leitura)
    if leitura.erro:
        leitura.linhas.clear()
    return leitura


def _erro_nao_e_pdf(caminho: Path) -> str:
    """Mensagem para quando escolheram o relatório de outra cidade (ou outro arquivo)."""
    if _leu_bem(ler_relatorio_prefeitura(caminho)):
        return ("Este é o Relatório de Serviços Contratados de Cidade Beta. "
                "Para conferi-lo, use a aba Cidade Beta da Conferência ISS.")
    if _leu_bem(ler_relatorio_cidade_epsilon(caminho)):
        return ("Este é o Relatório de Serviços Tomados de Cidade Epsilon. "
                "Para conferi-lo, use a aba Cidade Epsilon da Conferência ISS.")
    if eh_relatorio_de_cidade_gama(caminho):
        return ERRO_E_DE_CIDADE_GAMA
    from modulos.conferencia_iss.leitor_prefeitura_fr import ERRO_E_DE_CIDADE_ALFA, eh_relatorio_de_cidade_alfa
    if eh_relatorio_de_cidade_alfa(caminho):
        return ERRO_E_DE_CIDADE_ALFA
    return (f"O arquivo não é um PDF. Confira se é a {NOME_RELATORIO} baixada do site da "
            "Prefeitura de Cidade Zeta.")


def _leu_bem(leitura: LeituraPrefeitura) -> bool:
    return leitura.erro is None and bool(leitura.linhas)


def _linhas_do_pdf(caminho: Path) -> list[_Linha]:
    """Todas as linhas de texto do PDF, em ordem (página, de cima para baixo)."""
    import pdfplumber

    linhas: list[_Linha] = []
    with pdfplumber.open(caminho) as pdf:
        for numero_pagina, pagina in enumerate(pdf.pages, start=1):
            palavras = pagina.extract_words(keep_blank_chars=True, x_tolerance=1.5)
            da_pagina: list[_Linha] = []
            for palavra in sorted(palavras, key=lambda p: (p["top"], p["x0"])):
                if da_pagina and abs(da_pagina[-1].topo - palavra["top"]) < TOLERANCIA_LINHA:
                    da_pagina[-1].palavras.append(palavra)
                else:
                    da_pagina.append(_Linha(numero_pagina, palavra["top"], [palavra]))
            for linha in da_pagina:
                linha.palavras.sort(key=lambda p: p["x0"])
            linhas.extend(da_pagina)
    return linhas


# ---------------------------------------------------------------------
# Interpretação das linhas
# ---------------------------------------------------------------------
def _ler_linhas(linhas: list[_Linha], leitura: LeituraPrefeitura) -> None:
    ano = mes = None
    situacao = "Normal"
    retido = ""
    dentro_das_notas = False
    grupo = _Grupo()              # desde o último "Qtde Notas:"
    da_situacao = _Grupo(situacao)  # desde o último título de situação
    totais_conferidos = 0

    posicao = 0
    while posicao < len(linhas):
        linha = linhas[posicao]
        texto = linha.texto

        if not dentro_das_notas:
            if (encontrado := _REGEX_ANO.match(texto)):
                ano = int(encontrado.group(1))
            elif (encontrado := _REGEX_MES.match(texto)):
                mes = int(encontrado.group(1))
            elif "Inscrição Municipal" in texto and not leitura.inscricao_municipal:
                leitura.inscricao_municipal = _valor_abaixo(linha, linhas, posicao,
                                                            "Inscrição Municipal")
            elif texto.startswith(_INICIO_NOTAS):
                dentro_das_notas = True
            posicao += 1
            continue

        if texto.startswith(ROT_NUMERO):
            bloco = [linha]
            posicao += 1
            while posicao < len(linhas):
                seguinte = linhas[posicao].texto
                if seguinte.startswith(_LINHAS_IGNORADAS):
                    # rodapé no meio da nota (a nota continua na página seguinte)
                    resto = linhas[posicao + 1].texto if posicao + 1 < len(linhas) else ""
                    if _continua_nota(resto):
                        posicao += 1
                        continue
                    break
                if not _continua_nota(seguinte):
                    break
                bloco.append(linhas[posicao])
                posicao += 1
            nota = _montar_nota(bloco, len(leitura.linhas) + 1, situacao, retido, leitura)
            leitura.linhas.append(nota)
            grupo.linhas.append(nota)
            da_situacao.linhas.append(nota)
            continue

        posicao += 1
        if texto.startswith(_FIM_NOTAS):
            totais_conferidos += _conferir_total_final(linhas, posicao, leitura)
            break
        if (encontrado := _REGEX_RETIDO.search(texto)):
            retido = encontrado.group(1)
        elif (encontrado := _REGEX_TOTAL_GRUPO.match(texto)):
            _conferir_total(leitura, grupo, int(encontrado.group(1)), texto,
                            f"Imposto Retido: {retido or '?'}")
            totais_conferidos += 1
            grupo = _Grupo()
        elif (encontrado := _REGEX_TOTAL_SITUACAO.match(texto)):
            _conferir_total(leitura, da_situacao, int(encontrado.group(2)), texto,
                            f"notas {encontrado.group(1)}")
            totais_conferidos += 1
            grupo = _Grupo()
        elif texto.startswith(_LINHAS_IGNORADAS):
            pass
        elif _eh_titulo_de_situacao(texto):
            situacao = texto
            da_situacao = _Grupo(situacao)
            grupo = _Grupo()
        else:
            leitura.avisos.append(_aviso(
                leitura, f"Página {linha.pagina}: linha não reconhecida no meio das notas "
                         f"({texto[:80]!r}). Confira essa parte do PDF.",
            ))

    if not dentro_das_notas or not leitura.linhas:
        leitura.erro = (
            f"Nenhuma nota encontrada. Confira se é a {NOME_RELATORIO} baixada do site da "
            "Prefeitura de Cidade Zeta."
        )
        return
    if totais_conferidos == 0:
        leitura.avisos.append(_aviso(
            leitura, "Os totais do PDF não foram encontrados: não foi possível conferir se "
                     "todas as notas foram lidas. Confira a quantidade de notas no PDF.",
        ))

    if ano and mes and 1 <= mes <= 12:
        leitura.competencia = f"{ano}-{mes:02d}"
        leitura.competencia_texto = f"{NOMES_MESES[mes]}/{ano}"
    else:
        leitura.avisos.append(_aviso(leitura, "Competência (Ano/Mês) não encontrada no PDF."))
    if not leitura.inscricao_municipal:
        leitura.avisos.append(_aviso(
            leitura, "Inscrição municipal não encontrada no cabeçalho do PDF."
        ))


def _continua_nota(texto: str) -> bool:
    """Linha que faz parte da nota anterior (tem rótulos e não começa outra nota/total)."""
    return (bool(_REGEX_ROTULOS.search(texto)) and not texto.startswith(ROT_NUMERO)
            and not texto.startswith("Qtde"))


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def _eh_titulo_de_situacao(texto: str) -> bool:
    """Linha curta só com palavras (ex.: "Normal", "Cancelada"): título da situação das notas."""
    return bool(re.fullmatch(r"[A-Za-zÀ-ÿ]+( [A-Za-zÀ-ÿ]+)?", texto)) and len(texto) <= 25


def _eh_cancelada(situacao: str) -> bool:
    return _sem_acento(situacao).casefold().startswith("cancel")


def _valor_abaixo(linha: _Linha, linhas: list[_Linha], posicao: int, titulo: str) -> str:
    """Valor que está logo abaixo de um título de coluna (cabeçalho do tomador)."""
    coluna = next((p for p in linha.palavras if titulo in p["text"]), None)
    if coluna is None or posicao + 1 >= len(linhas):
        return ""
    for palavra in linhas[posicao + 1].palavras:
        if abs(palavra["x0"] - coluna["x0"]) <= TOLERANCIA_COLUNA:
            return palavra["text"].strip()
    return ""


def _conferir_total(leitura: LeituraPrefeitura, grupo: _Grupo, quantidade: int,
                    texto: str, nome: str) -> None:
    """Compara as notas lidas com a quantidade e o Valor Nota impressos no PDF."""
    encontrado = _REGEX_VALOR_NOTA.search(texto)
    valor = valor_prefeitura(encontrado.group(1)) if encontrado else None
    lidas, soma = len(grupo.linhas), grupo.soma()
    if lidas != quantidade or (valor is not None and soma != valor):
        impresso = f"{quantidade} notas" + (f", {_reais(valor)}" if valor is not None else "")
        leitura.avisos.append(_aviso(
            leitura, f"ATENÇÃO: a leitura do PDF não bate com o total impresso ({nome}): "
                     f"o PDF diz {impresso}; o programa leu {lidas} notas, {_reais(soma)}. "
                     "Alguma nota pode não ter sido lida — confira o PDF.",
        ))


def _conferir_total_final(linhas: list[_Linha], posicao: int, leitura: LeituraPrefeitura) -> int:
    """
    Resumo da última página ("TOTAL DECLARADO NO MOVIMENTO"): quantidade e valor.
    Confere contra as notas não canceladas (ou contra todas, se for o caso).
    """
    for linha in linhas[posicao:]:
        if not linha.texto.startswith("TOTAL DECLARADO NO MOVIMENTO"):
            continue
        indice = linhas.index(linha)
        for seguinte in linhas[indice + 1:indice + 4]:
            encontrado = _REGEX_TOTAL_FINAL.match(seguinte.texto)
            if encontrado:
                quantidade = int(encontrado.group(1))
                valor = valor_prefeitura(encontrado.group(2))
                normais = _Grupo(linhas=[l for l in leitura.linhas if not l.cancelada])
                todas = _Grupo(linhas=list(leitura.linhas))
                if any(len(g.linhas) == quantidade and g.soma() == valor for g in (normais, todas)):
                    return 1
                _conferir_total(leitura, normais, quantidade,
                                f"Valor Nota: R$ {encontrado.group(2)}", "total declarado")
                return 1
    return 0


def _reais(valor: Decimal) -> str:
    texto = f"{valor:,.2f}"
    return "R$ " + texto.replace(",", "_").replace(".", ",").replace("_", ".")


# ---------------------------------------------------------------------
# Uma nota
# ---------------------------------------------------------------------
def _campos(bloco: list[_Linha]) -> dict[str, str]:
    """Separa as linhas da nota pelos rótulos: {"Serviço:": "R$ 17.489,10", ...}."""
    campos: dict[str, str] = {}
    for linha in bloco:
        partes = _REGEX_ROTULOS.split(linha.texto)
        for posicao in range(1, len(partes), 2):
            campos.setdefault(partes[posicao], partes[posicao + 1].strip())
    return campos


def _montar_nota(bloco: list[_Linha], numero_linha: int, situacao: str, retido: str,
                 leitura: LeituraPrefeitura) -> LinhaPrefeitura:
    campos = _campos(bloco)

    # "Competência:01/09/2026  A.B.C. SERVICOS MEDICOS LTDA" — o prestador não tem rótulo
    competencia, _, prestador = campos.get(ROT_COMPETENCIA, "").partition("  ")
    prestador = prestador.strip()
    numero_doc = campos.get(ROT_NUMERO, "").strip()
    documento_original = campos.get(ROT_DOCUMENTO, "").strip()
    identificacao = (
        f"Página {bloco[0].pagina}, nota {numero_doc or '(sem número)'} "
        f"({prestador or documento_original or 'sem prestador'})"
    )

    faltando = [r.rstrip(":?") for r in ROTULOS_OBRIGATORIOS if r not in campos]
    if faltando:
        leitura.avisos.append(_aviso(
            leitura, f"{identificacao}: campo(s) não encontrado(s) no PDF: {', '.join(faltando)}.",
        ))

    def reais(rotulo: str) -> Decimal | None:
        texto = campos.get(rotulo, "")
        encontrado = _REGEX_REAIS.search(texto)
        if encontrado:
            return valor_prefeitura(encontrado.group(1))
        if texto:
            leitura.avisos.append(_aviso(
                leitura, f"{identificacao}: {rotulo.rstrip(':')} inválido ({texto!r}); "
                         "tratado como vazio.",
            ))
        return None

    valor_doc = reais(ROT_SERVICO)
    if valor_doc is None and ROT_SERVICO in campos and not campos[ROT_SERVICO]:
        leitura.avisos.append(_aviso(leitura, f"{identificacao}: valor do Serviço vazio."))

    documento = normalizar_documento(documento_original)
    if not documento:
        leitura.avisos.append(_aviso(leitura, f"{identificacao}: sem CPF/CNPJ do prestador."))
    numero = normalizar_numero(numero_doc)
    if not numero:
        leitura.avisos.append(_aviso(leitura, f"{identificacao}: sem número da nota."))
    elif numero == "0":
        leitura.avisos.append(_aviso(
            leitura, f"{identificacao}: a nota está com número 0 no PDF, então não casa pelo "
                     "número com o Tasy. Confira no Tasy uma nota desse prestador com o mesmo valor.",
        ))

    aliquota = _REGEX_PERCENTUAL.search(campos.get(ROT_ALIQUOTA, ""))
    cancelada = _eh_cancelada(situacao)
    if not cancelada and _sem_acento(situacao).casefold() != "normal":
        leitura.avisos.append(_aviso(
            leitura, f"{identificacao}: situação no PDF é {situacao!r} (nem Normal nem "
                     "Cancelada); foi conferida normalmente.",
        ))

    return LinhaPrefeitura(
        linha=numero_linha,
        documento=documento,
        documento_original=documento_original,
        prestador=prestador,
        numero_doc=numero_doc,
        numero=numero,
        valor_doc=valor_doc,
        aliquota=f"{aliquota.group(1)}%" if aliquota else "",
        imp_ret=retido,
        valor_imposto=reais(ROT_ISS),
        valor_deducoes=reais(ROT_DEDUCAO),
        cancelada=cancelada,
        situacao_nf=situacao,
        competencia=competencia.strip(),
        data_emissao=campos.get(ROT_EMISSAO, "").strip(),
        incidencia=campos.get(ROT_INCIDENCIA, "").strip(),
        serie=campos.get(ROT_SERIE, "").strip(),
        especie=campos.get(ROT_ESPECIE, "").strip(),
        optante=campos.get(ROT_OPTANTE, "").strip(),
        exigibilidade=campos.get(ROT_EXIGIBILIDADE, "").strip(),
        regime=campos.get(ROT_REGIME, "").strip(),
        valor_desconto=reais(ROT_DESCONTO),
        valor_cofins=reais(ROT_COFINS),
        valor_csll=reais(ROT_CSLL),
        valor_inss=reais(ROT_INSS),
        valor_irrf=reais(ROT_IRRF),
        valor_pis=reais(ROT_PIS),
    )
