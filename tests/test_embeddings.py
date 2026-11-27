"""Testes de src/embeddings.py que NÃO baixam modelo.

Rodar a partir da raiz do repositório:
    .\\.venv\\Scripts\\python -m pytest tests/test_embeddings.py -v

Os modelos reais têm ~2,2 GB; aqui trocamos o modelo por um "modelo falso" que só
registra o que recebeu. Assim conferimos os prefixos e os parâmetros enviados ao
modelo sem precisar baixá-lo. O modelo real é exercitado pelo script de avaliação.
"""

import numpy as np
import pytest

from src import embeddings
from src.embeddings import gerar_embeddings, preparar_textos


class ModeloFalso:
    """Imita um SentenceTransformer: guarda os textos e parâmetros recebidos."""

    def __init__(self):
        self.textos_recebidos = None
        self.parametros = None

    def encode(self, textos, **parametros):
        self.textos_recebidos = textos
        self.parametros = parametros
        return np.ones((len(textos), 3))


@pytest.fixture
def modelo_falso(monkeypatch):
    """Faz carregar_modelo() devolver o ModeloFalso em vez de baixar o modelo real."""
    falso = ModeloFalso()
    monkeypatch.setattr(embeddings, "carregar_modelo", lambda modelo: falso)
    return falso


# ---------------------------------------------------------------- prefixos

def test_e5_usa_prefixo_query_na_pergunta():
    assert preparar_textos(["Qual a taxa?"], "multilingual-e5-large", "pergunta") == ["query: Qual a taxa?"]


def test_e5_usa_prefixo_passage_no_trecho():
    assert preparar_textos(["Artigo 1º"], "multilingual-e5-large", "trecho") == ["passage: Artigo 1º"]


def test_bge_m3_nao_usa_prefixo():
    assert preparar_textos(["Qual a taxa?"], "bge-m3", "pergunta") == ["Qual a taxa?"]
    assert preparar_textos(["Artigo 1º"], "bge-m3", "trecho") == ["Artigo 1º"]


def test_modelo_desconhecido_da_erro():
    with pytest.raises(ValueError, match="Modelo desconhecido"):
        preparar_textos(["x"], "modelo-inexistente", "pergunta")


def test_tipo_desconhecido_da_erro():
    with pytest.raises(ValueError, match="Tipo desconhecido"):
        preparar_textos(["x"], "bge-m3", "documento")


# ---------------------------------------------------------------- gerar_embeddings

def test_gerar_embeddings_envia_textos_com_prefixo(modelo_falso):
    gerar_embeddings(["Qual a taxa?"], "multilingual-e5-large", "pergunta")
    assert modelo_falso.textos_recebidos == ["query: Qual a taxa?"]


def test_gerar_embeddings_pede_vetores_normalizados(modelo_falso):
    gerar_embeddings(["a", "b"], "bge-m3", "trecho")
    assert modelo_falso.parametros["normalize_embeddings"] is True


def test_gerar_embeddings_devolve_um_vetor_por_texto(modelo_falso):
    vetores = gerar_embeddings(["a", "b", "c"], "bge-m3", "trecho")
    assert vetores.shape[0] == 3
