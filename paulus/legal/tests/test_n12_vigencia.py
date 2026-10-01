"""
N12 - vigência: o texto da redação anterior e a vacatio legis (src/vigencia.py,
tools/vigencia_pacote.py, config/acervo-inicial/vigencia-pacote.json.gz).

  - o pacote do instalador: as leis lidas (com a publicação, a cláusula e o
    vigor) e as redações riscadas dos códigos;
  - as versões de um dispositivo, na ordem do tempo: numa data, a redação que
    valia, com o texto; hoje, a de hoje;
  - a vacatio: a mudança vale a partir da publicação mais o prazo (Lei
    10.695/2003: 30 dias); vigência em partes é dita;
  - nos códigos de verdade: CDC 39 em 1993 com o texto anterior do caput;
    CLT 477 em 2000 com o caput antigo; CP 121 com a vacatio da Lei 13.964;
  - a frase do que a resposta garante muda com o pacote;
  - no Edge: o texto anterior no diálogo da vigência.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_n12_vigencia.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-n12-"))
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
    print("  N12 — texto anterior e vacatio legis")
    print("=" * 55)
    import vigencia as v

    print("\no pacote")
    p = v.pacote()
    riscadas = {c: sum(len(x) for x in a.values()) for c, a in p.get("anteriores", {}).items()}
    checar(len(p.get("leis", {})) >= 500 and sum(1 for x in p["leis"].values() if x.get("simples")) >= 400,
           "as leis lidas, a maioria com prazo simples", len(p.get("leis", {})))
    checar(len(riscadas) == 11 and riscadas.get("clt", 0) > 1000 and riscadas.get("cf", 0) > 300, "as redações riscadas dos 11 códigos", riscadas)
    x = p["leis"].get("lei|10695|2003") or {}
    checar(x.get("publicacao") == "2003-07-02" and x.get("vacatio_dias") == 30 and x.get("vigor") == "2003-08-01",
           "a Lei 10.695/2003: publicada em 02/07, 30 dias, vale em 01/08", x)
    checar((p["leis"].get("lei|5584|1970") or {}).get("publicacao") == "1970-06-29", "a republicação de anos depois não vira a publicação")

    print("\nas versões de um dispositivo")
    d = {"rotulo": "caput", "texto": "Texto de hoje.", "vetado": False, "revogado": False,
         "notas": v.notas("(Redação dada pela Lei nº 13.874, de 20.9.2019)"),
         "anteriores": [{"texto": "Texto original.", "notas": []},
                        {"texto": "Texto do meio.", "notas": v.notas("(Redação dada pela Lei nº 8.884, de 11.6.1994)")}]}
    s93, s00, s20 = (v.situacao(d, q, "cdc") for q in ("1993-01-01", "2000-01-01", "2020-01-01"))
    checar(s93.get("texto") == "Texto original." and s00.get("texto") == "Texto do meio." and s20["estado"] == "vigente",
           "em 1993 a original, em 2000 a do meio, em 2020 a de hoje", (s93, s00, s20))
    sem = dict(d, anteriores=[])
    checar("não guarda o texto anterior" in v.situacao(sem, "1993-01-01", "cdc")["frase"], "sem riscado: diz que o Planalto não guardou")

    print("\na vacatio")
    n = v.notas("(Redação dada pela Lei nº 10.695, de 1º.7.2003)")[0]
    checar(n["data"] == "2003-07-01" and n["efetiva"] == "2003-08-01" and n["vacatio_dias"] == 30, "a nota ganha o vigor (com o “1º”)", n)
    dv = {"rotulo": "caput", "texto": "Novo.", "vetado": False, "revogado": False,
          "notas": v.notas("(Redação dada pela Lei nº 10.695, de 1º.7.2003)"), "anteriores": [{"texto": "Velho.", "notas": []}]}
    s = v.situacao(dv, "2003-07-15", "cp")
    checar(s.get("texto") == "Velho." and "em vigor desde 01/08/2003" in s["frase"] and "30 dias de vacatio" in s["frase"],
           "no meio da vacatio, ainda valia a anterior, e diz por quê", s)
    checar(v.situacao(dv, "2003-08-01", "cp")["estado"] == "vigente", "no dia do vigor, a nova")
    partes = v.notas("(Incluído pela Lei nº 13.874, de 20.9.2019)")[0]
    checar(partes["em_partes"], "vigência em partes (Lei 13.874/2019): marcada", partes)

    import api
    from biblioteca import nativo
    from fastapi.testclient import TestClient

    nativo.instalar(api.estado.leis, api.estado.material, Path(os.environ["PAULUS_DADOS"]) / "leis", forcar=True)
    local = TestClient(api.app, headers=api.cabecalho_local())

    print("\nnos códigos de verdade")
    r = local.get("/api/leis/vigencia?codigo=cdc&numero=39&data=1993-01-01").json()
    caput = next(x for x in r["dispositivos"] if x["rotulo"] == "caput")
    checar(caput["na_data"].get("texto") == "É vedado ao fornecedor de produtos ou serviços:" and "em vigor desde 13/06/1994" in caput["na_data"]["frase"],
           "CDC 39 em 1993: o texto anterior do caput, e quando a nova passou a valer", caput["na_data"])
    r = local.get("/api/leis/vigencia?codigo=clt&numero=477&data=2000-01-01").json()
    caput = next(x for x in r["dispositivos"] if x["rotulo"] == "caput")
    checar(caput["na_data"].get("texto", "").startswith("É assegurado a todo empregado"), "CLT 477 em 2000: o caput antigo", caput["na_data"])
    r = local.get("/api/leis/vigencia?codigo=cp&numero=121&data=2020-01-01").json()
    h = [x for x in r["historico"] if x["lei"] == "Lei nº 13.964"]
    checar(h and h[0]["vigor"] == "2020-01-23" and h[0]["vacatio_dias"] == 30, "CP 121: a Lei 13.964 vale de 23/01/2020 (30 dias)", h[:1])
    checar("pacote de vigência do instalador" in r["limites"], "a frase do que a resposta garante fala do pacote", r["limites"])

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
        with sync_playwright() as pw:
            try:
                nav = pw.chromium.launch(channel="msedge")
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
                pag.evaluate("() => { const c = document.getElementById('vig-data'); c.value = '1993-01-01'; c.dispatchEvent(new Event('change')); }")
                pag.wait_for_selector(".vig-anterior", timeout=10000)
                checar("É vedado ao fornecedor de produtos ou serviços:" in pag.inner_text(".vig-anterior"), "o texto anterior no diálogo")
                checar("dias de vacatio" in pag.inner_text("#vig-corpo") or "em vigor desde" in pag.inner_text("#vig-corpo"), "e quando a mudança passou a valer")
                pag.wait_for_timeout(300)
                pag.screenshot(path=str(TMP / "n12-vigencia.png"))
                checar(not erros, "nenhum erro de JavaScript", erros[:3])
                print(f"  (fotos em {TMP})")
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
