"""
N7 - os temas e as súmulas na resposta da conversa (src/fundamentacao.py `relacionados`, js/67-fundamentacao.js).

  - por regra: os temas do STJ ligados aos artigos citados na pergunta e na
    resposta ("art. 206 do CC"), o tema e a súmula citados pelo número
    ("Tema 970", "Súmula 297 do STJ"), a posição da casa do artigo; a súmula do
    STF (fora desta etapa) não vira STJ; sem citação, nada;
  - na conversa (modelo simulado): o bloco vai embaixo da resposta, guardado
    com ela, e a resposta não muda; com a chave desligada, não vem;
  - no Edge: o bloco fechado embaixo da resposta, e aberto mostra o tema, a
    súmula e a posição da casa, com o aviso de que é por regra.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_n7_temas_na_conversa.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-n7-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))

_falhas: list[str] = []
RESPOSTA = "O prazo é de três anos, pelo art. 206, § 3º, do CC. Veja também a Súmula 297 do STJ e o Tema 970."


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def eventos(texto: str) -> list[tuple[str, dict]]:
    saida = []
    for bloco in texto.split("\n\n"):
        tipo = next((l[7:] for l in bloco.splitlines() if l.startswith("event: ")), "")
        dado = next((l[6:] for l in bloco.splitlines() if l.startswith("data: ")), "")
        if tipo:
            saida.append((tipo, json.loads(dado) if dado else {}))
    return saida


def simulado(ctx, pergunta: str = "", top: int = 6, apenas=None):
    yield "fontes", {"consultados": ["contrato.pdf"], "ignorados": [], "total_contratos": 1, "apenas": [],
                     "trechos": [{"documento": "contrato.pdf", "trecho": 1, "score": 1.0, "texto": "prazo"}]}
    yield "lendo", {"caracteres": 500, "trechos": 1, "documentos": 1, "caminho": "busca", "modelo": "simulado", "previsao": {"sabe": False}}
    yield "escrevendo", {"lendo_segundos": 0.1}
    for p in RESPOSTA.split(" "):
        yield "token", {"t": p + " "}
    yield "fim", {}


def main() -> int:
    print("=" * 55)
    print("  N7 — temas e súmulas na resposta")
    print("=" * 55)
    import api
    import fundamentacao as f
    from biblioteca import nativo
    from fastapi.testclient import TestClient

    for th in threading.enumerate():
        if th.name == "temas-stj":
            th.join(60)
    nativo.instalar(api.estado.leis, api.estado.material, Path(os.environ["PAULUS_DADOS"]) / "leis", forcar=True)
    api.estado.posicoes.gravar("cc", "206", "Para a casa, a pretensão de reparação civil prescreve em três anos.", "Dra. Ana")
    local = TestClient(api.app, headers=api.cabecalho_local())

    print("\npor regra")
    r = f.relacionados(api.estado, "Qual o prazo para cobrar?", RESPOSTA)
    rotulos = [t["rotulo"] for t in (r or {}).get("temas", [])]
    checar(r and "Tema Repetitivo 970/STJ" in rotulos and any("art. 206 do CC" in t["porque"] for t in r["temas"]),
           "os temas do art. 206 do CC e o Tema 970 citado", rotulos)
    checar(r and r["temas"][0]["rotulo"] == "Tema Repetitivo 970/STJ", "o tema citado pelo número vem primeiro", rotulos[:2])
    checar(r and [s["numero"] for s in r["sumulas"]] == ["297"] and "instituições financeiras" in r["sumulas"][0]["texto"],
           "a Súmula 297 do STJ, citada pelo número", r and r["sumulas"])
    checar(r and r["posicoes"] and r["posicoes"][0]["artigo"] == "art. 206 do CC" and r["posicoes"][0]["autor"] == "Dra. Ana",
           "a posição da casa do artigo citado", r and r["posicoes"])
    checar(r and "por regra" in r["aviso"] and "Confira" in r["aviso"], "com o aviso de que é por regra")
    s = f.relacionados(api.estado, "e a súmula?", "Pela Súmula 7 do STF, …")
    checar(not s or not s.get("sumulas"), "súmula do STF não vira súmula do STJ", s)
    checar(f.relacionados(api.estado, "qual o valor do contrato?", "O valor é de R$ 10.000,00.") is None, "sem citação, nada")
    lei = f.relacionados(api.estado, "multa", "A multa…", fontes=[{"origem": "lei", "codigo": "cc", "numero": "206"}])
    checar(lei and any("art. 206 do CC" in t["porque"] for t in lei["temas"]), "o artigo que veio como fonte de lei também conta")

    print("\nna conversa")
    habilidade = api.estado.registro.obter("perguntar")
    antes = habilidade.executar
    habilidade.executar = simulado
    try:
        tid = local.post("/api/trabalhos", json={"pedido": "teste N7"}).json()["id"]
        ev = eventos(local.post(f"/api/trabalhos/{tid}/perguntar", json={"pergunta": "Qual o prazo para cobrar a indenização?", "tudo": True}).text)
        tipos = [t for t, _ in ev]
        rel = next((d for t, d in ev if t == "relacionados"), None)
        checar("relacionados" in tipos and tipos.index("relacionados") > tipos.index("fim") and rel and rel["temas"],
               "o bloco chega depois do fim da resposta", tipos[-4:])
        m = local.get(f"/api/trabalhos/{tid}").json()["mensagens"][-1]
        checar(m["texto"].strip() == RESPOSTA and (m.get("cobertura") or {}).get("relacionados", {}).get("temas"),
               "guardado com a resposta, e a resposta não muda", m["texto"][:80])
        api.estado.prefs.dados.setdefault("conversa", {})["relacionados"] = False
        ev = eventos(local.post(f"/api/trabalhos/{tid}/perguntar", json={"pergunta": "E o prazo de novo?", "tudo": True}).text)
        checar(not any(t == "relacionados" for t, _ in ev), "com a chave desligada, não vem")
        api.estado.prefs.dados["conversa"]["relacionados"] = True

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
                    pag.wait_for_function("() => typeof abrirTrabalho === 'function' && typeof blocoRelacionados === 'function'")
                    pag.wait_for_timeout(800)
                    pag.evaluate("(id) => { abrirTrabalho(id); }", tid)
                    pag.wait_for_selector(".rel-bloco", timeout=15000)
                    resumo = pag.inner_text(".rel-bloco summary")
                    checar("Na Biblioteca" in resumo and "tema" in resumo and "súmula" in resumo and "art. 206 do CC" in resumo,
                           "fechado embaixo da resposta, com o que tem", resumo)
                    checar(pag.evaluate("() => !document.querySelector('.rel-bloco').open"), "começa fechado")
                    pag.click(".rel-bloco summary")
                    pag.wait_for_timeout(300)
                    texto = pag.inner_text(".rel-bloco")
                    checar("Tema Repetitivo 970/STJ" in texto and "Súmula 297" in texto and "Posição da casa" in texto and "por regra" in texto,
                           "aberto: o tema, a súmula e a posição da casa, com o aviso", texto[:300])
                    pag.screenshot(path=str(TMP / "n7-bloco.png"))
                    pag.set_viewport_size({"width": 390, "height": 844})
                    pag.wait_for_timeout(400)
                    checar(pag.evaluate("() => document.documentElement.scrollWidth") <= 392, "no celular (390 px), nada vaza")
                    checar(not erros, "nenhum erro de JavaScript", erros[:3])
                    print(f"  (fotos em {TMP})")
                    nav.close()
    finally:
        habilidade.executar = antes

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
