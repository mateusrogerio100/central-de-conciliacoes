"""Quais notas entram no SPED — ESPECIFICACAO_EFD_CONTRIBUICOES.md, seção 4.2 (decisões do usuário, 05/11/2026).

Cada PDF termina com uma situação. A ordem em que as regras são olhadas:
1. não lido (R4);
2. número repetido: com o mesmo tomador (CNPJ) e o mesmo valor, entra o 1º PDF (ordem do nome do arquivo) e as
   cópias ficam "Fora: repetida"; com tomador ou valor diferente, todos ficam em conflito e o SPED não é gerado (R5);
3. mês da competência da NFS-e diferente do mês da data de emissão;
4. mês da data de emissão diferente da competência do SPED que está sendo gerado;
5. tomador pessoa física (regra da origem: só PJ é lançado);
6. o que sobra entra no SPED.

Ajustes de 05/11/2026 (pedido do usuário): uma nota que ficou fora por causa das DATAS (regras 3 e 4) pode ser
incluída à mão na tela (incluir()); e avisos_prestador() avisa quando os PDFs vêm de prestadores com CNPJ diferente.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from modulos.efd_contribuicoes import configuracao as cfg
from modulos.efd_contribuicoes.leitor_danfse import PF, NotaDanfse


@dataclass
class NotaClassificada:
    nota: NotaDanfse
    situacao: str
    observacao: str = ""

    @property
    def no_sped(self) -> bool:
        return self.situacao in (cfg.SITUACAO_NO_SPED, cfg.SITUACAO_INCLUIDA)

    @property
    def incluivel(self) -> bool:
        """Ficou fora por causa das datas: pode ser incluída à mão."""
        return self.situacao in cfg.SITUACOES_INCLUIVEIS


@dataclass
class Selecao:
    notas: list[NotaClassificada] = field(default_factory=list)       # na ordem do nome do arquivo
    conflitos: list[str] = field(default_factory=list)                # R5: uma mensagem por número em conflito

    @property
    def no_sped(self) -> list[NotaClassificada]:
        return [n for n in self.notas if n.no_sped]

    @property
    def nao_lidas(self) -> list[NotaClassificada]:
        return [n for n in self.notas if n.situacao == cfg.SITUACAO_NAO_LIDO]

    @property
    def incluiveis(self) -> list[NotaClassificada]:
        return [n for n in self.notas if n.incluivel]

    def contar(self, situacao: str) -> int:
        return sum(1 for n in self.notas if n.situacao == situacao)


def _mes_texto(ano_mes: tuple[int, int] | None) -> str:
    return "?" if ano_mes is None else f"{ano_mes[1]:02d}/{ano_mes[0]}"


def classificar(notas: list[NotaDanfse], competencia: str) -> Selecao:
    """`competencia` = mês do SPED que está sendo gerado ("MM/AAAA")."""
    mes, ano = (int(p) for p in competencia.split("/"))
    competencia_sped = (ano, mes)
    ordenadas = sorted(notas, key=lambda n: n.arquivo.casefold())
    situacao: dict[int, NotaClassificada] = {}

    # 1. não lidos
    for nota in ordenadas:
        if not nota.lida:
            situacao[id(nota)] = NotaClassificada(nota, cfg.SITUACAO_NAO_LIDO, nota.status.removeprefix("ERRO: "))

    # 2. números repetidos (entre as notas lidas)
    selecao = Selecao()
    por_numero: dict[str, list[NotaDanfse]] = {}
    for nota in ordenadas:
        if id(nota) not in situacao:
            por_numero.setdefault(nota.numero_nfse.strip(), []).append(nota)
    for numero, grupo in por_numero.items():
        if len(grupo) < 2:
            continue
        arquivos = ", ".join(n.arquivo for n in grupo)
        iguais = len({(n.cnpj_digitos, n.valor) for n in grupo}) == 1
        if iguais:
            primeira = grupo[0]
            for copia in grupo[1:]:
                situacao[id(copia)] = NotaClassificada(
                    copia, cfg.SITUACAO_REPETIDA, f"NFS-e {numero} repetida: entrou o arquivo {primeira.arquivo}")
        else:
            selecao.conflitos.append(f"NFS-e {numero} aparece em mais de um PDF com tomador ou valor diferente: "
                                     f"{arquivos}. Deixe só o PDF certo na pasta e gere de novo.")
            for nota in grupo:
                situacao[id(nota)] = NotaClassificada(nota, cfg.SITUACAO_CONFLITO, f"mesmo número em: {arquivos}")

    # 3 a 6
    for nota in ordenadas:
        if id(nota) in situacao:
            continue
        if nota.mes_competencia != nota.mes_emissao:
            situacao[id(nota)] = NotaClassificada(
                nota, cfg.SITUACAO_COMPETENCIA,
                f"competência {_mes_texto(nota.mes_competencia)}, emitida em {nota.data_emissao:%d/%m/%Y}")
        elif nota.mes_emissao != competencia_sped:
            situacao[id(nota)] = NotaClassificada(
                nota, cfg.SITUACAO_EMISSAO, f"emitida em {nota.data_emissao:%d/%m/%Y}, fora de {competencia}")
        elif nota.tipo_pessoa == PF:
            situacao[id(nota)] = NotaClassificada(nota, cfg.SITUACAO_PF)
        else:
            situacao[id(nota)] = NotaClassificada(nota, cfg.SITUACAO_NO_SPED)

    selecao.notas = [situacao[id(n)] for n in ordenadas]
    return selecao


def incluir(selecao: Selecao, arquivos: list[str]) -> list[NotaClassificada]:
    """Inclui à mão as notas destes arquivos que ficaram fora pelas datas. Devolve as que foram incluídas."""
    escolhidos = set(arquivos)
    incluidas = []
    for item in selecao.notas:
        if item.nota.arquivo in escolhidos and item.incluivel:
            motivo = item.situacao.removeprefix("Fora: ")
            item.observacao = f"{motivo}: {item.observacao} — incluída à mão" if item.observacao else "incluída à mão"
            item.situacao = cfg.SITUACAO_INCLUIDA
            incluidas.append(item)
    return incluidas


def avisos_prestador(notas: list[NotaDanfse]) -> list[str]:
    """Os PDFs lidos deveriam ser todos do mesmo prestador. CNPJ diferente → um aviso por arquivo diferente da maioria."""
    por_cnpj: dict[str, list[NotaDanfse]] = {}
    for nota in notas:
        if nota.lida:
            por_cnpj.setdefault(nota.cnpj_prestador_digitos, []).append(nota)
    if len(por_cnpj) <= 1:
        return []
    principal = max(por_cnpj, key=lambda c: len(por_cnpj[c]))
    principal_txt = por_cnpj[principal][0].doc_prestador or "(vazio)"
    avisos = []
    for cnpj, lista in sorted(por_cnpj.items()):
        if cnpj == principal:
            continue
        for nota in lista:
            avisos.append(f"{nota.arquivo}: prestador com CNPJ {nota.doc_prestador or '(não encontrado)'} "
                          f"({nota.prestador or 'sem nome'}), diferente do CNPJ {principal_txt} dos outros "
                          f"{len(por_cnpj[principal])} PDF(s). Confira se a nota é mesmo da Fundação.")
    return avisos
