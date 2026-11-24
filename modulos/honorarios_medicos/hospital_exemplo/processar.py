"""
Orquestração da Conciliação Honorários Hospital Exemplo: reconhece os arquivos, lê, pareia, gera o Excel.

processar_honorarios_hospital_exemplo() é a ÚNICA porta de entrada para a interface e nunca levanta exceção.
Recebe a lista de arquivos (ou pastas: tudo o que estiver dentro, nas subpastas também) e reconhece cada
um pelo conteúdo. Arquivo não reconhecido ou com problema vira aviso e é deixado de fora; só não gera
o relatório quando falta o balancete ou quando há dois relatórios do mesmo tipo e lado (ex.: dois HM PF).

Planilha: Conciliacao_Honorarios_Medicos_PF_PJ_<mm>_<aaaa>.xlsx (o nome da planilha do usuário), na pasta
escolhida (pasta_destino) ou na pasta do primeiro balancete; nome repetido ganha _2, _3...
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Callable

from modulos.honorarios_medicos.fornecedores.avisos import NIVEL_ERRO, NIVEL_OK, Aviso
from modulos.honorarios_medicos.fornecedores.leitores import mesma_unidade_pelo_nome, nome_curto_unidade, reais
from modulos.honorarios_medicos.fornecedores.relatorio_excel import mes_curto
from modulos.honorarios_medicos.hospital_exemplo.leitores import (
    ARQUIVO_BALANCETE,
    ARQUIVO_PDF_OUTRO,
    ARQUIVO_REPASSE_PDF,
    ARQUIVO_SENIOR,
    GRUPO_PAGAMENTO,
    identificar_arquivo,
    ler_balancete_hospital_exemplo,
    ler_repasse_pdf,
    ler_senior,
)
from modulos.honorarios_medicos.hospital_exemplo.modelos import (
    LADOS,
    NOMES_LADO,
    SITUACAO_DIVERGENTE,
    SITUACAO_OK,
    SITUACAO_SO_BALANCETE,
    SITUACAO_SO_SENIOR,
    TIPO_BALANCETE,
    TIPO_REPASSE,
    TIPO_SENIOR,
    ResultadoHospitalExemplo,
)
from modulos.honorarios_medicos.hospital_exemplo.pareamento import agrupar_terceiros, parear_hospital_exemplo
from modulos.honorarios_medicos.hospital_exemplo.relatorio_excel import gerar_relatorio_hospital_exemplo

PREFIXO_ARQUIVO = "Conciliacao_Honorarios_Medicos_PF_PJ"
ARQUIVO_CONCILIACAO = "Conciliação"
EXTENSOES = {".xls", ".xlsx", ".pdf", ".csv", ".txt"}

FuncaoProgresso = Callable[[int, str], None]


def arquivos_da_pasta(pasta: Path) -> list[Path]:
    """Todos os arquivos da pasta e das subpastas que podem ser relatórios (sem as planilhas já geradas)."""
    return sorted(p for p in Path(pasta).rglob("*")
                  if p.is_file() and p.suffix.casefold() in EXTENSOES
                  and not p.name.startswith(("~$", PREFIXO_ARQUIVO)))


def _expandir(caminhos) -> list[Path]:
    arquivos: list[Path] = []
    for caminho in caminhos:
        caminho = Path(caminho)
        arquivos += arquivos_da_pasta(caminho) if caminho.is_dir() else [caminho]
    return list(dict.fromkeys(arquivos))


def processar_honorarios_hospital_exemplo(arquivos, ao_progredir: FuncaoProgresso | None = None,
                                    pasta_destino: Path | None = None) -> ResultadoHospitalExemplo:
    """Faz a conciliação completa (nunca levanta exceção). pasta_destino None = pasta do balancete."""
    resultado = ResultadoHospitalExemplo()
    try:
        _processar(resultado, _expandir(arquivos), ao_progredir, Path(pasta_destino) if pasta_destino else None)
    except Exception as erro:  # rede de segurança: a interface nunca recebe exceção
        resultado.erro = f"Erro inesperado durante a conciliação: {erro}"
    return resultado


@dataclass
class _Leituras:
    balancetes: list = field(default_factory=list)
    seniors: list = field(default_factory=list)
    pdfs: list = field(default_factory=list)
    pasta_balancete: Path | None = None


def _ler_tudo(resultado: ResultadoHospitalExemplo, arquivos: list[Path], progresso) -> _Leituras:
    avisos = resultado.avisos
    leituras = _Leituras()
    vistos: dict[str, str] = {}
    for posicao, arquivo in enumerate(arquivos):
        progresso(5 + 45 * posicao // max(len(arquivos), 1), f"Lendo {arquivo.name}...")
        try:
            assinatura = hashlib.sha256(arquivo.read_bytes()).hexdigest()
        except OSError as erro:
            avisos.append(Aviso(arquivo=arquivo.name, nivel=NIVEL_ERRO, linhas_lidas=0,
                                mensagem=f"Não foi possível abrir o arquivo: {erro.strerror or erro}."))
            continue
        if assinatura in vistos:
            avisos.append(Aviso(arquivo=arquivo.name, mensagem=f"É o mesmo arquivo que {vistos[assinatura]}; "
                                                               "foi lido uma vez só."))
            continue
        vistos[assinatura] = arquivo.name
        tipo = identificar_arquivo(arquivo)
        if tipo == ARQUIVO_BALANCETE:
            leitura, tipo_aviso = ler_balancete_hospital_exemplo(arquivo), TIPO_BALANCETE
            quantidade = sum(len(c) for c in leitura.contas.values())
            lista = leituras.balancetes
            if leituras.pasta_balancete is None and not leitura.erro:
                leituras.pasta_balancete = arquivo.parent
        elif tipo == ARQUIVO_SENIOR:
            leitura, tipo_aviso = ler_senior(arquivo), TIPO_SENIOR
            quantidade, lista = len(leitura.lancamentos), leituras.seniors
        elif tipo == ARQUIVO_REPASSE_PDF:
            leitura, tipo_aviso = ler_repasse_pdf(arquivo), TIPO_REPASSE
            quantidade, lista = len(leitura.repasses), leituras.pdfs
        elif tipo == ARQUIVO_PDF_OUTRO:
            avisos.append(Aviso(arquivo=arquivo.name, linhas_lidas=0,
                                mensagem="PDF que não é o SCF – Repasse Sintético (6095 / Remoção); ficou de fora. "
                                         "O balancete e o HM Senior entram pelo .xls."))
            continue
        else:
            avisos.append(Aviso(arquivo=arquivo.name, linhas_lidas=0,
                                mensagem="Arquivo não reconhecido (não é balancete, HM Senior nem SCF – Repasse "
                                         "Sintético); ficou de fora."))
            continue
        if leitura.erro:
            avisos.append(Aviso(arquivo=leitura.arquivo, tipo_arquivo=tipo_aviso, nivel=NIVEL_ERRO,
                                mensagem=leitura.erro, linhas_lidas=0))
            continue
        avisos.append(Aviso(arquivo=leitura.arquivo, tipo_arquivo=tipo_aviso, nivel=NIVEL_OK, mensagem="OK",
                            linhas_lidas=quantidade, unidades=nome_curto_unidade(getattr(leitura, "unidade", ""))))
        avisos.extend(leitura.avisos)
        lista.append(leitura)
    return leituras


def _processar(resultado: ResultadoHospitalExemplo, arquivos: list[Path], ao_progredir,
               pasta_destino: Path | None) -> None:
    def progresso(percentual: int, mensagem: str) -> None:
        if ao_progredir is not None:
            ao_progredir(percentual, mensagem)

    avisos = resultado.avisos
    if not arquivos:
        resultado.erro = "Nenhum arquivo foi escolhido."
        return
    leituras = _ler_tudo(resultado, arquivos, progresso)

    # um balancete e um Senior por lado
    problemas: list[str] = []
    contas, totais, senior = {}, {}, {}
    for leitura in leituras.balancetes:
        for lado, total in leitura.totais.items():
            if lado in totais:
                problemas.append(f"há dois balancetes com a conta de honorários {lado}")
                continue
            totais[lado], contas[lado] = total, leitura.contas[lado]
    # Senior e PDFs de outro mês que o balancete ficam de fora (ex.: a pasta do mês anterior dentro da escolhida)
    mes_balancete = next((l.mes for l in leituras.balancetes if l.mes), None)

    def do_mesmo_mes(leitura) -> bool:
        if mes_balancete is None or leitura.mes is None or leitura.mes == mes_balancete:
            return True
        avisos.append(Aviso(arquivo=leitura.arquivo,
                            mensagem=f"ATENÇÃO: o arquivo é de {mes_curto(leitura.mes)}, mas o balancete é de "
                                     f"{mes_curto(mes_balancete)}; ele ficou de fora."))
        return False

    leituras.seniors = [l for l in leituras.seniors if do_mesmo_mes(l)]
    leituras.pdfs = [l for l in leituras.pdfs if do_mesmo_mes(l)]
    for leitura in leituras.seniors:
        if leitura.lado in senior:
            problemas.append(f"há dois relatórios HM {leitura.lado} Senior")
            continue
        senior[leitura.lado] = leitura
    if not totais:
        problemas.insert(0, "nenhum balancete de honorários foi lido")
    if problemas:
        resultado.erro = "Relatório não gerado: " + "; ".join(dict.fromkeys(problemas)) + "."
        progresso(100, "Não foi possível fazer a conciliação.")
        return

    balancete = leituras.balancetes[0]
    resultado.unidade = balancete.unidade
    resultado.lados = [lado for lado in LADOS if lado in totais]
    resultado.contas_total = totais
    resultado.totais_balancete = {lado: totais[lado].saldo_atual for lado in resultado.lados}
    for lado in LADOS:
        if lado in totais and lado not in senior:
            avisos.append(Aviso(arquivo=ARQUIVO_CONCILIACAO,
                                mensagem=f"ATENÇÃO: falta o relatório HM {lado} Senior; as contas {lado} foram "
                                         "comparadas só com a Remoção/Deslocamento."))
        if lado in senior and lado not in totais:
            avisos.append(Aviso(arquivo=senior[lado].arquivo,
                                mensagem=f"ATENÇÃO: não há balancete com a conta de honorários {lado}; o HM {lado} "
                                         "Senior ficou de fora."))
    resultado.totais_senior = {lado: senior[lado].total for lado in resultado.lados if lado in senior}

    # PDFs: só os da mesma unidade; o mesmo Nr Repasse em dois PDFs entra uma vez
    numeros: dict[str, str] = {}
    for leitura in leituras.pdfs:
        if leitura.unidade and balancete.unidade and not mesma_unidade_pelo_nome(balancete.unidade, leitura.unidade):
            avisos.append(Aviso(arquivo=leitura.arquivo, nivel=NIVEL_ERRO,
                                mensagem=f"O PDF é de outra unidade ({leitura.unidade}); ficou de fora."))
            continue
        for repasse in leitura.repasses:
            if repasse.numero in numeros:
                avisos.append(Aviso(arquivo=leitura.arquivo,
                                    mensagem=f"ATENÇÃO: o repasse {repasse.numero} ({repasse.terceiro}) também está "
                                             f"em {numeros[repasse.numero]}; entrou uma vez só."))
                continue
            numeros[repasse.numero] = leitura.arquivo
            resultado.repasses.append(repasse)
            resultado.origem_do_repasse[id(repasse)] = leitura.arquivo

    meses = Counter(m for m in [balancete.mes, *(s.mes for s in senior.values()),
                                *(p.mes for p in leituras.pdfs if p.repasses)] if m)
    resultado.mes = balancete.mes or (meses.most_common(1)[0][0] if meses else None)
    if len(meses) > 1:
        avisos.append(Aviso(arquivo=ARQUIVO_CONCILIACAO,
                            mensagem="ATENÇÃO: os relatórios são de meses diferentes ("
                                     + ", ".join(mes_curto(m) for m in sorted(meses))
                                     + "). Confira se escolheu os arquivos do mesmo mês."))
    resultado.arquivos = [l.arquivo for l in [*leituras.balancetes, *senior.values(), *leituras.pdfs]]

    progresso(60, "Pareando os médicos e clínicas...")
    terceiros = agrupar_terceiros(resultado.repasses)
    pareamento = parear_hospital_exemplo(contas, {lado: s.lancamentos for lado, s in senior.items()}, terceiros)
    zeradas = []
    for lado in resultado.lados:
        linhas = pareamento.linhas[lado]
        fora = [l for l in linhas if l.situacao in (SITUACAO_SO_BALANCETE, SITUACAO_SO_SENIOR)
                and (l.saldo_contabil or 0) == 0 and (l.saldo_senior or 0) == 0]
        zeradas += fora
        resultado.linhas[lado] = [l for l in linhas if l not in fora]
        for linha in resultado.linhas[lado]:
            for terceiro in linha.remocao:
                for repasse in terceiro.repasses:
                    resultado.lado_do_repasse[id(repasse)] = lado
                    resultado.conta_do_repasse[id(repasse)] = linha.conta.codigo

    # Prova final por lado: contábil − (Senior + Remoção do lado) = soma das diferenças
    for lado in resultado.lados:
        soma = sum((l.diferenca for l in resultado.linhas[lado]), Decimal(0))
        senior_lado = sum((l.saldo_senior or Decimal(0) for l in resultado.linhas[lado]), Decimal(0))
        esperado = resultado.totais_balancete[lado] - senior_lado - resultado.remocao_do_lado(lado)
        if esperado != soma:
            avisos.append(Aviso(arquivo=ARQUIVO_CONCILIACAO,
                                mensagem=f"ATENÇÃO: a prova final do {lado} não fechou — contábil − Senior − "
                                         f"Remoção = {reais(esperado)}, mas a soma das diferenças é {reais(soma)}."))

    resultado.notas = _notas(resultado, pareamento, zeradas)

    progresso(85, "Gerando o relatório em Excel...")
    pasta = pasta_destino or leituras.pasta_balancete
    if pasta is None or not pasta.is_dir():
        resultado.erro = (f"A pasta escolhida para salvar a planilha não existe mais: {pasta}. "
                          "Escolha outra pasta e gere de novo.")
        progresso(100, "Relatório não salvo.")
        return
    caminho = caminho_do_relatorio(pasta, resultado.mes)
    try:
        resultado.caminho_relatorio = gerar_relatorio_hospital_exemplo(resultado, caminho)
    except PermissionError:
        resultado.erro = (f"Não foi possível salvar o relatório na pasta {caminho.parent}. Verifique se "
                          "você tem permissão para gravar nessa pasta (ou escolha outra) e tente de novo.")
    except OSError as erro:
        resultado.erro = f"Não foi possível salvar o relatório em {caminho}: {erro.strerror or erro}."
    progresso(100, "Concluído." if resultado.erro is None else "Relatório não salvo.")


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _notas(resultado: ResultadoHospitalExemplo, pareamento, zeradas) -> list[str]:
    notas = ["O pareamento é pelo nome: o Senior só com as contas do mesmo lado (HM PF com a 2131, HM PJ com a "
             "2132); a Remoção/Deslocamento com todas as contas, porque os PDFs misturam PF e PJ. Cada linha dos "
             "PDFs entra no lado da conta onde a pessoa foi encontrada."]
    for lado in resultado.lados:
        linhas = resultado.linhas[lado]
        contagem = Counter(l.situacao for l in linhas)
        azuis = sum(1 for l in linhas if l.acertada_pela_remocao)
        partes = [_plural(contagem[SITUACAO_OK], "conta bate", "contas batem")]
        if azuis:
            partes[0] += f" ({azuis} com a Remoção/Deslocamento)"
        if contagem[SITUACAO_DIVERGENTE]:
            partes.append(_plural(contagem[SITUACAO_DIVERGENTE], "diverge", "divergem"))
        if contagem[SITUACAO_SO_BALANCETE]:
            partes.append(_plural(contagem[SITUACAO_SO_BALANCETE], "conta sem nada nos relatórios",
                                  "contas sem nada nos relatórios"))
        if contagem[SITUACAO_SO_SENIOR]:
            partes.append(_plural(contagem[SITUACAO_SO_SENIOR], "pessoa do Senior sem conta",
                                  "pessoas do Senior sem conta"))
        notas.append(f"{NOMES_LADO[lado]} ({lado}): " + "; ".join(partes) + ".")

    por_valor = [l for l in pareamento.por_valor if l.lado in resultado.lados and l.conta is not None]
    if por_valor:
        notas.append("Pareadas pelo VALOR (nomes diferentes; confirmar): "
                     + "; ".join(f"{l.conta.descricao} × {l.nome_senior}" for l in por_valor) + ".")
    duplicados = [l for l in pareamento.duplicados if l.lado in resultado.lados]
    if duplicados:
        notas.append("Mais de um cadastro no Senior somado na mesma conta: "
                     + "; ".join(f"{l.conta.descricao} ({l.nome_senior})" for l in duplicados) + ".")

    # diferenças que se anulam entre PF e PJ (a mesma pessoa lançada na conta do outro lado)
    if len(resultado.lados) == 2:
        pj = [l for l in resultado.linhas["PJ"] if l.diferenca != 0]
        cruzadas = []
        for l_pf in resultado.linhas["PF"]:
            par = next((l for l in pj if l.diferenca == -l_pf.diferenca and l_pf.diferenca != 0), None)
            if par is not None:
                pj.remove(par)
                cruzadas.append(f"{_nome(l_pf)} (PF {reais(l_pf.diferenca)}) × {_nome(par)} "
                                f"(PJ {reais(par.diferenca)})")
        if cruzadas:
            notas.append("Diferenças que se anulam entre PF e PJ (conferir se o lançamento foi na conta do outro "
                         "lado): " + "; ".join(cruzadas) + ".")

    # o Rel. 6203 não traz a competência: entra sempre, e quem concilia confere o mês (decisão do usuário, out/2026)
    particulares = [r for r in resultado.repasses if r.grupo == GRUPO_PAGAMENTO]
    if particulares:
        arquivos = dict.fromkeys(resultado.origem_do_repasse[id(r)] for r in particulares)
        notas.append(f"Pagamento particular (Rel. 6203): {_plural(len(particulares), 'repasse', 'repasses')}, R$ "
                     f"{reais(sum((r.bruto for r in particulares), Decimal(0)))}, de " + ", ".join(arquivos)
                     + ". Esse relatório não traz a competência: confira se ele é do mesmo mês do balancete.")

    sem_conta = resultado.repasses_sem_conta
    if sem_conta:
        notas.append(f"{_plural(len(sem_conta), 'linha', 'linhas')} da Remoção/Deslocamento sem conta no balancete "
                     f"(R$ {reais(sum((r.bruto for r in sem_conta), Decimal(0)))}): "
                     + "; ".join(f"{r.terceiro} ({reais(r.bruto)})" for r in sem_conta)
                     + ". Estão na aba da Remoção, fora das abas PF e PJ.")
    if zeradas:
        notas.append(f"{_plural(len(zeradas), 'linha com saldo zero', 'linhas com saldo zero')} e sem par ficaram "
                     "fora da conciliação: " + "; ".join(_nome(l) for l in zeradas) + ".")
    atencao = [a.mensagem if a.arquivo == ARQUIVO_CONCILIACAO else f"{a.arquivo}: {a.mensagem}"
               for a in resultado.avisos if a.mensagem.startswith("ATENÇÃO")]
    notas += atencao
    return notas


def _nome(linha) -> str:
    return linha.conta.descricao if linha.conta is not None else linha.nome_senior


# ---------------------------------------------------------------------
# Nome do arquivo
# ---------------------------------------------------------------------
def caminho_do_relatorio(pasta: Path, mes) -> Path:
    mes_texto = f"{mes.month:02d}_{mes.year}" if mes else "sem_mes"
    original = Path(pasta) / f"{PREFIXO_ARQUIVO}_{mes_texto}.xlsx"
    caminho, contador = original, 2
    while caminho.exists():
        caminho = original.with_name(f"{original.stem}_{contador}{original.suffix}")
        contador += 1
    return caminho


# ---------------------------------------------------------------------
# Prévia da tela (o que foi reconhecido entre os arquivos escolhidos)
# ---------------------------------------------------------------------
@dataclass
class PreviaHospitalExemplo:
    descricao: str = ""
    erro: str | None = None
    avisos: list[str] = field(default_factory=list)


def _sem_repetidos(arquivos: list[Path]) -> list[Path]:
    vistos, unicos = set(), []
    for arquivo in arquivos:
        try:
            assinatura = hashlib.sha256(arquivo.read_bytes()).hexdigest()
        except OSError:
            assinatura = str(arquivo)
        if assinatura not in vistos:
            vistos.add(assinatura)
            unicos.append(arquivo)
    return unicos


def _juntar(lados) -> str:
    return " e ".join(lado for lado in LADOS if lado in lados)


def previa_arquivos(caminhos) -> PreviaHospitalExemplo:
    """Arquivos e/ou pastas escolhidos → "Balancete PF e PJ · HM PF e PJ · 3 PDFs de repasse".

    erro = não dá para gerar (falta o balancete; dois relatórios do mesmo tipo e lado); avisos = dá para gerar,
    mas falta algo ou há arquivo que fica de fora. Nunca levanta exceção.
    """
    try:
        arquivos = _sem_repetidos(_expandir(caminhos))
    except Exception as erro:
        return PreviaHospitalExemplo(erro=f"Não foi possível abrir os arquivos: {erro}")
    if not arquivos:
        return PreviaHospitalExemplo(erro="Nenhum relatório encontrado.")
    balancetes, seniors = Counter(), Counter()
    pdfs, fora, ilegiveis = 0, 0, []
    for arquivo in arquivos:
        try:
            tipo = identificar_arquivo(arquivo)
            if tipo == ARQUIVO_BALANCETE:
                leitura = ler_balancete_hospital_exemplo(arquivo)
                if leitura.erro:
                    ilegiveis.append(arquivo.name)
                balancetes.update(list(leitura.totais))         # conta os lados (PF, PJ)
            elif tipo == ARQUIVO_SENIOR:
                leitura = ler_senior(arquivo)
                if leitura.erro:
                    ilegiveis.append(arquivo.name)
                else:
                    seniors[leitura.lado] += 1
            elif tipo == ARQUIVO_REPASSE_PDF:
                pdfs += 1
            else:
                fora += 1
        except Exception:
            ilegiveis.append(arquivo.name)

    partes = []
    if balancetes:
        partes.append(f"Balancete {_juntar(balancetes)}")
    if seniors:
        partes.append(f"HM {_juntar(seniors)} Senior")
    if pdfs:
        partes.append(_plural(pdfs, "PDF de repasse", "PDFs de repasse"))
    if fora:
        partes.append(_plural(fora, "arquivo fica de fora", "arquivos ficam de fora"))
    previa = PreviaHospitalExemplo(descricao=" · ".join(partes) or "Nenhum relatório reconhecido")

    repetidos = [f"dois balancetes {lado}" for lado, n in balancetes.items() if n > 1]
    repetidos += [f"dois HM {lado} Senior" for lado, n in seniors.items() if n > 1]
    if not balancetes:
        previa.erro = "Falta o balancete de honorários (.xls com a 2131 – PF e/ou a 2132 – PJ)."
    elif repetidos:
        previa.erro = "Há " + " e ".join(repetidos) + "; deixe só um de cada."
    faltando = [f"HM {lado} Senior" for lado in LADOS if lado in balancetes and lado not in seniors]
    faltando += [f"balancete {lado}" for lado in LADOS if lado in seniors and lado not in balancetes and balancetes]
    if not pdfs:
        faltando.append("PDFs de Remoção / 6095 / 6203 (se houver no mês)")
    if faltando:
        previa.avisos.append("Falta: " + ", ".join(faltando))
    if ilegiveis:
        previa.avisos.append("Não puderam ser lidos: " + ", ".join(ilegiveis))
    return previa


# ---------------------------------------------------------------------
# Números da tela
# ---------------------------------------------------------------------
@dataclass(frozen=True)
class NumerosHospitalExemplo:
    linhas: int
    ok: int
    nao_ok: int


def numeros_principais(resultado: ResultadoHospitalExemplo) -> NumerosHospitalExemplo:
    linhas = [l for lado in resultado.lados for l in resultado.linhas.get(lado, [])]
    ok = sum(1 for l in linhas if l.situacao == SITUACAO_OK)
    return NumerosHospitalExemplo(linhas=len(linhas), ok=ok, nao_ok=len(linhas) - ok)
