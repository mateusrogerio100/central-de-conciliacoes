import hashlib
import re
import zipfile
from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest

from modulos.subvencoes.conciliacao import conciliar
from modulos.subvencoes.leitor_balancete import ler_balancete
from modulos.subvencoes.leitor_patrimonio import ler_patrimonio
from modulos.subvencoes.modelos import ErroArquivo, Gravidade, MesReferencia, ResultadoLinha
from modulos.subvencoes.preenchedor import caminho_destino, gravar_planilha, ler_estrutura_planilha
from testes.subvencoes.conftest import arquivos_do_mes, ler_gabarito

NOMES_GABARITO = {"Subvenções_Investimento": "subvencoes", "Projetos": "projetos"}


def _celulas_com_aviso(planilha, tipo):
    return {(a.aba, re.match(r"Célula (\w+)", a.mensagem).group(1)) for a in planilha.avisos if a.tipo == tipo}


def _hash(caminho):
    return hashlib.sha256(Path(caminho).read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Estrutura
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("qual", ["subvencoes", "projetos"])
def test_linhas_de_conta_iguais_ao_gabarito(arquivos, qual):
    planilha = ler_estrutura_planilha(getattr(arquivos, qual))
    esperado = [(l["aba"], l["linha"], l["conta_contabil"], l["convenio"])
                for l in ler_gabarito(arquivos.gabarito) if NOMES_GABARITO[l["planilha"]] == qual]
    obtido = [(a.nome, l.linha, l.conta_contabil, l.convenio) for a in planilha.abas for l in a.linhas]
    assert obtido == esperado
    assert planilha.abas_sem_contas == []


def test_titulos_localizados_pelo_texto(arquivos):
    subvencoes = ler_estrutura_planilha(arquivos.subvencoes)
    assert {a.nome: a.linha_titulos for a in subvencoes.abas} == {
        "Federal Investimento": 4, "Estadual Investimento": 4, "Municipal Investimento": 4}
    projetos = ler_estrutura_planilha(arquivos.projetos)
    assert [a.linha_titulos for a in projetos.abas] == [8]


def test_avisos_r12_subvencoes(arquivos):
    planilha = ler_estrutura_planilha(arquivos.subvencoes)
    assert _celulas_com_aviso(planilha, "vínculo externo") == {
        ("Federal Investimento", c) for c in ["D81", "D85", "D86", "D87", "D88"]}
    # D35 = SUM(D5:D33) sem a linha 34: corrigido na cópia (decisão do usuário na Etapa 6)
    assert _celulas_com_aviso(planilha, "fórmula de total corrigida") == {("Estadual Investimento", "D35")}
    assert _celulas_com_aviso(planilha, "fórmula de total incompleta") == set()
    assert all(a.gravidade == Gravidade.ATENCAO for a in planilha.avisos)
    aviso_d35 = next(a for a in planilha.avisos if a.tipo == "fórmula de total corrigida")
    assert "34" in aviso_d35.mensagem and "=SUM(D5:D34)" in aviso_d35.mensagem
    estadual = next(a for a in planilha.abas if a.nome == "Estadual Investimento")
    assert [(c.celula, c.formula_original, c.formula_corrigida) for c in estadual.correcoes_formula] == [
        ("D35", "=SUM(D5:D33)", "=SUM(D5:D34)")]
    assert all(not a.correcoes_formula for a in planilha.abas if a.nome != "Estadual Investimento")


def test_avisos_r12_projetos(arquivos, mes_exemplo):
    """Julho: D24 = SUM(D9:D22) deixa de fora a linha 23. Agosto: já corrigido (D9:D23)."""
    planilha = ler_estrutura_planilha(arquivos.projetos)
    esperado = {("PROJETOS 1", "D24")} if mes_exemplo == "2026-07" else set()
    assert _celulas_com_aviso(planilha, "fórmula de total corrigida") == esperado
    assert _celulas_com_aviso(planilha, "fórmula de total incompleta") == set()
    corrigidas = [(c.celula, c.formula_corrigida) for c in planilha.abas[0].correcoes_formula]
    assert corrigidas == ([("D24", "=SUM(D9:D23)")] if mes_exemplo == "2026-07" else [])
    assert _celulas_com_aviso(planilha, "vínculo externo") == set()


# ---------------------------------------------------------------------------
# Gravação: valores e comparação célula por célula
# ---------------------------------------------------------------------------


@pytest.fixture
def geradas(arquivos, tmp_path):
    """Roda leitura + conciliação + gravação das duas planilhas do mês na pasta temporária."""
    hashes_antes = {q: _hash(getattr(arquivos, q)) for q in ("subvencoes", "projetos")}
    planilhas = {q: ler_estrutura_planilha(getattr(arquivos, q)) for q in ("subvencoes", "projetos")}
    resultado = conciliar(ler_balancete(arquivos.balancete), ler_patrimonio(arquivos.patrimonio),
                          list(planilhas.values()))
    saidas = {}
    for qual, planilha in planilhas.items():
        origem = getattr(arquivos, qual)
        destino = tmp_path / origem.name
        valores = [l for l in resultado.linhas if l.planilha == planilha.arquivo]
        assert gravar_planilha(origem, destino, valores) == len(valores)
        saidas[qual] = (origem, destino, planilha)
    return saidas, hashes_antes


def test_arquivos_de_entrada_nao_sao_alterados(geradas, arquivos):
    _, hashes_antes = geradas
    for qual, valor in hashes_antes.items():
        assert _hash(getattr(arquivos, qual)) == valor


def test_valores_gravados_iguais_ao_gabarito(geradas, arquivos):
    saidas, _ = geradas
    gabarito = ler_gabarito(arquivos.gabarito)
    pastas = {q: openpyxl.load_workbook(destino) for q, (_, destino, _) in saidas.items()}
    for linha in gabarito:
        aba = pastas[NOMES_GABARITO[linha["planilha"]]][linha["aba"]]
        assert aba.cell(linha["linha"], 2).value == linha["conta_contabil"]
        for coluna, campo in ((4, "saldo_patrimonio"), (5, "saldo_contabil")):
            valor = aba.cell(linha["linha"], coluna).value
            assert isinstance(valor, (int, float)), f"{linha['aba']}!{linha['linha']}: {valor!r}"
            assert Decimal(repr(valor)).quantize(Decimal("0.01")) == linha[campo], \
                f"{linha['aba']} linha {linha['linha']} {campo}"


def _atributos_celula(celula):
    return (
        celula.value,
        celula.number_format,
        repr(celula.font), repr(celula.fill), repr(celula.border),
        repr(celula.alignment), repr(celula.protection),
        (celula.comment.text, celula.comment.author) if celula.comment else None,
        celula.hyperlink.target if celula.hyperlink else None,
    )


def test_somente_saldos_das_linhas_de_conta_mudaram(geradas):
    """R6: comparando original x gerada, só D/E (Saldo Patrimônio/Contábil) das linhas de conta e as
    fórmulas de total corrigidas mudam. As demais fórmulas (inclusive vínculos [1]...), formatos,
    estilos, comentários, mesclagens, larguras, alturas, congelamento, filtros e configuração de
    página continuam iguais."""
    saidas, _ = geradas
    for origem, destino, estrutura in saidas.values():
        original = openpyxl.load_workbook(origem, keep_links=True)
        gerada = openpyxl.load_workbook(destino, keep_links=True)
        assert gerada.sheetnames == original.sheetnames

        permitidas = {
            (aba.nome, linha.linha, coluna)
            for aba in estrutura.abas for linha in aba.linhas
            for coluna in (aba.coluna_saldo_patrimonio, aba.coluna_saldo_contabil)
        }
        corrigidas = {(aba.nome, c.linha, c.coluna): c.formula_corrigida
                      for aba in estrutura.abas for c in aba.correcoes_formula}
        for nome in original.sheetnames:
            a, b = original[nome], gerada[nome]
            # O Excel às vezes guarda células vazias e sem formato no fim da aba, que o openpyxl não
            # regrava; por isso compara a área maior das duas (essas células continuam vazias).
            for linha in range(1, max(a.max_row, b.max_row) + 1):
                for coluna in range(1, max(a.max_column, b.max_column) + 1):
                    ca, cb = a.cell(linha, coluna), b.cell(linha, coluna)
                    if (nome, linha, coluna) in permitidas:
                        # o valor pode mudar; o formato numérico e o estilo, não
                        assert _atributos_celula(ca)[1:] == _atributos_celula(cb)[1:], ca.coordinate
                    elif (nome, linha, coluna) in corrigidas:
                        assert cb.value == corrigidas[(nome, linha, coluna)], ca.coordinate
                        assert _atributos_celula(ca)[1:] == _atributos_celula(cb)[1:], ca.coordinate
                    else:
                        assert _atributos_celula(ca) == _atributos_celula(cb), f"{nome}!{ca.coordinate}"

            assert sorted(map(str, a.merged_cells.ranges)) == sorted(map(str, b.merged_cells.ranges))
            assert {k: (d.width, d.hidden, d.outlineLevel) for k, d in a.column_dimensions.items()} == \
                   {k: (d.width, d.hidden, d.outlineLevel) for k, d in b.column_dimensions.items()}
            assert {k: (d.height, d.hidden, d.outlineLevel) for k, d in a.row_dimensions.items()} == \
                   {k: (d.height, d.hidden, d.outlineLevel) for k, d in b.row_dimensions.items()}
            assert a.freeze_panes == b.freeze_panes
            assert a.auto_filter.ref == b.auto_filter.ref
            assert repr(a.page_setup) == repr(b.page_setup)
            assert repr(a.page_margins) == repr(b.page_margins)
            assert a.print_area == b.print_area
            assert a.sheet_state == b.sheet_state
            assert len(a.conditional_formatting) == len(b.conditional_formatting)
            assert len(a.data_validations.dataValidation) == len(b.data_validations.dataValidation)
            assert len(a._charts) == len(b._charts)
            posicao = lambda aba: [(repr(i.anchor._from), repr(i.anchor.to), i.width, i.height) for i in aba._images]
            assert posicao(a) == posicao(b)

        # vínculos externos mantidos (mesmos arquivos de destino)
        alvos = lambda pasta: [l.file_link.Target for l in pasta._external_links]
        assert alvos(gerada) == alvos(original)
        assert list(gerada.defined_names.keys()) == list(original.defined_names.keys())


def test_nenhuma_parte_do_arquivo_perdida(geradas):
    """Proteção contra recursos que o openpyxl não suporta (imagens, gráficos, macros...).
    Diferenças conhecidas e aceitas: calcChain (o Excel recria), printerSettings (dados do driver
    da impressora; a configuração de página é mantida), sharedStrings e comentários/VML (regravados
    com outro nome, mesmo conteúdo — conferido célula por célula)."""
    aceitas = re.compile(r"xl/(calcChain\.xml|printerSettings/.*|sharedStrings\.xml|comments.*|"
                         r"drawings/(vmlDrawing|commentsDrawing)\d+\.vml)$")
    saidas, _ = geradas
    for origem, destino, _ in saidas.values():
        with zipfile.ZipFile(origem) as a, zipfile.ZipFile(destino) as b:
            perdidas = {n for n in set(a.namelist()) - set(b.namelist()) if not aceitas.match(n)}
        assert perdidas == set(), f"{origem.name}: partes perdidas {perdidas}"


def test_total_d35_corrigido_na_copia_e_nao_na_entrada(geradas):
    saidas, _ = geradas
    origem, destino, _ = saidas["subvencoes"]
    assert openpyxl.load_workbook(origem)["Estadual Investimento"]["D35"].value == "=SUM(D5:D33)"
    gerada = openpyxl.load_workbook(destino)["Estadual Investimento"]
    assert gerada["D35"].value == "=SUM(D5:D34)"
    assert gerada["E35"].value == "=SUM(E5:E34)"          # já estava certa: não muda


def test_imagem_do_projetos_mantida(geradas):
    """O Projetos tem um logotipo; sem a biblioteca Pillow o openpyxl o descartaria em silêncio."""
    saidas, _ = geradas
    origem, destino, _ = saidas["projetos"]
    imagens = openpyxl.load_workbook(destino)["PROJETOS 1"]._images
    assert len(imagens) == 1
    with zipfile.ZipFile(origem) as a, zipfile.ZipFile(destino) as b:
        assert a.read("xl/media/image1.png") == b.read("xl/media/image1.png")


def test_excel_recalcula_ao_abrir(geradas):
    saidas, _ = geradas
    for _, destino, _ in saidas.values():
        assert openpyxl.load_workbook(destino).calculation.fullCalcOnLoad


# ---------------------------------------------------------------------------
# Segurança da gravação e R11
# ---------------------------------------------------------------------------


def test_destino_igual_a_origem_e_recusado(tmp_path):
    caminho = _planilha_minima(tmp_path / "Projetos_08-2026.xlsx")
    with pytest.raises(ErroArquivo, match="próprio arquivo de entrada"):
        gravar_planilha(caminho, caminho, [])


def test_codigo_diferente_cancela_a_gravacao(tmp_path):
    origem = _planilha_minima(tmp_path / "Projetos_08-2026.xlsx")
    destino = tmp_path / "saida" / "Projetos_09-2026.xlsx"
    errado = ResultadoLinha("Projetos_08-2026.xlsx", "Aba", 5, 999, "", "", Decimal("1"), Decimal("2"))
    with pytest.raises(ErroArquivo, match="esperado código 999"):
        gravar_planilha(origem, destino, [errado])
    assert not destino.exists()


def test_destino_aberto_da_mensagem_clara(tmp_path):
    origem = _planilha_minima(tmp_path / "Projetos_08-2026.xlsx")
    destino = tmp_path / "Projetos_09-2026.xlsx"
    openpyxl.Workbook().save(destino)
    with open(destino, "rb"):                     # simula o arquivo aberto no Excel
        with pytest.raises(ErroArquivo, match="Feche o arquivo"):
            gravar_planilha(origem, destino, [])
    assert not [p for p in tmp_path.iterdir() if p.name.startswith("~tmp_")]


def test_gravacao_minima(tmp_path):
    origem = _planilha_minima(tmp_path / "Projetos_08-2026.xlsx")
    destino = caminho_destino(origem, tmp_path / "saida", MesReferencia(2026, 9))
    assert destino.name == "Projetos_09-2026.xlsx"
    linha = ResultadoLinha(origem.name, "Aba", 5, 24876, "", "", Decimal("569.57"), Decimal("0.10"))
    gravar_planilha(origem, destino, [linha])
    aba = openpyxl.load_workbook(destino)["Aba"]
    assert (aba["D5"].value, aba["E5"].value) == (569.57, 0.1)
    assert aba["D5"].number_format == "#,##0.00"
    assert aba["D6"].value == "=SUM(D5:D5)"


@pytest.mark.parametrize("nome, esperado", [
    ("Subvenções Investimento 08-2026.xlsx", "Subvenções Investimento 09-2026.xlsx"),
    ("Projetos_08-2026.xlsx", "Projetos_09-2026.xlsx"),
    ("Planilha.xlsx", "Planilha_09-2026.xlsx"),
])
def test_r11_nome_de_saida(tmp_path, nome, esperado):
    assert caminho_destino(Path("c:/entrada") / nome, tmp_path, MesReferencia(2026, 9)) == tmp_path / esperado


# ---------------------------------------------------------------------------
# Estrutura: casos construídos
# ---------------------------------------------------------------------------


def _planilha_minima(caminho, extra=None):
    pasta = openpyxl.Workbook()
    aba = pasta.active
    aba.title = "Aba"
    for coluna, titulo in enumerate(["Conta Contábil", "Convênio", "Saldo Patrimônio", "Saldo Contábil"], 2):
        aba.cell(4, coluna, titulo)
    aba["B5"], aba["C5"] = 24876, " Convênio X "
    aba["D5"].number_format = aba["E5"].number_format = "#,##0.00"
    aba["C6"], aba["D6"] = "Total", "=SUM(D5:D5)"
    if extra:
        extra(pasta)
    pasta.save(caminho)
    return caminho


def test_aba_sem_titulos_e_aba_incompleta(tmp_path):
    def extra(pasta):
        pasta.create_sheet("Anotações")["A1"] = "texto"
        incompleta = pasta.create_sheet("Incompleta")
        incompleta["B2"], incompleta["C2"] = "Conta Contábil", "Convênio"
        incompleta["B3"] = 1
    planilha = ler_estrutura_planilha(_planilha_minima(tmp_path / "p.xlsx", extra))
    assert [a.nome for a in planilha.abas] == ["Aba"]
    assert planilha.abas_sem_contas == ["Anotações", "Incompleta"]
    erro = [a for a in planilha.avisos if a.gravidade == Gravidade.ERRO]
    assert len(erro) == 1 and erro[0].aba == "Incompleta" and "Saldo Patrimônio" in erro[0].mensagem
    assert planilha.abas[0].linhas[0].convenio == "Convênio X"


def test_r12_somas(tmp_path):
    def extra(pasta):
        aba = pasta["Aba"]
        aba["B7"] = 11
        aba["B8"] = 12
        aba["D6"] = "=SUM(D5:D6)"                 # pega 5, falta 7 e 8 -> aviso
        aba["E9"] = "=SUM(E5:E8)"                 # completo -> sem aviso
        aba["D20"] = "=SUM(D15:D19)"              # bloco de rodapé, não toca contas -> sem aviso
        aba["D21"] = "=SUM(Outra!D5:D8)+D5"       # referência a outra aba -> não é total da aba
        aba["E22"] = "=soma(E5:E7)+SUM(E8)"       # falta nada? E5..E7 + E8 = completo
        aba["E23"] = "=SUM(E5,E7)"                # falta 8 -> aviso
        aba["F30"] = "='[1]Plan1'!A1"            # vínculo externo fora das colunas de saldo
    planilha = ler_estrutura_planilha(_planilha_minima(tmp_path / "p.xlsx", extra))
    # D6 somaria a si mesmo se ampliado e E23 não é um SUM simples: só aviso, sem correção
    assert _celulas_com_aviso(planilha, "fórmula de total incompleta") == {("Aba", "D6"), ("Aba", "E23")}
    assert _celulas_com_aviso(planilha, "fórmula de total corrigida") == set()
    assert planilha.abas[0].correcoes_formula == []
    assert _celulas_com_aviso(planilha, "vínculo externo") == {("Aba", "F30")}


def test_correcao_de_totais_simples(tmp_path):
    """Decisão do usuário (Etapa 6): total simples incompleto é corrigido na cópia gerada."""
    def extra(pasta):
        aba = pasta["Aba"]
        aba["D6"] = None                          # linha 6 vazia (nem conta, nem valor)
        aba["B7"], aba["B8"] = 11, 12             # contas nas linhas 5, 7 e 8
        aba["D10"] = "=SUM(D5:D7)"                # falta 8 -> =SUM(D5:D8)
        aba["E10"] = "=sum($E$5:$E$5)"            # falta 7 e 8 -> mantém $ e a grafia da função
    origem = _planilha_minima(tmp_path / "Projetos_08-2026.xlsx", extra)
    planilha = ler_estrutura_planilha(origem)
    correcoes = [(c.celula, c.formula_corrigida) for c in planilha.abas[0].correcoes_formula]
    assert correcoes == [("D10", "=SUM(D5:D8)"), ("E10", "=sum($E$5:$E$8)")]
    assert _celulas_com_aviso(planilha, "fórmula de total corrigida") == {("Aba", "D10"), ("Aba", "E10")}

    destino = tmp_path / "saida" / "Projetos_09-2026.xlsx"
    gravar_planilha(origem, destino, [])
    gerada = openpyxl.load_workbook(destino)["Aba"]
    assert (gerada["D10"].value, gerada["E10"].value) == ("=SUM(D5:D8)", "=sum($E$5:$E$8)")
    assert openpyxl.load_workbook(origem)["Aba"]["D10"].value == "=SUM(D5:D7)"   # entrada intacta


def test_total_nao_e_corrigido_se_pegaria_outra_celula_preenchida(tmp_path):
    def extra(pasta):
        aba = pasta["Aba"]
        aba["D6"] = None
        aba["C7"], aba["D7"] = "anotação", 999    # linha 7 não é conta, mas tem valor
        aba["B8"] = 11
        aba["D10"] = "=SUM(D5:D6)"                # ampliar até 8 somaria o 999 -> só aviso
    planilha = ler_estrutura_planilha(_planilha_minima(tmp_path / "p.xlsx", extra))
    assert planilha.abas[0].correcoes_formula == []
    assert _celulas_com_aviso(planilha, "fórmula de total incompleta") == {("Aba", "D10")}


def test_baloes_dos_comentarios_iguais_ao_original(geradas):
    """A pedido do usuário: o desenho dos comentários (tamanho/posição dos balões) é o do original."""
    from modulos.subvencoes.preenchedor import _vml_por_aba

    saidas, _ = geradas
    for origem, destino, _ in saidas.values():
        with zipfile.ZipFile(origem) as a, zipfile.ZipFile(destino) as b:
            vml_a, vml_b = _vml_por_aba(a), _vml_por_aba(b)
            assert vml_a and set(vml_a) == set(vml_b)
            for aba in vml_a:
                assert a.read(vml_a[aba]) == b.read(vml_b[aba]), f"{origem.name} / {aba}"
