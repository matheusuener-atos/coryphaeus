"""
Portao da R1 - a chave da janela local (src/acesso/chave.py e porteiro.py).

  - sem chave, TODA rota registrada no app responde 403 - a lista sai de
    `app.routes`, e nao de uma lista escrita a mao: rota nova nasce coberta;
  - com o cabecalho X-PAULUS-Chave ou o cookie da sessao local, o
    comportamento e o de sempre;
  - chave errada: 403;
  - `/entrar-local` troca a chave por um cookie, de valor diferente da chave,
    e o mesmo endereco nao vale uma segunda vez;
  - cabecalho forjado (Cf-Connecting-IP, X-Forwarded-For de 127.0.0.1) nao
    faz ninguem virar local;
  - o desktop.py grava a chave no arquivo de instancia e a segunda instancia
    manda o cabecalho.

Tudo numa pasta temporaria (PAULUS_DADOS).

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_r1_chave_da_janela.py
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-r1-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def _caminho_de_exemplo(rota: str) -> str:
    """/api/x/{id}/y -> /api/x/1/y; {caminho:path} -> a/b."""
    return re.sub(r"\{([^}:]+)(:[^}]+)?\}", lambda m: "a/b" if m.group(2) == ":path" else "1", rota)


def test_todas_as_rotas_sem_chave() -> None:
    print("\nsem chave, toda rota registrada recusa")
    from fastapi.routing import APIRoute
    from fastapi.testclient import TestClient

    import api

    sem = TestClient(api.app)
    rotas = [r for r in api.app.routes if hasattr(r, "path")]
    checar(len(rotas) > 300, "as rotas vem do app", len(rotas))
    passaram = []
    do_word = []
    import word_suplemento

    for r in rotas:
        metodos = sorted(getattr(r, "methods", None) or {"GET"})
        for m in metodos:
            if m == "HEAD":
                continue
            resp = sem.request(m, _caminho_de_exemplo(r.path))
            # W1: o suplemento do Word tem porta e token próprios (como o /mcp):
            # sem a chave, recusa com 404 (desligado) ou 401 (sem token).
            if (m, r.path) in word_suplemento.PAREAR or r.path.startswith(word_suplemento.PREFIXO_SUPLEMENTO):
                if resp.status_code not in (401, 404):
                    do_word.append((m, r.path, resp.status_code))
                continue
            if resp.status_code != 403:
                passaram.append((m, r.path, resp.status_code))
    checar(not passaram, f"{len(rotas)} rotas, todas 403 sem a chave", passaram[:10])
    checar(not do_word, "as do suplemento do Word recusam com 404 (desligado) ou 401 (sem token)", do_word[:5])
    checar(sem.get("/rota/que/nao/existe").status_code == 403, "ate rota que nao existe responde 403 (nao 404)")
    r = sem.get("/")
    checar(r.status_code == 403 and "janela do PAULUS" in r.text, "a pagina inicial explica, em HTML", r.status_code)
    r = sem.get("/api/status")
    checar(r.status_code == 403 and r.headers["content-type"].startswith("application/json"), "a API recusa em JSON")
    _ = APIRoute


def test_com_chave() -> None:
    print("\ncom a chave, como sempre")
    from fastapi.testclient import TestClient

    import api

    com = TestClient(api.app, headers=api.cabecalho_local())
    r = com.get("/api/status")
    checar(r.status_code == 200 and "versao" in r.json(), "cabecalho X-PAULUS-Chave: /api/status responde", r.status_code)
    checar(com.get("/").status_code == 200, "cabecalho: a pagina abre")
    errada = TestClient(api.app, headers={"X-PAULUS-Chave": api.estado.acesso.chave[:-2] + "xx"})
    checar(errada.get("/api/status").status_code == 403, "chave errada: 403")
    forjado = TestClient(api.app, headers={"Cf-Connecting-IP": "127.0.0.1", "X-Forwarded-For": "127.0.0.1",
                                           "X-Real-IP": "127.0.0.1", "Host": "127.0.0.1:8000"})
    checar(forjado.get("/api/status").status_code == 403, "cabecalho de origem forjado nao vira local")


def test_entrar_local() -> None:
    print("\n/entrar-local")
    from fastapi.testclient import TestClient

    import api
    from acesso.chave import COOKIE

    janela = TestClient(api.app)
    chave = api.estado.acesso.chave
    checar(janela.get("/entrar-local?chave=errada").status_code == 403, "chave errada nao entra")
    r = janela.get("/entrar-local?chave=" + chave)
    cookie = r.cookies.get(COOKIE) or janela.cookies.get(COOKIE)
    checar(r.status_code == 200 and bool(cookie), "a chave vira cookie", r.status_code)
    checar(cookie != chave, "o cookie nao e a chave")
    bruto = r.headers.get("set-cookie", "")
    checar("HttpOnly" in bruto and "SameSite=Strict" in bruto, "cookie HttpOnly e SameSite=Strict", bruto)
    checar("location.hash" in r.text, "segue para / levando o #fragmento")
    checar(janela.get("/api/status").status_code == 200, "com o cookie, a janela e local")
    outra = TestClient(api.app)
    checar(outra.get("/entrar-local?chave=" + chave).status_code == 403, "o mesmo endereco nao vale duas vezes")
    checar(outra.get("/api/status").status_code == 403, "e quem tentou continua de fora")
    falso = TestClient(api.app, cookies={COOKIE: "inventado"})
    checar(falso.get("/api/status").status_code == 403, "cookie inventado: 403")
    checar(janela.post("/entrar-local?chave=" + chave).status_code in (403, 405), "entrar-local so por GET")


def test_desktop() -> None:
    print("\no desktop.py e a segunda instancia")
    import desktop

    checar("chave" in desktop._conteudo_da_instancia(8123, "abc"), "o arquivo de instancia leva a chave")
    (TMP / "dados").mkdir(parents=True, exist_ok=True)
    desktop._instancia_path().write_text('{"porta": 1, "pid": 1, "chave": "k123"}', encoding="utf-8")
    checar(desktop._chave_da_instancia() == "k123", "a segunda instancia le a chave do arquivo")
    checar(desktop._cabecalho_local() == {"X-PAULUS-Chave": "k123"}, "e manda no cabecalho")
    checar("/entrar-local?chave=" in desktop._endereco_da_janela(8123, "k", ""), "a janela abre pelo /entrar-local")
    checar(desktop._endereco_da_janela(8123, "k", "C:/a b.pdf").endswith("#perguntar=C%3A/a%20b.pdf"),
           "com o fragmento do Explorer depois")


def main() -> int:
    print("=" * 55)
    print("  R1 - a chave da janela local")
    print("=" * 55)
    try:
        test_todas_as_rotas_sem_chave()
        test_com_chave()
        test_entrar_local()
        test_desktop()
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
