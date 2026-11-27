"""Métricas de recuperação: Recall@k e MRR.

Usadas na Etapa 3 (BGE-M3 × E5) e de novo na Etapa 4 (busca densa × híbrida).

Como as métricas são calculadas:
    1. Para cada pergunta, olhamos os k primeiros trechos devolvidos pela busca e
       anotamos a posição (1, 2, 3...) do PRIMEIRO trecho correto, ou None se nenhum
       dos k for correto.
    2. Recall@k = fração das perguntas com algum trecho correto entre os k primeiros.
       (Como cada pergunta tem um lugar esperado, isso também é chamado de "hit rate"
       ou "acerto@k". Fica registrado assim no artigo.)
    3. MRR (Mean Reciprocal Rank) = média de 1/posição do primeiro acerto, contando 0
       quando não há acerto. Acertar em 1º vale 1; em 2º, 0,5; em 3º, 0,33...
       O MRR mostra não só SE o modelo acha, mas QUÃO NO TOPO ele coloca a resposta.
"""


def lugares_esperados(pergunta):
    """Lista de (documento, página) onde a resposta da pergunta pode estar.

    Junta o lugar principal (documento_esperado, pagina_esperada) com as
    alternativas opcionais do YAML de perguntas.
    """
    lugares = [(pergunta["documento_esperado"], pergunta["pagina_esperada"])]
    for alternativa in pergunta.get("alternativas") or []:
        lugares.append((alternativa["documento"], alternativa["pagina"]))
    return lugares


def eh_acerto(trecho, lugares):
    """Um trecho é correto se é do documento esperado e cobre a página esperada.

    "Cobre" porque um trecho pode atravessar páginas: vale qualquer página entre
    pagina e pagina_fim (inclusive).
    """
    return any(
        trecho["documento"] == documento and trecho["pagina"] <= pagina <= trecho["pagina_fim"]
        for documento, pagina in lugares
    )


def posicao_do_primeiro_acerto(trechos_ordenados, lugares, k=5):
    """Posição (começando em 1) do primeiro trecho correto entre os k primeiros, ou None."""
    for posicao, trecho in enumerate(trechos_ordenados[:k], start=1):
        if eh_acerto(trecho, lugares):
            return posicao
    return None


def recall_at_k(posicoes):
    """Fração das perguntas com acerto. `posicoes` vem de posicao_do_primeiro_acerto."""
    if not posicoes:
        raise ValueError("Nenhuma pergunta para avaliar.")
    acertos = sum(1 for p in posicoes if p is not None)
    return acertos / len(posicoes)


def mrr(posicoes):
    """Média de 1/posição do primeiro acerto (0 quando não houve acerto)."""
    if not posicoes:
        raise ValueError("Nenhuma pergunta para avaliar.")
    return sum(1 / p for p in posicoes if p is not None) / len(posicoes)
