"""Check list (já atualizado pelo usuário) -> notas pendentes por responsável. Regras P1 a P6.

- Pendente = célula do mês vazia (P1), menos: célula com texto, contrato encerrado no mês anterior e
  linha CONTA DIVERGENTE no relatório da conferência do mês, quando informado (P2). As de CONTA
  DIVERGENTE não vão nos e-mails, mas são listadas na prévia (notas_conta_divergente).
- O responsável é identificado pelo número no começo da coluna Responsável ("13 - Carlos manutenção",
  decisão do usuário de 23/10/2026). Sem número, vale a chave do nome (P5) e o e-mail não sai (E2).
- O redirecionamento P4 foi aposentado: quem muda de responsável é corrigido na própria planilha.
"""

from __future__ import annotations

import tempfile
from collections import Counter
from pathlib import Path

import openpyxl

from modulos.checklist_contratos import configuracao as cfg
from modulos.checklist_contratos.leitor_checklist import copiar_para_ler, nome_do_mes, texto_da_celula
from modulos.checklist_contratos.modelos import (
    Aviso, Checklist, ErroLeitura, LinhaChecklist, ListaPendente, Situacao,
)
from modulos.checklist_contratos.normalizacao import chave_responsavel, normalizar


def codigo_e_nome(responsavel: str) -> tuple[str, str]:
    """"13 - Carlos manutenção" -> ("13", "Carlos manutenção"); sem número -> ("", texto)."""
    achado = cfg.RE_CODIGO_RESPONSAVEL.match(responsavel or "")
    if achado:
        return str(int(achado.group(1))), achado.group(2).strip()
    return "", (responsavel or "").strip()


def chave_da_linha(linha: LinhaChecklist) -> tuple[str, str, str]:
    """(chave, código, nome) do responsável da linha (P3, P5)."""
    codigo, nome = codigo_e_nome(linha.responsavel)
    if codigo:
        return codigo, codigo, nome
    if not nome:
        return normalizar(cfg.SEM_RESPONSAVEL), "", cfg.SEM_RESPONSAVEL
    return chave_responsavel(nome), "", nome


def linhas_divergentes(relatorio: Path, ano: int, mes: int, checklist: Checklist) -> set[tuple[str, int]]:
    """P2: (estabelecimento, linha) das linhas CONTA DIVERGENTE no relatório da conferência do mês."""
    relatorio = Path(relatorio)
    mes_do_nome = cfg.RE_MES_DO_RELATORIO.search(relatorio.name)
    if mes_do_nome and (int(mes_do_nome.group(1)), int(mes_do_nome.group(2))) != (ano, mes):
        raise ErroLeitura(f"O relatório {relatorio.name} não é da conferência de {nome_do_mes(ano, mes)}.")
    estabelecimentos = {normalizar(aba.nome): e for e, aba in checklist.abas.items()}
    with tempfile.TemporaryDirectory(prefix="relatorio_") as pasta:
        copia = copiar_para_ler(relatorio, Path(pasta))
        try:
            livro = openpyxl.load_workbook(copia, data_only=True)
        except Exception as erro:
            raise ErroLeitura(f"O relatório não pôde ser aberto como planilha do Excel: {erro}") from None
        try:
            aba = next((livro[n] for n in livro.sheetnames if normalizar(n) == cfg.REL_ABA_CONFERENCIA), None)
            if aba is None:
                raise ErroLeitura(f"O arquivo {relatorio.name} não é um relatório da conferência "
                                  "(falta a aba Conferência).")
            linhas = aba.iter_rows(values_only=True)
            titulos = [normalizar(t) for t in next(linhas, ())]
            colunas = [next((titulos.index(t) for t in aceitos if t in titulos), None) for aceitos in (
                (cfg.REL_TITULO_ABA,), (cfg.REL_TITULO_LINHA,), cfg.REL_TITULOS_SITUACAO)]
            if None in colunas:
                raise ErroLeitura(f"A aba Conferência de {relatorio.name} não tem as colunas Aba, Linha e "
                                  "Situação.")
            col_aba, col_linha, col_situacao = colunas
            divergentes = set()
            for valores in linhas:
                if len(valores) <= max(colunas):
                    continue
                situacao = texto_da_celula(valores[col_situacao])
                estabelecimento = estabelecimentos.get(normalizar(valores[col_aba]))
                if situacao.startswith(Situacao.CONTA_DIVERGENTE.value) and estabelecimento and \
                        isinstance(valores[col_linha], (int, float)):
                    divergentes.add((estabelecimento, int(valores[col_linha])))
        finally:
            livro.close()
    return divergentes


def _encerrado(linha: LinhaChecklist) -> bool:
    anterior = normalizar(linha.valor_mes_anterior) if isinstance(linha.valor_mes_anterior, str) else ""
    return any(texto in anterior for texto in cfg.TEXTOS_ENCERRADO)


def _celula_vazia(linha: LinhaChecklist) -> bool:
    """P1 e P2: linha com fornecedor, célula do mês vazia e contrato não encerrado no mês anterior."""
    return bool(linha.fornecedor) and not texto_da_celula(linha.valor_mes) and not _encerrado(linha)


def notas_conta_divergente(checklist: Checklist, divergentes: set[tuple[str, int]]
                           ) -> list[tuple[str, LinhaChecklist]]:
    """P2: as linhas que seriam pendentes, mas ficam fora dos e-mails por CONTA DIVERGENTE (a nota chegou,
    em outra conta). Vão para a prévia, para não sumirem em silêncio. (estabelecimento, linha)."""
    return [(estabelecimento, linha) for estabelecimento, aba in checklist.abas.items() for linha in aba.linhas
            if (estabelecimento, linha.numero) in divergentes and _celula_vazia(linha)]


def gerar_listas(checklist: Checklist, divergentes: set[tuple[str, int]] = frozenset()
                 ) -> tuple[list[ListaPendente], list[Aviso]]:
    """P1 a P6: uma lista por estabelecimento + responsável, na ordem da planilha."""
    avisos: list[Aviso] = []
    # P5: o nome mostrado é a forma mais frequente da chave em toda a planilha
    nomes: dict[str, Counter] = {}
    for aba in checklist.abas.values():
        for linha in aba.linhas:
            if linha.fornecedor:
                chave, _, nome = chave_da_linha(linha)
                nomes.setdefault(chave, Counter())[nome] += 1
    for chave, contagem in nomes.items():
        if chave.isdigit() and len({chave_responsavel(n) for n in contagem}) > 1:
            avisos.append(Aviso(f"Responsável {chave}", "O número " + chave + " está com nomes diferentes na "
                                f"planilha ({', '.join(contagem)}): confira a coluna Responsável."))

    listas: dict[tuple[str, str], ListaPendente] = {}
    for estabelecimento, aba in checklist.abas.items():
        for linha in aba.linhas:
            if not _celula_vazia(linha) or (estabelecimento, linha.numero) in divergentes:   # P1, P2
                continue
            chave, codigo, _ = chave_da_linha(linha)
            lista = listas.get((estabelecimento, chave))
            if lista is None:
                nome = nomes[chave].most_common(1)[0][0]
                lista = listas[(estabelecimento, chave)] = ListaPendente(estabelecimento, chave, codigo, nome)
            lista.notas.append(linha)
    return list(listas.values()), avisos


def avisos_dos_codigos(checklist: Checklist) -> list[Aviso]:
    """Número da aba Emails que não está na planilha e número da planilha sem nenhum contato."""
    na_planilha = {chave_da_linha(l)[1] for aba in checklist.abas.values() for l in aba.linhas if l.fornecedor}
    na_planilha.discard("")
    nos_contatos = {c for contato in checklist.contatos for c in contato.codigos}
    avisos = []
    for contato in checklist.contatos:
        if not contato.codigos:
            avisos.append(Aviso(f"{cfg.ABA_EMAILS} {contato.celula}", f"{contato.email} não tem número ao lado: "
                                "não recebe nenhum e-mail."))
        for codigo in contato.codigos:
            if codigo.isdigit() and codigo not in na_planilha:
                avisos.append(Aviso(f"{cfg.ABA_EMAILS} {contato.celula}", f"{contato.email}: o número {codigo} "
                                    "não está em nenhuma linha da planilha."))
    for codigo in sorted(na_planilha - nos_contatos, key=int):
        avisos.append(Aviso(f"Responsável {codigo}", f"Nenhum contato da aba {cfg.ABA_EMAILS} tem o número "
                            f"{codigo}: os e-mails desse responsável não serão gerados."))
    return avisos

