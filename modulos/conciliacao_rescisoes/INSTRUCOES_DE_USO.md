# Rescisões — instruções de uso

## O que o módulo faz (e o que não faz)

**Faz:** confere os **pagamentos de rescisão** do mês (razão da conta Rescisões a pagar) contra as rescisões calculadas na folha e as que já estavam pendentes, e monta a **lista nova de Rescisões a pagar**. Serve para a Hospital Exemplo e para os AMEs.

**Não faz:** não altera os arquivos que você escolhe nem nada no Tasy ou na folha: só lê e cria uma planilha nova.

---

## Os arquivos

| Arquivo | Observação |
|---|---|
| **Razão** da conta Rescisões a pagar (Tasy) | Do jeito que sai do Tasy (.xls); .xlsx também vale |
| **Eventos da folha** (um ou mais) | O de **Cálculo Mensal** e, se houver, os de **Complementar Rescisão**. Só o item **0264 – Líquido Rescisão** é usado. Se o PDF der problema, use o **mesmo relatório exportado em Excel (.xlsx)**: o programa lê do mesmo jeito |
| **Rescisões a pagar** do mês anterior | A planilha de controle (aba "Rescisões a pagar") ou a planilha que o programa gerou no mês anterior |
| **Títulos a pagar do financeiro** (opcional) | O relatório analítico de títulos a pagar do Tasy (o mesmo do módulo Fornecedores), filtrado nos títulos de rescisão. A lista nova é comparada com ele, pessoa a pessoa |

---

## Passo a passo

1. No menu, em **CONCILIAÇÕES · PASSIVO**, clique em **Rescisões**.
2. Escolha o **razão**. Confirmação, ex.: *"Fundação Hospital Exemplo… · jun/2026 · 92 pagamentos · saldo final R$ 132.082,98"*.
3. Escolha os **eventos da folha** — um ou **vários de uma vez** (segure **Ctrl** ao clicar): o mensal e os complementares. No lugar de um PDF, pode ser o mesmo relatório em **Excel (.xlsx)**; aí a origem aparece como "Excel mensal" em vez de "PDF mensal".
   - Com um PDF, ex.: *"0264 · jun/2026 · 85 pessoas · R$ 222.394,99"*.
   - Com vários, depois de escolher também o razão e a lista, a confirmação diz quais entram no mês, ex.: *"entram no mês: PDF mensal + PDF complementar 29/06 (= créditos do razão R$ 222.585,59); fora (provavelmente do mês seguinte): PDF complementar 15/07"*. O mesmo PDF escolhido duas vezes: a cópia é ignorada.
4. Escolha a **lista do mês anterior**. Confirmação, ex.: *"aba "Rescisões a pagar" · 139 rescisões · R$ 104.350,71"*. Se o mês do razão e o do PDF não baterem, ou se o saldo anterior não bater com a lista, o cartão mostra **atenção**.
5. (Opcional) Escolha os **títulos a pagar do financeiro**. Confirmação, ex.: *"98 títulos · 90 pessoas · R$ 53.836,22"*.
6. (Opcional) Em **Pasta para salvar a planilha**, escolha onde salvar. O programa lembra a pasta nas próximas vezes; sem escolher, a planilha vai para a pasta do razão. **Limpar**, no cartão, volta a esse padrão.
7. Clique em **Gerar relatório** e depois em **Abrir planilha**.

A planilha se chama `Conciliacao_Rescisoes_<unidade>_<mês>.xlsx` (ex.: `Conciliacao_Rescisoes_HospitalExemplo_jun2026.xlsx`).

**Escolheu um arquivo no campo errado?** A mensagem diz em qual campo colocar, e o botão não acende enquanto houver um cartão em vermelho. **Limpar** tira só aquele arquivo; **Limpar tudo** recomeça (a pasta escolhida fica).

---

## Como o programa confere

**Quais PDFs entram no mês.** Um complementar pode ser do mês seguinte (calculado no mês, mas não lançado no razão). Por isso o programa procura a **combinação de PDFs cuja soma do 0264 é igual aos créditos do razão** (tolerância de R$ 0,01):

- **Uma combinação bate:** só esses PDFs são usados; os outros aparecem no Resumo como *"PDFs não lançados no razão deste mês (provavelmente do mês seguinte)"* e **não entram** no casamento nem na lista nova.
- **Nenhuma bate:** o programa olha **cada lançamento de crédito** do razão e procura o PDF (ou os PDFs juntos) com a mesma soma. Isso acontece quando o razão tem um crédito que não vem de PDF (ex.: um reembolso lançado à mão): o aviso diz qual é, e ele aparece na composição da diferença.
- **Nenhum PDF casa, ou mais de uma combinação bate:** todos os PDFs são usados, e o Resumo mostra a diferença créditos − PDFs, com um aviso.

**Cada pagamento** do razão é procurado **nos PDFs usados (0264) e na lista do mês anterior**, ao mesmo tempo:

- se em algum dos dois houver uma rescisão com o **valor igual ao pago** (até R$ 0,01 de diferença), é ela que fica — e, se houver nos dois, a da **lista anterior** (a mais antiga). Ex.: a pessoa está na lista de maio com R$ 3.500,00 e no PDF de junho com R$ 700,00 (novo cálculo, ainda não pago); o pagamento foi de R$ 3.500,00 → baixa a de maio, e a de junho vai para a lista nova;
- se o valor não for igual em nenhum, fica a do **PDF** (ou, sem PDF, a da lista anterior), e a diferença vai para a aba **Valores diferentes**.

Cada rescisão só pode ser baixada uma vez. Um nome **idêntico** sempre ganha de um apenas parecido. Nomes escritos de jeitos diferentes ("Barretto" × "Barreto", sobrenome a mais, letra no lugar do nome) são casados por semelhança; a coluna **Confiança do nome** mostra quanto se parecem (1 = idênticos).

- Achou, com o mesmo valor: a rescisão está paga e sai da lista.
- Achou, com **valor diferente**: vai para **Valores diferentes**. **Pago a menor:** o que faltou **continua na lista nova** (origem *"PDF mensal – restante (pago R$ 112,03 em 15/07/2026)"*). **Pago a maior:** a rescisão sai da lista e a diferença vai para a composição da diferença.
- **Não achou:** vai para **Não encontrados**.
- As rescisões que **não tiveram pagamento** formam a lista nova.

**Lista nova × financeiro** (se escolheu o relatório do financeiro): o programa **soma por pessoa** dos dois lados e junta as pessoas pelo nome, com a mesma regra do módulo Fornecedores (aceita nomes escritos de jeitos diferentes, como "Ana Lima Exemplo" × "Ana Lima Exemplar"). Nome só parecido com valor diferente: são **duas pessoas**, não junta. Cada pessoa fica **OK**, **DIVERGENTE**, **SÓ NA LISTA** ou **SÓ NO FINANCEIRO**. A comparação não muda a lista nova.

---

## O resultado

Na tela: **Pagamentos achados**, **Valores diferentes** e **Não encontrados**; a tabela **saldo final do razão × lista nova**, com a composição da diferença até **Sem explicação** (deve dar zero); a lista dos não encontrados; os PDFs que ficaram fora do mês; com o financeiro, se ele bate pessoa a pessoa. Botões: **Abrir planilha**, **Abrir pasta**, **Ver avisos**.

Abas da planilha:

- **Resumo:** movimento do razão, as conferências (saldo anterior × lista anterior; uma linha por PDF usado; total dos PDFs e a diferença créditos − PDFs, com os pagamentos complementares), os PDFs não lançados no razão deste mês, os pagamentos por origem e a prova **saldo final × lista nova**.
- **Pagamentos:** todos os pagamentos do razão e onde cada um foi achado (*"PDF mensal"*, *"PDF complementar 29/06"*, *"Pendente anterior"* ou *"Não encontrado"*).
- **Valores diferentes:** os achados com valor diferente; a coluna **O que foi feito** diz se o restante ficou na lista ou se a diferença foi para a composição.
- **Não encontrados:** com a **Observação** da explicação provável (a primeira que se aplicar):
  - **a)** *"Rescisão de R$ X (PDF mensal) já baixada pelo pagamento de DD/MM, borderô N."* — a rescisão da pessoa já foi baixada por outro pagamento no mês. Se o PDF complementar existir, escolha-o junto com o mensal: o pagamento passa a ser achado nele.
  - **b)** *"Consta no PDF <arquivo> (pagamento DD/MM, R$ X), não lançado no razão deste mês."* — a pessoa só está num PDF que ficou de fora do mês.
  - **c)** *"Consta na composição da diferença da lista anterior: '…' (R$ valor)."* — o nome está no rodapé da planilha do mês anterior.
  - **d)** *"Sem rescisão correspondente."* — analise o pagamento.
- **Financeiro × lista** (só com o relatório do financeiro): o que conferir vem primeiro (DIVERGENTE em vermelho, SÓ NA LISTA e SÓ NO FINANCEIRO em amarelo); confira também as OK com **Confiança do nome** menor que 1.
- **Rescisões a pagar:** a lista nova, no formato da planilha de controle (Periodo, Colaborador, Valor e Origem). **No mês seguinte, use esta planilha como a lista do mês anterior.** Abaixo do total vem a **composição da diferença** ("COMPOSIÇÃO DA DIFERENÇA: SALDO DO RAZÃO − LISTA"): um item por linha explicando por que a lista não bate com o saldo do razão, o "Total da composição" e o "Saldo do razão em … (lista + composição)", que deve ser igual ao saldo final. **Os itens continuam valendo mês após mês:** antes de usar a planilha no mês seguinte, apague (ou corrija) os que já foram resolvidos.

---

## Se algo der errado

| Aviso | O que fazer |
|---|---|
| "ATENÇÃO: o razão é de … mas o PDF de eventos … é de …" | Confira se os arquivos são do mesmo mês |
| "ATENÇÃO: nenhuma combinação (ou mais de uma) dos PDFs de eventos soma os créditos do razão…" | Foram usados todos os PDFs. Confira se algum é de outro mês (ou se falta algum) e gere de novo só com os certos |
| "PDF de eventos repetido, ignorado: …" | O mesmo PDF foi escolhido duas vezes (ou o PDF e o Excel do mesmo relatório): nada a fazer |
| "O \"Período\" do cabeçalho da planilha (…) é diferente da competência das pessoas (…)" | O Excel de eventos veio com o Período errado; o programa usou o mês das pessoas. Confira se o arquivo é do mês certo |
| "ATENÇÃO: o saldo anterior do razão … não bate com o total da lista do mês anterior" | Confira se escolheu a lista do mês certo (e, na planilha gerada pelo programa, os itens da composição que você apagou ou mudou) |
| "ATENÇÃO: foram lidas N pessoas … no 0264, mas o PDF diz …" / "a prova não fechou" | O programa pode não ter lido tudo. Não confie nessa planilha e avise quem faz a manutenção |
| "Este arquivo é …, não …" | O arquivo foi escolhido no campo errado: a mensagem diz em qual colocar |
| "ATENÇÃO: a lista nova (R$ …) e os títulos a pagar do financeiro (R$ …) não batem pessoa a pessoa…" | Veja a aba **Financeiro × lista** |
| "ATENÇÃO: o relatório do financeiro tem títulos que não são de rescisão…" | Tire o relatório de novo só com os títulos de rescisão |
