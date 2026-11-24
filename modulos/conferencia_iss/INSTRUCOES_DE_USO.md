# Conferência ISS — instruções de uso

## O que o módulo faz (e o que não faz)

**Faz:** confere se as notas de serviço lançadas no **Tasy** estão escrituradas no site da prefeitura com o mesmo valor, e gera uma planilha com o resultado. Atende cinco prefeituras, uma em cada aba: **Cidade Beta**, **Cidade Epsilon**, **Cidade Zeta**, **Cidade Gama** e **Cidade Alfa**.

A tela e a planilha são iguais em todas. O que muda é o relatório que você baixa do site, as notas canceladas (todas menos Cidade Beta) e, em Cidade Gama, a forma de achar as notas (pelo nome do prestador).

**Não faz:**

- não muda nada no Tasy nem no site da prefeitura: só lê os arquivos que você baixar e cria uma planilha nova;
- não ignora diferenças pequenas: **qualquer centavo de diferença é apontado**.

---

## Os arquivos de que você precisa

**Do Tasy: um ou mais arquivos CSV.** Os relatórios de notas fiscais de entrada da unidade, salvos em **CSV** (ex.: Serviço PJ, Honorário PJ e Notas de pessoa física). Pode escolher vários de uma vez. O arquivo precisa ter, no mínimo, as colunas **Nota Fiscal**, **Emitente**, **Código emitente**, **Tipo de nota** e **Valor da mercadoria**, em qualquer ordem.

**Da prefeitura** (o da competência que você quer conferir):

| Aba | Relatório no site | Formato |
|---|---|---|
| **Cidade Beta** | Relatório de Serviços Contratados | `.xls` — use **do jeito que o site entregou**; não abra e salve por cima no Excel (se acontecer, o programa avisa e é só baixar de novo) |
| **Cidade Epsilon** | Relatório de Serviços Tomados | `.xls` (ex.: `nfe SJ.xls`) — é uma planilha de verdade: abrir no Excel não estraga |
| **Cidade Zeta** | Declaração Completa de Tomador | **PDF** (ex.: `ISS Cidade Zeta.pdf`) — ao escolher, o cartão mostra *"Lendo o arquivo…"* por uns 3 segundos; é normal |
| **Cidade Gama** | Relatório de Nota Fiscal | `.xlsx` — não traz o CNPJ do prestador, só o nome (veja "Cidade Gama" mais abaixo) |
| **Cidade Alfa** | relatório de notas tomadas (site SilTecnologia) | **CSV** (ex.: `resultado_Prefeitura_Cidade_Alfa.csv`) — não traz a competência: o programa usa o **mês das datas de emissão**; confira na confirmação do cartão |

- Pode renomear os arquivos à vontade.
- Em Cidade Zeta, o programa confere a leitura com os totais que o próprio PDF imprime; se não bater, aparece um aviso de **ATENÇÃO**.
- Em Cidade Alfa, como os CSVs do Tasy também são `.csv`, cuidado para não trocar de cartão: o programa avisa se isso acontecer.
- **Escolheu o relatório de uma cidade na aba de outra?** O programa reconhece e diz qual aba usar.

**Dica:** guarde os arquivos do mês juntos numa pasta (ex.: `ISS RB\2026-09\`). A planilha gerada é salva **na mesma pasta do arquivo da prefeitura**.

---

## Passo a passo

1. No menu, em **FISCAL**, clique em **Conferência ISS** e escolha a aba da cidade. O módulo abre na última cidade que você usou. Pode trocar de aba a qualquer momento: cada uma guarda os seus arquivos e o seu resultado.
2. Em **Relatórios do Tasy (CSV)**, clique em **Selecionar** e escolha um ou mais CSVs (para vários, segure **Ctrl** enquanto clica). Confirmação, ex.: *"159 notas · unidade AME Cidade Beta"*.
3. Em **Relatório da prefeitura**, clique em **Selecionar** e escolha o relatório. Confirmação, ex.: *"Competência setembro/2026 · Inscr. 20164715 · 130 linhas"* (em Cidade Gama aparece o CNPJ da unidade no lugar da inscrição; em Cidade Alfa, nenhum dos dois). Confira se a competência é a que você queria.
4. Clique em **Gerar relatório**. A barra mostra o andamento, que leva poucos segundos.
5. O resultado aparece à direita. **Abrir pasta** abre o Explorador com a planilha já selecionada.

**Escolheu um arquivo errado?** **Limpar**, no próprio cartão, tira só aquele arquivo; **Limpar tudo**, ao lado de "Gerar relatório", recomeça do zero; **Novo**, depois de gerar, faz o mesmo que "Limpar tudo". O botão não acende enquanto houver um cartão em vermelho.

O nome da planilha é `Conferencia_ISS_RB_2026-09_AME_Cidade_Beta_14h05.xlsx` (Cidade Epsilon `_SJ_`, Cidade Zeta `_AV_`, Cidade Gama `_CP_`, Cidade Alfa `_FR_`):

- `2026-09` é a competência do relatório da prefeitura;
- `AME_Cidade_Beta` é a unidade dos CSVs do Tasy (unidades diferentes → `Varias_unidades`);
- `14h05` é a hora em que foi gerada. Gerou de novo no mesmo minuto? A nova ganha `_2`, `_3`… e **nenhuma é apagada**.

---

## O resultado

Na tela:

- **Conferidas:** notas do Tasy que bateram com a prefeitura.
- **Somente no Tasy:** notas que não estão na prefeitura.
- **Para analisar:** divergências de valor + notas escrituradas mais de uma vez + linhas só na prefeitura + notas do Tasy canceladas na prefeitura + (Cidade Gama) notas com nome diferente.
- **Tabela:** quantidade e valor de cada situação.
- **Conferências:** "Notas do Tasy no relatório **159 de 159**" e "Linhas da prefeitura no relatório **130 de 130**". Com o ✓ verde, nenhuma nota ficou de fora.
- **Avisos:** quantos houve; **Ver avisos** mostra a lista.

Abas da planilha:

| Aba | O que tem | O que fazer |
|---|---|---|
| **Resumo** | Unidade, competência, inscrição, arquivos lidos, tabela por situação e as conferências "nada sumiu" | Conferir os totais e o "X de X" |
| **Conferidas** | Notas que bateram (veja os tipos abaixo) | Nada. Nas "sem CPF", confira os dois nomes lado a lado |
| **Divergência de valor** | Mesma nota (CNPJ + número) nos dois lados, com valores diferentes; a coluna **Diferença** mostra quanto | Corrigir no Tasy ou na prefeitura |
| **Nome diferente (verificar)** (Cidade Gama) | Número e valor iguais, mas o nome do prestador não parece o mesmo | Comparar Emitente × Nome Empresarial: se for o mesmo prestador (ex.: mudou a razão social), está conferida |
| **Somente no Tasy** | Notas do Tasy que não estão no site | Verificar se precisam ser escrituradas na prefeitura |
| **Somente na prefeitura** | Linhas do site sem nota no Tasy | Verificar se falta lançar no Tasy ou se a escrituração está errada |
| **Escrituradas mais de uma vez** | Nota do Tasy que aparece 2 ou mais vezes na prefeitura; uma linha por escrituração, com **Valor confere?** (Sim/Não) | Ver se é duplicidade no site (em Cidade Alfa, compare CFPS e Deduções das duas linhas) |
| **Canceladas na prefeitura** (todas menos Cidade Beta) | Notas com situação "Cancelada" no site | Ver as "lançadas no Tasy" |
| **Avisos** | Um registro por arquivo lido ("OK" ou o erro) e os avisos de notas e linhas | Ler sempre |

**Os três tipos de "Conferida":**

- **Conferida:** mesmo CNPJ, mesmo número e mesmo valor.
- **Conferida (número ajustado):** o Tasy tem o número como "ano + zeros + número" (ex.: `2026000000122`) e a prefeitura só o número (`122`); mesmo CNPJ e mesmo valor.
- **Conferida sem CPF (por número e valor):** nota de pessoa física. O Tasy não tem o CPF; o programa achou na prefeitura **uma única** nota com o mesmo número e valor. Confira se os nomes (Emitente e Prestador) são da mesma pessoa.

**Notas canceladas (Cidade Epsilon, Cidade Zeta, Cidade Gama e Cidade Alfa):** ficam fora da conferência normal; por isso uma nota cancelada e reemitida com o mesmo número **não** aparece como "escriturada 2 vezes".

- **Cancelada na prefeitura (lançada no Tasy):** o Tasy tem a nota, mas no site ela está cancelada. Precisa de análise (talvez a nota não devesse estar no Tasy, ou falte a substituta no site). Entra em "Para analisar".
- **Cancelada na prefeitura (sem nota no Tasy):** em geral está tudo certo; fica na aba só para conferência.

**Cidade Gama — como o programa acha a nota sem o CNPJ:** o número sozinho não basta (prestadores diferentes usam os mesmos números), então ele exige **número + nome parecido**:

- **Nome parecido** = pelo menos uma palavra em comum, sem ligar para acentos, maiúsculas e palavras comuns como LTDA, ME, EIRELI, Serviços, Médicos, Clínica, Saúde. Ex. (nomes fictícios): "VERANO SERVIÇOS MÉDICOS LTDA" e "Verano Servicos Medicos Ltda" → parecidos.
- Número e nome batem, valor igual → **Conferida**; valor diferente → **Divergência de valor**.
- Número e valor batem, mas o nome não → **Número e valor iguais, nome diferente — verificar**.
- O **Nº Documento Escriturado** (ex.: "2543 / 1") também vale como número da nota.

**Colunas das abas de detalhe:** no começo, situação, CNPJ/CPF, emitente, número, **Valor da mercadoria** (Tasy), o valor da prefeitura (Valor do Doc., Vlr. Nota, Valor do Serviço, Valor Serviço ou Valor dos serviços, conforme a cidade) e **Diferença**, lado a lado; depois, os outros dados da prefeitura, com os nomes que o site usa; no final, os outros dados do Tasy. Cabeçalho verde = Tasy, dourado = prefeitura. Use o filtro da coluna **Diferença** para achar rápido o que não bateu.

- O programa compara **só o Valor da mercadoria** com o valor da prefeitura.
- Notas de concessionárias, locadoras ou da própria Hospital Exemplo aparecem em "Somente no Tasy": não há lista de exceções, você decide caso a caso.
- A coluna **Observação** do Tasy nunca aparece na planilha (tem dados pessoais).

---

## Se algo der errado

| Mensagem | O que fazer |
|---|---|
| Cartão do Tasy em **laranja**: "unidades misturadas" | Se foi sem querer, clique em **Limpar** e escolha só os da unidade certa |
| Cartão em **vermelho**, botão "Gerar relatório" apagado | O arquivo não é o esperado (ex.: coluna faltando). Leia a mensagem, clique em **Limpar** e escolha o certo |
| "O arquivo é uma planilha do Excel, não o relatório no formato do site" (Cidade Beta) | Baixe de novo do site e use o arquivo original |
| "Este é o Relatório de … de Cidade Epsilon. Para conferi-lo, use a aba Cidade Epsilon da Conferência ISS." (ou outra cidade) | Você escolheu o relatório de outra cidade: vá à aba indicada |
| "ATENÇÃO: a leitura do PDF não bate com o total impresso…" (Cidade Zeta) | Não confie no relatório desse mês. Confira o PDF e avise quem faz a manutenção |
| "a nota está com número 0 no PDF…" (Cidade Zeta) | A nota foi digitada errada no site: aparece em "Somente no Tasy" e "Somente na prefeitura". Confira e corrija no site |
| "ATENÇÃO: o relatório da prefeitura é do CNPJ … mas os CSVs do Tasy são do CNPJ …" (Cidade Gama) | Confira se escolheu os arquivos da mesma unidade |
| "Este é um CSV do Tasy…" / "Este é o relatório da Prefeitura de Cidade Alfa, não um CSV do Tasy…" | Escolha cada arquivo no cartão certo |
| "O relatório tem notas emitidas em mais de um mês…" (Cidade Alfa) | Confira se a competência usada é a certa |
| "situação na prefeitura é … (nem Normal nem Cancelada)" | A nota foi conferida normalmente. Confira no site o que significa |
| "Coluna(s) obrigatória(s) não encontrada(s): …" | Exporte de novo do Tasy, com o layout de sempre |
| Arquivo com **Erro** na aba Avisos | Aquele arquivo não pôde ser lido; os outros foram processados. Corrija e gere de novo |
| "Valor do Doc. vazio" / "Vlr. Nota vazio" | A linha aparece em "Somente na prefeitura". Confira no site |
| "Valor da mercadoria vazio ou inválido… não foi conferida" | Corrija no Tasy e gere de novo |
| "aparece em mais de um CSV do Tasy" | Ambas aparecem no relatório. Veja se o lançamento está duplicado |
| "Mais de uma nota da prefeitura com mesmo número e valor" | Nota de pessoa física que poderia ser de duas pessoas: fica em "Somente no Tasy". Confira à mão |
| "situação no Tasy é … (não Ativa)" | Foi conferida normalmente. Avalie se deveria estar no relatório |
| "Relatório não gerado: …" | Leia o motivo; em **Ver avisos** aparece o de cada arquivo |
| "Não foi possível salvar o relatório na pasta…" | Copie os arquivos para outra pasta (ex.: Documentos) e gere de novo |
| "Notas do Tasy no relatório" **com ✗ vermelho** | Algo ficou de fora (não deveria acontecer). Não use o relatório e avise quem faz a manutenção |
