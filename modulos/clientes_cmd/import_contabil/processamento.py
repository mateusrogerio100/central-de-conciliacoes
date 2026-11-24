"""Import Contábil em dois passos. É o único arquivo do Import que a tela (telas/import_contabil.py) chama.

1. gerar_rel_geral: junta todos os relatórios (.xlsx ou o .xls do Tasy) da pasta do mês numa planilha Rel_Geral
   (consolidar.py). O usuário pode conferir e corrigir essa planilha antes do passo 2.
2. gerar_arquivo_import: a partir do Rel_Geral (gerado no passo 1 ou montado à mão), grava o
   .txt que o sistema contábil importa (gerar_txt.py).

Os nomes padrão dos arquivos vieram da janela original (aba "Import Contábil"), sem mudança:
na Central a tela não tem regra de negócio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

from .consolidar import consolidar_relatorios, listar_relatorios, salvar_rel_geral
from .gerar_txt import gerar_import


@dataclass
class ResultadoRelGeral:
    caminho: Path                                                   # Rel_Geral gravado
    total: int                                                      # lançamentos no Rel_Geral
    linhas_por_arquivo: dict[str, int] = field(default_factory=dict)  # {relatório: linhas}


@dataclass
class ResultadoImport:
    caminho: Path       # .txt gravado
    total: int          # lançamentos gravados (cada um vira duas linhas no .txt)
    mes: int
    ano: int


def interpretar_mes(texto: str) -> tuple[int, int] | None:
    """"08/2026" -> (8, 2026). None se o texto não for um mês válido."""
    partes = (texto or "").strip().replace("-", "/").split("/")
    if len(partes) != 2 or not all(p.strip().isdigit() for p in partes):
        return None
    mes, ano = int(partes[0]), int(partes[1])
    if not 1 <= mes <= 12 or not 2000 <= ano <= 2100:
        return None
    return mes, ano


def mes_anterior(hoje: date | None = None) -> tuple[int, int]:
    """Mês sugerido ao abrir a tela (como na janela original): o mês anterior ao de hoje."""
    hoje = hoje or date.today()
    ultimo_dia_mes_passado = hoje.replace(day=1) - timedelta(days=1)
    return ultimo_dia_mes_passado.month, ultimo_dia_mes_passado.year


def formatar_mes(mes: int, ano: int) -> str:
    return f"{mes:02d}/{ano}"


def contar_relatorios(pasta) -> int:
    """Quantos relatórios (.xlsx ou .xls) a pasta tem, para a tela mostrar ao escolher a pasta."""
    try:
        return len(listar_relatorios(pasta))
    except OSError:
        return 0


def nome_rel_geral(mes: int, ano: int) -> str:
    return f"Rel_Geral_{mes:02d}_{ano}.xlsx"


def nome_import(mes: int, ano: int) -> str:
    return f"Import_gerado_{mes:02d}_{ano}.txt"


def gerar_rel_geral(pasta_relatorios, caminho_saida,
                    progresso: Callable[[str, float | None], None] | None = None) -> ResultadoRelGeral:
    """Passo 1. Levanta ValueError (mensagem para o usuário) se a pasta não tiver relatórios
    ou se um relatório não tiver o formato esperado."""
    if progresso is None:
        progresso = _sem_progresso
    progresso("Lendo os relatórios do mês...", 0.0)
    df = consolidar_relatorios(pasta_relatorios)
    progresso("Gravando o Rel_Geral...", 0.7)
    salvar_rel_geral(df, caminho_saida)
    progresso("Concluído.", 1.0)
    return ResultadoRelGeral(caminho=Path(caminho_saida), total=len(df),
                             linhas_por_arquivo=dict(df.attrs["linhas_por_arquivo"]))


def gerar_arquivo_import(caminho_rel_geral, mes: int, ano: int, caminho_saida,
                         progresso: Callable[[str, float | None], None] | None = None) -> ResultadoImport:
    """Passo 2. Levanta ValueError (mensagem para o usuário) se o Rel_Geral estiver fora do
    formato ou tiver um caractere que não existe na codificação do import."""
    if progresso is None:
        progresso = _sem_progresso
    progresso("Gerando o arquivo de import...", 0.0)
    Path(caminho_saida).parent.mkdir(parents=True, exist_ok=True)
    total = gerar_import(caminho_rel_geral, mes, ano, caminho_saida)
    progresso("Concluído.", 1.0)
    return ResultadoImport(caminho=Path(caminho_saida), total=total, mes=mes, ano=ano)


def _sem_progresso(texto: str, fracao: float | None) -> None:
    """Usado quando ninguém acompanha o andamento (testes)."""
