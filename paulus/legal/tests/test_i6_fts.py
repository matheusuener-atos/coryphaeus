"""
Portao da I6 - o indice lexico em SQLite FTS5 (src/lexico.py).

  - a normalizacao e a mesma para indexar e para consultar, com os quatro
    exemplos do contrato (art. 300, §1º, 13.105/2015, S. 331 TST);
  - a mesma consulta duas vezes da a mesma ordem;
  - o filtro por documento vale antes de ordenar;
  - o indice e incremental: abrir de novo nao reindexa nada, e o documento
    que sai do acervo sai do indice;
  - Recall@20 so-lexico no conjunto da demonstracao, como linha de base
    (tools/medir.py --so-busca faz a mesma conta pelo programa).

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_i6_fts.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tools"))
sys.path.insert(0, str(RAIZ / "tools" / "demo"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


TEXTO = """PETIÇÃO INICIAL

DO DIREITO
Nos termos do art. 300 do CPC (Lei 13.105/2015), a tutela de urgência será concedida.
Conforme a Súmula 331 do TST, o tomador responde subsidiariamente.

DOS PEDIDOS
Requer, com base no § 1º do art. 300, a concessão da tutela.
"""


def main() -> int:
    print("=" * 55)
    print("  I6 - FTS5 com normalizacao juridica")
    print("=" * 55)
    import lexico
    from extract import Document
    from search import ContractSearcher

    print("\na normalização, dos dois lados")
    pares = [("art. 300", "art 300"), ("§1º", "par 1"), ("13.105/2015", "13105 2015"), ("S. 331 TST", "sumula 331 tst")]
    for bruto, esperado in pares:
        checar(lexico.normalizar(bruto) == esperado, f"“{bruto}” → “{esperado}”", lexico.normalizar(bruto))
    no_texto = lexico.normalizar(TEXTO)
    for bruto, esperado in pares:
        checar(esperado in no_texto, f"o texto indexado também tem “{esperado}”")

    with tempfile.TemporaryDirectory() as tmp:
        indice = lexico.IndiceLexico(Path(tmp) / "lexico.db")
        docs = [Document(name="Peticao.pdf", path="x/Peticao.pdf", text=TEXTO, sha1="1" * 40),
                Document(name="Contrato.pdf", path="x/Contrato.pdf",
                         text="CLÁUSULA 1ª - DO OBJETO\nPrestação de serviços, observado o art. 300 do Código Civil.\n\n"
                              "CLÁUSULA 2ª - DO PREÇO\nR$ 10.000,00 por mês.", sha1="2" * 40)]
        s = ContractSearcher(estrutural=True, lexico=indice)
        s.add_contracts(docs)
        s.build()

        print("\na busca")
        um = [h.chunk.chunk_id for h in s.search("art. 300", top_k=5, per_doc_limit=5)]
        dois = [h.chunk.chunk_id for h in s.search("art. 300", top_k=5, per_doc_limit=5)]
        checar(um and um == dois, "a mesma consulta duas vezes, a mesma ordem", (um, dois))
        achou = s.search("súmula 331 do TST", top_k=1)
        checar(achou and "331" in achou[0].chunk.text, "“súmula 331 do TST” acha “Súmula 331 do TST”")
        achou = s.search("S. 331 TST", top_k=1)
        checar(achou and "331" in achou[0].chunk.text, "“S. 331 TST” acha o mesmo trecho")
        achou = s.search("paragrafo 1 do artigo 300", top_k=1)
        checar(achou and "§ 1º" in achou[0].chunk.text, "“parágrafo 1 do artigo 300” acha “§ 1º do art. 300”")
        so = s.search("art. 300", top_k=5, per_doc_limit=5, documentos=["Contrato.pdf"])
        checar(so and all(h.doc_name == "Contrato.pdf" for h in so), "o filtro por documento vale antes da busca",
               [h.doc_name for h in so])

        print("\nincremental")
        s2 = ContractSearcher(estrutural=True, lexico=indice)
        s2.add_contracts(docs)
        chunks = s2.chunks
        checar(indice.sincronizar(chunks)["entraram"] == 0, "abrir de novo não reindexa nada")
        so_um = [c for c in chunks if c.doc_name == "Peticao.pdf"]
        mudou = indice.sincronizar(so_um)
        checar(mudou["sairam"] == 1 and not indice.buscar("preço", 5, ["Contrato.pdf"]),
               "o documento que saiu do acervo sai do índice", mudou)
        indice.fechar()

    print("\nRecall@20 só léxico, no conjunto da demonstração (linha de base)")
    import medir
    from criar_demo import DOCUMENTOS

    demo = []
    for nome, blocos in DOCUMENTOS.items():
        texto = "\n\n".join(t for _, t in blocos)
        demo.append(Document(name=Path(nome).name, path=nome, text=texto, sha1=""))
    with tempfile.TemporaryDirectory() as tmp:
        indice = lexico.IndiceLexico(Path(tmp) / "lexico.db")
        s = ContractSearcher(estrutural=True, lexico=indice)
        s.add_contracts(demo)
        s.build()
        conjunto = medir.ler_conjunto(medir.CONJUNTO_DEMO)
        linhas = [medir.medir_busca(s, p) for p in conjunto]
        r20 = sum(r["recall20"] for r in linhas) / len(linhas)
        r6 = sum(r["recall6"] for r in linhas) / len(linhas)
        mrr = sum(r["rr6"] for r in linhas) / len(linhas)
        print(f"  ...  Recall@20 {r20:.2f} · Recall@6 {r6:.2f} · MRR@6 {mrr:.2f} ({len(linhas)} perguntas, {len(s.chunks)} trechos)")
        checar(r20 > 0, "o índice léxico acha as frases esperadas", r20)
        indice.fechar()

    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for f in _falhas:
            print("   -", f)
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
