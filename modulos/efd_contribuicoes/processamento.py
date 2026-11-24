"""Porta de entrada do EFD Contribuições para a tela (ESPECIFICACAO da Central, seção 4.3).

O trabalho é feito em duas partes, porque a tela pode precisar perguntar algo no meio (seção 4.3):
1. preparar(): lê os PDFs, classifica as notas (selecao.py) e dá o código de cada cliente num cadastro de
   trabalho (uma cópia do cadastro lido). Não grava nada. Diz o que impede a geração (conflitos,
   cadastro sem clientes) e o que precisa de resposta (PDF não lido: R6; cliente novo sem Código IBGE: R7).
2. gerar(): com as respostas, monta o SPED, faz a conferência final (R16), grava o cadastro (relendo
   antes; se outra pessoa gravou, para sem gravar nada) e, por fim, o SPED e o Excel na pasta de saída.
   O cadastro vai primeiro de propósito: se ele não puder ser gravado, nenhum SPED sai com códigos que não
   estão no cadastro. Se o SPED não puder ser gravado depois, os clientes novos ficam guardados (os códigos
   reservados não fazem mal) e basta gerar de novo.
Nada aqui levanta exceção para a tela: os problemas voltam em `erro` / `bloqueios`.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Callable

from modulos.efd_contribuicoes import configuracao as cfg
from modulos.efd_contribuicoes.cadastro_clientes import (  # noqa: F401  (reexportados para a tela)
    Cadastro,
    CadastroMudou,
    ErroCadastro,
    carregar_cadastro,
    codigo_ibge_valido,
    criar_a_partir_do_sped,
    gravar_cadastro,
    novo_cadastro,
)
from modulos.efd_contribuicoes.leitor_danfse import ler_danfse
from modulos.efd_contribuicoes.leitor_sped import ErroSped, MoldeSped, ler_molde, previa_sped  # noqa: F401
from modulos.efd_contribuicoes.montagem_sped import NotaSped, montar_sped
from modulos.efd_contribuicoes.relatorio_excel import gerar_excel, nome_do_excel
from modulos.efd_contribuicoes.selecao import NotaClassificada, Selecao, avisos_prestador, classificar, incluir

Progresso = Callable[[str, float | None], None]


@dataclass
class Preparacao:
    pasta_pdfs: Path
    competencia: str
    molde: MoldeSped | None = None
    cadastro: Cadastro | None = None          # cópia de trabalho (o arquivo só muda ao gerar)
    selecao: Selecao = field(default_factory=Selecao)
    notas_sped: list[NotaSped] = field(default_factory=list)
    bloqueios: list[str] = field(default_factory=list)      # impedem a geração (a tela só mostra)
    avisos_prestador: list[str] = field(default_factory=list)   # PDFs de prestador com CNPJ diferente

    @property
    def nao_lidas(self):
        return self.selecao.nao_lidas

    @property
    def incluiveis(self) -> list[NotaClassificada]:
        """Notas fora por causa das datas: a tela oferece incluir (ajuste de 05/11/2026)."""
        return self.selecao.incluiveis

    @property
    def avisos(self) -> list[str]:
        """Prestador com CNPJ diferente, diferenças com o cadastro e cada nota fora do SPED (ou incluída à mão)."""
        avisos = list(self.avisos_prestador)
        if self.cadastro is not None:
            avisos.extend(self.cadastro.avisos)
        for item in self.selecao.notas:
            if item.situacao not in (cfg.SITUACAO_NO_SPED, cfg.SITUACAO_PF):
                avisos.append(f"{item.nota.arquivo}: {item.situacao}"
                              + (f" — {item.observacao}" if item.observacao else ""))
        return avisos

    def novos_sem_ibge(self) -> list[dict]:
        return self.cadastro.novos_sem_ibge() if self.cadastro is not None else []


@dataclass
class ResultadoEFD:
    preparacao: Preparacao
    caminho_sped: Path | None = None
    caminho_excel: Path | None = None
    caminho_copia_cadastro: Path | None = None
    total_receita: Decimal = Decimal("0")
    erro: str = ""
    avisos: list[str] = field(default_factory=list)

    @property
    def selecao(self) -> Selecao:
        return self.preparacao.selecao

    @property
    def competencia(self) -> str:
        return self.preparacao.competencia

    @property
    def clientes_novos(self) -> list[tuple[dict, str]]:
        cadastro = self.preparacao.cadastro
        if cadastro is None:
            return []
        return [(cadastro.clientes[c], origem) for c, origem in cadastro.novos.items()]

    def totais(self) -> list[tuple[str, int, Decimal]]:
        """(rótulo, quantidade, valor): no SPED (= M400), PF e fora do SPED (os demais)."""
        def soma(itens):
            return sum((i.nota.valor or Decimal("0") for i in itens), Decimal("0"))
        notas = self.selecao.notas
        no_sped = [i for i in notas if i.no_sped]
        pf = [i for i in notas if i.situacao == cfg.SITUACAO_PF]
        fora = [i for i in notas if not i.no_sped and i.situacao != cfg.SITUACAO_PF]
        return [("No SPED", len(no_sped), soma(no_sped)), ("PF", len(pf), soma(pf)),
                ("Fora do SPED (outros motivos)", len(fora), soma(fora))]


def _avisar(progresso: Progresso | None, texto: str, fracao: float) -> None:
    if progresso is not None:
        progresso(texto, fracao)


def competencia_valida(texto: str) -> bool:
    partes = (texto or "").strip().split("/")
    return len(partes) == 2 and partes[0].isdigit() and partes[1].isdigit() and len(partes[1]) == 4 \
        and 1 <= int(partes[0]) <= 12 and len(partes[0]) == 2


def preparar(pasta_pdfs: Path, arquivo_sped: Path, competencia: str, cadastro: Cadastro,
             progresso: Progresso | None = None) -> Preparacao:
    """Parte 1. `cadastro` é o lido do arquivo escolhido (a tela lê em segundo plano); ele não é alterado."""
    pasta_pdfs = Path(pasta_pdfs)
    preparacao = Preparacao(pasta_pdfs=pasta_pdfs, competencia=competencia)
    if not competencia_valida(competencia):
        preparacao.bloqueios.append("Competência inválida: use MM/AAAA (ex.: 09/2026).")
        return preparacao
    try:
        preparacao.molde = ler_molde(arquivo_sped)
    except ErroSped as erro:
        preparacao.bloqueios.append(str(erro))
        return preparacao
    if not cadastro.clientes:          # cadastro vazio recomeçaria os códigos do 1
        preparacao.bloqueios.append("O cadastro de clientes está vazio: escolha o clientes.json ou crie um a "
                                    "partir do SPED do mês anterior.")
        return preparacao
    preparacao.cadastro = copy.deepcopy(cadastro)

    pdfs = sorted(pasta_pdfs.glob("*.pdf"), key=lambda p: p.name.casefold())
    if not pdfs:
        preparacao.bloqueios.append(f"Nenhum PDF na pasta {pasta_pdfs}.")
        return preparacao
    notas = []
    for posicao, pdf in enumerate(pdfs, start=1):
        _avisar(progresso, f"Lendo as notas ({posicao} de {len(pdfs)})...", 0.05 + 0.75 * posicao / len(pdfs))
        notas.append(ler_danfse(pdf))

    _avisar(progresso, "Conferindo as notas...", 0.85)
    preparacao.selecao = classificar(notas, competencia)
    preparacao.bloqueios.extend(preparacao.selecao.conflitos)
    preparacao.avisos_prestador = avisos_prestador(notas)
    _entrar_no_sped(preparacao, preparacao.selecao.no_sped)
    _avisar(progresso, "Notas conferidas.", 1.0)
    return preparacao


def _entrar_no_sped(preparacao: Preparacao, itens: list[NotaClassificada]) -> None:
    for item in itens:
        nota = item.nota
        cod_part = preparacao.cadastro.obter_cod_part(nota.cnpj_digitos, nota.tomador, nota.codigo_ibge_tomador)
        preparacao.notas_sped.append(NotaSped(cod_part, nota.numero_nfse.strip(), nota.data_emissao, nota.valor))


def incluir_notas(preparacao: Preparacao, arquivos: list[str]) -> int:
    """Inclui à mão as notas destes arquivos que ficaram fora pelas datas (ajuste de 05/11/2026). Devolve quantas."""
    incluidas = incluir(preparacao.selecao, arquivos)
    _entrar_no_sped(preparacao, incluidas)
    return len(incluidas)


def _caminho_livre(caminho: Path) -> Path:
    candidato, contador = caminho, 2
    while candidato.exists():
        candidato = caminho.with_name(f"{caminho.stem}_{contador}{caminho.suffix}")
        contador += 1
    return candidato


def gerar(preparacao: Preparacao, pasta_saida: Path, aceitar_nao_lidas: bool = False,
          progresso: Progresso | None = None, agora: datetime | None = None) -> ResultadoEFD:
    """Parte 2. `aceitar_nao_lidas`: a resposta "Sim" à pergunta da R6."""
    agora = agora or datetime.now()
    resultado = ResultadoEFD(preparacao=preparacao, avisos=list(preparacao.avisos))
    if preparacao.bloqueios:
        resultado.erro = preparacao.bloqueios[0]
        return resultado
    if not preparacao.notas_sped:
        resultado.erro = "Nenhuma nota para o SPED: todas ficaram fora (veja a situação de cada uma)."
        return resultado
    if preparacao.nao_lidas and not aceitar_nao_lidas:
        resultado.erro = "Geração cancelada: há PDF(s) que não puderam ser lidos."
        return resultado
    sem_ibge = preparacao.novos_sem_ibge()
    if sem_ibge:
        resultado.erro = ("Cliente(s) novo(s) sem Código IBGE (o EFD Contribuições não aceita): "
                          + "; ".join(f"{c['nome']} (código {c['cod_part']})" for c in sem_ibge) + ".")
        return resultado
    pasta_saida = Path(pasta_saida)
    if not pasta_saida.is_dir():
        resultado.erro = f"A pasta de saída não existe: {pasta_saida}."
        return resultado

    _avisar(progresso, "Montando o SPED...", 0.2)
    montado = montar_sped(preparacao.molde, preparacao.competencia, preparacao.cadastro.para_sped(),
                          preparacao.notas_sped)
    if montado.erros:
        resultado.erro = "O arquivo montado não passou na conferência final (nada foi gravado): " + \
                         " ".join(montado.erros)
        return resultado
    resultado.total_receita = montado.total_receita

    _avisar(progresso, "Gravando o cadastro de clientes...", 0.5)
    try:
        if preparacao.cadastro.novos or not preparacao.cadastro.existe:
            resultado.caminho_copia_cadastro = gravar_cadastro(preparacao.cadastro, agora)
    except ErroCadastro as erro:
        resultado.erro = str(erro)
        return resultado

    _avisar(progresso, "Gravando o SPED e o Excel...", 0.8)
    mes, ano = preparacao.competencia.split("/")
    try:
        caminho_sped = _caminho_livre(pasta_saida / f"SpedEPC_gerado_{mes}_{ano}.txt")
        caminho_sped.write_bytes(montado.texto.encode(cfg.CODIFICACAO_SPED))
        resultado.caminho_sped = caminho_sped
        resultado.caminho_excel = gerar_excel(
            resultado, _caminho_livre(pasta_saida / nome_do_excel(preparacao.competencia, agora)))
    except UnicodeEncodeError as erro:
        resultado.erro = f"Um nome de cliente tem um caractere que o SPED (ISO-8859-1) não aceita: {erro.object[erro.start:erro.end]!r}."
    except OSError as erro:
        resultado.erro = (f"Não foi possível gravar na pasta {pasta_saida} ({erro.strerror or erro}). "
                          "O cadastro já foi atualizado; feche o arquivo se estiver aberto e gere de novo.")
    _avisar(progresso, "Concluído." if not resultado.erro else "Não concluído.", 1.0)
    return resultado
