"""Teste de ambiente (Etapa 1).

Verifica se o ambiente está pronto para o projeto:
  1. conexão com o banco (PostgreSQL do Supabase);
  2. extensão vector (pgvector) ativada e funcionando;
  3. chamada à API do Claude (pulada com aviso se a chave ainda não existir).

Uso (na raiz do projeto, com o venv ativo):
    python tests/teste_ambiente.py

Termina com código 1 se algum teste FALHOU. "PULADO" não conta como falha.
Por segurança, o script nunca imprime a DATABASE_URL nem a chave da API.
"""

import os
import sys
from pathlib import Path

import anthropic
import psycopg
from dotenv import load_dotenv

# Modelo do Claude definido no código (e não no .env) para ficar registrado no Git.
MODELO = "claude-sonnet-5-5"

# Valor falso que vem no .env.example; se a chave for esse texto, ainda não há chave real.
CHAVE_DE_EXEMPLO = "sk-ant-coloque-sua-chave-aqui"

OK, FALHOU, PULADO = "OK", "FALHOU", "PULADO"


def testar_banco():
    """Tenta conectar ao banco. Devolve (status, mensagem, conexão ou None)."""
    url = os.getenv("DATABASE_URL")
    if not url:
        return FALHOU, "DATABASE_URL não encontrada no .env", None

    try:
        # connect_timeout evita que o script fique travado se a rede bloquear a conexão.
        conexao = psycopg.connect(url, connect_timeout=10)
        versao = conexao.execute("SELECT version()").fetchone()[0]
    except psycopg.Error as erro:
        # A mensagem do psycopg pode citar o servidor, mas nunca a senha.
        return FALHOU, f"não conectou ({type(erro).__name__}: {erro})", None

    # version() devolve um texto longo; as duas primeiras palavras bastam (ex.: "PostgreSQL 17.4").
    versao_curta = " ".join(versao.split()[:2])
    return OK, f"conectado ({versao_curta})", conexao


def testar_extensao_vector(conexao):
    """Confere se a extensão vector está ativa e se calcula distâncias. Devolve (status, mensagem)."""
    if conexao is None:
        return PULADO, "depende da conexão com o banco, que falhou"

    try:
        # 1) A extensão está instalada neste banco? pg_extension lista as extensões ativas.
        linha = conexao.execute(
            "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
        ).fetchone()
        if linha is None:
            return FALHOU, "extensão vector não está ativada no Supabase"
        versao = linha[0]

        # 2) Ela funciona? '<->' é a distância euclidiana entre dois vetores,
        #    a operação que a busca do RAG vai usar. Entre [1,2,3] e [1,2,4] ela vale 1.
        #    Nada é criado nem gravado no banco.
        distancia = conexao.execute(
            "SELECT '[1,2,3]'::vector <-> '[1,2,4]'::vector"
        ).fetchone()[0]
    except psycopg.Error as erro:
        return FALHOU, f"erro ao usar a extensão ({type(erro).__name__}: {erro})"

    if abs(distancia - 1.0) > 1e-6:
        return FALHOU, f"distância de teste deveria ser 1.0, mas deu {distancia}"
    return OK, f"versão {versao}; distância de teste = {distancia}"


def testar_claude():
    """Faz uma chamada curta ao Claude, ou pula se não houver chave. Devolve (status, mensagem)."""
    chave = os.getenv("ANTHROPIC_API_KEY", "")
    if not chave or chave == CHAVE_DE_EXEMPLO:
        return PULADO, "ANTHROPIC_API_KEY ausente ou com valor de exemplo (chave prevista até o início de dezembro)"

    # O SDK lê a chave sozinho da variável ANTHROPIC_API_KEY.
    cliente = anthropic.Anthropic()
    try:
        resposta = cliente.messages.create(
            model=MODELO,
            # O Sonnet 5.5 raciocina antes de responder; um limite muito baixo cortaria a resposta.
            max_tokens=1024,
            # Esforço baixo: o teste fica rápido e barato.
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": "Responda apenas com a palavra: ok"}],
        )
    # Erros do mais específico para o mais geral, cada um com uma mensagem clara.
    except anthropic.AuthenticationError:
        return FALHOU, "chave inválida (AuthenticationError)"
    except anthropic.NotFoundError:
        return FALHOU, f"modelo {MODELO} não encontrado (NotFoundError)"
    except anthropic.APIStatusError as erro:
        return FALHOU, f"erro da API (código {erro.status_code})"
    except anthropic.APIConnectionError:
        return FALHOU, "sem conexão com a API (internet ou proxy)"

    # A resposta vem em blocos; juntamos só os blocos de texto.
    texto = "".join(bloco.text for bloco in resposta.content if bloco.type == "text").strip()
    if not texto:
        return FALHOU, f"resposta sem texto (stop_reason = {resposta.stop_reason})"
    return OK, f"{MODELO} respondeu: {texto[:40]!r}"


def main():
    # Carrega o .env da raiz do projeto (a pasta acima de tests/).
    raiz = Path(__file__).resolve().parent.parent
    load_dotenv(raiz / ".env")

    resultados = []

    status, mensagem, conexao = testar_banco()
    resultados.append(("Banco", status, mensagem))

    status, mensagem = testar_extensao_vector(conexao)
    resultados.append(("Extensão vector", status, mensagem))

    if conexao is not None:
        conexao.close()

    status, mensagem = testar_claude()
    resultados.append(("Claude", status, mensagem))

    for nome, status, mensagem in resultados:
        print(f"[{status}]".ljust(9) + f"{nome}: {mensagem}")

    total_ok = sum(1 for _, status, _ in resultados if status == OK)
    total_falhas = sum(1 for _, status, _ in resultados if status == FALHOU)
    total_pulados = sum(1 for _, status, _ in resultados if status == PULADO)
    print(f"\nResumo: {total_ok} OK · {total_falhas} falha(s) · {total_pulados} pulado(s)")

    # Código de saída: 1 = algo falhou; 0 = tudo certo (pulados não contam como falha).
    sys.exit(1 if total_falhas else 0)


if __name__ == "__main__":
    main()
