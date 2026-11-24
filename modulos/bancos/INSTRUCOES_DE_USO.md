# Conciliação Bancária — instruções de uso

Confere, todo mês, se o saldo de cada conta bancária no **balancete contábil** (Excel exportado do sistema, relatório WEXE001) bate com o saldo do **extrato do banco** (PDF baixado do internet banking). O resultado é uma planilha com um **status** por conta. As diferenças são investigadas por quem confere: o programa só aponta, não tenta explicar.

## Passo a passo do mês

### 1. Junte os arquivos do mês

Numa pasta do mês, coloque o balancete e uma pasta com os extratos, por exemplo:

- `Conciliação 2026-08\balancete_bancario.xlsx`
- `Conciliação 2026-08\extratos\` (com subpastas à vontade: Banco do Brasil, CEF, Santander, Sicoob...)

A organização das subpastas é livre: o programa lê a pasta de extratos **e todas as subpastas**, e descobre o banco pelo **conteúdo** do PDF, não pelo nome do arquivo nem da pasta. Os nomes dos arquivos também são livres ("ok", "_ok", espaços — tanto faz).

### 2. Escolha os arquivos (aba "Conciliação")

| Cartão | O que escolher |
|---|---|
| **Balancete bancário (.xls do Tasy ou .xlsx)** | o balancete do mês, **do jeito que sai do Tasy** (.xls) ou salvo no Excel (.xlsx). Logo abaixo aparece a **competência** lida (ex.: "Competência 08/2026"). A pasta dele é sugerida como "Salvar em". |
| **Pasta dos extratos (PDF, com subpastas)** | a pasta `extratos`. Aparece quantos PDFs foram encontrados. |
| **Salvar em** | onde gravar a planilha. Se você trocar, a sua escolha é mantida mesmo que troque o balancete depois. |

> Escolheu um arquivo por engano? Clique em **Limpar**, embaixo do botão **Trocar** do cartão: a seleção sai e o cartão volta a ficar vazio.

### 3. Clique em **Conciliar**

A barra mostra o andamento, um PDF por vez. Se já existir uma planilha com o mesmo nome, a tela pergunta antes de substituir.

### 4. Confira o resultado

- **Números:** contas OK, contas com DIFERENÇA e extratos com problema.
- **Tabela:** quantas contas ficaram em cada status.
- **Linhas de conferência:** cada PDF que não foi lido, com a situação.
- **Botões:** **Abrir planilha** (`conciliacao_bancaria_AAAA-MM.xlsx`), **Abrir pasta**, **Novo** (limpa as escolhas para outro mês) e, quando houver extrato de modelo não reconhecido, **Modelo novo** (ver mais abaixo).

## O que pedir ao financeiro

- **Um PDF por conta/produto**, baixado do internet banking (com texto), **nunca escaneado** nem impresso como imagem ("Microsoft Print to PDF" de uma tela gera imagem). PDF escaneado não é lido.
- **Extratos do mês da competência** (de 01 a 31). Extratos de outro mês são recusados. No **BB** e no **Santander**, o extrato de conta corrente que vai até o dia seguinte (ex.: 01/10 a 01/11) também serve: o programa usa o saldo do último dia do mês.
- No **Santander**, além do extrato de conta corrente, o **extrato ContaMax** ("Posição Consolidada Mensal") de cada aplicação.
- No **BB**, o extrato **completo** do CDB (com a tabela "Saldo nos últimos 6 meses"), não o resumo.
- No **BB**, o extrato de conta corrente pode vir do **BB Cash** ou da tela **"Consultas – Extrato de conta corrente"** do autoatendimento, salvo pelo navegador com **"Salvar como PDF"** (assim o PDF sai com texto).

## A planilha gerada

Um arquivo por mês, `conciliacao_bancaria_AAAA-MM.xlsx` (o mês vem do balancete), com quatro abas: Resumo, Conciliação, Arquivos e Detalhe. Nas abas Conciliação, Arquivos e Detalhe a primeira linha fica fixa ao rolar, cada coluna tem filtro e os valores estão no formato 1.234,56.

### Aba Resumo

Visão geral: a **competência**, a data e hora da geração, quantas contas ficaram em cada status e quantos PDFs foram lidos, escaneados, com erro, com modelo não reconhecido ou duplicados. Use esta aba para saber, de relance, quanto trabalho de conferência manual sobrou.

As quantidades são **fórmulas**: quando você resolve uma pendência e troca o **Status** na aba Conciliação (ex.: de DIFERENÇA para OK), o Resumo se ajusta sozinho, e a cor da linha também muda. Na coluna Status há uma **lista suspensa** com os status possíveis. Se digitar outro texto, o Excel avisa, e a conta aparece no Resumo em "Outros (status digitado fora da lista)".

### Aba Conciliação

A aba principal: uma linha para cada conta bancária do balancete e, no fim, as contas que apareceram nos extratos mas não existem no balancete.

| Coluna | O que mostra |
|---|---|
| Código, Classificação, Descrição | dados da conta no balancete |
| Banco, Tipo, Conta | banco (BB, CEF, SANTANDER, SICOOB), tipo (CC = conta corrente, APLICACAO, POUPANCA) e número da conta, sem pontos, traços e zeros à esquerda |
| Saldo Balancete | o Saldo Atual da conta no balancete |
| Saldo Disponível (extrato) | saldo livre para uso, segundo o extrato |
| Saldo Bloqueado (extrato) | valor bloqueado (por exemplo, cheques em compensação no Sicoob) |
| Saldo Total (extrato) | disponível + bloqueado. É este valor que é comparado com o balancete |
| Diferença | Saldo Total do extrato − Saldo do balancete |
| Status | o resultado da comparação (ver abaixo) |
| Arquivos | os PDFs de onde veio o saldo. Quando há mais de um, os saldos foram somados (por exemplo, CDB + Rende Fácil da mesma conta) |
| Observação | avisos para quem confere: conta casada pelo final do número, aplicação zerada, saldo bloqueado, fundos que compõem o saldo etc. |

| Status | Cor | Significado | O que fazer |
|---|---|---|---|
| OK | verde | o extrato bate com o balancete | nada |
| DIFERENÇA | vermelho | os valores não batem | investigar a diferença |
| SEM EXTRATO | amarelo | a conta está no balancete, mas nenhum extrato dela foi lido | ver se o extrato falta na pasta ou se aparece na aba Arquivos com algum problema |
| NÃO ESTÁ NO BALANCETE | amarelo | há extrato, mas a conta não existe no balancete | se a observação disser "saldo zero", em geral pode ser ignorada; se tiver saldo, verificar |

### Aba Arquivos

Uma linha para cada PDF encontrado na pasta de extratos, inclusive nas subpastas. Nenhum arquivo some sem explicação.

| Coluna | O que mostra |
|---|---|
| Subpasta | a subpasta onde o arquivo estava (por exemplo, Banco do Brasil\Aplicações) |
| Arquivo | nome do PDF |
| Modelo | o tipo de extrato reconhecido (por exemplo, "BB - CDB", "Santander - ContaMax") |
| Situação | o que aconteceu com o arquivo (ver abaixo) |
| Contas extraídas | tipo e número da conta lidos do PDF |
| Mensagem | o motivo, quando o arquivo não foi lido, ou um aviso |

| Situação | Cor | Significado |
|---|---|---|
| LIDO | sem cor | lido normalmente. A mensagem pode trazer um aviso, como um extrato do BB guardado na pasta do Sicoob |
| ESCANEADO – CONFERIR MANUALMENTE | cinza | o PDF é uma imagem, sem texto, e não pode ser lido. A observação diz o motivo: se foi salvo pelo "Microsoft Print to PDF", salve de novo pelo navegador ("Salvar como PDF") e rode outra vez. Se não der, conferir à mão ou pelo projeto do Claude |
| MODELO NÃO RECONHECIDO | cinza | é um tipo de extrato que o programa ainda não conhece. Use o botão **Modelo novo** (ver abaixo) |
| ERRO DE LEITURA | cinza | o extrato foi reconhecido, mas o saldo não pôde ser lido com segurança. A mensagem diz o motivo: extrato de outro mês, CDB em formato resumo, extrato sem saldo impresso, vários extratos juntos num PDF etc. |
| DUPLICADO – IGNORADO | cinza | cópia idêntica de outro PDF da pasta. É ignorada para o saldo não ser contado duas vezes |

### Aba Detalhe

Uma linha para cada saldo lido de cada PDF, antes de qualquer soma. Serve para rastrear de onde veio cada valor da aba Conciliação.

| Coluna | O que mostra |
|---|---|
| Arquivo, Modelo | o PDF e o tipo de extrato |
| Banco, Tipo | banco e tipo da conta |
| Conta original | o número da conta exatamente como aparece no extrato (por exemplo, 000568630703-9) |
| Conta normalizada | o mesmo número sem pontos, traços e zeros à esquerda, que é o usado para achar a conta no balancete |
| Disponível, Bloqueado, Total | os saldos lidos daquele PDF |
| Fonte secundária | "Sim" quando o saldo só serve de apoio, se não houver extrato principal. Hoje nenhum modelo usa, então aparece sempre "Não" |
| Observação | avisos daquele extrato |

## Regras que o programa usa (resumo)

- **Contas do balancete:** só as analíticas dos grupos 1.01.01.02 (depósitos), 1.01.01.03 (aplicações) e 1.01.01.04 (poupança). Banco, tipo e número vêm da descrição (`BB C/C 8036-5`, `Santander Aplicação 3634-5`...). "S/A" é tratado como conta corrente.
- **Casamento:** por banco + tipo + número da conta. Se não houver casamento exato, aceita quando um número termina com o outro (ex.: Santander `130036369` x `3636-9`), desde que haja um único candidato.
- **Soma:** extratos da mesma conta e tipo são somados (ex.: CDB + Rende Fácil da mesma conta de aplicação do BB).
- **Mês:** todo extrato tem o período conferido; extrato de outro mês vira ERRO DE LEITURA e não entra na soma.
- **Nunca inventar zero:** se o saldo não for encontrado com segurança, o arquivo vira ERRO DE LEITURA com o motivo. Zero só quando o próprio extrato diz que a aplicação está zerada.

| Modelo | Saldo usado |
|---|---|
| BB — Conta corrente | última linha `S A L D O`; se o extrato passa do fim do mês, a última linha com data até o fim do mês |
| BB — CDB | coluna *Liquid.proj.* da tabela "Saldo nos últimos 6 meses" (com juros), não o capital |
| BB — Poupança | "Saldo total" (não o "Saldo atual"); o extrato pode ir até o dia 1 do mês seguinte (ex.: 01/10 a 01/11) |
| BB — Rende Fácil | "Saldo bruto em <último dia do mês>" |
| BB — Fundos | soma dos "Saldo Atual =" de cada fundo |
| CEF — Conta corrente | coluna Saldo da última linha de lançamento |
| Santander — Conta corrente | coluna Saldo da última linha de lançamento (o quadro-resumo é da data de emissão do PDF e não é usado) |
| Santander — ContaMax | "Saldo Bruto Final" da linha do mês, conferido pela fórmula do próprio extrato |
| Sicoob — Conta corrente | "Saldo em conta" + bloqueado (cheques + judicial) |

## Modelo novo de extrato

Quando um PDF aparece como **MODELO NÃO RECONHECIDO**, é um extrato que o programa ainda não conhece (um banco novo ou um layout diferente). A conciliação do mês não depende disso: a conta fica como SEM EXTRATO até o leitor existir.

1. **Confira à mão** no PDF: número da conta, tipo e o saldo do último dia do mês.
2. No resultado, clique em **Modelo novo**. Para cada PDF não reconhecido aparece um formulário com o início do texto do extrato: preencha banco, tipo, conta, saldo total conferido (e o bloqueado, se houver) e clique em **Salvar pacote** (ou **Pular este arquivo**).
3. A Central cria a pasta `<Salvar em>\modelos_novos\<AAAA-MM>_<nome do PDF>\` e mostra no resultado o comando `/novo-modelo "<pacote>"` — ele **já fica copiado** (é só colar com Ctrl+V).
4. Abra o Claude Code na pasta da Central e cole o comando. Ele cria o leitor, confere o saldo com o que você informou, roda os testes e gera o programa de novo. Se algo não bater, ele para e pergunta.
5. Com o programa novo, **concilie o mês de novo**: a conta sai de SEM EXTRATO.

O passo a passo completo, inclusive sem o botão, está em `modulos\bancos\COMO_ADICIONAR_MODELO.md`.

## Quando algo dá errado

| Situação | O que fazer |
|---|---|
| "Não foi possível gravar a planilha... Se ela estiver aberta no Excel, feche e rode de novo" | Feche a planilha no Excel e clique em **Conciliar** de novo. |
| "Não foi possível ler o balancete" (em vermelho no cartão do balancete) | Confira se é o balancete bancário exportado do Tasy (.xls, sem abrir e salvar) ou salvo como .xlsx. Um .xls salvo no Excel no formato antigo (97-2003) não é lido: salve como .xlsx. |
| "Nenhum PDF nesta pasta nem nas subpastas" | A pasta escolhida está errada ou vazia. |
| Muitas contas em SEM EXTRATO | Veja nas linhas de conferência (e na aba Arquivos) se os PDFs foram lidos; confira se são do mês certo. |
| Um PDF aparece como ESCANEADO | Peça ao financeiro o PDF baixado do internet banking (com texto): no navegador, **Imprimir → Destino "Salvar como PDF"**, não "Microsoft Print to PDF". Se não der para refazer, use o projeto do Claude (`modulos\bancos\projeto_claude\COMO_USAR.md`): ele lê esses PDFs pela imagem e completa as contas SEM EXTRATO, sempre para você conferir. |
