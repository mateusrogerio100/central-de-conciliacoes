# Manutenção — para quem for programar na Central

Esta parte é para um programador que nunca viu o projeto. Ela dá o mapa; os detalhes estão nos
documentos da pasta do projeto (lista no fim).

## O que é o programa

A Central de Conciliações é um programa de janela (Python 3.14 + customtkinter) que reúne as automações
da área contábil da Fundação Hospital Exemplo. Cada item do menu é um **módulo**:
uma conciliação ou ferramenta que lê relatórios exportados do Tasy, das prefeituras ou dos bancos e grava
uma planilha (ou um `.txt` de importação). O usuário recebe um `.exe` único, sem precisar de Python.

Os módulos vieram de quatro origens: três programas antigos (Bancos, Clientes CMD, Subvenções), módulos
escritos já dentro da Central (Serviços Tomados, Estoque, Conferência de NF) e o programa Conciliações
AMES (Conferência ISS, Fornecedores, Rescisões, Honorários Médicos, Imobilizado e Imprimir PDFs, na
versão 1.4.0). Em todos os casos migrados, a regra foi **mudar a casa, nunca a regra de negócio**: os
testes do programa original passam aqui com os mesmos resultados.

## Preparar o computador

1. Instale o **uv** (<https://docs.astral.sh/uv/>), que instala o Python, e o **Git**.
2. Copie a pasta do projeto **inteira, inclusive `exemplos\`** (os arquivos reais dos testes, que não
   ficam no git).
3. No PowerShell, na pasta do projeto:
   - `uv venv .venv --python 3.14`
   - `uv pip install --python .venv\Scripts\python.exe -r requirements.txt`
   - `.\.venv\Scripts\python.exe -m pytest` — todos os testes (uns 8 minutos)
   - `.\.venv\Scripts\python.exe main.py` — abre o programa

Neste tipo de computador o comando `python` do Windows costuma abrir a Microsoft Store: use sempre o
Python do `.venv`. As versões das bibliotecas são fixas no `requirements.txt` (as mesmas dos programas
originais, para os resultados não mudarem).

## Como o código é organizado

| Pasta | O que tem |
|---|---|
| `main.py` | abre a janela |
| `central\` | a "casca": janela, menu, visual, peças de tela, preferências, segundo plano. **Não tem regra de negócio** |
| `modulos\<chave>\` | um pacote por módulo: a lógica, as telas e os textos dele |
| `testes\` | uma pasta por módulo, mais `central\` e `manual\` |
| `exemplos\` | arquivos reais usados pelos testes — **fora do git** (dados de pessoas e fornecedores) |
| `manual\` | este manual: exemplos fictícios, prints e montagem do PDF |
| `recursos\` | ícone do `.exe` e o logo da Hospital Exemplo |

**O contrato de um módulo** (detalhe na seção 4 do `ESPECIFICACAO.md`):

- `__init__.py` declara `MODULO = InfoModulo(chave, nome, descricao, contexto, icone, criar_painel)`;
- `painel.py` monta a tela com abas (`PainelComAbas`); `telas\` tem uma tela por aba de trabalho;
- `processamento.py` é a **única porta** que as telas chamam; o trabalho pesado recebe uma função
  `progresso(texto, fração)` e roda em segundo plano (`central\segundo_plano.py`);
- `INSTRUCOES_DE_USO.md` é o texto da aba "Instruções de uso" (e deste manual);
- `ESPECIFICACAO_*.md` tem as regras de negócio e o gabarito do módulo.

A lista do menu fica em `central\registro.py` (`SECOES`). Um módulo que não carrega aparece no menu com
a mensagem de erro e não derruba os outros.

## Regras da casa

As três primeiras são conferidas por testes em `testes\central\`; as outras, pelos testes de cada módulo.

- **Um módulo nunca importa outro.** O que dois módulos precisam em comum é copiado para dentro de cada
  um (testes de Rescisões e Honorários conferem que a cópia do código de Fornecedores continua igual).
- **A lógica não importa a interface**; só `painel.py` e `telas\` usam tkinter.
- **Nenhuma cor ou fonte escrita direto numa tela**: tudo vem de `central\tema.py` e das peças de
  `central\componentes.py` (regras visuais no `GUIA_VISUAL.md`).
- **Os arquivos de entrada nunca são alterados**: o programa só grava na pasta de saída e se recusa a
  gravar por cima de uma entrada.
- **Nada some em silêncio**: toda linha de entrada aparece no relatório com o que aconteceu; um arquivo
  com problema vira aviso e os outros continuam.
- **Dinheiro em `Decimal`** nos módulos que já usam; colunas localizadas pelo título, não pela letra.
- Código, mensagens e nomes em **português**.

## Testes

- `pytest testes\<módulo>` roda só um módulo; os módulos são independentes. Mexeu em `central\`? Rode
  tudo.
- Os testes de gabarito usam os arquivos reais de `exemplos\`. **Sem essa pasta eles são pulados**, não
  quebram (`pytest -rs` mostra o motivo). Com ela, nenhum teste deve ser pulado.
- **Nunca ajuste um gabarito ou um valor esperado só para o teste passar.** Se um resultado divergir,
  descubra a causa: o gabarito foi conferido à mão pela contabilidade.
- `testes\manual\` roda os exemplos fictícios deste manual em todos os módulos; funciona em qualquer
  computador, mesmo sem `exemplos\`.

## Dados sensíveis

Os relatórios têm nomes de pessoas, fornecedores, CPFs e CNPJs reais. **Nunca vão para o git**:
`exemplos\`, planilhas (`.xlsx`, `.xls`), PDFs, `.csv`, os `.txt` gerados, pastas de saída, `build\`,
`dist\` (o `.gitignore` cuida disso, e um teste confere). Os casos do gabarito que citam alguém real ficam
num `casos_reais.json` dentro de `exemplos\<módulo>\`, e os testes leem de lá. Nos testes, no código e na
documentação, só nomes fictícios.

## Colocar um módulo novo

1. Escreva antes a especificação (`modulos\<chave>\ESPECIFICACAO_<NOME>.md`): entradas, regras, saída e
   um gabarito conferido à mão.
2. Crie a pasta `modulos\<chave>\` seguindo o contrato acima e os testes em `testes\<chave>\`.
3. Acrescente a chave em `central\registro.py`, na seção certa do menu.
4. Escreva o `INSTRUCOES_DE_USO.md`, o exemplo fictício em `manual\ficticios\<chave>.py` (o teste de
   `testes\manual\` exige um por módulo) e acrescente o `--add-data` das instruções no comando do `.exe`.
5. Atualize `README.md`, `MANUAL_DE_USO.md` e `GUIA_DE_MANUTENCAO.md`.

Bons modelos: Fornecedores (simples) e Conferência ISS (várias abas). O `GUIA_DE_MANUTENCAO.md` tem um
prompt pronto para fazer isso com o Claude Code.

## Gerar o .exe

O comando completo do PyInstaller está no `README.md` (seção 3) e no `CLAUDE.md`. Três cuidados:

- `--collect-submodules modulos` é obrigatório: os módulos são carregados pelo nome e o PyInstaller não
  os enxerga sozinho;
- cada módulo precisa do `--add-data` do seu `INSTRUCOES_DE_USO.md`;
- **suba a versão** (`VERSAO` em `central\__init__.py`, aparece no pé do menu): módulo novo = número do
  meio (1.4.0 → 1.5.0); ajuste = último número (1.4.0 → 1.4.1).

Teste o `.exe` numa pasta fora do projeto antes de entregar.

## Onde o programa guarda as escolhas do usuário

Tudo em `%APPDATA%\CentralConciliacoes\` (fora do projeto): o modo claro/escuro
(`preferencias.json`), as pastas e escolhas lembradas de cada módulo (`<chave>.json`), a cidade dos
prestadores do Serviços Tomados (`escrituracao_tomados\prestadores.json`) e a configuração da EST-02 do
Estoque (`configuracoes\`). As preferências do programa antigo Conciliações AMES
(`%APPDATA%\ConferenciaISSRB\config.json`) são só **lidas**, como valor inicial. Apagar qualquer um
desses arquivos não quebra o programa: ele volta aos valores padrão.

## Atualizar este manual

O manual é gerado, não editado à mão. Mudou uma tela ou um texto de instruções?

1. `.\.venv\Scripts\python.exe -m manual.tirar_prints` — abre a Central com os arquivos fictícios de
   `manual\ficticios\` e fotografa cada tela (não mexa no mouse enquanto roda);
2. `.\.venv\Scripts\python.exe -m manual.montar_manual` — junta as Instruções de uso de cada módulo, os
   prints e esta parte num PDF (`manual\saida\`), usando o Microsoft Edge.

Mudou o formato de um relatório que um módulo lê? Ajuste o gerador fictício dele: o teste de
`testes\manual\` avisa quando um exemplo deixa de funcionar. Os arquivos fictícios podem ser gerados numa
pasta para testar o programa à mão: `python -m manual.gerar_exemplos`.

## Documentos do projeto

| Documento | Para quê |
|---|---|
| `README.md` | visão técnica: arquitetura, bibliotecas, `.exe`, resumo das regras, testes |
| `ESPECIFICACAO.md` | a fonte da verdade: estrutura, contrato dos módulos, decisões tomadas |
| `modulos\<chave>\ESPECIFICACAO_*.md` | as regras de negócio e o gabarito de cada módulo |
| `GUIA_DE_MANUTENCAO.md` | casos comuns (relatório que mudou, banco novo, mês novo nos testes...) com prompts prontos para o Claude Code |
| `GUIA_VISUAL.md` | cores, fontes, medidas e o layout das telas |
| `CLAUDE.md` | as regras que o Claude Code segue neste projeto |
| `MANUAL_DE_USO.md` | o manual de quem usa (a primeira parte deste PDF) |

O projeto foi escrito com o **Claude Code**, que lê o `CLAUDE.md` sozinho; o `GUIA_DE_MANUTENCAO.md`
tem os pedidos prontos para as manutenções mais comuns. Com ou sem ele, valem as mesmas regras: uma
mudança por vez, testes passando e documentação atualizada no mesmo commit.
