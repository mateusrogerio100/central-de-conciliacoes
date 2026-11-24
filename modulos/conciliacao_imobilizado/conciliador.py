"""
Comparação conta por conta (ESPECIFICACAO seção 15, decisões do usuário):

- Chave: o código da conta (11038). Compara o Saldo atual do patrimônio com o do balancete.
  Diferença = patrimônio − balancete; qualquer valor diferente de zero é diferença
  (inclusive centavos: quem concilia analisa).
- Contas-mães do balancete (152, 1320, 1515) não entram: são a soma das outras.
- Conta só de um lado → "Somente no patrimônio" / "Somente no balancete".
- Com diferença:
  - sem os relatórios de Bens adquiridos e Baixa de bens → "Diferença — verificar";
  - com eles → testa se a diferença (para mais ou para menos) é igual às entradas da
    conta, às baixas da conta ou a entradas − baixas. Igual → "Diferença explicada pelos
    bens adquiridos/baixados"; senão → "Diferença sem explicação — verificar".
- Bens adquiridos acham a conta pelo código; baixas, pelo NOME exato da conta (o relatório
  561 não traz o código). Nome que não bate com nenhuma conta, ou com mais de uma → aviso.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from modulos.conciliacao_imobilizado.base_iss import Aviso
from modulos.conciliacao_imobilizado.leitor_texto import juntar_espacos, reais
from modulos.conciliacao_imobilizado.modelos import (
    SITUACAO_CONFERE,
    SITUACAO_DIFERENCA,
    SITUACAO_DIFERENCA_EXPLICADA,
    SITUACAO_DIFERENCA_SEM_EXPLICACAO,
    SITUACAO_SOMENTE_BALANCETE,
    SITUACAO_SOMENTE_PATRIMONIO,
    BemAdquirido,
    BemBaixado,
    ContaBalancete,
    ContaPatrimonio,
    ItemConciliacao,
)

ARQUIVO_CONCILIACAO = "Conciliação"     # "arquivo" dos avisos gerados aqui


@dataclass
class Conciliacao:
    itens: list[ItemConciliacao] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)


def _chave_nome(nome: str) -> str:
    return juntar_espacos(nome).casefold()


def ligar_baixas_as_contas(baixas: list[BemBaixado], contas_patrimonio: list[ContaPatrimonio],
                           contas_balancete: list[ContaBalancete]) -> list[Aviso]:
    """Preenche BemBaixado.conta_codigo achando a conta pelo nome exato. Devolve os avisos."""
    por_nome: dict[str, set[str]] = {}
    for conta in contas_patrimonio:
        por_nome.setdefault(_chave_nome(conta.nome), set()).add(conta.codigo)
    for conta in contas_balancete:
        if not conta.sintetica:
            por_nome.setdefault(_chave_nome(conta.descricao), set()).add(conta.codigo)

    avisos: list[Aviso] = []
    avisados: set[str] = set()
    for bem in baixas:
        codigos = por_nome.get(_chave_nome(bem.conta_nome), set())
        if len(codigos) == 1:
            bem.conta_codigo = next(iter(codigos))
            continue
        if bem.conta_nome in avisados:
            continue
        avisados.add(bem.conta_nome)
        if not codigos:
            mensagem = (f"Baixas da conta \"{bem.conta_nome}\": nenhuma conta do patrimônio ou do "
                        "balancete tem esse nome; essas baixas não foram usadas para explicar "
                        "diferenças.")
        else:
            mensagem = (f"Baixas da conta \"{bem.conta_nome}\": mais de uma conta tem esse nome "
                        f"({', '.join(sorted(codigos))}); essas baixas não foram usadas para "
                        "explicar diferenças.")
        avisos.append(Aviso(arquivo=ARQUIVO_CONCILIACAO, mensagem=mensagem))
    return avisos


def conciliar(contas_patrimonio: list[ContaPatrimonio], contas_balancete: list[ContaBalancete],
              bens_adquiridos: list[BemAdquirido] | None = None,
              bens_baixados: list[BemBaixado] | None = None) -> Conciliacao:
    """
    bens_adquiridos / bens_baixados: None = relatório não informado; [] = informado e vazio.
    As baixas já devem ter passado por ligar_baixas_as_contas().
    """
    resultado = Conciliacao()
    tem_movimento = bens_adquiridos is not None or bens_baixados is not None

    patrimonio = {c.codigo: c for c in contas_patrimonio}
    balancete: dict[str, ContaBalancete] = {}
    for conta in contas_balancete:
        if conta.sintetica:
            continue
        if conta.codigo in balancete:
            resultado.avisos.append(Aviso(
                arquivo=conta.arquivo,
                mensagem=f"A conta {conta.codigo} aparece em mais de um balancete "
                         f"({balancete[conta.codigo].arquivo} e {conta.arquivo}); "
                         "foi usada só a primeira.",
            ))
            continue
        balancete[conta.codigo] = conta

    entradas: dict[str, Decimal] = {}
    for bem in bens_adquiridos or []:
        entradas[bem.conta_codigo] = entradas.get(bem.conta_codigo, Decimal(0)) + bem.valor
    baixas: dict[str, Decimal] = {}
    for bem in bens_baixados or []:
        if bem.conta_codigo:
            baixas[bem.conta_codigo] = baixas.get(bem.conta_codigo, Decimal(0)) + bem.valor_origem

    codigos = sorted(set(patrimonio) | set(balancete), key=lambda c: (len(c), c))
    for codigo in codigos:
        conta_p, conta_b = patrimonio.get(codigo), balancete.get(codigo)
        item = ItemConciliacao(
            codigo=codigo,
            nome=conta_p.nome if conta_p else conta_b.descricao,
            situacao="",
            conta_patrimonio=conta_p, conta_balancete=conta_b,
            entradas=entradas.get(codigo, Decimal(0)),
            baixas=baixas.get(codigo, Decimal(0)),
        )
        _classificar(item, tem_movimento)
        resultado.itens.append(item)

    # Bens de contas que não estão em nenhum dos dois relatórios
    for codigo in sorted(set(entradas) - set(codigos)):
        resultado.avisos.append(Aviso(
            arquivo=ARQUIVO_CONCILIACAO,
            mensagem=f"Bens adquiridos na conta {codigo} ({reais(entradas[codigo])}), que não "
                     "está no patrimônio nem nos balancetes.",
        ))
    for codigo in sorted(set(baixas) - set(codigos)):
        resultado.avisos.append(Aviso(
            arquivo=ARQUIVO_CONCILIACAO,
            mensagem=f"Baixas na conta {codigo} ({reais(baixas[codigo])}), que não está no "
                     "patrimônio nem nos balancetes.",
        ))
    return resultado


def _classificar(item: ItemConciliacao, tem_movimento: bool) -> None:
    if item.conta_patrimonio is None:
        item.situacao = SITUACAO_SOMENTE_BALANCETE
        return
    if item.conta_balancete is None:
        item.situacao = SITUACAO_SOMENTE_PATRIMONIO
        return

    diferenca = item.diferenca
    if diferenca == 0:
        item.situacao = SITUACAO_CONFERE
        return

    lado = (f"Patrimônio maior que o balancete em {reais(diferenca)}" if diferenca > 0
            else f"Patrimônio menor que o balancete em {reais(-diferenca)}")
    if not tem_movimento:
        item.situacao = SITUACAO_DIFERENCA
        item.explicacao = (f"{lado}. Selecione os relatórios de Bens adquiridos e/ou Baixa de "
                           "bens para tentar explicar.")
        return

    candidatos = [
        (item.entradas, "entradas da conta (bens adquiridos)"),
        (item.baixas, "baixas da conta"),
        (item.entradas - item.baixas, "entradas menos baixas da conta"),
    ]
    for valor, descricao in candidatos:
        if valor != 0 and abs(valor) == abs(diferenca):
            item.situacao = SITUACAO_DIFERENCA_EXPLICADA
            item.explicacao = f"{lado} = {descricao}: {reais(abs(valor))}."
            return
    item.situacao = SITUACAO_DIFERENCA_SEM_EXPLICACAO
    item.explicacao = (f"{lado}. Na conta: entradas {reais(item.entradas)}, "
                       f"baixas {reais(item.baixas)}.")
