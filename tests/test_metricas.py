"""Testes das métricas de recuperação (avaliacao/metricas.py).

Rodar a partir da raiz do repositório:
    .\\.venv\\Scripts\\python -m pytest tests/test_metricas.py -v

Os rankings são inventados, para o resultado certo ser calculado à mão.
"""

import pytest

from avaliacao.metricas import (
    eh_acerto,
    lugares_esperados,
    mrr,
    posicao_do_primeiro_acerto,
    recall_at_k,
)


def trecho(documento, pagina, pagina_fim=None):
    """Atalho para criar um trecho só com os campos que as métricas usam."""
    return {"documento": documento, "pagina": pagina, "pagina_fim": pagina_fim or pagina}


# ---------------------------------------------------------------- lugares esperados

def test_lugares_esperados_sem_alternativas():
    pergunta = {"documento_esperado": "a.pdf", "pagina_esperada": 3}
    assert lugares_esperados(pergunta) == [("a.pdf", 3)]


def test_lugares_esperados_com_alternativas():
    pergunta = {
        "documento_esperado": "a.pdf", "pagina_esperada": 3,
        "alternativas": [{"documento": "b.pdf", "pagina": 7}],
    }
    assert lugares_esperados(pergunta) == [("a.pdf", 3), ("b.pdf", 7)]


# ---------------------------------------------------------------- acerto

def test_acerto_exige_documento_e_pagina():
    lugares = [("a.pdf", 3)]
    assert eh_acerto(trecho("a.pdf", 3), lugares)
    assert not eh_acerto(trecho("a.pdf", 4), lugares)  # página errada
    assert not eh_acerto(trecho("b.pdf", 3), lugares)  # documento errado


def test_acerto_vale_para_trecho_que_atravessa_paginas():
    lugares = [("a.pdf", 8)]
    assert eh_acerto(trecho("a.pdf", 7, 9), lugares)  # 8 está entre 7 e 9
    assert eh_acerto(trecho("a.pdf", 8, 9), lugares)  # borda inicial
    assert eh_acerto(trecho("a.pdf", 7, 8), lugares)  # borda final
    assert not eh_acerto(trecho("a.pdf", 9, 10), lugares)


def test_acerto_por_alternativa():
    lugares = [("a.pdf", 3), ("b.pdf", 7)]
    assert eh_acerto(trecho("b.pdf", 7), lugares)


# ---------------------------------------------------------------- posição do primeiro acerto

def test_posicao_do_primeiro_acerto():
    ranking = [trecho("x.pdf", 1), trecho("a.pdf", 3), trecho("a.pdf", 3)]
    assert posicao_do_primeiro_acerto(ranking, [("a.pdf", 3)]) == 2


def test_sem_acerto_devolve_none():
    ranking = [trecho("x.pdf", 1), trecho("y.pdf", 2)]
    assert posicao_do_primeiro_acerto(ranking, [("a.pdf", 3)]) is None


def test_acerto_depois_do_top_k_nao_conta():
    # O acerto está na 6ª posição: fora do top-5.
    ranking = [trecho("x.pdf", i) for i in range(1, 6)] + [trecho("a.pdf", 3)]
    assert posicao_do_primeiro_acerto(ranking, [("a.pdf", 3)], k=5) is None
    assert posicao_do_primeiro_acerto(ranking, [("a.pdf", 3)], k=6) == 6


# ---------------------------------------------------------------- Recall@k e MRR

def test_recall_e_mrr_calculados_a_mao():
    # 4 perguntas: acerto em 1º, em 2º, nenhum, em 4º.
    posicoes = [1, 2, None, 4]
    assert recall_at_k(posicoes) == pytest.approx(3 / 4)
    assert mrr(posicoes) == pytest.approx((1 + 1 / 2 + 0 + 1 / 4) / 4)  # 0,4375


def test_tudo_certo_em_primeiro():
    assert recall_at_k([1, 1, 1]) == 1.0
    assert mrr([1, 1, 1]) == 1.0


def test_nenhum_acerto():
    assert recall_at_k([None, None]) == 0.0
    assert mrr([None, None]) == 0.0


def test_lista_vazia_da_erro():
    with pytest.raises(ValueError):
        recall_at_k([])
    with pytest.raises(ValueError):
        mrr([])
