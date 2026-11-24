"""Orquestra o processamento completo. É o único módulo que a interface chama.

Ordem: balancete -> patrimônio -> estrutura das planilhas -> conciliação -> gravação das cópias
-> relatório de avisos. Cada arquivo é tratado separadamente (R14): um problema num arquivo é
registrado e o processamento continua com os demais. Todo arquivo de entrada aparece no
Resumo do relatório com o que aconteceu (R13).

Funções para a interface:
- interpretar_mes: valida o mês digitado (MM/AAAA);
- mes_do_balancete / mes_do_patrimonio: mês lido de cada arquivo (R10);
- arquivos_de_saida: caminhos que serão gravados, para perguntar antes de substituir (R11);
- processar: faz tudo e devolve o ResultadoProcessamento. Aceita a função opcional
  progresso(texto, fracao), chamada a cada passo para a tela mostrar o andamento
  (ESPECIFICACAO da Central, regra 4.3.3).
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from modulos.subvencoes import configuracao
from modulos.subvencoes.conciliacao import conciliar
from modulos.subvencoes.leitor_balancete import ler_balancete
from modulos.subvencoes.leitor_patrimonio import ler_patrimonio
from modulos.subvencoes.modelos import (
    TIPO_BALANCETE,
    TIPO_PATRIMONIO,
    TIPO_PLANILHA,
    ArquivoResumo,
    Aviso,
    ErroArquivo,
    Gravidade,
    MesReferencia,
    ResultadoProcessamento,
    StatusArquivo,
)
from modulos.subvencoes.preenchedor import caminho_destino, gravar_planilha, ler_estrutura_planilha
from modulos.subvencoes.relatorio_avisos import gerar_relatorio
from modulos.subvencoes.utilitarios import mes_de_texto


# ---------------------------------------------------------------------------
# Consultas para a interface (antes de processar)
# ---------------------------------------------------------------------------


def interpretar_mes(texto: str) -> MesReferencia | None:
    """Mês digitado na tela ("08/2026") -> MesReferencia. None se inválido."""
    return mes_de_texto(texto or "")


def mes_do_balancete(caminho) -> MesReferencia | None:
    """Mês de referência do balancete, para preencher o campo da tela. None se não der para ler."""
    try:
        return ler_balancete(caminho).mes_referencia
    except Exception:
        return None


def mes_do_patrimonio(caminho) -> MesReferencia | None:
    try:
        return ler_patrimonio(caminho).mes_referencia
    except Exception:
        return None


def caminho_relatorio(pasta_saida, mes: MesReferencia) -> Path:
    return Path(pasta_saida) / configuracao.NOME_RELATORIO_AVISOS.format(mes_ano=mes.para_nome_arquivo)


def arquivos_de_saida(planilhas, pasta_saida, mes: MesReferencia) -> list[Path]:
    """Todos os arquivos que o processamento vai gravar (planilhas e relatório)."""
    return [caminho_destino(p, pasta_saida, mes) for p in planilhas] + [caminho_relatorio(pasta_saida, mes)]


# ---------------------------------------------------------------------------
# Processamento
# ---------------------------------------------------------------------------


def processar(balancete, patrimonio, planilhas, pasta_saida, mes_referencia: MesReferencia,
              progresso: Callable[[str, float | None], None] | None = None) -> ResultadoProcessamento:
    """Processa tudo e grava as cópias e o relatório em `pasta_saida`.

    `mes_referencia` é o mês escolhido na tela (R10): define os nomes dos arquivos gerados.
    `progresso(texto, fracao)`, se informado, recebe cada passo (fracao de 0 a 1).
    Nunca levanta exceção por problema em arquivo: tudo vai para o resultado e o relatório.
    """
    if mes_referencia is None:
        raise ValueError("Informe o mês de referência (MM/AAAA).")
    if progresso is None:
        progresso = _sem_progresso
    pasta_saida = Path(pasta_saida)
    resultado = ResultadoProcessamento(mes_referencia=mes_referencia, pasta_saida=str(pasta_saida))

    progresso("Lendo o balancete...", 0.0)
    resumo_balancete = _ler_balancete(balancete, resultado)
    progresso("Lendo o relatório de patrimônio...", 0.15)
    resumo_patrimonio = _ler_patrimonio(patrimonio, resultado)
    _conferir_meses(resultado, resumo_balancete, resumo_patrimonio)

    planilhas_lidas = []
    for caminho in planilhas:
        progresso(f"Lendo a planilha {Path(caminho).name}...", 0.35)
        lida = _ler_planilha(caminho, resultado)
        if lida is not None:
            planilhas_lidas.append((Path(caminho), lida))

    if resultado.balancete is None or resultado.patrimonio is None:
        falhou = "balancete" if resultado.balancete is None else "relatório de patrimônio"
        for resumo in resultado.planilhas:
            if resumo.status == StatusArquivo.LIDO:
                resumo.status = StatusArquivo.NAO_PROCESSADO
                resumo.detalhe = f"Não preenchida: o {falhou} não pôde ser lido."
                _avisar(resultado, Gravidade.ERRO, "planilha não gerada", resumo.detalhe, arquivo=resumo.nome)
    else:
        progresso("Conciliando...", 0.55)
        conciliacao = conciliar(resultado.balancete, resultado.patrimonio, [l for _, l in planilhas_lidas])
        resultado.conciliacao = conciliacao
        resultado.avisos.extend(conciliacao.avisos)
        progresso("Gravando as planilhas preenchidas...", 0.7)
        _gravar_planilhas(planilhas_lidas, pasta_saida, resultado)

    progresso("Gerando o relatório de avisos...", 0.9)
    _gerar_relatorio(resultado, pasta_saida)
    progresso("Concluído.", 1.0)
    return resultado


def _sem_progresso(texto: str, fracao: float | None) -> None:
    """Usado quando ninguém acompanha o andamento (testes, linha de comando)."""


def _avisar(resultado, gravidade, tipo, mensagem, arquivo="", aba="", linha=None, conta=""):
    resultado.avisos.append(Aviso(gravidade, tipo, mensagem, arquivo=arquivo, aba=aba, linha=linha, conta=conta))


def _mensagem_erro(erro: Exception) -> str:
    if isinstance(erro, ErroArquivo):
        return str(erro)
    return f"Erro inesperado: {type(erro).__name__}: {erro}"


def _ler_balancete(caminho, resultado) -> ArquivoResumo:
    resumo = ArquivoResumo(caminho=str(caminho), tipo=TIPO_BALANCETE, status=StatusArquivo.LIDO)
    resultado.arquivos.append(resumo)
    try:
        balancete = ler_balancete(caminho)
    except Exception as erro:
        resumo.status, resumo.detalhe = StatusArquivo.FALHOU, _mensagem_erro(erro)
        _avisar(resultado, Gravidade.ERRO, "arquivo não lido", resumo.detalhe, arquivo=resumo.nome)
        return resumo
    resultado.balancete = balancete
    resultado.avisos.extend(balancete.avisos)
    resumo.mes_lido = balancete.mes_referencia
    resumo.detalhe = f"{len(balancete.contas)} contas lidas ({len(balancete.analiticas())} analíticas)."
    return resumo


def _ler_patrimonio(caminho, resultado) -> ArquivoResumo:
    resumo = ArquivoResumo(caminho=str(caminho), tipo=TIPO_PATRIMONIO, status=StatusArquivo.LIDO)
    resultado.arquivos.append(resumo)
    try:
        patrimonio = ler_patrimonio(caminho)
    except Exception as erro:
        resumo.status, resumo.detalhe = StatusArquivo.FALHOU, _mensagem_erro(erro)
        _avisar(resultado, Gravidade.ERRO, "arquivo não lido", resumo.detalhe, arquivo=resumo.nome)
        return resumo
    resultado.patrimonio = patrimonio
    resultado.avisos.extend(patrimonio.avisos)
    resumo.mes_lido = patrimonio.mes_referencia
    resumo.detalhe = f"{len(patrimonio.contas)} contas, {patrimonio.quantidade_itens} bens lidos."
    return resumo


def _conferir_meses(resultado, resumo_balancete, resumo_patrimonio):
    """R10: mês do patrimônio x mês do balancete; mês informado na tela x mês do balancete."""
    mes_balancete, mes_patrimonio = resumo_balancete.mes_lido, resumo_patrimonio.mes_lido
    if mes_balancete and mes_patrimonio and mes_balancete != mes_patrimonio:
        _avisar(resultado, Gravidade.ATENCAO, "meses diferentes",
                f"O balancete é de {mes_balancete} e o relatório de patrimônio é de {mes_patrimonio}. "
                "O processamento continuou a pedido do usuário.")
    if mes_balancete and mes_balancete != resultado.mes_referencia:
        _avisar(resultado, Gravidade.ATENCAO, "meses diferentes",
                f"O mês de referência informado ({resultado.mes_referencia}) é diferente do mês do "
                f"balancete ({mes_balancete}). Os arquivos foram gerados com {resultado.mes_referencia}.")


def _ler_planilha(caminho, resultado):
    resumo = ArquivoResumo(caminho=str(caminho), tipo=TIPO_PLANILHA, status=StatusArquivo.LIDO)
    resultado.arquivos.append(resumo)
    try:
        lida = ler_estrutura_planilha(caminho)
    except Exception as erro:
        resumo.status, resumo.detalhe = StatusArquivo.FALHOU, _mensagem_erro(erro)
        _avisar(resultado, Gravidade.ERRO, "planilha não gerada", resumo.detalhe, arquivo=resumo.nome)
        return None
    resultado.avisos.extend(lida.avisos)
    resumo.abas_sem_contas = list(lida.abas_sem_contas)
    for aba in lida.abas_sem_contas:
        _avisar(resultado, Gravidade.INFO, "aba sem contas",
                f"A aba não tem a linha de títulos com '{configuracao.PLANILHA_TITULO_CONTA_CONTABIL}' "
                "e foi ignorada.", arquivo=resumo.nome, aba=aba)
    if not lida.abas:
        resumo.status = StatusArquivo.FALHOU
        resumo.detalhe = "Nenhuma aba com a linha de títulos das contas."
        _avisar(resultado, Gravidade.ERRO, "planilha não gerada", resumo.detalhe, arquivo=resumo.nome)
        return None
    return lida


def _gravar_planilhas(planilhas_lidas, pasta_saida, resultado):
    destinos_usados: dict[Path, str] = {}
    for caminho, lida in planilhas_lidas:
        resumo = next(r for r in resultado.planilhas if Path(r.caminho) == caminho and r.status == StatusArquivo.LIDO)
        destino = caminho_destino(caminho, pasta_saida, resultado.mes_referencia)
        chave = destino.resolve()
        if chave in destinos_usados:
            resumo.status = StatusArquivo.FALHOU
            resumo.detalhe = (f"O arquivo de saída {destino.name} seria o mesmo de {destinos_usados[chave]}; "
                              "esta planilha não foi gravada para não sobrescrever a outra.")
            _avisar(resultado, Gravidade.ERRO, "planilha não gerada", resumo.detalhe, arquivo=resumo.nome)
            continue
        destinos_usados[chave] = caminho.name

        valores = [l for l in resultado.conciliacao.linhas if l.planilha == lida.arquivo]
        try:
            gravar_planilha(caminho, destino, valores)
        except Exception as erro:
            resumo.status, resumo.detalhe = StatusArquivo.FALHOU, _mensagem_erro(erro)
            _avisar(resultado, Gravidade.ERRO, "planilha não gerada", resumo.detalhe, arquivo=resumo.nome)
            continue
        resumo.status = StatusArquivo.GERADO
        resumo.destino = str(destino)
        resumo.linhas_preenchidas = len(valores)
        resumo.linhas_com_diferenca = sum(1 for v in valores if v.diferenca != 0)
        resumo.detalhe = f"Gerada: {destino.name}."


def _gerar_relatorio(resultado, pasta_saida):
    caminho = caminho_relatorio(pasta_saida, resultado.mes_referencia)
    try:
        gerar_relatorio(resultado, caminho)
    except Exception as erro:
        resultado.erro_relatorio = _mensagem_erro(erro)
        return
    resultado.caminho_relatorio = str(caminho)
