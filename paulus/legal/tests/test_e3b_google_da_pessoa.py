"""
Portao da E3b do PAULUS de equipe (docs/PLANO-EQUIPE.md) - o e-mail, a
Agenda e o Drive da conta de quem entrou.

Com o Google simulado:

  - conectar o proprio Google pede estar dentro (de fora); o endereco pede o
    e-mail, a Agenda e o Drive, offline;
  - a volta cria a conta de e-mail DA PESSOA (dono = a conta do acesso,
    cliente web); /api/acesso/eu diz qual e;
  - de fora, cada pessoa ve a dela e as do escritorio, e a dela abre
    primeiro; a caixa de outra pessoa da 403; a janela do servidor ve todas;
  - o e-mail enviado de fora vai para a fila ja com a conta de quem pediu;
  - a renovacao do token usa o cliente que emitiu (o web);
  - a conta Google da vez e a da pessoa; o cache da agenda e por conta;
  - um e-mail que ja e conta do escritorio nao vira de ninguem.

    PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tests/test_e3b_google_da_pessoa.py
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
TMP = Path(tempfile.mkdtemp(prefix="paulus-e3b-"))
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
    return b({"alg": "RS256"}) + "." + b(corpo) + ".x"


def test_http() -> None:
    print("\no Google de cada pessoa")
    import segredos

    if not segredos.disponivel():
        print("  pulado: sem DPAPI (fora do Windows)")
        return
    from fastapi.testclient import TestClient

    import api
    import correio_oauth
    from acesso.contas import codigo_totp
    from acesso.porteiro import PESSOA_DA_VEZ
    from correio_contas import Conta

    servico = api.estado.acesso_de_fora
    prefs = api.estado.prefs.dados["acesso_remoto"]
    servico.conferir_turnstile = lambda token, ip="": "ok" if token == "ok" else "recusado"
    # Aqui a Bia e o Caio entram por senha (o foco e o Google DELES): o "so
    # Google" do escritorio e testado em test_e3_google.py.
    prefs.update(ligado=True, hostname="moura.paulus.ia.br", so_google=False)
    local = TestClient(api.app, headers=api.cabecalho_local())
    respostas = {}
    servico.google.trocar = lambda code, verificador, cred: respostas.get(code, {"error": "invalid_grant"})

    # A conta de e-mail do escritorio (dono 0), como ja existe hoje.
    escritorio = Conta(id="esc1", email="escritorio@moura.adv.br", imap_host="imap.moura.adv.br",
                       smtp_host="smtp.moura.adv.br")
    api.estado.contas.itens.append(escritorio)
    api.estado.contas.lembrar("esc1", "senha-do-escritorio")
    passo = int(time.time() // 30) - 1

    def entrar(nome, email, papel="colaborador"):
        c = servico.contas.criar(nome, email, papel, "senha-forte-" + nome.lower())
        servico.contas.confirmar_totp(c["conta"]["id"], codigo_totp(c["segredo"], passo))
        f = TestClient(api.app, base_url="https://moura.paulus.ia.br", headers={"Cf-Connecting-IP": "200.5.5.5"},
                       follow_redirects=False)
        pend = f.post("/api/acesso/entrar", json={"email": email, "senha": "senha-forte-" + nome.lower(),
                                                 "turnstile": "ok"}).json()["pendente"]
        r = f.post("/api/acesso/entrar/codigo", json={"pendente": pend, "codigo": codigo_totp(c["segredo"], passo + 1)})
        f.headers["X-PAULUS-CSRF"] = r.json()["csrf"]
        return c["conta"]["id"], f

    try:
        servico.contas.criar("Tita", "tita@moura.adv.br", "titular", "senha-da-tita-1")
        bia_id, bia = entrar("Bia", "bia@moura.adv.br")
        caio_id, caio = entrar("Caio", "caio@moura.adv.br")

        print("  conectar o proprio Google")
        anonimo = TestClient(api.app, base_url="https://moura.paulus.ia.br", headers={"Cf-Connecting-IP": "200.6.6.6"})
        r = anonimo.post("/api/acesso/google/iniciar", json={"finalidade": "servicos", "turnstile": "ok"})
        checar(r.status_code == 403, "sem estar dentro: 403", r.status_code)
        r = bia.post("/api/acesso/google/iniciar", json={"finalidade": "servicos"})
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(r.json().get("url", "")).query))
        checar(r.status_code == 200 and "https://mail.google.com/" in q.get("scope", "") and "calendar.events" in q.get("scope", "")
               and "drive.file" in q.get("scope", "") and q.get("access_type") == "offline",
               "o endereco pede e-mail, Agenda e Drive, offline", q.get("scope"))
        respostas["b1"] = {"id_token": _jwt(email="bia.souza@gmail.com", name="Bia Souza"), "access_token": "at-bia",
                           "refresh_token": "rt-bia", "expires_in": 3600,
                           "scope": "openid email https://mail.google.com/ https://www.googleapis.com/auth/calendar.events "
                                    "https://www.googleapis.com/auth/drive.file"}
        r = bia.get("/api/acesso/google/retorno", params={"code": "b1", "state": q["state"]})
        para = urllib.parse.unquote(r.headers.get("location", ""))
        checar(r.status_code == 303 and para == "/#google=bia.souza@gmail.com", "a volta: conectado", para)
        propria = api.estado.contas.por_email("bia.souza@gmail.com")
        checar(propria is not None and propria.dono == bia_id and propria.cliente == "google_web"
               and propria.autenticacao == "google", "vira a conta de e-mail DA Bia, pelo cliente web",
               propria and (propria.dono, propria.cliente))
        checar(bia.get("/api/acesso/eu").json().get("google") == "bia.souza@gmail.com", "/api/acesso/eu diz qual e")

        print("  quem ve o que")
        d = bia.get("/api/email/contas").json()
        emails = {c["email"] for c in d["contas"]}
        checar(emails == {"bia.souza@gmail.com", "escritorio@moura.adv.br"} and d["em_uso"] == propria.id,
               "a Bia ve a dela e a do escritorio, e a dela abre primeiro", (emails, d["em_uso"]))
        d = caio.get("/api/email/contas").json()
        checar({c["email"] for c in d["contas"]} == {"escritorio@moura.adv.br"}, "o Caio nao ve a da Bia",
               [c["email"] for c in d["contas"]])
        r = caio.get("/api/email/caixa", params={"conta_id": propria.id})
        checar(r.status_code == 403 and "outra pessoa" in r.json().get("detail", ""), "a caixa da Bia, pelo Caio: 403",
               r.text[:160])
        checar(len(local.get("/api/email/contas").json()["contas"]) == 2, "a janela do servidor ve todas")

        print("  enviar de fora")
        r = bia.post("/api/email/enviar", json={"para": "cliente@x.com", "assunto": "Oi", "corpo": "Teste"})
        pedido = r.json().get("pedido") or {}
        guardado = api.estado.fila.obter(pedido.get("id", ""))
        checar(r.status_code == 200 and guardado and guardado.dados.get("conta_id") == propria.id,
               "vai para a fila ja com a conta da Bia (e nao a 'em uso' do servidor)", r.text[:200])

        print("  o token e o Google da vez")
        chamados = []
        antes = correio_oauth.renovar
        correio_oauth.renovar = lambda prov, cred, rt, endpoint="": (chamados.append(cred["client_id"]) or
                                                                     {"access_token": "novo", "expira_em": time.time() + 3600})
        try:
            api.estado.contas._tokens.pop(propria.id, None)
            checar(api.estado.contas.credencial(propria) == "novo" and chamados == ["cliente-web.apps.googleusercontent.com"],
                   "a renovacao usa o cliente que emitiu (o web)", chamados)
        finally:
            correio_oauth.renovar = antes
        marca = PESSOA_DA_VEZ.set({"conta_id": bia_id, "nome": "Bia"})
        try:
            checar(api.estado.conta_google() is propria, "de fora, a conta Google da vez e a da Bia")
            checar(api.estado.google.quem() == "bia.souza@gmail.com", "e o cache da agenda e o dela")
            checar(api.estado.google_tem("drive") and api.estado.google_tem("agenda"), "com Agenda e Drive")
        finally:
            PESSOA_DA_VEZ.reset(marca)
        marca = PESSOA_DA_VEZ.set({"conta_id": caio_id, "nome": "Caio"})
        try:
            checar(api.estado.conta_google() is None, "o Caio, sem Google proprio, nao usa o da Bia")
        finally:
            PESSOA_DA_VEZ.reset(marca)
        checar(api.estado.conta_google() is None, "na janela do servidor, o Google pessoal da Bia nao e o do escritorio")

        print("  o e-mail do escritorio nao vira de ninguem")
        r = caio.post("/api/acesso/google/iniciar", json={"finalidade": "servicos"})
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(r.json()["url"]).query))
        respostas["c1"] = {"id_token": _jwt(email="escritorio@moura.adv.br"), "access_token": "x", "refresh_token": "y",
                           "expires_in": 3600, "scope": "openid email"}
        r = caio.get("/api/acesso/google/retorno", params={"code": "c1", "state": q["state"]})
        para = urllib.parse.unquote(r.headers.get("location", ""))
        checar(para.startswith("/#google-erro=") and api.estado.contas.obter("esc1").dono == 0,
               "conectar um e-mail do escritorio como pessoal: recusado", para)
    finally:
        prefs.update(ligado=False, hostname="", so_google=True)
        servico.__dict__.pop("conferir_turnstile", None)


def main() -> int:
    print("=" * 55)
    print("  E3b - e-mail, Agenda e Drive de quem entrou")
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
