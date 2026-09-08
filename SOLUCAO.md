# Solução

## Arquitetura

Um único pipeline atende os dois tipos de documento:

1. upload do PDF;
2. criação imediata da transcrição com status `processando`;
3. processamento em background;
4. extração de texto por página;
5. OCR local somente nas páginas sem camada de texto;
6. normalização para o contrato do desafio;
7. revisão no navegador;
8. `PUT` das correções;
9. exportação XLSX, CSV ou JSON.

O backend usa Python + FastAPI. O frontend é HTML/CSS/JavaScript sem framework para manter a entrega pequena e fácil de avaliar.

## Extração

### Cartão de ponto

São reconhecidos dois layouts presentes nos exemplos:

- linhas que já trazem `dd/mm/aaaa`;
- o layout SIPON, que imprime o dia do mês e uma coluna `Jornada` separada das batidas.

No SIPON, o primeiro `08:00` da linha é a jornada prevista e não é tratado como batida. As linhas de continuação recebem as batidas seguintes.

### Holerite

O extrator identifica:

- competência `Mês/Ano` ou `Período`;
- linhas de verbas iniciadas por código;
- referência quando há duas colunas numéricas;
- valor monetário como string;
- bases/totais da seção de resumo.

`fields[]` contém apenas verbas. `bases[]` contém bases/totais separados, conforme o contrato.

## OCR

O OCR é feito localmente com Tesseract (`por+eng`) e Poppler. Isso evita enviar documentos trabalhistas para terceiros.

A extração é feita por página para que uma página escaneada não obrigue todo o documento a passar por OCR.

## Incerteza

A regra principal é não inventar. O projeto preserva `time_raw`/`time_hhmm` e os valores monetários como strings. Quando uma leitura não é confiável, a interface deve deixar a incerteza visível para revisão.

## Avisos

Os avisos não entram no JSON como campos extras. São derivados dos próprios dados:

- cartão: batidas ímpares e data não sequencial;
- holerite: página vazia e mês não sequencial;
- `?` também recebe destaque visual.

No XLSX, linhas de atenção recebem destaque amarelo e problemas de sequência/validade recebem destaque vermelho.

## Escopo cortado

Não foi implementada a rastreabilidade visual por coordenadas do PDF, pois é um bônus e aumentaria bastante a complexidade do pipeline.

Também não foi implementado armazenamento persistente. Para um desafio curto, manter os dados em memória reduz retenção de PII e simplifica a operação. Isso não é suficiente para alta disponibilidade.

## Validação

Os quatro PDFs fornecidos como exemplos foram processados localmente para validar os dois tipos e os caminhos de texto/OCR. As planilhas resultantes ficam em `exemplos/`.

Os testes automatizados cobrem o contrato de parsing e a construção básica da planilha.
