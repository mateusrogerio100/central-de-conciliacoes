"""Junta tudo: é o único arquivo do módulo que a tela chama (seção 6 da especificação).

gerar(): pasta das notas do mês + aba Emails do Check list + modelo do e-mail -> e-mails -> prévia e
relatório na pasta de saída.
Nunca levanta exceção por problema em arquivo: o que não pôde ser lido ou gravado vai para o resultado.
Levanta ValueError só se a própria chamada estiver incompleta (a tela valida antes).
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from central.preferencias import ler_preferencias_modulo, salvar_preferencias_modulo
from modulos.notas_pendentes import configuracao as cfg
from modulos.notas_pendentes.emails import (
    competencia, montar_emails, previa_html, tamanho_legivel, texto_para_claude_desktop,
)
from modulos.notas_pendentes.leitor_contatos import ler_contatos
from modulos.notas_pendentes.leitor_modelo import ler_modelo, sugerir_modelo
from modulos.notas_pendentes.leitor_pasta import ler_pasta
from modulos.notas_pendentes.modelos import EmailsDoMes, ErroLeitura, PastaNotas
from modulos.notas_pendentes.relatorio import gerar_relatorio

Progresso = Callable[[str, float | None], None]


def interpretar_competencia(texto: str) -> tuple[int, int] | None:
    """"10/2026" -> (2026, 10); inválido -> None."""
    achado = cfg.RE_MES_DIGITADO.match(texto or "")
    if not achado:
        return None
    mes, ano = int(achado.group(1)), int(achado.group(2))
    return (ano, mes) if 1 <= mes <= 12 and 2000 <= ano <= 2100 else None


def interpretar_prazo(texto: str) -> date | None:
    """"29/10/2026" -> date; data que não existe (31/11/2026) ou fora do formato -> None."""
    try:
        return datetime.strptime((texto or "").strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def _caminho_livre(caminho: Path) -> Path:
    """O próprio caminho, ou com _2, _3... se já existir."""
    numero, original = 2, caminho
    while caminho.exists():
        caminho = original.with_name(f"{original.stem}_{numero}{original.suffix}")
        numero += 1
    return caminho


@dataclass
class ResultadoGeracao:
    """O que a tela mostra depois de gerar os e-mails do mês."""

    ano: int
    mes: int
    prazo: date
    pasta: PastaNotas | None = None
    emails: EmailsDoMes = field(default_factory=EmailsDoMes)
    origem_modelo: str = ""
    caminho_previa: Path | None = None
    caminho_relatorio: Path | None = None
    caminho_texto: Path | None = None      # os e-mails em texto, para o Claude Desktop criar os rascunhos (E7)
    erro: str = ""             # não deu para gerar (pasta, Check list ou modelo)
    erro_saida: str = ""       # não deu para gravar a prévia, o texto ou o relatório


def gerar(pasta_notas: Path, checklist: Path, pasta_saida: Path, ano: int, mes: int, prazo: date,
          modelo: Path | None = None, progresso: Progresso | None = None,
          agora: datetime | None = None) -> ResultadoGeracao:
    """Lê as entradas, monta os e-mails (E1 a E5) e grava a prévia (E6), o texto para o Claude Desktop (E7)
    e o relatório (seção 5).

    modelo: o modelo_email.txt; None = o de fábrica (com aviso).
    """
    if not (pasta_notas and checklist and pasta_saida and ano and mes and prazo):
        raise ValueError("Escolha a pasta das notas, o Check list, a pasta de saída, a competência e o prazo.")
    if Path(pasta_saida).resolve() == Path(pasta_notas).resolve():
        raise ValueError("A pasta de saída não pode ser a pasta das notas: ela nunca recebe nada.")
    agora = agora or datetime.now()
    resultado = ResultadoGeracao(ano, mes, prazo)

    def avisar(texto: str, fracao: float | None):
        if progresso:
            progresso(texto, fracao)

    try:
        avisar("Lendo a pasta das notas...", 0.1)
        pasta = resultado.pasta = ler_pasta(Path(pasta_notas))
        avisar("Lendo os contatos do Check list...", 0.3)
        contatos = ler_contatos(Path(checklist))
        avisar("Lendo o modelo do e-mail...", 0.5)
        lido = ler_modelo(Path(modelo) if modelo else None)
    except ErroLeitura as erro:
        resultado.erro = str(erro)
        avisar("Não foi possível gerar os e-mails.", 1.0)
        return resultado

    avisar("Montando os e-mails...", 0.6)
    emails = resultado.emails = montar_emails(pasta, contatos.contatos, lido, ano, mes, prazo)
    emails.avisos = pasta.avisos + contatos.avisos + lido.avisos
    resultado.origem_modelo = lido.origem

    avisar("Gravando a prévia, o texto e o relatório...", 0.8)
    data_hora = agora.strftime(cfg.FORMATO_DATA_HORA_NOME)
    nomes = {"ano": ano, "mes": mes, "data_hora": data_hora}
    saidas = (("caminho_previa", cfg.NOME_PREVIA, "a prévia", lambda: previa_html(emails, ano, mes, prazo, lido.origem),
               "utf-8"),
              ("caminho_texto", cfg.NOME_TEXTO_CLAUDE, "o texto para o Claude Desktop",
               lambda: texto_para_claude_desktop(emails, ano, mes, prazo), "utf-8-sig"))
    for atributo, modelo_nome, descricao, montar, codificacao in saidas:
        caminho = _caminho_livre(Path(pasta_saida) / modelo_nome.format(**nomes))
        try:
            caminho.write_text(montar(), encoding=codificacao)
            setattr(resultado, atributo, caminho)
        except OSError as erro:
            resultado.erro_saida += f"Não foi possível gravar {descricao} {caminho.name}: {erro} "
    relatorio = _caminho_livre(Path(pasta_saida) / cfg.NOME_RELATORIO.format(**nomes))
    arquivos = {"Pasta das notas": str(pasta_notas), "Check list": str(checklist), "Modelo do e-mail": lido.origem}
    try:
        resultado.caminho_relatorio = gerar_relatorio(relatorio, pasta, emails, ano, mes, prazo, arquivos, agora)
    except OSError as erro:
        resultado.erro_saida += f"Não foi possível gravar o relatório {relatorio.name}: {erro} "
    resultado.erro_saida = resultado.erro_saida.strip()
    avisar("E-mails gerados.", 1.0)
    return resultado


# ---------------------------------------------------------------------------
# Apoio à tela: escolhas lembradas, confirmação de cada cartão, sugestões e resumo (seção 7)
# ---------------------------------------------------------------------------

CHAVE_PREFERENCIAS = "notas_pendentes"     # %APPDATA%\CentralConciliacoes\notas_pendentes.json
PREFERENCIAS = ("pasta_notas", "checklist", "modelo", "saida", "competencia", "prazo")

Confirmacao = tuple[str, str]              # (texto, "ok" | "atencao" | "erro")


def ler_preferencias(pasta: Path | None = None) -> dict[str, str]:
    """O que a tela lembra (caminhos, competência, último prazo). Nada aqui toca na rede: só o .json local."""
    dados = ler_preferencias_modulo(CHAVE_PREFERENCIAS, pasta)
    return {chave: valor for chave, valor in dados.items()
            if chave in PREFERENCIAS and isinstance(valor, str) and valor}


def salvar_preferencias(pasta: Path | None = None, **valores) -> bool:
    """Guarda os valores informados (os outros continuam como estavam)."""
    dados = ler_preferencias(pasta)
    dados.update({chave: str(valor) for chave, valor in valores.items() if chave in PREFERENCIAS and valor})
    return salvar_preferencias_modulo(CHAVE_PREFERENCIAS, dados, pasta)


def texto_competencia(ano: int, mes: int) -> str:
    return competencia(ano, mes)


def prazo_sugerido(ultimo_prazo: str, ano: int, mes: int) -> str:
    """3.4: o mesmo dia do último prazo usado, no mês da competência (29/10 -> 29/11); "" sem prazo anterior.
    Dia que não existe no mês (31 em novembro) vira o último dia do mês."""
    anterior = interpretar_prazo(ultimo_prazo)
    if anterior is None:
        return ""
    dia = min(anterior.day, calendar.monthrange(ano, mes)[1])
    return f"{date(ano, mes, dia):%d/%m/%Y}"


def pasta_do_mes(pasta_atual: Path, ano: int, mes: int) -> Path | None:
    """3.1: a pasta <MMAAAA> da competência ao lado da pasta escolhida ("102026" -> "112026"); None se não houver.
    Toca na pasta (pode ser a rede): a tela chama em segundo plano."""
    pasta_atual = Path(pasta_atual)
    if not cfg.RE_NOME_PASTA_MES.match(pasta_atual.name):
        return None
    candidata = pasta_atual.parent / cfg.NOME_PASTA_MES.format(ano=ano, mes=mes)
    return candidata if candidata != pasta_atual and candidata.is_dir() else None


def modelo_sugerido(pasta_notas: Path) -> Path | None:
    """3.3: o modelo_email.txt da pasta config ao lado das pastas dos meses (a tela chama em segundo plano)."""
    return sugerir_modelo(Path(pasta_notas))


def confirmar_pasta_notas(caminho: Path) -> Confirmacao:
    try:
        pasta = ler_pasta(Path(caminho))
    except ErroLeitura as erro:
        return str(erro), "erro"
    grupos = pasta.por_numero()
    if not pasta.notas:
        return "Nenhum PDF nesta pasta", "atencao"
    texto = f"{len(pasta.notas)} PDF(s) de {len(grupos)} responsável(is)"
    if pasta.sem_numero:
        return f"{texto}; {len(pasta.sem_numero)} sem número no nome", "atencao"
    if pasta.avisos:
        return f"{texto}; {len(pasta.avisos)} aviso(s): {pasta.avisos[0].mensagem}", "atencao"
    return texto, "ok"


def confirmar_checklist(caminho: Path) -> Confirmacao:
    try:
        lidos = ler_contatos(Path(caminho))
    except ErroLeitura as erro:
        return str(erro), "erro"
    texto = f"{len(lidos.contatos)} contato(s) na aba {cfg.ABA_EMAILS}"
    if lidos.avisos:
        return f"{texto}; {len(lidos.avisos)} aviso(s): {lidos.avisos[0].mensagem}", "atencao"
    return texto, "ok"


def confirmar_modelo(caminho: Path) -> Confirmacao:
    try:
        modelo = ler_modelo(Path(caminho))
    except ErroLeitura as erro:
        return str(erro), "erro"
    if modelo.avisos:
        return modelo.avisos[0].mensagem, "atencao"
    return f"Assunto: {modelo.assunto}", "ok"


@dataclass
class ResumoGeracao:
    """O que a aba mostra depois de gerar (os textos já prontos)."""

    numeros: list[tuple] = field(default_factory=list)
    emails: list[tuple] = field(default_factory=list)       # (número, notas, destinatários, tamanho)
    linhas: list[tuple] = field(default_factory=list)       # (texto, status)
    selo: tuple[str, str] = ("Concluído", "ok")


def resumir(resultado: ResultadoGeracao) -> ResumoGeracao:
    emails = resultado.emails
    resumo = ResumoGeracao()
    anexadas = sum(len(e.anexos) for e in emails.emails)
    sem = sum(len(s.notas) for s in emails.sem_email)
    resumo.numeros = [(anexadas, "Notas anexadas", "principal"), (len(emails.emails), "E-mails", "ok"),
                      (sem, "Sem e-mail", "erro" if sem else "ok")]
    resumo.emails = [(e.numero, len(e.anexos), len(e.para), tamanho_legivel(e.tamanho)) for e in emails.emails]
    linhas = [(f"Sem e-mail ({f'número {s.numero}' if s.numero else 'sem número'}): {len(s.notas)} nota(s). "
               f"{s.motivo}", "erro") for s in emails.sem_email]
    if emails.avisos:
        linhas.append((f"{len(emails.avisos)} aviso(s) no fim da prévia (ex.: {emails.avisos[0].mensagem})",
                       "atencao"))
    erros = [(resultado.erro_saida, "erro")] if resultado.erro_saida else []
    resumo.linhas = erros + linhas or [("Todas as notas têm e-mail", "ok")]
    if erros:
        resumo.selo = ("Com erro", "erro")
    elif linhas:
        resumo.selo = ("Conferir", "atencao")
    return resumo
