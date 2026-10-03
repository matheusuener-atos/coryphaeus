"""
Portao da E3a do PAULUS de equipe (docs/PLANO-EQUIPE.md) - entrar com o
Google, e o codigo do celular depois (src/acesso/google_login.py).

Com o Google simulado (a troca do codigo devolve um id_token montado aqui):

  - sem o cliente web configurado ou sem o acesso conectado, o botao nao
    aparece; com os dois, aparece;
  - ir ao Google pede a verificacao contra robos; o endereco leva PKCE S256,
    o retorno de paulus.ia.br e o state "<slug>~<aleatorio>", e um cookie
    amarra a volta ao navegador;
  - a volta sem o cookie, com o state gasto, com o id_token de outro
    aplicativo ou sem e-mail confirmado: recusada, com a frase;
  - entrar: conta do e-mail + codigo do celular = sessao; e-mail sem conta,
    a frase do convite;
  - convite pelo Google: so o e-mail do convite; a conta nasce, o QR volta
    uma vez, o codigo confirma, e dai em diante entra com Google + codigo.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_e3_google.py
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
TMP = Path(tempfile.mkdtemp(prefix="paulus-e3-"))
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
    print("\nentrar com o Google, de ponta a ponta")
    import segredos

    if not segredos.disponivel():
        print("  pulado: sem DPAPI (fora do Windows)")
        return
    from fastapi.testclient import TestClient

    import api
    from acesso.contas import codigo_totp

    servico = api.estado.acesso_de_fora
    # o PAULUS do servidor vinculado (E5), aberto: convidar e ligar o acesso pedem o vinculo
    api.estado.prefs.dados["vinculo"] = {"email": "dono@x.com", "nome": "Dono", "em": "", "manter_aberto": True}
    prefs = api.estado.prefs.dados["acesso_remoto"]
    servico.conferir_turnstile = lambda token, ip="": "ok" if token == "ok" else "recusado"
    prefs["ligado"] = True
    local = TestClient(api.app, headers=api.cabecalho_local())
    respostas = {}
    trocas = []

    def trocar(code, verificador, credenciais):
        trocas.append((code, verificador, credenciais["client_secret"]))
        return respostas.get(code, {"error": "invalid_grant"})

    servico.google.trocar = trocar

    def de_fora() -> TestClient:
        return TestClient(api.app, base_url="https://moura.paulus.ia.br", headers={"Cf-Connecting-IP": "200.4.4.4"},
                          follow_redirects=False)

    def ir(f, **dados):
        r = f.post("/api/acesso/google/iniciar", json={"turnstile": "ok", **dados})
        url = r.json().get("url", "") if r.status_code == 200 else ""
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
        return r, q

    def pend(para: str) -> str:
        return urllib.parse.parse_qs(para.split("#", 1)[1])["g"][0]

    def voltar(f, code, state):
        r = f.get("/api/acesso/google/retorno", params={"code": code, "state": state})
        return r, urllib.parse.unquote(r.headers.get("location", ""))

    try:
        f = de_fora()
        checar(f.get("/api/acesso/entrar/config").json().get("google") is False, "sem o acesso conectado: sem o botao")
        prefs["hostname"] = "moura.paulus.ia.br"
        checar(f.get("/api/acesso/entrar/config").json().get("google") is True, "com o cliente web e o acesso: o botao aparece")

        t = servico.contas.criar("Tita", "tita@x.com", "titular", "senha-da-tita-1")
        servico.contas.confirmar_totp(t["conta"]["id"], codigo_totp(t["segredo"], int(time.time() // 30) - 1))

        print("  ir ao Google")
        r = f.post("/api/acesso/google/iniciar", json={"finalidade": "entrar"})
        checar(r.status_code == 403, "sem a verificacao contra robos: 403", r.status_code)
        r, q = ir(f, finalidade="entrar")
        checar(r.status_code == 200 and q.get("redirect_uri") == "https://paulus.ia.br/oauth/google"
               and q.get("code_challenge_method") == "S256" and q.get("scope") == "openid email profile"
               and q.get("state", "").startswith("moura~"), "o endereco do Google: PKCE, retorno e state", q)
        checar("paulus_google=" in r.headers.get("set-cookie", "") and "HttpOnly" in r.headers.get("set-cookie", ""),
               "o cookie que amarra a volta a este navegador", r.headers.get("set-cookie"))
        # 02/10: o entrar nao forca a tela do Google (select_account pedia a
        # escolha de conta em todo login); a dica do aparelho vira login_hint.
        checar("prompt" not in q and "login_hint" not in q, "entrar sem prompt: o Google só pergunta na primeira vez", q.get("prompt"))
        _, q = ir(f, finalidade="entrar", dica="tita@x.com")
        checar(q.get("login_hint") == "tita@x.com" and "prompt" not in q, "a conta da última entrada vai como login_hint", q.get("login_hint"))
        _, q = ir(f, finalidade="entrar", dica="nao-e-email")
        checar("login_hint" not in q, "dica que não é e-mail não vai ao Google")

        print("  a volta, recusada")
        outro = de_fora()
        respostas["c1"] = {"id_token": _jwt(email="tita@x.com")}
        _, para = voltar(outro, "c1", q["state"])
        checar(para.startswith("/#erro=") and "navegador" in para, "sem o cookie (outro navegador): recusada", para)
        _, para = voltar(f, "c1", q["state"])
        checar(para.startswith("/#erro=") and "comece de novo" in para, "o state ja gasto nao vale de novo", para)
        _, q = ir(f, finalidade="entrar")
        respostas["c2"] = {"id_token": _jwt(email="tita@x.com", aud="outro-aplicativo")}
        _, para = voltar(f, "c2", q["state"])
        checar("não é para este aplicativo" in para, "id_token de outro aplicativo: recusado", para)
        _, q = ir(f, finalidade="entrar")
        respostas["c3"] = {"id_token": _jwt(email="tita@x.com", email_verified=False)}
        _, para = voltar(f, "c3", q["state"])
        checar("e-mail confirmado" in para, "e-mail nao confirmado no Google: recusado", para)
        _, q = ir(f, finalidade="entrar")
        respostas["c4"] = {"id_token": _jwt(email="ninguem@x.com")}
        _, para = voltar(f, "c4", q["state"])
        checar("peça um convite" in para, "e-mail sem conta: a frase do convite", para)

        print("  entrar: Google + codigo do celular")
        _, q = ir(f, finalidade="entrar")
        respostas["c5"] = {"id_token": _jwt(email="Tita@X.com")}
        r, para = voltar(f, "c5", q["state"])
        checar(r.status_code == 303 and para.startswith("/#g="), "a volta leva ao codigo do celular (depois do #)", para)
        checar(trocas[-1][1] and trocas[-1][2] == "segredo-web", "a troca usa o verificador PKCE e o segredo, aqui")
        pendente = pend(para)
        r = f.post("/api/acesso/entrar/codigo", json={"pendente": pendente,
                                                      "codigo": codigo_totp(t["segredo"], int(time.time() // 30))})
        checar(r.status_code == 200 and r.json().get("csrf"), "com o codigo: sessao", r.text[:160])

        print("  o convite pelo Google")
        c = local.post("/api/acesso/convites", json={"nome": "Dani Lima", "email": "dani@x.com"}).json()
        codigo = c["link"].rsplit("/", 1)[1]
        g = de_fora()
        r, q = ir(g, finalidade="convite", convite=codigo)
        checar(r.status_code == 200, "ir ao Google pelo convite")
        respostas["d1"] = {"id_token": _jwt(email="outra@x.com")}
        _, para = voltar(g, "d1", q["state"])
        checar(para.startswith("/convite/" + codigo + "#erro=") and "dani@x.com" in para,
               "outra conta do Google: volta ao convite dizendo qual e-mail", para)
        r, q = ir(g, finalidade="convite", convite=codigo)
        respostas["d2"] = {"id_token": _jwt(email="dani@x.com", name="Dani Lima")}
        _, para = voltar(g, "d2", q["state"])
        checar(para.startswith("/convite/" + codigo + "#g="), "o e-mail do convite: volta com o token do QR", para)
        token = para.split("#g=", 1)[1]
        r = g.get(f"/api/acesso/convite/{codigo}/google", params={"t": token})
        checar(r.status_code == 200 and r.json()["otpauth"].startswith("otpauth://"), "o QR volta uma vez", r.text[:120])
        checar(g.get(f"/api/acesso/convite/{codigo}/google", params={"t": token}).status_code == 410, "e so uma vez")
        segredo = r.json()["segredo"]
        r = g.post(f"/api/acesso/convite/{codigo}/confirmar", json={"codigo": codigo_totp(segredo, int(time.time() // 30))})
        checar(r.status_code == 200 and len(r.json()["codigos_recuperacao"]) == 10, "confirma com o codigo do celular")
        _, q = ir(g, finalidade="entrar")
        respostas["d3"] = {"id_token": _jwt(email="dani@x.com")}
        _, para = voltar(g, "d3", q["state"])
        r = g.post("/api/acesso/entrar/codigo", json={"pendente": pend(para),
                                                      "codigo": codigo_totp(segredo, int(time.time() // 30) + 1)})
        checar(r.status_code == 200, "a Dani entra com Google + codigo", r.text[:160])

        print("  confiar neste navegador por 30 dias")
        _, q = ir(g, finalidade="entrar")
        respostas["d4"] = {"id_token": _jwt(email="dani@x.com")}
        _, para = voltar(g, "d4", q["state"])
        checar("&e=dani@x.com" in para, "a volta leva o e-mail para a tela do codigo", para)
        r = g.post("/api/acesso/entrar/codigo", json={"pendente": pend(para),
                                                      # o do celular ja foi gasto nesta janela: um de recuperacao
                                                      "codigo": servico.contas.novos_codigos(
                                                          next(x for x in servico.contas.listar() if x["email"] == "dani@x.com")["id"])[0],
                                                      "confiar": True})
        cookie = r.headers.get("set-cookie", "")
        checar(r.status_code == 200 and "paulus_confia=" in cookie and "Path=/api/acesso" in cookie and "HttpOnly" in cookie,
               "com 'confiar', o navegador ganha o cookie (so do login, HttpOnly)", cookie[:200])
        _, q = ir(g, finalidade="entrar")
        respostas["d5"] = {"id_token": _jwt(email="dani@x.com")}
        r, para = voltar(g, "d5", q["state"])
        checar(para == "/#entrou" and "paulus_sessao=" in r.headers.get("set-cookie", ""),
               "o proximo login pelo Google entra direto, sem o codigo", para)
        estranho = de_fora()
        _, q = ir(estranho, finalidade="entrar")
        respostas["d6"] = {"id_token": _jwt(email="dani@x.com")}
        _, para = voltar(estranho, "d6", q["state"])
        checar(para.startswith("/#g="), "outro navegador (sem o cookie) ainda pede o codigo", para)
        dani = next(x for x in servico.contas.listar() if x["email"] == "dani@x.com")
        servico.contas.encerrar_sessoes(dani["id"])
        _, q = ir(g, finalidade="entrar")
        respostas["d7"] = {"id_token": _jwt(email="dani@x.com")}
        _, para = voltar(g, "d7", q["state"])
        checar(para.startswith("/#g="), "encerrar as sessoes esquece o navegador confiado", para)
        conta = next(x for x in servico.contas.listar() if x["email"] == "dani@x.com")
        checar(conta["papel"] == "colaborador", "e e colaborador")

        print("  so o Google (decisao do escritorio)")
        checar(f.get("/api/acesso/entrar/config").json().get("so_google") is True, "a tela de entrar sabe que e so o Google")
        r = f.post("/api/acesso/entrar", json={"email": "tita@x.com", "senha": "senha-da-tita-1", "turnstile": "ok"})
        checar(r.status_code == 403 and "Google" in r.json().get("detail", ""), "e-mail e senha de fora: 403", r.text[:160])
        c = local.post("/api/acesso/convites", json={"nome": "Edu", "email": "edu@gmail.com",
                                                     "email_secundario": "edu@escritorio.com"}).json()
        cod = c["link"].rsplit("/", 1)[1]
        checar(g.get("/api/acesso/convite/" + cod).json().get("so_google") is True, "o convite sabe que e so o Google")
        r = g.post(f"/api/acesso/convite/{cod}/aceitar", json={"senha": "senha-longa-123", "turnstile": "ok"})
        checar(r.status_code == 403, "aceitar o convite com senha: 403", r.status_code)
        r = local.post("/api/acesso/contas", json={"nome": "Fabi", "email": "fabi@gmail.com", "email_secundario": "fabi@moura.adv.br"})
        checar(r.status_code == 200 and r.json()["conta"]["email_secundario"] == "fabi@moura.adv.br",
               "criar conta aqui sem senha, com e-mail secundario", r.text[:160])
        fid = r.json()["conta"]["id"]
        r = local.patch(f"/api/acesso/contas/{fid}", json={"email_secundario": "fabi2@moura.adv.br"})
        checar(r.status_code == 200 and r.json()["conta"]["email_secundario"] == "fabi2@moura.adv.br", "trocar o secundario")
        r = f.post("/api/acesso/minha-senha", json={"atual": "x", "nova": "y" * 12, "codigo": "000000"},
                   headers={"X-PAULUS-CSRF": f.get("/api/acesso/eu").json().get("csrf", "")})
        checar(r.status_code == 403, "trocar a propria senha de fora: 403 (nao ha senha)", r.status_code)
        prefs["so_google"] = False
        checar(f.get("/api/acesso/entrar/config").json().get("so_google") is False, "desligando a regra, a senha volta")
        prefs["so_google"] = True
    finally:
        prefs["ligado"] = False
        prefs["hostname"] = ""
        servico.__dict__.pop("conferir_turnstile", None)


def main() -> int:
    print("=" * 55)
    print("  E3a - entrar com o Google + codigo do celular")
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
