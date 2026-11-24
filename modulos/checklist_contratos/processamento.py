"""Junta tudo: é o único arquivo do módulo que a tela chama (seção 6 da especificação).

conferir(): movimentos (arquivo ou pasta, SC e CMD) -> Check list -> configuração -> conferência ->
cópia do Check list preenchida -> relatório.
gerar_pendencias(): Check list da rede (+ relatório do mês) -> pendências -> e-mails -> prévia.
criar_rascunhos(): e-mails -> rascunhos no Gmail (só rascunho) -> registro.
Nunca levantam exceção por problema em arquivo: o que não
pôde ser lido ou gravado vai para o resultado (e para os avisos do relatório). Levanta ValueError só
se a própria chamada estiver incompleta (a tela valida antes).
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from central.preferencias import ler_preferencias_modulo, salvar_preferencias_modulo
from modulos.checklist_contratos import configuracao as cfg
from modulos.checklist_contratos.conferencia import conferir as conferir_regras
from modulos.checklist_contratos.emails import montar_emails, previa_html, texto_para_claude_desktop
from modulos.checklist_contratos.gmail import ClienteGmail, ErroGmail, esquecer_autorizacao  # noqa: F401 (tela)
from modulos.checklist_contratos.leitor_checklist import ler_checklist
from modulos.checklist_contratos.leitor_configuracao import ler_configuracao
from modulos.checklist_contratos.leitor_movimento import arquivos_do_movimento, ler_movimentos
from modulos.checklist_contratos.modelos import (
    Aviso, Checklist, Conferencia, Email, ErroLeitura, Movimento, Pendencias, Situacao,
)
from modulos.checklist_contratos.pendencias import (
    avisos_dos_codigos, gerar_listas, linhas_divergentes, notas_conta_divergente,
)
from modulos.checklist_contratos.preenchimento import gravar_copia, valores_para_gravar
from modulos.checklist_contratos.relatorio import gerar_relatorio

Progresso = Callable[[str, float | None], None]


@dataclass
class ResultadoMes:
    """O que a tela mostra depois de conferir o mês."""

    ano: int
    mes: int
    conferencia: Conferencia | None = None
    checklist: Checklist | None = None
    movimentos: dict[str, Movimento] = field(default_factory=dict)
    caminho_relatorio: Path | None = None
    caminho_copia: Path | None = None
    erro: str = ""                         # não deu para conferir (Check list, configuração...)
    erro_relatorio: str = ""
    erro_copia: str = ""
    avisos: list[Aviso] = field(default_factory=list)   # da gravação (somam-se aos do relatório)

    def quantidade(self, situacao: Situacao) -> int:
        return self.conferencia.contagem()[situacao] if self.conferencia else 0

    @property
    def preenchidas(self) -> int:
        return sum(1 for r in self.conferencia.resultados if r.gravar) if self.conferencia else 0


def nome_copia(ano: int, mes: int) -> str:
    return cfg.NOME_COPIA_CHECKLIST.format(ano=ano, mes=mes)


def _caminho_livre(caminho: Path, proibidos: set[Path] = frozenset()) -> Path:
    """O próprio caminho, ou com _2, _3... se já existir ou for um arquivo de entrada."""
    numero, original = 2, caminho
    while caminho.exists() or caminho.resolve() in proibidos:
        caminho = original.with_name(f"{original.stem}_{numero}{original.suffix}")
        numero += 1
    return caminho


def arquivos_que_seriam_substituidos(pasta_saida: Path, ano: int, mes: int) -> list[Path]:
    """Para a tela perguntar antes de substituir (regra 4.3.4): a cópia do Check list do mês."""
    copia = Path(pasta_saida) / nome_copia(ano, mes)
    return [copia] if copia.exists() else []


def conferir(movimento_sc: Path, movimento_cmd: Path, checklist: Path, pasta_configuracao: Path,
             pasta_saida: Path, ano: int, mes: int, progresso: Progresso | None = None,
             substituir: bool = False, agora: datetime | None = None) -> ResultadoMes:
    """Confere o mês e grava a cópia do Check list e o relatório na pasta de saída.

    substituir=True: a tela já perguntou e o usuário aceitou substituir a cópia do mês; senão uma cópia
    que já existe fica e a nova ganha _2, _3...
    """
    if not (movimento_sc and movimento_cmd and checklist and pasta_configuracao and pasta_saida and ano and mes):
        raise ValueError("Escolha os movimentos da Hospital Exemplo e do CMD, o Check list, a pasta de configuração, "
                         "a pasta de saída e o mês.")
    agora = agora or datetime.now()
    resultado = ResultadoMes(ano, mes)

    def avisar(texto: str, fracao: float | None):
        if progresso:
            progresso(texto, fracao)

    entradas = {"SC": Path(movimento_sc), "CMD": Path(movimento_cmd)}
    try:
        for passo, (estabelecimento, caminho) in enumerate(entradas.items()):
            avisar(f"Lendo o movimento {cfg.NOMES_ESTABELECIMENTOS[estabelecimento]}...", 0.1 + 0.25 * passo)
            resultado.movimentos[estabelecimento] = ler_movimentos(caminho, estabelecimento)
        avisar("Lendo o Check list...", 0.6)
        resultado.checklist = ler_checklist(Path(checklist), ano, mes)
        avisar("Lendo a configuração...", 0.7)
        configuracao = ler_configuracao(Path(pasta_configuracao))
    except ErroLeitura as erro:
        resultado.erro = str(erro)
        avisar("Não foi possível conferir.", 1.0)
        return resultado

    avisar("Conferindo as linhas do Check list...", 0.75)
    resultado.conferencia = conferir_regras(resultado.movimentos, resultado.checklist, configuracao)
    resultado.conferencia.avisos[:0] = configuracao.avisos

    pasta_saida = Path(pasta_saida)
    entradas_resolvidas = {p.resolve() for p in (*entradas.values(), Path(checklist))}
    avisar("Gravando a cópia do Check list...", 0.85)
    destino = pasta_saida / nome_copia(ano, mes)
    if not substituir or destino.resolve() in entradas_resolvidas:
        destino = _caminho_livre(destino, entradas_resolvidas)
    try:
        valores = valores_para_gravar(resultado.conferencia.resultados, resultado.checklist)
        resultado.avisos += gravar_copia(Path(checklist), destino, valores)
        resultado.caminho_copia = destino
    except OSError as erro:
        resultado.erro_copia = (f"Não foi possível gravar {destino.name}. Ele provavelmente está aberto no "
                                f"Excel: feche e tente de novo. ({erro})")
        resultado.avisos.append(Aviso(destino.name, resultado.erro_copia))

    avisar("Gravando o relatório...", 0.95)
    nome = cfg.NOME_RELATORIO.format(ano=ano, mes=mes, data_hora=agora.strftime(cfg.FORMATO_DATA_HORA_NOME))
    caminho = _caminho_livre(pasta_saida / nome)
    arquivos = {"movimento Hospital Exemplo": str(entradas["SC"]), "movimento CMD": str(entradas["CMD"]),
                "Check list": str(checklist), "configuração": str(pasta_configuracao),
                "cópia preenchida": str(resultado.caminho_copia or "(não gravada)")}
    try:
        resultado.caminho_relatorio = gerar_relatorio(caminho, resultado.conferencia, resultado.checklist,
                                                      resultado.movimentos, arquivos, resultado.avisos, agora)
    except OSError as erro:
        resultado.erro_relatorio = f"Não foi possível gravar o relatório {caminho.name}: {erro}"
    avisar("Conferência concluída.", 1.0)
    return resultado


@dataclass
class ResultadoPendencias:
    """O que a tela mostra depois de gerar as pendências e os e-mails do mês."""

    ano: int
    mes: int
    pendencias: Pendencias | None = None
    caminho_previa: Path | None = None
    caminho_texto: Path | None = None      # os e-mails em texto, para o Claude Desktop criar os rascunhos
    erro: str = ""                         # não deu para gerar (Check list, relatório...)
    erro_previa: str = ""                  # não deu para gravar a prévia ou o texto


def gerar_pendencias(checklist: Path, pasta_saida: Path, ano: int, mes: int, relatorio: Path | None = None,
                     progresso: Progresso | None = None, agora: datetime | None = None) -> ResultadoPendencias:
    """Pendências por responsável (P1 a P6), e-mails (E1 a E6) e a prévia na pasta de saída (E7).

    relatorio (opcional): o relatório da conferência do mesmo mês, para deixar de fora as linhas com
    CONTA DIVERGENTE (P2).
    """
    if not (checklist and pasta_saida and ano and mes):
        raise ValueError("Escolha o Check list, a pasta de saída e o mês.")
    agora = agora or datetime.now()
    resultado = ResultadoPendencias(ano, mes)

    def avisar(texto: str, fracao: float | None):
        if progresso:
            progresso(texto, fracao)

    try:
        avisar("Lendo o Check list...", 0.1)
        lido = ler_checklist(Path(checklist), ano, mes)
        divergentes = set()
        if relatorio:
            avisar("Lendo o relatório da conferência...", 0.4)
            divergentes = linhas_divergentes(Path(relatorio), ano, mes, lido)
    except ErroLeitura as erro:
        resultado.erro = str(erro)
        avisar("Não foi possível gerar as pendências.", 1.0)
        return resultado

    avisar("Separando as notas pendentes por responsável...", 0.6)
    listas, avisos = gerar_listas(lido, divergentes)
    pendencias = resultado.pendencias = Pendencias(listas, avisos=lido.avisos + avisos + avisos_dos_codigos(lido),
                                                   conta_divergente=notas_conta_divergente(lido, divergentes))
    avisar("Montando os e-mails...", 0.8)
    montar_emails(pendencias, lido.contatos, ano, mes, agora.date())

    avisar("Gravando a prévia dos e-mails...", 0.9)
    data_hora = agora.strftime(cfg.FORMATO_DATA_HORA_NOME)
    saidas = (("caminho_previa", cfg.NOME_PREVIA_EMAILS, "a prévia", previa_html, "utf-8"),
              ("caminho_texto", cfg.NOME_TEXTO_CLAUDE_DESKTOP, "o texto para o Claude Desktop",
               texto_para_claude_desktop, "utf-8-sig"))
    for atributo, modelo_nome, descricao, montar, codificacao in saidas:
        caminho = _caminho_livre(Path(pasta_saida) / modelo_nome.format(ano=ano, mes=mes, data_hora=data_hora))
        try:
            caminho.write_text(montar(pendencias, ano, mes, agora.date()), encoding=codificacao)
            setattr(resultado, atributo, caminho)
        except OSError as erro:
            resultado.erro_previa += f"Não foi possível gravar {descricao} {caminho.name}: {erro} "
    resultado.erro_previa = resultado.erro_previa.strip()
    avisar("Pendências geradas.", 1.0)
    return resultado


@dataclass
class ItemRascunho:
    """Um e-mail e o que aconteceu com ele no Gmail (G5)."""

    email: Email
    id_gmail: str = ""
    erro: str = ""


@dataclass
class ResultadoRascunhos:
    """O que a tela mostra depois de criar os rascunhos."""

    conta: str = ""                        # a conta autorizada (G2)
    itens: list[ItemRascunho] = field(default_factory=list)
    caminho_registro: Path | None = None
    erro: str = ""                         # nada foi criado (autorização, conta errada...)
    erro_registro: str = ""

    @property
    def criados(self) -> int:
        return sum(1 for i in self.itens if i.id_gmail)


def _gravar_registro(caminho: Path, itens: list[ItemRascunho], agora: datetime) -> None:
    with open(caminho, "w", encoding="utf-8-sig", newline="") as arquivo:
        escritor = csv.writer(arquivo, delimiter=";")
        escritor.writerow(cfg.REGISTRO_GMAIL_COLUNAS)
        for item in itens:
            escritor.writerow([agora.strftime("%d/%m/%Y %H:%M:%S"), cfg.TIPO_REGISTRO_RASCUNHO,
                               item.email.responsavel, ", ".join(item.email.para), item.email.assunto,
                               item.email.notas, item.id_gmail, item.erro])


def criar_rascunhos(emails: list[Email], credentials_json: Path, remetente_esperado: str, pasta_saida: Path,
                    progresso: Progresso | None = None, cliente=None, agora: datetime | None = None
                    ) -> ResultadoRascunhos:
    """G1 a G5: um rascunho por e-mail na conta autorizada, só se ela for a do remetente esperado.

    cliente: só para os testes (um Gmail simulado); no uso normal, o ClienteGmail (abre o navegador
    para autorizar na primeira vez).
    """
    if not (emails and remetente_esperado and pasta_saida):
        raise ValueError("Gere as pendências antes e informe o remetente e a pasta de saída.")
    agora = agora or datetime.now()
    resultado = ResultadoRascunhos()

    def avisar(texto: str, fracao: float | None):
        if progresso:
            progresso(texto, fracao)

    try:
        if cliente is None:
            avisar("Conectando ao Gmail (na primeira vez o navegador pede a autorização)...", None)
            cliente = ClienteGmail(Path(credentials_json))
        resultado.conta = cliente.conta()
    except ErroGmail as erro:
        resultado.erro = str(erro)
        avisar("Não foi possível conectar ao Gmail.", 1.0)
        return resultado
    if resultado.conta != remetente_esperado.strip().lower():                     # G2
        resultado.erro = (f"A conta autorizada é {resultado.conta}, mas o remetente esperado é "
                          f"{remetente_esperado.strip()}. Nenhum rascunho foi criado: troque a conta "
                          "autorizada ou o remetente esperado.")
        avisar("Conta diferente da esperada.", 1.0)
        return resultado

    for numero, email in enumerate(emails, start=1):
        avisar(f"Criando o rascunho {numero} de {len(emails)} ({email.responsavel})...", numero / len(emails))
        item = ItemRascunho(email)
        try:
            item.id_gmail = cliente.criar_rascunho(email, resultado.conta)
        except ErroGmail as erro:                                                  # G5: os outros seguem
            item.erro = str(erro)
        resultado.itens.append(item)

    nome = cfg.NOME_REGISTRO_GMAIL.format(data_hora=agora.strftime(cfg.FORMATO_DATA_HORA_NOME))
    caminho = _caminho_livre(Path(pasta_saida) / nome)
    try:
        _gravar_registro(caminho, resultado.itens, agora)
        resultado.caminho_registro = caminho
    except OSError as erro:
        resultado.erro_registro = f"Não foi possível gravar o registro {caminho.name}: {erro}"
    avisar(f"{resultado.criados} de {len(emails)} rascunho(s) criado(s).", 1.0)
    return resultado


# ---------------------------------------------------------------------------
# Apoio à tela: mês, confirmação de cada cartão, escolhas lembradas e resumos (seção 7)
# ---------------------------------------------------------------------------

CHAVE_PREFERENCIAS = "checklist_contratos"     # %APPDATA%\CentralConciliacoes\checklist_contratos.json
REMETENTE_PADRAO = cfg.REMETENTE_PADRAO
# G6: sem credencial, a aba E-mails explica como pedir à TI e lembra o texto para o Claude Desktop (E8)
TEXTO_SEM_CREDENCIAL = (
    "Para criar os rascunhos direto no Gmail é preciso o credentials.json do Google: peça à TI um projeto "
    "no Google Cloud da Hospital Exemplo com a Gmail API ativa, tela de consentimento \"Interno\" e uma "
    "credencial OAuth do tipo \"App para computador\" (veja as Instruções de uso). Enquanto isso, use o "
    "botão \"Texto Claude\" da aba Pendências: o Claude Desktop cria os rascunhos com ele.")
PREFERENCIAS = ("movimento_sc", "movimento_cmd", "checklist", "configuracao", "saida", "relatorio",
                "credenciais", "remetente", "mes")


def interpretar_mes(texto: str) -> tuple[int, int] | None:
    """"10/2026" -> (2026, 10); inválido -> None."""
    achado = cfg.RE_MES_DIGITADO.match(texto or "")
    if not achado:
        return None
    mes, ano = int(achado.group(1)), int(achado.group(2))
    return (ano, mes) if 1 <= mes <= 12 and 2000 <= ano <= 2100 else None


def texto_do_mes(ano: int, mes: int) -> str:
    return f"{mes:02d}/{ano}"


def ler_preferencias(pasta: Path | None = None) -> dict[str, str]:
    """O que a tela lembra (caminhos, remetente, mês). Nada aqui toca na rede: só o .json local."""
    dados = ler_preferencias_modulo(CHAVE_PREFERENCIAS, pasta)
    return {chave: valor for chave, valor in dados.items()
            if chave in PREFERENCIAS and isinstance(valor, str) and valor}


def salvar_preferencias(pasta: Path | None = None, **valores) -> bool:
    """Guarda os valores informados (os outros continuam como estavam)."""
    dados = ler_preferencias(pasta)
    dados.update({chave: str(valor) for chave, valor in valores.items() if chave in PREFERENCIAS and valor})
    return salvar_preferencias_modulo(CHAVE_PREFERENCIAS, dados, pasta)


Confirmacao = tuple[str, str]                  # (texto, "ok" | "atencao" | "erro")


def confirmar_movimento(caminho: Path, estabelecimento: str) -> Confirmacao:
    """Lê o movimento (arquivo ou pasta, M3) para mostrar no cartão."""
    try:
        movimento = ler_movimentos(Path(caminho), estabelecimento)
    except ErroLeitura as erro:
        return str(erro), "erro"
    arquivos = len(arquivos_do_movimento(Path(caminho)))
    texto = (f"{len(movimento.lancamentos)} lançamento(s) de débito"
             + (f" em {arquivos} arquivos" if arquivos > 1 else ""))
    if movimento.avisos:
        return f"{texto}; {len(movimento.avisos)} aviso(s): {movimento.avisos[0].mensagem}", "atencao"
    return texto, "ok"


def confirmar_checklist(caminho: Path, ano: int | None, mes: int | None) -> Confirmacao:
    if not (ano and mes):
        return "Informe o mês de referência para conferir o Check list", "atencao"
    try:
        checklist = ler_checklist(Path(caminho), ano, mes)
    except ErroLeitura as erro:
        return str(erro), "erro"
    sc, cmd = (len(checklist.abas[e].linhas) for e in cfg.ESTABELECIMENTOS)
    texto = f"{sc} linhas Hospital Exemplo, {cmd} CMD, {len(checklist.contatos)} contatos"
    if checklist.avisos:
        return f"{texto}; {len(checklist.avisos)} aviso(s) na aba {cfg.ABA_EMAILS}", "atencao"
    return texto, "ok"


def pasta_configuracao_sugerida(checklist: Path) -> Path | None:
    """A pasta com o regras.csv ao lado do Check list (a "config" dele ou a própria pasta); None se não houver.

    Toca na pasta do Check list (pode ser a rede): a tela chama em segundo plano."""
    pasta = Path(checklist).parent
    for nome in cfg.PASTAS_CONFIGURACAO_SUGERIDAS:
        candidata = (pasta / nome) if nome != "." else pasta
        if (candidata / cfg.ARQUIVO_REGRAS).is_file():
            return candidata
    return None


def confirmar_configuracao(pasta: Path) -> Confirmacao:
    try:
        configuracao = ler_configuracao(Path(pasta))
    except ErroLeitura as erro:
        return str(erro), "erro"
    texto = f"{len(configuracao.regras)} regra(s)"
    if configuracao.avisos:
        return f"{texto}; {len(configuracao.avisos)} aviso(s): {configuracao.avisos[0].mensagem}", "atencao"
    return texto, "ok"


def confirmar_relatorio(caminho: Path, ano: int | None, mes: int | None) -> Confirmacao:
    """O relatório da conferência (P2): confere o mês pelo nome; a leitura é na hora de gerar."""
    if not Path(caminho).is_file():
        return "Arquivo não encontrado", "erro"
    achado = cfg.RE_MES_DO_RELATORIO.search(Path(caminho).name)
    if achado and ano and mes and (int(achado.group(1)), int(achado.group(2))) != (ano, mes):
        return f"É de {achado.group(2)}/{achado.group(1)}, não do mês escolhido", "erro"
    return "As linhas com conta divergente ficam fora das pendências", "ok"


def confirmar_credenciais(caminho: Path) -> Confirmacao:
    try:
        dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "Não é um credentials.json do Google", "erro"
    if not isinstance(dados, dict) or "installed" not in dados:
        return "Não é um credentials.json de \"App para computador\"", "erro"
    return "Credencial do Google (App para computador)", "ok"


def _reais(valor) -> str:
    return "" if valor is None else f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


@dataclass
class ResumoConferencia:
    """O que a aba Conferência mostra (os textos já prontos)."""

    numeros: list[tuple] = field(default_factory=list)       # (número, legenda, tom)
    divergencias: list[tuple] = field(default_factory=list)  # (fornecedor, contas, valor, lote/lançamento)
    linhas: list[tuple] = field(default_factory=list)        # (texto, status) para LinhaConferencia
    selo: tuple[str, str] = ("Concluído", "ok")


def resumir_conferencia(resultado: ResultadoMes, maximo_linhas: int = 12) -> ResumoConferencia:
    resumo = ResumoConferencia()
    contagem = resultado.conferencia.contagem()
    divergente = contagem[Situacao.CONTA_DIVERGENTE]
    resumo.numeros = [(resultado.preenchidas, "Preenchidas na cópia", "ok"),
                      (divergente, "Conta divergente", "atencao" if divergente else "ok"),
                      (contagem[Situacao.NAO_ENCONTRADO], "Não encontradas", "principal"),
                      (contagem[Situacao.MANUAL], "Manuais", "principal")]
    linhas = []
    for r in resultado.conferencia.resultados:
        if r.situacao == Situacao.CONTA_DIVERGENTE:
            for l in r.divergentes:
                resumo.divergencias.append((r.linha.fornecedor, f"{'/'.join(r.regra.contas)} x {l.conta}",
                                            _reais(l.valor), l.lote_lancamento))
        local = f"{cfg.NOMES_CURTOS[r.regra.aba]} linha {r.linha.numero} ({r.linha.fornecedor})"
        if r.valor_diferente:
            linhas.append((f"{local}: achado {_reais(r.valor)}, diferente do que já está na planilha", "atencao"))
        if r.provisao:
            linhas.append((f"{local}: \"Provisão\" na planilha e achado {_reais(r.valor)}. "
                           f"{cfg.AVISO_PROVISAO}", "atencao"))
        if r.variacao_destacada:
            linhas.append((f"{local}: variação de {_reais(r.variacao)}% sobre o mês anterior", "atencao"))
    avisos = resultado.conferencia.avisos + resultado.avisos
    if avisos:
        linhas.append((f"{len(avisos)} aviso(s) na aba Avisos do relatório (ex.: {avisos[0].mensagem})",
                       "atencao"))
    if len(linhas) > maximo_linhas:
        linhas = linhas[:maximo_linhas - 1] + [(f"e mais {len(linhas) - maximo_linhas + 1} no relatório",
                                                "atencao")]
    erros = [(texto, "erro") for texto in (resultado.erro_relatorio, resultado.erro_copia) if texto]
    resumo.linhas = erros + linhas or [("Nenhum destaque: valores e variações dentro do esperado", "ok")]
    if erros:
        resumo.selo = ("Com erro", "erro")
    elif divergente or avisos or linhas:
        resumo.selo = ("Conferir", "atencao")
    return resumo


@dataclass
class ResumoPendencias:
    """O que a aba Pendências mostra (os textos já prontos)."""

    numeros: list[tuple] = field(default_factory=list)
    responsaveis: list[tuple] = field(default_factory=list)  # (responsável, estabelecimentos, notas, destinatários)
    linhas: list[tuple] = field(default_factory=list)        # (texto, status)
    selo: tuple[str, str] = ("Concluído", "ok")


def resumir_pendencias(resultado: ResultadoPendencias) -> ResumoPendencias:
    pendencias = resultado.pendencias
    resumo = ResumoPendencias()
    sem = len(pendencias.sem_email)
    resumo.numeros = [(pendencias.notas, "Notas pendentes", "principal"),
                      (len(pendencias.emails), "E-mails", "ok"),
                      (sem, "Sem e-mail", "erro" if sem else "ok")]
    for email in pendencias.emails:
        resumo.responsaveis.append((email.responsavel, " e ".join(cfg.NOMES_CURTOS[l.estabelecimento]
                                                                  for l in email.listas),
                                    email.notas, len(email.para)))
    linhas = [(f"Sem e-mail: {item.responsavel} ({sum(len(l.notas) for l in item.listas)} nota(s)). "
               f"{item.motivo}", "erro") for item in pendencias.sem_email]
    if pendencias.conta_divergente:
        linhas.append((f"{len(pendencias.conta_divergente)} nota(s) fora dos e-mails por conta divergente: a nota "
                       "chegou, falta corrigir a conta (lista na prévia)", "atencao"))
    if pendencias.avisos:
        linhas.append((f"{len(pendencias.avisos)} aviso(s) no fim da prévia (ex.: "
                       f"{pendencias.avisos[0].mensagem})", "atencao"))
    erros = [(resultado.erro_previa, "erro")] if resultado.erro_previa else []
    resumo.linhas = erros + linhas or [("Todos os responsáveis têm e-mail", "ok")]
    if erros:
        resumo.selo = ("Com erro", "erro")
    elif linhas:
        resumo.selo = ("Conferir", "atencao")
    return resumo
