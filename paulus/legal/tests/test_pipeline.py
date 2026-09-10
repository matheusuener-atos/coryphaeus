"""
Testes do pipeline de extracao e busca.

Nao dependem do Ollama nem de rede - rodam em segundos.

    python tests/test_pipeline.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from extract import Document, index_all_contracts  # noqa: E402
from search import (  # noqa: E402
    Chunk,
    ContractSearcher,
    chunk_document,
    merge_chunks,
    normalize,
    tokenize,
)

SAMPLES = RAIZ / "data" / "samples"
_falhas: list[str] = []


def checar(condicao: bool, descricao: str) -> None:
    if condicao:
        print(f"  ok   {descricao}")
    else:
        print(f"  FALHA {descricao}")
        _falhas.append(descricao)


# ---------------------------------------------------------------- tokenizacao


def test_normalizacao() -> None:
    print("\ntokenizacao")
    checar(normalize("CLÁUSULA Rescisão") == "clausula rescisao", "remove acento e caixa")
    checar("clausula" in tokenize("CLÁUSULA QUARTA"), "clausula acentuada vira token")
    checar("de" not in tokenize("contrato de locacao"), "stopword 'de' removida")
    checar("90" in tokenize("prazo de 90 dias"), "numero de 2 digitos preservado")
    checar(tokenize("") == [], "texto vazio nao quebra")


# -------------------------------------------------------------------- chunking


def test_chunking() -> None:
    print("\nchunking")
    texto = "\n\n".join(f"Paragrafo {i}. " + "palavra " * 60 for i in range(10))
    doc = Document(name="x.txt", path="x.txt", text=texto)
    chunks = chunk_document(doc, size=1200, overlap=200)

    checar(len(chunks) > 1, "texto longo gera mais de um trecho")
    checar(all(c.text.strip() for c in chunks), "nenhum trecho vazio")
    checar([c.index for c in chunks] == list(range(len(chunks))), "indices sequenciais")
    checar(max(len(c.text) for c in chunks) <= 1600, "trechos respeitam o tamanho alvo")
    checar("Paragrafo 9" in chunks[-1].text, "fim do documento chega no ultimo trecho")

    # paragrafo unico gigante, sem quebras de linha
    doc_denso = Document(name="y.txt", path="y.txt", text="frase. " * 800)
    checar(len(chunk_document(doc_denso)) > 1, "paragrafo unico gigante e fatiado")

    doc_curto = Document(name="z.txt", path="z.txt", text="Contrato curto.")
    checar(len(chunk_document(doc_curto)) == 1, "documento curto vira um trecho so")


def test_merge() -> None:
    print("\nremontagem de trechos")
    a = Chunk("c.txt", "c.txt", 0, "CLAUSULA 1. Objeto do contrato. TRECHO COMPARTILHADO ENTRE OS DOIS BLOCOS")
    b = Chunk("c.txt", "c.txt", 1, "TRECHO COMPARTILHADO ENTRE OS DOIS BLOCOS CLAUSULA 2. Prazo de vigencia.")
    juntos = merge_chunks([a, b])
    checar(juntos.count("TRECHO COMPARTILHADO") == 1, "sobreposicao de vizinhos removida")
    checar("CLAUSULA 1" in juntos and "CLAUSULA 2" in juntos, "conteudo dos dois trechos preservado")

    distante = Chunk("c.txt", "c.txt", 5, "CLAUSULA 9. Foro.")
    checar("[...]" in merge_chunks([a, distante]), "lacuna entre trechos e sinalizada")
    checar(merge_chunks([]) == "", "lista vazia nao quebra")


# ---------------------------------------------------------------------- busca


def test_busca() -> None:
    print("\nbusca BM25")
    docs = index_all_contracts(SAMPLES, verbose=False)
    checar(len(docs) == 3, f"3 contratos de exemplo extraidos (achou {len(docs)})")
    checar(any(d.name.endswith(".docx") for d in docs), "extrator de DOCX funcionou")
    checar(all(d.chars > 500 for d in docs), "todos os contratos tem texto")

    searcher = ContractSearcher()
    searcher.add_contracts(docs)
    searcher.build()

    hits = searcher.search("aluguel IPTU condominio", top_k=3)
    checar(bool(hits) and "locacao" in hits[0].doc_name, "pergunta sobre aluguel acha o contrato de locacao")

    hits_nda = searcher.search("acordo de confidencialidade due diligence", top_k=3)
    checar(bool(hits_nda) and "nda" in hits_nda[0].doc_name, "pergunta sobre NDA acha o NDA")

    checar(searcher.search("xyzabc123inexistente") == [], "termo inexistente retorna vazio")
    checar(searcher.search("") == [], "busca vazia retorna vazio")

    penalidades = searcher.search("multa penalidade rescisao", top_k=6)
    por_doc: dict[str, int] = {}
    for h in penalidades:
        por_doc[h.doc_name] = por_doc.get(h.doc_name, 0) + 1
    checar(max(por_doc.values()) <= 2, "nenhum contrato ocupa mais que o limite por documento")
    checar(all(h.snippet for h in penalidades), "todo resultado traz um snippet")


def test_busca_poucos_contratos() -> None:
    """
    Regressao: o IDF do BM25 zera (ou fica negativo) para termos presentes em
    metade ou mais dos trechos. Com um ou dois contratos indexados a busca
    devolvia vazio mesmo com o termo presente no texto.
    """
    print("\nbusca com poucos contratos indexados")

    um = Document(
        name="unico.txt",
        path="unico.txt",
        text="CLAUSULA 2. Multa de 15% por descumprimento contratual.",
    )
    searcher = ContractSearcher()
    searcher.add_contracts([um])
    searcher.build()

    hits = searcher.search("descumprimento", top_k=3)
    checar(bool(hits), "termo presente e encontrado com um unico contrato indexado")
    checar(bool(searcher.format_context(hits)), "contexto montado com um unico contrato")
    checar(searcher.search("hipoteca maritima", top_k=3) == [], "termo ausente continua vazio")

    dois = Document(name="outro.txt", path="outro.txt", text="CLAUSULA 1. Prazo de 12 meses.")
    searcher2 = ContractSearcher()
    searcher2.add_contracts([um, dois])
    searcher2.build()
    achados = searcher2.search("descumprimento", top_k=3)
    checar(bool(achados), "termo presente e encontrado com dois contratos indexados")
    checar(achados[0].doc_name == "unico.txt", "acha o contrato certo, nao o outro")


def test_contexto() -> None:
    print("\nmontagem do contexto para o LLM")
    docs = index_all_contracts(SAMPLES, verbose=False)
    searcher = ContractSearcher()
    searcher.add_contracts(docs)
    searcher.build()

    hits = searcher.search("multa penalidade rescisao", top_k=6)
    ctx = searcher.format_context(hits)
    cabecalhos = [l for l in ctx.splitlines() if l.startswith("--- ")]

    checar(len(cabecalhos) == len(set(cabecalhos)), "cada contrato aparece uma unica vez no contexto")
    checar(bool(cabecalhos), "contexto tem cabecalho de origem")
    checar(len(searcher.format_context(hits, max_chars=500)) <= 700, "max_chars limita o contexto")
    checar(searcher.format_context([]) == "", "sem hits, contexto vazio")


# ---------------------------------------------------------------------- cache


def test_cache() -> None:
    print("\ncache de extracao")
    with tempfile.TemporaryDirectory() as tmp:
        pasta = Path(tmp) / "contratos"
        pasta.mkdir()
        (pasta / "a.txt").write_text("CLAUSULA 1. Prazo de 12 meses.", encoding="utf-8")
        cache = Path(tmp) / "index.json"

        primeira = index_all_contracts(pasta, cache, verbose=False)
        checar(len(primeira) == 1 and cache.exists(), "primeira passada extrai e grava cache")

        segunda = index_all_contracts(pasta, cache, verbose=False)
        checar(segunda[0].text == primeira[0].text, "segunda passada reaproveita o cache")

        (pasta / "a.txt").write_text("CLAUSULA 1. Prazo de 24 meses.", encoding="utf-8")
        terceira = index_all_contracts(pasta, cache, verbose=False)
        checar("24 meses" in terceira[0].text, "arquivo alterado e reextraido")

        (pasta / "ignorado.xyz").write_text("nao suportado", encoding="utf-8")
        checar(len(index_all_contracts(pasta, cache, verbose=False)) == 1, "formato nao suportado e ignorado")

    checar(index_all_contracts(Path("pasta/que/nao/existe"), verbose=False) == [], "pasta inexistente retorna vazio")


def main() -> int:
    print("=" * 55)
    print("  PAULUS Legal - testes do pipeline (sem LLM)")
    print("=" * 55)

    if not SAMPLES.exists():
        print(f"\nERRO: pasta de exemplos nao encontrada: {SAMPLES}")
        return 1

    test_normalizacao()
    test_chunking()
    test_merge()
    test_busca()
    test_busca_poucos_contratos()
    test_contexto()
    test_cache()

    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print(f"    - {f}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
