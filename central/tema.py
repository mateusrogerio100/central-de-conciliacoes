"""
Tema visual da Central de Conciliações.

Todas as telas usam as cores, fontes e medidas deste arquivo.
Para mudar o visual do programa inteiro, basta mudar aqui.

Cada cor é um par (modo claro, modo escuro): o CustomTkinter escolhe
sozinho qual usar conforme ctk.set_appearance_mode("light" | "dark").
"""

from pathlib import Path

import customtkinter as ctk

from central.caminhos import caminho_interno


# ---------------------------------------------------------------------
# Cores (claro, escuro)
# ---------------------------------------------------------------------
# Paleta azul escuro (Etapa 9 da unificação, aprovada pelo usuário em 20/10/2026). Todas as combinações de
# texto e fundo passam com folga do contraste mínimo recomendado para leitura (4,5:1). As cores de situação
# (verde, laranja, vermelho) continuam as de antes: o azul não se confunde com nenhuma delas.
COR_FUNDO = ("#f3f5f9", "#0d1424")          # fundo da área de conteúdo
COR_SUPERFICIE = ("#ffffff", "#151f33")     # cartões e painéis
COR_BORDA = ("#dde3ee", "#26324a")          # bordas finas
COR_TEXTO = ("#172033", "#e6ebf3")          # texto principal
COR_TEXTO_SUAVE = ("#556074", "#9aa7bd")    # legendas, rótulos

COR_PRINCIPAL = ("#1f3a68", "#7fa6e8")          # botão principal, destaques
COR_PRINCIPAL_HOVER = ("#152a4f", "#9dbcf0")
COR_TEXTO_SOBRE_PRINCIPAL = ("#ffffff", "#0b1426")
COR_PRINCIPAL_SUAVE = ("#e6ecf6", "#1c2a45")    # fundo de ícones e números

COR_OK = ("#1b6e45", "#6cc996")
COR_OK_SUAVE = ("#e1f1e7", "#173328")
COR_ATENCAO = ("#a44a07", "#f2a65e")
COR_ATENCAO_SUAVE = ("#fbeedd", "#3a2a1a")
COR_ERRO = ("#b42318", "#f28b82")
COR_ERRO_SUAVE = ("#fde8e6", "#3b1f22")

# Menu lateral (escuro nos dois modos)
COR_MENU_FUNDO = ("#0f1e3c", "#0a1120")
COR_MENU_ITEM_ATIVO = ("#23396a", "#22365e")
COR_MENU_ITEM_HOVER = ("#192b52", "#16223b")
COR_MENU_TEXTO = ("#c5d0e4", "#c5d0e4")
COR_MENU_TEXTO_ATIVO = ("#ffffff", "#ffffff")
COR_MENU_SECAO = ("#8b9bbb", "#8b9bbb")
COR_MENU_BORDA = ("#2a3d66", "#1f2c47")
COR_MARCA = ("#ffffff", "#ffffff")              # quadrado do logo (o símbolo da Hospital Exemplo, colorido)

# ---------------------------------------------------------------------
# Medidas
# ---------------------------------------------------------------------
LARGURA_MENU = 248
RAIO_CARTAO = 14
RAIO_BOTAO = 10
RAIO_PEQUENO = 8
ALTURA_BOTAO = 48
ALTURA_BOTAO_PEQUENO = 36
LARGURA_MINIMA_ABA = 90          # aba com nome curto; nome longo cresce (6 abas cabem na janela mínima)
ALTURA_ITEM_MENU = 40             # 12 itens em 4 seções cabem nos 800 px da janela inicial
ESPACO_PAGINA_X = 40
ESPACO_PAGINA_Y = 32
ESPACO_ENTRE_BLOCOS = 24
ESPACO_INTERNO_CARTAO = 24
ESPACO_PEQUENO = 12
LARGURA_BORDA = 1

# Janela
LARGURA_JANELA = 1280
ALTURA_JANELA = 800
LARGURA_MINIMA_JANELA = 1100
ALTURA_MINIMA_JANELA = 700

# Componentes (GUIA_VISUAL, seções 2 a 4)
ALTURA_CAMPO = 44                 # campos como "Mês de referência"
TAMANHO_MARCA = 40                # quadrado do logo no menu
TAMANHO_ICONE_MENU = 18
ESPACO_SECAO_MENU = 10            # espaço acima de cada seção do menu, a partir da segunda
ESPACO_ABAIXO_SECAO_MENU = 6      # entre o nome da seção e o primeiro item
ESPACO_ITEM_MENU = 1              # acima e abaixo de cada item do menu
ESPACO_MARCA_MENU = (16, 14)      # acima e abaixo da marca no topo do menu
LARGURA_BARRA_MENU = 8            # barra de rolagem do menu (só aparece quando os itens não cabem)
TAMANHO_ICONE_BOTAO = 18
TAMANHO_QUADRO_ICONE = 40         # quadrado do ícone no CartaoArquivo
TAMANHO_ICONE_CARTAO = 22
TAMANHO_ICONE_CONFERENCIA = 18
TAMANHO_QUADRO_VAZIO = 72         # quadrado do ícone no EstadoVazio
TAMANHO_ICONE_VAZIO = 34
ALTURA_SELO = 24
ALTURA_BARRA_PROGRESSO = 8
ALTURA_BARRA_CARTAO = 4           # barrinha de "lendo..." no cartão de arquivo
LARGURA_BOTAO_RODAPE = 120        # botões secundários do rodapé do resultado
LARGURA_MINIMA_PRINCIPAL_RODAPE = 140   # menos que isto para o principal: rodapé em duas linhas
ESPACO_INTERNO_ARQUIVO = 14       # espaço interno do CartaoArquivo

# ---------------------------------------------------------------------
# Fontes
# ---------------------------------------------------------------------
FAMILIA_TEXTO = "IBM Plex Sans"
FAMILIA_NUMEROS = "IBM Plex Mono"
FAMILIA_RESERVA = "Segoe UI"   # usada se as fontes acima não carregarem


def _pasta_fontes() -> Path:
    """Pasta das fontes, funcionando tanto no Python quanto no .exe (central/fontes)."""
    return caminho_interno("central", "fontes")


def carregar_fontes() -> None:
    """
    Carrega as fontes IBM Plex da pasta central/fontes/.
    Se não conseguir, o programa segue com a Segoe UI (nada quebra).
    Chamar uma vez, antes de criar a janela principal.
    """
    global FAMILIA_TEXTO, FAMILIA_NUMEROS
    pasta = _pasta_fontes()
    arquivos = list(pasta.glob("*.ttf")) if pasta.exists() else []
    if not arquivos:
        FAMILIA_TEXTO = FAMILIA_NUMEROS = FAMILIA_RESERVA
        return
    for arquivo in arquivos:
        try:
            ctk.FontManager.load_font(str(arquivo))
        except Exception:
            FAMILIA_TEXTO = FAMILIA_NUMEROS = FAMILIA_RESERVA
            return


def fonte_titulo() -> ctk.CTkFont:
    return ctk.CTkFont(family=FAMILIA_TEXTO, size=28, weight="bold")


def fonte_subtitulo() -> ctk.CTkFont:
    return ctk.CTkFont(family=FAMILIA_TEXTO, size=16, weight="bold")


def fonte_texto() -> ctk.CTkFont:
    return ctk.CTkFont(family=FAMILIA_TEXTO, size=14)


def fonte_texto_forte() -> ctk.CTkFont:
    return ctk.CTkFont(family=FAMILIA_TEXTO, size=14, weight="bold")


def fonte_legenda() -> ctk.CTkFont:
    return ctk.CTkFont(family=FAMILIA_TEXTO, size=12)


def fonte_rotulo() -> ctk.CTkFont:
    """Rótulo em negrito acima de um campo (ex.: "Mês de referência")."""
    return ctk.CTkFont(family=FAMILIA_TEXTO, size=12, weight="bold")


def fonte_contexto() -> ctk.CTkFont:
    """Linha pequena acima do título do módulo (ex.: "Conciliações / Bancos")."""
    return ctk.CTkFont(family=FAMILIA_TEXTO, size=13)


def fonte_marca() -> ctk.CTkFont:
    """Nome do programa no topo do menu."""
    return ctk.CTkFont(family=FAMILIA_TEXTO, size=15, weight="bold")


def fonte_secao_menu() -> ctk.CTkFont:
    return ctk.CTkFont(family=FAMILIA_TEXTO, size=11, weight="bold")


TAMANHO_NUMERO_GRANDE = 28
TAMANHO_NUMERO_GRANDE_MINIMO = 14   # quadro estreito (janela pequena): o número encolhe até aqui para caber inteiro


def fonte_numero_grande(tamanho: int = TAMANHO_NUMERO_GRANDE) -> ctk.CTkFont:
    return ctk.CTkFont(family=FAMILIA_NUMEROS, size=tamanho, weight="bold")


def fonte_numero() -> ctk.CTkFont:
    return ctk.CTkFont(family=FAMILIA_NUMEROS, size=13)


def fonte_campo() -> ctk.CTkFont:
    """Texto digitado nos campos (números: mês, valores)."""
    return ctk.CTkFont(family=FAMILIA_NUMEROS, size=15)


def aplicar_tema_inicial(modo: str = "light") -> None:
    """Define o modo (claro/escuro) e carrega as fontes."""
    ctk.set_appearance_mode(modo)
    carregar_fontes()
