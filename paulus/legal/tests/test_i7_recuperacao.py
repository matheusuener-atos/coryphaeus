"""
Portao da I7 - denso + RRF + orcamento, e a virada do "ler tudo"
(src/denso.py, src/recuperacao.py).

Sem Ollama:
  - a fusao RRF (k=60) da a conta certa, e o trecho fraco nao entra;
  - o orcamento: no maximo 6 trechos, 3000 tokens, 3 por documento, e o
    quase-duplicado (cosseno >= 0,92) fica de fora;
  - vetores de outro espaco nunca se misturam;
  - o backfill cede a vez antes de cada lote e termina sem faltar trecho;
  - a virada (`ia.leitura = "trechos"`): acervo grande le os trechos, escopo
    pequeno e "leia o documento inteiro" leem tudo; a janela cai para 8192.

Com o Ollama e o bge-m3 (senao pula), no conjunto da demonstracao:
  - Recall@20 hibrido >= o melhor dos dois sozinhos;
  - Recall@6 >= 0,80 e contexto p50 <= 3000 tokens.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_i7_recuperacao.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "habilidades"))
sys.path.insert(0, str(RAIZ / "tools"))
sys.path.insert(0, str(RAIZ / "tools" / "demo"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


class Vetores:
    """
    O vetorizador de mentira: cada palavra cai numa das 1024 posicoes (hash
    estavel). Texto igual da cosseno 1; trechos de assuntos diferentes, menos.
    """

    def __init__(self) -> None:
        self.chamadas = 0

    def vetores(self, textos):
        import hashlib
        import re

        self.chamadas += 1
        linhas = []
        for t in textos:
            v = np.full(1024, 1e-4, dtype=np.float32)
            for palavra in re.findall(r"\w+", t.lower()):
                v[int(hashlib.md5(palavra.encode()).hexdigest(), 16) % 1024] += 1
            linhas.append(v / np.linalg.norm(v))
        return np.vstack(linhas)


def test_rrf_e_orcamento() -> None:
    print("\na fusão e o orçamento")
    import recuperacao

    fundidos = dict(recuperacao.rrf([["a", "b", "c"], ["b", "d"]]))
    checar(abs(fundidos["b"] - (1 / 62 + 1 / 61)) < 1e-9 and max(fundidos, key=fundidos.get) == "b",
           "o que está bem nas duas listas sobe (b)", fundidos)
    checar(abs(fundidos["a"] - 1 / 61) < 1e-9 and abs(fundidos["d"] - 1 / 62) < 1e-9, "1/(60+posição) em cada lista")
    checar(recuperacao.minimo_rrf() == 1 / 80, "abaixo da 20ª posição de uma lista só é fraco")

    import denso
    from extract import Document
    from search import ContractSearcher

    docs = []
    for n in range(4):
        blocos = [f"CLÁUSULA {k}ª - DA MULTA {k}\nA multa por atraso da parcela {k} do contrato {n} é de {k}% "
                  f"sobre o valor, com prazo de {k} dias e foro da comarca {n}. " + f"Enchimento {n}-{k} " * 20 + "Texto de enchimento. " * 30
                  for k in range(1, 6)]
        docs.append(Document(name=f"Contrato {n}.pdf", path=f"x/{n}.pdf", text="\n\n".join(blocos), sha1=str(n) * 40))
    # Uma cópia quase idêntica de um trecho, em outro documento.
    docs.append(Document(name="Cópia.pdf", path="x/c.pdf", text=docs[0].text, sha1="9" * 40))
    with tempfile.TemporaryDirectory() as tmp:
        s = ContractSearcher(estrutural=True)
        s.add_contracts(docs)
        s.build()
        indice = denso.IndiceDenso(Path(tmp) / "d.db")
        vet = Vetores()
        indice.gravar(s.chunks, vet.vetores([c.text_embed for c in s.chunks]))
        hits = recuperacao.recuperar(s, "qual a multa por atraso?", denso=indice, vetorizador=vet)
        por_doc: dict[str, int] = {}
        for h in hits:
            por_doc[h.doc_name] = por_doc.get(h.doc_name, 0) + 1
        tokens = sum(len(h.chunk.text) for h in hits) // 3
        checar(0 < len(hits) <= 6, f"no máximo 6 trechos ({len(hits)})")
        checar(tokens <= 3000, f"no máximo 3000 tokens ({tokens})")
        checar(max(por_doc.values()) <= 3, "no máximo 3 por documento", por_doc)
        vetores = [indice.vetor_de(h.chunk.chunk_id) for h in hits]
        pares = [float(a @ b) for i, a in enumerate(vetores) for b in vetores[i + 1:]]
        checar(all(p < 0.92 for p in pares), "nenhum par quase igual (cosseno < 0,92)", max(pares) if pares else None)

        print("\nespaços de vetores")
        outro = denso.IndiceDenso(Path(tmp) / "d.db", espaco="outro-modelo|384|l2|v1")
        checar(outro.quantos() == 0 and not outro.buscar(np.ones(1024), 5),
               "vetores de outro espaço não aparecem na consulta")
        checar(len(indice.faltam(s.chunks)) == 0 and len(outro.faltam(s.chunks)) == len(s.chunks),
               "trocar de espaço pede vetorizar tudo de novo")
        outro.fechar()

        print("\no backfill")
        novo = denso.IndiceDenso(Path(tmp) / "b.db")
        cedeu = []
        b = denso.Backfill(novo, Vetores(), ceder=lambda: cedeu.append(1))
        b.iniciar(s.chunks)
        b.esperar(60)
        lotes = -(-len(s.chunks) // denso.LOTE)
        checar(len(cedeu) == lotes, f"cede a vez antes de cada lote ({len(cedeu)} de {lotes})")
        checar(not novo.faltam(s.chunks) and b.estado["feitos"] == len(s.chunks), "e termina sem faltar trecho",
               b.estado)
        menos = [c for c in s.chunks if c.doc_name != "Cópia.pdf"]
        checar(novo.podar(menos) == len(s.chunks) - len(menos), "o que saiu do acervo sai dos vetores")
        novo.fechar()
        indice.fechar()


def test_virada() -> None:
    print("\na virada do “ler tudo”")
    import inferencia
    import perguntar
    from habilidade_base import Contexto
    from inteligencia.catalogo import Catalogo

    class Buscador:
        def __init__(self, tamanho):
            self.tamanho = tamanho
            self.documents = []

        def caracteres(self):
            return self.tamanho

    chamou = []
    ctx = Contexto(searcher=Buscador(0), ia={"leitura": "trechos"}, recuperar=lambda q, d: chamou.append(q) or [])
    checar(perguntar._por_trechos(ctx, "qual a multa?", 200_000), "acervo grande: lê os trechos")
    checar(not perguntar._por_trechos(ctx, "qual a multa?", 9_000), "escopo que cabe em ~4000 tokens: lê tudo")
    checar(not perguntar._por_trechos(ctx, "leia o contrato inteiro e diga a multa", 200_000),
           "“leia o contrato inteiro”: lê tudo")
    checar(not perguntar._por_trechos(Contexto(ia={"leitura": "tudo"}, recuperar=lambda q, d: []), "x", 200_000),
           "com a chave em “tudo”, nada muda")
    o = inferencia.opcoes(Catalogo.carregar(), {"ia": {"leitura": "trechos"}}, "llama3.2:3b")
    checar(o.num_ctx == 8192, "depois da virada, a janela cai para 8192", o.num_ctx)
    o = inferencia.opcoes(Catalogo.carregar(), {"ia": {"leitura": "trechos", "janela_por_modelo": {"x:1b": 32768}}},
                          "x:1b")
    checar(o.num_ctx == 32768, "a janela escolhida para o modelo vale", o.num_ctx)


def test_com_ollama() -> None:
    print("\nno conjunto da demonstração, com o bge-m3 de verdade")
    import requests

    try:
        nomes = [m["name"] for m in requests.get("http://127.0.0.1:11434/api/tags", timeout=3).json()["models"]]
    except Exception:  # noqa: BLE001
        print("  (Ollama fora do ar: pulei)")
        return
    if not any(n.split(":")[0] == "bge-m3" for n in nomes):
        print("  (bge-m3 não instalado: pulei)")
        return
    import denso
    import lexico
    import medir
    import memoria
    from criar_demo import DOCUMENTOS
    from extract import Document
    from search import ContractSearcher

    docs = [Document(name=Path(n).name, path=n, text="\n\n".join(t for _, t in b), sha1="") for n, b in DOCUMENTOS.items()]
    with tempfile.TemporaryDirectory() as tmp:
        s = ContractSearcher(estrutural=True, lexico=lexico.IndiceLexico(Path(tmp) / "l.db"))
        s.add_contracts(docs)
        s.build()
        indice = denso.IndiceDenso(Path(tmp) / "d.db")
        vet = denso.Vetorizador("http://127.0.0.1:11434")
        b = denso.Backfill(indice, vet)
        b.iniciar(s.chunks)
        b.esperar(600)
        conjunto = medir.ler_conjunto(medir.CONJUNTO_DEMO)
        linhas, assunto, anterior = [], None, ""
        for p in conjunto:
            consulta = memoria.reescrever(p["pergunta"], anterior, assunto) if p.get("continua") else p["pergunta"]
            if consulta == p["pergunta"]:
                assunto = memoria.assunto_de(p["pergunta"]) or assunto
            anterior = consulta
            linhas.append(medir.medir_busca(s, p, consulta, indice, vet))
        media = lambda k: sum(r[k] for r in linhas) / len(linhas)  # noqa: E731
        tokens = sorted(r["tokens_contexto"] for r in linhas)[len(linhas) // 2]
        print(f"  ...  só léxico R@20 {media('lexico20'):.2f} · só denso R@20 {media('denso20'):.2f} · "
              f"híbrido R@20 {media('recall20'):.2f} · R@6 {media('recall6'):.2f} · MRR@6 {media('rr6'):.2f} · "
              f"contexto p50 {tokens} tokens ({len(s.chunks)} trechos, {indice.quantos()} vetores)")
        checar(media("recall20") >= max(media("lexico20"), media("denso20")) - 1e-9,
               "híbrido R@20 não fica abaixo do melhor dos dois")
        checar(media("recall6") >= 0.80, "Recall@6 >= 0,80", media("recall6"))
        checar(tokens <= 3000, "contexto p50 <= 3000 tokens", tokens)
        indice.fechar()
        s.lexico.fechar()


def main() -> int:
    print("=" * 55)
    print("  I7 - denso + RRF + a virada")
    print("=" * 55)
    test_rrf_e_orcamento()
    test_virada()
    test_com_ollama()
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
