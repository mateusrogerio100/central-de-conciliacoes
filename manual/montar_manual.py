"""Monta o manual em PDF: python -m manual.montar_manual

Junta, numa página HTML:
- capa e sumário;
- Parte I (uso): as seções gerais do MANUAL_DE_USO.md e, para cada módulo (na ordem do menu), o print do
  exemplo fictício e o INSTRUCOES_DE_USO.md dele — o mesmo texto da aba "Instruções de uso";
- Parte II (manutenção): manual\\MANUTENCAO_PROGRAMADOR.md.

Depois o Microsoft Edge (que todo Windows 11 tem) imprime a página em PDF, sem biblioteca nova. Rode antes
`python -m manual.tirar_prints`: os prints saem de manual\\saida\\prints\\. O PDF sai em manual\\saida\\.
"""

from __future__ import annotations

import html
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA_SAIDA = RAIZ / "manual" / "saida"
PASTA_PRINTS = PASTA_SAIDA / "prints"
EDGE = [Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")]

# seções do MANUAL_DE_USO.md que entram na Parte I (título da seção -> capítulo)
SECOES_GERAIS_INICIO = ["1. Abrir o programa", "2. A janela", "3. Como usar cada módulo"]
SECAO_GERAL_FIM = "4. Quando algo dá errado"
FIM_DA_SECAO_3 = "### Instruções de cada módulo"          # a tabela-resumo não entra (cada módulo tem capítulo)

LEGENDAS = {
    "janela_inicial": "A janela da Central ao abrir: o menu à esquerda, dividido em seções, e o módulo "
                      "Imprimir PDFs, que é o que abre mais rápido.",
    "modo_escuro": "A mesma Central no modo escuro (botão no pé do menu).",
    "instrucoes_de_uso": "A aba Instruções de uso de um módulo: o mesmo texto deste manual, dentro do programa.",
    "conferencia_nf": "Lote fictício com 4 notas: 2 conferidas pelo programa, 2 para conferir com a nota "
                      "impressa (uma com valor diferente, outra sem nota na pasta) e 1 XML sem lançamento.",
    "escrituracao_tomados": "Exportação fictícia de um lote: 3 notas vão para o arquivo, 1 emitida em outro "
                            "mês fica para lançar à mão, 1 já escriturada e 1 cancelada ficam de fora.",
    "conferencia_iss": "Aba Cidade Alfa com notas fictícias: conferidas (uma pelo número \"ano + zeros\"), uma "
                       "escriturada duas vezes, uma com valor diferente, uma só no Tasy, uma só na prefeitura "
                       "e uma cancelada.",
    "bancos": "Balancete e extratos fictícios: 2 contas OK, 1 com diferença, 1 sem extrato e 1 extrato de "
              "conta que não está no balancete.",
    "clientes_cmd_conciliacao": "Conciliação fictícia: 4 clientes OK (inclusive um com o nome cortado no "
                                "financeiro), 1 divergente, 1 só no balancete e 1 só no financeiro.",
    "clientes_cmd_import": "Import Contábil depois dos dois passos: 3 relatórios juntados no Rel_Geral e o "
                           ".txt gerado com 5 lançamentos.",
    "estoque": "EST-01 fictícia: 3 contas conciliadas, 1 com diferença e 1 local do SCF sem conta no balancete.",
    "imobilizado": "AME fictício: 4 contas conferem, 2 diferenças explicadas (bem adquirido e baixa) e 1 "
                   "diferença de centavos para analisar.",
    "credito_estouro": "Junho fictício: 5 colaboradores com 0256 em maio (cobrados no 0258, um parcelado, um baixado "
                       "na rescisão e um não cobrado, para conferir), um parcelamento quitado e dois afastados; a "
                       "diferença sem explicação é zero.",
    "fornecedores": "Unidade fictícia: 4 fornecedores OK (um deles com o cadastro duplicado somado), 1 "
                    "divergente, \"a reclassificar\" só no balancete e 1 fornecedor só no financeiro.",
    "rescisoes": "Junho fictício: 4 pagamentos achados (no PDF e na lista anterior), 1 pago a mais, 1 não "
                 "encontrado; a prova fecha com \"sem explicação\" igual a zero.",
    "honorarios_ames": "Aba AMEs: 3 médicos/clínicas OK (um com repasses em dois grupos), 1 divergente, 1 "
                       "conta sem repasse e 1 repasse sem conta.",
    "honorarios_hospital_exemplo": "Aba Hospital Exemplo: 4 OK (um só bate somando a Remoção), 1 divergente, 1 só no "
                             "Senior e 1 linha do PDF de Remoção sem conta no balancete.",
    "planilha_hm": "Setembro fictício: 5 eventos, um centro de custo novo num evento que já existia e um evento novo "
                   "que entrou na seção de fixos pela conta dele; o TOTAL GERAL fecha com o Movimento.",
    "subvencoes": "Planilhas fictícias de agosto preenchidas com setembro: 6 contas, 2 com o patrimônio "
                  "diferente do contábil e o aviso de uma conta nova no balancete.",
    "efd_contribuicoes": "Setembro fictício: 3 notas de pessoa jurídica no SPED (uma de um cliente novo, que "
                         "ganha o próximo código do cadastro) e 1 nota de pessoa física fora do SPED.",
    "imprimir_pdfs": "Pasta fictícia com 5 PDFs: 7 folhas para colocar na impressora e 1 PDF danificado "
                     "(fica em vermelho, fora da impressão).",
}


# ---------------------------------------------------------------------------
# Markdown simples -> HTML (títulos, parágrafos, listas com níveis, citações, tabelas, negrito, itálico,
# código e links — o que os INSTRUCOES_DE_USO.md usam)
# ---------------------------------------------------------------------------
RE_ITEM = re.compile(r"^(\s*)([-*]|\d+\.)\s+(.*)$")
RE_TITULO = re.compile(r"^(#{1,6})\s+(.*)$")


def _inline(texto: str) -> str:
    # o código sai antes (vira uma marca \0N\0) para o negrito em volta dele, "**Dinheiro em `Decimal`**",
    # ser visto como um trecho só; no fim a marca volta a ser o código
    codigos = []

    def guardar(m):
        codigos.append(f"<code>{html.escape(m[1])}</code>")
        return f"\0{len(codigos) - 1}\0"

    texto = html.escape(re.sub(r"`([^`]+)`", guardar, texto), quote=False)
    texto = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
                   lambda m: f'<a href="{m[2]}">{m[1]}</a>' if m[2].startswith("http") else m[1], texto)
    texto = re.sub(r"&lt;(https?://[^\s&]+)&gt;", r'<a href="\1">\1</a>', texto)
    texto = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", texto)
    texto = re.sub(r"(?<![\w*])\*(?![\s*])(.+?)(?<![\s*])\*(?![\w*])", r"<em>\1</em>", texto)
    return re.sub(r"\0(\d+)\0", lambda m: codigos[int(m[1])], texto)


def _tabela(linhas: list[str]) -> str:
    def celulas(linha):
        return [c.strip() for c in linha.strip().strip("|").split("|")]

    cabecalho, corpo = celulas(linhas[0]), [celulas(l) for l in linhas[2:]]
    partes = ["<table><thead><tr>"] + [f"<th>{_inline(c)}</th>" for c in cabecalho] + ["</tr></thead><tbody>"]
    for linha in corpo:
        partes += ["<tr>"] + [f"<td>{_inline(c)}</td>" for c in linha] + ["</tr>"]
    return "".join(partes + ["</tbody></table>"])


def markdown_para_html(texto: str, deslocar_titulos: int = 0, ancora=None) -> str:
    """deslocar_titulos: soma aos níveis (# vira h2 com 1). ancora(titulo) -> id para os títulos (opcional)."""
    saida: list[str] = []
    paragrafo: list[str] = []
    listas: list[tuple[int, str]] = []          # (recuo, "ul"/"ol") abertas, a de dentro por último
    texto_item: list[str] = []                  # o item aberto e as linhas que continuam ele
    linhas = texto.splitlines()

    def fechar_item():
        if texto_item:                          # convertido de uma vez: um negrito pode quebrar a linha
            saida.append(_inline(" ".join(texto_item)))
            texto_item.clear()

    def fechar_paragrafo():
        fechar_item()
        if paragrafo:
            saida.append(f"<p>{_inline(' '.join(paragrafo))}</p>")
            paragrafo.clear()

    def fechar_listas(ate: int = -1):
        while listas and listas[-1][0] > ate:
            saida.append(f"</li></{listas.pop()[1]}>")

    i = 0
    while i < len(linhas):
        linha = linhas[i]
        if not linha.strip() or linha.strip() == "---":      # o separador "---" não entra: os títulos já separam
            fechar_paragrafo()
            i += 1
            continue
        titulo = RE_TITULO.match(linha)
        item = RE_ITEM.match(linha)
        if titulo:
            fechar_paragrafo()
            fechar_listas()
            nivel = min(len(titulo[1]) + deslocar_titulos, 6)
            id_ = f' id="{ancora(titulo[2])}"' if ancora else ""
            saida.append(f"<h{nivel}{id_}>{_inline(titulo[2])}</h{nivel}>")
        elif linha.lstrip().startswith("|"):
            fechar_paragrafo()
            fechar_listas()
            bloco = []
            while i < len(linhas) and linhas[i].lstrip().startswith("|"):
                bloco.append(linhas[i])
                i += 1
            saida.append(_tabela(bloco))
            continue
        elif linha.startswith(">"):
            fechar_paragrafo()
            fechar_listas()
            bloco = []
            while i < len(linhas) and linhas[i].startswith(">"):
                bloco.append(linhas[i][1:].strip())
                i += 1
            saida.append(f"<blockquote><p>{_inline(' '.join(bloco))}</p></blockquote>")
            continue
        elif item:
            fechar_paragrafo()
            recuo, marcador, conteudo = len(item[1]), item[2], item[3]
            tipo = "ol" if marcador[0].isdigit() else "ul"
            inicio = f' start="{marcador[:-1]}"' if tipo == "ol" and marcador != "1." else ""
            if not listas or recuo > listas[-1][0]:
                saida.append(f"<{tipo}{inicio}><li>")
                listas.append((recuo, tipo))
            else:
                fechar_listas(recuo)
                if listas and listas[-1][1] != tipo:
                    saida.append(f"</li></{listas.pop()[1]}><{tipo}{inicio}><li>")
                    listas.append((recuo, tipo))
                elif listas:
                    saida.append("</li><li>")
                else:
                    saida.append(f"<{tipo}{inicio}><li>")
                    listas.append((recuo, tipo))
            texto_item.append(conteudo)
        elif listas and linha.startswith(" "):
            texto_item.append(linha.strip())                    # continuação do item aberto
        else:
            fechar_item()
            fechar_listas()
            paragrafo.append(linha.strip())
        i += 1
    fechar_paragrafo()
    fechar_listas()
    return "\n".join(saida)


# ---------------------------------------------------------------------------
# Montagem
# ---------------------------------------------------------------------------
def _secoes_do_manual_de_uso() -> dict[str, str]:
    """Título de cada seção "## " do MANUAL_DE_USO.md -> o texto dela."""
    texto = (RAIZ / "MANUAL_DE_USO.md").read_text(encoding="utf-8")
    secoes, atual = {}, None
    for linha in texto.splitlines():
        if linha.startswith("## "):
            atual = linha[3:].strip()
            secoes[atual] = []
        elif atual is not None and linha.strip() != "---":
            secoes[atual].append(linha)
    return {titulo: "\n".join(linhas).strip() for titulo, linhas in secoes.items()}


def _sem_titulo_principal(texto: str) -> str:
    """Tira o "# Módulo — instruções de uso" do começo (o capítulo já tem título)."""
    linhas = texto.splitlines()
    while linhas and not linhas[0].strip():
        linhas.pop(0)
    if linhas and linhas[0].startswith("# "):
        linhas.pop(0)
    return "\n".join(linhas)


def _figura(nome: str) -> str:
    caminho = PASTA_PRINTS / f"{nome}.png"
    if not caminho.is_file():
        raise FileNotFoundError(f"Falta o print {caminho.name}: rode antes python -m manual.tirar_prints")
    return (f'<figure><img src="prints/{nome}.png" alt=""><figcaption>{html.escape(LEGENDAS.get(nome, ""))}'
            "</figcaption></figure>")


def _prints_por_modulo() -> dict[str, list[str]]:
    from manual.ficticios import gerar_todos

    with tempfile.TemporaryDirectory() as pasta:
        exemplos = gerar_todos(Path(pasta))
    por_modulo: dict[str, list[str]] = {}
    for exemplo in exemplos:
        por_modulo.setdefault(exemplo.chave, []).append(exemplo.nome)
    return por_modulo


def montar_html(paginas: dict[int, int] | None = None) -> str:
    """paginas: número do capítulo -> página onde começa (para o sumário; None na primeira passada)."""
    from central import VERSAO, registro

    infos = {m.info.chave: m.info for m in registro.carregar_modulos() if m.ok}
    prints = _prints_por_modulo()
    gerais = _secoes_do_manual_de_uso()
    capitulos: list[tuple[str, str, str]] = []     # (id, título, html)

    def capitulo(titulo: str, corpo: str) -> None:
        capitulos.append((f"cap{len(capitulos) + 1}", titulo, corpo))

    abrir = markdown_para_html(gerais[SECOES_GERAIS_INICIO[0]], 1)
    janela = markdown_para_html(gerais[SECOES_GERAIS_INICIO[1]], 1)
    capitulo("Abrir o programa e conhecer a janela",
             abrir + _figura("janela_inicial") + janela + _figura("modo_escuro"))
    como_usar = gerais[SECOES_GERAIS_INICIO[2]].split(FIM_DA_SECAO_3)[0]
    capitulo("Como usar cada módulo", markdown_para_html(como_usar, 1) + _figura("instrucoes_de_uso"))
    for _secao, chaves in registro.SECOES:
        for chave in chaves:
            info = infos[chave]
            cabecalho = (f'<p class="contexto">{html.escape(info.contexto)}</p>'
                         f'<p class="descricao">{html.escape(info.descricao)}</p>')
            figuras = "".join(_figura(nome) for nome in prints.get(chave, []))
            instrucoes = (RAIZ / "modulos" / chave / "INSTRUCOES_DE_USO.md").read_text(encoding="utf-8")
            capitulo(info.nome, cabecalho + figuras + markdown_para_html(_sem_titulo_principal(instrucoes), 1))
    capitulo("Quando algo dá errado", markdown_para_html(gerais[SECAO_GERAL_FIM], 1))
    capitulos_uso = len(capitulos)

    manutencao = (RAIZ / "manual" / "MANUTENCAO_PROGRAMADOR.md").read_text(encoding="utf-8")
    capitulo("Manutenção — para quem for programar na Central",
             markdown_para_html(_sem_titulo_principal(manutencao), 1))

    sumario = []
    for numero, (id_, titulo, _corpo) in enumerate(capitulos, start=1):
        if numero == 1:
            sumario.append('<li class="parte">Parte I — Uso</li>')
        if numero == capitulos_uso + 1:
            sumario.append('<li class="parte">Parte II — Manutenção</li>')
        pagina = f'<span class="pagina">{paginas[numero]}</span>' if paginas and numero in paginas else ""
        sumario.append(f'<li><a href="#{id_}">{numero}. {html.escape(titulo)}</a>{pagina}</li>')

    corpo = []
    for numero, (id_, titulo, conteudo) in enumerate(capitulos, start=1):
        if numero == 1:
            corpo.append('<section class="parte"><h1>Parte I<br>Uso</h1><p>Como usar a Central e cada um dos '
                         'módulos. Os prints usam arquivos fictícios.</p></section>')
        if numero == capitulos_uso + 1:
            corpo.append('<section class="parte"><h1>Parte II<br>Manutenção</h1><p>Para um programador que '
                         'for manter ou ampliar a Central.</p></section>')
        corpo.append(f'<section class="capitulo"><h2 id="{id_}">{numero}. {html.escape(titulo)}</h2>{conteudo}'
                     "</section>")

    logo = (RAIZ / "recursos" / "logo_hospital_exemplo_256.png").as_uri()
    fontes = (RAIZ / "central" / "fontes").as_uri()
    hoje = date.today().strftime("%m/%Y")
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><title>Central de Conciliações — Manual</title>
<style>
@font-face {{ font-family: Plex; src: url("{fontes}/IBMPlexSans-Regular.ttf"); }}
@font-face {{ font-family: Plex; font-weight: bold; src: url("{fontes}/IBMPlexSans-Bold.ttf"); }}
@font-face {{ font-family: PlexMono; src: url("{fontes}/IBMPlexMono-Regular.ttf"); }}
@page {{ size: A4; margin: 18mm 16mm 18mm 16mm;
        @bottom-right {{ content: counter(page); font: 9pt Plex, sans-serif; color: #556074; }}
        @bottom-left {{ content: "Central de Conciliações · Manual · versão {VERSAO}"; font: 9pt Plex, sans-serif;
                        color: #556074; }} }}
@page :first {{ @bottom-right {{ content: none; }} @bottom-left {{ content: none; }} }}
body {{ font: 10.5pt/1.5 Plex, "Segoe UI", sans-serif; color: #172033; background: #ffffff; margin: 0; }}
h1, h2, h3, h4 {{ color: #1f3a68; line-height: 1.25; break-after: avoid; }}
h2 {{ font-size: 19pt; margin: 0 0 4mm; padding-bottom: 2mm; border-bottom: 2px solid #1f3a68; }}
h3 {{ font-size: 13pt; margin: 6mm 0 2mm; }}
h4 {{ font-size: 11pt; margin: 4mm 0 1.5mm; }}
p {{ margin: 0 0 2.2mm; }}
ul, ol {{ margin: 0 0 2.2mm; padding-left: 6mm; }}
li {{ margin: 0.6mm 0; }}
code {{ font-family: PlexMono, Consolas, monospace; font-size: 9pt; background: #e6ecf6; padding: 0 1mm;
        border-radius: 2px; }}
a {{ color: #1f3a68; text-decoration: none; }}
table {{ border-collapse: collapse; width: 100%; margin: 2mm 0 4mm; font-size: 9pt; break-inside: auto; }}
th, td {{ border: 1px solid #dde3ee; padding: 1.4mm 2mm; text-align: left; vertical-align: top; }}
th {{ background: #e6ecf6; color: #1f3a68; }}
tr {{ break-inside: avoid; }}
blockquote {{ margin: 2mm 0 3mm; padding: 2mm 4mm; background: #f3f5f9; border-left: 3px solid #1f3a68; }}
figure {{ margin: 3mm 0 5mm; break-inside: avoid; }}
figure img {{ width: 100%; border: 1px solid #dde3ee; border-radius: 4px; }}
figcaption {{ font-size: 9pt; color: #556074; margin-top: 1.5mm; }}
.capa {{ height: 255mm; display: flex; flex-direction: column; justify-content: center; text-align: center;
         break-after: page; }}
.capa img {{ width: 60mm; margin: 0 auto 12mm; }}
.capa h1 {{ font-size: 30pt; margin: 0 0 4mm; }}
.capa .subtitulo {{ font-size: 15pt; color: #556074; margin-bottom: 16mm; }}
.capa .rodape {{ font-size: 10.5pt; color: #556074; }}
.sumario {{ break-after: page; }}
.sumario ol {{ list-style: none; padding: 0; columns: 1; }}
.sumario li {{ margin: 1.6mm 0; font-size: 11pt; display: flex; }}
.sumario li a {{ flex: 1; border-bottom: 1px dotted #c3ccdb; }}
.sumario li .pagina {{ padding-left: 3mm; color: #556074; }}
.sumario li.parte {{ margin-top: 6mm; font-weight: bold; color: #1f3a68; font-size: 12pt; }}
section.parte {{ break-before: page; break-after: page; height: 240mm; display: flex; flex-direction: column;
                 justify-content: center; }}
section.parte h1 {{ font-size: 34pt; margin: 0 0 6mm; }}
section.parte p {{ font-size: 12pt; color: #556074; }}
section.capitulo {{ break-before: page; }}
section.parte + section.capitulo {{ break-before: auto; }}
.contexto {{ font-size: 9pt; color: #556074; margin: 0; text-transform: uppercase; letter-spacing: 0.04em; }}
.descricao {{ font-size: 11pt; margin: 1mm 0 3mm; }}
</style></head><body>
<div class="capa">
  <img src="{logo}" alt="">
  <h1>Central de Conciliações</h1>
  <div class="subtitulo">Manual de uso e de manutenção</div>
  <div class="rodape">Fundação Hospital Exemplo · Área contábil<br>
  Versão {VERSAO} · {hoje}</div>
</div>
<div class="sumario"><h2>Sumário</h2><ol>{"".join(sumario)}</ol></div>
{"".join(corpo)}
</body></html>
"""


def gerar_pdf(caminho_html: Path, caminho_pdf: Path) -> Path:
    edge = next((e for e in EDGE if e.is_file()), None)
    if edge is None:
        raise FileNotFoundError("Microsoft Edge não encontrado: abra o .html no navegador e imprima em PDF.")
    caminho_pdf.unlink(missing_ok=True)
    # perfil temporário: nunca usa (nem abre janela no) navegador de quem está rodando
    with tempfile.TemporaryDirectory() as perfil:
        subprocess.run([str(edge), "--headless=new", "--disable-gpu", "--no-first-run", f"--user-data-dir={perfil}",
                        "--no-pdf-header-footer", f"--print-to-pdf={caminho_pdf}", caminho_html.as_uri()],
                       check=True, timeout=300, capture_output=True)
    if not caminho_pdf.is_file():
        raise RuntimeError("O Edge não gerou o PDF.")
    return caminho_pdf


def paginas_dos_capitulos(caminho_pdf: Path) -> dict[int, int]:
    """Em que página começa cada capítulo ("N. Título" no alto da página; o sumário é a página 2)."""
    import pypdfium2 as pdfium

    paginas: dict[int, int] = {}
    documento = pdfium.PdfDocument(caminho_pdf)
    try:
        for indice in range(2, len(documento)):
            linhas = documento[indice].get_textpage().get_text_range().splitlines()
            for linha in linhas[:3]:
                achado = re.match(r"^(\d+)\. ", linha)
                if achado and int(achado[1]) not in paginas:
                    paginas[int(achado[1])] = indice + 1
    finally:
        documento.close()
    return paginas


def main() -> None:
    from central import VERSAO

    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
    caminho_html = PASTA_SAIDA / "manual.html"
    caminho_pdf = PASTA_SAIDA / f"Manual_Central_de_Conciliacoes_v{VERSAO}.pdf"
    # duas passadas: a primeira só descobre a página de cada capítulo, para o sumário
    caminho_html.write_text(montar_html(), encoding="utf-8")
    paginas = paginas_dos_capitulos(gerar_pdf(caminho_html, caminho_pdf))
    caminho_html.write_text(montar_html(paginas), encoding="utf-8")
    gerar_pdf(caminho_html, caminho_pdf)
    print(f"manual: {caminho_pdf}")


if __name__ == "__main__":
    sys.path.insert(0, str(RAIZ))
    main()
