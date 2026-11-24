# Crédito Estouro — instruções de uso

## O que o módulo faz (e o que não faz)

**Faz:** concilia a conta **Crédito Complemento Salário** (10652 – 1.01.03.02.0002 na Hospital Exemplo). Ela guarda o que cada colaborador ficou devendo quando a folha dele deu negativa. Exemplo: o afastado pelo INSS que tem o desconto do plano de saúde.

O módulo confere, **colaborador por colaborador**, o que aconteceu com essa dívida:
- se foi cobrada na folha do mês seguinte;
- se foi paga, ou parcelada;
- se foi baixada na rescisão.

Depois ele prova que o **saldo do razão** é igual ao que todos ainda devem. O que ficou em aberto é **carregado para o mês seguinte**, até ser acertado no mês aberto.

**Não faz:** não altera os arquivos que você escolhe nem nada no Tasy ou na folha: só lê e cria uma planilha nova.

---

## Os eventos da folha

| Evento | O que é |
|---|---|
| **0256** – Crédito estouro do mês | o que o colaborador ficou devendo no mês |
| **0258** – Débito estouro mês anterior | a cobrança, na folha, do 0256 do mês anterior |
| **0241** – Reembolso débito afastado | o que o afastado deve devolver (ele paga fora da folha: plano de saúde, tesouraria) |
| **1204** – Débito estouro parcelado | a parcela de quem paga a dívida aos poucos |
| **0775** – Devolução | devolução ao colaborador de um desconto do 0258 que não devia ter sido feito (vem num **PDF separado**) |

---

## Os arquivos

| Arquivo | Observação |
|---|---|
| **Eventos da folha do mês** (PDF, um ou mais) | O mesmo relatório de eventos usado nas Rescisões ("EVENTOS … C/IDENT") e, se houver no mês, o **PDF do 0775** ("EVENTO 775 COM IDENT …"), que vem separado. O relatório de eventos é do mês da conciliação; o do 0775 pode ser de um mês anterior (veja "O 0775") |
| **Razão** da conta Crédito Complemento Salário | Só o mês da conciliação. **De preferência o Excel (.xls) que sai do Tasy**: o PDF às vezes corta o fim do nome no histórico, e aí o pagamento não acha o dono |
| **Controle do mês anterior** | O **Excel que o próprio Crédito Estouro gerou** no mês anterior (ele tem a aba "Controle") |

**Onde ficam os arquivos (Hospital Exemplo):** na pasta da rede

`\\servidor-arquivos\contabilidade\CONCILIAÇÕES 2026\CONCILIAÇÕES 2026 - Hospital Exemplo\1 - ATIVO\1.01 - ATIVO CIRCULANTE\1.01.03 - OUTROS CREDITOS\1.01.03.02 - ADIANTAMENTO A EMPREGADOS\CREDITO COMPLEMENTO DE SALARIO`

Lá ficam os eventos da folha, o razão e o Excel do Crédito Estouro de cada mês. Escolha essa pasta também em **Pasta para salvar a planilha**: assim o Excel do mês fica junto dos outros e é ele que você escolhe como controle no mês seguinte.

**Primeira vez:** o ponto de partida é o Excel de **maio/2026**, montado a partir da planilha feita à mão (`Conciliacao_CreditoEstouro_HospitalExemplo_mai2026.xlsx`, o nome antigo; os novos saem como `CreditoEstouro_<mês>.xlsx`). Com ele, você roda junho; com o de junho, julho; e assim até o mês aberto.

---

## Passo a passo

1. No menu, em **CONCILIAÇÕES · ATIVO**, clique em **Crédito Estouro**.
2. Escolha o **PDF de eventos** do mês e, se houver, o **PDF do 0775**, juntos (segure **Ctrl** ao clicar). Confirmação, ex.: *"FUNDAÇÃO HOSPITAL EXEMPLO… · jul/2026 · 0256: 206 · 0258: 160 · 0241: 27 · 1204: 1 · 0775: 1"*. Se o razão tiver uma devolução e você não escolher o PDF do 0775, a planilha avisa.
3. Escolha o **razão** da conta, do mesmo mês. Confirmação, ex.: *"Excel · jun/2026 · 27 lançamentos · saldo final R$ 116.027,92"*. Com o PDF, aparece também um lembrete de que o Excel é melhor.
4. Escolha o **controle do mês anterior**. Confirmação, ex.: *"mai/2026 · 153 itens · R$ 98.853,35"*.
5. (Opcional) Em **Pasta para salvar a planilha**, escolha onde salvar. O programa lembra a pasta; sem escolher, a planilha vai para a pasta do razão.
6. Clique em **Gerar conciliação** e depois em **Abrir planilha**.

A planilha se chama `CreditoEstouro_<mês>.xlsx` (ex.: `CreditoEstouro_jun2026.xlsx`). Se ela já existir, o programa grava `_2`, `_3`…: nada é substituído.

**Arquivo errado?** O cartão fica em vermelho e o botão não acende. Isso vale para:
- o arquivo escolhido no campo de outro;
- um razão de outro mês, ou de vários meses;
- um controle que não é do mês anterior.

**Limpar** tira só aquele arquivo; **Limpar tudo** recomeça.

---

## Como o programa confere

**Quem é quem.** Na folha, pela **matrícula**. No razão, pelo **crachá**, quando o histórico traz. Sem crachá, pelo **nome completo**: todas as palavras do nome têm de estar no histórico. Uma palavra pode ter uma letra diferente, como "Faleiros" × "Falleiros" ou "Souza" × "Sousa". Nome que não dá para achar com segurança nunca é "chutado": vai para conferir.

**O 0256 do mês anterior**, de cada colaborador:

| Situação | Quando |
|---|---|
| Cobrado na folha do mês seguinte – colaborador continua na folha (trabalhando ou afastado) | 0258 do mês com o mesmo valor (o caso normal) |
| Cobrado na folha com valor diferente – conferir | 0258 com outro valor: a diferença fica no controle |
| Parcelamento novo | sem 0258, mas com 1204: vira parcelamento |
| Baixado na rescisão do razão – colaborador desligado | "Rescisão negativa" no razão com o mesmo valor |
| Baixado na rescisão do razão com valor diferente – conferir a diferença | rescisão com outro valor |
| Não cobrado na folha e não encontrado na rescisão negativa – conferir | nada disso: o valor continua no controle |

**O 0241 (afastados).** O 0241 do mês, mais a diferença que a pessoa já tinha, é comparado com os pagamentos no nome dela no razão. Contam como pagamento:
- o desconto de plano de saúde;
- o recebimento na tesouraria;
- o "Referente crédito de estouro … não lançado na folha".

O resultado é **Pagou certo**, **Pagou a mais**, **Pagou a menos** ou **Não pagou**. A diferença fica no controle.

**Pagamento em nome de outra pessoa** (ex.: o plano de saúde da dependente pago no nome dela):
- Na primeira vez, ele vai para "Lançamentos do razão a conferir", com a sugestão do afastado de mesmo sobrenome.
- Para a aplicação passar a contar sozinha, acrescente na aba **Controle** do Excel do mês uma linha:
  - **Tipo:** "Pagamento por outra pessoa";
  - **Matrícula:** a do colaborador;
  - **Pagador (nome no razão):** o nome como aparece no histórico.
- A linha é carregada todo mês.

**Parcelamentos (1204).** A parcela do mês é abatida do saldo. A situação pode ser:
- **quitado**, no 1204 ou no próprio razão;
- **parcela diferente** ou **parcela não descontada**, para conferir.

Parcelamento novo combinado com o DP: acrescente uma linha "Parcelamento" na aba **Controle** antes de rodar o mês.

**O 0775 (devolução).** O total é conferido com a "Devolução desconto crédito complemento salário" do razão do mês.
Para cada colaborador:
- se ele tinha no controle a pendência **"cobrado a mais"** no mesmo valor, o 0775 **zera** essa pendência;
- senão, o valor fica no controle como **"Devolução 0775 – conferir"**, até o acerto no razão.

**Em que mês o 0775 entra:** no mês em que a devolução foi **lançada no razão**, não no mês da folha. Ex.: o 0775
da folha complementar de junho/2026 só foi lançado no razão em setembro. De junho a agosto, não escolha esse PDF: a
pendência de "cobrado a mais" continua no controle. Em setembro, escolha o PDF do 0775 de junho junto com os eventos de
setembro: ele confere com o lançamento do razão e zera a pendência. A tela avisa que o PDF é de outro mês; não o
escolha de novo depois.

**Lançamentos do razão a conferir.** O que nenhuma regra explicou aparece com a data, o histórico e o valor, e entra na prova como **acerto manual**. Nada some.

**A prova do saldo.** O saldo final do razão tem de ser igual ao **total do controle**: o 0256 do mês, mais tudo o que ficou em aberto, mais os acertos. A **diferença sem explicação** deve ser **zero**.

---

## A planilha

| Aba | O que mostra |
|---|---|
| **Resumo** | arquivos usados, saldo do razão, folha × razão, composição do saldo, diferença sem explicação e quantas pessoas em cada situação |
| **0256 do mês anterior** | cada colaborador e o que aconteceu com o 0256 dele (o que precisa conferir vem primeiro) |
| **0241 – afastados** | quanto devia, quanto pagou, a diferença e quais pagamentos do razão contaram |
| **Parcelamentos** | saldo anterior, parcela, 1204 do mês e saldo novo |
| **0775 – devoluções** | cada 0775 e se ele zerou uma pendência de cobrado a mais ou ficou para conferir |
| **Lançamentos do razão a conferir** | o que nenhuma regra explicou |
| **Controle** | o que fica em aberto: **é o arquivo que você escolhe no mês seguinte** |
| **Avisos** | problemas de leitura |

**O Resumo acompanha o que você muda.** Os números do Resumo são fórmulas. Se você trocar a situação de uma linha na lista suspensa da coluna **Situação**, as contagens mudam. Se apagar da aba **Controle** uma linha já acertada, a composição do saldo muda.

Para acertar uma pendência: resolva no mês aberto e **apague a linha dela na aba Controle** antes de usar o arquivo no mês seguinte.

---

## O que fazer quando…

| Mensagem | O que fazer |
|---|---|
| "Diferença sem explicação" diferente de zero | Algum lançamento do razão ou da folha não foi explicado: veja os **Avisos** e o bloco **Folha × razão** do Resumo |
| "ATENÇÃO: o controle do mês anterior soma …, mas o saldo anterior do razão é …" | O controle escolhido não é o do mês anterior, ou alguém mexeu nele sem acertar no razão |
| "O razão é de … até …, mas os eventos são de …" | Tire no Tasy o razão só do mês dos eventos |
| "Razão em PDF: o Tasy às vezes corta o fim do nome" | Se puder, use o Excel (.xls) do razão |
| "O razão tem Devolução desconto…, mas nenhum PDF escolhido tem o evento 0775" | Escolha também o PDF do 0775 do mês, junto com o de eventos |
| "Os PDFs de eventos são de meses diferentes" | Escolha só o relatório de eventos do mês da conciliação |
| "O PDF do 0775 … é de …, depois do mês do relatório de eventos" | Esse 0775 entra num mês seguinte: escolha-o na conciliação do mês em que a devolução foi lançada no razão |
| "… eventos R$ … Se a devolução ainda não foi lançada no razão…" | O 0775 escolhido ainda não está no razão: tire o PDF dele e escolha-o no mês do lançamento |
| "Pagamento sem colaborador identificado no histórico" | Veja a sugestão; se for pagamento por outra pessoa, use a linha "Pagamento por outra pessoa" no controle |
