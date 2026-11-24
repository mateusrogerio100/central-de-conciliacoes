"""Estoque, etapa EST-01 (Conciliação saldo anterior estoque): balancete do grupo 1.01.04 e o SCF -
Movimento Estoque (Contabilidade), os dois como o ".xls" de texto do Tasy.

Mostra: locais que batem, um com o saldo anterior diferente e um local do SCF sem conta no balancete. A
EST-03 funciona igual com o saldo atual; a EST-02 usa também o PDF "Movimento estoque" e a
configuração (botão "Editar configuração").
"""

from __future__ import annotations

from pathlib import Path

from manual.ficticios import Exemplo

# código, local (número entre parênteses = código do local no SCF), saldo anterior, movimento
CONTAS = [
    (10971, "Almoxarifado Central Exemplo (11)", 120000.00, 5000.00),
    (10972, "Farmácia Exemplo (12)", 85430.50, -3430.50),
    (10973, "Nutrição Exemplo (13)", 12300.00, 200.00),
    (10974, "Manutenção Exemplo (14)", 7800.00, 0.00),
]
# local, saldo anterior no SCF, entradas (notas fiscais), saídas (consumo)
LOCAIS_SCF = [
    ("Almoxarifado Central Exemplo (11)", 120000.00, 9000.00, 4000.00),
    ("Farmácia Exemplo (12)", 85130.50, 2000.00, 5130.50),          # 300,00 a menos que o balancete
    ("Nutrição Exemplo (13)", 12300.00, 1200.00, 1000.00),
    ("Manutenção Exemplo (14)", 7800.00, 0.00, 0.00),
    ("Lavanderia Exemplo (15)", 450.00, 0.00, 0.00),                # sem conta no balancete
]


def _br(valor: float) -> str:
    return f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _balancete(caminho: Path) -> Path:
    def linha(codigo, classificacao, descricao, anterior, movimento):
        return (f"\t\t{codigo}\t\t{classificacao}\t  {descricao}\t\t\t\t{_br(anterior)}\t\t{_br(movimento)}\t"
                f"{_br(anterior + movimento)}")

    anterior = sum(c[2] for c in CONTAS)
    movimento = sum(c[3] for c in CONTAS)
    linhas = ["Fundação Exemplo de Misericórdia\t\t", "\t\t\t\t\t\tMês Referência:\t\tset/2026",
              "\tCódigo\t\tClassificação\t\tDescrição\t\t\t\tSaldo Anterior\t\tMovimento\tSaldo Atual",
              linha(114, "1.01.04", "ESTOQUES", anterior, movimento),
              linha(1141, "1.01.04.01", "ESTOQUES EXEMPLO", anterior, movimento)]
    for posicao, (codigo, descricao, saldo_anterior, mov) in enumerate(CONTAS, start=1):
        linhas.append(linha(codigo, f"1.01.04.01.{posicao:04d}", descricao, saldo_anterior, mov))
    linhas.append("\tImpresso em: 05/10/2026 09:12:10\t\t\t\t\tPágina: 1")
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes("\n".join(linhas).encode("cp1252"))
    return caminho


def _valores(anterior, entradas, saidas) -> list[float]:
    return [anterior, entradas, 0, 0, 0, entradas, saidas, 0, 0, 0, 0, saidas, anterior + entradas - saidas]


def _scf(caminho: Path) -> Path:
    def linha(descricao, valores):
        return descricao + "\t" + "\t\t".join(_br(v) for v in valores)

    titulos = "Descrição\t" + "\t".join(("Saldo Anterior", "Notas Fiscais", "Emprestimo", "Inventário", "Out.Entradas",
                                         "Total (E)", "Consumo", "Inventário", "Pacientes", "Subvenção",
                                         "Out.Saídas", "Total (S)", "Saldo Atual"))
    linhas = ["\t\t\tSCF - Movimento Estoque (Contabilidade)", "\t\tMês competência:\t\t01/09/2026", titulos]
    totais = [0.0] * 13
    for local, anterior, entradas, saidas in LOCAIS_SCF:
        valores = _valores(anterior, entradas, saidas)
        totais = [t + v for t, v in zip(totais, valores)]
        linhas.append(linha(local, valores))
    linhas.append(linha(f"Total({len(LOCAIS_SCF)})", totais))
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes("\n".join(linhas).encode("cp1252"))
    return caminho


def gerar(pasta: Path) -> list[Exemplo]:
    saida = pasta / "saida"
    saida.mkdir(parents=True, exist_ok=True)
    return [Exemplo("conciliacao_estoque", "estoque", "Conciliação", "conciliacao", {
        "cartao_balancete": [_balancete(pasta / "Balancete_estoque_set2026.xls")],
        "cartao_scf": [_scf(pasta / "SCF - Movimento Estoque (Contabilidade) set2026.xls")],
        "cartao_saida": [saida]},
        preparar=lambda tela: tela.campo_mes.definir("09/2026"),
        acao=lambda tela: tela.processar_etapa("EST-01"), pasta_saida=saida, numeros=("3", "1", "1"))]
