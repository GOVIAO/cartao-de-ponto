# Processo de IA

## Uso

Foi usado ChatGPT como apoio à implementação, revisão do contrato do desafio, criação do código, testes e documentação.

A implementação foi revisada contra o contrato literal do desafio antes de ser atualizada no repositório.

## Iterações relevantes

1. A primeira versão tinha apenas um extrator inicial e não montava os arquivos estáticos corretamente.
2. Os PDFs de exemplo foram usados para descobrir diferenças reais entre layouts:
   - cartão SIPON com `Jornada` separada das batidas;
   - cartão escaneado que exige OCR;
   - holerite com tabela de verbas e resumo;
   - holerite com seção adicional de `ACERTO`.
3. O pipeline foi ajustado para extrair por página, usar OCR apenas quando necessário e preservar a estrutura `pages[]`.
4. Foram adicionados revisão editável, `PUT`, destaques, exportação e testes.
5. O código foi executado localmente e os quatro exemplos fornecidos foram processados.

## Princípio de segurança

Em documentos trabalhistas, precisão é mais importante que preencher tudo. A solução evita completar valores por palpite e mantém a incerteza visível para revisão humana.
