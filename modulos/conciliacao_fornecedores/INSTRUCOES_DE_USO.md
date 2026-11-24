# Fornecedores — instruções de uso

## Antes de tudo: como tirar o relatório do financeiro no Tasy

O programa só lê corretamente o **Relatório de Títulos a Pagar** tirado exatamente assim:

| Onde | O que marcar |
|---|---|
| **Configurações** | **Excel** (o Excel normal, **não** o "Excel do PDF") |
| **Tipo de relatório** | **Analítico** |
| **Dimensões → Situação** | **Diferente de**: Cancelado |
| **Dimensões → Tipo título** | **Igual a**: Bloqueto, Cupom fiscal, Diversos, Nota Fiscal e Recibo de Pagamento |
| **Quebras → Selecionados** | Fornecedor |
| **Campos → Selecionados** | todos estes 12: Pessoa física/jurídica, Nr doc, Nr título, Tipo título, Sit, Dt emissão, Dt Vencto, Dt liquid, Vl juros, Vl multa, Classif e Vl saldo |

Os 12 campos são **todos necessários**: sem algum deles, o programa não consegue analisar o relatório direito.

---

## O que o módulo faz (e o que não faz)

**Faz:** confere, fornecedor a fornecedor, se o **saldo na conta 2111 – Fornecedores no País do balancete** é igual ao **saldo no relatório de títulos a pagar** do Tasy. Serve para qualquer AME e para a Hospital Exemplo. Quando um fornecedor tem diferença, a planilha mostra os **títulos** dele (Nr. Doc. e Nr. Título) para você procurar no Tasy.

**Não faz:**

- não altera os relatórios que você escolhe nem nada no Tasy: só lê e grava uma planilha nova;
- não confere o mês do relatório de títulos (ele não traz o mês): confira você;
- não usa a coluna **Observação** do Tasy (nunca é lida).

---

## Os relatórios do Tasy (do jeito que saem, .xls)

| Relatório no Tasy | Observação |
|---|---|
| **Balancete** (865) | Precisa ter a conta 2111 – Fornecedores no País |
| **Relatório de títulos a pagar – analítico** | Uma linha por título (colunas Pessoa Física/Jurídica, Nr. Doc., Nr. Título, Vl. Saldo...) |

- Os dois da **mesma unidade** e do **mesmo mês**. Unidades diferentes: o programa não deixa gerar.
- **Não precisa abrir nem salvar no Excel:** baixe do Tasy e escolha o arquivo direto. Pode renomear à vontade. (Se alguém abriu e salvou como `.xlsx`, também funciona.)
- O relatório **sintético** ("Sintético por Fornecedor") não é mais usado: se escolhido, o programa avisa.

---

## Passo a passo

1. No menu, em **CONCILIAÇÕES · PASSIVO**, clique em **Fornecedores**.
2. Em **Balancete (865) – conta 2111 Fornecedores**, clique em **Selecionar** e escolha o balancete. Confirmação, ex.: *"AME - Cidade Delta · set/2026 · 25 contas · R$ 181.279,11"*.
3. Em **Títulos a pagar – Analítico**, escolha o relatório. Confirmação, ex.: *"AME - Cidade Delta · 33 títulos · 28 fornecedores · R$ 149.479,96"*. Se os dois forem de unidades diferentes, a linha fica vermelha e o botão não acende.
4. (Opcional) Em **Pasta para salvar a planilha**, escolha onde salvar. O programa lembra essa pasta nas próximas vezes. Sem escolher, a planilha vai para a pasta do balancete. Para voltar a esse padrão, clique em **Limpar** no cartão da pasta.
5. Clique em **Gerar relatório**. Depois use **Abrir planilha** para ver o resultado.

A planilha se chama `Conciliacao_Fornecedores_<unidade>_<mês>.xlsx` (ex.: `Conciliacao_Fornecedores_CidadeDelta_set2026.xlsx`). Se já existir uma com o mesmo nome, a nova ganha `_2`, `_3`... e nenhuma é apagada.

**Escolheu um arquivo errado?** **Limpar**, embaixo do "Trocar" de cada cartão, tira só aquele arquivo; **Limpar tudo**, ao lado de "Gerar relatório", recomeça do zero (a pasta escolhida fica).

---

## Como o programa casa os fornecedores

O saldo de cada fornecedor no financeiro é a **soma dos seus títulos**. Fornecedores com **saldo zero** (ex.: boletos de R$ 0,00 do banco) ficam fora, e uma nota no Resumo diz quais foram.

O relatório financeiro não traz o código da conta, então o programa casa **pelo nome**, mesmo escrito de jeitos diferentes (ex.: "Verano Com. Informática Ltda Epp" × "Veranno Comercio e Informatica Ltda - EPP"):

1. As contas **"Fornecedores a reclassificar"** nunca são casadas (aparecem como Só no Balancete).
2. Nomes parecidos são casados, do mais parecido para o menos.
3. Se o mesmo fornecedor tem **dois cadastros** no financeiro, os saldos são **somados** (aparece "Nome 1 + Nome 2" e uma nota no Resumo). Filiais com o mesmo nome e **CNPJ diferente** ficam separadas.
4. Nomes bem diferentes, mas com **o mesmo valor**, são casados com uma nota pedindo para **confirmar**.
5. O que sobra fica como **Só no Balancete** ou **Só no Relatório**.

A coluna **Confiança do Pareamento** (0 a 1) mostra o quanto os nomes se parecem: **audite os de confiança baixa**.

---

## O resultado

Na tela: **Fornecedores OK**, **Divergentes ou sem par** e **Linhas na conciliação**; os totais do balancete e dos títulos e a diferença; a lista do que não bateu (os primeiros 12; o resto está na planilha); e quantos avisos houve (**Ver avisos** mostra a lista).

| Situação | O que quer dizer |
|---|---|
| **OK** | Mesmo saldo nos dois relatórios |
| **DIVERGENTE** | Casados, mas com saldos diferentes |
| **SÓ NO BALANCETE** | Conta sem fornecedor correspondente no financeiro (inclui as "a reclassificar") |
| **SÓ NO RELATÓRIO** | Fornecedor do financeiro sem conta no balancete |

Abas da planilha:

- **Resumo:** totais, diferença, contagens (fórmulas do Excel), a lista do que não bateu e as notas.
- **Conciliação Completa:** todos os fornecedores, na ordem do balancete, com a diferença (fórmula) e o TOTAL.
- **Títulos das diferenças:** os títulos de cada fornecedor DIVERGENTE ou SÓ NO RELATÓRIO, um por linha, com o **Nr. Doc. (coluna B)** e o **Nr. Título (coluna C)**, tipo, emissão, vencimento e saldo. Use esses números para achar a diferença no Tasy. (Contas só no balancete não têm títulos no financeiro.)

---

## Se algo der errado

| Aviso | O que fazer |
|---|---|
| "Os arquivos são de unidades diferentes" | Escolha o balancete e os títulos da mesma unidade |
| "Este é o relatório de títulos a pagar "Sintético por Fornecedor"…" | Tire o relatório **analítico** de títulos a pagar |
| "ATENÇÃO: … mais de um estabelecimento" | O relatório de títulos saiu com mais de uma unidade: tire de novo só com a unidade certa |
| "ATENÇÃO: a soma … não bate com o total …" / "a prova final não fechou" | O programa pode não ter lido tudo. Não confie nessa planilha e avise quem faz a manutenção |
| Arquivo escolhido no campo errado | A mensagem diz em qual campo colocar |
