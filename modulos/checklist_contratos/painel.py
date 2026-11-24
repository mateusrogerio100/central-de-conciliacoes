"""Tela do módulo Notas de Contrato: abas "Conferência" (telas/conferencia.py), "Pendências"
(telas/pendencias.py), "E-mails" (telas/emails.py) e "Instruções de uso" (INSTRUCOES_DE_USO.md,
acrescentada pela Central).

O relatório gerado na Conferência vai para a aba Pendências (P2), e os e-mails gerados nas Pendências
aparecem na aba E-mails.
"""

from __future__ import annotations

from central.painel_abas import Aba, PainelComAbas
from modulos.checklist_contratos.telas.conferencia import PainelConferencia
from modulos.checklist_contratos.telas.emails import PainelEmails
from modulos.checklist_contratos.telas.pendencias import PainelPendencias

ABA_CONFERENCIA = "Conferência"
ABA_PENDENCIAS = "Pendências"
ABA_EMAILS = "E-mails"
DESCRICAO_PENDENCIAS = ("Separa as notas que ainda faltam por responsável e monta um e-mail para cada um, "
                        "com a prévia para conferir antes.")
DESCRICAO_EMAILS = "Cria um rascunho no Gmail da Contabilidade para cada e-mail das pendências. Nada é enviado."


class PainelContratos(PainelComAbas):
    def __init__(self, pai, info):
        super().__init__(pai, info, [
            Aba(ABA_CONFERENCIA, lambda p: PainelConferencia(p, info, ao_conferir=self._conferiu),
                info.descricao, "conferencia"),
            Aba(ABA_PENDENCIAS, lambda p: PainelPendencias(p, info), DESCRICAO_PENDENCIAS, "pendencias"),
            Aba(ABA_EMAILS, lambda p: PainelEmails(p, info, self._ultimas_pendencias), DESCRICAO_EMAILS,
                "emails"),
        ])

    def _conferiu(self, resultado) -> None:
        """A conferência gerou o relatório: a aba Pendências passa a usá-lo (P2)."""
        if resultado.caminho_relatorio is not None:
            self.pendencias.usar_relatorio(resultado.caminho_relatorio, (resultado.ano, resultado.mes))

    def _ultimas_pendencias(self):
        painel = self.paineis.get(ABA_PENDENCIAS)
        return painel.ultimo_resultado if painel is not None else None

    def mostrar_aba(self, nome: str) -> None:
        super().mostrar_aba(nome)
        if nome == ABA_EMAILS:
            self.paineis[ABA_EMAILS].ao_ver_a_aba()
