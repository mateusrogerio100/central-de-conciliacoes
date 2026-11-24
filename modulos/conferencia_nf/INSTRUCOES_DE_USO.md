# Conferência de NF — instruções de uso

## O que o módulo faz (e o que não faz)

**Faz:** confere, fato contábil por fato contábil, o lote de Notas Fiscais importado no Tasy com os PDFs das notas. Para cada fato, ele confere:

- o **número da nota** (o "NF." do complemento);
- a **data de emissão** (o "DT" do complemento);
- o **valor**: o valor da nota no PDF tem que ser igual à **soma dos débitos** do fato;
- **partidas x contrapartidas**: o fato tem débito e crédito, e os dois somam o mesmo valor;
- o **CNPJ da unidade**: a nota (de compra ou de serviço) tem que ter vindo para a unidade que você está conferindo.

O resultado separa o lote em duas pilhas:

- **Verde:** número, data, valor e partidas já foram conferidos pelo programa. Falta só olhar se as **contas contábeis** estão certas e marcar como revisado no Tasy.
- **Conferir com a nota impressa:** o PDF não veio, o lançamento não é de nota fiscal (recibo, doação, taxa), o PDF não bate com o lançamento ou há alguma observação.

**Não faz:**

- não altera nada no Tasy nem nos arquivos que você seleciona: só lê e grava um Excel;
- não confere as contas contábeis: isso continua com você;
- não lê nota em papel escaneado nem nota de serviço de outros modelos: lê só a DANFSe nacional (v2.0) e a
  **Nota Paulistana** (NFS-e da Prefeitura de São Paulo), no PDF e no XML.

---

## Passo a passo do dia

### 1. Exporte o lote do Tasy

Exporte em **.csv** o **Movimento contábil** do lote (o arquivo com as colunas "Centro custo" e "Classificação da conta"). Ele traz os mesmos lançamentos do lote **e o centro de custo**, que o programa confere.

O lote exportado da tela de movimento (nome parecido com `Movimento_ 09_2026 Lote_ 72648 Status_ Atualizado Tipo_ Notas Fiscais.csv`) também é aceito, mas ele não traz o centro de custo: o Resumo avisa "NÃO CONFERIDO".

Use o arquivo como sai do Tasy, sem abrir e salvar no Excel.

### 2. Baixe os PDFs das notas

No download em lote das notas (DANFE das notas de compra e DANFSe das notas de serviço), filtre pela **data de atualização no estoque**, e **não** pela data de emissão. O lote do Tasy é montado pela data de entrada: baixando pela data de emissão, quase nenhuma nota casa.

- Pode deixar os PDFs em várias pastas (ex.: `danfe-lote`, `danfse-lote (11)`): o programa lê a pasta escolhida e todas as subpastas.
- Se a mesma nota estiver em duas pastas, vale a primeira; a outra aparece como "PDF repetido".
- O download pode trazer um `_sem_pdf.txt` com as notas que vieram sem DANFE. Deixe-o na pasta: o programa avisa quais notas do lote estão nele.

**XML das notas (opcional, recomendado):** se baixar também os **XMLs** (de compra e de serviço), deixe-os na mesma pasta do dia, numa subpasta (ex.: `Notas_XML`). O XML é a própria nota fiscal autorizada: o programa lê cada dado direto dele, sem depender do desenho do PDF, e uma nota que veio sem DANFE passa a ser conferida pelo XML.

- Nota com **XML e PDF**: os dados vêm do XML; a situação (cancelada, substituída) vem do PDF, porque o XML não diz se a nota foi cancelada depois. Se o XML e o PDF disserem coisas diferentes, a nota fica amarela com a diferença.
- Nota **só com XML**: é conferida normalmente, mas sem saber se foi cancelada (o Resumo diz quantas).
- Nota **só com PDF**: como sempre.
- **Nota Paulistana** (prestador de São Paulo, "PREFEITURA DO MUNICÍPIO DE SÃO PAULO" no alto da nota): o PDF e o XML são lidos como as outras notas de serviço. O PDF não diz o regime (Simples); se o programa não achar se o ISS foi retido, o fato fica roxo para conferir a retenção.
- Use o XML **autorizado** da nota (o que traz o protocolo da Sefaz). XML de evento (cancelamento, carta de correção) não é lido e aparece em "Erros de leitura".

### 3. Escolha os arquivos (aba "Conferir lote")

| Campo | O que escolher |
|---|---|
| **Unidade conferida** | a unidade do lote: Fundação Hospital Exemplo ou um dos AMEs. O programa confere se cada nota veio com o CNPJ dela. Fica lembrada para a próxima vez. |
| **Lote do Tasy** | o .csv do passo 1. Abaixo do nome aparece quantos fatos e lançamentos ele tem; em vermelho, se não for o arquivo certo. A pasta dele é sugerida como pasta de saída. |
| **Pasta das notas** | a pasta do passo 2 (com os PDFs e, se tiver, os XMLs). Abaixo aparece quantos PDFs e XMLs há nela (com as subpastas). |
| **Pasta do gabarito de contas** | opcional: a pasta do `Gabarito_contas.xlsx` (veja "Gabarito de contas" abaixo). Fica lembrada. |
| **Pasta de saída** | onde o relatório será gravado. |

Os seletores abrem nas pastas usadas na última conferência.

> Escolheu um arquivo por engano? Clique em **Limpar**, embaixo do botão do cartão.

### 4. Clique em "Conferir lote"

A barra mostra o andamento ("Lendo PDFs... 12 de 84"). O relatório é gravado como `Conferencia_NF_<data e hora>.xlsx`: um relatório novo a cada conferência, sem substituir os anteriores.

### 5. Confira o resultado

- **Números:** conferidos pelo programa (verde), para conferir com a nota impressa e PDFs sem lançamento neste lote.
- **Conferir à mão, por motivo:** quantos fatos há em cada motivo.
- **Conferências:** se todos os PDFs foram lidos, PDFs repetidos, notas sem DANFE e se as partidas fecham em todos os fatos.
- **"A pasta dos PDFs parece ser de outro dia"** (vermelho, também na linha 4 do Resumo do Excel): menos de um quarto (25%) dos PDFs da pasta casou com o lote. Quase sempre é a pasta de outro dia escolhida por engano (as pastas `danfe-lote (3)` de dias diferentes têm o mesmo nome). Troque a pasta no cartão e confira de novo.
- Botões **Abrir relatório**, **Abrir pasta** e **Novo**.

---

## O relatório (Excel)

| Aba | Para que serve |
|---|---|
| **Resumo** | Totais do lote: as duas pilhas, os motivos e a contagem dos PDFs. |
| **Conferir à mão** | A lista das notas para separar no papel, com o motivo e o que aconteceu. Tem a coluna **Conferido** para marcar. |
| **Escriturar na prefeitura** | As notas de serviço do lote (as que vieram com PDF de DANFSe), para escriturar no site da prefeitura, com a coluna **Escriturado** para marcar. Nota de serviço **sem PDF não aparece aqui** (o lote não diz se é serviço): confira as do motivo "PDF da nota não veio". |
| **Lançamentos** | O lote inteiro, na ordem do Tasy, uma linha por lançamento, com o **centro de custo**, "O que fazer" e a caixa **Revisado** em cada fato. |
| **Rateios** | As contas de resultado divididas entre centros de custo: o valor e o % de cada um e o total da conta. Só informativo. |
| **PDF x Tasy** | Uma linha por fato com o que foi lido do PDF ao lado: número, emissão, valor, emitente, para quem a nota foi emitida (destinatário / tomador) e o resultado de cada conferência (coluna **Unidade**: OK, ERRADO ou NÃO LIDO). |
| **PDFs sem lançamento** | PDFs que não casaram com nenhum fato do lote (nota de outro dia, PDF repetido, nota emitida pela própria Fundação) e as notas do `_sem_pdf.txt`. |
| **Erros de leitura** | PDFs (ou o lote) que não puderam ser lidos, com o motivo. |

Nas abas **Conferir à mão** e **Lançamentos**, a coluna **Escriturar na prefeitura** mostra "SIM" nas notas de serviço: dá para filtrar por ela.

**Centro de custo:** toda conta de resultado (classificação começando por **3** ou **4**) precisa de centro de custo. Se faltar, o fato fica **vermelho** (divergente), com o motivo "Conta de resultado sem centro de custo" e a célula destacada na aba **Lançamentos**: corrija no Tasy. **Rateio** (a mesma conta dividida entre vários centros de custo) não é erro: aparece na aba **Rateios**. Se o rateio não somar o valor da nota, o fato já fica vermelho pela conferência do valor e das partidas.

**Centro de custo 539 - CMD:** a despesa do CMD vai na **conta do ativo**, não no centro de custo 539. Lançamento com esse centro de custo deixa o fato **laranja** (conferir), com o motivo "Centro de custo 539 - CMD: trocar pela conta do ativo" e a célula marcada na aba **Lançamentos**: troque no Tasy.

**Software, uniforme e enxoval acima de R$ 1.000,00:** conta de despesa ou receita com uma dessas palavras no nome e valor maior que R$ 1.000,00 no fato deixa o fato **laranja**, com o aviso "Verificar se é possível a diluição do custo ou despesa". Na aba **Lançamentos**, o nome da conta do lançamento fica em destaque (amarelo forte, negrito) com "VERIFICAR A DILUIÇÃO".

**Fornecedores a reclassificar:** lançamento nessa conta deixa o fato **laranja** (conferir), com o aviso conforme o lado:

- **no crédito:** "conferir se precisa trocar para a conta do próprio fornecedor";
- **no débito:** "conferir se foi provisionada".

Na aba **Lançamentos**, o nome da conta do lançamento fica em destaque com "TROCAR PELA CONTA DO FORNECEDOR?" (crédito) ou "FOI PROVISIONADA?" (débito).

**CNPJ da unidade:** o programa lê o CNPJ para quem a nota foi emitida — o **destinatário** na nota de compra (DANFE) e o **tomador** na nota de serviço (DANFSe) — e compara com o da **unidade conferida** escolhida na tela. Se for de outra unidade (ex.: nota do AME Cidade Gama num lote do AME Cidade Alfa) ou de fora da Fundação, o fato fica **vermelho**, com o motivo "CNPJ da nota não é o da unidade conferida" e a frase dizendo para quem a nota veio. Se o programa não conseguir ler o CNPJ no PDF, o fato fica amarelo, para conferir.

| Unidade | CNPJ |
|---|---|
| Fundação Hospital Exemplo | 98.765.432/0001-98 |
| AME Cidade Alfa | 98.765.432/0004-30 |
| AME Cidade Eta | 98.765.432/0007-83 |
| AME Cidade Gama | 98.765.432/0008-64 |
| CMD | 98.765.432/0009-45 |
| AME Vale Zeta / Cidade Zeta | 98.765.432/0010-89 |
| AME Cidade Delta | 98.765.432/0011-60 |
| AME Cidade Beta | 98.765.432/0012-40 |
| AME Cidade Epsilon | 98.765.432/0014-02 |

**"Código" na coluna "Descrição contrib. sociais":** é o tipo de retenção do PIS/COFINS/CSLL que vem na nota de serviço (Nota Técnica nº 007/2026 da NFS-e nacional). A coluna "Contribuições Sociais retidas" é a **soma** do que foi retido dos três, e o programa confere a alíquota pelo código:

| Código | Retidos | Alíquota esperada |
|---|---|---|
| 0 | nenhum | 0% |
| 1 | PIS/COFINS (código antigo; não diz da CSLL) | 3,65% ou 4,65% |
| 2 | PIS/COFINS não retidos (código antigo; não diz da CSLL) | 0% ou 1% |
| 3 | PIS, COFINS e CSLL | 4,65% |
| 4 | PIS e COFINS | 3,65% |
| 5 | só PIS | 0,65% |
| 6 | só COFINS | 3% |
| 7 | COFINS e CSLL | 4% |
| 8 | só CSLL | 1% |
| 9 | PIS e CSLL | 1,65% |

Nota sem código: o programa espera os três (4,65%). A mesma tabela aparece embaixo das notas, na aba **Escriturar na prefeitura**.

**Falar com o fornecedor:** na aba **Escriturar na prefeitura**, cada nota de serviço mostra o regime do prestador (Simples), a atividade (código e descrição), o ISS e os impostos federais retidos (IRRF, Previdência e Contribuições Sociais — PIS/COFINS/CSLL). Quando o prestador é **"Não Optante"** e a nota **não tem nenhum imposto federal retido**, a coluna **Falar com o fornecedor** mostra SIM: essas notas geralmente têm retenção, então pergunte ao fornecedor e anote a resposta em **Retorno do fornecedor**. O ISS não decide (para o Não Optante ele pode ou não ser retido). Isso não muda a cor nem a situação da nota.

### O que fazer com cada cor

| Cor | Situação | O que fazer |
|---|---|---|
| **Verde** | OK | Só conferir as contas contábeis e revisar no Tasy. |
| **Vermelho** | DIVERGENTE | O PDF não bate com o lançamento: a coluna "O que aconteceu" mostra os dois valores (ex.: "Valor: Tasy 29,80 x nota 19,80"), ou a nota veio com o **CNPJ de outra unidade**. Conferir com a nota e corrigir. |
| **Amarelo** | CONFERIR | Casou com o PDF e tudo confere, mas há uma observação (ex.: nome do fornecedor diferente do da nota, nota cancelada). Conferir com a nota impressa. |
| **Amarelo** | SEM PDF | O PDF da nota não veio no download. Conferir com a nota impressa. |
| **Cinza** | SEM Nº DE NOTA | Não é nota fiscal (recibo, doação, taxa): conferir com o documento. |
| **Roxo** | CONFERIR RETENÇÃO | Nota de serviço em que a retenção da nota não bate com o lançamento: falta o crédito do imposto, o valor é diferente, ou há crédito na conta do imposto sem a retenção estar na nota. A observação diz qual imposto, a conta e os dois valores. Contas: IRRF 20776 (ou 20775 se o prestador tem CPF), INSS 20769, PIS/COFINS/CSLL 25206, ISS retido 21996. Também fica roxo quando a **alíquota** da retenção na nota não é a esperada sobre o valor do serviço: IRRF 1,5%, INSS 11% ou 20%, PIS/COFINS/CSLL 4,65% (aceita 1 centavo de arredondamento; o IRRF de prestador com CPF não é conferido). Para o PIS/COFINS/CSLL, vale o **código** da nota (veja abaixo). A observação mostra a alíquota da nota e o valor esperado. |
| **Azul** | ESTORNO | O mesmo lançamento aparece lançado e estornado (débito e crédito invertidos): um anula o outro. Verificar e apagar esses lançamentos no Tasy. A observação diz qual fato vale. |

---

## Como o programa confere

- **Casamento:** cada fato é ligado ao PDF pelo **número da nota**. Como fornecedores diferentes repetem números, o nome do fornecedor (parecido) confirma. Se o nome for muito diferente (ex.: "Omega Exemplo do Brasil" no Tasy e "OXB BR" na nota), o fato só casa se o valor também bater, e fica amarelo para conferir.
- **Valor:** valor total da nota (DANFE) ou valor do serviço (DANFSe) = soma dos débitos. Em nota de serviço com retenção, o valor da nota é o bruto; as retenções e o líquido ficam nos créditos.
- **Desconto lançado à parte:** se o desconto veio num lançamento próprio, a crédito numa conta de **desconto**, o valor da nota é comparado com os débitos menos esse desconto, e o fato continua verde.
- **Cada PDF casa com um fato só.** Se a mesma nota aparecer em dois fatos, o segundo fica "SEM PDF" dizendo em qual fato a nota já foi usada.

---

## Gabarito de contas (aba "Gabarito de contas")

O programa aprende com os lançamentos **já revisados** quais contas cada fornecedor e produto costumam usar, e na conferência avisa quando uma conta foge do habitual. **É só aviso: a cor da nota não muda.**

**Ensinar (a primeira vez e depois, de tempos em tempos):**

1. Exporte do Tasy o **Movimento contábil** dos dias **já revisados** (um arquivo por dia, como sai do Tasy). Não é preciso juntar os arquivos.
2. Na aba **Gabarito de contas**, escolha a **pasta do gabarito** (a subpasta junto do programa, na rede: todos usam a mesma) e os arquivos (pode selecionar vários de uma vez).
3. Clique em **Ensinar**. Ensinar o mesmo dia de novo não conta em dobro.

Só ensine lançamentos **já revisados e corrigidos**: o programa aprende o que estiver no arquivo, inclusive um erro.

**A planilha `Gabarito_contas.xlsx`:**

| Aba | Quem preenche | Para que serve |
|---|---|---|
| **Padrão** | a chefia | a conta oficial de cada fornecedor (código da conta do fornecedor) + produto. Produto em branco = vale para todos os produtos do fornecedor. O Padrão vale mais que o histórico. |
| **Histórico** | o programa | tudo o que foi aprendido: fornecedor, produto, conta, quantas vezes, primeira e última vez. |
| **Para padronizar** | o programa | fornecedor + produto lançado em mais de uma conta, com o % de cada uma e a mais usada. Use o filtro para levar à chefia; para padronizar, copie a conta escolhida para a aba Padrão (não apague linhas do Histórico: elas voltariam ao ensinar de novo). |
| **Fatos aprendidos** | o programa | controle para não contar em dobro. |

- Para só a chefia mudar o Padrão: no Excel, na aba **Padrão**, use **Revisão → Proteger Planilha** com senha. O programa continua funcionando. **Não** use "Criptografar com senha" (senha para abrir o arquivo): aí o programa não consegue ler.
- Antes de gravar, o programa guarda uma cópia em `copias_de_seguranca\` (as 20 últimas).
- Se a planilha estiver aberta no Excel na hora de ensinar, o programa avisa: feche e ensine de novo.

**Na conferência**, a aba **Contas a conferir** do relatório lista os lançamentos **fora do padrão** (laranja), **diferentes do habitual** (amarelo) e **sem histórico** (cinza: produto ou fornecedor novo), com o que o gabarito diz. A aba **Lançamentos** tem a coluna **Gabarito de contas** em cada débito.

---

## Se algo der errado

| Situação | O que fazer |
|---|---|
| "Não é o lote esperado: Colunas não encontradas..." | O .csv não é a exportação do movimento tipo Notas Fiscais, ou o Tasy mudou o nome de uma coluna. Exporte de novo; se continuar, avise quem cuida do programa. |
| PDF em "Erros de leitura" | O PDF está estragado, é escaneado ou é de outro modelo. Confira essa nota à mão. |
| XML em "Erros de leitura" | O XML está incompleto, não é o autorizado (sem o protocolo da Sefaz) ou é de um evento (cancelamento, carta de correção). Baixe de novo o XML da nota; se houver o PDF, a nota é conferida por ele. |
| "Não foi possível gravar o relatório" | A pasta de saída não existe ou não pode ser gravada. Escolha outra pasta. |
| Muitas notas "SEM PDF" | Confira se os PDFs foram baixados pela **data de atualização no estoque**. |
