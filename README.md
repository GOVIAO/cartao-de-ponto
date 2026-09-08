# Cartão de Ponto — Quick Filler

Aplicação web para envio, processamento, revisão e exportação de cartões de ponto e holerites.

## Rodar

```bash
docker compose up --build
```

Abra `http://localhost:8000`.

A implementação segue o contrato HTTP do desafio e preserva valores `_raw`, marca incertezas com `?` e calcula avisos derivados.