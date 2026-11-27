"""Embeddings: transforma textos em vetores com um modelo do sentence-transformers.

Regra do projeto: todo o código que precisa de embeddings chama gerar_embeddings().
Assim, a escolha do modelo e os detalhes de cada um (como os prefixos do E5) ficam
num lugar só, e perguntas e trechos sempre passam pelo mesmo caminho.

Os modelos rodam em CPU. Na primeira vez, cada um é baixado (~2,2 GB) para o cache do
Hugging Face, fora do repositório.
"""

from sentence_transformers import SentenceTransformer

# Modelos disponíveis. A chave (ex.: "bge-m3") é o nome usado no projeto e o que será
# gravado em colecoes.modelo_embedding na Etapa 4.
MODELOS = {
    "bge-m3": {
        "nome_hf": "BAAI/bge-m3",
        # O BGE-M3 não usa prefixos na busca densa.
        "prefixo_pergunta": "",
        "prefixo_trecho": "",
    },
    "multilingual-e5-large": {
        "nome_hf": "intfloat/multilingual-e5-large",
        # O E5 foi treinado com esses prefixos; sem eles, a qualidade da busca cai.
        "prefixo_pergunta": "query: ",
        "prefixo_trecho": "passage: ",
    },
}

TIPOS = ("pergunta", "trecho")

# Guarda os modelos já carregados, para não ler ~2 GB do disco a cada chamada.
_modelos_carregados = {}


def preparar_textos(textos, modelo, tipo):
    """Acrescenta o prefixo que o modelo espera para o tipo de texto.

    tipo = "pergunta" (o que o usuário digita) ou "trecho" (pedaço de documento).
    """
    if modelo not in MODELOS:
        raise ValueError(f"Modelo desconhecido: {modelo!r}. Opções: {', '.join(MODELOS)}")
    if tipo not in TIPOS:
        raise ValueError(f"Tipo desconhecido: {tipo!r}. Opções: {', '.join(TIPOS)}")

    prefixo = MODELOS[modelo][f"prefixo_{tipo}"]
    return [prefixo + texto for texto in textos]


def carregar_modelo(modelo):
    """Carrega o modelo em CPU na primeira chamada e reaproveita nas seguintes."""
    if modelo not in _modelos_carregados:
        nome_hf = MODELOS[modelo]["nome_hf"]
        _modelos_carregados[modelo] = SentenceTransformer(nome_hf, device="cpu")
    return _modelos_carregados[modelo]


def gerar_embeddings(textos, modelo, tipo, tamanho_lote=8):
    """Devolve um vetor por texto, como um array numpy de formato (len(textos), dimensão).

    Os vetores saem normalizados (comprimento 1). Com isso, a similaridade de cosseno
    entre dois vetores é só o produto escalar entre eles, o que simplifica a busca.

    tamanho_lote: quantos textos o modelo processa de uma vez. Lotes pequenos usam
    menos memória, o que importa em CPU.
    """
    preparados = preparar_textos(textos, modelo, tipo)
    return carregar_modelo(modelo).encode(
        preparados,
        batch_size=tamanho_lote,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )


def contar_tokens(textos, modelo, tipo):
    """Conta quantos tokens cada texto ocupa no modelo, já com o prefixo.

    Serve para saber se algum texto passa do limite do modelo (limite_tokens) e
    teria o final ignorado. A contagem inclui os tokens especiais de início e fim.
    """
    preparados = preparar_textos(textos, modelo, tipo)
    tokenizador = carregar_modelo(modelo).tokenizer
    return [len(tokenizador(texto)["input_ids"]) for texto in preparados]


def limite_tokens(modelo):
    """Número máximo de tokens que o modelo lê por texto; o que passar disso é cortado."""
    return carregar_modelo(modelo).max_seq_length
