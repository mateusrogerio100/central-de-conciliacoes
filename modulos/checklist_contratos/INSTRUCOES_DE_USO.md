# Notas Check-list — instruções de uso

## O que o módulo faz (e o que não faz)

**Faz**, em três passos (uma aba para cada):

1. **Conferência:** procura no movimento do Tasy a nota de cada contrato do Check list (pelo fornecedor, pela conta e pela descrição) e grava o valor numa **cópia** do Check list. Avisa quando a nota foi lançada na **conta errada**.
2. **Pendências:** separa, por responsável, as notas de contrato que ainda não chegaram no mês e monta um e-mail para cada um.
3. **E-mails:** cria os e-mails como **rascunhos** no Gmail da Contabilidade, para você revisar e enviar.

**Não faz:**

- não altera nada no Tasy;
- não altera o Check list da rede: grava uma cópia na pasta de saída, e você confere e copia para a rede;
- não envia e-mail: só cria rascunhos.

---

## Passo a passo do dia

### 1. Exporte o movimento do Tasy

Exporte em **.csv** o movimento do dia (o "Movimento contábil" ou o "Movimentos_NF"), um para a **Hospital Exemplo** e um para o **CMD**. Use o arquivo como sai do Tasy, sem abrir e salvar no Excel.

Guarde cada dia numa pasta por estabelecimento (uma pasta para a Hospital Exemplo e outra para o CMD). O programa lê **todos os .csv da pasta juntos**, então ele enxerga o mês inteiro até o dia mais recente: as somas, as notas em duplicidade e as variações saem certas.

- Baixou o mesmo dia duas vezes? O programa usa o arquivo mais recente e avisa.
- Estornos e notas devolvidas são reconhecidos e não contam em dobro (aparecem na aba "Estornos e devoluções" do relatório).

### 2. Aba "Conferência"

| Campo | O que escolher |
|---|---|
| **Mês de referência** | o mês das notas, no formato MM/AAAA (ex.: 10/2026). |
| **Movimento da Hospital Exemplo** e **do CMD** | as pastas do passo 1. Abaixo aparece quantos lançamentos foram lidos. |
| **Check list** | o `Check list <ano>.xlsx` da rede, já atualizado por você. Pode estar aberto no Excel de alguém: o programa lê uma cópia. |
| **Pasta das regras** | a pasta onde está o `regras.csv` (as regras de cada linha do Check list). Se ela se chamar `config` e ficar ao lado do Check list (ou se o `regras.csv` estiver na própria pasta do Check list), entra sozinha ao escolher o Check list. |
| **Pasta de saída** | onde a cópia preenchida e o relatório serão gravados. |

As escolhas ficam lembradas para o dia seguinte. Clique em **Conferir mês**.

O que sai na pasta de saída:

- **`Check list <ano> - <MM> preenchido.xlsx`**: a cópia, com o valor do mês preenchido **só nas linhas OK** e só nas células vazias. O resto da planilha fica igual. Confira e copie os valores para a rede.
- **`Conferencia_Contratos_<AAAA-MM>_<data e hora>.xlsx`**: o relatório (veja abaixo).

Na tela:

- **Números:** preenchidas na cópia, conta divergente, não encontradas e manuais.
- **Conta divergente: corrigir no Tasy:** a nota chegou, mas está numa conta diferente da do Check list.
- **Destaques:** valor achado diferente do que já está na planilha (pode ser outra nota do mesmo contrato ou uma duplicidade) e variação de 10% ou mais sobre o mês anterior.

### 3. Aba "Pendências"

| Campo | O que escolher |
|---|---|
| **Mês de referência** | o mesmo mês. |
| **Check list da rede** | o Check list **depois** de você copiar os valores da conferência. |
| **Relatório da conferência** | opcional: as linhas com conta divergente ficam fora dos e-mails (a nota já chegou) e aparecem no fim da prévia, em "Fora dos e-mails: conta divergente", para você corrigir a conta. Depois de conferir, o relatório novo já vem escolhido. |
| **Pasta de saída** | onde a prévia e o texto serão gravados. |

Clique em **Gerar pendências**. Ficam pendentes as linhas com a célula do mês **vazia**. Ficam de fora a célula com texto ("Provisão", "virá no lote programado"...) e o contrato que no mês anterior diz encerrado, rescindido, finalizado ou "não assinou".

O que sai na pasta de saída:

- **`Previa_emails_<AAAA-MM>_<data e hora>.html`**: todos os e-mails, para conferir no navegador. Quem ficou **sem e-mail** aparece em vermelho, com o motivo e as notas.
- **`Emails_para_Claude_Desktop_<AAAA-MM>_<data e hora>.txt`**: os mesmos e-mails com as instruções para o Claude Desktop criar os rascunhos (botão **Texto Claude**). Copie tudo e cole no Claude Desktop ligado ao Gmail da Contabilidade.

### 4. Aba "E-mails" (rascunhos direto no Gmail)

Precisa do `credentials.json` do Google (veja "Gmail: o pedido à TI" abaixo).

- **Credencial do Google:** o `credentials.json`, escolhido uma vez.
- **Remetente esperado:** a conta em que os rascunhos devem ficar (padrão: a da Contabilidade). Se a conta autorizada for outra, o programa para e não cria nada.
- **Criar rascunhos no Gmail:** na primeira vez o navegador abre para você autorizar. Um rascunho por e-mail; **nada é enviado**. Um registro `Envio_Gmail_<data e hora>.csv` fica na pasta de saída.
- **Trocar conta:** esquece a autorização; na próxima vez o navegador pede de novo.

---

## Quem recebe cada e-mail: os números dos responsáveis

Os destinatários vêm do próprio Check list:

- Na coluna **Responsável**, cada linha começa com o **número** do responsável: `13 - Carlos manutenção`. O número identifica o responsável; o nome vai na saudação ("Olá, Carlos,").
- Na aba **Emails**, cada pessoa fica numa célula da coluna A (`Nome <email>`, `<email>` ou só o e-mail) e, **na célula ao lado (coluna B)**, os números dos responsáveis cujos e-mails ela recebe, separados por `;`: `11; 12; 13`.
- `Todos` na coluna B: vai em todos os e-mails. `Todos CMD`: vai em todos os e-mails que tenham notas do CMD. `Cópia`: vai **em cópia** (Cc) de todos os e-mails. `Cópia CMD`: em cópia só dos e-mails que tenham notas do CMD. Pode juntar: `6; Todos` ou `6; Cópia` (no Para dos e-mails do 6 e em cópia nos outros).

Um responsável com notas na Hospital Exemplo e no CMD recebe um e-mail só, com as duas tabelas.

**Fica sem e-mail** (aparece em vermelho na prévia e na tela): linha sem número na coluna Responsável, linha sem responsável, ou número que nenhum contato da aba Emails tem.

Para mudar quem recebe: mude o número na coluna B da aba Emails. Responsável novo: dê a ele o próximo número livre, na coluna Responsável e na coluna B dos contatos dele.

---

## As situações do relatório

| Situação | O que significa | O que fazer |
|---|---|---|
| **OK** (verde) | achou a nota na conta certa; o valor foi para a cópia | conferir e copiar para a rede |
| **OK (célula já preenchida)** | a célula do mês já tinha algo: não foi alterada | se estiver destacada, o valor achado é diferente: veja as notas na coluna "Lançamentos usados". Se a célula diz **"Provisão"**, a coluna Obs avisa: "Valor se refere ao mês anterior, pois ele foi provisionado" |
| **CONTA DIVERGENTE** (laranja) | a nota chegou numa conta diferente | corrigir a conta no Tasy |
| **NÃO ENCONTRADO** (rosa) | nenhuma nota do contrato no movimento | a nota ainda não chegou: vai para as pendências |
| **MANUAL** (amarelo) | linha que você preenche à mão; o relatório lista as notas candidatas | preencher à mão |
| **IGNORADO** (cinza) | contrato encerrado, rescindido... | nada |

Outras abas do relatório: **Conta divergente**, **Manuais**, **Não vinculados** (notas de fornecedores do Check list que nenhuma linha usou: duplicidade, nome novo, outro produto, devolução, conta 23334), **Estornos e devoluções** e **Avisos**.

---

## A configuração (`regras.csv`)

Uma linha por linha do Check list, separada por `;`. Guarde-o numa pasta `config` **ao lado do Check list, na rede**: assim ele entra sozinho na tela e a equipe toda usa as mesmas regras. Para mudar uma regra, abra o `regras.csv` no Excel, altere e salve (continue em `.csv` separado por `;`).

| Coluna | Uso |
|---|---|
| `Aba` | `SC` ou `CMD` |
| `Linha` | a linha da planilha |
| `Fornecedor_Planilha`, `Descricao_Planilha` | o texto das colunas Fornecedor e Descrição da despesa daquela linha. Se a linha mudar de lugar, o programa a acha por eles e avisa. |
| `Contas` | as contas aceitas, separadas por `/` |
| `Busca_Fornecedor` | o que procurar no complemento do lançamento (sem acento, minúsculo; `\|` = ou; `^` = começa com) |
| `Busca_Descricao` | opcional: o complemento também precisa ter isto |
| `Excluir` | opcional: descarta os lançamentos que tenham isto |
| `Selecao` | vazio = soma todas as notas; `maior` ou `menor` = fica com uma só |
| `Tipo` | `auto`, `manual` ou `ignorar` |
| `Obs` | texto livre, vai para o relatório |
| `Centro_Custo` | opcional (coluna no fim): só as notas com um centro de custo que tenha isto (sem acento, minúsculo; `\|` = ou). Ex.: os dois contratos de locação de veículos, `engenharia clinica` numa linha e `laboratorio\|gerencia` na outra. Precisa do movimento **"Movimento contábil"** (o que traz o centro de custo); com o outro .csv a linha fica Manual, com aviso. |

Exemplo: `SC;12;Fornecedor Exemplo Ltda;Locação de equipamento;30044;^fornecedor exemplo;locacao;;;auto;`

Os arquivos antigos `destinatarios_extras.csv` e `redirecionamentos.csv` não são mais usados (os destinatários vêm dos números do Check list): se estiverem na pasta, o relatório avisa e você pode apagá-los.

---

## Gmail: o pedido à TI

Para a aba "E-mails" criar os rascunhos direto no Gmail, peça à TI:

> Criar um projeto no Google Cloud da Hospital Exemplo, ativar a **Gmail API**, configurar a tela de consentimento como **Interno** e criar uma credencial OAuth do tipo **"App para computador"**. Enviar o arquivo `credentials.json`.

Guarde o `credentials.json` numa pasta sua (não na pasta da Central) e escolha-o na aba "E-mails". A autorização fica guardada no seu usuário do Windows (`%APPDATA%\CentralConciliacoes\checklist_contratos\gmail_token.json`); o botão **Trocar conta** a apaga.

Enquanto não houver a credencial, use o texto para o Claude Desktop (aba "Pendências").
