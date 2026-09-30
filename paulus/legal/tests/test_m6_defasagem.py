"""
Portão da M6 da Biblioteca: o aviso de obra anterior à redação atual do
artigo (src/biblioteca/defasagem.py, `ano_da_alteracao` em src/leis.py).

  - 20 artigos com alteração conhecida e 10 sem, no CDC e no CC do Planalto:
    `alterado_em` certo em todos (o gabarito foi conferido lendo as notas
    "(Redação dada pela...)", "(Incluído pela...)" e "(Revogado pela...)" de
    cada um, em 30/09/2026);
  - obra anterior à alteração -> aviso em 100%; obra posterior, ou artigo sem
    alteração -> zero aviso; obra sem ano -> "Ano da obra desconhecido";
  - na resposta em camadas (modelo de mentira) e na tela da lei.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_m6_defasagem.py
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

import leis as leis_mod  # noqa: E402
from base import Base  # noqa: E402
from biblioteca import camadas as camadas_mod  # noqa: E402
from biblioteca import defasagem  # noqa: E402

LEIS = RAIZ / "data" / "leis"
_falhas: list[str] = []

COM_ALTERACAO = {
    ("cdc", "4º"): 2021, ("cdc", "5º"): 2021, ("cdc", "6º"): 2021, ("cdc", "8º"): 2017, ("cdc", "39"): 2017,
    ("cdc", "42-A"): 2009, ("cdc", "43"): 2015, ("cdc", "51"): 2021, ("cdc", "52"): 1996, ("cdc", "54-A"): 2021,
    ("cdc", "104-A"): 2021, ("cc", "3º"): 2015, ("cc", "4º"): 2015, ("cc", "50"): 2019, ("cc", "113"): 2019,
    ("cc", "421"): 2019, ("cc", "421-A"): 2019, ("cc", "980-A"): 2022, ("cc", "1.052"): 2019, ("cc", "1.815"): 2017,
}
SEM_ALTERACAO = [("cdc", "2º"), ("cdc", "3º"), ("cdc", "12"), ("cdc", "18"), ("cdc", "26"), ("cdc", "27"),
                 ("cdc", "49"), ("cc", "422"), ("cc", "475"), ("cc", "1.228")]


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def test_alterado_em(L) -> None:
    print("\nalterado_em nos códigos do Planalto")
    errados = []
    for (codigo, numero), ano in COM_ALTERACAO.items():
        a = L.artigo(codigo, numero)
        if not a or a["alterado_em"] != ano:
            errados.append((codigo, numero, a and a["alterado_em"], ano))
    checar(not errados, f"{len(COM_ALTERACAO)} artigos com alteração: o ano certo em todos", errados)
    errados = [(c, n, (L.artigo(c, n) or {}).get("alterado_em")) for c, n in SEM_ALTERACAO
               if (L.artigo(c, n) or {}).get("alterado_em", -1) != 0]
    checar(not errados, f"{len(SEM_ALTERACAO)} artigos sem alteração: vazio em todos", errados)
    checar(leis_mod.ano_da_alteracao("(Redação dada pela Lei nº 9.298, de 1º.8.1996)") == 1996,
           "a data por extenso da nota (1º.8.1996) também dá o ano")
    checar(leis_mod.ano_da_alteracao("(Vide ADPF 54) (Vide Lei nº 9.099, de 1995)") == 0,
           "“Vide” não é alteração da redação")


def test_aviso() -> None:
    print("\no aviso")
    checar(defasagem.aviso("2015", 2021).startswith("Obra de 2015; este artigo teve a redação alterada em 2021."),
           "obra anterior à alteração: aviso")
    checar(defasagem.aviso("2022", 2021) == "" and defasagem.aviso("2021", 2021) == "",
           "obra do mesmo ano ou posterior: sem aviso")
    checar(defasagem.aviso("2015", 0) == "", "artigo sem alteração: sem aviso")
    checar(defasagem.aviso("", 2021) == "Ano da obra desconhecido; confira a redação.",
           "obra sem ano na ficha: “Ano da obra desconhecido”")


def test_na_resposta(L) -> None:
    print("\nna resposta")
    a = camadas_mod.Trecho("doutrina", "Brandão", "O art. 6º do CDC enumera os direitos básicos.", {"origem": "doutrina"},
                           autor="Heitor Valadares Brandão", obra="Vícios", ano="2015", dispositivos=[("cdc", "6º")])
    b = camadas_mod.Trecho("doutrina", "Teles", "Entende-se por superendividamento...", {"origem": "doutrina"},
                           autor="Marina Albuquerque Teles", obra="Teoria", ano="2022", dispositivos=[("cdc", "54-A")])
    c = camadas_mod.Trecho("doutrina", "Teles", "função social", {"origem": "doutrina"}, autor="Marina Albuquerque Teles",
                           obra="Teoria", ano="2022", dispositivos=[("cc", "421"), ("cc", "422")])
    d = camadas_mod.Trecho("doutrina", "Brandão", "art. 18", {"origem": "doutrina"}, autor="Heitor Valadares Brandão",
                           obra="Vícios", ano="2015", dispositivos=[("cdc", "18"), ("cdc", "26")])
    texto = defasagem.para_a_resposta("Os direitos básicos estão no art. 6º [T1].", [a, b, c, d], L)
    checar("Brandão sobre o CDC, art. 6º: Obra de 2015; este artigo teve a redação alterada em 2021." in texto,
           "obra de 2015 sobre o art. 6º (alterado em 2021): aviso", texto)
    checar("Teles" not in texto and "18" not in texto, "o que a resposta não cita não ganha aviso", texto)
    texto = defasagem.para_a_resposta("Resposta sem marca.", [b, c, d], L)
    checar(texto == "", "obra posterior à alteração e artigo sem alteração: zero aviso", texto)


def test_conversa(pasta: Path) -> None:
    print("\nna conversa e na tela da lei")
    if not (LEIS / "l8078compilado.htm").exists():
        print("  pulado: sem o CDC do Planalto")
        return
    sys.path.insert(0, str(RAIZ / "tests"))
    import test_m4_camadas

    base, L, m = test_m4_camadas._biblioteca(pasta)
    m._chaves = lambda: {"anotacoes": True, "camadas": True, "defasagem": True}
    import perguntar
    from habilidade_base import Contexto
    from search import ContractSearcher

    class Cliente:
        model = "falso"
        num_ctx = 8192

        def ask(self, pergunta, contexto="", **k):
            r = "O art. 6º do CDC enumera os direitos básicos do consumidor, como a informação adequada e clara."
            if k.get("on_token"):
                k["on_token"](r)
            return r

    eventos = list(perguntar.executar(Contexto(searcher=ContractSearcher(), client=Cliente(), material=m),
                                      pergunta="o que a doutrina diz sobre os direitos básicos do art. 6º do CDC?"))
    rev = next((d for t, d in eventos if t == "revisao"), {})
    checar("Obra de 2015; este artigo teve a redação alterada em 2021. Confira se o comentário ainda vale."
           in rev.get("texto", ""), "a resposta sobre o art. 6º avisa que a obra é de 2015", rev.get("texto", "")[-200:])
    eventos = list(perguntar.executar(Contexto(searcher=ContractSearcher(), client=Cliente(), material=m),
                                      pergunta="o que a doutrina diz do superendividamento no art. 54-A do CDC?"))
    rev = next((d for t, d in eventos if t == "revisao"), {})
    checar("Obra de" not in rev.get("texto", ""), "a obra de 2022 sobre o art. 54-A (2021) não ganha aviso",
           rev.get("texto", "")[-200:])

    from fastapi.testclient import TestClient

    import api

    original, prefs, leis_antes = api.estado.material, dict(api.estado.prefs.dados.get("biblioteca") or {}), api.estado.leis
    api.estado.material, api.estado.leis = m, L
    api.estado.prefs.dados["biblioteca"] = {**prefs, "anotacoes": True, "defasagem": True}
    m._chaves = lambda: api.estado.prefs.dados.get("biblioteca") or {}
    try:
        c = TestClient(api.app, headers=api.cabecalho_local())
        d = c.get("/api/leis/anotacoes", params={"codigo": "cdc", "numero": "6"}).json()
        avisos = {n["autor"]: n["aviso"] for n in d["anotacoes"]}
        checar(avisos.get("Heitor Valadares Brandão", "").startswith("Obra de 2015")
               and not avisos.get("Marina Albuquerque Teles"),
               "na tela do art. 6º: aviso na obra de 2015, nada na de 2022", avisos)
    finally:
        api.estado.material, api.estado.leis = original, leis_antes
        api.estado.prefs.dados["biblioteca"] = prefs
        m.fechar()
        base.con.close()


def main() -> int:
    print("=" * 55)
    print("  M6 — obra anterior à redação atual do artigo")
    print("=" * 55)
    pastas = [Path(tempfile.mkdtemp(prefix=f"paulus-m6-{i}-")) for i in range(2)]
    base = Base(pastas[0] / "l.db")
    try:
        L = leis_mod.Leis(base)
        falta = [f for f in ("l8078compilado.htm", "l10406compilada.htm") if not (LEIS / f).exists()]
        if falta:
            print(f"  pulado em parte: sem {', '.join(falta)} em data/leis (tools/demo/biblioteca_demo.py baixa)")
        else:
            L.importar(LEIS / "l8078compilado.htm", "cdc")
            L.importar(LEIS / "l10406compilada.htm", "cc")
            test_alterado_em(L)
        test_aviso()
        if not falta:
            test_na_resposta(L)
        test_conversa(pastas[1])
    finally:
        base.con.close()
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
