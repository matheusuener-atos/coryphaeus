"""
Portao da I5 - trechos pela estrutura do documento (src/trechos.py).

  - o mesmo documento da os mesmos `chunk_id`, e reindexar do zero tambem;
  - todo trecho de documento paginado tem pagina;
  - nenhum trecho atravessa clausula, secao ou artigo: ou ele e feito de
    secoes inteiras, ou fica dentro de uma so;
  - a API publica do buscador continua a mesma (search, tudo,
    dos_documentos, format_context);
  - 20 trechos de cada regime impressos para inspecao (--mostrar).

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_i5_trechos.py [--mostrar]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def contrato_longo() -> str:
    """Um contrato de 12 clausulas em 4 paginas, com uma clausula enorme."""
    partes = ["[pagina 1]", "CONTRATO DE PRESTAÇÃO DE SERVIÇOS", "",
              "CONTRATANTE: ACME COMÉRCIO LTDA. CONTRATADA: BETA SERVIÇOS LTDA.", ""]
    for n in range(1, 13):
        if n == 5:
            partes.append("[pagina 2]")
        if n == 9:
            partes.append("[pagina 4]")
        partes.append(f"CLÁUSULA {n}ª - DA OBRIGAÇÃO NÚMERO {n}")
        if n == 7:
            # A clausula enorme: passa de 1000 tokens e vira janelas dentro dela.
            corpo = " ".join(f"Item {k} da cláusula sétima: a CONTRATADA manterá registro do serviço "
                             f"prestado no mês {k}, com a assinatura do responsável." for k in range(1, 70))
            partes.insert(len(partes), corpo)
            partes.append("[pagina 3]")
            partes.append("Parágrafo único. O registro fica à disposição da CONTRATANTE por cinco anos.")
        else:
            partes.append(f"A parte cumprirá a obrigação {n} no prazo de {n * 5} dias, sob pena de multa "
                          f"de {n}% sobre o valor do contrato, corrigida pelo IPCA.")
        partes.append("")
    partes.append("DO FORO")
    partes.append("Fica eleito o foro da Comarca de Belém/PA.")
    return "\n".join(partes)


def lei() -> str:
    linhas = ["LEI Nº 99.999, DE 1º DE JANEIRO DE 2026", "Dispõe sobre o teste de trechos.", ""]
    for n in range(1, 31):
        linhas.append(f"Art. {n}º O teste número {n} observará o disposto nesta Lei.")
        if n % 3 == 0:
            linhas.append(f"§ 1º O parágrafo do artigo {n} vale para todos os casos.")
            linhas.append(f"I - inciso primeiro do artigo {n};")
            linhas.append(f"II - inciso segundo do artigo {n}.")
        linhas.append("")
    return "\n".join(linhas)


def fronteiras(texto: str, regime: str) -> list[int]:
    import trechos

    padrao = trechos.RE_ARTIGO if regime == trechos.REGIME_LEI else trechos.RE_CABECALHO
    return [m.start() for m in padrao.finditer(texto)]


def atravessa(texto: str, chunk, marcas: list[int]) -> bool:
    """
    O trecho corta uma secao ao meio: ele comeca antes de uma fronteira e
    termina depois dela, sem terminar numa fronteira (ou no fim).
    """
    import trechos

    dentro = [m for m in marcas if chunk.char_start < m < chunk.char_end]
    if not dentro:
        return False  # dentro de uma secao so
    # Feito de secoes inteiras: comeca numa fronteira (ou no preambulo) e
    # termina numa fronteira (ou no fim do texto).
    seguinte = next((m for m in marcas if m >= chunk.char_end), len(texto))
    termina_bem = texto[chunk.char_end:seguinte].strip() == ""
    anterior = max([m for m in marcas if m <= chunk.char_start] or [0])
    comeca_bem = texto[anterior:chunk.char_start].strip() == "" or anterior == 0 and not texto[:chunk.char_start].strip()
    _ = trechos
    return not (termina_bem and comeca_bem)


def main() -> int:
    print("=" * 55)
    print("  I5 - trechos pela estrutura")
    print("=" * 55)
    from extract import Document
    from search import ContractSearcher, chunk_estrutural

    doc = Document(name="Contrato ACME.pdf", path="x/Contrato ACME.pdf", text=contrato_longo(), pages=4, sha1="a" * 40)
    doc_lei = Document(name="Lei 99999.pdf", path="x/Lei 99999.pdf", text=lei(), pages=0, sha1="b" * 40)

    print("\nids estáveis")
    um, dois = chunk_estrutural(doc), chunk_estrutural(doc)
    checar([c.chunk_id for c in um] == [c.chunk_id for c in dois], "mesmo documento, mesmos ids")
    import trechos

    versao = trechos.versao_de("a" * 40, doc.text, doc.name)
    checar(all(c.chunk_id == f"chunk_{versao}_{c.char_start:08d}" for c in um), "o id é versão + posição",
           [c.chunk_id for c in um[:2]])
    copia = Document(name="Contrato ACME (1).pdf", path="x/Contrato ACME (1).pdf", text=doc.text, sha1=doc.sha1)
    checar(not {c.chunk_id for c in um} & {c.chunk_id for c in chunk_estrutural(copia)},
           "a cópia com outro nome tem ids próprios")
    s1 = ContractSearcher(estrutural=True)
    s1.add_contracts([doc, doc_lei])
    s2 = ContractSearcher(estrutural=True)
    s2.add_contracts([doc_lei, doc])
    checar(sorted(c.chunk_id for c in s1.chunks) == sorted(c.chunk_id for c in s2.chunks),
           "reindexar do zero, em outra ordem, dá os mesmos ids")
    checar(len({c.chunk_id for c in s1.chunks}) == len(s1.chunks), "nenhum id repetido")

    print("\npáginas e regime")
    checar(all(c.pagina_inicio for c in um), "todo trecho do documento paginado tem página",
           [(c.chunk_id, c.pagina_inicio) for c in um if not c.pagina_inicio])
    setima = [c for c in um if "sétima" in c.text]
    checar(len(setima) >= 2 and setima[-1].pagina_fim == 3, "a cláusula longa vira janelas e chega à página 3",
           [(c.pagina_inicio, c.pagina_fim) for c in setima])
    checar({c.regime for c in um} == {"B"} and {c.regime for c in chunk_estrutural(doc_lei)} == {"A"},
           "contrato é regime B, lei é regime A")

    print("\nnenhum trecho atravessa fronteira")
    for d in (doc, doc_lei):
        chunks = chunk_estrutural(d)
        marcas = fronteiras(d.text, chunks[0].regime)
        ruins = [c.chunk_id for c in chunks if atravessa(d.text, c, marcas)]
        checar(not ruins, f"{d.name}: {len(chunks)} trechos, nenhum corta seção ao meio", ruins)
        grandes = [c for c in chunks if len(c.text) > 1000 * 3 + 50]
        checar(not grandes, f"{d.name}: nenhum trecho acima de ~1000 tokens", [len(c.text) for c in grandes])
        checar(all(c.text == d.text[c.char_start:c.char_end] for c in chunks), f"{d.name}: o texto é a faixa exata")
    artigos = chunk_estrutural(doc_lei)
    checar(all(("parágrafo do artigo 3 vale" in c.text) == ("Art. 3º O" in c.text) for c in artigos)
           and all(len(re.findall(r"^Art\. \d+", c.text, re.M)) == 1 for c in artigos if c.text.startswith("Art.")),
           "um artigo por trecho, e o parágrafo fica com o artigo dele",
           [c.text[:40] for c in artigos[:3]])

    print("\na API do buscador")
    hits = s1.search("multa da obrigação 11", top_k=3)
    checar(hits and "11" in hits[0].chunk.text, "search acha a cláusula 11", [h.chunk.text[:60] for h in hits])
    checar(len(s1.tudo()) == len(s1.chunks), "tudo devolve todos")
    so = s1.dos_documentos(["Contrato ACME.pdf"])
    checar(so and all(h.doc_name == "Contrato ACME.pdf" for h in so), "dos_documentos só o pedido")
    montado = s1.format_context(so, max_chars=200_000)
    checar("CLÁUSULA 12ª" in montado and montado.count("Parágrafo único") == 1,
           "format_context remonta sem repetir a sobreposição", montado.count("Parágrafo único"))

    if "--mostrar" in sys.argv:
        for nome, d in (("B", doc), ("A", doc_lei)):
            print(f"\n--- regime {nome}: os primeiros 20 trechos ---")
            for c in chunk_estrutural(d)[:20]:
                print(f"[{c.chunk_id} p.{c.pagina_inicio}-{c.pagina_fim}] {c.text_embed[:160]!r}")

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
