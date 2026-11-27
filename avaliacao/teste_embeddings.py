"""Teste de embeddings (Etapa 3): compara modelos na busca densa com Recall@k e MRR@k.

Para cada modelo:
    1. carrega o modelo (mede o tempo);
    2. conta os tokens de cada trecho e quantos passam do limite do modelo (são cortados);
    3. gera os vetores de todos os trechos da coleção ("indexação", mede o tempo);
    4. para cada pergunta, gera o vetor da pergunta e ordena os trechos por similaridade
       de cosseno (mede o tempo médio por pergunta, com o modelo já carregado);
    5. calcula Recall@k e MRR@k só com as perguntas que têm resposta nos documentos.

Perguntas sem resposta (documento_esperado vazio) não entram nas métricas: o script só
mostra a pontuação do melhor trecho, para comparar com a das perguntas que têm resposta.
Isso vai ajudar na Etapa 5, quando o sistema precisar decidir quando dizer "não sei".

A busca aqui é em memória (numpy), sem banco: o banco entra na Etapa 4.

Uso (a partir da raiz do repositório; leva alguns minutos por modelo em CPU):
    .\\.venv\\Scripts\\python -m avaliacao.teste_embeddings
    .\\.venv\\Scripts\\python -m avaliacao.teste_embeddings --modelos bge-m3
"""

import argparse
import datetime
import json
import platform
import statistics
import sys
import time
from pathlib import Path

import numpy as np
import sentence_transformers
import torch
import yaml

from avaliacao.metricas import lugares_esperados, mrr, posicao_do_primeiro_acerto, recall_at_k
from src.embeddings import MODELOS, contar_tokens, gerar_embeddings, limite_tokens
from src.ingestao import PASTA_PROCESSADA, SOBREPOSICAO, TAMANHO_TRECHO

ARQUIVO_PERGUNTAS = Path("avaliacao/perguntas_embeddings.yaml")
PASTA_RESULTADOS = Path("avaliacao/resultados")
K = 5  # o sistema devolve os 5 trechos mais parecidos (top-5)


class ErroPerguntas(Exception):
    """O arquivo de perguntas está mal preenchido."""


# ---------------------------------------------------------------- leitura dos dados

def carregar_trechos(colecao):
    """Lê os trechos gerados pela ingestão (Etapa 2)."""
    caminho = PASTA_PROCESSADA / colecao / "trechos.json"
    if not caminho.exists():
        raise FileNotFoundError(
            f"{caminho} não existe. Rode antes: .\\.venv\\Scripts\\python -m src.ingestao {colecao}"
        )
    with open(caminho, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def separar_perguntas(perguntas, documentos_validos):
    """Separa as perguntas em três grupos e confere o preenchimento.

    Devolve (com_resposta, sem_resposta, nao_preenchidas):
      - com_resposta: têm documento_esperado; entram no Recall e no MRR;
      - sem_resposta: pergunta preenchida e documento_esperado vazio; ficam à parte;
      - nao_preenchidas: ids das perguntas com o texto vazio (ainda do modelo); ignoradas.

    Falha (ErroPerguntas) se um documento não existir na coleção (erro de digitação)
    ou se a página esperada não for um número inteiro.
    """
    com_resposta, sem_resposta, nao_preenchidas = [], [], []
    for pergunta in perguntas:
        ident = pergunta.get("id", "?")
        if not pergunta.get("pergunta"):
            nao_preenchidas.append(ident)
            continue
        if not pergunta.get("documento_esperado"):
            sem_resposta.append(pergunta)
            continue

        for documento, pagina in lugares_esperados(pergunta):
            if documento not in documentos_validos:
                raise ErroPerguntas(f"{ident}: documento {documento!r} não existe na coleção.")
            # bool é um tipo de int em Python; por isso é excluído explicitamente.
            if not isinstance(pagina, int) or isinstance(pagina, bool) or pagina < 1:
                raise ErroPerguntas(f"{ident}: página {pagina!r} de {documento} não é um número válido.")
        com_resposta.append(pergunta)

    return com_resposta, sem_resposta, nao_preenchidas


def carregar_perguntas(caminho, documentos_validos):
    """Lê o YAML de perguntas e devolve os três grupos de separar_perguntas()."""
    with open(caminho, encoding="utf-8") as arquivo:
        dados = yaml.safe_load(arquivo) or {}
    com_resposta, sem_resposta, nao_preenchidas = separar_perguntas(
        dados.get("perguntas") or [], documentos_validos
    )
    if not com_resposta:
        raise ErroPerguntas(f"{caminho} não tem nenhuma pergunta com resposta preenchida.")
    return com_resposta, sem_resposta, nao_preenchidas


# ---------------------------------------------------------------- busca e avaliação

def ranquear(vetores_trechos, vetor_pergunta, k=K):
    """Devolve os k trechos mais parecidos com a pergunta: lista de (índice, pontuação).

    Como os vetores são normalizados, a similaridade de cosseno é o produto escalar.
    `vetores_trechos @ vetor_pergunta` calcula, de uma vez, a pontuação de todos os trechos.
    """
    pontuacoes = vetores_trechos @ vetor_pergunta
    ordem = np.argsort(-pontuacoes)[:k]  # índices da maior para a menor pontuação
    return [(int(i), float(pontuacoes[i])) for i in ordem]


def resumo_trecho(trecho, pontuacao):
    """Dados de um trecho devolvido pela busca, para o relatório."""
    return {
        "documento": trecho["documento"],
        "pagina": trecho["pagina"],
        "pagina_fim": trecho["pagina_fim"],
        "posicao": trecho["posicao"],
        "pontuacao": round(pontuacao, 4),
    }


def avaliar_modelo(modelo, trechos, com_resposta, sem_resposta, k=K):
    """Roda o teste completo de um modelo e devolve os resultados num dicionário."""
    textos = [t["texto"] for t in trechos]

    # 1. Carga do modelo (limite_tokens carrega o modelo na primeira chamada).
    inicio = time.perf_counter()
    limite = limite_tokens(modelo)
    tempo_carga = time.perf_counter() - inicio

    # 2. Trechos acima do limite de tokens: o modelo ignora o final deles.
    tokens = contar_tokens(textos, modelo, "trecho")
    cortados = [n for n in tokens if n > limite]

    # 3. Indexação: vetores de todos os trechos.
    inicio = time.perf_counter()
    vetores_trechos = gerar_embeddings(textos, modelo, "trecho")
    tempo_indexacao = time.perf_counter() - inicio

    # 4. Perguntas, uma por vez (como na API), medindo o tempo de cada uma.
    def buscar(pergunta):
        inicio = time.perf_counter()
        vetor = gerar_embeddings([pergunta["pergunta"]], modelo, "pergunta")[0]
        ranking = ranquear(vetores_trechos, vetor, k)
        return ranking, time.perf_counter() - inicio

    tempos_pergunta = []
    detalhes, posicoes = [], []
    for pergunta in com_resposta:
        ranking, tempo = buscar(pergunta)
        tempos_pergunta.append(tempo)
        devolvidos = [trechos[i] for i, _ in ranking]
        posicao = posicao_do_primeiro_acerto(devolvidos, lugares_esperados(pergunta), k)
        posicoes.append(posicao)
        detalhes.append({
            "id": pergunta["id"],
            "pergunta": pergunta["pergunta"],
            "esperado": lugares_esperados(pergunta),
            "posicao_primeiro_acerto": posicao,
            "top_k": [resumo_trecho(trechos[i], p) for i, p in ranking],
        })

    detalhes_sem_resposta = []
    for pergunta in sem_resposta:
        ranking, tempo = buscar(pergunta)
        tempos_pergunta.append(tempo)
        i, pontuacao = ranking[0]
        detalhes_sem_resposta.append({
            "id": pergunta["id"],
            "pergunta": pergunta["pergunta"],
            "melhor_trecho": resumo_trecho(trechos[i], pontuacao),
        })

    # 5. Métricas (só perguntas com resposta).
    return {
        "modelo": modelo,
        "nome_hf": MODELOS[modelo]["nome_hf"],
        "dimensao": int(vetores_trechos.shape[1]),
        "limite_tokens": limite,
        "tokens_por_trecho": {
            "min": min(tokens), "mediana": statistics.median(tokens), "max": max(tokens),
        },
        "trechos_cortados": len(cortados),
        "trechos_total": len(trechos),
        "percentual_cortados": round(100 * len(cortados) / len(trechos), 1),
        "tempo_carga_s": round(tempo_carga, 1),
        "tempo_indexacao_s": round(tempo_indexacao, 1),
        "tempo_medio_pergunta_ms": round(1000 * statistics.mean(tempos_pergunta)),
        f"recall_at_{k}": round(recall_at_k(posicoes), 4),
        f"mrr_at_{k}": round(mrr(posicoes), 4),
        # Pontuação do 1º trecho nas perguntas com resposta, para comparar com as sem resposta.
        "pontuacao_top1_com_resposta_media": round(
            statistics.mean(d["top_k"][0]["pontuacao"] for d in detalhes), 4
        ),
        "perguntas": detalhes,
        "perguntas_sem_resposta": detalhes_sem_resposta,
    }


# ---------------------------------------------------------------- saída

def aviso_corte(r):
    """Frase explícita sobre os trechos cortados pelo limite de tokens do modelo."""
    if r["trechos_cortados"] == 0:
        return (f"{r['modelo']}: nenhum trecho passa do limite de {r['limite_tokens']} tokens "
                f"(trechos de {TAMANHO_TRECHO} palavras são lidos inteiros).")
    return (f"ATENÇÃO — {r['modelo']}: com trechos de {TAMANHO_TRECHO} palavras, o modelo corta "
            f"{r['trechos_cortados']} de {r['trechos_total']} trechos ({r['percentual_cortados']:.0f}%): "
            f"o limite é {r['limite_tokens']} tokens e o final desses trechos é ignorado.")


def imprimir_resultados(resultados, n_com, n_sem, nao_preenchidas, k=K):
    print(f"\nPerguntas: {n_com} com resposta (entram nas métricas), {n_sem} sem resposta (à parte)")
    if nao_preenchidas:
        print(f"Ignoradas por estarem vazias: {', '.join(nao_preenchidas)}")
    if n_com < 20:
        print(f"AVISO: só {n_com} pergunta(s) com resposta; o resultado ainda não é conclusivo.")

    print(f"\n{'Modelo':<24}{'Recall@' + str(k):>10}{'MRR@' + str(k):>8}"
          f"{'Carga (s)':>11}{'Indexação (s)':>15}{'Pergunta (ms)':>15}{'Cortados':>10}")
    for r in resultados:
        print(f"{r['modelo']:<24}{r[f'recall_at_{k}']:>10.3f}{r[f'mrr_at_{k}']:>8.3f}"
              f"{r['tempo_carga_s']:>11.1f}{r['tempo_indexacao_s']:>15.1f}"
              f"{r['tempo_medio_pergunta_ms']:>15}{r['percentual_cortados']:>9.0f}%")

    print()
    for r in resultados:
        print(aviso_corte(r))

    for r in resultados:
        print(f"\n--- {r['modelo']}: por pergunta (posição do 1º acerto no top-{k}; — = não achou)")
        for d in r["perguntas"]:
            pos = d["posicao_primeiro_acerto"] or "—"
            top1 = d["top_k"][0]
            print(f"  {d['id']}  acerto: {pos!s:<3} 1º trecho: {top1['documento']} "
                  f"p.{top1['pagina']}–{top1['pagina_fim']} ({top1['pontuacao']:.3f})")
        print(f"  pontuação média do 1º trecho (com resposta): {r['pontuacao_top1_com_resposta_media']:.3f}")
        for d in r["perguntas_sem_resposta"]:
            m = d["melhor_trecho"]
            print(f"  {d['id']}  SEM RESPOSTA — melhor trecho: {m['documento']} "
                  f"p.{m['pagina']}–{m['pagina_fim']} ({m['pontuacao']:.3f})")


def salvar_resultados(resultados, colecao, n_com, n_sem, pasta, k=K):
    """Grava tudo num JSON com data e hora no nome, junto com a configuração usada."""
    agora = datetime.datetime.now()
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f"embeddings_{colecao}_{agora:%Y-%m-%d_%H%M}.json"
    conteudo = {
        "data_hora": agora.isoformat(timespec="seconds"),
        "colecao": colecao,
        "k": k,
        "chunking": {"tamanho_palavras": TAMANHO_TRECHO, "sobreposicao": SOBREPOSICAO},
        "perguntas_com_resposta": n_com,
        "perguntas_sem_resposta": n_sem,
        # Ambiente: os tempos dependem da máquina, então ela fica registrada.
        "ambiente": {
            "python": platform.python_version(),
            "sentence_transformers": sentence_transformers.__version__,
            "torch": torch.__version__,
            "processador": platform.processor(),
            "threads_cpu": torch.get_num_threads(),
        },
        "resultados": resultados,
        "avisos": [aviso_corte(r) for r in resultados],
    }
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(conteudo, arquivo, ensure_ascii=False, indent=2)
    return caminho


def main():
    parser = argparse.ArgumentParser(description="Compara modelos de embedding (Recall@k e MRR@k).")
    parser.add_argument("--colecao", default="vestibular-2027-1")
    parser.add_argument("--perguntas", default=str(ARQUIVO_PERGUNTAS))
    parser.add_argument("--modelos", nargs="+", default=list(MODELOS), choices=list(MODELOS))
    parser.add_argument("--pasta-resultados", default=str(PASTA_RESULTADOS))
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")  # acentos corretos no terminal do Windows

    trechos = carregar_trechos(args.colecao)
    documentos = {t["documento"] for t in trechos}
    try:
        com_resposta, sem_resposta, nao_preenchidas = carregar_perguntas(args.perguntas, documentos)
    except ErroPerguntas as erro:
        print(f"ERRO: {erro}")
        sys.exit(1)

    resultados = []
    for modelo in args.modelos:
        print(f"Avaliando {modelo} ({len(trechos)} trechos)... pode levar alguns minutos.", flush=True)
        resultados.append(avaliar_modelo(modelo, trechos, com_resposta, sem_resposta))

    imprimir_resultados(resultados, len(com_resposta), len(sem_resposta), nao_preenchidas)
    caminho = salvar_resultados(
        resultados, args.colecao, len(com_resposta), len(sem_resposta), args.pasta_resultados
    )
    print(f"\nResultados salvos em {caminho}")


if __name__ == "__main__":
    main()
