# Diário de desenvolvimento

Registro do que foi feito em cada etapa, como funciona e o que deu errado.
A seção "Pendências" fica no topo e é atualizada sempre que algo é resolvido ou surge.

## Pendências

- [ ] **Testar a chamada real ao Claude** quando a chave da API chegar (prevista até o
      início de dezembro de 2026). Colocar a chave no `.env` e rodar
      `python tests/teste_ambiente.py`: o Claude deve passar de `[PULADO]` para `[OK]`.
      Até lá, o critério de pronto da Etapa 1 ("banco + Claude") está parcial.
- [x] **Etapa 2:** `src/ingestao.py` deve criar `data/processed/` se a pasta não existir
      (ela não é versionada). Feito em 26/11/2026 (`mkdir(parents=True, exist_ok=True)`).
- [ ] **Antes da Etapa 8:** gerar `requirements-lock.txt` com `pip freeze`, para fixar também
      as dependências indiretas.
- [ ] **PC de casa:** o histórico do Git foi reescrito em 25/11/2026. Não usar `git pull` no
      clone antigo; clonar o repositório de novo e copiar o `.env`.

## Ideias futuras

- **Padrões de remoção configuráveis por coleção** (26/11/2026): hoje a ingestão só remove
  linhas que se repetem em mais da metade das páginas de um documento, e por isso os rodapés
  do Diário Oficial ficam nas portarias de 1 página. Uma opção é listar no `manifesto.yaml` de
  cada coleção padrões de linhas a remover (ex.: a assinatura digital do DOE), mantendo o
  código livre de regras específicas de um cliente.

## Etapa 1 — Ambiente (18/11 a 25/11/2026)

- **Feito:** estrutura de pastas, `.gitignore`, venv com Python 3.12, `requirements.txt` com
  versões fixas, `.env.example` e `tests/teste_ambiente.py`.
- **Como funciona:** o teste lê o `.env`, conecta ao Supabase pelo Session pooler, confere a
  extensão vector (versão 0.8.2) calculando uma distância entre dois vetores (deu 1.0) e chama
  o Claude, ou pula essa parte com aviso quando a chave ainda é o valor de exemplo.
- **Decisões:** PDFs oficiais versionados em `data/raw/` (reprodutibilidade), com fontes em
  `FONTES.md`; nome do modelo do Claude no código, não no `.env`.
- **O que deu errado:** a chave da API do Claude não chegou a tempo, e a Etapa 1 foi fechada
  com essa pendência. O histórico do Git precisou ser reescrito para remover uma linha de
  coautoria, o que exigiu refazer clones antigos.
