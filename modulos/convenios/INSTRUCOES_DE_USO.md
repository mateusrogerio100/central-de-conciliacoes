# Convênios — instruções de uso

## O que o módulo faz (e o que não faz)

**Faz:** lê o **Razão Convênios** do mês (contas de receita de convênios do Tasy, grupo 4.01.05.01), soma os lançamentos **por convênio** (o nome está no histórico) e grava uma **cópia** da planilha **RECEITAS DE CONVÊNIOS** com a coluna do mês preenchida, a linha **Saldo Contábil** (o total do razão) e uma linha nova para cada convênio que ainda não existia.

**Não faz:**

- não altera a planilha escolhida nem o razão: grava uma cópia na pasta de saída;
- não decide sozinho o que ele não reconhece: o que fica de fora vai para **"Não identificado"**, com aviso, para você preencher à mão (ex.: o IAMSPE, enquanto não há a regra para separar SC de HC).

---

## Passo a passo

### 1. Os arquivos

- **Razão Convênios** do mês, exportado do Tasy. Serve o `.xls` que o Tasy gera (não precisa abrir e salvar no Excel) ou o `.xlsx`.
- **Planilha RECEITAS DE CONVÊNIOS** em **`.xlsx`**. Se ela ainda estiver em `.xls`, abra no Excel e use **Salvar como > Pasta de Trabalho do Excel (.xlsx)** uma vez. A planilha precisa ter a aba do ano do razão ("Receita de Convênios 2026").
- **Pasta das equivalências**: a pasta `config` com o `equivalencias.csv` (veja abaixo). Se ela estiver ao lado da planilha, entra sozinha.

### 2. Aba "Preenchimento"

| Cartão | O que escolher | O que a tela confirma |
|---|---|---|
| **Razão Convênios do mês** | o razão do Tasy | o mês, o número de contas e o total (ex.: "Mês 09/2026 · 4 conta(s) · R$ 3.135.190,13") |
| **Planilha RECEITAS DE CONVÊNIOS** | a planilha `.xlsx` | a aba do ano, o número de convênios e se o mês está vazio ou já preenchido |
| **Pasta das equivalências** | a pasta `config` | quantas equivalências o `equivalencias.csv` tem |
| **Pasta de saída** | onde gravar a cópia e o relatório | |

A planilha, a pasta das equivalências e a pasta de saída ficam lembradas para o mês seguinte. Clique em **Preencher**.

**Mês já preenchido:** a tela pergunta se você quer substituir. Na substituição, as linhas que **não têm lançamento no razão mantêm o valor** que já tinham (ex.: o que foi digitado à mão) e aparecem como "mantida" no relatório.

### 3. O resultado

A tela mostra quantos convênios foram preenchidos, as linhas novas, os lançamentos não identificados e a conferência **TOTAL RECEITAS × Saldo Contábil**. Diferença diferente de zero fica em vermelho: normalmente é o valor não identificado, que você preenche à mão na cópia.

O que sai na pasta de saída:

- **`RECEITAS DE CONVÊNIOS <MMAAAA>.xlsx`**: a cópia preenchida (o mês do razão no nome). Se já existir um arquivo com esse nome, a cópia sai com `_2`, `_3`...: nada é substituído.
- **`Conferencia_Convenios_<AAAA-MM>_<data e hora>.xlsx`**: o relatório, com as abas **Resumo**, **Por convênio** (valor anterior e novo de cada linha e os nomes do razão que caíram nela), **Lançamentos** (todos os lançamentos do razão, com a linha em que cada um entrou) e **Avisos**.

Botões: **Abrir planilha**, **Abrir relatório** e **Abrir pasta**.

---

## Como o programa acha a linha de cada convênio

1. O nome sai do histórico: `Faturamento Mês NF 299141 PM de Cidade Teta Set/2026 ...` ou `Referente Fundação do ABC NF. 89592 ...`.
2. O nome é comparado com a coluna CONVÊNIO da planilha **sem acento, sem maiúsculas, sem pontuação e sem "de/da/do"** ("PM de Cidade Teta" = "PM Cidade Teta").
3. O que não bate assim vem do **`equivalencias.csv`**.
4. Nome que não bate com nada é um **convênio novo**: ganha uma linha na cópia, em ordem alfabética, com aviso para conferir o nome. As fórmulas do TOTAL e do Acumulado já incluem a linha nova.
5. Débito diminui o valor do convênio. Tudo o que cai na mesma linha soma, de todas as contas.

---

## As equivalências (`equivalencias.csv`)

Arquivo de texto separado por `;`, que você edita no Excel ou no Bloco de Notas, sem precisar de uma versão nova da Central. Fica na pasta `config`, ao lado da planilha de receitas.

| Coluna | O que vai nela |
|---|---|
| `Nome_no_razao` | o nome como aparece no histórico do razão (ex.: `PM CIDADE ALFA CONVENIO`) |
| `Linha_da_planilha` | o nome da linha da planilha onde ele entra (ex.: `PM Cidade Alfa`) |
| `Obs` | anotação livre (aparece no relatório) |

- Vários nomes podem ir para a mesma linha: somam juntos.
- `NÃO IDENTIFICADO` em `Linha_da_planilha` manda o valor para "Não identificado", com aviso (usado no IAMSPE).
- Sem o arquivo, o programa avisa em vermelho e os nomes que só casavam por ele viram linhas novas.

---

## Problemas comuns

| Mensagem | O que fazer |
|---|---|
| "é um Excel antigo (.xls 97-2003)" | abra a planilha no Excel e salve como `.xlsx`. |
| "não tem a aba Receita de Convênios <ano>" | crie a aba do ano na planilha (copiando a do ano anterior). |
| "Convênio novo: ... linha acrescentada" | confira o nome. Se ele for de um convênio que já tem linha, acrescente a equivalência no `equivalencias.csv` e preencha de novo. |
| "Não identificado" | preencha à mão na cópia. Se o nome deve sempre ir para uma linha, acrescente a equivalência. |
| "A fórmula do TOTAL RECEITAS do mês não soma todas as linhas" | ajuste a fórmula na cópia para pegar todas as linhas de convênio. |
