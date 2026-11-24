# Honorários Médicos — instruções de uso

## O que o módulo faz (e o que não faz)

**Faz:** confere se o saldo de cada médico ou clínica na conta de **Honorários médicos a pagar** do balancete é igual ao que os relatórios do mês mostram para ele. Tem duas abas:

- **AMEs:** compara o balancete com o relatório de **repasse médico** do Tasy (SCF – Repasse Sintético). Serve também para a Hospital Exemplo quando a conta é conferida só com o repasse.
- **Hospital Exemplo (PF e PJ):** compara as contas **2131 – Pessoa Física** e **2132 – Pessoa Jurídica** com a **soma** do **HM Senior** (S. Atual) e dos PDFs de **Remoção/Deslocamento** e de **Pagamento particular** (Vl repasse). A planilha sai com uma aba para PF e outra para PJ.

O módulo abre na última aba usada.

**Não faz:** não altera os arquivos que você escolhe nem nada no Tasy ou no Senior: só lê e cria uma planilha nova.

Não importa o nome do arquivo: o programa reconhece cada relatório **pelo conteúdo**.

---

# Aba AMEs

## Os relatórios do Tasy

| Relatório | Observação |
|---|---|
| **Balancete** (865) com a conta de Honorários médicos a pagar (no AME, 2132) | Do jeito que sai do Tasy (.xls); .xlsx também vale |
| **SCF – Repasse Sintético** (repasse médico) | Do jeito que sai do Tasy (.xls); .xlsx também vale |

## Passo a passo

1. No menu, em **CONCILIAÇÕES · PASSIVO**, clique em **Honorários Médicos** e na aba **AMEs**.
2. Escolha o **balancete**. Confirmação, ex.: *"AME - Cidade Delta · set/2026 · conta 2132 · 53 contas · R$ 366.298,38"*.
3. Escolha o **repasse médico**. Confirmação, ex.: *"AME - Cidade Delta · set/2026 · 70 repasses · 53 terceiros · R$ 366.298,38"*. Se os dois forem de **unidades diferentes**, o cartão fica vermelho e o botão não acende; se forem de **meses diferentes**, aparece uma atenção.
4. (Opcional) Em **Pasta para salvar a planilha**, escolha onde salvar. O programa lembra a pasta nas próximas vezes; sem escolher, a planilha vai para a pasta do balancete. **Limpar**, no cartão, volta a esse padrão.
5. Clique em **Gerar relatório** e depois em **Abrir planilha**.

A planilha se chama `Conciliacao_HonorariosMedicos_<unidade>_<mês>.xlsx` (ex.: `Conciliacao_HonorariosMedicos_CidadeDelta_set2026.xlsx`).

**Escolheu um arquivo no campo errado?** A mensagem diz em qual campo colocar. **Limpar** tira só aquele arquivo; **Limpar tudo** recomeça (a pasta escolhida fica).

## Como o programa confere

- Um mesmo médico ou clínica pode ter **vários repasses** no mês (ex.: um de Produção Médica e outro de Deslocamento). O programa **soma todos** e compara a soma com o saldo da conta dele no balancete.
- A comparação é pelo **valor bruto** do repasse (Vl repasse), que é como o saldo está na contabilidade. A diferença entre bruto e líquido são as **retenções**: aparecem na planilha, mas não contam como diferença.
- O relatório de repasse não traz a conta contábil: o programa casa os dois lados **pelo nome**, do mesmo jeito do módulo Fornecedores. A coluna **Confiança do Pareamento** mostra quanto os nomes se parecem (1 = idênticos); confira os de confiança baixa.
- Uma conta com **saldo zero e sem repasse** no mês não entra na conciliação: ela aparece só numa nota do Resumo.

## O resultado

Na tela: **Médicos OK**, **Com diferença ou sem par** e **Linhas na conciliação**; os totais (balancete, repasse bruto, diferença e retenções); a lista do que não bateu. Botões: **Abrir planilha**, **Abrir pasta**, **Ver avisos**.

Abas da planilha:

- **Resumo:** os totais (balancete, repasse bruto e a diferença), quantos bateram, a **composição do repasse** por grupo (bruto, líquido e retenções), a lista do que não bateu e as notas.
- **Conciliação Completa:** uma linha por médico/clínica, com o saldo do balancete, o repasse de cada grupo, o total, a diferença e a situação:
  - **OK:** o saldo é igual à soma dos repasses;
  - **Divergente:** os dois existem, mas os valores não batem;
  - **Só no Balancete:** a conta tem saldo, mas não houve repasse no mês;
  - **Só no Repasse:** houve repasse, mas o médico/clínica não tem conta no balancete.
- **Repasses (detalhe):** cada repasse do relatório, com o grupo, as retenções e a conta do balancete com que foi casado.

## Se algo der errado

| Aviso | O que fazer |
|---|---|
| "Os arquivos são de unidades diferentes" | Escolha o balancete e o repasse da mesma unidade (o relatório não é gerado) |
| "ATENÇÃO: o balancete é de … mas o repasse é de …" | Confira se os dois arquivos são do mesmo mês |
| "ATENÇÃO: … foram lidos N repasses …, mas o relatório diz …" / "a soma das contas … não bate" / "a prova final não fechou" | O programa pode não ter lido tudo. Não confie nessa planilha e avise quem faz a manutenção |
| "Este arquivo é …, não …" | O arquivo foi escolhido no campo errado: a mensagem diz em qual colocar |

---

# Aba Hospital Exemplo (PF e PJ)

## Os relatórios

| Relatório | Formato | Observação |
|---|---|---|
| **Balancete** (865) com a 2131 e/ou a 2132 | .xls, do jeito que sai do Tasy | Pode ser um arquivo com as duas contas ou um para cada |
| **HM PF Senior** e **HM PJ Senior** ("Lançamentos Honorários Médicos em Aberto") | .XLS | Use o .XLS, não o PDF |
| **Relatório 6095 – Deslocamento** e **Remoção/Transporte** (SCF – Repasse Sintético) | PDF | Do jeito que sai do Tasy; o PDF da Remoção pode trazer junto o detalhado e as notas de débito |
| **Rel. 6203 – Pagamento particular** (Demonstrativo de Valores a Pagar) | PDF | Se houver no mês |

O balancete e o HM **em PDF** não são usados (ficam de fora, com um aviso), então pode selecionar todos os arquivos da pasta sem medo.

## Passo a passo

1. No menu, em **CONCILIAÇÕES · PASSIVO**, clique em **Honorários Médicos** e na aba **Hospital Exemplo (PF e PJ)**.
2. Clique em **Adicionar arquivos** e escolha os relatórios do mês. Pode escolher **todos de uma vez** (segure **Ctrl** para marcar vários) ou **ir adicionando**: por exemplo, os da pasta PF, depois clique de novo em **Adicionar arquivos** e escolha os da pasta PJ. Os arquivos vão **somando** na lista (o mesmo arquivo escolhido duas vezes entra uma vez); para começar de novo, clique em **Limpar**.
3. Espere a conferência (alguns segundos, por causa dos PDFs). Ela diz o que foi encontrado e o que falta:
   - verde, ex.: *"Balancete PF e PJ · HM PF e PJ Senior · 2 PDFs de repasse"* — está completo;
   - laranja, ex.: *"… · Falta: HM PJ Senior"* — dá para gerar, mas confira se não esqueceu algum arquivo;
   - vermelho, ex.: *"Falta o balancete…"* ou *"Há dois HM PF Senior…"* — o botão não acende até corrigir.
4. (Opcional) Em **Pasta para salvar a planilha**, escolha onde salvar (cada aba lembra a sua). Sem escolher, a planilha vai para a pasta do balancete.
5. Clique em **Gerar relatório** e depois em **Abrir planilha**.

A planilha se chama `Conciliacao_Honorarios_Medicos_PF_PJ_<mês>_<ano>.xlsx` (ex.: `Conciliacao_Honorarios_Medicos_PF_PJ_09_2026.xlsx`). Se já existir, a nova ganha `_2` no fim do nome.

> **Escolha só os arquivos do mês.** O Rel. 6203 não traz a competência, então o programa não consegue saber se ele é do mês certo: se o de outro mês for escolhido, ele entra na soma. (Os outros relatórios de outro mês ficam de fora sozinhos, com um aviso.) Por isso, deixe cada mês numa pasta separada.

## Como o programa confere

- **Os PDFs primeiro:** eles misturam pessoas físicas e clínicas, então o programa procura cada pessoa dos PDFs **nas contas PF e PJ juntas**, pelo nome. Cada linha do PDF vai para o lado (PF ou PJ) da conta em que a pessoa foi achada.
- **Depois o HM Senior:** o HM PF só com as contas PF (2131), e o HM PJ só com as contas PJ (2132), também pelo nome.
- Quando os nomes são muito diferentes (ex.: a conta no nome da médica e o Senior no nome da clínica dela), o programa casa **pelo valor**, se ele for único. Esses pares aparecem como **"valor (confirmar)"**: confira-os.
- Uma conta com **saldo zero e sem nada nos relatórios** não entra na conciliação: aparece só numa nota do Resumo.

## O resultado

Na tela: **Médicos OK**, **Com diferença ou sem par** e **Linhas na conciliação**; os totais de PF e PJ (contábil, Senior, PDFs de repasse e diferença); as linhas dos PDFs sem conta no balancete, se houver; a lista do que não bateu (ex.: *"PF · Sem par"*, *"PJ · Divergente"*). Botões: **Abrir planilha**, **Abrir pasta**, **Ver avisos**.

Abas da planilha:

- **Resumo:** para PF e para PJ, o Total Contábil, o Total Senior, (+) Remoção/Deslocamento, (=) Senior Ajustada, a diferença antes e depois dos PDFs, e a **Diferença AJUSTADA Total (PF + PJ)**. Embaixo, os arquivos usados e as observações (pares pelo valor, diferenças que se anulam entre PF e PJ, Pagamento particular incluído etc.).
- **PF - Conciliação** e **PJ - Conciliação:** uma linha por médico/clínica, com o saldo contábil, o nome e o saldo no Senior, o valor dos PDFs, o **Saldo Senior Ajustado** (Senior + PDFs) e a **Diferença Ajustada** (contábil − ajustado):
  - **sem cor:** bate;
  - **azul:** bate com a ajuda dos PDFs de Remoção/Deslocamento/Pagamento particular;
  - **vermelho:** ainda diverge — diferença positiva = o balancete tem mais do que os relatórios; negativa = os relatórios têm mais do que o balancete;
  - **amarelo:** sem correspondência (conta sem nada nos relatórios, ou pessoa do Senior sem conta).
- **Remoção-Deslocamento PFxPJ:** cada linha dos PDFs, marcada **PF**, **PJ** ou **Sem conta**, com a conta do balancete em que entrou e o arquivo de onde veio.

## Se algo der errado

| Aviso | O que fazer |
|---|---|
| "O PDF não traz a linha Total(n)…" | Normal no 6095 com uma linha só: o valor foi lido, só não pôde ser conferido pelo total do PDF |
| "Pagamento particular (Rel. 6203): … confira se ele é do mesmo mês do balancete" | Confira o mês do 6203 escolhido (ele não traz a competência) |
| "ATENÇÃO: o arquivo é de …, mas o balancete é de …; ele ficou de fora" | Um relatório de outro mês foi escolhido junto: não entrou na conta |
| "Diferenças que se anulam entre PF e PJ…" | A mesma pessoa pode ter sido lançada na conta do outro lado (PF × PJ) |
| "ATENÇÃO: … não bate com o Total…" / "a prova final … não fechou" | O programa pode não ter lido tudo. Não confie nessa planilha e avise quem faz a manutenção |
