"""Desenha os ícones da Central em central/icones/*.png (ferramenta de manutenção, não entra no .exe).

Os ícones seguem o estilo "linha" do Lucide (grade de 24 x 24, traço 2, pontas arredondadas),
mas são desenhados aqui mesmo, com Pillow, para não depender de download nem de licença.
Cada PNG é branco sobre fundo transparente: o programa pinta na cor certa ao carregar
(central/icones.py), para o modo claro e para o escuro.

Para criar ou mudar um ícone: acrescente/edite uma função em ICONES e rode, na raiz do projeto:
    python -m central.gerar_icones

O mesmo comando refaz a marca do menu (central/icones/logo.png) e o ícone do .exe e das janelas
(recursos/icone.ico) a partir do logo da Hospital Exemplo (recursos/logo_hospital_exemplo_256.png): só o símbolo
(o quadrado colorido), sem a faixa cinza de baixo, que fica ilegível em tamanho pequeno.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

PASTA_ICONES = Path(__file__).resolve().parent / "icones"
PASTA_RECURSOS = Path(__file__).resolve().parent.parent / "recursos"
LOGO_ORIGINAL = PASTA_RECURSOS / "logo_hospital_exemplo_256.png"
TAMANHO_LOGO = 128                 # px da marca gravada (o menu mostra em 32)
TAMANHOS_ICO = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

GRADE = 24            # unidades do desenho (como o Lucide)
ESCALA = 8            # desenha 8x maior e reduz no fim: bordas suaves
TAMANHO_FINAL = 64    # px do PNG gravado
TRACO = 2             # espessura do traço, em unidades da grade


class Desenho:
    """Caneta sobre a grade 24 x 24 (coordenadas em unidades da grade)."""

    def __init__(self):
        lado = GRADE * ESCALA
        self.imagem = Image.new("L", (lado, lado), 0)
        self.caneta = ImageDraw.Draw(self.imagem)
        self.largura = TRACO * ESCALA

    def _p(self, x, y):
        return (x * ESCALA, y * ESCALA)

    def _ponta(self, x, y):
        r = self.largura / 2
        cx, cy = self._p(x, y)
        self.caneta.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)

    def linha(self, *pontos, fechada=False):
        """Linha passando pelos pontos (x, y), com pontas e juntas arredondadas."""
        pontos = list(pontos) + ([pontos[0]] if fechada else [])
        coordenadas = [self._p(x, y) for x, y in pontos]
        self.caneta.line(coordenadas, fill=255, width=self.largura, joint="curve")
        for x, y in pontos:
            self._ponta(x, y)

    def circulo(self, cx, cy, r):
        (x0, y0), (x1, y1) = self._p(cx - r, cy - r), self._p(cx + r, cy + r)
        self.caneta.ellipse((x0, y0, x1, y1), outline=255, width=self.largura)

    def arco(self, cx, cy, r, inicio, fim, passos=48):
        """Arco de circunferência, ângulos em graus (0 = direita, 90 = para baixo)."""
        pontos = []
        for i in range(passos + 1):
            angulo = math.radians(inicio + (fim - inicio) * i / passos)
            pontos.append((cx + r * math.cos(angulo), cy + r * math.sin(angulo)))
        self.linha(*pontos)

    def ponto(self, x, y):
        self._ponta(x, y)

    def retangulo(self, x0, y0, x1, y1, raio):
        (a, b), (c, d) = self._p(x0, y0), self._p(x1, y1)
        self.caneta.rounded_rectangle((a, b, c, d), radius=raio * ESCALA, outline=255, width=self.largura)

    def gravar(self, caminho: Path):
        mascara = self.imagem.resize((TAMANHO_FINAL, TAMANHO_FINAL), Image.LANCZOS)
        branco = Image.new("RGBA", mascara.size, (255, 255, 255, 0))
        branco.putalpha(mascara)
        branco.save(caminho)


# ---------------------------------------------------------------------------
# Ícones (um por função). O nome da função é o nome do arquivo.
# ---------------------------------------------------------------------------


def arquivo(d: Desenho):
    d.linha((14, 2), (6, 2), (4, 4), (4, 20), (6, 22), (18, 22), (20, 20), (20, 8), (14, 2))
    d.linha((14, 2), (14, 8), (20, 8))
    d.linha((8, 13), (16, 13))
    d.linha((8, 17), (16, 17))
    d.linha((8, 9), (10, 9))


def arquivos(d: Desenho):
    d.linha((15, 2), (9, 2), (7, 4), (7, 16), (9, 18), (19, 18), (21, 16), (21, 8), (15, 2))
    d.linha((15, 2), (15, 8), (21, 8))
    d.linha((3, 7), (3, 20), (5, 22), (15, 22))


def pasta(d: Desenho):
    d.linha((4, 20), (20, 20), (22, 18), (22, 8), (20, 6), (12, 6), (10, 3), (4, 3), (2, 5), (2, 18), (4, 20))


def banco(d: Desenho):
    d.linha((3, 22), (21, 22))
    for x in (6, 10, 14, 18):
        d.linha((x, 18), (x, 11))
    d.linha((12, 2), (20, 7), (4, 7), fechada=True)


def pessoas(d: Desenho):
    d.circulo(9, 7, 4)
    d.arco(9, 19, 6, 180, 360)
    d.linha((3, 19), (3, 21))
    d.linha((15, 19), (15, 21))
    d.arco(16, 7, 4, -70, 70)
    d.arco(17.5, 19, 4.5, 250, 360)
    d.linha((22, 19), (22, 21))


def importar(d: Desenho):
    d.linha((14, 2), (6, 2), (4, 4), (4, 20), (6, 22), (18, 22), (20, 20), (20, 8), (14, 2))
    d.linha((14, 2), (14, 8), (20, 8))
    d.linha((12, 18), (12, 12))
    d.linha((9, 15), (12, 12), (15, 15))


def moedas(d: Desenho):
    d.circulo(8, 8, 6)
    d.arco(16, 16, 6, -80, 190)
    d.linha((7, 6), (8, 6), (8, 10))
    d.linha((15.5, 14), (16.5, 14), (16.5, 18))


def lua(d: Desenho):
    # crescente: arco grande (centro 12,12) + arco menor que "morde" o canto superior direito
    d.arco(12, 12, 9, 0, 270)
    d.arco(16.5, 7.5, 6.36, 225, 45)


def sol(d: Desenho):
    d.circulo(12, 12, 4)
    for angulo in range(0, 360, 45):
        a = math.radians(angulo)
        d.linha((12 + 7.5 * math.cos(a), 12 + 7.5 * math.sin(a)), (12 + 9.5 * math.cos(a), 12 + 9.5 * math.sin(a)))


def check(d: Desenho):
    d.circulo(12, 12, 10)
    d.linha((8.5, 12), (11, 14.5), (15.5, 10))


def alerta(d: Desenho):
    d.linha((12, 3), (22, 20), (2, 20), fechada=True)
    d.linha((12, 9), (12, 13))
    d.ponto(12, 16.8)


def erro(d: Desenho):
    d.circulo(12, 12, 10)
    d.linha((15, 9), (9, 15))
    d.linha((9, 9), (15, 15))


def caixa(d: Desenho):
    d.linha((22, 12), (16, 12), (14, 15), (10, 15), (8, 12), (2, 12))
    d.linha((2, 12), (5.5, 5), (18.5, 5), (22, 12), (22, 18), (20, 20), (4, 20), (2, 18), (2, 12))


def mais(d: Desenho):
    d.linha((12, 5), (12, 19))
    d.linha((5, 12), (19, 12))


def seta_direita(d: Desenho):
    d.linha((5, 12), (19, 12))
    d.linha((13, 6), (19, 12), (13, 18))


def olho(d: Desenho):
    d.arco(12, 19, 11.4, 218, 322)
    d.arco(12, 5, 11.4, 38, 142)
    d.circulo(12, 12, 3)


def atualizar(d: Desenho):
    d.arco(12, 12, 9, 200, 470)
    d.linha((3, 3), (3, 8.9), (8.9, 8.9))


def impressora(d: Desenho):
    """Imprimir PDFs."""
    d.linha((6, 9), (6, 3), (7, 2), (17, 2), (18, 3), (18, 9))
    d.linha((6, 18), (4, 18), (2, 16), (2, 11), (4, 9), (20, 9), (22, 11), (22, 16), (20, 18), (18, 18))
    d.retangulo(6, 14, 18, 22, 1)


def estetoscopio(d: Desenho):
    """Honorários Médicos (o mesmo do Conciliações AMES)."""
    d.linha((5, 2), (5, 4))
    d.linha((11, 2), (11, 4))
    d.linha((5, 3), (4, 3), (2, 5), (2, 9))
    d.arco(8, 9, 6, 0, 180)
    d.linha((14, 9), (14, 5), (12, 3), (11, 3))
    d.arco(14, 15, 6, 0, 180)
    d.linha((20, 15), (20, 12))
    d.circulo(20, 10, 2)


def caminhao(d: Desenho):
    """Fornecedores."""
    d.linha((5, 18), (3, 18), (2, 17), (2, 6), (4, 4), (12, 4), (14, 6), (14, 18))
    d.linha((9, 18), (15, 18))
    d.linha((14, 8), (17.5, 8), (22, 13.5), (22, 17), (21, 18), (19, 18))
    d.circulo(7, 18, 2)
    d.circulo(17, 18, 2)


def porta_saida(d: Desenho):
    """Rescisões (o desligamento: a porta e a seta de saída)."""
    d.linha((9, 21), (5, 21), (3, 19), (3, 5), (5, 3), (9, 3))
    d.linha((16, 17), (21, 12), (16, 7))
    d.linha((21, 12), (9, 12))


def predio(d: Desenho):
    """Imobilizado (o patrimônio)."""
    d.retangulo(4, 2, 20, 22, 2)
    for y in (6, 10, 14):
        d.ponto(9, y)
        d.ponto(15, y)
    d.linha((10, 22), (10, 18), (14, 18), (14, 22))


def prancheta(d: Desenho):
    """Notas de Contrato (o check list mensal)."""
    d.linha((8, 4), (6, 4), (4, 6), (4, 20), (6, 22), (18, 22), (20, 20), (20, 6), (18, 4), (16, 4))
    d.retangulo(8, 2, 16, 6, 1)
    d.linha((8, 13), (10.5, 15.5), (15.5, 10.5))



def relogio(d: Desenho):
    """Histórico de uso (quem usou e quando)."""
    d.circulo(12, 12, 10)
    d.linha((12, 6.5), (12, 12), (15.5, 14))


def envelope(d: Desenho):
    """Notas Pendentes (o e-mail com as notas para registrar)."""
    d.retangulo(2, 5, 22, 19, 2)
    d.linha((3, 6.5), (12, 13), (21, 6.5))


def grafico(d: Desenho):
    """Convênios (a receita do mês, seção RECEITAS)."""
    d.linha((2, 17), (8.5, 10.5), (13.5, 15.5), (22, 7))
    d.linha((16, 7), (22, 7), (22, 13))



def tabela(d: Desenho):
    """Planilha HM (a planilha mensal que vai para a Controladoria)."""
    d.retangulo(3, 3, 21, 21, 2)
    d.linha((3, 9), (21, 9))
    d.linha((3, 15), (21, 15))
    d.linha((9, 9), (9, 21))


def carteira(d: Desenho):
    """Crédito Estouro (o que o colaborador ficou devendo à folha)."""
    d.linha((18, 7), (18, 5), (16, 3), (5, 3), (3, 5))
    d.retangulo(3, 6, 21, 21, 2)
    d.retangulo(15, 11, 21, 16, 1)
    d.ponto(17.5, 13.5)


ICONES = [arquivo, arquivos, pasta, banco, pessoas, importar, moedas, lua, sol, check, alerta,
          erro, caixa, mais, seta_direita, olho, atualizar, impressora, estetoscopio, caminhao, porta_saida,
          predio, prancheta, relogio, envelope, grafico, tabela, carteira]


def gerar_todos(pasta_destino: Path = PASTA_ICONES) -> list[Path]:
    pasta_destino.mkdir(parents=True, exist_ok=True)
    gerados = []
    for funcao in ICONES:
        desenho = Desenho()
        funcao(desenho)
        caminho = pasta_destino / f"{funcao.__name__}.png"
        desenho.gravar(caminho)
        gerados.append(caminho)
    return gerados


def simbolo_do_logo(logo: Image.Image) -> Image.Image:
    """O símbolo do logo, num quadrado transparente. O texto do logo é cinza (vermelho, verde e azul quase
    iguais); o símbolo é colorido: fica a caixa dos pixels coloridos e visíveis."""
    logo = logo.convert("RGBA")
    pixels = logo.load()
    xs, ys = [], []
    for y in range(logo.height):
        for x in range(logo.width):
            r, g, b, a = pixels[x, y]
            if a > 40 and max(r, g, b) - min(r, g, b) > 40:
                xs.append(x)
                ys.append(y)
    simbolo = logo.crop((min(xs), min(ys), max(xs) + 1, max(ys) + 1))
    lado = max(simbolo.size)
    quadrado = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    quadrado.alpha_composite(simbolo, ((lado - simbolo.width) // 2, (lado - simbolo.height) // 2))
    return quadrado


def gerar_logo_e_icone(logo: Path = LOGO_ORIGINAL, pasta_icones: Path = PASTA_ICONES,
                       pasta_recursos: Path = PASTA_RECURSOS) -> list[Path]:
    """Marca do menu (logo.png) e ícone do .exe e das janelas (icone.ico), feitos do símbolo do logo."""
    simbolo = simbolo_do_logo(Image.open(logo))
    marca = pasta_icones / "logo.png"
    simbolo.resize((TAMANHO_LOGO, TAMANHO_LOGO), Image.LANCZOS).save(marca)
    icone = pasta_recursos / "icone.ico"
    simbolo.resize((256, 256), Image.LANCZOS).save(icone, sizes=TAMANHOS_ICO)
    return [marca, icone]


if __name__ == "__main__":
    for caminho in gerar_todos():
        print(caminho)
    if LOGO_ORIGINAL.is_file():
        for caminho in gerar_logo_e_icone():
            print(caminho)
