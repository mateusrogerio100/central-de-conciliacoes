"""
Testes da Conciliação Honorários Hospital Exemplo (ESPECIFICACAO seção 20).

Arquivos sintéticos com nomes inventados: o balancete é o .xls de texto do Tasy (contas 2131 – PF e
2132 – PJ, num arquivo só ou em dois); o HM Senior real é um .XLS antigo (BIFF2), mas aqui vai como texto
(o leitor aceita os dois); o PDF do SCF – Repasse Sintético entra como o texto que o pdfplumber tira.

Gabaritos com os arquivos reais (pulados se exemplos/ não existir):
- set/2026: os relatórios do Tasy (balancete PF e PJ .xls, HM PF e PJ .XLS, 6095 e Remoção em PDF);
- ago/2026: a planilha montada à mão pelo usuário — as contas, o Senior e o PDF do 6095 de agosto entram no
  pareamento e cada par tem de sair igual ao dele.
"""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import load_workbook

from modulos.honorarios_medicos.ames.modelos import ContaHonorario
from modulos.honorarios_medicos.hospital_exemplo import arquivos_da_pasta, numeros_principais, processar_honorarios_hospital_exemplo
from modulos.honorarios_medicos.hospital_exemplo.leitores import (
    ARQUIVO_BALANCETE,
    ARQUIVO_SENIOR,
    identificar_arquivo,
    ler_balancete_hospital_exemplo,
    ler_repasse_do_texto,
    ler_repasse_pdf,
    ler_senior,
)
from modulos.honorarios_medicos.hospital_exemplo.modelos import (
    PAREAMENTO_VALOR,
    SITUACAO_DIVERGENTE,
    SITUACAO_OK,
    SITUACAO_SO_BALANCETE,
    SITUACAO_SO_SENIOR,
    LancamentoSenior,
    LeituraRepassePdf,
)
from modulos.honorarios_medicos.hospital_exemplo.pareamento import agrupar_terceiros, parear_hospital_exemplo
from modulos.honorarios_medicos.hospital_exemplo.relatorio_excel import ABA_REMOCAO, ABA_RESUMO, ABAS_LADO

from testes.conftest import PASTA_EXEMPLOS
from testes.honorarios_medicos.apoio_fornecedores import _conta, _topo_balancete, texto_tasy

PASTA_HONORARIOS = PASTA_EXEMPLOS / "honorarios_medicos" / "Exemplos_Honorarios"
D = Decimal
UNIDADE = "Fundação Hospital Exemplo"
PASTA_HOSPITAL_EXEMPLO = PASTA_HONORARIOS / "Conciliações Hospital Exemplo"
# ago/2026 (planilha do usuário e PDFs): fica ao lado de "Conciliações Hospital Exemplo" (antes ficava dentro)
PASTA_AGOSTO = next((p for p in (PASTA_HONORARIOS / "08-09", PASTA_HOSPITAL_EXEMPLO / "08-09") if p.exists()),
                    PASTA_HONORARIOS / "08-09")


# ---------------------------------------------------------------------
# Arquivos sintéticos
# ---------------------------------------------------------------------
def linhas_balancete(pf=None, pj=None, mes="set/2026"):
    """pf / pj: [(codigo, descricao, saldo)] — None = conta fora do arquivo."""
    linhas = _topo_balancete(UNIDADE, mes)
    linhas.append(_conta(213, "2.01.03", "HONORARIOS MEDICOS A PAGAR", 0))
    for contas, codigo, classificacao, descricao in ((pf, 2131, "2.01.03.01", "HONORARIOS MEDICOS A "),
                                                     (pj, 2132, "2.01.03.02", "HONORARIOS MEDICOS A PAGAR - PJ")):
        if contas is None:
            continue
        linhas.append(_conta(codigo, classificacao, descricao, sum(c[2] for c in contas)))
        for posicao, (codigo_conta, nome, saldo) in enumerate(contas, start=1):
            linhas.append(_conta(codigo_conta, f"{classificacao}.{posicao:04d}", nome, saldo))
    linhas.append([None, "Impresso em: 19/10/2026", None, "WEXE001"])
    return linhas


def linhas_senior(lado, pessoas, competencia="09/2026", total=None):
    """pessoas: [(codigo, nome, saldo "625,40")]; total None = soma."""
    if total is None:
        total = _reais(sum(D(p[2].replace(".", "").replace(",", ".")) for p in pessoas))
    linhas = [[None, "Pág.:", 1],
              [f"Lançamentos Honorários Médicos em Aberto - {lado}"],
              ["Competência:", "01/1999", "a", competencia]]
    for codigo, nome, saldo in pessoas:
        linhas.append([codigo, nome, "S. Atual:", saldo, "Prev. Pgto:", saldo, "S. Posterior:", 0])
    linhas.append(["S. Atual:", total, "Prev. Pgto:", total, "S. Posterior:", 0])
    linhas.append(["Total Geral:"])
    linhas.append(["FPTE135.COL  -  19/10/2026  -  15:12:38     FUNDAÇÃO HOSPITAL EXEMPLO DE MISER. DE CIDADE ALFA"])
    return linhas


def _reais(valor) -> str:
    texto = f"{D(str(valor)):,.2f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


def pagina_repasse(grupos, total=True, dt_ref="01/09/2026"):
    """grupos: [(nome, [(terceiro, numero, valor)])] → texto de uma página do SCF – Repasse Sintético."""
    linhas = ["SCF - Repasse Sintetico AME", "HOSPITAL EXEMPLO",
              "Terceiro Nr Repasse Dt Ref Status Vl repasse Vl. Líquido"]
    soma, quantidade = D(0), 0
    for nome, repasses in grupos:
        linhas.append(nome)
        for terceiro, numero, valor in repasses:
            linhas.append(f"{terceiro} {numero} {dt_ref} F {_reais(valor)} {_reais(valor)}")
            soma += D(str(valor))
            quantidade += 1
        if total:
            subtotal = sum(D(str(v)) for _t, _n, v in repasses)
            linhas.append(f"Total - {nome}({len(repasses)}) {_reais(subtotal)} {_reais(subtotal)}")
    if total:
        linhas.append(f"Total({quantidade}) {_reais(soma)} {_reais(soma)}")
    linhas.append("IImmpprreessssoo eemm:: 0099//1100//22002266 0088::5577::4488 PP��ggiinnaa 11 LLAAMMOONNTTEEIIRROO")
    return "\n".join(linhas)


def ler_paginas(paginas) -> LeituraRepassePdf:
    return ler_repasse_do_texto(paginas, LeituraRepassePdf(arquivo="teste.pdf"))


def _conta_obj(codigo, nome, saldo):
    return ContaHonorario(codigo=str(codigo), classificacao=f"2.01.03.0x.{codigo}", descricao=nome,
                          saldo_anterior=D(0), debitos=D(0), creditos=D(0), saldo_atual=D(str(saldo)))


def _senior_obj(lado, nome, saldo, codigo="1"):
    return LancamentoSenior(lado=lado, codigo=codigo, nome=nome, saldo=D(str(saldo)))


def _repasses(*itens):
    pagina = pagina_repasse([("Remoção/Transporte", [(t, 100 + i, v) for i, (t, v) in enumerate(itens)])])
    return ler_paginas([pagina]).repasses


@pytest.fixture
def pdf_falso(monkeypatch):
    """Troca o pdfplumber por textos sintéticos: {nome do arquivo: [páginas]}."""
    import modulos.honorarios_medicos.hospital_exemplo.leitores as leitores

    textos: dict[str, list[str]] = {}

    def paginas(caminho):
        return textos[Path(caminho).name]

    class Pagina:
        def __init__(self, texto):
            self.texto = texto

        def extract_text(self):
            return self.texto

    class Pdf:
        def __init__(self, caminho):
            self.pages = [Pagina(t) for t in textos[Path(caminho).name]]

        def __enter__(self):
            return self

        def __exit__(self, *erro):
            return False

    import pdfplumber

    monkeypatch.setattr(leitores, "paginas_do_pdf", paginas)
    monkeypatch.setattr(pdfplumber, "open", Pdf)

    def criar(pasta: Path, nome: str, paginas_texto: list[str]) -> Path:
        caminho = pasta / nome
        caminho.write_bytes(b"%PDF-1.4 sintetico " + nome.encode())
        textos[nome] = paginas_texto
        return caminho

    return criar


# ---------------------------------------------------------------------
# Leitores
# ---------------------------------------------------------------------
def test_balancete_com_pf_e_pj_no_mesmo_arquivo(tmp_path):
    caminho = texto_tasy(tmp_path, "Balancete.xls", linhas_balancete(
        pf=[(23701, "Médica Um da Silva", 25.60), (23536, "Médico Dois Souza", 16.80)],
        pj=[(20704, "Clínica Três Ltda", 7020.00)]))
    leitura = ler_balancete_hospital_exemplo(caminho)
    assert leitura.erro is None
    assert leitura.mes == date(2026, 9, 1)
    assert {lado: t.codigo for lado, t in leitura.totais.items()} == {"PF": "2131", "PJ": "2132"}
    assert [c.codigo for c in leitura.contas["PF"]] == ["23701", "23536"]
    assert leitura.totais["PF"].saldo_atual == D("42.40")
    assert [c.descricao for c in leitura.contas["PJ"]] == ["Clínica Três Ltda"]
    assert identificar_arquivo(caminho) == ARQUIVO_BALANCETE


def test_balancete_so_pf(tmp_path):
    caminho = texto_tasy(tmp_path, "Balancete PF.xls", linhas_balancete(pf=[(1, "Médica Um", 10)]))
    leitura = ler_balancete_hospital_exemplo(caminho)
    assert leitura.erro is None and list(leitura.totais) == ["PF"]


def test_balancete_soma_errada_gera_atencao(tmp_path):
    linhas = linhas_balancete(pf=[(1, "Médica Um", 10), (2, "Médico Dois", 20)])
    linhas[6][-1] = 999          # Saldo Atual da 2131
    leitura = ler_balancete_hospital_exemplo(texto_tasy(tmp_path, "B.xls", linhas))
    assert any(a.mensagem.startswith("ATENÇÃO: a soma") for a in leitura.avisos)


def test_senior_em_texto(tmp_path):
    caminho = texto_tasy(tmp_path, "HM PF.XLS", linhas_senior("PF", [
        ("93435", "MEDICA UM DA SILVA", "625,40"), ("90846", "MÉDICO DOIS SOUZA", "50,40")], total="675,80"))
    assert identificar_arquivo(caminho) == ARQUIVO_SENIOR
    leitura = ler_senior(caminho)
    assert leitura.erro is None and leitura.avisos == []
    assert leitura.lado == "PF" and leitura.mes == date(2026, 9, 1)
    assert [(l.codigo, l.nome, l.saldo) for l in leitura.lancamentos] == [
        ("93435", "MEDICA UM DA SILVA", D("625.40")), ("90846", "MÉDICO DOIS SOUZA", D("50.40"))]
    assert leitura.total_impresso == D("675.80")


def test_senior_total_que_nao_bate(tmp_path):
    caminho = texto_tasy(tmp_path, "HM PJ.XLS", linhas_senior("PJ", [("1", "CLINICA UM LTDA", "10,00")],
                                                              total="11,00"))
    leitura = ler_senior(caminho)
    assert leitura.lado == "PJ"
    assert any(a.mensagem.startswith("ATENÇÃO: a soma do S. Atual") for a in leitura.avisos)


def test_pdf_de_repasse_pula_outras_paginas_e_confere_total():
    paginas = [
        pagina_repasse([("Remoção/Transporte", [("Médica Um da Silva", 289263, 280),
                                                ("Clínica Três Ltda", 289252, 1000)])]),
        "Filtros\nCompetência: 09/2026;\nRepasses Gerados no Período\n4963 Médica Um da Silva 2,00 280,00",
        "Nota Fiscal de Débito\nFundacao Hospital Exemplo\nValor 280,00",
    ]
    leitura = ler_paginas(paginas)
    assert leitura.erro is None and leitura.avisos == []
    assert leitura.unidade == "HOSPITAL EXEMPLO" and leitura.mes == date(2026, 9, 1)
    assert leitura.grupos == ["Remoção/Transporte"]
    assert [(r.terceiro, r.numero, r.bruto) for r in leitura.repasses] == [
        ("Médica Um da Silva", "289263", D("280.00")), ("Clínica Três Ltda", "289252", D("1000.00"))]


def test_pdf_sem_total_so_avisa():
    leitura = ler_paginas([pagina_repasse([("Deslocamento", [("Clínica Três Ltda", 1, 504)])], total=False)])
    assert leitura.erro is None and len(leitura.repasses) == 1
    assert [a.mensagem for a in leitura.avisos] == [
        "O PDF não traz a linha Total(n); a leitura não pôde ser conferida pelo total."]


def test_pdf_com_linha_perdida_gera_atencao():
    pagina = pagina_repasse([("Deslocamento", [("Clínica Três Ltda", 1, 504), ("Médica Um", 2, 100)])])
    pagina = pagina.replace("Médica Um 2 01/09/2026 F 100,00 100,00", "Médica Um 2 x 100,00")
    leitura = ler_paginas([pagina])
    assert any(a.mensagem.startswith("Linha não reconhecida") for a in leitura.avisos)
    assert any(a.mensagem.startswith("ATENÇÃO: 1 repasse(s) lido(s)") for a in leitura.avisos)


def test_pdf_que_nao_e_repasse():
    leitura = ler_paginas(["Nota Fiscal de Débito\nFundacao Hospital Exemplo"])
    assert leitura.erro and "não é o relatório SCF" in leitura.erro


def pagina_pagamento(terceiro, numero, *valores):
    """Uma página do Demonstrativo de Valores a Pagar (Rel. 6203)."""
    linhas = ["Demonstrativo de Valores a Pagar",
              "Fundacao Hospital Exemplo CNPJ: 00.000.000/0001-00",
              "Praça Exemplo, 100, 14400000, Cidade Alfa-SP",
              f"Repasse : {numero} Status : Fechado",
              f"Terceiro : {terceiro} CNPJ : 11.111.111/0001-11",
              "DESCRIÇÃO OBRIGATÓRIA PARA NOTA FISCAL",
              "Pagamento de interconsulta",
              "Tipo Descrição Qtde Vl Repasse"]
    linhas += [f"Repasse Item Pagamento De Interconsulta Para Paciente 1,00 {_reais(v)}" for v in valores]
    linhas.append("IImmpprreessssoo eemm:: 1188//0099//22002266 PP��ggiinnaa 11 CCAATTEE66220033")
    return "\n".join(linhas)


def test_pagamento_particular_soma_os_itens():
    leitura = ler_paginas([pagina_pagamento("Clínica Quatro Eireli", 284139, 500, 250.50),
                           pagina_pagamento("Médica Cinco", 284140, 100)])
    assert leitura.erro is None
    assert leitura.unidade == "Fundacao Hospital Exemplo" and leitura.mes is None
    assert [(r.grupo, r.terceiro, r.numero, r.status, r.bruto) for r in leitura.repasses] == [
        ("Pagamento particular", "Clínica Quatro Eireli", "284139", "Fechado", D("750.50")),
        ("Pagamento particular", "Médica Cinco", "284140", "Fechado", D("100.00"))]
    assert [a.mensagem for a in leitura.avisos] == [
        "O Demonstrativo de Valores a Pagar (Rel. 6203) não traz a competência; confira se ele é do mesmo mês do "
        "balancete."]


def test_pagamento_particular_incompleto_gera_atencao():
    leitura = ler_paginas([pagina_pagamento("Clínica Quatro Eireli", 1)])          # sem itens
    assert leitura.repasses == []
    assert any(a.mensagem.startswith("ATENÇÃO: uma página do Demonstrativo") for a in leitura.avisos)


# ---------------------------------------------------------------------
# Pareamento
# ---------------------------------------------------------------------
def test_remocao_vai_para_a_conta_do_lado_certo():
    contas = {"PF": [_conta_obj(1, "Beatriz Exemplo", 625.40)],
              "PJ": [_conta_obj(2, "Beatriz Exemplo Medicina e Saúde Ltda", 895.40)]}
    senior = {"PF": [_senior_obj("PF", "BEATRIZ EXEMPLO", 625.40)],
              "PJ": [_senior_obj("PJ", "BEATRIZ EXEMPLO MEDICINA E SAUDE LTDA", 625.40)]}
    terceiros = agrupar_terceiros(_repasses(("Beatriz Exemplo Medicina E Saude Ltda", 270)))
    resultado = parear_hospital_exemplo(contas, senior, terceiros)
    pf, pj = resultado.linhas["PF"][0], resultado.linhas["PJ"][0]
    assert pf.situacao == SITUACAO_OK and not pf.remocao
    assert pj.situacao == SITUACAO_OK and pj.valor_remocao == D("270.00") and pj.acertada_pela_remocao
    assert pj.senior_ajustado == D("895.40")


def test_senior_pf_nunca_casa_com_conta_pj():
    contas = {"PF": [], "PJ": [_conta_obj(2, "Ana Teste Serviços Médicos Ltda", 500)]}
    senior = {"PF": [_senior_obj("PF", "ANA TESTE", 500)], "PJ": []}
    resultado = parear_hospital_exemplo(contas, senior, [])
    assert [l.situacao for l in resultado.linhas["PJ"]] == [SITUACAO_SO_BALANCETE]
    assert [l.situacao for l in resultado.linhas["PF"]] == [SITUACAO_SO_SENIOR]


def _conferir_conta_fechada_pela_remocao(clinica, outra_conta, nome_senior):
    contas = {"PJ": [_conta_obj(1, clinica, 390),
                     _conta_obj(2, outra_conta, 52417.50)]}
    senior = {"PJ": [_senior_obj("PJ", nome_senior, 52417.50)]}
    terceiros = agrupar_terceiros(_repasses((clinica, 390)))
    linhas = parear_hospital_exemplo(contas, senior, terceiros).linhas["PJ"]
    assert linhas[0].situacao == SITUACAO_OK and not linhas[0].senior
    assert linhas[1].situacao == SITUACAO_OK and linhas[1].nome_senior == nome_senior
    assert linhas[1].pareamento == PAREAMENTO_VALOR


def test_conta_fechada_pela_remocao_nao_recebe_senior():
    # nomes com "Serviços Médicos" dão nota alta a clínicas diferentes (set/2026: 0,86)
    # (nomes fictícios com as mesmas notas do caso original, que está em casos_reais.json: teste abaixo)
    _conferir_conta_fechada_pela_remocao("Vila Serviços Medicos Ltda", "Fulano Ciclano Vilano Clínica Médica",
                                         "VILANO SERVIÇOS MEDICOS LTDA")


def test_conta_fechada_pela_remocao_caso_real():
    """O mesmo teste com os nomes do teste original do Conciliações AMES (parte de um nome real: fica em
    exemplos/honorarios_medicos/casos_reais.json, fora do git)."""
    arquivo = PASTA_EXEMPLOS / "honorarios_medicos" / "casos_reais.json"
    if not arquivo.exists():
        pytest.skip("exemplos/honorarios_medicos/casos_reais.json não existe (dados reais ficam fora do git)")
    caso = json.loads(arquivo.read_text(encoding="utf-8"))["conta_fechada_pela_remocao"]
    _conferir_conta_fechada_pela_remocao(caso["clinica"], caso["outra_conta"], caso["nome_senior"])


def test_valor_unico_casa_nomes_diferentes():
    # "I N C" são as iniciais da médica: nota baixa, mas o valor só existe uma vez dos dois lados
    contas = {"PJ": [_conta_obj(1, "Dra Iara Exemplo de Castro", 3842.97),
                     _conta_obj(2, "Outra Clinica Medica Ltda", -500)]}
    senior = {"PJ": [_senior_obj("PJ", "I N C CLINICA MEDICA LTDA", 3842.97)]}
    linhas = parear_hospital_exemplo(contas, senior, []).linhas["PJ"]
    assert linhas[0].situacao == SITUACAO_OK and linhas[0].pareamento == PAREAMENTO_VALOR
    assert linhas[1].situacao == SITUACAO_SO_BALANCETE


def test_nome_mais_ou_menos_parecido_so_entre_as_sobras():
    contas = {"PJ": [_conta_obj(1, "Clínica Alfa Beta Gama", 100)]}
    senior = {"PJ": [_senior_obj("PJ", "CLINICA ALFA BETA GAMA DELTA EPSILON", 90)]}
    linha = parear_hospital_exemplo(contas, senior, []).linhas["PJ"][0]
    assert linha.situacao == SITUACAO_DIVERGENTE and linha.diferenca == D("10.00")


def test_dois_pdfs_do_mesmo_terceiro_somam():
    contas = {"PF": [_conta_obj(1, "Carla Exemplo Teste", 2500)]}
    terceiros = agrupar_terceiros(_repasses(("Carla Exemplo Teste", 1000), ("Carla Exemplo Teste", 1500)))
    linha = parear_hospital_exemplo(contas, {"PF": []}, terceiros).linhas["PF"][0]
    assert linha.situacao == SITUACAO_OK and linha.valor_remocao == D("2500.00")


# ---------------------------------------------------------------------
# Processamento completo (arquivos sintéticos)
# ---------------------------------------------------------------------
def _pasta_completa(pasta: Path, pdf_falso, mes_pdf="01/09/2026"):
    (pasta / "PF").mkdir()
    (pasta / "PJ").mkdir()
    texto_tasy(pasta / "PF", "Balancete PF.xls", linhas_balancete(pf=[
        (11, "Médica Um da Silva", 905.40), (12, "Médico Dois Souza", 100), (13, "Zerada Teste", 0),
        (14, "Médica Cruzada Teste", 50)]))
    texto_tasy(pasta / "PJ", "Balancete PJ.xls", linhas_balancete(pj=[
        (21, "Clínica Três Ltda", 1000), (22, "Médica Cruzada Teste Odontologia", -50)]))
    texto_tasy(pasta / "PF", "HM PF.XLS", linhas_senior("PF", [
        ("1", "MEDICA UM DA SILVA", "625,40"), ("2", "MEDICO DOIS SOUZA", "90,00"), ("3", "SEM CONTA TESTE", "7,00")]))
    texto_tasy(pasta / "PJ", "HM PJ.XLS", linhas_senior("PJ", [("4", "CLINICA TRES LTDA", "1.000,00")]))
    pdf_falso(pasta / "PF", "Remocao.pdf", [pagina_repasse(
        [("Remoção/Transporte", [("Médica Um da Silva", 1, 280), ("Pessoa Sem Conta", 2, 30)])],
        dt_ref=mes_pdf)])
    pdf_falso(pasta / "PF", "Balancete PF.pdf", ["Balancete\nqualquer coisa"])
    (pasta / "anotacoes.txt").write_text("não é relatório", encoding="utf-8")


def test_processar_pasta_completa(tmp_path, pdf_falso):
    _pasta_completa(tmp_path, pdf_falso)
    resultado = processar_honorarios_hospital_exemplo([tmp_path], pasta_destino=tmp_path)
    assert resultado.erro is None
    assert resultado.lados == ["PF", "PJ"] and resultado.mes == date(2026, 9, 1)
    pf = {l.conta.codigo if l.conta else l.nome_senior: l for l in resultado.linhas["PF"]}
    assert pf["11"].situacao == SITUACAO_OK and pf["11"].acertada_pela_remocao
    assert pf["12"].situacao == SITUACAO_DIVERGENTE and pf["12"].diferenca == D("10.00")
    assert "13" not in pf                                     # saldo zero e sem nada: fora (nota)
    assert pf["SEM CONTA TESTE"].situacao == SITUACAO_SO_SENIOR
    assert resultado.remocao_do_lado("PF") == D("280.00")
    assert [r.terceiro for r in resultado.repasses_sem_conta] == ["Pessoa Sem Conta"]
    assert numeros_principais(resultado).linhas == 6            # PF: 3 contas + 1 só no Senior; PJ: 2

    notas = " ".join(resultado.notas)
    assert "Zerada Teste" in notas and "Pessoa Sem Conta" in notas
    assert "se anulam entre PF e PJ" in notas
    mensagens = {a.arquivo: a.mensagem for a in resultado.avisos}
    assert "ficou de fora" in mensagens["Balancete PF.pdf"]
    assert "não reconhecido" in mensagens["anotacoes.txt"]

    livro = load_workbook(resultado.caminho_relatorio)
    assert livro.sheetnames == [ABA_RESUMO, ABAS_LADO["PF"], ABAS_LADO["PJ"], ABA_REMOCAO]
    aba_pf = livro[ABAS_LADO["PF"]]
    assert aba_pf["B4"].value == "Nome (Contábil)" and aba_pf["N4"].value == "Situação"
    assert aba_pf["I5"].value == '=IF(G5="",0,G5)+IF(H5="",0,H5)' and aba_pf["J5"].value == "=D5-I5"
    assert aba_pf["H5"].value == 280 and aba_pf["K5"].value == "Médica Um da Silva"
    assert aba_pf["B5"].fill.fgColor.rgb.endswith("DDEBF7")             # azul: acertada pela Remoção
    assert aba_pf["B6"].fill.fgColor.rgb.endswith("FFC7CE")             # vermelho: diverge
    resumo = livro[ABA_RESUMO]
    linha_total = next(c.row for c in aba_pf["B"] if c.value == "TOTAL")
    assert aba_pf[f"D{linha_total}"].value == f"=SUM(D5:D{linha_total - 1})"
    assert resumo["D6"].value == f"='{ABAS_LADO['PF']}'!D{linha_total}"
    remocao = livro[ABA_REMOCAO]
    assert [remocao.cell(row=r, column=2).value for r in (6, 7)] == ["PF", "Sem conta"]
    assert resultado.caminho_relatorio.name == "Conciliacao_Honorarios_Medicos_PF_PJ_09_2026.xlsx"

    # rodar de novo não sobrescreve, e a planilha gerada não é lida como relatório
    assert all(not p.name.startswith("Conciliacao_") for p in arquivos_da_pasta(tmp_path))
    de_novo = processar_honorarios_hospital_exemplo([tmp_path], pasta_destino=tmp_path)
    assert de_novo.caminho_relatorio.name == "Conciliacao_Honorarios_Medicos_PF_PJ_09_2026_2.xlsx"


def test_pdf_de_outro_mes_fica_de_fora(tmp_path, pdf_falso):
    _pasta_completa(tmp_path, pdf_falso, mes_pdf="01/08/2026")
    resultado = processar_honorarios_hospital_exemplo([tmp_path], pasta_destino=tmp_path)
    assert resultado.erro is None and resultado.repasses == []
    assert any("ago/2026" in n and "ficou de fora" in n for n in resultado.notas)


def test_dois_hm_pf_nao_gera(tmp_path, pdf_falso):
    _pasta_completa(tmp_path, pdf_falso)
    texto_tasy(tmp_path, "HM PF outro.XLS", linhas_senior("PF", [("9", "OUTRA PESSOA", "1,00")]))
    resultado = processar_honorarios_hospital_exemplo([tmp_path], pasta_destino=tmp_path)
    assert resultado.erro and "dois relatórios HM PF" in resultado.erro


def test_sem_balancete_nao_gera(tmp_path):
    texto_tasy(tmp_path, "HM PF.XLS", linhas_senior("PF", [("1", "MEDICA UM", "1,00")]))
    resultado = processar_honorarios_hospital_exemplo([tmp_path / "HM PF.XLS"], pasta_destino=tmp_path)
    assert resultado.erro and "nenhum balancete" in resultado.erro


def test_pagamento_particular_entra_na_soma(tmp_path, pdf_falso):
    _pasta_completa(tmp_path, pdf_falso)
    texto_tasy(tmp_path / "PJ", "Balancete PJ.xls", linhas_balancete(pj=[
        (21, "Clínica Três Ltda", 1000), (22, "Médica Cruzada Teste Odontologia", -50),
        (23, "Clínica Quatro Eireli", 500)]))
    pdf_falso(tmp_path, "Rel 6203.pdf", [pagina_pagamento("Clínica Quatro Eireli", 284139, 500)])
    resultado = processar_honorarios_hospital_exemplo([tmp_path], pasta_destino=tmp_path)
    assert resultado.erro is None
    linha = next(l for l in resultado.linhas["PJ"] if l.conta and l.conta.codigo == "23")
    assert linha.situacao == SITUACAO_OK and linha.acertada_pela_remocao
    assert linha.nome_remocao == "Clínica Quatro Eireli"
    assert resultado.remocao_do_lado("PJ") == D("500.00")
    assert any(n.startswith("Pagamento particular (Rel. 6203): 1 repasse, R$ 500,00, de Rel 6203.pdf")
               and "confira se ele é do mesmo mês" in n for n in resultado.notas)
    remocao = load_workbook(resultado.caminho_relatorio)[ABA_REMOCAO]
    assert "Rel. 6203" in remocao["B2"].value
    assert any(remocao.cell(row=r, column=3).value == "Pagamento particular" for r in range(6, 10))


def test_mesmo_arquivo_duas_vezes_conta_uma(tmp_path, pdf_falso):
    _pasta_completa(tmp_path, pdf_falso)
    arquivo = tmp_path / "PF" / "Remocao.pdf"
    resultado = processar_honorarios_hospital_exemplo([tmp_path, arquivo], pasta_destino=tmp_path)
    assert resultado.erro is None and len(resultado.repasses) == 2


# ---------------------------------------------------------------------
# Gabaritos com os arquivos reais
# ---------------------------------------------------------------------
precisa_exemplos = pytest.mark.skipif(not PASTA_HOSPITAL_EXEMPLO.exists(), reason="exemplos/ não disponível")


@precisa_exemplos
def test_gabarito_set2026(tmp_path):
    resultado = processar_honorarios_hospital_exemplo([PASTA_HOSPITAL_EXEMPLO / "PF", PASTA_HOSPITAL_EXEMPLO / "PJ"],
                                                pasta_destino=tmp_path)
    assert resultado.erro is None
    assert resultado.mes == date(2026, 9, 1)
    assert resultado.totais_balancete == {"PF": D("83748.35"), "PJ": D("5838244.51")}
    assert resultado.totais_senior == {"PF": D("73910.75"), "PJ": D("5805551.05")}
    assert len(resultado.repasses) == 19 and resultado.total_remocao == D("16294.00")
    assert resultado.repasses_sem_conta == []
    assert resultado.remocao_do_lado("PF") + resultado.remocao_do_lado("PJ") == D("16294.00")

    contagem = {lado: {s: sum(1 for l in resultado.linhas[lado] if l.situacao == s)
                       for s in (SITUACAO_OK, SITUACAO_DIVERGENTE, SITUACAO_SO_BALANCETE, SITUACAO_SO_SENIOR)}
                for lado in ("PF", "PJ")}
    assert contagem["PF"] == {SITUACAO_OK: 60, SITUACAO_DIVERGENTE: 2, SITUACAO_SO_BALANCETE: 5,
                              SITUACAO_SO_SENIOR: 0}
    assert contagem["PJ"] == {SITUACAO_OK: 305, SITUACAO_DIVERGENTE: 13, SITUACAO_SO_BALANCETE: 3,
                              SITUACAO_SO_SENIOR: 0}
    assert sum(1 for l in resultado.linhas["PF"] if l.acertada_pela_remocao) == 7
    assert sum(1 for l in resultado.linhas["PJ"] if l.acertada_pela_remocao) == 11
    assert [l.conta.codigo for lado in ("PF", "PJ") for l in resultado.linhas[lado]
            if l.pareamento == PAREAMENTO_VALOR] == ["27629", "201782"]
    # contábil − Senior − Remoção = soma das diferenças, nos dois lados
    for lado in ("PF", "PJ"):
        assert sum(l.diferenca for l in resultado.linhas[lado]) == (
            resultado.totais_balancete[lado] - resultado.totais_senior[lado] - resultado.remocao_do_lado(lado))
    assert not any(a.mensagem.startswith("ATENÇÃO") for a in resultado.avisos)


@precisa_exemplos
def test_leitores_com_os_arquivos_reais():
    senior = ler_senior(PASTA_HOSPITAL_EXEMPLO / "PF" / "HM PF Senior 09-2026.XLS")       # .XLS antigo (BIFF2)
    assert senior.erro is None and senior.lado == "PF" and len(senior.lancamentos) == 56
    assert senior.total == senior.total_impresso == D("73910.75")
    remocao = ler_repasse_pdf(PASTA_HOSPITAL_EXEMPLO / "PF" / "ok- TASY - Remocao - 09.26 - ok.pdf")
    assert remocao.erro is None and remocao.avisos == []
    assert len(remocao.repasses) == 18 and remocao.total_bruto == D("15790.00")
    if not PASTA_AGOSTO.exists():
        return
    particular = ler_repasse_pdf(PASTA_AGOSTO / "Remoções 08-2026" /
                                 "Pagamento particular - Tasy - Rel 6203.pdf")
    assert particular.erro is None and len(particular.repasses) == 1
    assert particular.repasses[0].numero == "284139" and particular.total_bruto == D("500.00")


@pytest.mark.skipif(not PASTA_AGOSTO.exists(), reason="exemplos de ago/2026 não disponíveis")
def test_gabarito_ago2026_igual_a_planilha_do_usuario():
    """Cada par (Senior e Remoção) e cada diferença saem iguais à planilha feita à mão em ago/2026."""
    pasta = PASTA_AGOSTO
    livro = load_workbook(pasta / "Conciliacao_Honorarios_Medicos_PF_PJ_08_2026_1.xlsx")
    contas, senior, esperado = {}, {}, {}
    for lado in ("PF", "PJ"):
        aba = livro[f"{lado} - Conciliação"]
        contas[lado], senior[lado] = [], []
        for linha in aba.iter_rows(min_row=5, min_col=2, max_col=13, values_only=True):
            nome, codigo, saldo, nome_senior, codigo_senior, saldo_senior, remocao = linha[:7]
            if not codigo or not isinstance(saldo, (int, float)):
                continue
            contas[lado].append(_conta_obj(codigo, nome, saldo))
            esperado[(lado, codigo)] = (nome_senior, linha[9], D(str(saldo)) - D(str(saldo_senior or 0))
                                        - D(str(remocao or 0)))
            if nome_senior:
                senior[lado].append(_senior_obj(lado, nome_senior, saldo_senior, codigo_senior))
    repasses = ler_repasse_pdf(pasta / "Remoções 08-2026" / "Remoção e Deslocamento - Rel 6095 (1).pdf").repasses
    assert sum(r.bruto for r in repasses) == D("25858.00")

    resultado = parear_hospital_exemplo(contas, senior, agrupar_terceiros(repasses))
    assert resultado.terceiros_sem_conta == []
    for lado in ("PF", "PJ"):
        assert all(l.conta is not None for l in resultado.linhas[lado])
        for linha in resultado.linhas[lado]:
            nome_senior, nome_remocao, diferenca = esperado[(lado, linha.conta.codigo)]
            assert (linha.nome_senior or None) == nome_senior, linha.conta.descricao
            assert (linha.nome_remocao.casefold() or None) == (nome_remocao.casefold() if nome_remocao else None)
            assert linha.diferenca == diferenca.quantize(D("0.01")), linha.conta.descricao
