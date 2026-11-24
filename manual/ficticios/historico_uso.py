"""Histórico de uso: a pasta do log com o arquivo de dois computadores (usuários fictícios), como a Central grava.

Mostra: dois usuários, quatro usos dos módulos (um com erro) e três aberturas da Central.
"""

from __future__ import annotations

from pathlib import Path

from manual.ficticios import Exemplo

TITULOS = "Data;Hora;Usuário;Computador;Versão;Módulo;Ação;Resultado"
USOS = {
    "2026-10 - CONTABIL-01 - ana.exemplo.csv": [
        "22/10/2026;08:02:10;ana.exemplo;CONTABIL-01;1.5.0;Central;Abriu a Central;ok",
        "22/10/2026;08:10:45;ana.exemplo;CONTABIL-01;1.5.0;Notas de Contrato;Conferir mês;ok",
        "22/10/2026;08:31:02;ana.exemplo;CONTABIL-01;1.5.0;Notas de Contrato;Gerar pendências;ok",
        "23/10/2026;09:00:00;ana.exemplo;CONTABIL-01;1.5.0;Central;Abriu a Central;ok",
        "23/10/2026;09:05:40;ana.exemplo;CONTABIL-01;1.5.0;Conferência de NF;Conferir lote;erro",
    ],
    "2026-10 - CONTABIL-02 - bruno.exemplo.csv": [
        "21/10/2026;14:20:00;bruno.exemplo;CONTABIL-02;1.5.0;Central;Abriu a Central;ok",
        "21/10/2026;14:25:13;bruno.exemplo;CONTABIL-02;1.5.0;Conciliação Bancária;Processar;ok",
    ],
}


def gerar(pasta: Path) -> list[Exemplo]:
    log = pasta / "Log de uso"
    log.mkdir(parents=True, exist_ok=True)
    for nome, linhas in USOS.items():
        (log / nome).write_text("\r\n".join([TITULOS, *linhas]) + "\r\n", encoding="utf-8-sig")
    saida = pasta / "saida"
    saida.mkdir(parents=True, exist_ok=True)
    return [Exemplo("historico_uso", "historico_uso", "Histórico", "historico",
                    {"cartao_log": [log], "cartao_saida": [saida]}, pasta_saida=saida, numeros=("2", "4", "3"))]
