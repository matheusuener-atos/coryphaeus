"""
Portão da M1 da Biblioteca: o material de consulta no pipeline híbrido
(src/biblioteca/indice.py, regime C em src/trechos.py).

  - mesmo arquivo -> mesmos `chunk_id`; reindexar do zero -> mesmos ids;
  - nenhum trecho do regime C atravessa capítulo; o sumário, a folha de rosto
    e o cabeçalho repetido não viram trecho, nem aparecem em resultado;
  - os três casos registrados em src/material.py continuam certos:
      a tabela com "entre 20% e 30%" não vem quando se pergunta o êxito do
      contrato de um cliente; a página do manual sobre a Dra. Helena não vem
      quando se pergunta da procuração dela; "em quanto tempo devemos
      responder o e-mail" acha o trecho certo;
  - material e Acervo nunca se misturam num índice;
  - sem o modelo de vetores, o material funciona só com o léxico, sem erro;
  - a chave desligada é o material de antes.

Os vetores dos testes vêm de um vetorizador de mentira (saco de palavras com
hash), para a regra rodar sem o Ollama. Com o bge-m3 no ar, os três casos
rodam também com os vetores de verdade.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_m1_material.py
"""

from __future__ import annotations

import hashlib
import re
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "habilidades"))
sys.path.insert(0, str(RAIZ / "tools" / "demo"))

import material as material_mod  # noqa: E402
import trechos  # noqa: E402
from biblioteca import indice as indice_mod  # noqa: E402

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


class VetorizadorFalso:
    """Saco de palavras com hash, normalizado: parecido com parecido, sem modelo."""

    def vetores(self, textos):
        from search import tokenize

        saida = np.zeros((len(textos), 1024), dtype=np.float32)
        for i, t in enumerate(textos):
            for tok in tokenize(t):
                saida[i, int(hashlib.md5(tok.encode()).hexdigest(), 16) % 1024] += 1.0
        normas = np.linalg.norm(saida, axis=1, keepdims=True)
        normas[normas == 0] = 1
        return saida / normas


def _obra_pdf() -> bytes:
    import biblioteca_demo

    return biblioteca_demo.obra_em_pdf(biblioteca_demo.OBRA_A)


def _manual_pdf() -> bytes:
    import criar_demo

    return criar_demo.manual_em_pdf()


def test_ids_estaveis(pasta: Path, obra: bytes) -> None:
    print("\nids estáveis")
    falso = VetorizadorFalso()
    m = material_mod.Material(pasta, hibrida=True, vetorizador=lambda: falso)
    item = m.absorver("Obra A.pdf", obra)
    ids = [c.chunk_id for c in m.indice.searcher.chunks]
    checar(ids and all(i.startswith("chunk_") for i in ids), "a obra vira trechos com chunk_id", len(ids))
    checar(item["trechos"] == len(ids), "a ficha do material conta os trechos do índice novo", item["trechos"])
    de_novo = material_mod.Material(pasta, hibrida=True, vetorizador=lambda: falso)
    de_novo.preparar()
    checar([c.chunk_id for c in de_novo.indice.searcher.chunks] == ids, "abrir de novo dá os mesmos ids")
    m.fechar()
    de_novo.fechar()
    shutil.rmtree(pasta / "indice")
    do_zero = material_mod.Material(pasta, hibrida=True, vetorizador=lambda: falso)
    do_zero.preparar()
    checar(not (pasta / "indice").exists() or do_zero.indice.lexico.quantos() == len(ids),
           "o índice apagado volta inteiro", do_zero.indice.lexico.quantos())
    checar([c.chunk_id for c in do_zero.indice.searcher.chunks] == ids, "reindexar do zero dá os mesmos ids")
    do_zero.fechar()
    texto = (pasta / "textos" / f"{item['id']}.txt").read_text(encoding="utf-8")
    outra = indice_mod.trechos_do_material({**item}, texto)
    checar([c.chunk_id for c in outra] == ids, "o mesmo texto, fatiado de novo, dá os mesmos ids")


def test_regime_c(pasta: Path) -> None:
    print("\nregime C")
    m = material_mod.Material(pasta, hibrida=True)
    item = m.itens[0]
    texto = (pasta / "textos" / f"{item['id']}.txt").read_text(encoding="utf-8")
    chunks = m.indice.searcher.chunks
    checar(all(c.regime == trechos.REGIME_OBRA for c in chunks), "a obra é lida no regime C",
           {c.regime for c in chunks})
    limpo = trechos.limpar_obra(texto)
    checar(len(limpo) == len(texto), "a limpeza não muda as posições do texto")
    capitulos = [p for p, n, _ in trechos._cabecalhos_obra(limpo) if n in ("capitulo", "superior")]
    atravessa = []
    for c in chunks:
        for b in capitulos:
            if c.char_start < b < c.char_end:
                antes = [l for l in limpo[c.char_start:b].splitlines()
                         if l.strip() and not re.match(r"^\s*\[pagina \d+\]\s*$", l)
                         and not trechos.RE_CAPITULO_OBRA.match(l) and not trechos.RE_CAIXA_ALTA.match(l)]
                if antes:
                    atravessa.append(c.text_embed.splitlines()[0])
    checar(not atravessa, "nenhum trecho atravessa capítulo", atravessa)
    juntos = "\n".join(c.text for c in chunks)
    checar("........" not in juntos and "SUMÁRIO" not in juntos, "o sumário não vira trecho")
    checar("ISBN" not in juntos and "Catalogação" not in juntos, "a folha de rosto e a ficha não viram trecho")
    checar("HEITOR VALADARES BRANDÃO · VÍCIOS" not in juntos, "o cabeçalho repetido não fica no texto dos trechos")
    checar(any(" > Cap. 3 — O VÍCIO DO PRODUTO > 3.2 O prazo de trinta dias" in c.text_embed for c in chunks),
           "o caminho vai no text_embed: obra > capítulo > seção",
           [c.text_embed.splitlines()[0] for c in chunks][:4])
    nota = next((c for c in chunks if "¹ Sobre o fato do produto" in c.text), None)
    checar(nota is not None and "3.1 A responsabilidade solidária" in nota.text,
           "a nota de rodapé fica no trecho da página dela", nota and nota.text[:80])
    hits = m.consultar("vício do produto prazo trinta dias sanar", top=6)
    checar(hits and not any("......" in h.chunk.text for h in hits), "a consulta não devolve o sumário",
           [h.chunk.text[:50] for h in hits])
    pagina = next((h for h in hits if "trinta dias para sanar" in h.chunk.text), None)
    checar(pagina is not None and m.onde(pagina) == "página 8", "o trecho diz a página certa",
           pagina and m.onde(pagina))


def test_tres_casos(pasta: Path, vetorizador, rotulo: str) -> None:
    print(f"\nos três casos de src/material.py ({rotulo})")
    m = material_mod.Material(pasta, hibrida=True, vetorizador=lambda: vetorizador)
    if not m.itens:
        m.absorver("Manual de rotinas.pdf", _manual_pdf())
    m.preparar(esperar=True)
    tabela = m.consultar("qual o percentual de êxito no contrato do João Batista?")
    checar(not any("20% e 30%" in h.chunk.text for h in tabela),
           "o êxito do contrato de um cliente não traz a tabela de honorários", [h.chunk.text[:60] for h in tabela])
    helena = m.consultar("quais poderes especiais a procuração dá à Dra. Helena?")
    checar(not any("Helena" in h.chunk.text for h in helena),
           "a procuração da Dra. Helena não traz a página do manual sobre ela", [h.chunk.text[:60] for h in helena])
    email = m.consultar("em quanto tempo devemos responder o e-mail de um cliente?")
    checar(email and "um dia útil" in email[0].chunk.text and m.pagina(email[0]) == 4,
           "“em quanto tempo devemos responder o e-mail” acha a página certa",
           [(m.pagina(h), h.chunk.text[:60]) for h in email])
    checar(m.consultar("e a Dra. Helena Moura?") == [], "pergunta que é só nome próprio não consulta o material")


def test_separados(pasta: Path) -> None:
    print("\nmaterial e Acervo separados")
    from extract import Document
    from lexico import IndiceLexico
    from search import ContractSearcher

    acervo = IndiceLexico(pasta / "acervo" / "lexico.db")
    buscador = ContractSearcher(estrutural=True, lexico=acervo)
    buscador.add_contracts([Document(name="Contrato Silva.pdf", path="x", text=(
        "CLÁUSULA 1ª - DO OBJETO\nO fornecedor entrega o produto sem vício, em trinta dias.\n"
        "CLÁUSULA 2ª - DO PREÇO\nO preço é de R$ 1.000,00, pago no dia 5.\n"))])
    buscador.build()
    m = material_mod.Material(pasta / "material", hibrida=True, vetorizador=lambda: VetorizadorFalso())
    m.absorver("Obra A.pdf", _obra_pdf())
    m.preparar(esperar=True)
    no_material = {r[0] for r in m.indice.lexico._con.execute("SELECT DISTINCT documento FROM trechos")}
    no_acervo = {r[0] for r in acervo._con.execute("SELECT DISTINCT documento FROM trechos")}
    checar(no_material == {"Obra A.pdf"}, "o índice do material só tem material", no_material)
    checar(no_acervo == {"Contrato Silva.pdf"}, "o índice do Acervo só tem o Acervo", no_acervo)
    checar(Path(m.indice.lexico.caminho).parent == pasta / "material" / "indice",
           "o léxico do material mora na pasta do material")
    checar(m.indice._denso is not None and Path(m.indice._denso.caminho).parent == pasta / "material" / "indice",
           "os vetores do material também")
    hits = m.consultar("o fornecedor entrega o produto sem vício em trinta dias", top=6)
    checar(all(h.doc_name == "Obra A.pdf" for h in hits), "a consulta do material não devolve documento do Acervo",
           [h.doc_name for h in hits])
    acervo.fechar()


def test_sem_vetores_e_chave(pasta: Path) -> None:
    print("\nsem o modelo de vetores, e com a chave desligada")
    m = material_mod.Material(pasta, hibrida=True, vetorizador=lambda: None)
    m.absorver("Manual de rotinas.pdf", _manual_pdf())
    checar(m.preparar()["vetores"] == 0, "sem o bge-m3, nada de vetor")
    hits = m.consultar("com quantos dias de antecedência devo protocolar uma contestação?")
    checar(hits and "três dias úteis" in hits[0].chunk.text, "e a busca léxica responde sozinha, sem erro",
           [h.chunk.text[:50] for h in hits])

    class Quebrado:
        def vetores(self, textos):
            raise ConnectionError("Ollama fora do ar")

    m2 = material_mod.Material(pasta, hibrida=True, vetorizador=lambda: Quebrado())
    hits = m2.consultar("com quantos dias de antecedência devo protocolar uma contestação?")
    checar(hits and "três dias úteis" in hits[0].chunk.text, "Ollama caindo no meio: fica o léxico, sem erro")
    antes = material_mod.Material(pasta)
    hits = antes.consultar("com quantos dias de antecedência devo protocolar uma contestação?")
    checar(antes.indice is None and hits and not hits[0].chunk.chunk_id,
           "chave desligada: o material de antes, sem índice novo")
    bloco = m.bloco(m.consultar("com quantos dias de antecedência devo protocolar uma contestação?"))
    checar("[Material: Manual de rotinas.pdf, página 2]" in bloco and "[pagina" not in bloco,
           "o bloco para o modelo leva nome e página, sem marca interna", bloco[:90])


def test_conversa(pasta: Path) -> None:
    print("\nna conversa (perguntar.py)")
    import perguntar
    from habilidade_base import Contexto
    from search import ContractSearcher

    class Cliente:
        model = "falso"
        num_ctx = 8192
        contexto = ""

        def ask(self, pergunta, contexto="", **k):
            Cliente.contexto = contexto
            if k.get("on_token"):
                k["on_token"]("resposta")
            return "resposta"

    m = material_mod.Material(pasta, hibrida=True, vetorizador=lambda: VetorizadorFalso())
    eventos = list(perguntar.executar(Contexto(searcher=ContractSearcher(), client=Cliente(), material=m),
                                      pergunta="qual o prazo para o fornecedor sanar o vício do produto?"))
    fontes = next((d for t, d in eventos if t == "fontes"), {})
    do_material = [f for f in fontes.get("trechos", []) if f.get("material")]
    checar(do_material and do_material[0]["onde"].startswith("página"), "a fonte do material diz a página",
           do_material[:1])
    checar("MATERIAL DE CONSULTA" in Cliente.contexto and "trinta dias" in Cliente.contexto,
           "o modelo lê o trecho da obra", Cliente.contexto[-200:])


def test_bge_m3(pasta: Path) -> None:
    """Com o Ollama e o bge-m3 no ar, os três casos com os vetores de verdade."""
    import requests

    try:
        nomes = [x["name"] for x in requests.get("http://127.0.0.1:11434/api/tags", timeout=3).json()["models"]]
    except Exception:  # noqa: BLE001
        print("\n  (Ollama fora do ar: os três casos com o bge-m3 ficam para depois)")
        return
    if not any(n.split(":")[0] == "bge-m3" for n in nomes):
        print("\n  (sem o bge-m3 instalado: os três casos com vetores de verdade ficam para depois)")
        return
    from denso import Vetorizador

    test_tres_casos(pasta, Vetorizador("http://127.0.0.1:11434"), "bge-m3 de verdade")


def main() -> int:
    print("=" * 55)
    print("  M1 — o material no pipeline híbrido")
    print("=" * 55)
    pastas = [Path(tempfile.mkdtemp(prefix=f"paulus-m1-{i}-")) for i in range(6)]
    try:
        obra = _obra_pdf()
        test_ids_estaveis(pastas[0], obra)
        test_regime_c(pastas[0])
        test_tres_casos(pastas[1], VetorizadorFalso(), "vetores de mentira")
        test_separados(pastas[2])
        test_sem_vetores_e_chave(pastas[3])
        shutil.copytree(pastas[0], pastas[4], dirs_exist_ok=True)
        test_conversa(pastas[4])
        test_bge_m3(pastas[5])
    finally:
        for p in pastas:
            shutil.rmtree(p, ignore_errors=True)
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
