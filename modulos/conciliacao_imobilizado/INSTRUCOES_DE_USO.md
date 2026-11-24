# Imobilizado – AME's — instruções de uso

## O que o módulo faz (e o que não faz)

**Faz:** confere se o **saldo atual de cada conta do patrimônio** é igual ao **saldo atual da mesma conta nos balancetes** do Tasy. Serve para qualquer AME: os relatórios e as contas são os mesmos. Quando há diferença, tenta explicá-la com os bens adquiridos e as baixas do mês.

**Não faz:**

- não altera os relatórios que você escolhe nem nada no Tasy: só lê e cria uma planilha nova;
- não ignora diferenças pequenas: **qualquer diferença aparece, mesmo de centavos** (quem concilia decide).

---

## Os relatórios do Tasy

| Relatório no Tasy | Nº | Obrigatório? |
|---|---|---|
| Patrimônio – Razão auxiliar (NOVO) | **6051** | Sim |
| Balancete – Intangível AME | **865** | Sim |
| Balancete – Imobilizado AME | **865** | Sim |
| Balancete – Cessão AME | **865** | Sim |
| Patrimônio – Bens adquiridos no período por centro custo | **555** | Não: só quando houver diferença |
| Baixa de Bens do Ativo Imobilizado | **561** | Não: só quando houver diferença |

- Todos do **mesmo AME** e do **mesmo mês**. Se misturar, o programa avisa.
- Salve do jeito que o Tasy gera (`.xls`). **Não abra e salve de novo no Excel**: o arquivo muda de formato e o programa pede o original.
- Pode renomear os arquivos à vontade.

---

## Passo a passo

1. No menu, em **CONCILIAÇÕES · ATIVO**, clique em **Imobilizado – AME's**.
2. Em **Patrimônio (6051) – Razão auxiliar**, escolha o Razão auxiliar. Confirmação, ex.: *"agosto/2026 · 9 contas"*.
3. Em **Balancetes (865)**, escolha os três balancetes de uma vez (segure **Ctrl** enquanto clica). Confirmação, ex.: *"Ame - Cidade Alfa · agosto/2026 · 9 contas"* — confira se é o AME e o mês certos.
4. (Opcional) Em **Pasta para salvar a planilha**, escolha onde a planilha deve ser salva. O programa lembra essa pasta nas próximas vezes. Se não escolher nenhuma, a planilha vai para a pasta do arquivo do patrimônio. Para voltar a esse padrão, clique em **Limpar** no cartão da pasta.
5. Clique em **Gerar relatório**. A planilha é salva com o nome `Conciliacao_imobilizado_<mês>_<AME>_<hora>.xlsx` (ex.: `Conciliacao_imobilizado_2026-08_Ame_Cidade_Alfa_15h30.xlsx`). Se gerar de novo no mesmo minuto, a nova ganha `_2`, `_3`... e nenhuma é apagada.
6. **Se aparecer diferença:** escolha também **Bens adquiridos (555)** e/ou **Baixa de bens (561)** e clique em **Gerar relatório** de novo. O programa tenta explicar a diferença com as entradas e saídas do mês. A tela avisa quando vale a pena fazer isso.

**Escolheu um arquivo no campo errado?** O programa diz qual relatório é e em qual campo colocar, e o botão não acende enquanto houver um cartão em vermelho (mesmo um opcional). **Limpar** tira só aquele arquivo; **Limpar tudo**, ao lado de "Gerar relatório", recomeça do zero (a pasta escolhida fica).

---

## O resultado

Na tela: **Conferem**, **Diferenças explicadas** e **Para analisar**, uma tabela por situação e quantos avisos houve (**Ver avisos** mostra a lista). **Abrir pasta** abre o Explorador com a planilha selecionada.

| Situação | O que quer dizer | O que fazer |
|---|---|---|
| **Confere** | Saldo atual igual no patrimônio e no balancete | Nada |
| **Diferença — verificar** | Saldos diferentes e os relatórios de bens adquiridos/baixas não foram escolhidos | Escolher os opcionais e gerar de novo, ou analisar |
| **Diferença explicada pelos bens adquiridos/baixados** | A diferença é igual às entradas, às baixas ou a entradas − baixas da conta no mês (para mais ou para menos) | Ver na coluna **Explicação** qual lado está maior: falta o lançamento do outro lado |
| **Diferença sem explicação — verificar** | Saldos diferentes e nem as entradas nem as baixas explicam | Analisar |
| **Somente no patrimônio** / **Somente no balancete** | A conta está só num dos relatórios | Ver se faltou um balancete ou se a conta é nova |

- **Diferença** = patrimônio − balancete. Positiva: o patrimônio está maior.

Abas da planilha:

- **Resumo:** AME, mês, arquivos lidos, tabela por situação e o total de cada balancete (Intangível, Imobilizado, Cessão) comparado com as mesmas contas no patrimônio.
- **Contas:** todas as contas, com os dois saldos, a diferença, a situação, a explicação e os movimentos de cada lado (azul = patrimônio, amarelo = balancete).
- **Diferenças:** só as contas que não conferem (aparece só se houver).
- **Bens adquiridos** e **Baixas:** os bens de cada relatório, com a conta de cada um (aparecem só se o relatório foi escolhido).
- **Avisos:** arquivos lidos e tudo o que merece atenção.

---

## Se algo der errado

| Aviso | O que fazer |
|---|---|
| "No patrimônio, a conta … não fecha: saldo anterior + entradas − baixas ± transferências ≠ saldo atual" | O próprio relatório 6051 não fecha naquela conta (ex.: linha "Baixas" veio zerada). Se o aviso disser que o valor é igual às baixas, foi isso |
| "ATENÇÃO: os balancetes são de AMEs diferentes" / "de meses diferentes" / "o patrimônio é de …" | Confira se escolheu os arquivos do mesmo AME e do mesmo mês |
| "Baixas da conta "…": nenhuma conta do patrimônio ou do balancete tem esse nome" | O relatório de baixas não traz o código da conta, só o nome; esse nome não bate com nenhuma conta. Confira à mão |
| "ATENÇÃO: foram lidos N bens somando …, mas o total impresso é …" | O programa pode não ter lido algum bem. Não confie nesse relatório e avise quem faz a manutenção |
| "O arquivo parece ter sido aberto e salvo de novo no Excel" | Tire o relatório de novo no Tasy |

---

## Aba "Comparação Ativo x Passivo"

A "comparação final" do imobilizado: confere se o **saldo de cada conta do Ativo** é igual ao da **conta irmã no Passivo**. Serve para qualquer AME.

### Os relatórios

Dois **razões contábeis** do Tasy (relatório "Razão"), do **mesmo AME** e do **mesmo mês**, salvos do jeito que o Tasy gera (`.xls`, sem abrir e salvar no Excel):

- **Razão do Ativo:** só as contas do imobilizado, intangível e cessão de uso do Ativo (contas que começam com **1.**);
- **Razão do Passivo:** só as contas irmãs do Passivo (contas que começam com **2.**).

### Passo a passo

1. No menu Imobilizado – AME's, clique na aba **Comparação Ativo x Passivo**.
2. Em **Razão do Ativo**, escolha o razão do Ativo. Confirmação, ex.: *"AME - Cidade Gama · outubro/2026 · 10 contas"*.
3. Em **Razão do Passivo**, escolha o razão do Passivo.
4. (Opcional) Escolha a **Pasta para salvar a planilha** (é a mesma pasta lembrada da aba "Conciliação"). Sem escolher, a planilha vai para a pasta do razão do Ativo.
5. Clique em **Comparar Ativo x Passivo**. A planilha sai como `Conciliacao_ativo_passivo_<mês>_<AME>_<hora>.xlsx`.

Escolheu o razão do Passivo no cartão do Ativo (ou o contrário)? O cartão fica vermelho e diz em qual colocar.

### Como o programa acha a conta irmã

Os nomes não são iguais ("Aparelhos de Informatica - AME Cidade Gama" × "Gestão Imobilizado Publico AmeC Aparelhos de Informatica") e o número da conta nem sempre ajuda. Por isso o programa:

- só procura dentro do mesmo grupo: **1.02 × 2.02** (imobilizado e intangível) e **1.05 × 2.05** (cessão de uso);
- compara o **tipo do bem** que sobra no nome, sem acentos, maiúsculas e plural, e sem as palavras "Gestão", "Imobilizado", "Público", "Cessão", "Uso", "AME", a sigla "AmeC" e o nome da cidade;
- **nunca usa o valor para achar o par**: o valor só é comparado depois. Assim a conta com diferença aparece como diferença, e não como conta sem par.

Se tiver dúvida (nenhum nome parecido, ou dois parecidos), o programa **não chuta**: a conta aparece como **Sem par — verificar**.

### O resultado

Na tela: **Conferem**, **Diferenças** e **Sem par**, a lista das contas que não conferem com a diferença de cada uma e os totais do Ativo, do Passivo e da diferença.

| Situação | O que quer dizer | O que fazer |
|---|---|---|
| **Confere** | Saldo igual no Ativo e no Passivo | Nada |
| **Diferença — verificar** | A conta tem irmã, mas os saldos são diferentes | Analisar o lançamento que falta num dos lados |
| **Sem par — verificar** | A conta não achou irmã (a coluna Observação diz por quê) | Ver se a conta é nova, se o nome está diferente no Tasy ou se faltou conta no razão |

- **Diferença** = Ativo − Passivo. Positiva: o Ativo está maior. Qualquer diferença aparece, mesmo de centavos.
- O saldo comparado é o da coluna **Saldo** do razão: o último de cada conta.

Abas da planilha: **Ativo x Passivo** (AME, mês, arquivos e uma linha por par: grupo, conta e saldo do Ativo, conta e saldo do Passivo, diferença, situação, observação e o total) e **Avisos**.

| Aviso | O que fazer |
|---|---|
| "Os razões são de AMEs diferentes" / "de períodos diferentes" | Confira se escolheu os dois razões do mesmo AME e mês |
| "Este razão tem contas do Ativo (1.x) e do Passivo (2.x) juntas" | Tire do Tasy um razão para cada lado |
| "o relatório diz N contas e foram lidas M" | O programa pode não ter lido alguma conta. Avise quem faz a manutenção |
