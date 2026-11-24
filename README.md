# Central de Conciliações

**Português** · [English](README.en.md)

Aplicativo de desktop que automatiza as conciliações e conferências mensais da contabilidade de um
hospital filantrópico: lê os relatórios do ERP hospitalar, os extratos bancários e as notas fiscais,
cruza as informações com as regras contábeis e entrega uma planilha Excel pronta para revisão, com
cada divergência explicada.

> Projeto real, em uso diário pela equipe de contabilidade. Este repositório é uma cópia **anonimizada**,
> publicada com autorização: nomes da instituição, das unidades e das cidades, CNPJs, pessoas e
> caminhos de rede foram trocados por dados fictícios. Os documentos internos (especificações e regras
> detalhadas de cada área) não foram publicados.

## O problema

Todo fechamento mensal exigia conferir à mão milhares de linhas entre o ERP, os bancos, as prefeituras
e as notas fiscais: saldo de cada conta bancária × balancete, cada nota × lançamento contábil, cada
venda de cartão × caixa, cada rescisão × folha. O trabalho levava dias, dependia de quem sabia o
caminho e não deixava registro do que foi conferido.

## A solução

Uma única janela com **19 módulos**, um para cada rotina, organizados como o plano de contas:

| Seção | Módulos |
|---|---|
| **Fiscal** | Conferência de notas fiscais (DANFE/DANFSe e XML × lote contábil), checklist de notas de contrato, notas pendentes, escrituração de serviços tomados (arquivo de importação da prefeitura), conferência de ISS de 5 municípios, EFD-Contribuições (SPED) |
| **Conciliações · Ativo** | Bancos (extratos em PDF de vários bancos × balancete), clientes, estoque, imobilizado, crédito de complemento salarial |
| **Conciliações · Passivo** | Fornecedores, rescisões, honorários médicos, planilha de honorários, subvenções e projetos |
| **Receitas** | Convênios |
| **Ferramentas** | Impressão de PDFs em lote, histórico de uso |

Em cada módulo o usuário escolhe os arquivos do mês e clica em um botão. O programa:

1. **lê** os arquivos de entrada (PDF, XML, `.xlsx`, `.xls` e `.csv` do ERP, extratos bancários,
   relatórios de prefeituras), localizando colunas e linhas pelo título, nunca por posição fixa;
2. **aplica as regras** da conciliação, com valores em `Decimal` (sem erro de arredondamento);
3. **grava um Excel** com o resumo, a conciliação linha a linha, as pendências e a lista de arquivos
   lidos. As contagens do resumo são fórmulas: quem corrige uma pendência na planilha vê o resumo
   se ajustar sozinho.

Princípios que valem para todos os módulos:

- **Os arquivos de entrada nunca são alterados**: o programa só grava na pasta de saída.
- **Nada some em silêncio**: todo arquivo e toda linha aparecem no relatório com o que aconteceu.
- **Um arquivo com problema não derruba o processamento**: o erro é registrado e os demais seguem.
- **Divergência é explicada**, não só apontada (ex.: "Líquido: ERP 49,51 × banco 49,50").

## Arquitetura

```
main.py
central/              janela, menu, tema, componentes de tela, registro dos módulos, log de uso
modulos/<nome>/       um pacote por módulo, com o mesmo contrato:
    __init__.py         informações do módulo (nome, seção, ícone, instruções)
    painel.py           só monta a tela (customtkinter) e chama o processamento
    processamento.py    regra de negócio (sem interface gráfica)
    leitores, relatório Excel, configuração...
testes/<nome>/        testes de cada módulo (pytest)
manual/               gera o manual em PDF com prints de dados fictícios
```

- **Módulos independentes**: um módulo nunca importa outro. Um módulo com erro aparece no menu com a
  mensagem do problema, e os demais continuam funcionando.
- **Tela separada da lógica**: `painel.py` só desenha e chama `processamento.py`; a lógica não depende
  de interface, o que permite testá-la inteira.
- **Tela que nunca trava**: leituras demoradas e pastas de rede rodam em segundo plano.
- **Distribuição em um único `.exe`** (PyInstaller) para a equipe, com versão no rodapé.

## Qualidade

- **~1.900 testes automatizados** (pytest) para ~56 mil linhas de código de aplicação.
- **Gabaritos reais**: cada módulo foi validado contra planilhas feitas à mão pela contabilidade, linha
  a linha. Na migração de programas antigos, a regra foi "a saída nova tem de ser idêntica à antiga";
  divergência era investigada, nunca "ajustada para o teste passar".
- **Desenvolvimento por etapas**: cada etapa com especificação, testes e commit próprio.

## Tecnologias

Python 3.14 · customtkinter · openpyxl · pandas · pdfplumber · pypdfium2 · xlrd · Pillow · pytest ·
PyInstaller

## Como rodar

```powershell
uv venv .venv --python 3.14
.\.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt
python main.py        # abre a Central
pytest                # roda os testes
```

Os testes que dependem de arquivos reais do hospital (gabaritos) são pulados automaticamente quando a
pasta de exemplos não existe, que é o caso deste repositório.

## Como foi feito

Desenvolvido por **Mateus Souza**, da contabilidade do hospital, com **assistência de IA (Claude
Code)**. A divisão de papéis:

- **Eu**: levantei cada processo com a equipe, escrevi as especificações e as regras de negócio,
  montei os gabaritos, decidi cada caso duvidoso e validei os resultados com os dados reais.
- **A IA**: escreveu a maior parte do código e dos testes a partir dessas especificações, sempre uma
  etapa por vez, com revisão a cada passo.

Hoje o projeto está sendo migrado, módulo a módulo, para o sistema web da instituição (NestJS +
Next.js), em conjunto com a equipe de TI.

## Aviso

Código publicado para fins de portfólio, com autorização da instituição. Todos os dados deste
repositório são fictícios. As fontes IBM Plex (`central/fontes/`) são distribuídas sob a SIL Open Font License.
