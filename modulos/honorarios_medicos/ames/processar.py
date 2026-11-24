"""
Orquestração da Conciliação Honorários: lê os dois relatórios, pareia, gera o Excel.

processar_honorarios() é a ÚNICA porta de entrada para a interface e nunca levanta exceção:
- relatório ilegível ou trocado, ou arquivos de unidades diferentes → ResultadoHonorarios.erro;
- não conseguiu salvar → ResultadoHonorarios.erro com mensagem clara.

Planilha: Conciliacao_HonorariosMedicos_<Unidade>_<mmmaaaa>.xlsx (ex.: ..._CidadeDelta_set2026.xlsx),
na pasta escolhida (pasta_destino) ou na pasta do balancete; nome repetido ganha _2, _3...
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Callable

from modulos.honorarios_medicos.fornecedores.avisos import NIVEL_ERRO, NIVEL_OK, Aviso
from modulos.honorarios_medicos.fornecedores.leitores import mesma_unidade_pelo_nome
from modulos.honorarios_medicos.fornecedores.processar import unidade_para_arquivo
from modulos.honorarios_medicos.ames.leitores import ler_balancete, ler_repasse, nome_curto_unidade, reais
from modulos.honorarios_medicos.ames.modelos import (
    SITUACAO_OK,
    SITUACAO_SO_BALANCETE,
    SITUACAO_SO_REPASSE,
    TIPO_BALANCETE,
    TIPO_REPASSE,
    LeituraBalancete,
    LeituraRepasse,
    ResultadoHonorarios,
)
from modulos.honorarios_medicos.ames.pareamento import agrupar_terceiros, parear_honorarios
from modulos.honorarios_medicos.ames.relatorio_excel import gerar_relatorio_honorarios, mes_curto

PREFIXO_ARQUIVO = "Conciliacao_HonorariosMedicos"
ARQUIVO_CONCILIACAO = "Conciliação"

FuncaoProgresso = Callable[[int, str], None]


def processar_honorarios(arquivo_balancete: Path, arquivo_repasse: Path,
                         ao_progredir: FuncaoProgresso | None = None,
                         agora: datetime | None = None,
                         pasta_destino: Path | None = None) -> ResultadoHonorarios:
    """Faz a conciliação completa (nunca levanta exceção). pasta_destino None = pasta do balancete."""
    resultado = ResultadoHonorarios()
    try:
        _processar(resultado, Path(arquivo_balancete), Path(arquivo_repasse), ao_progredir,
                   Path(pasta_destino) if pasta_destino else None)
    except Exception as erro:  # rede de segurança: a interface nunca recebe exceção
        resultado.erro = f"Erro inesperado durante a conciliação: {erro}"
    return resultado



def mesma_unidade(balancete: LeituraBalancete, repasse: LeituraRepasse) -> bool | None:
    """Compara só o nome antes do parêntese, aceitando um nome mais curto que o outro (o balancete diz "Ame -
    Cidade Epsilon" e o repasse "AME - Cidade Epsilon"). None = não dá para saber."""
    if not balancete.unidade or not repasse.unidade:
        return None
    return mesma_unidade_pelo_nome(balancete.unidade, repasse.unidade)


def _processar(resultado: ResultadoHonorarios, arquivo_balancete: Path, arquivo_repasse: Path,
               ao_progredir, pasta_destino: Path | None) -> None:
    def progresso(percentual: int, mensagem: str) -> None:
        if ao_progredir is not None:
            ao_progredir(percentual, mensagem)

    avisos = resultado.avisos
    progresso(10, f"Lendo {arquivo_balancete.name}...")
    balancete = ler_balancete(arquivo_balancete)
    progresso(30, f"Lendo {arquivo_repasse.name}...")
    repasse = ler_repasse(arquivo_repasse)
    resultado.arquivo_balancete = balancete.arquivo
    resultado.arquivo_repasse = repasse.arquivo

    for leitura, tipo, quantidade in ((balancete, TIPO_BALANCETE, len(balancete.contas)),
                                      (repasse, TIPO_REPASSE, len(repasse.repasses))):
        if leitura.erro:
            avisos.append(Aviso(arquivo=leitura.arquivo, tipo_arquivo=tipo, nivel=NIVEL_ERRO,
                                mensagem=leitura.erro, linhas_lidas=0))
        else:
            avisos.append(Aviso(arquivo=leitura.arquivo, tipo_arquivo=tipo, nivel=NIVEL_OK,
                                mensagem="OK", linhas_lidas=quantidade,
                                unidades=nome_curto_unidade(leitura.unidade)))
            avisos.extend(leitura.avisos)

    problemas = [f"{nome} não pôde ser lido ({leitura.erro})"
                 for nome, leitura in (("o balancete", balancete), ("o repasse médico", repasse))
                 if leitura.erro]
    if not problemas and mesma_unidade(balancete, repasse) is False:
        problemas.append(f"os arquivos são de unidades diferentes (balancete: "
                         f"{nome_curto_unidade(balancete.unidade)}; repasse: "
                         f"{nome_curto_unidade(repasse.unidade)})")
    if problemas:
        resultado.erro = "Relatório não gerado: " + "; ".join(problemas) + "."
        progresso(100, "Não foi possível fazer a conciliação.")
        return

    resultado.unidade = balancete.unidade
    resultado.mes = balancete.mes or repasse.mes
    resultado.conta_total = balancete.total
    resultado.total_balancete = balancete.total.saldo_atual
    resultado.repasses = repasse.repasses
    resultado.grupos = repasse.grupos
    resultado.total_repasse = repasse.total_bruto
    resultado.total_liquido = repasse.total_liquido

    if mesma_unidade(balancete, repasse) is None:
        avisos.append(Aviso(arquivo=ARQUIVO_CONCILIACAO,
                            mensagem="Não deu para conferir se os dois arquivos são da mesma unidade "
                                     "(o nome da unidade não foi encontrado num deles)."))
    if balancete.mes and repasse.mes and balancete.mes != repasse.mes:
        avisos.append(Aviso(arquivo=ARQUIVO_CONCILIACAO,
                            mensagem=f"ATENÇÃO: o balancete é de {mes_curto(balancete.mes)}, mas o repasse "
                                     f"é de {mes_curto(repasse.mes)}. Confira se os arquivos são do mesmo mês."))

    progresso(55, "Pareando os médicos e clínicas...")
    terceiros = agrupar_terceiros(repasse.repasses)
    pareamento = parear_honorarios(balancete.contas, terceiros)
    # Conta com saldo zero e sem repasse não entra na conciliação (fica registrada numa nota)
    zeradas = [l for l in pareamento.linhas
               if l.situacao == SITUACAO_SO_BALANCETE and l.saldo_balancete == 0]
    resultado.linhas = [l for l in pareamento.linhas if l not in zeradas]
    for linha in resultado.linhas:
        if linha.conta is not None:
            for terceiro in linha.terceiros:
                for r in terceiro.repasses:
                    resultado.conta_do_repasse[id(r)] = linha.conta.codigo

    # Prova final: total do balancete − total do repasse = soma das diferenças
    soma_diferencas = sum((l.diferenca for l in resultado.linhas), Decimal(0))
    if resultado.total_balancete - resultado.total_repasse != soma_diferencas:
        avisos.append(Aviso(
            arquivo=ARQUIVO_CONCILIACAO,
            mensagem=f"ATENÇÃO: a prova final não fechou — total do balancete − total do repasse = "
                     f"{reais(resultado.total_balancete - resultado.total_repasse)}, mas a soma das "
                     f"diferenças é {reais(soma_diferencas)}. Pode haver erro de leitura.",
        ))

    resultado.notas = _notas(resultado, pareamento, terceiros, balancete, zeradas)

    progresso(80, "Gerando o relatório em Excel...")
    pasta = pasta_destino or arquivo_balancete.parent
    if not pasta.is_dir():
        resultado.erro = (f"A pasta escolhida para salvar a planilha não existe mais: {pasta}. "
                          "Escolha outra pasta e gere de novo.")
        progresso(100, "Relatório não salvo.")
        return
    caminho = caminho_do_relatorio(pasta, resultado.unidade, resultado.mes)
    try:
        resultado.caminho_relatorio = gerar_relatorio_honorarios(resultado, caminho)
    except PermissionError:
        resultado.erro = (f"Não foi possível salvar o relatório na pasta {caminho.parent}. Verifique se "
                          "você tem permissão para gravar nessa pasta (ou escolha outra) e tente de novo.")
    except OSError as erro:
        resultado.erro = f"Não foi possível salvar o relatório em {caminho}: {erro.strerror or erro}."
    progresso(100, "Concluído." if resultado.erro is None else "Relatório não salvo.")


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _notas(resultado: ResultadoHonorarios, pareamento, terceiros, balancete: LeituraBalancete,
           zeradas) -> list[str]:
    grupos = resultado.grupos
    notas = [
        "o relatório de Repasse não traz código contábil — o pareamento foi feito por nome do terceiro "
        "(ver 'Confiança do Pareamento' na aba 'Conciliação Completa').",
        f"o Repasse traz {_plural(len(resultado.repasses), 'repasse', 'repasses')} de "
        f"{_plural(len(terceiros), 'terceiro', 'terceiros')}, em {_plural(len(grupos), 'grupo', 'grupos')} "
        f"({', '.join(grupos)}); o valor do Balancete foi comparado com a SOMA dos grupos de cada "
        "terceiro, pelo valor BRUTO (Vl repasse).",
    ]
    varios = [t for t in terceiros if len(t.repasses) > 1]
    if varios:
        texto = (f"{_plural(len(varios), 'terceiro tem', 'terceiros têm')} mais de um repasse no mês "
                 "(ex.: Produção + Deslocamento)")
        repetidos = []
        for t in varios:
            for grupo, quantidade in Counter(r.grupo for r in t.repasses).items():
                if quantidade > 1:
                    repetidos.append(f"{t.nome} tem {quantidade} repasses de {grupo}")
        notas.append(texto + ("; " + "; ".join(repetidos) if repetidos else "") + ".")
    com_retencao = [g for g in grupos
                    if any(r.retencao != 0 for r in resultado.repasses if r.grupo == g)]
    if com_retencao:
        notas.append(f"a diferença entre bruto e líquido (aba 'Repasses (detalhe)', coluna Retenções) "
                     f"corresponde aos descontos/retenções do repasse (R$ "
                     f"{reais(resultado.total_repasse - resultado.total_liquido)}, em "
                     f"{', '.join(com_retencao)}); o saldo contábil da conta {resultado.conta_total.codigo} "
                     "está pelo valor bruto.")
    total = balancete.total
    if total.saldo_anterior != 0:
        if total.debitos == total.saldo_anterior:
            notas.append(f"o saldo anterior do Balancete (R$ {reais(total.saldo_anterior)}) foi totalmente "
                         f"baixado em débitos no mês; o saldo atual é formado só pelos créditos de "
                         f"{mes_curto(resultado.mes)}.")
        else:
            notas.append(f"o saldo anterior do Balancete (R$ {reais(total.saldo_anterior)}) teve R$ "
                         f"{reais(total.debitos)} de débitos no mês: o saldo atual não é formado só pelos "
                         f"créditos de {mes_curto(resultado.mes)} (créditos R$ {reais(total.creditos)}).")
    status = Counter(r.status for r in resultado.repasses)
    if len(status) > 1:
        notas.append("o Repasse traz repasses com mais de um status: "
                     + ", ".join(f"'{s}' ({n})" for s, n in sorted(status.items())) + ".")
    for linha in pareamento.duplicados:
        nomes = " / ".join(f"'{t.nome}' ({reais(t.bruto)})" for t in linha.terceiros)
        notas.append(f"'{linha.conta.descricao}' aparece com {len(linha.terceiros)} nomes no Repasse "
                     f"({nomes}); os valores foram somados (R$ {reais(linha.total_repasse)}).")
    for linha in pareamento.por_valor:
        notas.append(f"'{linha.conta.descricao}' (Balancete) x '{linha.nome_repasse}' (Repasse): nomes "
                     f"diferentes, pareados por semelhança de nome + mesmo valor "
                     f"({reais(linha.saldo_balancete)}) — confirmar se é o mesmo médico/clínica.")
    if zeradas:
        nomes = ", ".join(f"'{l.conta.descricao}'" for l in zeradas)
        notas.append(f"{_plural(len(zeradas), 'conta', 'contas')} com saldo zero no Balancete e sem repasse "
                     f"no mês {'não entrou' if len(zeradas) == 1 else 'não entraram'} na conciliação: {nomes}.")
    so_balancete = [l for l in resultado.linhas if l.situacao == SITUACAO_SO_BALANCETE]
    if so_balancete:
        notas.append(f"{_plural(len(so_balancete), 'conta do Balancete não tem', 'contas do Balancete não têm')} "
                     f"repasse no mês (total R$ "
                     f"{reais(sum((l.saldo_balancete for l in so_balancete), Decimal(0)))}).")
    so_repasse = [l for l in resultado.linhas if l.situacao == SITUACAO_SO_REPASSE]
    if so_repasse:
        notas.append(f"{_plural(len(so_repasse), 'terceiro do Repasse não tem', 'terceiros do Repasse não têm')} "
                     f"conta no Balancete (total R$ "
                     f"{reais(sum((l.total_repasse for l in so_repasse), Decimal(0)))}).")
    for aviso in resultado.avisos:
        if "ATENÇÃO" in aviso.mensagem:
            notas.append(aviso.mensagem)
    return notas


# ---------------------------------------------------------------------
# Nome do arquivo
# ---------------------------------------------------------------------
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
class NumerosHonorarios:
    linhas: int
    ok: int
    nao_ok: int


def numeros_principais(resultado: ResultadoHonorarios) -> NumerosHonorarios:
    ok = sum(1 for l in resultado.linhas if l.situacao == SITUACAO_OK)
    return NumerosHonorarios(linhas=len(resultado.linhas), ok=ok, nao_ok=len(resultado.linhas) - ok)


@dataclass
class PreviaHonorarios:
    descricao: str = ""
    erro: str | None = None
    avisos: list[str] = field(default_factory=list)


def previa_balancete(arquivo: Path) -> PreviaHonorarios:
    leitura = ler_balancete(Path(arquivo))
    if leitura.erro:
        return PreviaHonorarios(erro=leitura.erro)
    partes = [nome_curto_unidade(leitura.unidade) or "unidade não encontrada",
              mes_curto(leitura.mes) or "mês não encontrado",
              f"conta {leitura.total.codigo}", f"{len(leitura.contas)} contas",
              f"R$ {reais(leitura.total.saldo_atual)}"]
    return PreviaHonorarios(descricao=" · ".join(partes), avisos=[a.mensagem for a in leitura.avisos])


def previa_repasse(arquivo: Path) -> PreviaHonorarios:
    leitura = ler_repasse(Path(arquivo))
    if leitura.erro:
        return PreviaHonorarios(erro=leitura.erro)
    terceiros = agrupar_terceiros(leitura.repasses)
    partes = [nome_curto_unidade(leitura.unidade) or "unidade não encontrada",
              mes_curto(leitura.mes) or "mês não encontrado",
              f"{len(leitura.repasses)} repasses", f"{len(terceiros)} terceiros",
              f"R$ {reais(leitura.total_bruto)}"]
    return PreviaHonorarios(descricao=" · ".join(partes), avisos=[a.mensagem for a in leitura.avisos])


def conferir_par(arquivo_balancete: Path, arquivo_repasse: Path) -> PreviaHonorarios:
    """Depois de escolher os dois: erro se forem de unidades diferentes; aviso se de meses diferentes."""
    balancete, repasse = ler_balancete(Path(arquivo_balancete)), ler_repasse(Path(arquivo_repasse))
    if balancete.erro or repasse.erro:
        return PreviaHonorarios()
    if mesma_unidade(balancete, repasse) is False:
        return PreviaHonorarios(erro=f"Os arquivos são de unidades diferentes: balancete "
                                     f"{nome_curto_unidade(balancete.unidade)}, repasse "
                                     f"{nome_curto_unidade(repasse.unidade)}.")
    if balancete.mes and repasse.mes and balancete.mes != repasse.mes:
        return PreviaHonorarios(avisos=[f"O balancete é de {mes_curto(balancete.mes)}, mas o repasse é de "
                                        f"{mes_curto(repasse.mes)}."])
    return PreviaHonorarios()
