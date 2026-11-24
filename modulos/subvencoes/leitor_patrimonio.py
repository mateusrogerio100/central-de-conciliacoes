"""Leitura do relatório "Patrimônio - Bens Subvenção".

Tipos de linha reconhecidos (o relatório se repete por página):
- título do relatório, "Data: 01/MM/AA à ...", rodapé "Impresso em:" -> controle/ignorados;
- linha de títulos com "Valor Contábil" -> define a coluna de valor DAQUELA página (P1);
- "Total(n)"            -> total geral do relatório;
- "Total - <conta>(n)"  -> fecha a conta;
- linha que começa com um número (Cód Bem) -> item (bem);
- linha com uma única célula de texto -> cabeçalho de conta;
- qualquer outra coisa  -> "linha não reconhecida" (ERRO). Nada é adivinhado.

Regras de montagem das contas (seção 2.2 da especificação):
- itens acumulam numa lista "pendente";
- um cabeçalho abre uma conta nova (a conta aberta anterior, sem linha Total, fica com os
  pendentes: caso P2, conta de um bem só);
- uma linha Total fecha a conta: mesmo nome da conta aberta -> confirma; nome diferente ou
  nenhuma conta aberta -> cria a conta com o nome do Total e dá a ela os pendentes (P4);
- o saldo da conta é SEMPRE a soma dos itens; a linha Total só serve para conferência (P3).
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from modulos.subvencoes import configuracao
from modulos.subvencoes.modelos import (
    Aviso,
    ContaPatrimonio,
    ErroArquivo,
    Gravidade,
    ItemPatrimonio,
    RelatorioPatrimonio,
)
from modulos.subvencoes.utilitarios import (
    abrir_relatorio_tasy,
    mes_de_texto,
    normalizar_texto,
    para_decimal,
    para_inteiro,
    texto_comeca_com,
    texto_igual,
)


def _padrao_prefixo(prefixo: str) -> str:
    """Transforma um prefixo da configuração em regex tolerante a espaços: "Total - " -> Total\\s*-\\s*"""
    return r"\s*".join(re.escape(parte) for parte in prefixo.split()) + r"\s*"


_PADRAO_TOTAL_CONTA = re.compile(
    r"^\s*" + _padrao_prefixo(configuracao.PATRIMONIO_PREFIXO_TOTAL_CONTA) + r"(.*?)\s*\((\d+)\)\s*$",
    re.IGNORECASE,
)
_PADRAO_TOTAL_GERAL = re.compile(
    r"^\s*" + re.escape(configuracao.PATRIMONIO_PREFIXO_TOTAL_GERAL.rstrip("(")) + r"\s*\((\d+)\)\s*$",
    re.IGNORECASE,
)
_PADRAO_DATA = re.compile(r"\d{1,2}/\d{1,2}/\d{2,4}")


def ler_patrimonio(caminho) -> RelatorioPatrimonio:
    caminho = Path(caminho)
    pasta_trabalho = abrir_relatorio_tasy(caminho)
    try:
        aba = _localizar_aba(pasta_trabalho)
        if aba is None:
            raise ErroArquivo(
                f"{caminho.name}: não parece ser o relatório de patrimônio "
                f"(título '{configuracao.PATRIMONIO_TITULO_VALOR_CONTABIL}' não encontrado)."
            )
        return _LeitorPatrimonio(aba, caminho.name).ler()
    finally:
        pasta_trabalho.close()


def _localizar_aba(pasta_trabalho):
    for aba in pasta_trabalho.worksheets:
        for linha in aba.iter_rows(values_only=True):
            if any(texto_igual(v, configuracao.PATRIMONIO_TITULO_VALOR_CONTABIL) for v in linha):
                return aba
    return None


class _LeitorPatrimonio:
    def __init__(self, aba, nome_arquivo: str):
        self.aba = aba
        self.relatorio = RelatorioPatrimonio(arquivo=nome_arquivo, mes_referencia=None)
        self.coluna_valor: int | None = None
        self.conta_aberta: ContaPatrimonio | None = None
        self.pendentes: list[ItemPatrimonio] = []
        self.linha_total_geral: int | None = None

    # -- avisos --------------------------------------------------------------

    def avisar(self, gravidade, tipo, mensagem, linha=None, conta=""):
        self.relatorio.avisos.append(Aviso(
            gravidade, tipo, mensagem,
            arquivo=self.relatorio.arquivo, aba=self.aba.title, linha=linha, conta=conta,
        ))

    def nao_reconhecida(self, numero_linha, motivo):
        self.relatorio.linhas_nao_reconhecidas.append(numero_linha)
        self.avisar(Gravidade.ERRO, "linha não reconhecida", motivo, numero_linha)

    # -- leitura -------------------------------------------------------------

    def ler(self) -> RelatorioPatrimonio:
        for linha_celulas in self.aba.iter_rows():
            celulas = {c.column: c.value for c in linha_celulas
                       if c.value is not None and not (isinstance(c.value, str) and not c.value.strip())}
            if celulas:
                self.ler_linha(celulas, linha_celulas[0].row)
        self.finalizar()
        return self.relatorio

    def ler_linha(self, celulas: dict[int, object], numero_linha: int):
        colunas = sorted(celulas)
        primeira = celulas[colunas[0]]

        if texto_comeca_com(primeira, configuracao.RODAPE_IMPRESSO_EM):
            return
        if texto_igual(primeira, configuracao.PATRIMONIO_TITULO_RELATORIO):
            return
        if texto_comeca_com(primeira, configuracao.PATRIMONIO_ROTULO_DATA):
            self.ler_data(primeira, numero_linha)
            return

        coluna_titulo = next((c for c in colunas
                              if texto_igual(celulas[c], configuracao.PATRIMONIO_TITULO_VALOR_CONTABIL)), None)
        if coluna_titulo is not None:
            self.coluna_valor = coluna_titulo
            return

        if isinstance(primeira, str):
            total_geral = _PADRAO_TOTAL_GERAL.match(primeira)
            if total_geral:
                self.ler_total_geral(celulas, int(total_geral.group(1)), numero_linha)
                return
            total_conta = _PADRAO_TOTAL_CONTA.match(primeira)
            if total_conta:
                self.ler_total_conta(celulas, total_conta.group(1).strip(), int(total_conta.group(2)),
                                     numero_linha)
                return
            if len(celulas) == 1:
                self.abrir_conta(primeira.strip(), numero_linha)
                return
            self.nao_reconhecida(numero_linha, f"Formato de linha desconhecido: {primeira!r}.")
            return

        if para_inteiro(primeira) is not None:
            self.ler_item(celulas, colunas, numero_linha)
            return

        self.nao_reconhecida(numero_linha, f"Formato de linha desconhecido: {primeira!r}.")

    def ler_data(self, texto: str, numero_linha: int):
        encontrado = _PADRAO_DATA.search(texto)
        mes = mes_de_texto(encontrado.group(0)) if encontrado else None
        if mes is None:
            self.avisar(Gravidade.ATENCAO, "mês não reconhecido",
                        f"Não foi possível ler o mês de referência: {texto!r}.", numero_linha)
        elif self.relatorio.mes_referencia is None:
            self.relatorio.mes_referencia = mes
        elif mes != self.relatorio.mes_referencia:
            self.avisar(Gravidade.ATENCAO, "mês diferente entre páginas",
                        f"Página com mês {mes}, diferente do mês {self.relatorio.mes_referencia} "
                        "da primeira página. Vale o da primeira página.", numero_linha)

    def ler_item(self, celulas, colunas, numero_linha):
        if self.coluna_valor is None:
            self.nao_reconhecida(numero_linha, "Bem antes da linha de títulos; coluna de valor desconhecida.")
            return
        valor = para_decimal(celulas.get(self.coluna_valor))
        if valor is None:
            self.nao_reconhecida(
                numero_linha,
                f"Bem sem número na coluna '{configuracao.PATRIMONIO_TITULO_VALOR_CONTABIL}' desta página; "
                "o valor não foi adivinhado.",
            )
            return
        codigo = celulas[colunas[0]]
        descricao = next((str(celulas[c]).strip() for c in colunas[1:] if isinstance(celulas[c], str)), "")
        self.pendentes.append(ItemPatrimonio(
            codigo_bem=str(para_inteiro(codigo)), descricao=descricao, valor=valor, linha=numero_linha,
        ))

    def valor_do_total(self, celulas) -> Decimal | None:
        """Número na coluna "Valor Contábil" da página; se vazio, o primeiro número da linha."""
        if self.coluna_valor is not None:
            valor = para_decimal(celulas.get(self.coluna_valor))
            if valor is not None:
                return valor
        for coluna in sorted(celulas):
            if not isinstance(celulas[coluna], str):
                valor = para_decimal(celulas[coluna])
                if valor is not None:
                    return valor
        return None

    # -- montagem das contas -------------------------------------------------

    def abrir_conta(self, nome: str, numero_linha: int):
        if self.conta_aberta is not None:
            self.fechar_conta_aberta()
        elif self.pendentes:
            self.guardar_itens_sem_conta(f"antes do cabeçalho '{nome}'")
        self.conta_aberta = ContaPatrimonio(nome=nome, linha_cabecalho=numero_linha)

    def fechar_conta_aberta(self):
        """Fecha a conta aberta sem linha Total (P2): ela fica com os itens pendentes."""
        conta = self.conta_aberta
        conta.itens.extend(self.pendentes)
        self.pendentes = []
        self.registrar_conta(conta)
        self.conta_aberta = None

    def ler_total_conta(self, celulas, nome: str, quantidade: int, numero_linha: int):
        conta = self.conta_aberta
        if conta is None or normalizar_texto(conta.nome) != normalizar_texto(nome):
            if conta is not None:
                # Conta aberta sem Total, seguida de itens sem cabeçalho: os pendentes vão para o Total.
                self.registrar_conta(conta)
                self.avisar(Gravidade.ATENCAO, "cabeçalho ausente",
                            f"A conta aberta '{conta.nome}' foi encerrada sem itens porque a linha Total "
                            f"seguinte é de outra conta ('{nome}').", numero_linha, conta.nome)
            conta = ContaPatrimonio(nome=nome, cabecalho_ausente=True)
            self.avisar(Gravidade.ATENCAO, "cabeçalho ausente",
                        f"Conta sem linha de cabeçalho; identificada pela linha Total. "
                        f"{len(self.pendentes)} bem(ns) atribuído(s) a ela.", numero_linha, nome)

        conta.itens.extend(self.pendentes)
        self.pendentes = []
        conta.total_sistema = self.valor_do_total(celulas)
        conta.quantidade_sistema = quantidade
        conta.linha_total = numero_linha
        self.registrar_conta(conta)
        self.conta_aberta = None

    def ler_total_geral(self, celulas, quantidade: int, numero_linha: int):
        if self.conta_aberta is not None:
            self.fechar_conta_aberta()
        elif self.pendentes:
            self.guardar_itens_sem_conta("antes do total geral")
        if self.linha_total_geral is not None:
            self.avisar(Gravidade.ATENCAO, "total geral repetido",
                        f"Linha de total geral repetida (a primeira está na linha {self.linha_total_geral}); "
                        "vale a última.", numero_linha)
        self.linha_total_geral = numero_linha
        self.relatorio.total_geral_sistema = self.valor_do_total(celulas)
        self.relatorio.quantidade_geral_sistema = quantidade

    def guardar_itens_sem_conta(self, onde: str):
        itens = self.pendentes
        self.pendentes = []
        self.relatorio.itens_sem_conta.extend(itens)
        linhas = ", ".join(str(i.linha) for i in itens)
        self.avisar(Gravidade.ATENCAO, "itens sem conta",
                    f"{len(itens)} bem(ns) sem conta {onde} (linhas {linhas}); não entram em nenhuma conta.",
                    itens[0].linha)

    def registrar_conta(self, conta: ContaPatrimonio):
        self.relatorio.contas.append(conta)

    def avisar_contas_repetidas(self):
        """Nome repetido: um aviso por nome, com as linhas de cada bloco (a conciliação soma os blocos)."""
        blocos: dict[str, list[ContaPatrimonio]] = {}
        for conta in self.relatorio.contas:
            blocos.setdefault(normalizar_texto(conta.nome), []).append(conta)
        for repetidas in blocos.values():
            if len(repetidas) < 2:
                continue
            descricoes = "; ".join(f"linhas {_faixa_de_linhas(c)} ({c.soma_itens})" for c in repetidas)
            self.avisar(Gravidade.ATENCAO, "conta repetida no patrimônio",
                        f"A conta '{repetidas[0].nome}' aparece em {len(repetidas)} blocos do relatório: "
                        f"{descricoes}. O Saldo Patrimônio usa a soma dos blocos.",
                        _primeira_linha(repetidas[0]), repetidas[0].nome)

    # -- conferências --------------------------------------------------------

    def finalizar(self):
        if self.conta_aberta is not None:
            self.fechar_conta_aberta()
        elif self.pendentes:
            self.guardar_itens_sem_conta("no fim do relatório")

        self.avisar_contas_repetidas()

        if self.relatorio.mes_referencia is None:
            self.avisar(Gravidade.ATENCAO, "mês não encontrado",
                        f"'{configuracao.PATRIMONIO_ROTULO_DATA}' não encontrado no relatório de patrimônio.")

        for conta in self.relatorio.contas:
            linha = conta.linha_total or conta.linha_cabecalho
            if conta.total_divergente:
                self.avisar(Gravidade.ATENCAO, "total do sistema divergente",
                            f"Soma dos bens = {conta.soma_itens}, mas a linha Total do sistema mostra "
                            f"{conta.total_sistema}. Vale a soma dos bens.", linha, conta.nome)
            if conta.quantidade_divergente:
                self.avisar(Gravidade.ATENCAO, "quantidade divergente",
                            f"{len(conta.itens)} bem(ns) lido(s), mas a linha Total indica "
                            f"{conta.quantidade_sistema}.", linha, conta.nome)

        relatorio = self.relatorio
        if relatorio.total_geral_sistema is None:
            self.avisar(Gravidade.ERRO, "total geral não confere",
                        "Linha de total geral 'Total(...)' não encontrada; não foi possível conferir "
                        f"a soma dos bens ({relatorio.soma_itens}).")
        else:
            if not relatorio.total_geral_confere:
                self.avisar(Gravidade.ERRO, "total geral não confere",
                            f"Soma de todos os bens lidos = {relatorio.soma_itens}, mas o total geral do "
                            f"relatório é {relatorio.total_geral_sistema}. Algum bem pode ter sido perdido "
                            "ou lido errado.", self.linha_total_geral)
            if relatorio.quantidade_geral_sistema != relatorio.quantidade_itens:
                self.avisar(Gravidade.ERRO, "total geral não confere",
                            f"{relatorio.quantidade_itens} bem(ns) lido(s) nas contas, mas o total geral "
                            f"indica {relatorio.quantidade_geral_sistema}.", self.linha_total_geral)


def _linhas_do_bloco(conta: ContaPatrimonio) -> list[int]:
    """Linhas do bloco da conta no relatório: cabeçalho, bens e Total."""
    linhas = [conta.linha_cabecalho, *(i.linha for i in conta.itens), conta.linha_total]
    return [l for l in linhas if l is not None]


def _primeira_linha(conta: ContaPatrimonio) -> int | None:
    return min(_linhas_do_bloco(conta), default=None)


def _faixa_de_linhas(conta: ContaPatrimonio) -> str:
    """Ex.: "1090 a 1093"."""
    linhas = _linhas_do_bloco(conta)
    if not linhas:
        return "?"
    return str(min(linhas)) if min(linhas) == max(linhas) else f"{min(linhas)} a {max(linhas)}"
