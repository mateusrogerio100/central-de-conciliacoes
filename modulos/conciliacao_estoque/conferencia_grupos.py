"""EST-02 — Conferência dos Grupos SCF x Movimento Estoque (PDF) (ESPECIFICACAO_ESTOQUE.md, seção 6.3).

Regras:
1. cada grupo: total na linha Total(...) do SCF (posição do grupo) x soma das operações do PDF
   que a configuração põe nesse grupo;
2. Total (E) e Total (S) = soma dos grupos, nos dois lados; a soma dos grupos do SCF também é
   conferida com as posições 6 e 12 da linha Total (diferença = ERRO de leitura);
3. operação do PDF sem grupo: não entra em nenhuma soma, aviso de ATENÇÃO;
4. Total geral do PDF x soma de todas as operações lidas;
5. fechamento só no total geral: saldo atual x saldo anterior + Total (E) − Total (S) (do SCF);
6. pares iguais: valor(A) x valor(B), operação ausente vale 0;
7. mês do PDF x mês do SCF.
"""

from __future__ import annotations

import re
from decimal import Decimal

from modulos.conciliacao_estoque import configuracao
from modulos.conciliacao_estoque.modelos import (
    Aviso,
    ConferenciaGrupoSCF,
    ConferenciaPar,
    ConfiguracaoEST02,
    ErroArquivo,
    Gravidade,
    LinhaOperacao,
    MovimentoEstoquePDF,
    RelatorioSCF,
    ResultadoEST02,
)
from modulos.conciliacao_estoque.utilitarios import formatar_valor

ZERO = Decimal("0.00")
NOME_TOTAL_ENTRADAS = "Total (E) — soma dos grupos de entrada"
NOME_TOTAL_SAIDAS = "Total (S) — soma dos grupos de saída"
NOME_NAO_CADASTRADA = "(não cadastrada na configuração)"
OBSERVACAO_SEM_GRUPO = "Operação sem grupo — cadastrar em Editar configuração"
_PREFIXO_ES = re.compile(r"^[ES]\s*-\s*")
POSICAO_TOTAL_E, POSICAO_TOTAL_S = configuracao.EST02_POSICOES_CALCULADAS


def nome_para_exibir(nome: str) -> str:
    """ "E - Produção" -> "Produção" (o E/S já aparece em coluna própria)."""
    return _PREFIXO_ES.sub("", nome).strip()


def conferir_grupos(scf: RelatorioSCF, pdf: MovimentoEstoquePDF, config: ConfiguracaoEST02) -> ResultadoEST02:
    if not config.valida:
        problemas = "; ".join(a.mensagem for a in config.avisos if a.gravidade == Gravidade.ERRO)
        raise ErroArquivo(f"A configuração da EST-02 tem problemas e precisa ser corrigida antes: {problemas}")
    if scf.total is None:
        raise ErroArquivo(f"{scf.arquivo}: linha Total(...) do Mapa do Estoque não lida; a EST-02 não pode ser feita.")

    resultado = ResultadoEST02(
        mes_referencia=scf.mes_referencia,
        arquivo_scf=scf.arquivo,
        arquivo_pdf=pdf.arquivo,
        arquivo_configuracao=config.caminho.replace("\\", "/").rsplit("/", 1)[-1],
        origem_configuracao=config.descricao_origem,
        total_geral_pdf=pdf.total_geral,
        soma_operacoes_pdf=pdf.soma_operacoes,
        saldo_anterior_scf=scf.total_na_posicao(1),
        saldo_atual_scf=scf.total_na_posicao(len(configuracao.SCF_TITULOS)),
    )

    def avisar(gravidade, tipo, mensagem, conta=""):
        resultado.avisos.append(Aviso(gravidade, tipo, f"EST-02: {mensagem}", conta=conta))

    if pdf.mes_referencia and scf.mes_referencia and pdf.mes_referencia != scf.mes_referencia:
        avisar(Gravidade.ATENCAO, "mês diferente", f"PDF de {pdf.mes_referencia} e Mapa do Estoque de {scf.mes_referencia}.")

    # Regra 1 — cada grupo
    for grupo in config.grupos:
        operacoes = sorted(o.codigo for o in pdf.operacoes if config.grupo_da_operacao(o.codigo) is grupo)
        linha = ConferenciaGrupoSCF(
            nome=grupo.nome, tipo=grupo.tipo, total_scf=scf.total_na_posicao(grupo.posicao),
            soma_pdf=sum((pdf.valor(c) for c in operacoes), ZERO), operacoes=operacoes,
        )
        (resultado.entradas if grupo.tipo == configuracao.EST02_TIPO_ENTRADA else resultado.saidas).append(linha)

    # Regra 2 — Total (E) e Total (S)
    resultado.total_entradas = _total(NOME_TOTAL_ENTRADAS, configuracao.EST02_TIPO_ENTRADA, resultado.entradas)
    resultado.total_saidas = _total(NOME_TOTAL_SAIDAS, configuracao.EST02_TIPO_SAIDA, resultado.saidas)
    for total, posicao in ((resultado.total_entradas, POSICAO_TOTAL_E), (resultado.total_saidas, POSICAO_TOTAL_S)):
        do_scf = scf.total_na_posicao(posicao)
        if total.total_scf != do_scf:
            avisar(Gravidade.ERRO, "total do Mapa do Estoque",
                   f"Soma dos grupos do Mapa do Estoque {formatar_valor(total.total_scf)} diferente da coluna "
                   f"{configuracao.SCF_TITULOS[posicao - 1]} do próprio Mapa do Estoque {formatar_valor(do_scf)}.")

    for linha in resultado.todas_as_linhas:
        if linha.diferenca != 0:
            avisar(Gravidade.ATENCAO, "grupo com diferença",
                   f"{linha.nome}: Mapa do Estoque {formatar_valor(linha.total_scf)} x PDF {formatar_valor(linha.soma_pdf)} "
                   f"(diferença {formatar_valor(linha.diferenca)}).", linha.nome)

    # Regra 6 — pares iguais (antes das operações: as observações delas citam os pares)
    for par in config.pares:
        conferencia = ConferenciaPar(
            par, nome_para_exibir(par.nome_a), nome_para_exibir(par.nome_b),
            pdf.valor(par.operacao_a), pdf.valor(par.operacao_b),
        )
        resultado.pares.append(conferencia)
        if conferencia.diferenca != 0:
            avisar(Gravidade.ATENCAO, "par diferente",
                   f"{conferencia.mensagem_atencao} (diferença {formatar_valor(conferencia.diferenca)}).")

    # Regra 3 — operações (aba Operações), sem grupo em destaque
    for operacao in sorted(pdf.operacoes, key=lambda o: o.codigo):
        resultado.operacoes.append(_linha_operacao(operacao, config, resultado.pares))
        if config.grupo_da_operacao(operacao.codigo) is None:
            avisar(Gravidade.ATENCAO, "operação sem grupo",
                   f"Operação {operacao.codigo} sem grupo — cadastrar em Editar configuração "
                   f"(valor {formatar_valor(operacao.valor)} fora das somas).", str(operacao.codigo))

    # Regra 4 — Total geral do PDF (a diferença já vem avisada pelo leitor do PDF)
    # Regra 5 — fechamento só no total geral
    if resultado.diferenca_fechamento != 0:
        avisar(Gravidade.ATENCAO, "fechamento do total geral",
               f"Saldo atual do Mapa do Estoque {formatar_valor(resultado.saldo_atual_scf)} diferente de saldo anterior + "
               f"Total (E) − Total (S) = {formatar_valor(resultado.fechamento_calculado)}.")
    return resultado


def _total(nome, tipo, grupos) -> ConferenciaGrupoSCF:
    return ConferenciaGrupoSCF(
        nome=nome, tipo=tipo,
        total_scf=sum((g.total_scf for g in grupos), ZERO),
        soma_pdf=sum((g.soma_pdf for g in grupos), ZERO),
        operacoes=sorted(c for g in grupos for c in g.operacoes),
        e_total=True,
    )


def _linha_operacao(operacao, config, pares) -> LinhaOperacao:
    item = config.itens.get(operacao.codigo)
    grupo = config.grupo_da_operacao(operacao.codigo)
    observacoes = []
    if grupo is None:
        observacoes.append(OBSERVACAO_SEM_GRUPO)
    elif item.es_tasy and item.es_tasy != configuracao.EST02_ES_DO_TIPO[grupo.tipo]:
        observacoes.append(f"Marcada {item.es_tasy} no Tasy, mas o grupo {grupo.nome} é de "
                           f"{grupo.tipo.lower()}: vale o grupo (caso conhecido)")
    for par in pares:
        if operacao.codigo in (par.par.operacao_a, par.par.operacao_b) and par.diferenca != 0:
            observacoes.append(
                f"{par.nome_a} ({par.par.operacao_a}) diferente de {par.nome_b} ({par.par.operacao_b}): "
                f"diferença de {formatar_valor(par.diferenca)} — ver aba Grupos"
            )
    return LinhaOperacao(
        codigo=operacao.codigo,
        nome=nome_para_exibir(item.nome) if item else NOME_NAO_CADASTRADA,
        valor=operacao.valor,
        grupo=grupo.nome if grupo else "",
        es_tabela=item.es_tasy if item else "",
        observacao="; ".join(observacoes),
    )
