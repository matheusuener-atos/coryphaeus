"""
B1 - o acervo que vem com o PAULUS e os tribunais (src/biblioteca/nativo.py,
src/biblioteca/tribunais.py).

- os códigos e as súmulas do STJ entram uma vez, sem rede, e cada código
  responde pelo artigo;
- o que a pessoa apagou não volta na abertura seguinte; o botão "pôr de novo"
  devolve;
- a súmula se acha por número e por palavras;
- o número único do processo: dígito verificador, tribunal do DataJud, e a
  consulta montada sem rede (a resposta do CNJ é simulada);
- as buscas de fora são só endereços, e o servidor de teste não instala nada.

    venv\\Scripts\\python.exe tests\\test_b1_acervo_inicial.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import leis as leis_mod  # noqa: E402
import material as material_mod  # noqa: E402
from base import Base  # noqa: E402
from biblioteca import nativo, tribunais  # noqa: E402
from biblioteca.rotas import procurar_sumulas  # noqa: E402

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def test_acervo(pasta: Path) -> None:
    print("\no acervo que vem com o PAULUS")
    idx = nativo.indice()
    checar(set(idx["codigos"]) == set(leis_mod.CODIGOS), "o acervo traz todos os códigos que o PAULUS conhece",
           sorted(set(leis_mod.CODIGOS) ^ set(idx["codigos"])))
    checar(idx["sumulas"]["stj"]["enunciados"] >= 600, "e as súmulas do STJ", idx["sumulas"].get("stj"))
    base = Base(pasta / "b.db")
    try:
        L = leis_mod.Leis(base)
        m = material_mod.Material(pasta / "material")
        antes = os.environ.pop("PAULUS_SEM_AVISOS", None)
        try:
            os.environ["PAULUS_SEM_AVISOS"] = "1"
            checar(nativo.instalar(L, m, pasta / "leis") == {"codigos": [], "sumulas": [], "erros": []},
                   "o servidor de teste (PAULUS_SEM_AVISOS) não instala nada")
            os.environ.pop("PAULUS_SEM_AVISOS")
            t = time.time()
            feito = nativo.instalar(L, m, pasta / "leis")
            gasto = time.time() - t
        finally:
            if antes is not None:
                os.environ["PAULUS_SEM_AVISOS"] = antes
        checar(len(feito["codigos"]) == len(leis_mod.CODIGOS) and feito["sumulas"] == ["stj"] and not feito["erros"],
               f"na primeira abertura entra tudo, sem rede ({gasto:.0f} s)", feito)
        checar(all(c["instalado"] for c in L.instalados()), "todos os códigos ficam instalados")
        cf5 = L.artigo("cf", "5") or {}
        checar("inviolabilidade do direito à vida" in cf5.get("texto", ""), "a Constituição responde pelo art. 5º",
               cf5.get("texto", "")[:120])
        cpp = L.artigo("cpp", "312") or {}
        checar("prisão preventiva" in cpp.get("texto", ""), "o CPP entra (art. 312, preventiva)", cpp.get("texto", "")[:120])
        ctb = L.artigo("ctb", "165") or {}
        checar("influência de álcool" in ctb.get("texto", ""), "e o CTB (art. 165)", ctb.get("texto", "")[:120])
        item = next((x for x in m.itens if (x.get("ficha") or {}).get("tipo") == "sumulas"), None)
        checar(item and item["ficha"]["autor"] == "Superior Tribunal de Justiça" and item["ficha"]["origem"] == "oficial",
               "as súmulas entram como material oficial, do STJ", item and item.get("ficha"))

        s = procurar_sumulas(m, numero="297")
        checar(len(s) == 1 and "Código de Defesa do Consumidor" in s[0]["texto"] and s[0]["titulo"] == "Súmula 297 do STJ",
               "a Súmula 297 do STJ se acha pelo número", s[:1])
        s = procurar_sumulas(m, termo="dano moral pessoa juridica")
        checar(any(x["numero"] == "227" for x in s), "e por palavras, sem acento (227: pessoa jurídica e dano moral)",
               [x["numero"] for x in s])
        checar(not procurar_sumulas(m, numero="603"), "a cancelada (603) não vem")

        situ = nativo.situacao(L, m, pasta / "leis")
        checar(situ["falta"] == 0, "a tela diz que não falta nada", situ["falta"])

        # quem apaga não vê voltar
        L.apagar("ctb")
        m.remover(item["id"])
        de_novo = nativo.instalar(L, m, pasta / "leis")
        checar(not de_novo["codigos"] and not de_novo["sumulas"], "o que a pessoa apagou não volta na abertura", de_novo)
        checar(nativo.situacao(L, m, pasta / "leis")["falta"] == 2, "e a tela diz que faltam dois")
        forcado = nativo.instalar(L, m, pasta / "leis", forcar=True)
        checar(forcado["codigos"] == ["ctb"] and forcado["sumulas"] == ["stj"], "o botão põe de novo só o que falta", forcado)
        reg = json.loads((pasta / "leis" / "acervo-inicial.json").read_text(encoding="utf-8"))
        checar(set(reg["codigos"]) == set(leis_mod.CODIGOS), "o registro diz o que entrou, nesta máquina")
    finally:
        base.con.close()
        m.fechar()


class _Resposta:
    def __init__(self, status: int, dados=None, texto: str = "") -> None:
        self.status_code, self._dados, self.text = status, dados, texto

    def json(self):
        if self._dados is None:
            raise ValueError("não é JSON")
        return self._dados

    def raise_for_status(self) -> None:
        pass


def test_tribunais() -> None:
    print("\no número do processo e o DataJud")
    n = tribunais.ler_numero("4014273-81.2026.8.26.0008")
    checar(n["ok"] and n["alias"] == "tjsp" and n["digitos"] == "40142738120268260008", "o número do TJSP é lido", n)
    checar(not tribunais.ler_numero("4014273-82.2026.8.26.0008")["ok"], "dígito verificador errado é recusado")
    checar(not tribunais.ler_numero("123")["ok"], "número curto é recusado")
    casos = {"8.07": "tjdft", "8.19": "tjrj", "4.03": "trf3", "5.02": "trt2", "5.00": "tst", "6.26": "tre-sp",
             "9.26": "tjmsp", "3.00": "stj"}
    for jtr, alias in casos.items():
        j, tr = jtr.split(".")
        checar(tribunais.alias_do_tribunal("0" * 13 + j + tr + "0000") == alias, f"J.TR {jtr} -> {alias}")
    checar(tribunais.alias_do_tribunal("0" * 13 + "1" + "00" + "0000") == "", "o STF não tem índice público no DataJud")

    pedidos = []

    def pedir(url, json=None, headers=None, timeout=None):
        pedidos.append((url, json, headers))
        return _Resposta(200, {"hits": {"hits": [{"_source": {
            "tribunal": "TJSP", "grau": "JE", "numeroProcesso": "40142738120268260008",
            "dataAjuizamento": "20260730012658", "classe": {"nome": "Procedimento do Juizado Especial Cível"},
            "orgaoJulgador": {"nome": "1ª Vara do Juizado Especial Cível"}, "assuntos": [{"nome": "Indenização por Dano Moral"}],
            "movimentos": [{"dataHora": "2026-09-03T08:12:03.000Z", "nome": "Documento"},
                           {"dataHora": "2026-09-15T10:38:57.000Z", "nome": "Publicação"}]}}]}})

    r = tribunais.consultar_datajud("4014273-81.2026.8.26.0008", pedir=pedir)
    url, corpo, cab = pedidos[0]
    checar(url.endswith("/api_publica_tjsp/_search") and corpo["query"]["match"]["numeroProcesso"] == "40142738120268260008",
           "a consulta vai ao índice do TJSP, só com o número", (url, corpo))
    checar(cab["Authorization"].startswith("APIKey "), "com a chave pública do CNJ")
    g = r["graus"][0]
    checar(g["classe"].startswith("Procedimento") and g["ajuizamento"] == "2026-07-30 01:26" and g["assuntos"] == ["Indenização por Dano Moral"],
           "a resposta vem resumida: classe, ajuizamento, assuntos", g)
    checar([x["nome"] for x in g["movimentos"]] == ["Publicação", "Documento"], "e os movimentos do mais novo ao mais antigo")
    for status, dados, erro, nome in ((403, None, PermissionError, "chave recusada vira aviso de chave trocada"),
                                      (200, None, ConnectionError, "resposta que não é JSON vira 'tente de novo'"),
                                      (503, None, ConnectionError, "erro do CNJ vira 'tente de novo'")):
        try:
            tribunais.consultar_datajud("40142738120268260008", pedir=lambda *a, **k: _Resposta(status, dados))
            checar(False, nome)
        except erro:
            checar(True, nome)

    links = tribunais.links("dano moral bancário")
    checar([x["id"] for x in links] == ["jusbrasil", "stf", "stj", "tst", "lexml"] and all("dano+moral" in x["url"] for x in links),
           "as buscas de fora são endereços com o termo", [x["url"] for x in links][:2])
    checar(tribunais.links("  ") == [], "sem termo, sem endereço")


def test_rotas(pasta: Path) -> None:
    print("\npela API")
    from fastapi.testclient import TestClient

    import api

    original_m, original_l = api.estado.material, api.estado.leis
    base = Base(pasta / "api.db")
    dados_de_verdade, api.DADOS_DIR = api.DADOS_DIR, pasta
    api.estado.material = material_mod.Material(pasta / "material")
    api.estado.leis = leis_mod.Leis(base)
    try:
        c = TestClient(api.app, headers=api.cabecalho_local())
        # a rota foi montada com a pasta de dados de verdade: a situação lê o
        # registro de lá, mas os códigos e o material são os do teste.
        d = c.get("/api/biblioteca/acervo-inicial").json()
        checar(len(d["codigos"]) == len(leis_mod.CODIGOS) and d["sumulas"][0]["chave"] == "stj",
               "GET /api/biblioteca/acervo-inicial lista o acervo", d.get("falta"))
        r = c.get("/api/biblioteca/fontes", params={"termo": "usucapião"}).json()
        checar(len(r["links"]) == 5, "GET /api/biblioteca/fontes devolve os endereços")
        r = c.post("/api/biblioteca/datajud", json={"numero": "123"})
        checar(r.status_code == 400 and "20 dígitos" in r.json()["detail"], "número errado volta 400 sem sair da máquina",
               r.json())
        r = c.get("/api/biblioteca/sumulas", params={"numero": "1"})
        checar(r.status_code == 200 and r.json()["achados"] == [], "sem súmulas guardadas, a busca volta vazia")
    finally:
        api.estado.material.fechar()
        api.estado.material, api.estado.leis, api.DADOS_DIR = original_m, original_l, dados_de_verdade
        base.con.close()


def main() -> int:
    print("=" * 55)
    print("  B1 — acervo inicial, súmulas e tribunais")
    print("=" * 55)
    pastas = [Path(tempfile.mkdtemp(prefix=f"paulus-b1-{i}-")) for i in range(2)]
    try:
        test_acervo(pastas[0])
        test_tribunais()
        test_rotas(pastas[1])
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
