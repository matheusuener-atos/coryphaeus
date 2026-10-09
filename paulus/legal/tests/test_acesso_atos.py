"""
Entrar com Atos, de fora (09/10/2026; src/acesso/atos_login.py, src/acesso/rotas.py).

A equipe que entra pelo endereco do escritorio entra com a Conta Atos: o
PAULUS manda o navegador a atos.dev.br (cliente pavlvs-escritorio, PKCE, nonce)
e a Atos volta direto ao escritorio. A troca do codigo e simulada (nada vai a
internet):

  - iniciar passa pelo anti-robo, devolve o endereco da Atos e poe o cookie
    que amarra a volta a este navegador;
  - a volta sem o cookie, com o state velho, com o nonce errado, de outro
    cliente ou de outro emissor nao entra;
  - a volta certa leva ao codigo do celular (como o Google levava); a conta
    de seguranca simples entra direto; e-mail sem conta nao entra;
  - o convite aceito pela Atos volta a pagina do convite com o QR.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_acesso_atos.py
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path

RAIZ = Path(__file__).parent.parent
TMP = Path(tempfile.mkdtemp(prefix="paulus-acesso-atos-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def _b64(d: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")


def main() -> int:
    from fastapi.testclient import TestClient

    import api
    import segredos
    from acesso.contas import codigo_totp

    print("=" * 55)
    print("  entrar com Atos, de fora")
    print("=" * 55)
    if not segredos.disponivel():
        print("  --   sem a protecao de dados do Windows: pulado")
        return 0
    servico = api.estado.acesso_de_fora
    prefs = api.estado.prefs.dados["acesso_remoto"]
    servico.conferir_turnstile = lambda token, ip="": "ok" if token == "ok" else "recusado"
    servico.cofre.tem = lambda: True
    prefs.update(ligado=True, hostname="moura.paulus.ia.br")
    diz: dict = {}
    trocas: list[dict] = []

    def trocar(code, verificador, volta):
        trocas.append({"code": code, "verificador": verificador, "volta": volta})
        corpo = {"iss": "https://atos.dev.br", "aud": "pavlvs-escritorio", "exp": int(time.time()) + 3600,
                 "email_verified": True, **diz}
        return {"access_token": "a", "id_token": _b64({"alg": "ES256"}) + "." + _b64(corpo) + ".x"}

    servico.atos.trocar = trocar
    try:
        c = servico.contas.criar("Edu", "edu@moura.adv.br", "colaborador", "")
        servico.contas.confirmar_totp(c["conta"]["id"], codigo_totp(c["segredo"], int(time.time() // 30) - 1))
        fora = TestClient(api.app, base_url="https://moura.paulus.ia.br", headers={"Cf-Connecting-IP": "200.9.9.9"})

        def ir(finalidade="entrar", convite="", cliente=fora):
            r = cliente.post("/api/acesso/atos/iniciar", json={"finalidade": finalidade, "convite": convite, "turnstile": "ok",
                                                               "dica": "edu@moura.adv.br"})
            url = urllib.parse.urlsplit(r.json().get("url", ""))
            return r, dict(urllib.parse.parse_qsl(url.query)), url

        def voltar(q, cliente=fora, **extra):
            diz.setdefault("nonce", q.get("nonce"))
            params = {"code": "c1", "state": q.get("state", ""), "iss": "https://atos.dev.br", **extra}
            return cliente.get("/api/acesso/atos/retorno?" + urllib.parse.urlencode(params), follow_redirects=False)

        print("\n  ir a Atos")
        r = fora.post("/api/acesso/atos/iniciar", json={"finalidade": "entrar", "turnstile": "robo"})
        checar(r.status_code == 403, "sem passar pelo anti-robo: 403", r.status_code)
        r, q, url = ir()
        checar(r.status_code == 200 and url.scheme + "://" + url.netloc + url.path == "https://atos.dev.br/entrar"
               and q["client_id"] == "pavlvs-escritorio" and q["redirect_uri"] == "https://moura.paulus.ia.br/api/acesso/atos/retorno"
               and q["code_challenge_method"] == "S256" and q.get("nonce") and q.get("login_hint") == "edu@moura.adv.br",
               "o endereco da Atos: pavlvs-escritorio, volta no escritorio, PKCE, nonce e a dica", q)
        checar("paulus_atos=" in r.headers.get("set-cookie", "") and "HttpOnly" in r.headers.get("set-cookie", ""),
               "o cookie que amarra a volta a este navegador", r.headers.get("set-cookie"))

        print("\n  as voltas que nao entram")
        outro = TestClient(api.app, base_url="https://moura.paulus.ia.br", headers={"Cf-Connecting-IP": "200.9.9.8"})
        diz.clear()
        diz.update(email="edu@moura.adv.br", name="Edu")
        rr = voltar(q, cliente=outro)
        checar(rr.status_code == 303 and "#erro=" in rr.headers["location"] and "navegador" in urllib.parse.unquote(rr.headers["location"]),
               "a volta em outro navegador (sem o cookie): recusada", rr.headers.get("location"))
        rr = voltar(q)
        checar("#erro=" in rr.headers["location"], "o state ja usado nao vale de novo", rr.headers.get("location"))
        r, q, _ = ir()
        diz.clear()
        diz.update(email="edu@moura.adv.br", name="Edu", nonce="outro")
        rr = voltar(q)
        checar("#erro=" in rr.headers["location"] and "pedido" in urllib.parse.unquote(rr.headers["location"]), "nonce errado: recusado",
               rr.headers.get("location"))
        r, q, _ = ir()
        diz.clear()
        diz.update(email="edu@moura.adv.br", aud="pavlvs-app")
        rr = voltar(q)
        checar("#erro=" in rr.headers["location"], "id_token de outro cliente: recusado")
        r, q, _ = ir()
        diz.clear()
        diz.update(email="edu@moura.adv.br")
        n = len(trocas)
        rr = voltar(q, iss="https://golpe.example")
        checar("#erro=" in rr.headers["location"] and len(trocas) == n, "volta de outro emissor: recusada antes de trocar")
        r, q, _ = ir()
        rr = voltar(q, error="access_denied")
        checar("#erro=" in rr.headers["location"] and "cancelada" in urllib.parse.unquote(rr.headers["location"]),
               "cancelar na Atos: volta dizendo que foi cancelada")

        print("\n  as voltas que entram")
        r, q, _ = ir()
        diz.clear()
        diz.update(email="Edu@Moura.adv.br", name="Edu")
        n = len(trocas)
        rr = voltar(q)
        loc = rr.headers["location"]
        checar(rr.status_code == 303 and loc.startswith("/#g=") and "e=edu%40moura.adv.br" in loc,
               "a conta certa vai ao codigo do celular", loc)
        checar(len(trocas) == n + 1 and trocas[-1]["volta"] == "https://moura.paulus.ia.br/api/acesso/atos/retorno",
               "a troca vai a Atos com o mesmo endereco de volta", trocas[-1:])
        pend = urllib.parse.parse_qs(loc[2:])["g"][0]
        rr = fora.post("/api/acesso/entrar/codigo", json={"pendente": pend, "codigo": codigo_totp(c["segredo"], int(time.time() // 30))})
        checar(rr.status_code == 200 and "paulus_sessao" in rr.headers.get("set-cookie", ""), "com o codigo do celular, a sessao abre",
               rr.text[:160])
        r, q, _ = ir()
        diz.clear()
        diz.update(email="ninguem@moura.adv.br")
        rr = voltar(q)
        checar("#erro=" in rr.headers["location"], "e-mail sem conta neste escritorio: nao entra", rr.headers.get("location"))
        simples = servico.contas.criar("Bia", "bia@moura.adv.br", "colaborador", "")
        servico.contas.confirmar_totp(simples["conta"]["id"], codigo_totp(simples["segredo"], int(time.time() // 30) - 1))
        servico.contas.mudar_seguranca(simples["conta"]["id"], "simples")
        r, q, _ = ir()
        diz.clear()
        diz.update(email="bia@moura.adv.br")
        rr = voltar(q)
        checar(rr.headers["location"] == "/#entrou" and "paulus_sessao" in rr.headers.get("set-cookie", ""),
               "seguranca simples: a Atos basta", rr.headers.get("location"))

        print("\n  o convite")
        codigo, _ = servico.convites.criar("Caio", "caio@moura.adv.br")
        r, q, _ = ir("convite", codigo)
        diz.clear()
        diz.update(email="caio@moura.adv.br", name="Caio")
        rr = voltar(q)
        checar(rr.headers["location"].startswith("/convite/" + codigo + "#g="), "o convite aceito pela Atos volta ao QR",
               rr.headers.get("location"))
    finally:
        prefs.update(ligado=False, hostname="")
        servico.__dict__.pop("conferir_turnstile", None)
        servico.cofre.__dict__.pop("tem", None)
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
