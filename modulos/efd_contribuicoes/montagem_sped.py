"""Montagem do SPED do novo mês — ESPECIFICACAO_EFD_CONTRIBUICOES.md, seção 4.5 (R10–R16) e 4.6.

Copiado de `gerar_sped_mensal.py` da aplicação Automacao-Notas-Fiscais-EFD (formatar_valor_sped, data_ddmmaaaa,
montar_a100_a170 e a montagem dos blocos em gerar_sped_mes), que já reconstruiu agosto/2026 byte a byte.
O que mudou em relação à origem:
- valores em Decimal (R3/4.6; a origem somava float e arredondava no fim);
- a montagem recebe as notas e os clientes já escolhidos (a leitura dos PDFs, a seleção e o cadastro ficam em
  outros arquivos) e devolve as linhas, sem gravar e sem imprimir;
- R16 (novo): conferir_sped() recalcula todos os contadores e a receita do arquivo pronto; quem grava só grava
  se não houver erro.
A ordem das notas é a da origem: pelo número da NFS-e como texto.
"""

from __future__ import annotations

import calendar
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from modulos.efd_contribuicoes import configuracao
from modulos.efd_contribuicoes.leitor_sped import MoldeSped, campos, montar_linha

CENTAVO = Decimal("0.01")


@dataclass(frozen=True)
class ClienteSped:
    cod_part: str
    nome: str
    cnpj: str            # só dígitos
    codigo_ibge: str


@dataclass(frozen=True)
class NotaSped:
    cod_part: str
    numero_nfse: str
    data_emissao: date
    valor: Decimal


@dataclass
class SpedMontado:
    linhas: list[str]
    competencia: str                     # "09/2026"
    total_receita: Decimal
    quantidade_notas: int
    quantidade_clientes: int
    erros: list[str] = field(default_factory=list)      # R16: vazio = pode gravar

    @property
    def texto(self) -> str:
        return configuracao.QUEBRA_LINHA_SPED.join(self.linhas) + configuracao.QUEBRA_LINHA_SPED


def formatar_valor_sped(valor: Decimal) -> str:
    """Decimal('1850.61') -> '1850,61' ; Decimal('30000.00') -> '30000' ; Decimal('50.50') -> '50,5'
    (sem zeros à direita desnecessários, igual ao padrão observado no arquivo original)."""
    valor = Decimal(valor).quantize(CENTAVO)
    if valor == valor.to_integral_value():
        return str(int(valor))
    texto = f"{valor:.2f}".rstrip("0").rstrip(".")
    return texto.replace(".", ",")


def valor_do_sped(texto: str) -> Decimal:
    """'1850,61' -> Decimal('1850.61') (para conferir o arquivo pronto)."""
    return Decimal(texto.replace(",", ".") or "0").quantize(CENTAVO)


def data_ddmmaaaa(dia: date) -> str:
    return f"{dia.day:02d}{dia.month:02d}{dia.year}"


def montar_a100_a170(cod_part: str, numero_nf: str, data_doc: date, valor: Decimal, cst: str = configuracao.CST):
    valor_txt = formatar_valor_sped(valor)
    dd = data_ddmmaaaa(data_doc)
    a100 = montar_linha([
        "A100", "1", "0", cod_part, "00", "", "", numero_nf, "",
        dd, dd, valor_txt, "0", "", valor_txt, "0", valor_txt, "0", "", "", "",
    ])
    a170 = montar_linha([
        "A170", "1", "1", "", valor_txt, "", "", "", cst, valor_txt, "", "",
        cst, valor_txt, "", "", "", "",
    ])
    return a100, a170


def linha_0150(cliente: ClienteSped) -> str:
    return montar_linha(["0150", cliente.cod_part, cliente.nome, configuracao.CODIGO_PAIS_BRASIL, cliente.cnpj,
                         "", "", cliente.codigo_ibge, "", "", "", "", ""])


def _ordem_cod_part(cliente: ClienteSped) -> int:
    return int(cliente.cod_part) if cliente.cod_part.isdigit() else 0


def montar_sped(molde: MoldeSped, competencia: str, clientes: list[ClienteSped], notas: list[NotaSped]) -> SpedMontado:
    """Monta o arquivo do mês `competencia` ("MM/AAAA"). Não grava nada; confira `erros` antes de gravar."""
    fixo = molde.fixos

    # --- registros A100/A170, um par por nota (R13) ---
    novas_linhas_a = []
    for nota in sorted(notas, key=lambda n: n.numero_nfse):
        novas_linhas_a.extend(montar_a100_a170(nota.cod_part, nota.numero_nfse, nota.data_emissao, nota.valor))

    # --- registro 0000: datas da competência (R11) ---
    mes, ano = (int(p) for p in competencia.split("/"))
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    # campos() inclui a tag '0000' em f[0]; layout real do registro 0000:
    # f[0]=0000 f[1]=COD_VER f[2]=TIPO_ESCRIT f[3]=IND_SIT_ESP f[4]=NUM_REC_ANTERIOR f[5]=DT_INI f[6]=DT_FIN ...
    f0000 = campos(molde.linha_0000)
    f0000[5] = f"01{mes:02d}{ano}"
    f0000[6] = f"{ultimo_dia:02d}{mes:02d}{ano}"
    linha_0000_nova = montar_linha(f0000)

    # --- bloco 0 (R12) ---
    linhas_0150 = [linha_0150(c) for c in sorted(clientes, key=_ordem_cod_part)]
    # 0000,0001,0100,0110,0140,0150(N),0200,0990 = 7 + N
    linha_0990 = montar_linha(["0990", str(7 + len(linhas_0150))])
    bloco0 = ([linha_0000_nova, fixo["0001"], fixo["0100"], fixo["0110"], fixo["0140"]]
              + linhas_0150 + [fixo["0200"], linha_0990])

    # --- bloco A ---
    qtd_a100 = len(novas_linhas_a) // 2
    # A001,A010,A100(N),A170(N),A990 = 3 + 2N
    linha_a990 = montar_linha(["A990", str(3 + 2 * qtd_a100)])
    blocoA = [fixo["A001"], fixo["A010"]] + novas_linhas_a + [linha_a990]

    # --- totais do bloco M (R14) ---
    total_receita = sum((n.valor for n in notas), Decimal("0")).quantize(CENTAVO)
    total_txt = formatar_valor_sped(total_receita)
    blocoM = [
        fixo["M001"], fixo["M200"],
        montar_linha(["M400", configuracao.CST, total_txt, "", ""]),
        montar_linha(["M410", configuracao.CODIGO_RECEITA_M410_M810, total_txt, "", ""]),
        fixo["M600"],
        montar_linha(["M800", configuracao.CST, total_txt, "", ""]),
        montar_linha(["M810", configuracao.CODIGO_RECEITA_M410_M810, total_txt, "", ""]),
        fixo["M990"],
    ]
    bloco_fechamento = (
        [fixo["C001"], fixo["C990"], fixo["D001"], fixo["D990"],
         fixo["F001"], fixo["F990"], fixo["I001"], fixo["I990"]]
        + blocoM
        + [fixo["P001"], fixo["P990"], fixo["1001"], fixo["1990"]]
    )
    corpo = bloco0 + blocoA + bloco_fechamento

    # --- bloco 9 (R15) ---
    linha_9001 = fixo["9001"]
    # conta também o próprio 9001 (abre o bloco 9 e vem antes dos 9900); 9990 e 9999 aparecem 1 vez cada
    contagem_tipos = Counter(campos(l)[0] for l in corpo + [linha_9001])
    contagem_tipos["9990"] = 1
    contagem_tipos["9999"] = 1
    # ordem dos registros 9900 = mesma ordem do arquivo do mês anterior
    linhas_9900 = [montar_linha(["9900", tipo, str(contagem_tipos.get(tipo, 0))])
                   for tipo in molde.ordem_9900 if tipo != "9900"]
    linhas_9900.append(montar_linha(["9900", "9900", str(len(linhas_9900) + 1)]))
    bloco9_sem_9999 = [linha_9001] + linhas_9900
    linha_9990 = montar_linha(["9990", str(len(bloco9_sem_9999) + 2)])      # + 9990 + 9999
    total_registros = len(corpo) + len(bloco9_sem_9999) + 2
    linha_9999 = montar_linha(["9999", str(total_registros)])

    linhas = corpo + bloco9_sem_9999 + [linha_9990, linha_9999]
    montado = SpedMontado(linhas=linhas, competencia=competencia, total_receita=total_receita,
                          quantidade_notas=qtd_a100, quantidade_clientes=len(linhas_0150))
    montado.erros = conferir_sped(linhas)
    return montado


def conferir_sped(linhas: list[str]) -> list[str]:
    """R16: recalcula, a partir do arquivo pronto, cada contador e a receita. Lista vazia = arquivo consistente."""
    erros: list[str] = []
    tipos = [campos(l)[0] for l in linhas]
    contagem = Counter(tipos)

    def valor_de(tipo: str, posicao: int = 1) -> str | None:
        achadas = [campos(l) for l in linhas if campos(l)[0] == tipo]
        return achadas[0][posicao] if achadas and len(achadas[0]) > posicao else None

    def conferir(descricao: str, informado: str | None, real: int) -> None:
        if informado != str(real):
            erros.append(f"{descricao}: o arquivo diz {informado}, mas há {real}.")

    conferir("0990 (linhas do bloco 0)", valor_de("0990"), sum(1 for t in tipos if t.startswith("0")))
    conferir("A990 (linhas do bloco A)", valor_de("A990"), sum(1 for t in tipos if t.startswith("A")))
    conferir("9990 (linhas do bloco 9)", valor_de("9990"), sum(1 for t in tipos if t.startswith("9")))
    conferir("9999 (linhas do arquivo)", valor_de("9999"), len(linhas))
    informados_9900 = {campos(l)[1]: campos(l)[2] for l in linhas if campos(l)[0] == "9900"}
    for tipo, quantidade in contagem.items():
        conferir(f"9900 do registro {tipo}", informados_9900.get(tipo), quantidade)
    for tipo in set(informados_9900) - set(contagem):
        erros.append(f"9900 do registro {tipo}: o arquivo diz {informados_9900[tipo]}, mas o registro não existe.")
    if contagem["A100"] != contagem["A170"]:
        erros.append(f"Há {contagem['A100']} A100 e {contagem['A170']} A170 (deveria ser um A170 para cada A100).")

    soma_a100 = sum((valor_do_sped(campos(l)[11]) for l in linhas if campos(l)[0] == "A100"), Decimal("0"))
    for tipo in ("M400", "M410", "M800", "M810"):
        informado = valor_de(tipo, 2)
        if informado is None or valor_do_sped(informado) != soma_a100:
            erros.append(f"{tipo}: o arquivo diz {informado}, mas a soma das notas (A100) é "
                         f"{formatar_valor_sped(soma_a100)}.")
    return erros
