# Solução

A aplicação segue o fluxo único do desafio: envio, processamento, revisão e exportação para cartão de ponto e holerite. O contrato HTTP obrigatório é implementado em FastAPI. A extração usa texto do PDF quando disponível e tenta OCR com Tesseract quando a camada de texto está ausente.

## Decisões
- Python + FastAPI para uma API simples e tipada.
- Processamento em memória nesta versão inicial, sem persistir documentos com PII.
- Limite de upload de 15 MB e validação de PDF.
- Exportação XLSX, CSV e JSON.
- Incertezas devem permanecer visíveis com `?`; não são substituídas por palpites.

## Retenção e privacidade
Os PDFs não são gravados em disco pela aplicação; os dados processados ficam somente em memória enquanto o processo estiver ativo. Não registrar conteúdo dos documentos nos logs.

## Escopo
A interface e o pipeline inicial estão funcionais para cartões de ponto com texto extraível e possuem fallback de OCR. O extrator de holerite ainda é uma base inicial e deve ser aprofundado para os layouts de exemplo antes de uma entrega final de processo seletivo.
