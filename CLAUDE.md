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
├── data/raw/            PDFs oficiais (versionados) + FONTES.md (arquivo, link, data do download)
├── data/processed/      trechos extraídos (JSON, gerados pelo código; não versionados)
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
- Reprodutibilidade: os PDFs usados no experimento são versionados em `data/raw/` e
  registrados em `data/raw/FONTES.md`. Avise antes de versionar qualquer arquivo
  acima de 20 MB. Pastas geradas (como `data/processed/`) são criadas pelo código
  quando não existirem.

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
  critério de pronto, com os testes mostrados.
- Nunca orientar: commitar `.env`, chaves ou senhas; `git push --force`; reescrever
  histórico já enviado.
- Antes de cada commit, alerte se algum arquivo sensível ou grande (PDFs pesados,
  modelos baixados, `node_modules/`, `.venv/`) aparece no `git status`.

## Relatório de desenvolvimento (obrigatório)

Sempre que você **parar para esperar o bolsista** depois de ter desenvolvido ou executado
algo (fim de um passo, um commit a orientar, um erro, uma decisão pendente), termine a
resposta com o relatório abaixo, sem esperar pedido. O bolsista vai copiá-lo para o
orientador técnico (outro chat), que acompanha o projeto e ajuda a tomar a próxima
decisão. Por isso, o relatório precisa se sustentar sozinho: quem lê não viu a sessão.

Regras do relatório:
- **Acumulado:** cobre a sessão inteira até aquele momento; o bolsista copia só o mais recente.
- **Só fatos verificados:** resultados vêm de comandos realmente executados, com a saída
  relevante resumida. O que não foi executado aparece como "não testado".
- **Nada sensível:** nunca inclua conteúdo do `.env`, chaves, senhas, connection strings
  ou dados pessoais. Mascare se aparecerem em alguma saída.
- **Decisões sempre com opções:** toda decisão pendente traz as opções, prós e contras
  e a sua recomendação justificada.
- Respostas que só tiram dúvidas ou apresentam um plano ainda não executado não precisam
  de relatório.

Use um único bloco de Markdown, pronto para copiar:

```
# Relatório de desenvolvimento — [data] · Etapa [N]: [nome] · branch [nome]

## 1. Situação geral
[1 a 2 frases: em que ponto da etapa estamos (ex.: passo 2 de 5) e se está no prazo]

## 2. O que foi feito
- [passo] — [arquivos criados/alterados] — [o que passa a fazer]

## 3. Resultados e evidências
- ✅ [o que funcionou] — [comando/teste → resultado real]
- ❌ [o que falhou] — [erro resumido]
- ⏳ [o que ainda não foi testado]

## 4. Problemas e riscos
- [problema] — causa provável: [...] — impacto: [...] — status: [resolvido / investigando / bloqueado]
  (ou "nenhum")

## 5. Decisões pendentes
### [pergunta objetiva]
- Opção A: [...] — prós: [...] — contras: [...]
- Opção B: [...] — prós: [...] — contras: [...]
- Recomendação: [opção] porque [...]
(ou "nenhuma")

## 6. Ações do bolsista
- [comandos Git a executar, configurações, testes manuais, contas a criar]
  (com os comandos exatos em bloco, quando houver)

## 7. Aderência ao escopo
[o que saiu do CLAUDE.md: nova dependência, mudança de estrutura, desvio da stack ou
das regras da arquitetura; ou "sem desvios"]

## 8. Git
[commits existentes na branch (hash curto + mensagem) · push: sim/não · merge na main: sim/não]

## 9. Próximo passo proposto
[1 a 2 linhas]
```

As linhas do diário de desenvolvimento são sugeridas à parte, só ao fim de cada etapa.
