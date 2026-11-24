"""PDFs por número + contatos + modelo -> e-mails (E1 a E5) e a prévia em .html (E6).

Um e-mail por número que tenha PDF. Para: os contatos com o número na aba Emails, depois os "Todos", sem
repetir endereço ("Todos CMD" não entra: a pasta é da Hospital Exemplo). Número sem contato próprio, anexos acima
do limite e PDF sem número ficam sem e-mail, com o motivo.
"""

from __future__ import annotations

from datetime import date
from html import escape

from modulos.notas_pendentes import configuracao as cfg
from modulos.notas_pendentes.leitor_modelo import marcador
from modulos.notas_pendentes.modelos import (
    ArquivoNota, Contato, Email, EmailsDoMes, ModeloEmail, PastaNotas, SemEmail,
)


def competencia(ano: int, mes: int) -> str:
    """(2026, 10) -> "10/2026"."""
    return f"{mes:02d}/{ano:04d}"


def competencia_por_extenso(ano: int, mes: int) -> str:
    """(2026, 10) -> "outubro/2026"."""
    return f"{cfg.MESES_POR_EXTENSO[mes - 1]}/{ano:04d}"


def tamanho_legivel(tamanho: int) -> str:
    """540000 -> "527 KB"; 21000000 -> "20,0 MB"."""
    if tamanho >= 1024 * 1024:
        return f"{tamanho / 1024 / 1024:.1f} MB".replace(".", ",")
    return f"{max(1, round(tamanho / 1024))} KB"


def lista_das_notas(notas: list[ArquivoNota]) -> str:
    """{lista_notas}: uma linha por PDF, na ordem dos anexos."""
    return "\n".join(f"{cfg.MARCADOR_ITEM_LISTA}{n.descricao}" for n in notas)


def preencher(texto: str, valores: dict[str, str]) -> str:
    """Troca cada {marcador} pelo valor (o leitor do modelo já garantiu que todos são conhecidos)."""
    return cfg.RE_MARCADOR.sub(lambda achado: valores[marcador(achado.group(1))], texto)


def destinatarios(numero: str, contatos: list[Contato]) -> tuple[list[str], bool]:
    """E2: (Para, tem contato próprio). Primeiro os do número, na ordem da aba Emails, depois os "Todos"."""
    proprios = [c.email for c in contatos if numero in c.codigos]
    todos = [c.email for c in contatos if cfg.CODIGO_TODOS in c.codigos]
    return list(dict.fromkeys(proprios + todos)), bool(proprios)


def copia(para: list[str], contatos: list[Contato]) -> list[str]:
    """E2: os contatos com "Cópia" vão em cópia (Cc), menos quem já está no Para; sem repetir."""
    return list(dict.fromkeys(c.email for c in contatos if cfg.CODIGO_COPIA in c.codigos and c.email not in para))


def montar_emails(pasta: PastaNotas, contatos: list[Contato], modelo: ModeloEmail,
                  ano: int, mes: int, prazo: date) -> EmailsDoMes:
    resultado = EmailsDoMes()
    fixos = {
        cfg.MARCADOR_COMPETENCIA: competencia(ano, mes),
        cfg.MARCADOR_COMPETENCIA_EXTENSO: competencia_por_extenso(ano, mes),
        cfg.MARCADOR_PRAZO: f"{prazo:%d/%m/%Y}",
    }
    for numero, notas in pasta.por_numero().items():
        para, tem_proprio = destinatarios(numero, contatos)
        if not tem_proprio:
            resultado.sem_email.append(SemEmail(numero, notas, cfg.MOTIVO_SEM_CONTATO.format(numero=numero),
                                                cfg.SITUACAO_SEM_CONTATO))
            continue
        valores = {**fixos, cfg.MARCADOR_LISTA_NOTAS: lista_das_notas(notas)}
        email = Email(numero, para, preencher(modelo.assunto, valores), preencher(modelo.corpo, valores), notas,
                      copia=copia(para, contatos))
        if email.tamanho > cfg.LIMITE_ANEXOS_BYTES:
            motivo = cfg.MOTIVO_LIMITE.format(tamanho=tamanho_legivel(email.tamanho),
                                              limite=tamanho_legivel(cfg.LIMITE_ANEXOS_BYTES))
            resultado.sem_email.append(SemEmail(numero, notas, motivo, cfg.SITUACAO_LIMITE))
            continue
        resultado.emails.append(email)
    if pasta.sem_numero:
        resultado.sem_email.append(SemEmail("", pasta.sem_numero, cfg.MOTIVO_SEM_NUMERO, cfg.SITUACAO_SEM_NUMERO))
    return resultado


def texto_para_claude_desktop(emails: EmailsDoMes, ano: int, mes: int, prazo: date) -> str:
    """E7: os e-mails com as instruções para o Claude Desktop criar os rascunhos no Gmail da Contabilidade,
    SEM anexos: o usuário anexa os PDFs à mão (o conector do Claude Desktop só aguenta 1 ou 2 PDFs).
    As notas sem e-mail não entram (estão na prévia)."""
    total = len(emails.emails)
    separador = "=" * 100
    linhas = [
        f"RASCUNHOS DE E-MAIL - NOTAS FISCAIS PENDENTES DE REGISTRO - COMPETÊNCIA {competencia(ano, mes)} "
        f"(prazo {prazo:%d/%m/%Y})",
        "",
        "INSTRUÇÕES PARA O CLAUDE DESKTOP",
        "1. Para cada e-mail abaixo, crie UM RASCUNHO no Gmail da Contabilidade. NÃO ENVIE NENHUM.",
        "2. Use exatamente os endereços de PARA (no campo Para) e de CÓPIA (no campo Cc), o ASSUNTO e o CORPO.",
        "   Nenhum endereço em Cco. E-mail sem a linha CÓPIA não tem ninguém em Cc.",
        "3. NÃO ANEXE NENHUM ARQUIVO: os PDFs da lista \"ANEXAR À MÃO\" serão anexados depois, manualmente.",
        "4. Copie o CORPO como está, com as quebras de linha. Não acrescente nem tire nada do texto.",
        "5. Ao terminar, liste os rascunhos criados (assunto e destinatários) para conferência.",
        f"Total: {total} e-mail(s).",
    ]
    for numero, email in enumerate(emails.emails, start=1):
        pasta = email.anexos[0].caminho.parent if email.anexos else ""
        linhas += ["", separador,
                   f"E-MAIL {numero} de {total} - número do responsável: {email.numero} "
                   f"({len(email.anexos)} nota(s))",
                   f"PARA: {'; '.join(email.para)}",
                   *([f"CÓPIA: {'; '.join(email.copia)}"] if email.copia else []),
                   f"ASSUNTO: {email.assunto}",
                   "CORPO:", "",
                   email.corpo,
                   "",
                   f"ANEXAR À MÃO (não anexar agora), da pasta {pasta}:",
                   *(f"  {nota.nome}" for nota in email.anexos)]
    return "\n".join(linhas) + "\n"


def _lista_html(notas: list[ArquivoNota]) -> str:
    return "<ul>" + "".join(f"<li>{escape(n.nome)} <small>({tamanho_legivel(n.tamanho)})</small></li>"
                            for n in notas) + "</ul>"


def previa_html(emails: EmailsDoMes, ano: int, mes: int, prazo: date, origem_modelo: str) -> str:
    """E6: todos os e-mails (Para, assunto, texto, anexos), as notas sem e-mail e os avisos."""
    titulo = f"Prévia dos e-mails - notas pendentes de registro - {competencia(ano, mes)}"
    notas = sum(len(e.anexos) for e in emails.emails)
    sem = sum(len(s.notas) for s in emails.sem_email)
    partes = [f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>{escape(titulo)}</title>'
              '</head><body style="font-family:Calibri,Arial,sans-serif;max-width:1000px;margin:20px auto">',
              f"<h2>{escape(titulo)}</h2>",
              f"<p>Prazo para registro: <b>{prazo:%d/%m/%Y}</b>. Texto: {escape(origem_modelo)}.<br>"
              f"<b>{len(emails.emails)}</b> e-mail(s) com <b>{notas}</b> nota(s) anexada(s)"
              + (f', <b style="color:#b00">{sem} nota(s) sem e-mail</b>' if sem else "") + ".</p>"]
    for email in emails.emails:
        partes.append(f"<hr><p><b>Número {escape(email.numero)}</b><br>"
                      f"<b>Para:</b> {escape('; '.join(email.para))}<br>"
                      + (f"<b>Cópia:</b> {escape('; '.join(email.copia))}<br>" if email.copia else "")
                      + f"<b>Assunto:</b> {escape(email.assunto)}</p>"
                      f'<div style="white-space:pre-wrap;border-left:3px solid #ccc;padding-left:10px">'
                      f"{escape(email.corpo)}</div>"
                      f"<p><b>Anexos ({len(email.anexos)}, {tamanho_legivel(email.tamanho)}):</b></p>"
                      + _lista_html(email.anexos))
    for s in emails.sem_email:
        rotulo = f"número {s.numero}" if s.numero else "sem número"
        partes.append(f'<hr><p style="color:#b00"><b>Sem e-mail ({escape(rotulo)}): {len(s.notas)} nota(s).</b> '
                      f"{escape(s.motivo)}</p>" + _lista_html(s.notas))
    if emails.avisos:
        partes.append("<hr><h3>Avisos</h3><ul>" + "".join(
            f"<li><b>{escape(a.origem)}</b>: {escape(a.mensagem)}</li>" for a in emails.avisos) + "</ul>")
    partes.append("</body></html>")
    return "\n".join(partes)
