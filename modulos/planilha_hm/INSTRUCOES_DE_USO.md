# Planilha HM — instruções de uso

## O que o módulo faz (e o que não faz)

**Faz:** preenche a **Planilha HM** do mês (o relatório mensal de honorários médicos que vai para a Controladoria) a partir de dois relatórios do Tasy:

- a aba **Senior MM AAAA** do mês, com uma linha por centro de custo de cada evento do **Eventos**;
- na aba do ano ("2026"), as linhas que faltam: **centro de custo novo** num evento que já existe, **evento novo** (no fim da seção certa, já somado no total da seção) e **seção nova**, quando for o caso. As fórmulas abaixo das linhas inseridas são corrigidas;
- a linha **LOTE REPASSE** do mês, com o total do **Movimento** (a linha de baixo, a diferença, tem que dar zero).

No fim, confere o **TOTAL GERAL** do mês com o Movimento e grava um relatório de conferência.

**Não faz:**

- não altera a planilha escolhida, o Eventos nem o Movimento: grava uma **cópia** na pasta de saída;
- não confere o balancete: isso é o módulo **Honorários Médicos**;
- não decide sozinho a seção de um evento novo cuja conta ele não conhece: pergunta na tela.

---

## Passo a passo

### 1. Os arquivos

- **Eventos** do mês: o relatório "Conferência Lançamentos Contábeis" do Tasy, no `.XLS` que o Tasy gera (não precisa abrir nem salvar no Excel).
- **Movimento** do lote de Repasse a terceiros: o `.csv` que o Tasy exporta.
- **Planilha HM do mês anterior** em **`.xlsx`** (ex.: a de agosto pronta, para preencher setembro). Ela precisa ter a aba do ano e a aba "Senior" do mês.

### 2. Aba "Preenchimento"

| Cartão | O que escolher | O que a tela confirma |
|---|---|---|
| **Eventos do mês** | o `.XLS` do Tasy | a competência, o número de eventos e o total (ex.: "Eventos · set/2026 · 136 eventos · R$ 5.794.120,73") |
| **Movimento** | o `.csv` do Tasy | o mês, o lote e o total (ex.: "Movimento · set/2026 · lote 72959 · R$ 5.794.120,73") |
| **Planilha HM do mês anterior** | a planilha `.xlsx` | a aba do ano e a última competência preenchida (ex.: "última competência preenchida: ago/2026") |
| **Pasta de saída** | onde gravar a cópia e a conferência | vem sugerida com a pasta da planilha e fica lembrada para o mês seguinte |

O botão **Preencher planilha** só acende quando o Eventos e o Movimento são **do mesmo mês** e a planilha é do mesmo ano. Se não forem, o cartão fica vermelho e diz o porquê.

### 3. As perguntas

Antes de gravar, a tela pode perguntar:

- **A aba Senior do mês já tem dados** (ex.: você já preencheu esse mês): substituir? Se responder Não, nada é gravado.
- **A cópia já existe** na pasta de saída (mesmo nome, mesmo dia): substituir?
- **Em qual seção entra um evento novo**, quando a conta dele no Movimento ainda não está na tabela conta → seção (veja abaixo). A janela mostra o evento, a conta e a lista das seções da planilha; a última opção é **"Criar seção nova"**, com o nome da conta (ex.: "HM CATARATA - AGLUTINADA PJ"). A seção nova entra logo antes do TOTAL GERAL. Se cancelar, nada é gravado.

### 4. O resultado

A tela mostra:

- **TOTAL GERAL × Movimento**: diferença em **verde** quando é zero, em **vermelho** quando não fecha;
- o TOTAL GERAL do mês, o total do Movimento, o LOTE REPASSE gravado e quantas linhas a aba Senior ganhou;
- os eventos que ficaram **fora da planilha** (ex.: evento cujo total não bate com a soma dos centros de custo);
- a lista das **linhas criadas** na aba do ano (linha, o quê, evento, centro de custo e seção).

Botões: **Abrir planilha**, **Abrir conferência** e **Abrir pasta**.

O que sai na pasta de saída:

- **`MM Planilha HM AAAA Atualizada em DD-MM-AAAA COMPETENCIA MM.xlsx`**: a cópia preenchida (DD-MM-AAAA = o dia em que você preencheu). Os totais aparecem ao abrir no Excel (o Excel recalcula sozinho).
- **`Conferencia_PlanilhaHM_<AAAA-MM>_<data e hora>.xlsx`**: a conferência, com as abas **Resumo**, **Eventos** (cada evento: total, centros de custo, seção, valor no Movimento e situação), **Linhas criadas** (o que foi acrescentado e por quê), **Movimento sem evento** (só quando o TOTAL GERAL não fecha: as linhas do Movimento para conferir à mão) e **Avisos**. Rodar de novo nunca apaga uma conferência anterior.

---

## A tabela conta → seção (`secoes_contas.csv`)

Cada seção da aba do ano corresponde a uma conta contábil (ex.: a seção de fixos recebe as contas "Fixos PJ" e "Fixos PF"). O programa usa uma tabela para saber em que seção entra um evento novo:

- **Na primeira vez**, ele monta a tabela sozinho, olhando no Movimento a conta dos eventos que já estão em cada seção.
- **Nos meses seguintes**, usa a tabela. Conta nova, que não está na tabela: a tela pergunta e grava a resposta.
- A tabela fica na pasta **`config`, ao lado da Planilha HM** escolhida (o programa cria a pasta se ela não existir). É um arquivo de texto separado por `;`, que você pode abrir no Excel e corrigir.

| Coluna | O que vai nela |
|---|---|
| `Classificacao` | a classificação da conta (ex.: `3.01.01.06.03.0002`) |
| `Conta` | o nome da conta, como vem no Movimento |
| `Secao` | o nome da seção na aba do ano, exatamente como está na planilha |

---

## O que a cópia não leva

A cópia é gravada sem o Excel, e por isso alguns enfeites da planilha não vão junto. A conferência avisa quando a planilha escolhida tem algum deles:

- **desenhos** (ex.: as setas abaixo da diferença do LOTE REPASSE);
- as marcas de **"ignorar erro"** (sem elas, alguns triângulos verdes voltam a aparecer nas células).

Os valores e as fórmulas não mudam. Se quiser os desenhos, copie da planilha anterior para a cópia.

---

## Problemas comuns

| Mensagem | O que fazer |
|---|---|
| "o Movimento é de ... e o Eventos, de ..." | escolha o Eventos e o Movimento do mesmo mês. |
| "a planilha é de 2026 e o Eventos, de 2027" | no começo do ano, crie a planilha do ano novo (com a aba do ano e as abas Senior) e escolha ela. |
| "falta a aba Senior MM AAAA" | crie a aba Senior do mês na planilha (copiando a de outro mês) e escolha de novo. |
| "evento(s) com erro ficam fora da planilha" | o total do evento no Eventos não bate com a soma dos centros de custo: confira no Tasy. Ele aparece na conferência e não entra na cópia. |
| Diferença no TOTAL GERAL × Movimento | abra a conferência: a aba **Eventos** mostra o valor de cada evento no Movimento e a aba **Movimento sem evento** lista as linhas para conferir à mão. |
| O nome do evento novo veio sem acento | o nome vem do Tasy exatamente como está lá. Corrija à mão na cópia, se quiser. |
| Um evento novo caiu na seção errada | corrija a seção da conta no `secoes_contas.csv` (pasta `config`) e preencha de novo. |
