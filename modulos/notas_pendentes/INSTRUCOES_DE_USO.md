# Notas Pendentes — instruções de uso

## O que o módulo faz (e o que não faz)

**Faz:** lê a pasta da rede com as notas fiscais de serviço que ainda não foram encaminhadas para registro, junta os PDFs pelo **número do responsável** (o número no começo do nome de cada PDF) e monta **um e-mail para cada número**, com o texto padrão, a lista das notas e **todos os PDFs anexados**.

**Não faz:**

- não move, não renomeia e não apaga nenhum PDF da pasta;
- não altera o Check list (só lê a aba Emails);
- ainda não envia os e-mails: o envio com os anexos entra quando a TI liberar a API de envio. Por enquanto, os rascunhos são criados pelo Claude Desktop, **sem os PDFs**, e você anexa os PDFs à mão (veja o passo 3).

---

## Passo a passo

### 1. A pasta das notas

As notas do mês ficam em `\\servidor-arquivos\contabilidade\8- NOTAS PENDENTES AUTOMATIZADOR\HOSPITAL EXEMPLO\<MMAAAA>` (ex.: `102026` para outubro de 2026). O nome de cada PDF começa com o **número do responsável**, seguido de um separador: `13.DANFSe-...`, `13-DANFSe-...`, `13+DANFSe-...` ou `13 DANFSe-...`.

### 2. Aba "E-mails"

| Campo | O que escolher |
|---|---|
| **Competência** | o mês das notas, no formato MM/AAAA (ex.: 10/2026). |
| **Prazo para registro** | a data limite que vai no texto (ex.: 29/10/2026). A tela sugere o mesmo dia do último prazo usado, no mês da competência: confira. |
| **Pasta das notas do mês** | a pasta `<MMAAAA>` da rede. Ao mudar a competência, a pasta do mês novo entra sozinha, se já existir. |
| **Check list de contratos** | o `Check list <ano>.xlsx` da rede: os contatos vêm da aba **Emails**. Pode estar aberto no Excel de alguém: o programa lê uma cópia. |
| **Modelo do e-mail** | opcional: o `modelo_email.txt` (veja abaixo). Se ele estiver na pasta `config`, ao lado das pastas dos meses, entra sozinho. Sem ele, vale o texto de fábrica. |
| **Pasta de saída** | onde a prévia, o texto para o Claude Desktop e o relatório serão gravados (nunca a própria pasta das notas). |

As escolhas ficam lembradas para o mês seguinte. Clique em **Gerar e-mails**.

O que sai na pasta de saída:

- **`Previa_notas_pendentes_<AAAA-MM>_<data e hora>.html`**: todos os e-mails (destinatários, assunto, texto e a lista dos anexos), para conferir no navegador. As notas que ficaram **sem e-mail** aparecem em vermelho, com o motivo.
- **`Emails_para_Claude_Desktop_<AAAA-MM>_<data e hora>.txt`**: os mesmos e-mails com as instruções para o Claude Desktop criar os rascunhos (botão **Texto Claude**).
- **`Notas_pendentes_<AAAA-MM>_<data e hora>.xlsx`**: o relatório, com a aba **Arquivos** (uma linha por arquivo da pasta e o que aconteceu com ele: anexada, sem número, número sem contato, ignorado) e a aba **Avisos**.

### 3. Rascunhos pelo Claude Desktop (enquanto não há o envio pela API da TI)

1. Clique em **Texto Claude**, copie tudo e cole no Claude Desktop ligado ao Gmail da Contabilidade.
2. Ele cria **um rascunho por e-mail**, com destinatários, assunto e texto, **sem anexos e sem enviar nada**.
3. No Gmail, abra cada rascunho e anexe os PDFs da lista **"ANEXAR À MÃO"** daquele e-mail (a pasta e o nome de cada arquivo estão no texto). Confira e envie.

---

## Quem recebe cada e-mail

Os destinatários vêm da aba **Emails** do Check list de contratos (a mesma lista do módulo Notas Check-list):

- na coluna A, a pessoa (`Nome <email>`, `<email>` ou só o e-mail);
- na coluna B, ao lado, os números que ela recebe, separados por `;` (ex.: `11; 12; 13`);
- `Todos` na coluna B: recebe **todos** os e-mails.
- `Cópia` na coluna B: vai **em cópia** (Cc) de todos os e-mails. Pode juntar com o número: `6; Cópia` (no Para dos e-mails do 6 e em cópia nos outros).

Um número que só tem os contatos `Todos` ou `Cópia` fica **sem e-mail** (aparece em vermelho na prévia): cadastre na aba Emails quem responde por ele. Responsável novo: use o próximo número livre no nome dos PDFs e na coluna B dos contatos dele.

---

## O modelo do e-mail (`modelo_email.txt`)

O texto do e-mail fica num arquivo de texto que você (ou a chefia) edita no Bloco de Notas, sem precisar de uma versão nova da Central. O modelo de fábrica vem com o programa; copie-o para `...\8- NOTAS PENDENTES AUTOMATIZADOR\HOSPITAL EXEMPLO\config\modelo_email.txt` e edite lá.

- A **1ª linha** é o assunto: `Assunto: Notas fiscais pendentes de registro - Competência {competencia}`.
- Depois, uma linha em branco e o texto do e-mail.
- Marcadores que o programa troca:

| Marcador | Vira |
|---|---|
| `{competencia}` | 10/2026 |
| `{competencia_extenso}` | outubro/2026 |
| `{prazo}` | 29/10/2026 |
| `{lista_notas}` | a lista das notas anexas, uma por linha |

- Marcador digitado errado (ex.: `{prazoo}`) ou sem a linha `Assunto:`: nenhum e-mail é gerado e a tela diz o que corrigir.
- Um marcador apagado: o programa avisa e gera os e-mails mesmo assim.
