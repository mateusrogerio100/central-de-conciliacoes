"""Cadastro de clientes (clientes.json) — ESPECIFICACAO_EFD_CONTRIBUICOES.md, seção 4.4.

Veio da classe CadastroClientes e das funções carregar_clientes / salvar_clientes /
bootstrap_clientes_a_partir_do_sped do `gerar_sped_mensal.py` da origem. Mesmo formato de arquivo
({"clientes": [{"cod_part", "nome", "cnpj", "codigo_ibge"}, ...]}) e mesma regra de código
(cliente conhecido = mesmo CNPJ; cliente novo = maior código + 1). O que mudou (decisões do usuário, 05/11/2026):
- o arquivo é ESCOLHIDO NA TELA (ajuste de 05/11/2026; antes era um caminho fixo na rede): a equipe escolhe o
  mesmo arquivo numa pasta da rede para usar a mesma lista; arquivo inacessível → não gera (R9);
- sem cadastro ainda: criar um novo a partir dos 0150 do SPED anterior, num arquivo escolhido;
- gravação segura: relê o arquivo antes de gravar (se mudou desde a leitura, nada é sobrescrito), guarda uma
  cópia do anterior em copias\\ e grava num arquivo temporário antes de trocar;
- cliente conhecido com nome ou Código IBGE diferente no PDF: fica o do cadastro, com aviso;
- o Código IBGE que faltar num cliente novo pode ser digitado na tela (R7).
Este arquivo não sabe nada da tela: quem chama decide quando ler (em segundo plano) e quando gravar.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from modulos.efd_contribuicoes import configuracao
from modulos.efd_contribuicoes.leitor_sped import MoldeSped, campos
from modulos.efd_contribuicoes.montagem_sped import ClienteSped

ORIGEM_PDF = "PDF"
ORIGEM_DIGITADO = "digitado"


class ErroCadastro(Exception):
    """Problema com o cadastro (arquivo inacessível, ilegível...): mensagem para a tela."""


class CadastroMudou(ErroCadastro):
    """Outra pessoa gravou o cadastro depois que ele foi lido: nada foi sobrescrito."""


def nome_comparavel(nome: str) -> str:
    """Nome sem acento, maiúscula, pontuação e espaços repetidos: "Serviço  de Assistência - Cidade Alfa." →
    "servico de assistencia cidade_alfa"."""
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", nome) if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", sem_acento.casefold()))


def codigo_ibge_valido(codigo: str | None) -> bool:
    return bool(codigo) and bool(re.fullmatch(r"\d{7}", codigo.strip()))


@dataclass
class Cadastro:
    caminho: Path                       # o clientes.json escolhido na tela
    clientes: dict[str, dict] = field(default_factory=dict)     # cnpj -> {"cod_part", "nome", "cnpj", "codigo_ibge"}
    existe: bool = True                 # False = cadastro novo (o arquivo é criado ao gerar)
    texto_lido: str | None = None       # o arquivo como estava ao ler (para saber se outra pessoa gravou depois)
    novos: dict[str, str] = field(default_factory=dict)         # cnpj -> origem do Código IBGE (PDF ou digitado)
    avisos: list[str] = field(default_factory=list)

    @property
    def pasta(self) -> Path:
        return self.caminho.parent

    @property
    def max_cod_part(self) -> int:
        codigos = [int(c["cod_part"]) for c in self.clientes.values() if str(c["cod_part"]).isdigit()]
        return max(codigos) if codigos else 0

    def obter_cod_part(self, cnpj_digitos: str, nome: str, codigo_ibge: str | None) -> str:
        """Código do participante; cadastra um cliente novo (próximo código) se o CNPJ ainda não for conhecido."""
        conhecido = self.clientes.get(cnpj_digitos)
        if conhecido is not None:
            if cnpj_digitos not in self.novos:
                self._avisar_diferencas(conhecido, nome, codigo_ibge)
            return conhecido["cod_part"]
        novo_cod = str(self.max_cod_part + 1)
        self.clientes[cnpj_digitos] = {"cod_part": novo_cod, "nome": nome, "cnpj": cnpj_digitos,
                                       "codigo_ibge": codigo_ibge or ""}
        self.novos[cnpj_digitos] = ORIGEM_PDF if codigo_ibge else ""
        return novo_cod

    def _avisar_diferencas(self, conhecido: dict, nome: str, codigo_ibge: str | None) -> None:
        # Pedido do usuário (05/11/2026): diferença só de maiúscula, acento, pontuação ou espaços não é aviso
        # ("Prefeitura Municipal de Restinga" = "PREFEITURA MUNICIPAL DE RESTINGA"), e cada aviso sai uma vez por
        # cliente, mesmo com várias notas dele.
        avisos = []
        if nome and nome_comparavel(nome) != nome_comparavel(conhecido["nome"]):
            avisos.append(f"Cliente {conhecido['cod_part']}: no PDF o nome é \"{nome}\"; ficou o do cadastro, "
                          f"\"{conhecido['nome']}\".")
        if codigo_ibge and codigo_ibge != conhecido["codigo_ibge"]:
            avisos.append(f"Cliente {conhecido['cod_part']} ({conhecido['nome']}): no PDF o Código IBGE é "
                          f"{codigo_ibge}; ficou o do cadastro, {conhecido['codigo_ibge'] or '(vazio)'}.")
        self.avisos.extend(a for a in avisos if a not in self.avisos)

    def novos_sem_ibge(self) -> list[dict]:
        """Clientes novos sem Código IBGE (R7: o SPED não pode ser gerado assim)."""
        return [self.clientes[c] for c in self.novos if not codigo_ibge_valido(self.clientes[c]["codigo_ibge"])]

    def definir_ibge(self, cnpj_digitos: str, codigo: str) -> None:
        """R7: o código digitado na tela para um cliente novo."""
        codigo = codigo.strip()
        if cnpj_digitos not in self.novos:
            raise ErroCadastro("Só dá para digitar o Código IBGE de um cliente novo desta geração.")
        if not codigo_ibge_valido(codigo):
            raise ErroCadastro(f"Código IBGE inválido: \"{codigo}\" (são 7 números, ex.: 3516200).")
        self.clientes[cnpj_digitos]["codigo_ibge"] = codigo
        self.novos[cnpj_digitos] = ORIGEM_DIGITADO

    def lista_ordenada(self) -> list[dict]:
        return sorted(self.clientes.values(), key=lambda c: int(c["cod_part"]) if str(c["cod_part"]).isdigit() else 0)

    def para_sped(self) -> list[ClienteSped]:
        return [ClienteSped(c["cod_part"], c["nome"], c["cnpj"], c["codigo_ibge"]) for c in self.lista_ordenada()]


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------


def _clientes_do_texto(texto: str, nome: str) -> list[dict]:
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as erro:
        raise ErroCadastro(f"{nome}: o arquivo não é um cadastro válido ({erro.msg}, linha {erro.lineno}).")
    clientes = dados.get("clientes") if isinstance(dados, dict) else None
    if not isinstance(clientes, list):
        raise ErroCadastro(f"{nome}: o arquivo não tem a lista \"clientes\".")
    lidos = []
    for posicao, cliente in enumerate(clientes, start=1):
        if not isinstance(cliente, dict) or not all(k in cliente for k in ("cod_part", "nome", "cnpj")):
            raise ErroCadastro(f"{nome}: o cliente nº {posicao} está incompleto (precisa de cod_part, nome e cnpj).")
        lidos.append({"cod_part": str(cliente["cod_part"]), "nome": str(cliente["nome"]),
                      "cnpj": re.sub(r"\D", "", str(cliente["cnpj"])),
                      "codigo_ibge": str(cliente.get("codigo_ibge") or "")})
    repetidos = _repetidos([c["cnpj"] for c in lidos]) + _repetidos([c["cod_part"] for c in lidos])
    if repetidos:
        raise ErroCadastro(f"{nome}: CNPJ ou código repetido no cadastro ({', '.join(repetidos)}); confira o arquivo.")
    return lidos


def _repetidos(valores: list[str]) -> list[str]:
    vistos, repetidos = set(), []
    for valor in valores:
        if valor in vistos and valor not in repetidos:
            repetidos.append(valor)
        vistos.add(valor)
    return repetidos


def _pasta_acessivel(pasta: Path) -> bool:
    try:
        return pasta.is_dir()
    except OSError:
        return False


def carregar_cadastro(caminho: Path) -> Cadastro:
    """Lê o clientes.json escolhido. Pasta ou arquivo inacessível → ErroCadastro (R9: sem ele não gera)."""
    caminho = Path(caminho)
    if not _pasta_acessivel(caminho.parent):
        raise ErroCadastro(f"Sem acesso à pasta do cadastro de clientes ({caminho.parent}). Sem ele não dá para "
                           "gerar o SPED: confira a conexão com a rede e tente de novo.")
    if not caminho.is_file():
        raise ErroCadastro(f"O cadastro de clientes {caminho} não foi encontrado (foi movido ou renomeado?). "
                           "Escolha o arquivo de novo.")
    texto = _ler_texto(caminho)
    clientes = _clientes_do_texto(texto, caminho.name)
    return Cadastro(caminho=caminho, clientes={c["cnpj"]: c for c in clientes}, texto_lido=texto)


def novo_cadastro(caminho: Path, molde: MoldeSped) -> Cadastro:
    """Sem cadastro ainda: um cadastro novo com os clientes dos 0150 do SPED anterior, que será gravado em
    `caminho` ao gerar (era o --bootstrap-clientes da origem). Arquivo que já existe → ErroCadastro."""
    caminho = Path(caminho)
    if not _pasta_acessivel(caminho.parent):
        raise ErroCadastro(f"Sem acesso à pasta {caminho.parent}.")
    if caminho.exists():
        raise ErroCadastro(f"Já existe um cadastro em {caminho}: escolha esse arquivo no cartão do cadastro.")
    cadastro = Cadastro(caminho=caminho, existe=False)
    criar_a_partir_do_sped(cadastro, molde)
    return cadastro


def _ler_texto(caminho: Path) -> str:
    try:
        return caminho.read_text(encoding="utf-8")
    except OSError as erro:
        raise ErroCadastro(f"Não foi possível ler o cadastro {caminho}: {erro.strerror or erro}.")


def criar_a_partir_do_sped(cadastro: Cadastro, molde: MoldeSped) -> int:
    """Os clientes dos 0150 do SPED anterior (era o --bootstrap-clientes da origem). Devolve quantos."""
    clientes = []
    for linha in molde.linhas_0150:
        f = campos(linha)
        clientes.append({"cod_part": f[1], "nome": f[2], "cnpj": re.sub(r"\D", "", f[4]) if len(f) > 4 else "",
                         "codigo_ibge": f[7] if len(f) > 7 else ""})
    cadastro.clientes = {c["cnpj"]: c for c in clientes}
    return len(clientes)


# ---------------------------------------------------------------------------
# Gravação segura
# ---------------------------------------------------------------------------


def texto_do_cadastro(cadastro: Cadastro) -> str:
    return json.dumps({"clientes": cadastro.lista_ordenada()}, ensure_ascii=False, indent=2)


def gravar_cadastro(cadastro: Cadastro, agora: datetime | None = None) -> Path | None:
    """Grava o cadastro no arquivo escolhido. Devolve o caminho da cópia de segurança (None se ainda não havia arquivo).

    Antes de gravar, relê o arquivo: se outra pessoa gravou depois da leitura → CadastroMudou, nada é gravado.
    """
    agora = agora or datetime.now()
    caminho = cadastro.caminho
    try:
        existe_agora = caminho.exists()
        atual = _ler_texto(caminho) if existe_agora else None
    except OSError as erro:
        raise ErroCadastro(f"Sem acesso ao cadastro ({caminho}): {erro}.")
    if atual != cadastro.texto_lido:
        raise CadastroMudou("O cadastro de clientes foi alterado por outra pessoa enquanto você gerava. "
                            "Nada foi sobrescrito: gere de novo para usar a lista atualizada.")
    copia = None
    try:
        if existe_agora:
            pasta_copias = cadastro.pasta / configuracao.PASTA_COPIAS
            pasta_copias.mkdir(exist_ok=True)
            copia = _caminho_livre(pasta_copias / f"clientes_{agora:%Y-%m-%d_%Hh%M}.json")
            copia.write_text(atual, encoding="utf-8")
        novo_texto = texto_do_cadastro(cadastro)
        temporario = caminho.with_name(caminho.name + ".gravando")
        temporario.write_text(novo_texto, encoding="utf-8")
        os.replace(temporario, caminho)
    except OSError as erro:
        raise ErroCadastro(f"Não foi possível gravar o cadastro ({caminho}): {erro.strerror or erro}.")
    cadastro.texto_lido = novo_texto
    cadastro.existe = True
    return copia


def _caminho_livre(caminho: Path) -> Path:
    candidato, contador = caminho, 2
    while candidato.exists():
        candidato = caminho.with_name(f"{caminho.stem}_{contador}{caminho.suffix}")
        contador += 1
    return candidato
