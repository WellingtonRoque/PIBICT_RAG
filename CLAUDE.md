# Assistente RAG — Vestibular Fatec Indaiatuba

Projeto de Iniciação Científica (PIBICT/CPS 2026/2027) do bolsista Vicenzo Cirilo,
orientado pelo Prof. Dr. Wellington Roque. Objetivo: desenvolver e avaliar uma
arquitetura RAG que responda dúvidas de candidatos ao Vestibular usando apenas
documentos oficiais, sempre indicando a fonte (documento e página).

## Arquitetura v2: produto multi-cliente

O sistema é um produto que atende vários clientes com o mesmo código. O Vestibular
Fatec Indaiatuba é o **primeiro cliente** (e o caso estudado na pesquisa).

- **Implantação:** hospedagem compartilhada por padrão (todos os clientes no mesmo
  back-end e banco); hospedagem dedicada quando o cliente exigir, com o mesmo código.
- **O que muda por cliente:** só os documentos (coleções) e a configuração do
  assistente. Nada fixo do Vestibular no código (nomes, textos, regras ou caminhos
  vêm do banco ou do YAML do assistente).
- **Isolamento:** um cliente nunca vê dados de outro. Garantido por Row Level Security
  e por filtro explícito de `cliente_id` em toda consulta (ver "Modelo de dados").

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
- Não faça alterações destrutivas (apagar dados, recriar o banco) sem pedir. Para Git,
  valem as regras da seção "Regras de Git": você só orienta, o bolsista executa.
- Não afirme que algo funciona sem ter executado e mostrado o resultado.
- Ao final de cada etapa, sugira 3 a 4 linhas para o diário de desenvolvimento
  (`docs/diario.md`): o que foi feito, como funciona, o que deu errado.

## Stack decidida (não alterar sem aprovação)

| Peça | Escolha |
|---|---|
| Linguagem | Python 3.11+ |
| Leitura de PDF | PyMuPDF |
| Embeddings | BGE-M3 ou multilingual-E5 (via sentence-transformers), rodando em CPU — escolha final após teste da Etapa 3; sempre chamado por `gerar_embeddings()` |
| Banco | PostgreSQL + pgvector no Supabase (sem Docker), índice HNSW, full-text search do Postgres (`tsvector`, configuração `portuguese`), Row Level Security; dados de todos os clientes, trechos e logs no mesmo banco |
| Driver do banco | psycopg 3, no modo assíncrono dentro da API |
| LLM | API do Claude, modelo `claude-sonnet-5-5` (SDK `anthropic`), com streaming |
| API | FastAPI, rotas assíncronas (`async def`) e sem estado |
| Configuração do assistente | Arquivos YAML (`assistentes/<slug>.yaml`), lidos com PyYAML (aprovado; entra no `requirements.txt` quando for usado) |
| Interface | React (Vite) hospedado no Vercel desde o MVP; consome a API, com CORS liberado só para o domínio do Vercel |
| Pipeline | Código próprio, sem LangChain ou LlamaIndex |

Ambiente de desenvolvimento: Windows, sem GPU dedicada. O frontend exige Node.js (LTS).

## Estrutura do repositório

```
PIBICT_RAG/              (raiz do repositório)
├── data/raw/<colecao>/  PDFs oficiais (versionados) + manifesto.yaml (arquivo, titulo,
│                        fonte_url, baixado_em, metadados), uma pasta por coleção
├── data/processed/<colecao>/trechos.json   trechos extraídos (gerados pelo código; não versionados)
├── assistentes/         um YAML por assistente (<slug>.yaml), ex.: vestibular-fatec-indaiatuba.yaml
├── sql/esquema.sql      tabelas, índices e políticas de RLS
├── src/
│   ├── ingestao.py      PDF → trechos com documento, página e posição (por coleção)
│   ├── embeddings.py    gerar_embeddings(): única porta de entrada para o modelo de embedding
│   ├── indexacao.py     trechos → embeddings → pgvector; registra a ingestão
│   ├── assistentes.py   lê assistentes/<slug>.yaml, valida e grava na tabela assistentes
│   ├── recuperacao.py   pergunta → top-5 trechos, densa e híbrida (escrito pelo bolsista)
│   ├── geracao.py       pergunta + trechos → resposta com fontes; modo sem recuperação (Cenário A)
│   ├── logs.py          registro anonimizado das interações, com tokens e custo
│   └── api.py           FastAPI, orquestra tudo
├── frontend/            interface em React (Vite), publicada no Vercel; a mesma para todos os clientes
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
- Chunking do MVP: tamanho fixo, ~400 palavras, 15% de sobreposição. O trecho pode
  atravessar a virada de página: guarda `pagina` (onde começa) e `pagina_fim` (onde
  termina), e a citação mostra o intervalo (ex.: p. 8–9).
- Busca do MVP: top-5, híbrida (densa no pgvector + full-text search do Postgres,
  combinadas por RRF — Reciprocal Rank Fusion), implementada na Etapa 4 e medida
  com e sem a parte full-text. Reranking só após medição.
- Toda busca é filtrada por `cliente_id` e pelas coleções do assistente
  (`colecao_id` em `assistente_colecoes`), com varredura iterativa do
  índice HNSW ligada (`hnsw.iterative_scan`, pgvector ≥ 0.8), para o filtro não
  deixar o resultado com menos de 5 trechos.
- Embeddings só por `gerar_embeddings()` (em `src/embeddings.py`). O modelo usado fica
  registrado em `colecoes.modelo_embedding`; a pergunta usa o modelo da coleção
  consultada.
- multilingual-E5 exige os prefixos `query: ` (pergunta) e `passage: ` (trechos);
  esses prefixos ficam dentro de `gerar_embeddings()`.
- O Cenário A (só LLM) e o Cenário B (RAG) usam o mesmo modelo e a mesma configuração.
- Reprodutibilidade: os PDFs usados no experimento são versionados em
  `data/raw/<colecao>/` e registrados no `manifesto.yaml` da coleção (que substitui o
  antigo `FONTES.md`). A ingestão falha se faltar um PDF do manifesto ou se houver
  PDF na pasta fora dele. Avise antes de versionar qualquer arquivo
  acima de 20 MB. Pastas geradas (como `data/processed/`) são criadas pelo código
  quando não existirem.

## Modelo de dados (PostgreSQL/Supabase)

```
clientes     (id, nome, slug)
colecoes     (id, cliente_id, nome, modelo_embedding)
documentos   (id, colecao_id, titulo, arquivo, fonte_url, baixado_em, metadados JSONB)
trechos      (id, documento_id, cliente_id, colecao_id, pagina, pagina_fim, posicao, texto,
              metadados JSONB, embedding vector, texto_busca tsvector)
assistentes  (id, cliente_id, slug, config JSONB)
assistente_colecoes (assistente_id, colecao_id, cliente_id)
sessoes      (id, assistente_id, criada_em)
interacoes   (id, sessao_id, cliente_id, pergunta (mascarada), resposta, fontes, tempos,
              tokens_entrada, tokens_saida, custo_estimado, util, categoria)
ingestoes    (id, colecao_id, cliente_id, inicio, fim, documentos, trechos, tempo,
              custo_estimado)
```

- Um assistente pode usar várias coleções (ex.: `vestibular-2027-1`, que muda a cada
  edição, e `fatec-indaiatuba-institucional`, estável), ligadas por
  `assistente_colecoes`. O banco só aceita ligar coleções do mesmo cliente: a tabela
  guarda `cliente_id` e tem chaves estrangeiras compostas `(assistente_id, cliente_id)`
  → `assistentes(id, cliente_id)` e `(colecao_id, cliente_id)` → `colecoes(id, cliente_id)`.
- `trechos` repete `cliente_id` e `colecao_id` (em vez de só herdar do documento) para
  a busca filtrar sem JOIN.
- `texto_busca` é gerado a partir de `texto` com `to_tsvector('portuguese', ...)`, com
  índice GIN. `embedding` tem índice HNSW; a dimensão do vetor é fixada após a Etapa 3.
- Row Level Security ligada em todas as tabelas com `cliente_id`. A API não usa um
  papel do banco que ignore RLS, e o `cliente_id` vem do assistente consultado
  (definido no servidor), nunca de um campo enviado pelo navegador.
- As políticas e a estrutura ficam em `sql/esquema.sql`. Mudanças no esquema passam
  pelo bolsista antes de rodar no Supabase.

## Configuração do assistente

Cada assistente tem um arquivo `assistentes/<slug>.yaml`, versionado. `src/assistentes.py`
lê o arquivo e grava em `assistentes.config` (JSONB); em execução, a API lê do banco.
Campos:

- `nome`, `cores` (tema da interface), `boas_vindas`
- `perguntas_sugeridas` (lista)
- `pergunta_contexto` e `filtro`: pergunta feita ao usuário no início (ex.: curso de
  interesse) e o campo de `metadados` dos trechos que a resposta filtra
  (implementados na Etapa 7; até lá, o campo `contexto` da API é opcional e ignorado)
- `sem_resposta`: mensagem quando os documentos não respondem, com o contato do cliente
- `regras_prompt`: regras específicas do cliente, somadas às regras fixas do prompt
  (responder só com os trechos, citar a fonte, dizer quando não encontrou)
- `colecoes`: lista das coleções consultadas (gravada em `assistente_colecoes`)

## Custos

Cada interação grava `tokens_entrada`, `tokens_saida` (lidos da resposta da API do
Claude) e `custo_estimado`. Cada ingestão grava tempo e `custo_estimado`. Os preços por
token ficam em um único lugar do código, com a data em que foram conferidos.

## Segurança e LGPD

- Chaves, senhas e tokens apenas no `.env`, carregados por variáveis de ambiente.
- `.env` sempre no `.gitignore`.
- Logs sem nome, e-mail, CPF ou telefone: mascarar esses padrões na pergunta antes
  de salvar. Sessão identificada só por ID anônimo (tabela `sessoes`).
- **Teste de isolamento (obrigatório):** perguntas feitas como cliente A nunca devolvem
  trechos do cliente B, e o banco recusa ligar a um assistente do cliente A uma coleção
  do cliente B. Fica em `tests/` com dois clientes de teste e roda antes de
  todo merge que mexa em banco, busca ou API.

## Campos de log (a validar com o projeto da Jasmine)

Os logs ficam na tabela `interacoes` (ver "Modelo de dados"). Além dos campos de lá,
continuam previstos: `data_hora`, `pontuacoes_busca`, `tempo_recuperacao_ms`,
`tempo_geracao_ms`, `modelo`, `versao_prompt`. `categoria` é preenchida na análise;
`util` vem do 👍/👎 (opcional).

## Contrato da API

A API não guarda estado entre requisições: tudo o que ela precisa vem na requisição ou
no banco.

```json
// GET /assistentes/{slug} — configuração pública para a interface
// (nome, cores, boas-vindas, perguntas sugeridas, pergunta de contexto)

// POST /perguntar — requisição
{
  "assistente": "vestibular-fatec-indaiatuba",
  "sessao": "uuid (criada pela API se vier vazia)",
  "pergunta": "Quem tem direito à isenção da taxa?",
  "contexto": { "curso": "..." }
}

// resposta: em streaming (texto chega aos poucos); ao final, um bloco com
{
  "resposta": "...",
  "fontes": [{ "documento": "Edital Vestibular 1/2027", "pagina": 8, "pagina_fim": 9,
               "trecho": "...", "url": "https://...pdf#page=8" }],
  "encontrou": true,
  "id_interacao": "uuid",
  "sessao": "uuid",
  "tempo_ms": 2100
}

// POST /feedback
{ "id_interacao": "uuid", "util": true }
```

## UX do MVP

- Resposta em streaming.
- Fonte clicável: abre o PDF oficial na página citada.
- "Não sei" com contato: quando não encontra, mostra `sem_resposta` do assistente.
- Perguntas sugeridas na tela inicial.
- Feedback 👍/👎 em cada resposta (grava `util`).

## Etapas e cronograma (sem pausa no recesso)

| Período | Etapas | Entrega |
|---|---|---|
| até 18/12/2026 | 2 a 6 | back-end completo |
| 19/12/2026 a ~08/01/2027 | 7 e 8 | interface com a UX do MVP e avaliação inicial |
| a partir de ~08/01/2027 | — | piloto interno |

1. Ambiente: Git, venv, projeto no Supabase com a extensão vector, `.env`, script de teste (banco + Claude)
2. Ingestão e chunking: trechos com documento, página, posição e metadados, organizados
   por coleção (sem nada fixo do Vestibular)
3. Teste de embeddings (BGE-M3 × E5, 20 perguntas, Recall@5 e MRR), já por
   `gerar_embeddings()`
4. Esquema do banco (`sql/esquema.sql`, com RLS), indexação com registro da ingestão,
   busca densa e híbrida (RRF) medidas com e sem, e teste de isolamento
5. Geração com streaming e regras do assistente (incluindo modo sem recuperação),
   tokens e custo
6. API assíncrona e sem estado, YAML do assistente carregado no banco, logs e feedback
7. Interface React (Vite) no Vercel com a UX do MVP, com túnel para o back-end local nos
   testes; inclui a pergunta de contexto com filtro (front-end e filtro na busca)
8. Avaliação inicial (30 perguntas, Cenário A × B), teste de isolamento rodado e README

Cada etapa só termina quando seu critério de pronto foi verificado e mostrado.

## Regras de Git (o bolsista executa tudo manualmente)

**Você nunca executa comandos Git que alteram o repositório ou o GitHub.** O bolsista faz
cada um deles à mão. Seu papel é orientar: dizer o que fazer, o comando exato, por que e
o que conferir antes.

- **Pode executar** (só leitura): `git status`, `git diff`, `git log`, `git branch`
  (listar), `git remote -v`, `git show`.
- **Não executa nunca, nem com aprovação**: `git add`, `git commit` (inclusive `--amend`),
  `git checkout -b` / `git switch -c`, `git branch -d`, `git merge`, `git rebase`,
  `git reset`, `git stash`, `git tag`, `git push`, `git pull`, nem qualquer ação no
  GitHub (PR, configurações, deploy).
- Quando for hora de um commit, um push ou um merge, **pare** e entregue ao bolsista:
  1. o que será registrado (resumo do `git status` e do `git diff`);
  2. os comandos exatos, em um bloco pronto para copiar;
  3. o que conferir antes de rodar (ex.: `.env` fora da lista);
  4. como verificar depois (ex.: `git log --oneline -3`).
  Depois, espere o bolsista confirmar que executou antes de seguir.

Convenções a orientar:
- `main` é a versão validada e é o que o Vercel publica. Ninguém trabalha direto nela.
- Cada etapa em uma branch própria: `etapa-N-descricao` (ex.: `etapa-1-ambiente`).
- Commits pequenos, um assunto por commit, mensagem em português no padrão:
  `feat:` (funcionalidade), `fix:` (correção), `docs:` (documentação),
  `test:` (testes), `refactor:` (reorganização sem mudar comportamento), `chore:` (configuração).
  Ex.: `feat: extrai texto dos PDFs com número da página`.
- Merge na `main` (que dispara o deploy no Vercel) só depois de a etapa cumprir o
  critério de pronto, com os testes mostrados. O merge é feito por Pull Request no GitHub.
- Título e descrição do PR curtos e diretos, sem perder o essencial. Modelo:
  ```
  Título: Etapa N: [resumo em poucas palavras]

  [1 frase: o que entra na main]

  **Teste** (`comando`): [resultado em uma linha]
  **Pendência:** [o que falta e onde está registrado]   (omitir se não houver)
  **Atenção:** [o que quem clonar ou revisar precisa saber, ex.: nova variável no .env]   (omitir se não houver)
  ```
- Nunca orientar: commitar `.env`, chaves ou senhas; `git push --force`; reescrever
  histórico já enviado.
- Antes de cada commit, alerte se algum arquivo sensível ou grande (PDFs pesados,
  modelos baixados, `node_modules/`, `.venv/`) aparece no `git status`.

## Relatório de desenvolvimento (obrigatório)

Ao parar para esperar o bolsista depois de fazer algo, termine com o relatório abaixo.
Ele é copiado para o orientador técnico (outro chat), que acompanha o projeto.

Regras:
- No máximo ~15 linhas. Frases curtas. Sem repetir o que já foi relatado antes:
  só o que mudou desde o último relatório.
- Omita as linhas que não se aplicam (ex.: sem decisão, sem a linha "Decidir").
- Só fatos verificados. Nada do .env, chaves, senhas ou connection strings.

```
# Relatório — [data] · Etapa [N], passo [X/Y]
**Status:** [1 frase: onde estamos]
**Feito:** [o que mudou, 1 a 3 itens curtos]
**Testes:** ✅ [ok] · ❌ [falhou: erro em poucas palavras] · ⏳ [não testado]
**Decidir:** [pergunta] → recomendo [opção], porque [1 frase]. Alternativa: [1 frase]
**Você faz:** [comandos em bloco, se houver]
**Fora do escopo:** [desvio do CLAUDE.md, se houver]
**Git:** último commit [hash + mensagem] · push: sim/não
```

Explicações durante a sessão também devem ser curtas (até ~5 linhas) e em linguagem
simples. Dê mais detalhes só quando o bolsista pedir.

As linhas do diário de desenvolvimento são sugeridas à parte, só ao fim de cada etapa.