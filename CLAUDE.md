# Assistente RAG — Vestibular Fatec Indaiatuba

Projeto de Iniciação Científica (PIBICT/CPS 2026/2027) do bolsista Vicenzo Cirilo,
orientado pelo Prof. Dr. Wellington Roque. Objetivo: desenvolver e avaliar uma
arquitetura RAG que responda dúvidas de candidatos ao Vestibular usando apenas
documentos oficiais, sempre indicando a fonte (documento e página).

## Quem está programando

O bolsista está aprendendo. Ele precisa entender e conseguir explicar todo o código,
porque vai descrevê-lo no relatório e no artigo científico. Velocidade importa,
mas nunca à custa do entendimento.

## Modo de trabalho (obrigatório)

- Antes de escrever código, explique o plano (arquivos, o que cada um faz e por quê)
  e espere aprovação.
- Trabalhe em passos pequenos: um módulo ou função por vez.
- Depois de cada mudança, explique em português simples o que foi feito e por quê.
- Prefira código simples e legível a soluções "espertas". Comente o que não for óbvio.
- `src/recuperacao.py` e o prompt de `src/geracao.py` são escritos pelo bolsista:
  não os escreva sem pedido explícito; ajude explicando e revisando.
- Não introduza bibliotecas ou tecnologias fora da stack abaixo sem perguntar.
- Não faça commits, push nem alterações destrutivas (apagar dados, recriar o banco)
  sem pedir.
- Não afirme que algo funciona sem ter executado e mostrado o resultado.
- Ao final de cada etapa, sugira 3 a 4 linhas para o diário de desenvolvimento
  (`docs/diario.md`): o que foi feito, como funciona, o que deu errado.

## Stack decidida (não alterar sem aprovação)

| Peça | Escolha |
|---|---|
| Linguagem | Python 3.11+ |
| Leitura de PDF | PyMuPDF |
| Embeddings | BGE-M3 ou multilingual-E5 (via sentence-transformers), rodando em CPU — escolha final após teste da Etapa 3 |
| Banco | PostgreSQL + pgvector no Supabase (sem Docker), índice HNSW; trechos e logs no mesmo banco |
| LLM | API do Claude, modelo `claude-sonnet-5-5` (SDK `anthropic`) |
| API | FastAPI, rota `POST /perguntar` |
| Interface | React (Vite) hospedado no Vercel desde o MVP; consome a API, com CORS liberado só para o domínio do Vercel |
| Pipeline | Código próprio, sem LangChain ou LlamaIndex |

Ambiente de desenvolvimento: Windows, sem GPU dedicada. O frontend exige Node.js (LTS).

## Estrutura do repositório

```
PIBICT_RAG/              (raiz do repositório)
├── data/raw/            PDFs originais (não versionar se forem grandes)
├── data/processed/      trechos extraídos (JSON)
├── src/
│   ├── ingestao.py      PDF → trechos com documento, página e posição
│   ├── indexacao.py     trechos → embeddings → pgvector
│   ├── recuperacao.py   pergunta → top-5 trechos (escrito pelo bolsista)
│   ├── geracao.py       pergunta + trechos → resposta com fontes; modo sem recuperação (Cenário A)
│   ├── logs.py          registro anonimizado das interações
│   └── api.py           FastAPI, orquestra tudo
├── frontend/            interface em React (Vite), publicada no Vercel
├── avaliacao/           perguntas com gabarito e scripts de métricas
├── tests/
├── docs/diario.md       diário de desenvolvimento
├── .env                 chaves e senhas (NUNCA versionar)
└── README.md            como instalar e executar
```

## Regras fixas da arquitetura

- O mesmo modelo de embedding é usado para documentos e perguntas.
- Todo trecho guarda documento de origem, página e posição.
- O prompt instrui o LLM a responder só com base nos trechos, citar a fonte e dizer
  quando não encontrou a resposta.
- Chunking do MVP: tamanho fixo, ~400 palavras, 15% de sobreposição.
- Busca do MVP: apenas densa, top-5. Busca híbrida e reranking só após medição.
- multilingual-E5 exige os prefixos `query: ` (pergunta) e `passage: ` (trechos).
- O Cenário A (só LLM) e o Cenário B (RAG) usam o mesmo modelo e a mesma configuração.

## Segurança e LGPD

- Chaves, senhas e tokens apenas no `.env`, carregados por variáveis de ambiente.
- `.env` sempre no `.gitignore`.
- Logs sem nome, e-mail, CPF ou telefone: mascarar esses padrões na pergunta antes
  de salvar. Sessão identificada só por ID anônimo.

## Campos de log (a validar com o projeto da Jasmine)

`id`, `data_hora`, `sessao`, `pergunta` (mascarada), `resposta`, `fontes`,
`pontuacoes_busca`, `tempo_recuperacao_ms`, `tempo_geracao_ms`, `modelo`,
`versao_prompt`, `categoria` (preenchida na análise), `util` (opcional, sim/não).

## Contrato da API

```json
// POST /perguntar — requisição
{ "pergunta": "Quem tem direito à isenção da taxa?" }

// resposta
{
  "resposta": "...",
  "fontes": [{ "documento": "Edital Vestibular 1/2027", "pagina": 8, "trecho": "..." }],
  "id_interacao": "uuid",
  "tempo_ms": 2100
}
```

## Etapas do MVP (até 18/12/2026)

1. Ambiente: Git, venv, projeto no Supabase com a extensão vector, `.env`, script de teste (banco + Claude)
2. Ingestão e chunking
3. Teste de embeddings (BGE-M3 × E5, 20 perguntas, Recall@5 e MRR)
4. Indexação e busca
5. Geração (incluindo modo sem recuperação)
6. API e logs
7. Interface React (Vite) no Vercel, com túnel para o back-end local nos testes
8. Avaliação inicial (30 perguntas, Cenário A × B) e README

Cada etapa só termina quando seu critério de pronto foi verificado e mostrado.

## Regras de Git (o bolsista valida tudo antes)

- `main` é a versão validada e é o que o Vercel publica. Nunca trabalhe direto na `main`.
- Cada etapa em uma branch própria: `etapa-N-descricao` (ex.: `etapa-1-ambiente`).
- Commits pequenos, um assunto por commit, mensagem em português no padrão:
  `feat:` (funcionalidade), `fix:` (correção), `docs:` (documentação),
  `test:` (testes), `refactor:` (reorganização sem mudar comportamento), `chore:` (configuração).
  Ex.: `feat: extrai texto dos PDFs com número da página`.
- **Antes de cada commit:** mostre `git status`, um resumo do `git diff`, a mensagem
  proposta, e **espere o bolsista aprovar**.
- **Antes de cada push:** liste os commits que vão subir e **espere aprovação**.
- **Merge na `main` (que dispara o deploy no Vercel):** só depois de a etapa cumprir o
  critério de pronto, com os testes mostrados, e com aprovação explícita do bolsista.
- Nunca: commitar `.env`, chaves ou senhas; `git push --force`; reescrever histórico já
  enviado; apagar branches; alterar configurações do repositório remoto.
- Antes de commitar, confira se nenhum arquivo sensível ou grande (PDFs pesados,
  modelos baixados, `node_modules/`, `.venv/`) entrou no `git status`.

## Resumo automático do desenvolvimento (obrigatório)

Ao final de **toda resposta** em que algo foi desenvolvido ou executado, termine com o
resumo abaixo, sem esperar pedido. O foco é o **sistema**: o que foi construído, o que
funcionou, o que falhou e o que o bolsista precisa validar. O resumo é **acumulado**
(cobre a sessão inteira até aquele momento), para que o bolsista copie só o mais recente.
Respostas que só tiram dúvidas ou apresentam um plano ainda não executado não precisam
de resumo. Seja curto: uma linha por item.

```
## Resumo do desenvolvimento — [data] · Etapa [N] · branch [nome]

**Desenvolvido:**
- [componente/arquivo] — [o que faz agora]

**Funcionou ✅**
- [o quê] — evidência: [comando/teste → resultado real]

**Não funcionou / pendente ❌**
- [o quê] — [erro ou motivo] — [situação: investigando / bloqueado / adiado]

**Precisa da sua validação ⚠️**
- [commit, push, merge, decisão técnica, teste manual ou configuração que depende do bolsista]

**Git:** [commits feitos (hash curto + mensagem) · push: sim/não · merge na main: sim/não]

**Próximo passo:** [1 linha]
```

Não invente resultados: o que não foi executado vai em "pendente" como "não testado".
As linhas do diário de desenvolvimento são sugeridas à parte, só ao fim de cada etapa.
