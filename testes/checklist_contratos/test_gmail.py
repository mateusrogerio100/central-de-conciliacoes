"""T9 — Gmail simulado (G1 a G6). Nenhum teste acessa a internet."""

from __future__ import annotations

import base64
import csv
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from email import message_from_bytes, policy

import pytest

from modulos.checklist_contratos import gmail
from modulos.checklist_contratos.gmail import ClienteGmail, ErroGmail, esquecer_autorizacao, mensagem_mime
from modulos.checklist_contratos.modelos import Email, LinhaChecklist, ListaPendente
from modulos.checklist_contratos.processamento import criar_rascunhos

AGORA = datetime(2026, 10, 23, 15, 0)
REMETENTE = "contabil@exemplo.org.br"


def _email(responsavel: str, para: list[str]) -> Email:
    nota = LinhaChecklist(2, "30091", "Conta", "Fornecedor A", "Licença", f"1 - {responsavel}", None, None)
    lista = ListaPendente("SC", "1", "1", responsavel, [nota])
    return Email("1", "1", responsavel, [lista], para, "Notas fiscais pendentes - Hospital Exemplo - Outubro/2026",
                 f"<p>Olá, {responsavel},</p><p>Relação à disposição.</p>")


class GmailSimulado:
    """Os dois métodos do ClienteGmail, sem internet. Não tem como enviar: só guarda os rascunhos."""

    def __init__(self, conta=REMETENTE, falhar_em=(), falhar_conta=False):
        self._conta, self.falhar_em, self.falhar_conta = conta, set(falhar_em), falhar_conta
        self.rascunhos = []

    def conta(self):
        if self.falhar_conta:
            raise ErroGmail("Sem conexão com o Gmail: simulado")
        return self._conta

    def criar_rascunho(self, email, remetente):
        if email.responsavel in self.falhar_em:
            raise ErroGmail("O Gmail recusou o pedido (400): simulado")
        self.rascunhos.append((email, remetente))
        return f"r-{len(self.rascunhos)}"


EMAILS = [_email("Ana", ["ana@exemplo.org.br", REMETENTE]), _email("Bruno", ["bruno@exemplo.org.br"]),
          _email("Carla", ["carla@exemplo.org.br"])]


def test_t9_cria_um_rascunho_por_email_e_grava_o_registro(tmp_path):
    simulado = GmailSimulado()
    passos = []
    resultado = criar_rascunhos(EMAILS, tmp_path / "credentials.json", " Contabil@Exemplo.org.br ", tmp_path,
                                progresso=lambda t, f: passos.append(f), cliente=simulado, agora=AGORA)
    assert resultado.erro == "" and resultado.conta == REMETENTE and resultado.criados == 3
    assert [(e.responsavel, r) for e, r in simulado.rascunhos] == [("Ana", REMETENTE), ("Bruno", REMETENTE),
                                                                    ("Carla", REMETENTE)]
    assert passos[-1] == 1.0
    assert resultado.caminho_registro.name == "Envio_Gmail_2026-10-23_150000.csv"
    with open(resultado.caminho_registro, encoding="utf-8-sig") as arquivo:
        linhas = list(csv.reader(arquivo, delimiter=";"))
    assert linhas[0] == ["Data e hora", "Tipo", "Responsável", "Para", "Assunto", "Notas", "Id no Gmail", "Erro"]
    assert linhas[1] == ["23/10/2026 15:00:00", "rascunho", "Ana", f"ana@exemplo.org.br, {REMETENTE}",
                         "Notas fiscais pendentes - Hospital Exemplo - Outubro/2026", "1", "r-1", ""]


def test_t9_so_rascunho_nunca_envia():
    assert not any("envi" in nome or "send" in nome for nome in dir(ClienteGmail))
    assert all("send" not in valor for valor in vars(gmail.cfg).values() if isinstance(valor, str))
    assert gmail.cfg.GMAIL_ESCOPOS == ("https://www.googleapis.com/auth/gmail.compose",)


def test_t9_conta_diferente_da_esperada_nao_cria_nada(tmp_path):
    simulado = GmailSimulado(conta="outra@exemplo.org.br")
    resultado = criar_rascunhos(EMAILS, tmp_path / "c.json", REMETENTE, tmp_path, cliente=simulado, agora=AGORA)
    assert "outra@exemplo.org.br" in resultado.erro and REMETENTE in resultado.erro
    assert simulado.rascunhos == [] and resultado.itens == [] and resultado.caminho_registro is None


def test_t9_erro_em_um_email_nao_para_os_outros(tmp_path):
    simulado = GmailSimulado(falhar_em={"Bruno"})
    resultado = criar_rascunhos(EMAILS, tmp_path / "c.json", REMETENTE, tmp_path, cliente=simulado, agora=AGORA)
    assert [(i.email.responsavel, i.id_gmail, bool(i.erro)) for i in resultado.itens] == [
        ("Ana", "r-1", False), ("Bruno", "", True), ("Carla", "r-2", False)]
    assert resultado.criados == 2
    with open(resultado.caminho_registro, encoding="utf-8-sig") as arquivo:
        assert "recusou" in list(csv.reader(arquivo, delimiter=";"))[2][7]


def test_t9_sem_conexao_e_mensagem_clara(tmp_path):
    resultado = criar_rascunhos(EMAILS, tmp_path / "c.json", REMETENTE, tmp_path,
                                cliente=GmailSimulado(falhar_conta=True), agora=AGORA)
    assert "Sem conexão" in resultado.erro and resultado.caminho_registro is None


def test_t9_registro_nao_sobrescreve(tmp_path):
    primeiro = criar_rascunhos(EMAILS, tmp_path / "c.json", REMETENTE, tmp_path, cliente=GmailSimulado(), agora=AGORA)
    segundo = criar_rascunhos(EMAILS, tmp_path / "c.json", REMETENTE, tmp_path, cliente=GmailSimulado(), agora=AGORA)
    assert segundo.caminho_registro.stem == primeiro.caminho_registro.stem + "_2"


def test_t9_chamada_incompleta(tmp_path):
    with pytest.raises(ValueError):
        criar_rascunhos([], tmp_path / "c.json", REMETENTE, tmp_path, cliente=GmailSimulado())


def test_t9_mensagem_mime():
    raw = mensagem_mime(EMAILS[0], REMETENTE)
    mensagem = message_from_bytes(base64.urlsafe_b64decode(raw), policy=policy.default)
    assert mensagem["To"] == f"ana@exemplo.org.br, {REMETENTE}" and mensagem["From"] == REMETENTE
    assert mensagem["Subject"] == "Notas fiscais pendentes - Hospital Exemplo - Outubro/2026"
    assert mensagem.get_content_type() == "text/html"
    assert "Olá, Ana," in mensagem.get_content() and "à disposição" in mensagem.get_content()
    assert mensagem["Cc"] is None                       # sem contato com "Cópia", sem Cc


def test_t9_mensagem_mime_com_copia():
    email = _email("Ana", ["ana@exemplo.org.br"])
    email.copia = ["lia@exemplo.org.br", "contabil@exemplo.org.br"]
    mensagem = message_from_bytes(base64.urlsafe_b64decode(mensagem_mime(email, REMETENTE)), policy=policy.default)
    assert mensagem["To"] == "ana@exemplo.org.br"
    assert mensagem["Cc"] == "lia@exemplo.org.br, contabil@exemplo.org.br"


# ---------------------------------------------------------------------------
# G3 e G6: autorização (sem internet: só os caminhos que não chamam o Google)
# ---------------------------------------------------------------------------

def test_g6_sem_credentials_json_mensagem_clara(tmp_path):
    with pytest.raises(ErroGmail, match="credentials.json"):
        ClienteGmail(tmp_path / "credentials.json", tmp_path / "token.json")


def test_g3_token_estragado_pede_autorizacao_de_novo(tmp_path):
    (tmp_path / "token.json").write_text("isto não é um token", encoding="utf-8")
    with pytest.raises(ErroGmail, match="credentials.json"):      # foi para a autorização, sem erro técnico
        ClienteGmail(tmp_path / "credentials.json", tmp_path / "token.json")


def test_g6_credentials_de_outro_tipo(tmp_path):
    (tmp_path / "credentials.json").write_text(json.dumps({"outro": {}}), encoding="utf-8")
    with pytest.raises(ErroGmail, match="App para computador"):
        ClienteGmail(tmp_path / "credentials.json", tmp_path / "token.json")


def test_g3_token_valido_nao_abre_o_navegador(tmp_path):
    validade = (datetime.now(timezone.utc) + timedelta(hours=1)).replace(tzinfo=None)
    (tmp_path / "token.json").write_text(json.dumps({
        "token": "simulado", "refresh_token": "simulado", "client_id": "id", "client_secret": "segredo",
        "token_uri": "https://oauth2.googleapis.com/token", "scopes": list(gmail.cfg.GMAIL_ESCOPOS),
        "expiry": validade.isoformat() + "Z"}), encoding="utf-8")
    cliente = ClienteGmail(tmp_path / "nao_precisa.json", tmp_path / "token.json")
    assert cliente is not None


def test_g3_esquecer_autorizacao(tmp_path):
    token = tmp_path / "token.json"
    token.write_text("{}", encoding="utf-8")
    esquecer_autorizacao(token)
    esquecer_autorizacao(token)                   # já apagado: sem erro
    assert not token.exists()


def test_token_fica_no_appdata(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert gmail.caminho_token() == tmp_path / "CentralConciliacoes" / "checklist_contratos" / "gmail_token.json"


def test_bibliotecas_do_google_nao_atrasam_a_abertura():
    codigo = ("import sys, modulos.checklist_contratos.processamento; "
              "print(any(m.startswith('google') for m in sys.modules))")
    saida = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, check=True)
    assert saida.stdout.strip() == "False"
