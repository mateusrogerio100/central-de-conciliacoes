"""Cadastro de prestadores: cidade/UF por CNPJ/CPF (R11).

Arquivo %APPDATA%\\CentralConciliacoes\\escrituracao_tomados\\prestadores.json (fora do projeto e
do git, tem CNPJs reais): {documento: {cidade, uf, origem, atualizado_em}}.

Ordem para achar a cidade de um prestador:
1. o PDF da nota (e o cadastro é atualizado com ela);
2. o cadastro;
3. a consulta pública de CNPJ pela internet (BrasilAPI; reserva CNPJ.ws) — só CNPJ;
4. a pergunta na tela (função `perguntar_cidade` que a tela fornece).

A consulta é INJETÁVEL: quem chama passa a função. Nos testes ela é sempre simulada.
"""

from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Callable

from modulos.escrituracao_tomados import configuracao as cfg
from modulos.escrituracao_tomados.gerador_txt import normalizar_texto, so_digitos
from modulos.escrituracao_tomados.modelos import Aviso, NotaTomada

Cidade = tuple[str, str]                                   # (cidade, UF)
ConsultaCnpj = Callable[[str], Cidade | None]              # levanta exceção se falhar
PerguntaCidade = Callable[[str, str], Cidade | None]       # (documento, nome) -> cidade ou None


def pasta_dados_usuario() -> Path:
    """%APPDATA%\\CentralConciliacoes\\escrituracao_tomados (ou a pasta do usuário)."""
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / cfg.PASTA_DADOS_USUARIO / cfg.SUBPASTA_MODULO


def _cidade_valida(cidade: str, uf: str) -> Cidade | None:
    cidade, uf = normalizar_texto(cidade), normalizar_texto(uf)
    if cidade and len(uf) == 2 and uf.isalpha():
        return cidade, uf
    return None


class CadastroPrestadores:
    def __init__(self, caminho: Path | None = None):
        self.caminho = Path(caminho) if caminho else (pasta_dados_usuario()
                                                      / cfg.NOME_CADASTRO_PRESTADORES)
        self.dados: dict[str, dict] = {}
        self.problema_ao_abrir = ""
        self.problema_ao_salvar = ""
        self._alterado = False
        if self.caminho.exists():
            try:
                dados = json.loads(self.caminho.read_text(encoding="utf-8"))
                if not isinstance(dados, dict):
                    raise ValueError("formato inesperado")
                self.dados = {so_digitos(k): v for k, v in dados.items() if isinstance(v, dict)}
            except (OSError, ValueError) as erro:
                self.problema_ao_abrir = (f"O cadastro de prestadores ({self.caminho}) não pôde "
                                          f"ser lido ({erro}); começando vazio.")

    def obter(self, documento: str) -> Cidade | None:
        item = self.dados.get(so_digitos(documento))
        if not item:
            return None
        return _cidade_valida(item.get("cidade", ""), item.get("uf", ""))

    def registrar(self, documento: str, cidade: str, uf: str, origem: str) -> None:
        valida = _cidade_valida(cidade, uf)
        if valida is None:
            return
        chave = so_digitos(documento)
        atual = self.dados.get(chave, {})
        if (atual.get("cidade"), atual.get("uf")) == valida:
            return
        self.dados[chave] = {"cidade": valida[0], "uf": valida[1], "origem": origem,
                             "atualizado_em": datetime.now().strftime("%Y-%m-%d %H:%M")}
        self._alterado = True

    def salvar(self) -> None:
        """Grava só se algo mudou. Nunca derruba o processamento: se falhar, o motivo fica em
        `problema_ao_salvar` (o processamento mostra como aviso)."""
        self.problema_ao_salvar = ""
        if not self._alterado:
            return
        try:
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
            texto = json.dumps(dict(sorted(self.dados.items())), ensure_ascii=False, indent=2)
            self.caminho.write_text(texto, encoding="utf-8")
            self._alterado = False
        except OSError as erro:
            self.problema_ao_salvar = f"O cadastro de prestadores não pôde ser gravado ({erro})."


# ---------------------------------------------------------------------------
# Consulta pública de CNPJ (internet)
# ---------------------------------------------------------------------------


def _baixar_json(url: str) -> dict:
    pedido = urllib.request.Request(url, headers={"User-Agent": "CentralConciliacoes",
                                                  "Accept": "application/json"})
    with urllib.request.urlopen(pedido, timeout=cfg.TEMPO_LIMITE_CONSULTA_SEGUNDOS) as resposta:
        return json.loads(resposta.read().decode("utf-8"))


def consultar_cnpj_internet(cnpj: str) -> Cidade | None:
    """BrasilAPI; se falhar, CNPJ.ws. Devolve (cidade, UF) ou None (CNPJ não encontrado).

    Levanta a exceção da última tentativa se as duas falharem (sem internet, fora do ar...).
    """
    cnpj = so_digitos(cnpj)
    ultimo_erro: Exception | None = None
    try:
        dados = _baixar_json(cfg.URL_CONSULTA_CNPJ.format(cnpj=cnpj))
        achada = _cidade_valida(dados.get("municipio", ""), dados.get("uf", ""))
        if achada:
            return achada
    except Exception as erro:
        ultimo_erro = erro
    try:
        dados = _baixar_json(cfg.URL_CONSULTA_CNPJ_RESERVA.format(cnpj=cnpj))
        estabelecimento = dados.get("estabelecimento") or {}
        return _cidade_valida((estabelecimento.get("cidade") or {}).get("nome", ""),
                              (estabelecimento.get("estado") or {}).get("sigla", ""))
    except Exception as erro:
        raise erro from ultimo_erro


# ---------------------------------------------------------------------------
# Preencher a cidade das notas
# ---------------------------------------------------------------------------


def _aviso(nota: NotaTomada, tipo: str, mensagem: str) -> Aviso:
    return Aviso(tipo=tipo, mensagem=mensagem, arquivo=nota.arquivo,
                 nota=f"{nota.numero} - {nota.prestador_nome}")


def aprender_dos_pdfs(notas: list[NotaTomada], cadastro: CadastroPrestadores) -> None:
    """Passo 1: a cidade que está no PDF vai para o cadastro."""
    for nota in notas:
        if nota.origem == "PDF" and nota.prestador_cidade and nota.prestador_uf:
            cadastro.registrar(nota.prestador_documento, nota.prestador_cidade,
                               nota.prestador_uf, cfg.ORIGEM_CIDADE_PDF)


def preencher_cidades(notas: list[NotaTomada], cadastro: CadastroPrestadores,
                      consultar: ConsultaCnpj | None = consultar_cnpj_internet,
                      perguntar_cidade: PerguntaCidade | None = None) -> list[Aviso]:
    """Passos 2 a 4 para as notas sem cidade. Consulta e pergunta uma vez por prestador.

    Nota que continua sem cidade fica assim (as regras a mandam para "lançar à mão").
    """
    avisos: list[Aviso] = []
    resolvidos: dict[str, Cidade | None] = {}
    for nota in notas:
        if nota.prestador_cidade and nota.prestador_uf:
            continue
        documento = so_digitos(nota.prestador_documento)
        if documento not in resolvidos:
            resolvidos[documento] = _procurar_cidade(nota, cadastro, consultar,
                                                     perguntar_cidade, avisos)
        achada = resolvidos[documento]
        if achada:
            nota.prestador_cidade, nota.prestador_uf = achada
    return avisos


def _procurar_cidade(nota, cadastro, consultar, perguntar_cidade, avisos) -> Cidade | None:
    documento = so_digitos(nota.prestador_documento)
    achada = cadastro.obter(documento)
    if achada:
        return achada

    if len(documento) == 14 and consultar is not None:
        try:
            achada = consultar(documento)
        except Exception as erro:
            avisos.append(_aviso(nota, "Consulta de CNPJ falhou",
                                 f"Não foi possível consultar o CNPJ {documento} pela internet "
                                 f"({erro})."))
        else:
            if achada and _cidade_valida(*achada):
                achada = _cidade_valida(*achada)
                cadastro.registrar(documento, *achada, cfg.ORIGEM_CIDADE_CONSULTA)
                avisos.append(_aviso(nota, "Cidade pela consulta de CNPJ",
                                     f"Cidade do prestador obtida na consulta pública de CNPJ: "
                                     f"{achada[0]}/{achada[1]}."))
                return achada
            avisos.append(_aviso(nota, "Consulta de CNPJ falhou",
                                 f"CNPJ {documento} não encontrado na consulta pública."))

    if perguntar_cidade is not None:
        resposta = perguntar_cidade(documento, nota.prestador_nome)
        achada = _cidade_valida(*resposta) if resposta else None
        if achada:
            cadastro.registrar(documento, *achada, cfg.ORIGEM_CIDADE_INFORMADA)
            avisos.append(_aviso(nota, "Cidade informada à mão",
                                 f"Cidade do prestador informada na tela: {achada[0]}/{achada[1]}."))
            return achada
    avisos.append(_aviso(nota, "Cidade não encontrada",
                         f"Cidade do prestador {documento} não encontrada."))
    return None
