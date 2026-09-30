"""
Os niveis de seguranca das contas (acesso/contas.py NIVEIS) - o escritorio
escolhe, conta por conta, quanto pedir na entrada de fora:

  - "simples": so o Google (ou a senha); a conta fica pronta sem o
    autenticador e entra sem o passo do codigo;
  - "padrao": Google + codigo, podendo confiar no navegador por 30 dias;
  - "reforcada": Google + codigo sempre - "confiar" nao vale, e subir para
    ela esquece os navegadores confiados;
  - o convite leva o nivel: no "simples", aceitar pelo Google ja libera a
    conta, sem QR, e gasta o convite;
  - o padrao do escritorio vale para o convite sem nivel;
  - mudar o nivel (da conta ou o padrao) so na janela do servidor.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_e7_seguranca.py
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
TMP = Path(tempfile.mkdtemp(prefix="paulus-e7-"))
os.environ["PAULUS_DADOS"] = str(TMP / "dados")
os.environ["PAULUS_SEM_AVISOS"] = "1"
os.environ["PAULUS_GOOGLE_WEB_CLIENT_ID"] = "cliente-web.apps.googleusercontent.com"
os.environ["PAULUS_GOOGLE_WEB_CLIENT_SECRET"] = "segredo-web"
sys.path.insert(0, str(RAIZ / "src"))

_falhas: list[str] = []


def checar(cond, nome: str, detalhe=None) -> None:
    print(("  ok   " if cond else "  FALHOU  ") + nome + ("" if cond or detalhe is None else f"  -> {detalhe!r}"))
    if not cond:
        _falhas.append(nome)


def _jwt(**campos) -> str:
    b = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    corpo = {"iss": "https://accounts.google.com", "aud": "cliente-web.apps.googleusercontent.com",
             "exp": time.time() + 600, "email_verified": True, **campos}
    return b({"alg": "RS256"}) + "." + b(corpo) + ".assinatura"


def test_http() -> None:
    print("\nos niveis de seguranca, de ponta a ponta")
    import segredos

    if not segredos.disponivel():
        print("  pulado: sem DPAPI (fora do Windows)")
        return
    from fastapi.testclient import TestClient

    import api
    from acesso.contas import codigo_totp

    servico = api.estado.acesso_de_fora
    api.estado.prefs.dados["vinculo"] = {"email": "dono@x.com", "nome": "Dono", "em": "", "manter_aberto": True}
    prefs = api.estado.prefs.dados["acesso_remoto"]
    servico.conferir_turnstile = lambda token, ip="": "ok" if token == "ok" else "recusado"
    prefs["ligado"] = True
    prefs["hostname"] = "moura.paulus.ia.br"
    local = TestClient(api.app, headers=api.cabecalho_local())
    respostas = {}
    servico.google.trocar = lambda code, verificador, credenciais: respostas.get(code, {"error": "invalid_grant"})
    n = [0]

    def de_fora() -> TestClient:
        return TestClient(api.app, base_url="https://moura.paulus.ia.br", headers={"Cf-Connecting-IP": "200.7.7.7"},
                          follow_redirects=False)

    def google(f, email, **dados):
        """Vai ao Google e volta como `email`; devolve a resposta e o destino."""
        r = f.post("/api/acesso/google/iniciar", json={"turnstile": "ok", "finalidade": "entrar", **dados})
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(r.json().get("url", "")).query))
        n[0] += 1
        code = f"g{n[0]}"
        respostas[code] = {"id_token": _jwt(email=email)}
        r = f.get("/api/acesso/google/retorno", params={"code": code, "state": q.get("state", "")})
        return r, urllib.parse.unquote(r.headers.get("location", ""))

    try:
        t = servico.contas.criar("Tita", "tita@x.com", "titular", "senha-da-tita-1")
        servico.contas.confirmar_totp(t["conta"]["id"], codigo_totp(t["segredo"], int(time.time() // 30) - 1))
        checar(t["conta"]["seguranca"] == "padrao", "sem escolha, a conta nasce no nivel padrao", t["conta"]["seguranca"])

        print("  simples: so o Google")
        r = local.post("/api/acesso/contas", json={"nome": "Sil", "email": "sil@x.com", "seguranca": "simples"})
        checar(r.status_code == 200 and r.json()["conta"]["seguranca"] == "simples" and r.json()["conta"]["pronta"],
               "a conta simples nasce pronta, sem autenticador", r.text[:200])
        f = de_fora()
        r, para = google(f, "sil@x.com")
        checar(para == "/#entrou" and "paulus_sessao=" in r.headers.get("set-cookie", ""),
               "a volta do Google ja abre a sessao, sem o codigo", para)
        checar(f.get("/api/status").status_code == 200, "e a pessoa usa o PAULUS")
        checar(any(e.get("alvo") == "Google (segurança simples)" for e in servico.eventos), "o registro diz como entrou")

        print("  padrao: o navegador confiado")
        r = local.post("/api/acesso/contas", json={"nome": "Pat", "email": "pat@x.com"})
        pat = r.json()
        checar(pat["conta"]["seguranca"] == "padrao" and not pat["conta"]["pronta"], "padrao sem autenticador: nao pronta")
        servico.contas.confirmar_totp(pat["conta"]["id"], codigo_totp(pat["segredo"], int(time.time() // 30) - 1))
        g = de_fora()
        _, para = google(g, "pat@x.com")
        checar(para.startswith("/#g="), "padrao: a volta leva ao codigo", para)
        pend = urllib.parse.parse_qs(para.split("#", 1)[1])["g"][0]
        rec = servico.contas.novos_codigos(pat["conta"]["id"])
        r = g.post("/api/acesso/entrar/codigo", json={"pendente": pend, "codigo": rec[0], "confiar": True})
        checar(r.status_code == 200 and "paulus_confia=" in r.headers.get("set-cookie", ""), "padrao: 'confiar' vale")
        _, para = google(g, "pat@x.com")
        checar(para == "/#entrou", "o navegador confiado entra direto", para)

        print("  reforcada: o codigo sempre")
        r = local.put(f"/api/acesso/contas/{pat['conta']['id']}/seguranca", json={"nivel": "reforcada"})
        checar(r.status_code == 200 and r.json()["conta"]["seguranca"] == "reforcada", "mudar para reforcada", r.text[:160])
        _, para = google(g, "pat@x.com")
        checar(para.startswith("/#g="), "subir para reforcada esquece o navegador confiado", para)
        pend = urllib.parse.parse_qs(para.split("#", 1)[1])["g"][0]
        r = g.post("/api/acesso/entrar/codigo", json={"pendente": pend, "codigo": rec[1], "confiar": True})
        checar(r.status_code == 200 and "paulus_confia=" not in r.headers.get("set-cookie", ""),
               "reforcada: 'confiar' nao da o cookie", r.headers.get("set-cookie", "")[:200])
        r = local.put(f"/api/acesso/contas/{pat['conta']['id']}/seguranca", json={"nivel": "qualquer"})
        checar(r.status_code == 400, "nivel inventado: 400", r.status_code)

        print("  descer e subir de nivel")
        r = local.put(f"/api/acesso/contas/{pat['conta']['id']}/seguranca", json={"nivel": "simples"})
        _, para = google(de_fora(), "pat@x.com")
        checar(para == "/#entrou", "descer para simples: entra sem o codigo", para)
        r = local.post("/api/acesso/contas", json={"nome": "Sol", "email": "sol@x.com", "seguranca": "simples"})
        sol = r.json()["conta"]
        r = local.put(f"/api/acesso/contas/{sol['id']}/seguranca", json={"nivel": "padrao"})
        checar(r.status_code == 200 and not r.json()["conta"]["pronta"],
               "subir de simples (sem autenticador) deixa a conta esperando o autenticador", r.text[:200])
        _, para = google(de_fora(), "sol@x.com")
        checar(para.startswith("/#erro="), "e ela nao entra ate ligar o autenticador", para)

        print("  so na janela do servidor")
        tita = de_fora()
        _, para = google(tita, "tita@x.com")
        pend = urllib.parse.parse_qs(para.split("#", 1)[1])["g"][0]
        r = tita.post("/api/acesso/entrar/codigo", json={"pendente": pend, "codigo": codigo_totp(t["segredo"], int(time.time() // 30))})
        tita.headers["X-PAULUS-CSRF"] = r.json()["csrf"]
        r = tita.put(f"/api/acesso/contas/{sol['id']}/seguranca", json={"nivel": "simples"})
        checar(r.status_code == 403, "mudar o nivel de fora: 403, mesmo para o titular", r.status_code)
        r = tita.put("/api/acesso/seguranca-padrao", json={"nivel": "simples"})
        checar(r.status_code == 403, "mudar o padrao de fora: 403", r.status_code)

        print("  o convite leva o nivel")
        r = local.put("/api/acesso/seguranca-padrao", json={"nivel": "simples"})
        checar(r.status_code == 200 and local.get("/api/acesso/contas").json()["seguranca_padrao"] == "simples",
               "o padrao do escritorio muda e aparece nas contas")
        r = local.post("/api/acesso/convites", json={"nome": "Val", "email": "val@x.com"})
        codigo = r.json()["link"].rsplit("/", 1)[1]
        v = de_fora()
        checar(v.get("/api/acesso/convite/" + codigo).json().get("seguranca") == "simples",
               "o convite sem nivel leva o padrao do escritorio, e a pagina sabe")
        r, para = google(v, "val@x.com", finalidade="convite", convite=codigo)
        token = urllib.parse.parse_qs(para.split("#", 1)[1]).get("g", [""])[0]
        d = v.get(f"/api/acesso/convite/{codigo}/google", params={"t": token}).json()
        checar(d.get("simples") is True and "qr_svg" not in d, "aceito pelo Google: sem QR", d)
        val = next(c for c in servico.contas.listar() if c["email"] == "val@x.com")
        checar(val["pronta"] and val["seguranca"] == "simples" and not val["totp_confirmado"], "a conta ja esta pronta", val)
        checar(v.get("/api/acesso/convite/" + codigo).status_code == 410, "e o convite deixa de valer")
        _, para = google(de_fora(), "val@x.com")
        checar(para == "/#entrou", "a Val entra so com o Google", para)
        r = local.post("/api/acesso/convites", json={"nome": "Rui", "email": "rui@x.com", "seguranca": "reforcada"})
        c2 = r.json()["link"].rsplit("/", 1)[1]
        checar(de_fora().get("/api/acesso/convite/" + c2).json().get("seguranca") == "reforcada",
               "o nivel escolhido no convite vence o padrao")
    finally:
        prefs["ligado"] = False
        prefs["hostname"] = ""
        prefs["seguranca_padrao"] = "padrao"
        servico.__dict__.pop("conferir_turnstile", None)


def main() -> int:
    print("=" * 55)
    print("  E7 - niveis de seguranca por conta")
    print("=" * 55)
    try:
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
