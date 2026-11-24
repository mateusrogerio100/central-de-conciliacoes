"""Leitura da DANFSe v2.0 (layout nacional) em PDF — ESPECIFICACAO_EFD_CONTRIBUICOES.md, seção 4.1.

Copiado de `extrair_nfse.py` da aplicação Automacao-Notas-Fiscais-EFD (extrair_dados_pdf e funções de apoio).
O que mudou em relação à origem (decisões do usuário, 05/11/2026):
- R2: a COMPETÊNCIA DA NFS-E, que a origem lia e descartava, passa a ser guardada;
- R3: o valor vira Decimal (a origem guardava o texto e convertia para float);
- o resultado é um objeto NotaDanfse em vez de um dicionário, e a data de emissão também vem como date;
- PDF que não abre vira "ERRO: ..." (na origem, quem chamava é que pegava a exceção);
- o CNPJ do prestador (1º "CNPJ / CPF / NIF" da página), que a origem lia e descartava, passa a ser guardado
  (ajuste de 05/11/2026: aviso quando os PDFs vêm de prestadores com CNPJ diferente).
As mensagens de erro e a forma de achar cada campo são as mesmas da origem.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pdfplumber

from modulos.efd_contribuicoes import configuracao

# Linha logo abaixo do cabeçalho "NÚMERO DA NFS-E  COMPETÊNCIA DA NFS-E  DATA E HORA DA EMISSÃO DA NFS-E"
# Ex: "89504 01/08/2026 03/08/2026 03:00:00"  (R2: o 2º grupo, a competência, agora é capturado)
RE_NUMERO_DATA = re.compile(
    r"NÚMERO DA NFS-E\s+COMPETÊNCIA DA NFS-E\s+DATA E HORA DA EMISSÃO DA NFS-E\s*\n"
    r"(\d+)\s+(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})",
)

# Valor Total da NFS-E: primeiro "R$ ..." logo após o cabeçalho da seção
RE_VALOR_TOTAL = re.compile(
    r"VALOR TOTAL DA NFS-E\s+VALOR DA OPERAÇÃO / SERVIÇO.*\n"
    r"\s*R\$\s*([\d.,]+)",
)

PJ, PF = "PJ", "PF"
STATUS_OK = "OK"


@dataclass
class NotaDanfse:
    arquivo: str
    numero_nfse: str | None = None
    competencia: str | None = None          # "MM/AAAA" (R2)
    data_emissao: date | None = None
    data_emissao_texto: str | None = None   # "03/08/2026 03:00:00", como no PDF
    prestador: str | None = None
    doc_prestador: str | None = None        # CNPJ do prestador, como no PDF
    tomador: str | None = None
    doc_tomador: str | None = None          # como no PDF: "NN.NNN.NNN/NNNN-NN" ou "NNN.NNN.NNN-NN"
    tipo_pessoa: str | None = None          # PJ ou PF
    codigo_ibge_tomador: str | None = None
    valor: Decimal | None = None            # R3
    valor_texto: str | None = None          # "1.850,61", como no PDF
    status: str = STATUS_OK                 # "OK" ou "ERRO: ..." (R4)

    @property
    def lida(self) -> bool:
        return self.status == STATUS_OK

    @property
    def cnpj_digitos(self) -> str:
        return re.sub(r"\D", "", self.doc_tomador or "")

    @property
    def cnpj_prestador_digitos(self) -> str:
        return re.sub(r"\D", "", self.doc_prestador or "")

    @property
    def mes_competencia(self) -> tuple[int, int] | None:
        """(ano, mês) da competência da NFS-e."""
        if not self.competencia:
            return None
        mes, ano = self.competencia.split("/")
        return int(ano), int(mes)

    @property
    def mes_emissao(self) -> tuple[int, int] | None:
        return None if self.data_emissao is None else (self.data_emissao.year, self.data_emissao.month)


def eh_cnpj(doc: str) -> bool:
    """CNPJ tem formato NN.NNN.NNN/NNNN-NN (contém barra). CPF não tem barra."""
    return "/" in doc


def contar_digitos(doc: str) -> int:
    """Conta só os dígitos de um CNPJ/CPF, ignorando pontuação (. / -)."""
    return len(re.sub(r"\D", "", doc))


def valor_para_decimal(valor_str: str | None) -> Decimal | None:
    """'1.850,61' -> Decimal('1850.61') (R3; na origem, valor_para_float)."""
    if not valor_str:
        return None
    try:
        return Decimal(valor_str.replace(".", "").replace(",", ".")).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def _agrupar_por_linha(words, tolerancia=configuracao.TOLERANCIA_LINHA):
    """Agrupa palavras (de extract_words) em linhas, pela coordenada 'top'."""
    linhas = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if linhas and abs(linhas[-1][0]["top"] - w["top"]) <= tolerancia:
            linhas[-1].append(w)
        else:
            linhas.append([w])
    return linhas


def _texto_coluna1(linha_valor, limite_x=configuracao.LIMITE_X_COLUNA1):
    """Junta as palavras de uma linha cujo x0 está antes do limite (1ª coluna)."""
    palavras = [w["text"] for w in linha_valor if w["x0"] < limite_x]
    return " ".join(palavras).strip()


def _texto_coluna3(linha_valor, limite_x=configuracao.LIMITE_X_COLUNA3):
    """Junta as palavras de uma linha cujo x0 está a partir do limite (3ª coluna)."""
    palavras = [w["text"] for w in linha_valor if w["x0"] >= limite_x]
    return " ".join(palavras).strip()


def extrair_codigo_ibge(texto_coluna3: str):
    """'3516200 / 14400-750' -> '3516200' (só os 7 dígitos do Código IBGE)."""
    if not texto_coluna3:
        return None
    codigo = texto_coluna3.split("/")[0].strip()
    return codigo if re.fullmatch(r"\d{7}", codigo) else None


def ler_danfse(caminho_pdf: Path) -> NotaDanfse:
    """Lê uma DANFSe. Nunca levanta exceção: problema vira status "ERRO: ..." (R4)."""
    caminho_pdf = Path(caminho_pdf)
    try:
        with pdfplumber.open(caminho_pdf) as pdf:
            page = pdf.pages[0]
            texto = page.extract_text() or ""
            words = page.extract_words()
    except Exception as erro:       # pdfplumber/pdfminer levantam vários tipos para PDF inválido
        return NotaDanfse(arquivo=caminho_pdf.name, status=f"ERRO: não foi possível abrir o PDF ({erro})")
    return interpretar_danfse(caminho_pdf.name, texto, words)


def interpretar_danfse(nome_arquivo: str, texto: str, words: list[dict]) -> NotaDanfse:
    """A leitura em si (separada para os testes poderem montar casos sem PDF)."""
    linhas = _agrupar_por_linha(words)
    dados = NotaDanfse(arquivo=nome_arquivo)

    m = RE_NUMERO_DATA.search(texto)
    if m:
        dados.numero_nfse = m.group(1)
        dados.competencia = m.group(2)[3:]                       # "01/08/2026" -> "08/2026"
        dados.data_emissao_texto = m.group(3)
        dados.data_emissao = datetime.strptime(m.group(3).split()[0], "%d/%m/%Y").date()
    else:
        dados.status = "ERRO: número/data não encontrados"

    # "Nome / Nome Empresarial | Município / Sigla UF | Código IBGE / CEP"
    # aparece 2x: 1º Prestador, 2º Tomador (mesma linha traz as 3 colunas).
    nomes = []
    codigos_ibge = []
    for i, linha in enumerate(linhas):
        texto_linha = " ".join(w["text"] for w in linha)
        if "Nome / Nome Empresarial" in texto_linha and i + 1 < len(linhas):
            linha_valor = linhas[i + 1]
            nomes.append(_texto_coluna1(linha_valor))
            codigos_ibge.append(extrair_codigo_ibge(_texto_coluna3(linha_valor)))
    if len(nomes) >= 1:
        dados.prestador = nomes[0]
    if len(nomes) >= 2:
        dados.tomador = nomes[1]
    if len(codigos_ibge) >= 2:
        dados.codigo_ibge_tomador = codigos_ibge[1]

    # "CNPJ / CPF / NIF" aparece 2x: 1º Prestador, 2º Tomador
    docs = []
    for i, linha in enumerate(linhas):
        texto_linha = " ".join(w["text"] for w in linha)
        if "CNPJ / CPF / NIF" in texto_linha and i + 1 < len(linhas):
            docs.append(_texto_coluna1(linhas[i + 1]))
    if len(docs) >= 1:
        dados.doc_prestador = docs[0]
    if len(docs) >= 2:
        doc_tomador = docs[1]
        dados.doc_tomador = doc_tomador
        dados.tipo_pessoa = PJ if eh_cnpj(doc_tomador) else PF

        qtd_digitos = contar_digitos(doc_tomador)
        esperado = 14 if dados.tipo_pessoa == PJ else 11
        if qtd_digitos != esperado and dados.status == STATUS_OK:
            dados.status = (
                f"ERRO: CNPJ/CPF do tomador com {qtd_digitos} dígito(s) "
                f"(esperado {esperado} para {dados.tipo_pessoa}) - '{doc_tomador}'"
            )

    m = RE_VALOR_TOTAL.search(texto)
    if m:
        dados.valor_texto = m.group(1)
        dados.valor = valor_para_decimal(m.group(1))
        if dados.valor is None and dados.status == STATUS_OK:
            dados.status = f"ERRO: valor total ilegível ({m.group(1)!r})"
    elif dados.status == STATUS_OK:
        dados.status = "ERRO: valor total não encontrado"

    return dados
