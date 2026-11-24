# Estoque — instruções de uso

## O que o módulo faz (e o que não faz)

**Faz:** as três etapas da conciliação de estoque, **um botão para cada uma**, cada botão gerando o seu Excel. Faça na ordem: EST-01, EST-02 e EST-03.

| Botão | O que compara | Arquivos que usa | Excel gerado |
|---|---|---|---|
| **EST-01 · Conciliação saldo anterior estoque** | **Saldo anterior** do balancete x **Saldo anterior** do Mapa do Estoque, conta por conta | Balancete + Mapa do Estoque | `EST-01 Conciliação saldo anterior estoque MM-AAAA.xlsx` |
| **EST-02 · Conciliação contas estoque** | Total de cada grupo do Mapa do Estoque (Notas Fiscais, Out.Entradas, Consumo...) x soma das operações do PDF "Movimento estoque" | Mapa do Estoque + PDF | `EST-02 Conciliação contas estoque MM-AAAA.xlsx` |
| **EST-03 · Conciliação saldo atual estoque** | **Saldo atual** do balancete x **Saldo atual** do Mapa do Estoque, conta por conta | Balancete + Mapa do Estoque | `EST-03 Conciliação saldo atual estoque MM-AAAA.xlsx` |

Cada conta do balancete é ligada ao local do Mapa do Estoque pelo **número entre parênteses** no fim do nome (ex.: "Central de Kits - SC **(23)**" com "Central de Kits **(23)**"). Se o número faltar, o programa tenta pelo nome e avisa para conferir.

**Não faz:**

- não altera os arquivos que você seleciona;
- não cria lançamentos nem corrige saldos: só mostra onde está a diferença e a causa provável;
- não inventa a conta que o balancete não imprimiu (veja "Conta zerada que não aparece no balancete").

---

## Passo a passo do mês

### 1. Prepare os arquivos no Tasy

1. **Balancete** do mês (grupo 1.01.04 ESTOQUES). **Recomendação:** gere com a opção de **trazer as contas zeradas**. Sem ela, uma conta que zerou no mês some do balancete e a EST-01 mostra diferença no grupo dela.
2. **SCF - Movimento Estoque (Contabilidade)** do mesmo mês (o **Mapa do Estoque**: é assim que ele aparece na tela e nos Excels) (o mesmo relatório serve para as três etapas). Vale também o do **CMD** e dos **AMES**, que vem sem a coluna Subvenção: ela é considerada 0,00 (aparece um aviso INFO no Resumo). O balancete do CMD/AMES, com Débitos e Créditos no lugar do Movimento, também é aceito; como as contas dele não têm o número do local entre parênteses, elas casam pelo nome (confira a coluna "como casou").
3. **PDF "Movimento estoque"**, com quebra por **Operação**. Pode ser tirado pela **Data de Referência** ou por **período** ("De … Até …"); no período, use o mês inteiro (do dia 1 ao último dia), senão aparece um aviso de atenção e o programa não confere o mês do PDF.

> Os ".xls" do Tasy podem ser usados direto, sem abrir no Excel. Se você abriu e salvou, use "Salvar como" > **Pasta de Trabalho do Excel (.xlsx)**.

### 2. Escolha os arquivos (aba "Conciliação")

| Campo | O que escolher |
|---|---|
| **Mês de referência** | aparece sozinho, lido do balancete (ou do Mapa do Estoque, se o balancete ainda não foi escolhido). Confira; se precisar, digite no formato **MM/AAAA**. É esse mês que vai no nome dos Excels. |
| **Balancete** | o balancete do Tasy (EST-01 e EST-03). Abaixo do nome aparece o mês lido. A pasta dele é sugerida como pasta de saída. |
| **Mapa do Estoque** | o relatório SCF - Movimento Estoque (Contabilidade) do Tasy (as três etapas). Se o mês for diferente dos outros arquivos, a linha abaixo fica laranja. |
| **PDF Movimento estoque** | o PDF do Tasy (só a EST-02). |
| **Pasta de saída** | onde os Excels serão gravados. |

Cada botão fica disponível assim que os arquivos **daquela etapa** e a pasta de saída estão escolhidos. Ex.: com o Mapa do Estoque e o PDF, já dá para fazer a EST-02.

Logo acima dos botões aparece qual **configuração da EST-02** está valendo (de fábrica ou a sua) e o botão **Editar configuração** (explicado abaixo).

> Escolheu um arquivo por engano? Clique em **Limpar**, embaixo do botão do cartão.

### 3. Clique no botão da etapa

A tela pode perguntar:

- **"Os meses não batem... Deseja continuar mesmo assim?"** Normalmente foi escolhido o arquivo do mês errado. Responda **Não** e confira.
- **"Estes arquivos já existem na pasta de saída e serão substituídos"**. Responda **Sim** só se quiser refazer. Se o Excel estiver aberto, feche antes.

### 4. Confira o resultado

O resultado mostra a etapa que acabou de ser feita:

- **Números:** na EST-01 e na EST-03, contas conciliadas, contas com diferença e avisos; na EST-02, grupos conferidos (de 11), grupos com diferença e avisos.
- **Tabela:** na EST-01 e na EST-03, contas por grupo (Hospital Exemplo, Coração, Câncer); na EST-02, a diferença de cada grupo do Mapa do Estoque.
- **Conferências:** em verde o que bate; em laranja o que precisa de atenção; em vermelho o que impediu o Excel de ser gerado.
- **Avisos:** a lista completa, logo abaixo.
- **Botões:** **Abrir Excel**, **Abrir pasta** e **Novo** (limpa as escolhas para outro mês).

Depois, é só clicar no botão da próxima etapa: os arquivos continuam escolhidos.

---

## Os Excels gerados

### EST-01 e EST-03 (abas "Conciliação" e "Análise")

| Aba | Para que serve |
|---|---|
| **Conciliação** | Contas agrupadas por Hospital Exemplo, Coração e Câncer, com subtotal e TOTAL GERAL. Colunas: classificação, código, descrição no balancete, saldo do balancete, descrição no Mapa do Estoque, saldo do Mapa do Estoque, diferença, como casou e observação. No fim, o bloco **Conferências** e a lista de **locais do Mapa do Estoque sem conta no balancete**. |
| **Análise** | Uma linha por conta (com a classificação) e por local sem conta, com **filtro**. Use o filtro da coluna Diferença para ver só o que precisa corrigir; o TOTAL acompanha o filtro. Logo depois da Diferença vem o **Código** da conta contábil (o mesmo da aba Conciliação): é com ele que a diferença é lançada no Tasy. |

A **Diferença** é sempre fórmula (balancete − Mapa do Estoque). Zero aparece como "-"; diferença fica em **laranja**.

**Como casou:**

| Texto | Significado |
|---|---|
| Código do local | o número entre parênteses é o mesmo nos dois relatórios |
| Nome equivalente — conferir | sem número igual, casou pelo nome (abreviações como SC, HC e Hosp. são entendidas). Confira se o par está certo. |
| Sem par | não achou o local; a observação pode sugerir um "possível par" |

**Conferências:** saldo da conta 1.01.04 x soma das contas; linha Total do Mapa do Estoque x contas + locais sem conta; e cada grupo (1.01.04.01, .02, .03) x subtotal das contas dele.

### EST-02 (abas "Grupos" e "Operações")

| Aba | Para que serve |
|---|---|
| **Grupos** | Cada grupo do Mapa do Estoque: total no Mapa do Estoque, soma das operações do PDF, diferença e quais operações foram somadas. Total (E) e Total (S) somam os grupos. **Conferências:** Total geral do PDF x soma de todas as operações; fechamento do total geral (saldo anterior + entradas − saídas = saldo atual); e os **pares iguais** (ex.: Produção 15 x Consumo na Produção 16), com mensagem de ATENÇÃO quando os valores são diferentes. |
| **Operações** | Uma linha por operação do PDF: código, nome, valor, grupo e E/S. Operação **sem grupo** aparece em laranja e não entra em nenhuma soma. |

O fechamento por local não é conferido (por decisão do setor): só o total geral.

---

## Configuração da EST-02 (botão "Editar configuração")

A configuração diz **em qual grupo do Mapa do Estoque entra cada operação do Tasy**. O programa já vem com a configuração de fábrica. Ao clicar em **Editar configuração**, ele cria a sua cópia (na primeira vez) e abre no Excel. Daí em diante, vale a sua cópia.

Depois de alterar: **salve e feche** o Excel e clique na **EST-02** de novo.

### Como cadastrar uma operação nova

Quando aparecer o aviso **"Operação NNN sem grupo — cadastrar em Editar configuração"**:

1. Clique em **Editar configuração**.
2. Na aba **Itens**, acrescente uma linha: **Código** (o número da operação), **Operação** (o nome), **E/S no Tasy** (E ou S), **Tipo de operação** (opcional) e **Grupo SCF** (escolha na lista; é o grupo do Mapa do Estoque — na planilha de configuração a coluna continua com o nome antigo).
3. Salve, feche e clique na **EST-02** de novo.

Cada código só pode aparecer **uma vez**. Total (E) e Total (S) não se cadastram: o programa soma os grupos.

### Como incluir um par de operações iguais

Na aba **Pares iguais**, acrescente uma linha com **Operação A**, **Nome A**, **Operação B**, **Nome B** e uma observação. As duas operações precisam estar na aba Itens.

### Quando a configuração tem problema

Antes de rodar, o programa confere a planilha. Com código repetido, código vazio, grupo que não existe ou par inválido, a linha da configuração fica **vermelha** e a EST-02 **não é gerada** (as outras etapas funcionam normalmente). Veja o motivo nos avisos, corrija e gere de novo.

---

## Avisos

| Aviso | Gravidade | O que significa | O que fazer |
|---|---|---|---|
| arquivo não lido | ERRO | O arquivo não pôde ser aberto ou não é o relatório esperado. | Confira se escolheu o arquivo certo. |
| linha não reconhecida | ERRO | Uma linha do balancete ou do Mapa do Estoque não está no formato esperado e não foi usada. | Confira a linha indicada. Se o relatório mudou de formato, peça o ajuste do programa. |
| soma dos locais diferente do total / soma diferente do total geral | ERRO | A soma do que foi lido não bate com o total do próprio relatório: algo ficou de fora. | Não use o resultado até entender a diferença. |
| saldo não fecha | ERRO | No balancete, saldo anterior + movimento ≠ saldo atual. | Confira a conta no balancete. |
| etapa não gerada | ERRO | O Excel da etapa não pôde ser gravado (ex.: aberto no Excel). | Feche o arquivo e gere de novo. |
| código repetido / grupo inexistente / par inválido | ERRO | Problema na configuração da EST-02. | Corrija em **Editar configuração**. |
| grupo com diferença | ATENÇÃO | O saldo da conta sintética (ou o total do grupo do Mapa do Estoque) não bate com a soma. | Veja a observação; no caso de conta zerada, veja abaixo. |
| local com saldo sem conta | ATENÇÃO | Um local do Mapa do Estoque tem saldo, mas nenhuma conta do balancete casou com ele. | Normalmente é a conta zerada que o balancete não imprimiu. |
| conta sem par | ATENÇÃO | Uma conta do balancete não achou local no Mapa do Estoque. | Confira o número entre parênteses no nome da conta. |
| operação sem grupo | ATENÇÃO | Operação do PDF que não está na configuração. | Cadastre em **Editar configuração**. |
| par diferente | ATENÇÃO | Duas operações que deveriam ter o mesmo valor estão diferentes (ex.: 15 x 16). | Verificar no Tasy. |
| mês diferente | ATENÇÃO | Um dos arquivos é de outro mês. | Confira se escolheu os arquivos certos. |
| casada por nome | INFO | A conta casou pelo nome, não pelo número. | Conferir o par na aba Conciliação. |
| classificação repetida | INFO | Duas contas com a mesma classificação (ex.: 1.01.04.01.0017). Não é erro. | Nada. |
| E/S diferente do grupo | INFO | Operação marcada E no Tasy mas num grupo de saída (ou o contrário). Caso conhecido: 82 – Estorno de Saída. | Nada, se for isso mesmo. |

---

## Conta zerada que não aparece no balancete

Se o balancete for gerado **sem** as contas zeradas, uma conta cujo saldo atual zerou no mês **não aparece**, mas o saldo anterior dela continua somado na conta sintética. Na EST-01 isso aparece assim:

- o local do Mapa do Estoque fica como **"Local do Mapa do Estoque sem conta no balancete — COM SALDO"**;
- o grupo da conta mostra diferença igual a esse saldo, com a observação **"provável conta com saldo atual zero que o balancete não imprime"**.

**Solução:** gere o balancete no Tasy com a opção de **trazer as contas zeradas** e clique na **EST-01** de novo. A conta aparece e a diferença some.

---

## Quando algo dá errado

| Situação | O que fazer |
|---|---|
| "Não foi possível gravar... aberto no Excel" | Feche o Excel indicado e clique no botão da etapa de novo. |
| "é um Excel antigo (.xls 97-2003)" | Abra no Excel e salve como .xlsx. |
| "os títulos das colunas do Mapa do Estoque (SCF - Movimento Estoque) mudaram" | O Tasy mudou o relatório: peça o ajuste do programa. |
| O mês não aparece sozinho | Digite o mês à mão e veja os avisos. |
| A EST-02 não foi gerada | Veja o motivo no resultado: PDF com problema ou configuração com erro. |
| Apareceu "Erro inesperado" | Anote a mensagem (os detalhes aparecem no resultado) e peça o ajuste do programa. |
