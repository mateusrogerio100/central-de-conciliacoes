"""
Orquestração da Conciliação do Imobilizado – AME's: lê os arquivos, compara, gera o Excel.

processar_bens() é a ÚNICA porta de entrada para a interface e nunca levanta exceção:
- arquivo com problema → registro de erro na aba Avisos e o resto continua;
- sem o patrimônio ou sem nenhum balancete lido → ResultadoBens.erro;
- não conseguiu salvar o .xlsx → ResultadoBens.erro com mensagem clara.

A planilha é gravada na pasta escolhida pelo usuário (pasta_destino) ou, se nenhuma foi
escolhida, na pasta do Razão auxiliar do patrimônio, com o nome
Conciliacao_imobilizado_<AAAA-MM>_<AME>_<HHhMM>.xlsx.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from modulos.conciliacao_imobilizado.base_iss import NIVEL_AVISO, NIVEL_ERRO, NIVEL_OK, Aviso
from modulos.conciliacao_imobilizado.base_iss import caminho_do_relatorio
from modulos.conciliacao_imobilizado.conciliador import ARQUIVO_CONCILIACAO, conciliar, ligar_baixas_as_contas
from modulos.conciliacao_imobilizado.leitor_baixas import ler_baixas
from modulos.conciliacao_imobilizado.leitor_balancete import ler_balancete
from modulos.conciliacao_imobilizado.leitor_bens_adquiridos import ler_bens_adquiridos
from modulos.conciliacao_imobilizado.leitor_razao import ler_razao
from modulos.conciliacao_imobilizado.leitor_texto import (
    competencia_de_data,
    competencia_por_extenso,
    juntar_espacos,
    nome_curto_ame,
    reais,
)
from modulos.conciliacao_imobilizado.modelos import (
    TIPO_BAIXAS,
    TIPO_BALANCETE,
    TIPO_BENS_ADQUIRIDOS,
    TIPO_RAZAO,
    ResultadoBens,
)
from modulos.conciliacao_imobilizado.relatorio_excel import gerar_relatorio_bens
from modulos.conciliacao_imobilizado.resumo import diferencas_pendentes, relatorios_que_ajudariam

PREFIXO_ARQUIVO = "Conciliacao_imobilizado"

FuncaoProgresso = Callable[[int, str], None]


def processar_bens(arquivo_razao: Path, arquivos_balancete: list[Path],
                   arquivo_bens_adquiridos: Path | None = None,
                   arquivo_baixas: Path | None = None,
                   ao_progredir: FuncaoProgresso | None = None,
                   agora: datetime | None = None,
                   pasta_destino: Path | None = None) -> ResultadoBens:
    """
    Faz a conciliação completa e devolve o ResultadoBens (nunca levanta exceção).

    pasta_destino: onde salvar a planilha (None = pasta do arquivo do patrimônio).
    """
    resultado = ResultadoBens()
    try:
        _processar(resultado, Path(arquivo_razao), [Path(a) for a in arquivos_balancete],
                   Path(arquivo_bens_adquiridos) if arquivo_bens_adquiridos else None,
                   Path(arquivo_baixas) if arquivo_baixas else None,
                   ao_progredir, agora or datetime.now(),
                   Path(pasta_destino) if pasta_destino else None)
    except Exception as erro:  # rede de segurança: a interface nunca recebe exceção
        resultado.erro = f"Erro inesperado durante a conciliação: {erro}"
    return resultado


def _chave_ame(ame: str) -> str:
    return juntar_espacos(ame).casefold()


def _processar(resultado: ResultadoBens, arquivo_razao: Path, arquivos_balancete: list[Path],
               arquivo_bens: Path | None, arquivo_baixas: Path | None,
               ao_progredir, agora: datetime, pasta_destino: Path | None = None) -> None:
    def progresso(percentual: int, mensagem: str) -> None:
        if ao_progredir is not None:
            ao_progredir(percentual, mensagem)

    avisos = resultado.avisos

    # 1) Razão auxiliar do patrimônio
    progresso(5, f"Lendo {arquivo_razao.name}...")
    razao = ler_razao(arquivo_razao)
    if razao.erro:
        avisos.append(Aviso(arquivo=razao.arquivo, tipo_arquivo=TIPO_RAZAO, nivel=NIVEL_ERRO,
                            mensagem=razao.erro, linhas_lidas=0))
    else:
        avisos.append(Aviso(arquivo=razao.arquivo, tipo_arquivo=TIPO_RAZAO, nivel=NIVEL_OK,
                            mensagem="OK", linhas_lidas=len(razao.contas)))
        avisos.extend(razao.avisos)

    # 2) Balancetes
    contas_balancete = []
    ames: dict[str, str] = {}                # chave → nome como veio
    competencias: dict[str, list[str]] = {}  # competência → arquivos
    vistos: set[Path] = set()
    total = max(len(arquivos_balancete), 1)
    for posicao, arquivo in enumerate(arquivos_balancete):
        progresso(15 + 30 * posicao // total, f"Lendo {arquivo.name}...")
        chave = _chave_caminho(arquivo)
        if chave in vistos:
            avisos.append(Aviso(arquivo=arquivo.name, tipo_arquivo=TIPO_BALANCETE,
                                nivel=NIVEL_AVISO,
                                mensagem="Arquivo selecionado mais de uma vez; a cópia repetida "
                                         "foi ignorada."))
            continue
        vistos.add(chave)
        leitura = ler_balancete(arquivo)
        if leitura.erro:
            avisos.append(Aviso(arquivo=leitura.arquivo, tipo_arquivo=TIPO_BALANCETE,
                                nivel=NIVEL_ERRO, mensagem=leitura.erro, linhas_lidas=0))
            continue
        avisos.append(Aviso(arquivo=leitura.arquivo, tipo_arquivo=TIPO_BALANCETE, nivel=NIVEL_OK,
                            mensagem="OK", linhas_lidas=len(leitura.contas),
                            unidades=nome_curto_ame(leitura.ame)))
        avisos.extend(leitura.avisos)
        contas_balancete.extend(leitura.contas)
        resultado.contas_maes.extend(c for c in leitura.contas if c.sintetica)
        if leitura.ame:
            ames.setdefault(_chave_ame(leitura.ame), leitura.ame)
        if leitura.competencia:
            competencias.setdefault(leitura.competencia, []).append(leitura.arquivo)

    problemas = []
    if razao.erro:
        problemas.append(f"o Razão auxiliar do patrimônio não pôde ser lido ({razao.erro})")
    if not contas_balancete:
        problemas.append("nenhum balancete pôde ser lido (veja os avisos)")
    if problemas:
        resultado.erro = "Relatório não gerado: " + "; ".join(problemas) + "."
        progresso(100, "Não foi possível fazer a conciliação.")
        return

    # AME e mês (vêm dos balancetes)
    if ames:
        resultado.ame = nome_curto_ame(next(iter(ames.values())))
    if len(ames) > 1:
        avisos.append(Aviso(
            arquivo=ARQUIVO_CONCILIACAO, nivel=NIVEL_AVISO,
            mensagem="ATENÇÃO: os balancetes são de AMEs diferentes ("
                     + "; ".join(nome_curto_ame(a) for a in ames.values())
                     + "). Confira se escolheu os arquivos do mesmo AME.",
        ))
    if competencias:
        resultado.competencia = next(iter(competencias))
        resultado.competencia_texto = competencia_por_extenso(resultado.competencia)
    if len(competencias) > 1:
        detalhes = "; ".join(f"{competencia_por_extenso(c)}: {', '.join(a)}"
                             for c, a in competencias.items())
        avisos.append(Aviso(
            arquivo=ARQUIVO_CONCILIACAO,
            mensagem=f"ATENÇÃO: os balancetes são de meses diferentes ({detalhes}).",
        ))
    mes_razao = competencia_de_data(razao.data_referencia)
    if resultado.competencia and mes_razao and mes_razao != resultado.competencia:
        avisos.append(Aviso(
            arquivo=razao.arquivo,
            mensagem=f"ATENÇÃO: o patrimônio é de {competencia_por_extenso(mes_razao)}, mas os "
                     f"balancetes são de {resultado.competencia_texto}.",
        ))

    # 3) Opcionais: bens adquiridos e baixas
    bens_adquiridos = None
    if arquivo_bens is not None:
        progresso(50, f"Lendo {arquivo_bens.name}...")
        leitura_bens = ler_bens_adquiridos(arquivo_bens)
        if leitura_bens.erro:
            avisos.append(Aviso(arquivo=leitura_bens.arquivo, tipo_arquivo=TIPO_BENS_ADQUIRIDOS,
                                nivel=NIVEL_ERRO, mensagem=leitura_bens.erro, linhas_lidas=0))
        else:
            bens_adquiridos = leitura_bens.bens
            resultado.bens_adquiridos = leitura_bens.bens
            resultado.leu_bens_adquiridos = True
            avisos.append(Aviso(arquivo=leitura_bens.arquivo, tipo_arquivo=TIPO_BENS_ADQUIRIDOS,
                                nivel=NIVEL_OK, mensagem="OK", linhas_lidas=len(leitura_bens.bens)))
            avisos.extend(leitura_bens.avisos)
            meses = {competencia_de_data(leitura_bens.periodo_inicio),
                     competencia_de_data(leitura_bens.periodo_fim)} - {""}
            if resultado.competencia and meses and meses != {resultado.competencia}:
                avisos.append(Aviso(
                    arquivo=leitura_bens.arquivo,
                    mensagem="ATENÇÃO: o período dos bens adquiridos ("
                             f"{leitura_bens.periodo_inicio:%d/%m/%Y} a "
                             f"{leitura_bens.periodo_fim:%d/%m/%Y}) não é o mês dos balancetes "
                             f"({resultado.competencia_texto}).",
                ))

    bens_baixados = None
    if arquivo_baixas is not None:
        progresso(60, f"Lendo {arquivo_baixas.name}...")
        leitura_baixas = ler_baixas(arquivo_baixas)
        if leitura_baixas.erro:
            avisos.append(Aviso(arquivo=leitura_baixas.arquivo, tipo_arquivo=TIPO_BAIXAS,
                                nivel=NIVEL_ERRO, mensagem=leitura_baixas.erro, linhas_lidas=0))
        else:
            bens_baixados = leitura_baixas.bens
            resultado.bens_baixados = leitura_baixas.bens
            resultado.leu_baixas = True
            avisos.append(Aviso(arquivo=leitura_baixas.arquivo, tipo_arquivo=TIPO_BAIXAS,
                                nivel=NIVEL_OK, mensagem="OK",
                                linhas_lidas=len(leitura_baixas.bens),
                                unidades=nome_curto_ame(leitura_baixas.ame)))
            avisos.extend(leitura_baixas.avisos)
            ame_principal = next(iter(ames), None)
            if ame_principal and leitura_baixas.ame and _chave_ame(leitura_baixas.ame) != ame_principal:
                avisos.append(Aviso(
                    arquivo=leitura_baixas.arquivo,
                    mensagem=f"ATENÇÃO: o relatório de baixas é do {nome_curto_ame(leitura_baixas.ame)}"
                             f", mas os balancetes são do {resultado.ame}.",
                ))
            fora_do_mes = [b for b in leitura_baixas.bens
                           if b.data and resultado.competencia
                           and competencia_de_data(b.data) != resultado.competencia]
            if fora_do_mes:
                avisos.append(Aviso(
                    arquivo=leitura_baixas.arquivo,
                    mensagem=f"ATENÇÃO: {len(fora_do_mes)} baixa(s) com data fora de "
                             f"{resultado.competencia_texto} (ex.: {fora_do_mes[0].chapa} em "
                             f"{fora_do_mes[0].data:%d/%m/%Y}).",
                ))
            avisos.extend(ligar_baixas_as_contas(leitura_baixas.bens, razao.contas,
                                                 contas_balancete))

    # 4) Comparação
    progresso(70, "Comparando as contas...")
    conciliacao = conciliar(razao.contas, contas_balancete, bens_adquiridos, bens_baixados)
    resultado.itens = conciliacao.itens
    avisos.extend(conciliacao.avisos)
    _avisos_patrimonio_nao_fecha(resultado, razao.arquivo)
    _aviso_faltam_opcionais(resultado)

    # 5) Excel
    progresso(85, "Gerando o relatório em Excel...")
    pasta = pasta_destino or arquivo_razao.parent
    if not pasta.is_dir():
        resultado.erro = (f"A pasta escolhida para salvar a planilha não existe mais: {pasta}. "
                          "Escolha outra pasta e gere de novo.")
        progresso(100, "Relatório não salvo.")
        return
    unidade = resultado.ame.replace(" - ", " ")
    caminho = caminho_do_relatorio(pasta, resultado.competencia,
                                   [unidade] if unidade else [], agora, prefixo=PREFIXO_ARQUIVO)
    try:
        resultado.caminho_relatorio = gerar_relatorio_bens(resultado, caminho, gerado_em=agora)
    except PermissionError:
        resultado.erro = (
            f"Não foi possível salvar o relatório na pasta {caminho.parent}. "
            "Verifique se você tem permissão para gravar nessa pasta "
            "(ou escolha outra pasta para salvar a planilha) e tente de novo."
        )
    except OSError as erro:
        resultado.erro = f"Não foi possível salvar o relatório em {caminho}: {erro.strerror or erro}."
    progresso(100, "Concluído." if resultado.erro is None else "Relatório não salvo.")


def _avisos_patrimonio_nao_fecha(resultado: ResultadoBens, arquivo: str) -> None:
    """
    Conta do patrimônio em que saldo anterior + entradas − baixas ± transferências ≠ saldo atual
    (decisão do usuário: avisar). Se a diferença for igual às baixas ou entradas lidas nos
    relatórios opcionais, o aviso diz isso (ex.: linha "Baixas" do 6051 veio zerada).
    """
    for item in resultado.itens:
        conta = item.conta_patrimonio
        diferenca = None if conta is None else conta.diferenca_movimento
        if not diferenca:
            continue
        mensagem = (f"No patrimônio, a conta {conta.codigo} - {conta.nome} não fecha: saldo "
                    "anterior + entradas − baixas ± transferências ≠ saldo atual "
                    f"(diferença {reais(diferenca)}).")
        if item.baixas and abs(diferenca) == item.baixas:
            mensagem += (f" O valor é igual às baixas da conta no relatório de baixa de bens "
                         f"({reais(item.baixas)}): a linha \"Baixas\" do patrimônio pode ter vindo "
                         "sem elas.")
        elif item.entradas and abs(diferenca) == item.entradas:
            mensagem += (f" O valor é igual aos bens adquiridos da conta ({reais(item.entradas)}): "
                         "a linha \"Entradas\" do patrimônio pode ter vindo sem eles.")
        resultado.avisos.append(Aviso(arquivo=arquivo, mensagem=mensagem))


def _aviso_faltam_opcionais(resultado: ResultadoBens) -> None:
    """Há diferença sem explicação e falta relatório de movimento → sugere selecionar."""
    faltando = relatorios_que_ajudariam(resultado)
    if not faltando:
        return
    pendentes = diferencas_pendentes(resultado)
    contas = "; ".join(f"{i.codigo} - {i.nome} ({reais(i.diferenca)})" for i in pendentes)
    resultado.avisos.append(Aviso(
        arquivo=ARQUIVO_CONCILIACAO,
        mensagem=f"{len(pendentes)} conta(s) com diferença: {contas}. Se houve entrada ou baixa "
                 f"de bens no mês, selecione {' e '.join(faltando)} e gere de novo para o "
                 "programa tentar explicar.",
    ))


def _chave_caminho(caminho: Path) -> Path:
    try:
        return caminho.resolve()
    except OSError:
        return caminho.absolute()


# ---------------------------------------------------------------------
# Prévias (confirmação na tela logo depois de escolher os arquivos)
# ---------------------------------------------------------------------
@dataclass
class PreviaBens:
    """O que a tela mostra embaixo de cada campo: "ok" ou o erro."""

    descricao: str = ""                  # ex.: "Ame - Cidade Alfa · agosto/2026 · 6 contas"
    erro: str | None = None
    avisos: list[str] = field(default_factory=list)


def previa_razao(arquivo: Path) -> PreviaBens:
    leitura = ler_razao(Path(arquivo))
    if leitura.erro:
        return PreviaBens(erro=leitura.erro)
    mes = competencia_por_extenso(competencia_de_data(leitura.data_referencia)) or "mês não encontrado"
    return PreviaBens(descricao=f"{mes} · {len(leitura.contas)} contas",
                      avisos=[a.mensagem for a in leitura.avisos])


def previa_balancetes(arquivos: list[Path]) -> PreviaBens:
    contas, ames, meses, erros = 0, [], [], []
    for arquivo in arquivos:
        leitura = ler_balancete(Path(arquivo))
        if leitura.erro:
            erros.append(f"{leitura.arquivo}: {leitura.erro}")
            continue
        contas += sum(1 for c in leitura.contas if not c.sintetica)
        if leitura.ame and nome_curto_ame(leitura.ame) not in ames:
            ames.append(nome_curto_ame(leitura.ame))
        if leitura.competencia and leitura.competencia not in meses:
            meses.append(leitura.competencia)
    if erros and not contas:
        return PreviaBens(erro="; ".join(erros))
    partes = [" / ".join(ames) or "AME não encontrado",
              " / ".join(competencia_por_extenso(m) for m in meses) or "mês não encontrado",
              f"{contas} contas"]
    avisos = list(erros)
    if len(ames) > 1:
        avisos.append("Balancetes de AMEs diferentes.")
    if len(meses) > 1:
        avisos.append("Balancetes de meses diferentes.")
    return PreviaBens(descricao=" · ".join(partes), avisos=avisos)


def previa_bens_adquiridos(arquivo: Path) -> PreviaBens:
    leitura = ler_bens_adquiridos(Path(arquivo))
    if leitura.erro:
        return PreviaBens(erro=leitura.erro)
    total = sum((b.valor for b in leitura.bens), start=0)
    return PreviaBens(descricao=f"{len(leitura.bens)} bens · {reais(total)}",
                      avisos=[a.mensagem for a in leitura.avisos])


def previa_baixas(arquivo: Path) -> PreviaBens:
    leitura = ler_baixas(Path(arquivo))
    if leitura.erro:
        return PreviaBens(erro=leitura.erro)
    total = sum((b.valor_origem for b in leitura.bens), start=0)
    return PreviaBens(descricao=f"{len(leitura.bens)} bens · {reais(total)}",
                      avisos=[a.mensagem for a in leitura.avisos])
