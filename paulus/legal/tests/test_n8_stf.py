"""
N8 - as súmulas do STF, as vinculantes e as teses de repercussão geral no instalador
(tools/stf_pacote.py, config/acervo-inicial/, src/biblioteca/nativo.py, src/fundamentacao.py, src/mcp_leis.py).

  - o pacote: as súmulas do STF (sem as canceladas; as superadas marcadas),
    as vinculantes e as teses de repercussão geral, com a fonte e a data;
  - a instalação: as súmulas entram na Biblioteca como as do STJ; as teses
    entram na tabela de temas, com o tipo RG, sem apagar os temas do STJ (nem
    quando o STJ é atualizado);
  - na conversa (N7): "Súmula Vinculante 13", "Súmula 279 do STF" e "Tema 1 da
    repercussão geral" acham o do STF, não o do STJ; os temas do STF entram
    pelo artigo citado (art. 37 da CF);
  - no editor: a fundamentação traz a vinculante pelas palavras do trecho;
  - no MCP: sumulas_stf (e só as vinculantes), temas_repercussao_geral, e o
    temas_stj só com o STJ;
  - no Edge: a Biblioteca lista as súmulas do STF e as vinculantes.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_n8_stf.py
"""

from __future__ import annotations

import gzip
import json
import os
import sys
import tempfile
import threading
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-n8-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))
ACERVO = RAIZ / "config" / "acervo-inicial"

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def main() -> int:
    print("=" * 55)
    print("  N8 — STF: súmulas, vinculantes e repercussão geral")
    print("=" * 55)

    print("\no pacote")
    idx = json.loads((ACERVO / "indice.json").read_text(encoding="utf-8"))
    stf, vinc, rg = idx["sumulas"].get("stf", {}), idx["sumulas"].get("stf_vinculantes", {}), idx.get("temas_stf", {})
    checar(stf.get("enunciados", 0) >= 700 and stf.get("canceladas_fora", 0) >= 5 and vinc.get("enunciados", 0) >= 60 and rg.get("teses", 0) >= 1200,
           "as súmulas, as vinculantes e as teses, com as canceladas de fora", (stf.get("enunciados"), vinc.get("enunciados"), rg.get("teses")))
    texto_stf = gzip.decompress((ACERVO / "sumulas-stf.txt.gz").read_bytes()).decode("utf-8")
    checar("Súmula 3 do STF (superada)" in texto_stf and "Súmula 279 do STF\nPara simples reexame de prova não cabe recurso extraordinário." in texto_stf,
           "a superada marcada, e o enunciado logo abaixo do título")
    texto_vinc = gzip.decompress((ACERVO / "sumulas-vinculantes.txt.gz").read_bytes()).decode("utf-8")
    checar(texto_vinc.startswith("Súmula Vinculante 1 do STF\nOfende a garantia constitucional do ato jurídico perfeito"),
           "a Vinculante 1 com o enunciado (e não a jurisprudência citada)", texto_vinc[:120])
    cab = json.loads(gzip.open(ACERVO / "temas-rg-stf.jsonl.gz", "rt", encoding="utf-8").readline())
    checar(cab.get("fonte", "").startswith("https://portal.stf.jus.br") and cab.get("baixado_em"), "as teses dizem a fonte e a data", cab)

    import api
    import fundamentacao
    import mcp_leis
    from biblioteca import nativo
    from biblioteca.rotas import procurar_sumulas
    from fastapi.testclient import TestClient

    print("\na instalação")
    for th in threading.enumerate():
        if th.name == "temas-stj":
            th.join(90)
    temas = api.estado.temas
    n_rg = api.estado.base.um("SELECT COUNT(*) AS n FROM temas WHERE tipo = 'RG'")["n"]
    n_stj = api.estado.base.um("SELECT COUNT(*) AS n FROM temas WHERE tipo != 'RG'")["n"]
    checar(n_rg >= 1200 and n_stj > 1200, "as teses do STF entram junto dos temas do STJ", (n_rg, n_stj))
    t1 = [t for t in temas.procurar(numero="1") if t["tribunal"] == "STF"]
    checar(t1 and t1[0]["rotulo"] == "Tema 1 da repercussão geral/STF" and "PIS/COFINS-Importação" in t1[0]["tese"]
           and t1[0]["assuntos"] == "Paradigma: RE 559937", "o Tema 1 da repercussão geral, com a tese e o paradigma", t1[:1])
    checar(temas.instalar_rg() == 0, "e só uma vez")
    from test_l5_fundamentacao import CAB, linha

    linhas_falsas = "".join(linha("Tema", 1000 + i, "Trânsito em Julgado", "a questão", "a tese") for i in range(120))
    temas.atualizar_do_stj(baixar=lambda url: CAB + linhas_falsas)
    checar(api.estado.base.um("SELECT COUNT(*) AS n FROM temas WHERE tipo = 'RG'")["n"] == n_rg, "atualizar pelo STJ não apaga as teses do STF")
    nativo.instalar(api.estado.leis, api.estado.material, Path(os.environ["PAULUS_DADOS"]) / "leis", forcar=True)
    titulos = [x["titulo"] for x in procurar_sumulas(api.estado.material, numero="279", limite=10)]
    checar("Súmula 279 do STF" in titulos and "Súmula 279 do STJ" in titulos, "as súmulas do STF entram na Biblioteca, ao lado das do STJ", titulos)

    print("\nna conversa (N7)")
    r = fundamentacao.relacionados(api.estado, "nepotismo", "Pela Súmula Vinculante 13, é vedada a nomeação.") or {}
    checar([s["titulo"] for s in r.get("sumulas", [])] == ["Súmula Vinculante 13 do STF"], "“Súmula Vinculante 13”: a do STF", r.get("sumulas"))
    r = fundamentacao.relacionados(api.estado, "reexame", "Incide a Súmula 279 do STF.") or {}
    checar([s["titulo"] for s in r.get("sumulas", [])] == ["Súmula 279 do STF"], "“Súmula 279 do STF”: a do STF, não a do STJ", r.get("sumulas"))
    r = fundamentacao.relacionados(api.estado, "importação", "Veja o Tema 1 da repercussão geral.") or {}
    checar(r.get("temas") and r["temas"][0]["rotulo"] == "Tema 1 da repercussão geral/STF", "“Tema 1 da repercussão geral”: o do STF", r.get("temas", [])[:1])
    r = fundamentacao.relacionados(api.estado, "servidor", "Pelo art. 37 da CF, o concurso é obrigatório.") or {}
    checar(any("repercussão geral/STF" in t["rotulo"] for t in r.get("temas", [])), "os temas do STF entram pelo artigo citado (art. 37 da CF)",
           [t["rotulo"] for t in r.get("temas", [])])

    print("\nno editor")
    f = fundamentacao.sugerir(api.estado, "A nomeação de cônjuge para cargo em comissão na administração pública viola a Constituição.")
    checar(any("Vinculante 13" in s["titulo"] for s in f["sumulas"]), "a fundamentação traz a vinculante pelas palavras", [s["titulo"] for s in f["sumulas"]])

    print("\nno MCP")
    texto, _ = mcp_leis.chamar_escritorio(api.estado, {"escopo": {}}, "sumulas_stf", {"numero": "13", "vinculante": True})
    checar(texto.startswith("Súmula Vinculante 13 do STF") and "Súmula 13 do STF" not in texto, "sumulas_stf, só as vinculantes", texto[:80])
    texto, _ = mcp_leis.chamar_escritorio(api.estado, {"escopo": {}}, "temas_repercussao_geral", {"numero": "1"})
    checar(texto.startswith("Tema 1 da repercussão geral/STF") and "Paradigma: RE 559937" in texto, "temas_repercussao_geral", texto[:120])
    texto, _ = mcp_leis.chamar_escritorio(api.estado, {"escopo": {}}, "temas_stj", {"numero": "1"})
    checar("repercussão geral" not in texto, "temas_stj só com o STJ", texto[:120])

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
                pag.wait_for_function("() => typeof mostrarBibliotecaContexto === 'function'")
                pag.wait_for_timeout(800)
                pag.evaluate("() => { mostrarBibliotecaContexto('leis'); }")
                pag.wait_for_function("() => /Súmulas vinculantes do STF/.test((document.getElementById('bib-tela') || {}).innerText || '')", timeout=15000)
                texto = pag.inner_text("#bib-tela")
                checar("Súmulas do STF" in texto and "Súmulas vinculantes do STF" in texto, "a Biblioteca lista as súmulas do STF e as vinculantes")
                pag.wait_for_timeout(300)
                pag.screenshot(path=str(TMP / "n8-biblioteca.png"))
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
