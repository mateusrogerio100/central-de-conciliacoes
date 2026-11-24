"""
Orquestração da Conciliação Fornecedores: lê os dois relatórios, pareia, gera o Excel.

processar_fornecedores() é a ÚNICA porta de entrada para a interface e nunca levanta exceção:
- relatório ilegível ou trocado, ou arquivos de unidades diferentes → ResultadoFornecedores.erro;
- não conseguiu salvar → ResultadoFornecedores.erro com mensagem clara.

Planilha: Conciliacao_Fornecedores_<Unidade>_<mmmaaaa>.xlsx (ex.: ..._CidadeDelta_set2026.xlsx),
na pasta escolhida (pasta_destino) ou na pasta do balancete; nome repetido ganha _2, _3...
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Callable

from modulos.honorarios_medicos.fornecedores.avisos import NIVEL_ERRO, NIVEL_OK, Aviso
from modulos.honorarios_medicos.fornecedores.leitores import ler_balancete, ler_titulos, mesma_unidade_pelo_nome, nome_curto_unidade, reais
from modulos.honorarios_medicos.fornecedores.modelos import (
    SITUACAO_OK,
    SITUACAO_SO_BALANCETE,
    SITUACAO_SO_RELATORIO,
    TIPO_BALANCETE,
    TIPO_TITULOS,
    LeituraBalancete,
    LeituraTitulos,
    ResultadoFornecedores,
)
from modulos.honorarios_medicos.fornecedores.pareamento import parear
from modulos.honorarios_medicos.fornecedores.relatorio_excel import ABA_TITULOS, gerar_relatorio_fornecedores, mes_curto

PREFIXO_ARQUIVO = "Conciliacao_Fornecedores"
ARQUIVO_CONCILIACAO = "Conciliação"

FuncaoProgresso = Callable[[int, str], None]


def processar_fornecedores(arquivo_balancete: Path, arquivo_titulos: Path,
                           ao_progredir: FuncaoProgresso | None = None,
                           agora: datetime | None = None,
                           pasta_destino: Path | None = None) -> ResultadoFornecedores:
    """Faz a conciliação completa (nunca levanta exceção). pasta_destino None = pasta do balancete."""
    resultado = ResultadoFornecedores()
    try:
        _processar(resultado, Path(arquivo_balancete), Path(arquivo_titulos), ao_progredir,
                   Path(pasta_destino) if pasta_destino else None)
    except Exception as erro:  # rede de segurança: a interface nunca recebe exceção
        resultado.erro = f"Erro inesperado durante a conciliação: {erro}"
    return resultado


def mesma_unidade(balancete: LeituraBalancete, titulos: LeituraTitulos) -> bool | None:
    """Compara só o nome antes do parêntese (o financeiro corta o nome), aceitando um nome mais curto que o
    outro ("Cidade Epsilon" × "Cidade Epsilon"). None = não dá para saber."""
    if not balancete.unidade or not titulos.unidade:
        return None
    return mesma_unidade_pelo_nome(balancete.unidade, titulos.unidade)



def _processar(resultado: ResultadoFornecedores, arquivo_balancete: Path, arquivo_titulos: Path,
               ao_progredir, pasta_destino: Path | None) -> None:
    def progresso(percentual: int, mensagem: str) -> None:
        if ao_progredir is not None:
            ao_progredir(percentual, mensagem)

    avisos = resultado.avisos
    progresso(10, f"Lendo {arquivo_balancete.name}...")
    balancete = ler_balancete(arquivo_balancete)
    progresso(30, f"Lendo {arquivo_titulos.name}...")
    titulos = ler_titulos(arquivo_titulos)
    resultado.arquivo_balancete = balancete.arquivo
    resultado.arquivo_titulos = titulos.arquivo

    for leitura, tipo, quantidade in ((balancete, TIPO_BALANCETE, len(balancete.contas)),
                                      (titulos, TIPO_TITULOS, len(titulos.fornecedores))):
        if leitura.erro:
            avisos.append(Aviso(arquivo=leitura.arquivo, tipo_arquivo=tipo, nivel=NIVEL_ERRO,
                                mensagem=leitura.erro, linhas_lidas=0))
        else:
            avisos.append(Aviso(arquivo=leitura.arquivo, tipo_arquivo=tipo, nivel=NIVEL_OK,
                                mensagem="OK", linhas_lidas=quantidade,
                                unidades=nome_curto_unidade(leitura.unidade)))
            avisos.extend(leitura.avisos)

    problemas = [f"{nome} não pôde ser lido ({leitura.erro})"
                 for nome, leitura in (("o balancete", balancete), ("o relatório de títulos a pagar", titulos))
                 if leitura.erro]
    if not problemas and mesma_unidade(balancete, titulos) is False:
        problemas.append(f"os arquivos são de unidades diferentes (balancete: "
                         f"{nome_curto_unidade(balancete.unidade)}; títulos a pagar: "
                         f"{nome_curto_unidade(titulos.unidade)})")
    if problemas:
        resultado.erro = "Relatório não gerado: " + "; ".join(problemas) + "."
        progresso(100, "Não foi possível fazer a conciliação.")
        return

    resultado.unidade = balancete.unidade
    resultado.mes = balancete.mes
    resultado.total_balancete = balancete.total.saldo_atual
    resultado.total_financeiro = sum((f.saldo for f in titulos.fornecedores), Decimal(0))
    resultado.quantidade_titulos = titulos.quantidade_titulos

    if mesma_unidade(balancete, titulos) is None:
        avisos.append(Aviso(arquivo=ARQUIVO_CONCILIACAO,
                            mensagem="Não deu para conferir se os dois arquivos são da mesma unidade "
                                     "(o nome da unidade não foi encontrado num deles)."))

    progresso(55, "Pareando os fornecedores...")
    # Fornecedor com saldo zero no financeiro não entra na conciliação (fica registrado numa nota)
    com_saldo = [f for f in titulos.fornecedores if f.saldo != 0]
    pareamento = parear(balancete.contas, com_saldo)
    resultado.linhas = pareamento.linhas

    # Prova final: total do balancete − total do financeiro = soma das diferenças
    total_financeiro = resultado.total_financeiro
    soma_diferencas = sum((l.diferenca for l in resultado.linhas), Decimal(0))
    if resultado.total_balancete - total_financeiro != soma_diferencas:
        avisos.append(Aviso(
            arquivo=ARQUIVO_CONCILIACAO,
            mensagem=f"ATENÇÃO: a prova final não fechou — total do balancete − total do financeiro = "
                     f"{reais(resultado.total_balancete - total_financeiro)}, mas a soma das diferenças "
                     f"é {reais(soma_diferencas)}. Pode haver erro de leitura.",
        ))

    resultado.notas = _notas(resultado, pareamento, titulos)

    progresso(80, "Gerando o relatório em Excel...")
    pasta = pasta_destino or arquivo_balancete.parent
    if not pasta.is_dir():
        resultado.erro = (f"A pasta escolhida para salvar a planilha não existe mais: {pasta}. "
                          "Escolha outra pasta e gere de novo.")
        progresso(100, "Relatório não salvo.")
        return
    caminho = caminho_do_relatorio(pasta, resultado.unidade, resultado.mes)
    try:
        resultado.caminho_relatorio = gerar_relatorio_fornecedores(resultado, caminho)
    except PermissionError:
        resultado.erro = (f"Não foi possível salvar o relatório na pasta {caminho.parent}. Verifique se "
                          "você tem permissão para gravar nessa pasta (ou escolha outra) e tente de novo.")
    except OSError as erro:
        resultado.erro = f"Não foi possível salvar o relatório em {caminho}: {erro.strerror or erro}."
    progresso(100, "Concluído." if resultado.erro is None else "Relatório não salvo.")


def _notas(resultado: ResultadoFornecedores, pareamento, titulos: LeituraTitulos) -> list[str]:
    notas = [
        f"'{Path(resultado.arquivo_titulos).stem}' não traz código contábil — o pareamento entre os dois "
        "relatórios foi feito por nome de fornecedor (auditar nomes com confiança baixa na aba "
        "'Conciliação Completa').",
        f"o Relatório Financeiro traz {titulos.quantidade_titulos} títulos agrupados em "
        f"{len(titulos.fornecedores)} fornecedores (total R$ {reais(resultado.total_financeiro)}).",
    ]
    zerados = [f for f in titulos.fornecedores if f.saldo == 0]
    if zerados:
        nomes = ", ".join(f"'{f.nome}'" for f in zerados)
        notas.append(f"{len(zerados)} fornecedor{'es' if len(zerados) > 1 else ''} com saldo zero no financeiro "
                     f"(soma dos títulos = R$ 0,00) não entr{'aram' if len(zerados) > 1 else 'ou'} na "
                     f"conciliação: {nomes}.")
    for linha in pareamento.duplicados:
        repetidos = len({f.nome.casefold() for f in linha.financeiros}) < len(linha.financeiros)
        nomes = " / ".join(f"'{f.nome}'" + (f" CNPJ {f.cnpj}" if repetidos and f.cnpj else "")
                           + f" ({reais(f.saldo)})" for f in linha.financeiros)
        fecho = (" e batem com o Balancete." if linha.situacao == SITUACAO_OK
                 else f" — ainda há diferença de R$ {reais(linha.diferenca)}.")
        notas.append(f"'{linha.conta.descricao}' aparece com {len(linha.financeiros)} cadastros no "
                     f"financeiro ({nomes}); os saldos foram somados (R$ {reais(linha.saldo_financeiro)})"
                     + fecho)
    for linha in pareamento.por_valor:
        notas.append(f"'{linha.conta.descricao}' (Balancete) x '{linha.nome_financeiro}' (financeiro): nomes "
                     f"diferentes, pareados por semelhança de nome + mesmo valor "
                     f"({reais(linha.saldo_balancete)}) — confirmar se é o mesmo fornecedor.")
    reclassificar = [l for l in resultado.linhas
                     if l.situacao == SITUACAO_SO_BALANCETE and l.conta.a_reclassificar]
    if reclassificar:
        total = reais(sum((l.saldo_balancete for l in reclassificar), Decimal(0)))
        if len(reclassificar) == 1:
            notas.append(f"a conta '{reclassificar[0].conta.descricao}' soma R$ {total} no Balancete e "
                         "não tem correspondente no financeiro.")
        else:
            notas.append(f"as {len(reclassificar)} contas 'Fornecedores a reclassificar' somam R$ {total} "
                         "no Balancete e não têm correspondente no financeiro.")
    so_financeiro = [l for l in resultado.linhas if l.situacao == SITUACAO_SO_RELATORIO]
    if so_financeiro:
        total = reais(sum((l.saldo_financeiro for l in so_financeiro), Decimal(0)))
        plural = "fornecedores com saldo no financeiro não têm" if len(so_financeiro) > 1 else \
            "fornecedor com saldo no financeiro não tem"
        notas.append(f"{len(so_financeiro)} {plural} conta no Balancete (total R$ {total}).")
    if any(l.financeiros for l in resultado.linhas if l.situacao != SITUACAO_OK):
        notas.append(f"os títulos dos fornecedores com diferença (Nr. Doc. e Nr. Título, para procurar no "
                     f"Tasy) estão na aba '{ABA_TITULOS}'.")
    # Avisos que merecem ficar registrados na própria planilha
    for aviso in resultado.avisos:
        if not aviso.tipo_arquivo and "ATENÇÃO" in aviso.mensagem:
            notas.append(aviso.mensagem)
    return notas


# ---------------------------------------------------------------------
# Nome do arquivo
# ---------------------------------------------------------------------
def unidade_para_arquivo(unidade: str) -> str:
    """"AME - Cidade Delta (Fund. ...)" → "CidadeDelta"; "Ame - Vale Zeta (...)" → "ValeZeta"."""
    curto = nome_curto_unidade(unidade)
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
class NumerosFornecedores:
    linhas: int
    ok: int
    nao_ok: int


def numeros_principais(resultado: ResultadoFornecedores) -> NumerosFornecedores:
    ok = sum(1 for l in resultado.linhas if l.situacao == SITUACAO_OK)
    return NumerosFornecedores(linhas=len(resultado.linhas), ok=ok, nao_ok=len(resultado.linhas) - ok)


@dataclass
class PreviaFornecedores:
    descricao: str = ""
    erro: str | None = None
    avisos: list[str] = field(default_factory=list)


def previa_balancete(arquivo: Path) -> PreviaFornecedores:
    leitura = ler_balancete(Path(arquivo))
    if leitura.erro:
        return PreviaFornecedores(erro=leitura.erro)
    partes = [nome_curto_unidade(leitura.unidade) or "unidade não encontrada",
              mes_curto(leitura.mes) or "mês não encontrado",
              f"{len(leitura.contas)} contas", f"R$ {reais(leitura.total.saldo_atual)}"]
    return PreviaFornecedores(descricao=" · ".join(partes), avisos=[a.mensagem for a in leitura.avisos])


def previa_titulos(arquivo: Path) -> PreviaFornecedores:
    leitura = ler_titulos(Path(arquivo))
    if leitura.erro:
        return PreviaFornecedores(erro=leitura.erro)
    total = sum((f.saldo for f in leitura.fornecedores), Decimal(0))
    partes = [nome_curto_unidade(leitura.unidade) or "unidade não encontrada",
              f"{leitura.quantidade_titulos} títulos", f"{len(leitura.fornecedores)} fornecedores",
              f"R$ {reais(total)}"]
    return PreviaFornecedores(descricao=" · ".join(partes), avisos=[a.mensagem for a in leitura.avisos])


def conferir_par(arquivo_balancete: Path, arquivo_titulos: Path) -> PreviaFornecedores:
    """Depois de escolher os dois: erro se forem de unidades diferentes."""
    balancete, titulos = ler_balancete(Path(arquivo_balancete)), ler_titulos(Path(arquivo_titulos))
    if balancete.erro or titulos.erro:
        return PreviaFornecedores()
    if mesma_unidade(balancete, titulos) is False:
        return PreviaFornecedores(erro=f"Os arquivos são de unidades diferentes: balancete "
                                       f"{nome_curto_unidade(balancete.unidade)}, títulos a pagar "
                                       f"{nome_curto_unidade(titulos.unidade)}.")
    return PreviaFornecedores()
