"""Exportações de lotes do site da prefeitura (.txt com tabulação / .csv com ';') -> NotaTomada.

Seção 4.2 da especificação. Colunas localizadas pelo título. A exportação não traz tomador,
competência, cidade/UF do prestador, local da prestação nem município de incidência (V9):
- tomador e competência vêm da tela (R12);
- cidade/UF vêm do cadastro de prestadores (R11, cadastro_prestadores.py);
- CFPS vem da coluna cfps do site (R5);
- o código de retido usa a cidade do prestador (R6).

Uma linha com problema vira falha de leitura ("arquivo (linha N)") e as demais continuam.
"""

from __future__ import annotations

import re
from pathlib import Path

from modulos.escrituracao_tomados import configuracao as cfg
from modulos.escrituracao_tomados.conferencia import ler_tabela_do_site
from modulos.escrituracao_tomados.gerador_txt import normalizar_texto, so_digitos
from modulos.escrituracao_tomados.leitor_danfse import (
    converter_atividade, converter_base, converter_data, converter_documento, converter_valor,
)
from modulos.escrituracao_tomados.modelos import (
    Competencia, ErroLeitura, FalhaLeitura, NotaTomada,
)

ORIGEM = "Exportação"

# "NÃO" do site; alguns .txt exportados vêm com o "Ã" estragado ("N�O").
RE_NAO_ESTRAGADO = re.compile(r"^N.O$")


def converter_retido_site(texto: str) -> bool | None:
    """SIM -> True; NÃO -> False; outro valor (ex.: M) -> None (lançar à mão, R6)."""
    chave = normalizar_texto(texto)
    if chave == "SIM":
        return True
    if chave == "NAO" or RE_NAO_ESTRAGADO.match(texto.strip().upper()):
        return False
    return None


def _obrigatorio(registro: dict, coluna: str) -> str:
    valor = registro.get(coluna, "").strip()
    if not valor:
        raise ErroLeitura(f"Coluna \"{coluna}\" vazia.")
    return valor


def _nota_da_linha(registro: dict, arquivo: str, cnpj_tomador: str,
                   competencia: Competencia) -> NotaTomada:
    numero = so_digitos(_obrigatorio(registro, cfg.SITE_COLUNA_NUMERO))
    if not numero:
        raise ErroLeitura(f"Número da nota \"{registro[cfg.SITE_COLUNA_NUMERO]}\" inválido.")
    cfps = cfg.SITE_CFPS.get(_obrigatorio(registro, cfg.SITE_COLUNA_CFPS).lstrip("0"))
    if cfps is None:
        raise ErroLeitura(f"cfps \"{registro[cfg.SITE_COLUNA_CFPS]}\" não reconhecido (1 ou 2).")
    regime = _obrigatorio(registro, cfg.SITE_COLUNA_REGIME).upper()
    if regime not in cfg.CODIGOS_REGIME:
        raise ErroLeitura(f"enquadradosn \"{regime}\" não reconhecido (N, S ou M).")
    retido_site = _obrigatorio(registro, cfg.SITE_COLUNA_RETIDO)
    return NotaTomada(
        numero=numero,
        data_emissao=converter_data(registro.get(cfg.SITE_COLUNA_EMISSAO), "dtemissao"),
        competencia=competencia,
        prestador_documento=converter_documento(registro.get(cfg.SITE_COLUNA_DOCUMENTO),
                                                "cnpjcpf"),
        prestador_nome=_obrigatorio(registro, cfg.SITE_COLUNA_NOME),
        tomador_documento=so_digitos(cnpj_tomador),
        situacao=_obrigatorio(registro, cfg.SITE_COLUNA_SITUACAO),
        regime=regime,
        codigo_atividade=converter_atividade(registro.get(cfg.SITE_COLUNA_ATIVIDADE)),
        valor_servico=converter_valor(_obrigatorio(registro, cfg.SITE_COLUNA_SERVICOS),
                                      "vlrservicos"),
        deducoes=converter_valor(registro.get(cfg.SITE_COLUNA_DEDUCOES), "vlrdeducoes"),
        desconto_incondicionado=converter_valor(
            registro.get(cfg.SITE_COLUNA_DESCONTO_INCONDICIONADO), "descontoincondicionado"),
        aliquota=converter_valor(registro.get(cfg.SITE_COLUNA_ALIQUOTA), "aliquota"),
        valor_iss=converter_valor(registro.get(cfg.SITE_COLUNA_IMPOSTO), "vlrimposto"),
        base_calculo=converter_base(registro.get(cfg.SITE_COLUNA_BASE_CALCULO)),
        iss_retido=converter_retido_site(retido_site),
        origem=ORIGEM,
        arquivo=arquivo,
        cfps_site=cfps,
        retido_site=retido_site,
    )


def ler_exportacoes(arquivos: list[Path] | None, cnpj_tomador: str, competencia: Competencia
                    ) -> tuple[list[NotaTomada], list[FalhaLeitura]]:
    """Lê as exportações de lotes. Devolve (notas, falhas de leitura), na ordem dos arquivos."""
    notas: list[NotaTomada] = []
    falhas: list[FalhaLeitura] = []
    for caminho in arquivos or []:
        caminho = Path(caminho)
        try:
            registros = ler_tabela_do_site(caminho, cfg.SITE_COLUNAS_EXPORTACAO)
        except ErroLeitura as erro:
            falhas.append(FalhaLeitura(caminho.name, str(erro)))
            continue
        for numero_linha, registro in registros:
            try:
                notas.append(_nota_da_linha(registro, caminho.name, cnpj_tomador, competencia))
            except ErroLeitura as erro:
                falhas.append(FalhaLeitura(f"{caminho.name} (linha {numero_linha})", str(erro)))
    return notas, falhas


def competencia_de_texto(texto: str) -> Competencia:
    """'08/2026' -> Competencia(2026, 8). Levanta ErroLeitura se inválida."""
    achado = re.fullmatch(r"\s*(\d{1,2})/(\d{4})\s*", texto or "")
    if not achado or not 1 <= int(achado.group(1)) <= 12:
        raise ErroLeitura(f"Competência \"{texto}\" inválida (use MM/AAAA).")
    return Competencia(int(achado.group(2)), int(achado.group(1)))
