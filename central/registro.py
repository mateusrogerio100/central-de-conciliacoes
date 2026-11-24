"""Registro dos módulos que aparecem no menu da Central (ESPECIFICACAO, seção 4.2).

Para colocar uma conciliação nova no menu: crie a pasta modulos/<nome>/ seguindo o contrato
de central/modulo_base.py e acrescente o nome dela na seção certa de SECOES. A ordem das
seções e dos nomes é a ordem do menu.

Cada módulo é importado separadamente: se um deles tiver erro, ele aparece no menu com a
mensagem do problema e os outros continuam funcionando.
"""

from __future__ import annotations

import importlib
import traceback
from dataclasses import dataclass

from central.modulo_base import ErroModulo, InfoModulo

# (nome da seção no menu, módulos da seção). Seção sem módulo não aparece.
SECOES: list[tuple[str, list[str]]] = [
    ("FISCAL", [
        "conferencia_nf",
        "checklist_contratos",
        "notas_pendentes",
        "escrituracao_tomados",
        "conferencia_iss",
        "efd_contribuicoes",
    ]),
    ("CONCILIAÇÕES · ATIVO", [
        "bancos",
        "clientes_cmd",
        "conciliacao_estoque",
        "conciliacao_imobilizado",
        "credito_estouro",
    ]),
    ("CONCILIAÇÕES · PASSIVO", [
        "conciliacao_fornecedores",
        "conciliacao_rescisoes",
        "honorarios_medicos",
        "planilha_hm",
        "subvencoes",
    ]),
    ("RECEITAS", [
        "convenios",
    ]),
    ("FERRAMENTAS", [
        "imprimir_pdfs",
        "historico_uso",
    ]),
]

NOMES_MODULOS: list[str] = [nome for _, nomes in SECOES for nome in nomes]
SECAO_DO_MODULO: dict[str, str] = {nome: secao for secao, nomes in SECOES for nome in nomes}

# Módulo mostrado ao abrir a Central: sempre o que abre mais rápido (decisão do usuário, 20/10/2026;
# antes era o último usado, e a Conferência de NF deixava a abertura ~3 s mais lenta).
# Medido na Unificação 10 (20/10/2026, 12 módulos): Imprimir PDFs 1,35 s; Conferência ISS 1,96 s; Serviços Tomados
# 2,07 s; Subvenções 2,16 s; ... Conferência de NF e Rescisões 3,7 s.
MODULO_INICIAL = "imprimir_pdfs"

SECAO_PADRAO = "CONCILIAÇÕES"       # módulos carregados fora de SECOES (ex.: os de teste)
PACOTE_MODULOS = "modulos"


@dataclass
class ModuloCarregado:
    """Resultado da carga de um módulo: as informações dele ou o erro que impediu a carga."""

    nome_pasta: str
    info: InfoModulo | None = None
    erro: str = ""                  # mensagem para o usuário (vazio = carregou bem)
    detalhe_tecnico: str = ""       # traceback, para quem for consertar
    secao: str = SECAO_PADRAO       # seção do menu em que o item aparece

    @property
    def ok(self) -> bool:
        return self.info is not None

    @property
    def chave(self) -> str:
        return self.info.chave if self.info else self.nome_pasta

    @property
    def nome(self) -> str:
        return self.info.nome if self.info else self.nome_pasta


def carregar_modulos(nomes: list[str] | None = None, pacote: str = PACOTE_MODULOS) -> list[ModuloCarregado]:
    """Importa cada módulo da lista e devolve um ModuloCarregado por nome, na mesma ordem.

    Nunca levanta exceção por causa de um módulo: o problema fica registrado no próprio item.
    Nomes repetidos ou chaves repetidas também viram erro no item repetido.
    """
    if nomes is None:
        nomes = NOMES_MODULOS

    carregados: list[ModuloCarregado] = []
    chaves_usadas: set[str] = set()
    nomes_vistos: set[str] = set()

    for nome in nomes:
        item = ModuloCarregado(nome_pasta=nome, secao=SECAO_DO_MODULO.get(nome, SECAO_PADRAO))
        carregados.append(item)

        if nome in nomes_vistos:
            item.erro = f"O módulo '{nome}' aparece mais de uma vez no registro."
            continue
        nomes_vistos.add(nome)

        try:
            modulo_python = importlib.import_module(f"{pacote}.{nome}")
            info = getattr(modulo_python, "MODULO", None)
            if not isinstance(info, InfoModulo):
                raise ErroModulo(f"A pasta '{nome}' não define a variável MODULO (InfoModulo).")
        except ErroModulo as erro:
            item.erro = str(erro)
            item.detalhe_tecnico = traceback.format_exc()
            continue
        except Exception as erro:  # qualquer falha de importação isola só este módulo
            item.erro = f"Não foi possível carregar o módulo '{nome}': {erro}"
            item.detalhe_tecnico = traceback.format_exc()
            continue

        if info.chave in chaves_usadas:
            item.erro = f"A chave '{info.chave}' já é usada por outro módulo do registro."
            continue
        chaves_usadas.add(info.chave)
        item.info = info

    return carregados


def modulo_inicial(carregados: list[ModuloCarregado], chave_preferida: str | None) -> ModuloCarregado | None:
    """Módulo mostrado ao abrir: o preferido (MODULO_INICIAL), se existir e estiver ok; senão, o primeiro ok."""
    validos = [m for m in carregados if m.ok]
    for modulo in validos:
        if modulo.chave == chave_preferida:
            return modulo
    if validos:
        return validos[0]
    return carregados[0] if carregados else None
