"""Testes das partes do script de avaliação que não precisam de modelo.

Rodar a partir da raiz do repositório:
    .\\.venv\\Scripts\\python -m pytest tests/test_teste_embeddings.py -v
"""

import numpy as np
import pytest

from avaliacao.teste_embeddings import ErroPerguntas, ranquear, separar_perguntas

DOCUMENTOS = {"manual.pdf", "portaria.pdf"}


# ---------------------------------------------------------------- separação das perguntas

def test_separa_com_resposta_sem_resposta_e_vazias():
    perguntas = [
        {"id": "p01", "pergunta": "Qual a taxa?", "documento_esperado": "manual.pdf", "pagina_esperada": 6},
        {"id": "p02", "pergunta": "Tem estacionamento?", "documento_esperado": None},
        {"id": "p03", "pergunta": None, "documento_esperado": None},  # ainda do modelo
    ]
    com, sem, vazias = separar_perguntas(perguntas, DOCUMENTOS)
    assert [p["id"] for p in com] == ["p01"]
    assert [p["id"] for p in sem] == ["p02"]
    assert vazias == ["p03"]


def test_pergunta_sem_resposta_nao_exige_pagina():
    perguntas = [{"id": "p01", "pergunta": "Tem estacionamento?", "documento_esperado": ""}]
    _, sem, _ = separar_perguntas(perguntas, DOCUMENTOS)
    assert len(sem) == 1


def test_documento_inexistente_da_erro():
    perguntas = [{"id": "p01", "pergunta": "x", "documento_esperado": "manaul.pdf", "pagina_esperada": 1}]
    with pytest.raises(ErroPerguntas, match="manaul.pdf"):
        separar_perguntas(perguntas, DOCUMENTOS)


def test_alternativa_com_documento_inexistente_da_erro():
    perguntas = [{
        "id": "p01", "pergunta": "x", "documento_esperado": "manual.pdf", "pagina_esperada": 1,
        "alternativas": [{"documento": "edital.pdf", "pagina": 2}],
    }]
    with pytest.raises(ErroPerguntas, match="edital.pdf"):
        separar_perguntas(perguntas, DOCUMENTOS)


@pytest.mark.parametrize("pagina", [None, "6", 0, 2.5, True])
def test_pagina_invalida_da_erro(pagina):
    perguntas = [{"id": "p01", "pergunta": "x", "documento_esperado": "manual.pdf", "pagina_esperada": pagina}]
    with pytest.raises(ErroPerguntas, match="p01"):
        separar_perguntas(perguntas, DOCUMENTOS)


# ---------------------------------------------------------------- ranqueamento

def test_ranquear_ordena_pela_similaridade():
    # Vetores já normalizados; a pergunta é igual ao trecho 2, parecida com o 0.
    trechos = np.array([[0.8, 0.6], [0.0, 1.0], [1.0, 0.0]])
    pergunta = np.array([1.0, 0.0])
    ranking = ranquear(trechos, pergunta, k=3)
    assert [i for i, _ in ranking] == [2, 0, 1]
    assert [p for _, p in ranking] == pytest.approx([1.0, 0.8, 0.0])


def test_ranquear_devolve_so_k_trechos():
    trechos = np.eye(10)  # 10 trechos
    assert len(ranquear(trechos, np.ones(10) / np.sqrt(10), k=5)) == 5
