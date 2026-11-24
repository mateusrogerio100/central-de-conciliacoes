# Histórico de uso — instruções de uso

## O que é

A Central anota sozinha cada uso: **quem** (o usuário do Windows), **quando**, em qual **computador** e
**o que** foi feito. Contam como uso:

- abrir a Central;
- processar num módulo (o botão principal: "Conferir mês", "Conferir lote", "Imprimir"...), com o
  resultado (**ok** ou **erro**).

Escolher arquivos ou só trocar de módulo no menu não conta.

Este item do menu junta tudo numa planilha.

## Como as Centrais se encontram

Elas não conversam entre si: cada computador grava o **seu próprio arquivo** numa pasta da rede, um por
mês, por exemplo `2026-10 - CONT-05 - usuario.csv`. Como cada um escreve só no seu, nunca há duas
pessoas mexendo no mesmo arquivo. A pasta é:

`\\servidor-arquivos\contabilidade\CONCILIAÇÕES 2026\Automações\Dados\Log de uso`

Ela é criada sozinha no primeiro uso com a rede no ar.

**Rede fora do ar:** o uso fica guardado no computador e vai para a pasta da rede da próxima vez. A Central
nunca fica esperando a rede.

## Gerar a planilha

1. A **pasta do log de uso** já vem preenchida com a da rede.
2. Escolha a **pasta de saída** (fica lembrada).
3. Clique em **Gerar planilha**. Sai `Historico_de_uso_<data e hora>.xlsx`, sempre um arquivo novo, com:
   - **Resumo por mês:** por mês, cada usuário e cada módulo, quantas vezes foi usado, quantas deram erro e
     o último uso. As aberturas da Central aparecem como "Central (aberturas)".
   - **Por usuário:** computadores, aberturas da Central, usos dos módulos, quais módulos (com quantas vezes),
     primeiro e último uso.
   - **Histórico:** cada uso, linha por linha, do mais recente para o mais antigo. Os usos que deram erro
     ficam em vermelho.
   - **Avisos:** só aparece se algum arquivo da pasta não pôde ser lido.

Na tela aparecem o número de usuários, de usos dos módulos e de aberturas, e uma tabela com os usuários mais
recentes.

O programa só **lê** os arquivos da rede: nunca altera nem apaga nada lá.
