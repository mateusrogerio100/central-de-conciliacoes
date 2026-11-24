"""Manual em PDF da Central (Etapa 12 da unificação com o Conciliações AMES).

Ferramenta de manutenção, fora do .exe:
- ficticios\\: um gerador de arquivos FICTÍCIOS por módulo, no formato dos relatórios do Tasy e das
  prefeituras (`python -m manual.gerar_exemplos`). Os arquivos saem em exemplos_ficticios\\ (fora do
  git, como toda planilha e PDF); quem precisar deles roda o gerador de novo;
- tirar_prints.py: abre a Central de verdade com esses arquivos e fotografa cada tela;
- montar_manual.py: junta as Instruções de uso de cada módulo, os prints e a parte de manutenção
  num PDF.
"""
