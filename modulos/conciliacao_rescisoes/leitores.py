"""
Leitores dos três arquivos da Conciliação de Rescisões a pagar (ESPECIFICACAO seção 17).

Razão (Tasy WEXE002, conta Rescisões a pagar) — .xlsx ou o .xls de texto do Tasy:
- Topo de cada página: unidade (com "Página:"), "Razão", "Período: <início> até: <fim>" e o
  cabeçalho Data · Histórico · Lote · Débitos · Créditos · Saldo. Cada coluna do cabeçalho "é dona"
  das células até a próxima coluna (os valores podem vir uma célula deslocados).
- "Saldo anterior" → saldo do início do mês. Linha com Débitos = um pagamento: o nome vem depois de
  "bordero n. <número>" ou, nos pagamentos judiciais, entre "Verbas rescisórias" e "processo".
  Linha com Créditos = rescisões lançadas no mês ("Líquido Rescisão 0626").
- Linha só com histórico logo depois de um pagamento = pedaço do nome que o Tasy repete na quebra
  de página: ignorada se o nome já termina com ele; senão, é juntada ao nome.
- Validação: saldo anterior + créditos − débitos = último saldo impresso, e as somas = "Total - <conta>".

PDF de eventos da folha (FPRF404, "EVENTOS mm/aaaa C/IDENT" ou "EVENTO mmaaaa C/IDENT nnnn"):
- Blocos por evento ("0264-Liquido Rescisao"); cada linha "matrícula NOME SIT competência pagamento
  referência valor" (a matrícula e a SIT às vezes vêm grudadas no nome).
- Só o bloco 0264 interessa. Validação: quantidade e soma = "Total de Colaboradores: N 0,00 V".

Planilha "Rescisões a pagar" (controle do mês anterior, .xlsx — a de vocês ou a gerada pelo programa):
- Aba "Rescisões a pagar" (ou a primeira com o cabeçalho Colaborador / Valor); colunas Periodo,
  Colaborador, Valor achadas pelo nome. A lista vai do cabeçalho até a primeira linha sem colaborador
  (a linha do total); o que vem depois (composição do saldo, anotações) é ignorado.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook

from modulos.conciliacao_rescisoes.fornecedores.avisos import Aviso
from modulos.conciliacao_rescisoes.fornecedores.leitores import ArquivoIlegivel, dinheiro, ler_planilha, reais
from modulos.conciliacao_rescisoes.planilha_eventos import PlanilhaIlegivel, celulas_xlsx, eh_xlsx, paginas_da_planilha
from modulos.conciliacao_rescisoes.modelos import (
    Credito,
    LeituraControle,
    LeituraEventos,
    LeituraRazao,
    Pagamento,
    Pendente,
    RescisaoMes,
    ROTULO_COMPOSICAO,
    ROTULO_SALDO_RAZAO,
    ROTULO_TOTAL_COMPOSICAO,
    TEXTO_AVISO_COMPOSICAO,
)

COLUNAS_RAZAO = ["Data", "Histórico", "Débitos", "Créditos", "Saldo"]
CODIGO_EVENTO = "0264"
ABA_CONTROLE = "Rescisões a pagar"
COLUNA_COLABORADOR = "Colaborador"
COLUNA_VALOR = "Valor"
COLUNA_PERIODO = "Periodo"

RELATORIO_RAZAO = "razao"
RELATORIO_EVENTOS = "eventos"
RELATORIO_CONTROLE = "controle"
NOMES = {
    RELATORIO_RAZAO: "o Razão da conta Rescisões a pagar (Tasy)",
    RELATORIO_EVENTOS: "o relatório de eventos da folha (item 0264 – Líquido Rescisão), em PDF ou Excel",
    RELATORIO_CONTROLE: "a planilha Rescisões a pagar do mês anterior",
}
CAMPOS = {
    RELATORIO_RAZAO: "Razão",
    RELATORIO_EVENTOS: "Eventos da folha (PDF ou Excel)",
    RELATORIO_CONTROLE: "Rescisões a pagar (mês anterior)",
}

_REGEX_BORDERO = re.compile(r"border[oô]\s*n\.?\s*(\d+)\s*(.*)$", re.IGNORECASE)
_REGEX_JUDICIAL = re.compile(r"verbas\s+rescis[óo]rias\s+(.+?)\s+processo\b", re.IGNORECASE)
_REGEX_CONTA = re.compile(r"^\d+\s*-\s*[\d.]+\s+\S")
_REGEX_DATA = re.compile(r"^(\d{2})/(\d{2})/(\d{4})")
_REGEX_EVENTO = re.compile(r"^(\d{4})-\S")
_REGEX_TOPO_EMPRESA = re.compile(r"^\d{4}\s+-\S")      # "0001 -FUNDAÇÃO HOSPITAL EXEMPLO ... Pág.: 7"
_REGEX_LINHA_EVENTO = re.compile(
    r"^(\d+)\s*(.+?)\s*(\d{3})\s+(\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s+(-?[\d.]+,\d{2})\s+(-?[\d.]+,\d{2})$")
# nome comprido que invade a coluna SIT: o PDF mistura as letras do fim do nome com o "007" ("TE0L07")
_REGEX_LINHA_EVENTO_MISTURADA = re.compile(
    r"^(\d+)\s*(.+?)\s+([A-Z0-9]*[A-Z][A-Z0-9]*)\s+(\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s+(-?[\d.]+,\d{2})\s+"
    r"(-?[\d.]+,\d{2})$")
_REGEX_TOTAL_EVENTO = re.compile(r"^Total de Colaboradores:\s*(\d+)\s+(-?[\d.]+,\d{2})\s+(-?[\d.]+,\d{2})")
_REGEX_PERIODO_PDF = re.compile(r"Per[íi]odo:\s*(\d{2})/(\d{4})")
_REGEX_TIPO_PDF = re.compile(r"Tipo:\s*(.+?)\s*$", re.MULTILINE)   # "Tipo: Complementar Rescisão"
_TOPO_PDF = ("eventos ", "evento ", "período:", "periodo:", "fprf404")
# título do relatório: "EVENTOS 06/2026 C/IDENT" ou, desde out/2026, "EVENTO 102026 C/IDENT 1676"
_REGEX_TITULO_EVENTOS = re.compile(r"\bEVENTOS?\b")


def juntar_espacos(texto: object) -> str:
    return re.sub(r"\s+", " ", str(texto)).strip()


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().casefold()


def _data(valor: object) -> date | None:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        achado = _REGEX_DATA.match(valor.strip())
        if achado:
            dia, mes, ano = (int(p) for p in achado.groups())
            try:
                return date(ano, mes, dia)
            except ValueError:
                return None
    return None


def _preenchidas(linha: list[object]) -> list[object]:
    return [c for c in linha if c is not None and c != ""]


def _erro_relatorio_errado(esperado: str, encontrado: str | None) -> str | None:
    if encontrado == esperado:
        return None
    if encontrado is None:
        return f"Este arquivo não parece ser {NOMES[esperado]}. Confira se escolheu o arquivo certo."
    return (f"Este arquivo é {NOMES[encontrado]}, não {NOMES[esperado]}. "
            f"Escolha-o no campo \"{CAMPOS[encontrado]}\".")


def _eh_eventos_em_excel(caminho: Path) -> bool:
    """O relatório de eventos da folha exportado em Excel (o .xlsx do Tasy que o openpyxl não abre)."""
    if not eh_xlsx(caminho):
        return False
    try:
        linhas = [[valor for valor, _ in celulas] for celulas in celulas_xlsx(caminho)[:15]]
    except PlanilhaIlegivel:
        return False
    return _identificar_planilha(linhas) == RELATORIO_EVENTOS


def _eh_pdf(caminho: Path) -> bool:
    try:
        with open(caminho, "rb") as arquivo:
            return arquivo.read(5) == b"%PDF-"
    except OSError:
        return False


def _identificar_planilha(linhas: list[list[object]]) -> str | None:
    textos = [_sem_acento(str(c)) for linha in linhas[:15] for c in linha if isinstance(c, str)]
    if any("wctb938" in t for t in textos) or (
            "razao" in textos and {"debitos", "creditos"} <= set(textos)):
        return RELATORIO_RAZAO
    if {"evento", "colaborador", "sit"} <= set(textos):        # eventos da folha exportado em Excel
        return RELATORIO_EVENTOS
    if "colaborador" in textos and "valor" in textos:
        return RELATORIO_CONTROLE
    return None


# ---------------------------------------------------------------------
# Razão
# ---------------------------------------------------------------------
class _Cabecalho:
    """Colunas pelo nome; cada uma vai da sua posição até antes da próxima."""

    def __init__(self, linha: list[object]):
        self.posicoes = [(_sem_acento(c.strip()), i) for i, c in enumerate(linha) if isinstance(c, str) and c.strip()]

    @staticmethod
    def eh_cabecalho(linha: list[object]) -> bool:
        nomes = {_sem_acento(c.strip()) for c in linha if isinstance(c, str)}
        return all(_sem_acento(n) in nomes for n in COLUNAS_RAZAO)

    def valor(self, linha: list[object], nome: str) -> object:
        alvo = _sem_acento(nome)
        for indice, (atual, inicio) in enumerate(self.posicoes):
            if atual != alvo:
                continue
            fim = self.posicoes[indice + 1][1] if indice + 1 < len(self.posicoes) else len(linha)
            return next((c for c in linha[inicio:fim] if c is not None and c != ""), None)
        return None


def nome_do_historico(historico: str) -> tuple[str, str]:
    """Histórico do pagamento → (nome da pessoa, borderô). Sem padrão conhecido → (histórico, "")."""
    texto = juntar_espacos(historico)
    judicial = _REGEX_JUDICIAL.search(texto)
    if judicial:
        bordero = _REGEX_BORDERO.search(texto)
        return juntar_espacos(judicial.group(1)), bordero.group(1) if bordero else ""
    bordero = _REGEX_BORDERO.search(texto)
    if bordero and bordero.group(2).strip():
        return juntar_espacos(bordero.group(2)), bordero.group(1)
    return texto, bordero.group(1) if bordero else ""


def ler_razao(caminho: Path) -> LeituraRazao:
    caminho = Path(caminho)
    leitura = LeituraRazao(arquivo=caminho.name)
    if _eh_pdf(caminho) or _eh_eventos_em_excel(caminho):
        leitura.erro = _erro_relatorio_errado(RELATORIO_RAZAO, RELATORIO_EVENTOS)
        return leitura
    try:
        linhas = ler_planilha(caminho)
    except ArquivoIlegivel as erro:
        leitura.erro = str(erro)
        return leitura
    erro = _erro_relatorio_errado(RELATORIO_RAZAO, _identificar_planilha(linhas))
    if erro:
        leitura.erro = erro
        return leitura

    cabecalho: _Cabecalho | None = None
    ultimo: Pagamento | None = None
    ultimo_saldo: Decimal | None = None
    contas: list[str] = []
    totais_impressos: tuple[Decimal, Decimal] | None = None

    for numero, linha in enumerate(linhas, start=1):
        celulas = _preenchidas(linha)
        if not celulas:
            continue
        textos = [juntar_espacos(c) for c in celulas if isinstance(c, str)]
        if any(t.startswith("Página") for t in textos) and not leitura.unidade and textos:
            leitura.unidade = textos[0]
        if "Período:" in textos:
            datas = [_data(c) for c in celulas]
            datas = [d for d in datas if d]
            if datas and leitura.inicio is None:
                leitura.inicio, leitura.fim = datas[0], datas[-1]
            continue
        if _Cabecalho.eh_cabecalho(linha):
            cabecalho = _Cabecalho(linha)
            continue
        if cabecalho is None or any(t.startswith("Impresso em") for t in textos) or textos == ["Razão"]:
            continue
        if any(t.startswith("Página") for t in textos):
            continue
        historico = juntar_espacos(cabecalho.valor(linha, "Histórico") or "")
        data_texto = cabecalho.valor(linha, "Data")
        if len(celulas) == 1 and isinstance(data_texto, str) and _REGEX_CONTA.match(juntar_espacos(data_texto)):
            conta = juntar_espacos(data_texto)
            if conta not in contas:
                contas.append(conta)
            continue
        if (isinstance(data_texto, str) and data_texto.strip().startswith("Total")) or historico.startswith("Total"):
            if historico.startswith("Total -") or (isinstance(data_texto, str) and data_texto.startswith("Total -")):
                try:
                    totais_impressos = (dinheiro(cabecalho.valor(linha, "Débitos")),
                                        dinheiro(cabecalho.valor(linha, "Créditos")))
                except ValueError:
                    pass
            continue
        try:
            debito = cabecalho.valor(linha, "Débitos")
            credito = cabecalho.valor(linha, "Créditos")
            saldo = cabecalho.valor(linha, "Saldo")
            debito = dinheiro(debito) if debito is not None else None
            credito = dinheiro(credito) if credito is not None else None
            saldo = dinheiro(saldo) if saldo is not None else None
        except ValueError as erro_valor:
            leitura.avisos.append(Aviso(arquivo=leitura.arquivo,
                                        mensagem=f"Linha {numero}: valor não reconhecido ({erro_valor}); "
                                                 "a linha não foi lida."))
            continue

        if historico.casefold().startswith("saldo anterior"):
            leitura.saldo_anterior = saldo
            ultimo_saldo = saldo
            continue
        if debito is None and credito is None:
            # pedaço do nome repetido na quebra de página
            if historico and ultimo is not None:
                if not juntar_espacos(ultimo.historico).casefold().endswith(historico.casefold()):
                    ultimo.historico = f"{ultimo.historico} {historico}"
                    ultimo.nome, ultimo.bordero = nome_do_historico(ultimo.historico)
            continue
        if saldo is not None:
            ultimo_saldo = saldo
        if debito:
            nome, bordero = nome_do_historico(historico)
            ultimo = Pagamento(data=_data(data_texto), historico=historico, nome=nome, valor=debito,
                               bordero=bordero, linha=numero)
            leitura.pagamentos.append(ultimo)
            if not bordero and not _REGEX_JUDICIAL.search(historico):
                leitura.avisos.append(Aviso(arquivo=leitura.arquivo,
                                            mensagem=f"Linha {numero}: débito sem o padrão \"bordero n.\" "
                                                     f"(\"{historico}\"); o nome usado foi o histórico inteiro."))
        if credito:
            leitura.creditos.append(Credito(historico, credito, _data(data_texto)))
            ultimo = None

    if cabecalho is None:
        leitura.erro = ("Cabeçalho do razão não encontrado (colunas esperadas: " + ", ".join(COLUNAS_RAZAO) + ").")
        return leitura
    if leitura.saldo_anterior is None:
        leitura.erro = "O razão não traz o \"Saldo anterior\". Confira se escolheu o razão certo."
        return leitura
    leitura.conta = contas[0] if contas else ""
    if len(contas) > 1:
        leitura.avisos.append(Aviso(arquivo=leitura.arquivo,
                                    mensagem="ATENÇÃO: o razão tem mais de uma conta (" + "; ".join(contas)
                                             + "). Todas as linhas foram lidas juntas."))
    if ultimo_saldo is not None and leitura.saldo_final != ultimo_saldo:
        leitura.avisos.append(Aviso(
            arquivo=leitura.arquivo,
            mensagem=f"ATENÇÃO: saldo anterior + créditos − débitos ({reais(leitura.saldo_final)}) não bate com o "
                     f"último saldo do razão ({reais(ultimo_saldo)}). A leitura pode estar incompleta."))
    if totais_impressos is not None and totais_impressos != (leitura.total_pagamentos, leitura.total_creditos):
        leitura.avisos.append(Aviso(
            arquivo=leitura.arquivo,
            mensagem=f"ATENÇÃO: as somas lidas (débitos {reais(leitura.total_pagamentos)}, créditos "
                     f"{reais(leitura.total_creditos)}) não batem com o total impresso (débitos "
                     f"{reais(totais_impressos[0])}, créditos {reais(totais_impressos[1])})."))
    return leitura


# ---------------------------------------------------------------------
# PDF de eventos (item 0264 – Líquido Rescisão)
# ---------------------------------------------------------------------
def _valor_texto(texto: str) -> Decimal:
    return dinheiro(texto)


def paginas_do_pdf(caminho: Path) -> list[str]:
    """Texto de cada página do PDF (separado para os testes poderem usar texto sintético)."""
    import pdfplumber

    with pdfplumber.open(caminho) as pdf:
        return [pagina.extract_text() or "" for pagina in pdf.pages]


def _separar_sit_misturada(linha: str):
    """Linha do 0264 em que o fim do nome invadiu a coluna SIT ("... MODELO TE0L07 07/2026 ...").

    Aceita só se os algarismos do pedaço misturado formam exatamente a SIT de 3 dígitos; as letras voltam
    para o fim do nome. Devolve (match, nome) ou None.
    """
    achado = _REGEX_LINHA_EVENTO_MISTURADA.match(linha)
    if not achado:
        return None
    pedaco = achado.group(3)
    digitos = "".join(c for c in pedaco if c.isdigit())
    letras = "".join(c for c in pedaco if not c.isdigit())
    if len(digitos) != 3 or not letras:
        return None
    return achado, juntar_espacos(f"{achado.group(2)} {letras}")


def ler_eventos(caminho: Path) -> LeituraEventos:
    caminho = Path(caminho)
    leitura = LeituraEventos(arquivo=caminho.name)
    if not _eh_pdf(caminho) and eh_xlsx(caminho):
        return _ler_eventos_em_excel(caminho, leitura)
    if not _eh_pdf(caminho):
        try:
            tipo = _identificar_planilha(ler_planilha(caminho))
        except ArquivoIlegivel:
            tipo = None
        leitura.erro = _erro_relatorio_errado(RELATORIO_EVENTOS, tipo) or \
            "O arquivo de eventos precisa ser o PDF da folha ou o mesmo relatório exportado em Excel (.xlsx)."
        return leitura
    try:
        leitura.assinatura = hashlib.sha256(caminho.read_bytes()).hexdigest()
        paginas = paginas_do_pdf(caminho)
    except Exception as erro:
        leitura.erro = f"Não foi possível abrir o PDF: {erro}"
        return leitura
    return ler_eventos_do_texto(paginas, leitura)


def _ler_eventos_em_excel(caminho: Path, leitura: LeituraEventos) -> LeituraEventos:
    """O mesmo relatório exportado em Excel: as linhas viram o texto do PDF (planilha_eventos)."""
    leitura.formato = "Excel"
    try:
        leitura.assinatura = hashlib.sha256(caminho.read_bytes()).hexdigest()
        paginas, avisos = paginas_da_planilha(caminho)
    except (PlanilhaIlegivel, OSError) as erro:
        leitura.erro = str(erro)
        return leitura
    if not _REGEX_TITULO_EVENTOS.search(" ".join(paginas).upper()[:2000]):
        try:
            tipo = _identificar_planilha(ler_planilha(caminho))
        except ArquivoIlegivel:
            tipo = None
        leitura.erro = _erro_relatorio_errado(RELATORIO_EVENTOS, tipo) or             "O arquivo de eventos precisa ser o PDF da folha ou o mesmo relatório exportado em Excel."
        return leitura
    leitura = ler_eventos_do_texto(paginas, leitura)
    leitura.avisos[:0] = [Aviso(arquivo=leitura.arquivo, mensagem=m) for m in avisos]
    return leitura


def ler_eventos_do_texto(paginas: list[str], leitura: LeituraEventos) -> LeituraEventos:
    texto_inicio = " ".join(paginas[:1])
    if not _REGEX_TITULO_EVENTOS.search(texto_inicio.upper()):
        leitura.erro = _erro_relatorio_errado(RELATORIO_EVENTOS, None)
        return leitura
    periodo = _REGEX_PERIODO_PDF.search(texto_inicio)
    if periodo:
        leitura.competencia = date(int(periodo.group(2)), int(periodo.group(1)), 1)
    tipo = _REGEX_TIPO_PDF.search(texto_inicio)   # fim da linha do Período
    if tipo:
        leitura.tipo = juntar_espacos(tipo.group(1))

    evento_atual = ""
    achou_bloco = False
    for numero_pagina, texto in enumerate(paginas, start=1):
        for linha in texto.splitlines():
            linha = linha.strip()
            if not linha:
                continue
            total = _REGEX_TOTAL_EVENTO.match(linha)
            if total:
                if evento_atual == CODIGO_EVENTO:
                    leitura.quantidade_impressa = int(total.group(1))
                    leitura.total_impresso = _valor_texto(total.group(3))
                evento_atual = ""
                continue
            minusculo = linha.casefold()
            if (_REGEX_TOPO_EMPRESA.match(linha) or any(minusculo.startswith(t) for t in _TOPO_PDF)
                    or linha.isdigit()):
                continue                 # topo / rodapé de página (o bloco continua na página seguinte)
            evento = _REGEX_EVENTO.match(linha)
            if evento and not _REGEX_LINHA_EVENTO.match(linha):
                evento_atual = evento.group(1)
                achou_bloco = achou_bloco or evento_atual == CODIGO_EVENTO
                continue
            if evento_atual != CODIGO_EVENTO:
                continue
            pessoa = _REGEX_LINHA_EVENTO.match(linha)
            nome = juntar_espacos(pessoa.group(2)) if pessoa else ""
            if not pessoa:
                pessoa = _separar_sit_misturada(linha)
                nome = pessoa[1] if pessoa else ""
                pessoa = pessoa[0] if pessoa else None
            if pessoa:
                leitura.rescisoes.append(RescisaoMes(matricula=pessoa.group(1),
                                                     nome=nome,
                                                     valor=_valor_texto(pessoa.group(7)),
                                                     data_pagamento=_data(pessoa.group(5)),
                                                     tipo=leitura.tipo, arquivo=leitura.arquivo))
                continue
            leitura.avisos.append(Aviso(arquivo=leitura.arquivo,
                                        mensagem=f"Página {numero_pagina}: linha do 0264 não reconhecida "
                                                 f"(\"{linha}\")."))

    if not achou_bloco:
        leitura.erro = "O PDF não tem o item 0264 – Líquido Rescisão."
        return leitura
    if leitura.total_impresso is None:
        leitura.avisos.append(Aviso(arquivo=leitura.arquivo,
                                    mensagem="\"Total de Colaboradores\" do 0264 não encontrado: não deu para "
                                             "conferir se todas as pessoas foram lidas."))
    elif (leitura.quantidade_impressa, leitura.total_impresso) != (len(leitura.rescisoes), leitura.total):
        leitura.avisos.append(Aviso(
            arquivo=leitura.arquivo,
            mensagem=f"ATENÇÃO: foram lidas {len(leitura.rescisoes)} pessoas (R$ {reais(leitura.total)}) no 0264, "
                     f"mas o PDF diz {leitura.quantidade_impressa} (R$ {reais(leitura.total_impresso)}). "
                     "A leitura pode estar incompleta."))
    if leitura.competencia is None:
        leitura.avisos.append(Aviso(arquivo=leitura.arquivo, mensagem="Período do PDF não encontrado."))
    return leitura


# ---------------------------------------------------------------------
# Planilha "Rescisões a pagar" (mês anterior)
# ---------------------------------------------------------------------
def _abas_da_planilha(caminho: Path) -> list[tuple[str, list[list[object]]]]:
    """[(nome da aba, linhas)]: todas as abas de um .xlsx; um .xls de texto vira uma aba só."""
    with open(caminho, "rb") as arquivo:
        inicio = arquivo.read(2)
    if inicio != b"PK":
        return [(caminho.stem, ler_planilha(caminho))]
    try:
        livro = load_workbook(caminho, data_only=True)
    except Exception as erro:
        raise ArquivoIlegivel(f"Não foi possível abrir a planilha: {erro}") from erro
    abas = [(aba.title, [list(l) for l in aba.iter_rows(values_only=True)]) for aba in livro.worksheets]
    livro.close()
    return abas


def _posicoes_controle(linha: list[object]) -> dict[str, int] | None:
    nomes = {_sem_acento(c.strip()): i for i, c in enumerate(linha) if isinstance(c, str) and c.strip()}
    if _sem_acento(COLUNA_COLABORADOR) in nomes and _sem_acento(COLUNA_VALOR) in nomes:
        return nomes
    return None


def ler_controle(caminho: Path) -> LeituraControle:
    caminho = Path(caminho)
    leitura = LeituraControle(arquivo=caminho.name)
    if _eh_pdf(caminho) or _eh_eventos_em_excel(caminho):
        leitura.erro = _erro_relatorio_errado(RELATORIO_CONTROLE, RELATORIO_EVENTOS)
        return leitura
    try:
        abas = _abas_da_planilha(caminho)
    except (ArquivoIlegivel, OSError) as erro:
        leitura.erro = str(erro)
        return leitura

    def com_cabecalho(linhas):
        for indice, linha in enumerate(linhas[:20]):
            posicoes = _posicoes_controle(linha)
            if posicoes:
                return indice, posicoes
        return None

    escolhida = next(((nome, linhas) for nome, linhas in abas
                      if _sem_acento(nome.strip()) == _sem_acento(ABA_CONTROLE) and com_cabecalho(linhas)), None)
    escolhida = escolhida or next(((nome, linhas) for nome, linhas in abas if com_cabecalho(linhas)), None)
    if escolhida is None:
        tipo = next((_identificar_planilha(linhas) for _, linhas in abas if _identificar_planilha(linhas)), None)
        leitura.erro = _erro_relatorio_errado(RELATORIO_CONTROLE, tipo) or \
            "Não achei a lista com as colunas Colaborador e Valor."
        return leitura
    leitura.aba, linhas = escolhida
    inicio, posicoes = com_cabecalho(linhas)
    i_nome, i_valor = posicoes[_sem_acento(COLUNA_COLABORADOR)], posicoes[_sem_acento(COLUNA_VALOR)]
    i_periodo = posicoes.get(_sem_acento(COLUNA_PERIODO))

    fim_da_lista = len(linhas)
    for numero, linha in enumerate(linhas[inicio + 1:], start=inicio + 2):
        nome = linha[i_nome] if i_nome < len(linha) else None
        if not isinstance(nome, str) or not nome.strip():
            fim_da_lista = numero        # linha do total: fim da lista
            break
        valor = linha[i_valor] if i_valor < len(linha) else None
        try:
            valor = dinheiro(valor)
        except ValueError:
            leitura.avisos.append(Aviso(arquivo=leitura.arquivo,
                                        mensagem=f"Linha {numero}: \"{juntar_espacos(nome)}\" sem valor reconhecido "
                                                 f"({valor!r}); não foi lida."))
            continue
        periodo = linha[i_periodo] if i_periodo is not None and i_periodo < len(linha) else None
        leitura.pendentes.append(Pendente(periodo=periodo, nome=juntar_espacos(nome), valor=valor, linha=numero))

    if not leitura.pendentes:
        leitura.avisos.append(Aviso(arquivo=leitura.arquivo,
                                    mensagem="A lista de rescisões a pagar do mês anterior está vazia."))
    try:
        leitura.rodape = _rodape_do_controle(linhas[fim_da_lista:], i_nome, i_valor)
    except Exception:                    # rodapé em outro formato: só deixa de servir para as observações
        leitura.rodape = []
    leitura.rodape, leitura.composicao = _separar_composicao(leitura.rodape)
    return leitura


def _separar_composicao(rodape: list[tuple[str, Decimal | None]]):
    """Tira do rodapé a composição gravada pelo programa (ROTULO_COMPOSICAO ... ROTULO_TOTAL_COMPOSICAO).

    Devolve (rodapé para as observações, itens da composição). Os itens com nome continuam no rodapé (servem
    para a regra c); o título, o total, o saldo e as linhas sem valor saem.
    """
    titulo = _sem_acento(ROTULO_COMPOSICAO)
    inicio = next((i for i, (texto, _) in enumerate(rodape) if _sem_acento(texto) == titulo), None)
    if inicio is None:
        return rodape, []
    fins = (_sem_acento(ROTULO_TOTAL_COMPOSICAO), _sem_acento(ROTULO_SALDO_RAZAO), _sem_acento(TEXTO_AVISO_COMPOSICAO))
    fim = next((i for i in range(inicio + 1, len(rodape)) if _sem_acento(rodape[i][0]).startswith(fins)),
               len(rodape))
    itens = [(texto, valor) for texto, valor in rodape[inicio + 1:fim] if valor is not None]
    depois = [linha for linha in rodape[fim:] if not _sem_acento(linha[0]).startswith(fins)]
    return rodape[:inicio] + itens + depois, itens


def _rodape_do_controle(linhas: list[list[object]], i_nome: int, i_valor: int) -> list[tuple[str, Decimal | None]]:
    """Linhas de texto abaixo do total (composição da diferença, títulos a lançar...): (texto, valor).

    NÃO entram na lista nem no casamento: servem só para explicar pagamentos não encontrados.
    """
    rodape = []
    for linha in linhas:
        texto = linha[i_nome] if i_nome < len(linha) else None
        if not isinstance(texto, str) or not texto.strip():
            continue
        valor = linha[i_valor] if i_valor < len(linha) else None
        try:
            valor = dinheiro(valor) if valor is not None and valor != "" else None
        except ValueError:
            valor = None
        rodape.append((juntar_espacos(texto), valor))
    return rodape
