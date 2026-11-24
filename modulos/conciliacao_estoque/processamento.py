"""Orquestra a conciliação de estoque. É o único arquivo da lógica que a tela chama.

Um botão por etapa (decisão do usuário, 06/10/2026), cada um gerando o seu Excel:
- EST-01 (Conciliação saldo anterior estoque) e EST-03 (Conciliação saldo atual estoque):
  balancete + SCF (comparacao.py, relatorio_excel.py);
- EST-02 (Conciliação contas estoque): SCF + PDF "Movimento estoque" + configuração
  (conferencia_grupos.py, relatorio_est02.py).
Cada etapa só pede os arquivos que usa (ETAPAS_DA_TELA).

Funções para a tela:
- ETAPAS_DA_TELA: id, nome e arquivos de cada botão;
- interpretar_mes, mes_do_balancete, mes_do_scf, mes_do_pdf: mês digitado / lido de cada arquivo;
- arquivo_de_saida: o Excel que a etapa grava, para perguntar antes de substituir;
- situacao_configuracao, preparar_configuracao: a configuração da EST-02 e o botão "Editar configuração";
- processar: faz uma etapa e devolve o ResultadoEstoque. Aceita progresso(texto, fracao).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from modulos.conciliacao_estoque import configuracao
from modulos.conciliacao_estoque.comparacao import comparar
from modulos.conciliacao_estoque.conferencia_grupos import conferir_grupos
from modulos.conciliacao_estoque.configuracao_est02 import (
    carregar_configuracao_estoque,
    preparar_configuracao_do_usuario,
)
from modulos.conciliacao_estoque.leitor_balancete_estoque import ler_balancete_estoque
from modulos.conciliacao_estoque.leitor_pdf_movimento import ler_pdf_movimento
from modulos.conciliacao_estoque.leitor_scf import ler_scf
from modulos.conciliacao_estoque.modelos import (
    Aviso,
    ErroArquivo,
    Gravidade,
    MesReferencia,
    ResultadoComparacao,
    ResultadoEST02,
)
from modulos.conciliacao_estoque.relatorio_est02 import gerar_excel_est02, nome_arquivo_est02
from modulos.conciliacao_estoque.relatorio_excel import gerar_excel, nome_arquivo_etapa
from modulos.conciliacao_estoque.utilitarios import mes_de_texto

BALANCETE, SCF, PDF = "balancete", "scf", "pdf"


@dataclass(frozen=True)
class EtapaDaTela:
    id: str
    titulo: str
    arquivos: tuple[str, ...]       # quais entradas a etapa usa (BALANCETE, SCF, PDF)

    @property
    def texto_botao(self) -> str:
        return f"{self.id} · {self.titulo}"


_EST01, _EST03 = configuracao.ETAPAS
ETAPAS_DA_TELA = [
    EtapaDaTela(_EST01.id, _EST01.titulo, (BALANCETE, SCF)),
    EtapaDaTela(configuracao.ID_EST02, configuracao.TITULO_EST02, (SCF, PDF)),
    EtapaDaTela(_EST03.id, _EST03.titulo, (BALANCETE, SCF)),
]


def etapa_da_tela(id_etapa: str) -> EtapaDaTela:
    return next(e for e in ETAPAS_DA_TELA if e.id == id_etapa)


@dataclass
class ArquivoLido:
    tipo: str               # "Balancete", "Mapa do Estoque", "PDF Movimento estoque", "Configuração da EST-02"
    nome: str
    ok: bool
    detalhe: str = ""


@dataclass
class ResultadoEstoque:
    etapa: EtapaDaTela
    mes_referencia: MesReferencia
    pasta_saida: str
    comparacao: ResultadoComparacao | None = None   # EST-01 / EST-03
    est02: ResultadoEST02 | None = None             # EST-02
    caminho_excel: Path | None = None               # None = não gerado (ver `falha`)
    falha: str = ""
    arquivos: list[ArquivoLido] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)

    @property
    def erros(self) -> int:
        return sum(1 for a in self.avisos if a.gravidade == Gravidade.ERRO)


# ---------------------------------------------------------------------------
# Consultas para a tela (antes de processar)
# ---------------------------------------------------------------------------


def interpretar_mes(texto: str) -> MesReferencia | None:
    """Mês digitado na tela ("09/2026") -> MesReferencia. None se inválido."""
    texto = (texto or "").strip()
    return mes_de_texto(texto) if len(texto.split("/")) == 2 else None


def _mes_ou_nada(leitura):
    try:
        return leitura().mes_referencia
    except Exception:
        return None


def mes_do_balancete(caminho) -> MesReferencia | None:
    return _mes_ou_nada(lambda: ler_balancete_estoque(caminho))


def mes_do_scf(caminho) -> MesReferencia | None:
    return _mes_ou_nada(lambda: ler_scf(caminho))


def mes_do_pdf(caminho) -> MesReferencia | None:
    return _mes_ou_nada(lambda: ler_pdf_movimento(caminho))


def arquivo_de_saida(id_etapa: str, pasta_saida, mes: MesReferencia) -> Path:
    if id_etapa == configuracao.ID_EST02:
        return Path(pasta_saida) / nome_arquivo_est02(mes)
    etapa = next(e for e in configuracao.ETAPAS if e.id == id_etapa)
    return Path(pasta_saida) / nome_arquivo_etapa(etapa, mes)


def situacao_configuracao(pasta_configuracao: Path | None = None) -> tuple[str, str]:
    """(texto, status) para a tela: qual configuração da EST-02 vale e se está em ordem."""
    try:
        config = carregar_configuracao_estoque(pasta=pasta_configuracao)
    except ErroArquivo as erro:
        return f"Configuração da EST-02 não pôde ser lida: {erro}", "erro"
    if not config.valida:
        erros = sum(1 for a in config.avisos if a.gravidade == Gravidade.ERRO)
        return (f"Configuração da EST-02 com {erros} problema{'s' if erros > 1 else ''}: "
                "corrija em Editar configuração", "erro")
    origem = "de fábrica" if config.de_fabrica else "sua (editada)"
    return f"Configuração da EST-02: {origem}, {len(config.itens)} operações", "ok"


def preparar_configuracao(pasta_configuracao: Path | None = None) -> Path:
    """Botão "Editar configuração": garante a cópia do usuário e devolve o caminho para abrir no Excel."""
    return preparar_configuracao_do_usuario(pasta=pasta_configuracao)


# ---------------------------------------------------------------------------
# Processamento
# ---------------------------------------------------------------------------


def processar(id_etapa: str, pasta_saida, mes_referencia: MesReferencia, balancete=None, scf=None, pdf=None,
              progresso: Callable[[str, float | None], None] | None = None,
              pasta_configuracao: Path | None = None) -> ResultadoEstoque:
    """Faz UMA etapa e grava o Excel dela em `pasta_saida`.

    `mes_referencia` é o mês da tela: vai no nome do arquivo e no título.
    Não levanta exceção por problema em arquivo: o motivo vai para `falha` e `avisos`.
    """
    if mes_referencia is None:
        raise ValueError("Informe o mês de referência (MM/AAAA).")
    etapa = etapa_da_tela(id_etapa)
    progresso = progresso or (lambda texto, fracao: None)
    resultado = ResultadoEstoque(etapa=etapa, mes_referencia=mes_referencia, pasta_saida=str(pasta_saida))
    lidos = {}

    progresso("Lendo os arquivos...", 0.0)
    if BALANCETE in etapa.arquivos:
        progresso("Lendo o balancete...", 0.0)
        lidos[BALANCETE] = _ler(resultado, "Balancete", balancete, ler_balancete_estoque,
                                lambda b: f"{len(b.analiticas)} contas analíticas, mês {b.mes_referencia or '?'}")
    progresso("Lendo o Mapa do Estoque...", 0.25)
    lidos[SCF] = _ler(resultado, "Mapa do Estoque", scf, ler_scf, lambda s: f"{len(s.locais)} locais, mês {s.mes_referencia or '?'}")
    if PDF in etapa.arquivos:
        progresso("Lendo o PDF Movimento estoque...", 0.4)
        lidos[PDF] = _ler(resultado, "PDF Movimento estoque", pdf, ler_pdf_movimento,
                          lambda p: f"{len(p.operacoes)} operações, mês {p.mes_referencia or '?'}")
    _conferir_mes_informado(resultado, *lidos.values())

    nomes = {BALANCETE: "o balancete", SCF: "o Mapa do Estoque", PDF: "o PDF Movimento estoque"}
    faltando = [nomes[chave] for chave in etapa.arquivos if lidos.get(chave) is None]
    if faltando:
        resultado.falha = f"Não foi possível ler {' e '.join(faltando)}. Veja os avisos."
        return resultado

    if id_etapa == configuracao.ID_EST02:
        progresso("Lendo a configuração da EST-02...", 0.5)
        config = _ler_configuracao(resultado, pasta_configuracao)
        if config is None or not config.valida:
            resultado.falha = "A configuração da EST-02 tem problemas: corrija em Editar configuração."
            return resultado
        progresso("Conferindo os grupos...", 0.6)
        _executar(resultado, lambda: conferir_grupos(lidos[SCF], lidos[PDF], config), "est02", gerar_excel_est02)
    else:
        etapa_config = next(e for e in configuracao.ETAPAS if e.id == id_etapa)
        progresso("Comparando as contas...", 0.6)
        _executar(resultado, lambda: comparar(etapa_config, lidos[BALANCETE], lidos[SCF]), "comparacao", gerar_excel)
    progresso("Concluído.", 1.0)
    return resultado


def _mensagem(erro: Exception) -> str:
    if isinstance(erro, ErroArquivo):
        return str(erro)
    if isinstance(erro, PermissionError):
        nome = Path(erro.filename).name if getattr(erro, "filename", None) else "o arquivo"
        return f"Não foi possível gravar {nome}: ele provavelmente está aberto no Excel. Feche e tente de novo."
    return f"Erro inesperado: {type(erro).__name__}: {erro}"


def _ler(resultado, tipo, caminho, leitor, descrever):
    if caminho is None:
        resultado.avisos.append(Aviso(Gravidade.ERRO, "arquivo não escolhido", f"{tipo}: nenhum arquivo escolhido."))
        return None
    nome = Path(caminho).name
    try:
        dados = leitor(caminho)
    except Exception as erro:
        resultado.arquivos.append(ArquivoLido(tipo, nome, False, _mensagem(erro)))
        resultado.avisos.append(Aviso(Gravidade.ERRO, "arquivo não lido", _mensagem(erro), arquivo=nome))
        return None
    resultado.arquivos.append(ArquivoLido(tipo, nome, True, descrever(dados)))
    resultado.avisos.extend(dados.avisos)
    return dados


def _ler_configuracao(resultado, pasta_configuracao):
    tipo = "Configuração da EST-02"
    try:
        config = carregar_configuracao_estoque(pasta=pasta_configuracao)
    except ErroArquivo as erro:
        resultado.arquivos.append(ArquivoLido(tipo, "", False, str(erro)))
        resultado.avisos.append(Aviso(Gravidade.ERRO, "configuração não lida", str(erro)))
        return None
    resultado.arquivos.append(ArquivoLido(tipo, Path(config.caminho).name, config.valida,
                                          f"{config.descricao_origem}, {len(config.itens)} operações"))
    resultado.avisos.extend(config.avisos)
    return config


def _conferir_mes_informado(resultado, *lidos):
    """O mês da tela é o que vale; se algum arquivo é de outro mês, fica registrado."""
    for dados in lidos:
        if dados is not None and dados.mes_referencia and dados.mes_referencia != resultado.mes_referencia:
            resultado.avisos.append(Aviso(
                Gravidade.ATENCAO, "mês diferente",
                f"{dados.arquivo} é de {dados.mes_referencia}, diferente do mês informado "
                f"({resultado.mes_referencia}). O arquivo foi gerado com {resultado.mes_referencia}.",
                arquivo=dados.arquivo))


def _executar(resultado, calcular, atributo, gravar):
    try:
        conta = calcular()
        conta.mes_referencia = resultado.mes_referencia
        setattr(resultado, atributo, conta)
        resultado.avisos.extend(conta.avisos)
        resultado.caminho_excel = gravar(conta, resultado.pasta_saida)
    except Exception as erro:
        resultado.falha = _mensagem(erro)
        resultado.avisos.append(Aviso(Gravidade.ERRO, "etapa não gerada", _mensagem(erro)))
