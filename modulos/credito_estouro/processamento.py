"""Porta de entrada do Crédito Estouro para a tela (ESPECIFICACAO_CREDITO_ESTOURO.md, seções 3, 5 e 6).

processar(): eventos da folha + razão da conta + controle do mês anterior → conciliação (R1 a R6) → Excel na pasta
escolhida (ou na do razão). Nunca levanta exceção por problema em arquivo: vai para `erro` ou `erro_saida`.
Também: as prévias que a tela mostra ao escolher cada arquivo e a pasta de saída lembrada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Sequence

from central.preferencias import ler_preferencias_modulo, salvar_preferencias_modulo
from modulos.credito_estouro import conciliador as c
from modulos.credito_estouro.conciliador import Conciliacao, conciliar
from modulos.credito_estouro.controle import LeituraControle, ler_controle
from modulos.credito_estouro.leitor_eventos import ler_varios
from modulos.credito_estouro.leitor_razao import conferir_periodo, ler_razao
from modulos.credito_estouro.modelos import (
    EVENTO_CREDITO_ESTOURO,
    EVENTO_DEBITO_ESTOURO,
    EVENTO_DEVOLUCAO,
    EVENTO_PARCELADO,
    EVENTO_REEMBOLSO_AFASTADO,
    Aviso,
    LeituraEventos,
    LeituraRazao,
)
from modulos.credito_estouro.relatorio_excel import caminho_do_relatorio, gravar_relatorio, mes_curto
from modulos.credito_estouro.util import reais

CHAVE = "credito_estouro"
Progresso = Callable[[str, float | None], None]


@dataclass
class ResultadoCreditoEstouro:
    eventos: LeituraEventos | None = None
    razao: LeituraRazao | None = None
    controle: LeituraControle | None = None
    conciliacao: Conciliacao | None = None
    caminho_planilha: Path | None = None
    erro: str = ""            # não deu para conciliar (arquivo ilegível, mês errado…)
    erro_saida: str = ""      # conciliou, mas não deu para gravar o Excel

    @property
    def avisos(self) -> list[Aviso]:
        avisos: list[Aviso] = []
        for parte in (self.eventos, self.razao, self.controle, self.conciliacao):
            if parte is not None:
                avisos += parte.avisos
        return avisos


def mes_anterior(mes: date) -> date:
    return date(mes.year - (mes.month == 1), (mes.month - 2) % 12 + 1, 1)


def conferir_conjunto(eventos: LeituraEventos, razao: LeituraRazao, controle: LeituraControle) -> str:
    """Os três arquivos são do mesmo mês (o controle, do mês anterior)? Devolve a mensagem de erro ou ""."""
    if eventos.competencia is None:
        return "O PDF de eventos não diz de que mês é (\"Período:\"). Confira se escolheu o PDF certo."
    erro_periodo = conferir_periodo(razao, eventos.competencia)
    if erro_periodo:
        return erro_periodo
    esperado = mes_anterior(eventos.competencia)
    if controle.competencia != esperado:
        mes_controle = f"{controle.competencia:%m/%Y}" if controle.competencia else "sem mês"
        return (f"O controle escolhido é de {mes_controle}, mas os eventos são de {eventos.competencia:%m/%Y}. "
                f"Escolha o Excel do Crédito Estouro de {esperado:%m/%Y} (o mês anterior).")
    return ""


def processar(eventos: Path | Sequence[Path], razao: Path, controle: Path, pasta_destino: Path | None = None,
              progresso: Progresso | None = None, agora: datetime | None = None) -> ResultadoCreditoEstouro:
    """Lê os três arquivos, concilia e grava o Excel. pasta_destino None = a pasta do razão."""
    if not (eventos and razao and controle):
        raise ValueError("Escolha os eventos da folha, o razão da conta e o controle do mês anterior.")
    agora = agora or datetime.now()
    resultado = ResultadoCreditoEstouro()

    def avisar(texto: str, fracao: float | None) -> None:
        if progresso is not None:
            progresso(texto, fracao)

    avisar("Lendo o PDF de eventos da folha…", 0.05)
    resultado.eventos = ler_varios(eventos)          # um ou mais PDFs do mês (o 0775 vem separado)
    avisar("Lendo o razão da conta…", 0.35)
    resultado.razao = ler_razao(Path(razao))
    avisar("Lendo o controle do mês anterior…", 0.55)
    resultado.controle = ler_controle(Path(controle))
    for rotulo, leitura in (("Eventos da folha", resultado.eventos), ("Razão", resultado.razao),
                            ("Controle do mês anterior", resultado.controle)):
        if leitura.erro:
            resultado.erro = f"{rotulo} ({leitura.arquivo}): {leitura.erro}"
            return resultado
    resultado.erro = conferir_conjunto(resultado.eventos, resultado.razao, resultado.controle)
    if resultado.erro:
        return resultado

    avisar("Conciliando colaborador por colaborador…", 0.7)
    resultado.conciliacao = conciliar(resultado.eventos, resultado.razao, resultado.controle)

    avisar("Gravando o Excel…", 0.9)
    pasta = Path(pasta_destino) if pasta_destino else Path(razao).parent
    arquivos = {"Eventos da folha": resultado.eventos.arquivo, "Razão da conta": resultado.razao.arquivo,
                "Controle do mês anterior": resultado.controle.arquivo}
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        caminho = caminho_do_relatorio(pasta, resultado.eventos.unidade, resultado.eventos.competencia)
        resultado.caminho_planilha = gravar_relatorio(caminho, resultado.conciliacao, resultado.avisos, arquivos,
                                                      agora)
    except OSError as erro:
        resultado.erro_saida = (f"Não foi possível gravar o Excel em {pasta} ({erro.strerror or erro}). Se ele "
                                "estiver aberto, feche e processe de novo.")
    avisar("Pronto.", 1.0)
    return resultado


# ---------------------------------------------------------------------
# Prévias (o que a tela mostra ao escolher cada arquivo)
# ---------------------------------------------------------------------
@dataclass
class Previa:
    texto: str = ""
    erro: str = ""
    avisos: list[str] = field(default_factory=list)
    leitura: object = None            # a leitura do arquivo (para conferir os meses sem ler de novo)


def previa_eventos(caminhos: Path | Sequence[Path]) -> Previa:
    leitura = ler_varios(caminhos)
    if leitura.erro:
        return Previa(erro=leitura.erro)
    partes = [f"{codigo}: {leitura.quantidade(codigo)}" for codigo in
              (EVENTO_CREDITO_ESTOURO, EVENTO_DEBITO_ESTOURO, EVENTO_REEMBOLSO_AFASTADO, EVENTO_PARCELADO)]
    if leitura.quantidade(EVENTO_DEVOLUCAO):
        partes.append(f"{EVENTO_DEVOLUCAO}: {leitura.quantidade(EVENTO_DEVOLUCAO)}")
    return Previa(leitura=leitura, texto=f"{leitura.unidade} · {mes_curto(leitura.competencia)} · " + " · ".join(partes),
                  avisos=[a.mensagem for a in leitura.avisos])


def previa_razao(caminho: Path) -> Previa:
    leitura = ler_razao(Path(caminho))
    if leitura.erro:
        return Previa(erro=leitura.erro)
    mes = mes_curto(leitura.inicio.replace(day=1)) if leitura.inicio else "sem período"
    texto = (f"{leitura.formato} · {mes} · {len(leitura.lancamentos)} lançamentos · saldo final "
             f"R$ {reais(leitura.saldo_final)}")
    avisos = [a.mensagem for a in leitura.avisos]
    if leitura.formato == "PDF":
        avisos.append("Razão em PDF: o Tasy às vezes corta o fim do nome no PDF. Se puder, use o Excel (.xls) do "
                      "razão, que traz o histórico inteiro.")
    return Previa(texto=texto, avisos=avisos, leitura=leitura)


def previa_controle(caminho: Path) -> Previa:
    leitura = ler_controle(Path(caminho))
    if leitura.erro:
        return Previa(erro=leitura.erro)
    return Previa(texto=f"{mes_curto(leitura.competencia)} · {len(leitura.itens)} itens · R$ {reais(leitura.total)}",
                  avisos=[a.mensagem for a in leitura.avisos], leitura=leitura)


def conferir_previas(eventos: Previa, razao: Previa, controle: Previa) -> str:
    """Com os três arquivos lidos: os meses combinam? (a mesma conferência do processar, antes de clicar)."""
    if eventos.leitura is None or razao.leitura is None or controle.leitura is None:
        return ""
    return conferir_conjunto(eventos.leitura, razao.leitura, controle.leitura)


# ---------------------------------------------------------------------
# O que a tela mostra depois de processar
# ---------------------------------------------------------------------
@dataclass
class ResumoTela:
    contexto: str = ""
    numeros: list[tuple[str, str, str]] = field(default_factory=list)       # (valor, legenda, status)
    linhas: list[tuple[str, str, str | None]] = field(default_factory=list)  # (texto, status, valor)
    selo: tuple[str, str] = ("Concluído", "ok")


def _precisa_conferir(situacao: str) -> bool:
    return situacao.endswith("conferir") or situacao.endswith("conferir a diferença") or situacao in (
        c.PAGOU_A_MAIS, c.PAGOU_A_MENOS, c.NAO_PAGOU)


def resumir(resultado: ResultadoCreditoEstouro) -> ResumoTela:
    resumo = ResumoTela()
    conciliacao = resultado.conciliacao
    if conciliacao is None:
        resumo.linhas = [(resultado.erro or "Nada foi gravado.", "erro", None)]
        resumo.selo = ("Com erro", "erro")
        return resumo
    resumo.contexto = f"{conciliacao.unidade} · {mes_curto(conciliacao.competencia)}"
    situacoes = ([l.situacao for l in conciliacao.cobrancas] + [l.situacao for l in conciliacao.afastados]
                 + [l.situacao for l in conciliacao.parcelamentos] + [l.situacao for l in conciliacao.devolucoes])
    a_conferir = sum(1 for s in situacoes if _precisa_conferir(s)) + len(conciliacao.a_conferir)
    diferenca = conciliacao.diferenca_sem_explicacao
    resumo.numeros = [
        (str(len(conciliacao.cobrancas)), "0256 do mês anterior", "principal"),
        (str(a_conferir), "itens a conferir", "atencao" if a_conferir else "ok"),
        (f"R$ {reais(diferenca)}", "diferença sem explicação", "erro" if diferenca else "ok"),
    ]
    linhas: list[tuple[str, str, str | None]] = []
    if resultado.erro_saida:
        linhas.append((resultado.erro_saida, "erro", None))
    linhas.append(("Saldo final do razão", "ok", f"R$ {reais(conciliacao.saldo_final_razao)}"))
    linhas.append(("Total do controle (o que cada colaborador ainda deve + acertos)", "ok" if not diferenca
                   else "erro", f"R$ {reais(conciliacao.total_controle_novo)}"))
    for conferencia in conciliacao.conferencias_folha:
        if conferencia.diferenca:
            linhas.append((f"Folha × razão: {conferencia.descricao}", "erro", f"R$ {reais(conferencia.diferenca)}"))
    contagem: dict[str, int] = {}
    for situacao in situacoes:
        if _precisa_conferir(situacao):
            contagem[situacao] = contagem.get(situacao, 0) + 1
    for situacao, quantidade in contagem.items():
        linhas.append((f"{quantidade} × {situacao}", "atencao", None))
    if conciliacao.a_conferir:
        linhas.append((f"{len(conciliacao.a_conferir)} lançamento(s) do razão a conferir (aba \"Lançamentos do "
                       "razão a conferir\")", "atencao", None))
    if resultado.avisos:
        linhas.append((f"{len(resultado.avisos)} aviso(s) na aba Avisos (ex.: {resultado.avisos[0].mensagem})",
                       "erro" if any(a.mensagem.startswith("ATENÇÃO") for a in resultado.avisos) else "atencao",
                       None))
    resumo.linhas = linhas
    if resultado.erro_saida or diferenca:
        resumo.selo = ("Com erro" if resultado.erro_saida else "Diferença", "erro")
    elif a_conferir or resultado.avisos:
        resumo.selo = ("Conferir", "atencao")
    return resumo


# ---------------------------------------------------------------------
# Pasta lembrada
# ---------------------------------------------------------------------
def ler_pasta_lembrada(pasta_preferencias: Path | None = None) -> str:
    pasta = ler_preferencias_modulo(CHAVE, pasta_preferencias).get("pasta", "")
    return pasta if isinstance(pasta, str) else ""


def salvar_pasta_lembrada(pasta: str, pasta_preferencias: Path | None = None) -> bool:
    dados = ler_preferencias_modulo(CHAVE, pasta_preferencias)
    dados["pasta"] = pasta
    return salvar_preferencias_modulo(CHAVE, dados, pasta_preferencias)
