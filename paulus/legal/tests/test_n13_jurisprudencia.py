"""
N13 - a jurisprudência do STJ no computador (src/jurisprudencia.py, js/73-jurisprudencia.js).

Com o portal de dados abertos do STJ de mentira (nada sai daqui):

  - nada é pedido ao portal antes de a pessoa escolher e mandar baixar;
  - baixar um órgão: o pacote do órgão, o arquivo base (zip) e o mensal
    (json) entram; baixar de novo só traz o arquivo novo;
  - as referências legislativas viram artigos (cc:206; o CPC/73 não entra);
  - procurar por palavras (sem acento), por órgão e por data; os que citam um
    artigo; a citação pronta;
  - o acórdão aparece embaixo da resposta (N7), na fundamentação do editor e
    no MCP;
  - de fora, procurar vale e baixar não; apagar tira tudo;
  - no Edge: Biblioteca › Jurisprudência, procurar e abrir a ementa, 390 px.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_n13_jurisprudencia.py
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import time
import zipfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-n13-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def acordao(id_, ementa, refs, data="20240510", relator="NANCY ANDRIGHI", orgao="TERCEIRA TURMA"):
    return {"id": id_, "numeroProcesso": id_[-7:], "numeroRegistro": "2023" + id_[-8:], "siglaClasse": "REsp",
            "descricaoClasse": "RECURSO ESPECIAL", "nomeOrgaoJulgador": orgao, "ministroRelator": relator,
            "dataPublicacao": "DJE        DATA:20/05/2024", "ementa": ementa, "tipoDeDecisao": "ACÓRDÃO", "dataDecisao": data,
            "decisao": "Vistos... por unanimidade, negar provimento.", "teseJuridica": None, "tema": None,
            "informacoesComplementares": None, "referenciasLegislativas": refs}


CC206 = ["LEG:FED LEI:010406 ANO:2002\n*****  CC-02    CÓDIGO CIVIL DE 2002\n        ART:00206 PAR:00003 INC:00005"]
CDC51 = ["LEG:FED LEI:008078 ANO:1990\n*****  CDC-90    CÓDIGO DE DEFESA DO CONSUMIDOR\n        ART:00051 INC:00004",
         "LEG:FED LEI:005869 ANO:1973\n*****  CPC-73    CÓDIGO DE PROCESSO CIVIL DE 1973\n        ART:00535"]


class Portal:
    def __init__(self) -> None:
        self.pedidos: list[str] = []
        base = [acordao("000000001", "CIVIL. RESPONSABILIDADE CIVIL. PRESCRIÇÃO TRIENAL. Reparação civil: prazo de três anos.", CC206, "20210310"),
                acordao("000000002", "CONSUMIDOR. CONTRATO DE LOCAÇÃO. MULTA MORATÓRIA. Cláusula abusiva. Redução.", CDC51, "20220105")]
        z = io.BytesIO()
        with zipfile.ZipFile(z, "w") as arq:
            arq.writestr("base.json", json.dumps(base, ensure_ascii=False))
        self.arquivos = {"https://x/base.zip": z.getvalue(),
                         "https://x/20240531.json": json.dumps([acordao("000000003", "LOCAÇÃO. MULTA MORATÓRIA DE DEZ POR CENTO. Validade.",
                                                                        CC206 + CDC51, "20240510")], ensure_ascii=False).encode()}
        self.recursos = [{"id": "r1", "name": "20220508.zip", "url": "https://x/base.zip"},
                         {"id": "r2", "name": "20240531.json", "url": "https://x/20240531.json"},
                         {"id": "d", "name": "dicionario.csv", "url": "https://x/dicionario.csv"}]

    def __call__(self, url: str) -> bytes:
        self.pedidos.append(url)
        if "package_show" in url:
            return json.dumps({"result": {"resources": self.recursos}}).encode()
        return self.arquivos[url]


def main() -> int:
    print("=" * 55)
    print("  N13 — jurisprudência do STJ no computador")
    print("=" * 55)
    import api
    import jurisprudencia as j
    import mcp_leis
    from acesso import politicas
    from fastapi.testclient import TestClient

    portal = Portal()
    api.estado.jurisprudencia.baixar_fn = portal
    local = TestClient(api.app, headers=api.cabecalho_local())

    print("\nas referências")
    checar(j.artigos_das_referencias(CC206 + CDC51) == ["cc:206", "cdc:51"], "cc:206 e cdc:51; o CPC/73 não entra", j.artigos_das_referencias(CC206 + CDC51))

    print("\nbaixar")
    e = local.get("/api/jurisprudencia").json()
    checar(e["total"] == 0 and not portal.pedidos and len(e["orgaos"]) == 10, "nada é pedido ao portal antes de a pessoa mandar", portal.pedidos)
    checar(local.post("/api/jurisprudencia/baixar", json={"orgaos": []}).status_code == 400, "sem órgão: recusa")

    def baixar(orgaos):
        r = local.post("/api/jurisprudencia/baixar", json={"orgaos": orgaos})
        limite = time.time() + 20
        while time.time() < limite and api.estado.jurisprudencia.andamento.get("baixando"):
            time.sleep(0.1)
        return r

    r = baixar(["terceira-turma"])
    e = local.get("/api/jurisprudencia").json()
    checar(r.status_code == 200 and e["total"] == 3 and e["arquivos"] == 2 and e["por_orgao"] == {"terceira-turma": 3} and e["escolhidos"] == ["terceira-turma"],
           "o zip base e o mensal entram; o dicionário não", e)
    checar(all("dicionario" not in u for u in portal.pedidos), "o que não é dado não é baixado")
    portal.arquivos["https://x/20240630.json"] = json.dumps([acordao("000000004", "LOCAÇÃO. FIADOR. Exoneração.", [], "20240620")]).encode()
    portal.recursos.append({"id": "r3", "name": "20240630.json", "url": "https://x/20240630.json"})
    # O STJ às vezes publica um mês com o JSON quebrado (visto de verdade, Segunda Seção, 2024).
    portal.arquivos["https://x/20240430.json"] = b'[{"id": "9" "ementa": "quebrado"}]'
    portal.recursos.append({"id": "r4", "name": "20240430.json", "url": "https://x/20240430.json"})
    n = len(portal.pedidos)
    baixar(["terceira-turma"])
    novos = [u for u in portal.pedidos[n:] if "package_show" not in u]
    checar(sorted(novos) == ["https://x/20240430.json", "https://x/20240630.json"] and api.estado.jurisprudencia.total() == 4,
           "baixar de novo só traz os arquivos novos", novos)
    defeito = api.estado.jurisprudencia.andamento.get("com_defeito") or []
    checar(len(defeito) == 1 and "20240430" in defeito[0] and not api.estado.jurisprudencia.andamento.get("erro"),
           "o arquivo com o JSON quebrado fica de fora, dito, e o resto segue", api.estado.jurisprudencia.andamento)

    print("\nprocurar")
    d = local.get("/api/jurisprudencia/procurar", params={"termo": "multa moratoria"}).json()
    ids = [a["id"] for a in d["acordaos"]]
    checar(set(ids) == {"000000002", "000000003"} and "[" in d["acordaos"][0]["trecho"], "por palavras, sem acento, com o trecho marcado", (ids, d["acordaos"][:1]))
    a = d["acordaos"][0]
    checar(a["citacao"].startswith("STJ, REsp ") and "rel. Min. Nancy Andrighi" in a["citacao"] and "DJe 20/05/2024" in a["citacao"],
           "a citação pronta", a["citacao"])
    d = local.get("/api/jurisprudencia/procurar", params={"termo": "fiador zebrino"}).json()
    checar([x["id"] for x in d["acordaos"]] == ["000000004"] and d["acordaos"][0]["todas"] is False,
           "sem nenhum com todas as palavras: com parte delas, dito", d["acordaos"])
    d = local.get("/api/jurisprudencia/procurar", params={"termo": "multa moratoria", "de": "2023-01-01"}).json()
    checar([x["id"] for x in d["acordaos"]] == ["000000003"], "pela data")
    d = local.get("/api/jurisprudencia/procurar", params={"codigo": "cc", "artigo": "206"}).json()
    checar([x["id"] for x in d["acordaos"]] == ["000000003", "000000001"], "os que citam o art. 206 do CC, do mais novo")

    print("\nna conversa, no editor e no MCP")
    import fundamentacao

    rel = fundamentacao.relacionados(api.estado, "qual o prazo?", "Pelo art. 206, § 3º, do CC.")
    checar(rel and [x["id"] for x in rel["acordaos"]] == ["000000003", "000000001"], "embaixo da resposta: os acórdãos que citam o artigo",
           rel and rel.get("acordaos"))
    f = fundamentacao.sugerir(api.estado, "A multa moratória na locação é abusiva e deve ser reduzida.")
    checar(f["acordaos"] and f["acordaos"][0]["id"] in ("000000002", "000000003"), "a fundamentação do editor sugere o acórdão", f["acordaos"])
    texto, erro = mcp_leis.chamar_escritorio(api.estado, {"escopo": {}}, "jurisprudencia_stj", {"termo": "fiador exoneração"})
    checar(not erro and "000000004"[-7:] in texto and mcp_leis.publica("jurisprudencia_stj"), "o MCP procura (ferramenta pública)", texto[:120])

    print("\nde fora e apagar")
    checar(politicas.de("GET", "/api/jurisprudencia/procurar") == politicas.PERMITIDO
           and politicas.de("POST", "/api/jurisprudencia/baixar") == politicas.BLOQUEADO, "de fora: procurar vale, baixar não")

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
                pag.on("pageerror", lambda e_: erros.append(str(e_)))
                pag.add_init_script("try { localStorage.setItem('paulus.boasvindas', '1'); } catch (e) {}")
                pag.goto(f"http://127.0.0.1:{porta}/entrar-local?chave=" + api.estado.acesso.chave, wait_until="load")
                pag.wait_for_function("() => typeof abaJurisprudenciaBib === 'function'")
                pag.wait_for_timeout(800)
                pag.evaluate("() => { mostrarBibliotecaContexto('jurisprudencia'); }")
                pag.wait_for_selector("[data-jur-orgao]", timeout=15000)
                texto = pag.inner_text("#bib-tela")
                checar("4 acórdãos guardados" in texto and "Terceira Turma" in texto and "nenhum dado do escritório" in texto,
                       "a aba: o que está guardado, os órgãos e o que sai daqui", texto[:300])
                pag.fill("#jur-termo", "multa moratória")
                pag.click("[data-jur-procurar]")
                pag.wait_for_selector(".jur-acordao", timeout=10000)
                checar(pag.locator(".jur-acordao").count() == 2 and pag.locator(".jur-trecho mark").count() >= 1, "procurar: os dois, com a palavra marcada")
                pag.click(".jur-acordao >> nth=0 >> [data-jur-abrir]")
                pag.wait_for_selector(".jur-ementa", timeout=5000)
                checar(True, "ver a ementa inteira")
                pag.wait_for_timeout(300)
                pag.screenshot(path=str(TMP / "n13-jurisprudencia.png"))
                pag.set_viewport_size({"width": 390, "height": 844})
                pag.wait_for_timeout(500)
                largos = pag.evaluate("() => [...document.querySelectorAll('#bib-tela *, #nav-tela *')].filter((e) => e.getBoundingClientRect().right > 392)"
                                      ".slice(0, 6).map((e) => e.tagName + '.' + e.className + ' ' + Math.round(e.getBoundingClientRect().right))")
                checar(pag.evaluate("() => document.documentElement.scrollWidth") <= 392, "no celular (390 px), nada vaza", largos)
                checar(not erros, "nenhum erro de JavaScript", erros[:3])
                print(f"  (fotos em {TMP})")
                nav.close()

    r = local.delete("/api/jurisprudencia")
    checar(r.status_code == 200 and r.json()["total"] == 0, "apagar tira tudo")

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
