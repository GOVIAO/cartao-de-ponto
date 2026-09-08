# Processo de IA

## Ferramentas usadas
- ChatGPT: apoio na arquitetura, implementação inicial e revisão do contrato.
- GitHub: armazenamento do código e versionamento.

## Pontos corrigidos
1. A primeira tentativa de criação de arquivo pela API do GitHub falhou porque o repositório já tinha um commit inicial e o endpoint exigia SHA.
2. A estratégia foi alterada para blobs + árvore + commit, preservando o histórico existente.
3. A documentação foi alinhada ao contrato literal do desafio, incluindo endpoints e regras de incerteza.

## Revisão manual
A estrutura foi simplificada para manter o ciclo completo: upload, processamento, revisão e exportação. O extrator de holerite ainda precisa de testes com os PDFs de exemplo.

## Decisões abertas
- OCR local evita enviar documentos com PII a terceiros, mas depende das ferramentas do container.
- Memória simplifica o protótipo e reduz retenção, mas não atende alta disponibilidade.
- O próximo passo de qualidade é validar os exemplos reais e criar testes de precisão por campo.

## Riscos
O que quebra primeiro em produção é a extração de layouts desconhecidos e a concorrência de processamento OCR. A solução deve responder com incerteza em vez de inventar dados.
