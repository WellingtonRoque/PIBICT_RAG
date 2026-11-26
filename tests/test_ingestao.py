"""Testes da ingestão (src/ingestao.py).

Rodar a partir da raiz do repositório:
    .\\.venv\\Scripts\\python -m pytest tests/test_ingestao.py -v

A maioria dos testes usa páginas "inventadas" (listas de texto), para sabermos de antemão
o resultado certo. O último grupo roda a ingestão na coleção real.
"""

import json
from pathlib import Path

import pytest
import yaml

from src.ingestao import (
    ErroManifesto,
    carregar_manifesto,
    dividir_em_trechos,
    processar_colecao,
    remover_linhas_repetidas,
)


def paginas_falsas(palavras_por_pagina):
    """Cria páginas em que cada palavra diz de onde veio: 'p2_15' = página 2, palavra 15.

    Assim, olhando só para a palavra, o teste sabe qual é a página certa.
    """
    paginas = []
    for numero, quantidade in enumerate(palavras_por_pagina, start=1):
        texto = " ".join(f"p{numero}_{i}" for i in range(quantidade))
        paginas.append((numero, texto))
    return paginas


def pagina_da_palavra(palavra):
    """'p2_15' → 2"""
    return int(palavra.split("_")[0][1:])


# ---------------------------------------------------------------- páginas e sobreposição

def test_pagina_e_pagina_fim_vem_da_primeira_e_da_ultima_palavra():
    trechos = dividir_em_trechos(paginas_falsas([300, 300, 300]))
    for trecho in trechos:
        palavras = trecho["texto"].split()
        assert trecho["pagina"] == pagina_da_palavra(palavras[0])
        assert trecho["pagina_fim"] == pagina_da_palavra(palavras[-1])


def test_trecho_que_atravessa_a_virada_de_pagina():
    # 300 palavras na página 1: o primeiro trecho (400 palavras) termina na página 2.
    primeiro = dividir_em_trechos(paginas_falsas([300, 300]))[0]
    assert (primeiro["pagina"], primeiro["pagina_fim"]) == (1, 2)


def test_sobreposicao_de_15_por_cento():
    trechos = dividir_em_trechos(paginas_falsas([500, 500, 500]), tamanho=400, sobreposicao=0.15)
    assert len(trechos) > 2
    for atual, proximo in zip(trechos, trechos[1:]):
        # 15% de 400 = 60: as últimas 60 palavras de um trecho abrem o próximo.
        assert atual["texto"].split()[-60:] == proximo["texto"].split()[:60]


def test_tamanho_fixo_e_nenhuma_palavra_perdida():
    paginas = paginas_falsas([450, 450, 450])
    trechos = dividir_em_trechos(paginas)
    # Todos os trechos têm 400 palavras, menos talvez o último.
    assert all(len(t["texto"].split()) == 400 for t in trechos[:-1])
    # Toda palavra do documento aparece em algum trecho.
    todas = {p for _, texto in paginas for p in texto.split()}
    nos_trechos = {p for t in trechos for p in t["texto"].split()}
    assert todas == nos_trechos


def test_posicao_segue_a_ordem_dos_trechos():
    trechos = dividir_em_trechos(paginas_falsas([1000]))
    assert [t["posicao"] for t in trechos] == list(range(len(trechos)))


def test_documento_sem_texto_nao_gera_trechos():
    assert dividir_em_trechos([(1, ""), (2, "   \n ")]) == []


# ---------------------------------------------------------------- limpeza de cabeçalhos

def test_remove_cabecalho_e_rodape_ignorando_numeros():
    paginas = [
        (n, f"Manual do Candidato\nPág. {n}\nConteúdo único da página {n}\n{n}/4")
        for n in range(1, 5)
    ]
    limpas, removidas = remover_linhas_repetidas(paginas)

    assert "Manual do Candidato" in removidas
    assert "Pág. #" in removidas
    for numero, texto in limpas:
        assert "Manual do Candidato" not in texto
        assert "Pág." not in texto
        assert f"{numero}/4" not in texto


def test_limpeza_mantem_o_conteudo():
    # "Conteúdo único da página N" difere só no número, então seria "repetido".
    # Por isso aqui o conteúdo de cada página é diferente de verdade.
    conteudos = ["Inscrições até novembro", "Taxa de inscrição", "Isenção da taxa", "Dia da prova"]
    paginas = [(n, f"Cabeçalho\n{c}") for n, c in enumerate(conteudos, start=1)]
    limpas, _ = remover_linhas_repetidas(paginas)
    assert [texto for _, texto in limpas] == conteudos


def test_linha_em_exatamente_metade_das_paginas_fica():
    paginas = [(1, "Aviso\nA"), (2, "Aviso\nB"), (3, "C"), (4, "D")]
    _, removidas = remover_linhas_repetidas(paginas)
    assert removidas == []


def test_documento_de_uma_pagina_nao_perde_texto():
    paginas = [(1, "Portaria nº 5541\nDocumento assinado digitalmente")]
    limpas, removidas = remover_linhas_repetidas(paginas)
    assert removidas == []
    assert limpas == paginas


def test_linha_so_de_simbolos_nao_e_removida():
    paginas = [(n, f"•\nItem {chr(64 + n)}") for n in range(1, 5)]
    limpas, removidas = remover_linhas_repetidas(paginas)
    assert removidas == []
    assert all("•" in texto for _, texto in limpas)


# ---------------------------------------------------------------- manifesto

def criar_colecao(pasta, listados, na_pasta):
    """Cria uma coleção falsa: manifesto com `listados` e arquivos vazios `na_pasta`.

    Os PDFs podem ser vazios porque carregar_manifesto só confere os nomes.
    """
    manifesto = {
        "colecao": "teste",
        "documentos": [
            {"arquivo": nome, "titulo": f"Título de {nome}",
             "metadados": {"tipo": "portaria", "data": "2026-08-25"}}
            for nome in listados
        ],
    }
    (pasta / "manifesto.yaml").write_text(yaml.safe_dump(manifesto), encoding="utf-8")
    for nome in na_pasta:
        (pasta / nome).write_bytes(b"")


def test_manifesto_valido(tmp_path):
    criar_colecao(tmp_path, ["a.pdf", "b.pdf"], ["a.pdf", "b.pdf"])
    documentos = carregar_manifesto(tmp_path)
    assert [d["arquivo"] for d in documentos] == ["a.pdf", "b.pdf"]


def test_manifesto_falha_se_faltar_pdf(tmp_path):
    criar_colecao(tmp_path, ["a.pdf", "b.pdf"], ["a.pdf"])
    with pytest.raises(ErroManifesto, match="ausentes da pasta: b.pdf"):
        carregar_manifesto(tmp_path)


def test_manifesto_falha_se_sobrar_pdf(tmp_path):
    criar_colecao(tmp_path, ["a.pdf"], ["a.pdf", "c.pdf"])
    with pytest.raises(ErroManifesto, match="fora do manifesto: c.pdf"):
        carregar_manifesto(tmp_path)


def test_manifesto_falha_se_faltar_titulo(tmp_path):
    criar_colecao(tmp_path, ["a.pdf"], ["a.pdf"])
    caminho = tmp_path / "manifesto.yaml"
    manifesto = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    del manifesto["documentos"][0]["titulo"]
    caminho.write_text(yaml.safe_dump(manifesto), encoding="utf-8")
    with pytest.raises(ErroManifesto, match="sem 'titulo'"):
        carregar_manifesto(tmp_path)


def test_datas_do_manifesto_viram_texto(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"")
    (tmp_path / "manifesto.yaml").write_text(
        "documentos:\n"
        "  - arquivo: a.pdf\n"
        "    titulo: A\n"
        "    metadados: {data: 2026-08-25}\n",  # sem aspas: o YAML lê como data
        encoding="utf-8",
    )
    documentos = carregar_manifesto(tmp_path)
    assert documentos[0]["metadados"]["data"] == "2026-08-25"


# ---------------------------------------------------------------- coleção real

COLECAO_REAL = "vestibular-2027-1"
PASTA_REAL = Path("data/raw") / COLECAO_REAL


@pytest.fixture(scope="module")
def ingestao_real(tmp_path_factory):
    """Roda a ingestão real uma vez e grava o JSON numa pasta temporária."""
    if not PASTA_REAL.exists():
        pytest.skip(f"{PASTA_REAL} não encontrada")
    saida = tmp_path_factory.mktemp("processed")
    resumo = processar_colecao(COLECAO_REAL, pasta_saida=saida)
    with open(saida / COLECAO_REAL / "trechos.json", encoding="utf-8") as arquivo:
        trechos = json.load(arquivo)
    manifesto = {d["arquivo"]: d for d in carregar_manifesto(PASTA_REAL)}
    return resumo, trechos, manifesto


def test_real_todo_documento_do_manifesto_gera_trechos(ingestao_real):
    resumo, trechos, manifesto = ingestao_real
    assert {item["documento"] for item in resumo} == set(manifesto)
    assert {t["documento"] for t in trechos} == set(manifesto)


def test_real_trechos_tem_campos_e_paginas_validas(ingestao_real):
    resumo, trechos, _ = ingestao_real
    paginas_por_doc = {item["documento"]: item["paginas"] for item in resumo}
    for t in trechos:
        assert t["texto"].strip()
        assert 1 <= t["pagina"] <= t["pagina_fim"] <= paginas_por_doc[t["documento"]]


def test_real_metadados_e_titulo_vem_do_manifesto(ingestao_real):
    _, trechos, manifesto = ingestao_real
    for t in trechos:
        doc = manifesto[t["documento"]]
        assert t["titulo"] == doc["titulo"]
        assert t["metadados"] == doc["metadados"]


def test_real_portarias_tem_tipo_numero_e_data(ingestao_real):
    _, trechos, _ = ingestao_real
    portarias = [t for t in trechos if t["metadados"].get("tipo") == "portaria"]
    assert portarias
    for t in portarias:
        assert t["metadados"]["numero"] and t["metadados"]["data"]


def test_real_cabecalho_do_manual_foi_removido(ingestao_real):
    _, trechos, _ = ingestao_real
    do_manual = [t for t in trechos if t["documento"] == "manual-candidato-2027-1.pdf"]
    assert do_manual
    assert not any("Pág." in t["texto"] for t in do_manual)
