"""modelo_email.txt -> ModeloEmail. Seção 3.3 da especificação.

- 1ª linha: "Assunto: <texto>"; depois uma linha em branco; o resto é o corpo.
- Marcadores trocados depois pelo programa: {competencia}, {competencia_extenso}, {prazo}, {lista_notas}.
  Comparados sem acento e sem diferença de maiúsculas ({Competência} vale).
- Sem "Assunto:" ou com marcador desconhecido: ErroLeitura (nenhum e-mail é gerado).
- Faltando {prazo} ou {lista_notas}: aviso. Modelo não escolhido ou não encontrado: o de fábrica, com aviso.
"""

from __future__ import annotations

from pathlib import Path

from central.caminhos import caminho_interno
from modulos.notas_pendentes import configuracao as cfg
from modulos.notas_pendentes.modelos import Aviso, ErroLeitura, ModeloEmail
from modulos.notas_pendentes.normalizacao import normalizar

ORIGEM_FABRICA = "modelo de fábrica"


def caminho_modelo_fabrica() -> Path:
    return caminho_interno(*cfg.MODELO_FABRICA)


def sugerir_modelo(pasta_mes: Path) -> Path | None:
    """O modelo da pasta "config" ao lado da pasta do mês, se existir (a tela chama em segundo plano)."""
    candidato = Path(pasta_mes).parent / cfg.PASTA_MODELO_SUGERIDA / cfg.ARQUIVO_MODELO
    return candidato if candidato.is_file() else None


def marcador(texto: str) -> str:
    """"{ Competência }" -> "competencia": o nome do marcador como o programa o conhece."""
    return normalizar(texto).replace(" ", "_")


def _ler_texto(caminho: Path) -> str:
    try:
        dados = caminho.read_bytes()
    except OSError as erro:
        raise ErroLeitura(f"Não foi possível ler o modelo do e-mail {caminho}: {erro}") from None
    for codificacao in cfg.MODELO_CODIFICACOES:
        try:
            return dados.decode(codificacao)
        except UnicodeDecodeError:
            continue
    raise ErroLeitura(f"O modelo do e-mail {caminho} não está em texto (UTF-8). Salve-o pelo Bloco de Notas.")


def interpretar(texto: str, origem: str) -> ModeloEmail:
    """Separa assunto e corpo e confere os marcadores. Levanta ErroLeitura com o que corrigir."""
    linhas = texto.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while linhas and not linhas[0].strip():
        linhas.pop(0)
    primeira = linhas[0].strip() if linhas else ""
    if not normalizar(primeira).startswith(cfg.PREFIXO_ASSUNTO):
        raise ErroLeitura(f"O modelo do e-mail ({origem}) precisa começar com a linha \"Assunto: ...\".")
    assunto = primeira.split(":", 1)[1].strip()
    if not assunto:
        raise ErroLeitura(f"O modelo do e-mail ({origem}) está com o assunto vazio.")
    corpo_linhas = linhas[1:]
    while corpo_linhas and not corpo_linhas[0].strip():
        corpo_linhas.pop(0)
    corpo = "\n".join(linha.rstrip() for linha in corpo_linhas).rstrip()
    if not corpo:
        raise ErroLeitura(f"O modelo do e-mail ({origem}) não tem texto depois do assunto.")

    encontrados = [marcador(m) for m in cfg.RE_MARCADOR.findall(assunto + "\n" + corpo)]
    desconhecidos = sorted({f"{{{m}}}" for m in encontrados if m not in cfg.MARCADORES})
    if desconhecidos:
        validos = ", ".join(f"{{{m}}}" for m in cfg.MARCADORES)
        raise ErroLeitura(f"O modelo do e-mail ({origem}) tem marcador que o programa não conhece: "
                          f"{', '.join(desconhecidos)}. Os marcadores válidos são {validos}.")
    modelo = ModeloEmail(assunto, corpo, origem, de_fabrica=origem == ORIGEM_FABRICA)
    for esperado in cfg.MARCADORES_ESPERADOS:
        if esperado not in encontrados:
            modelo.avisos.append(Aviso(origem, f"O modelo do e-mail não tem o marcador {{{esperado}}}: "
                                               "os e-mails saem sem essa informação."))
    return modelo


def ler_modelo(caminho: Path | None) -> ModeloEmail:
    """Lê o modelo escolhido; sem ele (ou não encontrado), o de fábrica, com aviso."""
    aviso = None
    if caminho is None:
        aviso = "Modelo do e-mail não escolhido: usei o modelo de fábrica."
    elif not Path(caminho).is_file():
        aviso = f"Modelo do e-mail não encontrado ({caminho}): usei o modelo de fábrica."
    if aviso:
        modelo = interpretar(_ler_texto(caminho_modelo_fabrica()), ORIGEM_FABRICA)
        modelo.avisos.insert(0, Aviso(cfg.ARQUIVO_MODELO, aviso))
        return modelo
    return interpretar(_ler_texto(Path(caminho)), str(caminho))
