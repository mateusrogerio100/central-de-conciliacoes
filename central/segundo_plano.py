"""Roda um processamento pesado sem travar a janela (ESPECIFICACAO, regra 4.3.3).

O Tkinter só pode ser mexido pela thread da janela. Por isso a tarefa roda numa thread
separada e manda o andamento para uma fila; a janela lê essa fila de tempos em tempos
(widget.after) e chama as funções de retorno na thread certa.

Uso num painel:
    TarefaEmSegundoPlano(
        self,
        tarefa=lambda progresso: processamento.processar(..., progresso=progresso),
        ao_progresso=barra.atualizar,           # (texto, fracao)
        ao_concluir=self._mostrar_resultado,    # (resultado)
        ao_falhar=self._mostrar_erro,           # (erro, detalhe_tecnico)
    ).iniciar()
"""

from __future__ import annotations

import gc
import queue
import threading
import traceback
from typing import Any, Callable

Progresso = Callable[[str, "float | None"], None]


class TarefaEmSegundoPlano:
    INTERVALO_MS = 50

    def __init__(self, widget, tarefa: Callable[[Progresso], Any],
                 ao_progresso: Progresso | None = None,
                 ao_concluir: Callable[[Any], None] | None = None,
                 ao_falhar: Callable[[BaseException, str], None] | None = None):
        self.widget = widget
        self.tarefa = tarefa
        self.ao_progresso = ao_progresso
        self.ao_concluir = ao_concluir
        self.ao_falhar = ao_falhar
        self._fila: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self.terminou = False

    @property
    def em_andamento(self) -> bool:
        return self._thread is not None and not self.terminou

    def iniciar(self) -> "TarefaEmSegundoPlano":
        # Limpa agora, na thread da janela, os restos de telas já desmontadas (imagens, variáveis).
        # Se essa limpeza acontecesse dentro da thread de trabalho, cada resto teria de esperar a
        # janela para ser apagado (o Tkinter só aceita a thread da janela) e o processamento ficaria
        # muito mais lento.
        gc.collect()
        self._thread = threading.Thread(target=self._rodar, daemon=True)
        self._thread.start()
        self.widget.after(self.INTERVALO_MS, self._ler_fila)
        return self

    # --- thread de trabalho ---

    def _progresso(self, texto: str, fracao: float | None = None) -> None:
        self._fila.put(("progresso", (texto, fracao)))

    def _rodar(self) -> None:
        try:
            resultado = self.tarefa(self._progresso)
        except BaseException as erro:  # qualquer falha vira mensagem na tela, nunca fecha o programa
            self._fila.put(("falhou", (erro, traceback.format_exc())))
        else:
            self._fila.put(("concluiu", resultado))

    # --- thread da janela ---

    def _ler_fila(self) -> None:
        # Só o ÚLTIMO andamento de cada leitura é mostrado. Antes, cada mensagem redesenhava a barra na hora; com
        # uma tarefa que manda andamento muito seguido (ex.: um PDF lido a cada décimo de segundo) e uma tela
        # pesada, redesenhar demorava mais que a próxima mensagem chegar, este laço nunca terminava e a janela
        # ficava congelada até o fim, sem nem mostrar a barra (EFD Contribuições, 05/11/2026).
        ultimo_progresso = None
        while True:
            try:
                tipo, conteudo = self._fila.get_nowait()
            except queue.Empty:
                break
            if tipo == "progresso":
                ultimo_progresso = conteudo
                continue
            if ultimo_progresso is not None and self.ao_progresso:
                self.ao_progresso(*ultimo_progresso)
            self.terminou = True
            if tipo == "concluiu":
                if self.ao_concluir:
                    self.ao_concluir(conteudo)
            elif self.ao_falhar:
                self.ao_falhar(*conteudo)
            return
        if ultimo_progresso is not None and self.ao_progresso:
            self.ao_progresso(*ultimo_progresso)
        try:
            self.widget.after(self.INTERVALO_MS, self._ler_fila)
        except Exception:  # a janela foi fechada no meio do processamento
            pass
