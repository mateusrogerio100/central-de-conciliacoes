"""Aplica um Exemplo na tela de um módulo: escolhe os arquivos, espera as conferências, gera o resultado.

Usado pelo script de prints (com a Central aberta de verdade) e pelo teste dos exemplos (com a tela
escondida). As perguntas da tela ("substituir?") são respondidas com Sim: a pasta de saída dos
exemplos é descartável.
"""

from __future__ import annotations

import time

from manual.ficticios import Exemplo


def esperar(widget, condicao, limite_segundos: float = 180) -> None:
    """Processa os eventos da janela até `condicao()` ser verdadeira."""
    inicio = time.time()
    while not condicao():
        widget.update()
        if time.time() - inicio > limite_segundos:
            raise TimeoutError("a tela não terminou a tempo")
        time.sleep(0.02)
    for _ in range(5):
        widget.update()


def aplicar(painel_modulo, exemplo: Exemplo, limite_segundos: float = 180):
    """painel_modulo: o PainelComAbas do módulo. Devolve a tela da aba, já com o resultado."""
    painel_modulo.mostrar_aba(exemplo.aba)
    tela = getattr(painel_modulo, exemplo.atributo)
    tela.mensagens = []
    tela.perguntar = lambda texto: True
    tela.avisar = tela.informar = tela.mensagens.append
    for nome_cartao, caminhos in exemplo.arquivos.items():
        getattr(tela, nome_cartao).definir_caminhos(caminhos)
        esperar(tela, lambda: True)
    if exemplo.preparar:
        exemplo.preparar(tela)
    if exemplo.acao is None:
        esperar(tela, lambda: True)
        return tela
    esperar(tela, tela.pronto_para_processar, limite_segundos)
    for acao in exemplo.acao if isinstance(exemplo.acao, list) else [exemplo.acao]:
        acao(tela) if callable(acao) else getattr(tela, acao)()
        esperar(tela, lambda: not tela.ocupado, limite_segundos)
    return tela


def numeros_na_tela(widget) -> tuple[str, ...]:
    """Os números grandes (NumeroResumo) dentro de `widget`, na ordem em que foram criados."""
    from central.componentes import NumeroResumo

    achados = []
    for filho in widget.winfo_children():
        if isinstance(filho, NumeroResumo):
            achados.append(filho.rotulo_numero.cget("text"))
        else:
            achados += numeros_na_tela(filho)
    return tuple(achados)
