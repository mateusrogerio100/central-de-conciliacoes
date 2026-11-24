# Clientes CMD — instruções de uso

O módulo tem duas abas de trabalho:

- **Conciliação de clientes**: confere o balancete contábil de clientes contra a planilha de Títulos a Receber (financeiro), cliente a cliente;
- **Import Contábil**: junta os relatórios do mês numa planilha **Rel_Geral** e gera o arquivo **.txt** que o sistema contábil importa.

---

## Conciliação de clientes

Casa os lançamentos dos dois relatórios **pelo nome do cliente** e gera a planilha de conciliação com um status por cliente: `OK`, `DIVERGENTE`, `SEM CONTÁBIL` ou `SEM FINANCEIRO`.

### Passo a passo

1. **Balancete de clientes (.xls do Tasy ou .xlsx):** o balancete contábil exportado do sistema. Pode usar o `.xls` do jeito que o Tasy gera, sem abrir no Excel. A pasta dele é sugerida como pasta de saída.
2. **Títulos a Receber (.xls do Tasy ou .xlsx):** o relatório de Títulos a Receber do financeiro (também pode ser o `.xls` do Tasy).
3. **Pasta de saída:** onde gravar a planilha `Conciliacao_Clientes_CMD.xlsx`. Se ela já existir, a tela pergunta antes de substituir.
4. Clique em **Gerar conciliação**. A barra mostra o andamento (casar os nomes leva alguns segundos).
5. Confira o resultado: clientes OK, DIVERGENTES e sem par (sem contábil + sem financeiro), com a tabela por status. Use **Abrir planilha** para revisar, **Abrir pasta** e **Novo** para começar outra conciliação.

> Escolheu um arquivo por engano? Clique em **Limpar**, embaixo do botão **Trocar** do cartão: a seleção sai e o cartão volta a ficar vazio.

### A planilha gerada

| Coluna | O que mostra |
|---|---|
| Cod | código do cliente no balancete (vazio quando o cliente só existe no financeiro) |
| Contábil, Valor Contábil | nome e saldo do cliente no balancete |
| Financeiro, Valor Financeiro | nome e saldo ("Vl saldo") no relatório de Títulos a Receber |
| Dif | diferença Contábil − Financeiro (fórmula do Excel); "-" quando zera ou quando falta um dos lados |
| Status | fórmula do Excel com o resultado (ver abaixo) |

| Status | Cor da linha | Significado | O que fazer |
|---|---|---|---|
| OK | sem cor | o cliente está nos dois relatórios com o mesmo valor | nada |
| DIVERGENTE | vermelho claro | o cliente está nos dois relatórios, mas os valores são diferentes | investigar a diferença |
| SEM CONTÁBIL | amarelo claro | o cliente só aparece no financeiro | procurar o cliente no balancete (pode ser nome escrito de outro jeito) |
| SEM FINANCEIRO | amarelo claro | o cliente só aparece no balancete | procurar o cliente nos Títulos a Receber |

A primeira linha fica fixa ao rolar e cada coluna tem filtro.

### Como o casamento pelo nome funciona

Os dois relatórios escrevem os nomes de jeitos diferentes (nomes cortados, erros de digitação, pontuação e espaços). Por isso o programa tenta, **do critério mais confiável para o menos confiável**:

1. nome idêntico;
2. um nome é o começo do outro (nome cortado);
3. nome igual sem pontuação;
4. nomes muito parecidos;
5. valor único como último recurso;
6. vários lançamentos com o mesmo nome que só podem ser de um cliente do outro lado são somados.

> O casamento é automático, mas **não é 100% garantido**: alguns clientes podem ficar como SEM CONTÁBIL / SEM FINANCEIRO mesmo sendo o mesmo, ou (mais raramente) casar com o cliente errado quando os nomes são muito parecidos e os valores coincidem. Tudo o que não for `OK` deve ser revisado antes de fechar a conciliação.

---

## Import Contábil

Dois passos:

1. **Gerar Rel_Geral:** junta todos os relatórios da pasta do mês (o **`.xls` direto do Tasy**, sem abrir no Excel, ou o `.xlsx`) numa planilha só (`Rel_Geral_MM_AAAA.xlsx`). Você pode conferir e corrigir essa planilha.
2. **Gerar arquivo de import:** a partir do Rel_Geral (o gerado no passo 1 ou um montado à mão), grava o `Import_gerado_MM_AAAA.txt` no formato do sistema contábil.

### Passo a passo

1. **Mês de referência:** vem sugerido o mês anterior. Confira (formato **MM/AAAA**): ele vai no nome dos arquivos e na data dos lançamentos.
2. **Pasta com os relatórios do mês:** a pasta com os relatórios exportados (a quantidade e os nomes mudam de mês a mês). Aparece quantos relatórios (`.xls` ou `.xlsx`) foram encontrados. A pasta **acima** dela é sugerida como pasta de saída.
3. **Pasta de saída:** onde gravar o Rel_Geral e o `.txt`. Não pode ser a própria pasta dos relatórios: o Rel_Geral seria juntado aos relatórios da próxima vez.
4. Clique em **1. Gerar Rel_Geral**. O resultado mostra quantas linhas vieram de cada relatório e o total de lançamentos. O Rel_Geral gerado já fica escolhido no cartão **Rel_Geral**.
5. Se precisar, clique em **Abrir Rel_Geral**, confira e corrija. (Também dá para escolher no cartão **Rel_Geral** uma planilha montada à mão.)
6. Clique em **2. Gerar arquivo de import**. O resultado mostra os lançamentos e as linhas do arquivo (duas por lançamento).

> Escolheu um arquivo por engano? Clique em **Limpar**, embaixo do botão **Trocar** do cartão: a seleção sai e o cartão volta a ficar vazio.

### O que o programa faz em cada passo

**Rel_Geral:**

- lê **todos** os relatórios da pasta, `.xls` do Tasy e `.xlsx` (arquivos temporários do Excel, `~$...`, são ignorados). O `.xls` do Tasy é texto: o programa converte cada célula do mesmo jeito que o Excel fazia ao salvar como `.xlsx`, e o Rel_Geral sai igual;
- se o **mesmo relatório** estiver na pasta em `.xls` e em `.xlsx` (mesmo nome), o programa para e avisa, para ele não entrar duas vezes;
- as colunas são identificadas **pela posição**, porque os nomes do cabeçalho variam entre exportações: a primeira coluna (contrato) é descartada e as seguintes viram Dia lançamento, Conta debito, Conta credito, Vl parcela formatado, Historico, Complemento, Centro custo e Vl parcela formatado.1;
- descarta cabeçalhos repetidos no meio dos dados;
- tira espaços e aspas duplicadas das pontas do Complemento;
- corrige valores em texto malformados: em `"2,614.91"` ou `"2,614,91"`, o **último** separador é o decimal (vira 2614.91).

**Arquivo de import (.txt):**

- lê a aba "Consolidado" do Rel_Geral e descarta a linha de total;
- grava **duas linhas por lançamento**: na primeira, data (sempre o **último dia do mês**, `DDMMAA`), contas, valor com 14 posições, histórico e complemento; na segunda, centro de custo em 6 posições e o valor;
- centro de custo vazio (como nas provisões) vira `1007`;
- o complemento sai sempre entre um único par de aspas, com vírgulas trocadas por pontos;
- o arquivo é gravado em **ISO-8859-1** com quebras de linha **CRLF**, como o sistema contábil exige.

---

## Quando algo dá errado

| Situação | O que fazer |
|---|---|
| "Não foi possível gravar... Ele provavelmente está aberto no Excel" | Feche o arquivo no Excel e clique no botão de novo. |
| "Nenhum relatório .xlsx ou .xls encontrado em: ..." | A pasta dos relatórios está errada ou vazia. |
| "O mesmo relatório está na pasta em .xls e em .xlsx..." | Deixe só um dos dois arquivos de cada relatório citado e gere de novo. |
| "...: esperado ao menos 5 colunas" | Um arquivo da pasta não é um relatório de lançamentos (ou veio num formato diferente). Tire-o da pasta ou confira a exportação. |
| "A aba "Consolidado" deveria ter 8 colunas" | O Rel_Geral escolhido não está no formato esperado (aba "Consolidado" com as 8 colunas). |
| "O caractere ... não existe na codificação ISO-8859-1 exigida pelo import" | Algum texto do Rel_Geral tem um símbolo que o sistema não aceita (por exemplo, €). Corrija no Rel_Geral, na linha indicada, e gere o import de novo. |
| "Não foi possível concluir" na conciliação de clientes | Confira se escolheu o balancete de clientes e o relatório de Títulos a Receber certos, em .xlsx. |
| Apareceu "Erro inesperado" | Anote a mensagem (os detalhes técnicos aparecem no resultado) e peça o ajuste do programa. |
