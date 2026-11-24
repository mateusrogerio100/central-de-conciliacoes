"""Tela do módulo Imobilizado – AME's: aba "Conciliação" (telas/conciliacao.py), aba "Comparação Ativo x Passivo"
(telas/ativo_passivo.py, pedido do usuário de 05/11/2026) e a aba "Instruções de uso" (INSTRUCOES_DE_USO.md,
acrescentada pela Central)."""

from __future__ import annotations

from central.painel_abas import Aba, PainelComAbas
from modulos.conciliacao_imobilizado.telas.ativo_passivo import PainelAtivoPassivo
from modulos.conciliacao_imobilizado.telas.conciliacao import PainelConciliacaoImobilizado

ABA_CONCILIACAO = "Conciliação"
ABA_ATIVO_PASSIVO = "Comparação Ativo x Passivo"
DESCRICAO_ATIVO_PASSIVO = "Compara o saldo de cada conta do Ativo com o da conta irmã no Passivo (razões do Tasy)."


class PainelModuloImobilizado(PainelComAbas):
    def __init__(self, pai, info):
        super().__init__(pai, info, [
            Aba(ABA_CONCILIACAO, lambda p: PainelConciliacaoImobilizado(p, info), info.descricao, "conciliacao"),
            Aba(ABA_ATIVO_PASSIVO, lambda p: PainelAtivoPassivo(p, info), DESCRICAO_ATIVO_PASSIVO, "ativo_passivo"),
        ])
