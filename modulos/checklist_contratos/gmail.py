"""Gmail: autorização e rascunhos (G1 a G3). O único arquivo do módulo que fala com a internet.

- Login pelo navegador com a biblioteca do Google (google-auth-oauthlib), escopo gmail.compose (G3).
  O token fica em %APPDATA%\\CentralConciliacoes\\checklist_contratos\\gmail_token.json; vencido, é
  renovado; revogado ou inválido, é apagado e o navegador abre de novo (sem erro técnico).
- Só rascunho (G1): não há função de enviar.
- As bibliotecas do Google só são carregadas na hora de usar (a Central abre sem elas).
- Os testes nunca chegam aqui: usam um cliente simulado com os mesmos dois métodos (conta e
  criar_rascunho).
"""

from __future__ import annotations

import base64
import os
from email.message import EmailMessage
from pathlib import Path

from modulos.checklist_contratos import configuracao as cfg
from modulos.checklist_contratos.modelos import Email


class ErroGmail(Exception):
    """Problema com o Gmail; a mensagem é escrita para o usuário final."""


def caminho_token() -> Path:
    """%APPDATA%\\CentralConciliacoes\\checklist_contratos\\gmail_token.json (ou a pasta do usuário)."""
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / cfg.PASTA_DADOS_USUARIO / cfg.SUBPASTA_DADOS_MODULO / cfg.NOME_TOKEN_GMAIL


def esquecer_autorizacao(token: Path | None = None) -> None:
    """Apaga o token: na próxima vez o navegador pede a autorização de novo (trocar de conta)."""
    (token or caminho_token()).unlink(missing_ok=True)


def mensagem_mime(email: Email, remetente: str) -> str:
    """O e-mail em MIME, codificado como o Gmail pede (base64 para URL)."""
    mensagem = EmailMessage()
    mensagem["From"] = remetente
    mensagem["To"] = ", ".join(email.para)
    if email.copia:
        mensagem["Cc"] = ", ".join(email.copia)
    mensagem["Subject"] = email.assunto
    mensagem.set_content(email.html, subtype="html")
    return base64.urlsafe_b64encode(mensagem.as_bytes()).decode("ascii")


def _credenciais(credentials_json: Path, token: Path):
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    escopos = list(cfg.GMAIL_ESCOPOS)
    credenciais = None
    if token.is_file():
        try:
            credenciais = Credentials.from_authorized_user_file(str(token), escopos)
        except (ValueError, OSError):
            credenciais = None                     # token estragado: autoriza de novo
    if credenciais and credenciais.valid:
        return credenciais
    if credenciais and credenciais.expired and credenciais.refresh_token:
        try:
            credenciais.refresh(Request())
            token.write_text(credenciais.to_json(), encoding="utf-8")
            return credenciais
        except RefreshError:
            credenciais = None                     # revogado: autoriza de novo

    if not Path(credentials_json).is_file():
        raise ErroGmail("O arquivo de credenciais do Google (credentials.json) não foi encontrado. "
                        "Veja nas Instruções de uso como pedir à TI.")
    try:
        fluxo = InstalledAppFlow.from_client_secrets_file(str(credentials_json), escopos)
    except ValueError:
        raise ErroGmail("O arquivo escolhido não é um credentials.json de \"App para computador\" do "
                        "Google. Veja nas Instruções de uso como pedir à TI.") from None
    try:
        credenciais = fluxo.run_local_server(port=0, open_browser=True,
                                             authorization_prompt_message="",
                                             success_message="Autorização concluída. Pode fechar esta "
                                                             "janela e voltar para a Central.")
    except Exception as erro:                      # janela fechada, recusa, rede...
        raise ErroGmail(f"A autorização do Gmail não foi concluída: {erro}") from None
    token.parent.mkdir(parents=True, exist_ok=True)
    token.write_text(credenciais.to_json(), encoding="utf-8")
    return credenciais


class ClienteGmail:
    """Fala com a API do Gmail com a conta autorizada (abre o navegador na primeira vez)."""

    def __init__(self, credentials_json: Path, token: Path | None = None):
        from google.auth.transport.requests import AuthorizedSession

        self._sessao = AuthorizedSession(_credenciais(Path(credentials_json), token or caminho_token()))

    def _chamar(self, metodo: str, url: str, **dados) -> dict:
        import requests

        try:
            resposta = self._sessao.request(metodo, url, timeout=cfg.GMAIL_TEMPO_LIMITE, **dados)
        except requests.RequestException as erro:
            raise ErroGmail(f"Sem conexão com o Gmail: {erro}") from None
        if resposta.status_code >= 400:
            try:
                motivo = resposta.json()["error"]["message"]
            except (ValueError, KeyError, TypeError):
                motivo = resposta.text[:200]
            raise ErroGmail(f"O Gmail recusou o pedido ({resposta.status_code}): {motivo}")
        return resposta.json()

    def conta(self) -> str:
        """G2: o endereço da conta autorizada."""
        return self._chamar("GET", cfg.GMAIL_URL_PERFIL)["emailAddress"].lower()

    def criar_rascunho(self, email: Email, remetente: str) -> str:
        """G1: cria o rascunho e devolve o id dele no Gmail."""
        return self._chamar("POST", cfg.GMAIL_URL_RASCUNHOS,
                            json={"message": {"raw": mensagem_mime(email, remetente)}})["id"]
