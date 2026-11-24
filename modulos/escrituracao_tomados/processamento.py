"""Orquestra a geração completa. É o único módulo que a tela chama (seção 7 da especificação).

Ordem: PDFs -> exportações -> resultados da prefeitura -> cadastro de prestadores ->
duplicidades (R13) -> regras -> cidade dos prestadores que faltam (R11) -> regras de novo ->
arquivos .txt (R4, R17) -> conferências (R16) -> relatório Excel (seção 6).

Nunca levanta exceção por problema em arquivo ou nota: tudo vai para o resultado e o relatório.
Levanta ValueError só se a própria chamada estiver incompleta (a tela valida antes).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Callable

from modulos.escrituracao_tomados import (
    cadastro_prestadores, conferencia, configuracao as cfg, gerador_txt, leitor_danfse,
    leitor_exportacao, regras,
)
from modulos.escrituracao_tomados.cadastro_prestadores import (
    CadastroPrestadores, ConsultaCnpj, PerguntaCidade,
)
from modulos.escrituracao_tomados.conferencia import chave_nota
from modulos.escrituracao_tomados.gerador_txt import so_digitos
from modulos.escrituracao_tomados.modelos import (
    Aviso, Competencia, Destino, ErroLayout, FalhaLeitura, GrupoArquivo, NotaTomada,
)
from modulos.escrituracao_tomados.relatorio import gerar_relatorio

Progresso = Callable[[str, float | None], None]
PerguntaSubstituir = Callable[[list[Path]], bool]

ZERO = Decimal("0.00")
ESCRITURAVEIS = (Destino.INCLUIDA, Destino.LANCAR_A_MAO)


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------


@dataclass
class ArquivoGerado:
    caminho: Path
    tomador_documento: str
    tomador_nome: str
    competencia: Competencia
    quantidade: int
    total_servicos: Decimal
    total_deducoes: Decimal
    total_iss: Decimal
    gravado: bool = True
    problema: str = ""


@dataclass
class Conferencia:
    """Uma linha de conferência automática (R16), para a tela e o relatório."""

    descricao: str
    ok: bool
    detalhe: str = ""


@dataclass
class ResultadoGeracao:
    pasta_saida: Path
    notas: list[NotaTomada] = field(default_factory=list)
    falhas: list[FalhaLeitura] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)
    arquivos: list[ArquivoGerado] = field(default_factory=list)
    conferencias: list[Conferencia] = field(default_factory=list)
    arquivo_txt_da_nota: dict[int, str] = field(default_factory=dict)   # id(nota) -> nome do .txt
    caminho_relatorio: Path | None = None
    erro_relatorio: str = ""
    cancelado: bool = False           # o usuário não quis substituir arquivos existentes

    # --- números do resumo (seção 8) ---

    def _contar(self, *destinos) -> int:
        return sum(1 for n in self.notas if n.destino in destinos)

    @property
    def notas_no_arquivo(self) -> int:
        return sum(a.quantidade for a in self.arquivos if a.gravado)

    @property
    def lancar_a_mao(self) -> int:
        return self._contar(Destino.LANCAR_A_MAO)

    @property
    def ja_escrituradas(self) -> int:
        return self._contar(Destino.JA_ESCRITURADA)

    @property
    def canceladas(self) -> int:
        return sum(1 for n in self.notas
                   if n.destino is Destino.NAO_INCLUIDA and n.motivo == "nota cancelada")

    @property
    def notas_com_numero_ajustado(self) -> list[NotaTomada]:
        """Notas que entraram no .txt com os 8 últimos dígitos (R8): corrigir o número no site."""
        return [n for n in self.notas if n.numero_arquivo and id(n) in self.arquivo_txt_da_nota]

    @property
    def falar_com_fornecedor(self) -> list[NotaTomada]:
        """Não Optante sem imposto federal retido (R19)."""
        return [n for n in self.notas if n.falar_com_fornecedor]

    @property
    def duplicadas(self) -> int:
        return self._contar(Destino.DUPLICADA)

    @property
    def erros_de_leitura(self) -> int:
        return sum(1 for f in self.falhas if f.origem in ("PDF", leitor_exportacao.ORIGEM))

    @property
    def nao_incluidas(self) -> int:
        """Tudo o que não está no arquivo nem em "lançar à mão"."""
        fora = self._contar(Destino.NAO_INCLUIDA, Destino.JA_ESCRITURADA, Destino.DUPLICADA)
        nao_gravadas = sum(a.quantidade for a in self.arquivos if not a.gravado)
        return fora + nao_gravadas + self.erros_de_leitura

    @property
    def tudo_certo(self) -> bool:
        return all(c.ok for c in self.conferencias)


# ---------------------------------------------------------------------------
# Consultas para a tela
# ---------------------------------------------------------------------------


def contar_pdfs(pasta) -> int:
    try:
        return len(leitor_danfse.listar_pdfs(Path(pasta)))
    except OSError:
        return 0


def interpretar_competencia(texto: str) -> Competencia | None:
    try:
        return leitor_exportacao.competencia_de_texto(texto)
    except Exception:
        return None


def interpretar_data(texto: str) -> date | None:
    try:
        return datetime.strptime((texto or "").strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def contar_notas_exportacoes(arquivos) -> tuple[int, int, int]:
    """(linhas de nota, arquivos lidos, arquivos que não abriram), para a confirmação da tela."""
    notas = lidos = falhas = 0
    for caminho in arquivos or []:
        try:
            notas += len(conferencia.ler_tabela_do_site(caminho, cfg.SITE_COLUNAS_EXPORTACAO))
            lidos += 1
        except Exception:
            falhas += 1
    return notas, lidos, falhas


def _caminho_tomadores() -> Path:
    return cadastro_prestadores.pasta_dados_usuario() / cfg.NOME_TOMADORES_USADOS


def tomadores_usados() -> list[str]:
    """CNPJs de tomador já informados nas exportações (R12), o mais recente primeiro."""
    try:
        dados = json.loads(_caminho_tomadores().read_text(encoding="utf-8"))
        return [so_digitos(c) for c in dados if len(so_digitos(str(c))) == 14]
    except (OSError, ValueError, TypeError):
        return []


def lembrar_tomador(cnpj: str) -> None:
    """Guarda o CNPJ no topo da lista. Falha ao gravar não é erro (é só uma comodidade)."""
    cnpj = so_digitos(cnpj)
    if len(cnpj) != 14:
        return
    lista = [cnpj] + [c for c in tomadores_usados() if c != cnpj]
    try:
        _caminho_tomadores().parent.mkdir(parents=True, exist_ok=True)
        _caminho_tomadores().write_text(json.dumps(lista[:20]), encoding="utf-8")
    except OSError:
        pass


def _caminho_outros_cnpjs() -> Path:
    return cadastro_prestadores.pasta_dados_usuario() / cfg.NOME_OUTROS_CNPJS_FUNDACAO


def cnpj_valido(cnpj: str) -> bool:
    """14 dígitos com os dígitos verificadores certos (pega erro de digitação)."""
    d = so_digitos(cnpj)
    if len(d) != 14 or len(set(d)) == 1:
        return False
    for posicao in (12, 13):
        pesos = list(range(posicao - 7, 1, -1)) + list(range(9, 1, -1))
        resto = sum(int(x) * p for x, p in zip(d, pesos)) % 11
        if int(d[posicao]) != (0 if resto < 2 else 11 - resto):
            return False
    return True


def outros_cnpjs_fundacao() -> list[str]:
    """CNPJs da Fundação de outra raiz que não a 98765432 (R1), informados na tela."""
    try:
        dados = json.loads(_caminho_outros_cnpjs().read_text(encoding="utf-8"))
        return [so_digitos(str(c)) for c in dados if cnpj_valido(str(c))]
    except (OSError, ValueError, TypeError):
        return []


def interpretar_outros_cnpjs(texto: str) -> tuple[list[str], list[str]]:
    """Texto da tela (um CNPJ por linha) -> (CNPJs válidos sem repetir, linhas com problema)."""
    cnpjs, problemas = [], []
    for linha in (texto or "").splitlines():
        if not linha.strip():
            continue
        cnpj = so_digitos(linha)
        if not cnpj_valido(cnpj):
            problemas.append(linha.strip())
        elif cnpj not in cnpjs:
            cnpjs.append(cnpj)
    return cnpjs, problemas


def salvar_outros_cnpjs_fundacao(cnpjs: list[str]) -> str:
    """Grava a lista. Devolve "" ou a mensagem do problema ao gravar."""
    try:
        _caminho_outros_cnpjs().parent.mkdir(parents=True, exist_ok=True)
        _caminho_outros_cnpjs().write_text(json.dumps([so_digitos(c) for c in cnpjs]),
                                           encoding="utf-8")
    except OSError as erro:
        return f"Não foi possível gravar a lista: {erro}"
    return ""


# ---------------------------------------------------------------------------
# Geração
# ---------------------------------------------------------------------------


def _sem_progresso(texto: str, fracao: float | None) -> None:
    """Usado quando ninguém acompanha o andamento (testes, linha de comando)."""


def _faixa(progresso: Progresso, inicio: float, fim: float) -> Progresso:
    """Converte o andamento 0..1 de uma etapa para a faixa dela no total."""
    def _parcial(texto, fracao):
        progresso(texto, None if fracao is None else inicio + (fim - inicio) * fracao)
    return _parcial


def _validar(pasta_pdfs, exportacoes, cnpj_tomador, competencia, tipo_referencia,
             data_lancamento, pasta_saida) -> None:
    if not pasta_pdfs and not exportacoes:
        raise ValueError("Escolha a pasta com os PDFs ou as exportações de lotes do site.")
    if exportacoes:
        if len(so_digitos(cnpj_tomador or "")) != 14:
            raise ValueError("Informe o CNPJ do tomador das exportações (14 dígitos).")
        if competencia is None:
            raise ValueError("Informe a competência das exportações (MM/AAAA).")
    if tipo_referencia not in cfg.TIPOS_REFERENCIA:
        raise ValueError("Escolha o tipo da declaração (Normal ou Complementar).")
    if not isinstance(data_lancamento, date):
        raise ValueError("Informe a data de lançamento (DD/MM/AAAA).")
    if not pasta_saida:
        raise ValueError("Escolha a pasta de saída.")


def gerar(pasta_pdfs=None, exportacoes=None, resultados=None, cnpj_tomador: str = "",
          competencia: Competencia | None = None, tipo_referencia: str = "C",
          data_lancamento: date | None = None, pasta_saida=None,
          perguntar_cidade: PerguntaCidade | None = None,
          progresso: Progresso | None = None,
          perguntar_substituir: PerguntaSubstituir | None = None,
          consultar_cnpj: ConsultaCnpj | None = cadastro_prestadores.consultar_cnpj_internet,
          caminho_cadastro=None, outros_cnpjs: list[str] | None = None) -> ResultadoGeracao:
    """Gera os .txt e o relatório em `pasta_saida`.

    - `cnpj_tomador` e `competencia`: das exportações (R12); obrigatórios quando houver
      exportações.
    - `outros_cnpjs`: CNPJs da Fundação de outra raiz (R1); sem ele, vale a lista gravada pela
      tela.
    - `perguntar_cidade(documento, nome) -> (cidade, uf) | None`: a tela pergunta (R11.4).
    - `perguntar_substituir(caminhos) -> bool`: chamada se algum .txt já existir (R17). Sem
      ela, os arquivos existentes não são substituídos (resultado.cancelado).
    - `consultar_cnpj` e `caminho_cadastro`: trocáveis nos testes.
    """
    _validar(pasta_pdfs, exportacoes, cnpj_tomador, competencia, tipo_referencia,
             data_lancamento, pasta_saida)
    progresso = progresso or _sem_progresso
    if outros_cnpjs is None:
        outros_cnpjs = outros_cnpjs_fundacao()
    resultado = ResultadoGeracao(pasta_saida=Path(pasta_saida))

    # 1. leitura
    notas_pdf: list[NotaTomada] = []
    if pasta_pdfs:
        notas_pdf, falhas = leitor_danfse.ler_pasta(Path(pasta_pdfs), _faixa(progresso, 0, 0.6))
        _registrar_falhas(resultado, falhas, "PDF")
    progresso("Lendo as exportações de lotes...", 0.6)
    notas_exportacao, falhas = leitor_exportacao.ler_exportacoes(exportacoes, cnpj_tomador,
                                                                 competencia)
    _registrar_falhas(resultado, falhas, leitor_exportacao.ORIGEM)
    if exportacoes:
        lembrar_tomador(cnpj_tomador)
    progresso("Lendo os resultados da prefeitura...", 0.65)
    escrituradas = conferencia.ler_resultados(resultados) if resultados else None
    if escrituradas:
        _registrar_falhas(resultado, escrituradas.falhas, "Resultado")
    resultado.notas = notas_pdf + notas_exportacao

    # 2. regras e cidade dos prestadores
    progresso("Aplicando as regras...", 0.7)
    cadastro = CadastroPrestadores(caminho_cadastro)
    if cadastro.problema_ao_abrir:
        resultado.avisos.append(Aviso("Cadastro de prestadores", cadastro.problema_ao_abrir))
    cadastro_prestadores.aprender_dos_pdfs(resultado.notas, cadastro)
    resultado.avisos += regras.resolver_duplicidades(resultado.notas)
    regras.classificar(resultado.notas, escrituradas, outros_cnpjs)
    sem_cidade = [n for n in resultado.notas
                  if n.destino in ESCRITURAVEIS and not (n.prestador_cidade and n.prestador_uf)]
    if sem_cidade:
        progresso("Procurando a cidade dos prestadores...", 0.75)
        resultado.avisos += cadastro_prestadores.preencher_cidades(
            sem_cidade, cadastro, consultar_cnpj, perguntar_cidade)
    resultado.avisos += regras.classificar(resultado.notas, escrituradas, outros_cnpjs)
    resultado.avisos += regras.marcar_falar_com_fornecedor(resultado.notas)
    cadastro.salvar()
    if cadastro.problema_ao_salvar:
        resultado.avisos.append(Aviso("Cadastro de prestadores", cadastro.problema_ao_salvar))
    _separar_as_que_nao_cabem_no_layout(resultado)

    # 3. arquivos .txt
    progresso("Gerando os arquivos...", 0.85)
    grupos = regras.agrupar_para_arquivos(resultado.notas)
    if grupos and not _pode_gravar(grupos, resultado.pasta_saida, perguntar_substituir):
        resultado.cancelado = True
        return resultado
    for grupo in grupos:
        _gravar_grupo(grupo, tipo_referencia, data_lancamento, resultado)

    # 4. conferências e relatório
    _conferir(resultado, escrituradas, resultados)
    progresso("Gerando o relatório...", 0.95)
    _gerar_relatorio(resultado)
    progresso("Concluído.", 1.0)
    return resultado


def _registrar_falhas(resultado, falhas: list[FalhaLeitura], origem: str) -> None:
    for falha in falhas:
        falha.origem = origem
        resultado.falhas.append(falha)


def _separar_as_que_nao_cabem_no_layout(resultado) -> None:
    """Nota INCLUÍDA com algum dado que o layout recusa vai para "lançar à mão" (nunca derruba o
    arquivo inteiro)."""
    for nota in resultado.notas:
        if nota.destino is not Destino.INCLUIDA:
            continue
        try:
            gerador_txt.montar_detalhe(nota)
        except ErroLayout as erro:
            nota.destino = Destino.LANCAR_A_MAO
            nota.motivo = f"dado que o arquivo não aceita: {erro}"


def _caminho_do_grupo(grupo: GrupoArquivo, pasta_saida: Path) -> Path:
    return pasta_saida / gerador_txt.nome_arquivo(grupo.tomador_documento, grupo.competencia)


def _pode_gravar(grupos, pasta_saida: Path, perguntar_substituir) -> bool:
    existentes = [c for c in (_caminho_do_grupo(g, pasta_saida) for g in grupos) if c.exists()]
    if not existentes:
        return True
    return bool(perguntar_substituir and perguntar_substituir(existentes))


def _gravar_grupo(grupo: GrupoArquivo, tipo_referencia, data_lancamento, resultado) -> None:
    caminho = _caminho_do_grupo(grupo, resultado.pasta_saida)
    arquivo = ArquivoGerado(
        caminho=caminho, tomador_documento=grupo.tomador_documento,
        tomador_nome=grupo.tomador_nome, competencia=grupo.competencia,
        quantidade=len(grupo.notas),
        total_servicos=sum((n.valor_servico for n in grupo.notas), ZERO),
        total_deducoes=sum((n.deducoes for n in grupo.notas), ZERO),
        total_iss=sum((n.valor_iss for n in grupo.notas), ZERO))
    resultado.arquivos.append(arquivo)
    try:
        conteudo = gerador_txt.gerar_conteudo(grupo.tomador_documento, grupo.competencia,
                                              data_lancamento, tipo_referencia, grupo.notas)
        problemas = gerador_txt.conferir_conteudo(conteudo)
        if problemas:
            raise ErroLayout("; ".join(problemas))
        caminho.parent.mkdir(parents=True, exist_ok=True)
        gerador_txt.gravar_arquivo(caminho, conteudo)
    except (ErroLayout, OSError) as erro:
        arquivo.gravado = False
        arquivo.problema = (f"{caminho.name} não foi gravado: {erro}" if isinstance(erro, ErroLayout)
                            else f"{caminho.name} não foi gravado (arquivo aberto em outro "
                                 "programa ou pasta sem permissão).")
        resultado.avisos.append(Aviso("Arquivo não gravado", arquivo.problema, caminho.name))
        for nota in grupo.notas:
            nota.motivo = arquivo.problema
        return
    for nota in grupo.notas:
        resultado.arquivo_txt_da_nota[id(nota)] = caminho.name


# ---------------------------------------------------------------------------
# Conferências (R16)
# ---------------------------------------------------------------------------


def _moeda(valor: Decimal) -> str:
    return f"R$ {regras.formatar_moeda(valor)}"


def _conferir(resultado: ResultadoGeracao, escrituradas, resultados) -> None:
    conferencias = resultado.conferencias
    for arquivo in resultado.arquivos:
        if arquivo.gravado:
            conferencias.append(Conferencia(
                f"{arquivo.caminho.name}: totais conferidos, sem nota repetida", True))
        else:
            conferencias.append(Conferencia(f"{arquivo.caminho.name}", False, arquivo.problema))

    ajustadas = resultado.notas_com_numero_ajustado
    if ajustadas:
        conferencias.append(Conferencia(
            f"{len(ajustadas)} nota(s) com número ajustado aos 8 últimos dígitos: depois de "
            "importar, corrigir o número no site", False,
            "veja a aba \"Corrigir número no site\" do relatório"))

    sem_cidade = [n for n in resultado.notas if n.destino in ESCRITURAVEIS
                  and not (n.prestador_cidade and n.prestador_uf)]
    conferencias.append(Conferencia(
        "Cidade encontrada para todos os prestadores", not sem_cidade,
        f"{len(sem_cidade)} nota(s) sem cidade (em \"lançar à mão\")" if sem_cidade else ""))

    if resultados:
        falharam = [f for f in resultado.falhas if f.origem == "Resultado"]
        conferencias.append(Conferencia(
            "Resultados da prefeitura lidos",
            not falharam,
            f"{len(resultados) - len(falharam)} de {len(resultados)} arquivo(s)"
            + (": confira os avisos — notas já escrituradas podem não ter sido reconhecidas"
               if falharam else "")))

    exportadas = [n for n in resultado.notas if regras.e_exportacao(n)]
    if exportadas:
        conferencias.append(_conferir_unificacao(resultado, exportadas))

    falhas = [f for f in resultado.falhas if f.origem in ("PDF", leitor_exportacao.ORIGEM)]
    conferencias.append(Conferencia(
        "Todos os arquivos de entrada lidos", not falhas,
        f"{len(falhas)} com erro de leitura" if falhas else ""))


def _conferir_unificacao(resultado, exportadas) -> Conferencia:
    """Total das exportações (notas normais, cada uma uma vez) = arquivos + lançar à mão."""
    pdfs = {chave_nota(n.numero, n.prestador_documento): n for n in resultado.notas
            if not regras.e_exportacao(n) and n.destino is not Destino.DUPLICADA}
    total = no_arquivo = a_mao = ZERO
    vistas = set()
    outras = 0
    for nota in exportadas:
        if gerador_txt.normalizar_texto(nota.situacao) not in cfg.SITUACOES_AUTORIZADAS:
            continue
        chave = chave_nota(nota.numero, nota.prestador_documento)
        if chave in vistas:
            continue
        vistas.add(chave)
        representante = pdfs.get(chave, nota)       # nota que também veio em PDF: vale o PDF
        total += nota.valor_servico
        if representante.destino is Destino.INCLUIDA and \
                id(representante) in resultado.arquivo_txt_da_nota:
            no_arquivo += nota.valor_servico
        elif representante.destino is Destino.LANCAR_A_MAO:
            a_mao += nota.valor_servico
        else:
            outras += 1
    detalhe = (f"exportações {_moeda(total)}; nos arquivos {_moeda(no_arquivo)}; "
               f"lançar à mão {_moeda(a_mao)}")
    if outras:
        detalhe += f"; {outras} nota(s) fora do arquivo (já escriturada/não incluída): conferir"
    return Conferencia("Unificação: total das exportações = arquivos + lançar à mão",
                       total == no_arquivo + a_mao, detalhe)


# ---------------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------------


def caminho_relatorio(pasta_saida, momento: datetime | None = None) -> Path:
    momento = momento or datetime.now()
    return Path(pasta_saida) / cfg.MODELO_NOME_RELATORIO.format(
        data_hora=momento.strftime(cfg.FORMATO_DATA_HORA_RELATORIO))


def _gerar_relatorio(resultado: ResultadoGeracao) -> None:
    caminho = caminho_relatorio(resultado.pasta_saida)
    try:
        gerar_relatorio(resultado, caminho)
    except Exception as erro:          # o relatório nunca apaga o trabalho já gravado
        resultado.erro_relatorio = f"O relatório não pôde ser gravado: {erro}"
        return
    resultado.caminho_relatorio = caminho
