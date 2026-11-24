"""Porta de entrada da Conciliação do Imobilizado – AME's para a tela (ESPECIFICACAO da Central, seção 4.3).

A regra de negócio é a do Conciliações AMES, copiada sem mudanças (leitor_*.py, conciliador.py,
modelos.py, processar.py, relatorio_excel.py, resumo.py; e base_iss.py com os trechos do pacote do
ISS que ele usa; ESPECIFICACAO_IMOBILIZADO.md). Aqui só:
- processar(): chama processar_bens traduzindo o andamento para o formato da Central,
  progresso(texto, fração de 0 a 1) (o código copiado usa ao_progredir(percentual, texto));
- as prévias e os números da tela, reexportados (era o patrimonio/__init__.py de lá);
- a pasta onde salvar, lembrada entre aberturas (na primeira vez, a do Conciliações AMES);
- a aba "Comparação Ativo x Passivo" (pedido do usuário, 05/11/2026; regra em ativo_passivo.py):
  processar_ativo_passivo() e a prévia dos razões contábeis.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

from central.preferencias import ler_preferencias_modulo, ler_programa_antigo, salvar_preferencias_modulo
from modulos.conciliacao_imobilizado.ativo_passivo import (  # noqa: F401
    LADO_ATIVO,
    LADO_PASSIVO,
    ORDEM_SITUACOES_AP,
    SITUACAO_AP_CONFERE,
    SITUACAO_AP_DIFERENCA,
    SITUACAO_AP_SEM_PAR,
    PreviaRazaoContabil,
    ResultadoAtivoPassivo,
    comparar_ativo_passivo,
    mensagem_do_par,
    previa_razao_contabil,
)
from modulos.conciliacao_imobilizado.base_iss import NIVEL_ERRO  # noqa: F401  (reexportados para a tela)
from modulos.conciliacao_imobilizado.base_iss import caminho_do_relatorio
from modulos.conciliacao_imobilizado.modelos import (  # noqa: F401
    SITUACAO_CONFERE,
    SITUACAO_DIFERENCA,
    SITUACAO_DIFERENCA_EXPLICADA,
    SITUACAO_DIFERENCA_SEM_EXPLICACAO,
    SITUACAO_SOMENTE_BALANCETE,
    SITUACAO_SOMENTE_PATRIMONIO,
    ResultadoBens,
)
from modulos.conciliacao_imobilizado.processar import (  # noqa: F401
    PreviaBens,
    previa_baixas,
    previa_balancetes,
    previa_bens_adquiridos,
    previa_razao,
    processar_bens,
)
from modulos.conciliacao_imobilizado.resumo import (  # noqa: F401
    diferencas_pendentes,
    linhas_do_resumo,
    numeros_principais,
    relatorios_que_ajudariam,
)

CHAVE = "conciliacao_imobilizado"
CHAVE_PROGRAMA_ANTIGO = "pasta_imobilizado"       # no %APPDATA%\ConferenciaISSRB\config.json


def processar(razao: Path, balancetes: list[Path], bens_adquiridos: Path | None = None,
              baixas: Path | None = None, pasta_destino: Path | None = None,
              progresso: Callable[[str, float | None], None] | None = None,
              agora: datetime | None = None) -> ResultadoBens:
    """Faz a conciliação (nunca levanta exceção). pasta_destino None = pasta do patrimônio."""
    def ao_progredir(percentual: int, texto: str) -> None:
        if progresso is not None:
            progresso(texto, percentual / 100)

    return processar_bens(razao, balancetes, arquivo_bens_adquiridos=bens_adquiridos, arquivo_baixas=baixas,
                          ao_progredir=ao_progredir, agora=agora, pasta_destino=pasta_destino)


def processar_ativo_passivo(arquivo_ativo: Path, arquivo_passivo: Path, pasta_destino: Path | None = None,
                            progresso: Callable[[str, float | None], None] | None = None,
                            agora: datetime | None = None) -> ResultadoAtivoPassivo:
    """Compara os razões do Ativo e do Passivo e grava a planilha (nunca levanta exceção).
    pasta_destino None = pasta do razão do Ativo."""
    from modulos.conciliacao_imobilizado.relatorio_ativo_passivo import (
        PREFIXO_ARQUIVO_AP,
        gerar_relatorio_ativo_passivo,
    )

    def avisar(texto: str, fracao: float) -> None:
        if progresso is not None:
            progresso(texto, fracao)

    agora = agora or datetime.now()
    avisar("Lendo os razões...", 0.1)
    resultado = comparar_ativo_passivo(Path(arquivo_ativo), Path(arquivo_passivo))
    if not resultado.pares:
        avisar("Relatório não gerado.", 1.0)
        return resultado

    avisar("Gerando o relatório em Excel...", 0.7)
    pasta = Path(pasta_destino) if pasta_destino else Path(arquivo_ativo).parent
    if not pasta.is_dir():
        resultado.erro = (f"A pasta escolhida para salvar a planilha não existe mais: {pasta}. "
                          "Escolha outra pasta e gere de novo.")
        avisar("Relatório não salvo.", 1.0)
        return resultado
    unidade = resultado.ame.replace(" - ", " ")
    caminho = caminho_do_relatorio(pasta, resultado.competencia, [unidade] if unidade else [], agora,
                                   prefixo=PREFIXO_ARQUIVO_AP)
    try:
        resultado.caminho_relatorio = gerar_relatorio_ativo_passivo(resultado, caminho, gerado_em=agora)
    except PermissionError:
        resultado.erro = (f"Não foi possível salvar o relatório na pasta {caminho.parent}. "
                          "Verifique se você tem permissão para gravar nessa pasta "
                          "(ou se a planilha está aberta no Excel) e tente de novo.")
    except OSError as erro:
        resultado.erro = f"Não foi possível salvar o relatório em {caminho}: {erro.strerror or erro}."
    avisar("Concluído." if not resultado.erro else "Relatório não salvo.", 1.0)
    return resultado


# ---------------------------------------------------------------------------
# Pasta lembrada
# ---------------------------------------------------------------------------


def ler_pasta_lembrada(pasta_preferencias: Path | None = None, arquivo_antigo: Path | None = None) -> str:
    """A última pasta escolhida para salvar. Sem nada guardado na Central, a do Conciliações AMES."""
    dados = ler_preferencias_modulo(CHAVE, pasta_preferencias)
    if "pasta" in dados:
        return dados["pasta"] if isinstance(dados["pasta"], str) else ""
    antiga = ler_programa_antigo(arquivo_antigo).get(CHAVE_PROGRAMA_ANTIGO, "")
    return antiga if isinstance(antiga, str) else ""


def salvar_pasta_lembrada(pasta: str, pasta_preferencias: Path | None = None) -> bool:
    """Guarda a pasta escolhida ("" = esquecer: a planilha volta a ir para a pasta do patrimônio)."""
    dados = ler_preferencias_modulo(CHAVE, pasta_preferencias)
    dados["pasta"] = pasta
    return salvar_preferencias_modulo(CHAVE, dados, pasta_preferencias)
