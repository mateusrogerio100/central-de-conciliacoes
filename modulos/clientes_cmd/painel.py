"""Tela do módulo Clientes CMD: abas sob o mesmo cabeçalho, como no programa original.

- "Conciliação de clientes": telas/conciliacao.py
- "Import Contábil": telas/import_contabil.py
- "Instruções de uso": INSTRUCOES_DE_USO.md (acrescentada pela Central)
Sem regra de negócio: cada aba chama o seu processamento.
"""

from __future__ import annotations

from central.painel_abas import Aba, PainelComAbas
from modulos.clientes_cmd.telas.conciliacao import PainelConciliacaoClientes
from modulos.clientes_cmd.telas.import_contabil import PainelImportContabil

ABA_CONCILIACAO = "Conciliação de clientes"
ABA_IMPORT = "Import Contábil"

DESCRICOES = {
    ABA_CONCILIACAO: "Casa o balancete de clientes com os Títulos a Receber pelo nome do cliente "
                     "e gera a planilha de conciliação com o status de cada cliente.",
    ABA_IMPORT: "Junta os relatórios do mês numa planilha Rel_Geral e gera o arquivo .txt "
                "que o sistema contábil importa.",
}


class PainelClientesCMD(PainelComAbas):
    def __init__(self, pai, info):
        super().__init__(pai, info, [
            Aba(ABA_CONCILIACAO, lambda p: PainelConciliacaoClientes(p, info), DESCRICOES[ABA_CONCILIACAO],
                "conciliacao"),
            Aba(ABA_IMPORT, lambda p: PainelImportContabil(p, info), DESCRICOES[ABA_IMPORT], "import_contabil"),
        ])
