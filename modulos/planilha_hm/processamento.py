"""Junta tudo: é o único arquivo do módulo que a tela chama (seção 6 da especificação).

Em duas passadas (a tela pergunta no meio, R5 item 4):
1. analisar(): lê o Eventos, o Movimento e a Planilha HM e monta o plano (eventos novos e a seção de cada um;
   perguntas para o que a tabela conta → seção não resolve). Não grava nada.
2. processar(): com as respostas, grava na pasta de saída a cópia preenchida e o relatório de conferência, e a
   tabela conta → seção na pasta config.

Nunca levanta exceção por problema em arquivo: o que não pôde ser lido ou gravado vai para o resultado.
Aba Senior do mês já preenchida, ou cópia que já existe na pasta de saída: nada é gravado e o resultado diz
por quê (a tela pergunta e chama de novo com substituir_senior / substituir_copia).

No fim, o apoio à tela (seção 7): a confirmação de cada cartão, os textos das perguntas, a pasta lembrada e o
resumo do resultado, já prontos para mostrar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from central.preferencias import ler_preferencias_modulo, salvar_preferencias_modulo
from modulos.planilha_hm import configuracao as cfg
from modulos.planilha_hm.conferencia import conferir
from modulos.planilha_hm.leitor_eventos import ler_eventos
from modulos.planilha_hm.leitor_movimento import ler_movimento
from modulos.planilha_hm.leitor_planilha import ler_planilha
from modulos.planilha_hm.modelos import (
    Aviso,
    Conferencia,
    ErroLeitura,
    Eventos,
    Movimento,
    Pergunta,
    Planilha,
    Plano,
    Preenchimento,
)
from modulos.planilha_hm.normalizacao import formatar_valor
from modulos.planilha_hm.preenchimento import mes_ja_preenchido, nome_senior, planejar, preencher
from modulos.planilha_hm.relatorio import gerar_relatorio
from modulos.planilha_hm.secoes_contas import pasta_config as pasta_config_padrao

Progresso = Callable[[str, float | None], None]


def _caminho_livre(caminho: Path) -> Path:
    """O próprio caminho, ou com _2, _3... se já existir (o relatório anterior nunca é apagado)."""
    numero, original = 2, caminho
    while caminho.exists():
        caminho = original.with_name(f"{original.stem}_{numero}{original.suffix}")
        numero += 1
    return caminho


@dataclass
class Analise:
    """1ª passada: as entradas lidas e o plano (com as perguntas para a tela)."""

    arquivo_eventos: Path
    arquivo_movimento: Path
    arquivo_planilha: Path
    eventos: Eventos | None = None
    movimento: Movimento | None = None
    planilha: Planilha | None = None
    plano: Plano | None = None
    linhas_senior_preenchidas: int = 0      # a aba Senior do mês já tem dados: perguntar antes de substituir
    tabela_montada: bool = False            # a tabela conta → seção não existia: foi montada agora (R5a, item 1)
    erro: str = ""

    @property
    def avisos(self) -> list[Aviso]:
        avisos = []
        for parte in (self.eventos, self.movimento, self.planilha, self.plano):
            if parte is not None:
                avisos += parte.avisos
        return avisos


@dataclass
class ResultadoPlanilhaHM:
    """O que a tela mostra depois de processar."""

    analise: Analise
    preenchimento: Preenchimento | None = None
    final: Planilha | None = None           # a cópia gravada, lida de novo para a conferência
    conferencia: Conferencia | None = None
    caminho_planilha: Path | None = None
    caminho_relatorio: Path | None = None
    copia_existente: Path | None = None     # a cópia já existe: perguntar antes de substituir
    senior_preenchida: int = 0              # a aba Senior do mês já tem dados: perguntar antes de substituir
    erro: str = ""                          # não deu para processar
    erro_saida: str = ""                    # não deu para gravar o relatório

    @property
    def avisos(self) -> list[Aviso]:
        avisos = list(self.analise.avisos)
        for parte in (self.preenchimento, self.conferencia):
            if parte is not None:
                avisos += parte.avisos
        return avisos


def analisar(eventos: Path, movimento: Path, planilha: Path, pasta_config: Path | None = None,
             progresso: Progresso | None = None) -> Analise:
    """1ª passada. pasta_config: onde fica o secoes_contas.csv (padrão: a pasta config ao lado da planilha)."""
    if not (eventos and movimento and planilha):
        raise ValueError("Escolha o Eventos, o Movimento e a Planilha HM.")
    analise = Analise(Path(eventos), Path(movimento), Path(planilha))

    def avisar(texto: str, fracao: float | None):
        if progresso:
            progresso(texto, fracao)

    try:
        avisar("Lendo o Eventos...", 0.05)
        analise.eventos = ler_eventos(analise.arquivo_eventos)
        avisar("Lendo o Movimento...", 0.15)
        analise.movimento = ler_movimento(analise.arquivo_movimento)
        avisar("Lendo a Planilha HM...", 0.25)
        analise.planilha = ler_planilha(analise.arquivo_planilha)
        avisar("Procurando eventos novos...", 0.35)
        analise.plano = planejar(analise.eventos, analise.movimento, analise.planilha,
                                 Path(pasta_config) if pasta_config else pasta_config_padrao(analise.arquivo_planilha))
        analise.linhas_senior_preenchidas = mes_ja_preenchido(analise.planilha, analise.eventos.mes)
        analise.tabela_montada = not analise.plano.tabela.existia
    except (ErroLeitura, ValueError) as erro:
        analise.erro = str(erro)
    return analise


def nome_da_copia(analise: Analise, agora: datetime) -> str:
    return cfg.NOME_COPIA.format(mes=analise.eventos.mes, ano=analise.planilha.ano,
                                 data=agora.strftime(cfg.FORMATO_DATA_NOME))


def processar(analise: Analise, pasta_saida: Path, respostas: dict[str, str] | None = None,
              substituir_senior: bool = False, substituir_copia: bool = False,
              progresso: Progresso | None = None, agora: datetime | None = None) -> ResultadoPlanilhaHM:
    """2ª passada: grava a cópia, a tabela conta → seção e o relatório. respostas: {chave da pergunta: seção}."""
    if analise.erro or analise.plano is None:
        raise ValueError("A análise das entradas não terminou bem: corrija e analise de novo.")
    if not pasta_saida:
        raise ValueError("Escolha a pasta de saída.")
    agora = agora or datetime.now()
    resultado = ResultadoPlanilhaHM(analise)

    def avisar(texto: str, fracao: float | None):
        if progresso:
            progresso(texto, fracao)

    if analise.linhas_senior_preenchidas and not substituir_senior:
        resultado.senior_preenchida = analise.linhas_senior_preenchidas
        return resultado
    copia = Path(pasta_saida) / nome_da_copia(analise, agora)
    if copia.exists() and not substituir_copia:
        resultado.copia_existente = copia
        return resultado

    avisar("Gravando a cópia da Planilha HM...", 0.5)
    try:
        resultado.preenchimento = preencher(analise.arquivo_planilha, analise.planilha, analise.eventos,
                                            analise.movimento, analise.plano, respostas or {}, copia,
                                            substituir=substituir_senior)
        resultado.caminho_planilha = copia
        avisar("Conferindo o TOTAL GERAL com o Movimento...", 0.8)
        resultado.final = ler_planilha(copia)
        resultado.conferencia = conferir(analise.eventos, analise.movimento, resultado.final)
    except (OSError, ErroLeitura, ValueError) as erro:
        resultado.erro = f"Não foi possível gravar a cópia {copia.name}: {erro}"
        avisar("Não foi possível gravar a cópia.", 1.0)
        return resultado

    avisar("Gravando o relatório...", 0.9)
    nomes = {"ano": analise.planilha.ano, "mes": analise.eventos.mes,
             "data_hora": agora.strftime(cfg.FORMATO_DATA_HORA_NOME)}
    relatorio = _caminho_livre(Path(pasta_saida) / cfg.NOME_RELATORIO.format(**nomes))
    arquivos = {"Eventos": str(analise.arquivo_eventos), "Movimento": str(analise.arquivo_movimento),
                "Planilha HM do mês anterior": str(analise.arquivo_planilha),
                "Tabela conta → seção": analise.plano.caminho_tabela, "Cópia preenchida": str(copia)}
    try:
        resultado.caminho_relatorio = gerar_relatorio(relatorio, analise.eventos, analise.movimento, analise.plano,
                                                      resultado.preenchimento, resultado.final,
                                                      resultado.conferencia, arquivos, resultado.avisos, agora)
    except OSError as erro:
        resultado.erro_saida = f"Não foi possível gravar o relatório {relatorio.name}: {erro}"
    avisar("Pronto.", 1.0)
    return resultado


# ---------------------------------------------------------------------------
# Apoio à tela (seção 7)
# ---------------------------------------------------------------------------

RESPOSTA_SECAO_NOVA = cfg.RESPOSTA_SECAO_NOVA
Confirmacao = tuple[str, str | None]        # (texto, "ok" | "atencao" | "erro" | None)
Competencia = tuple[int, int]               # (ano, mês)


def competencia(mes: int, ano: int) -> str:
    """(9, 2026) -> "set/2026"."""
    return f"{cfg.MESES_ABREVIADOS[mes - 1]}/{ano}"


def ler_preferencias(pasta: Path | None = None) -> dict[str, str]:
    """O que a tela lembra: só a pasta de saída (o Eventos, o Movimento e a Planilha HM mudam todo mês)."""
    dados = ler_preferencias_modulo(cfg.CHAVE_PREFERENCIAS, pasta)
    return {chave: valor for chave, valor in dados.items()
            if chave in cfg.PREFERENCIAS and isinstance(valor, str) and valor}


def salvar_preferencias(pasta: Path | None = None, **valores) -> bool:
    dados = ler_preferencias(pasta)
    dados.update({chave: str(valor) for chave, valor in valores.items() if chave in cfg.PREFERENCIAS and valor})
    return salvar_preferencias_modulo(cfg.CHAVE_PREFERENCIAS, dados, pasta)


def _com_aviso(texto: str, avisos: list[Aviso]) -> Confirmacao:
    """O 1º aviso da leitura vai junto da confirmação, como atenção: o que ele diz não impede de processar (o que
    impede é ErroLeitura) e vai inteiro para o relatório."""
    if not avisos:
        return texto, "ok"
    return f"{texto}; {avisos[0].mensagem}", "atencao"


def confirmar_eventos(caminho: Path) -> tuple[Confirmacao, Competencia | None]:
    """A confirmação do cartão e o (ano, mês) do Eventos (None se não deu para ler). Evento com erro (R2) não
    impede: fica fora da planilha e vai para o relatório."""
    try:
        eventos = ler_eventos(Path(caminho))
    except ErroLeitura as erro:
        return (str(erro), "erro"), None
    if eventos.mes is None or eventos.ano is None:
        return ("A competência do Eventos não foi identificada (falta a linha \"Competência\")", "erro"), None
    texto = (f"Eventos · {competencia(eventos.mes, eventos.ano)} · {len(eventos.eventos)} eventos · "
             f"R$ {formatar_valor(eventos.total)}")
    com_erro = [e for e in eventos.eventos if not e.ok]
    if com_erro:
        texto = f"{texto}; {len(com_erro)} evento(s) com erro ficam fora da planilha (ex.: {com_erro[0].numero})"
        return (texto, "atencao"), (eventos.ano, eventos.mes)
    return _com_aviso(texto, eventos.avisos), (eventos.ano, eventos.mes)


def confirmar_movimento(caminho: Path) -> tuple[Confirmacao, Competencia | None]:
    try:
        movimento = ler_movimento(Path(caminho))
    except ErroLeitura as erro:
        return (str(erro), "erro"), None
    if movimento.mes is None or movimento.ano is None:
        return ("O mês do Movimento não foi identificado (coluna \"Data movimento\")", "erro"), None
    texto = (f"Movimento · {competencia(movimento.mes, movimento.ano)} · lote {movimento.lote} · "
             f"R$ {formatar_valor(movimento.total)}")
    return _com_aviso(texto, movimento.avisos), (movimento.ano, movimento.mes)


def texto_meses_diferentes(eventos: Competencia | None, movimento: Competencia | None) -> str:
    """Seção 3: Eventos e Movimento de meses diferentes não acendem o botão. "" = mesmo mês (ou falta um)."""
    if eventos is None or movimento is None or eventos == movimento:
        return ""
    return (f"o Movimento é de {competencia(movimento[1], movimento[0])} e o Eventos, de "
            f"{competencia(eventos[1], eventos[0])}")


def confirmar_planilha(caminho: Path, competencia_eventos: Competencia | None) -> Confirmacao:
    """A aba do ano e a última competência preenchida; com o mês do Eventos, confere também o ano e a aba Senior
    do mês (já preenchida: a tela pergunta antes de substituir)."""
    try:
        planilha = ler_planilha(Path(caminho))
    except ErroLeitura as erro:
        return str(erro), "erro"
    ultima = planilha.ultima_competencia
    texto = (f"Planilha HM · aba {planilha.aba_ano} · "
             + (f"última competência preenchida: {competencia(ultima, planilha.ano)}" if ultima
                else "nenhuma competência preenchida"))
    if competencia_eventos is not None:
        ano, mes = competencia_eventos
        senior = nome_senior(mes, planilha.ano)
        if ano != planilha.ano:
            return f"{texto}; a planilha é de {planilha.ano} e o Eventos, de {ano}", "erro"
        if mes not in planilha.seniors:
            return f"{texto}; falta a aba \"{senior}\"", "erro"
        if mes not in planilha.colunas_meses:
            return f"{texto}; a aba {planilha.aba_ano} não tem a coluna de {cfg.NOMES_MESES[mes - 1]}", "erro"
        ja = mes_ja_preenchido(planilha, mes)
        if ja:
            return f"{texto}; a aba {senior} já tem {ja} linha(s): será perguntado antes de substituir", "atencao"
    return _com_aviso(texto, planilha.avisos)


def texto_pergunta_senior(analise: Analise) -> str:
    senior = nome_senior(analise.eventos.mes, analise.planilha.ano)
    return (f"A aba \"{senior}\" da planilha escolhida já tem {analise.linhas_senior_preenchidas} linha(s) "
            "preenchida(s).\n\nDeseja substituir pelos dados do Eventos?\n\n"
            "A planilha escolhida não é alterada: o programa grava uma cópia.")


@dataclass
class TextosPergunta:
    """O que a janela da pergunta da R5 (item 4) mostra, já pronto."""

    motivo: str
    eventos: list[str]                      # "3172 · HM Catarata Aglutinada · R$ 1.234,00"
    contas: list[str]                       # "3.01.01.06.03.0010 · HM Catarata Aglutinada PJ"
    opcoes: list[tuple[str, str]]           # (resposta para processar(), texto do botão)


def textos_da_pergunta(analise: Analise, pergunta: Pergunta) -> TextosPergunta:
    por_numero = {e.numero: e for e in analise.eventos.eventos}
    eventos = []
    for numero in pergunta.eventos:
        evento = por_numero.get(numero)
        if evento is None:
            eventos.append(str(numero))
        else:
            valor = f" · R$ {formatar_valor(evento.total)}" if evento.total is not None else ""
            eventos.append(f"{numero} · {evento.nome}{valor}")
    opcoes = [(secao, secao) for secao in pergunta.opcoes]
    if pergunta.permite_nova:
        opcoes.append((RESPOSTA_SECAO_NOVA, cfg.TEXTO_OPCAO_SECAO_NOVA.format(nome=pergunta.nome_secao_nova)))
    return TextosPergunta(pergunta.motivo, eventos, [f"{c.classificacao} · {c.nome}" for c in pergunta.contas],
                          opcoes)


@dataclass
class ResumoPlanilhaHM:
    """O que a tela mostra depois de processar (os textos já prontos)."""

    numeros: list[tuple] = field(default_factory=list)
    linhas: list[tuple] = field(default_factory=list)        # (texto, status, valor ou None)
    criadas: list[tuple] = field(default_factory=list)       # (linha, o quê, evento, nome, seção)
    selo: tuple[str, str] = ("Concluído", "ok")


def resumir(resultado: ResultadoPlanilhaHM) -> ResumoPlanilhaHM:
    resumo = ResumoPlanilhaHM()
    p, conferencia = resultado.preenchimento, resultado.conferencia
    if p is None or conferencia is None:
        resumo.linhas = [(resultado.erro or resultado.erro_saida or "Nada foi gravado.", "erro", None)]
        resumo.selo = ("Com erro", "erro")
        return resumo
    analise = resultado.analise
    fora = {e.numero: e for e in analise.eventos.eventos if not e.ok}
    fora.update({e.numero: e for e in conferencia.eventos_fora if e.numero not in fora})
    resumo.numeros = [(len(analise.eventos.eventos), "eventos no mês", "principal"),
                      (len(p.criadas), "linhas criadas na aba do ano", "atencao" if p.criadas else "ok"),
                      (len(fora), "eventos fora da planilha", "erro" if fora else "ok")]
    status_total = "ok" if conferencia.ok else "erro"
    linhas = []
    if resultado.erro_saida:
        linhas.append((resultado.erro_saida, "erro", None))
    linhas += [
        ("TOTAL GERAL × Movimento: diferença", status_total, f"R$ {formatar_valor(conferencia.diferenca)}"),
        ("TOTAL GERAL do mês na cópia", status_total, f"R$ {formatar_valor(conferencia.total_geral)}"),
        (f"Movimento (lote {analise.movimento.lote})", status_total,
         f"R$ {formatar_valor(conferencia.total_movimento)}"),
        ("LOTE REPASSE gravado (a linha de baixo dá zero)", "ok", f"R$ {formatar_valor(p.lote)}"),
        (f"Aba {nome_senior(p.mes, p.ano)}: {p.linhas_senior} linha(s)", "ok", None),
    ]
    for evento in fora.values():
        valor = f"R$ {formatar_valor(evento.total)}" if evento.total is not None else None
        linhas.append((f"Evento {evento.numero} {evento.nome}: {evento.erro or cfg.SITUACAO_FORA}", "erro", valor))
    if analise.tabela_montada:
        linhas.append((f"Tabela conta → seção criada agora: {analise.plano.caminho_tabela}", "atencao", None))
    if resultado.avisos:
        linhas.append((f"{len(resultado.avisos)} aviso(s) na aba Avisos da conferência "
                       f"(ex.: {resultado.avisos[0].mensagem})",
                       "erro" if any(a.erro for a in resultado.avisos) else "atencao", None))
    resumo.linhas = linhas
    resumo.criadas = [(c.linha, c.tipo, c.evento or "",
                       c.nome_cc if c.tipo == "CC novo" else (c.nome_evento or c.secao), c.secao)
                      for c in sorted(p.criadas, key=lambda c: c.linha)]
    if resultado.erro_saida or not conferencia.ok:
        resumo.selo = ("Com erro" if conferencia.ok else "Com diferença", "erro")
    elif any(status != "ok" for _, status, _ in linhas):
        resumo.selo = ("Conferir", "atencao")
    return resumo
