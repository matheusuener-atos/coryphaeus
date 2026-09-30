"""
L10 - lei com vigência (src/vigencia.py, js/71-vigencia.js).

  - as notas do Planalto: redação, inclusão, revogação, veto, com a lei e a
    data (dia exato ou só o ano);
  - os dispositivos de uma linha só: caput, parágrafos, incisos e alíneas;
    "art. 373, § 1º" no meio do texto não vira parágrafo;
  - a situação numa data: antes do código, não existia, revogado, redação
    anterior (sem inventar o texto), vetado, incerto no ano da lei, vigente;
  - nos códigos de verdade: CDC 39 em 1993 e em 2020, CC 1.368-C em 2018, CC
    421 antes de 2003, CC 206 com o inciso revogado em 2024;
  - a rota, o MCP (ferramenta pública) e o diálogo no Edge.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_l10_vigencia.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-l10-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def main() -> int:
    print("=" * 55)
    print("  L10 — lei com vigência")
    print("=" * 55)
    import vigencia as v

    print("\nas notas e os dispositivos")
    ns = v.notas("x (Redação dada pela Lei nº 8.884, de 11.6.1994) y (Incluído pela Lei Complementar nº 123, de 2006) (VETADO)")
    checar([(n["tipo"], n["lei"], n["data"], n["data_exata"]) for n in ns] ==
           [("redação", "Lei nº 8.884", "1994-06-11", True), ("inclusão", "Lei Complementar nº 123", "2006-01-01", False), ("veto", "", "", False)],
           "redação com o dia, inclusão só com o ano, veto", ns)
    texto = ("É vedado: (Redação dada pela Lei nº 8.884, de 11.6.1994) I - condicionar; II - recusar, nos termos do art. 373, § 1º ; "
             "III - (VETADO); § 1º O disposto aplica-se: a) ao fornecedor; b) ao comerciante. (Incluído pela Lei nº 9.999, de 2.3.2000) "
             "§ 2º Revogado. (Revogado pela Lei nº 10.000, de 5.5.2010) Parágrafo único. Fim.")
    ds = v.dispositivos(texto)
    checar([d["rotulo"] for d in ds] == ["caput", "inciso I", "inciso II", "inciso III", "§ 1º", "§ 1º, alínea a", "§ 1º, alínea b", "§ 2º", "parágrafo único"],
           "caput, incisos, parágrafos, alíneas; o “§ 1º” da referência fica no inciso", [d["rotulo"] for d in ds])
    checar(ds[0]["texto"] == "É vedado:" and "art. 373, § 1º" in ds[2]["texto"], "o texto de cada um, sem as notas")
    por = {d["rotulo"]: d for d in ds}
    s = lambda rot, quando: v.situacao(por[rot], quando, "cdc")["estado"]  # noqa: E731
    checar(s("caput", "1990-01-01") == "antes do código", "antes de o código vigorar")
    checar(s("caput", "1993-01-01") == "outra redação" and "não traz o texto anterior" in v.situacao(por["caput"], "1993-01-01", "cdc")["frase"],
           "redação anterior, dita sem inventar o texto")
    checar(s("inciso III", "2020-01-01") == "vetado", "vetado: nunca vigorou")
    checar(s("§ 1º, alínea b", "1999-01-01") == "não existia" and s("§ 1º, alínea b", "2001-01-01") == "vigente", "incluído depois: não existia antes")
    checar(s("§ 2º", "2011-01-01") == "revogado" and s("§ 2º", "2009-01-01") == "vigente", "revogado a partir da lei")
    so_ano = v.dispositivos("Texto. (Incluído pela Lei nº 13.874, de 2019)")[0]
    checar(v.situacao(so_ano, "2019-06-01", "cc")["estado"] == "incerto", "no mesmo ano de lei sem o dia: incerto, e dito")

    import api
    from biblioteca import nativo
    from fastapi.testclient import TestClient

    nativo.instalar(api.estado.leis, api.estado.material, Path(os.environ["PAULUS_DADOS"]) / "leis", forcar=True)
    local = TestClient(api.app, headers=api.cabecalho_local())

    print("\nnos códigos de verdade")
    r = local.get("/api/leis/vigencia?codigo=cdc&numero=39&data=1993-01-01").json()
    d = {x["rotulo"]: x for x in r["dispositivos"]}
    checar(d["caput"]["na_data"]["estado"] == "outra redação" and d["inciso X"]["na_data"]["estado"] == "não existia"
           and "diferente de hoje" in r["resumo"], "CDC 39 em 1993: caput com outra redação, inciso X ainda não existia", r["resumo"])
    r = local.get("/api/leis/vigencia?codigo=cdc&numero=39&data=2020-01-01").json()
    checar(r["resumo"] == "Na data, o artigo estava como hoje.", "CDC 39 em 2020: como hoje", r["resumo"])
    r = local.get("/api/leis/vigencia?codigo=cc&numero=1.368-C&data=2018-05-01").json()
    checar(all(x["na_data"]["estado"] == "não existia" for x in r["dispositivos"]), "CC 1.368-C em 2018: ainda não existia")
    r = local.get("/api/leis/vigencia?codigo=cc&numero=421&data=2002-06-01").json()
    checar(r["resumo"].startswith("O código ainda não vigorava"), "CC 421 em 2002: o código ainda não vigorava", r["resumo"])
    r = local.get("/api/leis/vigencia?codigo=cc&numero=206&data=2023-06-01").json()
    inciso = next(x for x in r["dispositivos"] if x["rotulo"] == "§ 1º, inciso II")
    checar(inciso["diferente"] and "revogado depois" in inciso["na_data"]["frase"], "CC 206 em 2023: o inciso II ainda vigorava")
    r = local.get("/api/leis/vigencia?codigo=cpc&numero=1.015&data=2020-01-01").json()
    checar(not any(x["rotulo"].startswith("§") for x in r["dispositivos"]), "CPC 1.015: a referência “art. 373, § 1º” não vira parágrafo")
    checar(local.get("/api/leis/vigencia?codigo=cc&numero=421&data=ontem").status_code == 400
           and local.get("/api/leis/vigencia?codigo=cc&numero=99999").status_code == 404, "data errada: 400; artigo que não existe: 404")

    print("\no MCP")
    api.estado.prefs.dados.setdefault("umbrel", {})["mcp"] = True
    janela = TestClient(api.app, headers=api.cabecalho_local(), client=("127.0.0.1", 50124))
    token = janela.post("/api/mcp/conexoes", json={"nome": "Vigência", "ferramentas": ["vigencia_do_artigo"]}).json()["token"]
    mcp = TestClient(api.app, client=("127.0.0.1", 50125))
    resp = mcp.post("/mcp", headers={"Authorization": f"Bearer {token}"}, content=json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "vigencia_do_artigo",
                                                                      "arguments": {"codigo": "cdc", "numero": "39", "data": "1993-01-01"}}})).json()
    texto = resp["result"]["content"][0]["text"]
    checar("CDC, art. 39 em 1993-01-01" in texto and "inciso X: ainda não existia" in texto, "a ferramenta pública do MCP", texto[:200])

    print("\nno Edge")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sync_playwright = None
        print("  pulado: playwright não instalado")
    if sync_playwright is not None:
        from test_gravacoes import _porta_livre, _subir_servidor

        porta = _porta_livre()
        _subir_servidor(porta)
        with sync_playwright() as p:
            try:
                nav = p.chromium.launch(channel="msedge")
            except Exception as exc:  # noqa: BLE001
                nav = None
                print(f"  pulado: não achei o Edge ({str(exc)[:60]})")
            if nav is not None:
                pag = nav.new_context(viewport={"width": 1280, "height": 900}).new_page()
                erros = []
                pag.on("pageerror", lambda e: erros.append(str(e)))
                pag.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
                pag.goto(f"http://127.0.0.1:{porta}/entrar-local?chave=" + api.estado.acesso.chave, wait_until="load")
                pag.wait_for_function("() => typeof vigenciaDoArtigo === 'function'")
                pag.wait_for_timeout(800)
                pag.evaluate("() => { vigenciaDoArtigo({ codigo: 'cdc', numero: '39', citacao: 'CDC, art. 39' }); }")
                pag.wait_for_selector(".vig-linha", timeout=15000)
                checar("como hoje" in pag.inner_text("#vig-corpo"), "o diálogo abre em hoje")
                pag.evaluate("() => { const c = document.getElementById('vig-data'); c.value = '1993-01-01'; c.dispatchEvent(new Event('change')); }")
                pag.wait_for_function("() => /diferente de hoje/.test(document.getElementById('vig-corpo').textContent)", timeout=10000)
                checar(pag.locator(".vig-linha.diferente").count() >= 5 and "incluído pela Lei nº 8.884" in pag.inner_text("#vig-corpo"),
                       "trocar a data refaz a conta, com as linhas diferentes marcadas")
                pag.screenshot(path=str(TMP / "l10-vigencia.png"))
                checar(not erros, "nenhum erro de JavaScript", erros[:3])
                print(f"  (foto em {TMP})")
                nav.close()

    print("\n" + "=" * 55)
    if _falhas:
        print(f"  {len(_falhas)} FALHA(S):")
        for x in _falhas:
            print(f"    - {x}")
        return 1
    print("  todos os testes passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
