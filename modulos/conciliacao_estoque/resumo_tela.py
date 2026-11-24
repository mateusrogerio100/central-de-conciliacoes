"""O que a tela mostra depois de cada etapa (ESPECIFICACAO_ESTOQUE.md, seções 5.4 e 6.3 "Resumo na tela").

Só organiza para exibir o que o processamento já calculou: três números, uma tabela curta,
as conferências e os avisos. Nenhuma regra de negócio nova.
- EST-01 / EST-03: contas conciliadas, com diferença e avisos; tabela por grupo sintético;
  "Total do balancete = total do SCF" e "Grupos conferidos (N de N)".
- EST-02: grupos conferidos (de 11), com diferença e avisos; tabela por grupo do SCF;
  "Total geral do PDF conferido", "Fechamento do total geral" e os pares iguais.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from modulos.conciliacao_estoque.modelos import Gravidade
from modulos.conciliacao_estoque.processamento import ResultadoEstoque
from modulos.conciliacao_estoque.utilitarios import formatar_valor


@dataclass
class Numero:
    valor: int
    legenda: str
    tom: str                # "ok", "atencao", "erro" ou "principal"


@dataclass
class Conferencia:
    texto: str
    status: str             # "ok", "atencao" ou "erro"
    valor: str | None = None


@dataclass
class ResumoTela:
    titulo: str                                                     # "EST-01 · Conciliação saldo anterior estoque"
    numeros: list[Numero] = field(default_factory=list)
    colunas: tuple[str, str, str] = ("", "", "")                    # títulos da tabela
    linhas: list[tuple] = field(default_factory=list)
    conferencias: list[Conferencia] = field(default_factory=list)
    avisos: list[Conferencia] = field(default_factory=list)         # um por aviso, ERRO primeiro
    erros: int = 0

    @property
    def selo(self) -> tuple[str, str]:
        if self.erros:
            return "Concluído com erros", "erro"
        return "Concluído", "ok"


_STATUS_DO_AVISO = {Gravidade.ERRO: "erro", Gravidade.ATENCAO: "atencao", Gravidade.INFO: "ok"}


def _status(diferenca) -> str:
    return "ok" if diferenca == 0 else "atencao"


def _plural(quantidade: int, singular: str, plural: str) -> str:
    return singular if quantidade == 1 else plural


def resumir(resultado: ResultadoEstoque) -> ResumoTela:
    resumo = ResumoTela(titulo=resultado.etapa.texto_botao, erros=resultado.erros)
    ordenados = sorted(resultado.avisos, key=lambda a: list(Gravidade).index(a.gravidade))
    resumo.avisos = [Conferencia(a.mensagem, _STATUS_DO_AVISO[a.gravidade]) for a in ordenados]
    tom_avisos = "erro" if resumo.erros else "principal"
    legenda_avisos = f"avisos · {resumo.erros} {_plural(resumo.erros, 'erro', 'erros')}"

    if resultado.comparacao is not None:
        _resumir_comparacao(resumo, resultado.comparacao)
    elif resultado.est02 is not None:
        _resumir_est02(resumo, resultado.est02)
    resumo.numeros.append(Numero(len(resultado.avisos), legenda_avisos, tom_avisos))
    if resultado.falha:
        resumo.conferencias.append(Conferencia(f"Excel não gerado: {resultado.falha}", "erro"))
    return resumo


def _resumir_comparacao(resumo, comparacao):
    com_diferenca = comparacao.contas_com_diferenca
    resumo.numeros += [
        Numero(comparacao.contas_conciliadas, "contas conciliadas", "ok"),
        Numero(com_diferenca, _plural(com_diferenca, "conta com diferença", "contas com diferença"),
               "atencao" if com_diferenca else "ok"),
    ]
    resumo.colunas = ("Grupo", "Contas", "Com diferença")
    for grupo in comparacao.grupos:
        contas = [c for c in comparacao.contas if c.grupo == grupo.classificacao]
        resumo.linhas.append((grupo.descricao or grupo.classificacao, len(contas),
                              sum(1 for c in contas if c.diferenca != 0)))

    if comparacao.saldo_sintetica_raiz is not None and comparacao.total_scf is not None:
        diferenca = comparacao.saldo_sintetica_raiz - comparacao.total_scf
        if diferenca == 0:
            resumo.conferencias.append(Conferencia("Total do balancete = total do Mapa do Estoque", "ok",
                                                   formatar_valor(comparacao.total_scf)))
        else:
            resumo.conferencias.append(Conferencia("Total do balancete diferente do total do Mapa do Estoque", "atencao",
                                                   formatar_valor(diferenca)))
    grupos = comparacao.grupos
    if grupos:
        conferidos = comparacao.grupos_conferidos
        resumo.conferencias.append(Conferencia(f"Grupos conferidos ({conferidos} de {len(grupos)})",
                                               "ok" if conferidos == len(grupos) else "atencao"))
        for grupo in grupos:
            if grupo.diferenca != 0:
                texto = "provável conta zerada" if grupo.causa_provavel else "com diferença"
                resumo.conferencias.append(Conferencia(f"Grupo {grupo.classificacao}: {texto}",
                                                       "atencao", formatar_valor(grupo.diferenca)))
    sem_conta = [l for l in comparacao.locais_sem_conta if l.saldo_scf != 0]
    if sem_conta:
        resumo.conferencias.append(Conferencia(
            f"{len(sem_conta)} {_plural(len(sem_conta), 'local', 'locais')} do Mapa do Estoque com saldo e sem conta no balancete",
            "atencao"))


def _resumir_est02(resumo, est02):
    linhas = est02.todas_as_linhas
    resumo.numeros += [
        Numero(est02.grupos_conferidos, f"de {len(linhas)} grupos conferidos", "ok"),
        Numero(est02.grupos_com_diferenca, _plural(est02.grupos_com_diferenca, "grupo com diferença",
                                                   "grupos com diferença"),
               "atencao" if est02.grupos_com_diferenca else "ok"),
    ]
    resumo.colunas = ("Grupo do Mapa do Estoque", "Operações", "Diferença")
    resumo.linhas = [(linha.nome.split(" — ")[0], len(linha.operacoes), formatar_valor(linha.diferenca))
                     for linha in linhas]

    diferenca_pdf = est02.diferenca_total_geral_pdf
    if diferenca_pdf is None:
        resumo.conferencias.append(Conferencia("Total geral do PDF não encontrado", "erro"))
    elif diferenca_pdf == 0:
        resumo.conferencias.append(Conferencia("Total geral do PDF conferido", "ok",
                                               formatar_valor(est02.total_geral_pdf)))
    else:
        resumo.conferencias.append(Conferencia("Total geral do PDF diferente da soma das operações", "erro",
                                               formatar_valor(diferenca_pdf)))
    diferenca = est02.diferenca_fechamento
    resumo.conferencias.append(Conferencia("Fechamento do total geral", _status(diferenca),
                                           formatar_valor(est02.saldo_atual_scf if diferenca == 0 else diferenca)))
    for par in est02.pares:
        texto = f"{par.nome_a} ({par.par.operacao_a}) x {par.nome_b} ({par.par.operacao_b})"
        resumo.conferencias.append(Conferencia(texto, _status(par.diferenca),
                                               formatar_valor(par.diferenca) if par.diferenca else "iguais"))
    sem_grupo = [o for o in est02.operacoes if o.sem_grupo]
    if sem_grupo:
        codigos = ", ".join(str(o.codigo) for o in sem_grupo)
        resumo.conferencias.append(Conferencia(f"Operações sem grupo: {codigos} (cadastrar em Editar configuração)",
                                               "atencao"))
