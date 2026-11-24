"""Listas de pendências -> e-mails (E1 a E6) e a prévia em .html (E7).

Destinatários pelos códigos (decisão do usuário, 23/10/2026): recebe o e-mail do responsável 13 todo
contato da aba Emails com 13 na célula ao lado; "Todos" vai em todos os e-mails e "Todos CMD" em todo
e-mail com notas do CMD. O texto é o do protótipo (gerar_emails.ps1). Sem PDF e sem anexo: a tabela
vai no corpo do e-mail.
"""

from __future__ import annotations

import re
from datetime import date
from html import escape

from modulos.checklist_contratos import configuracao as cfg
from modulos.checklist_contratos.modelos import Contato, Email, ListaPendente, Pendencias, SemEmail

_RE_SEPARADOR_PESSOAS = re.compile(r"\s+e\s+|\s*[,/;&]\s*", re.IGNORECASE)


def mes_por_extenso(ano: int, mes: int) -> str:
    """(2026, 10) -> "Outubro/2026"."""
    return f"{cfg.MESES_POR_EXTENSO[mes - 1]}/{ano}"


def _juntar(nomes: list[str]) -> str:
    """["Ana"] -> "Ana"; ["Ana", "Bruno", "Carla"] -> "Ana, Bruno e Carla"."""
    return nomes[0] if len(nomes) == 1 else ", ".join(nomes[:-1]) + " e " + nomes[-1]


def nomes_da_saudacao(responsavel: str) -> list[str]:
    """E3: o primeiro nome de cada pessoa do responsável ("Ana/Bruno" -> Ana, Bruno;
    "Carlos manutenção" -> Carlos)."""
    pessoas = [p.strip() for p in _RE_SEPARADOR_PESSOAS.split(responsavel) if p.strip()]
    return [p.split()[0].capitalize() for p in pessoas]


def destinatarios(codigo: str, tem_cmd: bool, contatos: list[Contato]) -> list[str]:
    """E2, E5, E6: os contatos do número, depois os "Todos", depois os "Todos CMD"; sem repetir."""
    grupos = [codigo, cfg.CODIGO_TODOS] + ([cfg.CODIGO_TODOS_CMD] if tem_cmd else [])
    para = [c.email for grupo in grupos for c in contatos if grupo in c.codigos]
    return list(dict.fromkeys(para))


def copia(para: list[str], tem_cmd: bool, contatos: list[Contato]) -> list[str]:
    """E2: os contatos com "Cópia" (e, se o e-mail tem notas do CMD, os com "Cópia CMD") vão em cópia (Cc),
    menos quem já está no Para; sem repetir."""
    grupos = [cfg.CODIGO_COPIA] + ([cfg.CODIGO_COPIA_CMD] if tem_cmd else [])
    return list(dict.fromkeys(c.email for grupo in grupos for c in contatos
                              if grupo in c.codigos and c.email not in para))


def _tabela(lista: ListaPendente) -> str:
    titulos = "".join(f"<th>{escape(t)}</th>" for t in cfg.COLUNAS_TABELA_EMAIL)
    linhas = "".join(f"<tr><td>{escape(n.conta)}</td><td>{escape(n.fornecedor)}</td>"
                     f"<td>{escape(n.descricao_despesa)}</td></tr>\n" for n in lista.notas)
    return (f'<table border="1" cellpadding="5" cellspacing="0" style="{cfg.ESTILO_TABELA_EMAIL}">\n'
            f'<tr style="background:{cfg.COR_TITULOS_TABELA_EMAIL}">{titulos}</tr>\n{linhas}</table>\n')


def _tabela_conta_divergente(notas) -> str:
    """P2: as notas que ficaram fora dos e-mails por CONTA DIVERGENTE, para não sumirem em silêncio."""
    titulos = "".join(f"<th>{escape(t)}</th>" for t in cfg.COLUNAS_TABELA_CONTA_DIVERGENTE)
    linhas = "".join(
        f"<tr><td>{escape(cfg.NOMES_CURTOS[estabelecimento])}</td><td>{linha.numero}</td>"
        f"<td>{escape(linha.conta)}</td><td>{escape(linha.fornecedor)}</td>"
        f"<td>{escape(linha.descricao_despesa)}</td><td>{escape(linha.responsavel)}</td></tr>\n"
        for estabelecimento, linha in notas)
    return (f'<hr><h3 style="color:#b60">Fora dos e-mails: conta divergente ({len(notas)} nota(s))</h3>\n'
            "<p>A nota chegou, mas foi lançada em outra conta: não é cobrada do responsável. Corrija a conta "
            "(lote e lançamento na aba Conta divergente do relatório da conferência).</p>\n"
            f'<table border="1" cellpadding="5" cellspacing="0" style="{cfg.ESTILO_TABELA_EMAIL}">\n'
            f'<tr style="background:{cfg.COR_TITULOS_TABELA_EMAIL}">{titulos}</tr>\n{linhas}</table>\n')


def corpo_do_email(responsavel: str, listas: list[ListaPendente], ano: int, mes: int, posicao: date) -> str:
    """E3 e E4: saudação, abertura, uma tabela por estabelecimento e o fechamento."""
    nomes = nomes_da_saudacao(responsavel)
    sua = "responsabilidade de vocês" if len(nomes) > 1 else "sua responsabilidade"
    do_cmd = (f"do <b>{escape(cfg.NOMES_ESTABELECIMENTOS[cfg.CMD])}</b> "
              if [l.estabelecimento for l in listas] == [cfg.CMD] else "")
    html = f"<p>Olá, {escape(_juntar(nomes))},</p>\n"
    html += (f"<p>Segue a relação das notas fiscais de contrato {do_cmd}sob {sua} que ainda não foram lançadas "
             f"referentes a <b>{mes_por_extenso(ano, mes)}</b> (posição em {posicao:%d/%m/%Y}):</p>\n")
    for lista in listas:
        if len(listas) > 1:
            html += f"<p><b>{escape(cfg.NOMES_ESTABELECIMENTOS[lista.estabelecimento])}</b></p>\n"
        html += _tabela(lista)
    html += ("<p>Por gentileza, verifique junto aos fornecedores e encaminhe as notas para lançamento.</p>\n"
             "<p>Qualquer dúvida, estamos à disposição.</p>\n"
             "<p>Atenciosamente,<br>Contabilidade</p>")
    return html


def corpo_em_texto(responsavel: str, listas: list[ListaPendente], ano: int, mes: int, posicao: date) -> str:
    """O mesmo corpo de corpo_do_email, em texto: as tabelas viram linhas "Conta | Fornecedor | Descrição"."""
    nomes = nomes_da_saudacao(responsavel)
    sua = "responsabilidade de vocês" if len(nomes) > 1 else "sua responsabilidade"
    do_cmd = (f"do {cfg.NOMES_ESTABELECIMENTOS[cfg.CMD]} "
              if [l.estabelecimento for l in listas] == [cfg.CMD] else "")
    partes = [f"Olá, {_juntar(nomes)},",
              f"Segue a relação das notas fiscais de contrato {do_cmd}sob {sua} que ainda não foram lançadas "
              f"referentes a {mes_por_extenso(ano, mes)} (posição em {posicao:%d/%m/%Y}):"]
    for lista in listas:
        tabela = [" | ".join(cfg.COLUNAS_TABELA_EMAIL)] + [
            f"{n.conta} | {n.fornecedor} | {n.descricao_despesa}" for n in lista.notas]
        if len(listas) > 1:
            tabela.insert(0, f"[{cfg.NOMES_ESTABELECIMENTOS[lista.estabelecimento]}]")
        partes.append("\n".join(tabela))
    partes += ["Por gentileza, verifique junto aos fornecedores e encaminhe as notas para lançamento.",
               "Qualquer dúvida, estamos à disposição.", "Atenciosamente,\nContabilidade"]
    return "\n\n".join(partes)


def texto_para_claude_desktop(pendencias: Pendencias, ano: int, mes: int, posicao: date) -> str:
    """Os e-mails com as instruções para o Claude Desktop criar os rascunhos no Gmail da Contabilidade
    (caminho usado enquanto não há o credentials.json; decisão do usuário, 23/10/2026)."""
    mes_texto = mes_por_extenso(ano, mes)
    total = len(pendencias.emails)
    separador = "=" * 100
    linhas = [
        f"RASCUNHOS DE E-MAIL - NOTAS FISCAIS DE CONTRATO PENDENTES - {mes_texto.upper()} "
        f"(posição em {posicao:%d/%m/%Y})",
        "",
        "INSTRUÇÕES PARA O CLAUDE DESKTOP",
        "1. Para cada e-mail abaixo, crie UM RASCUNHO no Gmail da Contabilidade. NÃO ENVIE NENHUM.",
        "2. Use exatamente os endereços de PARA (no campo Para) e de CÓPIA (no campo Cc), o ASSUNTO e o CORPO.",
        "   Nenhum endereço em Cco. E-mail sem a linha CÓPIA não tem ninguém em Cc.",
        "3. No corpo, as linhas '" + " | ".join(cfg.COLUNAS_TABELA_EMAIL) + "' viram uma TABELA com essas três "
        "colunas",
        f"   (cabeçalho em negrito com fundo azul claro {cfg.COR_TITULOS_TABELA_EMAIL}, bordas finas, fonte "
        "Calibri 13px).",
        "   Quando houver duas listas, o título entre colchetes ("
        + ", ".join(f"[{n}]" for n in cfg.NOMES_ESTABELECIMENTOS.values()) + ")",
        "   vira um parágrafo em negrito antes da tabela.",
        f"4. '{mes_texto}' na frase de abertura fica em negrito. Não acrescente nem tire nada do texto.",
        "5. Ao terminar, liste os rascunhos criados (assunto e destinatários) para conferência.",
        f"Total: {total} e-mail(s).",
    ]
    for numero, email in enumerate(pendencias.emails, start=1):
        linhas += ["", separador,
                   f"E-MAIL {numero} de {total} - responsável no Check list: {email.responsavel} "
                   f"({email.notas} nota(s))",
                   f"PARA: {'; '.join(email.para)}",
                   *([f"CÓPIA: {'; '.join(email.copia)}"] if email.copia else []),
                   f"ASSUNTO: {email.assunto}",
                   "CORPO:", "",
                   corpo_em_texto(email.responsavel, email.listas, ano, mes, posicao)]
    return "\n".join(linhas) + "\n"


def montar_emails(pendencias: Pendencias, contatos: list[Contato], ano: int, mes: int, posicao: date) -> None:
    """E1 a E6: um e-mail por responsável (Hospital Exemplo e CMD juntos); o que não der vai para sem_email."""
    por_chave: dict[str, list[ListaPendente]] = {}
    for lista in pendencias.listas:
        por_chave.setdefault(lista.chave, []).append(lista)
    for chave, listas in por_chave.items():
        listas.sort(key=lambda l: cfg.ESTABELECIMENTOS.index(l.estabelecimento))
        primeira = listas[0]
        if primeira.responsavel == cfg.SEM_RESPONSAVEL:
            motivo = "As linhas estão sem responsável na planilha."
        elif not primeira.codigo:
            motivo = ("A coluna Responsável não começa com o número do responsável "
                      f"(ex.: \"13 - {primeira.responsavel}\").")
        else:
            motivo = ""
        tem_cmd = any(l.estabelecimento == cfg.CMD for l in listas)
        para = destinatarios(primeira.codigo, tem_cmd, contatos) if not motivo else []
        if not motivo and not any(primeira.codigo in c.codigos for c in contatos):
            motivo = f"Nenhum contato da aba {cfg.ABA_EMAILS} tem o número {primeira.codigo}."
        if motivo:
            pendencias.sem_email.append(SemEmail(primeira.responsavel, listas, motivo))
            continue
        estabelecimentos = " e ".join(cfg.NOMES_CURTOS[l.estabelecimento] for l in listas)
        pendencias.emails.append(Email(
            chave=chave, codigo=primeira.codigo, responsavel=primeira.responsavel, listas=listas, para=para,
            copia=copia(para, tem_cmd, contatos),
            assunto=cfg.ASSUNTO_EMAIL.format(estabelecimentos=estabelecimentos, mes=mes_por_extenso(ano, mes)),
            html=corpo_do_email(primeira.responsavel, listas, ano, mes, posicao)))


def previa_html(pendencias: Pendencias, ano: int, mes: int, posicao: date) -> str:
    """E7: todos os e-mails, quem ficou sem e-mail (com as notas) e os avisos, para conferir antes."""
    titulo = f"Prévia dos e-mails - {mes_por_extenso(ano, mes)}"
    partes = [f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>{escape(titulo)}</title>'
              '</head><body style="font-family:Calibri,Arial,sans-serif;max-width:1000px;margin:20px auto">',
              f"<h2>{escape(titulo)}</h2>",
              f"<p>Posição em {posicao:%d/%m/%Y}: <b>{pendencias.notas}</b> nota(s) pendente(s), "
              f"<b>{len(pendencias.emails)}</b> e-mail(s)"
              + (f', <b style="color:#b00">{len(pendencias.sem_email)} responsável(is) sem e-mail</b>'
                 if pendencias.sem_email else "") + ".</p>"]
    for email in pendencias.emails:
        partes.append(f"<hr><p><b>Para:</b> {escape('; '.join(email.para))}<br>"
                      + (f"<b>Cópia:</b> {escape('; '.join(email.copia))}<br>" if email.copia else "")
                      + f"<b>Assunto:</b> {escape(email.assunto)}<br>"
                      f"<b>Notas:</b> {email.notas}</p>{email.html}")
    for sem in pendencias.sem_email:
        partes.append(f'<hr><p style="color:#b00"><b>Sem e-mail: {escape(sem.responsavel)}</b> '
                      f"({sum(len(l.notas) for l in sem.listas)} nota(s)). {escape(sem.motivo)}</p>")
        for lista in sem.listas:
            partes.append(f"<p><b>{escape(cfg.NOMES_ESTABELECIMENTOS[lista.estabelecimento])}</b></p>"
                          + _tabela(lista))
    if pendencias.conta_divergente:
        partes.append(_tabela_conta_divergente(pendencias.conta_divergente))
    if pendencias.avisos:
        partes.append("<hr><h3>Avisos</h3><ul>" + "".join(
            f"<li><b>{escape(a.origem)}</b>: {escape(a.mensagem)}</li>" for a in pendencias.avisos) + "</ul>")
    partes.append("</body></html>")
    return "\n".join(partes)
