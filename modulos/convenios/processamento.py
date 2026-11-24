"""Junta tudo: é o único arquivo do módulo que a tela chama (seção 6 da especificação).

processar(): razão + planilha de receitas + equivalencias.csv -> classificação (C1 a C7) -> cópia da planilha
com o mês preenchido (P1 a P5) e relatório de conferência, na pasta de saída.
Nunca levanta exceção por problema em arquivo: o que não pôde ser lido ou gravado vai para o resultado.
Mês já preenchido sem substituir=True: nada é gravado e o resultado traz `mes_ja_preenchido` (a tela pergunta e
chama de novo com substituir=True).
Levanta ValueError só se a própria chamada estiver incompleta (a tela valida antes).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from central.preferencias import ler_preferencias_modulo, salvar_preferencias_modulo
from modulos.convenios import configuracao as cfg
from modulos.convenios.classificacao import Classificacao, classificar
from modulos.convenios.leitor_equivalencias import ler_equivalencias, pasta_sugerida
from modulos.convenios.leitor_planilha import ler_planilha
from modulos.convenios.leitor_razao import ler_razao
from modulos.convenios.modelos import Aviso, Equivalencias, ErroLeitura, Planilha, Razao
from modulos.convenios.normalizacao import formatar_valor
from modulos.convenios.preenchimento import Preenchimento, mes_ja_preenchido, preencher
from modulos.convenios.relatorio import gerar_relatorio

Progresso = Callable[[str, float | None], None]


def _caminho_livre(caminho: Path) -> Path:
    """O próprio caminho, ou com _2, _3... se já existir (nada é substituído sem perguntar)."""
    numero, original = 2, caminho
    while caminho.exists():
        caminho = original.with_name(f"{original.stem}_{numero}{original.suffix}")
        numero += 1
    return caminho


@dataclass
class ResultadoConvenios:
    """O que a tela mostra depois de processar."""

    razao: Razao | None = None
    planilha: Planilha | None = None
    equivalencias: Equivalencias | None = None
    classificacao: Classificacao | None = None
    preenchimento: Preenchimento | None = None
    mes_ja_preenchido: list[str] = field(default_factory=list)   # P1: perguntar antes de substituir
    caminho_planilha: Path | None = None
    caminho_relatorio: Path | None = None
    erro: str = ""             # não deu para processar (razão, planilha ou mês)
    erro_saida: str = ""       # não deu para gravar a cópia ou o relatório

    @property
    def avisos(self) -> list[Aviso]:
        avisos = []
        for parte in (self.razao, self.planilha, self.equivalencias, self.classificacao, self.preenchimento):
            if parte is not None:
                avisos += parte.avisos
        return avisos


def processar(razao: Path, planilha: Path, pasta_saida: Path, pasta_equivalencias: Path | None = None,
              substituir: bool = False, progresso: Progresso | None = None,
              agora: datetime | None = None) -> ResultadoConvenios:
    """Lê as entradas, classifica os lançamentos e grava a cópia preenchida e o relatório.

    pasta_equivalencias: a pasta com o equivalencias.csv; None = o modelo de fábrica (vazio, com aviso).
    """
    if not (razao and planilha and pasta_saida):
        raise ValueError("Escolha o razão, a planilha de receitas e a pasta de saída.")
    agora = agora or datetime.now()
    resultado = ResultadoConvenios()

    def avisar(texto: str, fracao: float | None):
        if progresso:
            progresso(texto, fracao)

    try:
        avisar("Lendo o razão...", 0.1)
        lido = resultado.razao = ler_razao(Path(razao))
        if lido.mes is None:
            raise ErroLeitura(f"{lido.arquivo}: o mês do razão não foi identificado (falta o \"Período\").")
        avisar("Lendo a planilha de receitas...", 0.3)
        receitas = resultado.planilha = ler_planilha(Path(planilha), lido.ano)
        if lido.mes not in receitas.colunas_mes:
            raise ErroLeitura(f"{Path(planilha).name}, aba {receitas.aba}: não tem a coluna do mês "
                              f"{lido.mes:02d}/{lido.ano}.")
        avisar("Lendo as equivalências...", 0.4)
        equivalencias = resultado.equivalencias = ler_equivalencias(Path(pasta_equivalencias)
                                                                    if pasta_equivalencias else None)
    except ErroLeitura as erro:
        resultado.erro = str(erro)
        avisar("Não foi possível processar.", 1.0)
        return resultado

    avisar("Separando os lançamentos por convênio...", 0.5)
    classificacao = resultado.classificacao = classificar(lido, receitas, equivalencias)
    resultado.mes_ja_preenchido = mes_ja_preenchido(receitas, lido.mes)
    if resultado.mes_ja_preenchido and not substituir:
        avisar(f"O mês {lido.mes:02d}/{lido.ano} já está preenchido.", 1.0)
        return resultado

    avisar("Gravando a cópia da planilha...", 0.7)
    nomes = {"ano": lido.ano, "mes": lido.mes, "data_hora": agora.strftime(cfg.FORMATO_DATA_HORA_NOME)}
    copia = _caminho_livre(Path(pasta_saida) / cfg.NOME_COPIA.format(**nomes))
    try:
        resultado.preenchimento = preencher(Path(planilha), receitas, lido, classificacao, copia, substituir)
        resultado.caminho_planilha = copia
    except (OSError, ErroLeitura) as erro:
        resultado.erro_saida = f"Não foi possível gravar a cópia da planilha {copia.name}: {erro}"
        avisar("Não foi possível gravar a cópia.", 1.0)
        return resultado

    avisar("Gravando o relatório...", 0.9)
    relatorio = _caminho_livre(Path(pasta_saida) / cfg.NOME_RELATORIO.format(**nomes))
    arquivos = {"Razão": str(razao), "Planilha de receitas": str(planilha),
                "Equivalências": equivalencias.caminho, "Cópia preenchida": str(copia)}
    try:
        resultado.caminho_relatorio = gerar_relatorio(relatorio, lido, classificacao, resultado.preenchimento,
                                                      arquivos, resultado.avisos, agora)
    except OSError as erro:
        resultado.erro_saida = f"Não foi possível gravar o relatório {relatorio.name}: {erro}"
    avisar("Pronto.", 1.0)
    return resultado


# ---------------------------------------------------------------------------
# Apoio à tela: escolhas lembradas, confirmação de cada cartão, pergunta do P1 e resumo (seção 7)
# ---------------------------------------------------------------------------

CHAVE_PREFERENCIAS = "convenios"            # %APPDATA%\CentralConciliacoes\convenios.json
PREFERENCIAS = ("planilha", "equivalencias", "saida")

Confirmacao = tuple[str, str | None]        # (texto, "ok" | "atencao" | "erro" | None)


def ler_preferencias(pasta: Path | None = None) -> dict[str, str]:
    """O que a tela lembra (a planilha, a pasta das equivalências e a de saída; o razão muda todo mês)."""
    dados = ler_preferencias_modulo(CHAVE_PREFERENCIAS, pasta)
    return {chave: valor for chave, valor in dados.items()
            if chave in PREFERENCIAS and isinstance(valor, str) and valor}


def salvar_preferencias(pasta: Path | None = None, **valores) -> bool:
    dados = ler_preferencias(pasta)
    dados.update({chave: str(valor) for chave, valor in valores.items() if chave in PREFERENCIAS and valor})
    return salvar_preferencias_modulo(CHAVE_PREFERENCIAS, dados, pasta)


def confirmar_razao(caminho: Path) -> tuple[Confirmacao, tuple[int, int] | None]:
    """A confirmação do cartão e o (ano, mês) do razão (None se não deu para ler)."""
    try:
        razao = ler_razao(Path(caminho))
    except ErroLeitura as erro:
        return (str(erro), "erro"), None
    if razao.mes is None:
        return ("Mês do razão não identificado (falta o \"Período\")", "erro"), None
    texto = f"Mês {razao.mes:02d}/{razao.ano} · {len(razao.contas)} conta(s) · R$ {formatar_valor(razao.total)}"
    if razao.avisos:
        status = "erro" if any(a.erro for a in razao.avisos) else "atencao"
        return (f"{texto}; {razao.avisos[0].mensagem}", status), (razao.ano, razao.mes)
    return (texto, "ok"), (razao.ano, razao.mes)


def confirmar_planilha(caminho: Path, competencia: tuple[int, int] | None) -> Confirmacao:
    """competencia = (ano, mês) do razão; sem ele, a aba do ano ainda não pode ser conferida."""
    if competencia is None:
        if not Path(caminho).is_file():
            return f"Arquivo não encontrado: {caminho}", "erro"
        return "Escolha o razão para conferir a aba do ano e o mês", None
    ano, mes = competencia
    try:
        planilha = ler_planilha(Path(caminho), ano)
    except ErroLeitura as erro:
        return str(erro), "erro"
    nome_mes = cfg.NOMES_MESES[mes - 1]
    if mes not in planilha.colunas_mes:
        return f"A aba {planilha.aba} não tem a coluna de {nome_mes}", "erro"
    ja = mes_ja_preenchido(planilha, mes)
    situacao = f"{nome_mes} já preenchido em {len(ja)} linha(s)" if ja else f"{nome_mes} vazio"
    texto = f"Aba {ano} · {len(planilha.convenios)} convênios · {situacao}"
    if planilha.avisos:
        return f"{texto}; {planilha.avisos[0].mensagem}", "atencao"
    return texto, "atencao" if ja else "ok"


def pasta_equivalencias_sugerida(planilha: Path) -> Path | None:
    """3.3: a pasta config ao lado da planilha de receitas (a tela chama em segundo plano)."""
    return pasta_sugerida(Path(planilha))


def confirmar_equivalencias(pasta: Path) -> Confirmacao:
    equivalencias = ler_equivalencias(Path(pasta))
    if equivalencias.de_fabrica:
        return (equivalencias.avisos[0].mensagem if equivalencias.avisos
                else f"Sem {cfg.ARQUIVO_EQUIVALENCIAS} nesta pasta"), "erro"
    texto = f"{len(equivalencias.itens)} equivalência(s) no {cfg.ARQUIVO_EQUIVALENCIAS}"
    if equivalencias.avisos:
        return f"{texto}; {equivalencias.avisos[0].mensagem}", "atencao"
    return texto, "ok"


def conferir_mes(razao: Path, planilha: Path) -> tuple[str, list[str]]:
    """P1, antes de processar: ("09/2026", convênios que já têm valor no mês). Problema de leitura -> ("", []):
    processar() mostra o erro."""
    try:
        lido = ler_razao(Path(razao))
        if lido.mes is None:
            return "", []
        receitas = ler_planilha(Path(planilha), lido.ano)
    except ErroLeitura:
        return "", []
    return f"{lido.mes:02d}/{lido.ano}", mes_ja_preenchido(receitas, lido.mes)


def texto_pergunta_substituir(mes: str, preenchidos: list[str]) -> str:
    return (f"O mês {mes} já está preenchido em {len(preenchidos)} linha(s) da planilha.\n\n"
            "Deseja substituir pelos valores do razão?\n\n"
            "As linhas que não têm lançamento no razão mantêm o valor que já têm (ex.: o que foi digitado à mão). "
            "A planilha escolhida não é alterada: o programa grava uma cópia.")


@dataclass
class ResumoConvenios:
    """O que a aba mostra depois de processar (os textos já prontos)."""

    numeros: list[tuple] = field(default_factory=list)
    convenios: list[tuple] = field(default_factory=list)     # (linha, convênio, valor do mês)
    linhas: list[tuple] = field(default_factory=list)        # (texto, status, valor ou None)
    selo: tuple[str, str] = ("Concluído", "ok")


def resumir(resultado: ResultadoConvenios) -> ResumoConvenios:
    resumo = ResumoConvenios()
    p, c = resultado.preenchimento, resultado.classificacao
    if p is None or c is None:
        resumo.linhas = [(resultado.erro_saida or resultado.erro or "Nada foi gravado.", "erro", None)]
        resumo.selo = ("Com erro", "erro")
        return resumo
    preenchidas = [l for l in p.linhas if l.total is not None and l.total.destinos]
    resumo.numeros = [(len(preenchidas), "convênios preenchidos", "principal"),
                      (len(p.linhas_novas), "linhas novas", "atencao" if p.linhas_novas else "ok"),
                      (len(c.nao_identificados), "lançamentos não identificados",
                       "erro" if c.nao_identificados else "ok")]
    resumo.convenios = [(l.linha, l.nome, formatar_valor(l.novo)) for l in preenchidas]
    linhas = []
    if resultado.erro_saida:
        linhas.append((resultado.erro_saida, "erro", None))
    linhas.append((f"{cfg.PLANILHA_TOTAL} × {cfg.PLANILHA_SALDO_CONTABIL}: diferença",
                   "ok" if p.diferenca == 0 else "erro", f"R$ {formatar_valor(p.diferenca)}"))
    if c.nao_identificados:
        linhas.append((f"Não identificado ({len(c.nao_identificados)} lançamento(s)): preencha à mão",
                       "erro", f"R$ {formatar_valor(c.total_nao_identificado)}"))
    for nova in p.linhas_novas:
        linhas.append((f"Linha nova {nova.linha}: \"{nova.nome}\" (confira o nome)", "atencao",
                       f"R$ {formatar_valor(nova.novo)}"))
    mantidas = [l for l in p.linhas if l.situacao == cfg.SITUACAO_MANTIDA]
    if mantidas:
        linhas.append((f"{len(mantidas)} linha(s) mantida(s) sem lançamento no razão: "
                       + ", ".join(l.nome for l in mantidas), "atencao", None))
    ja_mostrados = ("Convênio novo", "Não identificado", cfg.PLANILHA_DIFERENCA)
    outros = [a for a in resultado.avisos if a.origem not in ja_mostrados]
    if outros:
        linhas.append((f"{len(outros)} outro(s) aviso(s) no relatório (ex.: {outros[0].mensagem})",
                       "erro" if any(a.erro for a in outros) else "atencao", None))
    resumo.linhas = linhas
    if resultado.erro_saida:
        resumo.selo = ("Com erro", "erro")
    elif any(status != "ok" for _, status, _ in linhas):
        resumo.selo = ("Conferir", "atencao")
    return resumo
