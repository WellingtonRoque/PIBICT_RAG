# Assistente RAG — Vestibular Fatec Indaiatuba

Projeto de Iniciação Científica (PIBICT/CPS 2026/2027). O objetivo é desenvolver e avaliar
uma arquitetura RAG (geração aumentada por recuperação) que responda dúvidas de candidatos
ao Vestibular usando apenas documentos oficiais, sempre indicando a fonte (documento e página).

- Bolsista: Vicenzo Cirilo
- Orientador: Prof. Dr. Wellington Roque

## Situação

| Etapa | Situação |
|---|---|
| 1. Ambiente | Concluída (teste real do Claude pendente, aguardando a chave da API) |
| 2. Ingestão e chunking | Próxima |
| 3 a 8 | A fazer |

## Tecnologias

Python 3.12 · PostgreSQL + pgvector no Supabase · API do Claude (SDK `anthropic`) ·
PyMuPDF · sentence-transformers · FastAPI · React (Vite) no Vercel.
As bibliotecas entram no `requirements.txt` à medida que cada etapa começa.

## Pré-requisitos

- Windows com Python 3.12 e Git
- Projeto no Supabase com a extensão `vector` ativada
- Chave da API do Claude (opcional por enquanto: sem ela, o teste do Claude é pulado)

## Instalação

No PowerShell:

```powershell
git clone https://github.com/WellingtonRoque/PIBICT_RAG.git
cd PIBICT_RAG
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

No `.env`, preencha:

- `DATABASE_URL`: connection string do Supabase (Connect → Session pooler, porta 5432).
  Caracteres especiais da senha precisam ser codificados (ex.: `@` vira `%40`).
- `ANTHROPIC_API_KEY`: chave da API do Claude.

O `.env` guarda segredos e **nunca** vai para o Git (já está no `.gitignore`).

Se a ativação do venv for bloqueada pela política de execução, rode
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` e ative de novo.

## Teste do ambiente

Com o venv ativo, na raiz do projeto:

```powershell
python tests/teste_ambiente.py
```

Saída esperada (sem a chave do Claude):

```
[OK]     Banco: conectado (PostgreSQL 17.x)
[OK]     Extensão vector: versão 0.8.x; distância de teste = 1.0
[PULADO] Claude: ANTHROPIC_API_KEY ausente ou com valor de exemplo (...)
```

O script termina com código 1 se algum item falhar. "PULADO" não conta como falha.

## Estrutura

```
data/raw/         PDFs oficiais (versionados) + FONTES.md (origem e data de cada arquivo)
data/processed/   trechos extraídos, gerados pelo código (não versionados)
src/              código do pipeline (ingestão, indexação, recuperação, geração, API)
avaliacao/        perguntas com gabarito e scripts de métricas
tests/            testes
docs/diario.md    diário de desenvolvimento e pendências
```
