# Imprimir PDFs — instruções de uso

## O que o módulo faz (e o que não faz)

**Faz:** conta quantas folhas você vai precisar e manda vários PDFs para a impressora de uma vez, sem abrir um por um.

**Não faz:** não altera os PDFs, não abre o Acrobat nem nenhuma outra janela e não lê nem grava planilha.

---

## Passo a passo

1. No menu, em **FERRAMENTAS**, clique em **Imprimir PDFs**.
2. Clique em **Escolher pasta** (pega todos os PDFs da pasta, sem as subpastas) ou em **Escolher PDFs** (só os arquivos que você marcar na janela; segure **Ctrl** para escolher vários). Os botões já abrem na última pasta usada. Uma escolha nova substitui a lista.
3. Confira a lista: cada PDF aparece com uma caixinha e a quantidade de folhas. Desmarque o que não quer imprimir (ou use **Desmarcar todos** e marque só alguns).
   - Um PDF com **2 ou mais páginas** mostra embaixo do nome uma caixinha para cada página (*Pág. 1*, *Pág. 2*…). Desmarque as páginas que não quer, ou clique em **Só a 1ª** para imprimir só a primeira (**Todas** volta todas). À direita aparece, por exemplo, *"1 de 2 folhas"*.
4. À direita, veja o número **Folhas para colocar na impressora** e coloque esse papel na impressora.
5. Confira a **impressora** (o programa lembra da última escolhida; na primeira vez, usa a padrão do Windows).
6. Clique em **Imprimir N folhas** e confirme. Espere a mensagem *"N folhas mandadas para … às hh:mm"*.
7. Logo abaixo, o programa mostra **como a impressão está na fila** e vai atualizando sozinho por até 2 minutos: *Imprimindo*, *aguardando a vez* (com quantas impressões há na frente) e, no fim, *"Saiu da fila: já foi para a impressora"*. Se ela ficar **pausada**, com **erro** ou **sem papel**, a linha fica **vermelha** e diz o que fazer.

**Limpar tudo** esvazia a lista; a pasta e a impressora ficam lembradas.

---

## Como ele imprime

- **Um lado só, uma página por folha**, mesmo que a impressora esteja com frente e verso ligado. Se precisar de frente e verso, imprima pelo Acrobat e escolha na impressora.
- **Tudo numa impressão só:** na fila da impressora aparece um bloco só, por exemplo *"Central de Conciliações – 16 PDFs (18 folhas)"*. Se outra pessoa mandar algo ao mesmo tempo, as folhas dela saem antes ou depois das suas, nunca no meio.
- **Na ordem da lista**, que é a mesma do Explorador do Windows (o mesmo arquivo escolhido duas vezes entra uma vez).
- Página deitada sai deitada; página maior que a folha é reduzida para caber.
- Todos os PDFs são abertos antes de começar: se um não abrir, nada vai para a fila. Um erro no meio cancela a impressão inteira.

---

## A fila da impressora

O botão **Ver fila da impressora** abre a janela do Windows com tudo o que está na fila da impressora escolhida. A sua impressão aparece como *"Central de Conciliações – 16 PDFs (18 folhas) – 10:42:05"* (com o horário em que foi mandada). Clicando com o botão direito nela:

- **Continuar:** se ela estiver *Pausada*;
- **Reiniciar:** manda de novo para a impressora;
- **Cancelar:** tira da fila. Uma impressão travada na frente às vezes segura as outras: cancelar libera as de trás.

A mesma janela também abre por **Iniciar → Configurações → Bluetooth e dispositivos → Impressoras e scanners → (a impressora) → Abrir fila de impressão**.

---

## Se algo der errado

| Aviso | O que fazer |
|---|---|
| PDF em vermelho na lista ("PDF protegido por senha", "não foi possível abrir o PDF…") | Esse arquivo não imprime. Abra-o no Acrobat para ver o que há com ele; os outros imprimem normalmente |
| "Nenhuma impressora encontrada neste computador" | Instale a impressora no Windows e abra o programa de novo |
| "A impressão está PAUSADA na fila…" (linha vermelha; na fila do Windows aparece **"Suspenso"**) | O mais comum é a sua conta ter atingido o **limite de impressões (cota)** do programa de controle da empresa: fale com o **TI**. Se não for isso, clique em **Ver fila da impressora**, clique com o botão direito na sua impressão e em **Continuar**; se não andar, **Cancele** e mande de novo |
| "… a impressora está SEM PAPEL" / "DESLIGADA" / "precisa de atenção" | Veja o visor da impressora; resolvido, a impressão continua sozinha |
| "A impressora … não aceitou a impressão" / "parou de responder no meio da impressão" | A impressão foi cancelada. Confira na impressora se alguma folha chegou a sair, veja se ela está ligada e tente de novo |

Fechar o programa no meio de uma impressão: ele pergunta antes.
