# Serviços Tomados — instruções de uso

## O que o módulo faz (e o que não faz)

**Faz:** gera o arquivo **.txt de importação da Declaração de Serviços Tomados** do site da Prefeitura de Cidade Alfa (Contribuinte OnLine), no layout da prefeitura (Versão 3). Ele pode:

- **gerar a partir dos PDFs** das notas tomadas (DANFSe, o PDF padrão da NFS-e nacional);
- **tirar do arquivo as notas que já estão escrituradas** na prefeitura, para o site não recusar a importação por duplicidade;
- **unificar lotes**: juntar as exportações de vários lotes do site (lançados por colegas diferentes, inclusive à mão) num arquivo só, para você excluir os lotes pequenos e importar um único lote.

Sai um arquivo por **CNPJ do tomador + competência** (`tomados_<CNPJ>_<MM-AAAA>.txt`) e um relatório **Relatorio_Tomados_<data e hora>.xlsx** dizendo o que aconteceu com **cada** nota.

**Não faz:**

- não entra no site da prefeitura, não importa e não exclui lotes: isso continua sendo feito por você;
- não trata notas de serviços **prestados** pela Fundação (essas ficam de fora, com o motivo no relatório);
- não altera os PDFs nem as planilhas que você escolhe.

---

## Passo a passo

### 1. Prepare os arquivos

1. Salve numa pasta os **PDFs das notas** do mês (pode ter subpastas).
2. (Opcional, recomendado) No site, exporte o **resultado** das notas já declaradas — de preferência dos últimos meses e de todos os logins — para o programa tirar do arquivo o que já foi escriturado.
3. (Só para unificar) No site, exporte os **lotes** que quer juntar (botão de exportar da lista de itens de serviços tomados).

### 2. Escolha as entradas (aba "Gerar arquivo")

| Campo | O que escolher |
|---|---|
| **PDFs das notas (DANFSe)** | a pasta dos PDFs. Abaixo aparece quantos PDFs foram encontrados. A subpasta `saida` dela é sugerida como pasta de saída. |
| **Exportações de lotes (unificar)** | os `.txt`/`.csv` exportados dos lotes. Abaixo aparece quantas notas foram encontradas. Ao escolher, aparecem os campos **CNPJ do tomador** (a lista traz os já usados) e **Competência (MM/AAAA)**: a exportação do site não traz esses dados, então é preciso informar. |
| **Já escrituradas (opcional)** | um ou mais resultados exportados do site. A nota que aparecer em qualquer um deles fica fora do arquivo como "já escriturada". |
| **Tipo da declaração** | **Normal** ou **Complementar**. Escolha a cada geração (vale para todos os arquivos gerados). |
| **Data de lançamento** | vem com a data de hoje; troque se precisar (DD/MM/AAAA). |
| **Outros CNPJs da Fundação** | só se precisar. Os CNPJs que começam com **98.765.432** (matriz e filiais, como os AMEs de hoje) já são reconhecidos. Se um estabelecimento da Fundação tiver CNPJ de **outra raiz**, clique no botão e informe o CNPJ (um por linha). As notas tomadas por ele passam a entrar, num `.txt` próprio. A lista fica gravada no computador e vale para as próximas gerações; ao lado do botão aparece quantos estão cadastrados. |
| **Pasta de saída** | onde os `.txt` e o relatório serão gravados. |

Dá para usar PDFs e exportações juntos: a nota que vier nos dois entra **uma vez só**, pela versão do PDF.

> **Atenção ao unificar:** não informe em "Já escrituradas" a exportação dos próprios lotes que você vai substituir. Se fizer isso, todas as notas deles aparecem como "já escrituradas" e o arquivo sai vazio. Quando há exportações e resultados escolhidos ao mesmo tempo, a tela lembra disso em laranja.

> Escolheu um arquivo por engano? Clique em **Limpar**, embaixo do botão **Trocar** do cartão: a seleção sai e o cartão volta a ficar vazio.

### 3. Clique em **Gerar arquivo**

Durante a geração a tela pode perguntar:

- **"Não encontrei a cidade deste prestador"**: acontece com prestador que não veio em PDF, não está no cadastro e não foi achado na consulta pública de CNPJ (ou é CPF). Digite a **cidade** e a **UF**; a resposta fica guardada e não será perguntada de novo. Se clicar em **Não sei**, a nota vai para "lançar à mão".
- **"Estes arquivos já existem na pasta de saída e serão substituídos"**: responda **Sim** só se quiser refazer. Se responder **Não**, nada é gravado.

### 4. Confira o resultado

- **Números:** notas no arquivo, notas para **lançar à mão** e notas **não incluídas** (com quantas já estavam escrituradas, quantas canceladas e quantos arquivos deram erro de leitura).
- **Tabela:** um arquivo por tomador e competência, com a quantidade de notas, o total dos serviços e o ISS.
- **Conferências:** devem aparecer em verde. Em laranja, abra o relatório e veja o motivo.
- **Botões:** **Abrir pasta**, **Ver avisos** (abre o relatório) e **Novo** (limpa as escolhas).

### 5. Importe no site

1. Entre no site com o **login do tomador** do arquivo (o relatório mostra o CNPJ e o nome em "Arquivos gerados").
2. Importe o `.txt`. Os totais que o site mostrar devem bater com os da tabela.
3. **Corrija os números longos:** as notas da aba **Corrigir número no site** entraram com os **8 últimos dígitos** do número (ex.: a 2026000000090 entrou como 90), porque o arquivo da prefeitura só aceita 8. Depois de importar, abra cada uma no site e troque **só o número** pelo da coluna "Número correto". A tela também avisa, em laranja, quantas são.
4. Digite no site as notas da aba **Lançar à mão** do relatório: ela traz todos os campos na ordem da tela do site.
5. **Ao unificar lotes:** depois de importar o lote unificado, exclua os lotes antigos (entre no lote, selecione todas as notas, exclua; depois exclua o lote). As notas de número longo que estavam nos lotes antigos entram no lote unificado com os 8 últimos dígitos: corrija o número delas como no passo 3.

---

## Falar com o fornecedor (Não Optante sem imposto federal retido)

A aba **Falar com o fornecedor** do relatório lista as notas de prestador **"Não Optante"** do Simples que **não têm nenhum imposto federal retido** (IRRF, Previdência e Contribuições Sociais — PIS/COFINS/CSLL — todos em branco). Essas notas geralmente têm retenção: pergunte ao fornecedor e anote a resposta na coluna **Retorno do fornecedor**.

- O **ISS não decide**: para o Não Optante ele pode ou não ser retido. Ele aparece só como informação.
- A coluna **Atividade** traz o código e a descrição (ex.: 04.01.01 - Medicina.): use-a para filtrar, porque a retenção depende da atividade.
- Entram só as notas que a Fundação **tomou** (incluídas, lançar à mão e já escrituradas), lidas do **PDF**: a exportação do site não traz os impostos federais.
- Na aba **Notas**, todas as notas mostram os impostos federais lidos, e a coluna **Falar com o fornecedor** marca SIM nas da lista.
- Isso não muda nada no arquivo `.txt`.

---

## Por que uma nota ficou fora do arquivo

Cada nota aparece na aba **Notas** do relatório com um destino e o motivo:

| Destino | Quando acontece |
|---|---|
| **INCLUÍDA** | entrou no arquivo `.txt` indicado na última coluna. |
| **JÁ ESCRITURADA** | a nota (mesmo número **e** mesmo prestador) está num dos resultados informados. Nota de número longo (ex.: 2026000003076) também conta como já escriturada se alguém a digitou no site com o número curto (3076), do mesmo prestador e com o mesmo valor: o motivo diz "digitada como 3076". |
| **LANÇAR À MÃO** | não cabe no arquivo: nota no **modelo da Prefeitura de São Paulo** (não traz competência, Simples nem retenção do ISS: confira no PDF; se baixar a DANFSe nacional da mesma nota e colocar na pasta, vale a DANFSe), nota **emitida num mês diferente da competência** (ex.: emitida em 02/10 com competência 09 — o site recusa o arquivo inteiro: "data emissao não esta dentro da referencia"), desconto incondicionado, tributação que não é "Operação Tributável", imposto retido diferente de SIM/NÃO na exportação, cidade do prestador não encontrada, ISS devido numa cidade diferente da cidade do prestador e **não retido** (o site recusa o imposto retido nesse caso; a retida entra no arquivo), ou número longo cujos 8 últimos dígitos repetiriam uma nota do mesmo prestador (no site ou no arquivo). Digite no site pela aba "Lançar à mão". |
| **NÃO INCLUÍDA** | nota cancelada ou substituída, nota em que o prestador é a própria Fundação (serviço prestado), em que o tomador não é a Fundação ou não é identificado (ex.: a Fundação aparece só como intermediária), ou nota sem valor de serviço (R$ 0,00). |
| **DUPLICADA** | o mesmo PDF duas vezes na pasta, ou a mesma nota em duas exportações (ou em PDF e exportação): entra uma vez só. |
| **ERRO DE LEITURA** | o PDF não é uma DANFSe (escaneado, modelo de outra prefeitura), está estragado ou falta um campo. |

Se uma nota se encaixa em mais de um motivo, vale o primeiro da ordem: duplicada, situação (cancelada/substituída), não incluída, **já escriturada**, lançar à mão. Assim uma nota já digitada no site nunca volta para a lista de digitação.

---

## Como os códigos do arquivo são escolhidos

| Campo do site | Como o programa decide |
|---|---|
| **Local do serviço (CFPS)** | pelo "Local da Prestação" da nota: Cidade Alfa = "Serviço prestado no município de Cidade Alfa"; outra cidade = "fora do município". Nas exportações, vale o que veio do site. |
| **Imposto retido** | retido ou não, pela nota; e se o ISS é devido em Cidade Alfa, pelo município de incidência da nota (sem ele, pela cidade do prestador). Para ISS devido **fora** de Cidade Alfa, o site só aceita as opções "SIM/NÃO (devido FORA do município)". |
| **Enquadramento** | pelo campo "Simples Nacional na Data de Competência" da nota: Não Optante = Não; Optante = SINAC; MEI = MEI. Nas exportações, vale o que veio do site. |
| **Cidade do prestador** | pelo PDF; senão, pelo cadastro de prestadores; senão, pela consulta pública de CNPJ na internet; senão, a tela pergunta. |

**ISS zerado na nota:** alguns optantes do Simples emitem a nota com alíquota mas com "ISSQN Apurado" zerado. O site recalcula serviço × alíquota e recusa imposto zero, então o arquivo leva o **ISS calculado**, e a aba **Avisos** lista cada caso ("ISS da nota zerado: usado o calculado").

**Alíquota em branco na nota:** o contrário também acontece — a nota traz o ISS mas não a alíquota. O arquivo leva a **alíquota calculada** (ISS ÷ serviço, ex.: R$ 0,94 ÷ R$ 29,00 = 3,24%), mantendo o ISS da nota, e a aba **Avisos** lista o caso ("Alíquota em branco: calculada").

O relatório avisa (aba **Avisos**) quando o município de incidência é diferente da cidade do prestador (se a nota não for retida, ela vai para **lançar à mão**) e de onde veio a cidade de cada prestador novo. A aba **Divergências** mostra quando o ISS da nota não bate com a **base de cálculo (BC ISSQN)** × alíquota — a base já vem sem o desconto incondicionado, e aparece nas abas Notas e Lançar à mão. As diferenças entre um PDF e a exportação da mesma nota ficam na aba **Divergências**.

---

## Dúvidas frequentes

**O site recusou o arquivo dizendo que uma nota "já foi declarada".** Alguma nota já estava escriturada e não apareceu nos resultados informados. Exporte o resultado mais recente do site (de todos os logins) e gere de novo com ele.

**Quais resultados informar?** Todos os que você tiver: de **todos os logins** e dos **últimos meses** (a prefeitura declara pela competência, e uma nota pode ter sido declarada em outro mês). Em agosto/2026, duas exportações do mesmo mês tinham 157 notas diferentes entre si: usando só uma delas, 145 notas já declaradas voltariam para o arquivo e o site recusaria a importação.

**Uma nota da competência anterior apareceu num arquivo separado.** Está certo: a prefeitura declara pela **competência** da nota, não pela data de emissão. Importe cada arquivo na competência do nome dele.

**Onde fica o cadastro de cidades dos prestadores?** No seu usuário do Windows, em `%APPDATA%\CentralConciliacoes\escrituracao_tomados\prestadores.json`. Ele é preenchido sozinho; não é preciso mexer.
