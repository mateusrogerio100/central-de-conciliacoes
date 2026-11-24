"""
Orquestração da Conciliação de Rescisões a pagar: lê os três arquivos, casa, gera o Excel.
Opcional: o relatório de títulos a pagar do financeiro, comparado com a lista nova (rescisoes.financeiro).

processar_rescisoes() é a ÚNICA porta de entrada para a interface e nunca levanta exceção:
- arquivo ilegível ou trocado → ResultadoRescisoes.erro (com vários PDFs, um PDF com problema vira aviso
  e os outros continuam; erro só se nenhum PDF puder ser lido);
- vários PDFs de eventos (mensal + complementares): PDFs repetidos (mesmo conteúdo) são ignorados e
  escolher_pdfs() decide quais entram no mês pela soma do 0264 × créditos do razão;
- mês do razão ≠ mês do PDF, ou saldo anterior ≠ total da lista anterior → aviso (deixa continuar);
- não conseguiu salvar → ResultadoRescisoes.erro com mensagem clara;
- relatório do financeiro ilegível → aviso de erro só dele (a conciliação sai sem a comparação).

Planilha: Conciliacao_Rescisoes_<Unidade>_<mmmaaaa>.xlsx (ex.: ..._HospitalExemplo_jun2026.xlsx), na pasta
escolhida (pasta_destino) ou na pasta do razão; nome repetido ganha _2, _3...
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from itertools import combinations
from typing import Callable, Sequence

from modulos.conciliacao_rescisoes.fornecedores.avisos import NIVEL_ERRO, NIVEL_OK, Aviso
from modulos.conciliacao_rescisoes.fornecedores.leitores import ler_titulos, nome_curto_unidade, reais
from modulos.conciliacao_rescisoes.fornecedores.relatorio_excel import mes_curto
from modulos.conciliacao_rescisoes.conciliador import conciliar, palavras_do_nome
from modulos.conciliacao_rescisoes.financeiro import (
    SITUACAO_DIVERGENTE,
    SITUACAO_SO_FINANCEIRO,
    SITUACAO_SO_LISTA,
    comparar_com_financeiro,
)
from modulos.conciliacao_rescisoes.leitores import ler_controle, ler_eventos, ler_razao
from modulos.conciliacao_rescisoes.modelos import (
    ESCOLHA_COMBINACAO,
    ESCOLHA_LANCAMENTOS,
    ESCOLHA_NENHUMA,
    ESCOLHA_UNICO,
    ESCOLHA_VARIAS,
    ORIGEM_NAO_ENCONTRADO,
    ORIGEM_PDF,
    ORIGEM_PENDENTE,
    REGRA_SEM_RESCISAO,
    TIPO_CONTROLE,
    TIPO_EVENTOS,
    TIPO_FINANCEIRO,
    TIPO_RAZAO,
    Credito,
    LeituraControle,
    LeituraEventos,
    LeituraRazao,
    ResultadoRescisoes,
)
from modulos.conciliacao_rescisoes.relatorio_excel import (
    ABA_DIFERENTES,
    ABA_FINANCEIRO,
    ABA_NAO_ENCONTRADOS,
    gerar_relatorio_rescisoes,
)

PREFIXO_ARQUIVO = "Conciliacao_Rescisoes"
ARQUIVO_CONCILIACAO = "Conciliação"
TOLERANCIA_PDFS = Decimal("0.01")        # soma dos PDFs × créditos do razão
MAXIMO_PDFS_COMBINADOS = 12              # 2^12 = 4.096 combinações (na prática são 2 ou 3 PDFs)

FuncaoProgresso = Callable[[int, str], None]


def processar_rescisoes(arquivo_razao: Path, arquivo_eventos: Path | Sequence[Path], arquivo_controle: Path,
                        ao_progredir: FuncaoProgresso | None = None,
                        agora: datetime | None = None,
                        pasta_destino: Path | None = None,
                        arquivo_financeiro: Path | None = None) -> ResultadoRescisoes:
    """Faz a conciliação completa (nunca levanta exceção). pasta_destino None = pasta do razão.

    arquivo_eventos: um PDF ou uma lista de PDFs (o mensal e os complementares).
    arquivo_financeiro (opcional): relatório de títulos a pagar do financeiro, comparado com a lista nova.
    """
    resultado = ResultadoRescisoes()
    try:
        _processar(resultado, Path(arquivo_razao), _lista_de_caminhos(arquivo_eventos), Path(arquivo_controle),
                   ao_progredir, Path(pasta_destino) if pasta_destino else None,
                   Path(arquivo_financeiro) if arquivo_financeiro else None)
    except Exception as erro:  # rede de segurança: a interface nunca recebe exceção
        resultado.erro = f"Erro inesperado durante a conciliação: {erro}"
    return resultado


def _lista_de_caminhos(arquivos: Path | str | Sequence[Path]) -> list[Path]:
    if isinstance(arquivos, (str, Path)):
        return [Path(arquivos)]
    return [Path(a) for a in arquivos]


def _mes(dia: date | None) -> tuple[int, int] | None:
    return None if dia is None else (dia.year, dia.month)


def ler_varios_eventos(arquivos: Sequence[Path]) -> tuple[list[LeituraEventos], list[str]]:
    """Lê cada PDF (ou Excel); devolve (leituras, nomes dos repetidos ignorados — mesmo conteúdo de outro já lido).

    Repetido: o mesmo arquivo (assinatura) ou o mesmo relatório em outro formato (PDF e Excel com o mesmo tipo,
    competência e as mesmas pessoas, valores e datas de pagamento).
    """
    leituras, repetidos, vistas = [], [], {}
    for arquivo in arquivos:
        leitura = ler_eventos(arquivo)
        chaves = [leitura.assinatura] if leitura.assinatura else []
        if not leitura.erro and leitura.rescisoes:
            chaves.append((leitura.tipo, leitura.competencia, tuple(
                (r.matricula, r.valor, r.data_pagamento) for r in leitura.rescisoes)))
        igual = next((vistas[c] for c in chaves if c in vistas), None)
        if igual is not None:
            repetidos.append(f"{leitura.arquivo} (igual a {igual})")
            continue
        for chave in chaves:
            vistas[chave] = leitura.arquivo
        leituras.append(leitura)
    return leituras, repetidos


def _ordem_dos_pdfs(leitura: LeituraEventos):
    """Mensal primeiro, depois os complementares pela data de pagamento (o casamento segue essa ordem)."""
    return (leitura.complementar, leitura.data_pagamento or date.max, leitura.arquivo)


@dataclass
class EscolhaPdfs:
    usados: list[LeituraEventos]
    fora: list[LeituraEventos]           # não lançados no razão deste mês (provavelmente do mês seguinte)
    situacao: str                        # ESCOLHA_...

    @property
    def total(self) -> Decimal:
        return sum((leitura.total for leitura in self.usados), Decimal(0))


def parear_creditos(creditos: Sequence[Credito], leituras: Sequence[LeituraEventos]
                    ) -> tuple[list[tuple[Credito, list[LeituraEventos]]], list[Credito], list[LeituraEventos]]:
    """Cada lançamento de crédito do razão com o PDF (ou os PDFs juntos) de soma igual (± R$ 0,01).

    Devolve (pares, créditos sem PDF, PDFs sem crédito). Ex.: jul/2026 — "Líquido Rescisão 0726" 324.681,64 ↔
    PDF mensal e 1.284,28 ↔ complementar 1650; sobram o crédito "Reembolso de férias..." (sem PDF) e os
    complementares pagos em agosto (sem crédito). Um crédito pode valer por vários PDFs (mensal + complementar
    lançados juntos); fica a menor combinação, e cada PDF vale por um crédito só.
    """
    livres = sorted(leituras, key=_ordem_dos_pdfs)
    pares, sem_pdf = [], []
    for credito in creditos:
        grupo = None
        if len(livres) <= MAXIMO_PDFS_COMBINADOS:
            grupo = next((list(g) for tamanho in range(1, len(livres) + 1) for g in combinations(livres, tamanho)
                          if abs(sum((l.total for l in g), Decimal(0)) - credito.valor) <= TOLERANCIA_PDFS), None)
        if grupo is None:
            sem_pdf.append(credito)
        else:
            livres = [l for l in livres if l not in grupo]
            pares.append((credito, grupo))
    return pares, sem_pdf, livres


def escolher_pdfs(leituras: list[LeituraEventos], creditos: Decimal | None,
                  lancamentos: Sequence[Credito] = ()) -> EscolhaPdfs:
    """Quais PDFs entram no mês: a combinação cuja soma do 0264 é igual (± R$ 0,01) aos créditos do razão.

    Uma combinação só → usa esses PDFs (os outros ficam de fora: são do mês seguinte).
    Nenhuma → tenta cada PDF com um lançamento de crédito do razão (parear_creditos): se algum PDF tem crédito
    igual, entram os que têm e os outros ficam de fora (o razão pode ter um crédito que não é de PDF, como um
    reembolso, e aí nenhuma soma bate). Se nenhum PDF tem crédito igual, ou mais de uma combinação bate → usa
    todos (e o Resumo mostra a diferença, com um aviso).
    Um PDF só → usado como sempre (a diferença créditos − 0264 continua no Resumo).
    """
    leituras = sorted(leituras, key=_ordem_dos_pdfs)
    if len(leituras) <= 1:
        return EscolhaPdfs(leituras, [], ESCOLHA_UNICO)
    if creditos is None or len(leituras) > MAXIMO_PDFS_COMBINADOS:
        return EscolhaPdfs(leituras, [], ESCOLHA_NENHUMA)
    batem = [grupo for tamanho in range(1, len(leituras) + 1) for grupo in combinations(leituras, tamanho)
             if abs(sum((l.total for l in grupo), Decimal(0)) - creditos) <= TOLERANCIA_PDFS]
    if not batem and lancamentos:
        pares, _, sem_credito = parear_creditos(lancamentos, leituras)
        if pares:
            usados = [l for _, grupo in pares for l in grupo]
            return EscolhaPdfs([l for l in leituras if l in usados], sem_credito, ESCOLHA_LANCAMENTOS)
    if len(batem) != 1:
        return EscolhaPdfs(leituras, [], ESCOLHA_NENHUMA if not batem else ESCOLHA_VARIAS)
    usados = list(batem[0])
    return EscolhaPdfs(usados, [l for l in leituras if l not in usados], ESCOLHA_COMBINACAO)


def rotular_pdfs(leituras: list[LeituraEventos]) -> None:
    """Grava em cada rescisão o rótulo do PDF de onde veio; rótulos repetidos ganham o nome do arquivo."""
    contagem: dict[str, int] = {}
    for leitura in leituras:
        contagem[leitura.rotulo] = contagem.get(leitura.rotulo, 0) + 1
    for leitura in leituras:
        rotulo = leitura.rotulo if contagem[leitura.rotulo] == 1 else f"{leitura.rotulo} ({leitura.arquivo})"
        for rescisao in leitura.rescisoes:
            rescisao.pdf = rotulo


def aviso_da_escolha(escolha: EscolhaPdfs, creditos: Decimal | None,
                     lancamentos: Sequence[Credito] = ()) -> str | None:
    """Aviso quando vários PDFs foram escolhidos e nenhuma (ou mais de uma) combinação bateu."""
    if escolha.situacao == ESCOLHA_LANCAMENTOS:
        _, sem_pdf, _ = parear_creditos(lancamentos, escolha.usados)
        if not sem_pdf:
            return None
        return ("ATENÇÃO: o razão tem " + ("um lançamento de crédito" if len(sem_pdf) == 1 else
                                           f"{len(sem_pdf)} lançamentos de crédito")
                + " sem PDF de eventos de valor igual: "
                + "; ".join(f"{c.descricao} (R$ {reais(c.valor)})" for c in sem_pdf)
                + ". Por isso nenhuma combinação dos PDFs soma os créditos do razão; cada PDF foi casado com o seu "
                  "lançamento de crédito (veja a composição da diferença, no rodapé da lista nova).")
    if escolha.situacao not in (ESCOLHA_NENHUMA, ESCOLHA_VARIAS):
        return None
    motivo = ("nenhuma combinação dos PDFs de eventos soma" if escolha.situacao == ESCOLHA_NENHUMA
              else "mais de uma combinação dos PDFs de eventos soma")
    diferenca = (creditos or Decimal(0)) - escolha.total
    return (f"ATENÇÃO: {motivo} os créditos do razão (R$ {reais(creditos)}); foram usados todos os "
            f"{len(escolha.usados)} PDFs (R$ {reais(escolha.total)}). Diferença créditos − PDFs: "
            f"R$ {reais(diferenca)}. Confira se algum PDF é de outro mês.")


def avisos_do_conjunto(razao: LeituraRazao, eventos: LeituraEventos | Sequence[LeituraEventos],
                       controle: LeituraControle) -> list[str]:
    """Conferências entre os arquivos (só avisos: nada impede de gerar)."""
    avisos = []
    for leitura in ([eventos] if isinstance(eventos, LeituraEventos) else eventos):
        if razao.inicio and leitura.competencia and _mes(razao.inicio) != _mes(leitura.competencia):
            avisos.append(f"ATENÇÃO: o razão é de {mes_curto(razao.inicio)}, mas o PDF de eventos "
                          f"{leitura.arquivo} é de {mes_curto(leitura.competencia)}. Confira se são do mesmo mês.")
    esperado = controle.total + controle.total_composicao     # lista + composição da diferença gravada
    if razao.saldo_anterior is not None and controle.pendentes and razao.saldo_anterior != esperado:
        if controle.composicao:
            lista = (f"total da lista do mês anterior com a composição da diferença ({reais(controle.total)} + "
                     f"{reais(controle.total_composicao)} = {reais(esperado)})")
        else:
            lista = f"total da lista do mês anterior ({reais(controle.total)})"
        avisos.append(f"ATENÇÃO: o saldo anterior do razão ({reais(razao.saldo_anterior)}) não bate com o {lista}. "
                      "Confira se a lista é a do mês certo.")
    return avisos


def _processar(resultado: ResultadoRescisoes, arquivo_razao: Path, arquivos_eventos: list[Path],
               arquivo_controle: Path, ao_progredir, pasta_destino: Path | None,
               arquivo_financeiro: Path | None = None) -> None:
    def progresso(percentual: int, mensagem: str) -> None:
        if ao_progredir is not None:
            ao_progredir(percentual, mensagem)

    avisos = resultado.avisos
    progresso(10, f"Lendo {arquivo_razao.name}...")
    razao = ler_razao(arquivo_razao)
    progresso(25, "Lendo " + ", ".join(a.name for a in arquivos_eventos) + "...")
    todos_eventos, repetidos = ler_varios_eventos(arquivos_eventos)
    progresso(45, f"Lendo {arquivo_controle.name}...")
    controle = ler_controle(arquivo_controle)
    titulos = None
    if arquivo_financeiro is not None:
        progresso(50, f"Lendo {arquivo_financeiro.name}...")
        titulos = ler_titulos(arquivo_financeiro)
        resultado.arquivo_financeiro = titulos.arquivo
    resultado.arquivo_razao, resultado.arquivo_controle = razao.arquivo, controle.arquivo
    resultado.arquivo_eventos = ", ".join(l.arquivo for l in todos_eventos)

    for leitura, tipo, quantidade, unidade in (
            [(razao, TIPO_RAZAO, len(razao.pagamentos), nome_curto_unidade(razao.unidade))]
            + [(l, TIPO_EVENTOS, len(l.rescisoes), " · ".join(x for x in (mes_curto(l.competencia), l.tipo) if x))
               for l in todos_eventos]
            + [(controle, TIPO_CONTROLE, len(controle.pendentes), controle.aba)]):
        if leitura.erro:
            avisos.append(Aviso(arquivo=leitura.arquivo, tipo_arquivo=tipo, nivel=NIVEL_ERRO,
                                mensagem=leitura.erro, linhas_lidas=0))
        else:
            avisos.append(Aviso(arquivo=leitura.arquivo, tipo_arquivo=tipo, nivel=NIVEL_OK, mensagem="OK",
                                linhas_lidas=quantidade, unidades=unidade))
            avisos.extend(leitura.avisos)
    if titulos is not None:
        if titulos.erro:
            avisos.append(Aviso(arquivo=titulos.arquivo, tipo_arquivo=TIPO_FINANCEIRO, nivel=NIVEL_ERRO,
                                mensagem=f"{titulos.erro} A conciliação foi feita sem a comparação com o "
                                         "financeiro.", linhas_lidas=0))
        else:
            avisos.append(Aviso(arquivo=titulos.arquivo, tipo_arquivo=TIPO_FINANCEIRO, nivel=NIVEL_OK,
                                mensagem="OK", linhas_lidas=titulos.quantidade_titulos,
                                unidades=nome_curto_unidade(titulos.unidade)))
            avisos.extend(titulos.avisos)
            outros = outros_tipos_de_titulo(titulos)
            if outros:
                avisos.append(Aviso(arquivo=titulos.arquivo, mensagem=(
                    "ATENÇÃO: o relatório do financeiro tem títulos que não são de rescisão (" + outros
                    + "). Todos foram comparados com a lista nova; confira se o filtro do relatório está certo.")))
    for repetido in repetidos:
        avisos.append(Aviso(arquivo=ARQUIVO_CONCILIACAO,
                            mensagem=f"PDF de eventos repetido, ignorado: {repetido}."))

    validos = [l for l in todos_eventos if not l.erro]
    problemas = [f"{nome} não pôde ser lido ({leitura.erro})"
                 for nome, leitura in (("o razão", razao), ("a lista do mês anterior", controle)) if leitura.erro]
    if not validos:
        problemas.insert(1, "nenhum PDF de eventos pôde ser lido ("
                         + "; ".join(f"{l.arquivo}: {l.erro}" for l in todos_eventos) + ")")
    if problemas:
        resultado.erro = "Relatório não gerado: " + "; ".join(problemas) + "."
        progresso(100, "Não foi possível fazer a conciliação.")
        return

    escolha = escolher_pdfs(validos, razao.total_creditos, razao.creditos)
    rotular_pdfs(escolha.usados + escolha.fora)
    resultado.pdfs_usados, resultado.pdfs_fora, resultado.escolha_pdfs = escolha.usados, escolha.fora, escolha.situacao
    resultado.creditos = list(razao.creditos)
    pares, resultado.creditos_sem_pdf, resultado.pdfs_sem_credito = parear_creditos(razao.creditos, escolha.usados)
    if not pares:            # nenhum PDF com crédito igual: a diferença fica numa linha só, como antes
        resultado.creditos_sem_pdf, resultado.pdfs_sem_credito = [], []
    mensagem_escolha = aviso_da_escolha(escolha, razao.total_creditos, razao.creditos)
    if mensagem_escolha:
        avisos.append(Aviso(arquivo=ARQUIVO_CONCILIACAO, mensagem=mensagem_escolha))
    eventos = escolha.usados[0]                       # o primeiro (o mensal, se houver): competência do mês
    rescisoes = [r for leitura in escolha.usados for r in leitura.rescisoes]

    for mensagem in avisos_do_conjunto(razao, escolha.usados, controle):
        avisos.append(Aviso(arquivo=ARQUIVO_CONCILIACAO, mensagem=mensagem))

    resultado.unidade = razao.unidade
    resultado.competencia = date(razao.inicio.year, razao.inicio.month, 1) if razao.inicio else eventos.competencia
    resultado.data_final = razao.fim
    resultado.saldo_anterior = razao.saldo_anterior
    resultado.total_creditos = razao.total_creditos
    resultado.total_pagamentos = razao.total_pagamentos
    resultado.saldo_final = razao.saldo_final
    resultado.total_pdf = escolha.total
    resultado.total_controle = controle.total
    resultado.composicao_anterior = list(controle.composicao)

    progresso(60, "Procurando cada pagamento no PDF e na lista anterior...")
    conciliacao = conciliar(razao.pagamentos, rescisoes, controle.pendentes,
                            eventos.competencia or resultado.competencia, controle.rodape,
                            fora_do_mes=[r for leitura in escolha.fora for r in leitura.rescisoes])
    resultado.baixas = conciliacao.baixas
    resultado.lista_nova = conciliacao.lista_nova
    observar_creditos_sem_pdf(resultado)
    resultado.composicao_nova = itens_da_composicao(resultado)
    if titulos is not None and not titulos.erro:
        progresso(70, "Comparando a lista nova com os títulos a pagar do financeiro...")
        resultado.financeiro = comparar_com_financeiro(resultado.lista_nova, titulos)
        mensagem_financeiro = aviso_do_financeiro(resultado)
        if mensagem_financeiro:
            avisos.append(Aviso(arquivo=ARQUIVO_CONCILIACAO, mensagem=mensagem_financeiro))

    # Prova: saldo final − lista nova = (créditos − 0264) + diferenças de valor − não encontrados
    composicao = composicao_da_diferenca(resultado)
    if composicao.sem_explicacao != 0:
        avisos.append(Aviso(
            arquivo=ARQUIVO_CONCILIACAO,
            mensagem=f"ATENÇÃO: a prova não fechou — saldo final − lista nova = {reais(composicao.diferenca)}, "
                     f"mas as diferenças explicadas somam {reais(composicao.diferenca - composicao.sem_explicacao)}. "
                     "Pode haver erro de leitura."))

    resultado.notas = _notas(resultado)

    progresso(80, "Gerando o relatório em Excel...")
    pasta = pasta_destino or arquivo_razao.parent
    if not pasta.is_dir():
        resultado.erro = (f"A pasta escolhida para salvar a planilha não existe mais: {pasta}. "
                          "Escolha outra pasta e gere de novo.")
        progresso(100, "Relatório não salvo.")
        return
    caminho = caminho_do_relatorio(pasta, resultado.unidade, resultado.competencia)
    try:
        resultado.caminho_relatorio = gerar_relatorio_rescisoes(resultado, caminho)
    except PermissionError:
        resultado.erro = (f"Não foi possível salvar o relatório na pasta {caminho.parent}. Verifique se "
                          "você tem permissão para gravar nessa pasta (ou escolha outra) e tente de novo.")
    except OSError as erro:
        resultado.erro = f"Não foi possível salvar o relatório em {caminho}: {erro.strerror or erro}."
    progresso(100, "Concluído." if resultado.erro is None else "Relatório não salvo.")


def _notas(resultado: ResultadoRescisoes) -> list[str]:
    pdf, pendentes = resultado.baixas_de(ORIGEM_PDF), resultado.baixas_de(ORIGEM_PENDENTE)
    nao_encontrados = resultado.baixas_de(ORIGEM_NAO_ENCONTRADO)
    notas = [
        f"{len(resultado.baixas)} pagamentos no razão: {len(pdf)} achados no PDF (0264), {len(pendentes)} na lista "
        f"do mês anterior e {len(nao_encontrados)} não encontrados.",
    ]
    if resultado.escolha_pdfs in (ESCOLHA_COMBINACAO, ESCOLHA_LANCAMENTOS):
        usados = " + ".join(l.rotulo for l in resultado.pdfs_usados)
        if resultado.escolha_pdfs == ESCOLHA_COMBINACAO:
            texto = (f"os PDFs de eventos usados ({usados}) somam exatamente os créditos do razão "
                     f"(R$ {reais(resultado.total_pdf)}).")
        else:
            texto = (f"cada PDF de eventos usado ({usados}) tem um lançamento de crédito de valor igual no razão "
                     f"(total R$ {reais(resultado.total_pdf)}).")
        if resultado.pdfs_fora:
            texto += (" " + ("O PDF" if len(resultado.pdfs_fora) == 1 else "Os PDFs") + " "
                      + ", ".join(f"{l.rotulo} (R$ {reais(l.total)})" for l in resultado.pdfs_fora)
                      + (" não foi lançado" if len(resultado.pdfs_fora) == 1 else " não foram lançados")
                      + " no razão deste mês (provavelmente do mês seguinte): "
                      + ("ficou" if len(resultado.pdfs_fora) == 1 else "ficaram")
                      + " fora do casamento e da lista nova.")
        notas.append(texto)
    notas += [
        "o casamento é pelo nome; nomes escritos de jeitos diferentes foram casados por semelhança (confira os de "
        "confiança menor que 1 na aba 'Pagamentos').",
    ]
    parecidos = [b for b in resultado.baixas if b.nota is not None and b.nota < 1]
    if parecidos:
        notas.append(f"{len(parecidos)} pagamento(s) casados com nome parecido, não idêntico.")
    if resultado.pagos_a_menor:
        total = sum((b.diferenca for b in resultado.pagos_a_menor), Decimal(0))
        notas.append(f"{len(resultado.pagos_a_menor)} pagamento(s) menor(es) que a rescisão (falta pagar R$ "
                     f"{reais(total)}): o que faltou continua na lista nova, com a origem 'restante'; veja a aba "
                     f"'{ABA_DIFERENTES}'.")
    if resultado.pagos_a_maior:
        total = sum((b.diferenca for b in resultado.pagos_a_maior), Decimal(0))
        notas.append(f"{len(resultado.pagos_a_maior)} pagamento(s) maior(es) que a rescisão (diferença total R$ "
                     f"{reais(total)}): as rescisões saíram da lista nova e a diferença está na composição da "
                     f"diferença; analise na aba '{ABA_DIFERENTES}'.")
    if nao_encontrados:
        total = sum((b.pagamento.valor for b in nao_encontrados), Decimal(0))
        notas.append(f"{len(nao_encontrados)} pagamento(s) sem rescisão no PDF nem na lista anterior (R$ {reais(total)}): "
                     f"veja a aba '{ABA_NAO_ENCONTRADOS}' (a coluna Observação traz a explicação provável).")
    if resultado.complementares:
        complementares = sum((b.pagamento.valor for b in resultado.complementares), Decimal(0))
        creditos_menos_pdf = (resultado.total_creditos or Decimal(0)) - (resultado.total_pdf or Decimal(0))
        if creditos_menos_pdf == complementares:
            notas.append(f"a diferença entre os créditos do razão e o 0264 (R$ {reais(creditos_menos_pdf)}) corresponde "
                         f"aos {len(resultado.complementares)} pagamento(s) complementar(es) listados em "
                         f"'{ABA_NAO_ENCONTRADOS}'.")
    da_lista = sum(1 for i in resultado.lista_nova if i.origem == ORIGEM_PENDENTE)
    notas.append(f"a lista nova tem {len(resultado.lista_nova)} rescisões a pagar ({da_lista} que já estavam na lista "
                 f"anterior e {len(resultado.lista_nova) - da_lista} do PDF deste mês), total R$ "
                 f"{reais(resultado.total_lista_nova)}. Use a aba 'Rescisões a pagar' desta planilha como lista do "
                 "mês anterior na próxima conciliação.")
    financeiro = resultado.financeiro
    if financeiro is not None:
        iguais = len(financeiro.linhas) - len(financeiro.para_conferir)
        texto = (f"lista nova × títulos a pagar do financeiro ({financeiro.arquivo}): {iguais} pessoa(s) com o "
                 f"mesmo valor nos dois")
        if financeiro.nomes_parecidos:
            texto += (f", {len(financeiro.nomes_parecidos)} delas com o nome escrito diferente (confira as de "
                      f"confiança menor que 1)")
        texto += f"; veja a aba '{ABA_FINANCEIRO}'."
        notas.append(texto)
    for aviso in resultado.avisos:
        if not aviso.tipo_arquivo and "ATENÇÃO" in aviso.mensagem:
            notas.append(aviso.mensagem)
    return notas


def outros_tipos_de_titulo(titulos) -> str:
    """"Nota Fiscal: 3 títulos; ..." para os títulos cujo tipo não é rescisão ("Recisões" no Tasy); "" se nenhum."""
    contagem: dict[str, int] = {}
    for fornecedor in titulos.fornecedores:
        for titulo in fornecedor.titulos:
            if titulo.tipo and not re.search(r"re?s?cis", _sem_acento(titulo.tipo).casefold()):
                contagem[titulo.tipo] = contagem.get(titulo.tipo, 0) + 1
    return "; ".join(f"{tipo}: {n} título(s)" for tipo, n in contagem.items())


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()


def aviso_do_financeiro(resultado: ResultadoRescisoes) -> str | None:
    """ATENÇÃO quando a lista nova e o financeiro não batem pessoa a pessoa."""
    financeiro = resultado.financeiro
    if financeiro is None or not financeiro.para_conferir:
        return None
    partes = []
    for situacao, texto in ((SITUACAO_DIVERGENTE, "com valor diferente"),
                            (SITUACAO_SO_LISTA, "só na lista nova"),
                            (SITUACAO_SO_FINANCEIRO, "só no financeiro")):
        quantidade = len(financeiro.linhas_de(situacao))
        if quantidade:
            partes.append(f"{quantidade} {texto}")
    return (f"ATENÇÃO: a lista nova (R$ {reais(financeiro.total_lista)}) e os títulos a pagar do financeiro "
            f"(R$ {reais(financeiro.total_financeiro)}) não batem pessoa a pessoa: " + ", ".join(partes)
            + f" (diferença R$ {reais(financeiro.diferenca)}). Veja a aba '{ABA_FINANCEIRO}'.")


# ---------------------------------------------------------------------
# Nome do arquivo
# ---------------------------------------------------------------------
def unidade_para_arquivo(unidade: str) -> str:
    """"Fundação Hospital Exemplo de ..." → "HospitalExemplo"; "AME - Cidade Delta (...)" → "CidadeDelta"."""
    curto = nome_curto_unidade(unidade)
    if not re.match(r"^\s*ame\b", curto, re.IGNORECASE) and "hospital exemplo" in curto.casefold():
        return "HospitalExemplo"
    curto = re.sub(r"^\s*ame\s*-?\s*", "", curto, flags=re.IGNORECASE) or curto
    sem_acento = unicodedata.normalize("NFKD", curto).encode("ascii", "ignore").decode()
    palavras = re.findall(r"[A-Za-z0-9]+", sem_acento)
    return "".join(p[:1].upper() + p[1:] for p in palavras) or "Unidade"


def caminho_do_relatorio(pasta: Path, unidade: str, mes) -> Path:
    mes_texto = mes_curto(mes).replace("/", "") or "sem_mes"
    original = Path(pasta) / f"{PREFIXO_ARQUIVO}_{unidade_para_arquivo(unidade)}_{mes_texto}.xlsx"
    caminho, contador = original, 2
    while caminho.exists():
        caminho = original.with_name(f"{original.stem}_{contador}{original.suffix}")
        contador += 1
    return caminho


# ---------------------------------------------------------------------
# Números da tela e prévias
# ---------------------------------------------------------------------
@dataclass(frozen=True)
class ComposicaoDiferenca:
    """Saldo final do razão − lista nova, e o que explica essa diferença."""

    diferenca: Decimal
    creditos_menos_pdf: Decimal          # créditos do razão − total do 0264
    valores_diferentes: Decimal          # soma de (valor da rescisão − valor pago) dos pagos a maior
    nao_encontrados: Decimal             # pagamentos sem rescisão (entram com sinal negativo)
    sem_explicacao: Decimal
    composicao_anterior: Decimal = Decimal(0)   # itens da composição gravada na lista anterior


def composicao_da_diferenca(resultado: ResultadoRescisoes) -> ComposicaoDiferenca:
    diferenca = (resultado.saldo_final or Decimal(0)) - resultado.total_lista_nova
    creditos_menos_pdf = (resultado.total_creditos or Decimal(0)) - (resultado.total_pdf or Decimal(0))
    valores = sum((b.diferenca for b in resultado.pagos_a_maior), Decimal(0))   # pago a menor: na lista
    nao_encontrados = -sum((b.pagamento.valor for b in resultado.baixas_de(ORIGEM_NAO_ENCONTRADO)), Decimal(0))
    anterior = sum((v for _, v in resultado.composicao_anterior), Decimal(0))
    return ComposicaoDiferenca(diferenca, creditos_menos_pdf, valores, nao_encontrados,
                               diferenca - creditos_menos_pdf - valores - nao_encontrados - anterior, anterior)


def observar_creditos_sem_pdf(resultado: ResultadoRescisoes) -> None:
    """Não encontrado (regra d) com o nome num crédito do razão sem PDF (ex.: reembolso): a observação diz qual."""
    for baixa in resultado.baixas_de(ORIGEM_NAO_ENCONTRADO):
        if baixa.regra != REGRA_SEM_RESCISAO:
            continue
        nome = set(palavras_do_nome(baixa.pagamento.nome))
        credito = next((c for c in resultado.creditos_sem_pdf
                        if nome and nome <= set(palavras_do_nome(c.historico))), None)
        if credito is not None:
            baixa.observacao = (f"Sem rescisão no PDF nem na lista anterior; o razão tem um crédito com este nome, "
                                f"sem PDF de eventos: {credito.descricao} (R$ {reais(credito.valor)}).")


def _descrever_eventos(leitura: LeituraEventos) -> str:
    partes = [leitura.arquivo, leitura.tipo]
    if leitura.data_pagamento:
        partes.append(f"pagamento {leitura.data_pagamento:%d/%m/%Y}")
    return " — ".join(p for p in partes if p)


def _itens_creditos_menos_pdfs(resultado: ResultadoRescisoes, resto: Decimal) -> list[tuple[str, Decimal]]:
    """"Créditos do razão − PDFs" item por item: cada crédito sem PDF de valor igual (+), cada PDF usado sem
    crédito igual (−) e, se houver, os pagamentos complementares da regra a (−: ficam fora dos não encontrados)."""
    if not (resultado.creditos_sem_pdf or resultado.pdfs_sem_credito):
        mes = mes_curto(resultado.competencia)
        return [(f"Créditos do razão − PDFs de eventos de {mes} (sem os pagamentos complementares)", resto)]
    itens = [(f"Crédito do razão sem PDF de eventos: {c.descricao}", c.valor)
             for c in resultado.creditos_sem_pdf]
    for leitura in resultado.pdfs_sem_credito:
        itens.append((f"{leitura.formato} de eventos sem lançamento de crédito igual no razão: "
                      f"{_descrever_eventos(leitura)}", -leitura.total))
    complementares = sum((b.pagamento.valor for b in resultado.complementares), Decimal(0))
    if complementares:
        itens.append((f"Pagamentos complementares de rescisão do PDF (regra a, aba '{ABA_NAO_ENCONTRADOS}')",
                      -complementares))
    return itens


def itens_da_composicao(resultado: ResultadoRescisoes) -> list[tuple[str, Decimal]]:
    """Rodapé da lista nova: os itens que explicam "saldo final do razão − lista nova" (somam exatamente isso).

    - os itens da composição da lista anterior (continuam valendo até o usuário apagar);
    - o que sobrar de "saldo anterior − lista anterior − esses itens";
    - créditos − PDFs, sem os pagamentos complementares (que se anulam com os não encontrados da regra 1a),
      item por item: cada crédito do razão sem PDF de valor igual e cada PDF usado sem crédito igual;
    - cada pagamento a maior (rescisão − pago; o que foi pago a menor continua na lista) e cada não encontrado
      que não é complementar (− pago).
    O texto começa pelo nome ("NOME - ..."), para servir à regra c no mês seguinte.
    """
    itens = list(resultado.composicao_anterior)
    if resultado.saldo_anterior is not None:
        sobra = resultado.saldo_anterior - (resultado.total_controle or Decimal(0)) - sum(
            (v for _, v in itens), Decimal(0))
        if sobra:
            itens.append(("Diferença vinda da lista anterior (saldo anterior do razão − lista anterior)", sobra))
    complementares = resultado.complementares
    resto_pdf = ((resultado.total_creditos or Decimal(0)) - (resultado.total_pdf or Decimal(0))
                 - sum((b.pagamento.valor for b in complementares), Decimal(0)))
    mes = mes_curto(resultado.competencia)
    if resto_pdf:
        itens += _itens_creditos_menos_pdfs(resultado, resto_pdf)

    def quando(pagamento) -> str:
        data = f" em {pagamento.data:%d/%m/%Y}" if pagamento.data else ""
        bordero = f", borderô {pagamento.bordero}" if pagamento.bordero else ""
        return f"{data}{bordero}"

    for baixa in resultado.pagos_a_maior:
        pagamento = baixa.pagamento
        itens.append((f"{pagamento.nome} - pago R$ {reais(pagamento.valor)}{quando(pagamento)}, rescisão de "
                      f"R$ {reais(baixa.valor_referencia)} ({baixa.onde_achado}): pago a maior", baixa.diferenca))
    for baixa in resultado.baixas_de(ORIGEM_NAO_ENCONTRADO):
        if any(baixa is c for c in complementares):
            continue
        pagamento = baixa.pagamento
        itens.append((f"{pagamento.nome} - pago{quando(pagamento)} sem rescisão correspondente ({mes})",
                      -pagamento.valor))
    return itens


@dataclass(frozen=True)
class NumerosRescisoes:
    achados_pdf: int
    achados_lista: int
    nao_encontrados: int
    valores_diferentes: int
    lista_nova: int


def numeros_principais(resultado: ResultadoRescisoes) -> NumerosRescisoes:
    return NumerosRescisoes(
        achados_pdf=len(resultado.baixas_de(ORIGEM_PDF)),
        achados_lista=len(resultado.baixas_de(ORIGEM_PENDENTE)),
        nao_encontrados=len(resultado.baixas_de(ORIGEM_NAO_ENCONTRADO)),
        valores_diferentes=len(resultado.valores_diferentes),
        lista_nova=len(resultado.lista_nova))


@dataclass
class PreviaRescisoes:
    descricao: str = ""
    erro: str | None = None
    avisos: list[str] = field(default_factory=list)


def previa_razao(arquivo: Path) -> PreviaRescisoes:
    leitura = ler_razao(Path(arquivo))
    if leitura.erro:
        return PreviaRescisoes(erro=leitura.erro)
    partes = [nome_curto_unidade(leitura.unidade) or "unidade não encontrada",
              mes_curto(leitura.inicio) or "mês não encontrado",
              f"{len(leitura.pagamentos)} pagamentos", f"saldo final R$ {reais(leitura.saldo_final)}"]
    return PreviaRescisoes(descricao=" · ".join(partes), avisos=[a.mensagem for a in leitura.avisos])


def previa_eventos(arquivos: Path | Sequence[Path]) -> PreviaRescisoes:
    leituras, repetidos = ler_varios_eventos(_lista_de_caminhos(arquivos))
    com_erro = [l for l in leituras if l.erro]
    if com_erro:
        if len(leituras) == 1:
            return PreviaRescisoes(erro=com_erro[0].erro)
        return PreviaRescisoes(erro="; ".join(f"{l.arquivo}: {l.erro}" for l in com_erro))
    avisos = [a.mensagem for l in leituras for a in l.avisos]
    avisos += [f"repetido, ignorado: {r}" for r in repetidos]
    if len(leituras) == 1:
        leitura = leituras[0]
        partes = [f"0264 · {mes_curto(leitura.competencia) or 'mês não encontrado'}",
                  f"{len(leitura.rescisoes)} pessoas", f"R$ {reais(leitura.total)}"]
    else:
        leituras = sorted(leituras, key=_ordem_dos_pdfs)
        total = sum((l.total for l in leituras), Decimal(0))
        partes = [f"{len(leituras)} PDFs · 0264 · {mes_curto(leituras[0].competencia) or 'mês não encontrado'}",
                  " + ".join(f"{l.rotulo} R$ {reais(l.total)}" for l in leituras),
                  f"total R$ {reais(total)}"]
    return PreviaRescisoes(descricao=" · ".join(partes), avisos=avisos)


def previa_controle(arquivo: Path) -> PreviaRescisoes:
    leitura = ler_controle(Path(arquivo))
    if leitura.erro:
        return PreviaRescisoes(erro=leitura.erro)
    partes = [f"aba \"{leitura.aba}\"", f"{len(leitura.pendentes)} rescisões", f"R$ {reais(leitura.total)}"]
    return PreviaRescisoes(descricao=" · ".join(partes), avisos=[a.mensagem for a in leitura.avisos])


def previa_financeiro(arquivo: Path) -> PreviaRescisoes:
    leitura = ler_titulos(Path(arquivo))
    if leitura.erro:
        return PreviaRescisoes(erro=leitura.erro)
    total = sum((f.saldo for f in leitura.fornecedores), Decimal(0))
    partes = [f"{leitura.quantidade_titulos} títulos", f"{len(leitura.fornecedores)} pessoas", f"R$ {reais(total)}"]
    avisos = [a.mensagem for a in leitura.avisos]
    outros = outros_tipos_de_titulo(leitura)
    if outros:
        avisos.append(f"títulos que não são de rescisão ({outros})")
    return PreviaRescisoes(descricao=" · ".join(partes), avisos=avisos)


def conferir_conjunto(arquivo_razao: Path, arquivo_eventos: Path | Sequence[Path],
                      arquivo_controle: Path) -> PreviaRescisoes:
    """Com os três escolhidos: avisos de mês diferente e de saldo anterior × lista anterior; com vários
    PDFs, a descrição diz quais entram no mês (e quais ficam de fora)."""
    razao, controle = ler_razao(Path(arquivo_razao)), ler_controle(Path(arquivo_controle))
    leituras, _ = ler_varios_eventos(_lista_de_caminhos(arquivo_eventos))
    if razao.erro or controle.erro or not leituras or any(l.erro for l in leituras):
        return PreviaRescisoes()
    escolha = escolher_pdfs(leituras, razao.total_creditos, razao.creditos)
    avisos = avisos_do_conjunto(razao, escolha.usados, controle)
    descricao = ""
    if escolha.situacao in (ESCOLHA_COMBINACAO, ESCOLHA_LANCAMENTOS):
        descricao = ("entram no mês: " + " + ".join(l.rotulo for l in escolha.usados)
                     + (f" (= créditos do razão R$ {reais(razao.total_creditos)})"
                        if escolha.situacao == ESCOLHA_COMBINACAO else " (cada um = um lançamento de crédito do razão)"))
        if escolha.fora:
            descricao += "; fora (provavelmente do mês seguinte): " + ", ".join(l.rotulo for l in escolha.fora)
    mensagem = aviso_da_escolha(escolha, razao.total_creditos, razao.creditos)
    if mensagem:
        avisos.append(mensagem.replace("ATENÇÃO: ", ""))
    return PreviaRescisoes(descricao=descricao, avisos=avisos)
