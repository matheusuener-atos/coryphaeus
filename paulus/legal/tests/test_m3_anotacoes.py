"""
Portão da M3 da Biblioteca: a ponte doutrina ↔ lei, o Código anotado
(src/biblioteca/anotacoes.py).

  - as anotações das duas obras da demonstração, conferidas à mão contra o
    PDF (página de cada capítulo e seção): página certa em todas, e ZERO
    ligação ao código errado;
  - sem instrumento, não liga: "Como visto no art. 18", sozinho, não vira
    anotação;
  - a frase de cada anotação está no arquivo (conferida por alinhar.py), e a
    página é a da frase - não a do sumário, que repete o título da seção;
  - artigo sem anotação: a tela diz "nenhuma obra da biblioteca cita este
    artigo", e não mostra trecho "parecido";
  - a pergunta que cita o artigo acha os trechos que o comentam, mesmo sem a
    busca por sentido (a terceira lista da RRF);
  - remover o material remove as anotações dele.

As obras são fictícias (tools/demo/biblioteca_demo.py). O gabarito foi
conferido por quem escreveu o teste: a obra A tem o cap. 1 nas pp. 4-5, o 2
na 6, o 3 nas 7-8, o 4 nas 9-10 e o 5 nas 10-11; a obra B, o cap. 1 na 4, o
2 nas 5-6, o 3 na 7 e o 4 nas 8-9.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_m3_anotacoes.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "habilidades"))
sys.path.insert(0, str(RAIZ / "tools" / "demo"))

import material as material_mod  # noqa: E402

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


GABARITO_A = [("cdc", "2º", 4), ("cdc", "3º", 4), ("cdc", "4º", 5), ("cdc", "6º", 6), ("cdc", "6º", 6),
              ("cdc", "12", 7), ("cdc", "13", 7), ("cdc", "18", 7), ("cdc", "18", 8), ("cdc", "20", 8),
              ("cdc", "26", 9), ("cdc", "26", 9), ("cdc", "27", 10), ("cdc", "49", 10), ("cdc", "49", 11)]
GABARITO_B = [("cc", "421", 4), ("cc", "422", 4), ("cc", "474", 5), ("cc", "475", 5), ("cc", "476", 6),
              ("cc", "478", 7), ("cdc", "6º", 7), ("cdc", "18", 8), ("cdc", "51", 8), ("cdc", "54-A", 9),
              ("cdc", "104-A", 9)]


def _montar(pasta: Path, anotacoes: bool = True):
    import biblioteca_demo

    m = material_mod.Material(pasta, hibrida=True, vetorizador=lambda: None, chaves={"anotacoes": anotacoes})
    a = m.absorver(biblioteca_demo.OBRA_A["arquivo"], biblioteca_demo.obra_em_pdf(biblioteca_demo.OBRA_A))
    b = m.absorver(biblioteca_demo.OBRA_B["arquivo"], biblioteca_demo.obra_em_pdf(biblioteca_demo.OBRA_B))
    m.preparar()
    return m, a, b


def test_gabarito(pasta: Path) -> None:
    print("\nas anotações conferidas à mão")
    m, a, b = _montar(pasta)
    for item, gabarito, rotulo in ((a, GABARITO_A, "obra A"), (b, GABARITO_B, "obra B")):
        achadas = Counter((x["codigo"], x["artigo"], x["pagina"]) for x in m.anotacoes.do_material(item["id"]))
        esperadas = Counter(gabarito)
        checar(achadas == esperadas, f"{rotulo}: {sum(esperadas.values())} anotações, página e código certos",
               {"a mais": dict(achadas - esperadas), "faltando": dict(esperadas - achadas)})
    todas = m.anotacoes.do_material(a["id"]) + m.anotacoes.do_material(b["id"])
    errados = [x for x in todas if x["codigo"] not in ("cdc", "cc")]
    checar(not errados, "zero ligação a código errado", errados[:2])
    checar(not any("Como visto no art. 18" in x["quote"] for x in todas),
           "sem instrumento não liga: “Como visto no art. 18” fica sem anotação")
    texto_b = m.texto_de(b["id"])
    for x in todas:
        if x["material_id"] == b["id"]:
            checar(" ".join(texto_b[x["inicio"]:x["fim"]].split())[:40] == " ".join(x["quote"].split())[:40],
                   f"a frase do art. {x['artigo']} ({x['codigo']}) está no arquivo, no lugar gravado")
            break
    art18 = [x for x in m.anotacoes.do_artigo("cdc", "18")]
    checar(len({x["material_id"] for x in art18}) == 2, "o art. 18 do CDC tem as duas obras", len(art18))
    checar(all(x["pagina"] != 3 for x in art18), "e nenhuma página é a do sumário")
    contagem = m.anotacoes.contagem()
    checar(contagem["cdc"]["artigos"] == 14 and contagem["cc"]["artigos"] == 6,
           "a contagem por código: 14 artigos do CDC, 6 do CC", {k: v["artigos"] for k, v in contagem.items()})
    m.fechar()


def test_pergunta(pasta: Path) -> None:
    print("\na pergunta que cita o artigo")
    m, _, _ = _montar(pasta)
    hits = m.consultar("o que a doutrina diz sobre o art. 27 do CDC?", top=6)
    checar(any("cinco anos" in h.chunk.text for h in hits),
           "sem a busca por sentido, o trecho que comenta o art. 27 entra pela terceira lista",
           [h.chunk.text[:40] for h in hits])
    sem = material_mod.Material(pasta, hibrida=True, vetorizador=lambda: None, chaves={"anotacoes": False})
    checar(sem.listas_do_dispositivo("o que a doutrina diz sobre o art. 27 do CDC?") == [],
           "com a chave desligada, nada de terceira lista")
    checar(m.listas_do_dispositivo("o que diz o art. 27?") == [], "pergunta sem o instrumento não usa anotação")
    sem.fechar()
    m.fechar()


def test_remover(pasta: Path) -> None:
    print("\nremover o material")
    m, a, b = _montar(pasta)
    antes = len(m.anotacoes.do_material(a["id"]))
    m.remover(a["id"])
    checar(antes and not m.anotacoes.do_material(a["id"]), "remover a obra remove as anotações dela", antes)
    checar(m.anotacoes.do_material(b["id"]), "e as da outra obra ficam")
    checar(not [x for x in m.anotacoes.do_artigo("cdc", "2") if x["material_id"] == a["id"]],
           "o art. 2º do CDC volta a não ter a obra que saiu")
    m.fechar()


def test_api(pasta: Path) -> None:
    print("\na tela da lei, pela API")
    from fastapi.testclient import TestClient

    import api

    original, prefs = api.estado.material, dict(api.estado.prefs.dados.get("biblioteca") or {})
    m, a, _ = _montar(pasta)
    m._chaves = lambda: api.estado.prefs.dados.get("biblioteca") or {}
    api.estado.material = m
    try:
        c = TestClient(api.app, headers=api.cabecalho_local())
        api.estado.prefs.dados["biblioteca"] = {**prefs, "anotacoes": True}
        d = c.get("/api/leis/anotacoes", params={"codigo": "cdc", "numero": "18"}).json()
        checar(d["ligada"] and len(d["anotacoes"]) == 3, "o art. 18 mostra as três anotações", len(d["anotacoes"]))
        n = d["anotacoes"][0]
        checar(n["obra"] and n["pagina"] and len(n["trecho"]) <= 300 and n["pdf"],
               "cada uma com obra, página e trecho de até 300 caracteres", n)
        d = c.get("/api/leis/anotacoes", params={"codigo": "cdc", "numero": "100"}).json()
        checar(d["anotacoes"] == [] and d["mensagem"] == "nenhuma obra da biblioteca cita este artigo",
               "artigo sem anotação diz que nenhuma obra cita - sem trecho parecido", d)
        r = c.get(f"/api/material/{a['id']}/arquivo")
        checar(r.status_code == 200 and r.content[:4] == b"%PDF", "o arquivo abre para o visor, na página")
        api.estado.prefs.dados["biblioteca"] = {**prefs, "anotacoes": False}
        d = c.get("/api/leis/anotacoes", params={"codigo": "cdc", "numero": "18"}).json()
        checar(not d["ligada"] and d["anotacoes"] == [], "com a chave desligada, a seção não aparece")
    finally:
        api.estado.material = original
        api.estado.prefs.dados["biblioteca"] = prefs
        m.fechar()


def main() -> int:
    print("=" * 55)
    print("  M3 — o Código anotado pela biblioteca")
    print("=" * 55)
    pastas = [Path(tempfile.mkdtemp(prefix=f"paulus-m3-{i}-")) for i in range(4)]
    try:
        test_gabarito(pastas[0])
        test_pergunta(pastas[1])
        test_remover(pastas[2])
        test_api(pastas[3])
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
