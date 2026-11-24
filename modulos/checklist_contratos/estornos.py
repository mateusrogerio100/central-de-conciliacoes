"""Estornos e notas devolvidas: regra M4 da especificação (decisão do usuário, 23/10/2026).

O Tasy desfaz um lançamento de dois jeitos, e nos dois o lançamento desfeito não pode ser conferido
(senão o valor conta em dobro, ou o lado do fornecedor vira uma "conta divergente" falsa):

- Estorno: um lançamento com o mesmo complemento e as mesmas contas e valores, invertidos (o que era
  débito vira crédito). O original e o estorno se anulam; o relançamento, se houver, vale.
- Devolução: o complemento diz "Devolução NF 2591". A devolução nunca é uma nota a conferir (vai para
  os não vinculados, R9). Se a nota devolvida (mesmo fornecedor e número) estiver no período lido e a
  devolução desfizer a nota inteira (mesmas contas e valores, invertidos), as duas se anulam. Senão
  (nota de outro mês, devolução parcial) fica só o aviso.

Tudo o que é anulado vai para a aba "Estornos e devoluções" do relatório.
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from functools import cached_property

from modulos.checklist_contratos import configuracao as cfg
from modulos.checklist_contratos.modelos import Anulacao, Aviso, Lancamento, Movimento


def _ordem_da_data(data: str) -> str:
    """dd/mm/aaaa -> aaaammdd (para ordenar)."""
    return data[6:10] + data[3:5] + data[:2]


class _Documento:
    """Um lançamento contábil (todas as linhas de débito e crédito dele)."""

    def __init__(self, chave: str, ordem: int):
        self.chave = chave
        self.ordem = ordem
        self.linhas: list[Lancamento] = []
        self.mapa: Counter = Counter()      # conta -> débitos menos créditos

    def acrescentar(self, linha: Lancamento) -> None:
        self.linhas.append(linha)
        self.mapa[linha.conta] += linha.valor if linha.natureza == cfg.MOV_DEBITO else -linha.valor

    # As propriedades abaixo são calculadas uma vez só (cached_property): os documentos ficam prontos
    # antes da busca e não mudam mais.

    @property
    def data(self) -> str:
        return self.linhas[0].data

    @cached_property
    def complemento(self) -> str:
        """O complemento do lançamento (o da primeira linha que tiver um)."""
        return next((l.complemento_normalizado for l in self.linhas if l.complemento_normalizado), "")

    @cached_property
    def _assinatura(self) -> tuple:
        return tuple(sorted((conta, valor) for conta, valor in self.mapa.items() if valor != Decimal("0")))

    def assinatura(self, sinal: int = 1) -> tuple:
        return self._assinatura if sinal == 1 else tuple((conta, -valor) for conta, valor in self._assinatura)

    @cached_property
    def _e_devolucao(self) -> bool:
        return any(cfg.RE_DEVOLUCAO.search(l.complemento_normalizado) for l in self.linhas)

    def e_devolucao(self) -> bool:
        return self._e_devolucao

    @cached_property
    def _nota(self) -> tuple[str, str]:
        achado = cfg.RE_FORNECEDOR_E_NF.search(self.complemento)
        return (achado.group(1).strip(), achado.group(2)) if achado else ("", "")

    def nota(self) -> tuple[str, str]:
        """(fornecedor, número da NF) do começo do complemento; ("", "") se não der para saber."""
        return self._nota


def anular_estornos_e_devolucoes(linhas: list[Lancamento]) -> Movimento:
    """M4: separa os débitos que valem dos estornados e das devoluções. Mantém a ordem das linhas."""
    documentos: dict[str, _Documento] = {}
    for linha in linhas:
        chave = linha.documento or f"{linha.arquivo}:{linha.linha_arquivo}"
        documentos.setdefault(chave, _Documento(chave, len(documentos))).acrescentar(linha)
    em_ordem = sorted(documentos.values(), key=lambda d: (_ordem_da_data(d.data), d.ordem))

    anulacoes: list[Anulacao] = []
    avisos: list[Aviso] = []
    anulados: set[str] = set()
    devolucoes = [d for d in em_ordem if d.e_devolucao()]

    # devolução: anula a nota devolvida quando ela está no período e a devolução a desfaz inteira
    for devolucao in devolucoes:
        anulados.add(devolucao.chave)
        numero = cfg.RE_NF_DEVOLVIDA.search(devolucao.complemento)
        fornecedor = devolucao.nota()[0]
        origem = f"{devolucao.linhas[0].arquivo} ({devolucao.data})"
        if not numero or not fornecedor:
            avisos.append(Aviso(origem, f"Devolução sem o número da nota devolvida: \"{devolucao.complemento[:80]}\". "
                                        "Ela não foi conferida; confira a nota à mão."))
            continue
        original = next((d for d in em_ordem
                         if d.chave not in anulados and not d.e_devolucao()
                         and d.nota() == (fornecedor, numero.group(1))), None)
        if original is None:
            avisos.append(Aviso(origem, f"Devolução da NF {numero.group(1)} ({fornecedor}): a nota devolvida não "
                                        "está no período lido (deve ser de outro mês)."))
        elif original.assinatura() != devolucao.assinatura(-1):
            avisos.append(Aviso(origem, f"Devolução parcial da NF {numero.group(1)} ({fornecedor}): a nota "
                                        "continua na conferência; confira o valor à mão."))
        else:
            anulados.add(original.chave)
            anulacoes.append(Anulacao("devolução", original.linhas, devolucao.linhas))

    # estorno: mesmo complemento, contas e valores invertidos; anula o primeiro lançamento igual ao estornado.
    # A busca é só entre os lançamentos com o mesmo complemento (comparar com o mês inteiro levava segundos).
    mesmo_complemento: dict[str, list[_Documento]] = {}
    for documento in em_ordem:
        mesmo_complemento.setdefault(documento.complemento, []).append(documento)
    for estorno in em_ordem:
        if estorno.chave in anulados or not estorno.mapa or not estorno.complemento:
            continue
        anteriores = mesmo_complemento[estorno.complemento]
        anteriores = anteriores[:anteriores.index(estorno)]          # em_ordem: os de antes vêm antes
        invertida = estorno.assinatura(-1)
        original = next((d for d in anteriores if d.chave not in anulados and d.assinatura() == invertida), None)
        if original is not None:
            anulados.update((original.chave, estorno.chave))
            anulacoes.append(Anulacao("estorno", original.linhas, estorno.linhas))

    validos = [l for l in linhas if l.natureza == cfg.MOV_DEBITO
               and (l.documento or f"{l.arquivo}:{l.linha_arquivo}") not in anulados]
    chaves_devolucao = {d.chave for d in devolucoes}
    debitos_devolucao = [l for l in linhas if l.natureza == cfg.MOV_DEBITO
                         and (l.documento or f"{l.arquivo}:{l.linha_arquivo}") in chaves_devolucao]
    return Movimento(validos, debitos_devolucao, anulacoes, avisos)
