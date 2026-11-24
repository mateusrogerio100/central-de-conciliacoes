"""Junta tudo: é o único módulo que a tela chama (seção 6 da especificação).

Ordem: lote do Tasy -> PDFs (com andamento) -> _sem_pdf.txt -> conferência -> relatório Excel.
Também prepara o que a tela mostra (confirmação dos arquivos escolhidos e resumo do resultado) e
guarda as últimas pastas usadas: a tela só exibe.

Nunca levanta exceção por problema em arquivo: lote ilegível, PDF com erro e relatório que não
pôde ser gravado vão para o resultado (e para o relatório, quando ele é gravado).
Levanta ValueError só se a própria chamada estiver incompleta (a tela valida antes).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from modulos.conferencia_nf import configuracao as cfg
from modulos.conferencia_nf import gabarito as gabarito_de_contas
from modulos.conferencia_nf import leitor_pdfs
from modulos.conferencia_nf.conferencia import aviso_pasta_de_outro_dia, conferir, nome_unidade
from modulos.conferencia_nf.leitor_lote import ler_lote
from modulos.conferencia_nf.modelos import (
    ErroLeitura, FalhaLeitura, NotaPdf, NotaSemPdf, Resultado, Situacao,
)
from modulos.conferencia_nf.relatorio import gerar_relatorio

Progresso = Callable[[str, float | None], None]


@dataclass
class ResultadoConferencia:
    """O que a tela mostra depois de conferir um lote."""

    arquivo_lote: Path
    pasta_pdfs: Path
    pasta_saida: Path
    resultados: list[Resultado] = field(default_factory=list)
    notas: list[NotaPdf] = field(default_factory=list)
    falhas_lote: list[FalhaLeitura] = field(default_factory=list)
    falhas_pdf: list[FalhaLeitura] = field(default_factory=list)
    sem_pdf: list[NotaSemPdf] = field(default_factory=list)
    caminho_relatorio: Path | None = None
    erro_relatorio: str = ""
    pasta_gabarito: Path | None = None
    erro_gabarito: str = ""                  # o gabarito não pôde ser lido: conferiu sem ele
    cnpj_unidade: str = ""                   # S15: unidade escolhida na tela

    def quantidade(self, situacao: Situacao) -> int:
        return sum(1 for r in self.resultados if r.situacao == situacao)

    @property
    def conferidos(self) -> int:
        """Pilha verde: o programa conferiu tudo; falta só olhar as contas."""
        return self.quantidade(Situacao.OK)

    @property
    def a_mao(self) -> list[Resultado]:
        """Pilha "conferir com a nota impressa" (tudo o que não é OK)."""
        return [r for r in self.resultados if r.situacao != Situacao.OK]

    @property
    def repetidos(self) -> list[NotaPdf]:
        return [n for n in self.notas if n.repetida_de]

    @property
    def sem_lancamento(self) -> list[NotaPdf]:
        """PDFs lidos que não casaram com nenhum fato (sem contar os repetidos)."""
        return [n for n in self.notas if not n.usada and not n.repetida_de]


def contar_pdfs(pasta: Path) -> int:
    """Quantos PDFs há na pasta e nas subpastas (para a tela mostrar antes de conferir)."""
    return len(leitor_pdfs.listar_pdfs(pasta))


def contar_xmls(pasta: Path) -> int:
    return len(leitor_pdfs.listar_xmls(pasta))


def caminho_novo_relatorio(pasta_saida: Path, agora: datetime) -> Path:
    """Conferencia_NF_<data e hora>.xlsx; se já existir (mesmo segundo), acrescenta _2, _3..."""
    nome = cfg.NOME_RELATORIO.format(data_hora=agora.strftime(cfg.FORMATO_DATA_HORA_NOME))
    caminho = Path(pasta_saida) / nome
    numero = 2
    while caminho.exists():
        caminho = caminho.with_name(f"{Path(nome).stem}_{numero}{Path(nome).suffix}")
        numero += 1
    return caminho


def processar(arquivo_lote: Path, pasta_pdfs: Path, pasta_saida: Path,
              progresso: Progresso | None = None,
              pasta_gabarito: Path | None = None,
              cnpj_unidade: str | None = None) -> ResultadoConferencia:
    """Confere o lote com os PDFs e grava o relatório na pasta de saída. cnpj_unidade: a unidade
    escolhida na tela, para conferir o CNPJ do destinatário / tomador das notas (S15)."""
    if not arquivo_lote or not pasta_pdfs or not pasta_saida:
        raise ValueError("Escolha o lote do Tasy, a pasta dos PDFs e a pasta de saída.")
    arquivo_lote, pasta_pdfs, pasta_saida = Path(arquivo_lote), Path(pasta_pdfs), Path(pasta_saida)
    resultado = ResultadoConferencia(arquivo_lote, pasta_pdfs, pasta_saida,
                                     cnpj_unidade=cnpj_unidade or "")

    def avisar(texto: str, fracao: float | None):
        if progresso:
            progresso(texto, fracao)

    avisar("Lendo o lote do Tasy...", None)
    try:
        fatos = ler_lote(arquivo_lote)
    except ErroLeitura as erro:
        fatos = []
        resultado.falhas_lote.append(FalhaLeitura(arquivo_lote.name,
                                                  f"Não foi possível ler o lote: {erro}"))

    resultado.notas, resultado.falhas_pdf = leitor_pdfs.ler_pasta(pasta_pdfs, progresso)
    resultado.sem_pdf = leitor_pdfs.ler_sem_pdf(pasta_pdfs)

    avisar("Conferindo os lançamentos...", None)
    resultado.resultados = conferir(fatos, resultado.notas, resultado.sem_pdf,
                                    cnpj_unidade)
    gabarito_usado = None
    if pasta_gabarito:
        avisar("Conferindo as contas pelo gabarito...", None)
        resultado.pasta_gabarito = Path(pasta_gabarito)
        try:
            gabarito = gabarito_de_contas.abrir_gabarito(resultado.pasta_gabarito)
        except ErroLeitura as erro:
            resultado.erro_gabarito = str(erro)
        else:
            if gabarito.historico or gabarito.padroes:
                gabarito_de_contas.conferir_contas(resultado.resultados, gabarito)
                gabarito_usado = str(gabarito.caminho)
            else:
                resultado.erro_gabarito = ("O gabarito de contas ainda está vazio: ensine com o "
                                           "Movimento contábil já revisado (aba \"Gabarito de "
                                           "contas\").")

    avisar("Gravando o relatório...", None)
    agora = datetime.now()
    caminho = caminho_novo_relatorio(pasta_saida, agora)
    try:
        pasta_saida.mkdir(parents=True, exist_ok=True)
        resultado.caminho_relatorio = gerar_relatorio(
            caminho, resultado.resultados, resultado.notas, resultado.falhas_lote,
            resultado.falhas_pdf, resultado.sem_pdf, [arquivo_lote.name], agora,
            gabarito_usado, cnpj_unidade)
    except OSError as erro:
        resultado.erro_relatorio = f"Não foi possível gravar o relatório {caminho.name}: {erro}"
    avisar("Pronto.", 1.0)
    return resultado


# ---------------------------------------------------------------------------
# O que a tela mostra
# ---------------------------------------------------------------------------


def confirmar_lote(arquivo_lote: Path) -> tuple[str, str]:
    """Linha de confirmação do cartão do lote: (texto, status "ok" ou "erro")."""
    try:
        fatos = ler_lote(arquivo_lote)
    except ErroLeitura as erro:
        return f"Não é o lote esperado: {erro}", "erro"
    if not fatos:
        return "O lote não tem nenhum lançamento.", "erro"
    lancamentos = sum(len(f.lancamentos) for f in fatos)
    return f"{len(fatos)} fatos contábeis, {lancamentos} lançamentos", "ok"


def confirmar_pasta_pdfs(pasta: Path) -> tuple[str, str]:
    """Linha de confirmação do cartão da pasta dos PDFs: (texto, status "ok" ou "atencao")."""
    quantidade, xmls = contar_pdfs(pasta), contar_xmls(pasta)
    if quantidade == 0 and xmls == 0:
        return "Nenhum PDF nem XML nesta pasta nem nas subpastas", "atencao"
    texto = f"{quantidade} PDF{'s' if quantidade != 1 else ''}"
    if xmls:
        texto += f" e {xmls} XML{'s' if xmls != 1 else ''}"
    return f"{texto} (com as subpastas)", "ok"


@dataclass
class LinhaTela:
    texto: str
    status: str               # "ok", "atencao" ou "erro"
    valor: str | None = None


@dataclass
class ResumoTela:
    numeros: list[tuple]                  # (número, legenda, tom) dos três blocos
    motivos: list[tuple[str, int]]        # tabela "Conferir à mão, por motivo"
    conferencias: list[LinhaTela]
    selo: tuple[str, str]                 # (texto, status) ao lado do título "Resultado"
    erro: str = ""                        # o relatório não saiu: a tela mostra só a mensagem


def resumir(resultado: ResultadoConferencia) -> ResumoTela:
    """Números, tabela e conferências da área "Resultado" da tela."""
    a_mao = resultado.a_mao
    numeros = [
        (resultado.conferidos, "conferidos pelo programa: só olhar as contas", "ok"),
        (len(a_mao), "conferir com a nota impressa", "atencao" if a_mao else "ok"),
        (len(resultado.sem_lancamento), "PDFs sem lançamento neste lote", "principal"),
    ]
    motivos = [(cfg.MOTIVOS[s], resultado.quantidade(Situacao(s)))
               for s in cfg.ORDEM_SITUACAO if s != Situacao.OK.value]

    conferencias = []
    outro_dia = aviso_pasta_de_outro_dia(resultado.notas)       # S17: o primeiro aviso, em vermelho
    if outro_dia:
        conferencias.append(LinhaTela(outro_dia, "erro"))
    for falha in resultado.falhas_lote:
        conferencias.append(LinhaTela(falha.motivo, "erro"))
    if resultado.falhas_pdf:
        quantidade = len(resultado.falhas_pdf)
        conferencias.append(LinhaTela(
            f"{quantidade} PDF{'s' if quantidade > 1 else ''} com erro de leitura (aba \"Erros de "
            "leitura\")", "erro"))
    else:
        if any(n.xml for n in resultado.notas):
            texto = f"Todos os PDFs e XMLs foram lidos ({len(resultado.notas)} notas)"
        else:
            texto = f"Todos os {len(resultado.notas)} PDFs foram lidos"
        conferencias.append(LinhaTela(texto, "ok"))
        divergentes = [n for n in resultado.notas if n.diferencas_pdf]
        if divergentes:
            conferencias.append(LinhaTela("Notas em que o XML e o PDF não dizem o mesmo",
                                          "atencao", str(len(divergentes))))
    if resultado.repetidos:
        conferencias.append(LinhaTela("PDFs repetidos (mesma nota em duas pastas): o segundo é "
                                      "ignorado", "atencao", str(len(resultado.repetidos))))
    if resultado.sem_pdf:
        conferencias.append(LinhaTela(f"Notas que vieram sem DANFE ({cfg.ARQUIVO_SEM_PDF})",
                                      "atencao", str(len(resultado.sem_pdf))))
    if resultado.erro_gabarito:
        conferencias.append(LinhaTela(f"Gabarito de contas: {resultado.erro_gabarito}",
                                      "atencao"))
    elif resultado.pasta_gabarito:
        fora = [a for r in resultado.resultados for a in r.contas if not a.confere]
        conferencias.append(LinhaTela(
            "Contas diferentes do gabarito ou sem histórico (aba \"Contas a conferir\")",
            "atencao" if fora else "ok", str(len(fora))))
    if resultado.cnpj_unidade and resultado.resultados:
        erradas = [r for r in resultado.resultados if r.confere_destinatario == "ERRADO"]
        unidade = cfg.UNIDADES_FUNDACAO.get(resultado.cnpj_unidade, resultado.cnpj_unidade)
        if erradas:
            conferencias.append(LinhaTela(f"Notas com CNPJ diferente do da unidade {unidade}",
                                          "erro", str(len(erradas))))
        else:
            conferencias.append(LinhaTela(f"CNPJ das notas confere com a unidade {unidade}",
                                          "ok"))
    cmd = [r for r in resultado.resultados if r.centro_custo_cmd]      # S18
    if cmd:
        conferencias.append(LinhaTela(cfg.MOTIVO_CENTRO_CUSTO_CMD, "atencao", str(len(cmd))))
    diluir = [r for r in resultado.resultados if r.diluicao]        # S19
    if diluir:
        conferencias.append(LinhaTela(f"{cfg.MOTIVO_DILUICAO} (software, uniforme, enxoval)", "atencao",
                                      str(len(diluir))))
    reclassificar = [r for r in resultado.resultados if r.reclassificar]       # S20
    if reclassificar:
        conferencias.append(LinhaTela("Fornecedores a reclassificar: no crédito, trocar pela conta do "
                                      "fornecedor?; no débito, foi provisionada?", "atencao",
                                      str(len(reclassificar))))
    nao_fecham = [r for r in resultado.resultados if not r.partidas_ok]
    if resultado.resultados and not nao_fecham:
        conferencias.append(LinhaTela("Partidas x contrapartidas fecham em todos os fatos", "ok"))
    elif nao_fecham:
        conferencias.append(LinhaTela("Fatos com partidas e contrapartidas que não fecham",
                                      "erro", str(len(nao_fecham))))

    problemas = (resultado.falhas_lote or resultado.falhas_pdf or nao_fecham
                 or resultado.quantidade(Situacao.DIVERGENTE))
    if outro_dia:
        selo = ("Confira a pasta dos PDFs", "erro")
    elif problemas:
        selo = ("Concluído com alertas", "atencao")
    else:
        selo = ("Concluído", "ok")
    return ResumoTela(numeros, motivos, conferencias, selo, resultado.erro_relatorio)


# ---------------------------------------------------------------------------
# Gabarito de contas (S14): ensinar e confirmar a pasta
# ---------------------------------------------------------------------------


def ensinar_gabarito(pasta_gabarito: Path, arquivos: list[Path],
                     progresso: Progresso | None = None) -> gabarito_de_contas.ResultadoEnsino:
    if not pasta_gabarito or not arquivos:
        raise ValueError("Escolha a pasta do gabarito e os arquivos de Movimento contábil.")
    return gabarito_de_contas.ensinar(Path(pasta_gabarito), [Path(a) for a in arquivos],
                                      progresso)


def confirmar_pasta_gabarito(pasta: Path) -> tuple[str, str]:
    """Linha de confirmação do cartão da pasta do gabarito: (texto, status)."""
    try:
        gabarito = gabarito_de_contas.abrir_gabarito(pasta)
    except ErroLeitura as erro:
        return str(erro), "erro"
    if not gabarito.historico and not gabarito.padroes:
        return "Ainda sem gabarito nesta pasta: ensine com o Movimento contábil", "atencao"
    return (f"{len(gabarito.historico)} combinações aprendidas, {len(gabarito.padroes)} "
            f"padrões, {len(gabarito.fatos_aprendidos)} fatos ensinados"), "ok"


def confirmar_movimentos(arquivos: list[Path]) -> tuple[str, str]:
    """Linha de confirmação dos arquivos para ensinar."""
    fatos = falhas = 0
    for arquivo in arquivos:
        try:
            fatos += len(ler_lote(arquivo))
        except ErroLeitura:
            falhas += 1
    if falhas:
        return f"{falhas} arquivo(s) não puderam ser lidos (veja ao ensinar)", "atencao"
    return f"{len(arquivos)} arquivo(s), {fatos} fatos contábeis", "ok"


# ---------------------------------------------------------------------------
# Unidade conferida (S15): a lista da tela
# ---------------------------------------------------------------------------


def opcoes_unidades() -> list[str]:
    """Textos da lista "Unidade conferida": 'AME Cidade Alfa (98.765.432/0004-30)'."""
    return [nome_unidade(cnpj) for cnpj in cfg.UNIDADES_FUNDACAO]


def cnpj_da_opcao(texto: str) -> str | None:
    """O CNPJ da unidade escolhida na lista; None se o texto não for uma das opções."""
    return next((cnpj for cnpj in cfg.UNIDADES_FUNDACAO if nome_unidade(cnpj) == texto), None)


def opcao_do_cnpj(cnpj: str | None) -> str:
    """O texto da lista para o CNPJ (vazio se não for de uma unidade)."""
    return nome_unidade(cnpj) if cnpj in cfg.UNIDADES_FUNDACAO else ""


# ---------------------------------------------------------------------------
# Últimas pastas usadas (%APPDATA%\CentralConciliacoes\conferencia_nf.json)
# ---------------------------------------------------------------------------

NOME_ARQUIVO_PASTAS = "conferencia_nf.json"


def caminho_pastas_usadas() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "CentralConciliacoes" / NOME_ARQUIVO_PASTAS


def _ler_guardado() -> dict:
    """O conteúdo do conferencia_nf.json. Arquivo ausente ou estragado = vazio."""
    try:
        dados = json.loads(caminho_pastas_usadas().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def ler_unidade_usada() -> str:
    """CNPJ da unidade da última conferência (vazio se não houver ou não for mais da lista)."""
    cnpj = _ler_guardado().get("unidade")
    return cnpj if cnpj in cfg.UNIDADES_FUNDACAO else ""


def ler_pastas_usadas() -> dict[str, Path]:
    """{"lote", "pdfs", "saida"} -> última pasta usada. Arquivo ausente ou estragado = vazio."""
    dados = _ler_guardado()
    return {chave: Path(valor) for chave, valor in dados.items()
            if chave in ("lote", "pdfs", "saida", "gabarito", "movimentos")
            and isinstance(valor, str) and valor}


def salvar_pastas_usadas(arquivo_lote: Path | None = None, pasta_pdfs: Path | None = None,
                         pasta_saida: Path | None = None, pasta_gabarito: Path | None = None,
                         pasta_movimentos: Path | None = None,
                         cnpj_unidade: str | None = None) -> bool:
    """Guarda as pastas usadas (as não informadas continuam como estavam). False se não
    conseguir (não é essencial)."""
    caminho = caminho_pastas_usadas()
    novas = {"lote": Path(arquivo_lote).parent if arquivo_lote else None, "pdfs": pasta_pdfs,
             "saida": pasta_saida, "gabarito": pasta_gabarito, "movimentos": pasta_movimentos}
    dados = {chave: str(valor) for chave, valor in ler_pastas_usadas().items()}
    if ler_unidade_usada():
        dados["unidade"] = ler_unidade_usada()
    dados.update({chave: str(valor) for chave, valor in novas.items() if valor})
    if cnpj_unidade:
        dados["unidade"] = cnpj_unidade
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        return False
    return True
