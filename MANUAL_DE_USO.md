# Manual de Uso — Central de Conciliações

Este manual é para quem usa o programa **CentralConciliacoes.exe** no fechamento do mês.

A Central reúne, numa janela só, as conciliações da área contábil. Este manual explica o que é
**igual em todos os módulos**. O passo a passo de cada módulo está na aba **Instruções de uso**
dentro do próprio programa (e nos arquivos indicados na seção 3).

---

## 1. Abrir o programa

Dê dois cliques em **CentralConciliacoes.exe**. A janela abre em poucos segundos. Não precisa
instalar nada.

Na primeira vez, o Windows pode mostrar "O Windows protegeu o computador". Clique em
**Mais informações** e depois em **Executar assim mesmo**.

## 2. A janela

- **No alto do menu:** o símbolo da Hospital Exemplo e o nome do programa. O mesmo símbolo é o ícone do
  programa na barra de tarefas. As cores da tela são azul escuro, nos modos claro e escuro.
- **Menu à esquerda:** um item para cada módulo — **Conciliação Bancária**, **Clientes CMD**,
  **Subvenções e Projetos**, **Serviços Tomados**, **Estoque**, **Conferência de NF**, **Notas Check-list**, **Notas Pendentes**, **Conferência ISS**, **EFD Contribuições**, **Fornecedores**, **Rescisões**, **Honorários Médicos**, **Planilha HM**, **Imobilizado – AME's**, **Crédito Estouro**, **Convênios**, **Imprimir PDFs** e **Histórico de uso**. Clique para
  trocar de módulo.
- **Abas:** logo abaixo do título de cada módulo. As primeiras são as de trabalho; a última é
  sempre **Instruções de uso**.
  - Conciliação Bancária: *Conciliação* · *Instruções de uso*
  - Clientes CMD: *Conciliação de clientes* · *Import Contábil* · *Instruções de uso*
  - Subvenções e Projetos: *Preenchimento* · *Instruções de uso*
  - Serviços Tomados: *Gerar arquivo* · *Instruções de uso*
  - Estoque: *Conciliação* · *Instruções de uso*
  - Conferência de NF: *Conferir lote* · *Instruções de uso*
  - Notas Check-list: *Conferência* · *Pendências* · *E-mails* · *Instruções de uso*
  - Notas Pendentes: *E-mails* · *Instruções de uso*
  - Conferência ISS: *Cidade Beta* · *Cidade Epsilon* · *Cidade Zeta* · *Cidade Gama* · *Cidade Alfa* · *Instruções de uso* (abre na última cidade usada)
  - EFD Contribuições: *Geração do SPED* · *Instruções de uso*
  - Fornecedores: *Conciliação* · *Instruções de uso*
  - Rescisões: *Conciliação* · *Instruções de uso*
  - Honorários Médicos: *AMEs* · *Hospital Exemplo (PF e PJ)* · *Instruções de uso* (abre na última aba usada)
  - Imobilizado – AME's: *Conciliação* · *Instruções de uso*
  - Crédito Estouro: *Conciliação* · *Instruções de uso*
  - Imprimir PDFs: *Imprimir* · *Instruções de uso*
  - Planilha HM: *Preenchimento* · *Instruções de uso*
  - Convênios: *Preenchimento* · *Instruções de uso*
  - Histórico de uso: *Histórico* · *Instruções de uso*
- **Modo escuro / Modo claro:** botão no pé do menu. A escolha fica guardada.
- No pé do menu aparecem o seu usuário do Windows e a **versão** do programa (ex.: 1.10.5).
- O menu é dividido em seções: **Fiscal**, **Conciliações · Ativo**, **Conciliações · Passivo**,
  **Receitas** e **Ferramentas**. Se a janela estiver baixa e os itens não couberem, o menu rola (roda do mouse com o
  ponteiro sobre ele).
- O programa abre sempre no **Imprimir PDFs**, o módulo que abre mais rápido (até a versão 1.3.8
  abria no último módulo usado).
- Pode trocar de módulo ou de aba à vontade: **o que você já escolheu continua lá** quando você volta.
- **Quem usava o Conciliações AMES:** os módulos que vieram de lá (Conferência ISS, Fornecedores,
  Rescisões, Honorários Médicos, Imobilizado – AME's e Imprimir PDFs) funcionam igual e já abrem com
  as pastas, a impressora e a última cidade e aba que você usava lá. Depois de um mês
  usando só a Central, o `Conciliacoes AMES.exe` pode ser apagado.

---

## 3. Como usar cada módulo

Todas as telas de trabalho funcionam do mesmo jeito:

1. **À esquerda, "Arquivos de entrada":** em cada cartão, clique em **Selecionar** (ou **Trocar**)
   e escolha o arquivo ou a pasta (**Limpar**, embaixo do Trocar, tira a seleção do cartão). Abaixo do nome aparece uma linha de confirmação:
   - **verde:** tudo certo (ex.: "Mês de referência 08/2026");
   - **laranja:** atenção, confira (ex.: mês diferente do balancete);
   - **vermelho:** o arquivo não pôde ser lido.
2. **Pasta de saída:** o programa sugere uma pasta a partir do arquivo principal (a pasta do
   balancete; no Import Contábil, a pasta acima da dos relatórios). Troque se quiser gravar em
   outro lugar — a sua escolha é mantida.
3. **Mês de referência** (quando o módulo usa): aparece sozinho ou vem sugerido; confira e, se
   precisar, digite no formato **MM/AAAA**.
4. **O botão principal** (Conciliar, Gerar conciliação, Preencher...) só fica disponível quando
   tudo foi escolhido. No Estoque há **um botão por etapa** (EST-01, EST-02, EST-03), e cada um acende
   quando os arquivos daquela etapa foram escolhidos. Clique e acompanhe a **barra de andamento** à direita.
5. **À direita, "Resultado":** números principais, uma tabela e as conferências (verde = ok,
   laranja = conferir, vermelho = problema). No rodapé, os botões **Abrir planilha / Abrir pasta /
   Ver avisos** e **Novo** (limpa as escolhas para começar outro mês).

**Perguntas que o programa faz:**

- **"Estes arquivos já existem na pasta de saída e serão substituídos"** — responda **Sim** só se
  quiser refazer. Se algum deles estiver aberto no Excel, feche antes.
- Em Subvenções, se o balancete e o patrimônio forem de **meses diferentes**, ele pergunta se quer
  continuar. Normalmente é arquivo do mês errado: responda **Não** e confira.
- No Estoque, se o balancete, o SCF ou o PDF forem de **meses diferentes** do mês informado, ele
  pergunta se quer continuar. Normalmente é arquivo do mês errado: responda **Não** e confira.
- Em Serviços Tomados, **"Não encontrei a cidade deste prestador"**: digite a cidade e a UF (fica
  guardada para as próximas vezes) ou clique em **Não sei** (a nota vai para "lançar à mão").
- Em Serviços Tomados, o botão **Outros CNPJs da Fundação** só é preciso se um estabelecimento
  tiver CNPJ que **não** comece com 98.765.432: informe-o ali (um por linha) e as notas tomadas por
  ele passam a entrar, num `.txt` próprio.

**Garantias:** os arquivos que você escolhe **nunca são alterados** — o programa só grava na pasta
de saída, e se recusa a gravar por cima de um arquivo de entrada.

### Instruções de cada módulo

| Módulo | Resumo | Instruções completas |
|---|---|---|
| **Conciliação Bancária** | Balancete bancário (o .xls como sai do Tasy, ou .xlsx) + pasta dos extratos (PDF) → planilha `conciliacao_bancaria_AAAA-MM.xlsx` com o status de cada conta (OK, DIFERENÇA, SEM EXTRATO, NÃO ESTÁ NO BALANCETE). PDF sem texto (escaneado ou "Microsoft Print to PDF") é marcado na hora como ESCANEADO, sem deixar a leitura lenta; se veio do "Microsoft Print to PDF", a observação pede para salvar de novo pelo "Salvar como PDF" do navegador. Poupança do BB tirada até o dia 1 do mês seguinte vale (Saldo total). Balancete sem nenhuma conta (só o cabeçalho): a conciliação para e pede para tirar de novo no Tasy. As contagens do Resumo são fórmulas: trocou o status de uma conta na planilha, o Resumo se ajusta sozinho. O que pedir ao financeiro, como ler a planilha e o botão **Modelo novo** estão nas instruções. | aba **Instruções de uso** do módulo · [modulos/bancos/INSTRUCOES_DE_USO.md](modulos/bancos/INSTRUCOES_DE_USO.md) |
| **Clientes CMD** | *Conciliação de clientes:* balancete de clientes + Títulos a Receber (`.xls` direto do Tasy ou `.xlsx`) → `Conciliacao_Clientes_CMD.xlsx` (OK, DIVERGENTE, SEM CONTÁBIL, SEM FINANCEIRO). *Import Contábil:* pasta com os relatórios do mês (`.xls` direto do Tasy ou `.xlsx`) → **1. Gerar Rel_Geral** → **2. Gerar arquivo de import** (`Import_gerado_MM_AAAA.txt`). | aba **Instruções de uso** do módulo · [modulos/clientes_cmd/INSTRUCOES_DE_USO.md](modulos/clientes_cmd/INSTRUCOES_DE_USO.md) |
| **Subvenções e Projetos** | Balancete + relatório de patrimônio (o `.xls` direto do Tasy ou `.xlsx`; balancete vazio para com aviso) + planilhas do mês anterior → cópias preenchidas com o mês novo no nome e o relatório `Avisos_MM-AAAA.xlsx` (abas, gravidades e todos os tipos de aviso explicados nas instruções). | aba **Instruções de uso** do módulo · [modulos/subvencoes/INSTRUCOES_DE_USO.md](modulos/subvencoes/INSTRUCOES_DE_USO.md) |
| **Serviços Tomados** | Pasta dos PDFs das notas (DANFSe) e/ou exportações de lotes do site + resultados da prefeitura (notas já escrituradas) → `tomados_<CNPJ>_<MM-AAAA>.txt` para importar no site e `Relatorio_Tomados_<data e hora>.xlsx` com o destino de cada nota, as notas para **lançar à mão** (entre elas as não retidas com ISS devido numa cidade diferente da cidade do prestador as emitidas num mês diferente da competência e as NFS-e no modelo da Prefeitura de São Paulo) e as de **número a corrigir no site**; a aba **Falar com o fornecedor** lista as notas de prestador Não Optante sem nenhum imposto federal retido. Informe **todos** os resultados (de todos os logins e dos últimos meses). | aba **Instruções de uso** do módulo · [modulos/escrituracao_tomados/INSTRUCOES_DE_USO.md](modulos/escrituracao_tomados/INSTRUCOES_DE_USO.md) |
| **Estoque** | Balancete + SCF - Movimento Estoque (na tela e nos Excels, "Mapa do Estoque") + PDF "Movimento estoque" do Tasy → um Excel por etapa: `EST-01 Conciliação saldo anterior estoque MM-AAAA.xlsx`, `EST-02 Conciliação contas estoque MM-AAAA.xlsx` e `EST-03 Conciliação saldo atual estoque MM-AAAA.xlsx`. Gere o balancete com as **contas zeradas**. O balancete e o SCF do CMD e dos AMES (com Débitos/Créditos e sem a coluna Subvenção) também são aceitos. Operação nova do Tasy: botão **Editar configuração**. | aba **Instruções de uso** do módulo · [modulos/conciliacao_estoque/INSTRUCOES_DE_USO.md](modulos/conciliacao_estoque/INSTRUCOES_DE_USO.md) |
| **Conferência de NF** | **Unidade conferida** (a nota com CNPJ de outra unidade ou de fora da Fundação fica vermelha) + lote do Tasy (.csv; de preferência o **Movimento contábil**, que traz o centro de custo: conta 3 ou 4 sem centro de custo fica vermelha, e os rateios aparecem na aba *Rateios*; nota de serviço com retenção que não bate com o lançamento ou com a alíquota (IRRF 1,5%, INSS 11% ou 20%, PIS/COFINS/CSLL 4,65%) fica roxa; com a pasta do *gabarito de contas*, a aba *Contas a conferir* avisa as contas fora do habitual ou do Padrão — ensine o gabarito na aba *Gabarito de contas* com o Movimento contábil já revisado) + pasta das notas (PDFs e, se tiver, os **XMLs**, que o programa lê direto), baixados pela **data de atualização no estoque** → `Conferencia_NF_<data e hora>.xlsx` (um novo a cada conferência). Aviso vermelho **"A pasta dos PDFs parece ser de outro dia"**: menos de um quarto (25%) dos PDFs da pasta casou com o lote; troque a pasta dos PDFs e confira de novo. **Verde:** número, data, valor e partidas já conferidos, falta só olhar as contas. **Conferir à mão:** PDF não veio, não é nota fiscal, PDF não bate, casou com observação ou estorno; a aba *Conferir à mão* do Excel traz a lista com o motivo. Lançamento na conta **Fornecedores a reclassificar** também vai para conferir: no crédito, ver se precisa trocar para a conta do próprio fornecedor; no débito, ver se foi provisionada. A aba *Escriturar na prefeitura* lista as notas de serviço (com PDF de DANFSe) para escriturar no site da prefeitura, com os impostos retidos e a marca *Falar com o fornecedor* nas de prestador Não Optante sem imposto federal retido. Não altera nada no Tasy. | aba **Instruções de uso** do módulo · [modulos/conferencia_nf/INSTRUCOES_DE_USO.md](modulos/conferencia_nf/INSTRUCOES_DE_USO.md) |
| **Notas Check-list** | *Conferência:* mês + as pastas do movimento do Tasy da Hospital Exemplo e do CMD (um .csv por dia: ponha o dia novo junto com os outros) + o Check list da rede + a pasta das regras (a `config` ao lado do Check list entra sozinha) → `Check list <ano> - <MM> preenchido.xlsx` (uma **cópia**: o valor do mês só nas linhas OK e só em célula vazia; confira e copie para a rede) e `Conferencia_Contratos_<AAAA-MM>_<data e hora>.xlsx`. **Conta divergente:** a nota chegou na conta errada, corrija no Tasy. Destaques: variação de 10% ou mais, valor diferente do que já está na planilha e célula com "Provisão" com nota achada (o valor se refere ao mês anterior, que foi provisionado). *Pendências:* o Check list da rede já atualizado (+ o relatório, que vem sozinho) → `Previa_emails_...html` (todos os e-mails; quem ficou sem e-mail em vermelho; as notas de conta divergente, que não vão nos e-mails, numa seção no fim) e `Emails_para_Claude_Desktop_...txt` (botão **Texto Claude**: cole no Claude Desktop ligado ao Gmail da Contabilidade para ele criar os rascunhos). Quem recebe cada e-mail: o **número** no começo da coluna Responsável (`13 - Nome`) e, na aba Emails, os números ao lado de cada contato (`Todos`, `Todos CMD`; `Cópia` = em cópia de todos; `Cópia CMD` = em cópia dos que têm notas do CMD). *E-mails:* com o `credentials.json` da TI, cria os rascunhos direto no Gmail (nada é enviado). Não altera o Check list da rede nem o Tasy. | aba **Instruções de uso** do módulo · [modulos/checklist_contratos/INSTRUCOES_DE_USO.md](modulos/checklist_contratos/INSTRUCOES_DE_USO.md) |
| **Notas Pendentes** | Competência + prazo para registro + a pasta do mês da rede (`...\8- NOTAS PENDENTES AUTOMATIZADOR\HOSPITAL EXEMPLO\<MMAAAA>`; cada PDF começa com o número do responsável) + o Check list de contratos (os contatos da aba Emails) + o modelo do e-mail (opcional; o da pasta `config` entra sozinho) → `Previa_notas_pendentes_...html` (um e-mail por número, com o texto, os destinatários e os PDFs que vão anexados; quem ficou sem e-mail em vermelho), `Notas_pendentes_...xlsx` (cada arquivo da pasta e o que aconteceu com ele) e `Emails_para_Claude_Desktop_...txt` (botão **Texto Claude**: o Claude Desktop cria os rascunhos **sem anexos**; anexe à mão os PDFs da lista "ANEXAR À MÃO" de cada e-mail). Não altera a pasta das notas nem o Check list. | aba **Instruções de uso** do módulo · [modulos/notas_pendentes/INSTRUCOES_DE_USO.md](modulos/notas_pendentes/INSTRUCOES_DE_USO.md) |
| **Conferência ISS** | Um ou mais CSVs do Tasy + o relatório da prefeitura da cidade (Cidade Beta .xls, Cidade Epsilon .xls, Cidade Zeta .pdf, Cidade Gama .xlsx, Cidade Alfa .csv) → `Conferencia_ISS_<cidade>_<mês>_<unidade>_<hora>.xlsx` (Resumo, Conferidas, Divergência de valor, Somente no Tasy, Somente na prefeitura, Escrituradas mais de uma vez, Canceladas na prefeitura, Avisos), na pasta do relatório da prefeitura. | aba **Instruções de uso** do módulo · [modulos/conferencia_iss/INSTRUCOES_DE_USO.md](modulos/conferencia_iss/INSTRUCOES_DE_USO.md) |
| **EFD Contribuições** | Pasta com as DANFSe do mês + o SPED do mês anterior (`.txt`) + a pasta de saída → `SpedEPC_gerado_MM_AAAA.txt` (para importar no programa da Receita, na máquina remota) e `Conferencia_EFD_MM_AAAA_HHhMM.xlsx` (situação de cada PDF, clientes novos, avisos). Só notas de pessoa jurídica; o cadastro de clientes (`clientes.json`) é escolhido na tela e lembrado — guardem numa pasta da rede para a equipe usar a mesma lista. Pergunta antes de gerar sem um PDF que não pôde ser lido, deixa incluir à mão as notas que ficaram fora pelas datas, avisa PDF de prestador com CNPJ diferente e pede o Código IBGE de cliente novo que vier sem ele. | aba **Instruções de uso** do módulo · [modulos/efd_contribuicoes/INSTRUCOES_DE_USO.md](modulos/efd_contribuicoes/INSTRUCOES_DE_USO.md) |
| **Fornecedores** | Balancete (conta 2111) + relatório analítico de títulos a pagar (tirado em Excel normal, com os filtros e os 12 campos do começo das instruções do módulo), os dois como saem do Tasy → `Conciliacao_Fornecedores_<unidade>_<mês>.xlsx` (Resumo, Conciliação Completa e Títulos das diferenças), na pasta escolhida (lembrada) ou na do balancete. Situações: OK, DIVERGENTE, SÓ NO BALANCETE, SÓ NO RELATÓRIO. | aba **Instruções de uso** do módulo · [modulos/conciliacao_fornecedores/INSTRUCOES_DE_USO.md](modulos/conciliacao_fornecedores/INSTRUCOES_DE_USO.md) |
| **Rescisões** | Razão da conta Rescisões a pagar + eventos da folha (0264, PDF ou Excel; um ou mais) + lista de Rescisões a pagar do mês anterior e, opcional, os títulos a pagar do financeiro → `Conciliacao_Rescisoes_<unidade>_<mês>.xlsx` (Resumo, Pagamentos, Valores diferentes, Não encontrados, Rescisões a pagar — a lista do mês seguinte — e Financeiro × lista), na pasta escolhida (lembrada) ou na do razão. | aba **Instruções de uso** do módulo · [modulos/conciliacao_rescisoes/INSTRUCOES_DE_USO.md](modulos/conciliacao_rescisoes/INSTRUCOES_DE_USO.md) |
| **Honorários Médicos** | **AMEs:** balancete (865) da conta de Honorários médicos a pagar + SCF – Repasse Sintético → `Conciliacao_HonorariosMedicos_<unidade>_<mês>.xlsx` (Resumo, Conciliação Completa, Repasses (detalhe)). **Hospital Exemplo (PF e PJ):** os relatórios do mês num cartão só ("Adicionar arquivos" vai somando: balancete 2131/2132, HM PF e PJ Senior, PDFs 6095 / Remoção / 6203) → `Conciliacao_Honorarios_Medicos_PF_PJ_<mm>_<aaaa>.xlsx` (Resumo, PF - Conciliação, PJ - Conciliação, Remoção-Deslocamento PFxPJ). Na pasta escolhida (cada aba lembra a sua) ou na do balancete. | aba **Instruções de uso** do módulo · [modulos/honorarios_medicos/INSTRUCOES_DE_USO.md](modulos/honorarios_medicos/INSTRUCOES_DE_USO.md) |
| **Planilha HM** | Eventos do mês (o `.XLS` do Tasy) + Movimento do lote de Repasse a terceiros (o `.csv` do Tasy) + a Planilha HM do mês anterior em `.xlsx` → `MM Planilha HM AAAA Atualizada em DD-MM-AAAA COMPETENCIA MM.xlsx` (uma **cópia** com a aba Senior do mês, as linhas novas na aba do ano e o LOTE REPASSE) e `Conferencia_PlanilhaHM_<AAAA-MM>_<data e hora>.xlsx` (Resumo, Eventos, Linhas criadas, Movimento sem evento quando não fecha, Avisos). O botão só acende com o Eventos e o Movimento do mesmo mês. Evento novo com conta desconhecida: a tela pergunta a seção (ou cria uma seção nova) e grava a resposta no `secoes_contas.csv` da pasta `config`, ao lado da planilha. Aba Senior do mês já preenchida ou cópia já existente: a tela pergunta antes de substituir. Não altera os arquivos escolhidos. | aba **Instruções de uso** do módulo · [modulos/planilha_hm/INSTRUCOES_DE_USO.md](modulos/planilha_hm/INSTRUCOES_DE_USO.md) |
| **Crédito Estouro** | PDFs de eventos da folha do mês (0256, 0258, 0241, 1204 e, se houver, o PDF separado do 0775) + razão da conta Crédito Complemento Salário (de preferência o `.xls` do Tasy; o PDF às vezes corta o nome) + o **controle do mês anterior** (o Excel que o módulo gerou; o ponto de partida é o de maio/2026) → `CreditoEstouro_<mês>.xlsx` (Resumo, 0256 do mês anterior, 0241 – afastados, Parcelamentos, 0775 – devoluções, Lançamentos do razão a conferir, Controle, Avisos). A aba **Controle** é a entrada do mês seguinte: acertou uma pendência, apague a linha dela; parcelamento novo ou "pagamento por outra pessoa", acrescente uma linha. O Resumo usa fórmulas e acompanha essas mudanças. | aba **Instruções de uso** do módulo · [modulos/credito_estouro/INSTRUCOES_DE_USO.md](modulos/credito_estouro/INSTRUCOES_DE_USO.md) |
| **Convênios** | Razão Convênios do mês (o `.xls` do Tasy ou `.xlsx`) + a planilha RECEITAS DE CONVÊNIOS em `.xlsx` (com a aba do ano) + a pasta `config` com o `equivalencias.csv` (a que está ao lado da planilha entra sozinha) → `RECEITAS DE CONVÊNIOS <MMAAAA>.xlsx` (uma **cópia** com o mês preenchido, a linha Saldo Contábil e as linhas novas de convênios que ainda não existiam, em ordem alfabética) e `Conferencia_Convenios_<AAAA-MM>_<data e hora>.xlsx` (Resumo, Por convênio, Lançamentos, Avisos). **Não identificado** (ex.: IAMSPE, até a regra de SC × HC): preencha à mão na cópia. Mês já preenchido: a tela pergunta antes de substituir, e as linhas sem lançamento no razão mantêm o valor. Nome que deve ir para outra linha: acrescente no `equivalencias.csv`. Não altera o razão nem a planilha escolhida. | aba **Instruções de uso** do módulo · [modulos/convenios/INSTRUCOES_DE_USO.md](modulos/convenios/INSTRUCOES_DE_USO.md) |
| **Imprimir PDFs** | Os PDFs escolhidos (ou a pasta inteira) → nenhuma planilha: mostra o total de folhas e manda todos para a impressora escolhida (lembrada) numa impressão só, de um lado só; na fila aparece como "Central de Conciliações – N PDFs (N folhas) – hh:mm:ss". | aba **Instruções de uso** do módulo · [modulos/imprimir_pdfs/INSTRUCOES_DE_USO.md](modulos/imprimir_pdfs/INSTRUCOES_DE_USO.md) |
| **Imobilizado – AME's** | Razão auxiliar do patrimônio (6051) + os três balancetes (865) e, se houver diferença, Bens adquiridos (555) e Baixa de bens (561), todos como saem do Tasy → `Conciliacao_imobilizado_<mês>_<AME>_<hora>.xlsx` (Resumo, Contas, Diferenças, Bens adquiridos, Baixas, Avisos), na pasta escolhida (lembrada) ou na do patrimônio. Aba **Comparação Ativo x Passivo**: razão do Ativo + razão do Passivo do Tasy → `Conciliacao_ativo_passivo_<mês>_<AME>_<hora>.xlsx` (cada conta do Ativo com a irmã do Passivo, achada pelo nome; Confere / Diferença / Sem par). | aba **Instruções de uso** do módulo · [modulos/conciliacao_imobilizado/INSTRUCOES_DE_USO.md](modulos/conciliacao_imobilizado/INSTRUCOES_DE_USO.md) |

---

### Log de uso

A Central anota sozinha **quem** usou (o usuário do Windows), **quando**, em qual computador e **o que** foi
feito: a abertura do programa e cada processamento (o botão principal de cada módulo, com "ok" ou "erro").
Escolher arquivos ou trocar de módulo não conta. Cada computador grava o seu arquivo na pasta
`\\servidor-arquivos\contabilidade\CONCILIAÇÕES 2026\Automações\Dados\Log de uso`; com a rede fora do ar, o uso fica guardado no
computador e vai depois (a Central nunca espera a rede). A planilha com o resumo sai no item
**Histórico de uso**, em Ferramentas: botão **Gerar planilha**.

## 4. Quando algo dá errado

| Situação | O que fazer |
|---|---|
| "Não foi possível gravar ... Ele provavelmente está aberto no Excel: feche e tente de novo" | Feche o arquivo no Excel e clique no botão de novo. |
| "Estes arquivos seriam gravados por cima dos arquivos de entrada" | Escolha outra pasta de saída (ou confira o mês de referência). |
| O resultado mostra **"Não foi possível concluir"** com uma explicação | Leia a explicação: normalmente é arquivo errado ou fora do formato. Corrija e clique de novo — o botão volta a funcionar. |
| Apareceu **"Erro inesperado"** com "Detalhes técnicos" | Copie o texto dos detalhes técnicos e peça ajuda (Guia de Manutenção). |
| Um item do menu mostra **"Este módulo não pôde ser aberto"** | Os outros módulos funcionam normalmente. Copie os detalhes técnicos e peça ajuda. |
| Quer fechar o programa no meio de um processamento | Ele pergunta antes: fechar agora pode deixar arquivos incompletos na pasta de saída. Prefira esperar terminar. |
| A janela demorou uns 20 segundos para abrir | Normal na **primeira** abertura de um .exe novo (o Windows confere o arquivo); as seguintes levam poucos segundos. Se continuar sempre lento, peça ajuda (Guia de Manutenção, seção 17). |
| O Windows ou o antivírus bloqueou o .exe | "Mais informações" > "Executar assim mesmo". Se o antivírus apagar o arquivo, peça liberação à TI. |
| A janela ficou escura (ou clara) e você quer o contrário | Botão **Modo claro / Modo escuro** no pé do menu. |

Para o que é específico de cada módulo (mensagens, avisos, status), veja a seção "Quando algo dá
errado" nas **Instruções de uso** do módulo.
