# Subvenções e Projetos — instruções de uso

## O que o módulo faz (e o que não faz)

**Faz:** preenche, em cada linha de conta das planilhas **Subvenções Investimento** (abas Federal, Estadual e Municipal) e **Projetos**, as duas colunas:

- **Saldo Patrimônio** = soma dos bens da conta no relatório "Patrimônio - Bens Subvenção";
- **Saldo Contábil** = "Saldo Atual" da conta no Balancete.

Ele cria **cópias novas** das planilhas, já com o mês novo no nome, e um relatório **Avisos_MM-AAAA.xlsx** explicando tudo o que merece atenção.

**Não faz:**

- não altera os arquivos que você seleciona (eles ficam exatamente como estavam);
- não preenche as outras colunas (Devolução, Recurso Próprio, NF em Aberto etc.): elas vêm copiadas da planilha que você selecionou e continuam sendo trabalho seu;
- não cria linhas novas: se aparecer uma conta nova no balancete, ele avisa e você inclui a linha.

A única outra mudança que ele faz nas cópias é **corrigir fórmulas de total** que deixam alguma conta de fora (por exemplo, `=SUM(D5:D33)` vira `=SUM(D5:D34)`). Quando isso acontece, sai um aviso no relatório lembrando de corrigir também a sua planilha.

---

## Passo a passo do mês

### 1. Prepare os arquivos

1. No sistema, gere o **Balancete** do mês. Pode usar o **.xls** do jeito que o Tasy gera, sem abrir no Excel.
2. No sistema, gere o relatório **Patrimônio - Bens Subvenção** do mesmo mês (também pode ser o .xls do Tasy).
3. Separe as planilhas **Subvenções Investimento** e **Projetos** do **mês anterior** (por exemplo, `Projetos 08-2026.xlsx` para fazer setembro). Elas servem de base: o programa faz a cópia do mês novo a partir delas.
4. Crie (ou escolha) a **pasta onde as planilhas novas serão salvas**, por exemplo a pasta do mês na rede.

> O balancete e o patrimônio podem ser o **.xls direto do Tasy** ou o **.xlsx** salvo no Excel: o resultado é o mesmo. As **planilhas a preencher** (Subvenções e Projetos) precisam ser **.xlsx**.

### 2. Escolha os arquivos (aba "Preenchimento")

| Campo | O que escolher |
|---|---|
| **Mês de referência** | aparece sozinho, lido do balancete. Confira; se precisar, digite outro no formato **MM/AAAA** (ex.: 09/2026). É esse mês que vai no nome dos arquivos gerados. |
| **Balancete** | o balancete do mês. Abaixo do nome aparece o mês lido. A pasta dele é sugerida como pasta de saída. |
| **Relatório de patrimônio** | o relatório de patrimônio do mês. Se o mês for diferente do balancete, a linha abaixo fica laranja. |
| **Planilhas a preencher** | clique em **Selecionar** e escolha as planilhas do mês anterior (dá para escolher as duas de uma vez segurando Ctrl). **Trocar** escolhe de novo. |
| **Pasta de saída** | a pasta onde as cópias e o relatório serão gravados. |

> Escolheu um arquivo por engano? Clique em **Limpar**, embaixo do botão **Trocar** do cartão: a seleção sai e o cartão volta a ficar vazio.

### 3. Clique em **Preencher**

A tela pode fazer duas perguntas:

- **"O balancete é de X, mas o relatório de patrimônio é de Y. Deseja continuar mesmo assim?"** Normalmente significa que foi escolhido o arquivo do mês errado. Responda **Não** e confira.
- **"Estes arquivos já existem na pasta de saída e serão substituídos"**. Responda **Sim** só se quiser mesmo refazer (por exemplo, depois de corrigir algo). Se algum deles estiver aberto no Excel, feche antes.

Se a pasta de saída for a mesma das planilhas e o mês também, a cópia teria o nome da própria planilha de entrada: a tela avisa e não segue (os arquivos de entrada nunca são alterados). Escolha outra pasta de saída ou confira o mês.

Enquanto processa, aparece a barra de andamento (leva alguns segundos).

### 4. Confira o resultado

- **Números:** contas preenchidas, contas com diferença a analisar (Saldo Patrimônio ≠ Saldo Contábil) e avisos (com a quantidade de erros).
- **Tabela:** contas e contas com diferença, por aba.
- **Conferências:** "Soma dos bens = total do relatório" e "Saldo contábil de cada aba = balancete" devem aparecer em verde. Arquivos com problema aparecem em vermelho.
- **Botões:** **Abrir pasta**, **Ver avisos** (abre o relatório de avisos) e **Novo** (limpa as escolhas para outro mês).

Na pasta de saída estarão as planilhas novas, com o mês no nome (ex.: `Projetos 09-2026.xlsx`), e o relatório **Avisos_09-2026.xlsx**. Abra primeiro o **relatório de avisos** (explicado abaixo). Depois complete nas planilhas novas as colunas que são manuais.

---

## O relatório de avisos (Avisos_MM-AAAA.xlsx)

### Abas

| Aba | Para que serve |
|---|---|
| **Resumo** | Visão geral: mês, quantidade de avisos por gravidade, cada arquivo lido e o que aconteceu com ele, planilhas geradas (linhas preenchidas e quantas têm Saldo Patrimônio diferente do Contábil), **conferência por aba** (soma do Saldo Contábil da aba x conta sintética do balancete) e **total geral do patrimônio** (soma dos bens x total do relatório). Todas as conferências devem mostrar **"sim"**. |
| **Avisos** | Um aviso por linha: gravidade, tipo, arquivo, aba, linha, conta e a explicação. Os ERROS vêm primeiro. Use o filtro do Excel para ver por tipo. |
| **Conferência** | Todas as linhas de conta de todas as planilhas, com o valor gravado em cada coluna, a diferença (Patrimônio − Contábil) e observações. É a "prova" do que foi preenchido. |
| **Patrimônio** | Todas as contas do relatório de patrimônio: soma dos bens, total do sistema, quantidades e situação (**usada**, **não usada**, **total divergente**, **cabeçalho ausente**). "Não usada" é normal para contas como Bens em Comodato e Doações. |

### Gravidades

| Gravidade | Significado | O que fazer |
|---|---|---|
| **ERRO** (vermelho) | Algo impediu o trabalho ou pode ter deixado valor errado: arquivo não lido, planilha não gerada, bem que não foi lido, total do patrimônio que não bate. | **Resolver antes de usar as planilhas.** |
| **ATENÇÃO** (amarelo) | O programa fez o trabalho, mas encontrou algo para você conferir. | Ler e conferir. Muitos se repetem todo mês até a planilha base ser ajustada. |
| **INFO** | Apenas informação. | Nada, normalmente. |

### Tipos de aviso

| Tipo | Gravidade | O que significa | O que fazer |
|---|---|---|---|
| arquivo não lido | ERRO | O balancete ou o patrimônio não pôde ser aberto (arquivo errado, corrompido, aberto no Excel, ou balancete sem nenhuma conta). Nesse caso **nenhuma planilha é gerada**. | Veja a mensagem, corrija o arquivo e processe de novo. |
| planilha não gerada | ERRO | Uma planilha não pôde ser lida ou gravada. As outras foram geradas normalmente. | Veja a mensagem (ex.: "Feche o arquivo no Excel") e processe de novo. |
| aba sem títulos | ERRO | A aba tem "Conta Contábil", mas falta "Saldo Patrimônio" ou "Saldo Contábil" na linha de títulos. A aba não foi preenchida. | Confira os títulos da aba. |
| linha não reconhecida | ERRO | Uma linha do balancete ou do patrimônio não está no formato esperado e **não foi usada** (o programa não adivinha valores). | Veja a linha indicada no arquivo. Se o relatório do sistema mudou de formato, peça o ajuste do programa. |
| total geral não confere | ERRO | A soma de todos os bens lidos não bate com a linha "Total(...)" do relatório de patrimônio. Algum bem pode ter ficado de fora. | Não use os Saldos Patrimônio até entender a diferença (compare a aba Patrimônio com o relatório). |
| meses diferentes | ATENÇÃO | O balancete e o patrimônio são de meses diferentes, ou o mês digitado é diferente do mês do balancete. | Confira se os arquivos certos foram escolhidos. |
| conta nova no balancete | ATENÇÃO | Existe no balancete uma conta que não tem linha em nenhuma planilha. | Inclua a linha na planilha (com o código na coluna Conta Contábil) e processe de novo. |
| conta fora do balancete | ATENÇÃO | O código da planilha não está no balancete (conta encerrada ou com saldo zero). Os dois saldos ficam **0**. | Normal para contas zeradas. Confira se o código está certo. |
| conta sem bens no patrimônio | ATENÇÃO | A conta está no balancete, mas não existe conta com o mesmo nome no patrimônio. Saldo Patrimônio fica **0**. | Normal para convênios sem bens ainda. Se deveria ter bens, confira se o nome da conta é igual no balancete e no patrimônio. |
| conferência da aba não bate | ATENÇÃO | A soma do Saldo Contábil da aba é diferente do saldo da conta sintética do balancete (ou as contas da aba são de mais de uma sintética). | Normalmente falta a linha de uma conta nova, ou há código repetido. |
| total do sistema divergente | ATENÇÃO | Na conta do patrimônio, a linha "Total" do sistema não bate com a soma dos bens. O programa usa a **soma dos bens**. | Apenas saiba que o total do relatório está errado. |
| quantidade divergente | ATENÇÃO | O número de bens lidos numa conta é diferente do número entre parênteses na linha Total. | Confira a conta no relatório de patrimônio. |
| cabeçalho ausente | ATENÇÃO | No patrimônio, uma conta veio sem a linha com o nome; foi identificada pela linha Total. | Apenas conferir o valor da conta. |
| conta repetida no patrimônio | ATENÇÃO | O mesmo nome de conta aparece em mais de um bloco do relatório. O saldo é a **soma dos blocos**; a mensagem mostra as linhas de cada bloco. | Conferir no relatório se faz sentido. |
| código repetido nas planilhas | ATENÇÃO | O mesmo código aparece em mais de uma linha. Todas recebem os mesmos saldos. | Normalmente é erro de digitação: corrija o código. |
| código repetido no balancete | ATENÇÃO | O mesmo código aparece duas vezes no balancete; vale a primeira. | Conferir o balancete. |
| itens sem conta | ATENÇÃO | Bens do patrimônio que não ficaram em nenhuma conta. | Conferir o relatório de patrimônio (o total geral também vai acusar). |
| fórmula de total corrigida | ATENÇÃO | Uma fórmula de total da planilha deixava linhas de conta de fora; **na cópia gerada ela já foi corrigida**. | Corrija também a fórmula na sua planilha para o aviso deixar de aparecer. |
| fórmula de total incompleta | ATENÇÃO | Mesmo caso acima, mas a fórmula é complexa e **não foi corrigida**. | Corrija a fórmula na planilha. |
| vínculo externo | ATENÇÃO | Uma célula puxa valor de outro arquivo (fórmula com `[1]...`). O valor depende desse arquivo. | Avaliar se o vínculo ainda é necessário. |
| mês não encontrado / mês não reconhecido / mês diferente entre páginas | ATENÇÃO | Não deu para ler o mês de um arquivo, ou as páginas têm meses diferentes. | Conferir o arquivo e o mês de referência na tela. |
| total geral repetido | ATENÇÃO | O relatório de patrimônio tem mais de uma linha de total geral. | Conferir o relatório. |
| aba sem contas | INFO | Uma aba não tem a linha de títulos com "Conta Contábil" e foi ignorada (ex.: aba de anotações). | Nada, se for isso mesmo. |

---

## Quando algo dá errado

| Situação | O que fazer |
|---|---|
| "Não foi possível gravar... Ele provavelmente está aberto no Excel" | Feche o arquivo indicado (a planilha de saída ou o relatório) e clique em **Preencher** de novo. |
| "o balancete não tem nenhuma conta (só o cabeçalho)" | O Tasy exportou o balancete vazio. Tire de novo, conferindo se as contas aparecem, e processe outra vez. |
| "a planilha a preencher precisa ser .xlsx" | Abra a planilha de Subvenções/Projetos no Excel e salve como .xlsx. |
| O mês não aparece sozinho ("Mês não identificado") | O balancete pode estar em formato diferente. Digite o mês à mão e veja os avisos. |
| "Estes arquivos seriam gravados por cima dos arquivos de entrada" | A pasta de saída é a mesma da planilha e o mês é o mesmo. Escolha outra pasta de saída ou confira o mês. |
| Nenhuma planilha foi gerada | Veja nas conferências (e no Resumo do relatório) se o balancete ou o patrimônio falhou (ERRO "arquivo não lido"). |
| "Saldo contábil da aba ... ≠ balancete" | Veja no relatório de avisos se há "conta nova no balancete" ou "código repetido". |
| "Soma dos bens diferente do total do relatório" | Não use os Saldos Patrimônio: veja os avisos "linha não reconhecida" e peça o ajuste do programa. |
| Apareceu "Erro inesperado" | Anote a mensagem (os detalhes técnicos aparecem no resultado) e peça o ajuste do programa. |
