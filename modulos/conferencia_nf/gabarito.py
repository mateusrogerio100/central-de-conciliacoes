"""Gabarito de contas (S14): o programa aprende com o Movimento contábil já revisado e avisa quando
um lançamento vai para uma conta diferente da habitual ou do Padrão decidido pela chefia.

A memória é a planilha Gabarito_contas.xlsx, numa pasta escolhida na tela (em geral na rede, para
todos usarem a mesma):
- "Padrão": a conta oficial de cada fornecedor + produto. Só a chefia edita (pode proteger a aba
  com senha no Excel); o programa só LÊ esta aba e nunca grava nela.
- "Histórico": tudo o que já foi aprendido (fornecedor + produto + conta, quantas vezes, quando).
- "Para padronizar": os fornecedores + produtos lançados em mais de uma conta, com o %.
- "Fatos aprendidos": os fatos já ensinados (ensinar o mesmo mês de novo não conta em dobro).

O fornecedor é a conta dele no passivo (crédito em 2.01.01.01): única por fornecedor e estável,
ao contrário do nome. O produto é o texto do complemento entre "NF. número -" e "DT"/"PR"/"O.C"
(vazio quando o complemento não traz o produto: aí vale só o fornecedor). Só informativo: não
muda a situação do fato (decisão do usuário, 16/10/2026). O centro de custo fica de fora.

Sem tela: a tela chama processamento.py.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Callable

import openpyxl
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from modulos.conferencia_nf import configuracao as cfg
from modulos.conferencia_nf.conferencia import separar_estornos
from modulos.conferencia_nf.leitor_lote import ler_lote
from modulos.conferencia_nf.modelos import ErroLeitura, FalhaLeitura, Fato, Lancamento, Resultado, Situacao

Progresso = Callable[[str, float | None], None]


# ---------------------------------------------------------------------------
# Chave: fornecedor + produto
# ---------------------------------------------------------------------------


def normalizar_produto(texto: str) -> str:
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", texto)
                         if not unicodedata.combining(c))
    return " ".join(sem_acento.upper().split())[:cfg.GABARITO_TAMANHO_PRODUTO]


def produto_do_complemento(complemento: str) -> str:
    """'Fornecedor ... NF. 935 - Filtro de Agua  DT 01/10/2026 PR ...' -> 'FILTRO DE AGUA'."""
    achado = cfg.RE_PRODUTO.search(complemento)
    return normalizar_produto(achado.group(1)) if achado else ""


def fornecedor_do_fato(fato: Fato) -> tuple[str, str] | None:
    """(conta, nome) do fornecedor: o único crédito em conta de fornecedores. None se o fato não
    tiver exatamente um (recibo, doação, fato com dois fornecedores): não aprende nem confere."""
    creditos = {(l.conta_credito, l.nome_conta) for l in fato.lancamentos
                if l.conta_credito and l.classificacao.startswith(cfg.CLASSIFICACAO_FORNECEDORES)}
    return creditos.pop() if len(creditos) == 1 else None


def lancamentos_do_gabarito(fato: Fato) -> list[Lancamento]:
    """Os débitos em conta de produto/serviço (estoque, imobilizado, custo, despesa, receita)."""
    return [l for l in fato.lancamentos
            if l.conta_debito and l.classificacao.startswith(cfg.CLASSIFICACOES_GABARITO)]


def _data(texto: str) -> date | None:
    try:
        return datetime.strptime(texto.strip()[:10], "%d/%m/%Y").date()
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# A memória
# ---------------------------------------------------------------------------


@dataclass
class Conta:
    codigo: str
    classificacao: str
    nome: str

    @property
    def texto(self) -> str:
        return f"{self.classificacao} {self.nome} ({self.codigo})".strip()


@dataclass
class ItemHistorico:
    fornecedor: str
    nome_fornecedor: str
    produto: str
    conta: Conta
    vezes: int = 0
    primeira: date | None = None
    ultima: date | None = None
    exemplo: str = ""

    def contar(self, data: date | None, complemento: str):
        self.vezes += 1
        if data and (self.primeira is None or data < self.primeira):
            self.primeira = data
        if data and (self.ultima is None or data > self.ultima):
            self.ultima = data
        self.exemplo = self.exemplo or complemento


@dataclass
class Padrao:
    fornecedor: str
    produto: str               # vazio = vale para qualquer produto do fornecedor
    conta: str                 # código reduzido
    texto_conta: str = ""      # classificação e nome, como a chefia escreveu
    decidido_por: str = ""


@dataclass
class Gabarito:
    caminho: Path
    historico: dict[tuple[str, str, str], ItemHistorico] = field(default_factory=dict)
    padroes: dict[tuple[str, str], Padrao] = field(default_factory=dict)
    fatos_aprendidos: dict[str, tuple[str, str, str]] = field(default_factory=dict)

    def contas_de(self, fornecedor: str, produto: str) -> list[ItemHistorico]:
        itens = [i for (f, p, _), i in self.historico.items() if (f, p) == (fornecedor, produto)]
        return sorted(itens, key=lambda i: -i.vezes)

    def conhece_fornecedor(self, fornecedor: str) -> bool:
        return any(f == fornecedor for f, _, _ in self.historico)

    def vezes_na_conta(self, fornecedor: str, conta: str) -> int:
        """Quantas vezes o fornecedor foi lançado nesta conta, com qualquer produto."""
        return sum(i.vezes for (f, _, c), i in self.historico.items()
                   if (f, c) == (fornecedor, conta))

    def conta_mais_usada(self, fornecedor: str) -> Conta:
        por_conta: dict[str, list[ItemHistorico]] = {}
        for (f, _, c), item in self.historico.items():
            if f == fornecedor:
                por_conta.setdefault(c, []).append(item)
        itens = max(por_conta.values(), key=lambda itens: sum(i.vezes for i in itens))
        return itens[0].conta

    def padrao_de(self, fornecedor: str, produto: str) -> Padrao | None:
        return self.padroes.get((fornecedor, produto)) or self.padroes.get((fornecedor, ""))


def caminho_gabarito(pasta: Path) -> Path:
    return Path(pasta) / cfg.GABARITO_ARQUIVO


def _texto(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return str(valor).strip()


def _linhas(aba) -> list[dict]:
    titulos = [_texto(c.value) for c in aba[1]]
    return [dict(zip(titulos, linha)) for linha in aba.iter_rows(min_row=2, values_only=True)
            if any(v not in (None, "") for v in linha)]


def abrir_gabarito(pasta: Path) -> Gabarito:
    """Lê a planilha do gabarito. Pasta sem planilha = gabarito vazio (criado ao ensinar).
    Levanta ErroLeitura se a planilha existir e não puder ser lida."""
    caminho = caminho_gabarito(pasta)
    gabarito = Gabarito(caminho)
    if not caminho.exists():
        return gabarito
    try:
        livro = openpyxl.load_workbook(caminho, data_only=True)
    except Exception:
        raise ErroLeitura(f"Não foi possível abrir {caminho.name} (está protegida com senha para "
                          "abrir, estragada ou não é uma planilha). Só a senha de editar uma aba "
                          "(Proteger Planilha) é aceita.") from None
    for aba, titulos in cfg.GABARITO_ABAS.items():
        if aba not in livro.sheetnames:
            raise ErroLeitura(f"{caminho.name}: falta a aba \"{aba}\".")
        faltando = [t for t in titulos if t not in [_texto(c.value) for c in livro[aba][1]]]
        if faltando:
            raise ErroLeitura(f"{caminho.name}, aba \"{aba}\": faltam as colunas "
                              + ", ".join(faltando) + ".")
    for l in _linhas(livro[cfg.GABARITO_ABA_HISTORICO]):
        conta = Conta(_texto(l["Conta"]), _texto(l["Classificação"]), _texto(l["Nome da conta"]))
        item = ItemHistorico(_texto(l["Fornecedor (conta)"]), _texto(l["Nome do fornecedor"]),
                             _texto(l["Produto"]), conta, int(l["Vezes"] or 0),
                             _data(_texto(l["Primeira vez"])), _data(_texto(l["Última vez"])),
                             _texto(l["Exemplo de complemento"]))
        gabarito.historico[(item.fornecedor, item.produto, conta.codigo)] = item
    for l in _linhas(livro[cfg.GABARITO_ABA_PADRAO]):
        conta = _texto(l["Conta padrão (código)"])
        if not conta:
            continue
        produto = normalizar_produto(_texto(l["Produto"]))
        if produto == normalizar_produto(cfg.SEM_PRODUTO):
            produto = ""                       # copiado da aba "Para padronizar"
        padrao = Padrao(_texto(l["Fornecedor (conta)"]), produto,
                        conta, _texto(l["Classificação e nome"]), _texto(l["Decidido por"]))
        gabarito.padroes[(padrao.fornecedor, padrao.produto)] = padrao
    for l in _linhas(livro[cfg.GABARITO_ABA_FATOS]):
        gabarito.fatos_aprendidos[_texto(l["Fato contábil"])] = (
            _texto(l["Data"]), _texto(l["Arquivo"]), _texto(l["Aprendido em"]))
    return gabarito


# ---------------------------------------------------------------------------
# Ensinar
# ---------------------------------------------------------------------------


@dataclass
class ResultadoEnsino:
    pasta: Path
    caminho: Path | None = None
    arquivos_lidos: int = 0
    fatos_novos: int = 0
    fatos_ja_aprendidos: int = 0
    fatos_sem_fornecedor: int = 0
    lancamentos: int = 0
    falhas: list[FalhaLeitura] = field(default_factory=list)
    erro: str = ""             # a planilha não pôde ser aberta ou gravada: nada foi aprendido


def ensinar(pasta: Path, arquivos: list[Path], progresso: Progresso | None = None,
            agora: datetime | None = None) -> ResultadoEnsino:
    """Aprende com os arquivos de Movimento contábil (já revisados) e grava a planilha.
    Um arquivo com problema vira falha e os outros continuam. Estornos (F6) não são aprendidos."""
    agora = agora or datetime.now()
    resultado = ResultadoEnsino(Path(pasta))
    try:
        gabarito = abrir_gabarito(pasta)
    except ErroLeitura as erro:
        resultado.erro = str(erro)
        return resultado
    for posicao, arquivo in enumerate(arquivos, start=1):
        if progresso:
            progresso(f"Aprendendo... arquivo {posicao} de {len(arquivos)}",
                      (posicao - 1) / max(len(arquivos), 1))
        try:
            fatos = ler_lote(arquivo)
        except ErroLeitura as erro:
            resultado.falhas.append(FalhaLeitura(Path(arquivo).name, str(erro)))
            continue
        resultado.arquivos_lidos += 1
        anulados, _ = separar_estornos(fatos)
        for fato in fatos:
            if fato.fato in gabarito.fatos_aprendidos:
                resultado.fatos_ja_aprendidos += 1
                continue
            if fato.fato in anulados:
                continue
            fornecedor = fornecedor_do_fato(fato)
            if fornecedor is None:
                resultado.fatos_sem_fornecedor += 1
                continue
            resultado.fatos_novos += 1
            gabarito.fatos_aprendidos[fato.fato] = (fato.data_movimento, Path(arquivo).name,
                                                    agora.strftime("%d/%m/%Y %H:%M"))
            for l in lancamentos_do_gabarito(fato):
                produto = produto_do_complemento(l.complemento)
                chave = (fornecedor[0], produto, l.conta_debito)
                item = gabarito.historico.get(chave)
                if item is None:
                    item = gabarito.historico[chave] = ItemHistorico(
                        fornecedor[0], fornecedor[1], produto,
                        Conta(l.conta_debito, l.classificacao, l.nome_conta))
                item.contar(_data(fato.data_movimento), l.complemento)
                resultado.lancamentos += 1
    if progresso:
        progresso("Gravando o gabarito...", None)
    try:
        resultado.caminho = gravar_gabarito(gabarito, agora)
    except OSError as erro:
        resultado.erro = str(erro)
    return resultado


# ---------------------------------------------------------------------------
# Gravar a planilha (a aba "Padrão" nunca é alterada)
# ---------------------------------------------------------------------------

_NEGRITO_BRANCO = Font(bold=True, color=cfg.COR_FONTE_TITULO)
_FUNDO_TITULO = PatternFill("solid", fgColor=cfg.COR_FUNDO_TITULO)


def _formatar_data(d: date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else ""


def _reescrever(livro, nome: str, linhas: list[list], larguras: list[int]):
    """Apaga e reescreve o conteúdo da aba (cria se não existir), com o título formatado."""
    titulos = cfg.GABARITO_ABAS[nome]
    aba = livro[nome] if nome in livro.sheetnames else livro.create_sheet(nome)
    if aba.max_row:
        aba.delete_rows(1, aba.max_row)
    aba.append(list(titulos))
    for linha in linhas:
        aba.append(linha)
    for coluna, largura in enumerate(larguras, start=1):
        aba.column_dimensions[get_column_letter(coluna)].width = largura
        aba.cell(row=1, column=coluna).font = _NEGRITO_BRANCO
        aba.cell(row=1, column=coluna).fill = _FUNDO_TITULO
    aba.freeze_panes = "A2"
    aba.auto_filter.ref = aba.dimensions
    return aba


def para_padronizar(gabarito: Gabarito) -> list[list]:
    """Fornecedor + produto lançado em mais de uma conta, com o % de cada e a sugestão."""
    grupos: dict[tuple[str, str], list[ItemHistorico]] = {}
    for item in gabarito.historico.values():
        grupos.setdefault((item.fornecedor, item.produto), []).append(item)
    linhas = []
    for (fornecedor, produto), itens in sorted(
            grupos.items(), key=lambda g: (-sum(i.vezes for i in g[1]), g[0])):
        if len(itens) < 2:
            continue
        total = sum(i.vezes for i in itens)
        padrao = gabarito.padrao_de(fornecedor, produto)
        for posicao, item in enumerate(sorted(itens, key=lambda i: -i.vezes)):
            linhas.append([item.fornecedor, item.nome_fornecedor, item.produto or cfg.SEM_PRODUTO,
                           item.conta.codigo, item.conta.classificacao, item.conta.nome,
                           item.vezes, round(item.vezes / total, 4),
                           _formatar_data(item.ultima),
                           cfg.GABARITO_SUGESTAO if posicao == 0 else "",
                           f"SIM ({padrao.conta})" if padrao else ""])
    return linhas


def gravar_gabarito(gabarito: Gabarito, agora: datetime | None = None) -> Path:
    """Grava as abas do programa e preserva a "Padrão" (e a senha dela). Guarda antes uma cópia de
    segurança. Levanta OSError com a explicação se não conseguir (ex.: aberta no Excel)."""
    agora = agora or datetime.now()
    caminho = gabarito.caminho
    caminho.parent.mkdir(parents=True, exist_ok=True)
    if caminho.exists():
        _copia_de_seguranca(caminho, agora)
        livro = openpyxl.load_workbook(caminho)
    else:
        livro = openpyxl.Workbook()
        livro.active.title = cfg.GABARITO_ABA_PADRAO
        _reescrever(livro, cfg.GABARITO_ABA_PADRAO, [], [16, 40, 40, 20, 50, 25, 12, 50])
    historico = sorted(gabarito.historico.values(),
                       key=lambda i: (i.nome_fornecedor.upper(), i.produto, -i.vezes))
    _reescrever(livro, cfg.GABARITO_ABA_HISTORICO, [
        [i.fornecedor, i.nome_fornecedor, i.produto, i.conta.codigo, i.conta.classificacao,
         i.conta.nome, i.vezes, _formatar_data(i.primeira), _formatar_data(i.ultima), i.exemplo]
        for i in historico], [16, 40, 40, 10, 18, 40, 8, 13, 13, 90])
    aba = _reescrever(livro, cfg.GABARITO_ABA_PADRONIZAR, para_padronizar(gabarito),
                      [16, 40, 40, 10, 18, 40, 8, 9, 13, 14, 16])
    for (celula,) in aba.iter_rows(min_row=2, min_col=8, max_col=8):
        celula.number_format = "0.0%"
    _reescrever(livro, cfg.GABARITO_ABA_FATOS, [
        [fato, *dados] for fato, dados in sorted(gabarito.fatos_aprendidos.items())],
        [14, 13, 50, 18])
    descritor, temporario = tempfile.mkstemp(suffix=".xlsx", prefix="~gabarito_",
                                             dir=caminho.parent)
    os.close(descritor)
    try:
        livro.save(temporario)
        os.replace(temporario, caminho)
    except PermissionError:
        raise OSError(f"{caminho.name}: não foi possível gravar. Feche a planilha no Excel (ou "
                      "peça para quem estiver com ela aberta fechar) e tente de novo.") from None
    finally:
        if os.path.exists(temporario):
            os.remove(temporario)
    return caminho


def _copia_de_seguranca(caminho: Path, agora: datetime):
    """Cópia com data e hora antes de cada gravação; guarda as últimas GABARITO_COPIAS."""
    pasta = caminho.parent / cfg.GABARITO_PASTA_COPIAS
    pasta.mkdir(exist_ok=True)
    nome = f"{caminho.stem}_{agora:%Y-%m-%d_%H%M%S}"
    copia, numero = pasta / f"{nome}{caminho.suffix}", 2
    while copia.exists():                       # duas gravações no mesmo segundo
        copia, numero = pasta / f"{nome}_{numero}{caminho.suffix}", numero + 1
    shutil.copy2(caminho, copia)
    copias = sorted(pasta.glob(f"{caminho.stem}_*{caminho.suffix}"))
    for antiga in copias[:-cfg.GABARITO_COPIAS]:
        antiga.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Conferir
# ---------------------------------------------------------------------------


@dataclass
class AvaliacaoConta:
    """S14: o que o gabarito diz de um lançamento (só informativo)."""

    lancamento: Lancamento
    produto: str
    resultado: str             # um dos cfg.GABARITO_*
    detalhe: str = ""

    @property
    def confere(self) -> bool:
        return self.resultado in (cfg.GABARITO_IGUAL_PADRAO, cfg.GABARITO_IGUAL_HISTORICO)


def avaliar(gabarito: Gabarito, fato: Fato) -> list[AvaliacaoConta]:
    fornecedor = fornecedor_do_fato(fato)
    if fornecedor is None:
        return []
    avaliacoes = []
    for l in lancamentos_do_gabarito(fato):
        produto = produto_do_complemento(l.complemento)
        padrao = gabarito.padrao_de(fornecedor[0], produto)
        if padrao:
            if padrao.conta == l.conta_debito:
                avaliacoes.append(AvaliacaoConta(l, produto, cfg.GABARITO_IGUAL_PADRAO))
            else:
                avaliacoes.append(AvaliacaoConta(
                    l, produto, cfg.GABARITO_FORA_PADRAO,
                    f"Padrão: {padrao.texto_conta or padrao.conta}"
                    + (f" (decidido por {padrao.decidido_por})" if padrao.decidido_por else "")))
            continue
        itens = gabarito.contas_de(fornecedor[0], produto)
        total = sum(i.vezes for i in itens)
        mesma = next((i for i in itens if i.conta.codigo == l.conta_debito), None)
        if mesma:
            avaliacoes.append(AvaliacaoConta(l, produto, cfg.GABARITO_IGUAL_HISTORICO,
                                             f"{mesma.vezes} de {total} vezes nesta conta"))
        elif itens:
            habitual = itens[0]
            avaliacoes.append(AvaliacaoConta(
                l, produto, cfg.GABARITO_DIFERENTE,
                f"Habitual: {habitual.conta.texto}, {habitual.vezes} de {total} vezes"))
        elif gabarito.conhece_fornecedor(fornecedor[0]):
            vezes = gabarito.vezes_na_conta(fornecedor[0], l.conta_debito)
            detalhe = (f"Produto sem histórico; o fornecedor já usou esta conta {vezes} vez(es)"
                       if vezes else "Produto sem histórico e conta que o fornecedor nunca usou "
                       f"(usa: {gabarito.conta_mais_usada(fornecedor[0]).texto})")
            avaliacoes.append(AvaliacaoConta(l, produto, cfg.GABARITO_PRODUTO_NOVO, detalhe))
        else:
            avaliacoes.append(AvaliacaoConta(l, produto, cfg.GABARITO_FORNECEDOR_NOVO,
                                             "Fornecedor ainda sem histórico"))
    return avaliacoes


def conferir_contas(resultados: list[Resultado], gabarito: Gabarito) -> None:
    """Preenche r.contas de cada fato (menos os estornos). Não muda a situação."""
    for r in resultados:
        r.contas = [] if r.situacao == Situacao.ESTORNO else avaliar(gabarito, r.fato)
