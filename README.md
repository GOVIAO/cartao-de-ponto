# Quick Filler — Cartão de Ponto e Holerite

Aplicação web para o desafio técnico Quick Filler: **enviar PDF → processar → revisar → baixar planilha**.

## O que está implementado

- API FastAPI com o contrato obrigatório:
  - `POST /api/transcricoes`
  - `GET /api/transcricoes/:id`
  - `PUT /api/transcricoes/:id`
  - `GET /api/transcricoes/:id/planilha?formato=xlsx|csv|json`
  - `GET /healthz`
- Processamento assíncrono em background, com status `processando`, `concluido` ou `erro`.
- Extração de texto por página e fallback de OCR local com Tesseract.
- Dois extratores no mesmo pipeline:
  - cartão de ponto: datas e batidas em pares `IN`/`OUT`;
  - holerite: `fields[]` e `bases[]`, preservando valores monetários como strings.
- Interface com PDF visível ao lado da tabela, edição, avisos e salvamento.
- Exportação XLSX com cabeçalho e destaques de problemas; CSV e JSON também disponíveis.
- Limite de upload configurável por `MAX_UPLOAD_MB`.
- CI mínima com compilação e testes.
- Exemplos de planilhas em `exemplos/`, gerados a partir dos PDFs de exemplo fornecidos para esta implementação.

## Como executar

### Docker

```bash
docker compose up --build
```

Abra `http://localhost:8000`.

### Local

```bash
python -m venv .venv
# ative o ambiente virtual
pip install -r requirements.txt
uvicorn backend.app:app --reload
```

Para OCR local, instale Tesseract e Poppler no sistema.

## Segurança e privacidade

Os PDFs não são persistidos em disco pela aplicação. O conteúdo processado fica apenas em memória durante a execução do processo. O OCR é local, sem envio do documento para serviço externo.

A aplicação foi feita para um desafio/protótipo. Para produção real, ainda seriam necessários autenticação/autorização, limites de concorrência, armazenamento seguro com retenção definida, observabilidade sem PII e controles adicionais contra abuso.

## Decisões importantes

A solução é deliberadamente conservadora: quando a leitura não é segura, o dado deve permanecer vazio ou conter `?`, em vez de receber um palpite. Datas impossíveis não são fabricadas.

Consulte `SOLUCAO.md` para decisões, limitações e próximos passos e `PROCESSO.md` para o registro do uso de IA.
