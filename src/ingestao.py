"""Ingestão: transforma os PDFs de uma coleção em trechos com documento, página e posição.

Fluxo:
    1. lê o manifesto.yaml da coleção e confere se ele bate com os PDFs da pasta;
    2. extrai o texto de cada página com PyMuPDF;
    3. divide o texto em trechos de tamanho fixo (~400 palavras, 15% de sobreposição), guardando a página onde cada trecho começa e termina;
    4. salva tudo em data/processed/<colecao>/trechos.json.

Ainda não usa banco nem embeddings (isso é da Etapa 4).

Uso:
    .\\.venv\\Scripts\\python -m src.ingestao vestibular-2027-1
"""

import argparse
import datetime
import json
import re
import sys
from collections import Counter
from pathlib import Path

import pymupdf
import yaml

PASTA_RAW = Path("data/raw")
PASTA_PROCESSADA = Path("data/processed")

TAMANHO_TRECHO = 400
SOBREPOSICAO = 0.15 
MIN_CARACTERES_PAGINA = 20


class ErroManifesto(Exception): 
    """O manifesto não bate com os PDFs da pasta (ou está mal preenchido)."""


def _para_json(valor):
    """Converte o que o YAML lê como data (datetime.date) em texto 'AAAA-MM-DD'.

    O PyYAML transforma `2026-08-25` em um objeto de data, e o json não sabe gravar
    esse tipo. A função percorre dicionários e listas para achar datas em qualquer nível.
    """
    if isinstance(valor, (datetime.date, datetime.datetime)):
        return valor.isoformat()
    if isinstance(valor, dict):
        return {chave: _para_json(v) for chave, v in valor.items()}
    if isinstance(valor, list):
        return [_para_json(v) for v in valor]
    return valor


def carregar_manifesto(pasta_colecao):
    """Lê o manifesto.yaml e devolve a lista de documentos.

    Falha (ErroManifesto) se faltar o manifesto, se algum documento não tiver
    'arquivo' ou 'titulo', se um PDF listado não existir na pasta, ou se houver
    PDF na pasta que não está no manifesto.
    """
    pasta_colecao = Path(pasta_colecao)
    caminho = pasta_colecao / "manifesto.yaml"
    if not caminho.exists():
        raise ErroManifesto(f"Manifesto não encontrado: {caminho}")

    with open(caminho, encoding="utf-8") as arquivo:
        manifesto = yaml.safe_load(arquivo) or {}

    documentos = manifesto.get("documentos") or []
    if not documentos:
        raise ErroManifesto(f"O manifesto {caminho} não lista nenhum documento.")

    for i, doc in enumerate(documentos, start=1):
        for campo in ("arquivo", "titulo"):
            if not doc.get(campo):
                raise ErroManifesto(f"Documento nº {i} do manifesto está sem '{campo}'.")

    listados = {doc["arquivo"] for doc in documentos}
    na_pasta = {pdf.name for pdf in pasta_colecao.glob("*.pdf")}

    faltando = sorted(listados - na_pasta)
    fora_do_manifesto = sorted(na_pasta - listados)
    erros = []
    if faltando:
        erros.append("PDFs listados no manifesto, mas ausentes da pasta: " + ", ".join(faltando))
    if fora_do_manifesto:
        erros.append("PDFs na pasta, mas fora do manifesto: " + ", ".join(fora_do_manifesto))
    if erros:
        raise ErroManifesto(f"Manifesto de {pasta_colecao} não bate com a pasta.\n- " + "\n- ".join(erros))

    return _para_json(documentos)


def extrair_paginas(caminho_pdf):
    """Devolve uma lista [(numero_da_pagina, texto), ...], com páginas começando em 1."""
    paginas = []
    with pymupdf.open(caminho_pdf) as pdf:
        for numero, pagina in enumerate(pdf, start=1):
            paginas.append((numero, pagina.get_text()))
    return paginas


def _normalizar_linha(linha):
    """Prepara uma linha para comparação: troca números por '#' e junta espaços.

    Assim "Manual do Candidato Pág. 5" e "... Pág. 6" viram a mesma linha
    ("Manual do Candidato Pág. #"), e o cabeçalho é reconhecido como repetido.
    """
    linha = re.sub(r"\d+", "#", linha)
    return " ".join(linha.split())


def remover_linhas_repetidas(paginas):
    """Remove cabeçalhos e rodapés: linhas que aparecem em mais da metade das páginas.

    A comparação ignora números (ver _normalizar_linha). A linha também precisa
    aparecer em pelo menos 2 páginas; sem isso, num documento de 1 página toda
    linha estaria "em mais da metade" e o texto inteiro seria apagado.

    Devolve (paginas_limpas, linhas_removidas), com as linhas removidas já normalizadas.
    """

    contagem = Counter()
    for _, texto in paginas:
        linhas_da_pagina = {_normalizar_linha(l) for l in texto.splitlines()}
        linhas_da_pagina = {l for l in linhas_da_pagina if re.search(r"[\w#]", l)}
        contagem.update(linhas_da_pagina)

    metade = len(paginas) / 2
    repetidas = {linha for linha, n in contagem.items() if n > metade and n >= 2}

    paginas_limpas = []
    for numero, texto in paginas:
        mantidas = [l for l in texto.splitlines() if _normalizar_linha(l) not in repetidas]
        paginas_limpas.append((numero, "\n".join(mantidas)))
    return paginas_limpas, sorted(repetidas)


def dividir_em_trechos(paginas, tamanho=TAMANHO_TRECHO, sobreposicao=SOBREPOSICAO):
    """Divide o texto das páginas em trechos de `tamanho` palavras com sobreposição.

    Ideia: monta uma lista única com todas as palavras do documento, e cada palavra
    "lembra" de que página veio. Depois uma janela de `tamanho` palavras anda pela
    lista, avançando `passo` palavras por vez. Como o passo é menor que o tamanho,
    o fim de um trecho se repete no começo do próximo (a sobreposição).

    Ex.: tamanho=400 e sobreposicao=0.15 → 60 palavras repetidas, passo de 340.

    Devolve uma lista de dicionários com pagina, pagina_fim, posicao e texto.
    """
    palavras = []
    for numero, texto in paginas:
        for palavra in texto.split():
            palavras.append((palavra, numero))

    if not palavras:
        return []

    repetidas = round(tamanho * sobreposicao)
    passo = tamanho - repetidas

    trechos = []
    inicio = 0
    while True:
        janela = palavras[inicio:inicio + tamanho]
        trechos.append({
            "pagina": janela[0][1],
            "pagina_fim": janela[-1][1],
            "posicao": len(trechos),
            "texto": " ".join(palavra for palavra, _ in janela),
        })
        if inicio + tamanho >= len(palavras):
            break
        inicio += passo

    return trechos


def processar_colecao(colecao, pasta_raw=PASTA_RAW, pasta_saida=PASTA_PROCESSADA):
    """Executa a ingestão de uma coleção e salva data/processed/<colecao>/trechos.json.

    Devolve um resumo por documento: páginas, trechos e páginas sem texto.
    """
    pasta_colecao = Path(pasta_raw) / colecao
    documentos = carregar_manifesto(pasta_colecao)

    todos_trechos = []
    resumo = []
    for doc in documentos:
        paginas = extrair_paginas(pasta_colecao / doc["arquivo"])
        sem_texto = [n for n, texto in paginas if len(texto.strip()) < MIN_CARACTERES_PAGINA]

        paginas, linhas_removidas = remover_linhas_repetidas(paginas)
        trechos = dividir_em_trechos(paginas)
        for trecho in trechos:
            todos_trechos.append({
                "documento": doc["arquivo"],
                "titulo": doc["titulo"],
                **trecho,
                "metadados": doc.get("metadados") or {},
            })

        resumo.append({
            "documento": doc["arquivo"],
            "paginas": len(paginas),
            "trechos": len(trechos),
            "paginas_sem_texto": sem_texto,
            "linhas_removidas": linhas_removidas,
        })

    pasta_destino = Path(pasta_saida) / colecao
    pasta_destino.mkdir(parents=True, exist_ok=True)
    with open(pasta_destino / "trechos.json", "w", encoding="utf-8") as arquivo:
        json.dump(todos_trechos, arquivo, ensure_ascii=False, indent=2)

    return resumo


def imprimir_resumo(colecao, resumo):
    """Mostra o resumo da ingestão e avisa sobre páginas sem texto."""
    print(f"\nColeção: {colecao}")
    print(f"{'Documento':<48}{'Páginas':>8}{'Trechos':>9}")
    for item in resumo:
        print(f"{item['documento']:<48}{item['paginas']:>8}{item['trechos']:>9}")
    total_paginas = sum(item["paginas"] for item in resumo)
    total_trechos = sum(item["trechos"] for item in resumo)
    print(f"{'TOTAL: ' + str(len(resumo)) + ' documentos':<48}{total_paginas:>8}{total_trechos:>9}")

    for item in resumo:
        if item["linhas_removidas"]:
            print(f"Cabeçalhos/rodapés removidos de {item['documento']}:")
            for linha in item["linhas_removidas"]:
                print(f"    {linha!r}")

    for item in resumo:
        if item["paginas_sem_texto"]:
            paginas = ", ".join(str(n) for n in item["paginas_sem_texto"])
            print(f"AVISO: {item['documento']} tem páginas sem texto ({paginas}); "
                  "podem ser capa, imagem ou página escaneada.")


def main():
    parser = argparse.ArgumentParser(description="Gera os trechos de uma coleção de PDFs.")
    parser.add_argument("colecao", help="nome da pasta em data/raw/ (ex.: vestibular-2027-1)")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    try:
        resumo = processar_colecao(args.colecao)
    except ErroManifesto as erro:
        print(f"ERRO: {erro}")
        sys.exit(1)
    imprimir_resumo(args.colecao, resumo)
    print(f"\nTrechos salvos em {PASTA_PROCESSADA / args.colecao / 'trechos.json'}")


if __name__ == "__main__":
    main()