"""
O app instalavel do escritorio (12/10/2026): <nome>.paulus.ia.br vira PWA,
paulus.ia.br continua site.

  - de fora e sem sessao, o manifesto, o service worker, o icone e o
    js/instalar-app.js passam (o navegador pede o manifesto sem cookie, e o
    pedido de instalar aparece ja na tela de entrar); o resto do programa nao;
  - o manifesto tem escopo e inicio no endereco do escritorio, abre como app
    (standalone), leva o nome do endereco e nada mais do escritorio, e aponta
    a si mesmo em related_applications (o "ja esta instalado");
  - um Host estranho nao entra no nome;
  - o service worker nao guarda nada (sem Cache Storage) e so mexe nas paginas;
  - a tela de entrar e o programa carregam o js/instalar-app.js, e ele nao
    faz nada fora de *.paulus.ia.br (a janela do computador nao vira app);
  - o site (paulus.ia.br) nao ganhou manifesto.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_app_instalavel.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-app-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def test_arquivos() -> None:
    print("\nos arquivos")
    front = RAIZ / "frontend"
    js = (front / "js" / "instalar-app.js").read_text(encoding="utf-8")
    checar(r"if (!/\.paulus\.ia\.br$/.test(location.hostname)) return;" in js,
           "o instalar-app.js sai antes de tudo fora de *.paulus.ia.br")
    checar("beforeinstallprompt" in js and "getInstalledRelatedApps" in js and "display-mode: standalone" in js
           and "navigator.standalone" in js, "confere se ja e app, se ja esta instalado e usa o pedido do navegador")
    for pagina in ("entrar.html", "index.html"):
        html = (front / pagina).read_text(encoding="utf-8")
        checar('<script src="/js/instalar-app.js"></script>' in html and '<link rel="stylesheet" href="/css/instalar-app.css">' in html,
               f"{pagina} carrega o instalar-app.js e o estilo dele")
        checar('rel="manifest"' not in html, f"{pagina} nao liga o manifesto no <head> (so de fora, pelo script)")
    sw = (front / "sw.js").read_text(encoding="utf-8")
    checar("caches." not in sw and 'mode !== "navigate"' in sw, "o service worker nao guarda nada e so olha as paginas")
    site = RAIZ.parent.parent / "site"
    if site.exists():
        com_manifesto = [str(p.relative_to(site)) for p in site.rglob("*.html") if 'rel="manifest"' in p.read_text(encoding="utf-8")]
        checar(not com_manifesto and not list(site.rglob("*.webmanifest")), "paulus.ia.br continua site, sem manifesto", com_manifesto)


def test_http() -> None:
    print("\nHTTP, de fora e sem sessao")
    import segredos

    if not segredos.disponivel():
        print("  pulado: sem DPAPI (fora do Windows), o acesso de fora fica indisponivel")
        return
    from fastapi.testclient import TestClient

    import api

    fora = TestClient(api.app, base_url="https://carla.paulus.ia.br", headers={"Cf-Connecting-IP": "200.1.2.3"})
    api.estado.prefs.dados["acesso_remoto"]["ligado"] = True
    try:
        r = fora.get("/manifest.webmanifest")
        checar(r.status_code == 200 and r.headers.get("content-type", "").startswith("application/manifest+json"),
               "o manifesto passa sem sessao, com o tipo certo", (r.status_code, r.headers.get("content-type")))
        m = r.json()
        checar(m.get("scope") == "/" and m.get("start_url") == "/" and m.get("id") == "/" and m.get("display") == "standalone",
               "escopo e inicio no endereco do escritorio, como app", m)
        checar(m.get("name") == "PAVLVS · carla" and m.get("short_name") == "PAVLVS", "o nome e o do endereco", m.get("name"))
        checar(m.get("related_applications") == [{"platform": "webapp", "url": "https://carla.paulus.ia.br/manifest.webmanifest"}],
               "aponta a si mesmo, para o navegador dizer que ja esta instalado", m.get("related_applications"))
        icone = m["icons"][0]["src"]
        checar(fora.get(icone).status_code == 200, "o icone do manifesto passa sem sessao", icone)
        checar(set(m) <= {"id", "name", "short_name", "description", "lang", "start_url", "scope", "display",
                          "background_color", "theme_color", "icons", "related_applications"},
               "nada do escritorio no manifesto", sorted(m))
        r = fora.get("/sw.js")
        checar(r.status_code == 200 and "javascript" in r.headers.get("content-type", ""), "o service worker passa sem sessao")
        checar(r.headers.get("x-frame-options") == "DENY", "e leva os cabecalhos de seguranca de fora")
        r = fora.get("/js/instalar-app.js")
        checar(r.status_code == 200 and "beforeinstallprompt" in r.text, "o pedido de instalar passa sem sessao")
        checar(fora.get("/css/instalar-app.css").status_code == 200, "e o estilo dele tambem")
        r = fora.get("/js/02-casca.js")
        checar(r.status_code == 401, "o resto do programa continua fechado sem sessao", r.status_code)
        csp = fora.get("/").headers.get("content-security-policy", "")
        checar("default-src 'self'" in csp and "worker-src 'self'" in csp, "a CSP deixa o manifesto e o worker do proprio endereco", csp)

        estranho = TestClient(api.app, base_url="https://x.paulus.ia.br.mal.com", headers={"Cf-Connecting-IP": "200.1.2.3"})
        r = estranho.get("/manifest.webmanifest")
        if r.status_code == 200:
            checar(r.json().get("name") == "PAVLVS" and "related_applications" not in r.json(),
                   "Host estranho: o nome fica so PAVLVS", r.json())
        else:
            checar(True, f"Host estranho: recusado ({r.status_code})")
    finally:
        api.estado.prefs.dados["acesso_remoto"]["ligado"] = False


def main() -> int:
    print("=" * 55)
    print("  O app instalavel do escritorio")
    print("=" * 55)
    try:
        test_arquivos()
        test_http()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
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
