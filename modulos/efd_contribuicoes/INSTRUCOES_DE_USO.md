# EFD Contribuições — instruções de uso

## O que o módulo faz (e o que não faz)

**Faz:** gera o arquivo **SPED EFD-Contribuições** (`.txt`) do mês com as **notas de serviço emitidas** (DANFSe), pronto para importar no programa da Receita (EFD Contribuições) na máquina remota. Também grava um **Excel de conferência** com o que aconteceu com cada PDF.

**Não faz:**

- não assina nem transmite: no programa da Receita continua o fluxo de sempre (Importar → conferir → Verificar Pendências → Gerar Arquivo para Entrega → Assinatura → Transmitir). O `.txt` daqui não precisa de assinatura;
- não altera os PDFs nem o SPED do mês anterior: só lê e grava arquivos novos;
- não lança nota de **pessoa física**: elas aparecem no Excel como "Fora: PF", para você conferir.

---

## O que você precisa

| O quê | De onde |
|---|---|
| **Pasta com as DANFSe** do mês (PDF) | as notas emitidas, como baixadas (layout nacional) |
| **SPED do mês anterior** (`.txt`) | o arquivo do mês anterior: ele é o "molde" dos registros que não mudam |
| **Cadastro de clientes** (`clientes.json`) | a lista com o código de cada tomador; o programa lembra o último escolhido |
| **Pasta de saída** | onde gravar o SPED novo e o Excel (o programa lembra a última) |

Para toda a equipe usar a **mesma lista de códigos**, guardem o cadastro numa pasta da rede (sugestão: `CONCILIAÇÕES 2026\Automações\Dados\EFD Contribuições\clientes.json`) e todos escolham esse mesmo arquivo. O programa lê e atualiza o arquivo sozinho: **não edite à mão**.

---

## Passo a passo

1. No menu, em **FISCAL**, clique em **EFD Contribuições**.
3. Em **Pasta com as DANFSe**, escolha a pasta das notas do mês. Confirmação: *"52 PDF(s) na pasta"*.
4. Em **SPED do mês anterior**, escolha o `.txt`. Confirmação: *"SPED de 08/2026 · 44 clientes · 49 notas"*. A **competência** do novo SPED é preenchida com o mês seguinte; confira ou digite (MM/AAAA).
5. Em **Cadastro de clientes**, escolha o `clientes.json` (só na primeira vez: depois o programa lembra). Confirmação: *"44 clientes"*. Se ficar vermelho (*"Sem acesso à pasta…"*, *"não foi encontrado"*), confira a rede ou escolha o arquivo de novo: sem o cadastro não dá para gerar.
6. Escolha a **pasta para salvar**.
7. Clique em **Gerar SPED**. Se o programa precisar de você, ele pergunta antes de gravar (veja abaixo).
8. Copie o `SpedEPC_gerado_MM_AAAA.txt` para a máquina remota e importe no EFD Contribuições.

**Primeira vez:** copie o `clientes.json` da aplicação antiga para a pasta da rede e escolha essa cópia no cartão (os códigos continuam os mesmos). **Não tem cadastro nenhum?** Escolha o SPED do mês anterior e clique em **Não tenho o cadastro: criar a partir do SPED anterior**: o programa monta a lista com os clientes do SPED e pergunta onde guardar o arquivo (ele é criado quando você gerar o SPED).

---

## Quais notas entram no SPED

Cada PDF termina com uma **situação** (coluna Situação do Excel):

| Situação | Quando | Entra? |
|---|---|---|
| **No SPED** | pessoa jurídica, lida, datas certas | Sim |
| **Fora: PF** | o tomador é pessoa física | Não |
| **Fora: competência ≠ emissão** | o mês da competência da NFS-e é diferente do mês da data de emissão | Não, com aviso |
| **Fora: emissão fora do mês** | a nota foi emitida fora do mês do SPED que está sendo gerado | Não, com aviso |
| **Fora: repetida** | o mesmo número de NFS-e em dois PDFs, com o mesmo tomador e o mesmo valor: entra uma vez só | A cópia não, com aviso |
| **Fora: não lido** | o PDF não pôde ser lido (o motivo vai na Observação) | Não |
| **No SPED (incluída à mão)** | ficou fora por causa das datas, mas você marcou para incluir (veja abaixo) | Sim |

**Incluir uma nota que ficou fora pelas datas:** ao clicar em Gerar SPED, se houver notas fora por *competência ≠ emissão* ou *emissão fora do mês*, abre a janela **"Notas fora do SPED pelas datas"**. Marque as que devem entrar mesmo assim e clique em **Continuar** (as desmarcadas continuam fora; **Cancelar geração** não grava nada). A nota entra com a data de emissão dela — o programa da Receita pode avisar "data fora do período", o que não impede a entrega. Notas de PF, repetidas ou não lidas não podem ser incluídas.

## Quando o programa para ou pergunta

| O que aparece | O que fazer |
|---|---|
| *"N PDF(s) não puderam ser lidos… Gerar o SPED sem eles?"* | **Sim** gera sem eles (ficam "Fora: não lido"); **Não** cancela. Se for uma nota de verdade, baixe o PDF de novo |
| Janela **"Código IBGE dos clientes novos"** | O cliente é novo e o PDF não trouxe o código do município (o EFD não aceita sem). Digite os 7 números (ex.: 3516200); o código fica no cadastro |
| *"NFS-e … aparece em mais de um PDF com tomador ou valor diferente"* | Deixe só o PDF certo na pasta e gere de novo |
| *"Nenhuma nota para o SPED"* | Todas ficaram fora: veja a situação de cada uma |
| *"N PDF(s) com prestador de CNPJ diferente dos outros"* | Algum PDF não é da Fundação (ou é de outra unidade). Em **Ver avisos** aparecem o arquivo, o CNPJ e o nome do prestador; a coluna **CNPJ do prestador** do Excel mostra todos. A nota não é tirada do SPED por isso: confira e, se não for da Fundação, tire o PDF da pasta e gere de novo |
| *"O cadastro de clientes foi alterado por outra pessoa…"* | Alguém gerou ao mesmo tempo. Nada foi gravado: clique em Gerar SPED de novo |

## O resultado

Na tela: **Notas no SPED**, **Fora do SPED** e **Clientes novos**, a receita do mês (a mesma do M400/M800), quantos PDFs em cada situação e os avisos.

Arquivos na pasta de saída:

- **`SpedEPC_gerado_MM_AAAA.txt`** — o arquivo para importar. Se já existir um com o mesmo nome, o novo ganha `_2`, `_3`... (nada é apagado). Antes de gravar, o programa confere todos os contadores do arquivo: se algo não fechar, ele não grava.
- **`Conferencia_EFD_MM_AAAA_HHhMM.xlsx`** — abas **Notas** (cada PDF com a situação, o CNPJ do prestador e os totais: no SPED, PF e fora), **Clientes novos** (código, nome, CNPJ e Código IBGE, e se o IBGE veio do PDF ou foi digitado) e **Avisos**.

Cliente novo ganha o **próximo código** do cadastro. Antes de atualizar o cadastro, o programa guarda uma cópia do anterior na pasta `copias`, ao lado do `clientes.json`.

## Avisos que podem aparecer no programa da Receita

- **Erro "Código do Município"** no 0150: não deve acontecer, porque o programa não gera sem o Código IBGE dos clientes novos.
- **"Uma instância anterior da aplicação está em execução"**: é uma sessão antiga do EFD Contribuições travada na máquina remota (ou outra pessoa usando). Veja o Gerenciador de Tarefas antes de finalizar qualquer processo.
