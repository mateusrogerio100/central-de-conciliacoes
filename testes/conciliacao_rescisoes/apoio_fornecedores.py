"""Auxiliares dos testes de Fornecedores do Conciliações AMES (tests/test_fornecedores.py) que os testes de
Rescisões usam, COPIADOS sem mudança: um teste de módulo não depende dos testes de outro módulo.
"""

from datetime import date, datetime
from pathlib import Path

OBSERVACAO_SECRETA = "Obs. NF: texto sigiloso de teste"


def _texto_celula(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    if isinstance(valor, (datetime, date)):
        return f"{valor:%d/%m/%Y}"
    return str(valor)


def texto_tasy(pasta: Path, nome: str, linhas: list[list]) -> Path:
    """Como o Tasy salva: .xls que é texto separado por tabulação, em Windows-1252."""
    caminho = pasta / nome
    caminho.write_bytes("\r\n".join("\t".join(_texto_celula(c) for c in linha) for linha in linhas)
                        .encode("cp1252"))
    return caminho


CABECALHO_ANALITICO = ["Pessoa Física/Jurídica", "Nr. Doc.", "Nr. Título", "TIpo Título", "Sit.", "Dt. Emissão",
                       "Dt. Vencto. Atu.", "Dt. Vencto. Ori.", "Dt. Liquid.", "Vl. Juros", "Vl. Multa", "Vl. Saldo",
                       "Observação", "Vl classif", "Vl título", "Vl pago", "Cheque", "Estabelecimento", "CNPJ",
                       "Valor NF", "Ordem Compra", "Vl baixa", "Trans fin baixa", "Classificação"]
