"""Leitura do Movimento do lote de Repasse a terceiros do Tasy (.csv). Seção 2.2.

- Texto UTF-16 (o Tasy grava sem a marca BOM no início; com a marca também é aceito), separador ";",
  valores "1.234,56". Colunas achadas pelo título; "Histórico" aparece
  duas vezes: a 1ª é o código do histórico, a 2ª é o texto do lançamento.
- Total do Movimento = soma do Valor das linhas com Débito preenchido (inclui as com débito e crédito).
- Mês pela "Data movimento"; lote pelo "Fato contábil".
- Conta de um evento (R5): a conta de débito das linhas cujo histórico traz "Evento NNNN"
  ("HM Físico Médico (Evento 3171)" ou "Evento 3013 - HM ..."); se nenhuma, as linhas cujo histórico traz o
  nome do evento.
"""

from __future__ import annotations

import csv
import io
from collections import Counter
from pathlib import Path

from modulos.planilha_hm import configuracao as cfg
from modulos.planilha_hm.modelos import Aviso, ContaContabil, ErroLeitura, LinhaMovimento, Movimento
from modulos.planilha_hm.normalizacao import normalizar, para_decimal, texto_igual

COMO_NUMERO = "pelo número do evento"
COMO_NOME = "pelo nome do evento"


def _texto_do_arquivo(caminho: Path) -> str:
    try:
        conteudo = caminho.read_bytes()
    except FileNotFoundError:
        raise ErroLeitura(f"Arquivo não encontrado: {caminho}") from None
    except PermissionError:
        raise ErroLeitura(f"{caminho.name}: o arquivo está bloqueado por outro programa. Feche e tente de novo.") from None
    if conteudo.startswith((b"\xff\xfe", b"\xfe\xff")):
        codificacoes = ("utf-16",)
    elif len(conteudo) > 1 and conteudo[1] == 0:       # UTF-16 sem a marca no início (como o Tasy exporta)
        codificacoes = ("utf-16-le",)
    else:
        codificacoes = cfg.MOVIMENTO_CODIFICACOES
    for codificacao in codificacoes:
        try:
            return conteudo.decode(codificacao)
        except UnicodeDecodeError:
            continue
    raise ErroLeitura(f"{caminho.name}: não foi possível ler o arquivo como texto.")


def _indices(titulos: list[str]) -> dict[str, int] | None:
    """Coluna de cada título obrigatório; None se faltar algum."""
    indices = {}
    for titulo in cfg.MOVIMENTO_TITULOS_OBRIGATORIOS:
        indice = next((i for i, t in enumerate(titulos) if texto_igual(t, titulo)), None)
        if indice is None:
            return None
        indices[titulo] = indice
    historicos = [i for i, t in enumerate(titulos) if texto_igual(t, cfg.MOVIMENTO_TITULO_HISTORICO)]
    if len(historicos) < 2:
        return None
    indices["codigo_historico"], indices["historico"] = historicos[0], historicos[1]
    return indices


def evento_do_historico(historico: str) -> int | None:
    achado = cfg.RE_EVENTO_HISTORICO.search(historico or "")
    return int(achado.group(1) or achado.group(2)) if achado else None


def ler_movimento(caminho: Path) -> Movimento:
    """Lê o Movimento. Levanta ErroLeitura se faltar algum título obrigatório."""
    caminho = Path(caminho)
    movimento = Movimento(arquivo=caminho.name)
    linhas = list(csv.reader(io.StringIO(_texto_do_arquivo(caminho)), delimiter=cfg.MOVIMENTO_SEPARADOR))
    indices = _indices(linhas[0]) if linhas else None
    if indices is None:
        obrigatorios = (*cfg.MOVIMENTO_TITULOS_OBRIGATORIOS, f"{cfg.MOVIMENTO_TITULO_HISTORICO} (duas colunas)")
        raise ErroLeitura(f"{caminho.name}: não parece ser o Movimento do Tasy (faltam títulos; esperados: "
                          f"{', '.join(obrigatorios)}).")

    def campo(valores, chave) -> str:
        indice = indices[chave]
        return valores[indice].strip() if indice < len(valores) else ""

    meses, lotes = Counter(), Counter()
    for numero, valores in enumerate(linhas[1:], start=2):
        if not any(v.strip() for v in valores):
            continue
        origem = f"{caminho.name} linha {numero}"
        valor = para_decimal(campo(valores, cfg.MOVIMENTO_TITULO_VALOR))
        if valor is None:
            movimento.avisos.append(Aviso(origem, f"Valor inválido ({campo(valores, cfg.MOVIMENTO_TITULO_VALOR)!r}): "
                                                  "linha ignorada.", erro=True))
            continue
        data = cfg.RE_DATA_TEXTO.match(campo(valores, cfg.MOVIMENTO_TITULO_DATA))
        if data:
            meses[(int(data.group(3)), int(data.group(2)))] += 1
        if campo(valores, cfg.MOVIMENTO_TITULO_LOTE):
            lotes[campo(valores, cfg.MOVIMENTO_TITULO_LOTE)] += 1
        historico = " ".join(campo(valores, "historico").split())
        movimento.linhas.append(LinhaMovimento(
            numero, campo(valores, cfg.MOVIMENTO_TITULO_DEBITO), campo(valores, cfg.MOVIMENTO_TITULO_CREDITO), valor,
            campo(valores, "codigo_historico"), historico, campo(valores, cfg.MOVIMENTO_TITULO_CONTA_DEBITO),
            campo(valores, cfg.MOVIMENTO_TITULO_CLASSIFICACAO_DEBITO), evento_do_historico(historico)))

    if not movimento.linhas:
        raise ErroLeitura(f"{caminho.name}: nenhum lançamento no Movimento.")
    if meses:
        (movimento.ano, movimento.mes), _ = meses.most_common(1)[0]
        if len(meses) > 1:
            outros = ", ".join(f"{m:02d}/{a}" for a, m in sorted(meses) if (a, m) != (movimento.ano, movimento.mes))
            movimento.avisos.append(Aviso(caminho.name, f"O Movimento tem datas de mais de um mês ({outros}): vale "
                                                        f"{movimento.mes:02d}/{movimento.ano}.", erro=True))
    else:
        movimento.avisos.append(Aviso(caminho.name, "Nenhuma \"Data movimento\" válida: mês do Movimento "
                                                    "desconhecido.", erro=True))
    if lotes:
        movimento.lote = lotes.most_common(1)[0][0]
        if len(lotes) > 1:
            movimento.avisos.append(Aviso(caminho.name, f"O Movimento tem mais de um lote ({', '.join(sorted(lotes))})"
                                                        f": vale o {movimento.lote}."))
    return movimento


def _sem_repetir(contas) -> list[ContaContabil]:
    return list(dict.fromkeys(contas))


def contas_do_evento(movimento: Movimento, numero: int, nome: str = "") -> tuple[list[ContaContabil], str]:
    """R5, itens 1 e 2: as contas de débito do evento e como foram achadas (COMO_NUMERO, COMO_NOME ou "")."""
    pelo_numero = _sem_repetir(l.conta for l in movimento.linhas if l.tem_debito and l.evento == numero)
    if pelo_numero:
        return pelo_numero, COMO_NUMERO
    procurado = normalizar(nome)
    if procurado:
        pelo_nome = _sem_repetir(l.conta for l in movimento.linhas
                                 if l.tem_debito and procurado in normalizar(l.historico))
        if pelo_nome:
            return pelo_nome, COMO_NOME
    return [], ""
