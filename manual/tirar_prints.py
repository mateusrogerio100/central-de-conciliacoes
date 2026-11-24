"""Tira os prints do manual: python -m manual.tirar_prints [chave ...]

Abre a Central de verdade (a janela aparece na tela: não mexa no mouse enquanto roda), aplica o
exemplo fictício de cada módulo (manual\\ficticios), espera o resultado e fotografa a janela. Sem
chaves, faz todos os módulos e os prints gerais (janela inicial, Instruções de uso e modo escuro).

Para não misturar nada do usuário de verdade:
- as preferências vão para uma pasta temporária (APPDATA trocado antes de abrir a Central), então as
  pastas lembradas e as do Conciliações AMES não são lidas nem alteradas;
- o rodapé do menu mostra "usuario" no lugar do usuário do Windows.

Os prints saem em manual\\saida\\prints\\ (fora do git; o manual é montado a partir deles).
"""

from __future__ import annotations

import ctypes
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA_SAIDA = RAIZ / "manual" / "saida"
PASTA_PRINTS = PASTA_SAIDA / "prints"
TAMANHO_JANELA = "1280x800"
USUARIO_FICTICIO = "usuario"
PASTA_EXEMPLOS_PRINTS = "Exemplos Central"


def _preparar_ambiente(pasta_temporaria: Path) -> None:
    os.environ["APPDATA"] = str(pasta_temporaria / "appdata")     # antes de importar a Central
    os.environ["CENTRAL_LOG_USO_DESLIGADO"] = "1"                 # os prints não entram no log de uso


def fotografar(janela, caminho: Path) -> Path:
    from PIL import ImageGrab

    janela.attributes("-topmost", True)
    janela.lift()
    # o ponteiro do mouse fora da janela: senão o item do menu embaixo dele sai destacado
    ctypes.windll.user32.SetCursorPos(janela.winfo_screenwidth() - 1, janela.winfo_screenheight() - 1)
    for _ in range(40):                  # deixa a janela terminar de desenhar
        janela.update()
        time.sleep(0.03)
    x, y = janela.winfo_rootx(), janela.winfo_rooty()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    ImageGrab.grab((x, y, x + janela.winfo_width(), y + janela.winfo_height()), all_screens=True).save(caminho)
    return caminho


def main(chaves: list[str]) -> None:
    pasta_temporaria = Path(tempfile.mkdtemp(prefix="prints_central_"))
    _preparar_ambiente(pasta_temporaria)
    # os exemplos ficam na pasta pública do Windows: o caminho que aparece nos cartões não tem o nome de ninguém
    pasta_exemplos = Path(os.environ.get("PUBLIC", tempfile.gettempdir())) / PASTA_EXEMPLOS_PRINTS
    shutil.rmtree(pasta_exemplos, ignore_errors=True)

    import customtkinter as ctk

    from central import janela as modulo_janela
    from manual.ficticios import aplicar_substituicoes, gerar_todos
    from manual.ficticios.aplicar import aplicar, esperar

    modulo_janela.usuario_do_windows = lambda: USUARIO_FICTICIO
    exemplos = gerar_todos(pasta_exemplos)
    aplicar_substituicoes(exemplos)
    if chaves:
        exemplos = [e for e in exemplos if e.chave in chaves or e.nome in chaves]

    ctk.set_appearance_mode("light")
    janela = modulo_janela.JanelaCentral(caminho_preferencias=pasta_temporaria / "preferencias.json")
    janela.geometry(TAMANHO_JANELA + "+0+0")
    janela.deiconify()
    esperar(janela, lambda: True)
    try:
        if not chaves:
            fotografar(janela, PASTA_PRINTS / "janela_inicial.png")
        for exemplo in exemplos:
            janela.selecionar(exemplo.chave)
            esperar(janela, lambda: True)
            tela = aplicar(janela.paineis[exemplo.chave], exemplo)
            fotografar(janela, PASTA_PRINTS / f"{exemplo.nome}.png")
            print(f"{exemplo.nome}: ok" + (f" (mensagens: {tela.mensagens})" if tela.mensagens else ""))
        if not chaves and exemplos:
            primeiro = exemplos[0]
            janela.selecionar(primeiro.chave)
            janela.paineis[primeiro.chave].mostrar_aba("Instruções de uso")
            fotografar(janela, PASTA_PRINTS / "instrucoes_de_uso.png")
            janela.paineis[primeiro.chave].mostrar_aba(primeiro.aba)
            janela.alternar_modo()               # o botão do pé do menu (grava só nas preferências temporárias)
            fotografar(janela, PASTA_PRINTS / "modo_escuro.png")
            janela.alternar_modo()
    finally:
        janela.destroy()
        shutil.rmtree(pasta_temporaria, ignore_errors=True)
        shutil.rmtree(pasta_exemplos, ignore_errors=True)
    print(f"prints em {PASTA_PRINTS}")


if __name__ == "__main__":
    sys.path.insert(0, str(RAIZ))
    main(sys.argv[1:])
