"""
Estruturas de dados da Conciliação Honorários Hospital Exemplo (ESPECIFICACAO seção 20).

Compara, por mês, o Balancete das contas de Honorários médicos a pagar da Hospital Exemplo (2131 – PF e
2132 – PJ; Saldo Atual de cada médico/clínica) com a soma de três relatórios:
- HM PF / HM PJ Senior ("Lançamentos Honorários Médicos em Aberto", .XLS; coluna "S. Atual");
- Relatório 6095 (Deslocamento) e Remoção/Transporte, os dois "SCF – Repasse Sintético" em PDF
  (coluna "Vl repasse").
Os PDFs misturam PF e PJ: cada linha deles vai para o lado da conta do balancete onde a pessoa foi
encontrada. Modelo: a planilha Conciliacao_Honorarios_Medicos_PF_PJ_08_2026_1.xlsx do usuário.

Dinheiro sempre em Decimal. A nota de semelhança dos nomes (0 a 1) é float: não é dinheiro.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from modulos.honorarios_medicos.fornecedores.avisos import Aviso
from modulos.honorarios_medicos.ames.modelos import ContaHonorario, Repasse, Terceiro

LADO_PF = "PF"
LADO_PJ = "PJ"
LADOS = (LADO_PF, LADO_PJ)
NOMES_LADO = {LADO_PF: "Pessoas Físicas", LADO_PJ: "Pessoas Jurídicas"}

SITUACAO_OK = "OK"
SITUACAO_DIVERGENTE = "DIVERGENTE"
SITUACAO_SO_BALANCETE = "SÓ NO BALANCETE"
SITUACAO_SO_SENIOR = "SÓ NO SENIOR"

PAREAMENTO_NOME = "nome"
PAREAMENTO_VALOR = "valor"               # mesmo valor + nome parecido o bastante: confirmar

TIPO_BALANCETE = "Balancete (865)"
TIPO_SENIOR = "HM Senior"
TIPO_REPASSE = "Remoção/Deslocamento (PDF)"


@dataclass
class LancamentoSenior:
    """Uma pessoa do HM PF/PJ Senior."""

    lado: str                            # LADO_PF ou LADO_PJ
    codigo: str                          # Cód. Senior ("12345")
    nome: str                            # "MEDICA UM DA SILVA" (maiúsculas, como no relatório)
    saldo: Decimal                       # S. Atual
    previsto: Decimal = Decimal(0)       # Prev. Pgto
    posterior: Decimal = Decimal(0)      # S. Posterior


@dataclass
class LeituraBalanceteHospitalExemplo:
    """Um arquivo de balancete: pode trazer só a 2131, só a 2132 ou as duas."""

    arquivo: str
    unidade: str = ""
    mes: date | None = None
    totais: dict[str, ContaHonorario] = field(default_factory=dict)          # lado → conta sintética
    contas: dict[str, list[ContaHonorario]] = field(default_factory=dict)    # lado → contas dos médicos
    avisos: list[Aviso] = field(default_factory=list)
    erro: str | None = None


@dataclass
class LeituraSenior:
    arquivo: str
    lado: str = ""
    mes: date | None = None              # fim da Competência ("01/1999 a 09/2026")
    lancamentos: list[LancamentoSenior] = field(default_factory=list)
    total_impresso: Decimal | None = None   # "S. Atual" da linha Total Geral
    avisos: list[Aviso] = field(default_factory=list)
    erro: str | None = None

    @property
    def total(self) -> Decimal:
        return sum((l.saldo for l in self.lancamentos), Decimal(0))


@dataclass
class LeituraRepassePdf:
    """Um PDF do SCF – Repasse Sintético (Relatório 6095 ou Remoção/Transporte)."""

    arquivo: str
    unidade: str = ""                    # "HOSPITAL EXEMPLO"
    mes: date | None = None              # mês do Dt Ref
    repasses: list[Repasse] = field(default_factory=list)
    grupos: list[str] = field(default_factory=list)
    total_impresso: tuple[int, Decimal, Decimal] | None = None   # linha "Total(n) bruto líquido"
    avisos: list[Aviso] = field(default_factory=list)
    erro: str | None = None

    @property
    def total_bruto(self) -> Decimal:
        return sum((r.bruto for r in self.repasses), Decimal(0))


@dataclass
class LinhaHospitalExemplo:
    """Uma linha das abas "PF - Conciliação" e "PJ - Conciliação"."""

    lado: str
    situacao: str = ""
    conta: ContaHonorario | None = None
    senior: list[LancamentoSenior] = field(default_factory=list)
    remocao: list[Terceiro] = field(default_factory=list)       # terceiros dos PDFs
    pareamento: str = ""                 # como a conta casou com o Senior (nome / valor)
    nota: float | None = None            # nota do par com o Senior (ou com a Remoção, se só ela)

    @property
    def saldo_contabil(self) -> Decimal | None:
        return None if self.conta is None else self.conta.saldo_atual

    @property
    def saldo_senior(self) -> Decimal | None:
        if not self.senior:
            return None
        return sum((s.saldo for s in self.senior), Decimal(0))

    @property
    def valor_remocao(self) -> Decimal | None:
        if not self.remocao:
            return None
        return sum((t.bruto for t in self.remocao), Decimal(0))

    @property
    def senior_ajustado(self) -> Decimal:
        return (self.saldo_senior or Decimal(0)) + (self.valor_remocao or Decimal(0))

    @property
    def diferenca(self) -> Decimal:
        """Contábil − Senior ajustado (lado que falta conta como zero)."""
        return (self.saldo_contabil or Decimal(0)) - self.senior_ajustado

    @property
    def nome_senior(self) -> str:
        return " + ".join(dict.fromkeys(s.nome for s in self.senior))

    @property
    def codigo_senior(self) -> str:
        return " + ".join(dict.fromkeys(s.codigo for s in self.senior))

    @property
    def nome_remocao(self) -> str:
        return " + ".join(dict.fromkeys(t.nome for t in self.remocao))

    @property
    def sem_correspondencia(self) -> bool:
        """Amarelo: conta sem nada nos relatórios, ou pessoa do Senior sem conta."""
        return self.situacao in (SITUACAO_SO_BALANCETE, SITUACAO_SO_SENIOR)

    @property
    def acertada_pela_remocao(self) -> bool:
        """Azul: a Remoção/Deslocamento entrou e a conta bate."""
        return bool(self.remocao) and self.situacao == SITUACAO_OK


@dataclass
class ResultadoHospitalExemplo:
    """Tudo o que processar_honorarios_hospital_exemplo() devolve para a interface."""

    linhas: dict[str, list[LinhaHospitalExemplo]] = field(default_factory=dict)    # lado → linhas
    lados: list[str] = field(default_factory=list)                         # lados com balancete
    totais_balancete: dict[str, Decimal] = field(default_factory=dict)     # lado → conta sintética
    contas_total: dict[str, ContaHonorario] = field(default_factory=dict)
    totais_senior: dict[str, Decimal] = field(default_factory=dict)        # lado → soma do S. Atual
    repasses: list[Repasse] = field(default_factory=list)                  # todas as linhas dos PDFs
    lado_do_repasse: dict[int, str] = field(default_factory=dict)          # id(Repasse) → lado ("" = sem conta)
    conta_do_repasse: dict[int, str] = field(default_factory=dict)         # id(Repasse) → código da conta
    origem_do_repasse: dict[int, str] = field(default_factory=dict)        # id(Repasse) → nome do PDF
    notas: list[str] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)
    unidade: str = ""
    mes: date | None = None
    arquivos: list[str] = field(default_factory=list)                      # arquivos usados
    caminho_relatorio: Path | None = None
    erro: str | None = None

    @property
    def total_remocao(self) -> Decimal:
        return sum((r.bruto for r in self.repasses), Decimal(0))

    def remocao_do_lado(self, lado: str) -> Decimal:
        return sum((r.bruto for r in self.repasses if self.lado_do_repasse.get(id(r)) == lado), Decimal(0))

    @property
    def repasses_sem_conta(self) -> list[Repasse]:
        return [r for r in self.repasses if not self.lado_do_repasse.get(id(r))]
