"""Carrega os ícones de central/icones/ já pintados nas cores do tema.

Os PNGs são brancos sobre fundo transparente (ver central/gerar_icones.py). Aqui cada ícone é
pintado com um par de cores (modo claro, modo escuro) e vira um CTkImage, que o CustomTkinter
troca sozinho quando o modo muda.
"""

from __future__ import annotations

from functools import lru_cache

import customtkinter as ctk
from PIL import Image

from central.caminhos import caminho_interno


def pasta_icones():
    return caminho_interno("central", "icones")


def existe(nome: str) -> bool:
    return (pasta_icones() / f"{nome}.png").is_file()


@lru_cache(maxsize=None)
def _mascara(nome: str) -> Image.Image | None:
    caminho = pasta_icones() / f"{nome}.png"
    try:
        with Image.open(caminho) as imagem:
            return imagem.convert("RGBA").getchannel("A")
    except OSError:
        return None


def _pintar(mascara: Image.Image, cor: str) -> Image.Image:
    imagem = Image.new("RGBA", mascara.size, cor)
    imagem.putalpha(mascara)
    return imagem


def icone(nome: str, cor: tuple[str, str], tamanho: int) -> ctk.CTkImage | None:
    """Ícone `nome` pintado com `cor` = (claro, escuro), em `tamanho` px.

    Devolve None se o ícone não existir: a tela aparece sem ele, nada quebra.
    """
    mascara = _mascara(nome)
    if mascara is None:
        return None
    claro, escuro = cor
    return ctk.CTkImage(light_image=_pintar(mascara, claro), dark_image=_pintar(mascara, escuro),
                        size=(tamanho, tamanho))


def logo(tamanho: int) -> ctk.CTkImage | None:
    """Logo da Hospital Exemplo (central/icones/logo.png), se existir; senão None (o menu desenha o "+")."""
    caminho = pasta_icones() / "logo.png"
    if not caminho.is_file():
        return None
    try:
        with Image.open(caminho) as imagem:
            copia = imagem.convert("RGBA")
    except OSError:
        return None
    return ctk.CTkImage(light_image=copia, dark_image=copia, size=(tamanho, tamanho))
