"""Honorários Médicos, as duas abas.

AMEs: balancete (865) da conta de Honorários médicos a pagar e o SCF – Repasse Sintético do Tasy. Mostra
uma clínica com repasses em dois grupos que bate, uma com diferença, uma conta sem repasse, um repasse
sem conta e dois repasses da mesma clínica no mesmo grupo.

Hospital Exemplo (PF e PJ): balancetes 2131 e 2132, HM PF e PJ Senior (texto do Tasy) e o PDF de
Remoção/Transporte. Mostra um médico que só bate somando a Remoção, uma diferença, um lançamento só no
Senior, uma conta zerada (fica fora, com nota) e uma linha do PDF sem conta no balancete.
"""

from __future__ import annotations

from pathlib import Path

from manual.ficticios import Exemplo
from manual.ficticios.pdf_simples import gravar_pdf
from manual.ficticios.tasy import conta_balancete, numero_br, texto_tasy, topo_balancete

# --- AMEs ---------------------------------------------------------------------------------------------
UNIDADE_AME = "AME - Cidade Exemplo (Fund. Hospital Exemplo)"
UNIDADE_REPASSE = "AME - Cidade Exemplo"
CONTAS_AME = [
    (40001, "Clínica Alfa Exemplo Serviços Médicos Ltda", 15800.00),
    (40002, "Beta Exemplo Médicos Associados S/S", 8400.00),
    (40003, "Delta Exemplo Saúde Ltda", 3100.00),
    (40004, "Gama Exemplo Ortopedia Ltda", 6250.00),
    (40005, "Zeta Exemplo Oftalmologia Ltda", 9720.00),
]
GRUPOS_REPASSE = [                              # grupo: (terceiro, nr repasse, bruto, líquido)
    ("Deslocamento", [("Clinica Alfa Exemplo Servicos Medicos Ltda", "600001", 1200.00, 1200.00)]),
    ("Produção Médica", [
        ("Clinica Alfa Exemplo Servicos Medicos Ltda.", "600002", 14600.00, 13870.00),
        ("Beta Exemplo Medicos Associados S/s", "600003", 7950.00, 7552.50),
        ("Gama Exemplo Ortopedia Ltda", "600004", 6250.00, 5937.50),
        ("Zeta Exemplo Oftalmologia Ltda", "600005", 6000.00, 5700.00),
        ("Zeta Exemplo Oftalmologia Ltda", "600006", 3720.00, 3534.00),
        ("Omega Exemplo Servicos Medicos Ltda", "600007", 900.00, 855.00),
    ]),
]


def _balancete_ame(pasta: Path) -> Path:
    linhas = topo_balancete(UNIDADE_AME, "set/2026")
    linhas.append(conta_balancete(2132, "2.01.03.02", "HONORARIOS MEDICOS A PAGAR - PJ",
                                  sum(c[2] for c in CONTAS_AME)))
    for posicao, (codigo, nome, saldo) in enumerate(CONTAS_AME, start=1):
        linhas.append(conta_balancete(codigo, f"2.01.03.02.{posicao:04d}", nome, saldo))
    linhas.append([None, "Impresso em: 08/10/2026", None, None, None, None, None, "Página: 1", None,
                   None, None, "USUARIO", None, None, "WEXE001"])
    return texto_tasy(pasta / "balancete_honorarios_set2026.xls", linhas)


def _repasse_ame(pasta: Path) -> Path:
    linhas = [["SCF - Repasse Sintetico AME"], [None] * 4 + [UNIDADE_REPASSE],
              [None, None, "Terceiro", None, None, "Nr Repasse", "Dt Ref", "Status", "Vl repasse", "Vl. Líquido"]]
    quantidade, bruto_total, liquido_total = 0, 0.0, 0.0
    for nome, repasses in GRUPOS_REPASSE:
        linhas.append([None, None, f"{nome} - {UNIDADE_REPASSE.title()}"])
        for terceiro, numero, bruto, liquido in repasses:
            linhas.append([None, None, terceiro, None, None, numero, "01/09/2026", "F", bruto, liquido])
        q, b, l = len(repasses), sum(r[2] for r in repasses), sum(r[3] for r in repasses)
        quantidade, bruto_total, liquido_total = quantidade + q, bruto_total + b, liquido_total + l
        linhas.append([None, f"Total - {nome} - {UNIDADE_REPASSE.title()}({q})", None, None, None, None, None, None,
                       b, l])
    linhas.append([None, f"Total({quantidade})", None, None, None, None, None, None, bruto_total, liquido_total])
    linhas.append([None, None, "Impresso em:  08/10/2026", "Página   1", None, None, None, "USUARIO", None,
                   "CATE6095"])
    return texto_tasy(pasta / "repasse_sintetico_set2026.xls", linhas)


# --- Hospital Exemplo ---------------------------------------------------------------------------------------
UNIDADE_HOSPITAL_EXEMPLO = "Fundação Hospital Exemplo"
CONTAS_PF = [
    (11, "Ana Exemplo Médica", 9054.00),          # Senior 6.254,00 + Remoção 2.800,00
    (12, "Bruno Exemplo Médico", 1000.00),        # Senior 900,00: diferença
    (13, "Carla Exemplo Teste", 2340.00),
    (14, "Diego Teste Exemplo", 0.00),            # zerada e sem nada: fica fora (nota)
]
CONTAS_PJ = [
    (21, "Clínica Exemplo Três Ltda", 10000.00),
    (22, "Instituto Exemplo de Cardiologia Ltda", 4560.00),
]
SENIOR_PF = [("1", "ANA EXEMPLO MEDICA", 6254.00), ("2", "BRUNO EXEMPLO MEDICO", 900.00),
             ("3", "CARLA EXEMPLO TESTE", 2340.00), ("4", "EDUARDO SEM CONTA EXEMPLO", 70.00)]
SENIOR_PJ = [("5", "CLINICA EXEMPLO TRES LTDA", 10000.00), ("6", "INSTITUTO EXEMPLO DE CARDIOLOGIA LTDA", 4560.00)]
REMOCAO = [("Ana Exemplo Médica", "700101", 2800.00), ("Pessoa Exemplo Sem Conta", "700102", 300.00)]


def _balancete_hospital_exemplo(pasta: Path, lado: str) -> Path:
    contas, codigo, classificacao, descricao = {
        "PF": (CONTAS_PF, 2131, "2.01.03.01", "HONORARIOS MEDICOS A PAGAR - PF"),
        "PJ": (CONTAS_PJ, 2132, "2.01.03.02", "HONORARIOS MEDICOS A PAGAR - PJ")}[lado]
    linhas = topo_balancete(UNIDADE_HOSPITAL_EXEMPLO, "set/2026")
    linhas.append(conta_balancete(213, "2.01.03", "HONORARIOS MEDICOS A PAGAR", 0))
    linhas.append(conta_balancete(codigo, classificacao, descricao, sum(c[2] for c in contas)))
    for posicao, (codigo_conta, nome, saldo) in enumerate(contas, start=1):
        linhas.append(conta_balancete(codigo_conta, f"{classificacao}.{posicao:04d}", nome, saldo))
    linhas.append([None, "Impresso em: 09/10/2026", None, "WEXE001"])
    return texto_tasy(pasta / f"Balancete {lado}.xls", linhas)


def _senior(pasta: Path, lado: str) -> Path:
    pessoas = SENIOR_PF if lado == "PF" else SENIOR_PJ
    total = numero_br(sum(p[2] for p in pessoas))
    linhas = [[None, "Pág.:", 1], [f"Lançamentos Honorários Médicos em Aberto - {lado}"],
              ["Competência:", "01/1999", "a", "09/2026"]]
    for codigo, nome, saldo in pessoas:
        linhas.append([codigo, nome, "S. Atual:", numero_br(saldo), "Prev. Pgto:", numero_br(saldo), "S. Posterior:", 0])
    linhas += [["S. Atual:", total, "Prev. Pgto:", total, "S. Posterior:", 0], ["Total Geral:"],
               ["FPTE135.COL  -  09/10/2026  -  15:12:38     FUNDAÇÃO HOSPITAL EXEMPLO DE MISER. DE CIDADE ALFA"]]
    return texto_tasy(pasta / f"HM {lado}.XLS", linhas)


def _remocao(pasta: Path) -> Path:
    total = sum(r[2] for r in REMOCAO)
    linhas = ["SCF - Repasse Sintetico AME", "HOSPITAL EXEMPLO",
              "Terceiro Nr Repasse Dt Ref Status Vl repasse Vl. Líquido", "Remoção/Transporte"]
    linhas += [f"{terceiro} {numero} 01/09/2026 F {numero_br(valor)} {numero_br(valor)}"
               for terceiro, numero, valor in REMOCAO]
    linhas += [f"Total - Remoção/Transporte({len(REMOCAO)}) {numero_br(total)} {numero_br(total)}",
               f"Total({len(REMOCAO)}) {numero_br(total)} {numero_br(total)}",
               "Impresso em: 09/10/2026 08:57:48 Página 1"]
    return gravar_pdf(pasta / "Remocao set2026.pdf", [linhas])


def gerar(pasta: Path) -> list[Exemplo]:
    ames = pasta / "AMEs"
    hospital_exemplo = pasta / "Hospital Exemplo"
    arquivos_hospital_exemplo = [_balancete_hospital_exemplo(hospital_exemplo, "PF"), _balancete_hospital_exemplo(hospital_exemplo, "PJ"),
                           _senior(hospital_exemplo, "PF"), _senior(hospital_exemplo, "PJ"), _remocao(hospital_exemplo)]
    saida_ames, saida_hospital_exemplo = ames / "saida", hospital_exemplo / "saida"
    for saida in (saida_ames, saida_hospital_exemplo):
        saida.mkdir(parents=True, exist_ok=True)
    return [
        Exemplo("honorarios_medicos", "honorarios_ames", "AMEs", "ames", {
            "cartao_balancete": [_balancete_ame(ames)], "cartao_repasse": [_repasse_ame(ames)],
            "cartao_pasta": [saida_ames]}, pasta_saida=saida_ames, numeros=("3", "3", "6")),
        Exemplo("honorarios_medicos", "honorarios_hospital_exemplo", "Hospital Exemplo (PF e PJ)", "hospital_exemplo", {
            "cartao_arquivos": arquivos_hospital_exemplo, "cartao_pasta": [saida_hospital_exemplo]},
            pasta_saida=saida_hospital_exemplo, numeros=("4", "2", "6")),
    ]
