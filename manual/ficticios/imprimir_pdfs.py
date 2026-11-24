"""Imprimir PDFs: uma pasta com PDFs fictícios de 1 a 3 páginas e um PDF danificado.

O exemplo só escolhe a pasta e mostra a lista com as folhas: NUNCA manda nada para a impressora. A lista
de impressoras é trocada por uma fictícia (a da rede não aparece no print).
"""

from __future__ import annotations

from pathlib import Path

from manual.ficticios import Exemplo
from manual.ficticios.pdf_simples import gravar_pdf

IMPRESSORA_FICTICIA = "Impressora Exemplo"
DOCUMENTOS = [                                   # nome, páginas
    ("01 Nota fiscal 1001 - Fornecedor Exemplo.pdf", 1),
    ("02 Boleto - Fornecedor Exemplo.pdf", 1),
    ("03 Contrato de serviço - Exemplo.pdf", 3),
    ("04 Relatório de repasse - Exemplo.pdf", 2),
]


def gerar(pasta: Path) -> list[Exemplo]:
    pasta_pdfs = pasta / "PDFs para imprimir"
    for nome, paginas in DOCUMENTOS:
        titulo = Path(nome).stem
        gravar_pdf(pasta_pdfs / nome, [[titulo, "", f"Página {numero} de {paginas}", "",
                                        "Documento fictício gerado para o manual da Central de Conciliações."]
                                       for numero in range(1, paginas + 1)], fonte="Helvetica", tamanho=12, entrelinha=18)
    (pasta_pdfs / "05 Arquivo danificado.pdf").write_bytes(b"%PDF-1.4 este arquivo foi cortado no meio")
    return [Exemplo("imprimir_pdfs", "imprimir_pdfs", "Imprimir", "imprimir", acao=None,
                    preparar=lambda tela: tela.definir_pasta(pasta_pdfs),
                    substituicoes={
                        "modulos.imprimir_pdfs.processamento.listar_impressoras": lambda: [IMPRESSORA_FICTICIA],
                        "modulos.imprimir_pdfs.processamento.impressora_padrao": lambda: IMPRESSORA_FICTICIA,
                    },
        numeros=("7", "4", "1"))]
