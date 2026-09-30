"""
Portão da M7 da Biblioteca: o que o PAULUS sabe (src/biblioteca/mapa.py).

  - as perguntas "fora da cobertura" do conjunto da Biblioteca: 100% com a área
    certa e o aviso;
  - as perguntas dentro da cobertura: zero aviso;
  - as perguntas sem área clara (documento de cliente): zero aviso;
  - a contagem de anotações por código da tela bate com a tabela da M3;
  - na conversa (modelo de mentira): a resposta segue e ganha a linha no fim;
    se a biblioteca trouxe algo, não há aviso; a chave desligada não muda nada.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_m7_mapa.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "habilidades"))
sys.path.insert(0, str(RAIZ / "tools" / "demo"))
sys.path.insert(0, str(RAIZ / "tests"))

from biblioteca import mapa  # noqa: E402

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def test_area() -> None:
    print("\na área da pergunta")
    import biblioteca_demo

    fora = [q for q in biblioteca_demo.CONJUNTO_BIBLIOTECA if q["cobertura"] == "fora"]
    errados = [(q["pergunta"], mapa.area_da_pergunta(q["pergunta"]), q["area"]) for q in fora
               if mapa.area_da_pergunta(q["pergunta"]) != q["area"]]
    checar(not errados, f"as {len(fora)} perguntas fora da cobertura: a área certa", errados)
    sem = [q for q in biblioteca_demo.CONJUNTO_BIBLIOTECA if q["tipo"] in ("sem_material", "manual")]
    com_area = [(q["pergunta"], mapa.area_da_pergunta(q["pergunta"])) for q in sem if mapa.area_da_pergunta(q["pergunta"])]
    print(f"       (perguntas de cliente e do manual com área identificada: {com_area})")
    checar(mapa.area_da_pergunta("o que diz o art. 150 do CTN?") == "tributário",
           "o artigo com o código decide a área")
    checar(mapa.area_da_pergunta("qual o prazo?") == "", "sem termo nenhum, sem área")
    checar(mapa.area_da_pergunta("o empregado cometeu crime?") == "", "empate entre duas áreas: sem área")


def test_cobertura(pasta: Path) -> None:
    print("\na cobertura, na biblioteca da demonstração")
    import biblioteca_demo
    import test_m4_camadas

    base, L, m = test_m4_camadas._biblioteca(pasta)
    if (RAIZ / "data" / "leis" / "l10406compilada.htm").exists():
        L.importar(RAIZ / "data" / "leis" / "l10406compilada.htm", "cc")
    m._chaves = lambda: {"anotacoes": True, "camadas": True, "mapa": True}
    avisos_fora, avisos_dentro = [], []
    for q in biblioteca_demo.CONJUNTO_BIBLIOTECA:
        area = mapa.fora_da_cobertura(q["pergunta"], m, L)
        (avisos_fora if q["cobertura"] == "fora" else avisos_dentro).append((q["pergunta"], area))
    checar(all(a for _, a in avisos_fora), "fora da cobertura: 100% com aviso", avisos_fora)
    indevidos = [x for x in avisos_dentro if x[1]]
    checar(not indevidos, "dentro da cobertura e sem área clara: zero aviso", indevidos)

    painel = mapa.painel(m, L)
    areas = {a["area"] for a in painel["areas"]}
    checar({"consumidor", "civil"} <= areas, "a tela mostra as áreas que a biblioteca tem", areas)
    por_codigo = {c["codigo"]: c["anotados"] for c in painel["codigos"]}
    tabela = {k: v["artigos"] for k, v in m.anotacoes.contagem().items()}
    checar(por_codigo.get("cdc") == tabela.get("cdc") and por_codigo.get("cdc"),
           "a contagem de artigos anotados por código bate com a tabela da M3", (por_codigo, tabela))
    return base, L, m


def test_conversa(m) -> None:
    print("\nna conversa")
    import perguntar
    from extract import Document
    from habilidade_base import Contexto
    from search import ContractSearcher

    class Cliente:
        model = "falso"
        num_ctx = 8192

        def ask(self, pergunta, contexto="", **k):
            r = "O documento não trata disso."
            if k.get("on_token"):
                k["on_token"](r)
            return r

    buscador = ContractSearcher()
    buscador.add_contracts([Document(name="Contrato Silva.txt", path="x",
                                     text="CONTRATO DE COMPRA. O vendedor garante o produto por noventa dias.")])
    buscador.build()

    def rodar(pergunta):
        eventos = list(perguntar.executar(Contexto(searcher=buscador, client=Cliente(), material=m), pergunta=pergunta))
        texto = "".join(d.get("t", "") for t, d in eventos if t == "token") + \
            "".join(d.get("mensagem", "") for t, d in eventos if t == "vazio")
        return texto

    texto = rodar("qual a pena do crime de furto qualificado?")
    checar(texto.startswith("O documento não trata disso.") and texto.rstrip().endswith(
        "Não tenho material de penal na biblioteca; esta resposta usa só os documentos."),
        "a resposta segue, e ganha a linha no fim", texto)
    texto = rodar("com quantos dias de antecedência devo protocolar uma contestação?")
    checar("Não tenho material" not in texto, "a biblioteca trouxe o manual: sem aviso", texto[-120:])
    m._chaves = lambda: {"anotacoes": True, "camadas": True, "mapa": False}
    texto = rodar("qual a pena do crime de furto qualificado?")
    checar("Não tenho material" not in texto, "chave desligada: nada muda", texto)


def main() -> int:
    print("=" * 55)
    print("  M7 — o que o PAULUS sabe")
    print("=" * 55)
    pasta = Path(tempfile.mkdtemp(prefix="paulus-m7-"))
    base = m = None
    try:
        test_area()
        base, L, m = test_cobertura(pasta)
        test_conversa(m)
    finally:
        if m is not None:
            m.fechar()
        if base is not None:
            base.con.close()
        shutil.rmtree(pasta, ignore_errors=True)
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
