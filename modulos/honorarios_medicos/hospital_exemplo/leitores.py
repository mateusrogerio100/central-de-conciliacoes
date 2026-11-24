"""
Leitores dos relatórios da Conciliação Honorários Hospital Exemplo (ESPECIFICACAO seção 20.1).

O programa reconhece cada arquivo pelo CONTEÚDO, nunca pelo nome (identificar_arquivo):

Balancete (WEXE001, .xls de texto do Tasy) — lido por honorarios.leitores.ler_todas_as_contas.
- Contas de total: as contas sintéticas de último nível com "honor" na descrição. Na Hospital Exemplo,
  2131 – 2.01.03.01 (PF) e 2132 – 2.01.03.02 (PJ); podem vir num arquivo só ou em dois.
- Lado: "PF"/"PJ" na descrição; senão o fim da classificação (.01 = PF, .02 = PJ). A descrição da
  2131 vem cortada no Tasy ("HONORARIOS MEDICOS A "), por isso a classificação.
- Validação: soma das filhas = Saldo Atual da conta de total (senão ATENÇÃO).

HM PF / HM PJ Senior ("Lançamentos Honorários Médicos em Aberto - PF", FPTE135/FPTE136):
- .XLS de verdade, no formato antigo do Excel (BIFF2): lido pelo xlrd.
- Uma pessoa por linha: código · nome · "S. Atual:" valor · "Prev. Pgto:" valor · "S. Posterior:" valor
  (valores lidos pelo RÓTULO, nunca pela posição). A linha com "S. Atual:" e sem nome é o Total Geral.
- Lado: o fim do título ("- PF" / "- PJ"). Mês: o fim da "Competência:" ("01/1999 a 09/2026").
- Validação: soma do S. Atual = Total Geral (senão ATENÇÃO).

SCF – Repasse Sintético em PDF (Relatório 6095 – Deslocamento e Remoção/Transporte):
- Só as páginas que começam com "SCF - Repasse Sintetico" são lidas; as outras (o relatório por
  médico/item e as notas fiscais de débito que vêm no PDF da Remoção) são puladas.
- Linha: terceiro · Nr Repasse · Dt Ref · Status · Vl repasse · Vl. Líquido. Linha só com texto = grupo.
- Validação: "Total - <grupo>(n)" e "Total(n)" batem com o lido (senão ATENÇÃO). O 6095 pode vir
  sem o Total: aí fica só um aviso.

Pagamento particular (Rel. 6203 – "Demonstrativo de Valores a Pagar", PDF; entra na soma como a Remoção,
decisão do usuário em out/2026):
- Cada página é um repasse: "Repasse : 284139 Status : Fechado", "Terceiro : <nome> CNPJ : ..." e as linhas
  "Repasse Item <descrição> <Qtde> <Vl Repasse>". O valor do repasse é a SOMA dos itens (a descrição do
  item não é guardada). Grupo "Pagamento particular".
- Não traz a competência (só a data de impressão): fica um aviso pedindo para conferir o mês.
"""

from __future__ import annotations

import io
import re
import unicodedata
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path

from modulos.honorarios_medicos.fornecedores.avisos import Aviso
from modulos.honorarios_medicos.fornecedores.leitores import (
    ArquivoIlegivel,
    _data,
    _identificador,
    _juntar_espacos,
    dinheiro,
    ler_planilha,
    reais,
)
from modulos.honorarios_medicos.ames.leitores import _nome_do_grupo, conferir_soma_das_filhas, identificar, ler_todas_as_contas
from modulos.honorarios_medicos.ames.modelos import ContaHonorario, Repasse
from modulos.honorarios_medicos.hospital_exemplo.modelos import (
    LADO_PF,
    LADO_PJ,
    LancamentoSenior,
    LeituraBalanceteHospitalExemplo,
    LeituraRepassePdf,
    LeituraSenior,
)

ARQUIVO_BALANCETE = "balancete"
ARQUIVO_SENIOR = "senior"
ARQUIVO_REPASSE_PDF = "repasse_pdf"
ARQUIVO_PDF_OUTRO = "pdf_outro"

ROTULO_SALDO = "s. atual:"
ROTULO_PREVISTO = "prev. pgto:"
ROTULO_POSTERIOR = "s. posterior:"
ROTULO_TOTAL_GERAL = "total geral:"
ROTULO_COMPETENCIA = "competencia:"
TITULO_SENIOR = "lancamentos honorarios medicos em aberto"
TITULO_REPASSE = "scf - repasse sintetico"
TITULO_PAGAMENTO = "demonstrativo de valores a pagar"
GRUPO_PAGAMENTO = "Pagamento particular"

_REGEX_MES_ANO = re.compile(r"^(\d{2})/(\d{4})$")
_REGEX_LINHA_REPASSE = re.compile(
    r"^(?P<terceiro>.+?)\s+(?P<numero>\d+)\s+(?P<data>\d{2}/\d{2}/\d{4})\s+(?P<status>\S+)\s+"
    r"(?P<bruto>-?[\d.]*\d,\d{2})\s+(?P<liquido>-?[\d.]*\d,\d{2})$")
_REGEX_TOTAL_PDF = re.compile(
    r"^Total(?:\s*-\s*(?P<grupo>.*?))?\s*\((?P<quantidade>\d+)\)\s+(?P<bruto>-?[\d.]*\d,\d{2})\s+"
    r"(?P<liquido>-?[\d.]*\d,\d{2})$")
_REGEX_REPASSE_PAGAMENTO = re.compile(r"^Repasse\s*:\s*(?P<numero>\d+)(?:\s+Status\s*:\s*(?P<status>.+))?$")
_REGEX_TERCEIRO_PAGAMENTO = re.compile(r"^Terceiro\s*:\s*(?P<terceiro>.+?)(?:\s+CNPJ\s*:.*)?$")
_REGEX_ITEM_PAGAMENTO = re.compile(r"^Repasse Item\s+.*?\s(?P<qtde>-?[\d.]*\d,\d{2})\s+(?P<valor>-?[\d.]*\d,\d{2})$")
# rodapé "Impresso em:" — no PDF do Tasy cada letra sai dobrada ("IImmpprreessssoo eemm::")
_REGEX_RODAPE_PDF = re.compile(r"^I+m+p+r+e+s+s+o+\s", re.IGNORECASE)


def _sem_acento(texto: object) -> str:
    return unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().casefold().strip()


def _eh_pdf(caminho: Path) -> bool:
    try:
        with open(caminho, "rb") as arquivo:
            return arquivo.read(5) == b"%PDF-"
    except OSError:
        return False


# ---------------------------------------------------------------------
# Reconhecer o arquivo
# ---------------------------------------------------------------------
def _linhas_da_planilha(caminho: Path) -> list[list[object]]:
    """Planilha → linhas de células. Tenta o xlrd primeiro (lê o .XLS antigo do Senior, BIFF2, que o
    ler_planilha não reconhece); se não for Excel de verdade, o ler_planilha (texto do Tasy, .xlsx)."""
    try:
        import xlrd

        livro = xlrd.open_workbook(str(caminho), encoding_override="cp1252", logfile=io.StringIO())
    except Exception:
        return ler_planilha(caminho)
    aba = livro.sheet_by_index(0)
    return [[c.value.strip() if isinstance(c.value, str) else c.value for c in aba.row(i)]
            for i in range(aba.nrows)]


def _eh_senior(linhas) -> bool:
    return any(TITULO_SENIOR in _sem_acento(c) for linha in linhas[:10] for c in linha if isinstance(c, str))


def paginas_do_pdf(caminho: Path) -> list[str]:
    """Texto de cada página (separado para os testes poderem usar texto sintético)."""
    import pdfplumber

    with pdfplumber.open(caminho) as pdf:
        return [pagina.extract_text() or "" for pagina in pdf.pages]


def _primeira_linha(texto: str) -> str:
    return _sem_acento(next((l for l in texto.splitlines() if l.strip()), ""))


def _eh_pagina_de_repasse(texto: str) -> bool:
    return _primeira_linha(texto).startswith(TITULO_REPASSE)


def _eh_pagina_de_pagamento(texto: str) -> bool:
    return _primeira_linha(texto).startswith(TITULO_PAGAMENTO)


def identificar_arquivo(caminho: Path) -> str | None:
    """ARQUIVO_BALANCETE, ARQUIVO_SENIOR, ARQUIVO_REPASSE_PDF, ARQUIVO_PDF_OUTRO ou None (não reconhecido)."""
    caminho = Path(caminho)
    if _eh_pdf(caminho):
        try:
            import pdfplumber

            with pdfplumber.open(caminho) as pdf:
                for pagina in pdf.pages[:3]:
                    texto = pagina.extract_text() or ""
                    if _eh_pagina_de_repasse(texto) or _eh_pagina_de_pagamento(texto):
                        return ARQUIVO_REPASSE_PDF
        except Exception:
            return None
        return ARQUIVO_PDF_OUTRO
    try:
        linhas = _linhas_da_planilha(caminho)
    except (ArquivoIlegivel, OSError):
        return None
    if _eh_senior(linhas):
        return ARQUIVO_SENIOR
    if identificar(linhas) == "balancete":
        return ARQUIVO_BALANCETE
    return None


# ---------------------------------------------------------------------
# Balancete (2131 PF e/ou 2132 PJ)
# ---------------------------------------------------------------------
def _lado_da_conta(conta: ContaHonorario) -> str | None:
    palavras = set(re.findall(r"[a-z]+", _sem_acento(conta.descricao)))
    if "pf" in palavras and "pj" not in palavras:
        return LADO_PF
    if "pj" in palavras and "pf" not in palavras:
        return LADO_PJ
    fim = conta.classificacao.rsplit(".", 1)[-1]
    return {"01": LADO_PF, "02": LADO_PJ}.get(fim)


def ler_balancete_hospital_exemplo(caminho: Path) -> LeituraBalanceteHospitalExemplo:
    caminho = Path(caminho)
    leitura = LeituraBalanceteHospitalExemplo(arquivo=caminho.name)
    todas = ler_todas_as_contas(caminho, leitura)
    if todas is None:
        return leitura

    def filhas(conta: ContaHonorario) -> list[ContaHonorario]:
        return [c for c in todas if c.classificacao.startswith(conta.classificacao + ".")]

    # sintéticas de último nível: têm filhas, e nenhuma filha tem filhas
    sinteticas = [c for c in todas if filhas(c) and not any(filhas(f) for f in filhas(c))]
    sinteticas = [c for c in sinteticas if "honor" in _sem_acento(c.descricao)]
    if not sinteticas:
        leitura.erro = ("O balancete não traz as contas de Honorários médicos a pagar com as contas dos "
                        "médicos/clínicas (na Hospital Exemplo, 2131 – PF e 2132 – PJ). Confira se escolheu o "
                        "balancete certo.")
        return leitura
    for total in sinteticas:
        lado = _lado_da_conta(total)
        if lado is None:
            leitura.avisos.append(Aviso(
                arquivo=leitura.arquivo,
                mensagem=f"ATENÇÃO: não deu para saber se a conta {total.codigo} – {total.descricao} é de PF ou "
                         "de PJ; ela não entrou na conciliação."))
            continue
        if lado in leitura.totais:
            leitura.avisos.append(Aviso(
                arquivo=leitura.arquivo,
                mensagem=f"ATENÇÃO: o balancete tem mais de uma conta de honorários {lado} "
                         f"({leitura.totais[lado].codigo} e {total.codigo}); só a primeira entrou."))
            continue
        leitura.totais[lado] = total
        leitura.contas[lado] = filhas(total)
        conferir_soma_das_filhas(leitura, total, leitura.contas[lado])
    if not leitura.totais:
        leitura.erro = "Nenhuma conta de honorários PF ou PJ foi reconhecida no balancete."
        return leitura

    usadas = {id(c) for lado in leitura.totais for c in [leitura.totais[lado], *leitura.contas[lado]]}
    fora = [c for c in todas if id(c) not in usadas and not filhas(c)]
    if fora:
        leitura.avisos.append(Aviso(
            arquivo=leitura.arquivo,
            mensagem=f"{len(fora)} conta(s) do balancete fora das contas de honorários não entraram na "
                     "conciliação: " + ", ".join(f"{c.codigo} {c.descricao}" for c in fora[:5])
                     + ("..." if len(fora) > 5 else "") + "."))
    if leitura.mes is None:
        leitura.avisos.append(Aviso(arquivo=leitura.arquivo,
                                    mensagem="Mês Referência não encontrado no balancete."))
    return leitura


# ---------------------------------------------------------------------
# HM PF / HM PJ Senior
# ---------------------------------------------------------------------
def _valor_depois(celulas: list[object], rotulo: str) -> Decimal | None:
    """Valor da célula seguinte ao rótulo ("S. Atual:" → 625,40); rótulo sem valor → 0."""
    for posicao, celula in enumerate(celulas):
        if isinstance(celula, str) and _sem_acento(celula) == rotulo:
            for seguinte in celulas[posicao + 1:]:
                if seguinte is None or seguinte == "":
                    continue
                if isinstance(seguinte, str) and seguinte.strip().endswith(":"):
                    return Decimal("0.00")
                return dinheiro(seguinte)
            return Decimal("0.00")
    return None


def ler_senior(caminho: Path) -> LeituraSenior:
    caminho = Path(caminho)
    leitura = LeituraSenior(arquivo=caminho.name)
    try:
        linhas = _linhas_da_planilha(caminho)
    except ArquivoIlegivel as erro:
        leitura.erro = str(erro)
        return leitura
    if not _eh_senior(linhas):
        leitura.erro = ("Este arquivo não parece ser o relatório HM PF/PJ Senior (\"Lançamentos Honorários "
                        "Médicos em Aberto\"). Confira se escolheu o relatório certo.")
        return leitura

    for numero, linha in enumerate(linhas, start=1):
        celulas = [c for c in linha if c is not None and c != ""]
        if not celulas:
            continue
        textos = [_sem_acento(c) for c in celulas if isinstance(c, str)]
        titulo = next((t for t in textos if TITULO_SENIOR in t), None)
        if titulo is not None and not leitura.lado:
            fim = titulo.rsplit("-", 1)[-1].strip()
            leitura.lado = {"pf": LADO_PF, "pj": LADO_PJ}.get(fim, "")
            continue
        if ROTULO_COMPETENCIA in textos and leitura.mes is None:
            for celula in reversed(celulas):
                achado = _REGEX_MES_ANO.match(str(celula).strip())
                if achado:
                    leitura.mes = date(int(achado.group(2)), int(achado.group(1)), 1)
                    break
            continue
        if ROTULO_SALDO not in textos:
            continue

        antes = celulas[:next(i for i, c in enumerate(celulas)
                              if isinstance(c, str) and _sem_acento(c) == ROTULO_SALDO)]
        nomes = [c for c in antes if isinstance(c, str) and _sem_acento(c) != ROTULO_TOTAL_GERAL
                 and re.search(r"[a-z]", _sem_acento(c))]
        try:
            saldo = _valor_depois(celulas, ROTULO_SALDO)
            previsto = _valor_depois(celulas, ROTULO_PREVISTO) or Decimal("0.00")
            posterior = _valor_depois(celulas, ROTULO_POSTERIOR) or Decimal("0.00")
        except ValueError as erro_valor:
            leitura.avisos.append(Aviso(arquivo=leitura.arquivo,
                                        mensagem=f"Linha {numero}: valor não reconhecido ({erro_valor}); "
                                                 "ela não foi lida."))
            continue
        if not nomes:
            leitura.total_impresso = saldo
            continue
        codigo = antes[0] if antes and antes[0] is not nomes[-1] else ""   # 1ª célula, antes do nome
        leitura.lancamentos.append(LancamentoSenior(
            lado=leitura.lado, codigo=_identificador(codigo), nome=_juntar_espacos(nomes[-1]),
            saldo=saldo, previsto=previsto, posterior=posterior))

    if not leitura.lado:
        leitura.erro = ("Não deu para saber se o relatório Senior é de PF ou de PJ (o título não termina em "
                        "\"- PF\" ou \"- PJ\").")
        return leitura
    for lancamento in leitura.lancamentos:
        lancamento.lado = leitura.lado
    if not leitura.lancamentos:
        leitura.erro = "Nenhuma pessoa foi encontrada no relatório Senior."
        return leitura
    if leitura.total_impresso is None:
        leitura.avisos.append(Aviso(arquivo=leitura.arquivo,
                                    mensagem="ATENÇÃO: a linha Total Geral não foi encontrada no relatório "
                                             "Senior; a leitura não pôde ser conferida."))
    elif leitura.total_impresso != leitura.total:
        leitura.avisos.append(Aviso(
            arquivo=leitura.arquivo,
            mensagem=f"ATENÇÃO: a soma do S. Atual lido ({reais(leitura.total)}) não bate com o Total Geral do "
                     f"relatório ({reais(leitura.total_impresso)}). A leitura pode estar incompleta."))
    if leitura.mes is None:
        leitura.avisos.append(Aviso(arquivo=leitura.arquivo,
                                    mensagem="Competência não encontrada no relatório Senior."))
    return leitura


# ---------------------------------------------------------------------
# SCF – Repasse Sintético em PDF
# ---------------------------------------------------------------------
def ler_repasse_pdf(caminho: Path) -> LeituraRepassePdf:
    caminho = Path(caminho)
    leitura = LeituraRepassePdf(arquivo=caminho.name)
    if not _eh_pdf(caminho):
        leitura.erro = ("O Relatório 6095 e o de Remoção/Transporte precisam ser os PDFs do SCF – Repasse "
                        "Sintético.")
        return leitura
    try:
        paginas = paginas_do_pdf(caminho)
    except Exception as erro:
        leitura.erro = f"Não foi possível abrir o PDF: {erro}"
        return leitura
    return ler_repasse_do_texto(paginas, leitura)


def ler_repasse_do_texto(paginas: list[str], leitura: LeituraRepassePdf) -> LeituraRepassePdf:
    totais_grupo: dict[str, tuple[int, Decimal, Decimal]] = {}
    grupo = ""
    lidas = 0
    pagamentos = 0
    for texto in paginas:
        if _eh_pagina_de_pagamento(texto):
            lidas += 1
            pagamentos += _ler_pagamento(texto, leitura)
            continue
        if not _eh_pagina_de_repasse(texto):
            continue
        lidas += 1
        no_topo = True
        for linha in texto.splitlines():
            linha = _juntar_espacos(linha)
            if not linha:
                continue
            chave = _sem_acento(linha)
            if no_topo:
                if chave.startswith("terceiro") and "vl repasse" in chave:
                    no_topo = False
                elif not chave.startswith(TITULO_REPASSE) and not leitura.unidade:
                    leitura.unidade = linha
                continue
            if _REGEX_RODAPE_PDF.match(linha):
                break
            total = _REGEX_TOTAL_PDF.match(linha)
            if total:
                valores = (int(total.group("quantidade")), dinheiro(total.group("bruto")),
                           dinheiro(total.group("liquido")))
                if total.group("grupo") is None:
                    leitura.total_impresso = valores
                else:
                    totais_grupo[_nome_do_grupo(total.group("grupo"))] = valores
                continue
            dados = _REGEX_LINHA_REPASSE.match(linha)
            if dados:
                leitura.repasses.append(Repasse(
                    grupo=grupo or "Sem grupo",
                    terceiro=dados.group("terceiro"),
                    numero=dados.group("numero"),
                    data_referencia=_data(dados.group("data")),
                    status=dados.group("status"),
                    bruto=dinheiro(dados.group("bruto")),
                    liquido=dinheiro(dados.group("liquido")),
                ))
                continue
            if not any(c.isdigit() for c in linha):
                grupo = _nome_do_grupo(linha)
                if grupo not in leitura.grupos:
                    leitura.grupos.append(grupo)
                continue
            leitura.avisos.append(Aviso(arquivo=leitura.arquivo,
                                        mensagem=f"Linha não reconhecida no PDF ({linha}); ela não foi lida."))

    if lidas == 0:
        leitura.erro = ("Este PDF não é o relatório SCF – Repasse Sintético (Relatório 6095 ou Remoção/"
                        "Transporte) nem o Demonstrativo de Valores a Pagar (Rel. 6203). Confira se escolheu o "
                        "arquivo certo.")
        return leitura
    if pagamentos:
        leitura.avisos.append(Aviso(arquivo=leitura.arquivo,
                                    mensagem="O Demonstrativo de Valores a Pagar (Rel. 6203) não traz a competência; "
                                             "confira se ele é do mesmo mês do balancete."))
    if not leitura.repasses:
        leitura.avisos.append(Aviso(arquivo=leitura.arquivo, mensagem="O PDF não tem nenhum repasse."))

    meses = Counter((r.data_referencia.year, r.data_referencia.month) for r in leitura.repasses
                    if r.data_referencia)
    if meses:
        ano, mes = meses.most_common(1)[0][0]
        leitura.mes = date(ano, mes, 1)
        if len(meses) > 1:
            leitura.avisos.append(Aviso(arquivo=leitura.arquivo,
                                        mensagem="ATENÇÃO: o PDF tem repasses de mais de um mês (Dt Ref)."))

    for nome_grupo, (quantidade, bruto, liquido) in totais_grupo.items():
        do_grupo = [r for r in leitura.repasses if r.grupo == nome_grupo]
        lido = (len(do_grupo), sum((r.bruto for r in do_grupo), Decimal(0)),
                sum((r.liquido for r in do_grupo), Decimal(0)))
        if lido != (quantidade, bruto, liquido):
            leitura.avisos.append(Aviso(
                arquivo=leitura.arquivo,
                mensagem=f"ATENÇÃO: o grupo {nome_grupo} tem {lido[0]} repasse(s) lido(s), R$ {reais(lido[1])}, "
                         f"mas o total do PDF diz {quantidade}, R$ {reais(bruto)}. A leitura pode estar "
                         "incompleta."))
    if leitura.total_impresso is None:
        if len(leitura.repasses) > pagamentos:
            leitura.avisos.append(Aviso(arquivo=leitura.arquivo,
                                        mensagem="O PDF não traz a linha Total(n); a leitura não pôde ser "
                                                 "conferida pelo total."))
    else:
        quantidade, bruto, liquido = leitura.total_impresso
        lido = (len(leitura.repasses), leitura.total_bruto,
                sum((r.liquido for r in leitura.repasses), Decimal(0)))
        if lido != (quantidade, bruto, liquido):
            leitura.avisos.append(Aviso(
                arquivo=leitura.arquivo,
                mensagem=f"ATENÇÃO: {lido[0]} repasse(s) lido(s), R$ {reais(lido[1])}, mas o Total do PDF diz "
                         f"{quantidade}, R$ {reais(bruto)}. A leitura pode estar incompleta."))
    return leitura


def _ler_pagamento(texto: str, leitura: LeituraRepassePdf) -> int:
    """Uma página do Demonstrativo de Valores a Pagar → um repasse (soma dos itens). Devolve 1 se leu."""
    numero = status = terceiro = ""
    itens: list[Decimal] = []
    for linha in texto.splitlines():
        linha = _juntar_espacos(linha)
        if _REGEX_RODAPE_PDF.match(linha):
            break
        if not numero and (achado := _REGEX_REPASSE_PAGAMENTO.match(linha)):
            numero, status = achado.group("numero"), (achado.group("status") or "").strip()
        elif not terceiro and (achado := _REGEX_TERCEIRO_PAGAMENTO.match(linha)):
            terceiro = achado.group("terceiro").strip()
        elif achado := _REGEX_ITEM_PAGAMENTO.match(linha):
            itens.append(dinheiro(achado.group("valor")))
        elif not leitura.unidade and _sem_acento(linha).startswith("fundacao"):
            leitura.unidade = re.split(r"\s+CNPJ", linha)[0]
    if not numero or not terceiro or not itens:
        leitura.avisos.append(Aviso(
            arquivo=leitura.arquivo,
            mensagem="ATENÇÃO: uma página do Demonstrativo de Valores a Pagar não pôde ser lida (falta o número "
                     "do repasse, o terceiro ou os itens com o Vl Repasse)."))
        return 0
    valor = sum(itens, Decimal(0))
    existente = next((r for r in leitura.repasses if r.numero == numero and r.grupo == GRUPO_PAGAMENTO), None)
    if existente is not None:        # o mesmo repasse continuando na página seguinte
        existente.bruto += valor
        existente.liquido += valor
        return 0
    if GRUPO_PAGAMENTO not in leitura.grupos:
        leitura.grupos.append(GRUPO_PAGAMENTO)
    leitura.repasses.append(Repasse(grupo=GRUPO_PAGAMENTO, terceiro=terceiro, numero=numero,
                                    data_referencia=None, status=status, bruto=valor, liquido=valor))
    return 1
