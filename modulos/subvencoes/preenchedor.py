"""Leitura da estrutura das planilhas a preencher e gravação das cópias preenchidas.

- ler_estrutura_planilha: localiza, em cada aba, a linha de títulos ("Conta Contábil", "Convênio",
  "Saldo Patrimônio", "Saldo Contábil") e as linhas de conta (número inteiro em "Conta Contábil").
  Também gera os avisos R12 (vínculo externo; fórmula de total incompleta) e identifica as
  fórmulas de total simples que podem ser corrigidas (R12, decisão do usuário na Etapa 6).
- gravar_planilha: abre a planilha de ORIGEM, escreve só as células Saldo Patrimônio e Saldo
  Contábil das linhas de conta e as fórmulas de total corrigidas (R6) e salva no DESTINO.
  O arquivo de origem nunca é alterado.
  O desenho dos comentários (tamanho/posição dos balões) é copiado do original, a pedido do usuário.
"""

from __future__ import annotations

import os
import posixpath
import re
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from openpyxl.utils import range_boundaries
from openpyxl.worksheet.formula import ArrayFormula

from modulos.subvencoes import configuracao
from modulos.subvencoes.modelos import (
    AbaPlanilha,
    Aviso,
    CorrecaoFormula,
    ErroArquivo,
    Gravidade,
    LinhaPlanilha,
    MesReferencia,
    PlanilhaLida,
    ResultadoLinha,
)
from modulos.subvencoes.utilitarios import abrir_planilha, nome_com_mes, para_float_excel, para_inteiro, texto_igual

# Vínculo externo numa fórmula: [1]Aba!A1, '[2]PROJETOS 1'!$D$23, [C:\pasta\arq.xlsx]Aba!A1 ...
_PADRAO_VINCULO_EXTERNO = re.compile(r"\[[^\]]+\][^!]*!")
# SUM(...) / SOMA(...)
_PADRAO_SOMA = re.compile(r"\b(?:SUM|SOMA)\s*\(([^()]*)\)", re.IGNORECASE)
# Total simples que pode ser corrigido: =SUM(D5:D33) (um único intervalo, uma coluna)
_PADRAO_SOMA_SIMPLES = re.compile(
    r"^=\s*(SUM|SOMA)\s*\(\s*(\$?)([A-Z]{1,3})(\$?)(\d+)\s*:\s*(\$?)([A-Z]{1,3})(\$?)(\d+)\s*\)\s*$",
    re.IGNORECASE,
)
# Referência na mesma aba (sem "Aba!" antes): D5, $D$5, D5:D33
_PADRAO_INTERVALO = re.compile(r"(?<![!\w$:])(\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?)(?![\w(!])")


# ---------------------------------------------------------------------------
# Leitura da estrutura
# ---------------------------------------------------------------------------


def ler_estrutura_planilha(caminho) -> PlanilhaLida:
    caminho = Path(caminho)
    pasta_trabalho = abrir_planilha(caminho, somente_valores=False, manter_vinculos=True)
    try:
        return _estrutura_da_pasta(pasta_trabalho, caminho.name)
    finally:
        pasta_trabalho.close()


def _estrutura_da_pasta(pasta_trabalho, nome_arquivo: str) -> PlanilhaLida:
    planilha = PlanilhaLida(arquivo=nome_arquivo)
    for aba in pasta_trabalho.worksheets:
        _avisar_vinculos_externos(aba, planilha)
        estrutura = _estrutura_da_aba(aba, planilha)
        if estrutura is None:
            planilha.abas_sem_contas.append(aba.title)
            continue
        planilha.abas.append(estrutura)
        _conferir_totais(aba, estrutura, planilha)
    return planilha


def _avisar(planilha, gravidade, tipo, mensagem, aba="", linha=None, conta=""):
    planilha.avisos.append(Aviso(gravidade, tipo, mensagem, arquivo=planilha.arquivo, aba=aba,
                                 linha=linha, conta=conta))


def _estrutura_da_aba(aba, planilha: PlanilhaLida) -> AbaPlanilha | None:
    """Localiza os títulos pelo texto e lista as linhas de conta. None se a aba não tiver "Conta Contábil"."""
    titulos = {
        "coluna_conta": configuracao.PLANILHA_TITULO_CONTA_CONTABIL,
        "coluna_convenio": configuracao.PLANILHA_TITULO_CONVENIO,
        "coluna_saldo_patrimonio": configuracao.PLANILHA_TITULO_SALDO_PATRIMONIO,
        "coluna_saldo_contabil": configuracao.PLANILHA_TITULO_SALDO_CONTABIL,
    }
    for linha_celulas in aba.iter_rows():
        if not any(texto_igual(c.value, configuracao.PLANILHA_TITULO_CONTA_CONTABIL) for c in linha_celulas):
            continue
        estrutura = AbaPlanilha(nome=aba.title, linha_titulos=linha_celulas[0].row)
        for atributo, titulo in titulos.items():
            coluna = next((c.column for c in linha_celulas if texto_igual(c.value, titulo)), None)
            setattr(estrutura, atributo, coluna)
        faltando = [titulos[a] for a in ("coluna_saldo_patrimonio", "coluna_saldo_contabil")
                    if getattr(estrutura, a) is None]
        if faltando:
            _avisar(planilha, Gravidade.ERRO, "aba sem títulos",
                    f"A linha de títulos (linha {estrutura.linha_titulos}) não tem: {', '.join(faltando)}. "
                    "A aba não foi preenchida.", aba=aba.title, linha=estrutura.linha_titulos)
            return None
        _ler_linhas_de_conta(aba, estrutura)
        return estrutura
    return None


def _ler_linhas_de_conta(aba, estrutura: AbaPlanilha):
    for numero in range(estrutura.linha_titulos + 1, aba.max_row + 1):
        codigo = para_inteiro(aba.cell(numero, estrutura.coluna_conta).value)
        if codigo is None:
            continue
        convenio = ""
        if estrutura.coluna_convenio is not None:
            valor = aba.cell(numero, estrutura.coluna_convenio).value
            convenio = str(valor).strip() if valor is not None else ""
        estrutura.linhas.append(LinhaPlanilha(linha=numero, conta_contabil=codigo, convenio=convenio))


def _formula(valor) -> str | None:
    if isinstance(valor, ArrayFormula):
        return valor.text
    if isinstance(valor, str) and valor.startswith("="):
        return valor
    return None


def _avisar_vinculos_externos(aba, planilha: PlanilhaLida):
    """R12: fórmulas que puxam dados de outro arquivo ([1]...)."""
    for linha_celulas in aba.iter_rows():
        for celula in linha_celulas:
            formula = _formula(celula.value)
            if formula and _PADRAO_VINCULO_EXTERNO.search(formula):
                _avisar(planilha, Gravidade.ATENCAO, "vínculo externo",
                        f"Célula {celula.coordinate}: fórmula com vínculo a outro arquivo ({formula}). "
                        "O valor depende de um arquivo externo.", aba=aba.title, linha=celula.row)


def _linhas_somadas(formula: str, coluna: int) -> set[int]:
    """Linhas da mesma coluna cobertas pelos SUM/SOMA da fórmula (referências da própria aba)."""
    linhas: set[int] = set()
    for soma in _PADRAO_SOMA.finditer(formula):
        for intervalo in _PADRAO_INTERVALO.findall(soma.group(1)):
            col_ini, lin_ini, col_fim, lin_fim = range_boundaries(intervalo.replace("$", ""))
            if col_ini <= coluna <= col_fim:
                linhas.update(range(lin_ini, lin_fim + 1))
    return linhas


def _conferir_totais(aba, estrutura: AbaPlanilha, planilha: PlanilhaLida):
    """R12: SUM na coluna Saldo Patrimônio/Contábil que pega parte das linhas de conta, mas não todas.

    Somas que não tocam nenhuma linha de conta (ex.: blocos de composição no rodapé) não são totais
    das contas e não geram aviso. Totais simples (=SUM(D5:D33)) são corrigidos na cópia gerada
    (decisão do usuário); os demais só geram aviso.
    """
    linhas_conta = {l.linha for l in estrutura.linhas}
    if not linhas_conta:
        return
    for coluna in (estrutura.coluna_saldo_patrimonio, estrutura.coluna_saldo_contabil):
        for numero in range(estrutura.linha_titulos + 1, aba.max_row + 1):
            if numero in linhas_conta:
                continue
            celula = aba.cell(numero, coluna)
            formula = _formula(celula.value)
            if not formula:
                continue
            somadas = _linhas_somadas(formula, coluna)
            if not somadas & linhas_conta:
                continue
            faltando = sorted(linhas_conta - somadas)
            if not faltando:
                continue
            linhas_faltando = ", ".join(map(str, faltando))
            corrigida = _corrigir_total(aba, celula, formula, linhas_conta)
            if corrigida:
                estrutura.correcoes_formula.append(CorrecaoFormula(
                    linha=numero, coluna=coluna, celula=celula.coordinate,
                    formula_original=formula, formula_corrigida=corrigida))
                _avisar(planilha, Gravidade.ATENCAO, "fórmula de total corrigida",
                        f"Célula {celula.coordinate}: {formula} não incluía a(s) linha(s) de conta "
                        f"{linhas_faltando}. Na cópia gerada ficou {corrigida}. Corrija também a planilha "
                        "de origem para este aviso deixar de aparecer.", aba=aba.title, linha=numero)
            else:
                _avisar(planilha, Gravidade.ATENCAO, "fórmula de total incompleta",
                        f"Célula {celula.coordinate}: {formula} não inclui a(s) linha(s) de conta "
                        f"{linhas_faltando}. Não foi corrigida automaticamente (fórmula que não é um "
                        "SUM simples, ou o intervalo ampliado pegaria outras células preenchidas); "
                        "corrija na planilha.", aba=aba.title, linha=numero)


def _corrigir_total(aba, celula, formula: str, linhas_conta: set[int]) -> str | None:
    """Fórmula ampliada para cobrir todas as linhas de conta, ou None se não for seguro corrigir.

    Só corrige =SUM(<col><ini>:<col><fim>) na própria coluna da célula, e só se as linhas acrescentadas
    que não são de conta estiverem vazias nessa coluna (nunca soma anotações nem a própria célula).
    """
    encontrado = _PADRAO_SOMA_SIMPLES.match(formula)
    if not encontrado:
        return None
    funcao, d1, col_ini, d2, ini, d3, col_fim, d4, fim = encontrado.groups()
    if col_ini.upper() != col_fim.upper() or col_ini.upper() != celula.column_letter:
        return None
    ini, fim = int(ini), int(fim)
    novo_ini, novo_fim = min(ini, min(linhas_conta)), max(fim, max(linhas_conta))
    if novo_ini <= celula.row <= novo_fim:          # somaria a própria célula (referência circular)
        return None
    for numero in range(novo_ini, novo_fim + 1):
        if ini <= numero <= fim or numero in linhas_conta:
            continue
        if aba.cell(numero, celula.column).value not in (None, ""):
            return None
    return f"={funcao}({d1}{col_ini}{d2}{novo_ini}:{d3}{col_fim}{d4}{novo_fim})"


# ---------------------------------------------------------------------------
# Gravação
# ---------------------------------------------------------------------------


def caminho_destino(caminho_origem, pasta_saida, mes: MesReferencia) -> Path:
    """R11: mesmo nome da entrada, com o MM-AAAA trocado pelo mês de referência."""
    return Path(pasta_saida) / nome_com_mes(Path(caminho_origem).name, mes)


def gravar_planilha(caminho_origem, caminho_destino, valores: list[ResultadoLinha]) -> int:
    """Grava a cópia preenchida. Devolve a quantidade de linhas preenchidas.

    `valores` são as linhas desta planilha vindas da conciliação. Antes de escrever, confere se
    a linha ainda tem o mesmo código na coluna "Conta Contábil"; qualquer diferença cancela a
    gravação inteira desta planilha (ErroArquivo), para nunca escrever na linha errada.
    """
    origem = Path(caminho_origem)
    destino = Path(caminho_destino)
    if destino.resolve() == origem.resolve():
        raise ErroArquivo(f"{origem.name}: o arquivo de saída não pode ser o próprio arquivo de entrada.")

    pasta_trabalho = abrir_planilha(origem, somente_valores=False, manter_vinculos=True)
    try:
        estrutura = _estrutura_da_pasta(pasta_trabalho, origem.name)
        abas = {a.nome: a for a in estrutura.abas}
        for aba_estrutura in estrutura.abas:
            for correcao in aba_estrutura.correcoes_formula:
                celula = pasta_trabalho[aba_estrutura.nome].cell(correcao.linha, correcao.coluna)
                celula.value = correcao.formula_corrigida
        for valor in valores:
            aba_estrutura = abas.get(valor.aba)
            if aba_estrutura is None:
                raise ErroArquivo(f"{origem.name}: aba '{valor.aba}' não encontrada na hora de gravar.")
            aba = pasta_trabalho[valor.aba]
            codigo = para_inteiro(aba.cell(valor.linha, aba_estrutura.coluna_conta).value)
            if codigo != valor.conta_contabil:
                raise ErroArquivo(
                    f"{origem.name}: aba '{valor.aba}', linha {valor.linha}: esperado código "
                    f"{valor.conta_contabil}, encontrado {codigo}. Nada foi gravado nesta planilha."
                )
            aba.cell(valor.linha, aba_estrutura.coluna_saldo_patrimonio).value = \
                para_float_excel(valor.saldo_patrimonio)
            aba.cell(valor.linha, aba_estrutura.coluna_saldo_contabil).value = \
                para_float_excel(valor.saldo_contabil)

        # openpyxl não guarda os resultados das fórmulas; pede ao Excel para recalcular ao abrir.
        pasta_trabalho.calculation.fullCalcOnLoad = True
        _salvar(pasta_trabalho, origem, destino)
    finally:
        pasta_trabalho.close()
    return len(valores)


def _salvar(pasta_trabalho, origem: Path, destino: Path):
    """Salva num arquivo temporário e só então substitui o destino (nunca deixa arquivo pela metade)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    descritor, temporario = tempfile.mkstemp(suffix=".xlsx", prefix="~tmp_", dir=destino.parent)
    os.close(descritor)
    try:
        pasta_trabalho.save(temporario)
        _restaurar_desenho_comentarios(origem, Path(temporario))
        os.replace(temporario, destino)
    except PermissionError:
        raise ErroArquivo(f"{destino.name}: não foi possível gravar. Feche o arquivo no Excel e tente de novo.")
    finally:
        if os.path.exists(temporario):
            os.remove(temporario)


# ---------------------------------------------------------------------------
# Comentários: tamanho e posição originais dos balões
# ---------------------------------------------------------------------------
#
# O openpyxl mantém texto e autor dos comentários, mas regrava o "desenho" deles (arquivo VML
# interno) com um balão de tamanho padrão. A pedido do usuário, depois de salvar, o VML de cada
# aba é copiado do arquivo original, sem alteração. Só é feito quando o VML original tem apenas
# comentários ("Note"), na mesma quantidade da cópia, e não depende de outros arquivos internos;
# caso contrário, fica o VML do openpyxl (os textos continuam preservados).

_NS_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_NS_PLANILHA = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_NS_REL_DOC = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_TIPO_VML = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/vmlDrawing"


def _caminho_relacionamentos(parte: str) -> str:
    pasta, nome = posixpath.split(parte)
    return posixpath.join(pasta, "_rels", nome + ".rels")


def _relacionamentos(pacote: zipfile.ZipFile, parte: str) -> dict[str, tuple[str, str]]:
    """Id -> (tipo, caminho completo do alvo) dos relacionamentos de uma parte do pacote."""
    caminho = _caminho_relacionamentos(parte)
    if caminho not in pacote.namelist():
        return {}
    raiz = ElementTree.fromstring(pacote.read(caminho))
    pasta = posixpath.dirname(parte)

    def completo(alvo: str) -> str:
        # "/xl/..." é relativo à raiz do pacote (openpyxl); "../drawings/..." à pasta da parte (Excel)
        if alvo.startswith("/"):
            return posixpath.normpath(alvo.lstrip("/"))
        return posixpath.normpath(posixpath.join(pasta, alvo))

    return {
        r.get("Id"): (r.get("Type"), completo(r.get("Target")))
        for r in raiz.iter(f"{_NS_REL}Relationship")
        if r.get("TargetMode") != "External"
    }


def _vml_por_aba(pacote: zipfile.ZipFile) -> dict[str, str]:
    """Nome da aba -> caminho do VML de comentários dessa aba."""
    livro = ElementTree.fromstring(pacote.read("xl/workbook.xml"))
    rels_livro = _relacionamentos(pacote, "xl/workbook.xml")
    resultado = {}
    for aba in livro.iter(f"{_NS_PLANILHA}sheet"):
        alvo = rels_livro.get(aba.get(f"{_NS_REL_DOC}id"))
        if not alvo:
            continue
        vmls = [caminho for tipo, caminho in _relacionamentos(pacote, alvo[1]).values() if tipo == _TIPO_VML]
        if len(vmls) == 1:
            resultado[aba.get("name")] = vmls[0]
    return resultado


def _vml_so_de_comentarios(conteudo: bytes) -> int | None:
    """Quantidade de comentários do VML, ou None se ele tiver qualquer outro tipo de objeto."""
    texto = conteudo.decode("utf-8", errors="ignore")
    # o prefixo varia: "x:ClientData" (Excel), "ns2:ClientData" (openpyxl)
    objetos = re.findall(r"<(?:\w+:)?ClientData\s+ObjectType\s*=\s*[\"']?(\w+)", texto)
    if not objetos or any(o != "Note" for o in objetos):
        return None
    return len(objetos)


def _restaurar_desenho_comentarios(origem: Path, arquivo: Path):
    with zipfile.ZipFile(origem) as original, zipfile.ZipFile(arquivo) as copia:
        vml_original = _vml_por_aba(original)
        vml_copia = _vml_por_aba(copia)
        substituir = {}
        for aba, caminho_copia in vml_copia.items():
            caminho_original = vml_original.get(aba)
            if caminho_original is None or _relacionamentos(original, caminho_original):
                continue
            conteudo = original.read(caminho_original)
            quantidade = _vml_so_de_comentarios(conteudo)
            if quantidade is not None and quantidade == _vml_so_de_comentarios(copia.read(caminho_copia)):
                substituir[caminho_copia] = conteudo
        if not substituir:
            return
        novo = arquivo.with_name(arquivo.name + ".vml")
        try:
            with zipfile.ZipFile(novo, "w", zipfile.ZIP_DEFLATED) as destino:
                for item in copia.infolist():
                    destino.writestr(item, substituir.get(item.filename, copia.read(item.filename)))
        except BaseException:
            novo.unlink(missing_ok=True)
            raise
    os.replace(novo, arquivo)
