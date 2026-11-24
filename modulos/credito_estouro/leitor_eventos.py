"""Leitura do PDF de eventos da folha (FPRF404) — ESPECIFICACAO_CREDITO_ESTOURO.md, seções 2.1 e 3.1.

COPIADA de modulos\\conciliacao_rescisoes\\leitores.py (ler_eventos_do_texto, versão 1.9.10, que aceita o título
"EVENTOS" e "EVENTO") e ampliada: em vez de só o bloco 0264, guarda os blocos 0241, 0256, 0258, 1204 e 0775,
cada um conferido com o seu "Total de Colaboradores".

- Topo de cada página: "0001 -FUNDAÇÃO … Pág.: N", "EVENTOS mm/aaaa C/IDENT" (ou "EVENTO mmaaaa C/IDENT nnnn"),
  "Período: 05/2026 a 05/2026 Tipo: Cálculo Mensal" e "Evento Colaborador SIT …". Rodapé "FPRF404…" e o número
  da página. Nenhum deles encerra o bloco: um bloco pode atravessar páginas.
- Bloco: "0256-Cred. Estouro do Mes"; linhas "matrícula NOME SIT competência pagamento referência valor" (a
  matrícula às vezes grudada no nome); fim: "Total de Colaboradores: N 0,00 V".
"""

from __future__ import annotations

import hashlib
import re
from datetime import date
from pathlib import Path

from modulos.credito_estouro.modelos import (
    EVENTO_DEVOLUCAO,
    EVENTOS_USADOS,
    NOMES_EVENTOS,
    Aviso,
    LeituraEventos,
    LinhaEvento,
    TotalImpresso,
)
from modulos.credito_estouro.util import data_br, dinheiro, eh_pdf, juntar_espacos, paginas_do_pdf, reais

ERRO_NAO_EH_EVENTOS = ("Este arquivo não parece ser o PDF de eventos da folha (EVENTOS … C/IDENT, com os eventos "
                       "0256, 0258, 0241 e 1204). Confira se escolheu o arquivo certo.")

_REGEX_TITULO_EVENTOS = re.compile(r"\bEVENTOS?\b")
_REGEX_EVENTO = re.compile(r"^(\d{4})-\S")
_REGEX_TOPO_EMPRESA = re.compile(r"^\d{4}\s*-\s*(\S.*?)\s+P[áa]g\.?:")    # "0001 -FUNDAÇÃO … Pág.: 7"
_REGEX_LINHA_EVENTO = re.compile(
    r"^(\d+)\s*(.+?)\s*(\d{3})\s+(\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s+(-?[\d.]+,\d{2})\s+(-?[\d.]+,\d{2})$")
# nome comprido que invade a coluna SIT: o PDF mistura as letras do fim do nome com o "007" ("TE0L07")
_REGEX_LINHA_EVENTO_MISTURADA = re.compile(
    r"^(\d+)\s*(.+?)\s+([A-Z0-9]*[A-Z][A-Z0-9]*)\s+(\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s+(-?[\d.]+,\d{2})\s+"
    r"(-?[\d.]+,\d{2})$")
_REGEX_TOTAL_EVENTO = re.compile(r"^Total de Colaboradores:\s*(\d+)\s+(-?[\d.]+,\d{2})\s+(-?[\d.]+,\d{2})")
_REGEX_PERIODO_PDF = re.compile(r"Per[íi]odo:\s*(\d{2})/(\d{4})")
_REGEX_TIPO_PDF = re.compile(r"Tipo:\s*(.+?)\s*$", re.MULTILINE)
_TOPO_PDF = ("eventos ", "evento ", "período:", "periodo:", "fprf404")


def _separar_sit_misturada(linha: str):
    """Linha em que o fim do nome invadiu a coluna SIT ("... MODELO TE0L07 07/2026 ...").

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
    try:
        bruto = caminho.read_bytes()
    except OSError as erro:
        leitura.erro = f"Não foi possível abrir o arquivo: {erro.strerror or erro}."
        return leitura
    if not eh_pdf(bruto):
        leitura.erro = ERRO_NAO_EH_EVENTOS
        return leitura
    leitura.assinatura = hashlib.sha256(bruto).hexdigest()
    try:
        paginas = paginas_do_pdf(caminho)
    except Exception as erro:
        leitura.erro = f"Não foi possível abrir o PDF: {erro}"
        return leitura
    return ler_eventos_do_texto(paginas, leitura)


def ler_eventos_do_texto(paginas: list[str], leitura: LeituraEventos) -> LeituraEventos:
    texto_inicio = " ".join(paginas[:1])
    if not _REGEX_TITULO_EVENTOS.search(texto_inicio.upper()):
        leitura.erro = ERRO_NAO_EH_EVENTOS
        return leitura
    periodo = _REGEX_PERIODO_PDF.search(texto_inicio)
    if periodo:
        leitura.competencia = date(int(periodo.group(2)), int(periodo.group(1)), 1)
    tipo = _REGEX_TIPO_PDF.search(texto_inicio)
    if tipo:
        leitura.tipo = juntar_espacos(tipo.group(1))
    for linha in texto_inicio.splitlines():
        topo = _REGEX_TOPO_EMPRESA.match(linha.strip())
        if topo:
            leitura.unidade = juntar_espacos(topo.group(1))
            break

    evento_atual = ""
    blocos_achados: set[str] = set()
    for numero_pagina, texto in enumerate(paginas, start=1):
        for linha in texto.splitlines():
            linha = linha.strip()
            if not linha:
                continue
            total = _REGEX_TOTAL_EVENTO.match(linha)
            if total:
                if evento_atual in EVENTOS_USADOS:
                    leitura.totais_impressos[evento_atual] = TotalImpresso(int(total.group(1)),
                                                                           dinheiro(total.group(3)))
                evento_atual = ""
                continue
            minusculo = linha.casefold()
            if (_REGEX_TOPO_EMPRESA.match(linha) or any(minusculo.startswith(t) for t in _TOPO_PDF)
                    or linha.isdigit()):
                continue                 # topo / rodapé de página (o bloco continua na página seguinte)
            evento = _REGEX_EVENTO.match(linha)
            if evento and not _REGEX_LINHA_EVENTO.match(linha):
                evento_atual = evento.group(1)
                if evento_atual in EVENTOS_USADOS:
                    blocos_achados.add(evento_atual)
                continue
            if evento_atual not in EVENTOS_USADOS:
                continue
            pessoa = _REGEX_LINHA_EVENTO.match(linha)
            nome = juntar_espacos(pessoa.group(2)) if pessoa else ""
            if not pessoa:
                misturada = _separar_sit_misturada(linha)
                if misturada:
                    pessoa, nome = misturada
            if pessoa:
                leitura.linhas.append(LinhaEvento(evento=evento_atual, matricula=pessoa.group(1), nome=nome,
                                                  valor=dinheiro(pessoa.group(7)),
                                                  data_pagamento=data_br(pessoa.group(5)),
                                                  pagina=numero_pagina))
                continue
            leitura.avisos.append(Aviso(leitura.arquivo,
                                        f"Página {numero_pagina}: linha do {evento_atual} não reconhecida "
                                        f"(\"{linha}\")."))

    if not blocos_achados:
        leitura.erro = ("O PDF de eventos não tem nenhum dos eventos do crédito estouro (0241, 0256, 0258, 1204 "
                        "ou 0775). Confira se escolheu o relatório certo.")
        return leitura
    for evento in EVENTOS_USADOS:
        if evento not in blocos_achados:
            continue
        impresso = leitura.totais_impressos.get(evento)
        lido = (leitura.quantidade(evento), leitura.total(evento))
        if impresso is None:
            leitura.avisos.append(Aviso(leitura.arquivo,
                                        f"\"Total de Colaboradores\" do {evento} ({NOMES_EVENTOS[evento]}) não "
                                        "encontrado: não deu para conferir se todas as pessoas foram lidas."))
        elif (impresso.quantidade, impresso.valor) != lido:
            leitura.avisos.append(Aviso(
                leitura.arquivo,
                f"ATENÇÃO: foram lidas {lido[0]} pessoas (R$ {reais(lido[1])}) no {evento} "
                f"({NOMES_EVENTOS[evento]}), mas o PDF diz {impresso.quantidade} (R$ {reais(impresso.valor)}). "
                "A leitura pode estar incompleta."))
    if leitura.competencia is None:
        leitura.avisos.append(Aviso(leitura.arquivo, "Período do PDF não encontrado."))
    return leitura


def ler_varios(caminhos) -> LeituraEventos:
    """Um ou mais PDFs (o relatório de eventos e, separado, o do 0775 ou de uma folha complementar) lidos como um só.
    PDF repetido (mesmo conteúdo) é ignorado, com aviso. O mês é o do relatório de eventos; relatórios de meses
    diferentes = erro. O PDF que só tem o 0775 pode ser de um mês anterior (decisão de 16/11/2026: o 0775 entra no
    mês em que a devolução foi lançada no razão), nunca de um mês depois."""
    caminhos = [Path(c) for c in ([caminhos] if isinstance(caminhos, (str, Path)) else caminhos)]
    leituras: list[LeituraEventos] = []
    avisos: list[Aviso] = []
    for caminho in caminhos:
        leitura = ler_eventos(caminho)
        if leitura.erro:
            junta = LeituraEventos(arquivo=leitura.arquivo)
            junta.erro = leitura.erro if len(caminhos) == 1 else f"{leitura.arquivo}: {leitura.erro}"
            return junta
        if any(leitura.assinatura == outra.assinatura for outra in leituras):
            avisos.append(Aviso(leitura.arquivo, "PDF repetido (o mesmo conteúdo de outro escolhido): ignorado."))
            continue
        leituras.append(leitura)
    if len(leituras) == 1:
        leituras[0].avisos += avisos
        return leituras[0]
    so_0775 = [l for l in leituras if l.linhas and all(linha.evento == EVENTO_DEVOLUCAO for linha in l.linhas)]
    principais = [l for l in leituras if l not in so_0775] or leituras
    junta = LeituraEventos(arquivo=" + ".join(l.arquivo for l in leituras), unidade=principais[0].unidade,
                           competencia=principais[0].competencia)
    meses = {l.competencia for l in principais}
    if len(meses) > 1:
        junta.erro = ("Os PDFs de eventos são de meses diferentes (" + "; ".join(
            f"{l.arquivo}: {l.competencia:%m/%Y}" if l.competencia else f"{l.arquivo}: sem mês" for l in principais)
            + "). Escolha só os PDFs do mês da conciliação.")
        return junta
    mes = junta.competencia
    for leitura in so_0775:
        if leitura in principais or leitura.competencia is None or mes is None or leitura.competencia == mes:
            continue
        if leitura.competencia > mes:
            junta.erro = (f"O PDF do 0775 \"{leitura.arquivo}\" é de {leitura.competencia:%m/%Y}, depois do mês do "
                          f"relatório de eventos ({mes:%m/%Y}). Escolha esse PDF na conciliação do mês em que a "
                          "devolução foi lançada no razão.")
            return junta
        avisos.append(Aviso(leitura.arquivo,
                            f"PDF do 0775 de {leitura.competencia:%m/%Y}: ele entra nesta conciliação de {mes:%m/%Y}, "
                            "mês em que a devolução foi lançada no razão. Não escolha esse PDF de novo em outro mês."))
    junta.tipo = " + ".join(dict.fromkeys(l.tipo for l in leituras if l.tipo))
    for leitura in leituras:
        junta.linhas += leitura.linhas
        junta.avisos += leitura.avisos
        for evento, total in leitura.totais_impressos.items():
            anterior = junta.totais_impressos.get(evento)
            junta.totais_impressos[evento] = TotalImpresso(
                total.quantidade + (anterior.quantidade if anterior else 0),
                total.valor + (anterior.valor if anterior else 0))
    junta.avisos += avisos
    junta.assinatura = "+".join(l.assinatura for l in leituras)
    return junta
